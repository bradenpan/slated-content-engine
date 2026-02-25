# Analysis: Image Regeneration Flow — Complete Code Trace

## 1. How Regen Requests Are Read

### Source: `src/apis/sheets_api.py` (lines 449-498)

The regen system reads requests from the **Content Queue** tab of the Google Sheet. The method `SheetsAPI.read_regen_requests()` fetches columns A through L (range `A:L`), then filters for rows where **column J** (index 9, `CQ_COL_STATUS`) starts with the string `"regen"`.

**Columns read for each regen request:**

| Column | Index | Field in dict | Purpose |
|--------|-------|---------------|---------|
| A | 0 | `id` | Internal ID (e.g., "W9-02", "W9-P03") |
| B | 1 | `type` | "pin" or "blog" |
| C | 2 | `title` | Pin/blog title |
| D | 3 | `description` | Description text |
| E | 4 | `board` | Board name (pins only) |
| F | 5 | `slug` | Blog post URL |
| G | 6 | `schedule` | Scheduled date/slot |
| H | 7 | `pillar` | Content pillar (1-5) |
| I | 8 | (thumbnail) | Not read by regen |
| J | 9 | `status` | Regen type: "regen_image", "regen_copy", or "regen" |
| K | 10 | `notes` | Reviewer notes |
| L | 11 | `feedback` | **Reviewer feedback for regen** (the critical field) |

### Trigger mechanism

The regen workflow is triggered via Google Apps Script (`src/apps-script/trigger.gs`, line 47-51). When cell **N1** of the Content Queue tab is set to `"run"`, the Apps Script fires a `repository_dispatch` event to GitHub Actions with event type `regen-content`. The reviewer workflow is:

1. Reviewer marks rows with `regen_image`, `regen_copy`, or `regen` in column J
2. Reviewer writes specific feedback in column L
3. Reviewer types `run` in cell N1
4. Apps Script dispatches GitHub Actions workflow
5. `regen_content.py` runs on the GitHub Actions runner

---

## 2. Regen Dispatch Logic

### Source: `src/regen_content.py` (lines 51-400)

The main `regen()` function:

1. Reads all regen requests from Sheets
2. Loads `pin-generation-results.json` (canonical pin data from initial generation)
3. Loads `blog-generation-results.json` (for blog image regens)
4. Iterates through each request, dispatching based on `item_type` and `regen_type`

### Dispatch decision tree:

```
For each request:
  if type == "blog":
    if regen_type == "regen_copy":
      -> SKIP (not supported, log warning, reset to pending_review)
    if regen_type == "regen" (both):
      -> Treat as regen_image only (with note)
    -> Call _regen_blog_image()

  if type == "pin":
    -> Look up pin_data in pin-generation-results.json by pin_id
    -> Call _regen_item(pin_data, regen_type, feedback, ...)
```

### Blog regen path (`_regen_blog_image`, lines 661-759)

Blog images are **raw stock/AI photos** (not rendered through pin templates). The function:
1. Builds a minimal `pin_spec` from blog data (title used as primary_keyword, "recipe-pin" template context)
2. Adds `_regen_feedback` to pin_spec if feedback exists
3. Calls `source_image()` with tier determined from previous source
4. Saves hero with slug-based filename for `blog_deployer.py`
5. Uploads raw hero to GCS with timestamped name (cache-busting)

### Pin regen path (`_regen_item`, lines 403-646)

For pins, the function handles three regen types:

**regen_image**: Re-sources the hero image using `source_image()`, re-renders the pin, uploads to GCS.

**regen_copy**: Calls `generate_copy_batch()` with the pin_spec (including `_copy_feedback`). Updates title, description, alt_text, text_overlay.

**regen (both)**: Runs copy regen first, then image regen, then re-renders with new copy + new image.

---

## 3. Pin Spec Reconstruction

### Source: `src/regen_content.py` (lines 429-445)

During regen, a `pin_spec` is rebuilt from the stored `pin_data` in `pin-generation-results.json`:

```python
pin_spec = {
    "pin_id": pin_id,
    "pin_topic": pin_data.get("title", ""),           # Uses the generated TITLE, not original topic
    "target_board": pin_data.get("board_name", ""),
    "pillar": pin_data.get("pillar"),
    "primary_keyword": pin_data.get("primary_keyword", ""),
    "secondary_keywords": pin_data.get("secondary_keywords", []),
    "pin_template": pin_data.get("template", "recipe-pin"),
    "template_variant": pin_data.get("template_variant", 1),
    "content_type": pin_data.get("content_type"),
    "funnel_layer": pin_data.get("funnel_layer", "discovery"),
    "image_source_tier": pin_data.get("image_source", "stock"),
}
```

