"""Tests for openai_chat_api.py HTTP error wrapping.

Covers fix #16: raise_for_status() errors are wrapped in OpenAIChatAPIError
instead of propagating as raw requests.HTTPError.
"""

import json
from unittest.mock import patch, MagicMock

import pytest
import requests

from src.apis.openai_chat_api import OpenAIChatAPIError, call_gpt5_mini


def _mock_response(status_code: int, body: dict | None = None) -> MagicMock:
    """Build a mock requests.Response with the given status code and body."""
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.headers = {}

    if status_code >= 400:
        http_error = requests.HTTPError(
            f"{status_code} Server Error", response=resp
        )
        resp.raise_for_status.side_effect = http_error
    else:
        resp.raise_for_status.return_value = None

    if body is not None:
        resp.json.return_value = body
    else:
        resp.json.return_value = {}

    return resp


VALID_RESPONSE_BODY = {
    "choices": [
        {"message": {"content": "Hello from GPT-5 Mini"}}
    ]
}

ENV_PATCH = {"OPENAI_API_KEY": "test-key-fake"}


class TestHTTPErrorWrapping:
    """HTTP errors from requests must be wrapped as OpenAIChatAPIError."""

    @patch.dict("os.environ", ENV_PATCH)
    @patch("src.shared.apis.openai_chat_api.requests.post")
    def test_http_500_raises_openai_error(self, mock_post):
        mock_post.return_value = _mock_response(500)
        with pytest.raises(OpenAIChatAPIError):
            call_gpt5_mini(prompt="test", system="test")

    @patch.dict("os.environ", ENV_PATCH)
    @patch("src.shared.apis.openai_chat_api.requests.post")
    def test_http_400_raises_openai_error(self, mock_post):
        mock_post.return_value = _mock_response(400)
        with pytest.raises(OpenAIChatAPIError):
            call_gpt5_mini(prompt="test", system="test")

    @patch.dict("os.environ", ENV_PATCH)
    @patch("src.shared.apis.openai_chat_api.requests.post")
    def test_http_500_does_not_raise_raw_http_error(self, mock_post):
        mock_post.return_value = _mock_response(500)
        with pytest.raises(OpenAIChatAPIError) as exc_info:
            call_gpt5_mini(prompt="test", system="test")
        # The raised exception must NOT be a raw HTTPError
        assert not isinstance(exc_info.value, requests.HTTPError)

    @patch.dict("os.environ", ENV_PATCH)
    @patch("src.shared.apis.openai_chat_api.requests.post")
    def test_cause_is_original_http_error(self, mock_post):
        mock_post.return_value = _mock_response(500)
        with pytest.raises(OpenAIChatAPIError) as exc_info:
            call_gpt5_mini(prompt="test", system="test")
        # Exception should be chained via `from e`
        assert isinstance(exc_info.value.__cause__, requests.HTTPError)


class TestSuccessfulResponse:
    """Successful API calls should return content without error."""

    @patch.dict("os.environ", ENV_PATCH)
    @patch("src.shared.apis.openai_chat_api.requests.post")
    def test_successful_response_returns_content(self, mock_post):
        mock_post.return_value = _mock_response(200, VALID_RESPONSE_BODY)
        result = call_gpt5_mini(prompt="test", system="test")
        assert result == "Hello from GPT-5 Mini"


class TestMissingAPIKey:
    """Missing OPENAI_API_KEY should raise ValueError."""

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False)
    def test_missing_api_key_raises_value_error(self):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            call_gpt5_mini(prompt="test", system="test")
