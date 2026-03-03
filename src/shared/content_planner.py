"""Shared content planning utilities.

Data-loading functions used by channel-specific planners to build context
for Claude-driven content planning.  Any channel planner (Pinterest, TikTok,
etc.) can import these to load strategy files, content memory, latest
analysis, and seasonal context.

These functions were extracted from generate_weekly_plan.py during the
multi-channel restructure (Phase 3).
"""

import json
import logging
from datetime import date
from pathlib import Path

from src.shared.paths import STRATEGY_DIR, ANALYSIS_DIR, DATA_DIR
from src.shared.content_memory import generate_content_memory_summary

logger = logging.getLogger(__name__)


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
