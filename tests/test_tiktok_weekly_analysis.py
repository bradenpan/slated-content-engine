"""Tests for src/tiktok/weekly_analysis.py — TikTok weekly performance analysis."""

import sys
import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# Mock anthropic before importing weekly_analysis (which imports ClaudeAPI)
sys.modules.setdefault("anthropic", MagicMock())

from src.tiktok.weekly_analysis import (
    run_weekly_analysis,
    build_analysis_context,
    load_previous_analysis,
    save_analysis,
    _generate_fallback_analysis,
    _aggregate_list,
    _compute_account_trends,
)


def _make_entry(pin_id, days_ago=1, impressions=100, saves=10, shares=5,
                likes=20, comments=2, topic="grout", angle="how-to",
                structure="listicle", hook_type="question", **kwargs):
    """Helper to create a TikTok content log entry with derived metrics."""
    d = (date.today() - timedelta(days=days_ago)).isoformat()
    entry = {
        "channel": "tiktok",
        "pin_id": pin_id,
        "date": d,
        "posted_date": d,
        "title": f"Post {pin_id}",
        "topic": topic,
        "angle": angle,
        "structure": structure,
        "hook_type": hook_type,
        "template_family": "clean-educational",
        "impressions": impressions,
        "saves": saves,
        "shares": shares,
        "likes": likes,
        "comments": comments,
        "outbound_clicks": 0,
        "pin_clicks": 0,
    }
    entry.update(kwargs)
    return entry


@patch("src.tiktok.weekly_analysis.save_analysis")
@patch("src.tiktok.weekly_analysis.generate_cross_channel_summary", return_value="No cross-channel data.")
@patch("src.tiktok.weekly_analysis.load_content_memory", return_value="content memory text")
@patch("src.tiktok.weekly_analysis.load_strategy_context", return_value={"strategy_doc": "strategy text"})
@patch("src.tiktok.weekly_analysis.load_previous_analysis", return_value="")
@patch("src.tiktok.weekly_analysis.load_content_log")
@patch("src.tiktok.weekly_analysis.ClaudeAPI")
def test_run_weekly_analysis_loads_and_filters_tiktok(
    mock_claude_cls, mock_load, mock_prev, mock_strategy,
    mock_memory, mock_cross, mock_save_analysis
):
    mock_claude_cls.return_value.analyze_tiktok_performance.return_value = "# Analysis"
    mock_save_analysis.return_value = Path("/fake/analysis.md")
    mock_load.return_value = [
        _make_entry("T1", days_ago=2),
        {"channel": "pinterest", "pin_id": "P1", "posted_date": date.today().isoformat(),
         "impressions": 50, "saves": 5},
    ]
    result = run_weekly_analysis(week_number=10)
    assert result == "# Analysis"
    mock_claude_cls.return_value.analyze_tiktok_performance.assert_called_once()


@patch("src.tiktok.weekly_analysis.save_analysis")
@patch("src.tiktok.weekly_analysis.generate_cross_channel_summary", return_value="")
@patch("src.tiktok.weekly_analysis.load_content_memory", return_value="")
@patch("src.tiktok.weekly_analysis.load_strategy_context", return_value={"strategy_doc": ""})
@patch("src.tiktok.weekly_analysis.load_previous_analysis", return_value="")
@patch("src.tiktok.weekly_analysis.load_content_log")
@patch("src.tiktok.weekly_analysis.ClaudeAPI")
def test_run_weekly_analysis_calls_claude(
    mock_claude_cls, mock_load, mock_prev, mock_strategy,
    mock_memory, mock_cross, mock_save_analysis
):
    mock_claude_cls.return_value.analyze_tiktok_performance.return_value = "# Weekly Review"
    mock_save_analysis.return_value = Path("/fake/analysis.md")
    mock_load.return_value = [_make_entry("T1")]
    result = run_weekly_analysis(week_number=10)
    call_kwargs = mock_claude_cls.return_value.analyze_tiktok_performance.call_args
    assert "performance_data" in call_kwargs.kwargs or len(call_kwargs.args) > 0


@patch("src.tiktok.weekly_analysis.save_analysis")
@patch("src.tiktok.weekly_analysis.generate_cross_channel_summary", return_value="")
@patch("src.tiktok.weekly_analysis.load_content_memory", return_value="")
@patch("src.tiktok.weekly_analysis.load_strategy_context", return_value={"strategy_doc": ""})
@patch("src.tiktok.weekly_analysis.load_previous_analysis", return_value="")
@patch("src.tiktok.weekly_analysis.load_content_log")
@patch("src.tiktok.weekly_analysis.ClaudeAPI")
def test_run_weekly_analysis_fallback_on_claude_failure(
    mock_claude_cls, mock_load, mock_prev, mock_strategy,
    mock_memory, mock_cross, mock_save_analysis
):
    mock_claude_cls.return_value.analyze_tiktok_performance.side_effect = RuntimeError("API down")
    mock_save_analysis.return_value = Path("/fake/analysis.md")
    mock_load.return_value = [_make_entry("T1")]
    result = run_weekly_analysis(week_number=10)
    assert "Claude API was unavailable" in result
    assert "data-only report" in result


def test_build_analysis_context_computes_week_summary():
    entries = [
        _make_entry("T1", days_ago=2, impressions=100, saves=10, shares=5, likes=20, comments=3),
        _make_entry("T2", days_ago=3, impressions=200, saves=20, shares=10, likes=40, comments=6),
    ]
    context = build_analysis_context(entries)
    ws = context["week_summary"]
    assert ws["total_posts"] == 2
    assert ws["total_views"] == 300
    assert ws["total_saves"] == 30
    assert ws["total_shares"] == 15
    assert ws["total_likes"] == 60
    assert ws["total_comments"] == 9


