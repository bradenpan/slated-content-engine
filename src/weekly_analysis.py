"""
Weekly Performance Analysis

Analyzes the past week's Pinterest performance using Claude Sonnet.
Runs as part of the weekly-review.yml workflow (Monday early AM),
after pull_analytics.py.

Input context for Claude:
- This week's pin-level performance data
- Content plan vs. actual (what was posted, what was rejected, what failed)
- Per-content-type aggregate performance
- Per-keyword aggregate performance
- Per-board aggregate performance
- Per-pillar aggregate performance
- Per-funnel-layer aggregate performance
- Per-image-source aggregate performance
- Plan-level pin vs. standalone recipe pin performance
- Comparison to previous week
- Account-level trends (this week vs. last week vs. 4-week rolling avg)

Output (structured):
- Top 5 performing pins and why
- Bottom 5 performing pins and why
- Content type performance ranking
- Keyword performance insights
- Board performance insights
- Pillar-level performance ranking
- Specific recommendations for next week's plan
- Flags (declining metrics, content types to pause, keywords to add/remove)

Saved to analysis/weekly/YYYY-wNN-review.md
"""

import json
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from src.apis.claude_api import ClaudeAPI
from src.pull_analytics import (
    compute_derived_metrics,
    aggregate_by_dimension,
)
from src.paths import ANALYSIS_DIR as _ANALYSIS_BASE, DATA_DIR
from src.utils.content_log import load_content_log
from src.utils.content_memory import generate_content_memory_summary  # noqa: F401 — re-exported for weekly-review.yml

logger = logging.getLogger(__name__)

ANALYSIS_DIR = _ANALYSIS_BASE / "weekly"
PIN_SCHEDULE_PATH = DATA_DIR / "pin-schedule.json"
ANALYTICS_DIR = DATA_DIR / "analytics"


def run_weekly_analysis(week_number: Optional[int] = None) -> str:
    """
    Run the full weekly performance analysis.

    Steps:
    1. Load content-log.jsonl (with freshly updated analytics from pull_analytics)
    2. Load the current week's content plan (what was planned vs. posted)
    3. Load the previous week's analysis for trend comparison
    4. Compute aggregates across all dimensions
    5. Call Claude Sonnet with weekly_analysis.md prompt
    6. Save analysis to analysis/weekly/YYYY-wNN-review.md
    7. Return the analysis data (used by generate_weekly_plan.py as input)

    Args:
        week_number: ISO week number. If None, uses current week.

    Returns:
        str: The weekly analysis markdown.
    """
    today = date.today()
    if week_number is None:
        _, week_number, _ = today.isocalendar()

    iso_year = today.isocalendar()[0]
    logger.info("Running weekly analysis for %d-W%02d", iso_year, week_number)

    # Step 1: Load content log with freshly updated analytics
    entries = load_content_log()
    entries = compute_derived_metrics(entries)
    logger.info("Loaded %d content log entries", len(entries))

    # Step 2: Load content plan (what was planned for this week)
    content_plan = _load_content_plan()

    # Step 3: Load previous week's analysis
    previous_analysis = load_previous_analysis()

    # Step 4: Compute all aggregates
    analysis_context = build_analysis_context(entries, content_plan, previous_analysis)

    # Step 5: Call Claude for analysis
    try:
        claude = ClaudeAPI()
        analysis_md = claude.analyze_weekly_performance(
            performance_data=analysis_context,
            previous_analysis=previous_analysis,
            content_plan=content_plan,
        )
    except Exception as e:
        logger.error("Claude analysis failed: %s", e)
        # Fall back to a data-only report if Claude is unavailable
        analysis_md = _generate_fallback_analysis(analysis_context, iso_year, week_number)

    # Step 6: Save analysis
    output_path = save_analysis(analysis_md, iso_year, week_number)
    logger.info("Weekly analysis saved to %s", output_path)

    return analysis_md


