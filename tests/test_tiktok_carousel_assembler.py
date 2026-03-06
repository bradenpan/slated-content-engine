"""Tests for CarouselAssembler in src/tiktok/carousel_assembler.py."""

import json
import logging
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

from src.tiktok.carousel_assembler import (
    CarouselAssembler,
    CarouselAssemblerError,
    _escape_html,
    _build_list_items_html,
    TEMPLATE_FAMILIES,
    SLIDE_TYPES,
)


_MODULE = "src.tiktok.carousel_assembler"


def _make_slides(n=3):
    """Build a list of n slide specs (hook + content(s) + cta)."""
    slides = [{"slide_type": "hook", "headline": "Hook text"}]
    for i in range(max(0, n - 2)):
        slides.append({
            "slide_type": "content",
            "headline": f"Content {i + 1}",
            "body_text": f"Body {i + 1}",
        })
    slides.append({
        "slide_type": "cta",
        "cta_primary": "Follow @slatedapp",
        "handle": "@slatedapp",
    })
    return slides


@pytest.fixture
def template_dir(tmp_path):
    """Create a minimal template directory structure for one family."""
    family = "clean-educational"
    family_dir = tmp_path / family
    family_dir.mkdir()
    shared_dir = tmp_path / "shared"
    shared_dir.mkdir()

    # Base CSS
    (shared_dir / "base-styles.css").write_text(
        "body { margin: 0; width: 1080px; height: 1920px; }", encoding="utf-8"
    )
    # Family CSS
    (family_dir / "styles.css").write_text(
        ".slide { background: #fff; }", encoding="utf-8"
    )
    # Slide templates
    for st in SLIDE_TYPES:
        (family_dir / f"{st}-slide.html").write_text(
            f"<html>{{{{styles}}}}<body class='slide'>"
            f"<h1>{{{{headline}}}}</h1>"
            f"<p>{{{{body_text}}}}</p>"
            f"<span>{{{{cta_primary}}}}</span>"
            f"</body></html>",
            encoding="utf-8",
        )

    return tmp_path


# --- _escape_html ---

class TestEscapeHtml:

    def test_escapes_special_characters(self):
        assert _escape_html("<script>alert('xss')</script>") == (
            "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;"
        )

    def test_escapes_ampersand(self):
        assert _escape_html("A & B") == "A &amp; B"

    def test_escapes_quotes(self):
        assert _escape_html('"hello"') == "&quot;hello&quot;"

    def test_passes_plain_text_through(self):
        assert _escape_html("hello world") == "hello world"


# --- _build_list_items_html ---

class TestBuildListItemsHtml:

    def test_builds_numbered_items(self):
        items = ["First", "Second", "Third"]
        result = _build_list_items_html(items)
        assert '<span class="list-item-number">1.</span>' in result
        assert '<span class="list-item-text">First</span>' in result
        assert '<span class="list-item-number">3.</span>' in result
        assert '<span class="list-item-text">Third</span>' in result

    def test_empty_list_returns_empty_string(self):
        assert _build_list_items_html([]) == ""

    def test_escapes_html_in_items(self):
        items = ["Use <code> tags"]
        result = _build_list_items_html(items)
        assert "&lt;code&gt;" in result


# --- CarouselAssembler.render_carousel validation ---

class TestRenderCarouselValidation:

    def test_unknown_template_family_raises(self, template_dir):
        assembler = CarouselAssembler(templates_dir=template_dir)
        with pytest.raises(CarouselAssemblerError, match="Unknown template family"):
            assembler.render_carousel(
                family="neon-glow",
                slides=_make_slides(),
            )

    def test_no_slides_raises(self, template_dir):
        assembler = CarouselAssembler(templates_dir=template_dir)
        with pytest.raises(CarouselAssemblerError, match="No slides provided"):
            assembler.render_carousel(
                family="clean-educational",
                slides=[],
            )

    def test_unknown_slide_type_raises(self, template_dir):
        assembler = CarouselAssembler(templates_dir=template_dir)
        slides = [{"slide_type": "intro", "headline": "bad type"}]
        with pytest.raises(CarouselAssemblerError, match="Unknown slide_type"):
            assembler.render_carousel(
                family="clean-educational",
                slides=slides,
            )


# --- _render_batch ---

