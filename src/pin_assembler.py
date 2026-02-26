"""
Pin Image Assembler — HTML/CSS Template to Rendered PNG

Takes an HTML/CSS pin template, injects dynamic content (hero image, title
text, branding), and renders it to a 1000x1500px PNG image using Puppeteer
(headless Chromium) via a Node.js subprocess (render_pin.js).

Pin templates are in templates/pins/ with subdirectories per template type:
- recipe-pin/ — Food photo top 60-70%, overlay bar bottom 30-40%
- tip-pin/ — Lifestyle background, heavier text overlay
- listicle-pin/ — Collage or single image with strong overlay
- problem-solution-pin/ — Split or gradient design
- infographic-pin/ — Minimal background, multiple text blocks

Each template has 3 visual variants (A, B, C) in a single HTML file.
The assembler selects the active variant, injects content, inlines CSS,
and renders via Puppeteer screenshot.

All pins are 1000x1500px (2:3 ratio) with text in the center 80%
safe zone. Text must be readable at ~300px thumbnail width.
"""

import base64
import html as html_module
import json
import logging
import os
import random
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Resolve paths relative to this file's location
_SRC_DIR = Path(__file__).parent
_PROJECT_ROOT = _SRC_DIR.parent
TEMPLATES_DIR = _PROJECT_ROOT / "templates" / "pins"
SHARED_DIR = TEMPLATES_DIR / "shared"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "test_output"

# Path to the Node.js render script
RENDER_SCRIPT = _PROJECT_ROOT / "render_pin.js"

# Pin canvas dimensions
PIN_WIDTH = 1000
PIN_HEIGHT = 1500

# Maximum output PNG file size target (bytes)
MAX_PNG_SIZE = 500 * 1024  # 500 KB

# Variant number-to-letter mapping (callers may pass int or str)
_VARIANT_MAP = {1: "A", 2: "B", 3: "C", "1": "A", "2": "B", "3": "C"}

# Valid template names and their variant labels
# All template-specific variables (category_label, problem_label, solution_label,
# time_badge) are injected via simple_vars and consumed by HTML templates.
TEMPLATE_CONFIGS = {
    "recipe-pin": {
        "variants": ["A", "B", "C"],
        "description": "Food photo with text overlay — recipe name + descriptor",
        "variables": ["hero_image_url", "headline", "subtitle", "time_badge", "cta_text"],
    },
    "tip-pin": {
        "variants": ["A", "B", "C"],
        "description": "Lifestyle background with tip headline + bullet points",
        "variables": ["background_image_url", "headline", "bullet_1", "bullet_2", "bullet_3", "category_label", "cta_text"],
    },
    "listicle-pin": {
        "variants": ["A", "B", "C"],
        "description": "Number-prominent list with optional background image",
        "variables": ["number", "headline", "list_items", "background_image_url", "cta_text"],
    },
    "problem-solution-pin": {
        "variants": ["A", "B", "C"],
        "description": "Split design — problem statement top, solution bottom",
        "variables": ["problem_text", "solution_text", "background_image_url", "problem_label", "solution_label", "cta_text"],
    },
    "infographic-pin": {
        "variants": ["A", "B", "C"],
        "description": "Structured steps/info on branded background — minimal photography",
        "variables": ["title", "steps", "footer_text", "category_label", "cta_text"],
    },
}


class PinAssemblerError(Exception):
    """Raised when pin assembly or rendering fails."""
    pass


def _image_to_data_uri(image_path: str) -> str:
    """Convert a local image file path to a base64 data URI.

    This is critical for headless rendering — external file:// URLs
    and network requests may not work reliably in headless mode.
    """
    path = Path(image_path)
    if not path.exists():
        logger.warning("Image not found at %s, using empty placeholder", image_path)
        return ""

    suffix = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime = mime_map.get(suffix, "image/jpeg")

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")

    return f"data:{mime};base64,{encoded}"


