# Visual Pin Template System — Build Report

**Date:** 2026-02-20
**Builder:** Agent 2 (Visual Templates + Pin Assembler)
**Status:** Complete — ready for integration testing

---

## 1. Templates and Variants Created

All 5 pin template types are implemented with 3 variants each (15 total variant layouts). Every template follows the 1000x1500px (2:3) canvas specification with content within the center 80% safe zone.

### Recipe Pin (`templates/pins/recipe-pin/`)

The most-used template. Food photography dominant.

| Variant | Layout | Best For |
|---------|--------|----------|
| **A** | Bottom bar overlay: photo fills top 68%, green overlay bar bottom 38% with gradient bridge. White text on primary green. | Default for all recipe pins — classic food blog pin look |
| **B** | Side panel: cream text panel left 45%, image right 55%. Dark text on warm cream background. | Horizontal food shots, when a different composition is needed |
| **C** | Full bleed: image covers entire canvas with dark gradient from bottom. Text floats over gradient at bottom. | Hero shots, dramatic food photography |

**Variables:** `hero_image_url`, `headline`, `subtitle`

### Tip/How-To Pin (`templates/pins/tip-pin/`)

Text-heavier design for informational content. Value is in the words.

| Variant | Layout | Best For |
|---------|--------|----------|
| **A** | Centered text over dimmed background image (62% overlay). "Tips & Advice" label, headline, divider, bullet points. | General tips with a lifestyle background photo |
| **B** | Top/bottom split: image top 40%, dark green text section bottom 60%. | When you have a good background image but need substantial text |
| **C** | Full branded graphic — no photo. Deep green gradient with subtle accent radials, bullet cards with left accent border. | Template-only (Tier 3) pins, pure information design |

**Variables:** `background_image_url`, `headline`, `bullet_1`, `bullet_2`, `bullet_3` (optional)

### Listicle Pin (`templates/pins/listicle-pin/`)

Number-prominent list format. The large count number draws the eye.

| Variant | Layout | Best For |
|---------|--------|----------|
| **A** | Large accent-colored number with dimmed photo background. Number + headline + numbered list items below. | Full-length listicles with 5-7 items and a food photo |
| **B** | Image top 42% with floating coral circle badge (number). Cream background below with dark text list. | Shorter lists (3-5 items) where the image matters |
| **C** | Clean branded graphic (no photo). Large number, headline, numbered list items in subtle glass cards. | Template-only lists, dietary roundups, appliance-specific content |

**Variables:** `number`, `headline`, `list_items` (array of strings), `background_image_url`

### Problem-Solution Pin (`templates/pins/problem-solution-pin/`)

Split design creating visual tension between the problem and the solution.

| Variant | Layout | Best For |
|---------|--------|----------|
| **A** | Hard horizontal split — dark top (problem) with coral accent divider bar, warm cream bottom (solution). | Clean, high-contrast problem/solution statements |
| **B** | Full background image with gradient overlay (dark top fading to green bottom). Arrow connector with coral circle between sections. Solution in a glass card with left accent border. | When a lifestyle/background image adds emotional context |
| **C** | Single dark-green gradient with question-mark icon above problem, coral dot separator, accent-colored solution text. | Minimal design, strong typographic impact, no photo needed |

**Variables:** `problem_text`, `solution_text`, `background_image_url` (optional, used by variant B)

### Infographic Pin (`templates/pins/infographic-pin/`)

Structured information design. Brand colors forward, minimal photography.

| Variant | Layout | Best For |
|---------|--------|----------|
| **A** | Vertical numbered steps on warm cream background. Coral circle step numbers, accent top stripe, clean body text. | 3-6 step guides, lighter feel, approachable |
| **B** | 2-column grid on dark green gradient. Each step in a glass card with large accent number above text. | 4-6 steps with shorter text per step, denser information |
| **C** | Flowchart/timeline with vertical connector line on dark gradient. Timeline dots at each node, "Step N" labels in accent color. | Sequential processes, workflows, "here's how it works" content |

