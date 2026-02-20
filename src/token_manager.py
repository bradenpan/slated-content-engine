"""
Pinterest OAuth Token Manager

Handles Pinterest OAuth 2.0 token lifecycle:
- Access token: 30-day lifetime
- Refresh token: 60-day lifetime with continuous refresh (clock resets on each refresh)

IMPORTANT: Pinterest deprecated legacy 365-day refresh tokens in May 2025.
New apps use continuous_refresh=true, which gives 60-day refresh tokens that
renew indefinitely as long as you refresh before expiry.

Auto-refresh logic (runs before every workflow):
1. Read token from secure store (data/token-store.json or env vars)
2. Check if access token expires within 5 days
3. If yes: call POST /v5/oauth/token with grant_type=refresh_token
4. Store new access_token + refresh_token (both change on refresh)
5. Proceed with workflow

As long as the system runs at least once every 60 days, the refresh token
chain never breaks. The weekly workflows ensure this happens dozens of
times per month.

Initial OAuth authorization code flow must be run manually once to
obtain the first access_token + refresh_token pair.

Environment variables required:
- PINTEREST_APP_ID
- PINTEREST_APP_SECRET
- PINTEREST_ACCESS_TOKEN (or read from token store)
- PINTEREST_REFRESH_TOKEN (or read from token store)

Required OAuth scopes:
- boards:read, boards:write
- pins:read, pins:write
- user_accounts:read
"""

import os
import json
import time
import base64
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

TOKEN_STORE_PATH = Path(__file__).parent.parent / "data" / "token-store.json"
PINTEREST_OAUTH_URL = "https://api.pinterest.com/v5/oauth/token"
REDIRECT_URI = "http://localhost:8085/"
REFRESH_THRESHOLD_DAYS = 5
REFRESH_THRESHOLD_SECONDS = REFRESH_THRESHOLD_DAYS * 24 * 60 * 60


class TokenManagerError(Exception):
    """Raised when token operations fail."""
    pass


