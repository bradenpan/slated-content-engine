"""Canonical content log operations.

Single source of truth for reading, appending, and querying content-log.jsonl.
"""
import json
import logging
from pathlib import Path

from src.paths import CONTENT_LOG_PATH

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

    Args:
        entries: All content log entries (with updated analytics).
    """
    p = path or CONTENT_LOG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(p, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        logger.info("Saved %d entries to content log", len(entries))
    except OSError as e:
        logger.error("Failed to write content log: %s", e)
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


def is_pin_posted(pin_id: str, path: Path = None) -> bool:
    """Check if a pin has already been posted (idempotency guard).

    Scans content-log.jsonl for an entry with this pin_id that has
    a non-null pinterest_pin_id field.

    Args:
        pin_id: Internal pin ID (e.g., "W12-01").

    Returns:
        bool: True if pin already has a pinterest_pin_id in the content log.
    """
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
                    if entry.get("pin_id") == pin_id and entry.get("pinterest_pin_id"):
                        return True
                except json.JSONDecodeError:
                    continue
    except OSError as e:
        logger.warning("Could not read content log for idempotency check: %s", e)

    return False
