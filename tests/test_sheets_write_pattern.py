"""Tests for the write-then-clear pattern in SheetsAPI._clear_and_write.

Validates fix #1: _clear_and_write restructured to write data first, then
clear excess rows. This ensures data is preserved even if the clear step fails.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from src.apis.sheets_api import SheetsAPI, SheetsAPIError


@pytest.fixture
def sheets_api():
    """Create a SheetsAPI instance with mocked Google API internals."""
    with patch.object(SheetsAPI, "__init__", lambda self, **kw: None):
        api = SheetsAPI.__new__(SheetsAPI)
        api.sheet_id = "test-sheet-id"
        api.sheets = MagicMock()
        api._validated_tabs = set()
        return api


class TestClearAndWriteSuccessPath:
    """Normal operation: update succeeds, excess rows cleared."""

    def test_update_called_then_clear_called(self, sheets_api):
        rows = [["Header"], ["Row 1"], ["Row 2"]]
        sheets_api._clear_and_write("TestTab", rows)

        # update was called once (no retry needed)
        update_mock = sheets_api.sheets.values().update
        assert update_mock.call_count == 1

        call_kwargs = update_mock.call_args
        assert call_kwargs[1]["range"] == "'TestTab'!A1"
        assert call_kwargs[1]["body"] == {"values": rows}

        # clear was called for rows beyond the data
        clear_mock = sheets_api.sheets.values().clear
        assert clear_mock.call_count == 1
        clear_kwargs = clear_mock.call_args
        assert clear_kwargs[1]["range"] == "'TestTab'!A4:ZZ"

    def test_no_exception_on_normal_success(self, sheets_api):
        rows = [["A"], ["B"]]
        # Should not raise
        sheets_api._clear_and_write("Tab", rows)


class TestClearFailsButDataPreserved:
    """Scenario A: update succeeds but clear of excess rows fails."""

    def test_no_exception_raised_when_clear_fails(self, sheets_api):
        sheets_api.sheets.values().clear().execute.side_effect = Exception(
            "Clear API error"
        )

        rows = [["Header"], ["Data"]]
        # Should NOT raise -- data was already written
        sheets_api._clear_and_write("TestTab", rows)

    def test_warning_logged_when_clear_fails(self, sheets_api, caplog):
        sheets_api.sheets.values().clear().execute.side_effect = Exception(
            "Clear API error"
        )

        rows = [["Header"], ["Data"]]
        with caplog.at_level(logging.WARNING):
            sheets_api._clear_and_write("TestTab", rows)

        assert any("stale trailing rows" in r.message.lower() for r in caplog.records)

    def test_update_was_executed_before_clear_failure(self, sheets_api):
        sheets_api.sheets.values().clear().execute.side_effect = Exception(
            "Clear API error"
        )

        rows = [["Header"], ["Data"]]
        sheets_api._clear_and_write("TestTab", rows)

        # update was called and executed (data persisted)
        update_execute = sheets_api.sheets.values().update().execute
        assert update_execute.call_count == 1


class TestWriteFailsOnBothRetries:
    """Scenario B: update fails on both retry attempts."""

    def test_sheets_api_error_raised(self, sheets_api):
        sheets_api.sheets.values().update().execute.side_effect = Exception(
            "Write API error"
        )

        rows = [["Header"], ["Data"]]
        with pytest.raises(SheetsAPIError, match="(?i)failed.*retry"):
            sheets_api._clear_and_write("TestTab", rows)

    def test_clear_never_called_when_write_fails(self, sheets_api):
        sheets_api.sheets.values().update().execute.side_effect = Exception(
            "Write API error"
        )

        rows = [["Header"], ["Data"]]
        with pytest.raises(SheetsAPIError):
            sheets_api._clear_and_write("TestTab", rows)

        # clear should never be called -- data was not written
        clear_execute = sheets_api.sheets.values().clear().execute
        assert clear_execute.call_count == 0

    def test_update_retried_exactly_twice(self, sheets_api):
        sheets_api.sheets.values().update().execute.side_effect = Exception(
            "Write API error"
        )

        rows = [["Header"], ["Data"]]
        with pytest.raises(SheetsAPIError):
            sheets_api._clear_and_write("TestTab", rows)

        update_execute = sheets_api.sheets.values().update().execute
        assert update_execute.call_count == 2
