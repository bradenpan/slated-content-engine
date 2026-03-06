"""
TikTok Carousel Scheduling

Reads approved carousels from the TikTok Google Sheet Content Queue,
assigns them to time slots based on the scheduled_date from the plan,
resolves GCS slide URLs for each carousel, and MERGES them into the
existing carousel-schedule.json (preserving in-flight carousels from
prior weeks that haven't posted yet).

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
from src.shared.paths import DATA_DIR, TIKTOK_DATA_DIR
from src.shared.utils.plan_utils import find_latest_plan, load_plan
from src.shared.utils.safe_get import safe_get

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
    sheets: Optional[SheetsAPI] = None,
    slack: Optional[SlackNotify] = None,
) -> dict:
    """Read approved carousels, assign time slots using the plan's scheduled_date,
    and merge into the existing schedule (preserving in-flight carousels).

    Each carousel's scheduled_date comes from the plan (set during plan generation
    and preserved through enrichment). This function assigns a time slot
    (morning/afternoon/evening) via round-robin within each date, then merges
    the new entries with any existing in-flight entries from prior weeks.

    Args:
        sheets: SheetsAPI instance for TikTok spreadsheet.
        slack: SlackNotify instance.

    Returns:
        dict: {scheduled_count, carried_over_count, start_date, end_date}
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
        return {"scheduled_count": 0, "carried_over_count": 0, "start_date": None, "end_date": None}

    # Cap at max weekly slots to prevent slot collisions
    if len(approved) > MAX_WEEKLY_SLOTS:
        logger.warning(
            "Got %d approved carousels but only %d weekly slots. "
            "Scheduling first %d only.",
            len(approved), MAX_WEEKLY_SLOTS, MAX_WEEKLY_SLOTS,
        )
        approved = approved[:MAX_WEEKLY_SLOTS]

    logger.info("Found %d approved carousels to schedule.", len(approved))

    # Enrich approved carousels with full plan data (hashtags, angle, structure,
    # hook_type, hook_text, scheduled_date are not stored in the Content Queue
    # sheet but are needed by the posting pipeline and content log)
    approved = _enrich_from_plan(approved)

    # Resolve GCS slide URLs for each carousel
    _resolve_slide_urls(approved)

    # Warn about carousels missing slide URLs (GCS unavailable or slide_count=0)
    missing_urls = [safe_get(c, "carousel_id", "?") for c in approved if not c.get("slide_urls")]
    if missing_urls:
        msg = (
            f"*TikTok Scheduling Warning*\n"
            f"{len(missing_urls)} carousel(s) have no slide URLs and cannot be posted: "
            f"{', '.join(missing_urls)}"
        )
        logger.warning(msg)
        if slack:
            slack.notify(msg, level="warning")

    # Filter out carousels with no slide URLs (known to be unpostable)
    postable = [c for c in approved if c.get("slide_urls")]
    unpostable = [c for c in approved if not c.get("slide_urls")]
    if unpostable:
        for c in unpostable:
            cid = safe_get(c, "carousel_id", "?")
            logger.warning("Excluding carousel %s from schedule — no slide URLs", cid)
            try:
                sheets.update_tiktok_content_status(cid, "failed", error_message="No slide URLs")
            except Exception as e:
                logger.warning("Failed to update Sheet status for %s: %s", cid, e)

    # Assign time slots using the plan's scheduled_date (round-robin within each date)
    new_entries = _assign_time_slots(postable)

    # Merge with existing schedule: keep in-flight carousels from prior weeks
    new_ids = {safe_get(e, "carousel_id", "") for e in new_entries}
    carried_over = _load_carried_over(new_ids)

    combined = carried_over + new_entries

    # Write merged schedule file
    _write_schedule(combined)

    # Update Sheet status to "scheduled"
    for entry in new_entries:
        carousel_id = safe_get(entry, "carousel_id", "")
        if carousel_id:
            try:
                sheets.update_tiktok_content_status(carousel_id, "scheduled")
            except Exception as e:
                logger.warning("Failed to update Sheet status for %s: %s", carousel_id, e)

    # Calculate date range from new entries
    new_dates = sorted({safe_get(e, "scheduled_date", "") for e in new_entries} - {""})
    start_date_str = new_dates[0] if new_dates else None
    end_date_str = new_dates[-1] if new_dates else None

    # Slack notification
    if slack:
        try:
            carried_msg = f" ({len(carried_over)} carried over from prior week)" if carried_over else ""
            slack.notify(
                f"*TikTok Carousels Scheduled*\n"
                f"{len(new_entries)} carousels scheduled for "
                f"{start_date_str} to {end_date_str}{carried_msg}",
                level="info",
            )
        except Exception as e:
            logger.warning("Failed to send Slack notification: %s", e)

    return {
        "scheduled_count": len(new_entries),
        "carried_over_count": len(carried_over),
        "start_date": start_date_str,
        "end_date": end_date_str,
    }


