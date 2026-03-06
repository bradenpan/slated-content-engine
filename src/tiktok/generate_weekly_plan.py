"""TikTok Weekly Content Plan Generator.

Generates 7 TikTok carousel specifications per week using Claude Sonnet.
This is the main orchestrator — it loads shared context, calls Claude with
the TikTok planning prompt, validates the output, and either:
- (plan-only mode) saves specs + writes Weekly Review tab for human approval
- (full mode) renders carousels, uploads to GCS, publishes to Content Queue

Input context:
1. strategy/current-strategy.md — Strategic direction
2. strategy/tiktok/attribute-taxonomy.json — Attribute weights for explore/exploit
3. analysis/weekly/latest — Most recent weekly analysis
4. data/content-memory-summary.md — Content memory (prevents repetition)
5. strategy/seasonal-calendar.json — Current seasonal window
6. strategy/brand-voice.md — Brand voice guidelines
"""

import json
import logging
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from src.shared.apis.claude_api import ClaudeAPI
from src.shared.apis.sheets_api import SheetsAPI
from src.shared.apis.slack_notify import SlackNotify
from src.shared.content_planner import (
    load_strategy_context,
    load_latest_analysis,
    get_current_seasonal_window,
)
from src.shared.content_memory import generate_content_memory_summary
from src.shared.paths import DATA_DIR, STRATEGY_DIR, TIKTOK_DATA_DIR
from src.tiktok.compute_attribute_weights import load_taxonomy
from src.shared.apis.gcs_api import GcsAPI
from src.tiktok.generate_carousels import generate_carousels
from src.tiktok.publish_content_queue import publish_content_queue

logger = logging.getLogger(__name__)

# Required keys in each carousel spec
REQUIRED_CAROUSEL_KEYS = [
    "carousel_id", "topic", "angle", "structure", "hook_type",
    "template_family", "hook_text", "content_slides", "cta_slide",
    "caption", "hashtags", "scheduled_date", "is_aigc",
]

# Valid template families (must match CarouselAssembler after hyphen translation)
VALID_TEMPLATE_FAMILIES = [
    "clean_educational", "dark_bold", "photo_forward", "comparison_grid",
]


