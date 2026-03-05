"""Canonical content log operations.

Single source of truth for reading, appending, and querying content-log.jsonl.
"""
import json
import logging
from pathlib import Path

from src.shared.paths import CONTENT_LOG_PATH

logger = logging.getLogger(__name__)


def load_content_log(path: Path = None) -> list[dict]:
    """Load all entries from content-log.jsonl.

    Each line is a JSON object. Empty lines and malformed lines are skipped
    with a warning.

    Returns:
        list[dict]: All content log entries.
    """
    p = path or CONTENT_LOG_PATH
    if not p.exists():
        return []

    entries = []
    line_number = 0

    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line_number += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Malformed JSON on line %d of content log: %s", line_number, e
                    )
    except OSError as e:
        logger.error("Failed to read content log: %s", e)
        return []

    logger.info("Loaded %d entries from content log", len(entries))
    return entries


def save_content_log(entries: list[dict], path: Path = None) -> None:
    """Rewrite the entire content-log.jsonl with updated entries.

    Uses atomic write (temp file + rename) to prevent data loss if the
    process crashes mid-write.

    Args:
        entries: All content log entries (with updated analytics).
    """
    p = path or CONTENT_LOG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")

    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        tmp.replace(p)
        logger.info("Saved %d entries to content log", len(entries))
    except OSError as e:
        logger.error("Failed to write content log: %s", e)
        # Clean up partial temp file
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def append_content_log_entry(entry: dict, path: Path = None) -> None:
    """Append a single entry to content-log.jsonl.

    Args:
        entry: Content log entry to append.
    """
    p = path or CONTENT_LOG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.error("Failed to write to content log: %s", e)
        raise


# Map channel names to the platform-specific ID field that confirms posting.
_CHANNEL_PLATFORM_ID_FIELDS = {
    "pinterest": "pinterest_pin_id",
    "tiktok": "publer_post_id",
}


def is_content_posted(
    content_id: str,
    channel: str,
    path: Path = None,
) -> bool:
    """Check if content has already been posted for a given channel (idempotency guard).

    Scans content-log.jsonl for an entry with this content_id (pin_id field)
    that has a non-null platform ID field for the given channel.

    Args:
        content_id: Internal content ID (e.g., "W12-01").
        channel: Channel name ("pinterest", "tiktok", etc.).
        path: Override content log path (for testing).

    Returns:
        bool: True if content already has a platform ID in the content log.
    """
    platform_id_field = _CHANNEL_PLATFORM_ID_FIELDS.get(channel)
    if not platform_id_field:
        logger.warning("Unknown channel '%s' for idempotency check", channel)
        return False

    p = path or CONTENT_LOG_PATH
    if not p.exists():
        return False

    try:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    platform_id = entry.get(platform_id_field, "")
                    if (entry.get("pin_id") == content_id
                            and platform_id
                            and platform_id != "PENDING"):
                        return True
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        logger.warning("Could not read content log for idempotency check: %s", e)

    return False


def is_pin_posted(pin_id: str, path: Path = None) -> bool:
    """Check if a pin has already been posted to Pinterest (idempotency guard).

    Backward-compatible wrapper around is_content_posted().

    Args:
        pin_id: Internal pin ID (e.g., "W12-01").

    Returns:
        bool: True if pin already has a pinterest_pin_id in the content log.
    """
    return is_content_posted(pin_id, "pinterest", path=path)
