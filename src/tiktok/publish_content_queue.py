"""Publish rendered TikTok carousels to the Google Sheet Content Queue tab.

Thin orchestration layer — delegates the actual write to
SheetsAPI.write_tiktok_content_queue(), which owns the column schema,
header validation, and write logic.
"""

import logging
import os
from typing import Optional

from src.shared.apis.sheets_api import SheetsAPI

logger = logging.getLogger(__name__)


def publish_content_queue(
    carousels: list[dict],
    slide_urls: dict[str, str] = None,
    sheets: Optional[SheetsAPI] = None,
) -> None:
    """Write rendered carousels to the TikTok Google Sheet Content Queue.

    Args:
        carousels: List of enriched carousel dicts from generate_carousels().
        slide_urls: Optional dict of carousel_id -> public GCS URL for the
            first slide (used for =IMAGE() preview formula).
        sheets: SheetsAPI instance pointing to the TikTok spreadsheet.
            Created from TIKTOK_SPREADSHEET_ID env var if not provided.
    """
    if sheets is None:
        tiktok_sheet_id = os.environ.get("TIKTOK_SPREADSHEET_ID", "")
        if not tiktok_sheet_id:
            raise ValueError(
                "TIKTOK_SPREADSHEET_ID env var not set. "
                "Cannot publish to TikTok Google Sheet."
            )
        sheets = SheetsAPI(sheet_id=tiktok_sheet_id)

    logger.info("Publishing %d carousels to TikTok Content Queue...", len(carousels))
    sheets.write_tiktok_content_queue(carousels, slide_urls=slide_urls or {})
    logger.info("TikTok Content Queue published: %d carousels.", len(carousels))
