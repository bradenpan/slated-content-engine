"""Content memory summary generation.

Generates a condensed summary of all content created to date, used by the
weekly planning prompt to prevent topic repetition and enforce treatment limits.

This is the canonical implementation, consolidated from the two previous
copies in generate_weekly_plan.py (comprehensive, 7-section) and
weekly_analysis.py (simpler).
"""
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

from src.paths import DATA_DIR, STRATEGY_DIR
from src.utils.content_log import load_content_log

logger = logging.getLogger(__name__)

# Defaults matching generate_weekly_plan.py constants.  The caller can
# override these via function parameters.
_DEFAULT_TOPIC_WINDOW_WEEKS = 10
_DEFAULT_MAX_TREATMENTS = 5


def get_entry_date(entry: dict) -> str:
    """Get the date string from a content log entry.

    Content log entries may have the date under "date" (written by
    blog_deployer at schedule time) or "posted_date" (written by
    post_pins at posting time).

    Returns:
        Date string (YYYY-MM-DD) or empty string if neither field exists.
    """
    return entry.get("date") or entry.get("posted_date", "")


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse a date string in YYYY-MM-DD format.

    Returns:
        date object or None if parsing fails.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def generate_content_memory_summary(
    content_log_path: Path = None,
    output_path: Path = None,
    topic_window_weeks: int = _DEFAULT_TOPIC_WINDOW_WEEKS,
    max_treatments: int = _DEFAULT_MAX_TREATMENTS,
) -> str:
    """Generate the content memory summary markdown.

    Pure Python aggregation (no LLM call).  Reads the content log,
    computes aggregates, and writes a condensed summary to the output
    path (default ``data/content-memory-summary.md``).

    Sections produced:
    1. RECENT TOPICS (last *topic_window_weeks* weeks)
    2. ALL BLOG POSTS (grouped by type + pillar)
    3. PILLAR MIX (recent window + all time, content type, board, funnel)
    4. KEYWORD FREQUENCY (top 15 + untargeted, with performance data)
    5. IMAGES USED RECENTLY (last 90 days IDs)
    6. FRESH PIN CANDIDATES (posts with no pin in 4+ weeks)
    7. TREATMENT TRACKER (URLs with treatment counts in last 60 days)

    Args:
        content_log_path: Override the content log file path (for testing).
        output_path: Override the output file path (for testing).
        topic_window_weeks: Number of weeks for the recent-topics window.
        max_treatments: Maximum treatments per URL in 60 days.

    Returns:
        The generated content memory summary markdown string.
    """
    content_log = load_content_log(path=content_log_path)

    if not content_log:
        empty_summary = "# Content Memory Summary\n\nNo content has been created yet.\n"
        _write_summary(empty_summary, output_path)
        return empty_summary

    today = date.today()

    # Date boundaries
    topic_window_start = today - timedelta(weeks=topic_window_weeks)
    fresh_pin_window_start = today - timedelta(weeks=4)
    ninety_days_ago = today - timedelta(days=90)
    sixty_days_ago = today - timedelta(days=60)

    # Load keyword lists for untargeted keyword detection
    try:
        kw_data = json.loads(
            (STRATEGY_DIR / "keyword-lists.json").read_text(encoding="utf-8")
        )
        all_target_keywords: set[str] = set()
        for pillar_data in kw_data.get("pillars", {}).values():
            all_target_keywords.update(pillar_data.get("primary", []))
            all_target_keywords.update(pillar_data.get("secondary", []))
    except (FileNotFoundError, json.JSONDecodeError):
        all_target_keywords = set()

    sections: list[str] = []

    # --- Section 1: RECENT TOPICS ---
    recent_entries = [
        e for e in content_log
        if (d := parse_date(get_entry_date(e)))
        and d >= topic_window_start
    ]

    section_lines = [f"## 1. RECENT TOPICS (Last {topic_window_weeks} Weeks)\n"]
    if recent_entries:
        seen_slugs: set[str] = set()
        for entry in sorted(recent_entries, key=lambda e: get_entry_date(e), reverse=True):
            slug = entry.get("blog_slug", "")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                section_lines.append(
                    f"- [{get_entry_date(entry)}] P{entry.get('pillar', '?')}: "
                    f"{entry.get('blog_title', slug)} "
                    f"({entry.get('content_type', 'unknown')})"
                )
    else:
        section_lines.append(
            f"No content in the last {topic_window_weeks} weeks (first run)."
        )
    sections.append("\n".join(section_lines))

    # --- Section 2: ALL BLOG POSTS (grouped by type + pillar) ---
    section_lines = ["## 2. ALL BLOG POSTS\n"]
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

    # --- Section 3: PILLAR MIX ---
    section_lines = ["## 3. PILLAR MIX\n"]

    recent_pillar_counts = Counter(
        e.get("pillar", 0) for e in recent_entries
    )
    all_time_pillar_counts = Counter(
        e.get("pillar", 0) for e in content_log
    )

    section_lines.append(f"### Last {topic_window_weeks} Weeks")
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

    recent_type_counts = Counter(
        e.get("content_type", "unknown") for e in recent_entries
    )
    section_lines.append(f"\n### Content Type (Last {topic_window_weeks} Weeks)")
    for ctype, count in recent_type_counts.most_common():
        section_lines.append(f"  {ctype}: {count}")

    recent_board_counts = Counter(
        e.get("board", "unknown") for e in recent_entries
    )
    section_lines.append(f"\n### Board Distribution (Last {topic_window_weeks} Weeks)")
    for board, count in recent_board_counts.most_common():
        section_lines.append(f"  {board}: {count}")

    recent_funnel_counts = Counter(
        e.get("funnel_layer", "unknown") for e in recent_entries
    )
    section_lines.append(f"\n### Funnel Layer (Last {topic_window_weeks} Weeks)")
    for layer, count in recent_funnel_counts.most_common():
        section_lines.append(f"  {layer}: {count}")

    sections.append("\n".join(section_lines))

    # --- Section 4: KEYWORD FREQUENCY ---
    section_lines = ["## 4. KEYWORD FREQUENCY\n"]

    keyword_counts: Counter = Counter()
    keyword_last_used: dict[str, str] = {}
    keyword_performance: dict[str, dict] = defaultdict(
        lambda: {"impressions": 0, "saves": 0, "count": 0}
    )

    for entry in content_log:
        pk = entry.get("primary_keyword", "")
        if pk:
            keyword_counts[pk] += 1
            entry_date = get_entry_date(entry)
            if entry_date > keyword_last_used.get(pk, ""):
                keyword_last_used[pk] = entry_date
            keyword_performance[pk]["impressions"] += entry.get("impressions", 0)
            keyword_performance[pk]["saves"] += entry.get("saves", 0)
            keyword_performance[pk]["count"] += 1

        for sk in entry.get("secondary_keywords", []):
            keyword_counts[sk] += 1
            entry_date = get_entry_date(entry)
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

    used_keywords = set(keyword_counts.keys())
    untargeted = all_target_keywords - used_keywords
    if untargeted:
        section_lines.append("\n### Untargeted Keywords (from strategy, never used)")
        for kw in sorted(untargeted):
            section_lines.append(f"  - {kw}")

    sections.append("\n".join(section_lines))

    # --- Section 5: IMAGES USED RECENTLY (last 90 days) ---
    section_lines = ["## 5. IMAGES USED RECENTLY (Last 90 Days)\n"]

    recent_image_entries = [
        e for e in content_log
        if (d := parse_date(get_entry_date(e)))
        and d >= ninety_days_ago
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

    # --- Section 6: FRESH PIN CANDIDATES ---
    section_lines = ["## 6. FRESH PIN CANDIDATES\n"]
    section_lines.append(
        "Blog posts with no new pin in 4+ weeks, sorted by performance:\n"
    )

    slug_data: dict[str, dict] = {}
    for entry in content_log:
        slug = entry.get("blog_slug", "")
        if not slug:
            continue

        entry_date = get_entry_date(entry)
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

    candidates = []
    for slug, data in slug_data.items():
        last_date = parse_date(data["last_pin_date"])
        if (
            last_date
            and last_date < fresh_pin_window_start
            and data["treatment_count"] < max_treatments
        ):
            candidates.append((slug, data))

    candidates.sort(key=lambda x: x[1]["total_saves"], reverse=True)

    if candidates:
        for slug, data in candidates[:20]:
            section_lines.append(
                f"- {data['title']} ({slug}) | P{data['pillar']} | "
                f"Saves: {data['total_saves']} | Impressions: {data['total_impressions']} | "
                f"Treatment {data['treatment_count']}/{max_treatments} | "
                f"Last pin: {data['last_pin_date']}"
            )
    else:
        section_lines.append(
            "No fresh pin candidates yet (library too new or all recently pinned)."
        )

    sections.append("\n".join(section_lines))

    # --- Section 7: TREATMENT TRACKER ---
    section_lines = ["## 7. TREATMENT TRACKER\n"]
    section_lines.append("URLs with treatments in the last 60 days:\n")

    recent_60d_entries = [
        e for e in content_log
        if (d := parse_date(get_entry_date(e)))
        and d >= sixty_days_ago
    ]

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
            "date": get_entry_date(entry),
            "treatment_number": entry.get("treatment_number", 1),
        })

    if url_treatments:
        for slug, data in sorted(
            url_treatments.items(),
            key=lambda x: x[1]["treatment_count"],
            reverse=True,
        ):
            limit_warning = ""
            if data["treatment_count"] >= max_treatments - 1:
                limit_warning = " [APPROACHING LIMIT]"
            if data["treatment_count"] >= max_treatments:
                limit_warning = " [AT LIMIT - NO MORE TREATMENTS]"
            section_lines.append(
                f"- {data['title']} ({slug}): "
                f"{data['treatment_count']}/{max_treatments} treatments{limit_warning}"
            )
    else:
        section_lines.append("No treatments tracked in the last 60 days.")

    sections.append("\n".join(section_lines))

    # --- Assemble and write the summary ---
    header = (
        f"# Content Memory Summary\n"
        f"Generated: {today.isoformat()}\n"
        f"Content log entries: {len(content_log)}\n"
        f"---\n"
    )

    summary = header + "\n\n".join(sections)

    _write_summary(summary, output_path)
    return summary


def _write_summary(summary: str, output_path: Path = None) -> None:
    """Write the summary markdown to disk."""
    memory_path = output_path or (DATA_DIR / "content-memory-summary.md")
    try:
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text(summary, encoding="utf-8")
        logger.info("Wrote content memory summary to %s (%d chars)", memory_path, len(summary))
    except OSError as e:
        logger.warning("Failed to save content memory summary: %s", e)
