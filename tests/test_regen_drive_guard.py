"""Tests for regen_content.py drive null guard.

Covers fix #15: when drive=None, _regen_item() must not crash with
AttributeError on None.download_image(). The Drive download path
should be skipped gracefully.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock heavy dependencies before importing regen_content
sys.modules.setdefault("anthropic", MagicMock())

from src.pinterest.regen_content import _regen_item


def _make_pin_data(pin_id: str = "W1-01", with_drive_url: bool = True) -> dict:
    """Build a minimal pin_data dict for _regen_item."""
    data = {
        "pin_id": pin_id,
        "title": "Test Pin Title",
        "board_name": "Test Board",
        "pillar": 3,
        "primary_keyword": "test keyword",
        "secondary_keywords": [],
        "template": "recipe-pin",
        "template_variant": 1,
        "content_type": "recipe",
        "funnel_layer": "discovery",
        "text_overlay": {"headline": "Test", "sub_text": "Sub"},
        "description": "Test description",
        "alt_text": "Test alt",
    }
    if with_drive_url:
        data["_drive_image_url"] = "https://drive.google.com/uc?id=abc123&export=download"
        data["hero_image_path"] = "/nonexistent/hero.png"
    return data


class TestDriveNullGuard:
    """drive=None must not cause AttributeError during image download."""

    @patch("src.pinterest.regen_content.source_ai_image")
    @patch("src.pinterest.regen_content.build_template_context", return_value={})
    @patch("src.pinterest.regen_content.generate_copy_batch")
    @patch("src.pinterest.regen_content.extract_drive_file_id", return_value="abc123")
    def test_regen_image_with_drive_none_no_attribute_error(
        self, mock_extract, mock_copy_batch, mock_build_ctx, mock_source_ai
    ):
        """With drive=None and a Drive image URL, no AttributeError should occur."""
        pin_data = _make_pin_data(with_drive_url=True)

        # source_ai_image returns a new image (simulating successful AI image gen)
        mock_source_ai.return_value = (None, "ai", "", {})

        mock_gcs = MagicMock()
        mock_gcs.client = None  # GCS also unavailable

        mock_claude = MagicMock()
        mock_assembler = MagicMock()

        # This should NOT raise AttributeError
        result = _regen_item(
            pin_data=pin_data,
            regen_type="regen_image",
            feedback="try a brighter image",
            claude=mock_claude,
            image_gen_api=MagicMock(),
            assembler=mock_assembler,
            gcs=mock_gcs,
            drive=None,
            used_image_ids=[],
            brand_voice="test voice",
            keyword_targets={},
        )

        assert "pin_data" in result
        assert result["pin_data"]["pin_id"] == "W1-01"

    @patch("src.pinterest.regen_content.source_ai_image")
    @patch("src.pinterest.regen_content.build_template_context", return_value={})
    @patch("src.pinterest.regen_content.generate_copy_batch")
    @patch("src.pinterest.regen_content.extract_drive_file_id", return_value="abc123")
    def test_regen_copy_with_drive_none_skips_rerender(
        self, mock_extract, mock_copy_batch, mock_build_ctx, mock_source_ai
    ):
        """With drive=None and hero not on disk, copy regen should flag no-rerender."""
        pin_data = _make_pin_data(with_drive_url=True)

        mock_copy_batch.return_value = [
            {
                "title": "New Title",
                "description": "New desc",
                "alt_text": "New alt",
                "text_overlay": {"headline": "New", "sub_text": "Sub"},
            }
        ]

        mock_gcs = MagicMock()
        mock_gcs.client = None

        # This should NOT raise
        result = _regen_item(
            pin_data=pin_data,
            regen_type="regen_copy",
            feedback="improve the headline",
            claude=MagicMock(),
            image_gen_api=MagicMock(),
            assembler=MagicMock(),
            gcs=mock_gcs,
            drive=None,
            used_image_ids=[],
            brand_voice="test voice",
            keyword_targets={},
        )

        assert "pin_data" in result
        # Copy was updated but pin could not be re-rendered (no hero image)
        assert result["pin_data"].get("_copy_regen_no_rerender") is True

    @patch("src.pinterest.regen_content.source_ai_image")
    @patch("src.pinterest.regen_content.build_template_context", return_value={})
    @patch("src.pinterest.regen_content.extract_drive_file_id", return_value=None)
    def test_regen_with_no_image_url_and_no_drive(
        self, mock_extract, mock_build_ctx, mock_source_ai
    ):
        """With no image URL at all and drive=None, should handle gracefully."""
        pin_data = _make_pin_data(with_drive_url=False)

        mock_source_ai.return_value = (None, "ai", "", {})

        mock_gcs = MagicMock()
        mock_gcs.client = None

        result = _regen_item(
            pin_data=pin_data,
            regen_type="regen_image",
            feedback="",
            claude=MagicMock(),
            image_gen_api=MagicMock(),
            assembler=MagicMock(),
            gcs=mock_gcs,
            drive=None,
            used_image_ids=[],
            brand_voice="",
            keyword_targets={},
        )

        assert "pin_data" in result
        assert result["image_url"] is None