**Key difference from initial generation**: During initial gen, `pin_topic` comes from the weekly plan (e.g., "Lemon Herb One-Pan Chicken — Spring Vegetables"). During regen, `pin_topic` is the **generated title** (which may have been shortened/reworded by the copy generation prompt). This could cause the image search to use slightly different terms.

### Feedback incorporation

Feedback is attached to the pin_spec at line 443-444:
```python
if feedback:
    pin_spec["_regen_feedback"] = feedback
```

For copy regen, a separate `_copy_feedback` field is set (line 456-457):
```python
if feedback:
    copy_spec["_copy_feedback"] = feedback
```

---

## 4. `source_image()` During Regen vs Initial Gen

### Source: `src/generate_pin_content.py` (lines 297-352, 697-1021)

The `source_image()` function is **identical** for regen and initial gen. It dispatches based on `image_tier`:
- `"stock"` or `"Tier 1"` -> `_source_stock_image()`
- `"ai"` or `"Tier 2"` -> `_source_ai_image()`
- `"template"` or `"Tier 3"` -> No image (returns None)

### Image source tier IS locked to the original

In `regen_content.py` lines 483-489:
```python
original_source = pin_data.get("image_source", "stock")
if original_source in ("unsplash", "pexels", "stock"):
    image_tier = "stock"
elif original_source == "ai_generated":
    image_tier = "ai"
else:
    image_tier = "stock"
```

If the original pin used stock photos, regen will only search stock photos. If the original used AI generation, regen will only use AI generation. **There is no way for regen to switch tiers.** This is the root cause of the "this should be a stock image not a template" feedback pattern -- pins that were originally `"template"` tier would map to `image_tier = "stock"` via the else branch, but the original `image_source` was likely stored as something that routes to stock.

However, looking at the logs, the real issue is that pins assigned "Tier 3" (template-only) in the plan had `image_source` stored as `"template"` in pin-generation-results.json. During regen, the `_regen_item` function maps `image_source = "template"` to `image_tier = "stock"` via the else fallback. So template-only pins **do** get re-sourced with stock images during regen, which is the correct behavior when the reviewer explicitly requests a stock image.

### Key differences during regen

1. **Feedback reaches the search query prompt**: `_source_stock_image()` passes `regen_feedback` to `claude.generate_image_prompt()`, which appends it to the system message.

2. **Same quality gate applies**: The 6.5 threshold, retry logic, and AI fallback all work the same way.

3. **Dedup uses accumulated list**: `used_image_ids` includes both historically used IDs and any IDs consumed during the current regen session (line 512-513), preventing the same image from being re-selected.

---

## 5. Feedback Propagation — Where It Reaches and Where It's Lost

### Summary table

| Stage | Feedback reaches? | How? | Effective? |
|-------|-------------------|------|------------|
| Search query generation | YES | System message append in `claude_api.py:414-418` | Partially -- guides query terms |
| Candidate ranking (Haiku) | PARTIALLY | Buried in `{{PIN_SPEC}}` JSON dump | Weak -- no explicit instruction to avoid complaint |
| AI image prompt generation | YES | System message append + appended to prompt text (lines 938-941) | Yes |
| AI image validation | NO | Not passed at all | N/A |
| Copy regen | YES | `_copy_feedback` field in pin_spec, checked in `claude_api.py:245-252` | Yes -- added to system message |

### Detailed trace

#### Search query generation (stock path)

**File**: `src/apis/claude_api.py`, method `generate_image_prompt()` (lines 360-428)

Feedback reaches via system message:
```python
if regen_feedback:
    system_msg += (
        f" IMPORTANT: The previous image was rejected by the reviewer with this "
        f"feedback: {regen_feedback}. Generate a search query that specifically "
        f"addresses this feedback."
    )
```

This is effective -- the search query generation prompt gets explicit instruction about what went wrong. Looking at the logs, for W9-02 ("this is chicken with oranges, the recipe talks about lemon herb chicken"), the search query generated was "overhead lemon herb chicken vegetables one pan" -- correctly incorporating the feedback about needing lemon herb chicken.

#### Candidate ranking (Haiku vision)