**Variables:** `title`, `steps` (array of `{number, text}` dicts), `footer_text`

### Shared Base Styles (`templates/pins/shared/base-styles.css`)

Central design system consumed by all templates:
- Google Fonts import (`DM Sans` + `DM Serif Display`)
- CSS custom properties for all brand colors, overlays, gradients, typography, spacing
- Typography scale (display, headline, subheadline, body, caption, label, number)
- Layout utilities (flex, positioning, z-index)
- Color utilities (text colors, backgrounds)
- Overlay utilities (dark, heavy, gradient variations)
- Brand logo/wordmark styles (text placeholder)
- Decorative elements (divider lines, accent bars, step circles, bullet markers)
- Background image utilities
- Text shadow utilities for readability over images

---

## 2. Brand Design Decisions

### Color Palette (Placeholders)

| Variable | Value | Rationale |
|----------|-------|-----------|
| `--brand-primary` | `#2D5F2D` (forest green) | Warm, natural, family-oriented. Green signals freshness/food without being clinical. Provides strong contrast for text overlays. |
| `--brand-secondary` | `#F5E6D3` (warm cream) | Kitchen warmth, approachable. Works as text background (variant B layouts) and subtle text color. |
| `--brand-accent` | `#E87040` (warm coral) | Energy without aggression. Appetite-stimulating (food industry standard). Used for CTAs, numbers, step indicators, divider accents. |
| `--brand-text-light` | `#FFFFFF` | Clean white for text on dark/green backgrounds. |
| `--brand-text-dark` | `#1A1A1A` | Near-black for text on light backgrounds. Warmer than pure black. |
| `--brand-bg` | `#FAFAF7` | Off-white with warmth for pin canvas base. |

These colors were chosen to work as a cohesive system: green backgrounds with white text, cream backgrounds with dark text, and coral as the accent that pops on both. They are purely placeholders stored as CSS custom properties for trivial replacement.

### Typography

| Role | Font | Weight | Size Range | Rationale |
|------|------|--------|-----------|-----------|
| Display headlines | DM Serif Display | 400 | 56-72px | Serif for elegance and authority. Friendly, not stuffy. Reads well at thumbnail scale. |
| Body, bullets, labels | DM Sans | 300-700 | 22-36px | Clean, modern, highly legible sans-serif. Pairs naturally with DM Serif Display (same design family). |
| Large numbers | DM Serif Display | 400 | 100-160px | Serif numbers have visual impact for listicle counts. |

At 300px thumbnail width (mobile feed), a 48px headline renders at ~14.4px equivalent — the minimum for legibility. All headlines are set at 56-72px base, providing comfortable readability at thumbnail scale.

### Layout Principles

1. **Safe zone enforcement:** All text content is inside `safe-zone` containers with 100px left/right padding (10% of 1000px width). Pinterest crops edges on some devices and in some feed views.

2. **Visual hierarchy:** Every pin follows a clear reading order: label/category (if present) > headline > supporting text > brand mark. The eye naturally flows top-to-bottom.

3. **Brand mark restraint:** The Slated wordmark is deliberately small (24-28px) and low-opacity (45-70%). It's present for brand recognition but not competing with the content. This follows the strategy's principle that pins should be useful content first, not advertisements.

4. **Variant diversity:** The 3 variants per template ensure visual variety in the Pinterest feed. Variant A is typically the "default" composition, B is a structural alternative (split/panel), and C is either a photography-free option or a dramatically different composition.

5. **Warm/inviting color treatment:** Overlays use the brand green (`rgba(45, 95, 45, ...)`) rather than pure black, keeping the warm, kitchen-friendly feel even on photo overlays.

---

## 3. How to Swap Brand Colors/Logo When Real Assets Arrive

### Colors

All colors are defined as CSS custom properties in `templates/pins/shared/base-styles.css` under the `:root` selector. To swap:

1. Open `templates/pins/shared/base-styles.css`
2. Find the `:root` block (line ~24-43)
3. Replace the hex values:

```css
:root {
    --brand-primary: #YOUR_PRIMARY;
    --brand-secondary: #YOUR_SECONDARY;
    --brand-accent: #YOUR_ACCENT;
    --brand-text-light: #YOUR_LIGHT;
    --brand-text-dark: #YOUR_DARK;
    --brand-bg: #YOUR_BG;
}
```

4. Also update the derived overlay colors (lines ~48-60) if the new colors require different alpha values for readability.

Every template consumes these variables — no template-specific CSS needs to change.

### Logo

Currently, all templates use a text wordmark:
```html
<span class="brand-logo-text logo-light">slated</span>
```

When a real logo image is available:

1. Place the logo file in `templates/pins/shared/brand-elements/`
2. In each template HTML, replace the `<span class="brand-logo-text ...">slated</span>` with:
```html
<img src="{{logo_url}}" alt="Slated" style="height: 36px; width: auto;">
```
3. Pass `logo_url` in the context dict when calling `render_pin()`, pointing to the local logo file path (the assembler will convert it to a data URI).

Alternatively, for a simpler approach: the `pin_assembler.py` already supports `{{logo_url}}` as a template variable. You could replace the text wordmark spans with an `<img>` tag using `{{logo_url}}` and the assembler will inject the path.

### Fonts

Fonts are loaded via Google Fonts `@import` in `base-styles.css` (line 1). To change:

1. Update the `@import url(...)` to reference your chosen fonts
2. Update `--font-primary` and `--font-display` custom properties
3. All templates inherit the change

**Important for headless rendering:** Google Fonts are loaded via network at render time. If you need offline rendering, download the font files to `shared/brand-elements/` and use `@font-face` declarations instead. See Section 5 for details.

---

## 4. How `pin_assembler.py` Works

### Architecture

```
pin_assembler.py
    |
    +-- PinAssembler class
    |     |
    |     +-- render_pin()         Main method: template + context -> PNG
    |     +-- render_batch()       Process multiple pins sequentially
    |     +-- select_variant()     Pick a variant not used recently
    |     +-- get_available_templates()  List all templates and status
    |     |
    |     +-- _load_template_html()    Read template.html
    |     +-- _load_css()              Read base-styles.css + template styles.css
    |     +-- _inline_css()            Replace {{styles}} with <style> block
    |     +-- _activate_variant()      Show selected variant, remove others
    |     +-- _inject_variables()      Replace all {{variable}} placeholders
    |     +-- _optimize_image()        Compress PNG, convert to JPEG if needed
    |     +-- _ensure_browser()        Lazy Playwright browser init
    |     +-- _close_browser()         Cleanup
    |
    +-- render_pin_sync()          Synchronous wrapper for non-async callers
    +-- _image_to_data_uri()       Convert local image to base64 data URI
    +-- _build_list_items_html()   Generate list item HTML for listicle pins
    +-- _build_infographic_steps_html()  Generate step HTML for infographic pins
```

### Render Pipeline (per pin)

1. **Load** template HTML and CSS files from disk
2. **Inline CSS** — replace `{{styles}}` placeholder with `<style>` block containing both base and template CSS
3. **Activate variant** — parse the HTML, show the selected variant div (remove `display:none`), strip all other variant divs entirely
4. **Inject variables** — replace `{{variable_name}}` placeholders with escaped content:
   - Image paths are converted to base64 data URIs (critical for headless rendering)
   - List items (listicle) and steps (infographic) are converted from arrays to HTML
   - Empty `bullet_3` triggers hiding of the optional third bullet
   - All text is HTML-escaped to prevent injection
5. **Render** — Playwright opens a headless Chromium page at 1000x1500px, loads the HTML, waits for fonts, takes a screenshot clipped to pin dimensions
6. **Optimize** — If PNG is >500KB, re-save with Pillow optimization. If still over, convert to JPEG at quality 88.

### How to Test Locally

