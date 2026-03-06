"""
TikTok Carousel Assembler — HTML/CSS Template to Rendered PNG Slides

Takes carousel slide specifications and renders them to 1080x1920px PNG images
using Puppeteer (headless Chromium) via the shared render_pin.js script.

Template families are in templates/tiktok/carousels/ with subdirectories:
- clean-educational/ — Light background, bold dark headlines, numbered slides
- dark-bold/ — High-contrast white/accent on dark, dramatic
- photo-forward/ — Real photo background with semi-transparent text overlay
- comparison-grid/ — Split panels, structured data, balanced layout

Each family has 3 slide types: hook-slide, content-slide, cta-slide.
The assembler selects the correct template per slide, injects content,
inlines CSS, and renders all slides in a single Puppeteer batch via manifest.
"""

import html as html_module
import json
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from src.shared.paths import PROJECT_ROOT, TEMPLATES_DIR, TIKTOK_OUTPUT_DIR
from src.shared.config import TIKTOK_SLIDE_WIDTH, TIKTOK_SLIDE_HEIGHT, MIN_IMAGE_SIZE
from src.shared.utils.image_utils import image_to_data_uri

logger = logging.getLogger(__name__)

# TikTok carousel templates subdirectory
CAROUSEL_TEMPLATES_DIR = TEMPLATES_DIR / "tiktok" / "carousels"
SHARED_DIR = CAROUSEL_TEMPLATES_DIR / "shared"

# Shared render script (same as Pinterest)
RENDER_SCRIPT = PROJECT_ROOT / "render_pin.js"

# Valid template families and their slide types
TEMPLATE_FAMILIES = {
    "clean-educational": {
        "description": "Light background, bold dark headlines, numbered slides",
        "best_for": "Listicles, how-tos, tips",
    },
    "dark-bold": {
        "description": "High-contrast white/accent on dark, dramatic",
        "best_for": "Bold claims, contrarian takes, shocking stats",
    },
    "photo-forward": {
        "description": "Real photo background with semi-transparent text overlay",
        "best_for": "Recipes, food photography, transformations",
    },
    "comparison-grid": {
        "description": "Split panels, structured data, balanced layout",
        "best_for": "Before/after, comparisons, pros/cons",
    },
}

SLIDE_TYPES = ["hook", "content", "cta"]


class CarouselAssemblerError(Exception):
    """Raised when carousel assembly or rendering fails."""
    pass


def _escape_html(text: str) -> str:
    """Escape text for safe HTML injection."""
    return html_module.escape(text, quote=True)


def _build_list_items_html(items: list[str]) -> str:
    """Build HTML for numbered list items within a content slide."""
    if not items:
        return ""
    html_parts = []
    for i, item in enumerate(items, 1):
        escaped = _escape_html(item)
        html_parts.append(
            f'<div class="list-item-row">'
            f'  <span class="list-item-number">{i}.</span>'
            f'  <span class="list-item-text">{escaped}</span>'
            f'</div>'
        )
    return "\n".join(html_parts)


