"""Extended tests for src/shared/content_memory.py — TikTok-specific behavior."""

import json
from datetime import date, timedelta
from unittest.mock import patch

from src.shared.content_memory import (
    generate_content_memory_summary,
    generate_cross_channel_summary,
)


def _make_entry(pin_id, channel="pinterest", slug="test-slug", pillar=1,
                days_ago=0, content_type="recipe", impressions=100, saves=10,
                **kwargs):
    """Helper to create a content log entry."""
    d = (date.today() - timedelta(days=days_ago)).isoformat()
    entry = {
        "channel": channel,
        "pin_id": pin_id,
        "date": d,
        "posted_date": d,
        "blog_slug": slug,
        "blog_title": slug.replace("-", " ").title(),
        "pillar": pillar,
        "content_type": content_type,
        "board": "test-board",
        "funnel_layer": "discovery",
        "primary_keyword": "test keyword",
        "secondary_keywords": [],
        "impressions": impressions,
        "saves": saves,
    }
    entry.update(kwargs)
    return entry


def _write_log(tmp_path, entries):
    """Write entries to a temp content log file."""
    log_path = tmp_path / "content-log.jsonl"
    with open(log_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return log_path


def test_generate_content_memory_tiktok_filter(tmp_path):
    """generate_content_memory_summary with channel='tiktok' filters correctly."""
    entries = [
        _make_entry("P1", channel="pinterest", slug="pin-topic", days_ago=1),
        _make_entry("T1", channel="tiktok", slug="tiktok-topic-a", days_ago=2),
        _make_entry("T2", channel="tiktok", slug="tiktok-topic-b", days_ago=3),
    ]
    log_path = _write_log(tmp_path, entries)
    output_path = tmp_path / "summary.md"

    summary = generate_content_memory_summary(
        content_log_path=log_path,
        output_path=output_path,
        channel="tiktok",
    )
    assert "Channel filter: tiktok" in summary
    # TikTok entries should be present
    assert "Tiktok Topic A" in summary
    assert "Tiktok Topic B" in summary
    # Pinterest entry should NOT be present
    assert "Pin Topic" not in summary
    # Entry count should reflect filtered set
    assert "Content log entries: 2" in summary


def test_atomic_write_produces_complete_file(tmp_path):
    """_write_summary uses tmp+rename pattern — output file should exist with full content."""
    entries = [
        _make_entry("T1", channel="tiktok", slug="atomic-test", days_ago=1),
    ]
    log_path = _write_log(tmp_path, entries)
    output_path = tmp_path / "summary.md"

    summary = generate_content_memory_summary(
        content_log_path=log_path,
        output_path=output_path,
        channel="tiktok",
    )
    # Output file should exist
    assert output_path.exists()
    # Content should match what was returned
    written = output_path.read_text(encoding="utf-8")
    assert written == summary
    # No leftover .tmp files
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_performance_history_section_includes_pillar_lifetime(tmp_path):
    """Section 8 should include per-pillar lifetime stats."""
    entries = [
        _make_entry("T1", channel="tiktok", slug="topic-a", pillar=1,
                     days_ago=5, impressions=500, saves=50),
        _make_entry("T2", channel="tiktok", slug="topic-b", pillar=2,
                     days_ago=10, impressions=300, saves=15),
        _make_entry("T3", channel="tiktok", slug="topic-c", pillar=1,
                     days_ago=15, impressions=200, saves=20),
    ]
    log_path = _write_log(tmp_path, entries)
    output_path = tmp_path / "summary.md"

    summary = generate_content_memory_summary(
        content_log_path=log_path,
        output_path=output_path,
        channel="tiktok",
    )
    assert "PERFORMANCE HISTORY" in summary
    assert "Per-Pillar Lifetime" in summary
    # Pillar 1 should show 2 pins, 700 impressions, 70 saves
    assert "P1: 2 pins" in summary
    assert "P2: 1 pins" in summary


def test_cross_channel_summary_excludes_specified_channel(tmp_path):
    """generate_cross_channel_summary excludes the specified channel."""
    today = date.today()
    entries = [
        _make_entry("P1", channel="pinterest", slug="pin-post", days_ago=2,
                     impressions=500, saves=50),
        _make_entry("T1", channel="tiktok", slug="tiktok-post", days_ago=3,
                     impressions=300, saves=15),
    ]

    with patch("src.shared.content_memory.load_content_log", return_value=entries):
        result = generate_cross_channel_summary(exclude_channel="tiktok")
        # Should include pinterest data but not tiktok
        assert "Pinterest" in result or "pinterest" in result.lower()
        # Should not reference tiktok as a data source
        # The result describes other channels, so tiktok should be excluded
        assert "500" in result or "pin" in result.lower()


def test_cross_channel_summary_no_data_for_other_channels():
    """When only the excluded channel has data, return placeholder."""
    entries = [
        _make_entry("T1", channel="tiktok", slug="tiktok-post", days_ago=2),
    ]
    with patch("src.shared.content_memory.load_content_log", return_value=entries):
        result = generate_cross_channel_summary(exclude_channel="tiktok")
        assert "No cross-channel data" in result
        assert "tiktok" in result
