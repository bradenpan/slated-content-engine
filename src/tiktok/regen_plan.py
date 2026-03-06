"""TikTok Plan-Level Regeneration Orchestrator.

Handles carousel spec regeneration based on reviewer feedback in the
Weekly Review tab. When a reviewer sets a carousel's status to "regen"
(col J) with optional feedback (col K), this script:

1. Reads regen requests from the Weekly Review sheet
2. Loads the current plan JSON from disk
3. Parses feedback to determine action (direct edit vs. Claude regen)
4. Applies direct edits or calls Claude for regen (one call per carousel)
5. Re-writes the Weekly Review sheet with updated specs
6. Saves updated plan JSON to disk
7. Resets B5 trigger to "idle"
8. Sends Slack notification

Feedback parsing supports:
- "change hook to \"...\"" → direct text edit, no Claude call
- "change slide N to \"...\"" → direct text edit, no Claude call
- "regen hook" → Claude regenerates hook text only
- "regen slide N" → Claude regenerates specific content slide
- "regen" or empty → Claude replaces entire carousel spec
- Free-form text → falls through to full Claude regen with feedback as context

Triggered by:
- Apps Script: Weekly Review tab cell B5 = "regen" -> repository_dispatch
- GitHub Actions: tiktok-regen-plan.yml workflow
"""

import json
import logging
import os
import re
import sys

from src.shared.apis.claude_api import ClaudeAPI
from src.shared.apis.sheets_api import SheetsAPI
from src.shared.apis.slack_notify import SlackNotify
from src.shared.paths import TIKTOK_DATA_DIR
from src.shared.utils.plan_utils import find_latest_plan, load_plan
from src.tiktok.compute_attribute_weights import load_taxonomy
from src.tiktok.generate_weekly_plan import REQUIRED_CAROUSEL_KEYS, VALID_TEMPLATE_FAMILIES

logger = logging.getLogger(__name__)


def parse_feedback(feedback: str) -> dict:
    """Parse reviewer feedback into a structured action.

    Returns:
        dict with keys:
        - action: "direct_edit" | "targeted_regen" | "full_regen"
        - target: "hook" | "slide" (for direct_edit/targeted_regen)
        - index: int (1-based slide number, for slide targets)
        - text: str (replacement text, for direct_edit)
        - feedback: str (raw feedback, for full_regen with context)
    """
    feedback = (feedback or "").strip()

    if not feedback or feedback.lower() == "regen":
        return {"action": "full_regen"}

    # change hook to "..."
    m = re.match(r'change\s+hook\s+to\s+"(.+)"', feedback, re.IGNORECASE)
    if m:
        return {"action": "direct_edit", "target": "hook", "text": m.group(1)}

    # change slide N to "..."
    m = re.match(r'change\s+slide\s+(\d+)\s+to\s+"(.+)"', feedback, re.IGNORECASE)
    if m:
        return {"action": "direct_edit", "target": "slide", "index": int(m.group(1)), "text": m.group(2)}

    # regen hook
    m = re.match(r'^regen\s+hook$', feedback, re.IGNORECASE)
    if m:
        return {"action": "targeted_regen", "target": "hook"}

    # regen slide N
    m = re.match(r'^regen\s+slide\s+(\d+)$', feedback, re.IGNORECASE)
    if m:
        return {"action": "targeted_regen", "target": "slide", "index": int(m.group(1))}

    # Fallback: unrecognized feedback → full regen with raw feedback as context
    return {"action": "full_regen", "feedback": feedback}


def apply_direct_edit(carousel: dict, parsed: dict) -> tuple[bool, str]:
    """Apply a direct text edit to a carousel spec.

    Returns:
        (success, description) — False if the edit couldn't be applied
        (e.g., slide index out of range), in which case the caller
        should fall through to Claude regen.
    """
    if parsed["target"] == "hook":
        old = carousel.get("hook_text", "")
        carousel["hook_text"] = parsed["text"]
        return True, f"hook: \"{old}\" → \"{parsed['text']}\""

    if parsed["target"] == "slide":
        idx = parsed["index"] - 1  # Convert 1-based to 0-based
        slides = carousel.get("content_slides") or []
        if 0 <= idx < len(slides):
            slide = slides[idx]
            old = slide.get("headline", "") if isinstance(slide, dict) else str(slide)
            if isinstance(slide, dict):
                slide["headline"] = parsed["text"]
            else:
                slides[idx] = {"headline": parsed["text"]}
            return True, f"slide {parsed['index']}: \"{old}\" → \"{parsed['text']}\""
        else:
            return False, f"slide {parsed['index']}: index out of range (carousel has {len(slides)} content slides)"

    return False, "unknown target"