**File**: `src/apis/claude_api.py`, method `rank_stock_candidates()` (lines 673-772)

The pin_spec (including `_regen_feedback`) is passed as the `{{PIN_SPEC}}` template variable to `image_rank.md`. However:

1. **Feedback is buried in a JSON dump**. The `_regen_feedback` field appears as just another field in a serialized JSON object.
2. **The `image_rank.md` prompt has NO mention of regen feedback**. It has no instruction to look for feedback or penalize images matching the complaint.
3. **The system message** ("You are a visual quality evaluator...") has NO regen-specific guidance.
4. **Result**: Haiku scores purely on visual match to the topic, potentially selecting an image with the same defect the reviewer complained about.

Evidence from logs: For W9-02, Haiku gave score 8.0 to a candidate described as "lemon herb chicken with fresh vegetables" -- but the post-regen review (from the regen Excel) shows this pin was **still rejected**, suggesting Haiku may have misidentified the food content at thumbnail resolution.

#### AI image prompt generation

**File**: `src/generate_pin_content.py`, `_source_ai_image()` (lines 886-1021)

Feedback reaches in TWO places:
1. System message (via `claude.generate_image_prompt(pin_spec, image_source="ai", regen_feedback=regen_feedback)`)
2. Appended to the image generation prompt itself (lines 939-941):
```python
if regen_feedback:
    image_prompt = (
        f"{image_prompt}\n\nCRITICAL -- previous image was rejected: {regen_feedback}"
    )
```

This double injection is effective for AI image generation.

#### AI image validation (Sonnet vision)

**File**: `src/apis/claude_api.py`, `validate_ai_image()` (lines 774-872)

The validation prompt (`image_validate.md`) receives `{{PIN_SPEC}}` (which contains `_regen_feedback`) but the prompt template has **no instructions** about checking against regen feedback. The validation purely evaluates the image against standard quality criteria. Regen feedback about what was wrong with the previous image is not surfaced as evaluation criteria.

#### Copy regen

**File**: `src/apis/claude_api.py`, `generate_pin_copy()` (lines 196-272)

Feedback reaches effectively. When `_copy_feedback` is present on any pin in the batch (line 245-246):
```python
has_feedback = any(spec.get("_copy_feedback") for spec in batch)
if has_feedback:
    system += (
        " IMPORTANT: One or more pins have a '_copy_feedback' field containing "
        "reviewer feedback on the previous version. Read each pin's _copy_feedback "
        "carefully and address the feedback specifically in the new copy. "
        "The previous version was rejected for the stated reason."
    )
```

This is well-designed -- the system message explicitly directs the model to read and address the feedback.

---

## 6. Regen Limitations

### Blog copy regen is NOT supported
Blog text lives in MDX files (committed to git). The regen system cannot modify committed files. If `regen_copy` is requested for a blog item, it logs a warning and resets to `pending_review` with a note: "Blog copy regen not supported -- only image regen available." (lines 125-144)

### Blog image regen had a critical bug (now fixed)
In the regen run logs, blog items (W9-P03, W9-P04, W9-P06, W9-P08, W9-P09, W9-P10) all failed with "Blog regen not supported." The warning message at line 11 of the logs says "Blog regen not supported" even though the code at lines 122-243 does have blog image regen support. **This was a bug**: the code was checking for blog data in `blog_results` but the blog result key format didn't match the item ID format. The `blog_results` dict uses `post_id` as keys (from `blog-generation-results.json`), and the lookup at line 149 (`blog_data = blog_results.get(item_id)`) failed because the dict was empty or the keys didn't match. The actual log shows the WARNING message format from line 151, meaning `blog_data` was `None`.

**Update**: Looking more carefully at the log output, lines 11, 14, 17, 20, 23, 26 all show "Blog regen not supported" -- but that's the log message from the code path at line 127 which is the `regen_copy` check. Actually, re-reading the log: the status for these was `regen_image` not `regen_copy`. So the code should have fallen through to the blog image regen path. The "Blog regen not supported" message in the logs doesn't match any log message in the current code. This indicates the code was updated after this run -- the commit `fd655ea` (fix: 5 pre-existing bugs) likely fixed the blog regen path.

### Image source tier is locked
As documented in section 4, regen cannot switch between stock/AI/template tiers. If the reviewer wants a fundamentally different image source, they must manually override.