```bash
# 1. Install dependencies
pip install playwright Pillow
python -m playwright install chromium

# 2. Run the standalone test (renders all 15 variants)
cd C:\dev\pinterest-pipeline
python -m src.pin_assembler

# Or run directly:
python src/pin_assembler.py

# 3. Check output
ls test_output/
# Should contain 15 PNG files:
#   recipe-pin_A.png, recipe-pin_B.png, recipe-pin_C.png
#   tip-pin_A.png, tip-pin_B.png, tip-pin_C.png
#   listicle-pin_A.png, listicle-pin_B.png, listicle-pin_C.png
#   problem-solution-pin_A.png, problem-solution-pin_B.png, problem-solution-pin_C.png
#   infographic-pin_A.png, infographic-pin_B.png, infographic-pin_C.png
```

The test renders use sample text only (no images) since stock photos require API keys. To test with images, provide local image file paths in the context dict.

### Usage in the Pipeline

```python
from src.pin_assembler import PinAssembler

assembler = PinAssembler()

# Render a single pin
path = await assembler.render_pin(
    template_name="recipe-pin",
    variant="A",
    context={
        "hero_image_url": "/path/to/food-photo.jpg",
        "headline": "One-Pan Lemon Herb Chicken",
        "subtitle": "Ready in 30 Minutes",
    },
    output_path=Path("output/my-pin.png"),
)

# Render a batch
paths = await assembler.render_batch(pin_specs=[
    {"template_name": "recipe-pin", "variant": "A", "context": {...}},
    {"template_name": "tip-pin", "variant": "C", "context": {...}},
    # ... more specs
], output_dir=Path("output/"))

# Select a variant that wasn't used recently
variant = PinAssembler.select_variant(
    template_name="recipe-pin",
    recent_variants=["A", "B"],  # Used A and B recently
)
# Returns "C" (the unused one)

# Synchronous wrapper (for non-async code)
from src.pin_assembler import render_pin_sync
path = render_pin_sync("recipe-pin", "A", {"headline": "Test", "subtitle": "Test"})

# Cleanup
await assembler.close()
```

### Variant Selection Logic

`select_variant()` prevents visual monotony:
- Takes a list of recently used variants for the same template type
- Returns a variant NOT in the last 3 uses
- If all 3 have been used recently, returns the least recently used one
- Randomizes selection when multiple options are available

---

## 5. Rendering Quality and Cross-Platform Consistency Concerns

### Font Loading

**Current approach:** Google Fonts loaded via `@import url(...)` in CSS. Playwright will make a network request to fonts.googleapis.com during rendering.

**Concern:** On GitHub Actions, the first render after a cold start may be slow (~2-3s for font download). The 500ms `wait_for_timeout` after `set_content` should cover this in most cases, but it is not guaranteed.

**Mitigation options if fonts fail to load:**
1. Increase `wait_for_timeout` to 1000-1500ms
2. Download font files and use `@font-face` with local file paths (most reliable for CI)
3. Use `page.wait_for_function()` to detect font loading completion via the Font Loading API

**Recommendation:** If test renders show missing/fallback fonts, switch to locally bundled font files. The performance cost of the extra wait time is negligible since we render ~28 pins per batch (once per week).

### Image Handling

All images are converted to base64 data URIs before injection. This eliminates any dependency on file:// protocol support or network access at render time. The tradeoff is memory: a 500KB image becomes ~670KB as base64. For 28 pins per batch this is well within Playwright's memory limits.

### Color Consistency

Playwright's Chromium uses the sRGB color space by default. Colors will render identically across macOS, Windows, and Linux. The `--disable-gpu` flag prevents GPU-accelerated rendering which could introduce platform-specific color shifts.

### Text Rendering

The `--font-render-hinting=none` Chromium flag disables system-specific font hinting, producing more consistent text rendering across platforms. Text may appear slightly different from what you see in a desktop browser, but all renders from Playwright will be internally consistent.

### Known Limitations

1. **No text wrapping intelligence:** If a headline exceeds the available width, CSS handles wrapping automatically. But very long headlines (9+ words) may overflow on variant B (side panel) layouts. The content generation system should enforce the 6-8 word maximum.