def generate_plan(
    week_start_date: Optional[str] = None,
    claude: Optional[ClaudeAPI] = None,
    sheets: Optional[SheetsAPI] = None,
    slack: Optional[SlackNotify] = None,
    dry_run: bool = False,
    plan_only: bool = False,
) -> dict:
    """Generate the weekly TikTok carousel plan.

    Main orchestration function. Called by the GitHub Actions workflow.

    Args:
        week_start_date: ISO date string for the week start (Monday).
            Defaults to the current or next Monday.
        claude: ClaudeAPI instance.
        sheets: SheetsAPI instance for the TikTok spreadsheet.
        slack: SlackNotify instance.
        dry_run: If True, skip rendering, GCS upload, and Sheets write.
        plan_only: If True, stop after saving plan JSON and writing
            specs to the Weekly Review tab (no rendering or publishing).

    Returns:
        dict: The generated weekly plan with carousels array.
    """
    # Determine week start date
    if week_start_date:
        start_date = datetime.strptime(week_start_date, "%Y-%m-%d").date()
    else:
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        start_date = today + timedelta(days=days_until_monday) if days_until_monday > 0 else today

    week_number = start_date.isocalendar()[1]
    logger.info(
        "Generating TikTok weekly plan for week %d starting %s",
        week_number, start_date,
    )

    # Step 1: Load shared context
    strategy_context = load_strategy_context()
    logger.info("Loaded strategy context")

    # Step 2: Load latest analysis
    latest_analysis = load_latest_analysis()

    # Step 3: Generate content memory summary
    content_memory = generate_content_memory_summary(channel="tiktok")

    # Step 4: Determine seasonal window
    seasonal_calendar = strategy_context.get("seasonal_calendar", {})
    seasonal_context = get_current_seasonal_window(
        seasonal_calendar.get("seasons", [])
    )

    # Step 5: Load attribute taxonomy
    try:
        taxonomy = load_taxonomy()
    except FileNotFoundError:
        logger.warning("Attribute taxonomy not found, using defaults")
        taxonomy = {"dimensions": {}}

    # Step 6: Compute posting dates (one per day for 7 days starting Wednesday)
    post_start = start_date + timedelta(days=2)  # Wednesday
    posting_dates = "\n".join(
        f"- {(post_start + timedelta(days=i)).isoformat()} "
        f"({(post_start + timedelta(days=i)).strftime('%A')})"
        for i in range(7)
    )

    # Step 6.5: Fail-fast on missing Sheet ID (before expensive Claude/render calls)
    if not dry_run:
        tiktok_sheet_id = os.environ.get("TIKTOK_SPREADSHEET_ID", "")
        if not tiktok_sheet_id:
            raise ValueError(
                "TIKTOK_SPREADSHEET_ID env var not set. "
                "Set it before running plan generation to avoid wasted API calls."
            )

    # Step 7: Call Claude to generate the plan
    claude = claude or ClaudeAPI()
    try:
        plan = _call_claude_for_plan(
            claude=claude,
            strategy_context=strategy_context,
            content_memory=content_memory,
            latest_analysis=latest_analysis,
            seasonal_context=seasonal_context,
            taxonomy=taxonomy,
            week_number=week_number,
            posting_dates=posting_dates,
        )
    except Exception as e:
        logger.error("Claude plan generation failed: %s", e)
        try:
            _slack = slack or SlackNotify()
            _slack.notify_failure(
                "tiktok_generate_weekly_plan",
                f"Claude plan generation failed: {e}",
            )
        except Exception:
            pass
        raise

    # Step 8: Validate the plan
    _validate_plan(plan, taxonomy)

    # Step 10: Save plan JSON locally
    TIKTOK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    plan_filename = f"weekly-plan-{start_date.isoformat()}.json"
    plan_path = TIKTOK_DATA_DIR / plan_filename
    tmp_path = plan_path.with_suffix(".tmp")
    try:
        tmp_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp_path.replace(plan_path)
        logger.info("Saved plan to %s", plan_path)
    except OSError as e:
        logger.error("Failed to write plan file: %s", e)
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    if plan_only:
        # Write specs to Weekly Review tab and return (no rendering)
        if not dry_run:
            try:
                tiktok_sheet_id = os.environ.get("TIKTOK_SPREADSHEET_ID", "")
                sheets = sheets or SheetsAPI(sheet_id=tiktok_sheet_id)
                sheets.write_tiktok_weekly_review(plan)
                logger.info("Published plan specs to TikTok Weekly Review tab")
            except Exception as e:
                logger.error("Failed to publish to Weekly Review: %s", e)
                raise

        logger.info(
            "Plan-only mode: %d carousel specs saved. Awaiting review.",
            len(plan.get("carousels", [])),
        )
        return plan

    # --- Full pipeline (rendering + publish) below ---
    # NOTE: This code path is broken between Phase A and Phase D
    # (Step 9 removed but generate_carousels still expects _image_prompt).
    # Phase B switches the cron to --plan-only so this path is never called.

    # Step 11: Render carousels
    rendered = generate_carousels(plan, dry_run=dry_run)

    # Enrich plan with render results
    plan["_rendered"] = [
        {
            "carousel_id": r.get("carousel_id"),
            "slide_count": r.get("slide_count", 0),
            "rendered_slides": r.get("rendered_slides", []),
        }
        for r in rendered
    ]
    # Re-save plan with render data
    try:
        tmp_path.write_text(
            json.dumps(plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        tmp_path.replace(plan_path)
    except OSError as e:
        logger.error("Failed to re-save plan with render data: %s", e)

    # Step 12: Upload rendered slides to GCS
    slide_preview_urls = {}
    if not dry_run:
        try:
            gcs = GcsAPI()
            if gcs.is_available:
                for carousel in rendered:
                    carousel_id = carousel.get("carousel_id", "")
                    slide_paths = carousel.get("rendered_slides", [])
                    if not carousel_id or not slide_paths:
                        continue

                    gcs_urls = []
                    for i, slide_path in enumerate(slide_paths):
                        remote_name = f"tiktok/{carousel_id}/slide-{i}.png"
                        url = gcs.upload_image(Path(slide_path), remote_name)
                        if url:
                            gcs_urls.append(url)

                    if gcs_urls:
                        carousel["slide_urls"] = gcs_urls
                        carousel["slide_count"] = len(gcs_urls)
                        slide_preview_urls[carousel_id] = gcs_urls[0]
                        logger.info(
                            "Uploaded %d/%d slides for %s to GCS",
                            len(gcs_urls), len(slide_paths), carousel_id,
                        )
            else:
                logger.warning("GCS not available, skipping slide upload")
        except Exception as e:
            logger.error("Failed to upload slides to GCS: %s", e)
            for carousel in rendered:
                carousel["gcs_upload_failed"] = True

    # Step 13: Publish to Google Sheet
    if not dry_run:
        try:
            tiktok_sheet_id = os.environ.get("TIKTOK_SPREADSHEET_ID", "")
            sheets = sheets or SheetsAPI(sheet_id=tiktok_sheet_id)
            publish_content_queue(rendered, slide_urls=slide_preview_urls, sheets=sheets)
            logger.info("Published to TikTok Google Sheet")
        except Exception as e:
            logger.error("Failed to publish to Google Sheets: %s", e)
            raise

    # Step 14: Slack notification
    try:
        slack = slack or SlackNotify()
        num_carousels = len(plan.get("carousels", []))
        num_rendered = sum(1 for r in rendered if r.get("rendered_slides"))
        slack.notify(
            f"TikTok plan generated: {num_carousels} carousels "
            f"({num_rendered} rendered) for week of {start_date}",
        )
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    return plan


def _call_claude_for_plan(
    claude: ClaudeAPI,
    strategy_context: dict,
    content_memory: str,
    latest_analysis: str,
    seasonal_context: str,
    taxonomy: dict,
    week_number: int,
    posting_dates: str,
) -> dict:
    """Call Claude with the TikTok weekly plan prompt."""
    plan = claude.generate_tiktok_plan(
        strategy_doc=strategy_context.get("strategy_doc", ""),
        content_memory=content_memory,
        latest_analysis=latest_analysis,
        seasonal_context=seasonal_context,
        taxonomy=taxonomy,
        week_number=week_number,
        posting_dates=posting_dates,
    )

    if not isinstance(plan, dict):
        raise ValueError(
            f"Plan must be a dict, got {type(plan).__name__}. "
            "Claude may have returned an unexpected response format."
        )

    if "carousels" not in plan:
        raise ValueError(
            "Plan is missing 'carousels' key. "
            "Claude may have returned different key names."
        )

    if not isinstance(plan["carousels"], list) or not plan["carousels"]:
        raise ValueError("Plan 'carousels' must be a non-empty list.")

    return plan


def _validate_plan(plan: dict, taxonomy: dict) -> None:
    """Validate plan structure and taxonomy compliance.

    Three validation layers:
    1. Structural (hard fail): required keys present, correct types
    2. Taxonomy (warning): attribute values exist in taxonomy
    3. Quality (warning): content length, diversity
    """
    carousels = plan.get("carousels", [])
    dimensions = taxonomy.get("dimensions", {})

    for i, carousel in enumerate(carousels):
        # Default image_prompts to empty list if not provided
        carousel.setdefault("image_prompts", [])

        # Layer 1: Structural validation
        missing = [k for k in REQUIRED_CAROUSEL_KEYS if k not in carousel]
        if missing:
            raise ValueError(
                f"Carousel {i} missing required keys: {missing}"
            )

        # Layer 2: Taxonomy + template family validation
        for dim_name in ("topic", "angle", "structure", "hook_type"):
            value = carousel.get(dim_name, "")
            dim = dimensions.get(dim_name, {})
            valid_attrs = list(dim.get("attributes", {}).keys())
            if valid_attrs and value not in valid_attrs:
                logger.warning(
                    "Carousel %s has invalid %s='%s'. Valid: %s",
                    carousel.get("carousel_id", i),
                    dim_name, value, valid_attrs,
                )

        family = carousel.get("template_family", "")
        if family not in VALID_TEMPLATE_FAMILIES:
            logger.warning(
                "Carousel %s has invalid template_family='%s'. Valid: %s",
                carousel.get("carousel_id", i),
                family, VALID_TEMPLATE_FAMILIES,
            )

        # Layer 2b: Image prompts validation
        image_prompts = carousel.get("image_prompts", [])
        if len(image_prompts) > 3:
            logger.warning(
                "Carousel %s has %d image_prompts (max 3)",
                carousel.get("carousel_id", i), len(image_prompts),
            )
        if family not in ("photo_forward", "photo-forward") and image_prompts:
            logger.warning(
                "Carousel %s is '%s' but has %d image_prompts (should be empty)",
                carousel.get("carousel_id", i), family, len(image_prompts),
            )
        content_slide_count = len(carousel.get("content_slides") or [])
        cta_index = content_slide_count + 1
        for ip in image_prompts:
            if ip.get("slide_index") == cta_index:
                logger.warning(
                    "Carousel %s has image_prompt targeting CTA slide (index %d)",
                    carousel.get("carousel_id", i), cta_index,
                )

        # Layer 3: Quality checks
        content_slides = carousel.get("content_slides") or []
        if not isinstance(content_slides, list):
            logger.warning(
                "Carousel %s content_slides is %s, expected list",
                carousel.get("carousel_id", i), type(content_slides).__name__,
            )
            content_slides = []
        if len(content_slides) < 2:
            logger.warning(
                "Carousel %s has only %d content slides (recommend 3-7)",
                carousel.get("carousel_id", i), len(content_slides),
            )

        hook_text = carousel.get("hook_text") or ""
        if len(hook_text.split()) > 15:
            logger.warning(
                "Carousel %s hook_text is %d words (recommend ≤15)",
                carousel.get("carousel_id", i), len(hook_text.split()),
            )

    logger.info("Plan validation complete: %d carousels checked", len(carousels))


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Generate TikTok weekly plan")
    parser.add_argument("--week-start", help="Week start date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Skip rendering and Sheets write")
    parser.add_argument("--plan-only", action="store_true", help="Generate plan specs only (no rendering)")
    parser.add_argument("--check-plan-status", action="store_true",
                        help="Check Weekly Review B3 status and exit. "
                             "Exit 0 if safe to generate, exit 78 if review in progress.")
    args = parser.parse_args()

    if args.check_plan_status:
        import sys
        tiktok_sheet_id = os.environ.get("TIKTOK_SPREADSHEET_ID", "")
        if not tiktok_sheet_id:
            print("TIKTOK_SPREADSHEET_ID not set — treating as first run, safe to proceed.")
            sys.exit(0)
        sheets = SheetsAPI(sheet_id=tiktok_sheet_id)
        status = sheets.read_tiktok_plan_status()
        if status in (None, "", "idle", "rejected"):
            print(f"Plan status is '{status}' — safe to generate new plan.")
            sys.exit(0)
        else:
            print(f"Plan status is '{status}' — review in progress, skipping generation.")
            sys.exit(78)

    print("Generating TikTok weekly content plan...")
    result = generate_plan(
        week_start_date=args.week_start,
        dry_run=args.dry_run,
        plan_only=args.plan_only,
    )
    carousels = result.get("carousels", [])
    print(f"Generated plan with {len(carousels)} carousels")
    for c in carousels:
        print(f"  {c.get('carousel_id')}: {c.get('topic')} / {c.get('angle')} [{c.get('template_family')}]")
