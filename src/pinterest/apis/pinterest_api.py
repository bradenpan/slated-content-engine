"""
Pinterest v5 API Wrapper

Thin wrapper around Pinterest's v5 REST API for:
- Creating standard image pins (POST /v5/pins)
- Reading and deleting pins (GET/DELETE /v5/pins/{pin_id})
- Managing boards and board sections (CRUD)
- Pulling pin-level and account-level analytics
- Handling rate limits and error responses

Key limitations designed around:
- No native scheduling (GitHub Actions cron handles this)
- Rate limits: ~100 pin creates/hour, ~1000 reads/hour
- Pin descriptions: 500 char max, no clickable links, no HTML
- Analytics data latency: 24-48 hours
- No board-level analytics endpoint (aggregate from pin data)

Supports both sandbox and production base URLs via PINTEREST_ENVIRONMENT env var:
- "sandbox" -> https://api-sandbox.pinterest.com/v5
- "production" (default) -> https://api.pinterest.com/v5

Environment variables required:
- PINTEREST_ACCESS_TOKEN (or obtain via token_manager)
- PINTEREST_ENVIRONMENT (optional, defaults to "production")

See also: token_manager.py for OAuth token refresh.
"""

import os
import time
import base64
import logging
from typing import Optional

import requests

from src.shared.config import (
    PINTEREST_BASE_URL_PRODUCTION as BASE_URL_PRODUCTION,
    PINTEREST_BASE_URL_SANDBOX as BASE_URL_SANDBOX,
)

logger = logging.getLogger(__name__)

# Default metric types for analytics
DEFAULT_METRIC_TYPES = ["IMPRESSION", "SAVE", "PIN_CLICK", "OUTBOUND_CLICK"]

# Rate limit retry settings
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds, exponential backoff


class PinterestAPIError(Exception):
    """Raised when the Pinterest API returns an error response."""

    def __init__(self, status_code: int, message: str, response_body: dict = None):
        self.status_code = status_code
        self.response_body = response_body or {}
        super().__init__(f"Pinterest API error {status_code}: {message}")


