"""Centralized configuration for the content pipeline.

All hardcoded values, URL constants, model names, and cost rates live here.
Environment variables are read lazily (same as current behavior).
"""
import os

# --- External URLs ---
BLOG_BASE_URL = "https://goslated.com/blog"
GOSLATED_BASE_URL = "https://goslated.com"

# --- Pinterest ---
PINTEREST_BASE_URL_PRODUCTION = "https://api.pinterest.com/v5"
PINTEREST_BASE_URL_SANDBOX = "https://api-sandbox.pinterest.com/v5"
PINTEREST_OAUTH_URL = "https://api.pinterest.com/v5/oauth/token"
PINTEREST_REDIRECT_URI = "http://localhost:8085/"
PINTEREST_REFRESH_THRESHOLD_DAYS = 5

# --- LLM Models ---
CLAUDE_MODEL_ROUTINE = "claude-sonnet-4-6"
CLAUDE_MODEL_DEEP = "claude-opus-4-6"

# Read from env at import time to allow runtime model override (unlike
# other constants, this intentionally supports per-deployment configuration).
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")

# --- Cost Tracking (approximate, update periodically) ---
CLAUDE_COST_PER_MTK = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
}
IMAGE_COST_PER_IMAGE = {
    "openai": 0.05,
    "replicate": 0.05,
}
GPT5_MINI_COST_PER_MTK = {"input": 0.40, "output": 1.60}

# --- Pin Dimensions ---
PIN_WIDTH = 1000
PIN_HEIGHT = 1500
MAX_PNG_SIZE = 500 * 1024  # 500 KB
MIN_IMAGE_SIZE = 10_000  # 10KB

# --- TikTok Carousel Dimensions ---
TIKTOK_SLIDE_WIDTH = 1080
TIKTOK_SLIDE_HEIGHT = 1920

# --- Timing ---
DEPLOY_VERIFY_TIMEOUT = 180  # seconds
COPY_BATCH_SIZE = 6
MAX_LOOKBACK_DAYS = 90
MAX_PIN_FAILURES = 3
INITIAL_JITTER_MAX = 900  # 0-15 minutes
INTER_PIN_JITTER_MIN = 300  # 5 minutes
INTER_PIN_JITTER_MAX = 1200  # 20 minutes

# --- Publer (TikTok) ---
PUBLER_BASE_URL = "https://app.publer.com/api/v1"

# --- TikTok Posting Timing ---
TIKTOK_JITTER_MAX = 120  # 0-2 minutes (less than Pinterest; posting via Publer, not direct)
TIKTOK_MAX_POST_FAILURES = 3
