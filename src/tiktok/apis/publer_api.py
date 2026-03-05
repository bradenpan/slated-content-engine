"""
Publer REST API Wrapper

Thin wrapper around Publer's v1 REST API for scheduling TikTok carousel posts.

Authentication: static API key via PUBLER_API_KEY env var.
Workspace selection: PUBLER_WORKSPACE_ID header.

Base URL: https://app.publer.com/api/v1

Flow:
1. import_media(image_urls) -> job_id
2. poll_job(job_id) -> {media_ids, ...}
3. create_post(media_ids, caption, ...) -> job_id
4. poll_job(job_id) -> {post_id, ...}

Environment variables required:
- PUBLER_API_KEY
- PUBLER_WORKSPACE_ID
"""

import os
import time
import logging
from typing import Optional

import requests

from src.shared.config import PUBLER_BASE_URL

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds, exponential backoff


class PublerAPIError(Exception):
    """Raised when the Publer API returns an error response."""

    def __init__(self, status_code: int, message: str, response_body: dict = None):
        self.status_code = status_code
        self.response_body = response_body or {}
        super().__init__(f"Publer API error {status_code}: {message}")


class PublerAPI:
    """Client for Publer v1 API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        workspace_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("PUBLER_API_KEY", "")
        self.workspace_id = workspace_id or os.environ.get("PUBLER_WORKSPACE_ID", "")

        if not self.api_key:
            raise PublerAPIError(
                401,
                "No API key provided. Set PUBLER_API_KEY env var.",
            )
        if not self.workspace_id:
            raise PublerAPIError(
                400,
                "No workspace ID provided. Set PUBLER_WORKSPACE_ID env var.",
            )

        self.base_url = PUBLER_BASE_URL
        logger.info("Publer API initialized (workspace=%s)", self.workspace_id)

    def import_media(self, image_urls: list[str]) -> str:
        """Import media from URLs into Publer.

        Args:
            image_urls: List of public image URLs to import.

        Returns:
            str: Job ID to poll for completion.
        """
        logger.info("Importing %d media files via Publer...", len(image_urls))
        result = self._make_request(
            "POST",
            "/media/from-url",
            data={"url": image_urls},
        )
        job_id = result.get("job_id", "")
        if not job_id:
            raise PublerAPIError(0, "No job_id returned from media import", result)
        logger.info("Media import started: job_id=%s", job_id)
        return job_id

    def poll_job(self, job_id: str, timeout: int = 120) -> dict:
        """Poll a Publer job until completion.

        Uses exponential backoff starting at 2s, capped at 10s between polls.

        Args:
            job_id: The job ID to poll.
            timeout: Maximum seconds to wait before raising.

        Returns:
            dict: Job result payload.

        Raises:
            PublerAPIError: If job fails or times out.
        """
        start = time.time()
        poll_interval = 2

        while time.time() - start < timeout:
            result = self._make_request("GET", f"/job_status/{job_id}")
            status = result.get("status", "")

            if status == "complete":
                logger.info("Job %s completed.", job_id)
                return result

            if status == "error":
                raise PublerAPIError(
                    0,
                    f"Job {job_id} failed: {result.get('error', 'unknown')}",
                    result,
                )

            logger.debug("Job %s status=%s, polling in %.1fs...", job_id, status, poll_interval)
            time.sleep(poll_interval)
            poll_interval = min(poll_interval * 1.5, 10)

        raise PublerAPIError(
            0, f"Job {job_id} timed out after {timeout}s"
        )

    def create_post(
        self,
        media_ids: list[str],
        caption: str,
        title: str,
        scheduled_at: str,
        privacy: str = "PUBLIC_TO_EVERYONE",
        is_aigc: bool = False,
    ) -> str:
        """Schedule a TikTok carousel post via Publer.

        Args:
            media_ids: List of Publer media IDs (from import_media).
            caption: Post caption text.
            title: Post title.
            scheduled_at: ISO 8601 datetime for scheduling.
            privacy: TikTok privacy setting.
            is_aigc: Whether to flag as AI-generated content.

        Returns:
            str: Job ID to poll for post creation result.
        """
        logger.info("Creating TikTok post: title='%s', %d slides", title[:50], len(media_ids))
        result = self._make_request(
            "POST",
            "/posts/schedule/publish",
            data={
                "media_ids": media_ids,
                "text": caption,
                "title": title,
                "scheduled_at": scheduled_at,
                "privacy": privacy,
                "is_aigc": is_aigc,
                "workspace_id": self.workspace_id,
            },
        )
        job_id = result.get("job_id", "")
        if not job_id:
            raise PublerAPIError(0, "No job_id returned from create_post", result)
        logger.info("Post creation started: job_id=%s", job_id)
        return job_id

    def get_post_insights(
        self,
        account_id: Optional[str] = None,
        page: int = 0,
        per_page: int = 10,
    ) -> list[dict]:
        """Fetch post-level analytics from Publer.

        Paginates through all available pages and returns a flat list of
        post insight dicts.

        Args:
            account_id: Publer social account ID.  Falls back to
                        PUBLER_ACCOUNT_ID env var.  If neither is set,
                        calls the workspace-level endpoint (all accounts).
            page: Starting page (0-based).
            per_page: Results per page (max 10 per Publer docs).

        Returns:
            list[dict]: Post insight objects with metrics (views, likes,
                        comments, shares, engagement_rate, etc.).
        """
        acct = account_id or os.environ.get("PUBLER_ACCOUNT_ID", "")

        # Build endpoint — account-scoped if we have an ID, workspace-level otherwise
        if acct:
            endpoint = f"/analytics/{acct}/post_insights"
        else:
            endpoint = "/analytics/post_insights"
            logger.info("No PUBLER_ACCOUNT_ID set — using workspace-level post insights")

        all_insights: list[dict] = []
        current_page = page
        max_pages = 100  # Safety guard against infinite pagination

        while current_page - page < max_pages:
            result = self._make_request(
                "GET",
                endpoint,
                params={"page": current_page, "per_page": per_page},
            )

            posts = result if isinstance(result, list) else result.get("posts", [])
            if not posts:
                break

            all_insights.extend(posts)
            logger.debug(
                "Fetched page %d: %d posts (%d total so far)",
                current_page, len(posts), len(all_insights),
            )

            if len(posts) < per_page:
                break
            current_page += 1

            # Rate-limit: small delay between pages
            time.sleep(0.3)

        logger.info("Fetched %d post insights from Publer", len(all_insights))
        return all_insights

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[dict] = None,
        params: Optional[dict] = None,
    ) -> dict:
        """Make an authenticated request to the Publer API.

        Handles retry on 429/5xx with exponential backoff.
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
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

                if response.status_code in (200, 201):
                    return response.json()

                if response.status_code == 204:
                    return {}

                # Rate limit -- retry with backoff
                if response.status_code == 429:
                    wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        "Rate limited (429). Retry %d/%d after %.1fs.",
                        attempt + 1, MAX_RETRIES, wait_time,
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(wait_time)
                        continue
                    error_body = {}
                    try:
                        error_body = response.json() if response.text else {}
                    except (ValueError, KeyError):
                        pass
                    raise PublerAPIError(
                        429,
                        "Rate limit exceeded after all retries.",
                        error_body,
                    )

                # Server errors -- retry with backoff
                if response.status_code >= 500:
                    wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        "Server error (%d). Retry %d/%d after %.1fs.",
                        response.status_code, attempt + 1, MAX_RETRIES, wait_time,
                    )
                    if attempt < MAX_RETRIES:
                        time.sleep(wait_time)
                        continue
                    error_body = {}
                    try:
                        error_body = response.json() if response.text else {}
                    except (ValueError, KeyError):
                        pass
                    raise PublerAPIError(
                        response.status_code,
                        f"Server error after {MAX_RETRIES} retries",
                        error_body,
                    )

                # Client errors -- raise immediately
                error_body = {}
                error_message = response.text
                try:
                    error_body = response.json()
                    error_message = error_body.get("message", response.text)
                except (ValueError, KeyError):
                    pass

                raise PublerAPIError(
                    response.status_code,
                    error_message,
                    error_body,
                )

            except requests.RequestException as e:
                last_exception = e
                if attempt < MAX_RETRIES:
                    wait_time = RETRY_BACKOFF_BASE ** (attempt + 1)
                    logger.warning(
                        "Network error: %s. Retry %d/%d after %.1fs.",
                        e, attempt + 1, MAX_RETRIES, wait_time,
                    )
                    time.sleep(wait_time)
                    continue
                raise PublerAPIError(
                    0,
                    f"Network error after {MAX_RETRIES} retries: {e}",
                ) from e

        raise PublerAPIError(
            0, f"Request failed after all retries. Last error: {last_exception}"
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("Publer API smoke test")
    print("=====================")

    try:
        api = PublerAPI()
        # Simple auth check -- list recent posts
        result = api._make_request("GET", "/posts", params={"workspace_id": api.workspace_id})
        posts = result if isinstance(result, list) else result.get("posts", [])
        print(f"Connection OK. Found {len(posts)} recent posts.")
    except PublerAPIError as e:
        print(f"API Error: {e}")
    except Exception as e:
        print(f"Error: {e}")