def _escape_html(text: str) -> str:
    """Escape text for safe HTML injection."""
    return html_module.escape(text, quote=True)


def _build_list_items_html(items: list[str], variant: str, has_more: bool = False) -> str:
    """Build HTML for listicle pin list items based on variant.

    Args:
        items: List of item strings to render.
        variant: Template variant letter (A, B, or C).
        has_more: If True, append an italic "...and more" row after the items.
    """
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

    if has_more:
        html_parts.append(
            f'<div class="list-item-row list-item-more">'
            f'  <span class="list-item-number"></span>'
            f'  <span class="list-item-text" style="font-style: italic; opacity: 0.7;">...and more</span>'
            f'</div>'
        )

    return "\n".join(html_parts)


def _build_infographic_steps_html(steps: list[dict], variant: str) -> str:
    """Build HTML for infographic pin steps based on variant.

    Each step is a dict with 'number' (int or str) and 'text' (str).
    """
    if not steps:
        return ""

    html_parts = []
    for step in steps:
        num = step.get("number", "")
        text = _escape_html(step.get("text", ""))

        if variant == "A":
            html_parts.append(
                f'<div class="info-step-row">'
                f'  <div class="step-circle">{num}</div>'
                f'  <div class="info-step-text">{text}</div>'
                f'</div>'
            )
        elif variant == "B":
            html_parts.append(
                f'<div class="info-grid-cell">'
                f'  <div class="info-grid-number">{num}</div>'
                f'  <div class="info-grid-text">{text}</div>'
                f'</div>'
            )
        elif variant == "C":
            html_parts.append(
                f'<div class="info-timeline-node">'
                f'  <div class="info-timeline-dot"></div>'
                f'  <div class="info-timeline-content">'
                f'    <div class="info-timeline-step-num">Step {num}</div>'
                f'    <div class="info-timeline-text">{text}</div>'
                f'  </div>'
                f'</div>'
            )

    return "\n".join(html_parts)


def _normalize_variant(variant) -> str:
    """Normalize variant to a letter (A, B, C). Accepts int, str int, or letter."""
    if variant in _VARIANT_MAP:
        return _VARIANT_MAP[variant]
    if isinstance(variant, str) and variant.upper() in ("A", "B", "C"):
        return variant.upper()
    return "A"


