"""
Weekly Plan Regeneration Orchestrator

Handles plan-level feedback and regeneration. When a reviewer flags
blog posts in the Weekly Review sheet with status="regen" and provides
feedback, this script:

1. Reads regen requests from the Weekly Review sheet
2. Loads the current weekly plan JSON from disk
3. Identifies affected posts and their derived pins
4. Generates replacement posts/pins via Claude (with reviewer feedback)
5. Splices replacements into the plan
6. Saves the updated plan JSON
7. Re-writes the Weekly Review sheet (preserving B3/B4)
8. Resets B5 trigger to "idle"
9. Sends Slack notification

Triggered by:
- Apps Script: Weekly Review tab cell B5 = "regen" -> repository_dispatch
- GitHub Actions: regen-plan.yml workflow

Timing: Designed for the review phase BEFORE content generation (B3).
If triggered after content generation, the updated plan won't affect
already-generated content.
"""

import json
import logging
import sys
from collections import Counter
from pathlib import Path

from src.apis.claude_api import ClaudeAPI
from src.apis.sheets_api import SheetsAPI
from src.apis.slack_notify import SlackNotify
from src.generate_weekly_plan import load_content_memory
from src.utils.plan_utils import (
    find_latest_plan,
    load_plan,
    identify_replaceable_posts,
    splice_replacements,
)

logger = logging.getLogger(__name__)






def build_regen_violations(
    regen_requests: list[dict],
) -> list[dict]:
    """
    Convert sheet regen requests into the violation format expected by
    identify_replaceable_posts().

    Each regen request from the sheet maps to a targeted violation for
    the corresponding post_id.

    Args:
        regen_requests: Output from sheets.read_plan_regen_requests().

    Returns:
        list[dict]: Structured violations compatible with identify_replaceable_posts().
    """
    violations = []
    for req in regen_requests:
        post_id = req["post_id"]
        feedback = req.get("feedback", "")
        message = f"Post '{post_id}' flagged for regen by reviewer"
        if feedback:
            message += f": {feedback}"

        violations.append({
            "category": "reviewer_regen",
            "message": message,
            "post_id": post_id,
            "severity": "targeted",
        })

    return violations


