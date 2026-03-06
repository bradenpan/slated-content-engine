# TikTok Two-Phase Approval Flow — Implementation Plan

**Date:** 2026-03-05
**Status:** Draft — awaiting review

---

## Problem

The current TikTok pipeline is a single-pass approval:
1. `generate_weekly_plan.py` generates specs + renders all slides + publishes to Sheet in one shot
2. Reviewer sees a single Content Queue tab with one preview image per carousel
3. Approve/reject at the carousel level → schedule → post

This has three problems:
- **No plan review before rendering.** Claude calls + image generation + Puppeteer rendering are expensive. If the plan is bad, all that work is wasted.
- **Only one preview image visible.** Carousels have 5-9 slides but the Sheet only shows `=IMAGE()` for the first slide. You can't review what you can't see.
- **No granular regen.** You can only approve or reject a whole carousel. No way to say "the hook slide is weak" or "slide 3 needs different wording" without rejecting the entire carousel.

## Solution

Split into two phases, mirroring the Pinterest pattern (Weekly Review → Content Queue) but with carousel-specific slide-level granularity.

### Phase 1 — Plan Review (before rendering)
- Review carousel **specs** (topic, angle, structure, hook type, hook text, template family)
- Approve / reject / regen individual carousel specs
- Provide feedback for regen ("this topic overlaps with last week", "try a comparison angle instead")
- Only approved specs proceed to rendering

### Phase 2 — Content Review (after rendering)
- Review all rendered slides per carousel (hook, content slides, CTA) — visible inline in Sheet
- Approve / reject individual carousels
- Visual regen: regenerate a specific slide's AI image, or full carousel re-render
- Text was already approved in Phase 1 — Phase 2 is purely visual review

---

## Target Sheet Tab Structure (TikTok)

### Tab 1: Weekly Review (Plan Phase)
Human reviews carousel specs before any rendering happens.

**Control cells:**
| Cell | Purpose |
|------|---------|
| B3   | Plan status: `pending_review` / `approved` / `rejected` |
| B4   | (Future) Manual scheduling override trigger |
| B5   | Plan regen trigger: `idle` / `regen` |
| B6   | Last plan trigger timestamp (written by Apps Script on dispatch) |

**Carousel spec rows (starting row 7):**
| Col | Header | Content |
|-----|--------|---------|
| A | ID | Carousel ID (e.g., `TK-W10-01`) |
| B | Topic | Topic value from taxonomy |
| C | Angle | Angle value from taxonomy |
| D | Structure | Structure value from taxonomy |
| E | Hook Type | Hook type value from taxonomy |
| F | Template Family | `clean_educational`, `dark_bold`, etc. |
| G | Hook Text | The hook slide headline |
| H | Slide Text Preview | Concatenated text from all slides (hook headline + content headlines + CTA) for scannable review |
| I | Caption | TikTok caption (preview, truncated) |
| J | Status | `pending_review` / `approved` / `rejected` / `regen` |
| K | Feedback | Reviewer instructions for regen (see below) |

**Feedback column supports granular instructions:**
- `regen` (or empty feedback with status=regen) — Claude replaces entire carousel spec
- `regen slide 3` — Claude regenerates content slide 3 wording only
- `regen hook` — Claude regenerates hook text only
- `change slide 3 to "Here's what actually works"` — direct text replacement, no Claude call
- `change hook to "Stop doing this"` — direct text replacement
- Free-form feedback (e.g., `"slide 3 overlaps with last week"`) — passed as context to Claude for full regen

The regen_plan.py script parses the feedback to determine whether it's a direct edit or an AI regen. Direct edits update the plan JSON immediately without a Claude call.

**Workflow:**
1. `tiktok-weekly-review.yml` (Monday cron) runs `generate_weekly_plan.py --plan-only` → writes specs to Weekly Review tab
2. Reviewer opens Sheet, reads each carousel spec and slide text preview
3. For each carousel: set status to `approved`, `rejected`, or `regen` (with specific instructions in col K)
4. If any `regen`: set B5 = `regen` → triggers `tiktok-regen-plan.yml` → applies direct edits or Claude regeneration per feedback → re-writes Weekly Review tab → back to step 2
5. **B3 = `approved` means ALL carousel specs are approved.** The reviewer must resolve all `rejected` and `regen` statuses before setting B3. Rejected carousels should be regen'd into something acceptable or changed to `approved`. The plan JSON does not store per-carousel approval status — B3 is the single gate. `generate_content_from_plan()` renders ALL specs in the plan JSON (it does not read the Sheet for per-carousel status).
6. When all specs approved: set B3 = `approved` → triggers `tiktok-generate-content.yml` → renders all specs → writes to Content Queue tab

### Tab 2: Content Queue (Content Phase)
Human reviews rendered slides. All slides visible inline.

