# Implementation Plan: Pipeline Simplification & Model Changes

## Context

The Pinterest pipeline is over-engineered in its image sourcing — it searches stock APIs, ranks candidates with Claude Haiku vision, retries with broader queries, falls back to AI generation, validates AI with Claude Sonnet vision, then generates a SECOND AI comparison image alongside the stock winner. The user wants to simplify to: generate a prompt → generate an AI image → present it for human review. No stock APIs, no ranking, no AI validation, no comparison images.

Additionally: blog posts have a double-title bug, the weekly plan lacks a feedback/regen loop, and two model calls should switch from Claude Sonnet to GPT-5 Mini (image prompt generation and pin copy generation).

---

## Data Flow Reference (Cross-Cutting Concerns)

Key data paths that must remain consistent:

### Image Data Flow (after simplification)
```
generate_image_prompt() → image_gen_api.generate()
    → pin_data["hero_image_path"] = "{pin_id}-hero.png"
    → pin_data["image_source"] = "ai_generated"
    → pin_data["image_id"] = "ai_{prompt_hash}"
    → pin_assembler.assemble_pin(hero_image_path=...)
    → publish_content_queue → GCS upload → Sheet =IMAGE() formula (Column I)
    → pin-generation-results.json: _drive_image_url, _drive_download_url
    → blog_deployer → pin-schedule.json: image_url
    → post_pins.py → Pinterest API
```

### Naming Conventions (unchanged)
- Pin IDs: `W{N}-{NN}` (e.g., W12-01)
- Post IDs: `W{N}-P{NN}` (e.g., W12-P01)
- Hero images: `{pin_id}-hero.png` (pins) or `{slug}-hero.png` (blogs)
- Rendered pins: `{pin_id}.png`
- Blog slugs: lowercase-hyphenated from frontmatter

### Downstream Consumers of Image Data (verify these still work)
- `publish_content_queue.py` — reads pin-generation-results.json, uploads to GCS, writes Sheet
- `blog_deployer.py` — reads approvals, creates pin-schedule.json with image_url
- `regen_content.py` — reads/writes pin-generation-results.json, re-sources images
- `post_pins.py` — reads pin-schedule.json, sends image_url to Pinterest API
- `weekly_analysis.py` / `monthly_review.py` — reads content-log.jsonl by image_source
- `sheets_api.py` — Column I (Thumbnail), Column K (Notes)

### `image_source_tier` Traced Through Full Codebase

The `image_source_tier` field flows through exactly these locations:

| Location | Usage |
|----------|-------|
| `prompts/weekly_plan.md` | Schema defines field values: "stock"/"ai"/"template" |
| `prompts/weekly_plan_replace.md` | Referenced in replacement schema |
| `strategy/current-strategy.md` | Documents the tier concept |
| `generate_pin_content.py:137` | Reads from pin_spec to route to stock/ai/template |
| `generate_pin_content.py:310-363` | `source_image()` routes by tier value |
| `generate_pin_content.py:684-734` | `_source_pin_image()` routes by tier |
| `regen_content.py:500` | Sets tier from `image_source` for regen routing |
| `regen_content.py:542-555` | Normalizes and routes by tier |
| `regen_content.py:576,784-788` | Tier used in regen routing |

**NOT stored in:** pin-generation-results.json, pin-schedule.json, content-log.jsonl, Content Queue Sheet, or any analytics aggregation.

