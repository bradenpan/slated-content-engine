"""Tests for src/shared/content_memory.py — channel-aware content memory."""

import json
from datetime import date, timedelta

from src.shared.content_memory import generate_content_memory_summary


def _make_entry(pin_id, channel="pinterest", slug="test-slug", pillar=1,
                days_ago=0, content_type="recipe", **kwargs):
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
        "impressions": 100,
        "saves": 10,
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


def test_empty_log_returns_empty_summary(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    output_path = tmp_path / "summary.md"
    summary = generate_content_memory_summary(
        content_log_path=log_path,
        output_path=output_path,
    )
    assert "No content has been created yet" in summary


def test_channel_tags_shown_with_multiple_channels(tmp_path):
    entries = [
        _make_entry("P1", channel="pinterest", slug="pin-topic", days_ago=1),
        _make_entry("T1", channel="tiktok", slug="tiktok-topic", days_ago=2),
    ]
    log_path = _write_log(tmp_path, entries)
    output_path = tmp_path / "summary.md"

    summary = generate_content_memory_summary(
        content_log_path=log_path,
        output_path=output_path,
    )
    assert "[pinterest]" in summary
    assert "[tiktok]" in summary
    assert "Channels: all" in summary


def test_no_channel_tags_with_single_channel(tmp_path):
    entries = [
        _make_entry("P1", channel="pinterest", slug="topic-a", days_ago=1),
        _make_entry("P2", channel="pinterest", slug="topic-b", days_ago=2),
    ]
    log_path = _write_log(tmp_path, entries)
    output_path = tmp_path / "summary.md"

    summary = generate_content_memory_summary(
        content_log_path=log_path,
        output_path=output_path,
    )
    # No channel tags when only one channel exists
    assert "[pinterest]" not in summary


def test_channel_filter(tmp_path):
    entries = [
        _make_entry("P1", channel="pinterest", slug="pin-topic", days_ago=1),
        _make_entry("T1", channel="tiktok", slug="tiktok-topic", days_ago=2),
    ]
    log_path = _write_log(tmp_path, entries)
    output_path = tmp_path / "summary.md"

    summary = generate_content_memory_summary(
        content_log_path=log_path,
        output_path=output_path,
        channel="pinterest",
    )
    assert "Channel filter: pinterest" in summary
    assert "Pin Topic" in summary
    assert "Tiktok Topic" not in summary


def test_channel_distribution_section(tmp_path):
    entries = [
        _make_entry("P1", channel="pinterest", slug="pin-topic", days_ago=1),
        _make_entry("T1", channel="tiktok", slug="tiktok-topic-1", days_ago=2),
        _make_entry("T2", channel="tiktok", slug="tiktok-topic-2", days_ago=3),
    ]
    log_path = _write_log(tmp_path, entries)
    output_path = tmp_path / "summary.md"

    summary = generate_content_memory_summary(
        content_log_path=log_path,
        output_path=output_path,
    )
    assert "Channel Distribution" in summary
    assert "tiktok: 2 entries (67%)" in summary
    assert "pinterest: 1 entries (33%)" in summary


def test_missing_channel_defaults_to_pinterest(tmp_path):
    entries = [
        {"pin_id": "P1", "date": date.today().isoformat(),
         "posted_date": date.today().isoformat(),
         "blog_slug": "old-entry", "blog_title": "Old Entry",
         "pillar": 1, "content_type": "recipe",
         "board": "b", "funnel_layer": "d",
         "primary_keyword": "", "secondary_keywords": [],
         "impressions": 0, "saves": 0},
    ]
    log_path = _write_log(tmp_path, entries)
    output_path = tmp_path / "summary.md"

    # Filter for pinterest should still include entries with missing channel
    summary = generate_content_memory_summary(
        content_log_path=log_path,
        output_path=output_path,
        channel="pinterest",
    )
    assert "Old Entry" in summary
