"""
Pin Image Assembler — HTML/CSS Template to Rendered PNG

Takes an HTML/CSS pin template, injects dynamic content (hero image, title
text, branding), and renders it to a 1000x1500px PNG image using Playwright
(headless Chromium).

Pin templates are in templates/pins/ with subdirectories per template type:
- recipe-pin/ — Food photo top 60-70%, overlay bar bottom 30-40%
- tip-pin/ — Lifestyle background, heavier text overlay
- listicle-pin/ — Collage or single image with strong overlay
- problem-solution-pin/ — Split or gradient design
- infographic-pin/ — Minimal background, multiple text blocks

Each template has 3 visual variants (A, B, C) in a single HTML file.
The assembler selects the active variant, injects content, inlines CSS,
and renders via Playwright screenshot.

All pins are 1000x1500px (2:3 ratio) with text in the center 80%
safe zone. Text must be readable at ~300px thumbnail width.
"""

import asyncio
import base64
import html as html_module
import json
import logging
import os
import random
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Resolve paths relative to this file's location
_SRC_DIR = Path(__file__).parent
_PROJECT_ROOT = _SRC_DIR.parent
TEMPLATES_DIR = _PROJECT_ROOT / "templates" / "pins"
SHARED_DIR = TEMPLATES_DIR / "shared"
DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "test_output"

# Pin canvas dimensions
PIN_WIDTH = 1000
PIN_HEIGHT = 1500

# Maximum output PNG file size target (bytes)
MAX_PNG_SIZE = 500 * 1024  # 500 KB

# Valid template names and their variant labels
TEMPLATE_CONFIGS = {
    "recipe-pin": {
        "variants": ["A", "B", "C"],
        "description": "Food photo with text overlay — recipe name + descriptor",
        "variables": ["hero_image_url", "headline", "subtitle"],
    },
    "tip-pin": {
        "variants": ["A", "B", "C"],
        "description": "Lifestyle background with tip headline + bullet points",
        "variables": ["background_image_url", "headline", "bullet_1", "bullet_2", "bullet_3"],
    },
    "listicle-pin": {
        "variants": ["A", "B", "C"],
        "description": "Number-prominent list with optional background image",
        "variables": ["number", "headline", "list_items", "background_image_url"],
    },
    "problem-solution-pin": {
        "variants": ["A", "B", "C"],
        "description": "Split design — problem statement top, solution bottom",
        "variables": ["problem_text", "solution_text", "background_image_url"],
    },
    "infographic-pin": {
        "variants": ["A", "B", "C"],
        "description": "Structured steps/info on branded background — minimal photography",
        "variables": ["title", "steps", "footer_text"],
    },
}


class PinAssemblerError(Exception):
    """Raised when pin assembly or rendering fails."""
    pass


