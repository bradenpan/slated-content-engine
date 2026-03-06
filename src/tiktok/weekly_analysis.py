"""TikTok Weekly Performance Analysis

Analyzes the past week's TikTok performance using Claude Sonnet.
Runs as part of the tiktok-weekly-review.yml workflow (Monday AM),
after pull_analytics.py.

Input context:
- Post-level performance data (views, saves, shares, likes, comments)
- Per-attribute aggregates (topic, angle, structure, hook_type, template_family)
- Strategy context, content memory, cross-channel summary
- Previous week's analysis for trend comparison

Output: analysis/tiktok/weekly/YYYY-wNN-review.md
"""

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from src.shared.apis.claude_api import ClaudeAPI
from src.shared.analytics_utils import compute_derived_metrics, aggregate_by_dimension
from src.shared.content_planner import load_strategy_context, load_content_memory
from src.shared.content_memory import generate_cross_channel_summary
from src.shared.paths import ANALYSIS_DIR, DATA_DIR
from src.shared.utils.content_log import load_content_log

logger = logging.getLogger(__name__)

TIKTOK_ANALYSIS_DIR = ANALYSIS_DIR / "tiktok" / "weekly"

# TikTok attribute dimensions (instead of Pinterest's pillar/board/template)
ATTRIBUTE_DIMS = ["topic", "angle", "structure", "hook_type"]


def run_weekly_analysis(week_number: Optional[int] = None) -> str:
    """Run the full weekly TikTok performance analysis.

    Steps:
    1. Load content log, filter to tiktok channel
    2. Load strategy context + content memory + cross-channel summary
    3. Load previous analysis for trend comparison
    4. Compute aggregates across attribute dimensions
    5. Call Claude for analysis
    6. Save to analysis/tiktok/weekly/YYYY-wNN-review.md

    Args:
        week_number: ISO week number. If None, uses current week.

    Returns:
        str: The weekly analysis markdown.
    """
    today = date.today()
    if week_number is None:
        _, week_number, _ = today.isocalendar()

    iso_year = today.isocalendar()[0]
    logger.info("Running TikTok weekly analysis for %d-W%02d", iso_year, week_number)

    # Step 1: Load content log, filter to tiktok
    entries = load_content_log()
    entries = [e for e in entries if (e.get("channel") or "pinterest") == "tiktok"]
    entries = compute_derived_metrics(entries)
    logger.info("Loaded %d TikTok content log entries", len(entries))

    # Step 2: Load strategy + memory + cross-channel
    strategy_context = load_strategy_context()
    strategy_doc = strategy_context.get("strategy_doc", "")
    content_memory = load_content_memory()
    cross_channel = generate_cross_channel_summary(exclude_channel="tiktok")

    # Step 3: Load previous analysis
    previous_analysis = load_previous_analysis()

    # Step 4: Compute all aggregates
    analysis_context = build_analysis_context(entries, previous_analysis)
    analysis_context["week_number"] = str(week_number)
    analysis_context["date_range"] = f"{iso_year}-W{week_number:02d}"

    # Step 5: Call Claude
    try:
        claude = ClaudeAPI()
        analysis_md = claude.analyze_tiktok_performance(
            performance_data=analysis_context,
            previous_analysis=previous_analysis,
            strategy_doc=strategy_doc,
            content_memory=content_memory,
            cross_channel_summary=cross_channel,
        )
    except Exception as e:
        logger.error("Claude analysis failed: %s", e)
        analysis_md = _generate_fallback_analysis(analysis_context, iso_year, week_number)

    # Step 6: Save
    output_path = save_analysis(analysis_md, iso_year, week_number)
    logger.info("TikTok weekly analysis saved to %s", output_path)

    return analysis_md


