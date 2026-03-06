"""Tests for src/tiktok/post_content.py — TikTok carousel posting pipeline."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tiktok.post_content import (
    CAROUSEL_SCHEDULE_PATH,
    _apply_jitter,
    _build_log_entry,
    _clear_failure_record,
    _record_failure,
    load_carousel_schedule,
    post_content,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SAMPLE_CAROUSEL = {
    "carousel_id": "T-W10-01",
    "topic": "grout cleaning",
    "slide_urls": [
        "https://storage.googleapis.com/bucket/tiktok/T-W10-01/slide-0.png",
    ],
    "caption": "Test caption",
    "hashtags": ["#tiles"],
    "scheduled_date": "2026-03-10",
    "scheduled_slot": "morning",
    "scheduled_at": "2026-03-10T10:00:00-04:00",
    "template_family": "clean_educational",
    "angle": "practical-tips",
    "structure": "listicle",
    "hook_type": "question",
    "hook_text": "Want cleaner grout?",
    "slide_count": 5,
}


def _write_schedule(tmp_path, carousels):
    """Write a carousel schedule JSON to the tmp_path equivalent of CAROUSEL_SCHEDULE_PATH."""
    path = tmp_path / "tiktok" / "carousel-schedule.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(carousels), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# post_content — input validation
# ---------------------------------------------------------------------------


def test_post_content_raises_for_invalid_time_slot():
    with pytest.raises(ValueError, match="Invalid time_slot"):
        post_content("midnight")


def test_post_content_raises_for_bad_date_format():
    with pytest.raises(ValueError):
        post_content("morning", date_override="03-10-2026")


# ---------------------------------------------------------------------------
# post_content — no carousels
# ---------------------------------------------------------------------------


@patch("src.tiktok.post_content.load_carousel_schedule", return_value=[])
@patch("src.tiktok.post_content.SlackNotify")
def test_post_content_returns_zeros_when_no_carousels(mock_slack_cls, mock_load):
    mock_slack_cls.return_value = MagicMock()
    results = post_content("morning", date_override="2026-03-10")
    assert results["posted_count"] == 0
    assert results["failed_count"] == 0
    assert results["manual_count"] == 0


# ---------------------------------------------------------------------------
# post_content — Publer posting (enabled)
# ---------------------------------------------------------------------------


@patch("src.tiktok.post_content.time.sleep")
@patch("src.tiktok.post_content._clear_failure_record")
@patch("src.tiktok.post_content._update_pending_entry")
@patch("src.tiktok.post_content._remove_pending_entry")
@patch("src.tiktok.post_content.append_content_log_entry")
@patch("src.tiktok.post_content.is_content_posted", return_value=False)
@patch("src.tiktok.post_content.load_carousel_schedule")
@patch("src.tiktok.post_content.SlackNotify")
def test_post_content_posts_via_publer(
    mock_slack_cls, mock_load, mock_posted, mock_append,
    mock_remove, mock_update, mock_clear, mock_sleep, monkeypatch,
):
    monkeypatch.setenv("TIKTOK_POSTING_ENABLED", "true")
    mock_load.return_value = [SAMPLE_CAROUSEL]

    publer = MagicMock()
    publer.import_media.return_value = "job-import"
    publer.poll_job.side_effect = [
        {"status": "complete", "media_ids": ["m1"]},
        {"status": "complete", "post_id": "pub-999"},
    ]
    publer.create_post.return_value = "job-post"

    sheets = MagicMock()
    slack = MagicMock()

    results = post_content(
        "morning", date_override="2026-03-10",
        publer=publer, sheets=sheets, slack=slack,
    )

    assert results["posted_count"] == 1
    assert results["failed_count"] == 0
    mock_append.assert_called_once()
    mock_update.assert_called_once_with("T-W10-01", "pub-999")
    mock_clear.assert_called_once_with("T-W10-01")


@patch("src.tiktok.post_content.time.sleep")
@patch("src.tiktok.post_content.is_content_posted", return_value=True)
@patch("src.tiktok.post_content.load_carousel_schedule")
@patch("src.tiktok.post_content.SlackNotify")
def test_post_content_skips_already_posted(mock_slack_cls, mock_load, mock_posted, mock_sleep, monkeypatch):
    monkeypatch.setenv("TIKTOK_POSTING_ENABLED", "true")
    mock_load.return_value = [SAMPLE_CAROUSEL]
    publer = MagicMock()
    sheets = MagicMock()
    slack = MagicMock()

    results = post_content(
        "morning", date_override="2026-03-10",
        publer=publer, sheets=sheets, slack=slack,
    )

    assert results["skipped_count"] == 1
    assert results["posted_count"] == 0
    publer.import_media.assert_not_called()


@patch("src.tiktok.post_content.time.sleep")
@patch("src.tiktok.post_content._remove_pending_entry")
@patch("src.tiktok.post_content.append_content_log_entry")
@patch("src.tiktok.post_content.is_content_posted", return_value=False)
@patch("src.tiktok.post_content.load_carousel_schedule")
@patch("src.tiktok.post_content.SlackNotify")
def test_post_content_writes_pending_before_publer_call(
    mock_slack_cls, mock_load, mock_posted, mock_append, mock_remove, mock_sleep, monkeypatch,
):
    monkeypatch.setenv("TIKTOK_POSTING_ENABLED", "true")
    mock_load.return_value = [SAMPLE_CAROUSEL]

    publer = MagicMock()
    # Make import_media raise to test the PENDING placeholder path
    publer.import_media.side_effect = RuntimeError("network fail")

    sheets = MagicMock()
    slack = MagicMock()

    results = post_content(
        "morning", date_override="2026-03-10",
        publer=publer, sheets=sheets, slack=slack,
    )

    # PENDING placeholder should have been written
    mock_append.assert_called_once()
    entry = mock_append.call_args[0][0]
    assert entry["publer_post_id"] == "PENDING"

    # PENDING should have been removed on failure
    mock_remove.assert_called_once_with("T-W10-01")
    assert results["failed_count"] == 1


@patch("src.tiktok.post_content.time.sleep")
@patch("src.tiktok.post_content._remove_pending_entry")
@patch("src.tiktok.post_content.append_content_log_entry")
@patch("src.tiktok.post_content.is_content_posted", return_value=False)
@patch("src.tiktok.post_content.load_carousel_schedule")
@patch("src.tiktok.post_content.SlackNotify")
def test_post_content_removes_pending_on_failure(
    mock_slack_cls, mock_load, mock_posted, mock_append, mock_remove, mock_sleep, monkeypatch,
):
    monkeypatch.setenv("TIKTOK_POSTING_ENABLED", "true")
    mock_load.return_value = [SAMPLE_CAROUSEL]

    publer = MagicMock()
    publer.import_media.side_effect = RuntimeError("API down")

    results = post_content(
        "morning", date_override="2026-03-10",
        publer=publer, sheets=MagicMock(), slack=MagicMock(),
    )

    mock_remove.assert_called_once_with("T-W10-01")
    assert results["failed_count"] == 1


@patch("src.tiktok.post_content.time.sleep")
@patch("src.tiktok.post_content._clear_failure_record")
@patch("src.tiktok.post_content._update_pending_entry")
@patch("src.tiktok.post_content._remove_pending_entry")
@patch("src.tiktok.post_content.append_content_log_entry")
@patch("src.tiktok.post_content.is_content_posted", return_value=False)
@patch("src.tiktok.post_content.load_carousel_schedule")
@patch("src.tiktok.post_content.SlackNotify")
def test_post_content_updates_pending_with_real_post_id(
    mock_slack_cls, mock_load, mock_posted, mock_append,
    mock_remove, mock_update, mock_clear, mock_sleep, monkeypatch,
):
    monkeypatch.setenv("TIKTOK_POSTING_ENABLED", "true")
    mock_load.return_value = [SAMPLE_CAROUSEL]

    publer = MagicMock()
    publer.import_media.return_value = "ji"
    publer.poll_job.side_effect = [
        {"status": "complete", "media_ids": ["m1"]},
        {"status": "complete", "post_id": "pub-ABC"},
    ]
    publer.create_post.return_value = "jp"

    results = post_content(
        "morning", date_override="2026-03-10",
        publer=publer, sheets=MagicMock(), slack=MagicMock(),
    )

    mock_update.assert_called_once_with("T-W10-01", "pub-ABC")
    assert results["posted_count"] == 1


# ---------------------------------------------------------------------------
# post_content — fallback mode (TIKTOK_POSTING_ENABLED=false)
# ---------------------------------------------------------------------------


@patch("src.tiktok.post_content.time.sleep")
@patch("src.tiktok.post_content.append_content_log_entry")
@patch("src.tiktok.post_content.is_content_posted", return_value=False)
@patch("src.tiktok.post_content.load_carousel_schedule")
@patch("src.tiktok.post_content.SlackNotify")
def test_post_content_fallback_mode_logs_manual(
    mock_slack_cls, mock_load, mock_posted, mock_append, mock_sleep, monkeypatch,
):
    monkeypatch.setenv("TIKTOK_POSTING_ENABLED", "false")
    mock_load.return_value = [SAMPLE_CAROUSEL]
    slack = MagicMock()

    results = post_content(
        "morning", date_override="2026-03-10",
        sheets=MagicMock(), slack=slack,
    )

    assert results["manual_count"] == 1
    entry = mock_append.call_args[0][0]
    assert entry["publer_post_id"] == "MANUAL"
    assert entry["manual_upload_required"] is True


# ---------------------------------------------------------------------------
# post_content — failure recording
# ---------------------------------------------------------------------------


@patch("src.tiktok.post_content.time.sleep")
@patch("src.tiktok.post_content._record_failure")
@patch("src.tiktok.post_content._remove_pending_entry")
@patch("src.tiktok.post_content.append_content_log_entry")
@patch("src.tiktok.post_content.is_content_posted", return_value=False)
@patch("src.tiktok.post_content.load_carousel_schedule")
@patch("src.tiktok.post_content.SlackNotify")
def test_post_content_records_failure_on_exception(
    mock_slack_cls, mock_load, mock_posted, mock_append,
    mock_remove, mock_record, mock_sleep, monkeypatch,
):
    monkeypatch.setenv("TIKTOK_POSTING_ENABLED", "true")
    mock_load.return_value = [SAMPLE_CAROUSEL]

    publer = MagicMock()
    publer.import_media.side_effect = RuntimeError("boom")

    post_content(
        "morning", date_override="2026-03-10",
        publer=publer, sheets=MagicMock(), slack=MagicMock(),
    )

    mock_record.assert_called_once()
    assert mock_record.call_args[0][0] == "T-W10-01"


@patch("src.tiktok.post_content.time.sleep")
@patch("src.tiktok.post_content._clear_failure_record")
@patch("src.tiktok.post_content._update_pending_entry")
@patch("src.tiktok.post_content._remove_pending_entry")
@patch("src.tiktok.post_content.append_content_log_entry")
@patch("src.tiktok.post_content.is_content_posted", return_value=False)
@patch("src.tiktok.post_content.load_carousel_schedule")
@patch("src.tiktok.post_content.SlackNotify")
def test_post_content_clears_failure_on_success(
    mock_slack_cls, mock_load, mock_posted, mock_append,
    mock_remove, mock_update, mock_clear, mock_sleep, monkeypatch,
):
    monkeypatch.setenv("TIKTOK_POSTING_ENABLED", "true")
    mock_load.return_value = [SAMPLE_CAROUSEL]

    publer = MagicMock()
    publer.import_media.return_value = "ji"
    publer.poll_job.side_effect = [
        {"status": "complete", "media_ids": ["m1"]},
        {"status": "complete", "post_id": "pub-OK"},
    ]
    publer.create_post.return_value = "jp"

    post_content(
        "morning", date_override="2026-03-10",
        publer=publer, sheets=MagicMock(), slack=MagicMock(),
    )

    mock_clear.assert_called_once_with("T-W10-01")


# ---------------------------------------------------------------------------
# load_carousel_schedule
# ---------------------------------------------------------------------------


def test_load_carousel_schedule_returns_matching(tmp_path):
    carousels = [
        {**SAMPLE_CAROUSEL, "scheduled_date": "2026-03-10", "scheduled_slot": "morning"},
        {**SAMPLE_CAROUSEL, "carousel_id": "T-W10-02", "scheduled_date": "2026-03-10", "scheduled_slot": "afternoon"},
        {**SAMPLE_CAROUSEL, "carousel_id": "T-W10-03", "scheduled_date": "2026-03-11", "scheduled_slot": "morning"},
    ]
    path = _write_schedule(tmp_path, carousels)

    with patch("src.tiktok.post_content.CAROUSEL_SCHEDULE_PATH", path):
        result = load_carousel_schedule("2026-03-10", "morning")

    assert len(result) == 1
    assert result[0]["carousel_id"] == "T-W10-01"


def test_load_carousel_schedule_returns_empty_for_missing_file(tmp_path):
    missing = tmp_path / "tiktok" / "nope.json"
    with patch("src.tiktok.post_content.CAROUSEL_SCHEDULE_PATH", missing):
        result = load_carousel_schedule("2026-03-10", "morning")
    assert result == []


def test_load_carousel_schedule_returns_empty_for_invalid_json(tmp_path):
    bad = tmp_path / "tiktok" / "bad.json"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("NOT JSON{{{", encoding="utf-8")

    with patch("src.tiktok.post_content.CAROUSEL_SCHEDULE_PATH", bad):
        result = load_carousel_schedule("2026-03-10", "morning")
    assert result == []


# ---------------------------------------------------------------------------
# _build_log_entry
# ---------------------------------------------------------------------------


def test_build_log_entry_structure():
    entry = _build_log_entry(SAMPLE_CAROUSEL, "T-W10-01", "2026-03-10", "morning", "pub-xyz")
    assert entry["channel"] == "tiktok"
    assert entry["pin_id"] == "T-W10-01"
    assert entry["publer_post_id"] == "pub-xyz"
    assert entry["posted_date"] == "2026-03-10"
    assert entry["posted_slot"] == "morning"
    assert entry["topic"] == "grout cleaning"
    assert entry["angle"] == "practical-tips"
    assert entry["structure"] == "listicle"
    assert entry["hook_type"] == "question"
    assert entry["template_family"] == "clean_educational"
    assert entry["hook_text"] == "Want cleaner grout?"
    assert entry["caption"] == "Test caption"
    assert entry["slide_count"] == 5


# ---------------------------------------------------------------------------
# _record_failure / _clear_failure_record
# ---------------------------------------------------------------------------


def test_record_failure_creates_and_updates_file(tmp_path):
    failures_path = tmp_path / "tiktok" / "posting-failures.json"

    with patch("src.tiktok.post_content.DATA_DIR", tmp_path):
        with patch("src.tiktok.post_content.SlackNotify"):
            _record_failure("T-01", "error one")

    data = json.loads(failures_path.read_text(encoding="utf-8"))
    assert data["T-01"]["count"] == 1
    assert len(data["T-01"]["errors"]) == 1

    with patch("src.tiktok.post_content.DATA_DIR", tmp_path):
        with patch("src.tiktok.post_content.SlackNotify"):
            _record_failure("T-01", "error two")

    data = json.loads(failures_path.read_text(encoding="utf-8"))
    assert data["T-01"]["count"] == 2
    assert len(data["T-01"]["errors"]) == 2


def test_clear_failure_record_removes_carousel(tmp_path):
    failures_path = tmp_path / "tiktok" / "posting-failures.json"
    failures_path.parent.mkdir(parents=True, exist_ok=True)
    failures_path.write_text(
        json.dumps({"T-01": {"count": 1, "errors": []}, "T-02": {"count": 2, "errors": []}}),
        encoding="utf-8",
    )

    with patch("src.tiktok.post_content.DATA_DIR", tmp_path):
        _clear_failure_record("T-01")

    data = json.loads(failures_path.read_text(encoding="utf-8"))
    assert "T-01" not in data
    assert "T-02" in data


def test_clear_failure_record_noop_if_file_doesnt_exist(tmp_path):
    with patch("src.tiktok.post_content.DATA_DIR", tmp_path):
        # Should not raise
        _clear_failure_record("T-nonexistent")


# ---------------------------------------------------------------------------
# _apply_jitter
# ---------------------------------------------------------------------------


@patch("src.tiktok.post_content.time.sleep")
def test_apply_jitter_uses_deterministic_seed(mock_sleep):
    """Calling _apply_jitter with the same inputs should produce the same sleep duration."""
    _apply_jitter("morning", 0)
    first_call = mock_sleep.call_args[0][0]

    mock_sleep.reset_mock()
    _apply_jitter("morning", 0)
    second_call = mock_sleep.call_args[0][0]

    assert first_call == second_call
    # Jitter should be within [0, TIKTOK_JITTER_MAX]
    from src.shared.config import TIKTOK_JITTER_MAX
    assert 0 <= first_call <= TIKTOK_JITTER_MAX
