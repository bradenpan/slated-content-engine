"""Shared weekly plan loading and manipulation utilities."""
import json
import logging
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from src.paths import DATA_DIR
from src.utils.content_log import load_content_log as _load_content_log
from src.utils.content_memory import _get_entry_date, _parse_date

logger = logging.getLogger(__name__)


def find_latest_plan(data_dir: Path = None) -> Path | None:
    """Find the most recent weekly-plan-*.json file.

    Args:
        data_dir: Directory to search. Defaults to DATA_DIR.

    Returns:
        Path to the latest plan file, or None if no plans exist.
    """
    d = data_dir or DATA_DIR
    plans = sorted(d.glob("weekly-plan-*.json"), reverse=True)
    return plans[0] if plans else None


def load_plan(path: Path) -> dict:
    """Load and parse a weekly plan JSON file.

    Args:
        path: Path to the plan JSON file.

    Returns:
        dict: The weekly plan data.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def identify_replaceable_posts(
    plan: dict,
    violations: list[dict],
) -> dict:
    """
    Identify which blog posts need replacement and their derived pins.

    Args:
        plan: The current weekly plan.
        violations: Structured violation list from validate_plan().

    Returns:
        dict: Mapping of post_id -> {post, pins, pin_ids, slots, violations}.
              Only includes posts from targeted violations that can be replaced
              (not existing/published posts).
    """
    pins = plan.get("pins", [])
    blog_posts = plan.get("blog_posts", [])

    # Build indexes
    post_index = {p["post_id"]: p for p in blog_posts}
    pins_by_source: dict[str, list] = defaultdict(list)
    for pin in pins:
        pins_by_source[pin.get("source_post_id", "")].append(pin)

    # Trace pin-level violations to their source post
    pin_to_source = {
        pin.get("pin_id", ""): pin.get("source_post_id", "")
        for pin in pins
    }

    # Collect targeted violations and resolve to post IDs
    offending_post_ids: set[str] = set()
    violations_by_post: dict[str, list] = defaultdict(list)

    for v in violations:
        if v["severity"] != "targeted":
            continue
        pid = v.get("post_id")
        if pid:
            offending_post_ids.add(pid)
            violations_by_post[pid].append(v)
        elif v.get("category") == "negative_keyword_pin":
            # Extract pin_id from message and trace to source post
            msg = v.get("message", "")
            # Message format: "Pin 'W8-03' targets..."
            if "'" in msg:
                pin_id = msg.split("'")[1]
                source_pid = pin_to_source.get(pin_id, "")
                if source_pid and not source_pid.startswith("existing:"):
                    offending_post_ids.add(source_pid)
                    violations_by_post[source_pid].append(v)

    # Build the result with post objects, derived pins, and slot info
    result = {}
    for pid in offending_post_ids:
        post_obj = post_index.get(pid)
        if not post_obj:
            continue

        derived_pins = pins_by_source.get(pid, [])
        result[pid] = {
            "post": post_obj,
            "pins": derived_pins,
            "pin_ids": {p["pin_id"] for p in derived_pins},
            "slots": [
                {
                    "pin_id": p.get("pin_id"),
                    "source_post_id": p.get("source_post_id"),
                    "scheduled_date": p.get("scheduled_date"),
                    "scheduled_slot": p.get("scheduled_slot"),
                    "target_board": p.get("target_board"),
                    "pin_template": p.get("pin_template"),
                    "funnel_layer": p.get("funnel_layer"),
                    "pin_type": p.get("pin_type"),
                    "treatment_number": p.get("treatment_number"),
                }
                for p in derived_pins
            ],
            "violations": violations_by_post[pid],
        }

    return result


def splice_replacements(
    plan: dict,
    replacements: dict,
    offending_post_ids: set,
    offending_pin_ids: set,
) -> dict:
    """
    Splice replacement blog posts and pins into the existing plan by ID.

    After splicing, the plan has the same number of posts and pins with
    the same IDs and slot assignments -- only content fields change.

    Args:
        plan: The original weekly plan.
        replacements: Output from generate_replacement_posts() with
                      "blog_posts" and "pins" arrays.
        offending_post_ids: Set of post_ids being replaced.
        offending_pin_ids: Set of pin_ids being replaced.

    Returns:
        dict: Updated plan with replacements spliced in.
    """
    new_plan = dict(plan)

    replacement_posts = {
        p["post_id"]: p for p in replacements.get("blog_posts", [])
    }
    replacement_pins = {
        p["pin_id"]: p for p in replacements.get("pins", [])
    }

    new_plan["blog_posts"] = [
        replacement_posts.get(post["post_id"], post)
        if post.get("post_id") in offending_post_ids
        else post
        for post in plan.get("blog_posts", [])
    ]

    new_plan["pins"] = [
        replacement_pins.get(pin["pin_id"], pin)
        if pin.get("pin_id") in offending_pin_ids
        else pin
        for pin in plan.get("pins", [])
    ]

    return new_plan


def build_keyword_performance_data(
    keyword_lists: dict,
    content_log: list[dict] | None = None,
) -> dict:
    """
    Build keyword data with performance metrics from the content log.

    Enriches the keyword lists from strategy with actual performance data
    (impressions, saves, save_rate) aggregated from content-log.jsonl.

    Args:
        keyword_lists: Keyword lists from strategy/keyword-lists.json.
        content_log: Parsed content log entries. Loaded from disk if None.

    Returns:
        dict: Keyword data enriched with performance metrics.
    """
    if content_log is None:
        content_log = _load_content_log()

    # Aggregate performance by keyword
    keyword_perf: dict[str, dict] = defaultdict(
        lambda: {"impressions": 0, "saves": 0, "outbound_clicks": 0, "pin_count": 0}
    )

    for entry in content_log:
        pk = entry.get("primary_keyword", "")
        if pk:
            keyword_perf[pk]["impressions"] += entry.get("impressions", 0)
            keyword_perf[pk]["saves"] += entry.get("saves", 0)
            keyword_perf[pk]["outbound_clicks"] += entry.get("outbound_clicks", 0)
            keyword_perf[pk]["pin_count"] += 1

        for sk in entry.get("secondary_keywords", []):
            keyword_perf[sk]["impressions"] += entry.get("impressions", 0)
            keyword_perf[sk]["saves"] += entry.get("saves", 0)
            keyword_perf[sk]["outbound_clicks"] += entry.get("outbound_clicks", 0)
            keyword_perf[sk]["pin_count"] += 1

    # Compute save rates
    for kw, perf in keyword_perf.items():
        if perf["impressions"] > 0:
            perf["save_rate"] = perf["saves"] / perf["impressions"]
        else:
            perf["save_rate"] = 0.0

    # Merge into keyword lists
    enriched = {
        "pillars": keyword_lists.get("pillars", {}),
        "performance": dict(keyword_perf),
    }

    return enriched


def extract_recent_topics(content_log: list[dict], topic_repetition_window_weeks: int = 10) -> list[str]:
    """
    Extract unique recent topic strings from the content log.

    Uses the specified window. Passed to the replacement prompt so Claude
    knows what topics to avoid.

    Args:
        content_log: Parsed content log entries.
        topic_repetition_window_weeks: Lookback window in weeks.

    Returns:
        list[str]: Unique topic strings from recent content.
    """
    topic_window = date.today() - timedelta(weeks=topic_repetition_window_weeks)
    topics = set()
    for entry in content_log:
        entry_date = _parse_date(_get_entry_date(entry))
        if entry_date and entry_date >= topic_window:
            topic = entry.get("topic_summary", "")
            if topic:
                topics.add(topic)
    return list(topics)


def save_pin_schedule(schedule: list[dict], path: Path = None) -> None:
    """Atomically write pin-schedule.json using temp file + rename.

    Args:
        schedule: List of pin schedule entry dicts.
        path: Output path. Defaults to DATA_DIR / "pin-schedule.json".
    """
    p = path or (DATA_DIR / "pin-schedule.json")
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(schedule, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)
    logger.info("Saved pin schedule (%d entries) to %s", len(schedule), p)
