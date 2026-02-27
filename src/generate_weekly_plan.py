"""
Weekly Content Plan Generator

Generates the weekly content plan (8-10 blog posts + 28 derived pins)
using Claude Sonnet. This is the "brain" step that runs every Monday
at 6am ET as part of the weekly-review.yml workflow.

The plan is blog-first: blog posts are defined first, then pins are
derived from them.

Input context loaded for the planning prompt:
1. strategy/current-strategy.md -- Strategic direction
2. analysis/weekly/latest -- Most recent weekly analysis
3. data/content-memory-summary.md -- Content memory (prevents repetition)
4. strategy/seasonal-calendar.json -- Current seasonal window
5. strategy/keyword-lists.json + performance data -- Keyword targets
6. strategy/negative-keywords.json -- Topics to avoid
7. strategy/cta-variants.json -- CTA copy for blog post assignments
8. strategy/board-structure.json -- Board distribution constraints

Output: Structured plan written to Google Sheet "Weekly Review" tab.

Planning constraints enforced (from strategy Section 12.2):
- Pillar mix percentages
- No topic repetition within 10 weeks
- Max 5 treatments per URL in 60 days
- Max 5 pins per board per week
- No more than 3 consecutive same-template pins
- 4 pins per day across 3 time slots
- Seasonal content injection during windows
- Performance-informed adjustments
"""

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, date
from typing import Optional

from src.apis.claude_api import ClaudeAPI
from src.apis.sheets_api import SheetsAPI
from src.apis.slack_notify import SlackNotify
from src.paths import STRATEGY_DIR, ANALYSIS_DIR, DATA_DIR
from src.utils.content_log import load_content_log as _load_content_log
from src.utils.content_memory import (
    generate_content_memory_summary,
    _get_entry_date,
    _parse_date,
)

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


