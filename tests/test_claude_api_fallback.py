"""Tests for claude_api.py narrowed exception catch on GPT-5 Mini fallback.

Covers fix #17: generate_pin_copy() catches only (OpenAIChatAPIError,
ValueError, requests.HTTPError) from GPT-5 Mini and falls back to Sonnet.
Programming bugs (TypeError, KeyError) must propagate uncaught.
"""

import sys
from unittest.mock import patch, MagicMock

import pytest
import requests

from src.apis.openai_chat_api import OpenAIChatAPIError

# Mock the anthropic module before importing claude_api
sys.modules.setdefault("anthropic", MagicMock())

from src.apis.claude_api import ClaudeAPI


@pytest.fixture
def claude_api():
    """Create a ClaudeAPI instance with mocked internals."""
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-fake"}):
        api = ClaudeAPI()
        return api


# Common test data
PIN_SPECS = [
    {
        "pin_id": "W1-01",
        "pin_topic": "Easy weeknight dinner",
        "target_board": "Board A",
        "pillar": 3,
        "primary_keyword": "easy dinner",
        "secondary_keywords": [],
        "pin_template": "recipe-pin",
        "content_type": "recipe",
        "funnel_layer": "discovery",
    }
]

FALLBACK_RESPONSE = '[{"pin_id": "W1-01", "title": "Fallback Title", "description": "Fallback desc", "alt_text": "alt", "text_overlay": {}}]'


class TestFallbackOnCaughtExceptions:
    """OpenAIChatAPIError and ValueError should trigger Sonnet fallback."""

    @patch("src.shared.apis.claude_api.call_gpt5_mini")
    def test_openai_error_falls_back_to_sonnet(self, mock_gpt5, claude_api):
        mock_gpt5.side_effect = OpenAIChatAPIError("API error")
        claude_api._call_api = MagicMock(return_value=FALLBACK_RESPONSE)

        results = claude_api.generate_pin_copy(
            pin_specs=PIN_SPECS, brand_voice="test voice", keyword_targets={}
        )

        # Sonnet fallback should have been called
        claude_api._call_api.assert_called_once()
        assert len(results) == 1
        assert results[0]["pin_id"] == "W1-01"

    @patch("src.shared.apis.claude_api.call_gpt5_mini")
    def test_value_error_falls_back_to_sonnet(self, mock_gpt5, claude_api):
        mock_gpt5.side_effect = ValueError("bad value")
        claude_api._call_api = MagicMock(return_value=FALLBACK_RESPONSE)

        results = claude_api.generate_pin_copy(
            pin_specs=PIN_SPECS, brand_voice="test voice", keyword_targets={}
        )

        claude_api._call_api.assert_called_once()
        assert len(results) == 1

    @patch("src.shared.apis.claude_api.call_gpt5_mini")
    def test_http_error_falls_back_to_sonnet(self, mock_gpt5, claude_api):
        mock_gpt5.side_effect = requests.HTTPError("500 Server Error")
        claude_api._call_api = MagicMock(return_value=FALLBACK_RESPONSE)

        results = claude_api.generate_pin_copy(
            pin_specs=PIN_SPECS, brand_voice="test voice", keyword_targets={}
        )

        claude_api._call_api.assert_called_once()
        assert len(results) == 1


class TestPropagationOfUncaughtExceptions:
    """TypeError and KeyError (programming bugs) must NOT be caught."""

    @patch("src.shared.apis.claude_api.call_gpt5_mini")
    def test_type_error_propagates(self, mock_gpt5, claude_api):
        mock_gpt5.side_effect = TypeError("unexpected type")
        claude_api._call_api = MagicMock(return_value=FALLBACK_RESPONSE)

        with pytest.raises(TypeError, match="unexpected type"):
            claude_api.generate_pin_copy(
                pin_specs=PIN_SPECS,
                brand_voice="test voice",
                keyword_targets={},
            )

        # Sonnet fallback should NOT have been called
        claude_api._call_api.assert_not_called()

    @patch("src.shared.apis.claude_api.call_gpt5_mini")
    def test_key_error_propagates(self, mock_gpt5, claude_api):
        mock_gpt5.side_effect = KeyError("missing_key")
        claude_api._call_api = MagicMock(return_value=FALLBACK_RESPONSE)

        with pytest.raises(KeyError, match="missing_key"):
            claude_api.generate_pin_copy(
                pin_specs=PIN_SPECS,
                brand_voice="test voice",
                keyword_targets={},
            )

        claude_api._call_api.assert_not_called()
