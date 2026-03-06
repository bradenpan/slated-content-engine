"""Tests for src/tiktok/promote_and_schedule.py — carousel scheduling pipeline."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from src.tiktok.promote_and_schedule import (
    CAROUSEL_SCHEDULE_PATH,
    MAX_WEEKLY_SLOTS,
    SLOTS,
    SLOT_HOURS,
    _assign_time_slots,
    _enrich_from_plan,
    _load_carried_over,
    _resolve_slide_urls,
    _write_schedule,
    promote_and_schedule,
)

ET = ZoneInfo("America/New_York")


def _make_approved(n=3, start_date="2026-03-11"):
    """Generate n approved carousel dicts with scheduled_date spread across days."""
    carousels = []
    for i in range(1, n + 1):
        day_offset = (i - 1) // len(SLOTS)
        base = datetime.strptime(start_date, "%Y-%m-%d").date()
        sched_date = (base + timedelta(days=day_offset)).isoformat()
        carousels.append({
            "carousel_id": f"T-W10-{i:02d}",
            "topic": f"Topic {i}",
            "template_family": "clean_educational",
            "caption": f"Caption {i}",
            "slide_count": 5,
            "scheduled_date": sched_date,
            "slide_urls": [f"https://storage.example.com/tiktok/T-W10-{i:02d}/slide-{j}.png" for j in range(5)],
        })
    return carousels


# ---------------------------------------------------------------------------
# promote_and_schedule — env validation
# ---------------------------------------------------------------------------


def test_raises_if_tiktok_spreadsheet_id_not_set(monkeypatch):
    monkeypatch.delenv("TIKTOK_SPREADSHEET_ID", raising=False)
    with pytest.raises(ValueError, match="TIKTOK_SPREADSHEET_ID"):
        promote_and_schedule()


# ---------------------------------------------------------------------------
# promote_and_schedule — no approved
# ---------------------------------------------------------------------------


def test_returns_zero_when_no_approved():
    sheets = MagicMock()
    sheets.read_tiktok_approved_carousels.return_value = []
    slack = MagicMock()

    result = promote_and_schedule(sheets=sheets, slack=slack)

    assert result["scheduled_count"] == 0
    assert result["carried_over_count"] == 0
    assert result["start_date"] is None


# ---------------------------------------------------------------------------
# promote_and_schedule — cap at MAX_WEEKLY_SLOTS
# ---------------------------------------------------------------------------


@patch("src.tiktok.promote_and_schedule._resolve_slide_urls")
@patch("src.tiktok.promote_and_schedule._enrich_from_plan", side_effect=lambda x: x)
def test_caps_at_max_weekly_slots(mock_enrich, mock_resolve, tmp_path):
    over_limit = _make_approved(MAX_WEEKLY_SLOTS + 5)
    sheets = MagicMock()
    sheets.read_tiktok_approved_carousels.return_value = over_limit
    slack = MagicMock()

    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", tmp_path / "schedule.json"):
        result = promote_and_schedule(sheets=sheets, slack=slack)

    assert result["scheduled_count"] == MAX_WEEKLY_SLOTS


# ---------------------------------------------------------------------------
# _assign_time_slots — round-robin within each date
# ---------------------------------------------------------------------------


def test_assign_time_slots_round_robin():
    approved = _make_approved(7, start_date="2026-03-11")
    entries = _assign_time_slots(approved)

    assert len(entries) == 7

    # First 3 carousels on 2026-03-11 across morning/afternoon/evening
    assert entries[0]["scheduled_date"] == "2026-03-11"
    assert entries[0]["scheduled_slot"] == "morning"
    assert entries[1]["scheduled_date"] == "2026-03-11"
    assert entries[1]["scheduled_slot"] == "afternoon"
    assert entries[2]["scheduled_date"] == "2026-03-11"
    assert entries[2]["scheduled_slot"] == "evening"
    # Next 3 on 2026-03-12
    assert entries[3]["scheduled_date"] == "2026-03-12"
    assert entries[3]["scheduled_slot"] == "morning"
    # 7th carousel on 2026-03-13
    assert entries[6]["scheduled_date"] == "2026-03-13"
    assert entries[6]["scheduled_slot"] == "morning"


def test_assign_time_slots_uses_plan_dates():
    """Carousels with different scheduled_dates get grouped correctly."""
    carousels = [
        {"carousel_id": "A", "scheduled_date": "2026-03-15"},
        {"carousel_id": "B", "scheduled_date": "2026-03-15"},
        {"carousel_id": "C", "scheduled_date": "2026-03-17"},
    ]
    entries = _assign_time_slots(carousels)

    assert entries[0]["scheduled_date"] == "2026-03-15"
    assert entries[0]["scheduled_slot"] == "morning"
    assert entries[1]["scheduled_date"] == "2026-03-15"
    assert entries[1]["scheduled_slot"] == "afternoon"
    assert entries[2]["scheduled_date"] == "2026-03-17"
    assert entries[2]["scheduled_slot"] == "morning"


def test_assign_time_slots_fallback_for_missing_date():
    """Carousels missing scheduled_date get fallback dates starting tomorrow."""
    carousels = [
        {"carousel_id": "A"},
        {"carousel_id": "B"},
    ]
    entries = _assign_time_slots(carousels)

    assert len(entries) == 2
    tomorrow = (datetime.now(ET) + timedelta(days=1)).date().isoformat()
    assert entries[0]["scheduled_date"] == tomorrow
    assert entries[0]["scheduled_slot"] == "morning"
    assert entries[1]["scheduled_date"] == tomorrow
    assert entries[1]["scheduled_slot"] == "afternoon"


def test_assign_time_slots_scheduled_at_has_correct_hour():
    carousels = [{"carousel_id": "A", "scheduled_date": "2026-03-11"}]
    entries = _assign_time_slots(carousels)

    dt = datetime.fromisoformat(entries[0]["scheduled_at"])
    assert dt.hour == SLOT_HOURS["morning"][0]
    assert dt.minute == SLOT_HOURS["morning"][1]
    assert dt.tzinfo is not None


def test_assign_time_slots_overflow_to_next_date():
    """More than 3 carousels on a single date overflow to subsequent dates."""
    carousels = [
        {"carousel_id": f"C{i}", "scheduled_date": "2026-03-11"}
        for i in range(5)
    ]
    entries = _assign_time_slots(carousels)

    assert len(entries) == 5
    # First 3 on 2026-03-11
    assert entries[0]["scheduled_date"] == "2026-03-11"
    assert entries[0]["scheduled_slot"] == "morning"
    assert entries[2]["scheduled_date"] == "2026-03-11"
    assert entries[2]["scheduled_slot"] == "evening"
    # 4th and 5th overflow to 2026-03-12
    assert entries[3]["scheduled_date"] == "2026-03-12"
    assert entries[3]["scheduled_slot"] == "morning"
    assert entries[4]["scheduled_date"] == "2026-03-12"
    assert entries[4]["scheduled_slot"] == "afternoon"


# ---------------------------------------------------------------------------
# promote_and_schedule — filter carousels without slide_urls
# ---------------------------------------------------------------------------


@patch("src.tiktok.promote_and_schedule._resolve_slide_urls")
@patch("src.tiktok.promote_and_schedule._enrich_from_plan", side_effect=lambda x: x)
def test_filters_out_carousels_without_slide_urls(mock_enrich, mock_resolve, tmp_path):
    """Carousels without slide_urls are excluded and set to 'failed'."""
    approved = [
        {"carousel_id": "HAS-URLS", "scheduled_date": "2026-03-11",
         "slide_urls": ["https://example.com/slide-0.png"], "slide_count": 1},
        {"carousel_id": "NO-URLS", "scheduled_date": "2026-03-11", "slide_count": 0},
    ]
    sheets = MagicMock()
    sheets.read_tiktok_approved_carousels.return_value = approved
    slack = MagicMock()

    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", tmp_path / "schedule.json"):
        result = promote_and_schedule(sheets=sheets, slack=slack)

    assert result["scheduled_count"] == 1
    # NO-URLS should have been set to "failed"
    failed_calls = [c for c in sheets.update_tiktok_content_status.call_args_list
                    if c.args[1] == "failed"]
    assert len(failed_calls) == 1
    assert failed_calls[0].args[0] == "NO-URLS"


# ---------------------------------------------------------------------------
# _load_carried_over — merge behavior
# ---------------------------------------------------------------------------


def test_load_carried_over_preserves_future_entries(tmp_path):
    tomorrow = (datetime.now(ET) + timedelta(days=1)).date().isoformat()
    existing = [
        {"carousel_id": "OLD-1", "scheduled_date": tomorrow, "scheduled_slot": "morning"},
        {"carousel_id": "OLD-2", "scheduled_date": tomorrow, "scheduled_slot": "afternoon"},
    ]
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(json.dumps(existing), encoding="utf-8")

    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", schedule_path):
        carried = _load_carried_over(new_ids=set())

    assert len(carried) == 2


def test_load_carried_over_drops_past_entries(tmp_path):
    yesterday = (datetime.now(ET) - timedelta(days=1)).date().isoformat()
    existing = [
        {"carousel_id": "OLD-1", "scheduled_date": yesterday, "scheduled_slot": "morning"},
    ]
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(json.dumps(existing), encoding="utf-8")

    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", schedule_path):
        carried = _load_carried_over(new_ids=set())

    assert len(carried) == 0


def test_load_carried_over_deduplicates_against_new_batch(tmp_path):
    tomorrow = (datetime.now(ET) + timedelta(days=1)).date().isoformat()
    existing = [
        {"carousel_id": "SHARED-1", "scheduled_date": tomorrow, "scheduled_slot": "morning"},
        {"carousel_id": "OLD-ONLY", "scheduled_date": tomorrow, "scheduled_slot": "afternoon"},
    ]
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(json.dumps(existing), encoding="utf-8")

    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", schedule_path):
        carried = _load_carried_over(new_ids={"SHARED-1"})

    assert len(carried) == 1
    assert carried[0]["carousel_id"] == "OLD-ONLY"


def test_load_carried_over_handles_missing_file(tmp_path):
    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", tmp_path / "nonexistent.json"):
        carried = _load_carried_over(new_ids=set())

    assert carried == []


# ---------------------------------------------------------------------------
# _write_schedule — atomic write
# ---------------------------------------------------------------------------


def test_write_schedule_creates_file(tmp_path):
    schedule_path = tmp_path / "tiktok" / "schedule.json"
    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", schedule_path):
        _write_schedule([{"carousel_id": "A", "scheduled_date": "2026-03-11"}])

    assert schedule_path.exists()
    data = json.loads(schedule_path.read_text(encoding="utf-8"))
    assert len(data) == 1
    # No leftover .tmp file
    assert not list(tmp_path.rglob("*.tmp"))


# ---------------------------------------------------------------------------
# promote_and_schedule — full integration with merge
# ---------------------------------------------------------------------------


@patch("src.tiktok.promote_and_schedule._resolve_slide_urls")
@patch("src.tiktok.promote_and_schedule._enrich_from_plan", side_effect=lambda x: x)
def test_merges_with_existing_schedule(mock_enrich, mock_resolve, tmp_path):
    """New carousels merge with in-flight carousels from prior schedule."""
    tomorrow = (datetime.now(ET) + timedelta(days=1)).date().isoformat()
    existing = [
        {"carousel_id": "OLD-1", "scheduled_date": tomorrow, "scheduled_slot": "evening"},
    ]
    schedule_path = tmp_path / "schedule.json"
    schedule_path.write_text(json.dumps(existing), encoding="utf-8")

    new_approved = [
        {"carousel_id": "NEW-1", "scheduled_date": "2026-03-18", "slide_count": 3,
         "slide_urls": ["https://storage.example.com/tiktok/NEW-1/slide-0.png"]},
    ]
    sheets = MagicMock()
    sheets.read_tiktok_approved_carousels.return_value = new_approved
    slack = MagicMock()

    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", schedule_path):
        result = promote_and_schedule(sheets=sheets, slack=slack)

    assert result["scheduled_count"] == 1
    assert result["carried_over_count"] == 1

    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    ids = [e["carousel_id"] for e in schedule]
    assert "OLD-1" in ids
    assert "NEW-1" in ids


# ---------------------------------------------------------------------------
# promote_and_schedule — updates sheet status
# ---------------------------------------------------------------------------


@patch("src.tiktok.promote_and_schedule._resolve_slide_urls")
@patch("src.tiktok.promote_and_schedule._enrich_from_plan", side_effect=lambda x: x)
def test_updates_sheet_status_to_scheduled(mock_enrich, mock_resolve, tmp_path):
    sheets = MagicMock()
    sheets.read_tiktok_approved_carousels.return_value = _make_approved(2)
    slack = MagicMock()

    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", tmp_path / "schedule.json"):
        promote_and_schedule(sheets=sheets, slack=slack)

    calls = sheets.update_tiktok_content_status.call_args_list
    assert len(calls) == 2
    assert calls[0].args == ("T-W10-01", "scheduled")
    assert calls[1].args == ("T-W10-02", "scheduled")


# ---------------------------------------------------------------------------
# promote_and_schedule — schedule entries have required fields
# ---------------------------------------------------------------------------


@patch("src.tiktok.promote_and_schedule._resolve_slide_urls")
@patch("src.tiktok.promote_and_schedule._enrich_from_plan", side_effect=lambda x: x)
def test_schedule_entries_have_required_fields(mock_enrich, mock_resolve, tmp_path):
    sheets = MagicMock()
    sheets.read_tiktok_approved_carousels.return_value = _make_approved(1)
    slack = MagicMock()

    schedule_path = tmp_path / "schedule.json"
    with patch("src.tiktok.promote_and_schedule.CAROUSEL_SCHEDULE_PATH", schedule_path):
        promote_and_schedule(sheets=sheets, slack=slack)

    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    entry = schedule[0]
    assert "scheduled_date" in entry
    assert "scheduled_slot" in entry
    assert "scheduled_at" in entry
    dt = datetime.fromisoformat(entry["scheduled_at"])
    assert dt.tzinfo is not None


# ---------------------------------------------------------------------------
# _enrich_from_plan
# ---------------------------------------------------------------------------


@patch("src.tiktok.promote_and_schedule.load_plan")
@patch("src.tiktok.promote_and_schedule.find_latest_plan")
def test_enrich_joins_plan_data_including_scheduled_date(mock_find, mock_load):
    mock_find.return_value = Path("/fake/plan.json")
    mock_load.return_value = {
        "carousels": [
            {
                "carousel_id": "T-01",
                "hashtags": ["#grout"],
                "angle": "practical-tips",
                "structure": "listicle",
                "hook_type": "question",
                "hook_text": "Got grout?",
                "is_aigc": False,
                "content_slides": [{"text": "s1"}],
                "cta_slide": {"text": "cta"},
                "image_prompts": [{"slide_index": 0}],
                "scheduled_date": "2026-03-12",
            }
        ]
    }

    approved = [{"carousel_id": "T-01", "topic": "grout"}]
    enriched = _enrich_from_plan(approved)

    assert enriched[0]["hashtags"] == ["#grout"]
    assert enriched[0]["angle"] == "practical-tips"
    assert enriched[0]["structure"] == "listicle"
    assert enriched[0]["hook_type"] == "question"
    assert enriched[0]["hook_text"] == "Got grout?"
    assert enriched[0]["is_aigc"] is False
    assert enriched[0]["content_slides"] == [{"text": "s1"}]
    assert enriched[0]["cta_slide"] == {"text": "cta"}
    assert enriched[0]["image_prompts"] == [{"slide_index": 0}]
    assert enriched[0]["scheduled_date"] == "2026-03-12"


@patch("src.tiktok.promote_and_schedule.find_latest_plan", return_value=None)
def test_enrich_handles_missing_plan_gracefully(mock_find):
    approved = [{"carousel_id": "T-01", "topic": "grout"}]
    enriched = _enrich_from_plan(approved)
    assert enriched == approved


@patch("src.tiktok.promote_and_schedule.load_plan")
@patch("src.tiktok.promote_and_schedule.find_latest_plan")
def test_enrich_only_fills_missing_fields(mock_find, mock_load):
    mock_find.return_value = Path("/fake/plan.json")
    mock_load.return_value = {
        "carousels": [
            {
                "carousel_id": "T-01",
                "angle": "plan-angle",
                "hashtags": ["#plan"],
                "scheduled_date": "2026-03-12",
            }
        ]
    }

    # carousel already has angle set — should NOT be overwritten
    approved = [{"carousel_id": "T-01", "angle": "original-angle"}]
    enriched = _enrich_from_plan(approved)

    assert enriched[0]["angle"] == "original-angle"
    assert enriched[0]["hashtags"] == ["#plan"]
    assert enriched[0]["scheduled_date"] == "2026-03-12"


# ---------------------------------------------------------------------------
# _resolve_slide_urls
# ---------------------------------------------------------------------------


@patch("src.tiktok.promote_and_schedule.GcsAPI")
def test_resolve_slide_urls_builds_deterministic_urls(mock_gcs_cls):
    gcs = MagicMock()
    gcs.is_available = True
    gcs.get_public_url.side_effect = lambda path: f"https://storage.example.com/{path}"
    mock_gcs_cls.return_value = gcs

    carousels = [
        {"carousel_id": "T-01", "slide_count": 3},
    ]
    _resolve_slide_urls(carousels)

    assert len(carousels[0]["slide_urls"]) == 3
    assert carousels[0]["slide_urls"][0] == "https://storage.example.com/tiktok/T-01/slide-0.png"
    assert carousels[0]["slide_urls"][2] == "https://storage.example.com/tiktok/T-01/slide-2.png"


@patch("src.tiktok.promote_and_schedule.GcsAPI")
def test_resolve_slide_urls_handles_gcs_unavailable(mock_gcs_cls):
    gcs = MagicMock()
    gcs.is_available = False
    mock_gcs_cls.return_value = gcs

    carousels = [{"carousel_id": "T-01", "slide_count": 3}]
    _resolve_slide_urls(carousels)

    assert "slide_urls" not in carousels[0]
