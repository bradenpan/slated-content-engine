"""
Pinterest API Demo — for Standard Access review video.

This script demonstrates the live Pinterest API integration:
1. Loads OAuth tokens or accepts a sandbox token
2. Verifies account identity
3. Lists existing boards
4. Creates a test board
5. Creates a test pin with an image
6. Retrieves the pin to confirm it exists
7. Cleans up (deletes test pin and board)

Usage:
    # Using OAuth tokens from token store:
    python demo_for_review.py

    # Using a sandbox token (for demo video):
    python demo_for_review.py --sandbox YOUR_SANDBOX_TOKEN

    # Using production token from token store with sandbox API:
    python demo_for_review.py --sandbox-api
"""

import os
import sys
import json
import time
import logging
from pathlib import Path

# Load .env
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

import requests

# Load access token from token store
TOKEN_STORE = Path(__file__).parent / "data" / "token-store.json"

logging.basicConfig(level=logging.WARNING)  # Quiet logs for clean demo output

# A public image URL for the test pin (Unsplash, royalty-free)
TEST_IMAGE_URL = "https://images.unsplash.com/photo-1504674900247-0877df9cc836?w=735&h=1102&fit=crop"

# API base URLs
API_PRODUCTION = "https://api.pinterest.com/v5"
API_SANDBOX = "https://api-sandbox.pinterest.com/v5"


def parse_args():
    """Parse command-line arguments."""
    token = None
    api_base = API_PRODUCTION
    mode = "production"

    args = sys.argv[1:]
    if "--sandbox" in args:
        idx = args.index("--sandbox")
        if idx + 1 < len(args) and not args[idx + 1].startswith("--"):
            token = args[idx + 1]
        api_base = API_SANDBOX
        mode = "sandbox"
    elif "--sandbox-api" in args:
        api_base = API_SANDBOX
        mode = "sandbox"

    return token, api_base, mode


def load_token() -> str:
    """Load access token from the token store."""
    if not TOKEN_STORE.exists():
        print("ERROR: No token store found. Run oauth_setup.py first.")
        sys.exit(1)

    with open(TOKEN_STORE) as f:
        data = json.load(f)

    token = data.get("access_token", "")
    if not token:
        print("ERROR: Token store exists but has no access_token.")
        sys.exit(1)

    return token


# Will be set in main()
ACTIVE_API_BASE = API_PRODUCTION


def api_call(method: str, endpoint: str, token: str, json_body=None, params=None) -> dict:
    """Make a Pinterest v5 API call."""
    url = f"{ACTIVE_API_BASE}{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    resp = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=json_body,
        params=params,
        timeout=30,
    )

    if resp.status_code in (200, 201):
        return resp.json()
    elif resp.status_code == 204:
        return {}
    else:
        print(f"  API ERROR: {resp.status_code} — {resp.text}")
        return {"error": True, "status": resp.status_code, "detail": resp.text}


def pause(msg: str = ""):
    """Brief pause between steps for video readability."""
    if msg:
        print(msg)
    time.sleep(1.5)


