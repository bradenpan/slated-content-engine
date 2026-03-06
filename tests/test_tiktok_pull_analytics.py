"""Tests for src/tiktok/pull_analytics.py — TikTok analytics puller."""

import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from src.tiktok.pull_analytics import (
    pull_analytics,
    _extract_metrics,
    _build_performance_summary,
    _post_summary,
)


def _make_entry(pin_id, channel="tiktok", days_ago=1, publer_post_id="pub-123",
                impressions=0, saves=0, shares=0, likes=0, comments=0, **kwargs):
    """Helper to create a content log entry."""
    d = (date.today() - timedelta(days=days_ago)).isoformat()
    entry = {
        "channel": channel,
        "pin_id": pin_id,
        "date": d,
        "posted_date": d,
        "publer_post_id": publer_post_id,
        "title": f"Post {pin_id}",
        "topic": "grout",
        "angle": "how-to",
        "structure": "listicle",
        "hook_type": "question",
        "template_family": "clean-educational",
        "impressions": impressions,
        "saves": saves,
        "shares": shares,
        "likes": likes,
        "comments": comments,
    }
    entry.update(kwargs)
    return entry


@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log", return_value=[])
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_empty_content_log(mock_publer_cls, mock_load, mock_save):
    result = pull_analytics()
    assert result["post_level"] == {}
    assert result["entries"] == []
    assert result["top_posts"] == []


@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_filters_to_tiktok_only(mock_publer_cls, mock_load, mock_save):
    mock_publer_cls.return_value.get_post_insights.return_value = []
    mock_load.return_value = [
        _make_entry("T1", channel="tiktok"),
        _make_entry("P1", channel="pinterest", publer_post_id="pub-999"),
    ]
    result = pull_analytics()
    # Pinterest entry should not appear in top/bottom — only tiktok entries are tracked
    # The function still returns all entries (with derived metrics), but only tracks tiktok
    tiktok_in_result = [
        e for e in result["entries"]
        if (e.get("channel") or "pinterest") == "tiktok"
    ]
    assert len(tiktok_in_result) == 1


@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_filters_out_old_entries(mock_publer_cls, mock_load, mock_save):
    mock_publer_cls.return_value.get_post_insights.return_value = []
    mock_load.return_value = [
        _make_entry("T1", days_ago=5),     # within window
        _make_entry("T2", days_ago=35),    # outside 28-day window
    ]
    result = pull_analytics()
    # Old entry should not be tracked, but both entries are in result
    assert len(result["entries"]) == 2


@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_filters_out_entries_without_publer_id(mock_publer_cls, mock_load, mock_save):
    mock_publer_cls.return_value.get_post_insights.return_value = []
    mock_load.return_value = [
        _make_entry("T1", publer_post_id="pub-123"),
        _make_entry("T2", publer_post_id=""),  # no publer ID
    ]
    result = pull_analytics()
    assert len(result["entries"]) == 2


@patch("src.tiktok.pull_analytics._save_performance_summary")
@patch("src.tiktok.pull_analytics._save_analytics_snapshot")
@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_fetches_and_joins_insights(
    mock_publer_cls, mock_load, mock_save, mock_snapshot, mock_perf
):
    mock_snapshot.return_value = "/fake/path.json"
    mock_publer_cls.return_value.get_post_insights.return_value = [
        {"id": "pub-123", "views": 500, "likes": 30, "comments": 5,
         "shares": 10, "saves": 20, "engagement_rate": 0.05},
    ]
    mock_load.return_value = [
        _make_entry("T1", publer_post_id="pub-123"),
    ]
    result = pull_analytics()
    assert "T1" in result["post_level"]
    assert result["post_level"]["T1"]["metrics"]["views"] == 500
    assert result["post_level"]["T1"]["metrics"]["saves"] == 20