def generate_plan(week_start_date: Optional[str] = None) -> dict:
    """
    Generate the weekly content plan.

    Main orchestration function. This is the entry point called by
    the weekly-review.yml workflow.

    Args:
        week_start_date: ISO date string for the week start (Monday).
                        Defaults to the current or next Monday.

    Returns:
        dict: The generated weekly plan with blog_posts and pins arrays.
    """
    if week_start_date:
        start_date = datetime.strptime(week_start_date, "%Y-%m-%d").date()
    else:
        today = date.today()
        # Find the current or next Monday
        days_until_monday = (7 - today.weekday()) % 7
        start_date = today + timedelta(days=days_until_monday) if days_until_monday > 0 else today

    week_label = start_date.strftime("W%W-%Y")
    logger.info("Generating weekly plan for week starting %s (%s)", start_date, week_label)

    # Step 1: Load the current strategy document
    strategy_context = load_strategy_context()
    logger.info("Loaded strategy context: %d files", len(strategy_context))

    # Step 2: Load the most recent weekly analysis
    latest_analysis = load_latest_analysis()
    if latest_analysis:
        logger.info("Loaded latest weekly analysis")
    else:
        logger.info("No previous weekly analysis found (first run)")

    # Step 3: Generate the content memory summary
    content_memory = generate_content_memory_summary()
    logger.info("Generated content memory summary")

    # Step 4: Determine current seasonal window
    seasonal_calendar = strategy_context.get("seasonal_calendar", {})
    seasonal_context = get_current_seasonal_window(
        seasonal_calendar.get("seasons", [])
    )
    logger.info("Seasonal context: %s", seasonal_context[:100] if seasonal_context else "None")

    # Step 5: Load keyword performance data
    keyword_data = _build_keyword_performance_data(
        strategy_context.get("keyword_lists", {}),
    )

    # Step 6: Load negative keywords
    neg_kw_data = strategy_context.get("negative_keywords", {})
    negative_keywords = [
        item["term"] if isinstance(item, dict) else item
        for item in neg_kw_data.get("negative_keywords", [])
    ]

    # Step 7: Call Claude to generate the plan
    claude = ClaudeAPI()
    plan = claude.generate_weekly_plan(
        strategy_doc=strategy_context.get("strategy_doc", ""),
        weekly_analysis=latest_analysis,
        content_memory=content_memory,
        seasonal_context=seasonal_context,
        keyword_data=keyword_data,
        negative_keywords=negative_keywords,
    )

    # Step 8: Validate against constraints
    content_log = _load_content_log()
    board_structure = strategy_context.get("board_structure", {})
    violations = validate_plan(plan, content_memory, content_log, board_structure)

    # Step 9: Retry loop — targeted replacement first, full regen as fallback
    max_retries = 2
    retry_count = 0
    while violations and retry_count < max_retries:
        targeted = [v for v in violations if v["severity"] == "targeted"]
        structural = [v for v in violations if v["severity"] == "structural"]

        logger.warning(
            "Plan validation found %d issues (retry %d/%d): "
            "%d targeted, %d structural. %s",
            len(violations), retry_count + 1, max_retries,
            len(targeted), len(structural),
            violation_messages(violations),
        )

        if structural:
            # Structural issues require full plan regeneration
            logger.info("Structural violations present — full plan regeneration")
            violation_text = "\n".join(f"- {v['message']}" for v in violations)
            reprompt_context = (
                f"The generated plan has the following constraint violations that "
                f"must be fixed:\n\n{violation_text}\n\n"
                f"Please regenerate the plan, fixing these specific issues while "
                f"keeping the rest of the plan intact."
            )

            plan = claude.generate_weekly_plan(
                strategy_doc=strategy_context.get("strategy_doc", ""),
                weekly_analysis=latest_analysis + "\n\n" + reprompt_context,
                content_memory=content_memory,
                seasonal_context=seasonal_context,
                keyword_data=keyword_data,
                negative_keywords=negative_keywords,
            )
        else:
            # Only targeted violations — attempt surgical replacement
            replaceable = identify_replaceable_posts(plan, violations)

            if not replaceable:
                # Targeted violations but can't identify posts (e.g., pin neg-keyword
                # on an existing: source) — fall back to full regen
                logger.warning(
                    "Targeted violations but no replaceable posts found. "
                    "Falling back to full regeneration."
                )
                violation_text = "\n".join(f"- {v['message']}" for v in violations)
                reprompt_context = (
                    f"The generated plan has violations:\n\n{violation_text}\n\n"
                    f"Please regenerate the plan fixing these issues."
                )
                plan = claude.generate_weekly_plan(
                    strategy_doc=strategy_context.get("strategy_doc", ""),
                    weekly_analysis=latest_analysis + "\n\n" + reprompt_context,
                    content_memory=content_memory,
                    seasonal_context=seasonal_context,
                    keyword_data=keyword_data,
                    negative_keywords=negative_keywords,
                )
            elif len(replaceable) > len(plan.get("blog_posts", [])) * 0.5:
                # Too many posts need replacement — surgical fix is pointless
                logger.info(
                    "Too many posts need replacement (%d of %d). Full regeneration.",
                    len(replaceable), len(plan.get("blog_posts", [])),
                )
                violation_text = "\n".join(f"- {v['message']}" for v in violations)
                reprompt_context = (
                    f"The generated plan has violations:\n\n{violation_text}\n\n"
                    f"Please regenerate the plan fixing these issues."
                )
                plan = claude.generate_weekly_plan(
                    strategy_doc=strategy_context.get("strategy_doc", ""),
                    weekly_analysis=latest_analysis + "\n\n" + reprompt_context,
                    content_memory=content_memory,
                    seasonal_context=seasonal_context,
                    keyword_data=keyword_data,
                    negative_keywords=negative_keywords,
                )
            else:
                # Surgical replacement of specific posts
                logger.info(
                    "Attempting targeted replacement of %d post(s): %s",
                    len(replaceable), list(replaceable.keys()),
                )

                posts_to_replace = []
                all_slots = []
                all_offending_pin_ids: set[str] = set()
                for info in replaceable.values():
                    # Include violation reasons alongside the post for context
                    post_with_violations = dict(info["post"])
                    post_with_violations["_violations"] = [
                        v["message"] for v in info["violations"]
                    ]
                    posts_to_replace.append(post_with_violations)
                    all_slots.extend(info["slots"])
                    all_offending_pin_ids.update(info["pin_ids"])

                offending_post_ids = set(replaceable.keys())

                # Build context about the rest of the plan
                kept_posts = [
                    p for p in plan.get("blog_posts", [])
                    if p.get("post_id") not in offending_post_ids
                ]
                kept_pins = [
                    p for p in plan.get("pins", [])
                    if p.get("pin_id") not in all_offending_pin_ids
                ]

                plan_context = {
                    "kept_post_topics": [p.get("topic", "") for p in kept_posts],
                    "kept_pin_boards": dict(Counter(
                        p.get("target_board", "") for p in kept_pins
                    )),
                    "kept_pin_pillars": dict(Counter(
                        p.get("pillar", 0) for p in kept_pins
                    )),
                    "week_number": plan.get("week_number", ""),
                    "date_range": plan.get("date_range", ""),
                }

                recent_topics_list = _extract_recent_topics(content_log)

                try:
                    replacements = claude.generate_replacement_posts(
                        posts_to_replace=posts_to_replace,
                        slots_to_fill=all_slots,
                        plan_context=plan_context,
                        content_memory=content_memory,
                        negative_keywords=negative_keywords,
                        recent_topics=recent_topics_list,
                    )

                    # Validate replacement pin count before splicing
                    expected_pins = len(all_slots)
                    actual_pins = len(replacements.get("pins", []))
                    if actual_pins != expected_pins:
                        logger.warning(
                            "Replacement returned %d pins, expected %d. "
                            "Falling back to full regen on next iteration.",
                            actual_pins, expected_pins,
                        )
                        # Force structural path on next iteration
                        violations = [
                            {**v, "severity": "structural"} for v in violations
                        ]
                        retry_count += 1
                        continue

                    plan = splice_replacements(
                        plan, replacements,
                        offending_post_ids, all_offending_pin_ids,
                    )
                except Exception as e:
                    logger.error(
                        "Targeted replacement failed: %s. "
                        "Falling back to full regen on next iteration.", e,
                    )
                    violations = [
                        {**v, "severity": "structural"} for v in violations
                    ]
                    retry_count += 1
                    continue

        violations = validate_plan(plan, content_memory, content_log, board_structure)
        retry_count += 1

    if violations:
        logger.warning(
            "Plan still has %d violations after %d retries. Proceeding with warnings: %s",
            len(violations), max_retries, violation_messages(violations),
        )

    # Step 10: Write the approved plan to Google Sheets
    try:
        sheets = SheetsAPI()
        sheets.write_weekly_review(
            analysis_summary=latest_analysis[:500] if latest_analysis else "First week - no prior analysis",
            content_plan=plan,
            performance_data={},
        )
        logger.info("Written plan to Google Sheets Weekly Review tab")
    except Exception as e:
        logger.error("Failed to write to Google Sheets: %s", e)

    # Step 11: Save plan locally as JSON
    plan_filename = f"weekly-plan-{start_date.isoformat()}.json"
    plan_path = DATA_DIR / plan_filename
    plan_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Saved plan to %s", plan_path)

    # Step 12: Send Slack notification
    try:
        slack = SlackNotify()
        num_posts = len(plan.get("blog_posts", []))
        num_pins = len(plan.get("pins", []))
        slack.notify_review_ready(
            f"Generated plan: {num_posts} blog posts, {num_pins} pins for week of {start_date}"
        )
    except Exception as e:
        logger.error("Failed to send Slack notification: %s", e)

    return plan


