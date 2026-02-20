"""
Pinterest OAuth Setup — One-time interactive script.

Run this once to obtain your initial access_token + refresh_token pair.
After that, token_manager.py handles automatic refresh.

Usage:
    cd C:\\dev\\pinterest-pipeline
    python oauth_setup.py

Prerequisites:
    1. Copy .env.example to .env
    2. Fill in PINTEREST_APP_ID and PINTEREST_APP_SECRET from
       https://developers.pinterest.com/apps/
    3. In the Pinterest developer dashboard, set your app's
       Redirect URI to:  http://localhost:8085/
"""

import os
import sys
import json
import time
import webbrowser
import urllib.parse
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Load .env file manually (avoid import issues if dotenv isn't installed yet)
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if value:
                os.environ.setdefault(key, value)

# Now import project modules
from src.token_manager import TokenManager, TokenManagerError

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Configuration ---
REDIRECT_URI = "http://localhost:8085/"
CALLBACK_PORT = 8085
SCOPES = "boards:read,boards:write,pins:read,pins:write,user_accounts:read"
PINTEREST_AUTH_BASE = "https://www.pinterest.com/oauth/"

# Global to capture the auth code from the callback
captured_code = None
server_error = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Tiny HTTP handler that captures the OAuth authorization code."""

    def do_GET(self):
        global captured_code, server_error

        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            captured_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html><body style="font-family: system-ui, sans-serif; max-width: 500px; margin: 80px auto; text-align: center;">
                <h1 style="color: #059669;">Authorization Successful</h1>
                <p>You can close this browser tab and return to your terminal.</p>
                <p style="color: #888; font-size: 14px;">The authorization code has been captured.</p>
            </body></html>
            """)
        elif "error" in params:
            server_error = params.get("error_description", params["error"])[0]
            self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            error_msg = f"Error: {server_error}"
            self.wfile.write(f"""
            <html><body style="font-family: system-ui, sans-serif; max-width: 500px; margin: 80px auto; text-align: center;">
                <h1 style="color: #DC2626;">Authorization Failed</h1>
                <p>{error_msg}</p>
                <p>Return to your terminal to see details.</p>
            </body></html>
            """.encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"""
            <html><body style="font-family: system-ui, sans-serif; max-width: 500px; margin: 80px auto; text-align: center;">
                <h1>Waiting for Pinterest redirect...</h1>
                <p>If you see this, the redirect happened but no code was included.</p>
            </body></html>
            """)

    def log_message(self, format, *args):
        # Suppress default request logging
        pass


def build_auth_url(app_id: str) -> str:
    """Construct the Pinterest OAuth authorization URL."""
    params = {
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
    }
    return f"{PINTEREST_AUTH_BASE}?{urllib.parse.urlencode(params)}"


def wait_for_callback(timeout: int = 120) -> str:
    """Start a local HTTP server and wait for the OAuth callback."""
    global captured_code, server_error
    captured_code = None
    server_error = None

    server = HTTPServer(("127.0.0.1", CALLBACK_PORT), OAuthCallbackHandler)
    server.timeout = 1  # Check every second for shutdown

    deadline = time.time() + timeout
    while time.time() < deadline:
        server.handle_request()
        if captured_code or server_error:
            break

    server.server_close()

    if server_error:
        raise TokenManagerError(f"Pinterest denied authorization: {server_error}")

    if not captured_code:
        raise TokenManagerError(
            f"Timed out after {timeout}s waiting for OAuth callback. "
            "Make sure you complete the authorization in your browser."
        )

    return captured_code


