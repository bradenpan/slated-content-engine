# Pin Template Improvement Plan

**Date:** 2026-02-26
**Status:** Planned
**Based on:** Template audit findings + Pinterest design research report

---

## Table of Contents

1. [Part 1: Content Extraction Fixes (HIGH PRIORITY)](#part-1-content-extraction-fixes)
2. [Part 2: Font Size Improvements (HIGH PRIORITY)](#part-2-font-size-improvements)
3. [Part 3: CTA Elements (MEDIUM PRIORITY)](#part-3-cta-elements)
4. [Part 4: Template-Specific Improvements (MEDIUM PRIORITY)](#part-4-template-specific-improvements)
5. [Part 5: Pin Copy Prompt Overhaul (HIGH PRIORITY)](#part-5-pin-copy-prompt-overhaul)
6. [Part 6: Implementation Order](#part-6-implementation-order)

---

## Part 1: Content Extraction Fixes

**Priority: HIGH**
**Root Cause:** The `pin_copy.md` prompt generates a flat `text_overlay` with only `headline` and `sub_text`. All template-specific content (bullets, list items, steps, problem/solution text) is reverse-engineered from the `description` field by splitting on sentence boundaries. This produces 1-2 usable items when 3-5 are needed.

The fix requires changes at two levels: the prompt must generate structured content per template type, and the extraction code must consume that structured content (with robust fallbacks for when the AI returns the old format).

### 1.1 New `text_overlay` Schema

The `text_overlay` JSON object in the prompt output must be extended per template type. The AI should produce different fields depending on the template.

**Universal fields (all templates):**
```json
{
  "headline": "6-8 Word Headline",
  "sub_text": "Optional 3-5 word sub-line"
}
```

**recipe-pin additions:**
```json
{
  "headline": "Sheet Pan Honey Garlic Salmon",
  "sub_text": "One Pan / 25 Min",
  "time_badge": "25 min",
  "cta_text": "Get the Recipe"
}
```

**tip-pin additions:**
```json
{
  "headline": "5 Dinners. 1 List. Zero Thinking.",
  "sub_text": null,
  "bullet_1": "Plan your whole week in 2 minutes",
  "bullet_2": "One grocery trip covers every meal",
  "bullet_3": "Your family votes before you cook",
  "category_label": "Meal Planning Tips",
  "cta_text": "Save These Tips"
}
```

**listicle-pin additions:**
```json
{
  "headline": "Easy Weeknight Dinners Your Family Will Love",
  "sub_text": null,
  "number": "7",
  "list_items": [
    "One-Pan Lemon Herb Chicken",
    "Creamy Tuscan Sausage Pasta",
    "Slow Cooker Pulled Pork Tacos",
    "Sheet Pan Honey Garlic Salmon",
    "15-Minute Beef & Broccoli"
  ],
  "cta_text": "See All 7 Recipes"
}
```

**problem-solution-pin additions:**
```json
{
  "headline": "Everyone has an opinion about dinner.",
  "sub_text": "What if they gave it before you cooked?",
  "problem_text": "Everyone has an opinion about dinner.",
  "solution_text": "What if they gave it before you cooked?",
  "cta_text": "Here's How"
}
```

**infographic-pin additions:**
```json
{
  "headline": "How to Meal Plan in 5 Easy Steps",
  "sub_text": null,
  "category_label": "Meal Prep Guide",
  "steps": [
    {"number": "1", "text": "Set your family's dietary preferences"},
    {"number": "2", "text": "Choose how many nights to plan"},
    {"number": "3", "text": "Get personalized recipe suggestions"},
    {"number": "4", "text": "Let your family vote on the plan"},
    {"number": "5", "text": "Order groceries with one tap"}
  ],
  "footer_text": "Your whole week, handled.",
  "cta_text": "Save This Guide"
}
```

### 1.2 Extraction Code Changes

**File:** `src/generate_pin_content.py`
**Functions to modify:** `build_template_context()` (lines 482-549), `_extract_bullets()` (lines 552-573), `_extract_list_items()` (lines 582-590), `_extract_steps()` (lines 593-606)

#### Strategy: Prefer structured fields, fall back to extraction

The `build_template_context()` function should first look for the new structured fields in `text_overlay`. If the AI produced them (i.e., the new prompt was used), use them directly. If not (old-format fallback), use the existing extraction functions as a last resort.

#### Detailed changes per template type:

**tip-pin (`build_template_context`, lines 523-529):**

Current:
```python
if template_type == "tip-pin":
    bullets = _extract_bullets(description, overlay_sub_text, pin_topic)
    for i, bullet in enumerate(bullets[:3], 1):
        context[f"bullet_{i}"] = bullet
```

New:
```python
if template_type == "tip-pin":
    # Prefer structured bullets from text_overlay
    if isinstance(text_overlay, dict) and text_overlay.get("bullet_1"):
        for i in range(1, 4):
            context[f"bullet_{i}"] = text_overlay.get(f"bullet_{i}", "")
    else:
        # Fallback: extract from description
        bullets = _extract_bullets(description, overlay_sub_text, pin_topic)
        for i, bullet in enumerate(bullets[:3], 1):
            context[f"bullet_{i}"] = bullet
    # Category label (new field)
    if isinstance(text_overlay, dict) and text_overlay.get("category_label"):
        context["category_label"] = text_overlay["category_label"]
    else:
        context["category_label"] = "Tips & Advice"
    # CTA text (new field)
    if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
        context["cta_text"] = text_overlay["cta_text"]
```

**listicle-pin (`build_template_context`, lines 531-535):**

Current:
```python
elif template_type == "listicle-pin":
    context["number"] = _extract_leading_number(overlay_headline)
    context["list_items"] = _extract_list_items(description, pin_topic)
```

New:
```python
elif template_type == "listicle-pin":
    # Prefer structured list_items from text_overlay
    if isinstance(text_overlay, dict) and text_overlay.get("list_items"):
        items = text_overlay["list_items"]
        # Enforce max 5 items on pin (with "...and more" for longer lists)
        if len(items) > 5:
            items = items[:5]
            # Truncation is handled by assembler: appends "...and more" row
        context["list_items"] = items
        context["has_more_items"] = isinstance(text_overlay.get("list_items"), list) and len(text_overlay["list_items"]) > 5
    else:
        # Fallback: extract from description
        context["list_items"] = _extract_list_items(description, pin_topic)
        context["has_more_items"] = False

    # Number: prefer explicit field, fall back to extraction from headline
    if isinstance(text_overlay, dict) and text_overlay.get("number"):
        context["number"] = str(text_overlay["number"])
    else:
        context["number"] = _extract_leading_number(overlay_headline)

    # CTA text
    if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
        context["cta_text"] = text_overlay["cta_text"]
```

**problem-solution-pin (`build_template_context`, lines 537-541):**

Current:
```python
elif template_type == "problem-solution-pin":
    context["problem_text"] = overlay_headline
    context["solution_text"] = overlay_sub_text or pin_copy.get("title", "")
```

New:
```python
elif template_type == "problem-solution-pin":
    # Prefer explicit problem_text/solution_text from text_overlay
    if isinstance(text_overlay, dict) and text_overlay.get("problem_text"):
        context["problem_text"] = text_overlay["problem_text"]
        context["solution_text"] = text_overlay.get("solution_text", overlay_sub_text or "")
    else:
        # Fallback: headline = problem, sub_text = solution
        context["problem_text"] = overlay_headline
        context["solution_text"] = overlay_sub_text or pin_copy.get("title", "")
    # Section labels (defaults ensure {{problem_label}} / {{solution_label}} never render empty)
    context["problem_label"] = text_overlay.get("problem_label", "The Problem") if isinstance(text_overlay, dict) else "The Problem"
    context["solution_label"] = text_overlay.get("solution_label", "The Answer") if isinstance(text_overlay, dict) else "The Answer"
    # CTA text
    if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
        context["cta_text"] = text_overlay["cta_text"]
```

**infographic-pin (`build_template_context`, lines 543-547):**

Current:
```python
elif template_type == "infographic-pin":
    context["title"] = overlay_headline or pin_copy.get("title", "")
    context["steps"] = _extract_steps(description)
    context["footer_text"] = overlay_sub_text or ""
```

New:
```python
elif template_type == "infographic-pin":
    context["title"] = overlay_headline or pin_copy.get("title", "")
    # Prefer structured steps from text_overlay
    if isinstance(text_overlay, dict) and text_overlay.get("steps"):
        steps = text_overlay["steps"]
        # Ensure each step is a dict with number and text
        if isinstance(steps, list) and all(isinstance(s, dict) for s in steps):
            context["steps"] = steps[:6]  # Max 6 steps
        else:
            context["steps"] = _extract_steps(description)
    else:
        context["steps"] = _extract_steps(description)
    # Footer text: prefer explicit field
    if isinstance(text_overlay, dict) and text_overlay.get("footer_text"):
        context["footer_text"] = text_overlay["footer_text"]
    else:
        context["footer_text"] = overlay_sub_text or ""
    # Category label (dynamic, keyword-targeted)
    if isinstance(text_overlay, dict) and text_overlay.get("category_label"):
        context["category_label"] = text_overlay["category_label"]
    else:
        context["category_label"] = "Step by Step"
    # CTA text
    if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
        context["cta_text"] = text_overlay["cta_text"]
```

**recipe-pin (add new block to `build_template_context`):**

Currently, recipe-pin has no special handling in `build_template_context()`. Add:
```python
if template_type == "recipe-pin":
    # Time badge (new field)
    if isinstance(text_overlay, dict) and text_overlay.get("time_badge"):
        context["time_badge"] = text_overlay["time_badge"]
    # CTA text
    if isinstance(text_overlay, dict) and text_overlay.get("cta_text"):
        context["cta_text"] = text_overlay["cta_text"]
```

### 1.3 Improved Fallback Extraction Functions

Even with the prompt changes, the extraction functions should be improved as a safety net.

**`_extract_bullets()` improvements:**
- Try splitting on `\n` first (in case the AI put line breaks in the description)
- Try splitting on `;` as a delimiter
- Try extracting text that starts with `-`, `*`, or numbers
- Only fall back to sentence-boundary splitting as a last resort
- Ensure at least 2 bullets are always produced (duplicate sub_text as bullet_1 if needed)

**`_extract_list_items()` improvements:**
- Same multi-strategy approach: newlines, semicolons, numbered patterns, then sentence boundaries
- Add an "...and more" item if the source list was truncated
- Ensure each item is under 60 characters (truncate with ellipsis if longer)

**`_extract_steps()` improvements:**
- Look for patterns like "Step 1:", "1.", "First," etc.
- Split on newlines before falling back to sentences
- Ensure each step text is concise (under 80 characters)

### 1.4 Fallback Summary Table

| Template | Primary Source | Fallback Source | Last Resort |
|---|---|---|---|
| recipe-pin | `text_overlay.headline` + `text_overlay.sub_text` | `pin_copy.title` | N/A |
| tip-pin | `text_overlay.bullet_1/2/3` | Description sentences | Duplicate headline fragments |
| listicle-pin | `text_overlay.list_items[]` | Description sentences | Generate from headline + topic |
| problem-solution-pin | `text_overlay.problem_text` + `text_overlay.solution_text` | `headline` + `sub_text` | `title` for solution |
| infographic-pin | `text_overlay.steps[]` | Description sentences | Generate 3 generic steps |

---

## Part 2: Font Size Improvements

**Priority: HIGH**

### 2.1 Current vs. Recommended Font Sizes

The guiding principle: at 300px thumbnail width (0.3x scale), every element carrying meaningful content must be readable.

| Element | Class | Current | Recommended | At 300px thumbnail | Rationale |
|---|---|---|---|---|---|
| Display headline | `.text-display` | 72px | 72px (no change) | ~22px | Already excellent |
| Main headline | `.text-headline` | 56px | 56px (no change) | ~17px | Good legibility |
| Subheadline | `.text-subheadline` | 36px | 36px (no change) | ~11px | Acceptable for secondary info |
| Body text / bullets | `.text-body` | 30px | 32px | ~10px | Borderline at 30px; 32px adds safety margin |
| List item text | `.list-item-text` | 26px | 28px | ~8.4px | Currently at lower readability bound |
| Caption | `.text-caption` | 24px | 24px (no change) | ~7px | Fine for non-essential (logo, footer) |
| Label | `.text-label` | 22px | 24px | ~7.2px | Slight bump for category labels |
| Infographic grid text | `.info-grid-text` | 24px | 26px | ~7.8px | Currently too small for content text |
| Infographic timeline text | `.info-timeline-text` | 26px | 28px | ~8.4px | Match the step text standard |

### 2.2 CSS Changes

**File: `templates/pins/shared/base-styles.css`**

Change `.text-body` (line 149-154):
```css
/* Current */
.text-body {
    font-family: var(--font-primary);
    font-size: 30px;
    font-weight: 400;
    line-height: 1.45;
}

/* New */
.text-body {
    font-family: var(--font-primary);
    font-size: 32px;
    font-weight: 400;
    line-height: 1.4;
}
```

Change `.text-label` (line 166-173):
```css
/* Current */
.text-label {
    font-family: var(--font-primary);
    font-size: 22px;
    font-weight: 600;
    line-height: 1.3;
    letter-spacing: 2px;
    text-transform: uppercase;
}

/* New */
.text-label {
    font-family: var(--font-primary);
    font-size: 24px;
    font-weight: 600;
    line-height: 1.3;
    letter-spacing: 2px;
    text-transform: uppercase;
}
```

**File: `templates/pins/listicle-pin/styles.css`**

Change `.list-item-text` (lines 32-36):
```css
/* Current */
.list-item-text {
    font-family: var(--font-primary);
    font-size: 26px;
    font-weight: 400;
    line-height: 1.35;
}

/* New */
.list-item-text {
    font-family: var(--font-primary);
    font-size: 28px;
    font-weight: 400;
    line-height: 1.35;
}
```

Change `.variant-c .list-item-number` (lines 205-208):
```css
/* Current */
.variant-c .list-item-number {
    color: var(--brand-accent);
    font-size: 28px;
}

/* New */
.variant-c .list-item-number {
    color: var(--brand-accent);
    font-size: 30px;
}
```

**File: `templates/pins/infographic-pin/styles.css`**

Change `.variant-b .info-grid-text` (lines 140-147):
```css
/* Current */
.variant-b .info-grid-text {
    font-family: var(--font-primary);
    font-size: 24px;
    font-weight: 400;
    line-height: 1.35;
    color: var(--brand-text-light);
    opacity: 0.9;
}

/* New */
.variant-b .info-grid-text {
    font-family: var(--font-primary);
    font-size: 26px;
    font-weight: 400;
    line-height: 1.35;
    color: var(--brand-text-light);
    opacity: 0.9;
}
```

Change `.variant-c .info-timeline-text` (lines 244-251):
```css
/* Current */
.variant-c .info-timeline-text {
    font-family: var(--font-primary);
    font-size: 26px;
    font-weight: 400;
    line-height: 1.4;
    color: var(--brand-text-light);
    opacity: 0.9;
}

/* New */
.variant-c .info-timeline-text {
    font-family: var(--font-primary);
    font-size: 28px;
    font-weight: 400;
    line-height: 1.4;
    color: var(--brand-text-light);
    opacity: 0.9;
}
```

### 2.3 Font Size Summary

Total changes: 5 CSS values across 3 files.
- `base-styles.css`: `.text-body` 30px -> 32px, `.text-label` 22px -> 24px
- `listicle-pin/styles.css`: `.list-item-text` 26px -> 28px, `.variant-c .list-item-number` 28px -> 30px
- `infographic-pin/styles.css`: `.info-grid-text` 24px -> 26px, `.info-timeline-text` 26px -> 28px

---

## Part 3: CTA Elements

**Priority: MEDIUM**
**Impact:** Pins with CTAs receive 80% more interactions (research report, Section 6).

### 3.1 CTA Text Options Per Template Type

| Template | Default CTA | Alternative CTAs |
|---|---|---|
| recipe-pin | "Get the Recipe" | "Try This Tonight", "Save for Dinner" |
| tip-pin | "Save These Tips" | "Read the Guide", "Try This Week" |
| listicle-pin | "See All [N] Recipes" | "Get the Full List", "Save for Later" |
| problem-solution-pin | "Here's How" | "Read More", "See the Solution" |
| infographic-pin | "Save This Guide" | "Pin for Reference", "Read the Full Guide" |

### 3.2 CTA Positioning

The CTA should appear **above the logo and below the main content** in every template variant. It should be a small, pill-shaped element, not an aggressive button.

**Position in visual hierarchy (bottom of each template):**
```
[main content area]
        |
   [CTA element]    <-- new
   [brand logo]
```

### 3.3 CTA HTML (Shared Pattern)

Add this HTML block to every template variant, positioned just above the brand-logo div:

```html
<div class="pin-cta">
    <span class="pin-cta-text">{{cta_text}}</span>
</div>
```

### 3.4 CTA CSS (Add to `base-styles.css`)

```css
/* === CTA Element === */
.pin-cta {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 12px 32px;
    border-radius: 24px;
    background-color: var(--brand-accent);
    margin-bottom: 16px;
    transition: opacity 0.2s;
}

.pin-cta-text {
    font-family: var(--font-primary);
    font-size: 24px;
    font-weight: 600;
    color: var(--brand-text-light);
    letter-spacing: 0.5px;
}

/* Light variant for templates with light backgrounds */
.pin-cta-light {
    background-color: var(--brand-primary);
}

/* PRIMARY: Hide CTA via class-based hiding (assembler adds .hidden when cta_text is empty) */
.pin-cta.hidden {
    display: none;
}

/* BACKUP: :empty selector as defense-in-depth. Note: this will NOT trigger when
   the CTA has a child <span>, so the assembler's class-based approach above is
   the actual mechanism. Kept only as a safeguard for edge cases. */
/* .pin-cta:empty, .pin-cta-text:empty { display: none; } */
```

The CTA pill uses the emerald accent color (`#059669`) on dark/image backgrounds and the amber primary (`#D97706`) on light backgrounds (like recipe-pin variant B and infographic-pin variant A which use the cream surface).

### 3.5 CTA Population

**How it gets populated:**
1. The `pin_copy.md` prompt (Part 5) instructs the AI to generate a `cta_text` field in `text_overlay`.
2. `build_template_context()` extracts `cta_text` from `text_overlay` and adds it to the context dict.
3. `pin_assembler.py` injects `{{cta_text}}` into the HTML.
4. If `cta_text` is empty or missing, the assembler adds a `hidden` class to the `.pin-cta` div (class-based hiding, same pattern as `tip-bullet-optional`). This is the primary hiding mechanism. The `:empty` CSS selector does NOT work here because the CTA div always contains a child `<span>`, so it is never truly empty.

**Changes to `pin_assembler.py`:**
- Add `"cta_text"` to the `simple_vars` list in `_inject_variables()` (line 329).
- **PRIMARY hiding mechanism:** Add class-based CTA hiding logic in `_inject_variables()` (similar to the `tip-bullet-optional` pattern):
```python
if not context.get("cta_text"):
    result = result.replace('class="pin-cta"', 'class="pin-cta hidden"')
```
This is required because the `:empty` CSS selector does not work on the CTA div -- it always contains a child `<span>` element, so `:empty` never triggers.

**Changes to `TEMPLATE_CONFIGS`:**
- Add `"cta_text"` to the `variables` list for every template type.

### 3.6 CTA Positioning Per Variant

For each template, the CTA div goes between the last content element and the brand-logo:

| Template | Variant A | Variant B | Variant C |
|---|---|---|---|
| recipe-pin | Inside `.recipe-a-content`, above brand-logo | Inside `.recipe-b-panel-inner`, above brand-logo | Inside `.recipe-c-content`, above brand-logo |
| tip-pin | Inside `.tip-a-bottom`, above brand-logo | Inside `.tip-b-text-inner`, above brand-logo | Inside `.tip-c-bottom`, above brand-logo |
| listicle-pin | Inside `.list-a-content`, above brand-logo | Inside `.list-b-text-inner`, above brand-logo | Inside `.list-c-content`, above brand-logo |
| problem-solution-pin | Inside `.ps-a-solution-inner`, above brand-logo | Inside `.ps-b-content`, above brand-logo | Inside `.ps-c-content`, above brand-logo |
| infographic-pin | Inside `.info-a-footer`, above brand-logo | Inside `.info-b-footer`, above brand-logo | Inside `.info-c-footer`, above brand-logo |

---

## Part 4: Template-Specific Improvements

### 4.1 recipe-pin

**HTML changes (`templates/pins/recipe-pin/template.html`):**

1. Add CTA element to all 3 variants (above brand-logo).
2. Add optional `{{time_badge}}` element to all 3 variants. Position: small badge in the top-right corner or integrated into the subtitle area.

**Time badge HTML (add to each variant's content area, near the subtitle):**
```html
<div class="recipe-time-badge">
    <span class="recipe-time-badge-text">{{time_badge}}</span>
</div>
```
Hiding is handled by the assembler (class-based), not by inline styles. See pin assembler changes below.

**CSS changes (`templates/pins/recipe-pin/styles.css`):**

Add time badge styles:
```css
/* Time/difficulty badge */
.recipe-time-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 20px;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.25);
    margin-top: 12px;
}

.recipe-time-badge-text {
    font-family: var(--font-primary);
    font-size: 22px;
    font-weight: 500;
    color: var(--brand-text-light);
    letter-spacing: 0.5px;
}

/* Dark text variant for light backgrounds (Variant B panel) */
.variant-b .recipe-time-badge {
    background: rgba(217, 119, 6, 0.1);
    border: 1px solid rgba(217, 119, 6, 0.25);
}

.variant-b .recipe-time-badge-text {
    color: var(--brand-primary);
}

/* Hide time badge when assembler adds .hidden class (no time_badge value) */
.recipe-time-badge.hidden {
    display: none;
}
```

**New TEMPLATE_CONFIGS variables:** `"cta_text"`, `"time_badge"`

**Pin assembler changes:**
- Add `"time_badge"` to `simple_vars` in `_inject_variables()`.
- Add class-based hiding logic in `_inject_variables()` (matches the existing `tip-bullet-optional` pattern):
```python
if template_name == "recipe-pin" and not context.get("time_badge"):
    result = result.replace('class="recipe-time-badge"', 'class="recipe-time-badge hidden"')
```

### 4.2 tip-pin

**HTML changes (`templates/pins/tip-pin/template.html`):**

1. Replace hardcoded category labels with `{{category_label}}` (Dynamic Category Labels -- SEO Quick Win):
   - Variant A line 36: `"Tips & Advice"` -> `{{category_label}}`
   - Variant C line 96: `"Meal Planning Tips"` -> `{{category_label}}`
   - Currently these labels are static and provide zero keyword signal. Making them dynamic means the AI generates a keyword-targeted label for each pin (e.g., "Weeknight Dinners", "Family Meal Prep", "Grocery Planning"), turning a decorative element into an SEO asset. Pinterest's computer vision reads text on pins, so keyword-rich labels directly improve discoverability.
2. Add CTA element to all 3 variants (above brand-logo).

**CSS changes:** None beyond the shared CTA styles.

**New TEMPLATE_CONFIGS variables:** `"category_label"`, `"cta_text"`

**Pin assembler changes:**
- Add `"category_label"` to `simple_vars` in `_inject_variables()` (line 329).
- Default `category_label` to `"Tips & Advice"` if not provided (in `build_template_context()`).

**Prompt changes (`prompts/pin_copy.md`):**
- The `category_label` field is already included in the tip-pin text_overlay schema (see Part 5.1). Ensure the template-specific instructions (Part 5.3) tell the AI to use the primary keyword as the category label when it fits naturally (2-3 words).

### 4.3 listicle-pin

**HTML changes (`templates/pins/listicle-pin/template.html`):**

1. Add CTA element to all 3 variants (above brand-logo).
2. No structural changes needed -- the `{{list_items}}` injection already handles variable item counts.

**CSS changes:** Font size bump already covered in Part 2 (26px -> 28px).

**Pin assembler changes (`src/pin_assembler.py`) -- "Show 5, Truncate Rest" Logic:**

The current code has two issues:
1. `_extract_list_items()` (line 589 in `generate_pin_content.py`) caps at 7 items: `return items[:7]`. This should cap at 5 to match the pin's visual capacity.
2. `_build_list_items_html()` (lines 123-137 in `pin_assembler.py`) iterates all items with no cap, so if 7 items are passed through, all 7 render on the pin and overflow the layout.

**Change 1 -- `src/generate_pin_content.py`, `_extract_list_items()` (line 589):**
```python
# Current:
    return items[:7]

# New:
    return items[:5]
```

**Change 2 -- `src/pin_assembler.py`, `_build_list_items_html()` (lines 123-137):**

Add a `has_more` parameter, hard-cap at 5 visible items, and append an "...and more" truncation row when the source list was longer:
```python
def _build_list_items_html(items: list[str], variant: str, has_more: bool = False) -> str:
    if not items:
        return ""
    html_parts = []
    for i, item in enumerate(items[:5], 1):  # Hard cap at 5 visible items
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
            f'  <span class="list-item-number">&nbsp;</span>'
            f'  <span class="list-item-text list-item-more-text">...and more</span>'
            f'</div>'
        )
    return "\n".join(html_parts)
```

**Change 3 -- Update the call site in `_inject_variables()` (line 310):**

Pass `has_more` from the context:
```python
# Current:
    items_html = _build_list_items_html(items, variant)

# New:
    has_more = context.get("has_more_items", False)
    items_html = _build_list_items_html(items, variant, has_more=has_more)
```

**Change 4 -- Add CSS for the "...and more" element (`templates/pins/listicle-pin/styles.css`):**
```css
.list-item-more-text {
    font-style: italic;
    opacity: 0.7;
}
```

**Complexity:** S (one extraction cap change, one assembler function update, one CSS rule)

**New TEMPLATE_CONFIGS variables:** `"cta_text"`, `"has_more_items"` (internal, not from prompt)

### 4.4 problem-solution-pin

**HTML changes (`templates/pins/problem-solution-pin/template.html`):**

1. Add CTA element to the solution section of all 3 variants (above brand-logo).
2. Replace hardcoded section labels with template variables:
   - Variant A line 33: `"The Problem"` -> `{{problem_label}}` (default: "The Problem")
   - Variant A line 42: `"The Answer"` -> `{{solution_label}}` (default: "The Answer")
   - Same for Variants B and C.

**CSS changes (`templates/pins/problem-solution-pin/styles.css`):**

**4.4a: Adjust Variant A split ratio from 45/55 to 40/60 (solution-dominant):**
```css
/* Current */
.variant-a .ps-a-problem {
    height: 45%;
}
.variant-a .ps-a-solution {
    height: calc(55% - 10px);
}

/* New */
.variant-a .ps-a-problem {
    height: 40%;
}
.variant-a .ps-a-solution {
    height: calc(60% - 10px);
}
```

This makes the solution section larger, which aligns with the research finding that solution-dominant layouts (40/60 split) perform better.

**4.4b: Problem/solution font weight differentiation (Quick Win):**

Use lighter font weight for problem text and bolder for solution text. This creates visual hierarchy that reinforces the "tension to relief" dynamic -- the problem feels uncertain and the solution feels authoritative.

Currently, both problem and solution text use the `.text-headline` class (`font-weight: 700` from `base-styles.css`). In variant C, the solution already uses `.text-display` (`font-weight: 800`), which partially achieves this, but variants A and B have no differentiation.

Add these rules to `templates/pins/problem-solution-pin/styles.css`:
```css
/* Problem text: lighter weight creates visual "tension" */
.variant-a .ps-a-problem .text-headline,
.variant-b .ps-b-problem-area .text-headline {
    font-weight: 500;
}

/* Solution text: bolder weight creates visual "relief" */
.variant-a .ps-a-solution .text-headline,
.variant-b .ps-b-solution-card .text-headline {
    font-weight: 800;
}

/* Variant C already uses .text-display (800) for solution
   and .text-headline (700) for problem. Lighten the problem: */
.variant-c .ps-c-problem-area .text-headline {
    font-weight: 500;
}
```

**Complexity:** S (CSS-only, no HTML or Python changes)

**New TEMPLATE_CONFIGS variables:** `"cta_text"`, `"problem_label"`, `"solution_label"`

**Pin assembler changes:**
- Add `"problem_label"`, `"solution_label"` to `simple_vars`.
- Default `problem_label` to `"The Problem"`, `solution_label` to `"The Answer"` if not provided.

### 4.5 infographic-pin

**HTML changes (`templates/pins/infographic-pin/template.html`):**

1. Replace hardcoded category label with `{{category_label}}` (Dynamic Category Labels -- SEO Quick Win):
   - Variant A line 33: `"Step by Step"` -> `{{category_label}}`
   - Same rationale as tip-pin (section 4.2): static labels waste an SEO opportunity. Making this dynamic lets the AI generate keyword-targeted labels per pin (e.g., "Meal Prep Guide", "Weekly Planning", "Dinner System").
2. Add CTA element to the footer section of all 3 variants (above the brand-logo, replacing or supplementing the `footer_text` caption).

**CSS changes:** Font size bumps already covered in Part 2.

**New TEMPLATE_CONFIGS variables:** `"category_label"`, `"cta_text"`

**Pin assembler changes:**
- Add `"category_label"` to `simple_vars` in `_inject_variables()` (already needed for tip-pin; same variable name works for both templates).
- Default `category_label` to `"Step by Step"` for infographic-pin if not provided (in `build_template_context()`).

**Prompt changes (`prompts/pin_copy.md`):**
- Add `category_label` to the infographic-pin text_overlay schema in Part 5.1. The AI should generate a 2-3 word label using the pin's primary keyword when it fits.

### 4.6 Summary of TEMPLATE_CONFIGS Updates

**File: `src/pin_assembler.py`, lines 57-83**

```python
TEMPLATE_CONFIGS = {
    "recipe-pin": {
        "variants": ["A", "B", "C"],
        "description": "Food photo with text overlay -- recipe name + descriptor",
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
        "description": "Split design -- problem statement top, solution bottom",
        "variables": ["problem_text", "solution_text", "background_image_url", "problem_label", "solution_label", "cta_text"],
    },
    "infographic-pin": {
        "variants": ["A", "B", "C"],
        "description": "Structured steps/info on branded background -- minimal photography",
        "variables": ["title", "steps", "footer_text", "category_label", "cta_text"],
    },
    # NOTE: category_label added to both tip-pin and infographic-pin.
    # This field is populated by the AI from the pin_copy.md prompt.
    # Defaults: "Tips & Advice" for tip-pin, "Step by Step" for infographic-pin.
}
```

---

## Part 5: Pin Copy Prompt Overhaul

**Priority: HIGH**
**File: `prompts/pin_copy.md`**

### 5.1 New Output Format Section

Replace the existing OUTPUT FORMAT section (lines 93-113) with a template-aware output format. The key change: `text_overlay` must contain template-specific structured fields.

**New OUTPUT FORMAT section:**

````markdown
## OUTPUT FORMAT

Return valid JSON. No markdown code fences. One object per pin in the batch.

The `text_overlay` object MUST contain template-specific fields based on the `pin_template` in the pin specification. The template type determines what additional fields are required.

### Base format (all templates):
```json
{
  "pins": [
    {
      "pin_id": "W12-01",
      "title": "Pin title, max 100 characters, primary keyword leads",
      "description": "250-500 character description...",
      "alt_text": "Visual description...",
      "text_overlay": {
        "headline": "6-8 Word Headline",
        "sub_text": "Optional 3-5 word sub-line",
        "cta_text": "Get the Recipe"
      }
    }
  ]
}
```

### Template-specific `text_overlay` fields:

**recipe-pin:**
```json
{
  "headline": "Sheet Pan Honey Garlic Salmon",
  "sub_text": "One Pan / 25 Min",
  "time_badge": "25 min",
  "cta_text": "Get the Recipe"
}
```
- `sub_text`: MUST be 3-5 words max for recipe pins. Short, punchy qualifiers only (e.g. "One Pan / 25 Min", "Ready in 25 Minutes", "Weeknight Winner"). Do NOT write full sentences. Research shows recipe pin subtitles perform best when ultra-concise.
- `time_badge`: Short timing or effort label (e.g. "25 min", "One Pan", "5 Ingredients"). 2-3 words max.
- `cta_text`: Default to "Get the Recipe". Can also be "Try This Tonight" or "Save for Dinner".

**tip-pin:**
```json
{
  "headline": "5 Dinners. 1 List. Zero Thinking.",
  "sub_text": null,
  "bullet_1": "Plan your whole week in 2 minutes",
  "bullet_2": "One grocery trip covers every meal",
  "bullet_3": "Your family votes before you cook",
  "category_label": "Meal Planning Tips",
  "cta_text": "Save These Tips"
}
```
- `bullet_1`, `bullet_2`: REQUIRED. Each bullet is a distinct, actionable tip. 6-10 words. Do NOT just split a sentence -- write 2-3 genuinely different points.
- `bullet_3`: Optional third bullet. Leave as empty string "" if only 2 bullets are needed.
- `category_label`: 2-3 word category that matches the pin's topic. Use the primary keyword if it fits.
- `cta_text`: Default to "Save These Tips".

**listicle-pin:**
```json
{
  "headline": "Easy Weeknight Dinners the Family Will Love",
  "sub_text": null,
  "number": "7",
  "list_items": [
    "One-Pan Lemon Herb Chicken",
    "Creamy Tuscan Sausage Pasta",
    "Slow Cooker Pulled Pork Tacos",
    "Sheet Pan Honey Garlic Salmon",
    "15-Minute Beef & Broccoli"
  ],
  "cta_text": "See All 7 Recipes"
}
```
- `number`: The list count as a string (e.g. "7", "5", "10"). Must match the headline number.
- `list_items`: Array of 3-5 short items (4-8 words each). These appear on the pin image. If the full list is longer than 5, include only the best 5 -- the pin will show "...and more". Do NOT include more than 5 items.
- `cta_text`: Default to "See All [N] Recipes" or "Get the Full List".

**problem-solution-pin:**
```json
{
  "headline": "Everyone has an opinion about dinner.",
  "sub_text": "What if they gave it before you cooked?",
  "problem_text": "Everyone has an opinion about dinner.",
  "solution_text": "What if they gave it before you cooked?",
  "cta_text": "Here's How"
}
```
- `problem_text`: A relatable pain point. Short, emotional, 8-12 words. Often a statement the target reader has thought themselves.
- `solution_text`: A confident, specific answer. 8-15 words. Should feel like relief.
- The headline and sub_text can be the same as problem_text and solution_text, or complementary wording.
- `cta_text`: Default to "Here's How".

**infographic-pin:**
```json
{
  "headline": "How to Meal Plan in 5 Easy Steps",
  "sub_text": null,
  "category_label": "Meal Prep Guide",
  "steps": [
    {"number": "1", "text": "Set your family's dietary preferences"},
    {"number": "2", "text": "Choose how many nights to plan"},
    {"number": "3", "text": "Get personalized recipe suggestions"},
    {"number": "4", "text": "Let your family vote on the plan"},
    {"number": "5", "text": "Order groceries with one tap"}
  ],
  "footer_text": "Your whole week, handled.",
  "cta_text": "Save This Guide"
}
```
- `category_label`: 2-3 word category label using the pin's primary keyword (e.g. "Meal Prep Guide", "Weekly Planning", "Dinner System"). This replaces the hardcoded "Step by Step" label in the template. Use the primary keyword if it fits naturally.
- `steps`: Array of 3-5 step objects. Each has a `number` (string) and `text` (6-12 words per step). Steps must be distinct and sequential -- not just rephrased versions of each other.
- `footer_text`: Optional sign-off line (3-6 words). Can be a benefit statement or teaser.
- `cta_text`: Default to "Save This Guide".
````

### 5.2 Recipe Subtitle Tightening (Prompt-Only Quick Win)

The current `pin_copy.md` prompt allows full sentences for `sub_text` (line 81: "Can include a sub-text line of 3-5 additional words"). The existing few-shot example for recipe pins uses `"One pan. 30 minutes. Tuesday handled."` which is 6 words -- too long for a recipe-pin subtitle.

**Research finding:** Recipe pin subtitles perform best at 3-5 words max. Short qualifiers like "One Pan / 25 Min" or "Ready in 25 Minutes" outperform full sentences.

**Changes to `prompts/pin_copy.md`:**
- In the COPY RULES > Text Overlay section (line 81), update the sub-text guidance to explicitly note that recipe-pin sub_text must be 3-5 words max.
- In the few-shot recipe example (lines 129-133), change `"sub_text": "One pan. 30 minutes. Tuesday handled."` to `"sub_text": "One Pan / 30 Min"`.
- Add a bolded constraint in the TEMPLATE-SPECIFIC COPY INSTRUCTIONS > recipe-pin section (see 5.3 below).

**Files:** `prompts/pin_copy.md`
**Complexity:** S (prompt text changes only, no code changes)

### 5.3 Template-Specific Instructions

Add a new section to the prompt, between COPY RULES and PINTEREST SEO RULES:

````markdown
## TEMPLATE-SPECIFIC COPY INSTRUCTIONS

The `pin_template` field in the pin specification tells you which visual template this pin will use. You MUST generate the template-specific `text_overlay` fields listed above. The visual template relies on these structured fields to render correctly.

### recipe-pin
- The headline IS the recipe name. Keep it specific: "Sheet Pan Honey Garlic Salmon" not "Easy Dinner".
- The sub_text MUST be 3-5 words max. Short, punchy qualifiers only. Examples: "One Pan / 25 Min", "Ready in 25 Minutes", "Weeknight Winner". Do NOT write full sentences for sub_text on recipe pins.
- Always include a time_badge with the prep/cook time if available.

### tip-pin
- You MUST generate bullet_1 and bullet_2 as distinct, standalone tips. These are not fragments of a paragraph -- they are separate pieces of advice that each make sense on their own.
- Each bullet should be 6-10 words. Be actionable: start with a verb or benefit.
- GOOD bullets: "Plan your entire week in 2 minutes" / "One grocery trip covers every meal"
- BAD bullets: "This is a great way to" / "Another benefit of meal planning is that"

### listicle-pin
- The number in the headline MUST match the number field: "7 Easy Weeknight Dinners" -> number: "7".
- list_items are short recipe names or concise phrases, 4-8 words each. NOT full sentences.
- Include only 3-5 items in list_items even if the full list is longer.
- GOOD items: "One-Pan Lemon Herb Chicken" / "15-Minute Beef & Broccoli"
- BAD items: "One-pan lemon herb chicken is a great weeknight option for busy families"

### problem-solution-pin
- The problem_text and solution_text form a rhetorical pair. The problem is the relatable pain; the solution is the confident answer.
- Write them as if they are two halves of a conversation. The problem sounds like a frustrated parent; the solution sounds like a wise friend.
- Keep both under 15 words.

### infographic-pin
- Steps must be sequential and logically ordered. Each step builds on the previous.
- Step text should be concise (6-12 words). No "First, you should..." phrasing -- just the action.
- GOOD step: "Set your family's dietary preferences"
- BAD step: "The first thing you want to do is set up your dietary preferences in the app settings"
````

### 5.4 Updated Few-Shot Examples

Update the existing few-shot examples to include the new template-specific fields. Add at least one example per template type. (The existing examples are for recipe-pin and problem-solution-pin; add tip-pin, listicle-pin, and infographic-pin examples.)

Add these examples to the FEW-SHOT EXAMPLES section:

````markdown
### GOOD Example 4: Tip Pin (Pillar 1, Discovery)

**Context:** Pin for a blog post about streamlining weekly meal planning.

```json
{
  "pin_id": "W14-03",
  "title": "How to Plan a Week of Family Dinners in Under 10 Minutes",
  "description": "Weekly meal planning for families does not have to take hours. A simple 3-step approach turns the most stressful part of cooking into the easiest. Set your family's preferences, pick a few flexible recipes, and generate one grocery list that covers every dinner from Monday to Friday. This is the system that replaces the nightly 'what should we eat?' scramble with something that actually works.",
  "alt_text": "Overhead view of a meal planner notebook open on a kitchen counter with colorful ingredients arranged around it. Weekly family meal planning guide with easy tips.",
  "text_overlay": {
    "headline": "Plan a Week of Dinners in 10 Minutes",
    "sub_text": null,
    "bullet_1": "Set your family's preferences once",
    "bullet_2": "Pick 5 flexible weeknight recipes",
    "bullet_3": "One grocery list covers everything",
    "category_label": "Meal Planning",
    "cta_text": "Save These Tips"
  }
}
```

### GOOD Example 5: Listicle Pin (Pillar 3, Discovery)

**Context:** Pin for a roundup blog post of quick dinner recipes.

```json
{
  "pin_id": "W14-07",
  "title": "5 High-Protein Dinners Even Picky Kids Will Eat",
  "description": "High-protein weeknight dinners the whole family can agree on. These five recipes balance nutrition with kid-approved flavors -- no hiding vegetables required. From turkey taco lettuce wraps to a lentil bolognese that tastes like the real thing, each recipe is under 35 minutes and uses straightforward pantry ingredients. Real dinners for real families with real dietary goals.",
  "alt_text": "Colorful spread of five different dinner plates on a wooden table, showing turkey tacos, salmon, pasta, fried rice, and Greek chicken. High-protein family dinner ideas.",
  "text_overlay": {
    "headline": "High-Protein Dinners Kids Will Eat",
    "sub_text": null,
    "number": "5",
    "list_items": [
      "Turkey Taco Lettuce Wraps",
      "Salmon & Sweet Potato Sheet Pan",
      "Lentil Bolognese",
      "Egg Fried Rice with Veggies",
      "Greek Chicken Sheet Pan"
    ],
    "cta_text": "See All 5 Recipes"
  }
}
```

### GOOD Example 6: Infographic Pin (Pillar 2, Consideration)

**Context:** Pin for a step-by-step guide blog post about starting meal planning.

```json
{
  "pin_id": "W14-11",
  "title": "How to Start Meal Planning This Week — A 5-Step Beginner System",
  "description": "Starting a weekly meal plan from scratch feels overwhelming until you break it into five manageable steps. This beginner-friendly system walks through setting family preferences, choosing recipes, building a grocery list, getting family buy-in, and batch-prepping on Sunday. Each step takes less than 10 minutes. By the end you have a full week of dinners and one organized grocery run.",
  "alt_text": "Infographic showing five numbered steps for starting a weekly meal plan, with icons for each step on a warm amber background. Beginner meal planning guide.",
  "text_overlay": {
    "headline": "How to Meal Plan in 5 Easy Steps",
    "sub_text": null,
    "category_label": "Meal Planning Guide",
    "steps": [
      {"number": "1", "text": "Set your family's dietary preferences"},
      {"number": "2", "text": "Choose 5 flexible weeknight recipes"},
      {"number": "3", "text": "Generate one combined grocery list"},
      {"number": "4", "text": "Get your family to vote on the plan"},
      {"number": "5", "text": "Batch-prep ingredients on Sunday"}
    ],
    "footer_text": "Your whole week, handled.",
    "cta_text": "Save This Guide"
  }
}
```
````

### 5.5 System Message Update in `claude_api.py`

**File:** `src/claude_api.py`, function `generate_pin_copy()` (line ~241)

The system message currently describes `text_overlay` as containing `"text_overlay (6-8 words)"`. With the new template-specific structured fields (bullets, list_items, steps, time_badge, etc.), this description is inaccurate and may confuse the model.

**Change:** Update the system message from `"text_overlay (6-8 words)"` to `"text_overlay (JSON object with template-specific fields)"` (or similar wording that reflects the new schema). This ensures the model understands it should produce structured JSON in `text_overlay`, not just a short string.

---

## Part 6: Implementation Order

### Phase 1: Content Extraction + Prompt Overhaul (Highest Impact, Lowest Risk)

These are the changes that fix the core problem (pins with only 1-2 items). They can be done together because the prompt changes and code changes are tightly coupled, and the code includes backward-compatible fallbacks.

| # | Change | File(s) | Complexity | Dependencies |
|---|---|---|---|---|
| 1a | Overhaul `pin_copy.md` prompt with template-specific `text_overlay` schema, instructions, and few-shot examples. Includes recipe subtitle tightening (3-5 words max), dynamic `category_label` for tip-pin and infographic-pin, and `category_label` guidance in template-specific instructions. | `prompts/pin_copy.md` | M | None |
| 1b | Update `build_template_context()` to prefer structured fields from `text_overlay`, with extraction fallbacks. Includes `category_label` defaults per template type. | `src/generate_pin_content.py` | M | 1a (new fields must be defined first) |
| 1c | Improve fallback extraction functions (`_extract_bullets`, `_extract_list_items`, `_extract_steps`). Cap `_extract_list_items()` at 5 items (currently 7). | `src/generate_pin_content.py` | S | None |
| 1d | Update `TEMPLATE_CONFIGS` with new variable names (`category_label` for tip-pin and infographic-pin) | `src/pin_assembler.py` | S | 1a |

**Estimated effort:** 2-3 hours
**Risk:** Low. The fallback code means old-format AI responses still work. The new prompt is additive (new fields in `text_overlay`), not destructive (existing fields are unchanged).
**Validation:** Run a test batch of pin copy generation and verify that each template type receives its structured fields. Check that tip-pins get 2-3 bullets, listicle-pins get 3-5 items, infographic-pins get 3-5 steps.

### Phase 2: Font Sizes + CTA Elements (High Impact, Medium Risk)

Font size changes are purely CSS and can be tested visually. CTA elements require HTML template changes, CSS additions, and assembler updates.

| # | Change | File(s) | Complexity | Dependencies |
|---|---|---|---|---|
| 2a | Bump font sizes per Part 2 spec | `templates/pins/shared/base-styles.css`, `templates/pins/listicle-pin/styles.css`, `templates/pins/infographic-pin/styles.css` | S | None |
| 2b | Add CTA CSS to `base-styles.css` | `templates/pins/shared/base-styles.css` | S | None |
| 2c | Add CTA HTML to all 5 template files (15 variants total) | `templates/pins/*/template.html` (5 files) | M | 2b |
| 2d | Add CTA injection logic to `pin_assembler.py` (`_inject_variables`, hiding logic) | `src/pin_assembler.py` | S | 2c |

**Estimated effort:** 2-3 hours
**Risk:** Medium. Visual changes need testing across all 15 variants (5 templates x 3 variants) to ensure nothing overflows or clips. Run the existing test render suite (`python -m src.pin_assembler`) after changes.
**Validation:** Render all 15 variant test pins and visually inspect at both full size (1000x1500) and simulated thumbnail size (300px wide).

### Phase 3: Template-Specific Improvements (Medium Impact, Low Risk)

These are the per-template structural improvements that add polish.

| # | Change | File(s) | Complexity | Dependencies |
|---|---|---|---|---|
| 3a | Add `time_badge` to recipe-pin (HTML + CSS) | `templates/pins/recipe-pin/template.html`, `templates/pins/recipe-pin/styles.css` | S | Phase 1 (needs prompt to generate `time_badge`) |
| 3b | Make category labels dynamic in tip-pin and infographic-pin (SEO quick win -- keyword-targetable labels) | `templates/pins/tip-pin/template.html`, `templates/pins/infographic-pin/template.html` | S | Phase 1 (needs prompt to generate `category_label`) |
| 3c | Add "show 5, truncate rest" logic to listicle-pin: cap `_extract_list_items()` at 5, add `has_more` param to `_build_list_items_html()`, add "...and more" CSS | `src/pin_assembler.py`, `src/generate_pin_content.py`, `templates/pins/listicle-pin/styles.css` | S | Phase 1 (needs `has_more_items` logic) |
| 3d | Adjust problem-solution-pin Variant A split to 40/60 | `templates/pins/problem-solution-pin/styles.css` | S | None |
| 3e | Add problem/solution font weight differentiation: lighter (500) for problem, bolder (800) for solution | `templates/pins/problem-solution-pin/styles.css` | S | None |
| 3f | Make problem/solution section labels dynamic | `templates/pins/problem-solution-pin/template.html` | S | None |
| 3g | Standardize brand logo opacity to 0.6 across all templates (10 inline style edits, see Item 3g Detail below) | All 5 `template.html` files | S | None |
| 3h | Update test render data in `pin_assembler.py` `_run_test_renders()` to include new fields (`category_label`, `cta_text`, `time_badge`, etc.) | `src/pin_assembler.py` | S | All prior changes |

**Estimated effort:** 2-3 hours
**Risk:** Low. Each change is small and independent.
**Validation:** Run test renders, visually inspect.

#### Item 3g Detail: Logo Opacity Standardization

The brand logo text (`Slated.`) currently has inconsistent opacity values across templates, ranging from 0.45 to 0.7. These are set as inline styles on the `brand-logo-text` span in each template HTML file. Standardize all to `opacity: 0.6`.

| Template | Variant | Current Opacity | Line | Change |
|---|---|---|---|---|
| recipe-pin | A | 0.7 | template.html:39 | 0.7 -> 0.6 |
| recipe-pin | B | 0.6 | template.html:55 | No change |
| recipe-pin | C | 0.6 | template.html:72 | No change |
| tip-pin | A | 0.65 | template.html:57 | 0.65 -> 0.6 |
| tip-pin | B | 0.55 | template.html:85 | 0.55 -> 0.6 |
| tip-pin | C | 0.6 | template.html:114 | No change |
| listicle-pin | A | 0.6 | template.html:44 | No change |
| listicle-pin | B | 0.55 | template.html:65 | 0.55 -> 0.6 |
| listicle-pin | C | 0.55 | template.html:85 | 0.55 -> 0.6 |
| problem-solution-pin | A | 0.55 | template.html:46 | 0.55 -> 0.6 |
| problem-solution-pin | B | 0.55 | template.html:76 | 0.55 -> 0.6 |
| problem-solution-pin | C | 0.5 | template.html:99 | 0.5 -> 0.6 |
| infographic-pin | A | 0.5 | template.html:44 | 0.5 -> 0.6 |
| infographic-pin | B | 0.45 | template.html:65 | 0.45 -> 0.6 |
| infographic-pin | C | 0.45 | template.html:85 | 0.45 -> 0.6 |

**Total changes:** 10 inline style edits across 5 template HTML files. Simple find-and-replace on the `brand-logo-text` opacity value in each file.

### Phase Summary

| Phase | Changes | Total Effort | Impact | Risk |
|---|---|---|---|---|
| **Phase 1** | Prompt overhaul (incl. recipe subtitle tightening + dynamic category labels) + extraction code | 2-3 hours | HIGH (fixes the #1 problem: sparse content) | Low |
| **Phase 2** | Font sizes + CTA elements | 2-3 hours | HIGH (readability + 80% more interactions) | Medium |
| **Phase 3** | Template polish: time badges, dynamic labels, listicle truncation, font weight differentiation, logo opacity standardization | 2-3 hours | MEDIUM (refinement, consistency, and SEO wins) | Low |

**Total estimated effort:** 6-9 hours across all three phases.

### Files Modified (Complete List)

| File | Phases | Changes |
|---|---|---|
| `prompts/pin_copy.md` | 1 | New output format, template-specific instructions, new examples, recipe subtitle tightening (3-5 words max), dynamic `category_label` for tip-pin and infographic-pin |
| `src/generate_pin_content.py` | 1, 3 | `build_template_context()` rewrite (incl. `category_label` defaults), extraction function improvements, `_extract_list_items()` cap reduced from 7 to 5 |
| `src/pin_assembler.py` | 1, 2, 3 | `TEMPLATE_CONFIGS` update (incl. `category_label`), `_inject_variables()` additions, `_build_list_items_html()` update (5-item cap + `has_more` param + "...and more" row), CTA hiding logic, test data update |
| `templates/pins/shared/base-styles.css` | 2 | Font size bumps, CTA CSS |
| `templates/pins/recipe-pin/template.html` | 2, 3 | CTA elements, time badge, logo opacity standardization |
| `templates/pins/recipe-pin/styles.css` | 3 | Time badge CSS |
| `templates/pins/tip-pin/template.html` | 2, 3 | CTA elements, dynamic `{{category_label}}` replacing hardcoded "Tips & Advice" / "Meal Planning Tips", logo opacity standardization |
| `templates/pins/listicle-pin/template.html` | 2, 3 | CTA elements, logo opacity standardization |
| `templates/pins/listicle-pin/styles.css` | 2, 3 | Font size bump, "...and more" style |
| `templates/pins/problem-solution-pin/template.html` | 2, 3 | CTA elements, dynamic section labels, logo opacity standardization |
| `templates/pins/problem-solution-pin/styles.css` | 3 | 40/60 split adjustment, problem/solution font weight differentiation (500/800) |
| `templates/pins/infographic-pin/template.html` | 2, 3 | CTA elements, dynamic `{{category_label}}` replacing hardcoded "Step by Step", logo opacity standardization |
| `templates/pins/infographic-pin/styles.css` | 2 | Font size bumps |
| `src/claude_api.py` | 1 | Update system message in `generate_pin_copy()` to describe `text_overlay` as structured JSON, not a flat string (see 5.5) |

---

## Appendix: Backward Compatibility

All changes are designed to be backward-compatible:

1. **Prompt changes:** The new `text_overlay` fields are additive. Old fields (`headline`, `sub_text`) remain. If the AI generates old-format output, the fallback extraction code handles it.
2. **Template changes:** New HTML elements (CTA, time badge) are hidden when their template variables are empty. Existing pins rendered without these variables will simply not show the new elements.
3. **Font size changes:** These are CSS-only and apply globally. No code changes needed. Existing test renders will automatically reflect the new sizes.
4. **TEMPLATE_CONFIGS:** The `variables` lists are informational only (used by `get_available_templates()`). Adding new variable names does not break the injection logic.
