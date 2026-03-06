"""Tests for src/tiktok/regen_content.py — TikTok content-level regeneration."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from src.tiktok.regen_content import (
    _col_position_to_slide_index,
    _find_image_prompt,
    _parse_regen_status,
    regen_content,
)


# ---------------------------------------------------------------------------
# _parse_regen_status
# ---------------------------------------------------------------------------


def test_parse_regen_full():
    assert _parse_regen_status("regen") is None


def test_parse_regen_single_slide():
    assert _parse_regen_status("regen_image_0") == [0]


def test_parse_regen_multiple_slides():
    assert _parse_regen_status("regen_image_0,regen_image_3") == [0, 3]


def test_parse_regen_invalid_target_falls_back_to_full():
    # "regen_image_invalid" has no valid int — returns None (full regen)
    result = _parse_regen_status("regen_image_invalid")
    assert result is None


def test_parse_regen_strips_whitespace():
    assert _parse_regen_status("  regen_image_2  ") == [2]


# ---------------------------------------------------------------------------
# _col_position_to_slide_index
# ---------------------------------------------------------------------------


def test_col_pos_0_is_hook():
    assert _col_position_to_slide_index(0, 5) == 0


def test_col_pos_8_is_cta():
    # CTA is always at content_slide_count + 1
    assert _col_position_to_slide_index(8, 5) == 6


def test_col_pos_3_content_slide():
    assert _col_position_to_slide_index(3, 5) == 3


def test_col_pos_out_of_range():
    # 3 content slides, col_pos 6 is beyond content range but not CTA (8)
    assert _col_position_to_slide_index(6, 3) is None


def test_col_pos_at_boundary():
    # Exactly at the content_slide_count boundary
    assert _col_position_to_slide_index(3, 3) == 3


def test_col_pos_beyond_content_but_below_cta():
    # 2 content slides, col_pos 4 is out of range
    assert _col_position_to_slide_index(4, 2) is None


# ---------------------------------------------------------------------------
# _find_image_prompt
# ---------------------------------------------------------------------------


def test_find_image_prompt_match():
    prompts = [
        {"slide_index": 0, "prompt": "hook bg"},
        {"slide_index": 3, "prompt": "content bg"},
    ]
    assert _find_image_prompt(prompts, 3) == {"slide_index": 3, "prompt": "content bg"}


def test_find_image_prompt_missing():
    prompts = [{"slide_index": 0, "prompt": "hook bg"}]
    assert _find_image_prompt(prompts, 5) is None


def test_find_image_prompt_empty_list():
    assert _find_image_prompt([], 0) is None


# ---------------------------------------------------------------------------
# regen_content — env validation
# ---------------------------------------------------------------------------


def test_regen_raises_if_no_spreadsheet_id(monkeypatch):
    monkeypatch.delenv("TIKTOK_SPREADSHEET_ID", raising=False)
    with pytest.raises(ValueError, match="TIKTOK_SPREADSHEET_ID"):
        regen_content()


# ---------------------------------------------------------------------------
# regen_content — skips carousel not in plan
# ---------------------------------------------------------------------------


@patch("src.tiktok.regen_content.SlackNotify")
@patch("src.tiktok.regen_content.GcsAPI")
@patch("src.tiktok.regen_content.CarouselAssembler")
@patch("src.tiktok.regen_content.ImageGenAPI")
@patch("src.tiktok.regen_content.load_plan")
@patch("src.tiktok.regen_content.find_latest_plan")
def test_regen_skips_carousel_not_in_plan(
    mock_find, mock_load, mock_img, mock_assembler, mock_gcs, mock_slack_cls,
    monkeypatch,
):
    monkeypatch.setenv("TIKTOK_SPREADSHEET_ID", "sheet-123")
    mock_find.return_value = Path("/fake/plan.json")
    mock_load.return_value = {"carousels": []}  # no matching carousels

    sheets = MagicMock()
    sheets.read_tiktok_content_regen_requests.return_value = [
        {"carousel_id": "T-MISSING", "status": "regen"},
    ]

    regen_content(sheets=sheets, slack=MagicMock())

    sheets.update_tiktok_content_row.assert_called_once()
    call_args = sheets.update_tiktok_content_row.call_args
    assert call_args.args[0] == "T-MISSING"
    assert "not found" in call_args.kwargs["notes"].lower()


# ---------------------------------------------------------------------------
# regen_content — deferred prompt mutations
# ---------------------------------------------------------------------------


@patch("src.tiktok.regen_content.time.time", return_value=1000)
@patch("src.tiktok.regen_content.SlackNotify")
@patch("src.tiktok.regen_content.GcsAPI")
@patch("src.tiktok.regen_content.CarouselAssembler")
@patch("src.tiktok.regen_content.ImageGenAPI")
@patch("src.tiktok.regen_content.clean_image", side_effect=lambda p, **kw: p)
@patch("src.tiktok.regen_content.build_slides_for_render", return_value=[])
@patch("src.tiktok.regen_content.load_plan")
@patch("src.tiktok.regen_content.find_latest_plan")
def test_regen_defers_prompt_mutations_until_success(
    mock_find, mock_load, mock_build, mock_clean,
    mock_img_cls, mock_assembler_cls, mock_gcs_cls, mock_slack_cls, mock_time,
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("TIKTOK_SPREADSHEET_ID", "sheet-123")

    plan_path = tmp_path / "plan.json"
    plan = {
        "carousels": [
            {
                "carousel_id": "T-01",
                "template_family": "clean_educational",
                "content_slides": [{"text": "s1"}, {"text": "s2"}],
                "image_prompts": [
                    {"slide_index": 0, "prompt": "original hook prompt"},
                ],
            }
        ]
    }
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    mock_find.return_value = plan_path
    mock_load.return_value = plan

    sheets = MagicMock()
    sheets.read_tiktok_content_regen_requests.return_value = [
        {"carousel_id": "T-01", "status": "regen_image_0", "feedback": "make it brighter"},
    ]

    img_gen = MagicMock()
    img_gen.generate.return_value = tmp_path / "bg-slide-0.png"
    (tmp_path / "bg-slide-0.png").write_bytes(b"fake")
    mock_img_cls.return_value = img_gen

    assembler = MagicMock()
    assembler.render_carousel.return_value = [tmp_path / "slide-0.png"]
    (tmp_path / "slide-0.png").write_bytes(b"fake")
    mock_assembler_cls.return_value = assembler

    gcs = MagicMock()
    gcs.is_available = True
    gcs.upload_image.return_value = "https://example.com/slide-0.png"
    gcs.get_public_url.return_value = "https://example.com/existing.png"
    mock_gcs_cls.return_value = gcs

    # Patch TIKTOK_OUTPUT_DIR so rendered files go to tmp_path
    with patch("src.tiktok.regen_content.TIKTOK_OUTPUT_DIR", tmp_path):
        regen_content(sheets=sheets, slack=MagicMock())

    # After success, the prompt should have been updated with feedback
    updated_prompt = plan["carousels"][0]["image_prompts"][0]["prompt"]
    assert "make it brighter" in updated_prompt


# ---------------------------------------------------------------------------
# regen_content — saves plan only if at least one success
# ---------------------------------------------------------------------------


@patch("src.tiktok.regen_content.time.time", return_value=1000)
@patch("src.tiktok.regen_content.SlackNotify")
@patch("src.tiktok.regen_content.GcsAPI")
@patch("src.tiktok.regen_content.CarouselAssembler")
@patch("src.tiktok.regen_content.ImageGenAPI")
@patch("src.tiktok.regen_content.clean_image", side_effect=lambda p, **kw: p)
@patch("src.tiktok.regen_content.build_slides_for_render", return_value=[])
@patch("src.tiktok.regen_content.load_plan")
@patch("src.tiktok.regen_content.find_latest_plan")
def test_regen_saves_plan_on_success(
    mock_find, mock_load, mock_build, mock_clean,
    mock_img_cls, mock_assembler_cls, mock_gcs_cls, mock_slack_cls, mock_time,
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("TIKTOK_SPREADSHEET_ID", "sheet-123")

    plan_path = tmp_path / "plan.json"
    plan = {
        "carousels": [
            {
                "carousel_id": "T-01",
                "template_family": "clean_educational",
                "content_slides": [{"text": "s1"}],
                "image_prompts": [{"slide_index": 0, "prompt": "hook"}],
            }
        ]
    }
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    mock_find.return_value = plan_path
    mock_load.return_value = plan

    sheets = MagicMock()
    sheets.read_tiktok_content_regen_requests.return_value = [
        {"carousel_id": "T-01", "status": "regen"},
    ]

    img_gen = MagicMock()
    img_gen.generate.return_value = tmp_path / "bg.png"
    (tmp_path / "bg.png").write_bytes(b"fake")
    mock_img_cls.return_value = img_gen

    assembler = MagicMock()
    assembler.render_carousel.return_value = [tmp_path / "s0.png"]
    (tmp_path / "s0.png").write_bytes(b"fake")
    mock_assembler_cls.return_value = assembler

    gcs = MagicMock()
    gcs.is_available = True
    gcs.upload_image.return_value = "https://example.com/s0.png"
    gcs.get_public_url.return_value = "https://example.com/existing.png"
    mock_gcs_cls.return_value = gcs

    with patch("src.tiktok.regen_content.TIKTOK_OUTPUT_DIR", tmp_path):
        regen_content(sheets=sheets, slack=MagicMock())

    # Plan file should have been rewritten
    saved = json.loads(plan_path.read_text(encoding="utf-8"))
    assert saved is not None


# ---------------------------------------------------------------------------
# regen_content — resets trigger on success
# ---------------------------------------------------------------------------


@patch("src.tiktok.regen_content.time.time", return_value=1000)
@patch("src.tiktok.regen_content.SlackNotify")
@patch("src.tiktok.regen_content.GcsAPI")
@patch("src.tiktok.regen_content.CarouselAssembler")
@patch("src.tiktok.regen_content.ImageGenAPI")
@patch("src.tiktok.regen_content.clean_image", side_effect=lambda p, **kw: p)
@patch("src.tiktok.regen_content.build_slides_for_render", return_value=[])
@patch("src.tiktok.regen_content.load_plan")
@patch("src.tiktok.regen_content.find_latest_plan")
def test_regen_resets_trigger_on_success(
    mock_find, mock_load, mock_build, mock_clean,
    mock_img_cls, mock_assembler_cls, mock_gcs_cls, mock_slack_cls, mock_time,
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("TIKTOK_SPREADSHEET_ID", "sheet-123")

    plan_path = tmp_path / "plan.json"
    plan = {
        "carousels": [
            {
                "carousel_id": "T-01",
                "template_family": "clean_educational",
                "content_slides": [],
                "image_prompts": [{"slide_index": 0, "prompt": "hook"}],
            }
        ]
    }
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    mock_find.return_value = plan_path
    mock_load.return_value = plan

    sheets = MagicMock()
    sheets.read_tiktok_content_regen_requests.return_value = [
        {"carousel_id": "T-01", "status": "regen"},
    ]

    img_gen = MagicMock()
    img_gen.generate.return_value = tmp_path / "bg.png"
    (tmp_path / "bg.png").write_bytes(b"fake")
    mock_img_cls.return_value = img_gen

    assembler = MagicMock()
    assembler.render_carousel.return_value = [tmp_path / "s0.png"]
    (tmp_path / "s0.png").write_bytes(b"fake")
    mock_assembler_cls.return_value = assembler

    gcs = MagicMock()
    gcs.is_available = True
    gcs.upload_image.return_value = "https://example.com/s0.png"
    gcs.get_public_url.return_value = "https://example.com/existing.png"
    mock_gcs_cls.return_value = gcs

    with patch("src.tiktok.regen_content.TIKTOK_OUTPUT_DIR", tmp_path):
        regen_content(sheets=sheets, slack=MagicMock())

    sheets.reset_tiktok_content_regen_trigger.assert_called_once()


# ---------------------------------------------------------------------------
# regen_content — leaves trigger active when all fail
# ---------------------------------------------------------------------------


@patch("src.tiktok.regen_content.time.time", return_value=1000)
@patch("src.tiktok.regen_content.SlackNotify")
@patch("src.tiktok.regen_content.GcsAPI")
@patch("src.tiktok.regen_content.CarouselAssembler")
@patch("src.tiktok.regen_content.ImageGenAPI")
@patch("src.tiktok.regen_content.load_plan")
@patch("src.tiktok.regen_content.find_latest_plan")
def test_regen_leaves_trigger_when_all_fail(
    mock_find, mock_load,
    mock_img_cls, mock_assembler_cls, mock_gcs_cls, mock_slack_cls, mock_time,
    monkeypatch, tmp_path,
):
    monkeypatch.setenv("TIKTOK_SPREADSHEET_ID", "sheet-123")

    plan_path = tmp_path / "plan.json"
    plan = {
        "carousels": [
            {
                "carousel_id": "T-01",
                "template_family": "clean_educational",
                "content_slides": [],
                "image_prompts": [{"slide_index": 0, "prompt": "hook"}],
            }
        ]
    }
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    mock_find.return_value = plan_path
    mock_load.return_value = plan

    sheets = MagicMock()
    sheets.read_tiktok_content_regen_requests.return_value = [
        {"carousel_id": "T-01", "status": "regen"},
    ]

    img_gen = MagicMock()
    img_gen.generate.side_effect = RuntimeError("image gen exploded")
    mock_img_cls.return_value = img_gen

    assembler = MagicMock()
    # The assembler will raise because no images were generated
    assembler.render_carousel.side_effect = RuntimeError("render fail")
    mock_assembler_cls.return_value = assembler

    gcs = MagicMock()
    gcs.is_available = True
    mock_gcs_cls.return_value = gcs

    with patch("src.tiktok.regen_content.TIKTOK_OUTPUT_DIR", tmp_path):
        regen_content(sheets=sheets, slack=MagicMock())

    # Trigger should NOT have been reset
    sheets.reset_tiktok_content_regen_trigger.assert_not_called()
