"""Shared strategy file loading utilities."""
import logging
from pathlib import Path

from src.shared.paths import STRATEGY_DIR

logger = logging.getLogger(__name__)


def load_brand_voice(strategy_dir: Path = None) -> str:
    """Load brand-voice.md content.

    Args:
        strategy_dir: Directory containing brand-voice.md. Defaults to STRATEGY_DIR.

    Returns:
        str: Brand voice content, or empty string if not found.
    """
    d = strategy_dir or STRATEGY_DIR
    path = d / "brand-voice.md"
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("brand-voice.md not found")
        return ""
