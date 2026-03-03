"""Tests for publish_content_queue.py Slack notification gated by Sheets write.

Validates fix #2: When the Sheets write fails, the Slack notification sends
a failure message instead of the normal notify_content_ready() call, so the
user knows the Sheet was not updated.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.shared.apis.sheets_api import SheetsAPIError


@pytest.fixture
def mock_dependencies():
    """Patch all external dependencies of publish()."""
    with (
        patch("src.pinterest.publish_content_queue.SheetsAPI") as MockSheets,
        patch("src.pinterest.publish_content_queue.SlackNotify") as MockSlack,
        patch("src.pinterest.publish_content_queue.GcsAPI") as MockGcs,
        patch("src.pinterest.publish_content_queue.DATA_DIR") as mock_data_dir,
        patch("src.pinterest.publish_content_queue.BLOG_OUTPUT_DIR") as mock_blog_dir,
        patch("src.pinterest.publish_content_queue.PIN_OUTPUT_DIR") as mock_pin_dir,
    ):
        # GcsAPI: no GCS client so upload path is skipped
        gcs_instance = MagicMock()
        gcs_instance.client = None
        MockGcs.return_value = gcs_instance

        # DriveAPI: also skipped by making pin_image_urls empty
        # (no GCS, no Drive fallback needed for these tests)

        # Data paths: no result files exist
        mock_data_dir.__truediv__ = lambda self, name: MagicMock(exists=lambda: False)

        sheets_instance = MagicMock()
        MockSheets.return_value = sheets_instance

        slack_instance = MagicMock()
        MockSlack.return_value = slack_instance

        yield {
            "sheets_cls": MockSheets,
            "sheets": sheets_instance,
            "slack_cls": MockSlack,
            "slack": slack_instance,
            "gcs_cls": MockGcs,
            "data_dir": mock_data_dir,
        }


@pytest.fixture
def _no_result_files():
    """Ensure pin/blog result files don't exist during publish()."""
    blog_path = MagicMock()
    blog_path.exists.return_value = False
    pin_path = MagicMock()
    pin_path.exists.return_value = False

    with (
        patch(
            "src.pinterest.publish_content_queue.DATA_DIR",
            new_callable=lambda: type(
                "FakeDir", (), {
                    "__truediv__": lambda self, name: blog_path if "blog" in name else pin_path,
                }
            ),
        ),
    ):
        yield


class TestSheetsWriteSucceeds:
    """When Sheets write succeeds, notify_content_ready() is called."""

    def test_notify_content_ready_called(self, mock_dependencies):
        from src.pinterest.publish_content_queue import publish

        publish()

        slack = mock_dependencies["slack"]
        slack.notify_content_ready.assert_called_once()

    def test_no_failure_notification_sent(self, mock_dependencies):
        from src.pinterest.publish_content_queue import publish

        publish()

        slack = mock_dependencies["slack"]
        # notify() should NOT have been called with "write failed"
        for call in slack.notify.call_args_list:
            args = call[0] if call[0] else ()
            kwargs = call[1] if call[1] else {}
            msg = args[0] if args else kwargs.get("message", "")
            assert "write failed" not in msg.lower()


class TestSheetsWriteFails:
    """When Sheets write fails, a failure message is sent instead."""

    def test_notify_content_ready_not_called(self, mock_dependencies):
        from src.pinterest.publish_content_queue import publish

        mock_dependencies["sheets"].write_content_queue.side_effect = SheetsAPIError(
            "Sheets API down"
        )

        publish()

        slack = mock_dependencies["slack"]
        slack.notify_content_ready.assert_not_called()

    def test_failure_notification_sent(self, mock_dependencies):
        from src.pinterest.publish_content_queue import publish

        mock_dependencies["sheets"].write_content_queue.side_effect = SheetsAPIError(
            "Sheets API down"
        )

        publish()

        slack = mock_dependencies["slack"]
        slack.notify.assert_called()

        # Find the call that mentions "write failed"
        found_failure_msg = False
        for call in slack.notify.call_args_list:
            args = call[0] if call[0] else ()
            msg = args[0] if args else ""
            if "write failed" in msg.lower():
                found_failure_msg = True
                break

        assert found_failure_msg, (
            "Expected Slack notify() to be called with a 'write failed' message"
        )
