"""Shared weekly plan loading and manipulation utilities."""
import json
import logging
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from src.shared.paths import DATA_DIR
from src.shared.utils.content_log import load_content_log as _load_content_log
from src.shared.content_memory import get_entry_date, parse_date
from src.shared.utils.safe_get import safe_get

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

    Raises:
        FileNotFoundError: If the plan file does not exist.
        json.JSONDecodeError: If the file contains invalid JSON.
        OSError: If the file cannot be read.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        logger.error("Plan file not found: %s", path)
        raise
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in plan file %s: %s", path, e)
        raise
    except OSError as e:
        logger.error("Failed to read plan file %s: %s", path, e)
        raise


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
    pins = safe_get(plan, "pins", [])
    blog_posts = safe_get(plan, "blog_posts", [])

    # Build indexes
    post_index = {p["post_id"]: p for p in blog_posts}
    pins_by_source: dict[str, list] = defaultdict(list)
    for pin in pins:
        pins_by_source[safe_get(pin, "source_post_id", "")].append(pin)

    # Trace pin-level violations to their source post
    pin_to_source = {
        safe_get(pin, "pin_id", ""): safe_get(pin, "source_post_id", "")
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
        elif v.get("pin_id"):
            # Pin-level violation (e.g. negative_keyword_pin); trace to source post
            pin_id = v["pin_id"]
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
                    "pin_id": safe_get(p, "pin_id", None),
                    "source_post_id": safe_get(p, "source_post_id", None),
                    "scheduled_date": safe_get(p, "scheduled_date", None),
                    "scheduled_slot": safe_get(p, "scheduled_slot", None),
                    "target_board": safe_get(p, "target_board", None),
                    "pin_template": safe_get(p, "pin_template", None),
                    "funnel_layer": safe_get(p, "funnel_layer", None),
                    "pin_type": safe_get(p, "pin_type", None),
                    "treatment_number": safe_get(p, "treatment_number", None),
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
        p["post_id"]: p for p in safe_get(replacements, "blog_posts", [])
    }
    replacement_pins = {
        p["pin_id"]: p for p in safe_get(replacements, "pins", [])
    }

    new_plan["blog_posts"] = [
        replacement_posts.get(post["post_id"], post)
        if safe_get(post, "post_id", None) in offending_post_ids
        else post
        for post in safe_get(plan, "blog_posts", [])
    ]

    new_plan["pins"] = [
        replacement_pins.get(pin["pin_id"], pin)
        if safe_get(pin, "pin_id", None) in offending_pin_ids
        else pin
        for pin in safe_get(plan, "pins", [])
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
        pk = safe_get(entry, "primary_keyword", "")
        if pk:
            keyword_perf[pk]["impressions"] += safe_get(entry, "impressions", 0)
            keyword_perf[pk]["saves"] += safe_get(entry, "saves", 0)
            keyword_perf[pk]["outbound_clicks"] += safe_get(entry, "outbound_clicks", 0)
            keyword_perf[pk]["pin_count"] += 1

        for sk in safe_get(entry, "secondary_keywords", []):
            keyword_perf[sk]["impressions"] += safe_get(entry, "impressions", 0)
            keyword_perf[sk]["saves"] += safe_get(entry, "saves", 0)
            keyword_perf[sk]["outbound_clicks"] += safe_get(entry, "outbound_clicks", 0)
            keyword_perf[sk]["pin_count"] += 1

    # Compute save rates
    for kw, perf in keyword_perf.items():
        if perf["impressions"] > 0:
            perf["save_rate"] = perf["saves"] / perf["impressions"]
        else:
            perf["save_rate"] = 0.0

    # Merge into keyword lists
    enriched = {
        "pillars": safe_get(keyword_lists, "pillars", {}),
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
        entry_date = parse_date(get_entry_date(entry))
        if entry_date and entry_date >= topic_window:
            topic = safe_get(entry, "topic_summary", "")
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
