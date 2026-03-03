"""
Monthly Strategy Review

Runs the monthly deep analysis using Claude Opus for deeper reasoning.
Scheduled on the 1st Monday of each month via monthly-review.yml.

This is the one place where strategic decisions are recommended (not
just tactical adjustments). The human reviews and decides which
recommendations to adopt.

Input:
- 30 days of analytics data
- All weekly analyses from the past month (4-5 files)
- Current strategy document
- Content performance data aggregated by:
  - Content pillar/type
  - Keyword theme
  - Board
  - Image source (stock vs AI vs template)
  - Pin type (plan-level vs. recipe pull vs. fresh treatment)
  - Treatment number (do Treatment 2-5 pins perform differently?)
  - Content age (are older pins still generating engagement?)

Output:
- Month-over-month trend analysis
- Content pillar performance ranking + recommendations
- Keyword strategy assessment (add/deprioritize)
- Board architecture assessment (density, underperforming boards)
- Posting cadence analysis
- Template/format analysis
- Image source analysis
- Fresh pin effectiveness
- Content age analysis (compounding measurement)
- Recommended strategy adjustments (specific, actionable)
- Next month's focus areas

Saved to analysis/monthly/YYYY-MM-review.md
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from src.shared.apis.claude_api import ClaudeAPI
from src.shared.apis.sheets_api import SheetsAPI
from src.shared.apis.slack_notify import SlackNotify
from src.shared.utils.content_log import load_content_log
from src.shared.analytics_utils import (
    compute_derived_metrics,
    aggregate_by_dimension,
)
from src.shared.paths import ANALYSIS_DIR as _ANALYSIS_BASE, STRATEGY_DIR, DATA_DIR

logger = logging.getLogger(__name__)

ANALYSIS_DIR = _ANALYSIS_BASE / "monthly"
WEEKLY_DIR = _ANALYSIS_BASE / "weekly"


def run_monthly_review(month: Optional[int] = None, year: Optional[int] = None, claude=None, sheets=None, slack=None) -> str:
    """
    Run the full monthly strategy review.

    Steps:
    1. Load content-log.jsonl with full month of data
    2. Load all weekly analyses from the past month (4-5 files)
    3. Load current strategy document
    4. Compute 30-day multi-dimensional aggregates
    5. Call Claude Opus with monthly_review.md prompt
    6. Save to analysis/monthly/YYYY-MM-review.md
    7. Write monthly highlights to Google Sheet
    8. Send Slack notification: "Monthly review ready"

    Args:
        month: Month number (1-12). If None, uses current month.
        year: Year. If None, uses current year.

    Returns:
        str: Monthly review markdown with strategy recommendations.
    """
    today = date.today()
    if month is None:
        month = today.month
    if year is None:
        year = today.year

    logger.info("Running monthly review for %d-%02d", year, month)

    # Step 1: Load content log with full month of data
    entries = load_content_log()
    entries = compute_derived_metrics(entries)
    logger.info("Loaded %d total content log entries", len(entries))

    # Step 2: Load weekly analyses from the past month
    weekly_analyses = load_weekly_analyses(month, year)
    logger.info("Loaded %d weekly analyses for the month", len(weekly_analyses))

    # Step 3: Load current strategy document
    strategy_doc = load_current_strategy()

    # Step 4: Compute 30-day aggregates
    monthly_context = build_monthly_context(entries, weekly_analyses, year, month)

    # Step 4b: Load seasonal context
    seasonal_context = _load_seasonal_context()

    # Step 5: Call Claude Opus for monthly review
    try:
        claude = claude or ClaudeAPI()
        review_md = claude.run_monthly_review(
            monthly_data=monthly_context,
            weekly_analyses=weekly_analyses,
            current_strategy=strategy_doc,
            seasonal_context=seasonal_context,
        )
    except Exception as e:
        logger.error("Claude monthly review failed: %s", e)
        # Fall back to data-only report
        review_md = _generate_fallback_review(monthly_context, year, month)

    # Step 6: Save to file
    output_path = save_monthly_review(review_md, year, month)
    logger.info("Monthly review saved to %s", output_path)

    # Step 7: Write highlights to Google Sheet
    try:
        sheets = sheets or SheetsAPI()
        sheets.update_dashboard({
            "monthly_review_date": f"{year}-{month:02d}",
            "monthly_review_path": str(output_path),
        })
    except Exception as e:
        logger.warning("Failed to update Google Sheet with monthly review: %s", e)

    # Step 8: Send Slack notification
    try:
        slack = slack or SlackNotify()
        summary_lines = review_md.split("\n")[:10]
        brief_summary = "\n".join(summary_lines)
        # Pass the repo-relative path (not absolute) for clean GitHub link construction
        repo_relative_path = f"analysis/monthly/{output_path.name}"
        slack.notify_monthly_review_ready(brief_summary, review_path=repo_relative_path)
    except Exception as e:
        logger.warning("Failed to send Slack notification: %s", e)

    return review_md


def load_weekly_analyses(month: int, year: int) -> list[str]:
    """
    Load all weekly analyses from a specific month.

    Finds analysis files whose ISO week falls within the given month.
    Weekly analysis files are named YYYY-wNN-review.md.

    Args:
        month: Month number (1-12).
        year: Year (e.g., 2026).

    Returns:
        list[str]: Weekly analysis markdown texts, in chronological order.
    """
    WEEKLY_DIR.mkdir(parents=True, exist_ok=True)

    # Determine which ISO weeks fall within this month
    # We look for weeks where any day of the week falls in the target month
    target_weeks = set()
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)

    current = first_day
    while current <= last_day:
        iso_year, iso_week, _ = current.isocalendar()
        target_weeks.add((iso_year, iso_week))
        current += timedelta(days=1)

    # Load matching files
    analyses = []
    for iso_year, iso_week in sorted(target_weeks):
        filename = f"{iso_year}-w{iso_week:02d}-review.md"
        filepath = WEEKLY_DIR / filename
        if filepath.exists():
            try:
                text = filepath.read_text(encoding="utf-8")
                analyses.append(text)
                logger.debug("Loaded weekly analysis: %s", filename)
            except OSError as e:
                logger.warning("Failed to read %s: %s", filename, e)

    logger.info(
        "Loaded %d weekly analyses for %d-%02d (checked %d weeks)",
        len(analyses), year, month, len(target_weeks),
    )
    return analyses


def load_current_strategy() -> str:
    """
    Load the current strategy document.

    Returns:
        str: Full text of strategy/current-strategy.md,
             or empty string if not found.
    """
    strategy_path = STRATEGY_DIR / "current-strategy.md"
    if not strategy_path.exists():
        logger.warning("Strategy document not found: %s", strategy_path)
        return ""

    try:
        return strategy_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.error("Failed to read strategy document: %s", e)
        return ""


def build_monthly_context(
    entries: list[dict],
    weekly_analyses: list[str],
    year: int,
    month: int,
) -> dict:
    """
    Build the context for the monthly review prompt.

    Computes 30-day multi-dimensional aggregates, month-over-month
    comparison, and specialized analyses (keyword saturation, board
    density, fresh pin effectiveness, content age).

    Args:
        entries: Full content log with analytics.
        weekly_analyses: Weekly analyses from the month.
        year: Review year.
        month: Review month.

    Returns:
        dict: Multi-dimensional performance context for Claude Opus.
    """
    today = date.today()
    thirty_days_ago = (today - timedelta(days=30)).isoformat()
    sixty_days_ago = (today - timedelta(days=60)).isoformat()

    # Filter to this month's entries
    # Exclude blog_deployer placeholder entries (pin_id=None, 0 metrics)
    # so they don't inflate counts or dilute averages.
    month_entries = [
        e for e in entries
        if e.get("posted_date", "") >= thirty_days_ago
        and e.get("pin_id")
    ]

    # Previous month's entries (for month-over-month comparison)
    prev_month_entries = [
        e for e in entries
        if sixty_days_ago <= e.get("posted_date", "") < thirty_days_ago
        and e.get("pin_id")
    ]

    logger.info(
        "Monthly context: %d entries this month, %d entries previous month",
        len(month_entries), len(prev_month_entries),
    )

    # --- Standard dimension aggregates ---
    by_pillar = aggregate_by_dimension(month_entries, "pillar")
    by_content_type = aggregate_by_dimension(month_entries, "content_type")
    by_keyword = aggregate_by_dimension(month_entries, "primary_keyword")
    by_board = aggregate_by_dimension(month_entries, "board")
    by_template = aggregate_by_dimension(month_entries, "template")
    by_image_source = aggregate_by_dimension(month_entries, "image_source")
    by_funnel = aggregate_by_dimension(month_entries, "funnel_layer")
    by_pin_type = aggregate_by_dimension(month_entries, "pin_type")
    by_treatment = aggregate_by_dimension(month_entries, "treatment_number")

    # Previous month aggregates for comparison
    prev_by_pillar = aggregate_by_dimension(prev_month_entries, "pillar")

    # --- Month-over-month comparison ---
    this_month_totals = _aggregate_entries(month_entries)
    prev_month_totals = _aggregate_entries(prev_month_entries)

    mom_comparison = {
        "this_month": this_month_totals,
        "prev_month": prev_month_totals,
        "delta": {},
    }
    for metric in ["impressions", "saves", "outbound_clicks", "pin_clicks"]:
        this_val = this_month_totals.get(metric, 0)
        prev_val = prev_month_totals.get(metric, 0)
        if prev_val > 0:
            pct_change = round(((this_val - prev_val) / prev_val) * 100, 1)
        else:
            pct_change = None  # Cannot compute percentage change from zero
        mom_comparison["delta"][metric] = {
            "absolute": this_val - prev_val,
            "pct_change": pct_change,
        }

    # --- Pillar-level trends ---
    pillar_trends = {}
    for pillar_key in set(list(by_pillar.keys()) + list(prev_by_pillar.keys())):
        this_data = by_pillar.get(pillar_key, {"impressions": 0, "saves": 0, "save_rate": 0})
        prev_data = prev_by_pillar.get(pillar_key, {"impressions": 0, "saves": 0, "save_rate": 0})
        trend = "stable"
        if this_data.get("save_rate", 0) > prev_data.get("save_rate", 0) * 1.1:
            trend = "improving"
        elif this_data.get("save_rate", 0) < prev_data.get("save_rate", 0) * 0.9:
            trend = "declining"

        pillar_trends[pillar_key] = {
            "this_month": this_data,
            "prev_month": prev_data,
            "trend": trend,
        }

    # Exclude placeholders from all-time analyses too
    posted_entries = [e for e in entries if e.get("pin_id")]

    # --- Keyword saturation analysis ---
    keyword_saturation = _analyze_keyword_saturation(posted_entries, thirty_days_ago)

    # --- Board density analysis ---
    board_density = _analyze_board_density(posted_entries)

    # --- Fresh pin effectiveness ---
    fresh_pin_analysis = _analyze_fresh_pin_effectiveness(month_entries)

    # --- Content age analysis (compounding measurement) ---
    content_age_analysis = _analyze_content_age(posted_entries)

    # --- Plan-level vs. recipe pin performance ---
    plan_vs_recipe = _analyze_plan_vs_recipe(month_entries)

    context = {
        "review_period": f"{year}-{month:02d}",
        "month_summary": this_month_totals,
        "mom_comparison": mom_comparison,
        "by_pillar": by_pillar,
        "by_content_type": by_content_type,
        "by_keyword": by_keyword,
        "by_board": by_board,
        "by_template": by_template,
        "by_image_source": by_image_source,
        "by_funnel_layer": by_funnel,
        "by_pin_type": by_pin_type,
        "by_treatment_number": by_treatment,
        "pillar_trends": pillar_trends,
        "keyword_saturation": keyword_saturation,
        "board_density": board_density,
        "fresh_pin_analysis": fresh_pin_analysis,
        "content_age_analysis": content_age_analysis,
        "plan_vs_recipe": plan_vs_recipe,
        "weekly_analyses_count": len(weekly_analyses),
        "total_pins_all_time": len(posted_entries),
        "total_pins_this_month": len(month_entries),
    }

    return context


def save_monthly_review(review: str, year: Optional[int] = None, month: Optional[int] = None) -> Path:
    """
    Save the monthly review to the monthly analysis directory.

    Filename format: YYYY-MM-review.md

    Args:
        review: Monthly review markdown.
        year: Year. Defaults to current year.
        month: Month. Defaults to current month.

    Returns:
        Path: Path to the saved file.
    """
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today()
    if year is None:
        year = today.year
    if month is None:
        month = today.month

    filename = f"{year}-{month:02d}-review.md"
    output_path = ANALYSIS_DIR / filename

    try:
        output_path.write_text(review, encoding="utf-8")
        logger.info("Monthly review saved to %s", output_path)
    except OSError as e:
        logger.error("Failed to save monthly review: %s", e)
        raise

    return output_path


# --- Analysis helper functions ---

def _aggregate_entries(entries: list[dict]) -> dict:
    """Compute aggregate metrics for a list of entries."""
    total_impressions = sum(e.get("impressions", 0) for e in entries)
    total_saves = sum(e.get("saves", 0) for e in entries)
    total_clicks = sum(e.get("outbound_clicks", 0) for e in entries)
    total_pin_clicks = sum(e.get("pin_clicks", 0) for e in entries)

    return {
        "count": len(entries),
        "impressions": total_impressions,
        "saves": total_saves,
        "outbound_clicks": total_clicks,
        "pin_clicks": total_pin_clicks,
        "save_rate": round(total_saves / total_impressions, 6) if total_impressions > 0 else 0.0,
        "click_through_rate": round(total_clicks / total_impressions, 6) if total_impressions > 0 else 0.0,
    }


def _analyze_keyword_saturation(entries: list[dict], since: str) -> dict:
    """
    Analyze keyword saturation: which keywords are plateauing?

    A keyword is considered "plateauing" if it has been used 3+ times in the
    last 30 days but its most recent pins show lower save rates than earlier ones.

    Args:
        entries: Full content log.
        since: Date string for the lookback period.

    Returns:
        dict: keyword -> {count, avg_save_rate, trend}
    """
    keyword_pins = defaultdict(list)

    for entry in entries:
        kw = entry.get("primary_keyword", "")
        if not kw:
            continue
        keyword_pins[kw].append({
            "posted_date": entry.get("posted_date", ""),
            "save_rate": entry.get("save_rate", 0),
            "impressions": entry.get("impressions", 0),
        })

    result = {}
    for kw, pins in keyword_pins.items():
        # Sort by date
        pins_sorted = sorted(pins, key=lambda x: x["posted_date"])
        recent_pins = [p for p in pins_sorted if p["posted_date"] >= since]

        if not recent_pins:
            continue

        recent_rates = [p["save_rate"] for p in recent_pins if p["impressions"] > 0]
        all_rates = [p["save_rate"] for p in pins_sorted if p["impressions"] > 0]

        avg_recent = sum(recent_rates) / len(recent_rates) if recent_rates else 0
        avg_all = sum(all_rates) / len(all_rates) if all_rates else 0

        trend = "stable"
        if len(recent_pins) >= 3 and avg_all > 0:
            if avg_recent < avg_all * 0.8:
                trend = "plateauing"
            elif avg_recent > avg_all * 1.2:
                trend = "growing"

        result[kw] = {
            "total_uses": len(pins_sorted),
            "recent_uses": len(recent_pins),
            "avg_save_rate_recent": round(avg_recent, 6),
            "avg_save_rate_all": round(avg_all, 6),
            "trend": trend,
        }

    return result


def _analyze_board_density(entries: list[dict]) -> dict:
    """
    Analyze board density: how many pins per board?

    Identifies boards that are underpopulated (< 20 pins) or
    overconcentrated.

    Args:
        entries: Full content log.

    Returns:
        dict: board_name -> {pin_count, status}
    """
    board_counts = defaultdict(int)
    for entry in entries:
        board = entry.get("board") or "unknown"
        board_counts[board] += 1

    # Load board structure for expected boards
    board_structure_path = STRATEGY_DIR / "pinterest" / "board-structure.json"
    expected_boards = set()
    try:
        if board_structure_path.exists():
            with open(board_structure_path, "r", encoding="utf-8") as f:
                bs = json.load(f)
            for board in bs.get("boards", []):
                expected_boards.add(board["name"])
    except Exception as e:
        logger.warning("Could not load board structure: %s", e)

    result = {}
    # Include boards we have pins for
    for board, count in board_counts.items():
        status = "healthy"
        if count < 20:
            status = "underpopulated"
        elif count > 100:
            status = "dense"
        result[board] = {"pin_count": count, "status": status}

    # Include expected boards with no pins yet
    for board in expected_boards:
        if board not in result:
            result[board] = {"pin_count": 0, "status": "empty"}

    return result


def _analyze_fresh_pin_effectiveness(entries: list[dict]) -> dict:
    """
    Analyze whether Treatment 2-5 pins perform differently than Treatment 1.

    Groups entries by treatment_number and compares save rates.

    Args:
        entries: Entries for the analysis period.

    Returns:
        dict: treatment_number -> {count, avg_save_rate, avg_impressions}
    """
    treatment_groups = defaultdict(list)
    for entry in entries:
        tn = entry.get("treatment_number", 1)
        treatment_groups[tn].append(entry)

    result = {}
    for tn, group_entries in sorted(treatment_groups.items()):
        impressions_list = [e.get("impressions", 0) for e in group_entries]
        save_rates = [e.get("save_rate", 0) for e in group_entries if e.get("impressions", 0) > 0]

        result[str(tn)] = {
            "count": len(group_entries),
            "avg_impressions": round(sum(impressions_list) / len(impressions_list)) if impressions_list else 0,
            "avg_save_rate": round(sum(save_rates) / len(save_rates), 6) if save_rates else 0.0,
            "total_saves": sum(e.get("saves", 0) for e in group_entries),
        }

    return result


def _analyze_content_age(entries: list[dict]) -> dict:
    """
    Analyze content age vs. performance (compounding measurement).

    Groups pins by age bucket (1-7d, 8-14d, 15-30d, 31-60d, 61-90d)
    and measures whether older pins are still generating engagement.

    Args:
        entries: Full content log.

    Returns:
        dict: age_bucket -> {count, avg_impressions, avg_saves, avg_save_rate}
    """
    today = date.today()
    age_buckets = {
        "1-7d": (1, 7),
        "8-14d": (8, 14),
        "15-30d": (15, 30),
        "31-60d": (31, 60),
        "61-90d": (61, 90),
    }

    bucket_entries = {bucket: [] for bucket in age_buckets}

    for entry in entries:
        posted_str = entry.get("posted_date", "")
        if not posted_str:
            continue
        try:
            posted_date = date.fromisoformat(posted_str)
        except ValueError:
            continue

        age_days = (today - posted_date).days
        for bucket, (min_days, max_days) in age_buckets.items():
            if min_days <= age_days <= max_days:
                bucket_entries[bucket].append(entry)
                break

    result = {}
    for bucket, b_entries in bucket_entries.items():
        if not b_entries:
            result[bucket] = {
                "count": 0,
                "avg_impressions": 0,
                "avg_saves": 0,
                "avg_save_rate": 0.0,
                "still_generating": False,
            }
            continue

        impr = [e.get("impressions", 0) for e in b_entries]
        saves = [e.get("saves", 0) for e in b_entries]
        rates = [e.get("save_rate", 0) for e in b_entries if e.get("impressions", 0) > 0]

        avg_impressions = sum(impr) / len(impr)
        avg_saves = sum(saves) / len(saves)
        avg_rate = sum(rates) / len(rates) if rates else 0.0

        # A pin is "still generating" if it has > 10 impressions and > 0 saves
        still_generating = avg_impressions > 10 and avg_saves > 0

        result[bucket] = {
            "count": len(b_entries),
            "avg_impressions": round(avg_impressions),
            "avg_saves": round(avg_saves, 1),
            "avg_save_rate": round(avg_rate, 6),
            "still_generating": still_generating,
        }

    return result


def _analyze_plan_vs_recipe(entries: list[dict]) -> dict:
    """
    Compare plan-level pin performance vs. standalone recipe pins.

    This is a key strategic signal per strategy Section 13.2.

    Args:
        entries: Entries for the analysis period.

    Returns:
        dict with keys: plan_level, recipe_pull, standalone_recipe, fresh_treatment
    """
    categories = {
        "plan_level": [],
        "recipe_pull": [],
        "standalone_recipe": [],
        "fresh_treatment": [],
    }

    for entry in entries:
        pin_type = entry.get("pin_type", "")
        content_type = entry.get("content_type", "")

        if pin_type == "recipe-pull":
            categories["recipe_pull"].append(entry)
        elif pin_type == "fresh-treatment":
            categories["fresh_treatment"].append(entry)
        elif content_type == "weekly-plan":
            categories["plan_level"].append(entry)
        elif content_type == "recipe":
            categories["standalone_recipe"].append(entry)

    result = {}
    for cat, cat_entries in categories.items():
        result[cat] = _aggregate_entries(cat_entries)

    return result


def _generate_fallback_review(context: dict, year: int, month: int) -> str:
    """
    Generate a data-only monthly review when Claude API is unavailable.

    Args:
        context: Monthly context dict.
        year: Year.
        month: Month.

    Returns:
        str: Markdown review (data only).
    """
    lines = [
        f"# Monthly Strategy Review: {year}-{month:02d}",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "**Note:** Claude Opus API was unavailable. This is a data-only report.",
        "",
        "## Month Summary",
    ]

    summary = context.get("month_summary", {})
    lines.append(f"- Pins posted: {summary.get('count', 0)}")
    lines.append(f"- Total impressions: {summary.get('impressions', 0):,}")
    lines.append(f"- Total saves: {summary.get('saves', 0):,}")
    lines.append(f"- Total outbound clicks: {summary.get('outbound_clicks', 0):,}")
    lines.append(f"- Save rate: {summary.get('save_rate', 0):.4f}")
    lines.append(f"- Click-through rate: {summary.get('click_through_rate', 0):.4f}")
    lines.append("")

    # Month-over-month
    mom = context.get("mom_comparison", {})
    delta = mom.get("delta", {})
    if delta:
        lines.append("## Month-over-Month Changes")
        for metric, change in delta.items():
            pct = change.get("pct_change")
            pct_str = f" ({pct:+.1f}%)" if pct is not None else " (N/A - no previous data)"
            lines.append(f"- {metric}: {change.get('absolute', 0):+,}{pct_str}")
        lines.append("")

    # Pillar performance
    lines.append("## Pillar Performance")
    for pillar, data in sorted(context.get("by_pillar", {}).items()):
        trend_info = context.get("pillar_trends", {}).get(pillar, {})
        trend = trend_info.get("trend", "unknown")
        lines.append(
            f"- **Pillar {pillar}**: {data['count']} pins, "
            f"{data['impressions']:,} impr, {data['saves']:,} saves, "
            f"save_rate={data['save_rate']:.4f}, trend={trend}"
        )
    lines.append("")

    # Board density
    lines.append("## Board Density")
    for board, data in sorted(context.get("board_density", {}).items()):
        lines.append(f"- {board}: {data['pin_count']} pins ({data['status']})")
    lines.append("")

    # Keyword saturation
    lines.append("## Keyword Saturation")
    sat = context.get("keyword_saturation", {})
    plateauing = {k: v for k, v in sat.items() if v.get("trend") == "plateauing"}
    growing = {k: v for k, v in sat.items() if v.get("trend") == "growing"}
    if plateauing:
        lines.append("\n**Plateauing keywords:**")
        for kw, data in plateauing.items():
            lines.append(f"- `{kw}`: {data['total_uses']} uses, save_rate={data['avg_save_rate_recent']:.4f}")
    if growing:
        lines.append("\n**Growing keywords:**")
        for kw, data in growing.items():
            lines.append(f"- `{kw}`: {data['total_uses']} uses, save_rate={data['avg_save_rate_recent']:.4f}")
    lines.append("")

    # Fresh pin effectiveness
    lines.append("## Fresh Pin Effectiveness (by Treatment Number)")
    for tn, data in sorted(context.get("fresh_pin_analysis", {}).items()):
        lines.append(
            f"- Treatment {tn}: {data['count']} pins, "
            f"avg_impressions={data['avg_impressions']}, "
            f"avg_save_rate={data['avg_save_rate']:.4f}"
        )
    lines.append("")

    # Content age analysis
    lines.append("## Content Age Analysis (Compounding)")
    for bucket, data in context.get("content_age_analysis", {}).items():
        still = "yes" if data.get("still_generating") else "no"
        lines.append(
            f"- {bucket}: {data['count']} pins, "
            f"avg_impr={data['avg_impressions']}, "
            f"avg_saves={data['avg_saves']}, "
            f"still_generating={still}"
        )
    lines.append("")

    # Plan vs. Recipe
    lines.append("## Plan-Level vs. Recipe Pin Performance")
    for cat, data in context.get("plan_vs_recipe", {}).items():
        lines.append(
            f"- **{cat}**: {data.get('count', 0)} pins, "
            f"save_rate={data.get('save_rate', 0):.4f}, "
            f"CTR={data.get('click_through_rate', 0):.4f}"
        )
    lines.append("")

    # Image source
    lines.append("## Image Source Performance")
    for src, data in sorted(context.get("by_image_source", {}).items()):
        lines.append(
            f"- {src}: {data['count']} pins, "
            f"save_rate={data['save_rate']:.4f}"
        )
    lines.append("")

    return "\n".join(lines)


def _load_seasonal_context() -> str:
    """
    Load the seasonal calendar and return the current seasonal window description.

    Reuses the same logic as generate_weekly_plan.get_current_seasonal_window().

    Returns:
        str: Current seasonal window description, or empty string if unavailable.
    """
    calendar_path = STRATEGY_DIR / "seasonal-calendar.json"
    try:
        if not calendar_path.exists():
            return ""
        calendar_data = json.loads(calendar_path.read_text(encoding="utf-8"))
        seasons = calendar_data.get("seasons", [])
        if not seasons:
            return ""

        current_month = date.today().month
        active_seasons = []
        for season in seasons:
            publish_months = season.get("publish_window_months", [])
            if current_month in publish_months:
                active_seasons.append(season)

        if not active_seasons:
            return f"Current month: {current_month}. No seasonal publish windows are active."

        lines = [f"Current month: {current_month}. Active seasonal windows:\n"]
        for s in active_seasons:
            priority = s.get("priority", "normal")
            priority_label = " [HIGH PRIORITY]" if priority == "high" else ""
            lines.append(f"**{s['name']}**{priority_label}")
            lines.append(f"  Content angle: {s.get('content_angle', '')}")
            lines.append(f"  Seasonal keywords: {', '.join(s.get('keywords', []))}")
            lines.append(f"  Relevant pillars: {s.get('relevant_pillars', [])}")
            lines.append("")
        return "\n".join(lines)

    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not load seasonal calendar: %s", e)
        return ""


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if "--demo" in sys.argv:
        print("=== Demo mode: monthly_review ===")
        entries = load_content_log()
        entries = compute_derived_metrics(entries)
        print(f"Content log entries: {len(entries)}")

        today = date.today()
        weekly = load_weekly_analyses(today.month, today.year)
        print(f"Weekly analyses loaded: {len(weekly)}")

        strategy = load_current_strategy()
        print(f"Strategy doc loaded: {len(strategy)} chars")

        context = build_monthly_context(entries, weekly, today.year, today.month)
        print(f"\nMonth summary: {json.dumps(context['month_summary'], indent=2)}")
        print(f"Board density: {json.dumps(context['board_density'], indent=2)}")
    else:
        month = int(sys.argv[1]) if len(sys.argv) > 1 else None
        year = int(sys.argv[2]) if len(sys.argv) > 2 else None
        print("Running monthly strategy review...")
        review = run_monthly_review(month=month, year=year)
        print(f"Monthly review complete. Length: {len(review)} chars")