class PinterestAPI:
    """Client for Pinterest v5 API."""

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize the Pinterest API client.

        Args:
            access_token: Pinterest OAuth access token. If not provided,
                          reads from PINTEREST_ACCESS_TOKEN env var.
        """
        self.access_token = access_token or os.environ.get("PINTEREST_ACCESS_TOKEN", "")

        if not self.access_token:
            raise PinterestAPIError(
                401,
                "No access token provided. Set PINTEREST_ACCESS_TOKEN env var or pass access_token.",
            )

        env = os.environ.get("PINTEREST_ENVIRONMENT", "production").lower()
        if env == "sandbox":
            self.base_url = BASE_URL_SANDBOX
            logger.info("Using Pinterest SANDBOX API: %s", self.base_url)
        else:
            self.base_url = BASE_URL_PRODUCTION
            logger.info("Using Pinterest PRODUCTION API: %s", self.base_url)

        # Rate limit tracking (updated from response headers)
        self._rate_limit_remaining: Optional[int] = None
        self._rate_limit_limit: Optional[int] = None
        self._rate_limit_reset: Optional[int] = None

    def create_pin(
        self,
        board_id: str,
        title: str,
        description: str,
        link: str,
        image_base64: Optional[str] = None,
        image_url: Optional[str] = None,
        alt_text: Optional[str] = None,
    ) -> dict:
        """
        Create a standard image pin via POST /v5/pins.

        Args:
            board_id: The Pinterest board ID to pin to.
            title: Pin title (max 100 chars, ~40-50 visible in feed).
            description: Pin description (max 500 chars, keyword-rich).
            link: Destination URL (blog post URL with UTM params).
            image_base64: Base64-encoded image data (PNG or JPEG).
            image_url: Public URL of the image (alternative to base64).
            alt_text: Image alt text (max 500 chars, improves impressions ~25%).

        Returns:
            dict: Pinterest API response with pin id and details.

        Raises:
            PinterestAPIError: If the API returns an error.
            ValueError: If neither image_base64 nor image_url is provided.
        """
        if not image_base64 and not image_url:
            raise ValueError("Either image_base64 or image_url must be provided.")

        # Build media_source based on which image source is provided
        if image_url:
            media_source = {
                "source_type": "image_url",
                "url": image_url,
            }
        else:
            # Detect actual image format from magic bytes
            from src.shared.utils.image_utils import detect_mime_type
            raw_bytes = base64.b64decode(image_base64[:24])
            detected = detect_mime_type(raw_bytes)
            content_type = detected if detected != "application/octet-stream" else "image/png"

            media_source = {
                "source_type": "image_base64",
                "content_type": content_type,
                "data": image_base64,
            }

        body = {
            "board_id": board_id,
            "title": title[:100],  # Enforce max length
            "description": description[:500],  # Enforce max length
            "link": link,
            "media_source": media_source,
        }

        if alt_text:
            body["alt_text"] = alt_text[:500]

        logger.info("Creating pin on board %s: %s", board_id, title[:50])
        result = self._make_request("POST", "/pins", data=body)
        logger.info("Pin created successfully: pin_id=%s", result.get("id"))
        return result

    def list_boards(self, page_size: int = 25) -> list[dict]:
        """
        List all boards for the authenticated user via GET /v5/boards.

        Handles pagination to return all boards.

        Args:
            page_size: Number of boards per page (max 250).

        Returns:
            list[dict]: List of board objects with id, name, description, etc.
        """
        logger.info("Listing boards...")
        all_boards = []
        bookmark = None

        while True:
            params = {"page_size": min(page_size, 250)}
            if bookmark:
                params["bookmark"] = bookmark

            result = self._make_request("GET", "/boards", params=params)
            items = result.get("items", [])
            all_boards.extend(items)

            bookmark = result.get("bookmark")
            if not bookmark:
                break

        logger.info("Found %d boards.", len(all_boards))
        return all_boards

    def create_board(
        self,
        name: str,
        description: str,
        privacy: str = "PUBLIC",
    ) -> dict:
        """
        Create a new board via POST /v5/boards.

        Args:
            name: Board name (keyword-rich, e.g., "Quick Weeknight Dinner Recipes").
            description: Board description (2-3 sentences, keyword-rich).
            privacy: "PUBLIC" or "SECRET".

        Returns:
            dict: Created board object with id.
        """
        body = {
            "name": name,
            "description": description,
            "privacy": privacy,
        }

        logger.info("Creating board: %s (privacy=%s)", name, privacy)
        result = self._make_request("POST", "/boards", data=body)
        logger.info("Board created: id=%s name=%s", result.get("id"), name)
        return result

    def create_board_section(self, board_id: str, name: str) -> dict:
        """
        Create a section within a board via POST /v5/boards/{board_id}/sections.

        Args:
            board_id: The board to add the section to.
            name: Section name.

        Returns:
            dict: Created section object.
        """
        body = {"name": name}
        logger.info("Creating section '%s' in board %s", name, board_id)
        result = self._make_request("POST", f"/boards/{board_id}/sections", data=body)
        logger.info("Board section created: id=%s", result.get("id"))
        return result

    def get_pin_analytics(
        self,
        pin_id: str,
        start_date: str,
        end_date: str,
        metric_types: Optional[list[str]] = None,
        granularity: str = "DAY",
    ) -> dict:
        """
        Get analytics for a specific pin via GET /v5/pins/{pin_id}/analytics.

        Args:
            pin_id: The Pinterest pin ID.
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format (max 90-day range).
            metric_types: List of metrics. Defaults to
                          ["IMPRESSION", "SAVE", "PIN_CLICK", "OUTBOUND_CLICK"].
            granularity: "DAY", "WEEK", or "MONTH".

        Returns:
            dict: Analytics data with daily/weekly/monthly breakdowns.
        """
        if metric_types is None:
            metric_types = DEFAULT_METRIC_TYPES

        params = {
            "start_date": start_date,
            "end_date": end_date,
            "metric_types": ",".join(metric_types),
            "granularity": granularity,
        }

        logger.info(
            "Getting pin analytics: pin=%s range=%s to %s granularity=%s",
            pin_id, start_date, end_date, granularity,
        )
        return self._make_request("GET", f"/pins/{pin_id}/analytics", params=params)

    def get_account_analytics(
        self,
        start_date: str,
        end_date: str,
        granularity: str = "DAY",
        metric_types: Optional[list[str]] = None,
    ) -> dict:
        """
        Get account-level analytics via GET /v5/user_account/analytics.

        Args:
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            granularity: "DAY", "WEEK", or "MONTH".
            metric_types: List of metrics. Defaults to standard set.

        Returns:
            dict: Account-level aggregate metrics.
        """
        if metric_types is None:
            metric_types = DEFAULT_METRIC_TYPES

        params = {
            "start_date": start_date,
            "end_date": end_date,
            "metric_types": ",".join(metric_types),
            "granularity": granularity,
        }

        logger.info(
            "Getting account analytics: range=%s to %s granularity=%s",
            start_date, end_date, granularity,
        )
        return self._make_request("GET", "/user_account/analytics", params=params)

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """
        Make an authenticated request to the Pinterest API.

        Handles:
        - Authorization header injection
        - Rate limit detection (via X-RateLimit-* response headers)
        - Error response parsing with descriptive exceptions
        - Retry on transient failures (429 rate limit, 5xx server errors)
        - Exponential backoff

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            endpoint: API endpoint path (e.g., "/pins").
            data: JSON body for POST/PUT requests.
            params: Query parameters for GET requests.

        Returns:
            dict: Parsed JSON response body. Empty dict for DELETE (204).

        Raises:
            PinterestAPIError: On non-retryable errors.
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

        last_exception = None

        for attempt in range(MAX_RETRIES + 1):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data if method in ("POST", "PUT", "PATCH") else None,
                    params=params,
                    timeout=30,
                )

                # Update rate limit tracking from response headers
                self._update_rate_limits(response)

                # Success cases
                if response.status_code in (200, 201):
                    return response.json()

                if response.status_code == 204:
                    # DELETE success, no content
                    return {}

                # Rate limit hit -- sleep and retry
                if response.status_code == 429:
                    retry_after = self._get_retry_after(response, attempt)
                    logger.warning(
                        "Rate limited (429). Retry %d/%d after %.1f seconds.",
                        attempt + 1, MAX_RETRIES, retry_after,
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(retry_after)
                        continue
                    else:
                        raise PinterestAPIError(
                            429,
                            "Rate limit exceeded after all retries.",
                            response.json() if response.text else {},
                        )

                # Server errors -- retry with backoff
                if response.status_code >= 500:
                    wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        "Server error (%d). Retry %d/%d after %.1f seconds.",
                        response.status_code, attempt + 1, MAX_RETRIES, wait_time,
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(wait_time)
                        continue
                    else:
                        raise PinterestAPIError(
                            response.status_code,
                            f"Server error after {MAX_RETRIES} retries",
                            response.json() if response.text else {},
                        )

                # Client errors -- do not retry, raise immediately
                error_body = {}
                error_message = response.text
                try:
                    error_body = response.json()
                    error_message = error_body.get("message", response.text)
                except (ValueError, KeyError):
                    pass

                if response.status_code == 401:
                    raise PinterestAPIError(
                        401,
                        f"Authentication failed. Token may be expired or invalid. {error_message}",
                        error_body,
                    )
                elif response.status_code == 403:
                    raise PinterestAPIError(
                        403,
                        f"Forbidden. Check API access tier or scopes. {error_message}",
                        error_body,
                    )
                elif response.status_code == 404:
                    raise PinterestAPIError(
                        404,
                        f"Resource not found. {error_message}",
                        error_body,
                    )
                else:
                    raise PinterestAPIError(
                        response.status_code,
                        error_message,
                        error_body,
                    )

            except requests.RequestException as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        "Network error: %s. Retry %d/%d after %.1f seconds.",
                        e, attempt + 1, MAX_RETRIES, wait_time,
                    )
                    time.sleep(wait_time)
                    continue
                else:
                    raise PinterestAPIError(
                        0,
                        f"Network error after {MAX_RETRIES} retries: {e}",
                    ) from e

        # Should not reach here, but just in case
        raise PinterestAPIError(
            0,
            f"Request failed after all retries. Last error: {last_exception}",
        )

    @staticmethod
    def _parse_rate_limit_value(header_value: str) -> Optional[int]:
        """Parse a rate limit header, handling structured formats.

        Pinterest may return simple integers ("100") or structured values like:
        '100, 100;w=1;name="safety_net_app_id_user_id", 1000;w=60;name="org_read"'
        Extracts the first numeric value from the header.
        """
        if not header_value:
            return None
        first_token = header_value.split(",")[0].strip()
        numeric_part = first_token.split(";")[0].strip()
        try:
            return int(numeric_part)
        except (ValueError, TypeError):
            logger.warning("Could not parse rate limit header: %s", header_value)
            return None

    def _update_rate_limits(self, response: requests.Response) -> None:
        """Extract and log rate limit info from response headers."""
        limit = response.headers.get("X-RateLimit-Limit")
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")

        parsed = self._parse_rate_limit_value(limit)
        if parsed is not None:
            self._rate_limit_limit = parsed
        parsed = self._parse_rate_limit_value(remaining)
        if parsed is not None:
            self._rate_limit_remaining = parsed
        parsed = self._parse_rate_limit_value(reset)
        if parsed is not None:
            self._rate_limit_reset = parsed

        if self._rate_limit_remaining is not None and self._rate_limit_limit is not None:
            pct_remaining = (self._rate_limit_remaining / self._rate_limit_limit) * 100
            if pct_remaining < 20:
                logger.warning(
                    "Rate limit low: %d/%d remaining (%.0f%%)",
                    self._rate_limit_remaining,
                    self._rate_limit_limit,
                    pct_remaining,
                )
            else:
                logger.debug(
                    "Rate limit: %d/%d remaining",
                    self._rate_limit_remaining,
                    self._rate_limit_limit,
                )

    def _get_retry_after(self, response: requests.Response, attempt: int) -> float:
        """
        Determine how long to wait before retrying after a 429.

        Uses the X-RateLimit-Reset header if available, otherwise
        falls back to exponential backoff.
        """
        reset_timestamp = self._parse_rate_limit_value(
            response.headers.get("X-RateLimit-Reset")
        )
        if reset_timestamp:
            wait_seconds = reset_timestamp - int(time.time())
            if wait_seconds > 0:
                return min(wait_seconds + 1, 120)  # Cap at 2 minutes

        # Fallback: exponential backoff
        return min(RETRY_BACKOFF_BASE ** (attempt + 1), 60)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("Pinterest API smoke test")
    print("========================")

    try:
        api = PinterestAPI()
        boards = api.list_boards()
        print(f"\nFound {len(boards)} boards:")
        for board in boards:
            print(f"  - {board.get('name')} (ID: {board.get('id')})")
    except PinterestAPIError as e:
        print(f"API Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