def regen_plan(
    claude: ClaudeAPI | None = None,
    sheets: SheetsAPI | None = None,
    slack: SlackNotify | None = None,
) -> None:
    """Main orchestration function for TikTok plan-level regeneration."""
    logger.info("Starting TikTok plan-level regeneration...")

    # Step 1: Read regen requests from Sheet
    tiktok_sheet_id = os.environ.get("TIKTOK_SPREADSHEET_ID", "")
    if not tiktok_sheet_id:
        raise ValueError("TIKTOK_SPREADSHEET_ID env var not set.")
    sheets = sheets or SheetsAPI(sheet_id=tiktok_sheet_id)
    regen_requests = sheets.read_tiktok_plan_regen_requests()

    if not regen_requests:
        logger.info("No TikTok plan regen requests found. Nothing to do.")
        sheets.reset_tiktok_plan_regen_trigger()
        return

    logger.info(
        "Found %d regen requests: %s",
        len(regen_requests),
        [r["carousel_id"] for r in regen_requests],
    )

    # Step 2: Load current plan from disk
    plan_path = find_latest_plan(data_dir=TIKTOK_DATA_DIR)
    if not plan_path:
        raise FileNotFoundError(
            "No TikTok weekly plan files found in data/tiktok/. "
            "Run generate_weekly_plan.py --plan-only first."
        )
    plan = load_plan(plan_path)
    carousels = plan.get("carousels", [])
    carousel_by_id = {c.get("carousel_id", ""): c for c in carousels}

    # Step 3: Load taxonomy for Claude regen calls
    try:
        taxonomy = load_taxonomy()
    except FileNotFoundError:
        logger.warning("Attribute taxonomy not found, using defaults")
        taxonomy = {"dimensions": {}}

    # Step 4: Parse feedback and categorize actions
    direct_edits = []       # (carousel_id, parsed, description)
    claude_regens = []      # (carousel_id, parsed)
    skipped = []            # carousel_ids not found in plan

    for req in regen_requests:
        cid = req["carousel_id"]
        if cid not in carousel_by_id:
            logger.warning("Carousel %s not found in plan, skipping", cid)
            skipped.append(cid)
            continue

        parsed = parse_feedback(req.get("feedback", ""))

        if parsed["action"] == "direct_edit":
            success, desc = apply_direct_edit(carousel_by_id[cid], parsed)
            if success:
                direct_edits.append((cid, parsed, desc))
                logger.info("Direct edit applied to %s: %s", cid, desc)
            else:
                # Out-of-range or unknown target — fall through to Claude regen
                logger.warning("Direct edit failed for %s: %s — falling back to Claude regen", cid, desc)
                claude_regens.append((cid, {"action": "full_regen", "feedback": req.get("feedback", "")}))
        else:
            claude_regens.append((cid, parsed))

    # Step 5: Claude regen (one call per carousel — failures don't block others)
    claude_successes = []
    claude_failures = []
    if claude_regens:
        claude = claude or ClaudeAPI()

        for cid, parsed in claude_regens:
            carousel = carousel_by_id[cid]
            kept = [c for c in carousels if c.get("carousel_id") != cid]

            target = "full"
            if parsed["action"] == "targeted_regen":
                if parsed["target"] == "hook":
                    target = "hook"
                elif parsed["target"] == "slide":
                    target = f"slide_{parsed['index']}"

            feedback_text = parsed.get("feedback", "")
            if not feedback_text and parsed["action"] == "targeted_regen":
                feedback_text = f"Regenerate {target} for this carousel."

            try:
                replacement = claude.regenerate_tiktok_carousel_spec(
                    carousel_to_replace=carousel,
                    feedback=feedback_text,
                    target=target,
                    kept_specs=kept,
                    taxonomy=taxonomy,
                )

                # Guard against list response (Claude may wrap in array)
                if isinstance(replacement, list):
                    replacement = replacement[0]

                # Preserve carousel_id and scheduled_date
                replacement["carousel_id"] = carousel["carousel_id"]
                replacement["scheduled_date"] = carousel.get("scheduled_date", "")

                # Default image_prompts if missing
                replacement.setdefault("image_prompts", [])

                # Validate replacement has required keys
                missing = [k for k in REQUIRED_CAROUSEL_KEYS if k not in replacement]
                if missing:
                    raise ValueError(
                        f"Claude regen for {cid} missing required keys: {missing}"
                    )

                # Normalize template_family (Claude may return hyphenated)
                tf = replacement.get("template_family", "")
                if "-" in tf:
                    tf = tf.replace("-", "_")
                    replacement["template_family"] = tf
                if tf not in VALID_TEMPLATE_FAMILIES:
                    raise ValueError(
                        f"Claude regen for {cid} has invalid template_family='{tf}'"
                    )

                # Coerce is_aigc to bool
                is_aigc = replacement.get("is_aigc")
                if not isinstance(is_aigc, bool):
                    if isinstance(is_aigc, str):
                        replacement["is_aigc"] = is_aigc.lower() in ("true", "1", "yes")
                    else:
                        replacement["is_aigc"] = bool(is_aigc)

                # Splice into carousels list
                for i, c in enumerate(carousels):
                    if c.get("carousel_id") == cid:
                        carousels[i] = replacement
                        carousel_by_id[cid] = replacement
                        break

                claude_successes.append((cid, target))
                logger.info("Claude regen complete for %s (target: %s)", cid, target)
            except Exception as e:
                claude_failures.append((cid, str(e)))
                logger.error("Claude regen failed for %s: %s", cid, e)

    # Step 6: Write Sheet first, then save JSON
    # Skip if nothing actually changed — preserves reviewer feedback in the Sheet
    if not direct_edits and not claude_successes:
        logger.info("No successful edits or regens — skipping Sheet write to preserve reviewer feedback")
    else:
        # Note: write_tiktok_weekly_review() resets B3 to pending_review,
        # which is correct — reviewer must re-review after regen.
        plan["carousels"] = carousels
        sheets.write_tiktok_weekly_review(plan)
        logger.info("Re-wrote Weekly Review tab with updated specs")

    # Defensive B5 reset — write_tiktok_weekly_review() already writes
    # B5=idle via row data, but this explicit call ensures it even if
    # _clear_and_write partially failed. Wrapped in try/except so a
    # failure here doesn't prevent the JSON save below.
    try:
        sheets.reset_tiktok_plan_regen_trigger()
    except Exception as e:
        logger.warning("Failed to reset B5 trigger (non-fatal): %s", e)

    # Save plan JSON (atomic write) — only if something changed
    if not direct_edits and not claude_successes:
        logger.info("No changes to save to plan JSON")
    else:
        tmp = plan_path.with_suffix(".tmp")
        try:
            tmp.write_text(
                json.dumps(plan, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(plan_path)
        except OSError:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        logger.info("Saved updated plan to %s", plan_path)

    # Step 7: Slack notification
    summary_parts = []
    if direct_edits:
        summary_parts.append(f"{len(direct_edits)} direct edit(s)")
    if claude_successes:
        targets = [t for _, t in claude_successes]
        summary_parts.append(f"{len(claude_successes)} Claude regen(s) ({', '.join(targets)})")
    if claude_failures:
        failed_ids = [cid for cid, _ in claude_failures]
        summary_parts.append(f"{len(claude_failures)} FAILED ({', '.join(failed_ids)})")
    if skipped:
        summary_parts.append(f"{len(skipped)} skipped (not in plan)")

    try:
        slack = slack or SlackNotify()
        slack.notify(
            f"TikTok plan regen complete: {' + '.join(summary_parts)}. "
            f"Review updated specs in Weekly Review tab.",
        )
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    logger.info(
        "TikTok plan regen complete: %d direct edits, %d Claude successes, %d Claude failures, %d skipped.",
        len(direct_edits), len(claude_successes), len(claude_failures), len(skipped),
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        regen_plan()
    except Exception as e:
        logger.error("TikTok plan regen failed: %s", e, exc_info=True)
        sys.exit(1)