def _assign_time_slots(approved: list[dict]) -> list[dict]:
    """Assign time slots to approved carousels using their plan-provided scheduled_date.

    Groups carousels by scheduled_date, then assigns morning/afternoon/evening
    slots round-robin within each date. Carousels missing a scheduled_date get
    a fallback of tomorrow + offset.

    Returns a new list of schedule entry dicts (does not mutate input).
    """
    from collections import defaultdict

    today_str = datetime.now(ET).date().isoformat()

    # Group by scheduled_date
    by_date: dict[str, list[dict]] = defaultdict(list)
    fallback_carousels = []
    for carousel in approved:
        sched_date = safe_get(carousel, "scheduled_date", "")
        if sched_date:
            by_date[sched_date].append(carousel)
        else:
            logger.warning(
                "Carousel %s has no scheduled_date — will use fallback",
                safe_get(carousel, "carousel_id", "?"),
            )
            fallback_carousels.append(carousel)

    # Assign fallback dates for carousels missing scheduled_date
    if fallback_carousels:
        fallback_start = (datetime.now(ET) + timedelta(days=1)).date()
        for i, carousel in enumerate(fallback_carousels):
            day_offset = i // len(SLOTS)
            fallback_date = (fallback_start + timedelta(days=day_offset)).isoformat()
            by_date[fallback_date].append(carousel)

    # Assign slots within each date, tracking occupied slots to prevent collisions
    entries = []
    occupied_slots: dict[str, set[str]] = {}  # date -> set of slot names
    for sched_date in sorted(by_date.keys()):
        carousels = by_date[sched_date]
        parsed_date = datetime.strptime(sched_date, "%Y-%m-%d").date()

        # Pre-populate occupied slots for this date
        if sched_date not in occupied_slots:
            occupied_slots[sched_date] = set()

        for i, carousel in enumerate(carousels):
            slot_index = i
            if slot_index >= len(SLOTS):
                # Overflow: find the next unoccupied slot across subsequent dates
                overflow_days = slot_index // len(SLOTS)
                slot = SLOTS[slot_index % len(SLOTS)]
                overflow_date = (parsed_date + timedelta(days=overflow_days)).isoformat()

                # Skip forward if the target slot is already occupied
                while overflow_date in occupied_slots and slot in occupied_slots[overflow_date]:
                    overflow_days += 1
                    overflow_date = (parsed_date + timedelta(days=overflow_days)).isoformat()

                logger.warning(
                    "Date %s has %d carousels but only %d slots — "
                    "carousel %s overflows to %s %s",
                    sched_date, len(carousels), len(SLOTS),
                    safe_get(carousel, "carousel_id", "?"), overflow_date, slot,
                )
                sched_date_entry = overflow_date
                parsed_date_entry = parsed_date + timedelta(days=overflow_days)
            else:
                slot = SLOTS[slot_index]
                sched_date_entry = sched_date
                parsed_date_entry = parsed_date

            # Track this slot as occupied
            occupied_slots.setdefault(sched_date_entry, set()).add(slot)

            hour, minute = SLOT_HOURS[slot]
            scheduled_dt = datetime(
                parsed_date_entry.year, parsed_date_entry.month, parsed_date_entry.day,
                hour, minute, 0,
                tzinfo=ET,
            )

            entries.append({
                **carousel,
                "scheduled_date": sched_date_entry,
                "scheduled_slot": slot,
                "scheduled_at": scheduled_dt.isoformat(),
            })

    return entries


