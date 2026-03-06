"""Tests for generate_carousels(), build_slides_for_render(), _generate_slide_images()
in src/tiktok/generate_carousels.py."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from src.tiktok.generate_carousels import (
    generate_carousels,
    build_slides_for_render,
    _generate_slide_images,
    _taxonomy_to_assembler_family,
)


_MODULE = "src.tiktok.generate_carousels"


def _carousel_spec(**overrides):
    """Build a minimal carousel spec dict."""
    base = {
        "carousel_id": "T01",
        "template_family": "clean_educational",
        "hook_text": "Test hook",
        "content_slides": [
            {"headline": "Slide 1", "body_text": "Body 1"},
            {"headline": "Slide 2", "body_text": "Body 2"},
        ],
        "cta_slide": {"cta_primary": "Follow @slatedapp", "cta_secondary": "Save this!"},
        "image_prompts": [],
    }
    base.update(overrides)
    return base


def _plan_with(specs):
    """Wrap carousel specs in a plan dict."""
    return {"carousels": specs}


# --- build_slides_for_render ---

class TestBuildSlidesForRender:

    def test_produces_hook_content_and_cta_slides(self):
        """Should produce hook + N content + CTA slides."""
        spec = _carousel_spec()
        slides = build_slides_for_render(spec)
        assert len(slides) == 4  # 1 hook + 2 content + 1 CTA
        assert slides[0]["slide_type"] == "hook"
        assert slides[0]["headline"] == "Test hook"
        assert slides[1]["slide_type"] == "content"
        assert slides[2]["slide_type"] == "content"
        assert slides[3]["slide_type"] == "cta"
        assert slides[3]["cta_primary"] == "Follow @slatedapp"

    def test_no_content_slides_produces_hook_and_cta(self):
        """With empty content_slides, output is hook + CTA only."""
        spec = _carousel_spec(content_slides=[])
        slides = build_slides_for_render(spec)
        assert len(slides) == 2
        assert slides[0]["slide_type"] == "hook"
        assert slides[1]["slide_type"] == "cta"

    def test_injects_background_image_url_from_image_paths(self):
        """image_paths_by_index values should appear as background_image_url."""
        spec = _carousel_spec()
        image_paths = {
            0: Path("/tmp/hook-bg.png"),
            2: Path("/tmp/content2-bg.png"),
        }
        slides = build_slides_for_render(spec, image_paths_by_index=image_paths)
        assert slides[0]["background_image_url"] == str(Path("/tmp/hook-bg.png"))
        # Slide index 1 = first content slide, no image
        assert "background_image_url" not in slides[1]
        # Slide index 2 = second content slide
        assert slides[2]["background_image_url"] == str(Path("/tmp/content2-bg.png"))

    def test_handles_non_list_content_slides_gracefully(self):
        """Non-list content_slides should be treated as empty."""
        spec = _carousel_spec(content_slides="not a list")
        slides = build_slides_for_render(spec)
        assert len(slides) == 2  # hook + CTA only
        assert slides[0]["slide_type"] == "hook"
        assert slides[1]["slide_type"] == "cta"


# --- _taxonomy_to_assembler_family ---

class TestTaxonomyToAssemblerFamily:

    def test_translates_underscores_to_hyphens(self):
        assert _taxonomy_to_assembler_family("clean_educational") == "clean-educational"
        assert _taxonomy_to_assembler_family("photo_forward") == "photo-forward"
        assert _taxonomy_to_assembler_family("dark_bold") == "dark-bold"
        assert _taxonomy_to_assembler_family("comparison_grid") == "comparison-grid"

    def test_no_underscores_unchanged(self):
        assert _taxonomy_to_assembler_family("plain") == "plain"


# --- _generate_slide_images ---

class TestGenerateSlideImages:

    def test_generates_and_cleans_images(self, tmp_path):
        """Generates images for each image_prompt and cleans them."""
        spec = _carousel_spec(image_prompts=[
            {"slide_index": 0, "prompt": "overhead slate surface"},
            {"slide_index": 1, "prompt": "kitchen scene"},
        ])

        mock_image_gen = MagicMock()
        mock_image_gen.generate.side_effect = [
            tmp_path / "bg-slide-0.png",
            tmp_path / "bg-slide-1.png",
        ]

        with patch(f"{_MODULE}.clean_image", side_effect=lambda p, **kw: p) as m_clean:
            result = _generate_slide_images(spec, mock_image_gen, tmp_path)

        assert 0 in result
        assert 1 in result
        assert mock_image_gen.generate.call_count == 2
        assert m_clean.call_count == 2

    def test_skips_prompts_with_missing_fields(self, tmp_path):
        """image_prompts without slide_index or prompt are skipped."""
        spec = _carousel_spec(image_prompts=[
            {"slide_index": None, "prompt": "test"},
            {"slide_index": 0, "prompt": ""},
        ])
        mock_image_gen = MagicMock()
        result = _generate_slide_images(spec, mock_image_gen, tmp_path)
        assert len(result) == 0
        mock_image_gen.generate.assert_not_called()

    def test_handles_generation_failure_gracefully(self, tmp_path):
        """Failed image generation does not crash; slide renders text-only."""
        spec = _carousel_spec(image_prompts=[
            {"slide_index": 0, "prompt": "test prompt"},
        ])
        mock_image_gen = MagicMock()
        mock_image_gen.generate.side_effect = RuntimeError("API down")

        result = _generate_slide_images(spec, mock_image_gen, tmp_path)
        assert len(result) == 0  # No images generated

    def test_returns_empty_dict_when_no_image_prompts(self, tmp_path):
        """No image_prompts means empty result."""
        spec = _carousel_spec(image_prompts=[])
        mock_image_gen = MagicMock()
        result = _generate_slide_images(spec, mock_image_gen, tmp_path)
        assert result == {}


# --- generate_carousels ---

class TestGenerateCarousels:

    def test_dry_run_returns_enriched_specs_without_rendering(self, tmp_path):
        """dry_run=True returns enriched specs with empty rendered_slides."""
        plan = _plan_with([_carousel_spec(carousel_id="T01")])
        mock_assembler = MagicMock()

        result = generate_carousels(
            plan, assembler=mock_assembler, output_dir=tmp_path, dry_run=True,
        )

        assert len(result) == 1
        assert result[0]["carousel_id"] == "T01"
        assert result[0]["rendered_slides"] == []
        assert result[0]["slide_count"] == 4  # hook + 2 content + CTA
        mock_assembler.render_carousel.assert_not_called()

    def test_calls_assembler_render_carousel_for_each_spec(self, tmp_path):
        """Each carousel spec triggers a render_carousel call."""
        plan = _plan_with([
            _carousel_spec(carousel_id="T01"),
            _carousel_spec(carousel_id="T02"),
        ])
        mock_assembler = MagicMock()
        mock_assembler.render_carousel.return_value = [
            tmp_path / "slide-01.png",
            tmp_path / "slide-02.png",
        ]

        with patch(f"{_MODULE}.clean_image", side_effect=lambda p, **kw: p):
            result = generate_carousels(
                plan, assembler=mock_assembler, output_dir=tmp_path,
            )

        assert mock_assembler.render_carousel.call_count == 2
        assert len(result) == 2
        assert all(r.get("rendered_slides") for r in result)

    def test_handles_render_failures_gracefully(self, tmp_path):
        """When render_carousel raises, the carousel gets render_error."""
        plan = _plan_with([_carousel_spec(carousel_id="T01")])
        mock_assembler = MagicMock()
        mock_assembler.render_carousel.side_effect = RuntimeError("puppeteer crash")

        result = generate_carousels(
            plan, assembler=mock_assembler, output_dir=tmp_path,
        )

        assert len(result) == 1
        assert result[0]["render_error"] == "puppeteer crash"
        assert result[0]["rendered_slides"] == []

    def test_tracks_image_gen_failures(self, tmp_path):
        """Missing expected images are tracked in image_gen_failures."""
        spec = _carousel_spec(
            carousel_id="T01",
            template_family="photo_forward",
            image_prompts=[
                {"slide_index": 0, "prompt": "bg0"},
                {"slide_index": 1, "prompt": "bg1"},
            ],
        )
        plan = _plan_with([spec])

        mock_assembler = MagicMock()
        mock_assembler.render_carousel.return_value = [tmp_path / "s1.png"]

        mock_image_gen = MagicMock()
        # Only generate slide 0 successfully; slide 1 fails
        mock_image_gen.generate.side_effect = [
            tmp_path / "bg-0.png",
            RuntimeError("failed"),
        ]

        with (
            patch(f"{_MODULE}.clean_image", side_effect=lambda p, **kw: p),
        ):
            result = generate_carousels(
                plan, image_gen=mock_image_gen, assembler=mock_assembler,
                output_dir=tmp_path,
            )

        assert result[0].get("image_gen_failures") == [1]

    def test_empty_plan_returns_empty_list(self, tmp_path):
        """Plan with no carousels returns empty list."""
        plan = {"carousels": []}
        result = generate_carousels(plan, output_dir=tmp_path)
        assert result == []