def main():
    global ACTIVE_API_BASE

    sandbox_token, api_base, mode = parse_args()
    ACTIVE_API_BASE = api_base

    print()
    print("=" * 64)
    print("  Slated — Pinterest API Integration Demo")
    print("=" * 64)
    print()
    print(f"  Mode: {mode.upper()}")
    print(f"  API:  {ACTIVE_API_BASE}")
    print()

    # --- Step 1: Load token ---
    if sandbox_token:
        print("[1/6] Using provided sandbox token...")
        token = sandbox_token
    else:
        print("[1/6] Loading OAuth tokens from secure store...")
        token = load_token()
    print(f"       Token loaded: {token[:15]}...{token[-4:]}")
    pause()

    # --- Step 2: Verify account ---
    print()
    print("[2/6] Verifying account identity (GET /v5/user_account)...")
    user = api_call("GET", "/user_account", token)
    if user.get("error"):
        print("  Failed to verify account. Token may be expired.")
        sys.exit(1)

    print(f"       Username:      {user.get('username', 'N/A')}")
    print(f"       Account type:  {user.get('account_type', 'N/A')}")
    print(f"       Business name: {user.get('business_name', 'N/A')}")
    print(f"       Profile image: {user.get('profile_image', 'N/A')}")
    pause()

    # --- Step 3: List existing boards ---
    print()
    print("[3/6] Listing existing boards (GET /v5/boards)...")
    boards_resp = api_call("GET", "/boards", token, params={"page_size": 25})
    boards = boards_resp.get("items", [])
    if boards:
        print(f"       Found {len(boards)} board(s):")
        for b in boards:
            print(f"         - \"{b.get('name')}\"  (ID: {b.get('id')})")
    else:
        print("       No existing boards found.")
    pause()

    # --- Step 4: Create a test board ---
    print()
    print("[4/6] Creating test board (POST /v5/boards)...")
    board = api_call("POST", "/boards", token, json_body={
        "name": "API Demo — Weeknight Dinners",
        "description": "Demo board created by the Slated Pinterest automation pipeline to demonstrate API integration.",
        "privacy": "SECRET",
    })
    if board.get("error"):
        print("  Failed to create board.")
        sys.exit(1)

    board_id = board["id"]
    print(f"       Board created: \"{board['name']}\"")
    print(f"       Board ID:      {board_id}")
    print(f"       Privacy:       {board.get('privacy', 'N/A')}")
    pause()

    # --- Step 5: Create a test pin ---
    print()
    print("[5/6] Creating test pin (POST /v5/pins)...")
    print(f"       Image source:  Unsplash (public URL)")
    print(f"       Board:         {board_id}")

    pin = api_call("POST", "/pins", token, json_body={
        "board_id": board_id,
        "title": "30-Minute Weeknight Dinner Ideas",
        "description": (
            "Quick and easy dinner recipes the whole family will love. "
            "Plan your week in minutes with Slated — the family meal planning app. "
            "Save this pin for weeknight inspiration!"
        ),
        "link": "https://goslated.com/",
        "alt_text": "A delicious home-cooked dinner spread on a wooden table",
        "media_source": {
            "source_type": "image_url",
            "url": TEST_IMAGE_URL,
        },
    })

    if pin.get("error"):
        print("  Failed to create pin. Cleaning up board...")
        api_call("DELETE", f"/boards/{board_id}", token)
        sys.exit(1)

    pin_id = pin["id"]
    print(f"       Pin created!")
    print(f"       Pin ID:        {pin_id}")
    print(f"       Title:         {pin.get('title', 'N/A')}")
    print(f"       Link:          {pin.get('link', 'N/A')}")
    pause()

    # --- Step 6: Verify the pin ---
    print()
    print("[6/6] Verifying pin exists (GET /v5/pins/{pin_id})...")
    verified = api_call("GET", f"/pins/{pin_id}", token)
    if verified.get("error"):
        print("  Could not verify pin.")
    else:
        print(f"       Pin verified!")
        print(f"       Title:         {verified.get('title', 'N/A')}")
        print(f"       Board ID:      {verified.get('board_id', 'N/A')}")
        print(f"       Created at:    {verified.get('created_at', 'N/A')}")
        media = verified.get("media", {})
        if media:
            images = media.get("images", {})
            orig = images.get("originals", images.get("original", {}))
            if orig:
                print(f"       Image:         {orig.get('url', 'N/A')[:80]}...")
    pause()

    # --- Cleanup ---
    print()
    print("-" * 64)
    print("  Cleaning up demo resources...")
    print("-" * 64)

    print(f"  Deleting test pin {pin_id}...")
    api_call("DELETE", f"/pins/{pin_id}", token)
    print("  Pin deleted.")

    print(f"  Deleting test board {board_id}...")
    api_call("DELETE", f"/boards/{board_id}", token)
    print("  Board deleted.")

    # --- Done ---
    print()
    print("=" * 64)
    print("  Demo Complete")
    print("=" * 64)
    print()
    print("  This demo showed:")
    print("  1. OAuth token authentication (tokens from oauth_setup.py)")
    print("  2. User account verification via API")
    print("  3. Board listing via API")
    print("  4. Board creation via API")
    print("  5. Pin creation with image via API")
    print("  6. Pin verification via API")
    print("  7. Cleanup (pin + board deletion) via API")
    print()


if __name__ == "__main__":
    main()
