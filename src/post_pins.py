"""
Pin Posting Script

Posts approved pins from the posting queue via Pinterest API.
Runs 3x daily via GitHub Actions cron (morning, afternoon, evening).

Posting schedule:
- Morning (10am ET): 1 pin
- Afternoon (3pm ET): 1 pin
- Evening (8pm ET): 2 pins
Total: 4 pins/day, 28/week (Tue through Mon)

Anti-bot jitter:
1. Sleep for random(0, 900) seconds (0-15 min) at start of window
2. If posting multiple pins, space with random(300, 1200) seconds between
3. Jitter values seeded from date + slot (reproducible but non-repeating)

Idempotency: Checks content-log.jsonl before posting to prevent duplicates.

Error handling:
- On success: update Sheet status="posted", log to content-log.jsonl
- On failure: log error, Sheet status="failed", Slack alert
- After 3 failures for same pin: flag for manual investigation

Pin schedule file: data/pin-schedule.json (written by blog_deployer.py)
"""

import json
import time
import random
import hashlib
import logging
import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from src.apis.pinterest_api import PinterestAPI, PinterestAPIError
from src.apis.sheets_api import SheetsAPI
from src.apis.slack_notify import SlackNotify
from src.token_manager import TokenManager
from src.paths import PROJECT_ROOT, DATA_DIR, CONTENT_LOG_PATH, STRATEGY_DIR
from src.config import (
    INITIAL_JITTER_MAX,
    INTER_PIN_JITTER_MIN,
    INTER_PIN_JITTER_MAX,
    MAX_PIN_FAILURES,
)

logger = logging.getLogger(__name__)

PIN_SCHEDULE_PATH = DATA_DIR / "pin-schedule.json"
BOARD_STRUCTURE_PATH = STRATEGY_DIR / "board-structure.json"

# Timezone for scheduling logic (all dates are ET)
ET = ZoneInfo("America/New_York")

# Slot configuration: how many pins per slot
SLOT_PIN_COUNTS = {
    "morning": 1,
    "afternoon": 1,
    "evening": 2,
}