def test_build_analysis_context_computes_all_attribute_dims():
    entries = [
        _make_entry("T1", days_ago=2, topic="grout", angle="how-to",
                     structure="listicle", hook_type="question"),
    ]
    context = build_analysis_context(entries)
    assert "by_topic" in context
    assert "by_angle" in context
    assert "by_structure" in context
    assert "by_hook_type" in context
    assert "by_template_family" in context


def test_build_analysis_context_identifies_top_bottom_posts():
    entries = []
    for i in range(6):
        entries.append(_make_entry(
            f"T{i}", days_ago=2,
            impressions=100 + i * 50,
            saves=5 + i * 10,
        ))
    context = build_analysis_context(entries)
    assert len(context["top_posts"]) > 0
    # With 6 entries above 10 impressions, we should have bottom posts
    assert len(context["bottom_posts"]) == 5


def test_build_analysis_context_computes_account_trends():
    entries = [
        _make_entry("T1", days_ago=2, impressions=100, saves=10, shares=5),
        _make_entry("T2", days_ago=10, impressions=200, saves=20, shares=10),
    ]
    context = build_analysis_context(entries)
    trends = context["account_trends"]
    assert "this_week" in trends
    assert "last_week" in trends
    assert "rolling_4wk_avg" in trends
    assert trends["this_week"]["views"] == 100  # T1 is this week
    assert trends["last_week"]["views"] == 200  # T2 is last week


def test_load_previous_analysis_returns_empty_when_no_files(tmp_path):
    with patch("src.tiktok.weekly_analysis.TIKTOK_ANALYSIS_DIR", tmp_path):
        result = load_previous_analysis()
        assert result == ""


def test_load_previous_analysis_loads_most_recent(tmp_path):
    # Create two analysis files
    (tmp_path / "2026-w08-review.md").write_text("# Week 8 analysis", encoding="utf-8")
    (tmp_path / "2026-w09-review.md").write_text("# Week 9 analysis", encoding="utf-8")
    with patch("src.tiktok.weekly_analysis.TIKTOK_ANALYSIS_DIR", tmp_path):
        result = load_previous_analysis()
        assert "Week 9" in result


def test_save_analysis_writes_to_correct_path(tmp_path):
    with patch("src.tiktok.weekly_analysis.TIKTOK_ANALYSIS_DIR", tmp_path):
        output = save_analysis("# Test Analysis", year=2026, week=10)
        assert output.name == "2026-w10-review.md"
        assert output.read_text(encoding="utf-8") == "# Test Analysis"


def test_save_analysis_uses_atomic_write(tmp_path):
    """Verify save_analysis uses tmp+rename pattern (file exists after write)."""
    with patch("src.tiktok.weekly_analysis.TIKTOK_ANALYSIS_DIR", tmp_path):
        output = save_analysis("# Atomic Test", year=2026, week=11)
        assert output.exists()
        # No .tmp file should remain
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0


def test_generate_fallback_analysis_produces_valid_markdown():
    context = {
        "week_summary": {
            "total_posts": 3,
            "total_views": 1000,
            "total_saves": 50,
            "total_shares": 20,
            "total_likes": 100,
            "total_comments": 15,
        },
        "by_topic": {"grout": {"count": 2, "impressions": 600, "saves": 30, "save_rate": 0.05}},
        "by_angle": {},
        "by_structure": {},
        "by_hook_type": {},
        "by_template_family": {},
        "top_posts": [
            {"title": "Great Post", "topic": "grout", "angle": "how-to",
             "impressions": 500, "saves": 25, "save_rate": 0.05},
        ],
        "bottom_posts": [],
        "account_trends": {
            "this_week": {"views": 500, "saves": 25, "save_rate": 0.05},
            "last_week": {"views": 300, "saves": 15, "save_rate": 0.05},
        },
    }
    md = _generate_fallback_analysis(context, 2026, 10)
    assert "# TikTok Weekly Analysis: 2026-W10" in md
    assert "Claude API was unavailable" in md
    assert "Posts this week: 3" in md
    assert "Total views: 1,000" in md
    assert "Great Post" in md


def test_aggregate_list_handles_empty_entries():
    result = _aggregate_list([])
    assert result["count"] == 0
    assert result["views"] == 0
    assert result["saves"] == 0
    assert result["shares"] == 0
    assert result["save_rate"] == 0.0
    assert result["share_rate"] == 0.0


def test_aggregate_list_sums_correctly():
    entries = [
        {"impressions": 100, "saves": 10, "shares": 5, "likes": 20, "comments": 3},
        {"impressions": 200, "saves": 20, "shares": 10, "likes": 40, "comments": 6},
    ]
    result = _aggregate_list(entries)
    assert result["count"] == 2
    assert result["views"] == 300
    assert result["saves"] == 30
    assert result["shares"] == 15
    assert result["save_rate"] == round(30 / 300, 6)
    assert result["share_rate"] == round(15 / 300, 6)


def test_compute_account_trends_handles_zero_views():
    # Entries with no impressions
    entries = [
        _make_entry("T1", days_ago=2, impressions=0, saves=0, shares=0, likes=0, comments=0),
    ]
    trends = _compute_account_trends(entries)
    assert trends["this_week"]["save_rate"] == 0.0
    assert trends["this_week"]["share_rate"] == 0.0
    assert trends["rolling_4wk_avg"]["save_rate"] == 0.0