**Control cells:**
| Cell | Purpose |
|------|---------|
| R1   | Content regen trigger: `idle` / `run` |
| R2   | Last content trigger timestamp (written by Apps Script on dispatch) |

**Carousel rows (starting row 2):**
| Col | Header | Content |
|-----|--------|---------|
| A | ID | Carousel ID |
| B | Topic | Topic |
| C | Template Family | Template family |
| D | Hook | `=IMAGE(hook_slide_url)` |
| E | Slide 1 | `=IMAGE(slide_1_url)` |
| F | Slide 2 | `=IMAGE(slide_2_url)` |
| G | Slide 3 | `=IMAGE(slide_3_url)` |
| H | Slide 4 | `=IMAGE(slide_4_url)` |
| I | Slide 5 | `=IMAGE(slide_5_url)` |
| J | Slide 6 | `=IMAGE(slide_6_url)` |
| K | Slide 7 | `=IMAGE(slide_7_url)` |
| L | CTA | `=IMAGE(cta_slide_url)` |
| M | All Slides Link | Clickable GCS folder link |
| N | Caption | Full caption text |
| O | Status | `pending_review` / `approved` / `rejected` / `regen_image_N` / `regen` |
| P | Feedback | Reviewer feedback for regen |
| Q | Notes | System notes (render errors, regen history) |

Columns E-K hold content slide previews. Carousels with fewer than 7 content slides leave the extra columns blank. All 9 possible slides (hook + 7 content + CTA) are always visible inline — no slides are hidden behind a link.

**Regen status values (Phase 2 is visual-only — text was approved in Phase 1):**
- `regen_image_0` — Regenerate hook slide's AI image (new image gen call + re-render). Only valid for slides that have an AI-generated image.
- `regen_image_2` — Regenerate content slide 2's AI image
- `regen_image_0,regen_image_3` — Comma-separated for multiple slide images
- `regen` — Full carousel re-render (new images for all image slides + re-render all)

`regen_image_N` uses **Content Queue column-position numbering**: 0=hook (col D), 1-7=content slides (cols E-K), 8=CTA (col L). This is a fixed layout — it does NOT vary with the carousel's actual slide count. The regen script translates column-position N to the actual `slide_index` in the carousel's slide array using the spec's `content_slides` length (e.g., on a carousel with 3 content slides, column-position 8 maps to slide_index 4). `image_prompts` uses actual `slide_index`, so this translation is required. Setting `regen_image_N` on a slide that has no AI image is a no-op (note written to Notes column). Setting `regen_image_N` where N exceeds the carousel's actual slide count is also a no-op.

**Workflow:**
1. `tiktok-generate-content.yml` renders all specs from the approved plan → generates per-slide images where specified → uploads all slides to GCS → writes Content Queue with `=IMAGE()` per slide
2. Reviewer opens Sheet, scrolls through each carousel's slides
3. For each carousel: approve, reject, or set specific regen status with feedback
4. If any regen: set R1 = `run` → triggers `tiktok-regen-content.yml` → regenerates targeted images + re-renders → updates Content Queue → back to step 2
5. When all reviewed (approved/rejected): triggers `tiktok-promote-and-schedule.yml` → schedules approved carousels

### Tab 3: Post Log
Same as current — records posted carousels with publer_post_id, date, status.

### Tab 4: Dashboard
Same as current — weekly/monthly metrics from analytics pulls.

---

## Implementation Phases

### Phase A: Split Plan Generation from Rendering
**Goal:** `generate_weekly_plan.py` gains a `--plan-only` flag that stops after Claude spec generation (no rendering, no GCS, no Content Queue write).

**Files to modify:**
- `src/shared/paths.py`
  - Add `TIKTOK_DATA_DIR = DATA_DIR / "tiktok"` (currently defined only in `generate_weekly_plan.py` line 43 — promoting it so `regen_plan.py` and `regen_content.py` can import it without depending on the orchestrator)