def generate_weekly_plan() -> dict:
    """
    Convenience alias for generate_plan() with default date.

    Returns:
        dict: The generated weekly plan.
    """
    return generate_plan()


def load_strategy_context() -> dict:
    """
    Load all strategy files needed for planning.

    Returns:
        dict: Keys: strategy_doc, brand_voice, keyword_lists,
              negative_keywords, board_structure, cta_variants,
              seasonal_calendar.
    """
    context = {}

    # Current strategy document
    strategy_path = STRATEGY_DIR / "current-strategy.md"
    try:
        context["strategy_doc"] = strategy_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("current-strategy.md not found")
        context["strategy_doc"] = ""

    # Brand voice guidelines
    brand_voice_path = STRATEGY_DIR / "brand-voice.md"
    try:
        context["brand_voice"] = brand_voice_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("brand-voice.md not found")
        context["brand_voice"] = ""

    # JSON strategy files
    json_files = {
        "keyword_lists": "keyword-lists.json",
        "negative_keywords": "negative-keywords.json",
        "board_structure": "board-structure.json",
        "cta_variants": "cta-variants.json",
        "seasonal_calendar": "seasonal-calendar.json",
    }

    for key, filename in json_files.items():
        filepath = STRATEGY_DIR / filename
        try:
            context[key] = json.loads(filepath.read_text(encoding="utf-8"))
        except FileNotFoundError:
            logger.warning("%s not found", filename)
            context[key] = {}
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in %s: %s", filename, e)
            context[key] = {}

    return context