class TokenManager:
    """Manages Pinterest OAuth token refresh with 60-day continuous refresh tokens."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None,
        token_store_path: Optional[Path] = None,
    ):
        """
        Initialize the token manager.

        Args:
            app_id: Pinterest app ID. Falls back to PINTEREST_APP_ID env var.
            app_secret: Pinterest app secret. Falls back to PINTEREST_APP_SECRET env var.
            token_store_path: Path to token store JSON. Defaults to data/token-store.json.
        """
        self.app_id = app_id or os.environ.get("PINTEREST_APP_ID", "")
        self.app_secret = app_secret or os.environ.get("PINTEREST_APP_SECRET", "")
        self.token_store_path = token_store_path or TOKEN_STORE_PATH

        if not self.app_id or not self.app_secret:
            raise TokenManagerError(
                "PINTEREST_APP_ID and PINTEREST_APP_SECRET are required. "
                "Set them as environment variables or pass them to the constructor."
            )

        self._token_data: Optional[dict] = None
        self._slack_notifier = None

    def _get_basic_auth_header(self) -> str:
        """Build the Base64-encoded Basic auth header value."""
        credentials = f"{self.app_id}:{self.app_secret}"
        b64 = base64.b64encode(credentials.encode("ascii")).decode("ascii")
        return f"Basic {b64}"

    def _get_slack_notifier(self):
        """Lazy-load Slack notifier to avoid circular imports."""
        if self._slack_notifier is None:
            try:
                from src.apis.slack_notify import SlackNotify
                self._slack_notifier = SlackNotify()
            except Exception:
                logger.warning("Could not initialize Slack notifier for token alerts")
                self._slack_notifier = False  # Sentinel to avoid retrying
        return self._slack_notifier if self._slack_notifier is not False else None

    def get_valid_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        This is the main entry point -- call this before every API operation.

        Returns:
            str: A valid Pinterest access token.

        Raises:
            TokenManagerError: If token refresh fails.
        """
        token_data = self._load_tokens()

        if not token_data.get("access_token"):
            raise TokenManagerError(
                "No access token found. Run initial_auth() first to obtain tokens."
            )

        if self.needs_refresh():
            logger.info("Access token expiring within %d days, refreshing...", REFRESH_THRESHOLD_DAYS)
            new_data = self.refresh_token()
            return new_data["access_token"]

        logger.debug("Access token is still valid, no refresh needed.")
        return token_data["access_token"]

    def needs_refresh(self) -> bool:
        """
        Check if the access token expires within REFRESH_THRESHOLD_DAYS.

        Returns:
            bool: True if token should be refreshed.
        """
        token_data = self._load_tokens()
        expires_at = token_data.get("expires_at", 0)

        if expires_at == 0:
            # No expiry info -- assume we need to refresh to be safe
            logger.warning("No expires_at in token store, forcing refresh.")
            return True

        seconds_remaining = expires_at - int(time.time())
        days_remaining = seconds_remaining / 86400

        logger.info(
            "Access token expires in %.1f days (threshold: %d days)",
            days_remaining,
            REFRESH_THRESHOLD_DAYS,
        )

        return seconds_remaining < REFRESH_THRESHOLD_SECONDS

    def refresh_token(self) -> dict:
        """
        Refresh the access token using the refresh token.

        Calls POST /v5/oauth/token with grant_type=refresh_token.
        Both the access token AND refresh token change on each refresh.

        Returns:
            dict: New token data (access_token, refresh_token, expires_at, etc.).

        Raises:
            TokenManagerError: If refresh fails.
        """
        token_data = self._load_tokens()
        current_refresh_token = token_data.get("refresh_token")

        if not current_refresh_token:
            raise TokenManagerError(
                "No refresh token found. Run initial_auth() to obtain tokens."
            )

        # Check if the refresh token itself has expired
        refresh_expires_at = token_data.get("refresh_token_expires_at", 0)
        if refresh_expires_at and int(time.time()) > refresh_expires_at:
            msg = (
                "Refresh token has expired (60-day limit exceeded). "
                "You must re-run the manual OAuth authorization flow."
            )
            logger.error(msg)
            notifier = self._get_slack_notifier()
            if notifier:
                try:
                    notifier.notify_failure("token_refresh", msg)
                except Exception:
                    logger.warning("Failed to send Slack alert for expired refresh token")
            raise TokenManagerError(msg)

        logger.info("Refreshing Pinterest access token...")

        try:
            response = requests.post(
                PINTEREST_OAUTH_URL,
                headers={
                    "Authorization": self._get_basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": current_refresh_token,
                },
                timeout=30,
            )
        except requests.RequestException as e:
            msg = f"Network error during token refresh: {e}"
            logger.error(msg)
            raise TokenManagerError(msg) from e

        if response.status_code != 200:
            error_detail = response.text
            msg = f"Token refresh failed (HTTP {response.status_code}): {error_detail}"
            logger.error(msg)

            notifier = self._get_slack_notifier()
            if notifier:
                try:
                    notifier.notify_failure("token_refresh", msg)
                except Exception:
                    logger.warning("Failed to send Slack alert for token refresh failure")

            raise TokenManagerError(msg)

        resp_data = response.json()
        now = datetime.now(timezone.utc)

        new_token_data = {
            "access_token": resp_data["access_token"],
            "refresh_token": resp_data["refresh_token"],
            "token_type": resp_data.get("token_type", "bearer"),
            "scope": resp_data.get("scope", ""),
            "expires_in": resp_data["expires_in"],
            "expires_at": int((now + timedelta(seconds=resp_data["expires_in"])).timestamp()),
            "refresh_token_expires_in": resp_data.get("refresh_token_expires_in", 5184000),
            "refresh_token_expires_at": int(
                (now + timedelta(seconds=resp_data.get("refresh_token_expires_in", 5184000))).timestamp()
            ),
            "obtained_at": token_data.get("obtained_at", now.isoformat()),
            "refreshed_at": now.isoformat(),
        }

        self._save_tokens(new_token_data)

        logger.info(
            "Token refreshed successfully. New access token expires at %s. "
            "New refresh token expires at %s.",
            datetime.fromtimestamp(new_token_data["expires_at"], tz=timezone.utc).isoformat(),
            datetime.fromtimestamp(new_token_data["refresh_token_expires_at"], tz=timezone.utc).isoformat(),
        )

        return new_token_data

    def initial_auth(self, authorization_code: str) -> dict:
        """
        Exchange an authorization code for initial tokens.

        This is run manually once during setup. Must include
        continuous_refresh=true for 60-day refresh tokens.

        Args:
            authorization_code: The code from the OAuth redirect callback.

        Returns:
            dict: Token data (access_token, refresh_token, expires_in, etc.).

        Raises:
            TokenManagerError: If the exchange fails.
        """
        logger.info("Exchanging authorization code for initial tokens...")

        try:
            response = requests.post(
                PINTEREST_OAUTH_URL,
                headers={
                    "Authorization": self._get_basic_auth_header(),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": authorization_code,
                    "redirect_uri": REDIRECT_URI,
                    "continuous_refresh": "true",
                },
                timeout=30,
            )
        except requests.RequestException as e:
            raise TokenManagerError(f"Network error during auth code exchange: {e}") from e

        if response.status_code != 200:
            raise TokenManagerError(
                f"Auth code exchange failed (HTTP {response.status_code}): {response.text}"
            )

        resp_data = response.json()
        now = datetime.now(timezone.utc)

        token_data = {
            "access_token": resp_data["access_token"],
            "refresh_token": resp_data["refresh_token"],
            "token_type": resp_data.get("token_type", "bearer"),
            "scope": resp_data.get("scope", ""),
            "expires_in": resp_data["expires_in"],
            "expires_at": int((now + timedelta(seconds=resp_data["expires_in"])).timestamp()),
            "refresh_token_expires_in": resp_data.get("refresh_token_expires_in", 5184000),
            "refresh_token_expires_at": int(
                (now + timedelta(seconds=resp_data.get("refresh_token_expires_in", 5184000))).timestamp()
            ),
            "obtained_at": now.isoformat(),
            "refreshed_at": now.isoformat(),
        }

        self._save_tokens(token_data)

        logger.info(
            "Initial tokens obtained successfully. Access token expires in %d days. "
            "Refresh token expires in %d days (continuous refresh -- clock resets on each refresh).",
            resp_data["expires_in"] // 86400,
            resp_data.get("refresh_token_expires_in", 5184000) // 86400,
        )

        return token_data

    def _load_tokens(self) -> dict:
        """
        Load tokens from the token store file or environment variables.

        Priority: token store file > environment variables.
        This allows GitHub Actions to bootstrap from env vars on first run,
        then use the token store file for subsequent runs.

        Returns:
            dict: Token data with access_token, refresh_token, expires_at.
        """
        if self._token_data is not None:
            return self._token_data

        # Try loading from file first
        if self.token_store_path.exists():
            try:
                with open(self.token_store_path, "r") as f:
                    self._token_data = json.load(f)
                logger.debug("Loaded tokens from %s", self.token_store_path)
                return self._token_data
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read token store file: %s", e)

        # Fall back to environment variables
        access_token = os.environ.get("PINTEREST_ACCESS_TOKEN", "")
        refresh_token = os.environ.get("PINTEREST_REFRESH_TOKEN", "")

        if access_token or refresh_token:
            self._token_data = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": 0,  # Unknown -- will trigger refresh
                "refresh_token_expires_at": 0,
            }
            logger.info("Loaded tokens from environment variables (expiry unknown, will check).")
            return self._token_data

        self._token_data = {}
        return self._token_data

    def _save_tokens(self, token_data: dict) -> None:
        """
        Save tokens to the token store file.

        Args:
            token_data: Token data to save.
        """
        self._token_data = token_data

        # Ensure the data directory exists
        self.token_store_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.token_store_path, "w") as f:
                json.dump(token_data, f, indent=2)
            logger.info("Tokens saved to %s", self.token_store_path)
        except OSError as e:
            logger.error("Failed to save tokens to file: %s", e)
            # Don't raise -- the in-memory token data is still valid for this run


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        # Manual initial auth: python -m src.token_manager auth <AUTH_CODE>
        if len(sys.argv) < 3:
            print("Usage: python -m src.token_manager auth <AUTHORIZATION_CODE>")
            sys.exit(1)
        manager = TokenManager()
        result = manager.initial_auth(sys.argv[2])
        print("Initial auth successful!")
        print(f"  Access token: {result['access_token'][:20]}...")
        print(f"  Refresh token: {result['refresh_token'][:20]}...")
        print(f"  Access token expires: {datetime.fromtimestamp(result['expires_at'], tz=timezone.utc).isoformat()}")
        print(f"  Refresh token expires: {datetime.fromtimestamp(result['refresh_token_expires_at'], tz=timezone.utc).isoformat()}")
    else:
        # Normal mode: check and refresh if needed
        manager = TokenManager()
        if manager.needs_refresh():
            print("Token needs refresh, refreshing...")
            manager.refresh_token()
            print("Token refreshed successfully.")
        else:
            print("Token is still valid, no refresh needed.")
        token = manager.get_valid_token()
        print(f"Valid token: {token[:20]}...")
