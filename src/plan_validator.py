"""Weekly plan validation against strategy constraints.

Validates a generated weekly content plan against all planning constraints
from strategy Section 12.2: pillar mix, topic repetition, board limits,
treatment limits, template sequencing, day distribution, and negative keywords.
"""

import json
import logging
from collections import Counter
from datetime import date, timedelta
from typing import Optional

from src.paths import STRATEGY_DIR
from src.utils.content_log import load_content_log as _load_content_log
from src.utils.content_memory import get_entry_date, parse_date
from src.utils.safe_get import safe_get

logger = logging.getLogger(__name__)

# Pillar mix target ranges (percentage of 28 total pins)
# Format: pillar -> (min_pins, max_pins)
PILLAR_MIX_TARGETS = {
    1: (9, 10),   # 32-36%
    2: (7, 8),    # 25-29%
    3: (5, 6),    # 18-21%
    4: (2, 3),    # 7-10%
    5: (4, 5),    # 14-18%
}

TOTAL_WEEKLY_PINS = 28
PINS_PER_DAY = 4
MAX_PINS_PER_BOARD = 5
MAX_CONSECUTIVE_SAME_TEMPLATE = 3
MAX_FRESH_TREATMENTS_PER_URL_PER_WEEK = 2
TOPIC_REPETITION_WINDOW_WEEKS = 10
MAX_TREATMENTS_PER_URL_60_DAYS = 5