### Only one retry search
The stock image path does one retry with broader terms if the initial search scores below 6.5. After that, it falls back to AI generation. There's no mechanism for multiple retry strategies.

### Only first search query is used
The search prompt generates 3-5 queries, but only `queries[0]` is used (line 738). During regen, this limits the candidate pool unnecessarily.

### No comparison to original image
Regen doesn't know what the previous image actually looked like. It only knows the textual feedback. If the feedback is vague ("this picture doesn't match"), the system has no visual context of what went wrong.

### No memory of previously rejected candidates
If regen selects the same image that was initially used (because it scores well on the same criteria), there's no mechanism to detect this. The dedup system only checks the `used_image_ids` list from `content-log.jsonl`, which only contains posted pins.

---

## 7. Prompt Differences: Regen vs Initial Gen

### Same prompts used, feedback appended

The regen system uses the **exact same prompt templates** as initial generation:
- `prompts/image_search.md` -- stock photo search queries
- `prompts/image_rank.md` -- candidate ranking
- `prompts/image_prompt.md` -- AI image generation
- `prompts/image_validate.md` -- AI image validation
- `prompts/pin_copy.md` -- pin copy generation (via `generate_copy_batch`)

The only differences are:
1. **System message augmentation**: `generate_image_prompt()` appends feedback to the system message for search queries and AI prompts
2. **Copy feedback flag**: `generate_pin_copy()` gets an extra system message clause when `_copy_feedback` is present
3. **AI prompt text modification**: `_source_ai_image()` appends feedback directly to the prompt text

No regen-specific prompt templates exist.

---

## 8. Regen Results Analysis

### Source: `troubleshooting/regen-flagged-content-22326-logs.md`

### Run summary

- **Date**: 2026-02-23 21:39-21:44 (about 5 minutes total)
- **Total regen requests**: 21
- **Succeeded**: 15
- **Failed**: 6
- **Total API cost**: $0.2487

### Detailed breakdown by item

#### Blog regens (6 items, ALL FAILED)

| ID | Feedback | Outcome |
|----|----------|---------|
| W9-P03 | "this is a picture of vegetables, not a picture of mac and cheese WITH vegetables" | FAILED: "Blog regen not supported" |
| W9-P04 | "there is no picture here. what is supposed to go in this spot?" | FAILED: "Blog regen not supported" |
| W9-P06 | "this picture has noodles, the recipe is just salmon teriyaki." | FAILED: "Blog regen not supported" |
| W9-P08 | "there is no picture" | FAILED: "Blog regen not supported" |
| W9-P09 | "this picture has nothing to do with the blog post" | FAILED: "Blog regen not supported" |
| W9-P10 | "this is a picture of meatballs in tomato sauce. the recipe calls for meatball bo[wls]" | FAILED: "Blog regen not supported" |

All 6 blog regens failed because blog regen support was broken at the time of this run.

#### Pin regens (15 items, ALL SUCCEEDED technically)

| ID | Type | Feedback | Score | Outcome |
|----|------|----------|-------|---------|
| W9-02 | regen_image | "this is chicken with oranges, the recipe talks about lemon herb chicken" | 8.0 | New image sourced |
| W9-09 | regen (both) | "this is a picture of vegetables not a picture of macaroni and cheese with vegetables" | 9.0 | New copy + new image |
| W9-12 | regen_image | "this picture has noodles. this should be a bowl with teriyaki salmon, white rice" | 7.5 | New image sourced |
| W9-16 | regen_image | "this is turkey meatballs in tomato sauce not Turkey meatballs over rice and vegg" | 7.5 | New image sourced |
| W9-17 | regen_image | "i have no idea what this is a picture of but it is not chicken and rice in one p[an]" | 9.0 | New image sourced |
| W9-18 | regen_image | "this is a picture of broccoli, not a picture of beef and broccoli stir-fry" | 7.5 | New image sourced |
| W9-19 | regen (both) | "this should be a stock image not a template" | 8.5 | New copy + new image |
| W9-20 | regen_image | "this should be a stock image not a template" | 8.0 | New image sourced |
| W9-21 | regen_image | "this should be a stock image not a template" | 8.5 | New image sourced |
| W9-22 | regen_image | "this should be a stock image not a template" | 8.5 | New image sourced |
| W9-23 | regen_image | "this should be a stock image not a template" | 8.5 | New image sourced |
| W9-24 | regen_image | "this should be a stock image not a template" | 7.5 | New image sourced |
| W9-25 | regen_image | "this should be a stock image not a template" | 8.0 | New image sourced |
| W9-26 | regen_image | "this should be a stock image not a template" | 9.0 | New image sourced |
| W9-27 | regen_image | "this is a picture of flowers. the recipe is pasta primavera with vegetables" | 8.0 (after retry) | New image sourced (required retry -- initial best was 3.0) |