def post_pins(time_slot: str) -> dict:
    """
    Post approved pins for the current time slot.

    Steps:
    1. Refresh Pinterest token if needed
    2. Apply anti-bot jitter (random sleep)
    3. Load pin schedule and filter for today + slot
    4. Build board name -> board ID mapping
    5. For each pin:
       a. Check content-log.jsonl for idempotency
       b. Verify blog post URL is live
       c. Construct UTM-tagged link
       d. Create pin via Pinterest API
       e. Update content-log.jsonl and Google Sheet on success/failure
    6. Send Slack summary notification

    Args:
        time_slot: "morning", "afternoon", or "evening".

    Returns:
        dict: Results with posted_count, failed_count, skipped_count.
    """
    if time_slot not in SLOT_PIN_COUNTS:
        raise ValueError(f"Invalid time_slot: {time_slot}. Must be one of {list(SLOT_PIN_COUNTS.keys())}")

    results = {"posted_count": 0, "failed_count": 0, "skipped_count": 0, "errors": []}
    today_str = datetime.now(ET).date().isoformat()

    # Initialize services
    try:
        token_manager = TokenManager()
        access_token = token_manager.get_valid_token()
        pinterest = PinterestAPI(access_token=access_token)
        slack = SlackNotify()
    except Exception as e:
        logger.error("Failed to initialize services: %s", e)
        try:
            SlackNotify().notify_failure("post_pins", f"Service initialization failed: {e}")
        except Exception:
            pass
        raise

    # Apply initial jitter before posting
    apply_jitter(time_slot, pin_index=0)

    # Load pin schedule for today + slot
    pins_to_post = load_scheduled_pins(today_str, time_slot)
    if not pins_to_post:
        logger.info("No pins scheduled for %s on %s", time_slot, today_str)
        slack.notify_posting_complete(time_slot, 0, 0)
        return results

    # Build board name -> board ID mapping
    board_map = build_board_map(pinterest)

    # Initialize sheets for post log updates
    try:
        sheets = SheetsAPI()
    except Exception as e:
        logger.warning("Could not initialize SheetsAPI, post log updates will be skipped: %s", e)
        sheets = None

    total_pins = len(pins_to_post)

    for i, pin_data in enumerate(pins_to_post):
        pin_id = pin_data.get("pin_id", f"unknown-{i}")

        try:
            # Idempotency check
            if is_already_posted(pin_id):
                logger.info("Pin %s already posted, skipping (idempotent)", pin_id)
                results["skipped_count"] += 1
                continue

            # Inter-pin jitter (for 2nd+ pins in the same window)
            if i > 0:
                apply_jitter(time_slot, pin_index=i)

            # Resolve board ID from board name
            board_name = pin_data.get("board_name", pin_data.get("target_board", ""))
            board_id = board_map.get(board_name)
            if not board_id:
                # Try fuzzy matching (case-insensitive, strip whitespace)
                board_id = _fuzzy_board_lookup(board_name, board_map)

            if not board_id:
                raise ValueError(
                    f"Board '{board_name}' not found in Pinterest account. "
                    f"Available boards: {list(board_map.keys())}"
                )

            # Verify the blog post URL is live
            blog_url = pin_data.get("link", pin_data.get("blog_url", ""))
            if blog_url and not verify_url_is_live(blog_url):
                logger.warning("Blog URL not live: %s. Will proceed with posting anyway.", blog_url)

            # Construct UTM-tagged link
            link = construct_utm_link(
                blog_url=blog_url,
                board_name=board_name,
                pin_id=pin_id,
            )

            # Prepare image source
            image_base64 = None
            image_url = None
            image_path = pin_data.get("image_path")
            image_hosted_url = pin_data.get("image_url")

            if image_hosted_url:
                image_url = image_hosted_url
            elif image_path:
                image_path_obj = Path(image_path)
                if not image_path_obj.is_absolute():
                    image_path_obj = PROJECT_ROOT / image_path
                if image_path_obj.exists():
                    with open(image_path_obj, "rb") as f:
                        image_base64 = base64.b64encode(f.read()).decode("ascii")
                else:
                    raise FileNotFoundError(f"Pin image not found: {image_path_obj}")
            else:
                raise ValueError(f"Pin {pin_id} has no image_path or image_url")

            # Create pin via Pinterest API with retry logic
            pinterest_pin_id = _create_pin_with_retry(
                pinterest=pinterest,
                token_manager=token_manager,
                board_id=board_id,
                title=pin_data.get("title", ""),
                description=pin_data.get("description", ""),
                link=link,
                alt_text=pin_data.get("alt_text", ""),
                image_base64=image_base64,
                image_url=image_url,
            )

            # Success: update content log
            log_entry = {
                "pin_id": pin_id,
                "pinterest_pin_id": pinterest_pin_id,
                "posted_date": today_str,
                "posted_slot": time_slot,
                "board": board_name,
                "board_id": board_id,
                "title": pin_data.get("title", ""),
                "blog_slug": pin_data.get("blog_slug", ""),
                "blog_url": blog_url,
                "link": link,
                "pillar": pin_data.get("pillar"),
                "content_type": pin_data.get("content_type", ""),
                "funnel_layer": pin_data.get("funnel_layer", ""),
                "template": pin_data.get("template", pin_data.get("pin_template", "")),
                "primary_keyword": pin_data.get("primary_keyword", ""),
                "secondary_keywords": pin_data.get("secondary_keywords", []),
                "image_source": pin_data.get("image_source", ""),
                "image_id": pin_data.get("image_id", ""),
                "pin_type": pin_data.get("pin_type", "primary"),
                "treatment_number": pin_data.get("treatment_number", 1),
                "source_post_id": pin_data.get("source_post_id", ""),
                "impressions": 0,
                "saves": 0,
                "pin_clicks": 0,
                "outbound_clicks": 0,
                "save_rate": 0.0,
                "click_through_rate": 0.0,
                "last_analytics_pull": None,
            }
            append_to_content_log(log_entry)

            # Update Google Sheet post log
            if sheets:
                try:
                    sheets.update_pin_status(
                        pin_id=pin_id,
                        status="posted",
                        pinterest_pin_id=pinterest_pin_id,
                    )
                except Exception as e:
                    logger.warning("Failed to update Google Sheet for pin %s: %s", pin_id, e)

            results["posted_count"] += 1
            logger.info(
                "Successfully posted pin %s (pinterest_id=%s) to board '%s'",
                pin_id, pinterest_pin_id, board_name,
            )

        except Exception as e:
            results["failed_count"] += 1
            error_msg = f"Pin {pin_id} failed: {e}"
            results["errors"].append(error_msg)
            logger.error(error_msg, exc_info=True)

            # Update sheet with failure
            if sheets:
                try:
                    sheets.update_pin_status(
                        pin_id=pin_id,
                        status="failed",
                        error_message=str(e),
                    )
                except Exception:
                    pass

            # Record failure count for permanent failure detection
            _record_failure(pin_id, str(e))

    # Send Slack summary
    try:
        if results["failed_count"] > 0:
            slack.notify_posting_complete(time_slot, results["posted_count"], total_pins)
            if results["errors"]:
                error_summary = "\n".join(results["errors"][:3])
                slack.notify_failure("post_pins", f"Errors in {time_slot} slot:\n{error_summary}")
        else:
            slack.notify_posting_complete(time_slot, results["posted_count"], total_pins)
    except Exception as e:
        logger.warning("Failed to send Slack notification: %s", e)

    return results


