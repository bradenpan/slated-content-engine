"""Tests for save_pin_schedule() in src/utils/plan_utils.py."""

import json

from src.shared.utils.plan_utils import save_pin_schedule


def test_save_creates_file_with_correct_content(tmp_path):
    schedule = [
        {"pin_id": "W8-01", "scheduled_date": "2026-02-20", "slot": 1},
        {"pin_id": "W8-02", "scheduled_date": "2026-02-21", "slot": 2},
    ]
    out_path = tmp_path / "pin-schedule.json"

    save_pin_schedule(schedule, path=out_path)

    assert out_path.exists()
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded == schedule


def test_save_overwrites_existing_file(tmp_path):
    out_path = tmp_path / "pin-schedule.json"
    out_path.write_text('[{"old": true}]', encoding="utf-8")

    new_schedule = [{"pin_id": "W9-01", "scheduled_date": "2026-03-01"}]
    save_pin_schedule(new_schedule, path=out_path)

    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded == new_schedule


def test_save_handles_empty_schedule(tmp_path):
    out_path = tmp_path / "pin-schedule.json"

    save_pin_schedule([], path=out_path)

    assert out_path.exists()
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded == []
