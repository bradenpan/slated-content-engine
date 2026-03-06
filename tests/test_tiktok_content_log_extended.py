"""Extended tests for src/shared/utils/content_log.py — TikTok-specific behavior."""

import json

from src.shared.utils.content_log import (
    append_content_log_entry,
    is_content_posted,
    load_content_log,
    save_content_log,
)


# ---------------------------------------------------------------------------
# is_content_posted — PENDING handling
# ---------------------------------------------------------------------------


def test_is_content_posted_returns_false_for_pending(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    entries = [
        {
            "pin_id": "T-W10-01",
            "channel": "tiktok",
            "publer_post_id": "PENDING",
        }
    ]
    save_content_log(entries, path=log_path)

    assert is_content_posted("T-W10-01", "tiktok", path=log_path) is False


# ---------------------------------------------------------------------------
# is_content_posted — MANUAL sentinel
# ---------------------------------------------------------------------------


def test_is_content_posted_returns_true_for_manual(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    entries = [
        {
            "pin_id": "T-W10-02",
            "channel": "tiktok",
            "publer_post_id": "MANUAL",
        }
    ]
    save_content_log(entries, path=log_path)

    assert is_content_posted("T-W10-02", "tiktok", path=log_path) is True


# ---------------------------------------------------------------------------
# is_content_posted — channel filter doesn't cross-match
# ---------------------------------------------------------------------------


def test_is_content_posted_channel_filter_no_cross_match(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    entries = [
        {
            "pin_id": "W10-01",
            "channel": "pinterest",
            "pinterest_pin_id": "pin-123",
        },
        {
            "pin_id": "T-W10-01",
            "channel": "tiktok",
            "publer_post_id": "pub-456",
        },
    ]
    save_content_log(entries, path=log_path)

    # Pinterest entry should not match tiktok channel
    assert is_content_posted("W10-01", "tiktok", path=log_path) is False
    # TikTok entry should not match pinterest channel
    assert is_content_posted("T-W10-01", "pinterest", path=log_path) is False
    # Each should match its own channel
    assert is_content_posted("W10-01", "pinterest", path=log_path) is True
    assert is_content_posted("T-W10-01", "tiktok", path=log_path) is True


# ---------------------------------------------------------------------------
# is_content_posted — missing channel defaults to "pinterest"
# ---------------------------------------------------------------------------


def test_is_content_posted_missing_channel_defaults_to_pinterest(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    # Legacy entry without channel field
    entries = [
        {
            "pin_id": "W5-01",
            "pinterest_pin_id": "pin-789",
        }
    ]
    save_content_log(entries, path=log_path)

    # Should match pinterest (default channel)
    assert is_content_posted("W5-01", "pinterest", path=log_path) is True
    # Should NOT match tiktok
    assert is_content_posted("W5-01", "tiktok", path=log_path) is False


# ---------------------------------------------------------------------------
# TikTok fields roundtrip preservation
# ---------------------------------------------------------------------------


def test_tiktok_fields_preserved_on_roundtrip(tmp_path):
    log_path = tmp_path / "content-log.jsonl"

    tiktok_entry = {
        "channel": "tiktok",
        "pin_id": "T-W10-01",
        "publer_post_id": "pub-abc",
        "posted_date": "2026-03-10",
        "posted_slot": "morning",
        "topic": "grout cleaning",
        "angle": "practical-tips",
        "structure": "listicle",
        "hook_type": "question",
        "template_family": "clean_educational",
        "hook_text": "Want cleaner grout?",
        "caption": "Test caption with #hashtags",
        "slide_count": 5,
        "manual_upload_required": False,
    }

    append_content_log_entry(tiktok_entry, path=log_path)
    loaded = load_content_log(path=log_path)

    assert len(loaded) == 1
    for key, value in tiktok_entry.items():
        assert loaded[0][key] == value, f"Field '{key}' not preserved: {loaded[0].get(key)} != {value}"


def test_multiple_channel_entries_roundtrip(tmp_path):
    log_path = tmp_path / "content-log.jsonl"

    pinterest_entry = {
        "channel": "pinterest",
        "pin_id": "W10-01",
        "pinterest_pin_id": "pin-999",
        "topic": "slate tile",
    }
    tiktok_entry = {
        "channel": "tiktok",
        "pin_id": "T-W10-01",
        "publer_post_id": "pub-123",
        "topic": "grout cleaning",
        "angle": "practical-tips",
        "hook_text": "Got grout?",
        "slide_count": 5,
    }

    save_content_log([pinterest_entry, tiktok_entry], path=log_path)
    loaded = load_content_log(path=log_path)

    assert len(loaded) == 2
    assert loaded[0]["channel"] == "pinterest"
    assert loaded[1]["channel"] == "tiktok"
    assert loaded[1]["publer_post_id"] == "pub-123"
    assert loaded[1]["slide_count"] == 5
    assert loaded[1]["angle"] == "practical-tips"