def apply_jitter(time_slot: str, pin_index: int = 0) -> None:
    """
    Sleep for a random duration to avoid bot detection.

    First pin: random(0, 5400) seconds from window start.
    Subsequent pins: random(300, 1200) seconds between each.

    The jitter seed is derived from date + slot + pin_index, so it is
    reproducible for debugging but different every day.

    Args:
        time_slot: Current time slot.
        pin_index: Index of the pin within this window (0-based).
    """
    today_str = datetime.now(ET).date().isoformat()
    seed_str = f"{today_str}:{time_slot}:{pin_index}"
    seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)

    if pin_index == 0:
        # Initial jitter: 0 to 90 minutes
        jitter_seconds = rng.randint(0, INITIAL_JITTER_MAX)
        logger.info(
            "Applying initial jitter for %s slot: sleeping %d seconds (%.1f minutes)",
            time_slot, jitter_seconds, jitter_seconds / 60,
        )
    else:
        # Inter-pin jitter: 5-20 minutes
        jitter_seconds = rng.randint(INTER_PIN_JITTER_MIN, INTER_PIN_JITTER_MAX)
        logger.info(
            "Applying inter-pin jitter (pin %d): sleeping %d seconds (%.1f minutes)",
            pin_index, jitter_seconds, jitter_seconds / 60,
        )

    time.sleep(jitter_seconds)




