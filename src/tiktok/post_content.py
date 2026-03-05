"""
TikTok Content Posting Script

Posts approved carousels from the schedule via Publer API.
Runs 3x daily via GitHub Actions cron (morning, afternoon, evening).

Posting modes:
- TIKTOK_POSTING_ENABLED=true: Full pipeline via Publer (import → schedule → post)
- TIKTOK_POSTING_ENABLED=false: Fallback mode (Slack with GCS links for manual upload)

Anti-bot jitter: random(0, 120) seconds (less than Pinterest; posting via Publer, not direct).

Idempotency: Checks content-log.jsonl via is_content_posted(carousel_id, "tiktok").

Error handling:
- On success: update Sheet status="posted", log to content-log.jsonl
- On failure: log error, Sheet status="failed", Slack alert
- After 3 failures for same carousel: flag for manual investigation

Schedule file: data/tiktok/carousel-schedule.json (written by promote_and_schedule.py)
"""

import json
import os
import time
import random
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from src.tiktok.apis.publer_api import PublerAPI, PublerAPIError
from src.shared.apis.sheets_api import SheetsAPI
from src.shared.apis.slack_notify import SlackNotify
from src.shared.paths import DATA_DIR
from src.shared.utils.content_log import append_content_log_entry, is_content_posted
from src.shared.utils.safe_get import safe_get
from src.shared.config import TIKTOK_JITTER_MAX, TIKTOK_MAX_POST_FAILURES

logger = logging.getLogger(__name__)

CAROUSEL_SCHEDULE_PATH = DATA_DIR / "tiktok" / "carousel-schedule.json"

ET = ZoneInfo("America/New_York")


