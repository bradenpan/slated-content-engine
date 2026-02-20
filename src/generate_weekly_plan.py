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
- No topic repetition within 4 weeks
- Max 5 treatments per URL in 60 days
- Max 5 pins per board per week
- No more than 3 consecutive same-template pins
- 4 pins per day across 3 time slots
- Seasonal content injection during windows
- Performance-informed adjustments
"""

import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

from src.apis.claude_api import ClaudeAPI
from src.apis.sheets_api import SheetsAPI
from src.apis.slack_notify import SlackNotify

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
STRATEGY_DIR = PROJECT_ROOT / "strategy"
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
DATA_DIR = PROJECT_ROOT / "data"

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
TOPIC_REPETITION_WINDOW_WEEKS = 4
MAX_TREATMENTS_PER_URL_60_DAYS = 5

# Days in the posting week: Tuesday through Monday
POSTING_DAYS = ["tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "monday"]

# Time slots per day
TIME_SLOTS = ["morning", "afternoon", "evening_1", "evening_2"]


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

    # Step 9: If validation fails, re-prompt with violations
    max_retries = 2
    retry_count = 0
    while violations and retry_count < max_retries:
        logger.warning(
            "Plan validation found %d issues (retry %d/%d): %s",
            len(violations), retry_count + 1, max_retries, violations,
        )

        # Build violation context for re-prompting
        violation_text = "\n".join(f"- {v}" for v in violations)
        reprompt_context = (
            f"The generated plan has the following constraint violations that "
            f"must be fixed:\n\n{violation_text}\n\n"
            f"Please regenerate the plan, fixing these specific issues while "
            f"keeping the rest of the plan intact."
        )

        # Re-generate with violation feedback
        plan = claude.generate_weekly_plan(
            strategy_doc=strategy_context.get("strategy_doc", ""),
            weekly_analysis=latest_analysis + "\n\n" + reprompt_context,
            content_memory=content_memory,
            seasonal_context=seasonal_context,
            keyword_data=keyword_data,
            negative_keywords=negative_keywords,
        )

        violations = validate_plan(plan, content_memory, content_log, board_structure)
        retry_count += 1

    if violations:
        logger.warning(
            "Plan still has %d violations after %d retries. Proceeding with warnings: %s",
            len(violations), max_retries, violations,
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


def generate_content_memory_summary() -> str:
    """
    Generate the content memory summary from content-log.jsonl.

    This is pure Python aggregation -- NO LLM call. Reads the content log,
    computes aggregates, and writes a condensed summary to
    data/content-memory-summary.md.

    Sections produced:
    1. RECENT TOPICS (last 4 weeks)
    2. ALL BLOG POSTS (grouped by type + pillar)
    3. PILLAR MIX (last 4 weeks + all time)
    4. KEYWORD FREQUENCY (top 15 + untargeted)
    5. IMAGES USED RECENTLY (last 90 days IDs)
    6. FRESH PIN CANDIDATES (posts with no pin in 4+ weeks)
    7. TREATMENT TRACKER (URLs with treatment counts)

    Returns:
        str: The generated content memory summary markdown.
    """
    content_log = _load_content_log()
    today = date.today()

    # Date boundaries
    four_weeks_ago = today - timedelta(weeks=4)
    ninety_days_ago = today - timedelta(days=90)
    sixty_days_ago = today - timedelta(days=60)

    # Load keyword lists for untargeted keyword detection
    try:
        kw_data = json.loads(
            (STRATEGY_DIR / "keyword-lists.json").read_text(encoding="utf-8")
        )
        all_target_keywords = set()
        for pillar_data in kw_data.get("pillars", {}).values():
            all_target_keywords.update(pillar_data.get("primary", []))
            all_target_keywords.update(pillar_data.get("secondary", []))
    except (FileNotFoundError, json.JSONDecodeError):
        all_target_keywords = set()

    sections = []

    # -------------------------------------------------------
    # Section 1: RECENT TOPICS (last 4 weeks)
    # -------------------------------------------------------
    recent_entries = [
        e for e in content_log
        if _parse_date(_get_entry_date(e)) and _parse_date(_get_entry_date(e)) >= four_weeks_ago
    ]

    section_lines = ["## 1. RECENT TOPICS (Last 4 Weeks)\n"]
    if recent_entries:
        # Deduplicate by blog_slug to show unique blog posts
        seen_slugs: set = set()
        for entry in sorted(recent_entries, key=lambda e: _get_entry_date(e), reverse=True):
            slug = entry.get("blog_slug", "")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                section_lines.append(
                    f"- [{_get_entry_date(entry)}] P{entry.get('pillar', '?')}: "
                    f"{entry.get('blog_title', slug)} "
                    f"({entry.get('content_type', 'unknown')})"
                )
    else:
        section_lines.append("No content in the last 4 weeks (first run).")
    sections.append("\n".join(section_lines))

    # -------------------------------------------------------
    # Section 2: ALL BLOG POSTS (grouped by type + pillar)
    # -------------------------------------------------------
    section_lines = ["## 2. ALL BLOG POSTS\n"]

    # Group by content_type, then by pillar
    posts_by_type: dict[str, dict[int, list]] = defaultdict(lambda: defaultdict(list))
    seen_slugs = set()
    for entry in content_log:
        slug = entry.get("blog_slug", "")
        if slug and slug not in seen_slugs:
            seen_slugs.add(slug)
            ctype = entry.get("content_type", "unknown")
            pillar = entry.get("pillar", 0)
            posts_by_type[ctype][pillar].append({
                "slug": slug,
                "title": entry.get("blog_title", slug),
            })

    if posts_by_type:
        for ctype in sorted(posts_by_type.keys()):
            section_lines.append(f"\n### {ctype.title()}")
            for pillar in sorted(posts_by_type[ctype].keys()):
                section_lines.append(f"  Pillar {pillar}:")
                for post in posts_by_type[ctype][pillar]:
                    section_lines.append(f"    - {post['title']} ({post['slug']})")
    else:
        section_lines.append("No blog posts yet (first run).")
    sections.append("\n".join(section_lines))

    # -------------------------------------------------------
    # Section 3: PILLAR MIX (last 4 weeks vs. all time)
    # -------------------------------------------------------
    section_lines = ["## 3. PILLAR MIX\n"]

    # Last 4 weeks
    recent_pillar_counts = Counter(
        e.get("pillar", 0) for e in recent_entries
    )
    all_time_pillar_counts = Counter(
        e.get("pillar", 0) for e in content_log
    )

    section_lines.append("### Last 4 Weeks")
    for p in range(1, 6):
        count = recent_pillar_counts.get(p, 0)
        total_recent = sum(recent_pillar_counts.values()) or 1
        pct = count / total_recent * 100
        section_lines.append(f"  P{p}: {count} pins ({pct:.0f}%)")

    section_lines.append("\n### All Time")
    for p in range(1, 6):
        count = all_time_pillar_counts.get(p, 0)
        total_all = sum(all_time_pillar_counts.values()) or 1
        pct = count / total_all * 100
        section_lines.append(f"  P{p}: {count} pins ({pct:.0f}%)")

    # Content type mix
    recent_type_counts = Counter(
        e.get("content_type", "unknown") for e in recent_entries
    )
    section_lines.append("\n### Content Type (Last 4 Weeks)")
    for ctype, count in recent_type_counts.most_common():
        section_lines.append(f"  {ctype}: {count}")

    # Board mix
    recent_board_counts = Counter(
        e.get("board", "unknown") for e in recent_entries
    )
    section_lines.append("\n### Board Distribution (Last 4 Weeks)")
    for board, count in recent_board_counts.most_common():
        section_lines.append(f"  {board}: {count}")

    # Funnel layer mix
    recent_funnel_counts = Counter(
        e.get("funnel_layer", "unknown") for e in recent_entries
    )
    section_lines.append("\n### Funnel Layer (Last 4 Weeks)")
    for layer, count in recent_funnel_counts.most_common():
        section_lines.append(f"  {layer}: {count}")

    sections.append("\n".join(section_lines))

    # -------------------------------------------------------
    # Section 4: KEYWORD FREQUENCY (top 15 + untargeted)
    # -------------------------------------------------------
    section_lines = ["## 4. KEYWORD FREQUENCY\n"]

    # Count all primary keywords
    keyword_counts: Counter = Counter()
    keyword_last_used: dict[str, str] = {}
    keyword_performance: dict[str, dict] = defaultdict(
        lambda: {"impressions": 0, "saves": 0, "count": 0}
    )

    for entry in content_log:
        pk = entry.get("primary_keyword", "")
        if pk:
            keyword_counts[pk] += 1
            entry_date = _get_entry_date(entry)
            if entry_date > keyword_last_used.get(pk, ""):
                keyword_last_used[pk] = entry_date
            keyword_performance[pk]["impressions"] += entry.get("impressions", 0)
            keyword_performance[pk]["saves"] += entry.get("saves", 0)
            keyword_performance[pk]["count"] += 1

        # Also count secondary keywords
        for sk in entry.get("secondary_keywords", []):
            keyword_counts[sk] += 1
            entry_date = _get_entry_date(entry)
            if entry_date > keyword_last_used.get(sk, ""):
                keyword_last_used[sk] = entry_date

    section_lines.append("### Top 15 Keywords by Usage")
    for kw, count in keyword_counts.most_common(15):
        last_used = keyword_last_used.get(kw, "never")
        perf = keyword_performance.get(kw, {})
        save_rate = ""
        if perf.get("impressions", 0) > 0:
            sr = perf["saves"] / perf["impressions"] * 100
            save_rate = f", save_rate={sr:.1f}%"
        section_lines.append(f"  {kw}: {count} uses (last: {last_used}{save_rate})")

    # Find untargeted keywords
    used_keywords = set(keyword_counts.keys())
    untargeted = all_target_keywords - used_keywords
    if untargeted:
        section_lines.append("\n### Untargeted Keywords (from strategy, never used)")
        for kw in sorted(untargeted):
            section_lines.append(f"  - {kw}")

    sections.append("\n".join(section_lines))

    # -------------------------------------------------------
    # Section 5: IMAGES USED RECENTLY (last 90 days)
    # -------------------------------------------------------
    section_lines = ["## 5. IMAGES USED RECENTLY (Last 90 Days)\n"]

    recent_image_entries = [
        e for e in content_log
        if _parse_date(_get_entry_date(e)) and _parse_date(_get_entry_date(e)) >= ninety_days_ago
    ]

    image_ids = []
    for entry in recent_image_entries:
        source = entry.get("image_source", "")
        img_id = entry.get("image_id", "")
        if source and img_id:
            image_ids.append(f"{source}:{img_id}")

    if image_ids:
        section_lines.append(f"Total: {len(image_ids)} images")
        section_lines.append(", ".join(image_ids))
    else:
        section_lines.append("No images tracked yet.")

    sections.append("\n".join(section_lines))

    # -------------------------------------------------------
    # Section 6: FRESH PIN CANDIDATES
    # -------------------------------------------------------
    section_lines = ["## 6. FRESH PIN CANDIDATES\n"]
    section_lines.append("Blog posts with no new pin in 4+ weeks, sorted by performance:\n")

    # Find all unique blog slugs and their last pin date + performance
    slug_data: dict[str, dict] = {}
    for entry in content_log:
        slug = entry.get("blog_slug", "")
        if not slug:
            continue

        entry_date = _get_entry_date(entry)
        if slug not in slug_data:
            slug_data[slug] = {
                "title": entry.get("blog_title", slug),
                "pillar": entry.get("pillar", 0),
                "last_pin_date": entry_date,
                "total_impressions": 0,
                "total_saves": 0,
                "treatment_count": 0,
            }

        data = slug_data[slug]
        if entry_date > data["last_pin_date"]:
            data["last_pin_date"] = entry_date
        data["total_impressions"] += entry.get("impressions", 0)
        data["total_saves"] += entry.get("saves", 0)
        data["treatment_count"] = max(
            data["treatment_count"],
            entry.get("treatment_number", 1),
        )

    # Filter to candidates (no pin in 4+ weeks, under treatment limit)
    candidates = []
    for slug, data in slug_data.items():
        last_date = _parse_date(data["last_pin_date"])
        if last_date and last_date < four_weeks_ago and data["treatment_count"] < MAX_TREATMENTS_PER_URL_60_DAYS:
            candidates.append((slug, data))

    # Sort by total_saves descending (best performers first)
    candidates.sort(key=lambda x: x[1]["total_saves"], reverse=True)

    if candidates:
        for slug, data in candidates[:20]:  # Limit to top 20
            section_lines.append(
                f"- {data['title']} ({slug}) | P{data['pillar']} | "
                f"Saves: {data['total_saves']} | Impressions: {data['total_impressions']} | "
                f"Treatment {data['treatment_count']}/{MAX_TREATMENTS_PER_URL_60_DAYS} | "
                f"Last pin: {data['last_pin_date']}"
            )
    else:
        section_lines.append("No fresh pin candidates yet (library too new or all recently pinned).")

    sections.append("\n".join(section_lines))

    # -------------------------------------------------------
    # Section 7: TREATMENT TRACKER
    # -------------------------------------------------------
    section_lines = ["## 7. TREATMENT TRACKER\n"]
    section_lines.append("URLs with treatments in the last 60 days:\n")

    recent_60d_entries = [
        e for e in content_log
        if _parse_date(_get_entry_date(e)) and _parse_date(_get_entry_date(e)) >= sixty_days_ago
    ]

    # Count treatments per URL in the last 60 days
    url_treatments: dict[str, dict] = {}
    for entry in recent_60d_entries:
        slug = entry.get("blog_slug", "")
        if not slug:
            continue
        if slug not in url_treatments:
            url_treatments[slug] = {
                "title": entry.get("blog_title", slug),
                "treatment_count": 0,
                "treatments": [],
            }
        url_treatments[slug]["treatment_count"] += 1
        url_treatments[slug]["treatments"].append({
            "date": _get_entry_date(entry),
            "treatment_number": entry.get("treatment_number", 1),
        })

    if url_treatments:
        # Sort by treatment count descending
        for slug, data in sorted(
            url_treatments.items(),
            key=lambda x: x[1]["treatment_count"],
            reverse=True,
        ):
            limit_warning = ""
            if data["treatment_count"] >= MAX_TREATMENTS_PER_URL_60_DAYS - 1:
                limit_warning = " [APPROACHING LIMIT]"
            if data["treatment_count"] >= MAX_TREATMENTS_PER_URL_60_DAYS:
                limit_warning = " [AT LIMIT - NO MORE TREATMENTS]"
            section_lines.append(
                f"- {data['title']} ({slug}): "
                f"{data['treatment_count']}/{MAX_TREATMENTS_PER_URL_60_DAYS} treatments{limit_warning}"
            )
    else:
        section_lines.append("No treatments tracked in the last 60 days.")

    sections.append("\n".join(section_lines))

    # -------------------------------------------------------
    # Assemble and write the summary
    # -------------------------------------------------------
    header = (
        f"# Content Memory Summary\n"
        f"Generated: {today.isoformat()}\n"
        f"Content log entries: {len(content_log)}\n"
        f"---\n"
    )

    summary = header + "\n\n".join(sections)

    # Write to data/content-memory-summary.md
    memory_path = DATA_DIR / "content-memory-summary.md"
    memory_path.write_text(summary, encoding="utf-8")
    logger.info("Wrote content memory summary to %s (%d chars)", memory_path, len(summary))

    return summary


def validate_plan(
    plan: dict,
    content_memory: str,
    content_log: Optional[list[dict]] = None,
    board_structure: Optional[dict] = None,
) -> list[str]:
    """
    Validate a generated plan against all constraints.

    Args:
        plan: The generated weekly plan with blog_posts and pins arrays.
        content_memory: Content memory summary markdown.
        content_log: Parsed content log entries. Loaded if None.
        board_structure: Board structure from strategy. Loaded if None.

    Returns:
        list[str]: List of validation violation messages (empty if all pass).
    """
    violations = []
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
        violations.append(
            f"Total pins must be {TOTAL_WEEKLY_PINS}, got {len(pins)}"
        )

    # --- Check 2: Pillar mix within ranges (allow +/-1 pin tolerance) ---
    pillar_counts = Counter(pin.get("pillar", 0) for pin in pins)
    for pillar, (min_pins, max_pins) in PILLAR_MIX_TARGETS.items():
        count = pillar_counts.get(pillar, 0)
        # Allow +/-1 tolerance as specified
        if count < min_pins - 1 or count > max_pins + 1:
            violations.append(
                f"Pillar {pillar} has {count} pins, target range is "
                f"{min_pins}-{max_pins} (with +/-1 tolerance: {min_pins-1}-{max_pins+1})"
            )

    # --- Check 3: No topic repetition within 4 weeks ---
    four_weeks_ago = date.today() - timedelta(weeks=TOPIC_REPETITION_WINDOW_WEEKS)
    recent_topics = set()
    recent_slugs = set()
    for entry in content_log:
        entry_date = _parse_date(_get_entry_date(entry))
        if entry_date and entry_date >= four_weeks_ago:
            topic = entry.get("topic_summary", "").lower()
            if topic:
                recent_topics.add(topic)
            slug = entry.get("blog_slug", "")
            if slug:
                recent_slugs.add(slug)

    for post in blog_posts:
        topic = post.get("topic", "").lower()
        # Simple overlap check -- look for significant word overlap
        if topic:
            topic_words = set(topic.split())
            for recent_topic in recent_topics:
                recent_words = set(recent_topic.split())
                overlap = topic_words & recent_words
                # If more than 60% of words overlap, flag it
                if len(overlap) > 0.6 * max(len(topic_words), 1):
                    violations.append(
                        f"Topic '{post.get('topic')}' may repeat recent topic "
                        f"'{recent_topic}' (shared words: {overlap})"
                    )

    # --- Check 4: Max 5 pins per board ---
    board_counts = Counter(pin.get("target_board", "") for pin in pins)
    max_per_board = board_structure.get("rules", {}).get(
        "max_pins_per_board_per_week", MAX_PINS_PER_BOARD
    )
    for board, count in board_counts.items():
        if count > max_per_board:
            violations.append(
                f"Board '{board}' has {count} pins, max is {max_per_board}"
            )

    # --- Check 5: Max 2 fresh treatments per URL per week ---
    url_treatment_counts: Counter = Counter()
    for pin in pins:
        if pin.get("pin_type") == "fresh-treatment":
            slug = pin.get("blog_slug", "") or pin.get("source_post_id", "")
            if slug:
                url_treatment_counts[slug] += 1

    for url, count in url_treatment_counts.items():
        if count > MAX_FRESH_TREATMENTS_PER_URL_PER_WEEK:
            violations.append(
                f"URL '{url}' has {count} fresh treatments this week, "
                f"max is {MAX_FRESH_TREATMENTS_PER_URL_PER_WEEK}"
            )

    # --- Check 6: No more than 3 consecutive same-template pins ---
    if len(pins) >= MAX_CONSECUTIVE_SAME_TEMPLATE + 1:
        # Sort pins by scheduled day and slot for sequence checking
        sorted_pins = sorted(
            pins,
            key=lambda p: (
                POSTING_DAYS.index(p.get("scheduled_date", "tuesday").lower())
                if p.get("scheduled_date", "").lower() in POSTING_DAYS else 99,
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
                violations.append(
                    f"More than {MAX_CONSECUTIVE_SAME_TEMPLATE} consecutive pins "
                    f"use template '{templates[0]}' starting at position {i}"
                )
                break  # Only report the first occurrence

    # --- Check 7: 4 pins per day, spread across Tue-Mon ---
    day_counts = Counter(
        pin.get("scheduled_date", "").lower() for pin in pins
    )
    for day in POSTING_DAYS:
        count = day_counts.get(day, 0)
        if count != PINS_PER_DAY:
            violations.append(
                f"Day '{day}' has {count} pins, expected {PINS_PER_DAY}"
            )

    # --- Check 8: Negative keywords ---
    for pin in pins:
        pin_keywords = [pin.get("primary_keyword", "")] + pin.get("secondary_keywords", [])
        pin_topic = pin.get("pin_topic", "").lower()
        for neg_kw in negative_keywords:
            neg_kw_lower = neg_kw.lower()
            for kw in pin_keywords:
                if neg_kw_lower in kw.lower():
                    violations.append(
                        f"Pin '{pin.get('pin_id')}' targets negative keyword: "
                        f"'{kw}' matches '{neg_kw}'"
                    )
            if neg_kw_lower in pin_topic:
                violations.append(
                    f"Pin '{pin.get('pin_id')}' topic contains negative keyword: "
                    f"'{neg_kw}'"
                )

    for post in blog_posts:
        post_keywords = [post.get("primary_keyword", "")] + post.get("secondary_keywords", [])
        post_topic = post.get("topic", "").lower()
        for neg_kw in negative_keywords:
            neg_kw_lower = neg_kw.lower()
            for kw in post_keywords:
                if neg_kw_lower in kw.lower():
                    violations.append(
                        f"Blog post '{post.get('post_id')}' targets negative keyword: "
                        f"'{kw}' matches '{neg_kw}'"
                    )
            if neg_kw_lower in post_topic:
                violations.append(
                    f"Blog post '{post.get('post_id')}' topic contains negative keyword: "
                    f"'{neg_kw}'"
                )

    return violations


def _load_content_log() -> list[dict]:
    """
    Load and parse content-log.jsonl.

    Returns:
        list[dict]: List of content log entries.
    """
    log_path = DATA_DIR / "content-log.jsonl"
    entries = []

    if not log_path.exists():
        return entries

    try:
        content = log_path.read_text(encoding="utf-8")
        for line_num, line in enumerate(content.strip().split("\n"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning("Invalid JSON on line %d of content-log.jsonl: %s", line_num, e)
    except FileNotFoundError:
        pass

    return entries


def _get_entry_date(entry: dict) -> str:
    """
    Get the date string from a content log entry.

    Content log entries may have the date under "date" (written by
    blog_deployer at schedule time) or "posted_date" (written by
    post_pins at posting time). This helper checks both fields.

    Args:
        entry: Content log entry dict.

    Returns:
        Date string (YYYY-MM-DD) or empty string if neither field exists.
    """
    return entry.get("date") or entry.get("posted_date", "")


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """
    Parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string or None.

    Returns:
        date object or None if parsing fails.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


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