# Days in the posting week: Tuesday through Monday
POSTING_DAYS = ["tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "monday"]

# Time slots per day
TIME_SLOTS = ["morning", "afternoon", "evening-1", "evening-2"]


def violation_messages(violations: list[dict]) -> list[str]:
    """Extract human-readable messages from structured violations for logging."""
    return [v["message"] for v in violations]


def validate_plan(
    plan: dict,
    content_memory: str,
    content_log: Optional[list[dict]] = None,
    board_structure: Optional[dict] = None,
    negative_keywords: Optional[list[str]] = None,
) -> list[dict]:
    """
    Validate a generated plan against all constraints.

    Each violation is a dict with:
        - category: str identifying the check type
        - message: str human-readable violation description
        - post_id: str or None (set for post-attributable violations)
        - severity: "targeted" (can fix surgically) or "structural" (needs full regen)

    Args:
        plan: The generated weekly plan with blog_posts and pins arrays.
        content_memory: Content memory summary markdown.
        content_log: Parsed content log entries. Loaded if None.
        board_structure: Board structure from strategy. Loaded if None.
        negative_keywords: List of negative keyword strings. Loaded from disk if None.

    Returns:
        list[dict]: Structured violation objects (empty if all pass).
    """
    violations: list[dict] = []
    pins = safe_get(plan, "pins", [])
    blog_posts = safe_get(plan, "blog_posts", [])

    if content_log is None:
        content_log = _load_content_log()

    if board_structure is None:
        try:
            board_structure = json.loads(
                (STRATEGY_DIR / "board-structure.json").read_text(encoding="utf-8")
            )
        except (FileNotFoundError, json.JSONDecodeError):
            board_structure = {}

    # Load negative keywords
    if negative_keywords is None:
        try:
            neg_kw_data = json.loads(
                (STRATEGY_DIR / "negative-keywords.json").read_text(encoding="utf-8")
            )
            negative_keywords = [
                item["term"] if isinstance(item, dict) else item
                for item in safe_get(neg_kw_data, "negative_keywords", [])
            ]
        except (FileNotFoundError, json.JSONDecodeError):
            negative_keywords = []

    # --- Check 1: Total pins = 28 ---
    if len(pins) != TOTAL_WEEKLY_PINS:
        violations.append({
            "category": "pin_count",
            "message": f"Total pins must be {TOTAL_WEEKLY_PINS}, got {len(pins)}",
            "post_id": None,
            "severity": "structural",
        })

    # --- Check 2: Pillar mix within ranges (allow +/-1 pin tolerance) ---
    pillar_counts = Counter(safe_get(pin, "pillar", 0) for pin in pins)
    for pillar, (min_pins, max_pins) in PILLAR_MIX_TARGETS.items():
        count = pillar_counts.get(pillar, 0)
        if count < min_pins - 1 or count > max_pins + 1:
            violations.append({
                "category": "pillar_mix",
                "message": (
                    f"Pillar {pillar} has {count} pins, target range is "
                    f"{min_pins}-{max_pins} (with +/-1 tolerance: {min_pins-1}-{max_pins+1})"
                ),
                "post_id": None,
                "severity": "structural",
            })

    # --- Check 3: No topic repetition within the lookback window ---
    topic_window = date.today() - timedelta(weeks=TOPIC_REPETITION_WINDOW_WEEKS)
    recent_topics = set()
    recent_slugs = set()
    for entry in content_log:
        entry_date = parse_date(get_entry_date(entry))
        if entry_date and entry_date >= topic_window:
            topic = safe_get(entry, "topic_summary", "").lower()
            if topic:
                recent_topics.add(topic)
            slug = safe_get(entry, "blog_slug", "")
            if slug:
                recent_slugs.add(slug)

    for post in blog_posts:
        topic = safe_get(post, "topic", "").lower()
        if topic:
            topic_words = set(topic.split())
            for recent_topic in recent_topics:
                recent_words = set(recent_topic.split())
                overlap = topic_words & recent_words
                if len(overlap) > 0.6 * max(len(topic_words), 1):
                    violations.append({
                        "category": "topic_repetition",
                        "message": (
                            f"Topic '{safe_get(post, 'topic', '')}' may repeat recent topic "
                            f"'{recent_topic}' (shared words: {overlap})"
                        ),
                        "post_id": safe_get(post, "post_id", None),
                        "severity": "targeted",
                    })

    # --- Check 4: Max 5 pins per board ---
    board_counts = Counter(safe_get(pin, "target_board", "") for pin in pins)
    rules = safe_get(board_structure, "rules", {})
    max_per_board = safe_get(rules, "max_pins_per_board_per_week", MAX_PINS_PER_BOARD)
    for board, count in board_counts.items():
        if count > max_per_board:
            violations.append({
                "category": "board_limit",
                "message": f"Board '{board}' has {count} pins, max is {max_per_board}",
                "post_id": None,
                "severity": "structural",
            })

    # --- Check 5: Max 2 fresh treatments per URL per week ---
    url_treatment_counts: Counter = Counter()
    for pin in pins:
        if safe_get(pin, "pin_type", "") == "fresh-treatment":
            slug = safe_get(pin, "blog_slug", "") or safe_get(pin, "source_post_id", "")
            if slug:
                url_treatment_counts[slug] += 1

    for url, count in url_treatment_counts.items():
        if count > MAX_FRESH_TREATMENTS_PER_URL_PER_WEEK:
            violations.append({
                "category": "treatment_limit",
                "message": (
                    f"URL '{url}' has {count} fresh treatments this week, "
                    f"max is {MAX_FRESH_TREATMENTS_PER_URL_PER_WEEK}"
                ),
                "post_id": None,
                "severity": "structural",
            })

    # --- Check 6: No more than 3 consecutive same-template pins ---
    if len(pins) >= MAX_CONSECUTIVE_SAME_TEMPLATE + 1:
        sorted_pins = sorted(
            pins,
            key=lambda p: (
                safe_get(p, "scheduled_date", ""),
                TIME_SLOTS.index(safe_get(p, "scheduled_slot", "morning"))
                if safe_get(p, "scheduled_slot", "") in TIME_SLOTS else 99,
            ),
        )
        for i in range(len(sorted_pins) - MAX_CONSECUTIVE_SAME_TEMPLATE):
            templates = [
                safe_get(sorted_pins[j], "pin_template", "")
                for j in range(i, i + MAX_CONSECUTIVE_SAME_TEMPLATE + 1)
            ]
            if len(set(templates)) == 1 and templates[0]:
                violations.append({
                    "category": "consecutive_template",
                    "message": (
                        f"More than {MAX_CONSECUTIVE_SAME_TEMPLATE} consecutive pins "
                        f"use template '{templates[0]}' starting at position {i}"
                    ),
                    "post_id": None,
                    "severity": "structural",
                })
                break

    # --- Check 7: 4 pins per day, spread across Tue-Mon ---
    day_counts = Counter(
        safe_get(pin, "scheduled_date", "").lower() for pin in pins
    )
    # Verify correct number of posting days
    if len(day_counts) != len(POSTING_DAYS):
        violations.append({
            "category": "day_distribution",
            "message": f"Expected {len(POSTING_DAYS)} posting days, found {len(day_counts)}",
            "post_id": None,
            "severity": "structural",
        })
    for day_date, count in day_counts.items():
        if count != PINS_PER_DAY:
            violations.append({
                "category": "day_distribution",
                "message": f"Date '{day_date}' has {count} pins, expected {PINS_PER_DAY}",
                "post_id": None,
                "severity": "structural",
            })

    # --- Check 8: Negative keywords ---
    for pin in pins:
        pin_id = safe_get(pin, "pin_id", None)
        pin_keywords = [safe_get(pin, "primary_keyword", "")] + safe_get(pin, "secondary_keywords", [])
        pin_topic = safe_get(pin, "pin_topic", "").lower()
        for neg_kw in negative_keywords:
            neg_kw_lower = neg_kw.lower()
            for kw in pin_keywords:
                if neg_kw_lower in kw.lower():
                    violations.append({
                        "category": "negative_keyword_pin",
                        "message": (
                            f"Pin '{pin_id}' targets negative keyword: "
                            f"'{kw}' matches '{neg_kw}'"
                        ),
                        "post_id": None,
                        "pin_id": pin_id,
                        "severity": "targeted",
                    })
            if neg_kw_lower in pin_topic:
                violations.append({
                    "category": "negative_keyword_pin",
                    "message": (
                        f"Pin '{pin_id}' topic contains negative keyword: "
                        f"'{neg_kw}'"
                    ),
                    "post_id": None,
                    "pin_id": pin_id,
                    "severity": "targeted",
                })

    for post in blog_posts:
        post_keywords = [safe_get(post, "primary_keyword", "")] + safe_get(post, "secondary_keywords", [])
        post_topic = safe_get(post, "topic", "").lower()
        for neg_kw in negative_keywords:
            neg_kw_lower = neg_kw.lower()
            for kw in post_keywords:
                if neg_kw_lower in kw.lower():
                    violations.append({
                        "category": "negative_keyword_post",
                        "message": (
                            f"Blog post '{safe_get(post, 'post_id', '')}' targets negative keyword: "
                            f"'{kw}' matches '{neg_kw}'"
                        ),
                        "post_id": safe_get(post, "post_id", None),
                        "severity": "targeted",
                    })
            if neg_kw_lower in post_topic:
                violations.append({
                    "category": "negative_keyword_post",
                    "message": (
                        f"Blog post '{safe_get(post, 'post_id', '')}' topic contains negative keyword: "
                        f"'{neg_kw}'"
                    ),
                    "post_id": safe_get(post, "post_id", None),
                    "severity": "targeted",
                })

    return violations