### Feedback pattern categories

1. **Wrong food subject** (7 items: W9-02, W9-09, W9-12, W9-16, W9-17, W9-18, W9-27): The initial image showed the wrong food. This is the most actionable feedback type -- the search query generation correctly pivots to the right food term.

2. **Template-only needs stock** (8 items: W9-19, W9-20, W9-21, W9-22, W9-23, W9-24, W9-25, W9-26): Pins originally assigned template-only (Tier 3) but the reviewer wanted real food photography. These all succeeded because the fallback tier mapping routes template -> stock.

3. **Missing image** (2 blog items: W9-P04, W9-P08): No image was generated at all. Failed due to blog regen bug.

4. **Wrong food + blog** (4 blog items: W9-P03, W9-P06, W9-P09, W9-P10): Correct complaint about wrong food, but blog regen was broken.

### Quality scores

Pin regen quality scores from the ranking model:
- Average: 8.1
- Min: 7.5 (W9-12, W9-16, W9-18, W9-24)
- Max: 9.0 (W9-09, W9-17, W9-26)
- One retry needed: W9-27 (initial best 3.0, retry got 8.0)

### Post-regen approval results

Based on the `regen-quality-improvements.md` analysis document:

The prior analysis indicates that after regen, the reviewer still rejected some pins where the image quality score was high but the actual food subject was still wrong. The W9-02 case is notable: Haiku scored it 8.0 ("lemon herb chicken with fresh vegetables") but the image may have been misidentified at thumbnail resolution.

### Overall statistics

| Category | Count | Percentage |
|----------|-------|------------|
| Total regen requests | 21 | 100% |
| Blog regens (all failed due to bug) | 6 | 29% |
| Pin regens (technically succeeded) | 15 | 71% |
| Pins requiring retry search | 1 (W9-27) | 5% |
| Total API cost | $0.25 | -- |
| Avg time per pin regen | ~17 seconds | -- |

---

## 9. Critical Findings

### Finding 1: Feedback does NOT reach the candidate ranking prompt effectively

The most impactful gap. During regen, the reviewer's specific complaint (e.g., "this is chicken with oranges, not lemon herb chicken") is included in the pin_spec JSON but:
- The `image_rank.md` prompt has zero mention of regen feedback
- The system message for ranking has no regen-specific guidance
- Haiku processes `_regen_feedback` as just another metadata field in a JSON blob

This means the ranking model can select an image with the **exact same defect** the reviewer complained about.

### Finding 2: Blog regen was completely broken during this run

All 6 blog image regens failed. The code structure suggests this was a data lookup bug (`blog_results.get(item_id)` returning None) rather than a fundamental design issue. The commit `fd655ea` appears to have fixed this.

### Finding 3: Only one search query is used out of 3-5 generated

The search prompt (`image_search.md`) is designed to generate 3-5 queries ranging from specific to broad. But `_source_stock_image()` only uses `queries[0]`. During regen -- when the initial query already failed to find good results -- using only one query limits the candidate pool unnecessarily.

### Finding 4: Template-to-stock tier switching works by accident

Pins marked as template-only that get regen'd end up on the stock path because `image_source = "template"` falls into the `else` branch that defaults to `"stock"`. This is correct behavior but appears unintentional.

### Finding 5: pin_topic uses generated title, not original topic

During regen, `pin_spec["pin_topic"]` is set to `pin_data.get("title", "")` -- the AI-generated title. During initial gen, `pin_topic` comes from the weekly plan's `pin_topic` field, which is the raw topic description. The generated title is often shorter and more "Pinterest-optimized," which may produce different (potentially worse) search queries.

### Finding 6: Validation prompt ignores regen context

The `image_validate.md` prompt (used for AI-generated images) has no awareness that this is a regen. It doesn't know what was wrong with the previous image, so it can't specifically check for the complained-about defect.

### Finding 7: No tracking of what was tried

The regen system doesn't store the search queries used, the candidates evaluated, or the scores of rejected candidates. This makes debugging regen failures impossible without reading the full GitHub Actions logs.
