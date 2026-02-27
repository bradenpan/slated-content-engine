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
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional

from src.paths import PROJECT_ROOT, TEMPLATES_DIR as _BASE_TEMPLATES_DIR
from src.config import PIN_WIDTH, PIN_HEIGHT, MAX_PNG_SIZE

logger = logging.getLogger(__name__)

# Pin-specific templates subdirectory
TEMPLATES_DIR = _BASE_TEMPLATES_DIR / "pins"
SHARED_DIR = TEMPLATES_DIR / "shared"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "test_output"

# Path to the Node.js render script
RENDER_SCRIPT = PROJECT_ROOT / "render_pin.js"

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
    for i, item in enumerate(items[:5], 1):
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
            f'  <span class="list-item-text list-item-more-text">...and more</span>'
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
                'class="recipe-time-badge recipe-time-badge-dark"',
                'class="recipe-time-badge recipe-time-badge-dark hidden"'
            )
            result = result.replace(
                'class="recipe-time-badge"',
                'class="recipe-time-badge hidden"'
            )

        # Hide CTA if no cta_text provided
        if not context.get("cta_text"):
            result = result.replace('class="pin-cta pin-cta-light"', 'class="pin-cta pin-cta-light hidden"')
            result = result.replace('class="pin-cta"', 'class="pin-cta hidden"')

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

            # Step 7: Strip AI metadata and apply anti-detection post-processing
            from src.image_cleaner import clean_image
            clean_image(output_path)

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



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Print available templates
    assembler = PinAssembler()
    print("Available Pin Templates:")
    print("=" * 60)
    for name, config in TEMPLATE_CONFIGS.items():
        template_dir = assembler.templates_dir / name
        html_exists = (template_dir / "template.html").exists()
        css_exists = (template_dir / "styles.css").exists()
        status = "READY" if html_exists and css_exists else "MISSING"
        print(f"  [{status}] {name}")
        print(f"           Variants: {', '.join(config['variants'])}")
        print(f"           Variables: {', '.join(config['variables'])}")
        print(f"           {config['description']}")
        print()
