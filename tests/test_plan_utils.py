"""Tests for src/utils/plan_utils.py — plan loading and manipulation."""

import json

from src.utils.plan_utils import (
    find_latest_plan,
    identify_replaceable_posts,
    load_plan,
    splice_replacements,
)


def test_find_latest_plan_returns_none_when_no_plans(tmp_path):
    result = find_latest_plan(data_dir=tmp_path)
    assert result is None


def test_find_latest_plan_returns_most_recent(tmp_path):
    # Create plan files with different week numbers
    (tmp_path / "weekly-plan-2026-W05.json").write_text("{}", encoding="utf-8")
    (tmp_path / "weekly-plan-2026-W08.json").write_text("{}", encoding="utf-8")
    (tmp_path / "weekly-plan-2026-W03.json").write_text("{}", encoding="utf-8")

    result = find_latest_plan(data_dir=tmp_path)
    assert result is not None
    assert result.name == "weekly-plan-2026-W08.json"


def test_find_latest_plan_ignores_non_plan_files(tmp_path):
    (tmp_path / "something-else.json").write_text("{}", encoding="utf-8")
    result = find_latest_plan(data_dir=tmp_path)
    assert result is None


def test_load_plan_parses_json(tmp_path):
    plan_data = {"week": "W08", "blog_posts": [], "pins": []}
    plan_path = tmp_path / "weekly-plan-2026-W08.json"
    plan_path.write_text(json.dumps(plan_data), encoding="utf-8")

    result = load_plan(plan_path)
    assert result == plan_data


def test_identify_replaceable_posts_with_targeted_violation():
    plan = {
        "blog_posts": [
            {"post_id": "P1", "title": "Good Post"},
            {"post_id": "P2", "title": "Bad Post"},
        ],
        "pins": [
            {"pin_id": "W8-01", "source_post_id": "P1", "scheduled_date": "2026-02-20"},
            {"pin_id": "W8-02", "source_post_id": "P2", "scheduled_date": "2026-02-21"},
        ],
    }
    violations = [
        {"severity": "targeted", "post_id": "P2", "message": "Keyword violation"},
    ]

    result = identify_replaceable_posts(plan, violations)
    assert "P2" in result
    assert "P1" not in result
    assert result["P2"]["post"]["title"] == "Bad Post"
    assert len(result["P2"]["pins"]) == 1
    assert result["P2"]["pins"][0]["pin_id"] == "W8-02"


def test_identify_replaceable_posts_ignores_non_targeted():
    plan = {
        "blog_posts": [{"post_id": "P1", "title": "Post"}],
        "pins": [{"pin_id": "W8-01", "source_post_id": "P1"}],
    }
    violations = [
        {"severity": "warning", "post_id": "P1", "message": "Minor issue"},
    ]

    result = identify_replaceable_posts(plan, violations)
    assert result == {}


def test_splice_replacements_swaps_offending_content():
    plan = {
        "blog_posts": [
            {"post_id": "P1", "title": "Keep"},
            {"post_id": "P2", "title": "Replace Me"},
        ],
        "pins": [
            {"pin_id": "W8-01", "source_post_id": "P1", "text": "keep"},
            {"pin_id": "W8-02", "source_post_id": "P2", "text": "replace"},
        ],
    }
    replacements = {
        "blog_posts": [{"post_id": "P2", "title": "Replaced!"}],
        "pins": [{"pin_id": "W8-02", "source_post_id": "P2", "text": "new"}],
    }

    result = splice_replacements(
        plan,
        replacements,
        offending_post_ids={"P2"},
        offending_pin_ids={"W8-02"},
    )

    assert result["blog_posts"][0]["title"] == "Keep"
    assert result["blog_posts"][1]["title"] == "Replaced!"
    assert result["pins"][0]["text"] == "keep"
    assert result["pins"][1]["text"] == "new"


def test_splice_replacements_preserves_non_offending():
    plan = {
        "blog_posts": [{"post_id": "P1", "title": "Safe"}],
        "pins": [{"pin_id": "W8-01", "source_post_id": "P1", "text": "ok"}],
    }
    replacements = {"blog_posts": [], "pins": []}

    result = splice_replacements(
        plan, replacements, offending_post_ids=set(), offending_pin_ids=set()
    )

    assert result["blog_posts"][0]["title"] == "Safe"
    assert result["pins"][0]["text"] == "ok"
