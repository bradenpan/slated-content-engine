"""Tests for PublerAPI in src/tiktok/apis/publer_api.py."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.tiktok.apis.publer_api import (
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    PublerAPI,
    PublerAPIError,
)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_constructor_raises_if_no_api_key(monkeypatch):
    monkeypatch.delenv("PUBLER_API_KEY", raising=False)
    monkeypatch.delenv("PUBLER_WORKSPACE_ID", raising=False)
    with pytest.raises(PublerAPIError, match="No API key"):
        PublerAPI(api_key="", workspace_id="ws-123")


def test_constructor_raises_if_no_workspace_id(monkeypatch):
    monkeypatch.delenv("PUBLER_WORKSPACE_ID", raising=False)
    with pytest.raises(PublerAPIError, match="No workspace ID"):
        PublerAPI(api_key="key-abc", workspace_id="")


def test_constructor_accepts_explicit_params(monkeypatch):
    monkeypatch.delenv("PUBLER_API_KEY", raising=False)
    monkeypatch.delenv("PUBLER_WORKSPACE_ID", raising=False)
    api = PublerAPI(api_key="key-abc", workspace_id="ws-123")
    assert api.api_key == "key-abc"
    assert api.workspace_id == "ws-123"
    assert api.base_url == "https://app.publer.com/api/v1"


# ---------------------------------------------------------------------------
# import_media
# ---------------------------------------------------------------------------


def _make_api():
    """Create a PublerAPI instance with dummy credentials."""
    return PublerAPI(api_key="test-key", workspace_id="test-ws")


@patch("src.tiktok.apis.publer_api.requests.request")
def test_import_media_sends_post_and_returns_job_id(mock_req):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"job_id": "j-1234"}
    mock_req.return_value = resp

    api = _make_api()
    job_id = api.import_media(["https://example.com/img1.png"])

    assert job_id == "j-1234"
    call_kwargs = mock_req.call_args
    assert call_kwargs.kwargs["method"] == "POST"
    assert call_kwargs.kwargs["url"].endswith("/media/from-url")
    assert call_kwargs.kwargs["json"] == {"url": ["https://example.com/img1.png"]}


@patch("src.tiktok.apis.publer_api.requests.request")
def test_import_media_raises_if_no_job_id(mock_req):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"status": "ok"}
    mock_req.return_value = resp

    api = _make_api()
    with pytest.raises(PublerAPIError, match="No job_id"):
        api.import_media(["https://example.com/img.png"])


# ---------------------------------------------------------------------------
# poll_job
# ---------------------------------------------------------------------------


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_poll_job_returns_on_complete(mock_req, mock_sleep):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"status": "complete", "media_ids": ["m1"]}
    mock_req.return_value = resp

    api = _make_api()
    result = api.poll_job("j-1")
    assert result["status"] == "complete"
    assert result["media_ids"] == ["m1"]


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_poll_job_raises_on_error_status(mock_req, mock_sleep):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"status": "error", "error": "bad media"}
    mock_req.return_value = resp

    api = _make_api()
    with pytest.raises(PublerAPIError, match="failed"):
        api.poll_job("j-err")


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.time.time")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_poll_job_raises_on_timeout(mock_req, mock_time, mock_sleep):
    # Simulate time advancing past the timeout
    mock_time.side_effect = [0, 0, 50, 100, 200]  # start, first check, ...
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"status": "processing"}
    mock_req.return_value = resp

    api = _make_api()
    with pytest.raises(PublerAPIError, match="timed out"):
        api.poll_job("j-slow", timeout=120)


# ---------------------------------------------------------------------------
# create_post
# ---------------------------------------------------------------------------


@patch("src.tiktok.apis.publer_api.requests.request")
def test_create_post_sends_correct_payload(mock_req):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"job_id": "pj-1"}
    mock_req.return_value = resp

    api = _make_api()
    job_id = api.create_post(
        media_ids=["m1", "m2"],
        caption="Test caption",
        title="Test title",
        scheduled_at="2026-03-10T10:00:00-04:00",
    )

    assert job_id == "pj-1"
    payload = mock_req.call_args.kwargs["json"]
    assert payload["media_ids"] == ["m1", "m2"]
    assert payload["text"] == "Test caption"
    assert payload["title"] == "Test title"
    assert payload["scheduled_at"] == "2026-03-10T10:00:00-04:00"
    assert payload["workspace_id"] == "test-ws"


# ---------------------------------------------------------------------------
# get_post_insights
# ---------------------------------------------------------------------------


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_get_post_insights_paginates_all_pages(mock_req, mock_sleep):
    page0 = MagicMock(status_code=200)
    page0.json.return_value = [{"id": i} for i in range(10)]
    page1 = MagicMock(status_code=200)
    page1.json.return_value = [{"id": i} for i in range(10, 20)]
    page2 = MagicMock(status_code=200)
    page2.json.return_value = [{"id": i} for i in range(20, 25)]  # partial = last

    mock_req.side_effect = [page0, page1, page2]

    api = _make_api()
    results = api.get_post_insights(account_id="acct-1", per_page=10)

    assert len(results) == 25
    assert results[0]["id"] == 0
    assert results[-1]["id"] == 24


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_get_post_insights_stops_on_partial_page(mock_req, mock_sleep):
    page0 = MagicMock(status_code=200)
    page0.json.return_value = [{"id": 1}, {"id": 2}]  # 2 < per_page=10
    mock_req.return_value = page0

    api = _make_api()
    results = api.get_post_insights(account_id="acct-1", per_page=10)

    assert len(results) == 2
    # Only one call — should not paginate further
    assert mock_req.call_count == 1


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_get_post_insights_workspace_level_when_no_account(mock_req, mock_sleep, monkeypatch):
    monkeypatch.delenv("PUBLER_ACCOUNT_ID", raising=False)
    resp = MagicMock(status_code=200)
    resp.json.return_value = []
    mock_req.return_value = resp

    api = _make_api()
    api.get_post_insights(account_id=None)

    url = mock_req.call_args.kwargs["url"]
    assert "/analytics/post_insights" in url
    # Should NOT have an account_id path segment
    assert "/analytics/acct" not in url


# ---------------------------------------------------------------------------
# _make_request
# ---------------------------------------------------------------------------


@patch("src.tiktok.apis.publer_api.requests.request")
def test_make_request_adds_auth_headers(mock_req):
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"ok": True}
    mock_req.return_value = resp

    api = _make_api()
    api._make_request("GET", "/test")

    headers = mock_req.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Content-Type"] == "application/json"


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_make_request_retries_on_429(mock_req, mock_sleep):
    rate_limited = MagicMock(status_code=429, text="")
    rate_limited.json.return_value = {}
    success = MagicMock(status_code=200)
    success.json.return_value = {"data": "ok"}

    mock_req.side_effect = [rate_limited, success]

    api = _make_api()
    result = api._make_request("GET", "/limited")

    assert result == {"data": "ok"}
    assert mock_req.call_count == 2
    mock_sleep.assert_called_once()
    # Exponential backoff: first retry wait = RETRY_BACKOFF_BASE ** (0 + 1) = 2
    assert mock_sleep.call_args[0][0] == RETRY_BACKOFF_BASE ** 1


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_make_request_retries_on_500_with_backoff(mock_req, mock_sleep):
    err500 = MagicMock(status_code=500, text="")
    err500.json.return_value = {}
    success = MagicMock(status_code=200)
    success.json.return_value = {"ok": True}

    mock_req.side_effect = [err500, success]

    api = _make_api()
    result = api._make_request("GET", "/server-error")

    assert result == {"ok": True}
    assert mock_req.call_count == 2
    mock_sleep.assert_called_once()


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_make_request_raises_immediately_on_4xx(mock_req, mock_sleep):
    resp = MagicMock(status_code=403, text="Forbidden")
    resp.json.return_value = {"message": "Forbidden"}
    mock_req.return_value = resp

    api = _make_api()
    with pytest.raises(PublerAPIError) as exc_info:
        api._make_request("GET", "/forbidden")

    assert exc_info.value.status_code == 403
    assert mock_req.call_count == 1
    mock_sleep.assert_not_called()


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_make_request_retries_on_network_errors(mock_req, mock_sleep):
    success = MagicMock(status_code=200)
    success.json.return_value = {"ok": True}
    mock_req.side_effect = [
        requests.ConnectionError("connection reset"),
        success,
    ]

    api = _make_api()
    result = api._make_request("GET", "/flaky")

    assert result == {"ok": True}
    assert mock_req.call_count == 2
    mock_sleep.assert_called_once()


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_make_request_raises_after_all_retries_exhausted_on_429(mock_req, mock_sleep):
    rate_limited = MagicMock(status_code=429, text="")
    rate_limited.json.return_value = {}
    mock_req.return_value = rate_limited

    api = _make_api()
    with pytest.raises(PublerAPIError, match="Rate limit"):
        api._make_request("GET", "/always-limited")

    # initial + MAX_RETRIES retries
    assert mock_req.call_count == MAX_RETRIES + 1


@patch("src.tiktok.apis.publer_api.time.sleep")
@patch("src.tiktok.apis.publer_api.requests.request")
def test_make_request_raises_after_all_retries_exhausted_on_network(mock_req, mock_sleep):
    mock_req.side_effect = requests.ConnectionError("gone")

    api = _make_api()
    with pytest.raises(PublerAPIError, match="Network error"):
        api._make_request("GET", "/down")

    assert mock_req.call_count == MAX_RETRIES + 1