def build_analysis_context(
    entries: list[dict],
    content_plan: Optional[dict] = None,
    previous_analysis: Optional[str] = None,
) -> dict:
    """
    Build the full context object for the weekly analysis prompt.

    Computes aggregates across every relevant dimension and structures
    them for Claude.

    Args:
        entries: Content log entries with up-to-date analytics.
        content_plan: What was planned vs. what was posted.
        previous_analysis: Last week's analysis text.

    Returns:
        dict: Structured context with all dimensions aggregated.
    """
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()

    # Separate this week's pins from all-time
    # Exclude blog_deployer placeholder entries (pin_id=None, 0 metrics)
    # so they don't inflate counts or dilute averages.
    this_week_entries = [
        e for e in entries
        if e.get("posted_date", "") >= week_ago
        and e.get("pin_id")
    ]

    # Per-dimension aggregates (this week)
    by_pillar = aggregate_by_dimension(this_week_entries, "pillar")
    by_content_type = aggregate_by_dimension(this_week_entries, "content_type")
    by_keyword = aggregate_by_dimension(this_week_entries, "primary_keyword")
    by_board = aggregate_by_dimension(this_week_entries, "board")
    by_funnel = aggregate_by_dimension(this_week_entries, "funnel_layer")
    by_template = aggregate_by_dimension(this_week_entries, "template")
    by_image_source = aggregate_by_dimension(this_week_entries, "image_source")
    by_pin_type = aggregate_by_dimension(this_week_entries, "pin_type")

    # All-time aggregates for trend context (exclude placeholders)
    posted_entries = [e for e in entries if e.get("pin_id")]
    all_by_pillar = aggregate_by_dimension(posted_entries, "pillar")

    # Top and bottom performing pins (by save_rate, with minimum impression threshold)
    sorted_by_saves = sorted(
        [e for e in this_week_entries if e.get("impressions", 0) > 10],
        key=lambda x: x.get("save_rate", 0),
        reverse=True,
    )
    top_pins = sorted_by_saves[:5]
    bottom_pins = sorted_by_saves[-5:] if len(sorted_by_saves) >= 5 else []

    # Plan-level pin performance vs. standalone recipe pin performance
    plan_level_entries = [
        e for e in this_week_entries
        if e.get("pin_type") in ("primary",) and e.get("content_type") == "weekly-plan"
    ]
    recipe_pull_entries = [
        e for e in this_week_entries
        if e.get("pin_type") == "recipe-pull"
    ]
    standalone_recipe_entries = [
        e for e in this_week_entries
        if e.get("content_type") == "recipe"
        and e.get("pin_type") != "recipe-pull"
    ]

    plan_vs_recipe = {
        "plan_level": _aggregate_list(plan_level_entries),
        "recipe_pull": _aggregate_list(recipe_pull_entries),
        "standalone_recipe": _aggregate_list(standalone_recipe_entries),
    }

    # Account-level trends: this week vs. last week vs. 4-week rolling avg
    account_trends = _compute_account_trends(posted_entries)

    # 4-week rolling average per pillar
    four_weeks_ago = (today - timedelta(days=28)).isoformat()
    rolling_entries = [
        e for e in entries
        if e.get("posted_date", "") >= four_weeks_ago
        and e.get("pin_id")
    ]
    rolling_by_pillar = aggregate_by_dimension(rolling_entries, "pillar")

    context = {
        "week_summary": {
            "total_pins_posted": len(this_week_entries),
            "total_impressions": sum(e.get("impressions", 0) for e in this_week_entries),
            "total_saves": sum(e.get("saves", 0) for e in this_week_entries),
            "total_outbound_clicks": sum(e.get("outbound_clicks", 0) for e in this_week_entries),
            "total_pin_clicks": sum(e.get("pin_clicks", 0) for e in this_week_entries),
        },
        "by_pillar": by_pillar,
        "by_content_type": by_content_type,
        "by_keyword": by_keyword,
        "by_board": by_board,
        "by_funnel_layer": by_funnel,
        "by_template": by_template,
        "by_image_source": by_image_source,
        "by_pin_type": by_pin_type,
        "top_pins": [_pin_summary(p) for p in top_pins],
        "bottom_pins": [_pin_summary(p) for p in bottom_pins],
        "plan_vs_recipe": plan_vs_recipe,
        "account_trends": account_trends,
        "all_time_by_pillar": all_by_pillar,
        "rolling_4wk_by_pillar": rolling_by_pillar,
        "content_plan": content_plan,
        "all_time_pin_count": len(posted_entries),
    }

    return context


def load_previous_analysis() -> str:
    """
    Load the most recent weekly analysis for trend comparison.

    Scans analysis/weekly/ for YYYY-wNN-review.md files and returns
    the most recent one.

    Returns:
        str: Previous analysis markdown, or empty string if none exists.
    """
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    analysis_files = sorted(ANALYSIS_DIR.glob("*-w*-review.md"), reverse=True)
    if not analysis_files:
        logger.info("No previous weekly analysis found")
        return ""

    latest = analysis_files[0]
    logger.info("Loading previous analysis: %s", latest.name)

    try:
        return latest.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Failed to read previous analysis: %s", e)
        return ""


