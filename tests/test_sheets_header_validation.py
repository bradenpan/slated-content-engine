"""Tests for SheetsAPI._validate_headers raising SheetsAPIError on mismatch.

Validates fix #11: _validate_headers now raises SheetsAPIError (instead of
only logging a warning) when actual headers don't match expected headers,
preventing silent data corruption from manual Sheet edits.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.shared.apis.sheets_api import SheetsAPI, SheetsAPIError


@pytest.fixture
def sheets_api():
    """Create a SheetsAPI instance with mocked Google API internals."""
    with patch.object(SheetsAPI, "__init__", lambda self, **kw: None):
        api = SheetsAPI.__new__(SheetsAPI)
        api.sheet_id = "test-sheet-id"
        api.sheets = MagicMock()
        api._validated_tabs = set()
        return api


EXPECTED_HEADERS = ["ID", "Type", "Title", "Status"]


class TestHeaderMismatch:
    """_validate_headers raises SheetsAPIError when headers don't match."""

    def test_mismatched_headers_raises_error(self, sheets_api):
        sheets_api.sheets.values().get().execute.return_value = {
            "values": [["ID", "Type", "WRONG_COL", "Status"]]
        }

        with pytest.raises(SheetsAPIError, match="Header mismatch"):
            sheets_api._validate_headers("TestTab", EXPECTED_HEADERS)

    def test_error_message_describes_mismatch(self, sheets_api):
        actual = ["ID", "Type", "Name", "Status"]
        sheets_api.sheets.values().get().execute.return_value = {
            "values": [actual]
        }

        with pytest.raises(SheetsAPIError, match="Expected.*got"):
            sheets_api._validate_headers("TestTab", EXPECTED_HEADERS)

    def test_fewer_columns_raises_error(self, sheets_api):
        sheets_api.sheets.values().get().execute.return_value = {
            "values": [["ID", "Type"]]
        }

        with pytest.raises(SheetsAPIError, match="Header mismatch"):
            sheets_api._validate_headers("TestTab", EXPECTED_HEADERS)

    def test_extra_trailing_columns_allowed(self, sheets_api):
        """Extra columns AFTER expected headers are OK (e.g., regen workflow adds cols M-N)."""
        sheets_api.sheets.values().get().execute.return_value = {
            "values": [["ID", "Type", "Title", "Status", "Extra", "Regen →"]]
        }

        # Should NOT raise — trailing columns are ignored
        sheets_api._validate_headers("TestTab", EXPECTED_HEADERS)

    def test_inserted_column_shifts_expected_raises_error(self, sheets_api):
        """A column inserted BEFORE expected columns shifts indices and must raise."""
        sheets_api.sheets.values().get().execute.return_value = {
            "values": [["Extra", "ID", "Type", "Title", "Status"]]
        }

        with pytest.raises(SheetsAPIError, match="Header mismatch"):
            sheets_api._validate_headers("TestTab", EXPECTED_HEADERS)


class TestHeaderMatch:
    """_validate_headers succeeds when headers match."""

    def test_matching_headers_no_exception(self, sheets_api):
        sheets_api.sheets.values().get().execute.return_value = {
            "values": [EXPECTED_HEADERS]
        }

        # Should not raise
        sheets_api._validate_headers("TestTab", EXPECTED_HEADERS)

    def test_matching_headers_tab_added_to_validated(self, sheets_api):
        sheets_api.sheets.values().get().execute.return_value = {
            "values": [EXPECTED_HEADERS]
        }

        sheets_api._validate_headers("TestTab", EXPECTED_HEADERS)
        assert "TestTab" in sheets_api._validated_tabs


class TestHeaderCaching:
    """Second call for the same tab skips the API call (cached)."""

    def test_second_call_does_not_hit_api(self, sheets_api):
        sheets_api.sheets.values().get().execute.return_value = {
            "values": [EXPECTED_HEADERS]
        }

        sheets_api._validate_headers("TestTab", EXPECTED_HEADERS)

        # Reset the mock call count
        sheets_api.sheets.values().get().execute.reset_mock()

        # Second call for the same tab
        sheets_api._validate_headers("TestTab", EXPECTED_HEADERS)

        # API should NOT have been called again
        assert sheets_api.sheets.values().get().execute.call_count == 0

    def test_different_tab_still_calls_api(self, sheets_api):
        sheets_api.sheets.values().get().execute.return_value = {
            "values": [EXPECTED_HEADERS]
        }

        sheets_api._validate_headers("Tab1", EXPECTED_HEADERS)
        sheets_api.sheets.values().get().execute.reset_mock()

        sheets_api._validate_headers("Tab2", EXPECTED_HEADERS)

        # API should be called for the new tab
        assert sheets_api.sheets.values().get().execute.call_count == 1