def _image_to_data_uri(image_path: str) -> str:
    """Convert a local image file path to a base64 data URI.

    This is critical for Playwright rendering — external file:// URLs
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


def _build_list_items_html(items: list[str], variant: str) -> str:
    """Build HTML for listicle pin list items based on variant."""
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


class PinAssembler:
    """Assembles pin images from HTML/CSS templates + dynamic content.

    Uses Playwright (headless Chromium) to render HTML templates to PNG.
    Templates are loaded from the templates/pins/ directory, CSS is inlined,
    and variables are injected before rendering.
    """

    def __init__(self, templates_dir: Optional[Path] = None):
        """Initialize the pin assembler.

        Args:
            templates_dir: Override path to templates/pins/ directory.
                           Defaults to the standard project location.
        """
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self.shared_dir = self.templates_dir / "shared"
        self._browser = None
        self._playwright = None

    async def _ensure_browser(self):
        """Lazily initialize Playwright browser."""
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--font-render-hinting=none",
                ]
            )

    async def _close_browser(self):
        """Close browser and Playwright."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

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
            if isinstance(items, list):
                items_html = _build_list_items_html(items, variant)
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

        return result

    async def render_pin(
        self,
        template_name: str,
        variant: str,
        context: dict[str, Any],
        output_path: Optional[Path] = None,
    ) -> Path:
        """Render a pin image from template + context data.

        Args:
            template_name: One of the TEMPLATE_CONFIGS keys.
            variant: "A", "B", or "C".
            context: Dictionary of template variables.
            output_path: Where to save the PNG. Auto-generated if None.

        Returns:
            Path to the rendered PNG file.

        Raises:
            PinAssemblerError: If template not found or rendering fails.
        """
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
            # Step 1: Load HTML and CSS
            raw_html = self._load_template_html(template_name)
            base_css, template_css = self._load_css(template_name)

            # Step 2: Inline CSS
            html_with_css = self._inline_css(raw_html, base_css, template_css)

            # Step 3: Activate the selected variant
            html_active = self._activate_variant(html_with_css, variant)

            # Step 4: Inject template variables
            final_html = self._inject_variables(html_active, template_name, variant, context)

            # Step 5: Render to PNG via Playwright
            await self._ensure_browser()
            page = await self._browser.new_page(
                viewport={"width": PIN_WIDTH, "height": PIN_HEIGHT},
                device_scale_factor=1,
            )

            # Set the HTML content with a file:// base URL so local resources
            # can be resolved, but images should already be data URIs
            await page.set_content(final_html, wait_until="networkidle")

            # Wait a brief moment for fonts to load
            await page.wait_for_timeout(500)

            # Screenshot the full page at pin dimensions
            await page.screenshot(
                path=str(output_path),
                clip={"x": 0, "y": 0, "width": PIN_WIDTH, "height": PIN_HEIGHT},
                type="png",
            )

            await page.close()

            # Step 6: Optimize file size
            self._optimize_image(output_path)

            logger.info("Pin rendered successfully: %s (%d bytes)", output_path, output_path.stat().st_size)
            return output_path

        except PinAssemblerError:
            raise
        except Exception as e:
            raise PinAssemblerError(f"Failed to render {template_name} variant {variant}: {e}") from e

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

            # Replace PNG with JPEG if smaller
            if jpeg_path.stat().st_size < file_size:
                image_path.unlink()
                jpeg_path.rename(image_path.with_suffix(".jpg"))
                logger.info(
                    "Converted to JPEG: %d bytes (was %d bytes PNG)",
                    jpeg_path.stat().st_size if jpeg_path.exists() else 0,
                    file_size,
                )
            else:
                jpeg_path.unlink()

        except ImportError:
            logger.warning("Pillow not installed — skipping image optimization")
        except Exception as e:
            logger.warning("Image optimization failed: %s", e)

    async def render_batch(
        self,
        pin_specs: list[dict[str, Any]],
        output_dir: Optional[Path] = None,
    ) -> list[Path]:
        """Render multiple pins in batch.

        Args:
            pin_specs: List of dicts, each containing:
                - template_name: str
                - variant: str
                - context: dict of template variables
                - output_filename: str (optional, auto-generated if missing)
            output_dir: Directory for all output files.

        Returns:
            List of Paths to rendered images.
        """
        if output_dir is None:
            output_dir = DEFAULT_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        results = []
        for i, spec in enumerate(pin_specs):
            template_name = spec["template_name"]
            variant = spec["variant"]
            context = spec.get("context", {})
            filename = spec.get(
                "output_filename",
                f"{template_name}_{variant}_{i:03d}.png"
            )
            output_path = output_dir / filename

            try:
                path = await self.render_pin(
                    template_name=template_name,
                    variant=variant,
                    context=context,
                    output_path=output_path,
                )
                results.append(path)
            except PinAssemblerError as e:
                logger.error("Failed to render pin %d (%s): %s", i, template_name, e)
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

    async def close(self):
        """Clean up Playwright resources."""
        await self._close_browser()


# ============================================================================
# Synchronous wrapper for non-async callers
# ============================================================================

def render_pin_sync(
    template_name: str,
    variant: str,
    context: dict[str, Any],
    output_path: Optional[Path] = None,
) -> Path:
    """Synchronous wrapper around PinAssembler.render_pin().

    Convenience function for callers that don't use async/await.
    """
    assembler = PinAssembler()
    try:
        result = asyncio.run(_render_and_close(assembler, template_name, variant, context, output_path))
        return result
    except RuntimeError:
        # If an event loop is already running (e.g., Jupyter), use nest_asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            _render_and_close(assembler, template_name, variant, context, output_path)
        )


async def _render_and_close(assembler, template_name, variant, context, output_path):
    """Helper to render then close."""
    try:
        return await assembler.render_pin(template_name, variant, context, output_path)
    finally:
        await assembler.close()


# ============================================================================
# Standalone test — render one example pin per template with sample data
# ============================================================================

async def _run_test_renders():
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

    for spec in test_specs:
        tname = spec["template_name"]
        var = spec["variant"]
        filename = f"{tname}_{var}.png"
        output_path = output_dir / filename

        try:
            path = await assembler.render_pin(
                template_name=tname,
                variant=var,
                context=spec["context"],
                output_path=output_path,
            )
            size_kb = path.stat().st_size / 1024
            print(f"  [OK] {filename} ({size_kb:.1f} KB)")
        except Exception as e:
            print(f"  [FAIL] {filename}: {e}")

    await assembler.close()
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
    print("(Requires playwright install: python -m playwright install chromium)\n")

    try:
        asyncio.run(_run_test_renders())
    except Exception as e:
        print(f"\nTest render failed: {e}")
        print("Make sure Playwright is installed: pip install playwright && python -m playwright install chromium")
