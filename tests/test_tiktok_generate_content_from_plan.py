"""Tests for generate_content_from_plan() in src/tiktok/generate_weekly_plan.py."""

import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# Stub out heavy dependencies so we can import generate_weekly_plan
# without requiring anthropic, google-auth, etc.
_STUBS = [
    "anthropic",
    "google.auth",
    "google.oauth2",
    "google.oauth2.service_account",
    "googleapiclient",
    "googleapiclient.discovery",
    "google.cloud",
    "google.cloud.storage",
    "requests_oauthlib",
]
for _mod in _STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from src.tiktok.generate_weekly_plan import generate_content_from_plan


_MODULE = "src.tiktok.generate_weekly_plan"


def _valid_plan(n=2):
    """Return a minimal valid plan dict."""
    return {
        "carousels": [
            {
                "carousel_id": f"T{i:02d}",
                "topic": "topic",
                "angle": "angle",
                "structure": "structure",
                "hook_type": "hook_type",
                "template_family": "clean_educational",
                "hook_text": "Hook",
                "content_slides": [
                    {"headline": "H1", "body_text": "B1"},
                    {"headline": "H2", "body_text": "B2"},
                ],
                "cta_slide": {"cta_primary": "Follow @slatedapp"},
                "caption": "caption",
                "hashtags": ["#test"],
                "scheduled_date": "2026-03-10",
                "is_aigc": True,
            }
            for i in range(1, n + 1)
        ]
    }


def _rendered_result(carousel_id, slides=None, error=None):
    """Build a mock rendered carousel result."""
    r = {
        "carousel_id": carousel_id,
        "rendered_slides": slides or [f"/tmp/{carousel_id}-01.png", f"/tmp/{carousel_id}-02.png"],
        "slide_count": len(slides) if slides else 2,
    }
    if error:
        r["render_error"] = error
        r["rendered_slides"] = []
        r["slide_count"] = 0
    return r


@pytest.fixture
def plan_file(tmp_path):
    """Write a valid plan JSON to tmp_path and return the path."""
    plan = _valid_plan()
    plan_path = tmp_path / "weekly-plan-2026-03-09.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan_path


