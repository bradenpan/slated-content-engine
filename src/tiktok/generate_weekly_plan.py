"""TikTok Weekly Content Plan Generator.

Generates 7 TikTok carousel specifications per week using Claude Sonnet.
This is the main orchestrator for Phase 10 — it loads shared context,
calls Claude with the TikTok planning prompt, validates the output,
renders carousels, and publishes to the TikTok Google Sheet.

Input context:
1. strategy/current-strategy.md — Strategic direction
2. strategy/tiktok/attribute-taxonomy.json — Attribute weights for explore/exploit
3. analysis/weekly/latest — Most recent weekly analysis
4. data/content-memory-summary.md — Content memory (prevents repetition)
5. strategy/seasonal-calendar.json — Current seasonal window
6. strategy/brand-voice.md — Brand voice guidelines

Output: 7 carousel specs rendered to PNGs and published to TikTok Google Sheet.
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
from src.shared.paths import DATA_DIR, STRATEGY_DIR
from src.tiktok.compute_attribute_weights import load_taxonomy
from src.shared.apis.gcs_api import GcsAPI
from src.tiktok.generate_carousels import generate_carousels
from src.tiktok.publish_content_queue import publish_content_queue

logger = logging.getLogger(__name__)

TIKTOK_DATA_DIR = DATA_DIR / "tiktok"

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

    # Step 9: Generate image prompts for photo-forward carousels
    for carousel in plan.get("carousels", []):
        if carousel.get("template_family") in ("photo_forward", "photo-forward"):
            if not dry_run:
                try:
                    image_prompt_result = claude.generate_tiktok_image_prompt(
                        carousel_spec=carousel,
                    )
                    carousel["_image_prompt"] = image_prompt_result.get(
                        "image_prompt", ""
                    )
                except Exception as e:
                    logger.error(
                        "Failed to generate image prompt for %s: %s",
                        carousel.get("carousel_id"), e,
                    )

    # Step 10: Render carousels
    rendered = generate_carousels(plan, dry_run=dry_run)

    # Step 11: Save plan JSON locally
    TIKTOK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    plan_filename = f"weekly-plan-{start_date.isoformat()}.json"
    plan_path = TIKTOK_DATA_DIR / plan_filename
    tmp_path = plan_path.with_suffix(".tmp")
    try:
        # Enrich plan with render results before saving
        plan["_rendered"] = [
            {
                "carousel_id": r.get("carousel_id"),
                "slide_count": r.get("slide_count", 0),
                "rendered_slides": r.get("rendered_slides", []),
            }
            for r in rendered
        ]
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
            # Flag all carousels as having no GCS slides so downstream
            # code doesn't schedule dead URLs
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
    args = parser.parse_args()

    print("Generating TikTok weekly content plan...")
    result = generate_plan(
        week_start_date=args.week_start,
        dry_run=args.dry_run,
    )
    carousels = result.get("carousels", [])
    print(f"Generated plan with {len(carousels)} carousels")
    for c in carousels:
        print(f"  {c.get('carousel_id')}: {c.get('topic')} / {c.get('angle')} [{c.get('template_family')}]")
