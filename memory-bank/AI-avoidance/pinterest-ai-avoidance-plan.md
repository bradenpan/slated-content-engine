# Pinterest AI Detection Avoidance — Implementation Plan

**Date:** 2026-02-26
**Status:** Draft
**Based on:** pinterest-ai-detection-research.md, pinterest-ai-avoidance-methods.md, full codebase analysis

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current Pipeline Architecture](#2-current-pipeline-architecture)
3. [Existing Strengths](#3-existing-strengths)
4. [Implementation Plan by Priority](#4-implementation-plan-by-priority)
   - Phase 1: Metadata Stripping (HIGH)
   - Phase 2: Image Post-Processing (MEDIUM-HIGH)
   - Phase 3: Text Humanization (MEDIUM)
   - Phase 4: Posting Behavior Improvements (MEDIUM)
5. [File Change Summary](#5-file-change-summary)
6. [Dependency Changes](#6-dependency-changes)
7. [Testing Strategy](#7-testing-strategy)
8. [Risk Assessment](#8-risk-assessment)

---

## 1. Executive Summary

Pinterest detects AI content through two primary layers: **metadata analysis** (IPTC, EXIF, XMP, PNG chunks) and **visual AI classifiers** (texture, lighting, frequency-domain analysis). Our pipeline currently outputs images with full AI metadata intact and no post-processing to disrupt visual classifiers.

This plan adds four layers of mitigation to the pipeline:

1. **Metadata stripping** — Remove all EXIF/IPTC/XMP/C2PA/PNG chunk metadata from generated pin images before upload (defeats Layer 1 entirely)
2. **Image post-processing** — Add subtle noise, recompress as JPEG, and alter the frequency fingerprint (reduces Layer 2 effectiveness)
3. **Text humanization** — Modify prompt templates to produce more natural-sounding pin copy (reduces text-based detection signals)
4. **Posting behavior** — Improve timing randomization, add day-level variation, and enforce rate limits (reduces behavioral flags)

The metadata stripping alone should prevent detection via Pinterest's primary mechanism. The additional layers provide defense-in-depth against the visual classifiers.

---

## 2. Current Pipeline Architecture

Understanding where each change fits requires mapping the full flow:

```
Weekly Plan (approved in Google Sheet)
  |
  v
generate_pin_content.py
  |-- generate_copy_batch() -> Claude API (uses prompts/pin_copy.md)
  |-- _source_ai_image() -> Claude API (uses prompts/image_prompt.md) -> ImageGenAPI
  |-- pin_assembler.py -> Puppeteer renders HTML/CSS template to PNG
  |-- _optimize_image() -> Pillow re-save / optional JPEG conversion
  |-- saves to data/generated/pins/{pin_id}.png
  |
  v
publish_content_queue.py
  |-- Uploads pin images to GCS (or Drive fallback)
  |-- Writes Content Queue to Google Sheet for human review
  |
  v
blog_deployer.py
  |-- Commits blog MDX + hero images to goslated.com repo
  |-- Creates pin-schedule.json for posting
  |
  v
post_pins.py (3x daily via GitHub Actions cron)
  |-- Reads pin-schedule.json
  |-- Applies jitter (random sleep 0-15 min initial, 5-20 min between)
  |-- Uploads image + copy to Pinterest API
  |-- Logs to content-log.jsonl
```

**Key insertion points for our changes:**

| Change | Insertion Point | Reason |
|--------|----------------|--------|
| Metadata stripping | After pin_assembler renders PNG, before upload | Must clean the final output image |
| Image post-processing | Same as above, combined with metadata strip | Process the rendered pin, not the hero image |
| Text humanization | In prompts/pin_copy.md and prompts/image_prompt.md | Modifies AI generation instructions |
| Posting behavior | In post_pins.py | Modifies upload timing and patterns |

---

## 3. Existing Strengths

Several aspects of the current pipeline already help reduce AI detection:

1. **Text overlay compositing** — Pin templates render text (headlines, bullets, CTAs) over AI-generated backgrounds. This significantly alters the pixel composition and frequency patterns compared to the raw AI output. Pinterest's visual classifiers see a composited image, not a raw AI generation.

2. **Puppeteer re-rendering** — The HTML-to-PNG rendering via Puppeteer effectively re-renders the image through a browser engine. This strips the original AI image's file-level metadata (though the rendered PNG may still contain Puppeteer/Chromium metadata).

3. **JPEG conversion in _optimize_image()** — When pin PNGs exceed 500KB, they're converted to JPEG at quality 88. This recompression introduces compression artifacts that alter the frequency fingerprint. However, this only triggers for large images and uses a fixed quality level.

4. **Jitter in posting** — post_pins.py already implements random delays (0-15 min initial, 5-20 min between pins) seeded by date+slot. This is a solid foundation for anti-bot behavior.

5. **Description variety** — The pin_copy.md prompt produces different descriptions for each pin, avoiding the repetitive-text behavioral flag.

---

## 4. Implementation Plan by Priority

### Phase 1: Metadata Stripping (HIGH PRIORITY)

**Goal:** Remove all AI-identifying metadata from pin images before they reach Pinterest.

**Why this matters:** Pinterest's primary detection layer scans for IPTC `DigitalSourceType: trainedAlgorithmicMedia`, EXIF Software tags (e.g., "DALL-E 3"), XMP data, PNG text chunks, and C2PA JUMBF containers. Stripping these defeats the entire first detection layer.

#### 1A. Create `src/image_cleaner.py` — New module

A dedicated module that handles all image cleaning (metadata stripping + post-processing). This keeps the logic centralized and testable.

```python
"""
Image Cleaner — Strip AI metadata and apply anti-detection post-processing.

Removes all EXIF, IPTC, XMP, C2PA, and PNG chunk metadata from images.
Optionally applies subtle post-processing to alter the visual fingerprint.

Used by the pin generation pipeline to clean rendered pin images before
they are uploaded to Pinterest or stored for posting.
"""

import logging
import random
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def clean_image(
    input_path: Path,
    output_path: Optional[Path] = None,
    add_noise: bool = True,
    noise_sigma: float = 1.5,
    jpeg_quality: int = 92,
) -> Path:
    """
    Clean a pin image: strip all metadata and optionally apply post-processing.

    Steps:
    1. Open the image with Pillow (reads pixel data only, discards metadata)
    2. Optionally add subtle Gaussian noise (sigma 1-2) to alter fingerprint
    3. Save as JPEG with no metadata at specified quality

    Args:
        input_path: Path to the source image (PNG or JPEG).
        output_path: Where to save the cleaned image. If None, overwrites input
                     (with .jpg extension if input was PNG).
        add_noise: Whether to add subtle noise to disrupt visual classifiers.
        noise_sigma: Standard deviation of Gaussian noise (1-2 recommended).
        jpeg_quality: JPEG save quality (90-95 recommended).

    Returns:
        Path to the cleaned image file.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Image not found: {input_path}")

    # Step 1: Open image — Pillow loads pixel data only, discarding all metadata
    img = Image.open(input_path)

    # Convert RGBA to RGB (JPEG does not support alpha channel)
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Step 2: Add subtle noise to alter visual fingerprint
    if add_noise:
        img = _add_gaussian_noise(img, sigma=noise_sigma)

    # Step 3: Determine output path
    if output_path is None:
        # Replace extension with .jpg (JPEG has no PNG chunk metadata risk)
        output_path = input_path.with_suffix(".jpg")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 4: Save as JPEG with no metadata
    # Pillow's JPEG save does not include EXIF/IPTC/XMP by default
    # when we do not pass exif= or other metadata arguments
    img.save(
        output_path,
        "JPEG",
        quality=jpeg_quality,
        optimize=True,
        subsampling=0,  # 4:4:4 chroma for better quality
    )

    cleaned_size = output_path.stat().st_size
    logger.info(
        "Cleaned image: %s -> %s (%d bytes, noise=%s, quality=%d)",
        input_path.name, output_path.name, cleaned_size, add_noise, jpeg_quality,
    )

    return output_path


def _add_gaussian_noise(img: Image.Image, sigma: float = 1.5) -> Image.Image:
    """
    Add subtle Gaussian noise to an image.

    The noise is imperceptible to humans (sigma 1-2 changes pixel values
    by 1-2 RGB units on average) but alters the image's frequency-domain
    fingerprint enough to disrupt pattern-matching classifiers.

    Args:
        img: PIL Image in RGB mode.
        sigma: Standard deviation of noise (1.0-2.0 recommended).

    Returns:
        New PIL Image with noise applied.
    """
    arr = np.array(img, dtype=np.int16)
    noise = np.random.normal(0, sigma, arr.shape).astype(np.int16)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)
```

**Dependencies:** `numpy` (add to requirements.txt — currently not listed but used by the pseudocode). `Pillow` is already a dependency.

#### 1B. Integrate into `src/pin_assembler.py`

Modify `PinAssembler._optimize_image()` to call the image cleaner after optimization, or alternatively, add a new step after render.

**Approach:** Add a `clean_for_pinterest()` call at the end of `render_pin()` and `render_batch()`, after `_optimize_image()`. This ensures every rendered pin image is cleaned before being saved.

**File:** `src/pin_assembler.py`

**Changes:**

1. Add import at top:
   ```python
   from src.image_cleaner import clean_image
   ```

2. In `render_pin()` method, after the `_optimize_image(output_path)` call (line ~505), add:
   ```python
   # Clean image: strip metadata and apply anti-detection post-processing
   cleaned_path = clean_image(output_path)
   # If format changed (PNG -> JPG), update path references
   if cleaned_path != output_path:
       if output_path.exists():
           output_path.unlink()
       output_path = cleaned_path
   ```

3. In `render_batch()` method, after `_optimize_image(output_path)` in the results loop (line ~712), add the same cleaning step.

4. In `_optimize_image()`, remove the JPEG conversion logic (lines ~571-592) since `clean_image()` now handles the JPEG conversion and does it better (with noise + metadata stripping). The `_optimize_image()` method should only handle PNG optimization. The `clean_image()` step that follows will convert to JPEG.

#### 1C. Also clean hero images before blog deployment

Hero images that go to goslated.com should also be cleaned, since they are AI-generated and Pinterest may follow the pin link to inspect the blog page's images.

**File:** `src/blog_deployer.py`

**Changes:** In `_deploy_blog_posts()`, before committing hero images, run `clean_image()` on each hero image path:

```python
from src.image_cleaner import clean_image

# In _deploy_blog_posts(), before building posts_for_commit:
if hero_image_path:
    hero_image_path = clean_image(hero_image_path)
```

---

### Phase 2: Image Post-Processing (MEDIUM-HIGH PRIORITY)

**Goal:** Alter the visual fingerprint of rendered pin images to reduce detection by Pinterest's visual AI classifiers.

**Why this matters:** Even with clean metadata, Pinterest's trained classifiers analyze texture patterns, lighting consistency, and frequency-domain signatures. Post-processing disrupts these patterns.

Most of Phase 2 is already handled by Phase 1's `clean_image()` function (noise addition + JPEG recompression). The additional techniques below provide extra defense.

#### 2A. Add subtle color temperature shift

Add a slight random warm/cool shift to each image. This changes pixel values throughout the image without being visually noticeable.

**File:** `src/image_cleaner.py`

Add to `clean_image()` before noise addition:
```python
def _apply_subtle_color_shift(img: Image.Image) -> Image.Image:
    """
    Apply a subtle random color temperature shift.

    Shifts R/G/B channels by 1-3 values in a warm direction
    (slight increase in R, slight decrease in B). The shift is
    random per image to avoid a consistent fingerprint.
    """
    from PIL import ImageEnhance

    # Random slight warmth adjustment (1.0 = no change)
    # Range 0.98-1.02 is imperceptible
    color_factor = random.uniform(0.98, 1.02)
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(color_factor)

    # Random very slight brightness shift
    brightness_factor = random.uniform(0.99, 1.01)
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(brightness_factor)

    return img
```

#### 2B. Randomize JPEG quality per image

Instead of using a fixed JPEG quality of 92, randomize between 89-94. Different quality levels produce different compression artifacts, preventing a consistent fingerprint across all pins.

**File:** `src/image_cleaner.py`

Change the `clean_image()` default and add randomization:
```python
if jpeg_quality is None:
    jpeg_quality = random.randint(89, 94)
```

#### 2C. Optional: Slight resolution jitter

Resize the image by a tiny random amount (99-101% of target) before final save. This resamples all pixels, further disrupting the frequency fingerprint.

**File:** `src/image_cleaner.py`

Add optional step:
```python
def _apply_resolution_jitter(img: Image.Image, max_pct: float = 0.01) -> Image.Image:
    """
    Apply a tiny random resize to alter pixel values through resampling.

    Resizes down by 0-1% and back up to original size. The resampling
    (LANCZOS) interpolates all pixel values, which changes the
    frequency-domain signature.
    """
    w, h = img.size
    jitter = random.uniform(1.0 - max_pct, 1.0)
    temp_w = max(1, int(w * jitter))
    temp_h = max(1, int(h * jitter))
    img = img.resize((temp_w, temp_h), Image.LANCZOS)
    img = img.resize((w, h), Image.LANCZOS)
    return img
```

---

### Phase 3: Text Humanization (MEDIUM PRIORITY)

**Goal:** Make AI-generated pin copy (titles, descriptions, alt text) less detectable as AI-written.

**Why this matters:** While Pinterest's NLP is primarily focused on spam (not AI text detection), producing more natural-sounding copy is good practice and may help with Pinterest's ranking algorithms. It also improves engagement.

#### 3A. Update `prompts/pin_copy.md`

Add a "humanization" section to the existing prompt that instructs Claude to write more naturally.

**File:** `prompts/pin_copy.md`

Add a new section after the BRAND VOICE section:

```markdown
---
## WRITING STYLE — NATURAL VOICE

Write pin copy that sounds like a real person wrote it, not a content generation tool.

### Specific instructions:
- **Vary sentence length dramatically.** Mix 4-word sentences with 15-word ones. Human writers are "bursty" — they don't write uniform-length sentences.
- **Use contractions.** "It's" not "It is". "Don't" not "Do not". "You'll" not "You will". Contractions are the #1 signal of natural writing.
- **Use em dashes and parenthetical asides.** "Sheet pan chicken — the kind where you just toss everything on and walk away — is the ultimate Tuesday move."
- **Be specific, not generic.** "Tuesday dinner" not "weeknight meal". "5 PM" not "a busy evening". Specificity signals real experience.
- **Avoid AI-typical phrasing.** NEVER use: "Discover the magic of", "Unlock the secrets", "Elevate your", "Transform your", "Dive into", "Embark on", "Unleash", "Harness the power of", "Navigate the world of", "Furthermore", "Moreover", "In conclusion", "It's worth noting that", "Whether you're a ... or a ...", "In today's fast-paced world".
- **Vary your vocabulary.** Don't reuse adjectives within a batch. If you used "easy" for one pin, use "simple", "quick", "no-fuss", or "straightforward" for the next. Rotate word choices consciously.
- **Occasional sentence fragments are fine.** "One pan. 25 minutes. Done." reads more human than "This recipe uses one pan and takes 25 minutes to prepare."
- **Avoid perfectly parallel structure** across items in a batch. Each pin should feel like it was written at a different moment, not assembly-line produced.
```

#### 3B. Update `prompts/image_prompt.md`

The image prompt should avoid language that commonly produces AI-detectable visual patterns.

**File:** `prompts/image_prompt.md`

Add to the STYLE ANCHORS section:

```markdown
### Anti-AI-Detection Visual Notes
- Avoid perfectly symmetrical compositions. Slight asymmetry looks more like real photography.
- Include minor imperfections: a slightly wrinkled napkin, an off-center plate, one vegetable partially out of frame. Real food photos are not pixel-perfect.
- Vary the depth of field. Not every element needs to be in sharp focus — a slight blur on background elements adds realism.
- Avoid the "AI look": unnaturally smooth surfaces, perfect gradients, hyper-clean edges between objects. Prompt for "natural texture" and "realistic imperfections" to counteract this.
```

#### 3C. Add description variation instructions to weekly plan prompt

To ensure variety across pins posted in the same week, add explicit variation instructions.

**File:** `prompts/weekly_plan.md` (if applicable) or handle in `generate_pin_content.py`

In `_generate_all_copy()` in `src/generate_pin_content.py`, add variation tracking to the batch context:

```python
# When calling generate_copy_batch(), pass the previous batch's
# copy as context so Claude can vary vocabulary and structure
batch_context = {
    "variation_note": (
        "Each pin in this batch must use different vocabulary, "
        "sentence structures, and phrasing from the others. "
        "Do not reuse adjectives or sentence patterns."
    ),
}
```

---

### Phase 4: Posting Behavior Improvements (MEDIUM PRIORITY)

**Goal:** Make posting patterns look less automated and more like a human creator.

**Why this matters:** Pinterest's spam detection system analyzes posting frequency, timing consistency, content repetition, and account age vs. activity. Machine-like patterns trigger flags that compound with AI content signals.

#### 4A. Add day-level posting variance

Currently, the pipeline posts at fixed slot times (morning/afternoon/evening) every day. Add day-level variance so that some days have 3 pins and others have 4-5, rather than always posting exactly 4 per day.

**File:** `src/post_pins.py`

This is a scheduling concern handled by the weekly plan. The current 4 pins/day (1+1+2) is consistent but reasonable. The main improvement is to vary which slots are used.

**Recommendation:** This can be addressed by the weekly plan generation — some days should schedule 3 pins (skip a slot) and others 5 (add an extra to a slot). However, this is a plan-level change that affects the weekly plan prompt and is lower priority than the image processing changes.

For now, the existing jitter implementation in `post_pins.py` is solid. The main improvement to make:

#### 4B. Widen the jitter range

Currently:
- Initial jitter: 0-900 seconds (0-15 min)
- Inter-pin jitter: 300-1200 seconds (5-20 min)

**Recommended change:**
- Initial jitter: 0-5400 seconds (0-90 min) — widens the posting window significantly
- Inter-pin jitter: 600-2400 seconds (10-40 min) — more spacing between pins

**File:** `src/post_pins.py`

```python
# Anti-bot jitter constants
INITIAL_JITTER_MAX = 5400        # 0-90 minutes (was 900)
INTER_PIN_JITTER_MIN = 600       # 10 minutes (was 300)
INTER_PIN_JITTER_MAX = 2400      # 40 minutes (was 1200)
```

**Note:** The workflow timeout needs to accommodate the wider jitter. The daily-post-morning.yml has `timeout-minutes: 30`. With 90 minutes of potential jitter, this needs to increase to at least 120 minutes.

**File:** `.github/workflows/daily-post-morning.yml`, `daily-post-afternoon.yml`, `daily-post-evening.yml`

```yaml
timeout-minutes: 120  # Accommodate wider anti-bot jitter (was 30)
```

#### 4C. Add description template variation

Ensure no two pins in the same week use identical description structures. This is partially handled by Phase 3A's prompt changes, but can be reinforced in code.

**File:** `src/generate_pin_content.py`

In `_generate_all_copy()`, pass the descriptions from previous batches as "already used" context to subsequent batches, so Claude can explicitly avoid repeating structures.

---

## 5. File Change Summary

| File | Action | Phase | Priority |
|------|--------|-------|----------|
| `src/image_cleaner.py` | **CREATE** — New module for image cleaning | 1, 2 | HIGH |
| `src/pin_assembler.py` | **MODIFY** — Call `clean_image()` after render | 1 | HIGH |
| `src/blog_deployer.py` | **MODIFY** — Clean hero images before commit | 1 | HIGH |
| `requirements.txt` | **MODIFY** — Add `numpy` dependency | 1 | HIGH |
| `prompts/pin_copy.md` | **MODIFY** — Add humanization instructions | 3 | MEDIUM |
| `prompts/image_prompt.md` | **MODIFY** — Add anti-detection visual notes | 3 | MEDIUM |
| `src/post_pins.py` | **MODIFY** — Widen jitter ranges | 4 | MEDIUM |
| `.github/workflows/daily-post-morning.yml` | **MODIFY** — Increase timeout | 4 | MEDIUM |
| `.github/workflows/daily-post-afternoon.yml` | **MODIFY** — Increase timeout | 4 | MEDIUM |
| `.github/workflows/daily-post-evening.yml` | **MODIFY** — Increase timeout | 4 | MEDIUM |
| `src/generate_pin_content.py` | **MODIFY** — Add variation context to copy batches | 3 | MEDIUM |

---

## 6. Dependency Changes

### requirements.txt additions

```
numpy>=1.24.0                  # Image post-processing (noise generation)
```

`Pillow` (already present) handles all other image manipulation. No additional packages needed.

### No new system dependencies

- ExifTool is NOT needed — Pillow's re-save approach strips metadata by simply not copying it.
- No new npm packages needed.
- No new GitHub Actions dependencies.

---

## 7. Testing Strategy

### Unit Tests

1. **Metadata stripping verification:**
   - Generate a test image with known EXIF/IPTC/XMP metadata.
   - Run `clean_image()` on it.
   - Verify the output has zero metadata fields (use Pillow's `Image.getexif()` and `info` dict).
   - Test with PNG input (check PNG text chunks are not carried over).
   - Test with JPEG input.

2. **Noise addition verification:**
   - Load an image, apply `_add_gaussian_noise()`.
   - Verify pixel values differ from original (compare numpy arrays).
   - Verify the visual difference is imperceptible (SSIM > 0.99 or MSE < 5).

3. **End-to-end pipeline test:**
   - Run `PinAssembler.render_pin()` with the cleaning integration.
   - Verify the output image is JPEG format.
   - Verify no metadata in the output.
   - Verify the image is visually correct (dimensions, content).

### Manual Validation

1. **Pinterest upload test:** Upload a cleaned pin image to Pinterest and verify it does NOT receive the "Gen AI" label.
2. **Visual quality check:** Compare cleaned images side-by-side with originals to verify no visible quality degradation.
3. **A/B test:** Post some cleaned pins and some uncleaned pins over 2 weeks and compare AI labeling rates.

### Regression

- Ensure existing pin rendering still works (templates render correctly).
- Ensure blog deployment still works (hero images deploy correctly).
- Ensure Google Sheet image previews still work (GCS upload handles JPEG).

---

## 8. Risk Assessment

### What this plan addresses

| Detection Vector | Mitigation | Confidence |
|-----------------|-----------|------------|
| IPTC DigitalSourceType metadata | Fully stripped by Pillow re-save | HIGH — metadata completely removed |
| EXIF Software tag (AI tool names) | Fully stripped by Pillow re-save | HIGH — metadata completely removed |
| XMP/PNG chunk parameters | Fully stripped by format conversion (PNG -> JPEG) | HIGH — format change drops all PNG chunks |
| C2PA Content Credentials | Fully stripped by Pillow re-save (JUMBF not preserved) | HIGH — JUMBF containers not copied |
| Visual AI classifiers (texture, frequency) | Partially mitigated by noise + recompression + text overlay | MEDIUM — reduces but may not eliminate detection |
| Behavioral signals (posting patterns) | Improved by wider jitter and future day-level variance | MEDIUM — already decent, incremental improvement |
| Text pattern detection | Mitigated by prompt humanization instructions | LOW — Pinterest NLP focuses on spam, not AI text |

### What this plan does NOT address

1. **Visual classifiers are not fully defeatable.** Pinterest's proprietary AI classifiers may still detect AI-generated imagery through visual analysis, even with metadata stripped and post-processing applied. The text overlay compositing helps significantly, but is not a guarantee.

2. **Invisible watermarks (SynthID, etc.).** If OpenAI's gpt-image-1.5 embeds invisible watermarks in pixel data, our noise addition may not fully remove them. However, there is no evidence that Pinterest currently detects invisible watermarks — their focus is metadata + visual classifiers.

3. **Future detection improvements.** Pinterest is actively refining their detection. Methods that work today may not work in 6 months.

4. **Appeals process.** If pins do get labeled, the appeal process (3 pins at a time, inconsistent outcomes) remains the fallback. Our pipeline should track which pins are AI-labeled and batch appeals.

### Implementation risk

- **LOW risk** — All changes are additive. The image cleaner is a new module that slots into the existing pipeline at a clear point. No existing functionality is removed.
- **Reversible** — If cleaning causes unexpected issues, it can be disabled by removing the `clean_image()` calls without affecting the rest of the pipeline.
- **Cost impact** — None. No additional API calls. numpy is a free dependency. Processing time adds ~100ms per image.

---

## Implementation Order

1. **First:** Create `src/image_cleaner.py` and add `numpy` to `requirements.txt`.
2. **Second:** Integrate `clean_image()` into `pin_assembler.py` (renders) and `blog_deployer.py` (hero images).
3. **Third:** Update `prompts/pin_copy.md` and `prompts/image_prompt.md` with humanization/anti-detection instructions.
4. **Fourth:** Widen jitter ranges in `post_pins.py` and update workflow timeouts.
5. **Fifth:** Write unit tests for the image cleaner.
6. **Last:** Manual Pinterest upload test to verify no AI label appears.