def save_analysis(analysis: str, year: Optional[int] = None, week: Optional[int] = None) -> Path:
    """
    Save the analysis to the weekly analysis directory.

    Filename format: YYYY-wNN-review.md

    Args:
        analysis: Analysis markdown text.
        year: ISO year. Defaults to current year.
        week: ISO week number. Defaults to current week.

    Returns:
        Path: Path to the saved file.
    """
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today()
    if year is None:
        year = today.isocalendar()[0]
    if week is None:
        week = today.isocalendar()[1]

    filename = f"{year}-w{week:02d}-review.md"
    output_path = ANALYSIS_DIR / filename

    try:
        output_path.write_text(analysis, encoding="utf-8")
        logger.info("Analysis saved to %s", output_path)
    except OSError as e:
        logger.error("Failed to save analysis: %s", e)
        raise

    return output_path


# --- Helper functions ---

def _load_content_plan() -> Optional[dict]:
    """Load the current week's content plan (pin schedule)."""
    if not PIN_SCHEDULE_PATH.exists():
        logger.info("No pin schedule found at %s", PIN_SCHEDULE_PATH)
        return None

    try:
        with open(PIN_SCHEDULE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load pin schedule: %s", e)
        return None


def _pin_summary(entry: dict) -> dict:
    """Create a concise summary of a pin for the analysis context."""
    return {
        "pin_id": entry.get("pin_id"),
        "title": entry.get("title", ""),
        "pillar": entry.get("pillar"),
        "content_type": entry.get("content_type"),
        "board": entry.get("board"),
        "primary_keyword": entry.get("primary_keyword"),
        "impressions": entry.get("impressions", 0),
        "saves": entry.get("saves", 0),
        "outbound_clicks": entry.get("outbound_clicks", 0),
        "save_rate": entry.get("save_rate", 0),
        "click_through_rate": entry.get("click_through_rate", 0),
        "template": entry.get("template"),
        "image_source": entry.get("image_source"),
        "pin_type": entry.get("pin_type"),
        "treatment_number": entry.get("treatment_number"),
    }


def _aggregate_list(entries: list[dict]) -> dict:
    """Aggregate metrics for a list of entries into a summary dict."""
    if not entries:
        return {
            "count": 0,
            "impressions": 0,
            "saves": 0,
            "outbound_clicks": 0,
            "save_rate": 0.0,
            "click_through_rate": 0.0,
        }

    total_impressions = sum(e.get("impressions", 0) for e in entries)
    total_saves = sum(e.get("saves", 0) for e in entries)
    total_clicks = sum(e.get("outbound_clicks", 0) for e in entries)

    return {
        "count": len(entries),
        "impressions": total_impressions,
        "saves": total_saves,
        "outbound_clicks": total_clicks,
        "save_rate": round(total_saves / total_impressions, 6) if total_impressions > 0 else 0.0,
        "click_through_rate": round(total_clicks / total_impressions, 6) if total_impressions > 0 else 0.0,
    }


def _compute_account_trends(entries: list[dict]) -> dict:
    """
    Compute account-level trends: this week vs. last week vs. 4-week rolling average.

    Groups entries by week and computes weekly totals.

    Returns:
        dict with keys: this_week, last_week, rolling_4wk_avg
    """
    today = date.today()

    def _week_metrics(start: date, end: date) -> dict:
        start_str = start.isoformat()
        end_str = end.isoformat()
        week_entries = [
            e for e in entries
            if start_str <= e.get("posted_date", "") <= end_str
        ]
        return _aggregate_list(week_entries)

    # This week (last 7 days)
    this_week_start = today - timedelta(days=7)
    this_week = _week_metrics(this_week_start, today)

    # Last week (8-14 days ago)
    last_week_start = today - timedelta(days=14)
    last_week_end = today - timedelta(days=7)
    last_week = _week_metrics(last_week_start, last_week_end)

    # 4-week rolling average
    weekly_totals = []
    for w in range(4):
        w_start = today - timedelta(days=7 * (w + 1))
        w_end = today - timedelta(days=7 * w)
        weekly_totals.append(_week_metrics(w_start, w_end))

    if weekly_totals:
        avg_impressions = sum(w["impressions"] for w in weekly_totals) / len(weekly_totals)
        avg_saves = sum(w["saves"] for w in weekly_totals) / len(weekly_totals)
        avg_clicks = sum(w["outbound_clicks"] for w in weekly_totals) / len(weekly_totals)
        rolling_avg = {
            "impressions": round(avg_impressions),
            "saves": round(avg_saves),
            "outbound_clicks": round(avg_clicks),
            "save_rate": round(avg_saves / avg_impressions, 6) if avg_impressions > 0 else 0.0,
            "click_through_rate": round(avg_clicks / avg_impressions, 6) if avg_impressions > 0 else 0.0,
        }
    else:
        rolling_avg = {"impressions": 0, "saves": 0, "outbound_clicks": 0}

    return {
        "this_week": this_week,
        "last_week": last_week,
        "rolling_4wk_avg": rolling_avg,
    }


def _generate_fallback_analysis(context: dict, year: int, week: int) -> str:
    """
    Generate a data-only analysis report when Claude API is unavailable.

    This is a fallback that presents the raw aggregated data in markdown
    format without AI-generated insights.

    Args:
        context: The analysis context dict from build_analysis_context.
        year: ISO year.
        week: ISO week number.

    Returns:
        str: Markdown analysis (data only, no AI insights).
    """
    lines = [
        f"# Weekly Analysis: {year}-W{week:02d}",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "**Note:** Claude API was unavailable. This is a data-only report.",
        "",
        "## Summary",
        f"- Pins posted this week: {context['week_summary']['total_pins_posted']}",
        f"- Total impressions: {context['week_summary']['total_impressions']:,}",
        f"- Total saves: {context['week_summary']['total_saves']:,}",
        f"- Total outbound clicks: {context['week_summary']['total_outbound_clicks']:,}",
        f"- Total pin clicks: {context['week_summary']['total_pin_clicks']:,}",
        "",
    ]

    # Top pins
    lines.append("## Top Performing Pins")
    for pin in context.get("top_pins", []):
        lines.append(
            f"- **{pin.get('title', 'N/A')[:60]}** "
            f"(P{pin.get('pillar')}, {pin.get('content_type')}): "
            f"{pin.get('impressions', 0)} impr, {pin.get('saves', 0)} saves, "
            f"save_rate={pin.get('save_rate', 0):.4f}"
        )
    lines.append("")

    # Per-dimension tables
    for dim_name, dim_key in [
        ("Pillar", "by_pillar"),
        ("Content Type", "by_content_type"),
        ("Board", "by_board"),
        ("Funnel Layer", "by_funnel_layer"),
        ("Template", "by_template"),
        ("Image Source", "by_image_source"),
    ]:
        dim_data = context.get(dim_key, {})
        if dim_data:
            lines.append(f"## By {dim_name}")
            lines.append("| {0} | Count | Impressions | Saves | Save Rate | Outbound Clicks | CTR |".format(dim_name))
            lines.append("|---|---|---|---|---|---|---|")
            for value, metrics in sorted(dim_data.items(), key=lambda x: x[1]["saves"], reverse=True):
                lines.append(
                    f"| {value} | {metrics['count']} | {metrics['impressions']:,} | "
                    f"{metrics['saves']:,} | {metrics['save_rate']:.4f} | "
                    f"{metrics['outbound_clicks']:,} | {metrics['click_through_rate']:.4f} |"
                )
            lines.append("")

    # Plan vs. Recipe comparison
    pvr = context.get("plan_vs_recipe", {})
    if pvr:
        lines.append("## Plan-Level vs. Recipe Pin Performance")
        for label, data in pvr.items():
            lines.append(
                f"- **{label}**: {data.get('count', 0)} pins, "
                f"{data.get('impressions', 0)} impr, "
                f"{data.get('saves', 0)} saves, "
                f"save_rate={data.get('save_rate', 0):.4f}"
            )
        lines.append("")

    # Account trends
    trends = context.get("account_trends", {})
    if trends:
        lines.append("## Account Trends")
        for period, data in trends.items():
            if isinstance(data, dict):
                lines.append(
                    f"- **{period}**: {data.get('impressions', 0)} impr, "
                    f"{data.get('saves', 0)} saves, "
                    f"save_rate={data.get('save_rate', 0):.4f}"
                )
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if "--demo" in sys.argv:
        print("=== Demo mode: weekly_analysis ===")
        entries = load_content_log()
        entries = compute_derived_metrics(entries)
        print(f"Entries loaded: {len(entries)}")

        context = build_analysis_context(entries)
        print(f"\nWeek summary: {json.dumps(context['week_summary'], indent=2)}")

        print("\nGenerating content memory summary...")
        memory = generate_content_memory_summary()
        print(f"Memory summary length: {len(memory)} chars")
        print(memory[:500])
    elif "--memory" in sys.argv:
        print("Generating content memory summary...")
        memory = generate_content_memory_summary()
        print(memory)
    else:
        print("Running weekly performance analysis...")
        analysis = run_weekly_analysis()
        print(f"Analysis complete. Length: {len(analysis)} chars")
