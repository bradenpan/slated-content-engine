# Pinterest Pipeline — Codebase Audit

**Audit started:** 2026-02-25
**Last updated:** 2026-02-27
**Status:** Complete (post-simplification, verified against codebase)

**Simplification summary:** Removed stock photo search (deleted `image_stock.py`), removed AI image validation/ranking/comparison workflows, removed tier-based image routing (all images now AI-generated), added GPT-5 Mini for image prompts and pin copy (Claude Sonnet fallback), added plan-level regen (`regen_weekly_plan.py`), fixed double H1 blog bug, removed Column M from Content Queue, added `image_cleaner.py` for AI detection avoidance.

---

## Table of Contents
- [Phase 1: File-by-File Discovery](#phase-1-discovery)
- [Phase 2: Data Inventory](#phase-2-data-inventory)
- [Phase 3: Issue Identification](#phase-3-issues)
- [Phase 4: Dependency Map](#phase-4-dependency-map)
- [Phase 5: Refactoring Plan](#phase-5-refactoring-plan)

---

## Phase 1: Discovery

### API Layer (`src/apis/`)

#### `src/apis/__init__.py`
- **Purpose:** Empty package init (just a comment).
- **Issues:** None.

#### `src/apis/claude_api.py` (~954 lines, was ~540)
- **Purpose:** Wraps Anthropic Claude API for all LLM tasks. Now also handles GPT-5 Mini calls for image prompts and pin copy, with Claude Sonnet fallback.
- **Dependencies:** `anthropic`, `requests` (NEW: for GPT-5 Mini HTTP calls), `pathlib`, `json`, `base64`, `logging`. Reads from `prompts/` and `strategy/`.
- **Changes:** +414 lines. Added `generate_image_prompt()` dual-model support, `generate_pin_copy_batch()` dual-model support, GPT-5 Mini cost tracking. AI image validation/ranking methods removed.
- **Issues:**
  - God file **worsened** -- now handles Claude + GPT-5 Mini orchestration, planning, pin copy, blog posts, image prompts, weekly/monthly analysis.
  - Hardcoded model IDs (lines 40-42): Claude models. Should be config/env vars.
  - Hardcoded cost estimates (lines 45-49): Will go stale.
  - Relative path resolution for `PROMPTS_DIR`/`STRATEGY_DIR` is fragile.
  - NEW: GPT-5 model name has env var override (`OPENAI_CHAT_MODEL`, line 682) but default `"gpt-5-mini"` is hardcoded. Partially configurable.
  - NEW: Manual HTTP requests to OpenAI instead of using the `openai` Python SDK (already in requirements.txt).
  - NEW: Fragile GPT-5 Mini fallback logic -- manual try/except with silent fallback to Claude Sonnet.
  - NEW: Dual-model branching in `generate_image_prompt()` and `generate_pin_copy_batch()` adds complexity.
  - NEW: Hardcoded GPT-5 Mini cost rates.

#### `src/apis/pinterest_api.py` (~568 lines, unchanged)
- **Purpose:** Thin wrapper around Pinterest v5 REST API.
- **Issues:** Hardcoded API URLs, retry constants, metric types. `get_boards()` trivial alias. MIME detection duplicated across 3 files. No changes from simplification.

#### `src/apis/gcs_api.py` (~353 lines, was ~427)
- **Purpose:** Uploads pin/blog hero images to GCS for Sheets `=IMAGE()` previews.
- **Changes:** -74 lines. Cleanup from simplification.
- **Issues:** Hardcoded bucket name, duplicated MIME detection, silent `None` returns on error. ~~hardcoded prefix "W" in `delete_old_images()`~~ (fixed: replaced with week-scoped `delete_old_week_images()`).

#### `src/apis/github_api.py` (~543 lines, unchanged)
- **Purpose:** Commits blog posts to goslated.com repo, triggering Vercel deploy.
- **Issues:** Hardcoded base URL, three overlapping commit methods, dead `_create_or_update_file()`, mixed default branches. No changes from simplification.

#### `src/apis/sheets_api.py` (~1,017 lines, was ~944)
- **Purpose:** Manages Google Sheets (Weekly Review, Content Queue, Post Log, Dashboard tabs).
- **Changes:** +73 lines. Column M removed from Content Queue, regen trigger columns shifted.
- **Issues:** God file (now largest API file at 1,017 lines). Hardcoded column indices, tab names, cell references. Trivial alias methods. Fragile `_clear_and_write()`. No structural improvement.

#### `src/apis/drive_api.py` (~339 lines, unchanged)
- **Purpose:** Uploads pin images to Google Drive for Sheets `=IMAGE()` preview.
- **Issues:** Redundant with GCS, hardcoded folder name, duplicated MIME detection, `_clear_folder()` pagination limit. No changes from simplification.

#### `src/apis/image_gen.py` (~537 lines, unchanged)
- **Purpose:** AI image generation via OpenAI gpt-image-1.5 and Replicate Flux Pro.
- **Issues:** Hardcoded API endpoints, model name, cost estimates, output directory mismatch (`data/generated_pins` vs `data/generated/pins`), magic number threshold. No changes from simplification.

#### `src/apis/image_stock.py` -- DELETED
- **Previous:** ~453 lines. Stock photo search/download from Unsplash and Pexels.
- **Resolved:** Removed in pipeline simplification. All images now AI-generated.

#### `src/apis/slack_notify.py` (~537 lines)
- **Purpose:** Slack webhook notifications for pipeline events.
- **Changes:** +56 lines. Added `notify_plan_regen_complete()` and `notify_regen_complete()` for regen notifications.
- **Issues:** Hardcoded color constants. `"success"` level not in `color_map` (used by `blog_deployer.py` line 306). Otherwise well-structured.

### Pipeline Scripts (`src/`)

#### `src/token_manager.py` (~422 lines, unchanged)
- **Purpose:** Pinterest OAuth 2.0 token lifecycle.
- **Issues:** Hardcoded token store path, redirect URI, OAuth URL, refresh threshold. Lazy Slack loading pattern. No changes from simplification.

#### `src/generate_weekly_plan.py` (~1,405 lines, unchanged)
- **Purpose:** Generates weekly content plan (8-10 blog posts + 28 pins) using Claude Sonnet.
- **Issues:** God file. Loads context from 8+ strategy files. Tightly coupled to strategy JSON structure. Now has new consumer: `regen_weekly_plan.py` calls `splice_replacements()`.

#### `src/generate_blog_posts.py` (~375 lines, unchanged)
- **Purpose:** Orchestrates blog post generation from approved weekly plan.
- **Issues:** Two near-duplicate entry points (60% shared logic). Duplicated save logic. Fallback to local file when Sheets says not approved.

#### `src/blog_generator.py` (~790 lines)
- **Purpose:** Generates MDX blog posts with frontmatter from content plan specs.
- **Changes:** Added H1 stripping safety net (lines 137-164) to fix double H1 blog bug.
- **Issues:**
  - Custom YAML parser (lines 566-628) instead of PyYAML.
  - Four near-identical `generate_*_post()` methods (lines 250-377).
  - `_validate_generated_post()` warnings effectively invisible.
  - NEW: H1 stripping early break only checks first non-empty line -- blank lines before H1 not detected.

#### `src/generate_pin_content.py` (~816 lines, was ~1,127, -311 lines)
- **Purpose:** Generates pin assets (copy + images) for all pins in the approved plan.
- **Dependencies:** `ClaudeAPI`, `ImageGenAPI`, `PinAssembler`, `json`, `pathlib` (removed: `ImageStockAPI`).
- **Changes:** Removed `source_image()`, `_source_stock_image()`, `ImageStockAPI` import, quality gate metadata, AI comparison logic. Added simplified `_source_ai_image()` with JSON code-fence stripping, GPT-5 Mini image prompts, regen feedback loop.
- **Issues:**
  - Hardcoded `BLOG_BASE_URL` (duplicated).
  - Hardcoded `COPY_BATCH_SIZE = 6`.
  - O(n) image ID scan.
  - Fragile blog slug resolution.
  - NEW: JSON code-fence stripping (lines 710-725) can fail silently if GPT-5 Mini returns bad format.
  - NEW: Image retry count always 0 -- quality notes show "AI generated" not "retry N".
  - NEW: Assumes `image_gen_api.generate()` returns Path object.
  - Uses `image_cleaner.clean_image` (line 748) for AI detection avoidance.

#### `src/regen_content.py` (~821 lines)
- **Purpose:** Handles content regeneration triggered from Content Queue.
- **Changes:** Removed tier routing, stock API calls, AI comparison regen. Added blog image regen, plan-level feedback.
- **Issues:**
  - `_regen_item` is 228 lines (god method).
  - `_extract_drive_file_id()` duplicated (also in `publish_content_queue.py`).
  - Fragile GCS URL parsing.
  - NEW: Non-atomic pin-schedule.json update (load-modify-write with no recovery).
  - NEW: Hero image download assumes `_drive_image_url` field exists.

#### `src/publish_content_queue.py` (~443 lines)
- **Purpose:** Publishes approved content to Content Queue sheet with image previews.
- **Changes:** Removed AI comparison upload, tier-based decisions.
- **Issues:**
  - Frontmatter parsing duplication.
  - Hardcoded Drive/GCS names.
  - Drive file ID extraction logic duplicated (inline at line 118, same logic as `regen_content._extract_drive_file_id()`).
  - Uses PyYAML (`yaml.safe_load`, line 22) for frontmatter parsing -- contrast with `blog_generator.py`'s custom parser.
  - NEW: Malformed pins silently skip URL backup.

#### `src/blog_deployer.py` (~920 lines)
- **Purpose:** Commits approved blogs to goslated.com repo, verifies deployment, creates pin schedule, logs to content-log.jsonl.
- **Changes:** Removed `_process_ai_image_swaps()` function. Otherwise unchanged.
- **Issues:**
  - God file (920 lines). Four deployment methods (`deploy_approved_content`, `deploy_to_preview`, `promote_to_production`, `deploy_approved_posts`) with 60%+ duplication.
  - `BLOG_BASE_URL` duplicated.
  - Hardcoded deploy verify timeout/delay.
  - `pin-generation-results.json` loaded multiple times (was 3x, now 2x with swap removal).
  - `update_pin_status()` semantic mismatch (used for blogs).

#### `src/regen_weekly_plan.py` (~320 lines -- NEW FILE)
- **Purpose:** Plan-level regeneration. Replaces underperforming posts in the weekly plan by calling `generate_weekly_plan.splice_replacements()`.
- **Dependencies:** `SheetsAPI`, `generate_weekly_plan`, `SlackNotify`, `json`, `pathlib`.
- **Issues:**
  - NEW: Tight coupling to `generate_weekly_plan.splice_replacements()` -- breakage if that method signature changes.
  - NEW: Silent exception defaults when reading Sheet status.
  - NEW: No validation that Sheet cells B3/B4 were restored after plan splice.
  - NEW: Post identification failures silently skipped.

#### `src/pin_assembler.py` (~1,039 lines)
- **Purpose:** Assembles pin images from HTML/CSS templates using Puppeteer.
- **Changes:** Added `image_cleaner.clean_image` calls in `render_pin()` (line 508) and `render_batch()` (line 717) for AI detection avoidance.
- **Issues:** Hardcoded dimensions, max file size. JPEG-as-PNG naming. Fragile HTML variant parsing. ~200 lines of test data in module. `random.choice` variant selection.

#### `src/post_pins.py` (~731 lines, unchanged)
- **Purpose:** Posts approved pins to Pinterest via API.
- **Issues:** Hardcoded jitter, slot counts, timezone. O(n) `is_already_posted()`. Duplicate `append_to_content_log()`. Stale jitter comment.

#### `src/pull_analytics.py` (~559 lines, unchanged)
- **Purpose:** Pulls Pinterest analytics and updates content log.
- **Issues:** No significant changes or new issues.

#### `src/weekly_analysis.py` (~763 lines, unchanged)
- **Purpose:** Analyzes past week's Pinterest performance.
- **Issues:** Hardcoded paths, 220-line `generate_content_memory_summary()`, hardcoded date math, duplicated aggregation logic.

#### `src/monthly_review.py` (~864 lines, unchanged)
- **Purpose:** Monthly performance review using Claude Opus.
- **Issues:** No significant changes or new issues.

#### `src/image_cleaner.py` (~101 lines -- NEW FILE)
- **Purpose:** Strips all metadata (EXIF, IPTC, XMP, PNG text chunks) from images and applies subtle Gaussian noise to defeat AI-content fingerprinting.
- **Dependencies:** `numpy`, `PIL` (Pillow), `pathlib`, `logging`.
- **Called by:** `pin_assembler.py` (lines 508, 717), `generate_pin_content.py` (line 748).
- **Issues:**
  - Converts all images to JPEG (loses PNG transparency).
  - Silent failure: catches all exceptions, returns `input_path` unchanged on error (line 99-101).
  - Random JPEG quality (89-94) may cause inconsistent file sizes.

#### `src/setup_boards.py` (~105 lines -- utility)
- **Purpose:** One-time Pinterest board and section setup utility.
- **Dependencies:** `pinterest_api`, `token_manager`, `json`, `pathlib`.
- **Issues:** No significant issues. Utility script, not part of automated pipeline.

#### `src/backfill_hero_images.py` (~200 lines -- largely obsolete)
- **Purpose:** Backfill hero images from Google Drive to GCS for existing blog posts.
- **Dependencies:** `gcs_api`, `sheets_api`, `drive_api`, `pathlib`.
- **Issues:**
  - Largely obsolete per its own docstring (line 7-9).
  - References Column M which no longer exists in the simplified pipeline.
  - Should be considered for removal.

#### `src/__init__.py` (~1 line)
- **Purpose:** Empty package init.
- **Issues:** None.

### Non-Python Files

#### `.github/workflows/` (10 workflow files)
- All 10 workflows verified -- no broken references to removed features (stock, tier, image_rank).
- MINOR: `promote-and-schedule.yml` has inline pin schedule redating logic.
- MINOR: `monthly-review.yml` 30-min timeout may be tight for Opus.

#### `requirements.txt`, `package.json`
- Clean. All deps still used. No stale stock photo libraries. `openai` SDK present and used by `image_gen.py`, but `claude_api.py` uses raw HTTP `requests` for GPT-5 Mini instead of the SDK.
- `numpy` dependency added for `image_cleaner.py`.
- `package.json` only contains puppeteer.

#### `.gitignore`
- MEDIUM: Stale directory references (`data/generated_posts/`, `data/generated_pins/`) don't match actual dirs (`data/generated/pins/`, `data/generated/blog/`).
- Negation rules for hero images may contradict `*.png` ignore.

#### Strategy files (`strategy/`)
- All clean. No stale references to tiers/stock/ranking.
- `current-strategy.md` properly updated for simplification.

#### Prompt templates (`prompts/`)
- Deleted prompts confirmed gone: `image_rank.md`, `image_search.md`, `image_validate.md`.
- No stale references in remaining prompts.
- MINOR: `image_prompt.md` line 28 mentions dead code (htmlcsstoimage alternative).

#### Pin templates (`templates/pins/`)
- All 5 template types verified and clean.
- MINOR: SVG logos repeated across variants (could DRY up).

---

## Phase 2: Data Inventory

### External Data Stores

| Store | Type | Location | Readers | Writers | Canonical? |
|-------|------|----------|---------|---------|------------|
| **content-log.jsonl** | File (JSONL) | `data/content-log.jsonl` | `weekly_analysis.py`, `pull_analytics.py`, `post_pins.py` (idempotency check) | `blog_deployer.py` (initial entries), `post_pins.py` (posted entries), `pull_analytics.py` (analytics updates) | YES -- primary record of all content |
| **pin-schedule.json** | File (JSON) | `data/pin-schedule.json` | `post_pins.py`, `weekly_analysis.py` | `blog_deployer.py`, `regen_content.py` (NEW: modifies during regen) | YES -- posting queue |
| **pin-generation-results.json** | File (JSON) | `data/pin-generation-results.json` | `blog_deployer.py` (2x: deploy, schedule), `regen_content.py` | `generate_pin_content.py` | YES -- generated pin metadata |
| **blog-generation-results.json** | File (JSON) | `data/blog-generation-results.json` | `generate_pin_content.py` | `generate_blog_posts.py` | YES -- generated blog metadata |
| **weekly-plan-*.json** | File (JSON) | `data/weekly-plan-*.json` | `generate_blog_posts.py`, `generate_pin_content.py`, `regen_weekly_plan.py` (NEW) | `generate_weekly_plan.py`, `regen_weekly_plan.py` (NEW: splice) | YES -- weekly plan |
| **token-store.json** | File (JSON) | `data/token-store.json` | `token_manager.py` | `token_manager.py` | YES -- OAuth tokens |
| **content-memory-summary.md** | File (MD) | `data/content-memory-summary.md` | `generate_weekly_plan.py` | `weekly_analysis.py` | Derived from content-log.jsonl |
| **posting-failures.json** | File (JSON) | `data/posting-failures.json` | `post_pins.py` | `post_pins.py` | YES -- failure tracking |
| **Google Sheet: Weekly Review** | Cloud | Google Sheets tab | `sheets_api.py`, `regen_weekly_plan.py` (NEW: reads B3/B4) | `generate_weekly_plan.py`, `blog_deployer.py`, `regen_weekly_plan.py` (NEW: restores B3/B4) | Shared source of truth |
| **Google Sheet: Content Queue** | Cloud | Google Sheets tab | `blog_deployer.py`, `post_pins.py`, `regen_content.py` | `publish_content_queue.py`, `regen_content.py` | Shared source of truth (Column M removed) |
| **Google Sheet: Post Log** | Cloud | Google Sheets tab | -- | `sheets_api.py` | Derived |
| **Google Sheet: Dashboard** | Cloud | Google Sheets tab | -- | `sheets_api.py` | Derived |
| **GCS Bucket** | Cloud | `slated-pipeline-pins` | Google Sheets (=IMAGE()), `regen_content.py` | `gcs_api.py`, `publish_content_queue.py` | Image hosting |
| **Google Drive Folder** | Cloud | `pinterest-pipeline-pins` | Google Sheets (=IMAGE()) | `drive_api.py` | **REDUNDANT** -- same purpose as GCS |
| **goslated.com GitHub Repo** | Cloud | `content/blog/`, `public/assets/blog/` | Vercel (auto-deploy) | `github_api.py` | Blog deployment |
| **Pinterest API** | Cloud | Pinterest v5 API | `pull_analytics.py` | `post_pins.py` | External -- pin hosting |
| **Slack Webhook** | Cloud | Webhook URL | -- | `slack_notify.py` | Notification sink |
| **Anthropic Claude API** | Cloud | API | -- | `claude_api.py` | LLM provider |
| **OpenAI API** | Cloud | API | -- | `image_gen.py`, `claude_api.py` (NEW: GPT-5 Mini) | AI image gen + NEW: image prompts, pin copy |
| **Replicate API** | Cloud | API | -- | `image_gen.py` | AI image generation (Flux Pro) |

**Removed stores:**
- ~~Unsplash API~~ -- removed with `image_stock.py` deletion
- ~~Pexels API~~ -- removed with `image_stock.py` deletion

### Data Flow Anomalies

1. **D1: content-log.jsonl has THREE writers with DIFFERENT schemas** -- `blog_deployer.py` writes entries without analytics fields; `post_pins.py` writes entries with `pin_clicks`, `save_rate`, etc.; `pull_analytics.py` updates existing entries. Schema inconsistency persists. STILL PRESENT.

2. **D2: pin-generation-results.json loaded multiple times in blog_deployer.py** -- Was 3x (deploy, schedule, swap). Now 2x after `_process_ai_image_swaps()` removal. PARTIALLY RESOLVED.

3. **D3: Google Drive and GCS serve the same purpose** -- Both maintained for Sheets =IMAGE(). STILL PRESENT.

4. **D4: BLOG_BASE_URL defined in 3 places** -- `github_api.py`, `generate_pin_content.py`, `blog_deployer.py`. STILL PRESENT.

5. **D5 (NEW): pin-schedule.json now has a second writer** -- `regen_content.py` modifies pin-schedule.json with non-atomic load-modify-write. If interrupted, data loss.

---

## Phase 3: Issues

### 3.1 Data Flow & Source of Truth

| # | Severity | File(s) | Issue | Status |
|---|----------|---------|-------|--------|
| D1 | HIGH | `blog_deployer.py`, `post_pins.py` | content-log.jsonl has two append functions with different schemas. | OPEN |
| D2 | HIGH | `blog_deployer.py` | pin-generation-results.json loaded multiple times in single flow. | PARTIALLY RESOLVED (was 3x, now 2x after `_process_ai_image_swaps()` removal) |
| D3 | MEDIUM | `drive_api.py`, `gcs_api.py` | Two image hosting services for same purpose. Migration to GCS incomplete. | OPEN |
| D4 | MEDIUM | `github_api.py`, `generate_pin_content.py`, `blog_deployer.py` | BLOG_BASE_URL defined in 3 places. | OPEN |
| D5 | LOW | `post_pins.py` | Posting failures tracked in separate file, not connected to content log. | OPEN |

### 3.2 Hardcoded Values (27+ instances)

| # | File | Value | Should Be | Status |
|---|------|-------|-----------|--------|
| H1 | `claude_api.py` | Claude model IDs | Config/env var | OPEN |
| H2 | `claude_api.py` | Cost per million tokens | Config or dynamic lookup | OPEN |
| H3 | `pinterest_api.py` | Pinterest API base URLs | Config constant | OPEN |
| H4 | `gcs_api.py` | `DEFAULT_BUCKET_NAME` | Env var only | OPEN |
| H5 | `github_api.py` | `GOSLATED_BASE_URL` | Env var or shared config | OPEN |
| H6 | `drive_api.py` | `DRIVE_FOLDER_NAME` | Config constant | OPEN |
| H7 | `image_gen.py` | Cost per image dict | Config | OPEN |
| H8 | `image_gen.py` | `MIN_IMAGE_SIZE = 10_000` | Config constant | OPEN |
| H9 | `image_gen.py` | Output dir `data/generated_pins` | Shared path constant (mismatches `data/generated/pins`) | OPEN |
| H10 | `image_gen.py` | `"gpt-image-1.5"` model name | Config/env var | OPEN |
| H11 | `sheets_api.py` | Tab names | Config file | OPEN |
| H12 | `sheets_api.py` | Column indices | Config or schema definition | OPEN |
| H13 | `sheets_api.py` | Cell reference `B3` | Named range or config | OPEN |
| H14 | `sheets_api.py` | Cell range `A4:C4` | Named range or config | OPEN |
| H15 | `sheets_api.py` | Cell reference for regen trigger now at `N1` (line 569), plan regen at `B5` (line 653) | Named range or config | OPEN |
| H16 | `token_manager.py` | `REDIRECT_URI` | Env var | OPEN |
| H17 | `token_manager.py` | `REFRESH_THRESHOLD_DAYS = 5` | Config | OPEN |
| H18 | `pin_assembler.py` | Pin dimensions | Config constants | OPEN |
| H19 | `pin_assembler.py` | `MAX_PNG_SIZE` | Config constant | OPEN |
| H20 | `blog_deployer.py` | `BLOG_BASE_URL` (dup of H5) | Shared config | OPEN |
| H21 | `blog_deployer.py` | Deploy verify timeout/delay | Config | OPEN |
| H22 | `post_pins.py` | Timezone `America/New_York` | Config | OPEN |
| H23 | `post_pins.py` | Slot pin counts | Config or strategy file | OPEN |
| H24 | `post_pins.py` | Jitter constants | Config | OPEN |
| H25 | `generate_pin_content.py` | `BLOG_BASE_URL` (dup of H5, H20) | Shared config | OPEN |
| H26 | `generate_pin_content.py` | `COPY_BATCH_SIZE = 6` | Config | OPEN |
| H27 | `blog_generator.py` | `WORD_COUNT_TARGETS` | Config or strategy file | OPEN |
| H28 | `claude_api.py` | NEW: GPT-5 model name default `"gpt-5-mini"` (has env var `OPENAI_CHAT_MODEL` override) | Already partially configurable | PARTIALLY RESOLVED |
| H29 | `claude_api.py` | NEW: GPT-5 Mini cost rates | Config | NEW |

### 3.3 Fragile Coupling

| # | File(s) | Issue | Status |
|---|---------|-------|--------|
| F1 | `sheets_api.py` | Column indices create fragile coupling to Sheet layout. | OPEN |
| F2 | `sheets_api.py` | Cell references hardcoded to specific cells. | OPEN |
| F3 | `blog_deployer.py`, `generate_pin_content.py` | Pin generation results JSON schema assumed, never validated. | OPEN |
| F4 | `pin_assembler.py` | `_activate_variant()` parses HTML line-by-line -- fragile. | OPEN |
| F5 | `blog_generator.py` | Custom YAML parser will break on edge cases. | OPEN |
| F6 | `post_pins.py` | Board name mapping fails if Pinterest board names change. | OPEN |
| F7 | All pipeline scripts | All resolve paths via `Path(__file__).parent.parent`. | OPEN |
| F8 | `regen_weekly_plan.py` | NEW: Tight coupling to `generate_weekly_plan.splice_replacements()`. | NEW |
| F9 | `regen_content.py` | NEW: Fragile GCS URL parsing. | OPEN (existed before, still present) |
| F10 | `generate_pin_content.py` | NEW: Fragile blog slug resolution. | OPEN (existed before, still present) |

### 3.4 Duplication

| # | Files | Issue | Status |
|---|-------|-------|--------|
| DU1 | `pinterest_api.py`, `gcs_api.py`, `drive_api.py` | Magic-byte MIME detection duplicated in 3 files. | OPEN |
| DU2 | `blog_deployer.py`, `post_pins.py` | Two `append_to_content_log()` functions with different schemas. | OPEN |
| DU3 | `generate_blog_posts.py` | `generate_blog_posts()` and `generate_all_blog_posts()` ~60% identical. | OPEN |
| DU4 | `blog_generator.py` | Four `generate_*_post()` methods structurally identical. | OPEN |
| DU5 | `github_api.py` | Three commit methods with overlapping functionality. | OPEN |
| DU6 | `sheets_api.py` | Three trivial alias methods. | OPEN |
| DU7 | -- | ~~`upload_single_image()` trivial wrapper in `gcs_api.py`.~~ | RESOLVED (method does not exist -- audit error) |
| DU8 | `pinterest_api.py` | `get_boards()` trivial alias for `list_boards()`. | OPEN |
| DU9 | `blog_deployer.py` | Four deployment methods with 60%+ shared logic (`deploy_approved_content`, `deploy_to_preview`, `promote_to_production`, `deploy_approved_posts`). | OPEN |
| DU10 | `github_api.py`, `generate_pin_content.py`, `blog_deployer.py` | BLOG_BASE_URL defined 3 times. | OPEN |
| DU11 | `regen_content.py`, `publish_content_queue.py` | NEW: Drive file ID extraction logic duplicated. Named function in `regen_content.py` (lines 667-676), inline `url.split("id=")` in `publish_content_queue.py` (line 118). | NEW |
| DU12 | `claude_api.py` | NEW: Alias methods `generate_weekly_analysis()` (line 584) and `generate_monthly_review()` (line 664) are trivial wrappers. | NEW |

### 3.5 Missing Error Handling

| # | Severity | File | Issue | Status |
|---|----------|------|-------|--------|
| E1 | MEDIUM | `gcs_api.py` | Returns `None` on failure instead of raising. Callers don't check. | OPEN |
| E2 | LOW | `blog_generator.py` | `_validate_generated_post()` logs warnings but never raises. Results invisible. | OPEN |
| E3 | HIGH | `sheets_api.py` | `_clear_and_write()` clears tab then writes. Write failure = data loss. | OPEN |
| E4 | MEDIUM | `post_pins.py` | `is_already_posted()` scans entire JSONL file -- O(n) per pin. | OPEN |
| E5 | MEDIUM | `blog_deployer.py` | Uses `update_pin_status()` for blog posts -- semantic mismatch. | OPEN |

### 3.6 Structural Issues

| # | File | Issue | Status |
|---|------|-------|--------|
| S1 | `sheets_api.py` (1,017 lines) | God file managing 4 Sheet tabs. | OPEN (worsened: +73 lines) |
| S2 | `blog_deployer.py` (920 lines) | God file. Four deployment methods, logging, scheduling. | OPEN (reduced from ~1,018: `_process_ai_image_swaps()` removed) |
| S3 | `claude_api.py` (~954 lines) | God file. Now handles Claude + GPT-5 Mini orchestration. | OPEN (worsened: +414 lines, dual-model logic) |
| S4 | `pin_assembler.py` (~1,039 lines) | ~200 lines of test render data in module. | OPEN |
| S5 | No `config.py` or central configuration | 27+ hardcoded values across 15+ files. | OPEN |
| S6 | No shared utility module | Duplicated MIME detection, path resolution, content log ops. | OPEN |
| S7 | `regen_content.py` | `_regen_item` is 228 lines -- god method. | OPEN (existed before, still present) |

### 3.7 Configuration & Environment

| # | Issue | Status |
|---|-------|--------|
| C1 | No central configuration module. Each file defines own constants. | OPEN |
| C2 | `image_gen.py` uses `data/generated_pins` but elsewhere uses `data/generated/pins`. Path mismatch. | OPEN |
| C3 | Env var names documented per-file, not centrally. `.env.example` may be incomplete. | OPEN |
| C4 | Google credentials named `GOOGLE_SHEETS_CREDENTIALS_JSON` but used for Drive/GCS too. | OPEN |

### 3.8 New Issues from Simplification

| # | Severity | File | Issue |
|---|----------|------|-------|
| NEW-1 | MEDIUM | `generate_pin_content.py` | JSON code-fence stripping (lines 709-716) can fail silently if GPT-5 Mini returns bad format. |
| NEW-2 | LOW | `generate_pin_content.py` | Image retry count always 0 -- quality notes show "AI generated" not "retry N". |
| NEW-3 | LOW | `generate_pin_content.py` | Assumes `image_gen_api.generate()` returns Path object (no type check). |
| NEW-4 | MEDIUM | `regen_content.py` | Non-atomic pin-schedule.json update (load-modify-write with no recovery). |
| NEW-5 | LOW | `regen_content.py` | Hero image download assumes `_drive_image_url` field exists. |
| NEW-6 | MEDIUM | `publish_content_queue.py` | Malformed pins silently skip URL backup. |
| NEW-7 | LOW | `blog_generator.py` | H1 stripping early break only checks first non-empty line -- blank lines before H1 not detected. |
| NEW-8 | HIGH | `regen_weekly_plan.py` | Tight coupling to `generate_weekly_plan.splice_replacements()` -- breakage if method signature changes. |
| NEW-9 | MEDIUM | `regen_weekly_plan.py` | Silent exception defaults when reading Sheet status. |
| NEW-10 | MEDIUM | `regen_weekly_plan.py` | No validation that Sheet cells B3/B4 were restored after plan splice. |
| NEW-11 | LOW | `regen_weekly_plan.py` | Post identification failures silently skipped. |
| NEW-12 | LOW | `claude_api.py` | GPT-5 model name has env var override (`OPENAI_CHAT_MODEL`) but hardcoded default `"gpt-5-mini"` (line 682). Partially configurable -- severity reduced from HIGH. |
| NEW-13 | HIGH | `claude_api.py` | Manual HTTP requests to OpenAI instead of using the `openai` Python SDK (already in requirements.txt). |
| NEW-14 | HIGH | `claude_api.py` | Fragile GPT-5 Mini fallback -- manual try/except, silent fallback to Claude Sonnet on OpenAI failure. |
| NEW-15 | MEDIUM | `claude_api.py` | Dual-model branching complexity in `generate_image_prompt()` and `generate_pin_copy_batch()`. |
| NEW-16 | LOW | `claude_api.py` | Hardcoded GPT-5 Mini cost rates. |
| NEW-17 | MEDIUM | `.gitignore` | Stale directory refs (`data/generated_posts/`, `data/generated_pins/`) don't match actual dirs. |

### 3.9 Resolved Issues

| # | Was | Resolution |
|---|-----|------------|
| RESOLVED-1 | `image_stock.py` god file (453 lines), Unsplash/Pexels dependency | Deleted in pipeline simplification. |
| RESOLVED-2 | AI image validation/ranking methods in `claude_api.py` | Removed in pipeline simplification. |
| RESOLVED-3 | `source_image()` tier routing in `generate_pin_content.py` | Removed -- all images now AI-generated. |
| RESOLVED-4 | `_source_stock_image()` in `generate_pin_content.py` | Removed with stock image path. |
| RESOLVED-5 | AI comparison regen in `regen_content.py` | Removed in pipeline simplification. |
| RESOLVED-6 | AI comparison upload in `publish_content_queue.py` | Removed in pipeline simplification. |
| RESOLVED-7 | `_process_ai_image_swaps()` in `blog_deployer.py` | Removed in pipeline simplification. |
| RESOLVED-8 | Double H1 bug in blog output | Fixed with H1 stripping safety net in `blog_generator.py`. |
| RESOLVED-9 | Column M in Content Queue (tier indicator) | Removed; regen trigger columns shifted. |
| RESOLVED-10 | Stale prompt templates (`image_rank.md`, `image_search.md`, `image_validate.md`) | Deleted. |

---

## Phase 4: Dependency Map

### Module Dependency Graph

```
                    +-----------------------------+
                    |   GitHub Actions Workflows   |
                    |  (10 .yml files -- triggers) |
                    +--------------+--------------+
                                   |
          +------------------------+------------------------+
          |                        |                        |
          v                        v                        v
   weekly-review.yml        generate-content.yml     daily-post-*.yml
          |                        |                        |
          v                        v                        v
  +---------------+     +------------------+     +--------------+
  | pull_analytics |     |generate_weekly_  |     |  post_pins   |
  |               |     |     plan         |     |              |
  +-------+-------+     +--------+---------+     +------+-------+
          |                      |                       |
          v                      v                       |
  +---------------+     +------------------+             |
  |weekly_analysis|     |generate_blog_    |             |
  |               |     |    posts         |             |
  +-------+-------+     +--------+---------+             |
          |                      |                       |
          |                      v                       |
          |             +------------------+             |
          |             | blog_generator   |             |
          |             +--------+---------+             |
          |                      |                       |
          |                      v                       |
          |             +------------------+             |
          |             |generate_pin_     |             |
          |             |   content        |             |
          |             +--------+---------+             |
          |                      |                       |
          |              +-------+-------+               |
          |              v               v               |
          |        +---------+     +----------+          |
          |        |pin_asm  |     |image_gen |          |
          |        +---------+     +----------+          |
          |                      |                       |
          |                      v                       |
          |             +------------------+             |
          |             |publish_content_  |             |
          |             |    queue         |             |
          |             +--------+---------+             |
          |              +-------+-------+               |
          |              v       v       v               |
          |        +---------+ +----+ +------+           |
          |        |gcs_api  | |drv | |sheets|           |
          |        +---------+ +----+ +------+           |
          |                      |                       |
          |                      v                       |
          |             +------------------+             |
          |             |  blog_deployer   |<------------+
          |             +--------+---------+     (uses board map)
          |              +-------+-------+
          |              v       v       v
          |        +---------+ +----+ +------+
          |        |github_  | |shts| |slack |
          |        |api      | |api | |notfy |
          |        +---------+ +----+ +------+
          |
          |         +------------------+
          +-------->|  content-log.    |
                    |    jsonl         |
                    +------------------+

  NEW: Regen paths (triggered from Content Queue / manual):

  +--------------------+        +-------------------+
  | regen_weekly_plan  |------->| generate_weekly_  |
  | (NEW, 320 lines)   |       |   plan            |
  +--------------------+        | .splice_replace() |
          |                     +-------------------+
          v
  +--------------------+
  |   sheets_api       |  (reads/restores B3/B4)
  +--------------------+

  +--------------------+
  |   regen_content    |------->  claude_api, image_gen,
  |   (821 lines)      |         gcs_api, sheets_api,
  +--------------------+         slack_notify
```

**Removed node:** ~~`image_stock.py`~~ -- no longer consumed by `generate_pin_content.py`, `regen_content.py`, or `backfill_hero_images.py`.

**New node:** `image_cleaner.py` (101 lines) -- consumed by `pin_assembler.py` and `generate_pin_content.py`. AI detection avoidance (metadata stripping + Gaussian noise).

**Candidate for removal:** `backfill_hero_images.py` (200 lines) -- largely obsolete, references removed Column M.

### Shared API Dependencies

| API Module | Used By |
|------------|---------|
| `claude_api.py` | `generate_weekly_plan`, `blog_generator`, `generate_pin_content`, `weekly_analysis`, `monthly_review`, `regen_content` |
| `sheets_api.py` | `generate_weekly_plan`, `generate_blog_posts`, `blog_deployer`, `post_pins`, `publish_content_queue`, `regen_content`, `regen_weekly_plan` (NEW), `monthly_review` |
| `slack_notify.py` | `generate_weekly_plan`, `generate_blog_posts`, `blog_deployer`, `post_pins`, `publish_content_queue`, `regen_content`, `regen_weekly_plan` (NEW), `token_manager`, `monthly_review` |
| `pinterest_api.py` | `post_pins`, `pull_analytics`, `setup_boards` |
| `gcs_api.py` | `publish_content_queue`, `blog_deployer`, `regen_content`, `backfill_hero_images` |
| `github_api.py` | `blog_deployer` |
| ~~`image_stock.py`~~ | ~~`generate_pin_content`, `regen_content`, `backfill_hero_images`~~ DELETED |
| `image_gen.py` | `generate_pin_content`, `regen_content` |
| `image_cleaner.py` (NEW) | `pin_assembler`, `generate_pin_content` |

### Highest-Risk Nodes (change cascades)

1. **`sheets_api.py`** -- Used by 8 scripts (was 7, +`regen_weekly_plan`). Any column index change breaks multiple workflows.
2. **`content-log.jsonl`** -- Written by 3 modules, read by 3 modules, schema inconsistency.
3. **`claude_api.py`** -- Used by 6 scripts. Now also manages GPT-5 Mini. Model ID or prompt format change affects everything. God file risk increased.
4. **`pin-schedule.json`** -- Now has 2 writers (`blog_deployer`, `regen_content`). Non-atomic writes risk corruption.
5. **`generate_weekly_plan.py`** -- `regen_weekly_plan.py` tightly coupled to `splice_replacements()`. Signature change breaks regen.
6. **`slack_notify.py`** -- Used by 9 scripts but low risk (notification-only, graceful degradation).

---

## Phase 5: Refactoring Plan

### Tier 0: Data (Establish single source of truth -- zero logic change)

| # | Task | Files | Status |
|---|------|-------|--------|
| T0-1 | Unify content-log.jsonl schema -- both append functions write identical field sets | `blog_deployer.py`, `post_pins.py` | OPEN |
| T0-2 | Create shared `content_log.py` module -- single `append_entry()`, `load_entries()`, `is_pin_posted()` | New `src/content_log.py`, modify 4 files | OPEN |
| T0-3 | Consolidate image hosting (Drive vs GCS) -- remove the redundant one | `drive_api.py` (potentially remove), `gcs_api.py`, callers | OPEN |
| T0-4 | Single-load pin-generation-results.json in blog_deployer | `blog_deployer.py` | PARTIALLY RESOLVED (was 3x, now 2x after swap removal; still should be 1x) |
| T0-5 | NEW: Make pin-schedule.json writes atomic | `blog_deployer.py`, `regen_content.py` | NEW |

### Tier 1: Safety (Extract hardcoded values, add error handling -- zero behavior change)

| # | Task | Files | Status |
|---|------|-------|--------|
| T1-1 | Create central `config.py` with all hardcoded values (H1-H29) | New `src/config.py`, all files | OPEN |
| T1-2 | Extract shared MIME detection utility | New `src/utils.py`, 3 API files | OPEN |
| T1-3 | Add schema validation for pin-generation-results.json | `blog_deployer.py`, potentially new `src/schemas.py` | OPEN |
| T1-4 | Make Sheets `_clear_and_write()` atomic (or add recovery) | `sheets_api.py` | OPEN |
| T1-5 | Add content-log.jsonl index for O(1) idempotency checks | `post_pins.py` | OPEN |
| T1-6 | NEW: Migrate GPT-5 Mini calls to `openai` SDK | `claude_api.py` | NEW |
| T1-7 | NEW: Make GPT-5 Mini fallback explicit (log warnings, not silent) | `claude_api.py` | NEW |
| T1-8 | NEW: Extract `_extract_drive_file_id()` to shared utility | `regen_content.py`, `publish_content_queue.py` | NEW |
| T1-9 | NEW: Add validation for regen Sheet cell restoration (B3/B4) | `regen_weekly_plan.py` | NEW |
| T1-10 | NEW: Fix .gitignore stale directory references | `.gitignore` | NEW |

### Tier 2: Structure (Consolidate duplication, break apart god files)

| # | Task | Files | Status |
|---|------|-------|--------|
| T2-1 | Consolidate blog post generation entry points | `generate_blog_posts.py` | OPEN |
| T2-2 | Consolidate blog generator type methods (4 -> 1 parameterized) | `blog_generator.py` | OPEN |
| T2-3 | Consolidate GitHub commit methods (3 -> 1) | `github_api.py` | OPEN |
| T2-4 | Consolidate blog deployer deployment modes (extract shared logic) | `blog_deployer.py` | OPEN |
| T2-5 | Remove trivial aliases (`get_boards`, `read_plan_status`, `generate_weekly_analysis`, `generate_monthly_review`, etc.) | `sheets_api.py`, `pinterest_api.py`, `claude_api.py` | OPEN |
| T2-6 | Split `sheets_api.py` into per-tab modules | `sheets_api.py` -> multiple files | OPEN |
| T2-7 | Extract `generate_content_memory_summary()` to own module | `weekly_analysis.py` | OPEN |
| T2-8 | NEW: Split GPT-5 Mini logic out of `claude_api.py` into `openai_api.py` | `claude_api.py` -> `claude_api.py` + new `openai_api.py` | NEW |

### Tier 3: Robustness (Validation, logging, edge cases)

| # | Task | Files | Status |
|---|------|-------|--------|
| T3-1 | Replace custom YAML parser with PyYAML (already used in `publish_content_queue.py` line 22) | `blog_generator.py` | OPEN |
| T3-2 | Add Sheet column validation (verify headers on first read) | `sheets_api.py` | OPEN |
| T3-3 | Fix `image_gen.py` output directory inconsistency | `image_gen.py` | OPEN |
| T3-4 | Fix pin_assembler JPEG-as-PNG naming | `pin_assembler.py` | OPEN |
| T3-5 | Add content-log.jsonl rotation/archival | New utility or cron job | OPEN |
| T3-6 | Fix stale jitter comment in post_pins.py | `post_pins.py` | OPEN |
| T3-7 | NEW: Harden JSON code-fence stripping in `generate_pin_content.py` | `generate_pin_content.py` | NEW |
| T3-8 | NEW: Add explicit error on missing `_drive_image_url` in regen | `regen_content.py` | NEW |
| T3-9 | NEW: Fix H1 stripping to handle blank lines before H1 | `blog_generator.py` | NEW |
| T3-10 | NEW: Remove dead htmlcsstoimage reference from `image_prompt.md` | `prompts/image_prompt.md` | NEW |

### Priority Summary

**Highest priority (new HIGH issues from simplification):**
1. T1-6/T1-7: GPT-5 Mini SDK migration + explicit fallback (NEW-13, NEW-14)
2. T0-5: Atomic pin-schedule.json writes (NEW-4)
3. T2-8: Split dual-model logic out of claude_api.py (S3 worsened)
4. T1-9: Validate regen Sheet cell restoration (NEW-8, NEW-10)

**Carried forward HIGH issues (unchanged):**
1. T0-1/T0-2: Unify content-log.jsonl (D1, DU2)
2. T1-1: Central config module (S5, H1-H29)
3. T1-4: Atomic Sheets _clear_and_write() (E3)

### Simplification Impact Summary

| Metric | Before | After (verified) | Delta |
|--------|--------|-------------------|-------|
| Python files (src/apis/) | 10 | 9 | -1 (image_stock.py deleted) |
| Python files (src/*.py) | 16 | 18 | +2 (regen_weekly_plan.py, image_cleaner.py added) |
| Total Python files | 26 | 27 | +1 (1 deleted, 2 added) |
| Total lines (src/apis/) | ~4,836 | 4,849 | +13 (stock deleted -453, claude grew +414, slack grew +56) |
| Total lines (src/*.py) | ~9,236 | 10,675 | +1,439 (regen_weekly_plan +320, image_cleaner +101, pin_content shrunk -311, blog_deployer shrunk ~-98) |
| God files (>800 lines) | 5 | 6 | +1 (claude_api.py joined, image_stock.py left, blog_deployer dropped from 1,018 to 920 but still >800) |
| Hardcoded values | 27 | 28+ | +1 (GPT-5 cost rates; model name now has env var) |
| External API dependencies | 7 | 5 | -2 (Unsplash, Pexels removed) |
| HIGH severity issues | 5 | 7 | +2 (NEW-12 downgraded to LOW -- model name has env var override) |
| RESOLVED issues | 0 | 10 | +10 |
| Duplication instances | 10 | 12 | +2 (DU11: drive file ID extraction, DU12: claude_api aliases) |