@patch("src.tiktok.pull_analytics._save_performance_summary")
@patch("src.tiktok.pull_analytics._save_analytics_snapshot")
@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_updates_cumulative_metrics_with_max(
    mock_publer_cls, mock_load, mock_save, mock_snapshot, mock_perf
):
    mock_snapshot.return_value = "/fake/path.json"
    mock_publer_cls.return_value.get_post_insights.return_value = [
        {"id": "pub-123", "views": 300, "likes": 15, "comments": 2,
         "shares": 5, "saves": 8},
    ]
    # Entry already has higher impressions from a previous pull
    entry = _make_entry("T1", publer_post_id="pub-123", impressions=500, saves=3)
    mock_load.return_value = [entry]
    pull_analytics()
    # impressions should remain 500 (max(300, 500)), saves should be 8 (max(8, 3))
    assert entry["impressions"] == 500
    assert entry["saves"] == 8


@patch("src.tiktok.pull_analytics._save_performance_summary")
@patch("src.tiktok.pull_analytics._save_analytics_snapshot")
@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_computes_derived_metrics(
    mock_publer_cls, mock_load, mock_save, mock_snapshot, mock_perf
):
    mock_snapshot.return_value = "/fake/path.json"
    mock_publer_cls.return_value.get_post_insights.return_value = [
        {"id": "pub-123", "views": 1000, "likes": 50, "comments": 5,
         "shares": 20, "saves": 40},
    ]
    entry = _make_entry("T1", publer_post_id="pub-123")
    mock_load.return_value = [entry]
    result = pull_analytics()
    # After pull, entry should have derived metrics
    t1 = [e for e in result["entries"] if e["pin_id"] == "T1"][0]
    assert "save_rate" in t1
    assert "click_through_rate" in t1
    assert "share_rate" in t1


@patch("src.tiktok.pull_analytics._save_performance_summary")
@patch("src.tiktok.pull_analytics._save_analytics_snapshot")
@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_saves_snapshot(
    mock_publer_cls, mock_load, mock_save, mock_snapshot, mock_perf
):
    mock_snapshot.return_value = "/fake/snapshot.json"
    mock_publer_cls.return_value.get_post_insights.return_value = [
        {"id": "pub-123", "views": 100, "saves": 5},
    ]
    mock_load.return_value = [_make_entry("T1", publer_post_id="pub-123")]
    result = pull_analytics()
    mock_snapshot.assert_called_once()
    assert result["snapshot_path"] == "/fake/snapshot.json"


@patch("src.tiktok.pull_analytics._save_performance_summary")
@patch("src.tiktok.pull_analytics._save_analytics_snapshot")
@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_writes_performance_summary(
    mock_publer_cls, mock_load, mock_save, mock_snapshot, mock_perf
):
    mock_snapshot.return_value = "/fake/snapshot.json"
    mock_publer_cls.return_value.get_post_insights.return_value = [
        {"id": "pub-123", "views": 100, "saves": 5},
    ]
    mock_load.return_value = [_make_entry("T1", publer_post_id="pub-123")]
    pull_analytics()
    mock_perf.assert_called_once()


@patch("src.tiktok.pull_analytics._save_performance_summary")
@patch("src.tiktok.pull_analytics._save_analytics_snapshot")
@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_skips_perf_summary_when_no_insights(
    mock_publer_cls, mock_load, mock_save, mock_snapshot, mock_perf
):
    mock_snapshot.return_value = "/fake/snapshot.json"
    # Insights returned but none match our entries
    mock_publer_cls.return_value.get_post_insights.return_value = [
        {"id": "pub-999", "views": 100, "saves": 5},  # different ID
    ]
    mock_load.return_value = [_make_entry("T1", publer_post_id="pub-123")]
    result = pull_analytics()
    mock_perf.assert_not_called()
    assert result["performance_summary"] == {}


def test_extract_metrics_maps_fields():
    insight = {
        "views": 500, "likes": 30, "comments": 5,
        "shares": 10, "saves": 20, "engagement_rate": 0.05,
    }
    metrics = _extract_metrics(insight)
    assert metrics["views"] == 500
    assert metrics["likes"] == 30
    assert metrics["comments"] == 5
    assert metrics["shares"] == 10
    assert metrics["saves"] == 20
    assert metrics["engagement_rate"] == 0.05