def load_content_memory() -> str:
    """
    Load the content memory summary.

    Returns:
        str: Content memory summary markdown.
    """
    memory_path = DATA_DIR / "content-memory-summary.md"
    try:
        content = memory_path.read_text(encoding="utf-8")
        if content.strip():
            return content
    except FileNotFoundError:
        pass

    logger.info("No existing content memory summary, generating fresh")
    return generate_content_memory_summary()


def load_latest_analysis() -> str:
    """
    Load the most recent weekly analysis.

    Searches analysis/weekly/ for the latest file by name (YYYY-wNN-review.md).

    Returns:
        str: Latest weekly analysis markdown, or empty string if none exists.
    """
    weekly_dir = ANALYSIS_DIR / "weekly"
    if not weekly_dir.exists():
        return ""

    analysis_files = sorted(
        weekly_dir.glob("*-review.md"),
        reverse=True,
    )

    if not analysis_files:
        return ""

    latest = analysis_files[0]
    logger.info("Loading latest analysis: %s", latest.name)
    return latest.read_text(encoding="utf-8")


def get_current_seasonal_window(calendar: list[dict]) -> str:
    """
    Determine the current seasonal content window.

    Uses today's date to find which seasonal publish windows are active
    (content publishes 60-90 days before peak search).

    Args:
        calendar: Seasonal calendar data from seasonal-calendar.json.

    Returns:
        str: Description of current seasonal context for the planning prompt.
    """
    if not calendar:
        return "No seasonal calendar data available."

    current_month = date.today().month
    active_seasons = []

    for season in calendar:
        publish_months = season.get("publish_window_months", [])
        if current_month in publish_months:
            priority = season.get("priority", "normal")
            active_seasons.append({
                "name": season["name"],
                "content_angle": season.get("content_angle", ""),
                "keywords": season.get("keywords", []),
                "relevant_pillars": season.get("relevant_pillars", []),
                "priority": priority,
            })

    if not active_seasons:
        return (
            f"Current month: {current_month}. No seasonal publish windows are "
            f"active. Use standard pillar-driven topic selection."
        )

    lines = [f"Current month: {current_month}. Active seasonal windows:\n"]
    for s in active_seasons:
        priority_label = f" [HIGH PRIORITY]" if s["priority"] == "high" else ""
        lines.append(f"**{s['name']}**{priority_label}")
        lines.append(f"  Content angle: {s['content_angle']}")
        lines.append(f"  Seasonal keywords: {', '.join(s['keywords'])}")
        lines.append(f"  Relevant pillars: {s['relevant_pillars']}")
        lines.append("")

    lines.append(
        "Inject 2-4 seasonal-themed concepts by adjusting topic selection "
        "within existing pillar allocations. Seasonal content is additive, "
        "not replacement -- the pillar mix stays the same."
    )

    return "\n".join(lines)



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
    the same IDs and slot assignments — only content fields change.

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


def _extract_recent_topics(content_log: list[dict]) -> list[str]:
    """
    Extract unique recent topic strings from the content log.

    Uses the same window as TOPIC_REPETITION_WINDOW_WEEKS. Passed to
    the replacement prompt so Claude knows what topics to avoid.

    Returns:
        list[str]: Unique topic strings from recent content.
    """
    topic_window = date.today() - timedelta(weeks=TOPIC_REPETITION_WINDOW_WEEKS)
    topics = set()
    for entry in content_log:
        entry_date = _parse_date(_get_entry_date(entry))
        if entry_date and entry_date >= topic_window:
            topic = entry.get("topic_summary", "")
            if topic:
                topics.add(topic)
    return list(topics)


def violation_messages(violations: list[dict]) -> list[str]:
    """Extract human-readable messages from structured violations for logging."""
    return [v["message"] for v in violations]


