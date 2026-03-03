"""
One-time Pinterest board and section setup.

Reads board definitions from strategy/pinterest/board-structure.json and creates all
boards + sections in the Pinterest account. Safe to run multiple times —
skips boards that already exist (matched by name).

Usage:
    python -m src.setup_boards

Or via GitHub Actions: workflow_dispatch on setup-boards.yml.
"""

import json
import logging
import sys
import time

from src.pinterest.apis.pinterest_api import PinterestAPI, PinterestAPIError
from src.pinterest.token_manager import TokenManager
from src.shared.paths import STRATEGY_DIR

logger = logging.getLogger(__name__)

BOARD_STRUCTURE_PATH = STRATEGY_DIR / "pinterest" / "board-structure.json"


def load_board_structure() -> list[dict]:
    with open(BOARD_STRUCTURE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["boards"]


def setup_boards() -> None:
    token = TokenManager().get_valid_token()
    pinterest = PinterestAPI(access_token=token)

    board_definitions = load_board_structure()
    logger.info("Loaded %d board definitions from pinterest/board-structure.json", len(board_definitions))

    # Fetch existing boards to make this idempotent
    existing_boards = pinterest.list_boards()
    existing_by_name = {b["name"]: b["id"] for b in existing_boards}
    logger.info("Found %d existing boards in Pinterest account", len(existing_boards))

    created = 0
    skipped = 0
    errors = []

    for board_def in board_definitions:
        name = board_def["name"]
        description = board_def["description"]
        sections = board_def.get("sections", [])

        if name in existing_by_name:
            logger.info("Board already exists, skipping: '%s'", name)
            board_id = existing_by_name[name]
            skipped += 1
        else:
            try:
                result = pinterest.create_board(
                    name=name,
                    description=description,
                    privacy="PUBLIC",
                )
                board_id = result["id"]
                logger.info("Created board: '%s' (id=%s)", name, board_id)
                created += 1
                # Brief pause between creates to be respectful of rate limits
                time.sleep(1)
            except PinterestAPIError as e:
                logger.error("Failed to create board '%s': %s", name, e)
                errors.append(f"Board '{name}': {e}")
                continue

        # Create sections for this board
        for section_name in sections:
            try:
                pinterest.create_board_section(board_id=board_id, name=section_name)
                logger.info("  Created section: '%s' in '%s'", section_name, name)
                time.sleep(0.5)
            except PinterestAPIError as e:
                # Sections may already exist; log but don't fail hard
                logger.warning("  Could not create section '%s' in '%s': %s", section_name, name, e)

    logger.info(
        "Board setup complete. Created: %d  Skipped (already existed): %d  Errors: %d",
        created, skipped, len(errors),
    )

    if errors:
        for err in errors:
            logger.error("  %s", err)
        sys.exit(1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    setup_boards()
