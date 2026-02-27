"""Shared weekly plan loading utilities."""
import json
import logging
from pathlib import Path

from src.paths import DATA_DIR

logger = logging.getLogger(__name__)


def find_latest_plan(data_dir: Path = None) -> Path | None:
    """Find the most recent weekly-plan-*.json file.

    Args:
        data_dir: Directory to search. Defaults to DATA_DIR.

    Returns:
        Path to the latest plan file, or None if no plans exist.
    """
    d = data_dir or DATA_DIR
    plans = sorted(d.glob("weekly-plan-*.json"), reverse=True)
    return plans[0] if plans else None


def load_plan(path: Path) -> dict:
    """Load and parse a weekly plan JSON file.

    Args:
        path: Path to the plan JSON file.

    Returns:
        dict: The weekly plan data.
    """
    return json.loads(path.read_text(encoding="utf-8"))
