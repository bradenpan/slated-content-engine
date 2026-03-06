"""Tests for generate_plan() and _call_claude_for_plan() in src/tiktok/generate_weekly_plan.py."""

import json
import os
import sys
import pytest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

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

from src.tiktok.generate_weekly_plan import (
    generate_plan,
    _call_claude_for_plan,
)


def _valid_plan_dict(n=2):
    """Return a minimal valid plan dict with n carousels."""
    return {
        "carousels": [
            {
                "carousel_id": f"T{i:02d}",
                "topic": "topic_val",
                "angle": "angle_val",
                "structure": "structure_val",
                "hook_type": "hook_type_val",
                "template_family": "clean_educational",
                "hook_text": "Short hook",
                "content_slides": [
                    {"headline": "H1", "body_text": "B1"},
                    {"headline": "H2", "body_text": "B2"},
                    {"headline": "H3", "body_text": "B3"},
                ],
                "cta_slide": {"cta_primary": "Follow @slatedapp"},
                "caption": "caption text",
                "hashtags": ["#slated"],
                "scheduled_date": "2026-03-10",
                "is_aigc": True,
            }
            for i in range(1, n + 1)
        ]
    }


# Shared mock targets
_MODULE = "src.tiktok.generate_weekly_plan"


@pytest.fixture
def mock_deps():
    """Patch all external dependencies of generate_plan."""
    with (
        patch(f"{_MODULE}.load_strategy_context") as m_strategy,
        patch(f"{_MODULE}.load_latest_analysis") as m_analysis,
        patch(f"{_MODULE}.generate_content_memory_summary") as m_memory,
        patch(f"{_MODULE}.load_taxonomy") as m_taxonomy,
        patch(f"{_MODULE}.get_current_seasonal_window") as m_season,
    ):
        m_strategy.return_value = {"strategy_doc": "test strategy", "seasonal_calendar": {"seasons": []}}
        m_analysis.return_value = "no analysis"
        m_memory.return_value = "content memory"
        m_taxonomy.return_value = {"dimensions": {}}
        m_season.return_value = "no seasonal window"
        yield {
            "strategy": m_strategy,
            "analysis": m_analysis,
            "memory": m_memory,
            "taxonomy": m_taxonomy,
            "season": m_season,
        }


class TestCallClaudeForPlan:
    """Tests for _call_claude_for_plan()."""

    def test_raises_if_claude_returns_non_dict(self):
        """Non-dict response from Claude raises ValueError."""
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = "not a dict"
        with pytest.raises(ValueError, match="Plan must be a dict"):
            _call_claude_for_plan(
                claude=claude,
                strategy_context={"strategy_doc": ""},
                content_memory="",
                latest_analysis="",
                seasonal_context="",
                taxonomy={},
                week_number=1,
                posting_dates="",
            )

    def test_raises_if_carousels_key_missing(self):
        """Missing 'carousels' key raises ValueError."""
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = {"slides": []}
        with pytest.raises(ValueError, match="missing 'carousels' key"):
            _call_claude_for_plan(
                claude=claude,
                strategy_context={"strategy_doc": ""},
                content_memory="",
                latest_analysis="",
                seasonal_context="",
                taxonomy={},
                week_number=1,
                posting_dates="",
            )

    def test_raises_if_carousels_is_empty_list(self):
        """Empty carousels list raises ValueError."""
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = {"carousels": []}
        with pytest.raises(ValueError, match="non-empty list"):
            _call_claude_for_plan(
                claude=claude,
                strategy_context={"strategy_doc": ""},
                content_memory="",
                latest_analysis="",
                seasonal_context="",
                taxonomy={},
                week_number=1,
                posting_dates="",
            )