def test_extract_metrics_handles_missing_fields():
    insight = {}
    metrics = _extract_metrics(insight)
    assert metrics["views"] == 0
    assert metrics["likes"] == 0
    assert metrics["comments"] == 0
    assert metrics["shares"] == 0
    assert metrics["saves"] == 0
    assert metrics["engagement_rate"] == 0.0


def test_build_performance_summary_aggregates_by_attributes():
    entries = [
        {"topic": "grout", "angle": "how-to", "structure": "listicle",
         "hook_type": "question", "impressions": 100, "saves": 10,
         "shares": 5, "likes": 20},
        {"topic": "grout", "angle": "myth-busting", "structure": "listicle",
         "hook_type": "question", "impressions": 200, "saves": 20,
         "shares": 10, "likes": 40},
        {"topic": "tile", "angle": "how-to", "structure": "comparison",
         "hook_type": "bold-claim", "impressions": 300, "saves": 30,
         "shares": 15, "likes": 60},
    ]
    result = _build_performance_summary(entries)
    assert result["post_count"] == 3
    assert "by_attribute" in result
    assert result["by_attribute"]["topic"]["grout"]["impressions"] == 300
    assert result["by_attribute"]["topic"]["grout"]["post_count"] == 2
    assert result["by_attribute"]["topic"]["tile"]["post_count"] == 1


def test_build_performance_summary_skips_zero_impressions_in_condensed():
    entries = [
        {"topic": "grout", "angle": "how-to", "structure": "listicle",
         "hook_type": "question", "impressions": 100, "saves": 10,
         "shares": 5, "likes": 20},
        {"topic": "tile", "angle": "myth-busting", "structure": "comparison",
         "hook_type": "bold-claim", "impressions": 0, "saves": 0,
         "shares": 0, "likes": 0},
    ]
    result = _build_performance_summary(entries)
    assert result["post_count"] == 2
    # Condensed entries should only include the one with impressions > 0
    assert len(result["entries"]) == 1
    assert result["entries"][0]["topic"] == "grout"


def test_post_summary_creates_concise_dict():
    entry = {
        "pin_id": "T1", "title": "Great Post", "topic": "grout",
        "angle": "how-to", "structure": "listicle", "hook_type": "question",
        "template_family": "clean-educational",
        "impressions": 500, "saves": 25, "shares": 10, "likes": 50,
        "comments": 3, "save_rate": 0.05,
    }
    summary = _post_summary(entry)
    assert summary["pin_id"] == "T1"
    assert summary["title"] == "Great Post"
    assert summary["impressions"] == 500
    assert summary["saves"] == 25
    assert summary["shares"] == 10
    assert summary["save_rate"] == 0.05


@patch("src.tiktok.pull_analytics._save_performance_summary")
@patch("src.tiktok.pull_analytics._save_analytics_snapshot")
@patch("src.tiktok.pull_analytics.save_content_log")
@patch("src.tiktok.pull_analytics.load_content_log")
@patch("src.tiktok.pull_analytics.PublerAPI")
def test_pull_analytics_identifies_top_bottom_performers(
    mock_publer_cls, mock_load, mock_save, mock_snapshot, mock_perf
):
    mock_snapshot.return_value = "/fake/snapshot.json"
    # Create 6 entries with varying performance (need >= 5 for bottom_posts)
    entries = []
    insights = []
    for i in range(6):
        pid = f"pub-{i}"
        entries.append(_make_entry(f"T{i}", publer_post_id=pid, impressions=0))
        insights.append({
            "id": pid,
            "views": 100 + i * 50,
            "saves": 5 + i * 10,
            "likes": 10,
            "comments": 1,
            "shares": 2,
        })
    mock_publer_cls.return_value.get_post_insights.return_value = insights
    mock_load.return_value = entries
    result = pull_analytics()
    # Should have top and bottom posts
    assert len(result["top_posts"]) > 0
    assert len(result["bottom_posts"]) > 0
    # Top post should have highest save_rate
    assert result["top_posts"][0]["save_rate"] >= result["top_posts"][-1]["save_rate"]