**Conclusion:** Safe to remove. The tier is only used for routing (which we're eliminating). No downstream data depends on it.

---

## Change 1+2: Simplify Image Generation & Regen (Remove Stock, Ranking, Validation, Comparison, Tiers)

### Goal
Replace the entire multi-tier image flow with: generate prompt → generate AI image → done. Human review in the Content Queue is the quality gate.

### What Gets Removed
- **Stock photo search** (`_source_stock_image()` — ~190 lines)
- **Stock ranking** (`claude.rank_stock_candidates()` + `prompts/image_rank.md`)
- **AI image validation** (`claude.validate_ai_image()` + `prompts/image_validate.md`)
- **Retry-with-feedback loop** (regenerate if validation score < 6.5)
- **AI comparison image generation** (the second AI image alongside stock winner)
- **Tier routing** (`source_image()` stock/ai/template logic → everything is AI)
- **`use_ai_image` approval status** — only one image now
- **Column M ("AI Image")** in Content Queue — only one image
- **`image_source_tier`** from weekly plan prompts (no tiers to assign)
- **`low_confidence` flagging** — no automated quality gate

### What Stays
- `generate_image_prompt()` — still generates the prompt (model changes in Change 5)
- `image_gen_api.generate()` — still generates via gpt-image-1.5
- `image_gen_api` retry logic (if generation API fails, retry with modified prompt)
- Image dedup tracking via `load_used_image_ids()`
- Reviewer feedback in regen (`_regen_feedback`) still appended to AI prompt
- Quality notes in Sheet column K (simplified — just "AI generated" instead of scores)

### Files to Modify

#### `src/generate_pin_content.py`

**Delete these functions entirely:**
- `_source_pin_image()` (lines 681-734) — WRAPPER that called `source_image()` and generated AI comparison images. Both purposes are gone.
- `source_image()` (lines 308-363) — ROUTER that dispatched by tier. No tiers remain.
- `_source_stock_image()` (lines 737-923) — ~190 lines of stock photo search, ranking, fallback.

**Why not "collapse" them:** `source_image()` was a tier router, `_source_pin_image()` was a wrapper that called the router AND generated AI comparison images as a side effect. They served fundamentally different purposes. Since we're removing both tier routing AND comparison images, both functions are deleted entirely.

**New routing logic in `generate_pin_content()` main function (replaces line 137-149):**
```python
pin_template = pin_spec.get("pin_template", "")
if pin_template == "infographic-pin":
    # Infographic template is text-only, no image needed
    image_path, image_source, image_id, quality_meta = None, "template", "", {}
else:
    # All other templates get an AI-generated image — call simplified function directly
    image_path, image_source, image_id, quality_meta = _source_ai_image(
        pin_spec, claude, image_gen_api, output_dir
    )
```
This replaces `image_source_tier` routing entirely. The infographic-pin template is the only one with zero image references in its HTML. All others (recipe-pin, tip-pin, listicle-pin, problem-solution-pin) use `background_image_url` or `hero_image_url`.

**Rewrite `_source_ai_image()`** — strip out validation. New flow:
1. `claude.generate_image_prompt(pin_spec)` (no `image_source` param — only AI exists)
2. Parse JSON response for `image_prompt` field
3. Append `_regen_feedback` if present
4. `image_gen_api.generate(prompt, 1000, 1500, output_path)` (has its own retry logic)
5. Hash prompt for image_id tracking
6. Return `(path, "ai_generated", f"ai_{hash}", quality_meta)`

**Remove `ImageStockAPI` import** and instantiation from `generate_pin_content()`.

**Remove `image_source_tier` read** — line 137 `pin_spec.get("image_source_tier", "stock")` deleted entirely.

**Clean up quality_meta** — stop populating these fields entirely (omit from pin_data dict, do not set to null/defaults — downstream consumers never read them):
- `image_quality_score` — was from validation scoring
- `image_low_confidence` — was from validation threshold
- `image_source_original` — was for tracking tier fallbacks
- `image_quality_issues` — was from validation feedback
- `_ai_hero_image_path`, `_ai_image_id`, `_ai_image_score` — were for AI comparison images

**Keep these fields:**
- `image_retries` — still relevant (image_gen_api has its own retry logic)
- `image_source` — always `"ai_generated"` now (or `"template"` for infographic-pin)
- `image_id` — still tracked for dedup (`"ai_{hash}"` or `""` for template)

#### `src/apis/claude_api.py`
**Delete `rank_stock_candidates()`** — ~100 lines. Remove entirely.

**Delete `validate_ai_image()`** — ~100 lines. Remove entirely.

**Simplify `generate_image_prompt()`** signature:
- Remove `image_source` parameter entirely — no stock/ai distinction needed
- Remove `stock_retry` branch and its system message
- Remove the "stock" system message path (which loaded `image_search.md` — being deleted)
- Keep: `pin_spec`, `regen_feedback` params
- Keep: `_image_subject_hint` logic
- Keep: system message for AI image prompt generation (loads `image_prompt.md`)
- This will be further modified in Change 5 (GPT-5 Mini switch)
- **Coordinate signature change across all callers** — grep for `generate_image_prompt(` and update:
  - `generate_pin_content.py` line ~969 (primary generation)
  - `regen_content.py` (regen image path — wherever it calls for image regen)

**Delete `generate_image_search_query()`** (line ~436-448) — convenience wrapper that called `generate_image_prompt(image_source="stock")`. Dead code after removing stock search.

#### `src/apis/sheets_api.py`
**Remove `CQ_COL_AI_IMAGE = 12`** constant.

**Remove Column M ("AI Image")** from header row in `write_content_queue()` (line ~324).

**Remove `ai_image_urls` and `blog_ai_image_urls` params** from `write_content_queue()` signature (lines ~278-288) and all write logic that references them (lines ~349, ~375-376, ~391).

**Remove `ai_image` param** from `update_content_row()` signature (lines ~511-537) and its entry in `col_map` (lines ~539-547).

**Shift regen trigger columns:** N→M (label), O→N (trigger). Update all column references.

**Update read ranges after column removal:**
- `read_content_approvals()` (line ~419): change range from `A:M` to `A:L`
- `read_regen_requests()` (line ~475): change range from `A:M` to `A:L`
- Without this fix, these functions would read into the regen trigger columns and break.

**Update `reset_regen_trigger()`** (lines ~575-579): change cell reference from `O1` to `N1`.

**Remove `use_ai_image` from terminal statuses** in `read_content_approvals()` (line ~443).

**Simplify `_build_quality_note()`** — replace complex scoring format (`"AI | Score: 7.5 | Retries: 1 | LOW CONFIDENCE"`) with simple `"AI generated"`. If `image_retries > 0`, append `" (retry {n})"` for visibility.

#### `src/publish_content_queue.py`
**Remove AI hero image upload logic** (lines ~78-86) — delete `gcs.upload_ai_hero_images()` call and surrounding try/except.

**Remove `ai_image_urls` / `blog_ai_image_urls` dict building** (lines ~114-153) — delete the mapping logic that stores `_ai_image_url` into pin data and builds blog-to-AI-image mapping.

**Remove `ai_image_urls` and `blog_ai_image_urls` params** from `write_content_queue()` call (lines ~215-224).

**Shift regen trigger cells** — change range from `N1:O1` to `M1:N1` (line ~252). The write is `["Regen →", "idle"]` — same values, different cell range.

#### `src/regen_content.py`

**CRITICAL: Fix import breakage.** Lines 34-42 import from `generate_pin_content.py`:
```python
from src.generate_pin_content import (
    source_image,        # ← BEING DELETED — must update
    _source_ai_image,    # ← BEING SIMPLIFIED — signature changes
    ...
)
```
After deleting `source_image()`, this import will crash. Update imports to use the simplified `_source_ai_image()` directly.

**Simplify `_regen_item()`:**
- Remove AI comparison generation after primary sourcing (lines ~578-586)
- Remove all `_ai_hero_image_path`, `_ai_image_id`, `_ai_image_score`, `_ai_image_url` handling
- Remove `_source_ai_image` import for comparison purposes (keep import for direct AI sourcing)
- Remove ai_image column update logic (lines ~354-365) — no Column M to write to

**Simplify `_regen_blog_image()`** — remove AI comparison generation block (lines ~831-843).

**Clean up `_update_pin_results()`** — remove AI comparison fields from `keys_to_update` list (line ~895-896): `_ai_hero_image_path`, `_ai_image_id`, `_ai_image_score`, `_ai_image_url`.

**Remove tier routing entirely** (lines ~542-549) — the regen path currently reads `image_source` to determine tier, then routes through `source_image()`. Replace with direct call to simplified `_source_ai_image()`. Same logic as generate path: check `pin_template` — infographic-pin → template-only, everything else → AI.

**Remove dead `image_tier` variable** and all references to it.

**Update `generate_image_prompt()` call sites** — remove `image_source` parameter (coordinated with claude_api.py signature change).

#### `src/blog_deployer.py`
**Remove `use_ai_image` from approval filters** — **6 locations across 3 methods** (each method filters blogs AND pins separately):
- `deploy_approved_content()` — Lines 123 (blogs) + 129 (pins)
- `deploy_to_preview()` — Lines 262 (blogs) + 267 (pins)
- `promote_to_production()` — Lines 378 (blogs) + 383 (pins)

Change all from `status in ("approved", "use_ai_image")` to just `status == "approved"`. (Or keep `"use_ai_image"` as a backwards-compat alias — see migration note below.)

**Delete `_process_ai_image_swaps()`** method (lines 774-851) AND its call block (lines 428-453 in `promote_to_production()`). The call block includes:
- Building `use_ai_pins` list
- Checking `full_pin_data`
- Calling `self._process_ai_image_swaps(use_ai_pins, full_pin_data)`
- Saving modified pin data back to disk
All of this is unnecessary when all images are AI-generated from the start.

**Migration note for `use_ai_image` status:** If a Content Queue from a previous week has rows with `use_ai_image` status, removing it from the terminal set would cause `allContentReviewed()` to block deployment. **Decision: keep `"use_ai_image"` as a terminal status alias** in `trigger.gs` for backwards compatibility, but remove it from blog_deployer approval filters (treat as equivalent to "approved" — which it always was). This avoids needing a manual cleanup step.

#### `src/apps-script/trigger.gs`
**Keep `"use_ai_image"` in `terminal` array** in `allContentReviewed()` (line ~84) for backwards compatibility with any in-flight Content Queues. It does no harm — new weeks will never set this status, but old weeks won't block deployment.

**Shift regen trigger column detection** — `onSheetEdit()` (line ~48): change `getColumn() === 15` to `getColumn() === 14` (Column N in 1-based indexing, since Column M was removed).

**Update `runRegen()`** — change `sheet.getRange("O1").setValue("run")` to `sheet.getRange("N1").setValue("run")` (line ~102).

**Update comments** — all references to "col 15" → "col 14", "Column O" → "Column N".

#### `src/apis/gcs_api.py`
**Delete `upload_ai_hero_images()`** method.

**Keep** `upload_single_image()` (used by regen) and `upload_pin_images()` (used by publish).

#### Prompt files
**Delete `prompts/image_rank.md`** — stock ranking prompt.
**Delete `prompts/image_search.md`** — stock search query prompt.
**Delete `prompts/image_validate.md`** — AI validation prompt.
**Keep `prompts/image_prompt.md`** — AI image generation prompt.

#### Weekly plan prompts
**`prompts/weekly_plan.md`** — Remove `image_source_tier` from pin schema, examples, and field descriptions. Remove the "IMAGE SOURCE ASSIGNMENT" section entirely.
**`prompts/weekly_plan_replace.md`** — Remove `image_source_tier` from replacement schema and constraints.
**`strategy/current-strategy.md`** — Rewrite (not just delete) tier documentation. Two sections need updating:
- Section 5.3 "Image Source Assignment" (lines ~382-391): Replace the tier table with a statement that all images are AI-generated via `gpt-image-1.5`. Keep the section so Claude has context for plan generation.
- Section 12.1 "Planning Fields" (line ~651): Remove the `image_source_tier` row from the field reference table.

#### `src/generate_weekly_plan.py`
No changes needed — `image_source_tier` is not validated or referenced in plan validation.

#### Files NOT changed (verify they still work)
- `src/post_pins.py` — uses `image_url` from pin-schedule.json. Still populated.
- `src/weekly_analysis.py` / `src/monthly_review.py` — `image_source` in content-log.jsonl will always be "ai_generated". Aggregation still works (just one bucket).
- `src/pin_assembler.py` — receives `hero_image_path`. Source-agnostic.
- `src/apis/image_stock.py` — no longer imported. Keep file for potential future use.
- `src/apis/image_gen.py` — unchanged. Still uses gpt-image-1.5.

---

## Change 3: Fix Blog Post Double Title

### Problem
All 4 blog prompt templates instruct Claude to include `# {Title}` in the body. The goslated.com site auto-renders the title from frontmatter → title appears twice.

### Fix

**Prompt templates — remove H1 from Body Structure section:**
- `prompts/blog_post_recipe.md` line 76: remove `# {Recipe Title}`
- `prompts/blog_post_guide.md` line 56: remove `# {Guide Title}`
- `prompts/blog_post_listicle.md` line 73: remove `# {Number} {Topic} {Benefit/Hook}`
- `prompts/blog_post_weekly_plan.md` line 86: remove `# {Plan Title}`

**Example templates — remove the duplicate H1:**
- `templates/blog/recipe-post-example.md` line 44: remove `# 25-Minute Chicken Stir Fry`
- `templates/blog/guide-post-example.md` line 23: remove `# How to Get Your Family...`
- `templates/blog/listicle-post-example.md` line 23: remove `# 7 Easy Weeknight Dinners...`
- `templates/blog/weekly-plan-post-example.md` line 24: remove `# This Week's Family Dinner Plan...`

**Safety net in `src/blog_generator.py`:**
After extracting frontmatter, check if the first non-empty line of the body starts with `# ` and matches the title. If so, strip it. Prevents regression even if Claude ignores the updated prompt.

Implementation detail — add to body extraction (around lines 602-619):
```python
# Strip duplicate H1 if it matches the frontmatter title
body_lines = body.split("\n")
for i, line in enumerate(body_lines):
    stripped = line.strip()
    if not stripped:
        continue  # Skip blank lines
    if stripped.startswith("# "):
        h1_text = stripped[2:].strip()
        if h1_text.lower() == title.lower() or h1_text.lower() in title.lower():
            body_lines[i] = ""  # Remove the duplicate H1
            logger.info("Stripped duplicate H1 from blog body: %s", h1_text)
    break  # Only check the first non-empty line
body = "\n".join(body_lines)
```
Note: There is currently NO header validation in `_validate_generated_post()` (lines 447-514). The safety net is purely in the body extraction step, not validation.

---

## Change 4: Add Plan-Level Feedback & Regeneration

### Current State
Weekly Review tab shows the plan summary. User can only set B3="approved". No way to give feedback on individual topics before generation runs.

### Design

**Weekly Review tab — add columns to blog post rows:**
- Column F: **Status** — blank (default=approved), `regen`
- Column G: **Feedback** — free text (e.g., "too similar to last week's chicken recipe")
- Cell B5: **Plan Regen trigger** — set to "regen" to trigger regeneration

Pin rows don't need individual feedback — pins derive from blogs, so replacing a blog replaces its pins.

**New script: `src/regen_weekly_plan.py`**
1. Read plan regen requests from Sheet (blog rows with status="regen" + feedback)
2. Load current weekly plan JSON from disk
3. Call existing `identify_replaceable_posts()` (from `generate_weekly_plan.py`) to find affected posts + derived pins
4. Call existing `claude.generate_replacement_posts()` with per-post feedback added to context
5. Call existing `splice_replacements()` to swap in new posts/pins
6. Save updated plan JSON
7. Re-write Weekly Review sheet with updated plan
8. Reset B5 to "idle"
9. Send Slack notification

**Reuses existing code:**
- `generate_weekly_plan.py:identify_replaceable_posts()` — maps post → derived pins + slots
- `generate_weekly_plan.py:splice_replacements()` — swaps posts/pins in-place
- `claude_api.py:generate_replacement_posts()` — Claude generates replacements for specific posts

### Files to Modify
- `src/apis/sheets_api.py` — extend `write_weekly_review()` (add Status/Feedback columns), add `read_plan_regen_requests()`, add `reset_plan_regen_trigger()`
- `src/apis/claude_api.py` — extend `generate_replacement_posts()` context dict to include per-post reviewer feedback
- `src/regen_weekly_plan.py` — **NEW** — orchestrator script
- `.github/workflows/regen-plan.yml` — **NEW** — triggered by `repository_dispatch: regen-plan`
- `src/apps-script/trigger.gs` — add B5 watcher for "regen" → dispatch `regen-plan`; add `runPlanRegen()` button function
- `src/apis/slack_notify.py` — add `notify_plan_regen_complete()`

---

## Change 5: Switch Image Prompt & Pin Copy Generation to GPT-5 Mini

### Verified Model ID
- **Model alias:** `gpt-5-mini` (use this in code)
- **Dated snapshot:** `gpt-5-mini-2025-08-07`
- **Pricing:** $0.25/1M input tokens, $2.00/1M output tokens
- **Endpoint:** `https://api.openai.com/v1/chat/completions`

### Current State
Two methods in `claude_api.py` call Claude Sonnet (`MODEL_ROUTINE` = `claude-sonnet-4-20250514`, $3/$15 per MTk):
1. `generate_image_prompt()` (line ~360) — writes the text prompt for AI image generation
2. `generate_pin_copy()` (line 196) — generates title, description, alt text, text overlay for batches of 6 pins

### Goal
Switch both to GPT-5 Mini via OpenAI API — 12x cheaper input, 7.5x cheaper output.

### Design

**Shared helper — `_call_openai_gpt5_mini()`:**
Both methods need the same OpenAI call pattern. Add a private helper to avoid duplication:

```python
def _call_openai_gpt5_mini(self, prompt: str, system: str, max_tokens: int = 500, temperature: float = 0.8) -> str:
    """Call GPT-5 Mini via OpenAI API. Returns response text or raises on failure."""
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        raise ValueError("OPENAI_API_KEY not set")
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-5-mini",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
```

**Modify `generate_image_prompt()`:**
- Try `_call_openai_gpt5_mini()` first with same prompt/system content
- Fallback to Claude Sonnet `_call_api()` if OpenAI fails
- Keep all existing logic (template rendering, `_image_subject_hint`, `regen_feedback`)
- Remove `image_source` param (done in Change 1+2)

**Modify `generate_pin_copy()`:**
- Try `_call_openai_gpt5_mini()` first per batch (max_tokens=4096, temperature=0.7)
- Fallback to Claude Sonnet `_call_api()` if OpenAI fails
- Keep all existing logic: batching (6 pins), `_copy_feedback` handling, JSON parsing
- Same system message, same prompt template

**Fallback for both:** If OpenAI call fails (network error, missing key, rate limit), fall back to Claude Sonnet. Log a warning so failures are visible.

**File:** `src/apis/claude_api.py` — add `_call_openai_gpt5_mini()`, modify `generate_image_prompt()` and `generate_pin_copy()`.

**Env vars:** `OPENAI_API_KEY` — already set in all workflows.

---

## Implementation Order

1. **Change 3 (Blog double title)** — isolated prompt changes. Zero risk to image flow.
2. **Change 5 (GPT-5 Mini for image prompt + pin copy)** — isolated to `claude_api.py`. Easy to test/revert.
3. **Changes 1+2 (Image simplification)** — largest change, most files. Atomic.
4. **Change 4 (Plan feedback)** — new functionality, no existing flow modification.

---

## Verification

### Change 3
- Read updated prompts and examples — no `# {Title}` in body sections
- Verify `blog_generator.py` safety net strips matching H1 from test MDX

### Change 5
- Call `generate_image_prompt()` with test pin_spec → verify usable image prompt JSON returned
- Call `generate_pin_copy()` with test pin_specs → verify usable JSON copy returned
- **Verify JSON parsing compatibility:** GPT-5 Mini may format JSON differently than Claude Sonnet (different whitespace, key ordering, markdown code fences around JSON). Test that existing JSON parsing logic handles GPT-5 Mini output without errors.
- Test fallback by temporarily unsetting OPENAI_API_KEY → both methods should fall back to Claude Sonnet with a logged warning
- Verify model ID `gpt-5-mini` in API calls (not the dated snapshot — alias auto-resolves)

### Changes 1+2
- Verify `generate_pin_content.py` produces pins with `image_source: "ai_generated"` for all non-infographic pins
- Verify no stock API calls are made (ImageStockAPI not imported)
- Verify pin-generation-results.json has no `_ai_hero_image_path` / `_ai_image_score` / `image_quality_score` / `image_low_confidence` fields
- Verify Content Queue has 12 columns (A-L), no Column M "AI Image"
- Verify regen trigger at M1:N1 (not N1:O1)
- Verify `allContentReviewed()` in Apps Script keeps `use_ai_image` in terminal set (backwards compat)
- Verify `blog_deployer.py` filters only on `"approved"` across all 6 locations (3 methods × 2 filters each)
- Verify `_process_ai_image_swaps()` AND its call block (lines 428-453) are both removed
- Verify `post_pins.py` reads pin-schedule.json correctly (image_url still populated)
- Verify `weekly_plan.md` prompt no longer references `image_source_tier`
- Verify `regen_content.py` imports compile — no references to deleted `source_image()` function
- Verify `regen_content.py` no longer calls `generate_image_prompt()` with `image_source` parameter
- Verify `sheets_api.py` read ranges are `A:L` (not `A:M`) in `read_content_approvals()` and `read_regen_requests()`
- Verify `reset_regen_trigger()` writes to `N1` (not `O1`)
- Verify `publish_content_queue.py` writes regen trigger to `M1:N1` (not `N1:O1`)

### Change 4
- Write plan with blog rows including Status/Feedback columns
- Flag one blog as "regen" with feedback
- Run `regen_weekly_plan.py` → verify surgical replacement, sheet update, Slack notification

---

## Files Summary

| File | Changes | Risk |
|------|---------|------|
| `src/generate_pin_content.py` | Delete `_source_stock_image()`, `source_image()`, `_source_pin_image()`; simplify `_source_ai_image()`; remove tier routing; remove quality metadata | HIGH |
| `src/apis/claude_api.py` | Delete `rank_stock_candidates()`, `validate_ai_image()`, `generate_image_search_query()`; simplify `generate_image_prompt()` signature; add GPT-5 Mini helper + fallback for image prompt + pin copy | HIGH |
| `src/regen_content.py` | **Fix import breakage** (deleted `source_image`); remove AI comparison generation; remove tier routing; remove ai_image column updates; update `generate_image_prompt()` call sites | HIGH |
| `src/apis/sheets_api.py` | Remove AI Image col + constant; shift regen cols; update read ranges `A:M`→`A:L`; update `reset_regen_trigger()` `O1`→`N1`; remove `ai_image` params; simplify quality notes; add plan feedback cols | MEDIUM |
| `src/publish_content_queue.py` | Remove AI comparison uploads; remove `ai_image_urls` params; shift regen trigger `N1:O1`→`M1:N1` | MEDIUM |
| `src/blog_deployer.py` | Remove `use_ai_image` from 6 filter locations (3 methods × 2); delete `_process_ai_image_swaps()` AND call block (lines 428-453) | MEDIUM |
| `src/apps-script/trigger.gs` | Keep `use_ai_image` in terminal (backwards compat); shift regen col 15→14; update `runRegen()` `O1`→`N1`; add B5 watcher | LOW |
| `src/apis/gcs_api.py` | Delete `upload_ai_hero_images()` | LOW |
| `prompts/blog_post_*.md` (4) | Remove H1 from body structure | LOW |
| `templates/blog/*-example.md` (4) | Remove duplicate H1 | LOW |
| `src/blog_generator.py` | Add H1 stripping safety net in body extraction | LOW |
| `prompts/weekly_plan.md` | Remove `image_source_tier` from schema, examples, field descriptions, IMAGE SOURCE ASSIGNMENT section | LOW |
| `prompts/weekly_plan_replace.md` | Remove `image_source_tier` from schema, examples, constraints (lines 15, 39, 79, 93) | LOW |
| `strategy/current-strategy.md` | Rewrite Section 5.3 (AI-only images) + remove tier from Section 12.1 | LOW |
| `prompts/image_rank.md` | **DELETE** | LOW |
| `prompts/image_search.md` | **DELETE** | LOW |
| `prompts/image_validate.md` | **DELETE** | LOW |
| `src/regen_weekly_plan.py` | **NEW** — plan regen script | LOW |
| `.github/workflows/regen-plan.yml` | **NEW** — plan regen workflow | LOW |
| `src/apis/slack_notify.py` | Add `notify_plan_regen_complete()` | LOW |
| `src/apis/image_gen.py` | No changes | NONE |
| `src/post_pins.py` | No changes | NONE |
| `src/pin_assembler.py` | No changes | NONE |

### Cross-File Coordination Checklist

These changes span multiple files and must be done atomically:

| Coordination Point | Files Affected |
|---|---|
| `generate_image_prompt()` signature (remove `image_source` param) | `claude_api.py`, `generate_pin_content.py`, `regen_content.py` |
| `source_image()` deletion | `generate_pin_content.py` (definition), `regen_content.py` (import) |
| Column M removal → regen trigger shift | `sheets_api.py`, `publish_content_queue.py`, `trigger.gs` |
| `write_content_queue()` signature (remove AI image params) | `sheets_api.py` (definition), `publish_content_queue.py` (call site), `regen_content.py` (call site) |
| `update_content_row()` signature (remove `ai_image` param) | `sheets_api.py` (definition), `regen_content.py` (call site) |