class TestGeneratePlan:
    """Tests for generate_plan()."""

    def test_generate_plan_calls_claude_and_returns_plan(self, mock_deps, tmp_path):
        """generate_plan calls Claude and returns the plan dict."""
        plan_data = _valid_plan_dict()
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = plan_data

        with patch(f"{_MODULE}.TIKTOK_DATA_DIR", tmp_path):
            result = generate_plan(
                week_start_date="2026-03-09",
                claude=claude,
                dry_run=True,
            )

        assert result["carousels"] == plan_data["carousels"]
        claude.generate_tiktok_plan.assert_called_once()

    def test_plan_only_writes_to_weekly_review_sheet(self, mock_deps, tmp_path):
        """plan_only=True writes specs to Weekly Review tab and returns."""
        plan_data = _valid_plan_dict()
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = plan_data
        sheets = MagicMock()

        with (
            patch(f"{_MODULE}.TIKTOK_DATA_DIR", tmp_path),
            patch.dict(os.environ, {"TIKTOK_SPREADSHEET_ID": "sheet-123"}),
        ):
            result = generate_plan(
                week_start_date="2026-03-09",
                claude=claude,
                sheets=sheets,
                plan_only=True,
            )

        sheets.write_tiktok_weekly_review.assert_called_once_with(plan_data)
        assert "carousels" in result

    def test_dry_run_skips_sheet_writes(self, mock_deps, tmp_path):
        """dry_run=True skips all sheet interactions."""
        plan_data = _valid_plan_dict()
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = plan_data
        sheets = MagicMock()

        with patch(f"{_MODULE}.TIKTOK_DATA_DIR", tmp_path):
            result = generate_plan(
                week_start_date="2026-03-09",
                claude=claude,
                sheets=sheets,
                dry_run=True,
                plan_only=True,
            )

        sheets.write_tiktok_weekly_review.assert_not_called()
        assert "carousels" in result

    def test_saves_plan_json_to_tiktok_data_dir(self, mock_deps, tmp_path):
        """generate_plan saves plan JSON to TIKTOK_DATA_DIR."""
        plan_data = _valid_plan_dict()
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = plan_data

        with patch(f"{_MODULE}.TIKTOK_DATA_DIR", tmp_path):
            generate_plan(
                week_start_date="2026-03-09",
                claude=claude,
                dry_run=True,
            )

        plan_file = tmp_path / "weekly-plan-2026-03-09.json"
        assert plan_file.exists()
        saved = json.loads(plan_file.read_text(encoding="utf-8"))
        assert len(saved["carousels"]) == 2

    def test_raises_value_error_if_no_spreadsheet_id(self, mock_deps, tmp_path):
        """generate_plan raises ValueError when TIKTOK_SPREADSHEET_ID is unset (non dry_run)."""
        plan_data = _valid_plan_dict()
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = plan_data

        with (
            patch(f"{_MODULE}.TIKTOK_DATA_DIR", tmp_path),
            patch.dict(os.environ, {"TIKTOK_SPREADSHEET_ID": ""}, clear=False),
        ):
            with pytest.raises(ValueError, match="TIKTOK_SPREADSHEET_ID"):
                generate_plan(
                    week_start_date="2026-03-09",
                    claude=claude,
                    dry_run=False,
                )

    def test_week_start_date_defaults_to_next_monday(self, mock_deps, tmp_path):
        """When week_start_date is not provided, defaults to current/next Monday."""
        plan_data = _valid_plan_dict()
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = plan_data

        with patch(f"{_MODULE}.TIKTOK_DATA_DIR", tmp_path):
            result = generate_plan(
                claude=claude,
                dry_run=True,
            )

        # A plan file should exist with a Monday date
        plan_files = list(tmp_path.glob("weekly-plan-*.json"))
        assert len(plan_files) == 1
        # Verify the date in the filename is a Monday (weekday 0)
        fname = plan_files[0].stem  # e.g. "weekly-plan-2026-03-09"
        date_str = fname.replace("weekly-plan-", "")
        from datetime import datetime
        plan_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        today = date.today()
        if today.weekday() == 0:
            # If today is Monday, should use today
            assert plan_date == today
        else:
            # Should be next Monday
            assert plan_date.weekday() == 0
            assert plan_date > today

    def test_explicit_week_start_date_is_used(self, mock_deps, tmp_path):
        """An explicit week_start_date is respected in the plan filename."""
        plan_data = _valid_plan_dict()
        claude = MagicMock()
        claude.generate_tiktok_plan.return_value = plan_data

        with patch(f"{_MODULE}.TIKTOK_DATA_DIR", tmp_path):
            generate_plan(
                week_start_date="2026-04-06",
                claude=claude,
                dry_run=True,
            )

        assert (tmp_path / "weekly-plan-2026-04-06.json").exists()