class TestRenderBatch:

    def _make_assembler(self, template_dir=None):
        return CarouselAssembler(templates_dir=template_dir)

    def test_raises_on_non_zero_return_code(self, tmp_path):
        assembler = self._make_assembler(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: something failed"
        mock_result.stdout = ""

        with patch(f"{_MODULE}.subprocess.run", return_value=mock_result):
            with pytest.raises(CarouselAssemblerError, match="exited with code 1"):
                assembler._render_batch([{"html_file": "a.html", "output_file": "a.png"}])

    def test_raises_on_empty_stdout(self, tmp_path):
        assembler = self._make_assembler(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch(f"{_MODULE}.subprocess.run", return_value=mock_result):
            with pytest.raises(CarouselAssemblerError, match="no output"):
                assembler._render_batch([{"html_file": "a.html", "output_file": "a.png"}])

    def test_raises_on_invalid_json(self, tmp_path):
        assembler = self._make_assembler(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json {{"
        mock_result.stderr = ""

        with patch(f"{_MODULE}.subprocess.run", return_value=mock_result):
            with pytest.raises(CarouselAssemblerError, match="invalid JSON"):
                assembler._render_batch([{"html_file": "a.html", "output_file": "a.png"}])

    def test_raises_when_response_ok_is_false(self, tmp_path):
        assembler = self._make_assembler(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"ok": False, "error": "render failed"})
        mock_result.stderr = ""

        with patch(f"{_MODULE}.subprocess.run", return_value=mock_result):
            with pytest.raises(CarouselAssemblerError, match="render_pin.js failed"):
                assembler._render_batch([{"html_file": "a.html", "output_file": "a.png"}])

    def test_raises_when_rendered_count_differs_from_job_count(self, tmp_path):
        assembler = self._make_assembler(tmp_path)
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "ok": True,
            "rendered": ["/tmp/slide-01.png"],
        })
        mock_result.stderr = ""

        jobs = [
            {"html_file": "a.html", "output_file": "a.png"},
            {"html_file": "b.html", "output_file": "b.png"},
        ]

        with (
            patch(f"{_MODULE}.subprocess.run", return_value=mock_result),
            pytest.raises(CarouselAssemblerError, match="1 slides but 2 were requested"),
        ):
            assembler._render_batch(jobs)


# --- render_carousel integration (with mocked subprocess) ---

class TestRenderCarouselIntegration:

    def test_validates_output_file_existence_and_minimum_size(self, template_dir, tmp_path):
        """render_carousel checks that output files exist and meet minimum size."""
        assembler = CarouselAssembler(templates_dir=template_dir)
        slides = _make_slides(3)

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Create an output file that's too small (< MIN_IMAGE_SIZE)
        small_file = output_dir / "carousel-slide-01.png"
        small_file.write_bytes(b"\x89PNG" * 10)  # 40 bytes, well under threshold

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "ok": True,
            "rendered": [str(small_file)],
        })
        mock_result.stderr = ""

        with patch(f"{_MODULE}.subprocess.run", return_value=mock_result):
            with pytest.raises(CarouselAssemblerError, match="too small"):
                assembler.render_carousel(
                    family="clean-educational",
                    slides=[slides[0]],  # Single slide to match rendered count
                    output_dir=output_dir,
                    carousel_id="carousel",
                )

    def test_validates_output_file_existence(self, template_dir, tmp_path):
        """render_carousel raises when output file does not exist."""
        assembler = CarouselAssembler(templates_dir=template_dir)
        slides = [_make_slides(2)[0]]  # hook only

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        nonexistent = str(output_dir / "does-not-exist.png")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "ok": True,
            "rendered": [nonexistent],
        })
        mock_result.stderr = ""

        with patch(f"{_MODULE}.subprocess.run", return_value=mock_result):
            with pytest.raises(CarouselAssemblerError, match="no output"):
                assembler.render_carousel(
                    family="clean-educational",
                    slides=slides,
                    output_dir=output_dir,
                    carousel_id="carousel",
                )

    def test_cleans_up_temp_html_files_even_on_error(self, template_dir, tmp_path):
        """Temp HTML files are cleaned up even when rendering raises."""
        assembler = CarouselAssembler(templates_dir=template_dir)
        slides = _make_slides(2)  # hook + cta

        created_temps = []
        original_unlink = os.unlink

        def track_unlink(path):
            if path.endswith(".html"):
                created_temps.append(path)
            original_unlink(path)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "crash"
        mock_result.stdout = ""

        with (
            patch(f"{_MODULE}.subprocess.run", return_value=mock_result),
            patch(f"{_MODULE}.os.unlink", side_effect=track_unlink),
        ):
            with pytest.raises(CarouselAssemblerError):
                assembler.render_carousel(
                    family="clean-educational",
                    slides=slides,
                    output_dir=tmp_path / "output",
                    carousel_id="carousel",
                )

        # At least one temp HTML file should have been cleaned up
        assert len(created_temps) >= 1