def build_analysis_context(
    entries: list[dict],
    previous_analysis: Optional[str] = None,
) -> dict:
    """Build the full context object for the weekly analysis prompt.

    Computes aggregates across TikTok's attribute dimensions.
    """
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()

    # This week's posts
    this_week = [
        e for e in entries
        if e.get("posted_date", "") > week_ago
        and e.get("pin_id")
    ]

    # Per-attribute aggregates (include TikTok-specific metrics)
    tiktok_extras = ["shares", "likes", "comments"]
    by_topic = aggregate_by_dimension(this_week, "topic", extra_metrics=tiktok_extras)
    by_angle = aggregate_by_dimension(this_week, "angle", extra_metrics=tiktok_extras)
    by_structure = aggregate_by_dimension(this_week, "structure", extra_metrics=tiktok_extras)
    by_hook_type = aggregate_by_dimension(this_week, "hook_type", extra_metrics=tiktok_extras)
    by_template = aggregate_by_dimension(this_week, "template_family", extra_metrics=tiktok_extras)

    # Top / bottom performers
    scored = sorted(
        [e for e in this_week if e.get("impressions", 0) > 10],
        key=lambda x: x.get("save_rate", 0),
        reverse=True,
    )
    top_posts = scored[:5]
    bottom_posts = scored[-5:] if len(scored) >= 5 else []

    # Account-level trends
    account_trends = _compute_account_trends(entries)

    # TikTok-specific: add shares/likes to week summary
    total_views = sum(e.get("impressions", 0) for e in this_week)
    total_saves = sum(e.get("saves", 0) for e in this_week)
    total_shares = sum(e.get("shares", 0) for e in this_week)
    total_likes = sum(e.get("likes", 0) for e in this_week)
    total_comments = sum(e.get("comments", 0) for e in this_week)

    return {
        "week_summary": {
            "total_posts": len(this_week),
            "total_views": total_views,
            "total_saves": total_saves,
            "total_shares": total_shares,
            "total_likes": total_likes,
            "total_comments": total_comments,
        },
        "by_topic": by_topic,
        "by_angle": by_angle,
        "by_structure": by_structure,
        "by_hook_type": by_hook_type,
        "by_template_family": by_template,
        "top_posts": [_post_summary(p) for p in top_posts],
        "bottom_posts": [_post_summary(p) for p in bottom_posts],
        "account_trends": account_trends,
        "all_time_post_count": len([e for e in entries if e.get("pin_id")]),
    }


def load_previous_analysis() -> str:
    """Load the most recent TikTok weekly analysis for trend comparison."""
    TIKTOK_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    analysis_files = sorted(TIKTOK_ANALYSIS_DIR.glob("*-w*-review.md"), reverse=True)
    if not analysis_files:
        logger.info("No previous TikTok weekly analysis found")
        return ""

    latest = analysis_files[0]
    logger.info("Loading previous TikTok analysis: %s", latest.name)

    try:
        return latest.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to read previous analysis: %s", e)
        return ""