class TestGenerateContentFromPlan:

    def test_loads_latest_plan_from_tiktok_data_dir(self, tmp_path):
        """When plan_path is None, loads from TIKTOK_DATA_DIR via find_latest_plan."""
        plan = _valid_plan()
        plan_path = tmp_path / "weekly-plan-2026-03-09.json"
        plan_path.write_text(json.dumps(plan), encoding="utf-8")

        mock_find = MagicMock(return_value=plan_path)
        mock_load = MagicMock(return_value=plan)

        with (
            patch(f"{_MODULE}.TIKTOK_DATA_DIR", tmp_path),
            patch("src.shared.utils.plan_utils.find_latest_plan", mock_find),
            patch("src.shared.utils.plan_utils.load_plan", mock_load),
            patch(f"{_MODULE}.generate_carousels", return_value=[
                _rendered_result("T01"), _rendered_result("T02"),
            ]),
        ):
            result = generate_content_from_plan(dry_run=True)

        mock_find.assert_called_once_with(data_dir=tmp_path)
        assert "_rendered" in result

    def test_raises_file_not_found_if_no_plan_files(self, tmp_path):
        """Raises FileNotFoundError when no plan files exist."""
        mock_find = MagicMock(return_value=None)

        with (
            patch(f"{_MODULE}.TIKTOK_DATA_DIR", tmp_path),
            patch("src.shared.utils.plan_utils.find_latest_plan", mock_find),
        ):
            with pytest.raises(FileNotFoundError, match="No TikTok weekly plan"):
                generate_content_from_plan()

    def test_raises_value_error_if_plan_has_no_carousels(self, tmp_path):
        """Raises ValueError when plan has empty carousels."""
        plan_path = tmp_path / "weekly-plan-2026-03-09.json"
        empty_plan = {"carousels": []}
        plan_path.write_text(json.dumps(empty_plan), encoding="utf-8")

        mock_load = MagicMock(return_value=empty_plan)
        with patch("src.shared.utils.plan_utils.load_plan", mock_load):
            with pytest.raises(ValueError, match="no carousels"):
                generate_content_from_plan(plan_path=plan_path)

    def test_calls_generate_carousels_and_filters_render_failures(self, plan_file):
        """Render failures are filtered out of the published set."""
        rendered = [
            _rendered_result("T01"),
            _rendered_result("T02", error="puppeteer timeout"),
        ]

        with (
            patch("src.shared.utils.plan_utils.load_plan", return_value=_valid_plan()),
            patch(f"{_MODULE}.generate_carousels", return_value=rendered) as m_gen,
        ):
            result = generate_content_from_plan(plan_path=plan_file, dry_run=True)

        m_gen.assert_called_once()
        # Only T01 should be in _rendered (T02 had render_error)
        assert len(result["_rendered"]) == 1
        assert result["_rendered"][0]["carousel_id"] == "T01"

    def test_uploads_rendered_slides_to_gcs(self, plan_file):
        """Successful renders get uploaded to GCS."""
        rendered = [_rendered_result("T01")]

        mock_gcs = MagicMock()
        mock_gcs.is_available = True
        mock_gcs.upload_image.return_value = "https://storage.example.com/slide.png"

        with (
            patch("src.shared.utils.plan_utils.load_plan", return_value=_valid_plan(1)),
            patch(f"{_MODULE}.generate_carousels", return_value=rendered),
            patch(f"{_MODULE}.GcsAPI", return_value=mock_gcs),
            patch(f"{_MODULE}.publish_content_queue"),
            patch(f"{_MODULE}.SlackNotify"),
            patch.dict(os.environ, {"TIKTOK_SPREADSHEET_ID": "sheet-id"}),
            patch(f"{_MODULE}.SheetsAPI"),
        ):
            result = generate_content_from_plan(plan_path=plan_file, dry_run=False)

        assert mock_gcs.upload_image.call_count == 2  # 2 slides per carousel

    def test_publishes_to_content_queue_via_sheets(self, plan_file):
        """Rendered carousels get published to Content Queue."""
        rendered = [_rendered_result("T01")]

        mock_gcs = MagicMock()
        mock_gcs.is_available = True
        mock_gcs.upload_image.return_value = "https://gcs.example.com/slide.png"

        with (
            patch("src.shared.utils.plan_utils.load_plan", return_value=_valid_plan(1)),
            patch(f"{_MODULE}.generate_carousels", return_value=rendered),
            patch(f"{_MODULE}.GcsAPI", return_value=mock_gcs),
            patch(f"{_MODULE}.publish_content_queue") as m_publish,
            patch(f"{_MODULE}.SlackNotify"),
            patch.dict(os.environ, {"TIKTOK_SPREADSHEET_ID": "sheet-id"}),
            patch(f"{_MODULE}.SheetsAPI"),
        ):
            generate_content_from_plan(plan_path=plan_file, dry_run=False)

        m_publish.assert_called_once()

    def test_dry_run_skips_gcs_and_sheet_writes(self, plan_file):
        """dry_run=True skips GCS upload and sheet publish."""
        rendered = [_rendered_result("T01")]

        with (
            patch("src.shared.utils.plan_utils.load_plan", return_value=_valid_plan(1)),
            patch(f"{_MODULE}.generate_carousels", return_value=rendered),
            patch(f"{_MODULE}.GcsAPI") as m_gcs_cls,
            patch(f"{_MODULE}.publish_content_queue") as m_publish,
        ):
            result = generate_content_from_plan(plan_path=plan_file, dry_run=True)

        m_gcs_cls.assert_not_called()
        m_publish.assert_not_called()
        assert "_rendered" in result

    def test_resaves_plan_with_rendered_data(self, plan_file):
        """Plan file is re-saved with _rendered data after rendering."""
        rendered = [_rendered_result("T01"), _rendered_result("T02")]

        with (
            patch("src.shared.utils.plan_utils.load_plan", return_value=_valid_plan()),
            patch(f"{_MODULE}.generate_carousels", return_value=rendered),
        ):
            generate_content_from_plan(plan_path=plan_file, dry_run=True)

        saved = json.loads(plan_file.read_text(encoding="utf-8"))
        assert "_rendered" in saved
        assert len(saved["_rendered"]) == 2

    def test_handles_partial_gcs_upload_failures(self, plan_file):
        """Partial GCS upload failure sets gcs_upload_failed flag."""
        rendered = [_rendered_result("T01", slides=["/tmp/T01-01.png", "/tmp/T01-02.png"])]

        mock_gcs = MagicMock()
        mock_gcs.is_available = True
        # First upload succeeds, second returns None (failure)
        mock_gcs.upload_image.side_effect = [
            "https://gcs.example.com/slide-0.png",
            None,
        ]

        with (
            patch("src.shared.utils.plan_utils.load_plan", return_value=_valid_plan(1)),
            patch(f"{_MODULE}.generate_carousels", return_value=rendered),
            patch(f"{_MODULE}.GcsAPI", return_value=mock_gcs),
            patch(f"{_MODULE}.publish_content_queue"),
            patch(f"{_MODULE}.SlackNotify"),
            patch.dict(os.environ, {"TIKTOK_SPREADSHEET_ID": "sheet-id"}),
            patch(f"{_MODULE}.SheetsAPI"),
        ):
            result = generate_content_from_plan(plan_path=plan_file, dry_run=False)

        # The rendered carousel should have gcs_upload_failed flag
        # (only 1 of 2 uploads succeeded, so partial failure)
        # Note: the flag is set on the rendered dict items in-place
        assert rendered[0].get("gcs_upload_failed") is True