class PinAssembler:
    """Assembles pin images from HTML/CSS templates + dynamic content.

    Uses Puppeteer (headless Chromium) via Node.js subprocess to render
    HTML templates to PNG. Templates are loaded from the templates/pins/
    directory, CSS is inlined, and variables are injected before rendering.
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        """Initialize the pin assembler.

        Args:
            templates_dir: Override path to templates/pins/ directory.
                           Defaults to the standard project location.
        """
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.shared_dir = self.templates_dir / "shared"

    def _load_css(self, template_name: str) -> tuple[str, str]:
        """Load base CSS and template-specific CSS.

        Returns:
            (base_css, template_css) tuple of CSS strings.
        """
        base_css_path = self.shared_dir / "base-styles.css"
        template_css_path = self.templates_dir / template_name / "styles.css"

        if not base_css_path.exists():
            raise PinAssemblerError(f"Base CSS not found: {base_css_path}")
        if not template_css_path.exists():
            raise PinAssemblerError(f"Template CSS not found: {template_css_path}")

        base_css = base_css_path.read_text(encoding="utf-8")
        template_css = template_css_path.read_text(encoding="utf-8")

        return base_css, template_css

    def _load_template_html(self, template_name: str) -> str:
        """Load the template HTML file."""
        html_path = self.templates_dir / template_name / "template.html"
        if not html_path.exists():
            raise PinAssemblerError(f"Template HTML not found: {html_path}")
        return html_path.read_text(encoding="utf-8")

    def _inline_css(self, raw_html: str, base_css: str, template_css: str) -> str:
        """Replace the {{styles}} placeholder with inlined CSS."""
        combined_css = f"<style>\n{base_css}\n{template_css}\n</style>"
        return raw_html.replace("{{styles}}", combined_css)

    def _activate_variant(self, html_content: str, variant: str) -> str:
        """Show only the selected variant by toggling display.

        Each variant div has style='display: none;' by default.
        We remove that for the selected variant and remove non-selected variants entirely.
        """
        lines = html_content.split("\n")
        result = []
        in_wrong_variant = False
        depth = 0

        for line in lines:
            # Check if this line opens a variant container
            if 'data-variant="' in line and 'pin-canvas' in line:
                if f'data-variant="{variant}"' in line:
                    # This is the active variant — remove display:none
                    line = line.replace("style=\"display: none;\"", "")
                    in_wrong_variant = False
                    result.append(line)
                else:
                    # This is a non-active variant — skip it
                    in_wrong_variant = True
                    depth = 1
                continue

            if in_wrong_variant:
                # Count div opens and closes to skip the entire block
                depth += line.count("<div")
                depth -= line.count("</div")
                if depth <= 0:
                    in_wrong_variant = False
                continue

            result.append(line)

        return "\n".join(result)

    def _inject_variables(
        self,
        html_content: str,
        template_name: str,
        variant: str,
        context: dict[str, Any],
    ) -> str:
        """Inject template variables into the HTML content.

        Handles:
        - Simple string variables: {{variable_name}} -> escaped text
        - Image URLs: converts local paths to data URIs
        - List items (listicle): builds list HTML from array
        - Steps (infographic): builds step HTML from array of dicts
        - Logo URL placeholder
        - Optional bullet_3 hiding for tip pins
        """
        result = html_content

        # Handle image variables — convert local paths to data URIs
        image_vars = ["hero_image_url", "background_image_url"]
        for var in image_vars:
            placeholder = "{{" + var + "}}"
            if placeholder in result:
                value = context.get(var, "")
                if value and not value.startswith(("data:", "http://", "https://")):
                    # Local file path — convert to data URI
                    value = _image_to_data_uri(value)
                result = result.replace(placeholder, value or "")

        # Handle listicle list_items (array of strings -> HTML)
        if template_name == "listicle-pin" and "{{list_items}}" in result:
            items = context.get("list_items", [])
            has_more = bool(context.get("has_more_items", False))
            if isinstance(items, list):
                items_html = _build_list_items_html(items, variant, has_more=has_more)
            else:
                items_html = _escape_html(str(items))
            result = result.replace("{{list_items}}", items_html)

        # Handle infographic steps (array of dicts -> HTML)
        if template_name == "infographic-pin" and "{{steps}}" in result:
            steps = context.get("steps", [])
            if isinstance(steps, list):
                steps_html = _build_infographic_steps_html(steps, variant)
            else:
                steps_html = _escape_html(str(steps))
            result = result.replace("{{steps}}", steps_html)

        # Handle logo_url — for now, the template uses text placeholder
        logo_url = context.get("logo_url", "")
        result = result.replace("{{logo_url}}", logo_url)

        # Handle all remaining simple text variables
        simple_vars = [
            "headline", "subtitle", "number",
            "bullet_1", "bullet_2", "bullet_3",
            "problem_text", "solution_text",
            "title", "footer_text",
            "cta_text",
            "time_badge",
            "category_label",
            "problem_label", "solution_label",
        ]
        for var in simple_vars:
            placeholder = "{{" + var + "}}"
            if placeholder in result:
                value = context.get(var, "")
                result = result.replace(placeholder, _escape_html(str(value)))

        # Handle optional bullet_3 for tip pins — hide if empty
        if template_name == "tip-pin" and not context.get("bullet_3"):
            result = result.replace(
                'class="tip-bullet-row tip-bullet-optional"',
                'class="tip-bullet-row tip-bullet-optional hidden"'
            )
            result = result.replace(
                'class="tip-c-bullet-card tip-bullet-optional"',
                'class="tip-c-bullet-card tip-bullet-optional hidden"'
            )

        # Hide time badge if no time_badge provided
        if template_name == "recipe-pin" and not context.get("time_badge"):
            result = result.replace(
                'class="recipe-time-badge"',
                'class="recipe-time-badge hidden"'
            )
            result = result.replace(
                'class="recipe-time-badge recipe-time-badge-dark"',
                'class="recipe-time-badge recipe-time-badge-dark hidden"'
            )

        # Hide CTA if no cta_text provided
        if not context.get("cta_text"):
            result = result.replace('class="pin-cta"', 'class="pin-cta hidden"')
            result = result.replace('class="pin-cta pin-cta-light"', 'class="pin-cta pin-cta-light hidden"')

        return result

    def _prepare_html(
        self,
        template_name: str,
        variant: str,
        context: dict[str, Any],
    ) -> str:
        """Prepare final HTML string from template + context (no rendering).

        Loads template, inlines CSS, activates variant, injects variables.
        """
        raw_html = self._load_template_html(template_name)
        base_css, template_css = self._load_css(template_name)
        html_with_css = self._inline_css(raw_html, base_css, template_css)
        html_active = self._activate_variant(html_with_css, variant)
        return self._inject_variables(html_active, template_name, variant, context)

    def _render_via_puppeteer(self, html_file: str, output_file: str) -> None:
        """Call render_pin.js to render a single HTML file to PNG."""
        result = subprocess.run(
            [
                "node", str(RENDER_SCRIPT),
                "--html-file", html_file,
                "--output", output_file,
                "--width", str(PIN_WIDTH),
                "--height", str(PIN_HEIGHT),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Parse JSON output from render_pin.js
        stdout = result.stdout.strip()
        if not stdout:
            raise PinAssemblerError(
                f"render_pin.js produced no output. stderr: {result.stderr}"
            )

        try:
            response = json.loads(stdout)
        except json.JSONDecodeError:
            raise PinAssemblerError(
                f"render_pin.js returned invalid JSON: {stdout}. stderr: {result.stderr}"
            )

        if not response.get("ok"):
            errors = response.get("errors", response.get("error", "unknown error"))
            raise PinAssemblerError(f"render_pin.js failed: {errors}")

    def render_pin(
        self,
        template_name: str,
        variant: str,
        context: dict[str, Any],
        output_path: Optional[Path] = None,
    ) -> Path:
        """Render a pin image from template + context data.

        Args:
            template_name: One of the TEMPLATE_CONFIGS keys.
            variant: "A", "B", or "C" (also accepts 1, 2, 3).
            context: Dictionary of template variables.
            output_path: Where to save the PNG. Auto-generated if None.

        Returns:
            Path to the rendered PNG file.

        Raises:
            PinAssemblerError: If template not found or rendering fails.
        """
        variant = _normalize_variant(variant)

        # Validate template and variant
        if template_name not in TEMPLATE_CONFIGS:
            raise PinAssemblerError(
                f"Unknown template: {template_name}. "
                f"Valid templates: {list(TEMPLATE_CONFIGS.keys())}"
            )

        config = TEMPLATE_CONFIGS[template_name]
        if variant not in config["variants"]:
            raise PinAssemblerError(
                f"Unknown variant '{variant}' for {template_name}. "
                f"Valid variants: {config['variants']}"
            )

        # Build output path
        if output_path is None:
            output_dir = DEFAULT_OUTPUT_DIR
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{template_name}_{variant}.png"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Rendering %s variant %s -> %s", template_name, variant, output_path)

        try:
            # Step 1-4: Prepare final HTML
            final_html = self._prepare_html(template_name, variant, context)

            # Step 5: Write HTML to temp file, render via Puppeteer
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".html", encoding="utf-8", delete=False
            ) as f:
                f.write(final_html)
                temp_html_path = f.name

            try:
                self._render_via_puppeteer(temp_html_path, str(output_path))
            finally:
                os.unlink(temp_html_path)

            # Step 6: Optimize file size
            self._optimize_image(output_path)

            logger.info("Pin rendered successfully: %s (%d bytes)", output_path, output_path.stat().st_size)
            return output_path

        except PinAssemblerError:
            raise
        except Exception as e:
            raise PinAssemblerError(f"Failed to render {template_name} variant {variant}: {e}") from e

    def assemble_pin(
        self,
        template_type: str,
        hero_image_path: Optional[str],
        headline: str,
        subtitle: str = "",
        variant: int | str = 1,
        output_path: Optional[Path] = None,
        extra_context: Optional[dict[str, Any]] = None,
    ) -> Path:
        """Convenience method matching the caller interface in generate_pin_content.py.

        Maps positional arguments to the context dict expected by render_pin().
        An optional extra_context dict is merged in, allowing callers to pass
        template-specific variables (e.g. bullet_1, list_items, steps).
        """
        context = {
            "headline": headline,
            "subtitle": subtitle,
        }
        if hero_image_path:
            context["hero_image_url"] = str(hero_image_path)

        if extra_context:
            context.update(extra_context)

        return self.render_pin(
            template_name=template_type,
            variant=variant,
            context=context,
            output_path=output_path,
        )

    def _optimize_image(self, image_path: Path) -> None:
        """Optimize PNG file size. Target: <500KB per pin.

        Uses Pillow to re-save with optimization. If still over target,
        converts to high-quality JPEG.
        """
        try:
            from PIL import Image

            file_size = image_path.stat().st_size

            if file_size <= MAX_PNG_SIZE:
                return  # Already under target

            # Re-save PNG with optimization
            img = Image.open(image_path)
            img.save(image_path, "PNG", optimize=True)

            file_size = image_path.stat().st_size
            if file_size <= MAX_PNG_SIZE:
                logger.info("PNG optimized to %d bytes", file_size)
                return

            # If still too large, convert to JPEG
            jpeg_path = image_path.with_suffix(".jpg")
            if img.mode == "RGBA":
                # JPEG doesn't support alpha — composite on white
                bg = Image.new("RGB", img.size, (255, 255, 255))
                bg.paste(img, mask=img.split()[3])
                bg.save(jpeg_path, "JPEG", quality=88, optimize=True)
            else:
                img.save(jpeg_path, "JPEG", quality=88, optimize=True)

            # Replace PNG with JPEG if smaller — rename JPEG to the original
            # .png path so all downstream path references remain valid
            if jpeg_path.stat().st_size < file_size:
                image_path.unlink()          # delete original PNG
                jpeg_path.rename(image_path) # rename .jpg to original path
                logger.info(
                    "Converted to JPEG: %d bytes (was %d bytes PNG)",
                    image_path.stat().st_size,
                    file_size,
                )
            else:
                jpeg_path.unlink()

        except ImportError:
            logger.warning("Pillow not installed — skipping image optimization")
        except Exception as e:
            logger.warning("Image optimization failed: %s", e)

    def render_batch(
        self,
        pin_specs: list[dict[str, Any]],
        output_dir: Optional[Path] = None,
    ) -> list[Path]:
        """Render multiple pins in a single Puppeteer browser session.

        Uses a manifest file to pass all jobs to render_pin.js at once,
        so only one browser instance is launched for the entire batch.

        Args:
            pin_specs: List of dicts, each containing:
                - template_name: str
                - variant: str
                - context: dict of template variables
                - output_filename: str (optional, auto-generated if missing)
            output_dir: Directory for all output files.

        Returns:
            List of Paths to rendered images (None for failures).
        """
        if output_dir is None:
            output_dir = DEFAULT_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare all HTML files and build manifest
        manifest = []
        temp_files = []

        for i, spec in enumerate(pin_specs):
            template_name = spec["template_name"]
            variant = _normalize_variant(spec["variant"])
            context = spec.get("context", {})
            filename = spec.get(
                "output_filename",
                f"{template_name}_{variant}_{i:03d}.png"
            )
            output_path = output_dir / filename

            try:
                final_html = self._prepare_html(template_name, variant, context)

                tmp = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".html", encoding="utf-8", delete=False
                )
                tmp.write(final_html)
                tmp.close()
                temp_files.append(tmp.name)

                manifest.append({
                    "html_file": tmp.name,
                    "output_file": str(output_path),
                    "width": PIN_WIDTH,
                    "height": PIN_HEIGHT,
                })
            except PinAssemblerError as e:
                logger.error("Failed to prepare pin %d (%s): %s", i, template_name, e)
                manifest.append(None)
                temp_files.append(None)

        # Filter out failed preparations
        valid_manifest = [m for m in manifest if m is not None]

        if not valid_manifest:
            return [None] * len(pin_specs)

        # Write manifest and call render_pin.js once
        manifest_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", encoding="utf-8", delete=False
        )
        json.dump(valid_manifest, manifest_file)
        manifest_file.close()

        try:
            result = subprocess.run(
                ["node", str(RENDER_SCRIPT), "--manifest", manifest_file.name],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes for large batches
            )

            stdout = result.stdout.strip()
            if stdout:
                try:
                    response = json.loads(stdout)
                except json.JSONDecodeError:
                    logger.error("render_pin.js returned invalid JSON: %s", stdout)
                    response = {"ok": False}
            else:
                logger.error("render_pin.js produced no output. stderr: %s", result.stderr)
                response = {"ok": False}

            if not response.get("ok") and response.get("errors"):
                for err in response["errors"]:
                    logger.error("Render error: %s — %s", err.get("file"), err.get("error"))

        finally:
            # Clean up temp files
            os.unlink(manifest_file.name)
            for tf in temp_files:
                if tf and os.path.exists(tf):
                    os.unlink(tf)

        # Build results list, optimizing each rendered image
        results = []
        for i, spec in enumerate(pin_specs):
            filename = spec.get(
                "output_filename",
                f"{spec['template_name']}_{_normalize_variant(spec['variant'])}_{i:03d}.png"
            )
            output_path = output_dir / filename

            if output_path.exists():
                self._optimize_image(output_path)
                results.append(output_path)
            else:
                results.append(None)

        return results

    @staticmethod
    def select_variant(
        template_name: str,
        recent_variants: Optional[list[str]] = None,
    ) -> str:
        """Select a variant not used in the last 3 pins of the same template.

        Ensures visual diversity by avoiding repetition. If all variants
        were used recently, picks randomly.

        Args:
            template_name: The template type.
            recent_variants: List of variant letters used recently
                             (most recent first), e.g. ["A", "C", "B"].

        Returns:
            Selected variant letter ("A", "B", or "C").
        """
        config = TEMPLATE_CONFIGS.get(template_name)
        if not config:
            return "A"

        all_variants = config["variants"]

        if not recent_variants:
            return random.choice(all_variants)

        # Find variants not used in the last 3
        recent_set = set(recent_variants[:3])
        available = [v for v in all_variants if v not in recent_set]

        if available:
            return random.choice(available)

        # All were used recently — pick the least recently used
        # (last in the recent list = used longest ago)
        for v in reversed(recent_variants):
            if v in all_variants:
                return v

        return random.choice(all_variants)

    def get_available_templates(self) -> list[dict]:
        """List all available pin templates and their variants.

        Returns:
            List of template info dicts.
        """
        result = []
        for name, config in TEMPLATE_CONFIGS.items():
            template_dir = self.templates_dir / name
            result.append({
                "name": name,
                "variants": config["variants"],
                "description": config["description"],
                "variables": config["variables"],
                "html_exists": (template_dir / "template.html").exists(),
                "css_exists": (template_dir / "styles.css").exists(),
            })
        return result


# ============================================================================
# Synchronous convenience function (kept for backward compat)
# ============================================================================

def render_pin_sync(
    template_name: str,
    variant: str,
    context: dict[str, Any],
    output_path: Optional[Path] = None,
) -> Path:
    """Render a single pin (synchronous). Kept for backward compatibility."""
    assembler = PinAssembler()
    return assembler.render_pin(template_name, variant, context, output_path)


# ============================================================================
# Standalone test — render one example pin per template with sample data
# ============================================================================

def _run_test_renders():
    """Render one example pin per template variant for testing."""
    output_dir = _PROJECT_ROOT / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    assembler = PinAssembler()

    # Sample contexts for each template
    test_specs = [
        # Recipe Pin — all 3 variants
        {
            "template_name": "recipe-pin",
            "variant": "A",
            "context": {
                "headline": "One-Pan Lemon Herb Chicken",
                "subtitle": "Ready in 30 Minutes",
            },
        },
        {
            "template_name": "recipe-pin",
            "variant": "B",
            "context": {
                "headline": "Creamy Tuscan Sausage Pasta",
                "subtitle": "20 Minutes. One Skillet.",
            },
        },
        {
            "template_name": "recipe-pin",
            "variant": "C",
            "context": {
                "headline": "Sheet Pan Honey Garlic Salmon",
                "subtitle": "Weeknight dinner, elevated.",
            },
        },

        # Tip Pin — all 3 variants
        {
            "template_name": "tip-pin",
            "variant": "A",
            "context": {
                "headline": "5 Dinners. 1 List. Zero Thinking.",
                "bullet_1": "Plan your entire week in 2 minutes",
                "bullet_2": "One grocery trip covers every meal",
                "bullet_3": "Your family votes before you cook",
            },
        },
        {
            "template_name": "tip-pin",
            "variant": "B",
            "context": {
                "headline": "Stop Being the Short-Order Cook",
                "bullet_1": "Let everyone weigh in on the plan",
                "bullet_2": "Plan once, cook once, done",
                "bullet_3": "",
            },
        },
        {
            "template_name": "tip-pin",
            "variant": "C",
            "context": {
                "headline": "Meal Planning Doesn't Have to Be Hard",
                "bullet_1": "Pick your family's dietary needs",
                "bullet_2": "Get a personalized weekly plan",
                "bullet_3": "Groceries ordered in one tap",
            },
        },

        # Listicle Pin — all 3 variants
        {
            "template_name": "listicle-pin",
            "variant": "A",
            "context": {
                "number": "7",
                "headline": "Easy Weeknight Dinners Your Family Will Love",
                "list_items": [
                    "One-Pan Lemon Herb Chicken",
                    "Creamy Tuscan Sausage Pasta",
                    "Slow Cooker Pulled Pork Tacos",
                    "Sheet Pan Honey Garlic Salmon",
                    "15-Minute Beef & Broccoli",
                    "Chicken Thigh Grain Bowls",
                    "Black Bean Enchiladas",
                ],
            },
        },
        {
            "template_name": "listicle-pin",
            "variant": "B",
            "context": {
                "number": "5",
                "headline": "High-Protein Dinners Even Kids Will Eat",
                "list_items": [
                    "Turkey Taco Lettuce Wraps",
                    "Salmon & Sweet Potato Sheet Pan",
                    "Lentil Bolognese",
                    "Egg Fried Rice with Veggies",
                    "Greek Chicken Sheet Pan",
                ],
            },
        },
        {
            "template_name": "listicle-pin",
            "variant": "C",
            "context": {
                "number": "5",
                "headline": "Dinners Under 30 Minutes",
                "list_items": [
                    "Chicken Stir Fry",
                    "Pasta Primavera",
                    "Beef Tacos",
                    "Shrimp Fried Rice",
                    "Caprese Chicken",
                ],
            },
        },

        # Problem-Solution Pin — all 3 variants
        {
            "template_name": "problem-solution-pin",
            "variant": "A",
            "context": {
                "problem_text": "Everyone has an opinion about dinner.",
                "solution_text": "What if they gave it before you cooked?",
            },
        },
        {
            "template_name": "problem-solution-pin",
            "variant": "B",
            "context": {
                "problem_text": "Hello Fresh picks your dinners.",
                "solution_text": "What if your family did?",
            },
        },
        {
            "template_name": "problem-solution-pin",
            "variant": "C",
            "context": {
                "problem_text": "You plan. You cook. They complain.",
                "solution_text": "Give them a vote before you shop.",
            },
        },

        # Infographic Pin — all 3 variants
        {
            "template_name": "infographic-pin",
            "variant": "A",
            "context": {
                "title": "How to Meal Plan in 5 Easy Steps",
                "steps": [
                    {"number": "1", "text": "Set your family's dietary preferences"},
                    {"number": "2", "text": "Choose how many nights to plan"},
                    {"number": "3", "text": "Get personalized recipe suggestions"},
                    {"number": "4", "text": "Let your family vote on the plan"},
                    {"number": "5", "text": "Order groceries with one tap"},
                ],
                "footer_text": "Your whole week, handled.",
            },
        },
        {
            "template_name": "infographic-pin",
            "variant": "B",
            "context": {
                "title": "The Weekly Dinner System",
                "steps": [
                    {"number": "1", "text": "Set preferences and restrictions"},
                    {"number": "2", "text": "Review personalized meal plan"},
                    {"number": "3", "text": "Family votes on the meals"},
                    {"number": "4", "text": "Grocery list auto-generated"},
                    {"number": "5", "text": "Order via Instacart in one tap"},
                    {"number": "6", "text": "Cook with confidence all week"},
                ],
                "footer_text": "Dinner, decided.",
            },
        },
        {
            "template_name": "infographic-pin",
            "variant": "C",
            "context": {
                "title": "From Chaos to Calm in 5 Steps",
                "steps": [
                    {"number": "1", "text": "Tell us about your family's tastes"},
                    {"number": "2", "text": "Get a personalized weekly plan"},
                    {"number": "3", "text": "Everyone votes via Dinner Draft"},
                    {"number": "4", "text": "Groceries ordered automatically"},
                    {"number": "5", "text": "Cook what everyone already agreed on"},
                ],
                "footer_text": "No more 5 PM panic.",
            },
        },
    ]

    print(f"\nRendering {len(test_specs)} test pins to {output_dir}/\n")

    # Use batch rendering (single browser instance for all pins)
    results = assembler.render_batch(test_specs, output_dir=output_dir)

    for spec, result_path in zip(test_specs, results):
        tname = spec["template_name"]
        var = spec["variant"]
        filename = f"{tname}_{var}.png"

        if result_path and result_path.exists():
            size_kb = result_path.stat().st_size / 1024
            print(f"  [OK] {filename} ({size_kb:.1f} KB)")
        else:
            print(f"  [FAIL] {filename}")

    print(f"\nDone. Output in: {output_dir}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Print available templates
    assembler = PinAssembler()
    print("Available Pin Templates:")
    print("=" * 60)
    for t in assembler.get_available_templates():
        status = "READY" if t["html_exists"] and t["css_exists"] else "MISSING"
        print(f"  [{status}] {t['name']}")
        print(f"           Variants: {', '.join(t['variants'])}")
        print(f"           Variables: {', '.join(t['variables'])}")
        print(f"           {t['description']}")
        print()

    # Run test renders
    print("\nStarting test renders...")
    print("(Requires: npm install puppeteer)\n")

    try:
        _run_test_renders()
    except Exception as e:
        print(f"\nTest render failed: {e}")
        print("Make sure Puppeteer is installed: cd to project root && npm install puppeteer")
