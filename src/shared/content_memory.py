"""Content memory summary generation.

Generates a condensed summary of all content created to date, used by the
weekly planning prompt to prevent topic repetition and enforce treatment limits.

This is the canonical implementation, consolidated from the two previous
copies in generate_weekly_plan.py (comprehensive, 7-section) and
weekly_analysis.py (simpler).

Channel-aware: entries carry a "channel" field (defaults to "pinterest" for
backward compatibility).  The summary includes channel attribution on entries
so cross-channel planners can see what was published where and how it performed.
"""
import json
import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta, date
from pathlib import Path
from typing import Optional

from src.shared.paths import DATA_DIR, STRATEGY_DIR
from src.shared.utils.content_log import load_content_log
from src.shared.utils.safe_get import safe_get

logger = logging.getLogger(__name__)

# Defaults matching generate_weekly_plan.py constants.  The caller can
# override these via function parameters.
_DEFAULT_TOPIC_WINDOW_WEEKS = 10
_DEFAULT_MAX_TREATMENTS = 5


def _get_channel(entry: dict) -> str:
    """Get the channel for a content log entry, defaulting to 'pinterest'."""
    return safe_get(entry, "channel", "pinterest")


def get_entry_date(entry: dict) -> str:
    """Get the date string from a content log entry.

    Content log entries may have the date under "date" (written by
    blog_deployer at schedule time) or "posted_date" (written by
    post_pins at posting time).

    Returns:
        Date string (YYYY-MM-DD) or empty string if neither field exists.
    """
    return safe_get(entry, "date", "") or safe_get(entry, "posted_date", "")


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
    channel: Optional[str] = None,
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
    8. PERFORMANCE HISTORY (pillar lifetime with trends, top keywords
       by saves, compounding signal, top performers)

    Args:
        content_log_path: Override the content log file path (for testing).
        output_path: Override the output file path (for testing).
        topic_window_weeks: Number of weeks for the recent-topics window.
        max_treatments: Maximum treatments per URL in 60 days.
        channel: Optional channel filter.  When set, only entries for that
            channel are included.  When None (default), all channels are
            shown with channel attribution on each entry.

    Returns:
        The generated content memory summary markdown string.
    """
    all_entries = load_content_log(path=content_log_path)

    if not all_entries:
        empty_summary = "# Content Memory Summary\n\nNo content has been created yet.\n"
        _write_summary(empty_summary, output_path)
        return empty_summary

    # Apply channel filter if specified
    if channel:
        content_log = [e for e in all_entries if _get_channel(e) == channel]
    else:
        content_log = all_entries

    # Determine if we should show channel tags (when viewing all channels
    # and more than one channel exists in the data)
    all_channels = {_get_channel(e) for e in all_entries}
    show_channel_tags = channel is None and len(all_channels) > 1

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
        for pillar_data in safe_get(kw_data, "pillars", {}).values():
            all_target_keywords.update(safe_get(pillar_data, "primary", []))
            all_target_keywords.update(safe_get(pillar_data, "secondary", []))
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
            slug = safe_get(entry, "blog_slug", "")
            if slug and slug not in seen_slugs:
                seen_slugs.add(slug)
                channel_tag = f" [{_get_channel(entry)}]" if show_channel_tags else ""
                section_lines.append(
                    f"- [{get_entry_date(entry)}] P{safe_get(entry, 'pillar', '?')}: "
                    f"{safe_get(entry, 'blog_title', slug)} "
                    f"({safe_get(entry, 'content_type', 'unknown')})"
                    f"{channel_tag}"
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
        slug = safe_get(entry, "blog_slug", "")
        if slug and slug not in seen_slugs:
            seen_slugs.add(slug)
            ctype = safe_get(entry, "content_type", "unknown")
            pillar = safe_get(entry, "pillar", 0)
            posts_by_type[ctype][pillar].append({
                "slug": slug,
                "title": safe_get(entry, "blog_title", slug),
                "channel": _get_channel(entry),
            })

    if posts_by_type:
        for ctype in sorted(posts_by_type.keys()):
            section_lines.append(f"\n### {ctype.title()}")
            for pillar in sorted(posts_by_type[ctype].keys()):
                section_lines.append(f"  Pillar {pillar}:")
                for post in posts_by_type[ctype][pillar]:
                    channel_tag = f" [{post['channel']}]" if show_channel_tags else ""
                    section_lines.append(f"    - {post['title']} ({post['slug']}){channel_tag}")
    else:
        section_lines.append("No blog posts yet (first run).")
    sections.append("\n".join(section_lines))

    # --- Section 3: PILLAR MIX ---
    section_lines = ["## 3. PILLAR MIX\n"]

    # Channel distribution (only when showing all channels)
    if show_channel_tags:
        channel_counts = Counter(_get_channel(e) for e in content_log)
        section_lines.append("### Channel Distribution")
        total_entries = sum(channel_counts.values()) or 1
        for ch, count in channel_counts.most_common():
            pct = count / total_entries * 100
            section_lines.append(f"  {ch}: {count} entries ({pct:.0f}%)")
        section_lines.append("")

    recent_pillar_counts = Counter(
        safe_get(e, "pillar", 0) for e in recent_entries
    )
    all_time_pillar_counts = Counter(
        safe_get(e, "pillar", 0) for e in content_log
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
        safe_get(e, "content_type", "unknown") for e in recent_entries
    )
    section_lines.append(f"\n### Content Type (Last {topic_window_weeks} Weeks)")
    for ctype, count in recent_type_counts.most_common():
        section_lines.append(f"  {ctype}: {count}")

    recent_board_counts = Counter(
        safe_get(e, "board", "unknown") for e in recent_entries
    )
    section_lines.append(f"\n### Board Distribution (Last {topic_window_weeks} Weeks)")
    for board, count in recent_board_counts.most_common():
        section_lines.append(f"  {board}: {count}")

    recent_funnel_counts = Counter(
        safe_get(e, "funnel_layer", "unknown") for e in recent_entries
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
        pk = safe_get(entry, "primary_keyword", "")
        if pk:
            keyword_counts[pk] += 1
            entry_date = get_entry_date(entry)
            if entry_date > keyword_last_used.get(pk, ""):
                keyword_last_used[pk] = entry_date
            keyword_performance[pk]["impressions"] += safe_get(entry, "impressions", 0)
            keyword_performance[pk]["saves"] += safe_get(entry, "saves", 0)
            keyword_performance[pk]["count"] += 1

        for sk in safe_get(entry, "secondary_keywords", []):
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
        source = safe_get(entry, "image_source", "")
        img_id = safe_get(entry, "image_id", "")
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
        slug = safe_get(entry, "blog_slug", "")
        if not slug:
            continue

        entry_date = get_entry_date(entry)
        if slug not in slug_data:
            slug_data[slug] = {
                "title": safe_get(entry, "blog_title", slug),
                "pillar": safe_get(entry, "pillar", 0),
                "last_pin_date": entry_date,
                "total_impressions": 0,
                "total_saves": 0,
                "treatment_count": 0,
            }

        data = slug_data[slug]
        if entry_date > data["last_pin_date"]:
            data["last_pin_date"] = entry_date
        data["total_impressions"] += safe_get(entry, "impressions", 0)
        data["total_saves"] += safe_get(entry, "saves", 0)
        data["treatment_count"] = max(
            data["treatment_count"],
            safe_get(entry, "treatment_number", 1),
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
        slug = safe_get(entry, "blog_slug", "")
        if not slug:
            continue
        if slug not in url_treatments:
            url_treatments[slug] = {
                "title": safe_get(entry, "blog_title", slug),
                "treatment_count": 0,
                "treatments": [],
            }
        url_treatments[slug]["treatment_count"] += 1
        url_treatments[slug]["treatments"].append({
            "date": get_entry_date(entry),
            "treatment_number": safe_get(entry, "treatment_number", 1),
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

    # --- Section 8: PERFORMANCE HISTORY ---
    sections.append(_build_performance_history(content_log, today))

    # --- Assemble and write the summary ---
    channel_note = f"Channel filter: {channel}" if channel else "Channels: all"
    header = (
        f"# Content Memory Summary\n"
        f"Generated: {today.isoformat()}\n"
        f"Content log entries: {len(content_log)}\n"
        f"{channel_note}\n"
        f"---\n"
    )

    summary = header + "\n\n".join(sections)

    _write_summary(summary, output_path)
    return summary


def _build_performance_history(content_log: list[dict], today: date) -> str:
    """Build Section 8: Performance History.

    Four subsections providing lifetime performance context:
    1. Per-Pillar Lifetime — totals + trend direction (incl. raw percentages)
    2. Top Keywords by Saves (All-Time) — top 15
    3. Compounding Signal — 3-bucket age analysis
    4. Top All-Time Performers — top 10 by save_rate
    """
    four_weeks_ago = today - timedelta(weeks=4)
    eight_weeks_ago = today - timedelta(weeks=8)

    section_lines = ["## 8. PERFORMANCE HISTORY\n"]

    # Precompute date-bucketed entries
    recent_4wk = []
    prior_4wk = []
    for entry in content_log:
        d = parse_date(get_entry_date(entry))
        if not d:
            continue
        if d >= four_weeks_ago:
            recent_4wk.append(entry)
        elif d >= eight_weeks_ago:
            prior_4wk.append(entry)

    # --- 8a: Per-Pillar Lifetime ---
    section_lines.append("### Per-Pillar Lifetime")
    pillar_data: dict[int, dict] = defaultdict(
        lambda: {"impressions": 0, "saves": 0, "count": 0}
    )
    for entry in content_log:
        p = safe_get(entry, "pillar", 0)
        pillar_data[p]["impressions"] += safe_get(entry, "impressions", 0)
        pillar_data[p]["saves"] += safe_get(entry, "saves", 0)
        pillar_data[p]["count"] += 1

    # Per-pillar trend (recent 4wk vs prior 4wk save rate)
    def _pillar_save_rate(entries, pillar):
        impr = sum(safe_get(e, "impressions", 0) for e in entries if safe_get(e, "pillar", 0) == pillar)
        saves = sum(safe_get(e, "saves", 0) for e in entries if safe_get(e, "pillar", 0) == pillar)
        return saves / impr if impr > 0 else 0.0

    for p in sorted(pillar_data.keys()):
        d = pillar_data[p]
        sr = d["saves"] / d["impressions"] * 100 if d["impressions"] > 0 else 0
        recent_sr = _pillar_save_rate(recent_4wk, p)
        prior_sr = _pillar_save_rate(prior_4wk, p)
        if prior_sr > 0 and recent_sr > prior_sr * 1.1:
            trend = "improving"
        elif prior_sr > 0 and recent_sr < prior_sr * 0.9:
            trend = "declining"
        else:
            trend = "stable"
        section_lines.append(
            f"  P{p}: {d['count']} pins, {d['impressions']:,} impr, "
            f"{d['saves']:,} saves, save_rate={sr:.1f}%, trend={trend} "
            f"(recent={recent_sr*100:.1f}%, prior={prior_sr*100:.1f}%)"
        )

    # --- 8b: Top Keywords by Saves (All-Time) ---
    section_lines.append("\n### Top Keywords by Saves (All-Time)")
    kw_perf: dict[str, dict] = defaultdict(
        lambda: {"impressions": 0, "saves": 0, "count": 0}
    )
    for entry in content_log:
        pk = safe_get(entry, "primary_keyword", "")
        if pk:
            kw_perf[pk]["impressions"] += safe_get(entry, "impressions", 0)
            kw_perf[pk]["saves"] += safe_get(entry, "saves", 0)
            kw_perf[pk]["count"] += 1

    top_kws = sorted(kw_perf.items(), key=lambda x: x[1]["saves"], reverse=True)[:15]
    for kw, d in top_kws:
        sr = d["saves"] / d["impressions"] * 100 if d["impressions"] > 0 else 0
        section_lines.append(
            f"  {kw}: {d['count']} pins, {d['impressions']:,} impr, "
            f"{d['saves']:,} saves, save_rate={sr:.1f}%"
        )

    # --- 8c: Compounding Signal ---
    section_lines.append("\n### Compounding Signal")

    age_buckets = {"<30d": [], "30-60d": [], "60-90d": [], "90+d": []}
    for entry in content_log:
        d = parse_date(get_entry_date(entry))
        if not d:
            continue
        age = (today - d).days
        if age < 30:
            age_buckets["<30d"].append(entry)
        elif age < 60:
            age_buckets["30-60d"].append(entry)
        elif age < 90:
            age_buckets["60-90d"].append(entry)
        else:
            age_buckets["90+d"].append(entry)

    bucket_avgs = {}
    for bucket, entries in age_buckets.items():
        if entries:
            avg_impr = sum(safe_get(e, "impressions", 0) for e in entries) / len(entries)
        else:
            avg_impr = 0
        bucket_avgs[bucket] = avg_impr
        section_lines.append(
            f"  {bucket}: {len(entries)} pins, avg_impressions={avg_impr:.0f}"
        )

    # Verdict
    baseline = bucket_avgs.get("<30d", 0)
    mid_range = bucket_avgs.get("60-90d", 0)
    if baseline > 0 and mid_range > baseline * 0.5:
        verdict = "active (60-90d avg > 50% of <30d)"
    elif baseline > 0 and mid_range < baseline * 0.25:
        verdict = "decaying (60-90d avg < 25% of <30d)"
    else:
        verdict = "flat"
    section_lines.append(f"  Verdict: {verdict}")

    # --- 8d: Top All-Time Performers ---
    section_lines.append("\n### Top All-Time Performers")
    qualified = [
        e for e in content_log
        if safe_get(e, "impressions", 0) >= 100
    ]
    # Dedup by pin_id
    seen_pins: dict[str, dict] = {}
    for entry in qualified:
        pid = safe_get(entry, "pin_id", "")
        if pid and pid not in seen_pins:
            seen_pins[pid] = entry

    top_performers = sorted(
        seen_pins.values(),
        key=lambda e: safe_get(e, "saves", 0) / safe_get(e, "impressions", 1),
        reverse=True,
    )[:10]

    if top_performers:
        for entry in top_performers:
            impr = safe_get(entry, "impressions", 0)
            saves = safe_get(entry, "saves", 0)
            sr = saves / impr * 100 if impr > 0 else 0
            title = safe_get(entry, "blog_title", safe_get(entry, "title", "untitled"))
            section_lines.append(
                f"  - {title[:60]} | save_rate={sr:.1f}%, "
                f"{impr:,} impr, {saves:,} saves"
            )
    else:
        section_lines.append("  No pins with 100+ impressions yet.")

    return "\n".join(section_lines)


def generate_cross_channel_summary(exclude_channel: str) -> str:
    """Generate a short digest of other channels' recent performance.

    Filters the content log to entries NOT matching *exclude_channel* from the
    last 7 days, computes quick aggregates, and returns a 200-300 char summary
    suitable for the ``cross_channel_summary`` prompt param.

    Args:
        exclude_channel: Channel to exclude (e.g. "pinterest" when running
                         TikTok analysis, or "tiktok" for Pinterest).

    Returns:
        Short summary string, or a placeholder if no cross-channel data exists.
    """
    content_log = load_content_log()
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()

    other_entries = [
        e for e in content_log
        if _get_channel(e) != exclude_channel
        and (get_entry_date(e) or "") >= week_ago
    ]

    if not other_entries:
        return f"No cross-channel data (only {exclude_channel} active)."

    # Group by channel
    by_channel: dict[str, list[dict]] = defaultdict(list)
    for e in other_entries:
        by_channel[_get_channel(e)].append(e)

    parts = []
    for ch, entries in sorted(by_channel.items()):
        count = len(entries)
        total_impr = sum(safe_get(e, "impressions", 0) for e in entries)
        total_saves = sum(safe_get(e, "saves", 0) for e in entries)
        save_rate = total_saves / total_impr * 100 if total_impr > 0 else 0.0

        # Top performer by saves
        top = max(entries, key=lambda e: safe_get(e, "saves", 0))
        top_title = (
            safe_get(top, "title", "")
            or safe_get(top, "blog_title", "")
            or safe_get(top, "topic", "untitled")
        )[:40]

        parts.append(
            f"{ch.capitalize()}: {count} posts, {total_impr:,} impr, "
            f"save_rate={save_rate:.1f}%. Top: \"{top_title}\""
        )

    return "Last 7 days — " + " | ".join(parts)


def _write_summary(summary: str, output_path: Path = None) -> None:
    """Write the summary markdown to disk."""
    memory_path = output_path or (DATA_DIR / "content-memory-summary.md")
    try:
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        memory_path.write_text(summary, encoding="utf-8")
        logger.info("Wrote content memory summary to %s (%d chars)", memory_path, len(summary))
    except OSError as e:
        logger.warning("Failed to save content memory summary: %s", e)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    generate_content_memory_summary()
