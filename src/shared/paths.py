"""Canonical path constants for the content pipeline.

All modules import paths from here instead of computing Path(__file__).parent.parent.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STRATEGY_DIR = PROJECT_ROOT / "strategy"
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
PIN_OUTPUT_DIR = DATA_DIR / "generated" / "pins"
TIKTOK_OUTPUT_DIR = DATA_DIR / "generated" / "tiktok"
BLOG_OUTPUT_DIR = DATA_DIR / "generated" / "blog"
TIKTOK_DATA_DIR = DATA_DIR / "tiktok"
CONTENT_LOG_PATH = DATA_DIR / "content-log.jsonl"