2. **Empty image URLs:** When no hero/background image is provided (e.g., template-only Tier 3 pins), the background is transparent/empty. Variants A and B for recipe and listicle pins are designed to have images. The assembler does not error on missing images but the result may look incomplete. Use variant C (no-photo) variants for Tier 3 content.

3. **PNG file size:** Pins with large photographic images may exceed 500KB. The optimizer handles this by converting to JPEG, but the output path extension changes from `.png` to `.jpg`. Downstream code should handle both.

---

## 6. Playwright Dependencies for GitHub Actions

### Required Setup in GitHub Actions Workflow

```yaml
# In generate-content.yml or wherever pin rendering runs

jobs:
  generate:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Install Playwright Chromium
        run: python -m playwright install --with-deps chromium
        # The --with-deps flag installs system-level dependencies
        # (libnss3, libatk1.0, libcups2, etc.) required on Ubuntu

      - name: Generate pin images
        run: python -m src.generate_pin_content
```

### Key Details

1. **`python -m playwright install --with-deps chromium`** installs:
   - The Chromium browser binary (~150MB)
   - All required system libraries on Ubuntu (libnss3, libatk-bridge2.0, libcups2, libxcomposite1, libxrandr2, etc.)

2. **The `--with-deps` flag is critical on GitHub Actions.** Without it, Playwright installs the browser but the system libraries are missing, causing launch failures.

3. **Disk space:** Chromium binary is ~150MB. GitHub Actions runners have ~14GB free — not a concern.

4. **Caching:** To speed up subsequent runs, cache the Playwright browser:
```yaml
      - name: Cache Playwright browsers
        uses: actions/cache@v4
        with:
          path: ~/.cache/ms-playwright
          key: playwright-${{ runner.os }}-${{ hashFiles('requirements.txt') }}

      - name: Install Playwright (cached)
        run: python -m playwright install --with-deps chromium
```

5. **Runtime:** Each pin render takes ~1-2 seconds (dominated by font loading on first render, then ~0.5s per subsequent render with warm browser). A batch of 28 pins should complete in under 60 seconds.

6. **Memory:** Each pin render uses ~50-100MB of browser memory. With sequential rendering (current implementation), peak memory usage stays under 500MB — well within GitHub Actions' 7GB limit.

7. **Alternative: `mcr.microsoft.com/playwright/python` Docker image.** If dependency installation becomes flaky, Playwright provides pre-built Docker images with all dependencies pre-installed. This adds ~1-2 minutes to workflow startup but eliminates dependency issues entirely.

---

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `templates/pins/shared/base-styles.css` | Replaced | Full design system with CSS custom properties, typography, utilities |
| `templates/pins/recipe-pin/template.html` | Replaced | 3 variants (A: bottom bar, B: side panel, C: full bleed) |
| `templates/pins/recipe-pin/styles.css` | Replaced | Complete variant-specific styling |
| `templates/pins/tip-pin/template.html` | Replaced | 3 variants (A: centered over image, B: split, C: branded graphic) |
| `templates/pins/tip-pin/styles.css` | Replaced | Complete variant-specific styling |
| `templates/pins/listicle-pin/template.html` | Replaced | 3 variants (A: large number, B: badge, C: numbered list) |
| `templates/pins/listicle-pin/styles.css` | Replaced | Complete variant-specific styling |
| `templates/pins/problem-solution-pin/template.html` | Replaced | 3 variants (A: hard split, B: with image, C: single color) |
| `templates/pins/problem-solution-pin/styles.css` | Replaced | Complete variant-specific styling |
| `templates/pins/infographic-pin/template.html` | Replaced | 3 variants (A: vertical steps, B: grid, C: timeline) |
| `templates/pins/infographic-pin/styles.css` | Replaced | Complete variant-specific styling |
| `src/pin_assembler.py` | Replaced | Full implementation with Playwright rendering, batch support, variant selection |
| `REPORTS/visual-pipeline-report.md` | Created | This report |

**Not modified:** `src/apis/image_stock.py` — the interface was already suitable. The pin assembler accepts image paths from any source (stock API, AI generation, or local files) via the context dict.