def post_content(
    time_slot: str,
    date_override: Optional[str] = None,
    publer: Optional[PublerAPI] = None,
    sheets: Optional[SheetsAPI] = None,
    slack: Optional[SlackNotify] = None,
) -> dict:
    """Post approved TikTok carousels for the current time slot.

    Args:
        time_slot: "morning", "afternoon", or "evening".
        date_override: Optional YYYY-MM-DD to post for a specific date.

    Returns:
        dict: {posted_count, failed_count, skipped_count, manual_count, errors}
    """
    valid_slots = ("morning", "afternoon", "evening")
    if time_slot not in valid_slots:
        raise ValueError(f"Invalid time_slot: {time_slot}. Must be one of {valid_slots}")

    if date_override:
        datetime.strptime(date_override, "%Y-%m-%d")  # validate format

    posting_enabled = os.environ.get("TIKTOK_POSTING_ENABLED", "false").lower() == "true"
    results = {
        "posted_count": 0,
        "failed_count": 0,
        "skipped_count": 0,
        "manual_count": 0,
        "errors": [],
    }
    today_str = date_override or datetime.now(ET).date().isoformat()

    # Initialize services
    try:
        slack = slack or SlackNotify()
    except Exception:
        slack = None

    if posting_enabled and publer is None:
        try:
            publer = PublerAPI()
        except Exception as e:
            logger.error("Failed to initialize Publer API: %s", e)
            if slack:
                slack.notify_failure("tiktok_post_content", f"Publer init failed: {e}")
            raise

    # Load schedule
    carousels = load_carousel_schedule(today_str, time_slot)
    if not carousels:
        logger.info("No carousels scheduled for %s on %s", time_slot, today_str)
        if slack:
            slack.notify(f"No TikTok carousels scheduled for {time_slot} slot.", level="info")
        return results

    # Initialize sheets for status updates
    if sheets is None:
        try:
            tiktok_sheet_id = os.environ.get("TIKTOK_SPREADSHEET_ID", "")
            if tiktok_sheet_id:
                sheets = SheetsAPI(sheet_id=tiktok_sheet_id)
        except Exception as e:
            logger.warning("Could not initialize SheetsAPI: %s", e)
            sheets = None

    total = len(carousels)

    for i, carousel in enumerate(carousels):
        carousel_id = safe_get(carousel, "carousel_id", f"unknown-{i}")

        try:
            # Idempotency check
            if is_content_posted(carousel_id, "tiktok"):
                logger.info("Carousel %s already posted, skipping (idempotent)", carousel_id)
                results["skipped_count"] += 1
                continue

            # Apply jitter (skip for manual recovery)
            if not date_override:
                _apply_jitter(time_slot, i)

            if posting_enabled:
                # Full Publer pipeline
                # Write placeholder entry BEFORE Publer call to prevent double-posting
                # on crash-after-post. The placeholder uses publer_post_id="PENDING".
                placeholder_entry = _build_log_entry(carousel, carousel_id, today_str, time_slot, "PENDING")
                append_content_log_entry(placeholder_entry)

                try:
                    publer_post_id = _post_via_publer(publer, carousel)
                except Exception:
                    # Remove the PENDING placeholder on failure so retry is possible
                    _remove_pending_entry(carousel_id)
                    raise

                # Update content log with real publer_post_id
                _update_pending_entry(carousel_id, publer_post_id)

                # Update Sheet status
                if sheets:
                    try:
                        sheets.update_tiktok_content_status(
                            carousel_id, "posted", publer_post_id=publer_post_id,
                        )
                    except Exception as e:
                        logger.warning("Failed to update Sheet for %s: %s", carousel_id, e)

                results["posted_count"] += 1
                logger.info("Posted carousel %s (publer_id=%s)", carousel_id, publer_post_id)

            else:
                # Fallback mode: manual upload required
                gcs_urls = safe_get(carousel, "slide_urls", [])
                caption = safe_get(carousel, "caption", "")
                if slack:
                    slide_list = "\n".join(f"  {j+1}. {url}" for j, url in enumerate(gcs_urls))
                    slack.notify(
                        f"*TikTok Manual Upload Required*\n"
                        f"Carousel: `{carousel_id}`\n"
                        f"Caption: {caption[:200]}\n"
                        f"Slides:\n{slide_list}",
                        level="warning",
                    )

                # Log as manual upload required (publer_post_id="" so idempotency
                # check doesn't permanently skip this carousel on future retries)
                log_entry = _build_log_entry(carousel, carousel_id, today_str, time_slot, "")
                log_entry["manual_upload_required"] = True
                append_content_log_entry(log_entry)

                if sheets:
                    try:
                        sheets.update_tiktok_content_status(carousel_id, "manual_upload")
                    except Exception as e:
                        logger.warning("Failed to update Sheet for %s: %s", carousel_id, e)

                results["manual_count"] += 1
                logger.info("Carousel %s flagged for manual upload", carousel_id)

        except Exception as e:
            results["failed_count"] += 1
            error_msg = f"Carousel {carousel_id} failed: {e}"
            results["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)

            if sheets:
                try:
                    sheets.update_tiktok_content_status(
                        carousel_id, "failed", error_message=str(e),
                    )
                except Exception:
                    pass

            _record_failure(carousel_id, str(e))

    # Slack summary
    if slack:
        try:
            posted = results["posted_count"] + results["manual_count"]
            if results["failed_count"] > 0:
                level = "warning" if posted > 0 else "error"
                slack.notify(
                    f"TikTok {time_slot}: Posted {posted}/{total} carousels. "
                    f"{results['failed_count']} failed.",
                    level=level,
                )
            else:
                slack.notify(
                    f"TikTok {time_slot}: Posted {posted}/{total} carousels.",
                    level="info",
                )
            if results["errors"]:
                error_summary = "\n".join(results["errors"][:3])
                slack.notify_failure("tiktok_post_content", f"Errors in {time_slot} slot:\n{error_summary}")
        except Exception as e:
            logger.warning("Failed to send Slack notification: %s", e)

    return results


def _post_via_publer(publer: PublerAPI, carousel: dict) -> str:
    """Import slides and create a scheduled post via Publer.

    Returns the Publer post ID.
    """
    slide_urls = safe_get(carousel, "slide_urls", [])
    if not slide_urls:
        raise ValueError(f"Carousel {carousel.get('carousel_id')} has no slide_urls")

    # Step 1: Import media
    import_job_id = publer.import_media(slide_urls)
    import_result = publer.poll_job(import_job_id)
    media_ids = import_result.get("media_ids", [])
    if not media_ids:
        raise PublerAPIError(0, "Media import returned no media_ids", import_result)

    # Step 2: Create post
    caption = safe_get(carousel, "caption", "")
    hashtags = safe_get(carousel, "hashtags", [])
    if isinstance(hashtags, list):
        caption = f"{caption}\n\n{' '.join(hashtags)}".strip()

    title = safe_get(carousel, "topic", safe_get(carousel, "carousel_id", ""))
    scheduled_at = safe_get(carousel, "scheduled_at", datetime.now(ET).isoformat())

    post_job_id = publer.create_post(
        media_ids=media_ids,
        caption=caption,
        title=title,
        scheduled_at=scheduled_at,
    )
    post_result = publer.poll_job(post_job_id)

    publer_post_id = post_result.get("post_id", post_result.get("id", ""))
    if not publer_post_id:
        raise PublerAPIError(0, "Post creation returned no post_id", post_result)

    return publer_post_id


def _build_log_entry(
    carousel: dict,
    carousel_id: str,
    date_str: str,
    time_slot: str,
    publer_post_id: str,
) -> dict:
    """Build a content-log.jsonl entry for a posted carousel."""
    return {
        "channel": "tiktok",
        "pin_id": carousel_id,
        "publer_post_id": publer_post_id,
        "posted_date": date_str,
        "posted_slot": time_slot,
        "topic": safe_get(carousel, "topic", ""),
        "angle": safe_get(carousel, "angle", ""),
        "structure": safe_get(carousel, "structure", ""),
        "hook_type": safe_get(carousel, "hook_type", ""),
        "template_family": safe_get(carousel, "template_family", ""),
        "hook_text": safe_get(carousel, "hook_text", ""),
        "caption": safe_get(carousel, "caption", ""),
        "slide_count": safe_get(carousel, "slide_count", 0),
    }


def _remove_pending_entry(carousel_id: str) -> None:
    """Remove a PENDING placeholder entry from the content log after a posting failure."""
    from src.shared.utils.content_log import load_content_log, save_content_log
    entries = load_content_log()
    entries = [
        e for e in entries
        if not (e.get("pin_id") == carousel_id and e.get("publer_post_id") == "PENDING")
    ]
    save_content_log(entries)


def _update_pending_entry(carousel_id: str, publer_post_id: str) -> None:
    """Replace PENDING placeholder with actual publer_post_id after successful post."""
    from src.shared.utils.content_log import load_content_log, save_content_log
    entries = load_content_log()
    for entry in entries:
        if entry.get("pin_id") == carousel_id and entry.get("publer_post_id") == "PENDING":
            entry["publer_post_id"] = publer_post_id
            break
    save_content_log(entries)


def load_carousel_schedule(date_str: str, time_slot: str) -> list[dict]:
    """Load carousels scheduled for a specific date and time slot.

    Args:
        date_str: Date in YYYY-MM-DD format.
        time_slot: "morning", "afternoon", or "evening".

    Returns:
        list[dict]: Carousels scheduled for posting in this slot.
    """
    if not CAROUSEL_SCHEDULE_PATH.exists():
        logger.warning("Carousel schedule not found: %s", CAROUSEL_SCHEDULE_PATH)
        return []

    try:
        with open(CAROUSEL_SCHEDULE_PATH, "r", encoding="utf-8") as f:
            schedule = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load carousel schedule: %s", e)
        return []

    carousels = schedule if isinstance(schedule, list) else safe_get(schedule, "carousels", [])

    matching = [
        c for c in carousels
        if safe_get(c, "scheduled_date") == date_str
        and safe_get(c, "scheduled_slot") == time_slot
    ]

    logger.info("Loaded %d carousels for %s %s slot", len(matching), date_str, time_slot)
    return matching


def _apply_jitter(time_slot: str, carousel_index: int) -> None:
    """Sleep for a random duration to space out API calls."""
    today_str = datetime.now(ET).date().isoformat()
    seed_str = f"tiktok:{today_str}:{time_slot}:{carousel_index}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    jitter_seconds = rng.randint(0, TIKTOK_JITTER_MAX)
    logger.info(
        "Applying jitter for %s slot (carousel %d): sleeping %d seconds",
        time_slot, carousel_index, jitter_seconds,
    )
    time.sleep(jitter_seconds)


def _record_failure(carousel_id: str, error_msg: str) -> None:
    """Record a posting failure for permanent failure detection."""
    failures_path = DATA_DIR / "tiktok" / "posting-failures.json"
    failures_path.parent.mkdir(parents=True, exist_ok=True)

    failures = {}
    if failures_path.exists():
        try:
            with open(failures_path, "r", encoding="utf-8") as f:
                failures = json.load(f)
        except (json.JSONDecodeError, OSError):
            failures = {}

    entry = failures.get(carousel_id, {"count": 0, "errors": []})
    entry["count"] = entry.get("count", 0) + 1
    entry["errors"].append({
        "timestamp": datetime.now().isoformat(),
        "error": error_msg[:500],
    })
    entry["last_failure"] = datetime.now().isoformat()
    failures[carousel_id] = entry

    tmp = failures_path.with_suffix(".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2)
        tmp.replace(failures_path)
    except OSError as e:
        logger.warning("Could not write failures file: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass

    if entry["count"] >= TIKTOK_MAX_POST_FAILURES:
        logger.error(
            "Carousel %s has failed %d times. Flagging for manual investigation.",
            carousel_id, entry["count"],
        )
        try:
            slack = SlackNotify()
            slack.notify_failure(
                "tiktok_post_content",
                f"Carousel {carousel_id} has failed {entry['count']} times.\n"
                f"Last error: {error_msg[:300]}",
            )
        except Exception as e:
            logger.error("Failed to send failure alert for %s: %s", carousel_id, e)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    slot = sys.argv[1] if len(sys.argv) > 1 else "morning"

    date_override = None
    for arg in sys.argv[2:]:
        if arg.startswith("--date="):
            date_override = arg.split("=", 1)[1]

    if "--demo" in sys.argv:
        target_date = date_override or datetime.now(ET).date().isoformat()
        print(f"=== Demo mode: post_content('{slot}') ===")
        print(f"Date: {target_date}")
        print(f"Slot: {slot}")
        print(f"Posting enabled: {os.environ.get('TIKTOK_POSTING_ENABLED', 'false')}")
        carousels = load_carousel_schedule(target_date, slot)
        print(f"Scheduled carousels: {len(carousels)}")
        for c in carousels:
            cid = safe_get(c, "carousel_id", "?")
            print(f"  - {cid}: {safe_get(c, 'topic', 'N/A')[:50]}")
            print(f"    Already posted: {is_content_posted(cid, 'tiktok')}")
    else:
        target_date = date_override or datetime.now(ET).date().isoformat()
        print(f"Posting TikTok carousels for {slot} slot (date: {target_date})...")
        results = post_content(slot, date_override=date_override)
        print(f"Results: {json.dumps(results, indent=2)}")