def save_analysis(analysis: str, year: Optional[int] = None, week: Optional[int] = None) -> Path:
    """Save the analysis to the TikTok weekly analysis directory."""
    TIKTOK_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today()
    if year is None:
        year = today.isocalendar()[0]
    if week is None:
        week = today.isocalendar()[1]

    filename = f"{year}-w{week:02d}-review.md"
    output_path = TIKTOK_ANALYSIS_DIR / filename

    tmp = output_path.with_suffix(".tmp")
    try:
        tmp.write_text(analysis, encoding="utf-8")
        tmp.replace(output_path)
        logger.info("TikTok analysis saved to %s", output_path)
    except OSError as e:
        logger.error("Failed to save analysis: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise

    return output_path


def _post_summary(entry: dict) -> dict:
    """Create a concise summary of a post for the analysis context."""
    return {
        "pin_id": entry.get("pin_id"),
        "title": entry.get("title", ""),
        "topic": entry.get("topic"),
        "angle": entry.get("angle"),
        "structure": entry.get("structure"),
        "hook_type": entry.get("hook_type"),
        "template_family": entry.get("template_family"),
        "impressions": entry.get("impressions", 0),
        "saves": entry.get("saves", 0),
        "shares": entry.get("shares", 0),
        "likes": entry.get("likes", 0),
        "comments": entry.get("comments", 0),
        "save_rate": entry.get("save_rate", 0),
    }


def _aggregate_list(entries: list[dict]) -> dict:
    """Aggregate metrics for a list of TikTok entries."""
    if not entries:
        return {
            "count": 0, "views": 0, "saves": 0, "shares": 0,
            "likes": 0, "comments": 0, "save_rate": 0.0, "share_rate": 0.0,
        }

    total_views = sum(e.get("impressions", 0) for e in entries)
    total_saves = sum(e.get("saves", 0) for e in entries)
    total_shares = sum(e.get("shares", 0) for e in entries)
    total_likes = sum(e.get("likes", 0) for e in entries)
    total_comments = sum(e.get("comments", 0) for e in entries)

    return {
        "count": len(entries),
        "views": total_views,
        "saves": total_saves,
        "shares": total_shares,
        "likes": total_likes,
        "comments": total_comments,
        "save_rate": round(total_saves / total_views, 6) if total_views > 0 else 0.0,
        "share_rate": round(total_shares / total_views, 6) if total_views > 0 else 0.0,
    }


def _compute_account_trends(entries: list[dict]) -> dict:
    """Compute account-level trends: this week vs last week vs 4-week rolling avg."""
    today = date.today()

    def _week_metrics(start: date, end: date) -> dict:
        start_str = start.isoformat()
        end_str = end.isoformat()
        week_entries = [
            e for e in entries
            if start_str < e.get("posted_date", "") <= end_str
        ]
        return _aggregate_list(week_entries)

    this_week = _week_metrics(today - timedelta(days=7), today)
    last_week = _week_metrics(today - timedelta(days=14), today - timedelta(days=7))

    weekly_totals = []
    for w in range(1, 5):
        w_start = today - timedelta(days=7 * (w + 1))
        w_end = today - timedelta(days=7 * w)
        weekly_totals.append(_week_metrics(w_start, w_end))

    if weekly_totals:
        avg_views = sum(w["views"] for w in weekly_totals) / len(weekly_totals)
        avg_saves = sum(w["saves"] for w in weekly_totals) / len(weekly_totals)
        avg_shares = sum(w["shares"] for w in weekly_totals) / len(weekly_totals)
        rolling_avg = {
            "views": round(avg_views),
            "saves": round(avg_saves),
            "shares": round(avg_shares),
            "save_rate": round(avg_saves / avg_views, 6) if avg_views > 0 else 0.0,
            "share_rate": round(avg_shares / avg_views, 6) if avg_views > 0 else 0.0,
        }
    else:
        rolling_avg = {"views": 0, "saves": 0, "shares": 0}

    return {
        "this_week": this_week,
        "last_week": last_week,
        "rolling_4wk_avg": rolling_avg,
    }


def _generate_fallback_analysis(context: dict, year: int, week: int) -> str:
    """Generate a data-only analysis when Claude API is unavailable."""
    from datetime import datetime

    lines = [
        f"# TikTok Weekly Analysis: {year}-W{week:02d}",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "**Note:** Claude API was unavailable. This is a data-only report.",
        "",
        "## Summary",
        f"- Posts this week: {context['week_summary']['total_posts']}",
        f"- Total views: {context['week_summary']['total_views']:,}",
        f"- Total saves: {context['week_summary']['total_saves']:,}",
        f"- Total shares: {context['week_summary']['total_shares']:,}",
        f"- Total likes: {context['week_summary']['total_likes']:,}",
        f"- Total comments: {context['week_summary']['total_comments']:,}",
        "",
    ]

    # Top posts
    lines.append("## Top Performing Posts")
    for post in context.get("top_posts", []):
        lines.append(
            f"- **{post.get('title', 'N/A')[:60]}** "
            f"({post.get('topic')}, {post.get('angle')}): "
            f"{post.get('impressions', 0)} views, {post.get('saves', 0)} saves, "
            f"save_rate={post.get('save_rate', 0):.4f}"
        )
    lines.append("")

    # Per-attribute tables
    for dim_name, dim_key in [
        ("Topic", "by_topic"),
        ("Angle", "by_angle"),
        ("Structure", "by_structure"),
        ("Hook Type", "by_hook_type"),
        ("Template Family", "by_template_family"),
    ]:
        dim_data = context.get(dim_key, {})
        if dim_data:
            lines.append(f"## By {dim_name}")
            lines.append(f"| {dim_name} | Count | Views | Saves | Save Rate |")
            lines.append("|---|---|---|---|---|")
            for value, metrics in sorted(dim_data.items(), key=lambda x: x[1].get("saves", 0), reverse=True):
                lines.append(
                    f"| {value} | {metrics['count']} | {metrics.get('impressions', 0):,} | "
                    f"{metrics.get('saves', 0):,} | {metrics.get('save_rate', 0):.4f} |"
                )
            lines.append("")

    # Account trends
    trends = context.get("account_trends", {})
    if trends:
        lines.append("## Account Trends")
        for period, data in trends.items():
            if isinstance(data, dict):
                lines.append(
                    f"- **{period}**: {data.get('views', 0)} views, "
                    f"{data.get('saves', 0)} saves, "
                    f"save_rate={data.get('save_rate', 0):.4f}"
                )
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    from src.shared.content_memory import generate_content_memory_summary

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if "--demo" in sys.argv:
        print("=== Demo mode: weekly_analysis (TikTok) ===")
        entries = load_content_log()
        entries = [e for e in entries if (e.get("channel") or "pinterest") == "tiktok"]
        entries = compute_derived_metrics(entries)
        print(f"TikTok entries loaded: {len(entries)}")

        context = build_analysis_context(entries)
        print(f"\nWeek summary: {json.dumps(context['week_summary'], indent=2)}")

        print("\nLoading strategy context...")
        strategy_ctx = load_strategy_context()
        print(f"Strategy doc loaded: {len(strategy_ctx.get('strategy_doc', ''))} chars")

        print("\nCross-channel summary:")
        xc = generate_cross_channel_summary(exclude_channel="tiktok")
        print(xc)
    else:
        print("Running TikTok weekly performance analysis...")
        try:
            analysis = run_weekly_analysis()
            print(f"Analysis complete. Length: {len(analysis)} chars")
        except Exception as e:
            logger.error("TikTok weekly analysis failed: %s", e, exc_info=True)
            sys.exit(1)