def is_already_posted(pin_id: str) -> bool:
    """
    Check if a pin has already been posted (idempotency check).

    Scans content-log.jsonl for an entry with this pin_id that has
    a non-null pinterest_pin_id field.

    Args:
        pin_id: Internal pin ID (e.g., "W12-01").

    Returns:
        bool: True if pin already has a pinterest_pin_id in the content log.
    """
    if not CONTENT_LOG_PATH.exists():
        return False

    try:
        with open(CONTENT_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("pin_id") == pin_id and entry.get("pinterest_pin_id"):
                        return True
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        logger.warning("Could not read content log for idempotency check: %s", e)

    return False


def append_to_content_log(pin_data: dict) -> None:
    """
    Append a pin record to content-log.jsonl.

    Creates the file if it doesn't exist. Each line is a complete JSON object.

    Args:
        pin_data: Pin metadata to log.
    """
    CONTENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(CONTENT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(pin_data, ensure_ascii=False) + "\n")
        logger.debug("Appended pin %s to content log", pin_data.get("pin_id"))
    except OSError as e:
        logger.error("Failed to write to content log: %s", e)
        raise


def load_scheduled_pins(date_str: str, time_slot: str) -> list[dict]:
    """
    Load pins scheduled for a specific date and time slot.

    Reads from data/pin-schedule.json, which is written by blog_deployer.py
    during the deployment step. The schedule contains all approved pins
    for the week with their assigned dates and slots.

    Args:
        date_str: Date in YYYY-MM-DD format.
        time_slot: "morning", "afternoon", or "evening".

    Returns:
        list[dict]: Pins scheduled for posting in this slot.
    """
    if not PIN_SCHEDULE_PATH.exists():
        logger.warning("Pin schedule file not found: %s", PIN_SCHEDULE_PATH)
        return []

    try:
        with open(PIN_SCHEDULE_PATH, "r", encoding="utf-8") as f:
            schedule = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load pin schedule: %s", e)
        return []

    # The schedule is a list of pin objects with scheduled_date and scheduled_slot
    pins = schedule if isinstance(schedule, list) else schedule.get("pins", [])

    # Match pins for this date and slot. The evening slot is special:
    # Claude assigns "evening-1" and "evening-2" but the workflow calls with "evening".
    if time_slot == "evening":
        slot_matches = {"evening", "evening-1", "evening-2"}
    else:
        slot_matches = {time_slot}

    matching_pins = [
        pin for pin in pins
        if pin.get("scheduled_date") == date_str
        and pin.get("scheduled_slot") in slot_matches
    ]

    expected_count = SLOT_PIN_COUNTS.get(time_slot, 1)
    if len(matching_pins) != expected_count:
        logger.warning(
            "Expected %d pins for %s/%s, found %d",
            expected_count, date_str, time_slot, len(matching_pins),
        )

    logger.info("Loaded %d pins for %s %s slot", len(matching_pins), date_str, time_slot)
    return matching_pins


def build_board_map(pinterest: PinterestAPI) -> dict[str, str]:
    """
    Build a mapping of board names to board IDs.

    Calls pinterest_api.list_boards() and creates a name -> id lookup.
    This is called once per posting session and cached.

    Args:
        pinterest: Authenticated PinterestAPI instance.

    Returns:
        dict: Board name (str) -> board ID (str).
    """
    try:
        boards = pinterest.list_boards()
    except PinterestAPIError as e:
        logger.error("Failed to list boards: %s", e)
        raise

    board_map = {}
    for board in boards:
        name = board.get("name", "")
        board_id = board.get("id", "")
        if name and board_id:
            board_map[name] = board_id
            # Also store lowercase version for fuzzy matching
            board_map[name.lower()] = board_id

    logger.info("Built board map with %d boards", len(boards))
    return board_map


def _fuzzy_board_lookup(board_name: str, board_map: dict[str, str]) -> Optional[str]:
    """
    Try to find a board ID by fuzzy matching the board name.

    Attempts case-insensitive matching first, then partial matching.

    Args:
        board_name: The board name to look up.
        board_map: The board name -> ID mapping (includes lowercase keys).

    Returns:
        Optional board ID, or None if no match found.
    """
    # Case-insensitive exact match
    board_id = board_map.get(board_name.lower())
    if board_id:
        return board_id

    # Partial match: find boards containing the search term
    lower_name = board_name.lower()
    for key, bid in board_map.items():
        if lower_name in key.lower() or key.lower() in lower_name:
            logger.info("Fuzzy board match: '%s' -> '%s'", board_name, key)
            return bid

    return None


def construct_utm_link(blog_url: str, board_name: str, pin_id: str) -> str:
    """
    Construct a blog URL with UTM tracking parameters.

    Format: {blog_url}?utm_source=pinterest&utm_medium=organic
            &utm_campaign={board_name_slugified}&utm_content={pin_id}

    Args:
        blog_url: The base blog post URL.
        board_name: Pinterest board name (will be slugified).
        pin_id: Internal pin ID.

    Returns:
        str: Full URL with UTM parameters.
    """
    if not blog_url:
        return ""

    # Slugify the board name for the campaign parameter
    board_slug = re.sub(r"[^a-z0-9]+", "-", board_name.lower()).strip("-")

    separator = "&" if "?" in blog_url else "?"
    utm_params = (
        f"utm_source=pinterest"
        f"&utm_medium=organic"
        f"&utm_campaign={board_slug}"
        f"&utm_content={pin_id}"
    )

    return f"{blog_url}{separator}{utm_params}"


def verify_url_is_live(url: str, retries: int = 1) -> bool:
    """
    Verify that a blog post URL returns a 200 status.

    Performs a HEAD request with one retry on failure.

    Args:
        url: The URL to check.
        retries: Number of retries on non-200.

    Returns:
        bool: True if the URL is live (200 OK).
    """
    for attempt in range(retries + 1):
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                return True
            logger.warning(
                "URL check attempt %d: %s returned %d",
                attempt + 1, url, response.status_code,
            )
        except requests.RequestException as e:
            logger.warning("URL check attempt %d failed: %s", attempt + 1, e)

        if attempt < retries:
            time.sleep(2)

    return False


def _create_pin_with_retry(
    pinterest: PinterestAPI,
    token_manager: TokenManager,
    board_id: str,
    title: str,
    description: str,
    link: str,
    alt_text: str,
    image_base64: Optional[str] = None,
    image_url: Optional[str] = None,
) -> str:
    """
    Create a pin with retry logic for rate limits and auth failures.

    - On 429 (rate limit): wait using the retry-after header and retry
    - On 401 (auth): refresh token and retry once
    - On other errors: retry up to MAX_PIN_FAILURES times

    Args:
        pinterest: PinterestAPI instance.
        token_manager: TokenManager for auth refresh.
        board_id: Target board ID.
        title: Pin title.
        description: Pin description.
        link: Destination URL.
        alt_text: Image alt text.
        image_base64: Base64-encoded image (optional).
        image_url: Image URL (optional).

    Returns:
        str: The Pinterest-assigned pin ID.

    Raises:
        PinterestAPIError: After all retries are exhausted.
    """
    last_error = None

    for attempt in range(MAX_PIN_FAILURES):
        try:
            result = pinterest.create_pin(
                board_id=board_id,
                title=title,
                description=description,
                link=link,
                image_base64=image_base64,
                image_url=image_url,
                alt_text=alt_text,
            )
            return result.get("id", "")

        except PinterestAPIError as e:
            last_error = e

            if e.status_code == 429:
                # Rate limit: wait and retry
                wait_time = 60 * (attempt + 1)
                logger.warning(
                    "Rate limited on attempt %d/%d. Waiting %d seconds.",
                    attempt + 1, MAX_PIN_FAILURES, wait_time,
                )
                time.sleep(wait_time)
                continue

            elif e.status_code == 401:
                # Auth failure: refresh token and rebuild client
                logger.warning("Auth failure on attempt %d, refreshing token...", attempt + 1)
                try:
                    new_token = token_manager.get_valid_token()
                    pinterest.access_token = new_token
                    continue
                except Exception as refresh_err:
                    logger.error("Token refresh failed: %s", refresh_err)
                    raise e from refresh_err

            else:
                # Other error: retry with backoff
                wait_time = 5 * (attempt + 1)
                logger.warning(
                    "Pin creation failed (attempt %d/%d, HTTP %d): %s. Retrying in %ds.",
                    attempt + 1, MAX_PIN_FAILURES, e.status_code, e, wait_time,
                )
                time.sleep(wait_time)
                continue

    raise last_error or PinterestAPIError(0, "Pin creation failed after all retries")


def _record_failure(pin_id: str, error_msg: str) -> None:
    """
    Record a pin posting failure for permanent failure detection.

    Tracks failure count in a simple JSON file. After MAX_PIN_FAILURES
    consecutive failures for the same pin, sends a Slack alert for
    manual investigation.

    Args:
        pin_id: The failed pin ID.
        error_msg: The error message.
    """
    failures_path = DATA_DIR / "posting-failures.json"

    failures = {}
    if failures_path.exists():
        try:
            with open(failures_path, "r", encoding="utf-8") as f:
                failures = json.load(f)
        except (json.JSONDecodeError, OSError):
            failures = {}

    pin_failures = failures.get(pin_id, {"count": 0, "errors": []})
    pin_failures["count"] = pin_failures.get("count", 0) + 1
    pin_failures["errors"].append({
        "timestamp": datetime.now().isoformat(),
        "error": error_msg[:500],
    })
    pin_failures["last_failure"] = datetime.now().isoformat()
    failures[pin_id] = pin_failures

    try:
        with open(failures_path, "w", encoding="utf-8") as f:
            json.dump(failures, f, indent=2)
    except OSError as e:
        logger.warning("Could not write failures file: %s", e)

    # If permanently failed, send alert
    if pin_failures["count"] >= MAX_PIN_FAILURES:
        logger.error(
            "Pin %s has failed %d times. Marking as permanently failed.",
            pin_id, pin_failures["count"],
        )
        try:
            slack = SlackNotify()
            slack.notify_failure(
                "post_pins",
                f"Pin {pin_id} has failed {pin_failures['count']} times and needs manual investigation.\n"
                f"Last error: {error_msg[:300]}",
            )
        except Exception:
            pass


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    slot = sys.argv[1] if len(sys.argv) > 1 else "morning"

    if "--demo" in sys.argv:
        # Demo mode: show what would happen without actually posting
        print(f"=== Demo mode: post_pins('{slot}') ===")
        today_str = datetime.now(ET).date().isoformat()
        print(f"Date: {today_str}")
        print(f"Slot: {slot} (expected pins: {SLOT_PIN_COUNTS[slot]})")
        pins = load_scheduled_pins(today_str, slot)
        print(f"Scheduled pins: {len(pins)}")
        for pin in pins:
            print(f"  - {pin.get('pin_id')}: {pin.get('title', 'N/A')[:50]}")
            print(f"    Board: {pin.get('target_board')}")
            print(f"    Already posted: {is_already_posted(pin.get('pin_id', ''))}")
    else:
        print(f"Posting pins for {slot} slot...")
        results = post_pins(slot)
        print(f"Results: {json.dumps(results, indent=2)}")
