"""
TikTok Carousel Scheduling

Reads approved carousels from the TikTok Google Sheet Content Queue,
distributes them across 7 days x 3 slots (morning/afternoon/evening),
resolves GCS slide URLs for each carousel, writes the schedule to
data/tiktok/carousel-schedule.json, and updates the Sheet status to
"scheduled".

Triggered via repository_dispatch after Sheet approval.
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from src.shared.apis.gcs_api import GcsAPI
from src.shared.apis.sheets_api import SheetsAPI
from src.shared.apis.slack_notify import SlackNotify
from src.shared.paths import DATA_DIR

logger = logging.getLogger(__name__)

CAROUSEL_SCHEDULE_PATH = DATA_DIR / "tiktok" / "carousel-schedule.json"
ET = ZoneInfo("America/New_York")

# Time slots in posting order
SLOTS = ["morning", "afternoon", "evening"]

# Maximum carousels per week (7 days x 3 slots)
MAX_WEEKLY_SLOTS = 7 * len(SLOTS)

# Slot -> posting hour/minute (ET) for scheduled_at timestamps
SLOT_HOURS = {
    "morning": (10, 0),
    "afternoon": (16, 0),
    "evening": (19, 0),
}


def promote_and_schedule(
    start_date: Optional[str] = None,
    sheets: Optional[SheetsAPI] = None,
    slack: Optional[SlackNotify] = None,
) -> dict:
    """Read approved carousels and distribute across a 7-day schedule.

    Args:
        start_date: Start date for scheduling (YYYY-MM-DD). Defaults to tomorrow.
        sheets: SheetsAPI instance for TikTok spreadsheet.
        slack: SlackNotify instance.

    Returns:
        dict: {scheduled_count, start_date, end_date}
    """
    # Initialize services
    if sheets is None:
        tiktok_sheet_id = os.environ.get("TIKTOK_SPREADSHEET_ID", "")
        if not tiktok_sheet_id:
            raise ValueError("TIKTOK_SPREADSHEET_ID env var not set.")
        sheets = SheetsAPI(sheet_id=tiktok_sheet_id)

    try:
        slack = slack or SlackNotify()
    except Exception:
        slack = None

    # Read approved carousels from Sheet
    approved = sheets.read_tiktok_approved_carousels()
    if not approved:
        logger.info("No approved carousels found in TikTok Content Queue.")
        if slack:
            slack.notify("No approved TikTok carousels to schedule.", level="info")
        return {"scheduled_count": 0, "start_date": None, "end_date": None}

    # Cap at max weekly slots to prevent slot collisions
    if len(approved) > MAX_WEEKLY_SLOTS:
        logger.warning(
            "Got %d approved carousels but only %d weekly slots. "
            "Scheduling first %d only.",
            len(approved), MAX_WEEKLY_SLOTS, MAX_WEEKLY_SLOTS,
        )
        approved = approved[:MAX_WEEKLY_SLOTS]

    logger.info("Found %d approved carousels to schedule.", len(approved))

    # Determine start date (default: tomorrow)
    if start_date:
        schedule_start = datetime.strptime(start_date, "%Y-%m-%d").date()
    else:
        schedule_start = (datetime.now(ET) + timedelta(days=1)).date()

    # Resolve GCS slide URLs for each carousel
    _resolve_slide_urls(approved)

    # Warn about carousels missing slide URLs (GCS unavailable or slide_count=0)
    missing_urls = [c.get("carousel_id", "?") for c in approved if not c.get("slide_urls")]
    if missing_urls:
        msg = (
            f"*TikTok Scheduling Warning*\n"
            f"{len(missing_urls)} carousel(s) have no slide URLs and cannot be posted: "
            f"{', '.join(missing_urls)}"
        )
        logger.warning(msg)
        if slack:
            slack.notify(msg, level="warning")

    # Distribute carousels across 7 days x 3 slots, round-robin
    schedule = []

    for i, carousel in enumerate(approved):
        day_offset = i // len(SLOTS)
        slot_index = i % len(SLOTS)

        scheduled_date = schedule_start + timedelta(days=day_offset)
        slot = SLOTS[slot_index]

        # Build timezone-aware scheduled_at (handles DST correctly)
        hour, minute = SLOT_HOURS[slot]
        scheduled_dt = datetime(
            scheduled_date.year, scheduled_date.month, scheduled_date.day,
            hour, minute, 0,
            tzinfo=ET,
        )
        scheduled_at = scheduled_dt.isoformat()

        schedule_entry = {
            **carousel,
            "scheduled_date": scheduled_date.isoformat(),
            "scheduled_slot": slot,
            "scheduled_at": scheduled_at,
        }
        schedule.append(schedule_entry)

    # Write schedule file
    CAROUSEL_SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CAROUSEL_SCHEDULE_PATH.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(schedule, f, indent=2, ensure_ascii=False)
        tmp.replace(CAROUSEL_SCHEDULE_PATH)
        logger.info("Wrote %d entries to %s", len(schedule), CAROUSEL_SCHEDULE_PATH)
    except OSError as e:
        logger.error("Failed to write schedule file: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    # Update Sheet status to "scheduled"
    for entry in schedule:
        carousel_id = entry.get("carousel_id", "")
        if carousel_id:
            try:
                sheets.update_tiktok_content_status(carousel_id, "scheduled")
            except Exception as e:
                logger.warning("Failed to update Sheet status for %s: %s", carousel_id, e)

    # Calculate date range
    end_date = schedule_start + timedelta(days=min(6, (len(approved) - 1) // len(SLOTS)))

    # Slack notification
    if slack:
        try:
            slack.notify(
                f"*TikTok Carousels Scheduled*\n"
                f"{len(schedule)} carousels scheduled for {schedule_start.isoformat()} to {end_date.isoformat()}",
                level="info",
            )
        except Exception as e:
            logger.warning("Failed to send Slack notification: %s", e)

    return {
        "scheduled_count": len(schedule),
        "start_date": schedule_start.isoformat(),
        "end_date": end_date.isoformat(),
    }


def _resolve_slide_urls(carousels: list[dict]) -> None:
    """Resolve GCS slide URLs for each carousel.

    Uses the deterministic GCS path convention: tiktok/{carousel_id}/slide-{i}.png
    Constructs URLs from carousel_id and slide_count without listing blobs.

    Modifies carousels in-place, adding "slide_urls" key.
    """
    try:
        gcs = GcsAPI()
    except Exception as e:
        logger.warning("Could not initialize GcsAPI for slide URL resolution: %s", e)
        return

    if not gcs.is_available:
        logger.warning("GCS not available, slide URLs will not be resolved")
        return

    for carousel in carousels:
        carousel_id = carousel.get("carousel_id", "")
        slide_count = carousel.get("slide_count", 0)
        try:
            slide_count = int(slide_count)
        except (ValueError, TypeError):
            slide_count = 0

        if not carousel_id or slide_count <= 0:
            continue

        urls = [
            gcs.get_public_url(f"tiktok/{carousel_id}/slide-{i}.png")
            for i in range(slide_count)
        ]
        carousel["slide_urls"] = urls
        logger.debug("Resolved %d slide URLs for %s", len(urls), carousel_id)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    start_date = None
    for arg in sys.argv[1:]:
        if arg.startswith("--start-date="):
            start_date = arg.split("=", 1)[1]

    print("TikTok Promote & Schedule")
    print("=========================")
    result = promote_and_schedule(start_date=start_date)
    print(f"Results: {json.dumps(result, indent=2)}")
