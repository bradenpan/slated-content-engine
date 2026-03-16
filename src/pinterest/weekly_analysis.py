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

from src.shared.apis.claude_api import ClaudeAPI
from src.shared.analytics_utils import (
    compute_derived_metrics,
    aggregate_by_dimension,
)
from src.shared.content_planner import load_strategy_context
from src.shared.content_memory import generate_content_memory_summary, generate_cross_channel_summary
from src.shared.paths import ANALYSIS_DIR as _ANALYSIS_BASE, DATA_DIR
from src.shared.utils.content_log import load_content_log

logger = logging.getLogger(__name__)

ANALYSIS_DIR = _ANALYSIS_BASE / "weekly"
PIN_SCHEDULE_PATH = DATA_DIR / "pin-schedule.json"
ANALYTICS_DIR = DATA_DIR / "analytics"


def run_weekly_analysis(week_number: Optional[int] = None, channel: str = "pinterest") -> str:
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
    # Channel filter: only include entries for the target channel
    entries = [e for e in entries if (e.get("channel") or "pinterest") == channel]
    entries = compute_derived_metrics(entries)
    logger.info("Loaded %d %s content log entries", len(entries), channel)

    # Step 2: Load content plan (what was planned for this week)
    content_plan = _load_content_plan()

    # Step 2b: Load strategy context and content memory
    strategy_context = load_strategy_context()
    strategy_doc = strategy_context.get("strategy_doc", "")
    content_memory = generate_content_memory_summary(channel="pinterest")
    cross_channel = generate_cross_channel_summary(exclude_channel="pinterest")

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
            strategy_doc=strategy_doc,
            content_memory=content_memory,
            cross_channel_summary=cross_channel,
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

    Uses raw analytics snapshots to compute period-specific deltas
    (what happened THIS week) across ALL active pins, not just
    recently-posted ones.  Falls back to cumulative content-log
    metrics when snapshots are unavailable.

    Args:
        entries: Content log entries with up-to-date analytics.
        content_plan: What was planned vs. what was posted.
        previous_analysis: Last week's analysis text.

    Returns:
        dict: Structured context with all dimensions aggregated.
    """
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()

    # All posted pins (exclude blog_deployer placeholders with pin_id=None)
    posted_entries = [e for e in entries if e.get("pin_id")]

    # --- Period-specific data from raw snapshot diffs ---
    snapshots = _load_raw_snapshots(num_weeks=4)

    if len(snapshots) >= 2:
        period_entries = _compute_period_deltas(
            snapshots[0][1], snapshots[1][1], posted_entries,
        )
        logger.info(
            "Period deltas computed from %s vs %s: %d pins",
            snapshots[0][0], snapshots[1][0], len(period_entries),
        )
    elif len(snapshots) == 1:
        # Only one snapshot — use its raw metrics as the period data
        period_entries = _snapshot_to_entries(snapshots[0][1], posted_entries)
        logger.info(
            "Single snapshot %s: using raw metrics for %d pins",
            snapshots[0][0], len(period_entries),
        )
    else:
        # No snapshots — fall back to cumulative content-log data
        period_entries = posted_entries
        logger.warning("No analytics snapshots found; using cumulative metrics")

    # Content execution tracking: pins POSTED this week
    new_pins = [
        e for e in posted_entries
        if e.get("posted_date", "") >= week_ago
    ]

    # Per-dimension aggregates (period metrics — what happened this week)
    by_pillar = aggregate_by_dimension(period_entries, "pillar")
    by_content_type = aggregate_by_dimension(period_entries, "content_type")
    by_keyword = aggregate_by_dimension(period_entries, "primary_keyword")
    by_board = aggregate_by_dimension(period_entries, "board")
    by_funnel = aggregate_by_dimension(period_entries, "funnel_layer")
    by_template = aggregate_by_dimension(period_entries, "template")
    by_image_source = aggregate_by_dimension(period_entries, "image_source")
    by_pin_type = aggregate_by_dimension(period_entries, "pin_type")

    # All-time cumulative aggregates for trend context
    all_by_pillar = aggregate_by_dimension(posted_entries, "pillar")

    # Top and bottom performing pins (by period impressions)
    sorted_by_impressions = sorted(
        [e for e in period_entries if e.get("impressions", 0) > 0],
        key=lambda x: x.get("impressions", 0),
        reverse=True,
    )
    top_pins = sorted_by_impressions[:5]
    bottom_pins = sorted_by_impressions[-5:] if len(sorted_by_impressions) >= 5 else []

    # Plan-level pin performance vs. standalone recipe pin performance
    plan_level_entries = [
        e for e in period_entries
        if e.get("pin_type") in ("primary",) and e.get("content_type") == "weekly-plan"
    ]
    recipe_pull_entries = [
        e for e in period_entries
        if e.get("pin_type") == "recipe-pull"
    ]
    standalone_recipe_entries = [
        e for e in period_entries
        if e.get("content_type") == "recipe"
        and e.get("pin_type") != "recipe-pull"
    ]

    plan_vs_recipe = {
        "plan_level": _aggregate_list(plan_level_entries),
        "recipe_pull": _aggregate_list(recipe_pull_entries),
        "standalone_recipe": _aggregate_list(standalone_recipe_entries),
    }

    # Account-level trends from snapshot diffs
    account_trends = _compute_account_trends_from_snapshots(snapshots)

    # 4-week rolling average per pillar (from snapshots if available)
    rolling_by_pillar = all_by_pillar  # fallback: cumulative
    if len(snapshots) >= 2:
        # Combine all period entries across available snapshots
        all_period = []
        for i in range(min(len(snapshots) - 1, 4)):
            all_period.extend(
                _compute_period_deltas(
                    snapshots[i][1], snapshots[i + 1][1], posted_entries,
                )
            )
        if all_period:
            rolling_by_pillar = aggregate_by_dimension(all_period, "pillar")

    # Data quality check
    data_quality = _check_data_freshness(posted_entries)

    context = {
        "week_summary": {
            "total_pins_active": len(posted_entries),
            "new_pins_this_week": len(new_pins),
            "total_impressions": sum(e.get("impressions", 0) for e in period_entries),
            "total_saves": sum(e.get("saves", 0) for e in period_entries),
            "total_outbound_clicks": sum(e.get("outbound_clicks", 0) for e in period_entries),
            "total_pin_clicks": sum(e.get("pin_clicks", 0) for e in period_entries),
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
        "data_quality_notes": data_quality,
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


def _load_raw_snapshots(num_weeks: int = 4) -> list[tuple[str, dict]]:
    """
    Load recent raw analytics snapshots from data/analytics/.

    Args:
        num_weeks: Maximum number of snapshots to load.

    Returns:
        List of (week_label, snapshot_dict) sorted newest-first.
        Empty list if no snapshots exist.
    """
    if not ANALYTICS_DIR.exists():
        return []

    files = sorted(ANALYTICS_DIR.glob("*-w*-raw.json"), reverse=True)
    results = []
    for f in files[:num_weeks]:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            label = f.stem.replace("-raw", "")  # e.g. "2026-w12"
            results.append((label, data))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load snapshot %s: %s", f.name, e)

    return results


def _compute_period_deltas(
    current_snapshot: dict,
    previous_snapshot: dict,
    entries: list[dict],
) -> list[dict]:
    """
    Compute per-pin metric deltas between two consecutive snapshots.

    Each snapshot's period_metrics are cumulative from the pin's post date.
    The delta (current - previous) gives what happened between the two
    snapshot dates.

    Args:
        current_snapshot: The more recent snapshot dict.
        previous_snapshot: The older snapshot dict.
        entries: Content log entries (for metadata: pillar, keyword, etc.).

    Returns:
        List of entry-like dicts with impressions/saves/outbound_clicks/pin_clicks
        set to period delta values.  Includes content-log metadata for each pin.
    """
    cur_pins = current_snapshot.get("pin_analytics", {})
    prev_pins = previous_snapshot.get("pin_analytics", {})

    # Build lookup from pin_id to content-log entry for metadata
    entry_by_pin = {e["pin_id"]: e for e in entries if e.get("pin_id")}

    results = []
    for pin_id, cur_data in cur_pins.items():
        cur_m = cur_data.get("period_metrics", {})
        prev_m = prev_pins.get(pin_id, {}).get("period_metrics", {})

        delta = {
            "impressions": max(0, cur_m.get("IMPRESSION", 0) - prev_m.get("IMPRESSION", 0)),
            "saves": max(0, cur_m.get("SAVE", 0) - prev_m.get("SAVE", 0)),
            "pin_clicks": max(0, cur_m.get("PIN_CLICK", 0) - prev_m.get("PIN_CLICK", 0)),
            "outbound_clicks": max(0, cur_m.get("OUTBOUND_CLICK", 0) - prev_m.get("OUTBOUND_CLICK", 0)),
        }

        # Merge with content-log metadata
        base = entry_by_pin.get(pin_id, {})
        result = {**base, **delta}
        result["pin_id"] = pin_id
        results.append(result)

    return results


def _snapshot_to_entries(
    snapshot: dict,
    entries: list[dict],
) -> list[dict]:
    """
    Convert a single snapshot's raw metrics into entry-like dicts.

    Used when only one snapshot exists (no previous to diff against).
    """
    pin_analytics = snapshot.get("pin_analytics", {})
    entry_by_pin = {e["pin_id"]: e for e in entries if e.get("pin_id")}

    results = []
    for pin_id, pin_data in pin_analytics.items():
        m = pin_data.get("period_metrics", {})
        base = entry_by_pin.get(pin_id, {})
        result = {
            **base,
            "pin_id": pin_id,
            "impressions": m.get("IMPRESSION", 0),
            "saves": m.get("SAVE", 0),
            "pin_clicks": m.get("PIN_CLICK", 0),
            "outbound_clicks": m.get("OUTBOUND_CLICK", 0),
        }
        results.append(result)

    return results


def _check_data_freshness(entries: list[dict]) -> str:
    """
    Check analytics data freshness and quality.

    Returns a warning string if issues are found, empty string otherwise.
    """
    warnings = []

    pull_dates = [
        e.get("last_analytics_pull", "")
        for e in entries
        if e.get("last_analytics_pull")
    ]
    if pull_dates:
        latest_pull = max(pull_dates)
        try:
            pull_date = date.fromisoformat(latest_pull)
            age_days = (date.today() - pull_date).days
            if age_days > 2:
                warnings.append(
                    f"Analytics data is {age_days} days old (last pull: {latest_pull}). "
                    "Metrics may not reflect recent activity."
                )
        except ValueError:
            pass

    total_impressions = sum(e.get("impressions", 0) for e in entries)
    total_saves = sum(e.get("saves", 0) for e in entries)
    total_clicks = sum(e.get("outbound_clicks", 0) for e in entries)
    if total_impressions > 0 and total_saves == 0 and total_clicks == 0:
        warnings.append(
            f"{int(total_impressions)} impressions but 0 saves and 0 outbound clicks across "
            f"all pins. The Pinterest dashboard may show different numbers due to API "
            "reporting lag."
        )

    return " | ".join(warnings) if warnings else ""


def _compute_account_trends_from_snapshots(
    snapshots: list[tuple[str, dict]],
) -> dict:
    """
    Compute account-level trends from raw analytics snapshots.

    Diffs consecutive snapshots to get per-week totals, then computes
    week-over-week changes and a rolling average.

    Args:
        snapshots: List of (week_label, snapshot_dict) sorted newest-first.

    Returns:
        dict with keys: this_week, last_week, rolling_4wk_avg
    """
    def _snapshot_totals(snap: dict) -> dict:
        """Sum all pin metrics in a snapshot."""
        total = {"impressions": 0, "saves": 0, "outbound_clicks": 0, "pin_clicks": 0}
        for pin_data in snap.get("pin_analytics", {}).values():
            m = pin_data.get("period_metrics", {})
            total["impressions"] += m.get("IMPRESSION", 0)
            total["saves"] += m.get("SAVE", 0)
            total["outbound_clicks"] += m.get("OUTBOUND_CLICK", 0)
            total["pin_clicks"] += m.get("PIN_CLICK", 0)
        return total

    def _diff_totals(newer: dict, older: dict) -> dict:
        return {
            k: max(0, newer.get(k, 0) - older.get(k, 0))
            for k in ("impressions", "saves", "outbound_clicks", "pin_clicks")
        }

    def _with_rates(totals: dict) -> dict:
        imp = totals.get("impressions", 0)
        return {
            **totals,
            "save_rate": round(totals["saves"] / imp, 6) if imp > 0 else 0.0,
            "click_through_rate": round(totals["outbound_clicks"] / imp, 6) if imp > 0 else 0.0,
        }

    empty = _with_rates({"impressions": 0, "saves": 0, "outbound_clicks": 0, "pin_clicks": 0})

    if len(snapshots) < 2:
        # Not enough data for trends
        if snapshots:
            this_week = _with_rates(_snapshot_totals(snapshots[0][1]))
        else:
            this_week = empty
        return {
            "this_week": this_week,
            "last_week": empty,
            "rolling_4wk_avg": empty,
        }

    # Compute per-week deltas by diffing consecutive snapshot cumulative totals
    cumulative = [_snapshot_totals(s[1]) for s in snapshots]
    weekly_deltas = []
    for i in range(len(cumulative) - 1):
        weekly_deltas.append(_diff_totals(cumulative[i], cumulative[i + 1]))

    this_week = _with_rates(weekly_deltas[0]) if weekly_deltas else empty
    last_week = _with_rates(weekly_deltas[1]) if len(weekly_deltas) > 1 else empty

    # Rolling average across all available weekly deltas (up to 4)
    if weekly_deltas:
        n = len(weekly_deltas)
        avg_imp = sum(d["impressions"] for d in weekly_deltas) / n
        avg_saves = sum(d["saves"] for d in weekly_deltas) / n
        avg_clicks = sum(d["outbound_clicks"] for d in weekly_deltas) / n
        rolling_avg = {
            "impressions": round(avg_imp),
            "saves": round(avg_saves),
            "outbound_clicks": round(avg_clicks),
            "save_rate": round(avg_saves / avg_imp, 6) if avg_imp > 0 else 0.0,
            "click_through_rate": round(avg_clicks / avg_imp, 6) if avg_imp > 0 else 0.0,
        }
    else:
        rolling_avg = empty

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
        f"- Active pins: {context['week_summary']['total_pins_active']}",
        f"- New pins this week: {context['week_summary']['new_pins_this_week']}",
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

    # Data quality notes
    dq = context.get("data_quality_notes", "")
    if dq:
        lines.append("## Data Quality Notes")
        lines.append(dq)
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
        print("=== Demo mode: weekly_analysis ===")
        entries = load_content_log()
        # Apply channel filter
        channel = "pinterest"
        entries = [e for e in entries if (e.get("channel") or "pinterest") == channel]
        entries = compute_derived_metrics(entries)
        print(f"Entries loaded ({channel}): {len(entries)}")

        context = build_analysis_context(entries)
        print(f"\nWeek summary: {json.dumps(context['week_summary'], indent=2)}")

        print("\nLoading strategy context...")
        strategy_ctx = load_strategy_context()
        print(f"Strategy doc loaded: {len(strategy_ctx.get('strategy_doc', ''))} chars")

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