def regen_plan() -> None:
    """
    Main orchestration function for plan-level regeneration.

    Reads regen requests from the Weekly Review sheet, generates
    replacement posts/pins, updates the plan, and notifies via Slack.
    """
    logger.info("Starting plan-level regeneration...")

    # Step 1: Read regen requests from Sheet
    sheets = SheetsAPI()
    regen_requests = sheets.read_plan_regen_requests()

    if not regen_requests:
        logger.info("No plan regen requests found. Nothing to do.")
        sheets.reset_plan_regen_trigger()
        return

    logger.info(
        "Found %d plan regen requests: %s",
        len(regen_requests),
        [r["post_id"] for r in regen_requests],
    )

    # Step 2: Load current weekly plan from disk
    plan_path = find_latest_plan()
    if not plan_path:
        raise FileNotFoundError(
            "No weekly plan files found. Run generate_weekly_plan.py first."
        )
    plan = load_plan(plan_path)

    # Step 3: Build violations from regen requests and identify replaceable posts
    violations = build_regen_violations(regen_requests)
    replaceable = identify_replaceable_posts(plan, violations)

    if not replaceable:
        logger.warning(
            "Could not identify replaceable posts for regen requests. "
            "Post IDs may not match the current plan."
        )
        sheets.reset_plan_regen_trigger()
        return

    logger.info(
        "Identified %d replaceable posts: %s",
        len(replaceable), list(replaceable.keys()),
    )

    # Step 4: Build context for replacement generation
    offending_post_ids = set(replaceable.keys())
    all_offending_pin_ids: set[str] = set()
    posts_to_replace = []
    all_slots = []

    for info in replaceable.values():
        post_with_violations = dict(info["post"])
        post_with_violations["_violations"] = [
            v["message"] for v in info["violations"]
        ]
        posts_to_replace.append(post_with_violations)
        all_slots.extend(info["slots"])
        all_offending_pin_ids.update(info["pin_ids"])

    # Build kept-plan context
    kept_posts = [
        p for p in plan.get("blog_posts", [])
        if p.get("post_id") not in offending_post_ids
    ]
    kept_pins = [
        p for p in plan.get("pins", [])
        if p.get("pin_id") not in all_offending_pin_ids
    ]

    plan_context = {
        "kept_post_topics": [p.get("topic", "") for p in kept_posts],
        "kept_pin_boards": dict(Counter(
            p.get("target_board", "") for p in kept_pins
        )),
        "kept_pin_pillars": dict(Counter(
            p.get("pillar", 0) for p in kept_pins
        )),
        "week_number": plan.get("week_number", ""),
        "date_range": plan.get("date_range", ""),
    }

    # Build reviewer feedback dict: post_id -> feedback string
    reviewer_feedback = {
        req["post_id"]: req.get("feedback", "")
        for req in regen_requests
        if req.get("feedback")
    }

    content_memory = load_content_memory()

    # Step 5: Call Claude to generate replacements with reviewer feedback
    claude = ClaudeAPI()
    try:
        replacements = claude.generate_replacement_posts(
            posts_to_replace=posts_to_replace,
            slots_to_fill=all_slots,
            plan_context=plan_context,
            content_memory=content_memory,
            negative_keywords=[],  # No additional negative keywords for reviewer regen
            recent_topics=[],  # Not filtering by recent topics for reviewer regen
            reviewer_feedback=reviewer_feedback,
        )
    except Exception as e:
        logger.error("Failed to generate replacement posts: %s", e)
        sheets.reset_plan_regen_trigger()
        raise

    # Step 6: Splice replacements into the plan
    updated_plan = splice_replacements(
        plan, replacements,
        offending_post_ids, all_offending_pin_ids,
    )

    # Step 7: Save updated plan JSON (overwrite the same file)
    plan_path.write_text(
        json.dumps(updated_plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved updated plan to %s", plan_path)

    # Step 8: Re-write Weekly Review sheet with updated plan, preserving B3/B4
    # Read current B3 (plan approval) and B4 (deploy status) before clearing
    try:
        plan_status = sheets.read_plan_approval_status()
    except Exception as e:
        logger.warning("Could not read plan approval status, defaulting to pending_review: %s", e)
        plan_status = "pending_review"

    try:
        deploy_status = sheets.read_deploy_status()
    except Exception as e:
        logger.warning("Could not read deploy status, defaulting to pending_review: %s", e)
        deploy_status = "pending_review"

    # Re-write the Weekly Review tab with the updated plan
    sheets.write_weekly_review(
        analysis_summary="Plan updated via reviewer feedback regen",
        content_plan=updated_plan,
        performance_data={},
    )

    # Restore B3 and B4 values that were cleared by write_weekly_review
    from src.apis.sheets_api import TAB_WEEKLY_REVIEW, WR_CELL_PLAN_STATUS
    sheets.write_cell(TAB_WEEKLY_REVIEW, WR_CELL_PLAN_STATUS, plan_status)

    sheets.write_deploy_status(status=deploy_status)

    logger.info("Re-wrote Weekly Review sheet with updated plan (B3=%s, B4=%s preserved)",
                plan_status, deploy_status)

    # Step 9: Reset B5 trigger to "idle"
    sheets.reset_plan_regen_trigger()

    # Step 10: Build summary for Slack notification
    replaced_posts_summary = []
    old_posts_by_id = {p.get("post_id", ""): p for p in plan.get("blog_posts", [])}
    new_posts_by_id = {p.get("post_id", ""): p for p in updated_plan.get("blog_posts", [])}

    for post_id in offending_post_ids:
        old_post = old_posts_by_id.get(post_id, {})
        new_post = new_posts_by_id.get(post_id, {})
        replaced_posts_summary.append({
            "post_id": post_id,
            "old_topic": old_post.get("topic", "unknown"),
            "new_topic": new_post.get("topic", "unknown"),
        })

    total_pins_affected = len(all_offending_pin_ids)

    try:
        slack = SlackNotify()
        slack.notify_plan_regen_complete(replaced_posts_summary, total_pins_affected)
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    logger.info(
        "Plan regen complete: %d posts replaced, %d pins affected.",
        len(replaced_posts_summary), total_pins_affected,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        regen_plan()
    except Exception as e:
        logger.error("Plan regen failed: %s", e, exc_info=True)
        sys.exit(1)