def validate_plan(
    plan: dict,
    content_memory: str,
    content_log: Optional[list[dict]] = None,
    board_structure: Optional[dict] = None,
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

    Returns:
        list[dict]: Structured violation objects (empty if all pass).
    """
    violations: list[dict] = []
    pins = plan.get("pins", [])
    blog_posts = plan.get("blog_posts", [])

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
    try:
        neg_kw_data = json.loads(
            (STRATEGY_DIR / "negative-keywords.json").read_text(encoding="utf-8")
        )
        negative_keywords = [
            item["term"] if isinstance(item, dict) else item
            for item in neg_kw_data.get("negative_keywords", [])
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
    pillar_counts = Counter(pin.get("pillar", 0) for pin in pins)
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
        entry_date = _parse_date(_get_entry_date(entry))
        if entry_date and entry_date >= topic_window:
            topic = entry.get("topic_summary", "").lower()
            if topic:
                recent_topics.add(topic)
            slug = entry.get("blog_slug", "")
            if slug:
                recent_slugs.add(slug)

    for post in blog_posts:
        topic = post.get("topic", "").lower()
        if topic:
            topic_words = set(topic.split())
            for recent_topic in recent_topics:
                recent_words = set(recent_topic.split())
                overlap = topic_words & recent_words
                if len(overlap) > 0.6 * max(len(topic_words), 1):
                    violations.append({
                        "category": "topic_repetition",
                        "message": (
                            f"Topic '{post.get('topic')}' may repeat recent topic "
                            f"'{recent_topic}' (shared words: {overlap})"
                        ),
                        "post_id": post.get("post_id"),
                        "severity": "targeted",
                    })

    # --- Check 4: Max 5 pins per board ---
    board_counts = Counter(pin.get("target_board", "") for pin in pins)
    max_per_board = board_structure.get("rules", {}).get(
        "max_pins_per_board_per_week", MAX_PINS_PER_BOARD
    )
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
        if pin.get("pin_type") == "fresh-treatment":
            slug = pin.get("blog_slug", "") or pin.get("source_post_id", "")
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
                p.get("scheduled_date", ""),
                TIME_SLOTS.index(p.get("scheduled_slot", "morning"))
                if p.get("scheduled_slot", "") in TIME_SLOTS else 99,
            ),
        )
        for i in range(len(sorted_pins) - MAX_CONSECUTIVE_SAME_TEMPLATE):
            templates = [
                sorted_pins[j].get("pin_template", "")
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
        pin.get("scheduled_date", "").lower() for pin in pins
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
        pin_keywords = [pin.get("primary_keyword", "")] + pin.get("secondary_keywords", [])
        pin_topic = pin.get("pin_topic", "").lower()
        for neg_kw in negative_keywords:
            neg_kw_lower = neg_kw.lower()
            for kw in pin_keywords:
                if neg_kw_lower in kw.lower():
                    violations.append({
                        "category": "negative_keyword_pin",
                        "message": (
                            f"Pin '{pin.get('pin_id')}' targets negative keyword: "
                            f"'{kw}' matches '{neg_kw}'"
                        ),
                        "post_id": None,
                        "severity": "targeted",
                    })
            if neg_kw_lower in pin_topic:
                violations.append({
                    "category": "negative_keyword_pin",
                    "message": (
                        f"Pin '{pin.get('pin_id')}' topic contains negative keyword: "
                        f"'{neg_kw}'"
                    ),
                    "post_id": None,
                    "severity": "targeted",
                })

    for post in blog_posts:
        post_keywords = [post.get("primary_keyword", "")] + post.get("secondary_keywords", [])
        post_topic = post.get("topic", "").lower()
        for neg_kw in negative_keywords:
            neg_kw_lower = neg_kw.lower()
            for kw in post_keywords:
                if neg_kw_lower in kw.lower():
                    violations.append({
                        "category": "negative_keyword_post",
                        "message": (
                            f"Blog post '{post.get('post_id')}' targets negative keyword: "
                            f"'{kw}' matches '{neg_kw}'"
                        ),
                        "post_id": post.get("post_id"),
                        "severity": "targeted",
                    })
            if neg_kw_lower in post_topic:
                violations.append({
                    "category": "negative_keyword_post",
                    "message": (
                        f"Blog post '{post.get('post_id')}' topic contains negative keyword: "
                        f"'{neg_kw}'"
                    ),
                    "post_id": post.get("post_id"),
                    "severity": "targeted",
                })

    return violations






def _build_keyword_performance_data(keyword_lists: dict) -> dict:
    """
    Build keyword data with performance metrics from the content log.

    Enriches the keyword lists from strategy with actual performance data
    (impressions, saves, save_rate) aggregated from content-log.jsonl.

    Args:
        keyword_lists: Keyword lists from strategy/keyword-lists.json.

    Returns:
        dict: Keyword data enriched with performance metrics.
    """
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


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    print("Generating weekly content plan...")
    plan = generate_weekly_plan()
    print(
        f"Generated plan with {len(plan.get('blog_posts', []))} blog posts "
        f"and {len(plan.get('pins', []))} pins"
    )