def test_token(access_token: str) -> dict:
    """Verify the token works by calling the user account endpoint."""
    import requests

    resp = requests.get(
        "https://api.pinterest.com/v5/user_account",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise TokenManagerError(
            f"Token verification failed (HTTP {resp.status_code}): {resp.text}"
        )
    return resp.json()


def main():
    print()
    print("=" * 60)
    print("  Pinterest OAuth Setup")
    print("=" * 60)
    print()

    # --- Step 1: Check credentials ---
    app_id = os.environ.get("PINTEREST_APP_ID", "")
    app_secret = os.environ.get("PINTEREST_APP_SECRET", "")

    if not app_id or not app_secret:
        print("ERROR: PINTEREST_APP_ID and PINTEREST_APP_SECRET not found.")
        print()
        print("Fix this by creating a .env file:")
        print(f"  1. Copy .env.example to .env  (in {Path(__file__).parent})")
        print("  2. Fill in PINTEREST_APP_ID and PINTEREST_APP_SECRET")
        print("     from https://developers.pinterest.com/apps/")
        print("  3. Run this script again.")
        sys.exit(1)

    print(f"  App ID:     {app_id}")
    print(f"  App Secret: {app_secret[:6]}...{app_secret[-4:]}")
    print()

    # --- Step 2: Remind about redirect URI ---
    print("-" * 60)
    print("  IMPORTANT: Redirect URI")
    print("-" * 60)
    print()
    print(f"  Your Pinterest app's Redirect URI MUST be set to:")
    print(f"    {REDIRECT_URI}")
    print()
    print("  Set this at: https://developers.pinterest.com/apps/")
    print("  Click your app > scroll to 'Redirect URIs' > add the URI above")
    print()

    if sys.stdin.isatty() and "--no-prompt" not in sys.argv:
        input("  Press ENTER when your Redirect URI is set (or Ctrl+C to cancel)... ")
    print()

    # --- Step 3: Build auth URL and open browser ---
    auth_url = build_auth_url(app_id)

    print("-" * 60)
    print("  Step 1: Authorize in your browser")
    print("-" * 60)
    print()
    print("  Opening your browser to Pinterest's authorization page...")
    print()
    print("  If the browser doesn't open, manually go to this URL:")
    print()
    print(f"  {auth_url}")
    print()

    webbrowser.open(auth_url)

    # --- Step 4: Wait for the callback ---
    print("-" * 60)
    print("  Step 2: Waiting for authorization callback...")
    print("-" * 60)
    print()
    print(f"  Listening on http://127.0.0.1:{CALLBACK_PORT}/")
    print("  Complete the authorization in your browser. This will time out in 2 minutes.")
    print()

    try:
        auth_code = wait_for_callback(timeout=120)
    except TokenManagerError as e:
        print(f"  FAILED: {e}")
        sys.exit(1)

    print(f"  Authorization code received: {auth_code[:12]}...")
    print()

    # --- Step 5: Exchange code for tokens ---
    print("-" * 60)
    print("  Step 3: Exchanging code for tokens...")
    print("-" * 60)
    print()

    try:
        manager = TokenManager()
        token_data = manager.initial_auth(auth_code)
    except TokenManagerError as e:
        print(f"  FAILED: {e}")
        print()
        print("  Common causes:")
        print("  - Authorization code expired (they're single-use and short-lived)")
        print("  - Redirect URI mismatch between dashboard and this script")
        print("  - App ID/Secret mismatch")
        print()
        print("  Run this script again to retry.")
        sys.exit(1)

    print("  Tokens obtained successfully!")
    print()
    print(f"  Access token:         {token_data['access_token'][:20]}...")
    print(f"  Refresh token:        {token_data['refresh_token'][:20]}...")
    print(f"  Access token expires:  {token_data['expires_in'] // 86400} days")
    print(f"  Refresh token expires: {token_data['refresh_token_expires_in'] // 86400} days")
    print()
    token_store = Path(__file__).parent / "data" / "token-store.json"
    print(f"  Saved to: {token_store}")
    print()

    # --- Step 6: Verify the token ---
    print("-" * 60)
    print("  Step 4: Verifying token with a test API call...")
    print("-" * 60)
    print()

    try:
        user_info = test_token(token_data["access_token"])
        print("  Token verified! Connected account:")
        print(f"    Username:  {user_info.get('username', 'N/A')}")
        print(f"    Account type: {user_info.get('account_type', 'N/A')}")
        if user_info.get("business_name"):
            print(f"    Business name: {user_info['business_name']}")
        print()
    except Exception as e:
        print(f"  WARNING: Token verification failed: {e}")
        print("  The tokens were saved but may not be valid yet.")
        print("  This can happen in sandbox mode -- the token may still work for pin operations.")
        print()

    # --- Done ---
    print("=" * 60)
    print("  Setup Complete!")
    print("=" * 60)
    print()
    print("  Your tokens are stored and will auto-refresh before expiry.")
    print("  The pipeline's token_manager.py handles this automatically.")
    print()
    print("  Next steps:")
    print("  1. Test pin creation (sandbox pins are only visible to you):")
    print("       python -c \"from src.apis.pinterest_api import PinterestAPI; api = PinterestAPI(); print(api.get_boards())\"")
    print("  2. Apply for Standard access (for public pins):")
    print("       https://developers.pinterest.com/apps/  > your app > 'Request Standard access'")
    print()


if __name__ == "__main__":
    main()