class CarouselAssembler:
    """Assembles TikTok carousel slides from HTML/CSS templates + dynamic content.

    Uses Puppeteer (headless Chromium) via the shared render_pin.js script.
    All slides for a carousel are rendered in a single browser session via
    the manifest batch mode.
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        self.templates_dir = templates_dir or CAROUSEL_TEMPLATES_DIR
        self.shared_dir = self.templates_dir / "shared"

    def _load_css(self, family: str) -> tuple[str, str]:
        """Load base CSS and family-specific CSS."""
        base_css_path = self.shared_dir / "base-styles.css"
        family_css_path = self.templates_dir / family / "styles.css"

        if not base_css_path.exists():
            raise CarouselAssemblerError(f"Base CSS not found: {base_css_path}")
        if not family_css_path.exists():
            raise CarouselAssemblerError(f"Family CSS not found: {family_css_path}")

        return (
            base_css_path.read_text(encoding="utf-8"),
            family_css_path.read_text(encoding="utf-8"),
        )

    def _load_slide_html(self, family: str, slide_type: str) -> str:
        """Load the HTML template for a specific slide type."""
        html_path = self.templates_dir / family / f"{slide_type}-slide.html"
        if not html_path.exists():
            raise CarouselAssemblerError(f"Slide template not found: {html_path}")
        return html_path.read_text(encoding="utf-8")

    def _inline_css(self, raw_html: str, base_css: str, family_css: str) -> str:
        """Replace the {{styles}} placeholder with inlined CSS."""
        combined_css = f"<style>\n{base_css}\n{family_css}\n</style>"
        return raw_html.replace("{{styles}}", combined_css)

    def _inject_variables(self, html_content: str, context: dict[str, Any]) -> str:
        """Inject template variables into HTML content.

        Handles:
        - Image URLs: converts local paths to data URIs
        - List items: builds numbered list HTML from array
        - All other variables: escaped text replacement
        """
        result = html_content

        # Handle image variables — convert local paths to data URIs
        image_vars = ["background_image_url"]
        for var in image_vars:
            placeholder = "{{" + var + "}}"
            if placeholder in result:
                value = context.get(var, "")
                if value and not value.startswith(("data:", "http://", "https://")):
                    value = image_to_data_uri(value)
                result = result.replace(placeholder, value or "")

        # Handle list_items (array of strings -> HTML)
        if "{{list_items}}" in result:
            items = context.get("list_items", [])
            if isinstance(items, list):
                items_html = _build_list_items_html(items)
            else:
                items_html = _escape_html(str(items))
            result = result.replace("{{list_items}}", items_html)

        # Handle all remaining simple text variables
        simple_vars = [
            "headline", "subtitle", "body_text",
            "slide_number", "total_slides",
            "cta_primary", "cta_secondary", "handle",
            "left_label", "right_label", "left_text", "right_text",
        ]
        for var in simple_vars:
            placeholder = "{{" + var + "}}"
            if placeholder in result:
                value = context.get(var, "")
                result = result.replace(placeholder, _escape_html(str(value)))

        return result

    def _prepare_slide_html(
        self,
        family: str,
        slide_type: str,
        context: dict[str, Any],
    ) -> str:
        """Prepare final HTML string for one slide."""
        raw_html = self._load_slide_html(family, slide_type)
        base_css, family_css = self._load_css(family)
        html_with_css = self._inline_css(raw_html, base_css, family_css)
        return self._inject_variables(html_with_css, context)

    def render_carousel(
        self,
        family: str,
        slides: list[dict[str, Any]],
        output_dir: Optional[Path] = None,
        carousel_id: str = "carousel",
    ) -> list[Path]:
        """Render a multi-slide TikTok carousel.

        Args:
            family: Template family name (e.g., "clean-educational").
            slides: List of slide specs, each a dict with:
                - slide_type: "hook", "content", or "cta"
                - Plus template variables (headline, body_text, etc.)
            output_dir: Where to write slide PNGs. Defaults to TIKTOK_OUTPUT_DIR.
            carousel_id: Identifier for naming output files.

        Returns:
            List of Paths to rendered slide PNGs, in order.

        Raises:
            CarouselAssemblerError: If family/slide_type invalid or rendering fails.
        """
        if family not in TEMPLATE_FAMILIES:
            raise CarouselAssemblerError(
                f"Unknown template family: {family}. "
                f"Valid families: {list(TEMPLATE_FAMILIES.keys())}"
            )

        if not slides:
            raise CarouselAssemblerError("No slides provided")

        if output_dir is None:
            output_dir = TIKTOK_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        total_slides = len(slides)
        temp_html_paths = []
        manifest_jobs = []

        try:
            for i, slide_spec in enumerate(slides):
                slide_type = slide_spec.get("slide_type")
                if slide_type not in SLIDE_TYPES:
                    raise CarouselAssemblerError(
                        f"Unknown slide_type: {slide_type}. Valid types: {SLIDE_TYPES}"
                    )

                # Build context with auto-injected slide numbering
                context = dict(slide_spec)
                context.pop("slide_type", None)
                context.setdefault("slide_number", str(i + 1))
                context.setdefault("total_slides", str(total_slides))

                # Prepare HTML
                final_html = self._prepare_slide_html(family, slide_type, context)

                # Write to temp file
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".html", encoding="utf-8", delete=False
                ) as f:
                    f.write(final_html)
                    temp_html_paths.append(f.name)

                # Build manifest entry
                # First slide needs 500ms for web font loading; subsequent slides
                # reuse the browser's font cache and only need a brief settle.
                output_path = output_dir / f"{carousel_id}-slide-{i + 1:02d}.png"
                manifest_jobs.append({
                    "html_file": f.name,
                    "output_file": str(output_path),
                    "width": TIKTOK_SLIDE_WIDTH,
                    "height": TIKTOK_SLIDE_HEIGHT,
                    "wait_ms": 500 if i == 0 else 100,
                })

            # Write manifest and render all slides in one Puppeteer session
            rendered_paths = self._render_batch(manifest_jobs)

            # Validate outputs
            for path in rendered_paths:
                p = Path(path)
                if not p.exists():
                    raise CarouselAssemblerError(f"Render produced no output at {p}")
                if p.stat().st_size < MIN_IMAGE_SIZE:
                    raise CarouselAssemblerError(
                        f"Slide too small ({p.stat().st_size} bytes): {p}"
                    )

            logger.info(
                "Carousel rendered: %s — %d slides (%s)",
                carousel_id, len(rendered_paths), family,
            )
            return [Path(p) for p in rendered_paths]

        finally:
            # Clean up temp HTML files
            for tmp in temp_html_paths:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def _render_batch(self, jobs: list[dict]) -> list[str]:
        """Call render_pin.js with a manifest to render all slides in one session."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        ) as mf:
            json.dump(jobs, mf)
            manifest_path = mf.name

        try:
            result = subprocess.run(
                ["node", str(RENDER_SCRIPT), "--manifest", manifest_path],
                capture_output=True,
                text=True,
                timeout=120,  # longer timeout for multi-slide batches
            )

            if result.returncode != 0:
                raise CarouselAssemblerError(
                    f"render_pin.js exited with code {result.returncode}. "
                    f"stderr: {result.stderr}"
                )

            stdout = result.stdout.strip()
            if not stdout:
                raise CarouselAssemblerError(
                    f"render_pin.js produced no output. stderr: {result.stderr}"
                )

            try:
                response = json.loads(stdout)
            except json.JSONDecodeError:
                raise CarouselAssemblerError(
                    f"render_pin.js returned invalid JSON: {stdout}. stderr: {result.stderr}"
                )

            if not response.get("ok"):
                rendered_partial = response.get("rendered", [])
                errors = response.get("errors", response.get("error", "unknown error"))
                if rendered_partial:
                    # Partial success: some slides rendered but others failed.
                    # Reject the entire carousel — partial renders produce
                    # misaligned slide indices that corrupt GCS uploads.
                    logger.warning(
                        "render_pin.js partial failure: %d/%d slides rendered. "
                        "Rejecting entire carousel to prevent index misalignment. Errors: %s",
                        len(rendered_partial), len(jobs), errors,
                    )
                raise CarouselAssemblerError(
                    f"render_pin.js failed ({len(rendered_partial) if rendered_partial else 0}/"
                    f"{len(jobs)} slides): {errors}"
                )

            rendered = response.get("rendered", [])
            if len(rendered) != len(jobs):
                raise CarouselAssemblerError(
                    f"render_pin.js returned {len(rendered)} slides but "
                    f"{len(jobs)} were requested — rejecting to prevent index misalignment"
                )
            return rendered

        finally:
            try:
                os.unlink(manifest_path)
            except OSError:
                pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    assembler = CarouselAssembler()
    print("TikTok Carousel Template Families:")
    print("=" * 60)
    for name, config in TEMPLATE_FAMILIES.items():
        family_dir = assembler.templates_dir / name
        slides_ok = all(
            (family_dir / f"{st}-slide.html").exists() for st in SLIDE_TYPES
        )
        css_ok = (family_dir / "styles.css").exists()
        status = "READY" if slides_ok and css_ok else "MISSING"
        print(f"  [{status}] {name}")
        print(f"           {config['description']}")
        print(f"           Best for: {config['best_for']}")
        print(f"           Slide types: {', '.join(SLIDE_TYPES)}")
        print()