- `src/tiktok/generate_weekly_plan.py`
  - Replace local `TIKTOK_DATA_DIR = DATA_DIR / "tiktok"` with import from `src.shared.paths`
  - Add `plan_only: bool = False` parameter to `generate_plan()`
  - When `plan_only=True`: skip Steps 10, 12-14 (rendering, GCS upload, Content Queue publish, Slack). Step 9 is permanently removed (see below), not conditionally skipped.
  - Keep Step 11 (save plan JSON locally — needed for regen and content generation)
  - In plan-only mode, do NOT enrich plan with `_rendered` key (rendering hasn't happened yet). `generate_content_from_plan()` (Phase D) adds `_rendered` after rendering.
  - After saving: write specs to Weekly Review tab via new `sheets.write_tiktok_weekly_review()`
  - After writing: commit + push plan JSON with `[skip ci]` (same pattern as content-log.jsonl)
  - Add `--plan-only` flag to the `__main__` argparse block (Phase B's workflow depends on this CLI argument)

**Also modify:**
- `prompts/tiktok/weekly_plan.md`
  - Update output schema: each carousel spec includes `image_prompts` array of `{slide_index, prompt}` entries
  - Example schema addition:
    ```json
    "image_prompts": [
      {"slide_index": 0, "prompt": "Warm overhead shot of a family kitchen counter with scattered grocery lists and school forms"},
      {"slide_index": 2, "prompt": "Close-up of hands organizing a shared calendar app on a phone"}
    ]
    ```
  - `slide_index` uses the carousel's actual slide ordering (0=hook, 1..N=content slides, last=CTA). CTA slide index must never appear in `image_prompts`.
  - Add image rules per family (see Design Decision #2)
  - This must happen in Phase A (not Phase D) because `--plan-only` runs the planning prompt and the plan JSON needs `image_prompts` from the start

- `src/tiktok/generate_weekly_plan.py`
  - Remove Step 9 (`claude.generate_tiktok_image_prompt()` loop) — image prompts now come from the planning prompt output, not a separate Claude call
  - Do NOT add `image_prompts` to `REQUIRED_CAROUSEL_KEYS` (Claude may omit it for non-photo-forward carousels). Instead, default to `[]` if missing: in `_validate_plan()`, set `carousel.setdefault("image_prompts", [])` before validation.
  - Add validation in `_validate_plan()`: `len(image_prompts) <= 3`, non-`photo_forward` must have empty array, CTA slide index never in `image_prompts`

- `src/shared/apis/claude_api.py`
  - Delete `generate_tiktok_image_prompt()` method (line ~647). This is a fully implemented method that loads `prompts/tiktok/image_prompt.md` and generates a single image prompt per carousel. It becomes dead code after Step 9 removal — image prompts now come from the planning prompt output via the `image_prompts` array.

- `prompts/tiktok/image_prompt.md`
  - Delete file (becomes dead code after `generate_tiktok_image_prompt()` deletion above)

**New SheetsAPI methods** (note: `write_tiktok_weekly_review()` already exists as a stub at `sheets_api.py` line ~989 with parameter name `review_data` — replace the stub with the full implementation below):
- `write_tiktok_weekly_review(plan: dict)` — Writes carousel specs to Weekly Review tab with control cells. Generates the Slide Text Preview column (col H) by concatenating: hook headline → content slide headlines (numbered) → CTA text. Example: `"Hook: 5 things your partner doesn't track | 1. Grocery inventory 2. School forms 3. ... | CTA: Follow @slatedapp"`
- `read_tiktok_plan_status()` — Reads B3 value
- `read_tiktok_plan_regen_requests()` — Reads carousel rows where status = `regen`, returns list of `{carousel_id, feedback}`

**Estimated scope:** ~100 lines modified, ~80 lines new SheetsAPI methods

### Phase B: Workflow Updates
**Goal:** Update existing TikTok workflows for the two-phase flow.

**Files to modify:**
- `.github/workflows/tiktok-weekly-review.yml`
  - Change to run `generate_weekly_plan.py --plan-only` instead of full generation
  - Remove Node.js/Puppeteer steps (not needed for plan-only)
  - Keep `weekly_analysis.py` and `compute_attribute_weights.py --update` steps (they're independent of rendering)
  - Add cron collision guard: run `python -m src.tiktok.generate_weekly_plan --check-plan-status` as a pre-step. This calls `sheets.read_tiktok_plan_status()` (Phase A) and exits with code 0 if B3 is `idle`/`rejected`/empty (proceed), or exits with code 78 (neutral) if a review is in progress (skip). The workflow uses `if: steps.check.outcome == 'success'` to gate the generation step. On skip, sends Slack warning. (See Design Decision #7.)

- `.github/workflows/tiktok-promote-and-schedule.yml`
  - No workflow YAML changes needed, BUT the Python code it calls (`promote_and_schedule.py` → `sheets.read_tiktok_approved_carousels()`) requires the SheetsAPI column index updates from Phase D. **Phase D must be deployed before this workflow can run against the new schema.**

- `.github/workflows/tiktok-daily-post.yml`
  - No workflow YAML changes needed, BUT `post_content.py` → `sheets.update_tiktok_content_status()` requires the same SheetsAPI updates from Phase D.

**Estimated scope:** ~30 lines modified

### Phase C: Plan-Level Regen
**Goal:** Regenerate or directly edit individual carousel specs flagged in Weekly Review. Supports both AI regen and manual text replacement via the feedback column.

**New files:**
- `src/tiktok/regen_plan.py` — Plan-level regeneration orchestrator
  - Reads regen requests from Weekly Review tab (status=`regen` rows with feedback)
  - Loads current plan JSON from disk via `find_latest_plan(data_dir=TIKTOK_DATA_DIR)` — **must pass TikTok-specific data dir**, otherwise it defaults to `data/` and finds Pinterest plans
  - Parses each feedback instruction to determine action type:
    - `change hook to "..."` / `change slide N to "..."` → direct edit (update plan JSON, no Claude call)
    - `regen hook` / `regen slide N` → targeted Claude regen (regenerate specific slide wording with feedback context)
    - `regen` / free-form feedback → full carousel Claude regen
  - Applies direct edits immediately to the plan JSON
  - Batches Claude regen requests (one call per carousel, as discussed)
  - Splices all changes into plan
  - **Writes Sheet first, then commits JSON.** Re-writes Weekly Review tab (all specs, preserving B3/B5 control cells). Only after a successful Sheet write: saves plan JSON to disk, commits + pushes with `[skip ci]`. This ordering ensures the Sheet (what the reviewer sees) and the plan JSON (what rendering reads) never silently diverge — if the Sheet write fails, the JSON is not committed; if the commit fails after a successful Sheet write, the JSON can be re-committed on retry.
  - Resets B5 to `idle`

**New Claude API method:**
- `claude.regenerate_tiktok_carousel_specs(specs_to_replace, feedback, kept_specs, taxonomy)` — Returns replacement carousel specs. Supports targeted regen (specific slides) via the feedback parameter.

**New prompt template:**
- `prompts/tiktok/regen_plan.md` — Prompt for TikTok carousel regen. Receives: the carousel spec(s) to replace, reviewer feedback (raw text), the kept specs (for diversity context), and the attribute taxonomy. Must understand carousel-specific fields (`hook_text`, `content_slides`, `image_prompts`, `template_family`) and produce specs in the same JSON schema as the planning prompt. Mirrors the Pinterest pattern (`prompts/shared/regen_plan.md` → `generate_replacement_posts()`).

**New workflow:**
- `.github/workflows/tiktok-regen-plan.yml` — Triggered by `repository_dispatch: tiktok-regen-plan`

**Estimated scope:** ~220 lines new Python, ~30 lines new workflow, ~40 lines new Claude API method, ~60 lines new prompt template

### Phase D: Content Generation as Separate Step
**Goal:** Rendering runs after plan approval (B3=`approved` gates the entire plan — all specs are rendered). Implements per-slide image generation (replacing the current one-shared-background approach).

**New files:**
- `.github/workflows/tiktok-generate-content.yml` — Triggered by `repository_dispatch: tiktok-generate-content`
  - **Must `git pull` first** — plan JSON was committed by the plan-only workflow on a previous runner
  - Loads plan JSON from disk (all specs — B3=`approved` means the entire plan is approved, no per-carousel filtering needed)
  - Runs rendering pipeline (updated `generate_carousels()` with per-slide image support)
  - Uploads ALL slides to GCS (not just first slide)
  - Writes Content Queue with `=IMAGE()` per slide column

**Files to modify:**
- `src/tiktok/generate_weekly_plan.py`
  - Extract "render + upload + publish" into new function `generate_content_from_plan(plan_path)`
  - This function reads the saved plan JSON (all specs — B3=`approved` gates the entire plan), renders (enriching plan with `_rendered`), uploads ALL slides to GCS, publishes to Content Queue, sends Slack notification
  - **Steps 10-14 become dead code** after Phase A+B switches the cron to `--plan-only`. `generate_content_from_plan()` replaces their functionality. The old Steps 10-14 code can be deleted once `generate_content_from_plan()` is validated.
  - **Entry point:** Add `--generate-content` flag to `__main__` argparse. When set, calls `generate_content_from_plan(find_latest_plan(data_dir=TIKTOK_DATA_DIR))` instead of `generate_plan()`. The `tiktok-generate-content.yml` workflow invokes `python -m src.tiktok.generate_weekly_plan --generate-content`.
  - Planning prompt updated: Claude specifies `image_prompts` per slide (which slides need AI images and what prompt to use), not one shared image per carousel

- `src/tiktok/generate_carousels.py`
  - **Major change:** Replace one-shared-background model with per-slide image generation
  - Read `image_prompts` from carousel spec (list of `{slide_index, prompt}`)
  - Generate AI images only for specified slides (typically 1-3 per carousel, not every slide)
  - Each slide gets its own `background_image_path` (or none for text-only slides)
  - Slides without image prompts render as pure text/CSS (no background image)
  - **Refactor:** Extract slide-building logic (lines 115-169: building the `slides` list from a carousel spec + image paths) into a shared function `build_slides_for_render(spec, image_paths)`. This function is called by both `generate_carousels.py` (initial render) and `regen_content.py` (Phase F re-render after image regen). Without this, Phase F would need to duplicate ~55 lines of slide construction logic.
  - Remove reference to `_image_prompt` (singular) — replaced by `image_prompts` (array)

- `src/shared/apis/sheets_api.py`
  - Update `TIKTOK_CQ_HEADERS` constant from 14 columns to 17 columns (new schema A-Q)
  - Update `write_tiktok_content_queue()` with new 17-column schema (D-L = slide previews). The method's internal `slide_urls` handling changes from constructing 1 `=IMAGE()` formula to constructing 9 separate `=IMAGE()` formulas (one per slide column D-L), with blank cells for unused slide positions. This is a significant rewrite of the row-building logic.
  - Update `read_tiktok_approved_carousels()` — Status moves from col M (index 12) to col O (index 14), read range changes from `A:N` to `A:Q`. The old schema had an explicit `slide_count` column; the new schema derives slide count by counting non-empty slide preview columns (D-L) using `valueRenderOption=FORMULA` and checking for cells containing `=IMAGE(`. Note: `FORMATTED_VALUE` cannot be used here because `=IMAGE()` cells have no text representation and return empty strings. **Fallback:** if derived `slide_count` is 0 for an approved carousel, log a warning and fall back to the plan JSON's `image_prompts` length + content slides + 2 (hook + CTA) to compute expected slide count. This prevents silent posting failures when formula parsing is buggy. The returned carousel dict must still include `slide_count` because `promote_and_schedule.py` → `_resolve_slide_urls()` uses it to construct GCS URLs.
  - Update `update_tiktok_content_status()` — Status moves from col M to col O, Notes moves from col N to col Q. Called by `promote_and_schedule.py` and `post_content.py`.
  - Add `read_tiktok_content_regen_requests()` — reads rows with regen_* statuses from col O
  - Add `update_tiktok_content_row()` — updates specific cells for a carousel row
  - Add `TIKTOK_CQ_CELL_REGEN_TRIGGER = "R1"` constant — must be separate from Pinterest's `CQ_CELL_REGEN_TRIGGER = "N1"` to avoid breaking Pinterest
  - Add `reset_tiktok_content_regen_trigger()` — writes `idle` to R1 using the TikTok-specific constant

- `src/tiktok/publish_content_queue.py`
  - Change `slide_urls` parameter type from `dict[str, str]` (one URL per carousel) to `dict[str, list[str]]` (all slide URLs per carousel)
  - In `generate_content_from_plan()`, change the dict construction from `slide_preview_urls[carousel_id] = gcs_urls[0]` to `slide_preview_urls[carousel_id] = gcs_urls` (pass all URLs, not just the first)

**Schema transition note:** `write_tiktok_content_queue()` calls `_validate_headers()` before `_clear_and_write()`. On the first run after the schema change, the old 14-column headers won't match the new 17-column `TIKTOK_CQ_HEADERS`, causing `_validate_headers()` to raise `SheetsAPIError` before `_clear_and_write()` can run. **Fix:** Update `write_tiktok_content_queue()` to skip header validation when performing a full rewrite (i.e., when the method will call `_clear_and_write()` which overwrites headers anyway). Alternatively, pass a `skip_validation=True` flag for the clear-and-write path. After the first successful write, subsequent calls will find matching headers and validate normally. Deploy Apps Script triggers (Phase E) alongside the SheetsAPI changes (Phase D) to ensure no trigger fires the old code path against new headers or vice versa.

- `src/tiktok/generate_weekly_plan.py`
  - Note: prompt update, Step 9 removal, and `image_prompts` validation already done in Phase A
  - No additional prompt or validation changes needed in Phase D

**Estimated scope:** ~120 lines new workflow logic, ~150 lines modified SheetsAPI, ~100 lines modified generate_carousels, ~60 lines modified publish, ~20 lines prompt update

### Phase E: Apps Script + Trigger Wiring
**Goal:** Wire all Sheet interactions to GitHub Actions via repository_dispatch, with concurrency guards to prevent race conditions.

**Files to modify:**
- `src/apps-script/tiktok-trigger.gs` — Full rewrite with 6 trigger types:
  1. Weekly Review B3 = `approved` → `tiktok-generate-content`
  2. Weekly Review B5 = `regen` → `tiktok-regen-plan`
  3. Content Queue all col O reviewed → `tiktok-promote-and-schedule` (**guarded: only dispatches if Weekly Review B3 = `approved`** — prevents scheduling stale renders after a backward phase transition)
  4. Content Queue R1 = `run` → `tiktok-regen-content`
  5. (Future) Weekly Review B4 = `approved` → manual scheduling override
  6. Weekly Review B3 = `pending_review` → write "⚠️ STALE — plan under revision" to Content Queue cell S1 (stale indicator for backward phase transition)

**Concurrency guards in Apps Script:**
- B3 = `approved` is **blocked while B5 = `regen`** (plan regen in flight). The script checks B5 before dispatching content generation; if B5 is not `idle`, it writes a warning to a status cell and does not dispatch. The reviewer must wait for plan regen to complete before approving.
- R1 = `run` is **blocked while any row has `regen_image_*` AND any row has `approved`** that would trigger promote-and-schedule simultaneously. (In practice this is unlikely since the "all reviewed" check requires no pending statuses.)
- Each trigger writes a timestamp to a tracking cell (e.g., B6 for plan triggers, R2 for content triggers) so the reviewer can see when the last dispatch fired.

**Concurrency groups in workflows:**
- All TikTok plan workflows (`tiktok-regen-plan`, `tiktok-generate-content`) share concurrency group `tiktok-plan` with `cancel-in-progress: false` (queue, don't cancel).
- All TikTok content workflows (`tiktok-regen-content`, `tiktok-promote-and-schedule`) share concurrency group `tiktok-content`.
- This prevents two plan regens from racing each other or a regen from racing content generation.

**Convenience functions:**
- `runTikTokPlanRegen()` — Button drawing for plan regen
- `runTikTokContentRegen()` — Button drawing for content regen

**Estimated scope:** ~100 lines (rewrite of existing 72-line file)

### Phase F: Image-Level Regen
**Goal:** Regenerate AI-generated images for specific slides, triggered from Content Queue.

**Design context:** Phase 2 (Content Queue) is visual-only review — all text was approved in Phase 1. The only meaningful regen action in Phase 2 is regenerating AI-generated images for slides that have them.

**Design decisions:**
- **Image regen only, no copy regen in Phase 2.** Text was approved in Phase 1 via the Weekly Review tab. Phase 2 regen targets the visual output: AI-generated background images.
- **Backward phase transition:** If the reviewer realizes the text is wrong after seeing it rendered, they set B3 back to `pending_review` in the Weekly Review tab. This does NOT automatically clear the Content Queue — the stale renders remain. After fixing text in Phase 1 and re-approving (B3=`approved`), `tiktok-generate-content` re-runs, clears the Content Queue via `_clear_and_write()`, and populates it with fresh renders. The concurrency guard (Phase E) blocks the "all reviewed" trigger while B3 ≠ `approved`, preventing scheduling of stale content. **Important: the reviewer must change B3 to `pending_review` BEFORE approving the last Content Queue row** — otherwise trigger #3 fires immediately on the last approval (Apps Script `onEdit` is synchronous). **Stale indicator:** When B3 is changed to `pending_review` while the Content Queue tab has data, the Apps Script writes "⚠️ STALE — plan under revision" to Content Queue cell S1 (outside the data columns A-R, so it doesn't overwrite headers). This is cleared when `tiktok-generate-content` runs `_clear_and_write()`.
- **Full carousel re-render after image regen.** When a slide's AI image is regenerated, the entire carousel is re-rendered via `CarouselAssembler.render_carousel()` (all slides in one Puppeteer batch). Only the changed slides are re-uploaded to GCS. This reuses existing rendering code with zero changes to CarouselAssembler.
- **Plan JSON is the source of truth.** The regen script loads the plan JSON to get the carousel spec and the `image_prompts` array. After generating a new image, it updates the spec's image prompt (for audit trail) and re-saves the plan JSON.
- **`regen_image_N` on a text-only slide is a no-op.** The system checks the carousel spec's `image_prompts` to determine which slides have AI images. If slide N isn't in `image_prompts`, the regen is skipped and a note is written to the Notes column.

**New files:**
- `src/tiktok/regen_content.py` — Content-level regeneration orchestrator
  - **Workflow must `git pull` first** — plan JSON was committed by a previous runner
  - Loads plan JSON from disk via `find_latest_plan(data_dir=TIKTOK_DATA_DIR)` → `data/tiktok/weekly-plan-YYYY-MM-DD.json`. **Must pass TikTok-specific data dir** — the default searches `data/` which contains Pinterest plans.
  - Reads regen requests from Content Queue (rows where status starts with `regen`)
  - Parses regen status to determine targets:
    - `regen_image_0` → regenerate hook slide's AI image
    - `regen_image_2` → regenerate content slide 2's AI image
    - `regen_image_0,regen_image_3` → multiple slide images
    - `regen` → regenerate ALL AI images for the carousel + full re-render
  - For each `regen_image_N`: look up slide N in `image_prompts`, call `ImageGenAPI.generate()` with the existing prompt (or feedback-modified prompt), save new image
  - Re-render the full carousel via existing `CarouselAssembler.render_carousel()`
  - Upload changed slides to GCS (overwrite at same path + cache-bust `?t=TIMESTAMP`)
  - Update Content Queue row with new `=IMAGE()` URLs
  - Update plan JSON on disk (new image paths), commit + push with `[skip ci]`
  - Reset R1 to `idle`
  - Send Slack notification

**No new Claude API methods needed.** Image regen uses `ImageGenAPI.generate()` (already exists). Feedback from the reviewer can modify the image prompt (e.g., "make it brighter" → append to existing prompt).

**New workflow:**
- `.github/workflows/tiktok-regen-content.yml` — Triggered by `repository_dispatch: tiktok-regen-content`
  - `git pull` → run `regen_content.py` → commit + push updated plan JSON

**Estimated scope:** ~180 lines new Python, ~30 lines new workflow

---

## Execution Order

```
Phase A + B (split plan/render + workflow updates)  ← Deploy together (see note below)
  ↓
Phase C (plan regen)                                ← Can test plan review loop
  ↓
Phase D + E (content generation + Apps Script)      ← Deploy together (schema change + triggers)
  ↓
Phase F (image-level regen)                         ← Can test content review loop
```

**Testing groups:**
- After A+B: test the plan review loop (plan-only generation, Sheet write, cron guard)
- After C: test plan regen loop (direct edits, AI regen, feedback parsing)
- After D+E: test content generation + Apps Script triggers (rendering, GCS upload, schema change). **Apps Script and SheetsAPI schema change must deploy atomically** — if the Apps Script reads new column positions before the Python writes them (or vice versa), data will be misaligned.
- After F: test image-level regen loop

**Deployment constraint:** Phase A removes Step 9 (`_image_prompt` generation) and changes the prompt to output `image_prompts`. But `generate_carousels.py` still reads `_image_prompt` until Phase D rewrites it. **The non-`--plan-only` code path is broken between Phase A and Phase D.** This is acceptable because Phase B switches the cron workflow to `--plan-only`, so the full pipeline should never run. Phase B must deploy alongside Phase A to ensure the cron never calls the broken path.

---

## GCS Slide URL Convention

All slides uploaded to GCS follow this path convention:
```
tiktok/{carousel_id}/slide-0.png   ← hook slide
tiktok/{carousel_id}/slide-1.png   ← content slide 1
tiktok/{carousel_id}/slide-2.png   ← content slide 2
...
tiktok/{carousel_id}/slide-N.png   ← CTA slide (last)
```

The Content Queue `=IMAGE()` formulas reference these URLs directly. On regen, the old slide is overwritten at the same path (GCS allows overwrites). A cache-busting `?t=TIMESTAMP` query param is appended to force Sheet refresh.

**GCS folder link** (col M): Links to a Google Cloud Console object listing filtered by prefix `tiktok/{carousel_id}/`, letting the reviewer click through to full-resolution versions. (GCS public URLs don't support directory listings, so a Console link is needed.)

**Note on `=IMAGE()` performance:** 9 formulas per row × 7 carousels = 63 image loads. Google Sheets renders `=IMAGE()` lazily and may be sluggish. Acceptable for a review workflow, but worth noting.

---

## Data Flow Summary

```
Monday 6:30 AM ET (cron)
  ↓
generate_weekly_plan.py --plan-only
  → Claude generates 7 carousel specs
  → Saves plan JSON to data/tiktok/weekly-plan-YYYY-MM-DD.json
  → Writes specs to TikTok Sheet "Weekly Review" tab
  ↓
[Human reviews specs + slide text in Weekly Review]
  → approve / reject / regen (with granular feedback)
  → feedback supports: "regen slide 3", "change hook to ...", free-form
  ↓
If regen: B5 = "regen" → tiktok-regen-plan.yml
  → regen_plan.py parses feedback (direct edit vs. AI regen)
  → Applies direct text edits or calls Claude for regen
  → Re-writes Weekly Review tab
  → Back to human review
  ↓
B3 = "approved" (all specs must be approved before setting B3) → tiktok-generate-content.yml
  → generate_content_from_plan() renders all specs
  → Generates per-slide AI images where specified (1-3 per carousel)
  → Uploads ALL slides to GCS
  → Writes Content Queue with =IMAGE() per slide
  ↓
[Human reviews all rendered slides in Content Queue — visual review only]
  → approve / reject / regen_image_N / regen
  ↓
If regen: R1 = "run" → tiktok-regen-content.yml
  → regen_content.py regenerates targeted AI images
  → Re-renders carousel, re-uploads changed slides to GCS
  → Updates Content Queue row
  → Back to human review
  ↓
All reviewed → tiktok-promote-and-schedule.yml
  → promote_and_schedule.py reads approved carousels
  → Distributes across 7 days × 3 slots
  → Writes carousel-schedule.json
  ↓
3× daily (cron) → tiktok-daily-post.yml
  → post_content.py posts via Publer
```

---

## Comparison with Pinterest Flow

| Aspect | Pinterest | TikTok (new) |
|--------|-----------|-------------|
| Plan review tab | Weekly Review (B3/B5) | Weekly Review (B3/B5) — same pattern |
| Plan regen | `regen_weekly_plan.py` via B5 | `regen_plan.py` via B5 — same pattern |
| Content review tab | Content Queue (col J status) | Content Queue (col O status) |
| Content preview | 1 thumbnail per pin | All slides per carousel (cols D-L) |
| Content regen trigger | N1 = "run" | R1 = "run" — same pattern |
| Phase 1 regen | Plan-level regen (full post) | Granular: `regen slide N`, `change hook to "..."`, full regen |
| Phase 2 regen | `regen_image` / `regen_copy` / `regen` | `regen_image_N` / `regen` (visual only — text approved in Phase 1) |
| Regen feedback | Col L feedback | Col P feedback — same pattern |

The patterns are deliberately parallel so the same mental model applies to both channels.

---

## Resolved Design Decisions

1. **Max slides per carousel:** 9 total (hook + 7 content + CTA). Content Queue has 9 inline preview columns (D-L) so every slide is visible. Carousels with fewer content slides leave extra columns blank.

2. **Per-slide image model (hybrid).** Claude specifies `image_prompts` per slide in the carousel spec — a list of `{slide_index, prompt}` entries indicating which slides need AI-generated background images. Slides without image prompts render as pure text/CSS. This matches the original TikTok research plan and produces more natural-looking carousels than the previous one-shared-background approach. **This replaces the current `generate_carousels.py` model where one image is shared across all slides.**

   **Image rules by template family:**
   - `photo_forward`: Hook slide always gets an image. Claude picks up to 2 additional content slides that benefit from photography. CTA never gets an image. (1-3 images per carousel.)
   - `clean_educational`: No images. Text-dominant design is the point of this family.
   - `dark_bold`: No images. High-contrast typography on dark backgrounds doesn't need photography.
   - `comparison_grid`: No images. Structured data layout with split panels.
   - **Max 3 AI-generated images per carousel** (enforced in `_validate_plan()`). No weekly cap needed (3 × 7 = 21 max).
   - Claude specifies which slides get images via `image_prompts` array. Empty array = fully text-only carousel.

3. **Two-phase regen split.** Phase 1 (Weekly Review) handles all text changes — both direct edits and AI regen, with slide-level granularity via the feedback column. Phase 2 (Content Queue) handles visual changes only — regenerating AI-generated images for specific slides. This clean split means Phase 2 regen never needs a Claude API call (only `ImageGenAPI.generate()`), and Phase 1 regen never needs rendering.

4. **Phase 2 regen uses `regen_image_N` with column-position numbering.** `regen_image_0` = hook (col D), `regen_image_1` through `regen_image_7` = content slides (cols E-K), `regen_image_8` = CTA (col L). This is a fixed layout — the regen script translates column-position N to actual `slide_index` using the carousel's `content_slides` length (e.g., CTA is always column-position 8 but slide_index varies: 4 for a 3-content-slide carousel, 8 for a 7-content-slide carousel). The script checks `image_prompts` to verify the target slide has an AI image. No-op if it doesn't, or if N exceeds the carousel's actual slide count.

5. **Plan JSON persistence across phases:** Commit to repo and push, same as Pinterest. Plan JSON saved to `data/tiktok/weekly-plan-YYYY-MM-DD.json`, committed with `[skip ci]`. Regen updates the same file and pushes. **Every downstream workflow (`tiktok-generate-content`, `tiktok-regen-content`) must `git pull` before reading the plan JSON**, since it was committed by a previous ephemeral runner. This matches the existing `content-log.jsonl` auto-commit pattern. **All TikTok scripts must call `find_latest_plan(data_dir=TIKTOK_DATA_DIR)`** — the function defaults to `data/` which contains Pinterest plans.

6. **One Claude API call per carousel for plan regen (Phase C).** When multiple carousels are flagged for regen, each gets its own Claude call. Simpler code, easier to debug, and if one fails it doesn't affect the others. Typical regen batch is 1-2 carousels.

7. **Cron collision guard.** The Monday cron (`tiktok-weekly-review.yml`) generates a new plan. If last week's review cycle is still in progress, the cron would create a new `weekly-plan-YYYY-MM-DD.json` with a different date, and `find_latest_plan()` would return the new file — causing in-progress regen requests to apply to the wrong plan. Guard: the cron workflow checks B3 in the Weekly Review tab before running. If B3 is not `idle` or `rejected` (i.e., a review is in progress), the cron skips generation and sends a Slack warning: "Skipped plan generation — previous week's review still in progress." **First-run edge case:** If the Weekly Review tab doesn't exist yet (first ever run), `read_tiktok_plan_status()` should return `None`/empty, which is treated as `idle` — allowing the first plan generation to proceed.

8. **Feedback parsing fallback.** If the regen_plan.py feedback parser cannot match a targeted pattern (e.g., typo `regen sldie 3`), it falls through to full carousel Claude regen with the raw feedback as context. The reviewer gets a full regen instead of a targeted one — not silent corruption, but the original targeted intent is lost. A Slack notification includes which carousels got full regen vs. targeted, so the reviewer knows.

9. **Partial image failure handling.** If `ImageGenAPI.generate()` fails for one slide during initial content generation (Phase D) or regen (Phase F), the carousel is still rendered — the failed slide renders as text-only (no background image). The Notes column records which slide's image failed. The carousel is written to the Content Queue as `pending_review` so the reviewer can decide whether to approve the text-only version or regen the image.