def _load_carried_over(new_ids: set[str]) -> list[dict]:
    """Load existing schedule entries that should be preserved (carried over).

    Keeps entries whose scheduled_date is today or in the future AND whose
    carousel_id is NOT in the new batch (to avoid duplicates).
    """
    if not CAROUSEL_SCHEDULE_PATH.exists():
        return []

    try:
        with open(CAROUSEL_SCHEDULE_PATH, "r", encoding="utf-8") as f:
            existing = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load existing schedule for merge: %s", e)
        return []

    if not isinstance(existing, list):
        existing = existing.get("carousels", []) if isinstance(existing, dict) else []

    today_str = datetime.now(ET).date().isoformat()

    carried = []
    for entry in existing:
        cid = safe_get(entry, "carousel_id", "")
        sched_date = safe_get(entry, "scheduled_date", "")

        # Skip entries that are in the new batch (they'll be re-added)
        if cid in new_ids:
            continue
        # Skip entries with past dates (already posted or missed)
        if sched_date < today_str:
            continue

        carried.append(entry)

    if carried:
        logger.info(
            "Carrying over %d in-flight entries from existing schedule",
            len(carried),
        )

    return carried


def _write_schedule(schedule: list[dict]) -> None:
    """Write the merged schedule to carousel-schedule.json (atomic)."""
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


def _enrich_from_plan(approved: list[dict]) -> list[dict]:
    """Join approved carousels with plan JSON to recover fields lost in the Sheet round-trip.

    The Content Queue sheet only stores carousel_id, topic, template_family, caption,
    and slide_count. Fields like hashtags, angle, structure, hook_type, hook_text are
    needed by the posting pipeline and content log but are not in the sheet.
    """
    plan_path = find_latest_plan(data_dir=TIKTOK_DATA_DIR)
    if not plan_path:
        logger.warning("No plan JSON found — cannot enrich approved carousels with full spec data")
        return approved

    try:
        plan = load_plan(plan_path)
    except Exception as e:
        logger.warning("Failed to load plan JSON for enrichment: %s", e)
        return approved

    plan_by_id = {
        c.get("carousel_id", ""): c
        for c in plan.get("carousels", [])
    }

    enriched = []
    enrich_fields = [
        "hashtags", "angle", "structure", "hook_type", "hook_text", "is_aigc",
        "content_slides", "cta_slide", "image_prompts", "scheduled_date",
    ]
    for carousel in approved:
        cid = carousel.get("carousel_id", "")
        plan_spec = plan_by_id.get(cid)
        if plan_spec:
            for field in enrich_fields:
                if field not in carousel or carousel[field] is None:
                    val = plan_spec.get(field)
                    if val is not None:
                        carousel[field] = val
        else:
            logger.warning("Carousel %s not found in plan JSON — posting will have missing fields", cid)
        enriched.append(carousel)

    logger.info("Enriched %d carousels from plan JSON (%d matched)", len(enriched), sum(1 for c in enriched if plan_by_id.get(c.get("carousel_id", ""))))
    return enriched


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
        carousel_id = safe_get(carousel, "carousel_id", "")
        slide_count = safe_get(carousel, "slide_count", 0)
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

    print("TikTok Promote & Schedule")
    print("=========================")
    try:
        result = promote_and_schedule()
        print(f"Results: {json.dumps(result, indent=2)}")
    except Exception as e:
        logger.error("Promote & schedule failed: %s", e, exc_info=True)
        sys.exit(1)
