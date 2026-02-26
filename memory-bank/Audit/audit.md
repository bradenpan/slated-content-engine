# Pinterest Pipeline — Codebase Audit

**Audit started:** 2026-02-25
**Status:** In Progress

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
- **Dependencies:** None.
- **Issues:** None.

#### `src/apis/claude_api.py` (~540 lines)
- **Purpose:** Wraps Anthropic Claude API for all LLM tasks: planning, pin copy, blog posts, image prompts, weekly/monthly analysis.
- **Dependencies:** `anthropic`, `pathlib`, `json`, `base64`, `logging`. Reads from `prompts/` and `strategy/` directories.
- **Issues:**
  - **Hardcoded model IDs** (lines 40-42): `MODEL_ROUTINE = "claude-sonnet-4-6"`, `MODEL_DEEP = "claude-opus-4-6"`, `MODEL_HAIKU = "claude-haiku-4-5-20251001"`. Should be config/env vars.
  - **Hardcoded cost estimates** (lines 45-49): `COST_PER_MTK` dict. Will go stale as pricing changes.
  - **God file tendency:** This single file handles planning, copy generation, blog posts, image prompts, analysis, and monthly review — all via different methods on one class. Each concern could be a separate module or at least method group.
  - **PROMPTS_DIR/STRATEGY_DIR** (lines 36-37): Uses relative path `Path(__file__).parent.parent.parent / "prompts"`. Fragile if file moves.
  - Prompt template loading is tightly coupled to file naming conventions in `prompts/` directory.

#### `src/apis/pinterest_api.py` (~569 lines)
- **Purpose:** Thin wrapper around Pinterest v5 REST API (pins, boards, analytics, rate limits).
- **Dependencies:** `requests`, `time`, `base64`, `logging`.
- **Issues:**
  - **Hardcoded API URLs** (lines 39-40): `BASE_URL_PRODUCTION`, `BASE_URL_SANDBOX`.
  - **Hardcoded retry constants** (lines 46-47): `MAX_RETRIES = 3`, `RETRY_BACKOFF_BASE = 2`.
  - **Hardcoded metric types** (line 43): `DEFAULT_METRIC_TYPES`.
  - `get_boards()` (line 219-221) is a trivial alias for `list_boards()` — duplication.
  - Content-type detection via magic bytes (lines 131-139) is **duplicated** across pinterest_api.py, gcs_api.py, and drive_api.py.
  - `__main__` smoke test block is useful but could be a proper test.

#### `src/apis/gcs_api.py` (~427 lines)
- **Purpose:** Uploads pin/blog hero images to Google Cloud Storage for Sheets `=IMAGE()` previews.
- **Dependencies:** `google-cloud-storage`, `google-auth`, `json`, `base64`, `pathlib`.
- **Issues:**
  - **Hardcoded bucket name** (line 28): `DEFAULT_BUCKET_NAME = "slated-pipeline-pins"`.
  - **Duplicated magic-byte MIME detection** (lines 132-142): Same pattern as pinterest_api.py and drive_api.py.
  - `upload_single_image()` (lines 353-367) is a trivial wrapper around `upload_image()` — duplication.
  - Fallback for `pyca/cryptography` RSA key issues (lines 83-95): Workaround that should be documented/removed when root cause is fixed.
  - **Silent failures:** Many methods return `None` on error instead of raising. Callers must remember to check.
  - `delete_old_images(prefix="W")` (line 203): Hardcoded prefix "W" for weekly pin cleanup. Fragile.

#### `src/apis/github_api.py` (~544 lines)
- **Purpose:** Commits blog posts (MDX + images) to goslated.com repo, triggering Vercel deploy.
- **Dependencies:** `PyGithub`, `requests`, `time`, `pathlib`.
- **Issues:**
  - **Hardcoded base URL** (line 43): `GOSLATED_BASE_URL = "https://goslated.com"`. Should be config.
  - **Three methods for committing blog posts:** `commit_blog_post()`, `commit_blog_posts()`, `commit_multiple_posts()`. Overlapping functionality — consolidation needed.
  - `_create_or_update_file()` (lines 459-519): Dead code — never called from anywhere in the codebase (superseded by tree-based `_commit_files`).
  - `verify_deployment()` polls with exponential backoff, but the timeout/interval values are hardcoded.
  - **Default branch is hardcoded** to `"develop"` in `_commit_files` (line 373) and `"main"` in other methods. Mix of defaults is confusing.

#### `src/apis/sheets_api.py` (~944 lines)
- **Purpose:** Manages Google Sheets (Weekly Review, Content Queue, Post Log, Dashboard tabs).
- **Dependencies:** `google-api-python-client`, `google-auth`, `json`, `base64`.
- **Issues:**
  - **Largest API file (944 lines)** — god file. Manages 4 different sheet tabs with different schemas.
  - **Hardcoded column indices** (lines 47-69): `CQ_COL_ID = 0`, `CQ_COL_TYPE = 1`, etc. Any column reorder in the Sheet breaks everything silently.
  - **Hardcoded tab names** (lines 40-43): `TAB_WEEKLY_REVIEW = "Weekly Review"`, etc.
  - `read_plan_status()` (line 231-233) is trivial alias for `read_plan_approval_status()`.
  - `read_content_statuses()` (line 456-458) is trivial alias for `read_content_approvals()`.
  - `update_dashboard_metrics()` (lines 804-806) is trivial alias for `update_dashboard()`.
  - **Fragile coupling to Sheet layout**: `read_plan_approval_status()` reads from `B3` hardcoded (line 219). `write_deploy_status()` writes to `A4:C4` (line 249). If the layout changes, these silently read/write wrong cells.
  - `reset_regen_trigger()` writes to `O1` (line 579) — hardcoded cell reference.
  - `_clear_and_write()` clears entire tab then writes — no atomicity. If write fails after clear, data is lost.

#### `src/apis/drive_api.py` (~340 lines)
- **Purpose:** Uploads pin images to Google Drive for Sheets `=IMAGE()` preview.
- **Dependencies:** `google-api-python-client`, `google-auth`, `json`, `base64`.
- **Issues:**
  - **Hardcoded folder name** (line 26): `DRIVE_FOLDER_NAME = "pinterest-pipeline-pins"`.
  - **Duplicated magic-byte MIME detection** (lines 188-197): Same as gcs_api.py and pinterest_api.py.
  - **Redundant with GCS:** Both `drive_api.py` and `gcs_api.py` serve the same purpose (hosting images for Sheets preview). The codebase appears to have migrated from Drive to GCS but kept both.
  - `_clear_folder()` only fetches `pageSize=100` — won't clear all if >100 files.

#### `src/apis/image_gen.py` (~538 lines)
- **Purpose:** AI image generation via OpenAI gpt-image-1.5 and Replicate Flux Pro.
- **Dependencies:** `requests`, `uuid`, `base64`, `io`, `time`, `PIL` (optional).
- **Issues:**
  - **Hardcoded API endpoints** (lines 277, 336-337): OpenAI and Replicate URLs.
  - **Hardcoded model name** (line 284): `"gpt-image-1.5"`. Should be config.
  - **Hardcoded cost estimates** (lines 38-41): Will go stale.
  - **Hardcoded output directory** (line 158): `data/generated_pins` (note: different from `data/generated/pins` used elsewhere — potential bug or inconsistency).
  - `MIN_IMAGE_SIZE = 10_000` (line 44): Magic number threshold.
  - `_modify_prompt_for_retry()` uses hardcoded modifier strings (lines 473-478).
  - Replicate polling uses hardcoded `max_poll_time = 120`, `poll_interval = 3`.

#### `src/apis/image_stock.py` (~453 lines)
- **Purpose:** Stock photo search/download from Unsplash and Pexels.
- **Dependencies:** `requests`, `pathlib`.
- **Issues:**
  - **Hardcoded API base URLs** (lines 36-37): `UNSPLASH_BASE_URL`, `PEXELS_BASE_URL`.
  - `search_images()` (line 72-92) and `search()` (lines 94-175) are dual interfaces with confusing parameter mapping.
  - Rate limit tracking is instance-level (not persisted) — resets on each script run.

#### `src/apis/slack_notify.py` (~481 lines)
- **Purpose:** Slack webhook notifications for pipeline events.
- **Dependencies:** `requests`, `json`.
- **Issues:**
  - **Hardcoded color constants** (lines 34-37).
  - Well-structured with clear event-specific methods.
  - Graceful degradation when webhook URL missing (logs but doesn't crash).
  - `notify()` method accepts `level` but the level `"success"` (used in blog_deployer.py line 306) is not in `color_map` — falls back to green, but the intent is unclear.

### Pipeline Scripts (`src/`)

#### `src/token_manager.py` (~423 lines)
- **Purpose:** Pinterest OAuth 2.0 token lifecycle (30-day access, 60-day continuous refresh).
- **Dependencies:** `requests`, `json`, `base64`, `time`, `datetime`, `pathlib`, `src.apis.slack_notify`.
- **Issues:**
  - **Hardcoded token store path** (line 51): `TOKEN_STORE_PATH = Path(__file__).parent.parent / "data" / "token-store.json"`.
  - **Hardcoded redirect URI** (line 53): `REDIRECT_URI = "http://localhost:8085/"`.
  - **Hardcoded OAuth URL** (line 52): `PINTEREST_OAUTH_URL`.
  - **Hardcoded refresh threshold** (line 54): `REFRESH_THRESHOLD_DAYS = 5`.
  - Lazy-loads Slack notifier (lines 99-108): Uses `False` sentinel to prevent retrying — works but unconventional.
  - Token caching (`_token_data`) is instance-level; if multiple TokenManager instances exist in the same process, they could have stale data.

#### `src/generate_weekly_plan.py` (~large, truncated in read)
- **Purpose:** Generates the weekly content plan (8-10 blog posts + 28 pins) using Claude Sonnet. The "brain" step.
- **Dependencies:** `ClaudeAPI`, `SheetsAPI`, `SlackNotify`, `json`, `datetime`, `pathlib`.
- **Issues:**
  - File is large (estimated 600+ lines) — another god file candidate.
  - Loads context from 8+ strategy files — complex initialization.
  - Tightly coupled to the specific structure of strategy JSON files.
  - **CRITICAL: Analysis showed truncation — need to re-read this file fully.**

#### `src/weekly_analysis.py` (~764 lines)
- **Purpose:** Analyzes past week's Pinterest performance using Claude + data aggregation.
- **Dependencies:** `ClaudeAPI`, `pull_analytics` (imports `load_content_log`, `compute_derived_metrics`, `aggregate_by_dimension`), `json`, `datetime`, `pathlib`.
- **Issues:**
  - **Hardcoded paths** (lines 51-57): `PROJECT_ROOT`, `ANALYSIS_DIR`, `DATA_DIR`, `CONTENT_LOG_PATH`, `PIN_SCHEDULE_PATH`, `STRATEGY_DIR`, `ANALYTICS_DIR`.
  - `generate_content_memory_summary()` (lines 298-520) is 220 lines — could be its own module.
  - **Hardcoded date math**: `four_weeks_ago`, `ninety_days_ago`, `sixty_days_ago` computed from `date.today()` — no way to run analysis for a historical date.
  - Has a fallback analysis generator (lines 643-732) for when Claude is unavailable — good resilience pattern.
  - `_compute_account_trends()` duplicates some aggregation logic from `build_analysis_context()`.

#### `src/generate_blog_posts.py` (~376 lines)
- **Purpose:** Orchestrates blog post generation from approved weekly plan.
- **Dependencies:** `BlogGenerator`, `SheetsAPI`, `SlackNotify`, `json`, `pathlib`.
- **Issues:**
  - **Two entry points** that do nearly the same thing: `generate_blog_posts()` (line 42) and `generate_all_blog_posts()` (line 167). ~60% duplicated logic.
  - `save_generated_posts()` (lines 310-332) duplicates save logic already in `BlogGenerator.save_post()`.
  - `load_approved_plan()` (lines 280-308) falls back to local file even when Sheets says plan isn't approved — potentially dangerous.

#### `src/blog_generator.py` (~763 lines)
- **Purpose:** Generates MDX blog posts with frontmatter from content plan specs.
- **Dependencies:** `ClaudeAPI`, `json`, `re`, `unicodedata`, `pathlib`.
- **Issues:**
  - **Hardcoded word count targets** (lines 40-45): `WORD_COUNT_TARGETS`.
  - **Custom YAML parser** (lines 515-600): Implements a simple YAML parser instead of using `PyYAML` or `ruamel.yaml`. Will break on edge cases (nested objects, multi-line strings, special YAML characters).
  - The four `generate_*_post()` methods (lines 222-349) are nearly identical — only differ in prompt template name and default pillar. Classic duplication.
  - `_validate_generated_post()` logs warnings but never raises for non-critical issues — validation results are effectively lost.

#### `src/generate_pin_content.py` (~large, truncated)
- **Purpose:** Generates pin assets (copy + images) for all pins in the approved plan.
- **Dependencies:** `ClaudeAPI`, `ImageStockAPI`, `ImageGenAPI`, `PinAssembler`, `json`, `pathlib`.
- **Issues:**
  - **Hardcoded base URL** (line 41): `BLOG_BASE_URL = "https://goslated.com/blog"`. Duplicated from blog_deployer.py.
  - **Hardcoded batch size** (line 44): `COPY_BATCH_SIZE = 6`.
  - Large file (likely 800+ lines) — complex orchestration.
  - **CRITICAL: File was truncated — need full read for complete audit.**

#### `src/pin_assembler.py` (~996 lines)
- **Purpose:** Assembles pin images from HTML/CSS templates using Puppeteer (headless Chrome).
- **Dependencies:** `subprocess` (Node.js), `json`, `tempfile`, `pathlib`, `PIL` (optional), `base64`, `html`, `random`.
- **Issues:**
  - **Hardcoded dimensions** (lines 47-48): `PIN_WIDTH = 1000`, `PIN_HEIGHT = 1500`.
  - **Hardcoded max file size** (line 51): `MAX_PNG_SIZE = 500 * 1024`.
  - `render_pin_sync()` (lines 747-755) is a backward-compat wrapper — should eventually be removed.
  - `_optimize_image()` (lines 510-559): Renames JPEG to `.png` extension to keep downstream paths valid — this is a **file format lie** that will confuse debugging and MIME detection.
  - `_activate_variant()` (lines 239-274): Line-by-line HTML parsing to toggle variants — fragile, will break if HTML structure changes.
  - **Template test data** (lines 770-951) is hardcoded in the module — should be in test fixtures.
  - `select_variant()` uses `random.choice` — non-deterministic in production.

#### `src/blog_deployer.py` (~1018 lines)
- **Purpose:** Commits approved blogs to goslated.com repo, verifies deployment, creates pin schedule, logs to content-log.jsonl.
- **Dependencies:** `GitHubAPI`, `SheetsAPI`, `SlackNotify`, `PinAssembler`, `GcsAPI`, `json`, `pathlib`, `re`, `requests`.
- **Issues:**
  - **Largest pipeline script (1018 lines)** — god file. Handles blog deployment, URL verification, pin scheduling, content logging, AI image swaps.
  - **Hardcoded base URL** (line 40): `BLOG_BASE_URL = "https://goslated.com/blog"` — **duplicated** from generate_pin_content.py.
  - **Hardcoded timeout** (lines 43-44): `DEPLOY_VERIFY_TIMEOUT = 180`, `DEPLOY_VERIFY_RETRY_DELAY = 15`.
  - **Three deployment modes** with significant code overlap: `deploy_approved_content()`, `deploy_to_preview()`, `promote_to_production()`. Each reads approvals, filters, deploys — 60%+ duplicated logic.
  - `_append_to_content_log()` (lines 853-948): ~100 lines of content log writing logic that **overlaps with** `post_pins.py`'s `append_to_content_log()`. Both write to the same file with slightly different schemas.
  - `_create_pin_schedule()` (lines 701-772) loads `pin-generation-results.json` — this is the third time this file is loaded across the codebase.
  - `_process_ai_image_swaps()` (lines 774-851) imports `requests` inside the function body.

#### `src/post_pins.py` (~732 lines)
- **Purpose:** Posts approved pins to Pinterest via API. Runs 3x daily via cron.
- **Dependencies:** `PinterestAPI`, `SheetsAPI`, `SlackNotify`, `TokenManager`, `requests`, `json`, `time`, `random`, `hashlib`, `base64`, `zoneinfo`.
- **Issues:**
  - **Hardcoded jitter constants** (lines 66-68): `INITIAL_JITTER_MAX = 900`, `INTER_PIN_JITTER_MIN = 300`, `INTER_PIN_JITTER_MAX = 1200`.
  - **Hardcoded slot pin counts** (lines 59-63): `SLOT_PIN_COUNTS = {"morning": 1, "afternoon": 1, "evening": 2}`.
  - **Hardcoded timezone** (line 56): `ET = ZoneInfo("America/New_York")`.
  - `is_already_posted()` (lines 335-366): Scans **entire** content-log.jsonl line by line every time. Will get progressively slower as the log grows. No index.
  - `append_to_content_log()` (lines 369-386): **Duplicated** from blog_deployer.py with a slightly different schema (this one includes `pin_clicks`, `save_rate`, `click_through_rate`, `last_analytics_pull` — the blog_deployer version doesn't).
  - `_record_failure()` (lines 652-703): Tracks failures in a separate `posting-failures.json` file — another data store.
  - Board map includes both original case and lowercase keys (line 468) — doubles the map size unnecessarily.
  - Comment at line 300 says jitter is "0 to 5400 seconds" but `INITIAL_JITTER_MAX = 900` — **stale comment**.

### Remaining Files Still To Audit
- `src/pull_analytics.py`
- `src/publish_content_queue.py`
- `src/regen_content.py`
- `src/setup_boards.py`
- `src/backfill_hero_images.py`
- `src/monthly_review.py`
- `oauth_setup.py`
- `render_pin.js`
- `src/apps-script/trigger.gs`
- `.github/workflows/*.yml` (10 workflow files)
- `requirements.txt`, `package.json`
- `strategy/*.json`, `strategy/*.md`
- `prompts/*.md`
- `.env.example`
- `.gitignore`
- `templates/pins/**`

---

## Phase 2: Data Inventory

### External Data Stores

| Store | Type | Location | Readers | Writers | Canonical? |
|-------|------|----------|---------|---------|------------|
| **content-log.jsonl** | File (JSONL) | `data/content-log.jsonl` | `weekly_analysis.py`, `pull_analytics.py`, `post_pins.py` (idempotency check) | `blog_deployer.py` (initial entries, pin_id=None), `post_pins.py` (posted entries, pin_id set), `pull_analytics.py` (analytics updates) | YES — primary record of all content |
| **pin-schedule.json** | File (JSON) | `data/pin-schedule.json` | `post_pins.py`, `weekly_analysis.py` | `blog_deployer.py` | YES — posting queue |
| **pin-generation-results.json** | File (JSON) | `data/pin-generation-results.json` | `blog_deployer.py` (3x: deploy, schedule, swap), `regen_content.py` | `generate_pin_content.py`, `blog_deployer.py` (after AI swap) | YES — generated pin metadata |
| **blog-generation-results.json** | File (JSON) | `data/blog-generation-results.json` | `generate_pin_content.py` | `generate_blog_posts.py` | YES — generated blog metadata |
| **weekly-plan-*.json** | File (JSON) | `data/weekly-plan-*.json` | `generate_blog_posts.py`, `generate_pin_content.py` | `generate_weekly_plan.py` | YES — weekly plan |
| **token-store.json** | File (JSON) | `data/token-store.json` | `token_manager.py` | `token_manager.py` | YES — OAuth tokens |
| **content-memory-summary.md** | File (MD) | `data/content-memory-summary.md` | `generate_weekly_plan.py` | `weekly_analysis.py` | Derived from content-log.jsonl |
| **posting-failures.json** | File (JSON) | `data/posting-failures.json` | `post_pins.py` | `post_pins.py` | YES — failure tracking |
| **Google Sheet: Weekly Review** | Cloud | Google Sheets tab | `sheets_api.py` (plan status, deploy status) | `generate_weekly_plan.py`, `blog_deployer.py` | Shared source of truth with manual review |
| **Google Sheet: Content Queue** | Cloud | Google Sheets tab | `blog_deployer.py`, `post_pins.py`, `regen_content.py` | `publish_content_queue.py`, `regen_content.py` | Shared source of truth with manual review |
| **Google Sheet: Post Log** | Cloud | Google Sheets tab | — | `sheets_api.py` (append_post_log, update_pin_status) | Derived — also written to content-log.jsonl |
| **Google Sheet: Dashboard** | Cloud | Google Sheets tab | — | `sheets_api.py` (update_dashboard) | Derived — from analytics |
| **GCS Bucket** | Cloud | `slated-pipeline-pins` | Google Sheets (=IMAGE()), `regen_content.py` | `gcs_api.py`, `publish_content_queue.py` | Image hosting |
| **Google Drive Folder** | Cloud | `pinterest-pipeline-pins` | Google Sheets (=IMAGE()) | `drive_api.py` | **REDUNDANT** — same purpose as GCS |
| **goslated.com GitHub Repo** | Cloud | `content/blog/`, `public/assets/blog/` | Vercel (auto-deploy) | `github_api.py` | Blog content deployment |
| **Pinterest API** | Cloud | Pinterest v5 API | `pull_analytics.py` | `post_pins.py` | External — pin hosting |
| **Slack Webhook** | Cloud | Webhook URL | — | `slack_notify.py` | Notification sink |
| **Anthropic Claude API** | Cloud | API | — | `claude_api.py` | LLM provider |
| **Unsplash API** | Cloud | API | — | `image_stock.py` | Stock photo source |
| **Pexels API** | Cloud | API | — | `image_stock.py` | Stock photo source |
| **OpenAI API** | Cloud | API | — | `image_gen.py` | AI image generation |
| **Replicate API** | Cloud | API | — | `image_gen.py` | AI image generation |

### Data Flow Anomalies

1. **content-log.jsonl has THREE writers with DIFFERENT schemas:**
   - `blog_deployer.py` writes initial entries with `pin_id=None` and no analytics fields
   - `post_pins.py` writes entries with `pin_id`, `pinterest_pin_id`, and analytics fields (`pin_clicks`, `save_rate`, `click_through_rate`, `last_analytics_pull`)
   - `pull_analytics.py` updates existing entries with analytics data
   - **RISK:** Schema inconsistency between entry types.

2. **pin-generation-results.json is loaded 3 times in blog_deployer.py:**
   - `_create_pin_schedule()` loads it
   - `promote_to_production()` loads it for AI image swaps
   - `_append_to_content_log()` loads it again
   - Each load is independent with its own try/except.

3. **Google Drive and GCS serve the same purpose** (image hosting for Sheets =IMAGE()). Unclear which is the canonical store — both are maintained.

4. **BLOG_BASE_URL is defined in 3 places:**
   - `src/apis/github_api.py` line 43: `GOSLATED_BASE_URL = "https://goslated.com"`
   - `src/generate_pin_content.py` line 41: `BLOG_BASE_URL = "https://goslated.com/blog"`
   - `src/blog_deployer.py` line 40: `BLOG_BASE_URL = "https://goslated.com/blog"`

---

## Phase 3: Issues

### 3.1 Data Flow & Source of Truth

| # | Severity | File(s) | Issue |
|---|----------|---------|-------|
| D1 | HIGH | `blog_deployer.py`, `post_pins.py` | **content-log.jsonl has two append functions with different schemas.** `blog_deployer._append_to_content_log()` writes entries without analytics tracking fields. `post_pins.append_to_content_log()` writes entries with `pin_clicks`, `save_rate`, etc. This causes schema inconsistency — `pull_analytics.py` may fail to update fields that don't exist. |
| D2 | HIGH | `blog_deployer.py` | **pin-generation-results.json loaded 3 separate times** in a single deployment flow. Each load is independent — if the file changes between loads (e.g., during AI swap), later loads see different data. |
| D3 | MEDIUM | `drive_api.py`, `gcs_api.py` | **Two image hosting services for the same purpose.** Both Drive and GCS exist to host images for Sheets =IMAGE() formulas. Migration to GCS appears incomplete. |
| D4 | MEDIUM | `github_api.py`, `generate_pin_content.py`, `blog_deployer.py` | **BLOG_BASE_URL defined in 3 places.** Any URL change requires 3 edits. |
| D5 | LOW | `post_pins.py` | **Posting failures tracked in separate file** (`posting-failures.json`) not connected to the content log. No cleanup mechanism. |

### 3.2 Hardcoded Values

| # | File | Line | Value | Should Be |
|---|------|------|-------|-----------|
| H1 | `claude_api.py` | 40-42 | Model IDs (`claude-sonnet-4-6`, etc.) | `CONFIG.CLAUDE_MODEL_ROUTINE` or env var |
| H2 | `claude_api.py` | 45-49 | Cost per million tokens | Config or dynamic lookup |
| H3 | `pinterest_api.py` | 39-40 | Pinterest API base URLs | Config constant |
| H4 | `gcs_api.py` | 28 | `DEFAULT_BUCKET_NAME = "slated-pipeline-pins"` | Env var only (already has env fallback, but hardcoded default) |
| H5 | `github_api.py` | 43 | `GOSLATED_BASE_URL = "https://goslated.com"` | Env var or shared config |
| H6 | `drive_api.py` | 26 | `DRIVE_FOLDER_NAME = "pinterest-pipeline-pins"` | Config constant |
| H7 | `image_gen.py` | 38-41 | Cost per image dict | Config |
| H8 | `image_gen.py` | 44 | `MIN_IMAGE_SIZE = 10_000` | Config constant |
| H9 | `image_gen.py` | 158 | Output dir `data/generated_pins` | Shared path constant (note: differs from `data/generated/pins` used elsewhere!) |
| H10 | `image_gen.py` | 284 | `"gpt-image-1.5"` model name | Config/env var |
| H11 | `sheets_api.py` | 40-43 | Tab names (Weekly Review, etc.) | Config file |
| H12 | `sheets_api.py` | 47-69 | Column indices (CQ_COL_ID=0, etc.) | Config or schema definition file |
| H13 | `sheets_api.py` | 219 | Cell reference `B3` for plan status | Named range or config |
| H14 | `sheets_api.py` | 249 | Cell range `A4:C4` for deploy status | Named range or config |
| H15 | `sheets_api.py` | 579 | Cell reference `O1` for regen trigger | Named range or config |
| H16 | `token_manager.py` | 53 | `REDIRECT_URI = "http://localhost:8085/"` | Env var |
| H17 | `token_manager.py` | 54 | `REFRESH_THRESHOLD_DAYS = 5` | Config |
| H18 | `pin_assembler.py` | 47-48 | `PIN_WIDTH=1000, PIN_HEIGHT=1500` | Config constants |
| H19 | `pin_assembler.py` | 51 | `MAX_PNG_SIZE = 500 * 1024` | Config constant |
| H20 | `blog_deployer.py` | 40 | `BLOG_BASE_URL` (duplicate of H5) | Shared config |
| H21 | `blog_deployer.py` | 43-44 | Deploy verify timeout/delay | Config |
| H22 | `post_pins.py` | 56 | `ET = ZoneInfo("America/New_York")` | Config |
| H23 | `post_pins.py` | 59-63 | Slot pin counts | Config or strategy file |
| H24 | `post_pins.py` | 66-68 | Jitter constants | Config |
| H25 | `generate_pin_content.py` | 41 | `BLOG_BASE_URL` (duplicate of H5, H20) | Shared config |
| H26 | `generate_pin_content.py` | 44 | `COPY_BATCH_SIZE = 6` | Config |
| H27 | `blog_generator.py` | 40-45 | `WORD_COUNT_TARGETS` | Config or strategy file |

### 3.3 Fragile Coupling

| # | File(s) | Issue |
|---|---------|-------|
| F1 | `sheets_api.py` | Column indices (H12) create fragile coupling to Sheet layout. If user adds a column, all indices shift and break silently. |
| F2 | `sheets_api.py` | Cell references (H13-H15) hardcoded to specific cells. No validation that the cell contains the expected data type. |
| F3 | `blog_deployer.py`, `generate_pin_content.py` | Pin generation results JSON schema assumed but never validated. Key lookups use `.get()` with empty defaults, masking missing data. |
| F4 | `pin_assembler.py` | `_activate_variant()` parses HTML line-by-line looking for `data-variant=` and `pin-canvas` strings. Any HTML template restructuring breaks this. |
| F5 | `blog_generator.py` | Custom YAML parser (lines 515-600) will break on: nested objects, multi-line strings, YAML anchors/aliases, colons in values, special characters. |
| F6 | `post_pins.py` | `build_board_map()` creates a runtime mapping of board names to IDs. If Pinterest board names are changed, all scheduled pins with old names fail. |
| F7 | All pipeline scripts | All scripts resolve paths relative to `Path(__file__).parent.parent`. If the directory structure changes, everything breaks. |

### 3.4 Duplication

| # | Files | Issue |
|---|-------|-------|
| DU1 | `pinterest_api.py:131-139`, `gcs_api.py:132-142`, `drive_api.py:188-197` | **Magic-byte MIME type detection** (JPEG/PNG/WebP) duplicated in 3 files with identical logic. Should be a shared utility. |
| DU2 | `blog_deployer.py:853-948`, `post_pins.py:369-386` | **Two `append_to_content_log()` functions** writing to the same file with different schemas. |
| DU3 | `generate_blog_posts.py:42-164`, `generate_blog_posts.py:167-241` | **`generate_blog_posts()` and `generate_all_blog_posts()`** are ~60% identical. |
| DU4 | `blog_generator.py:222-349` | **Four `generate_*_post()` methods** are structurally identical — only differ in post_type string and default pillar. |
| DU5 | `github_api.py:90-218` | **Three commit methods** (`commit_blog_post`, `commit_blog_posts`, `commit_multiple_posts`) with overlapping functionality. |
| DU6 | `sheets_api.py` | **Three alias methods** that are trivial wrappers: `read_plan_status()`, `read_content_statuses()`, `update_dashboard_metrics()`. |
| DU7 | `gcs_api.py:353-367` | `upload_single_image()` is a trivial wrapper around `upload_image()`. |
| DU8 | `pinterest_api.py:219-221` | `get_boards()` is a trivial alias for `list_boards()`. |
| DU9 | `blog_deployer.py:73-221,223-317,319-491` | **Three deployment modes** (`deploy_approved_content`, `deploy_to_preview`, `promote_to_production`) with 60%+ shared logic (read approvals, filter, deploy, verify, schedule, log, notify). |
| DU10 | `github_api.py:43`, `generate_pin_content.py:41`, `blog_deployer.py:40` | **BLOG_BASE_URL defined 3 times**. |

### 3.5 Missing Error Handling

| # | File | Line(s) | Issue |
|---|------|---------|-------|
| E1 | `gcs_api.py` | Many methods | Returns `None` on failure instead of raising. Callers often don't check return values. |
| E2 | `blog_generator.py` | 447-513 | `_validate_generated_post()` logs warnings but never raises or returns validation results. Failed validations are effectively invisible. |
| E3 | `sheets_api.py` | 823-845 | `_clear_and_write()` clears tab, then writes. If write fails, data is lost with no recovery. |
| E4 | `post_pins.py` | 335-366 | `is_already_posted()` scans entire JSONL file — O(n) per pin. Will degrade as content log grows. Not an error handling issue per se, but a silent performance degradation. |
| E5 | `blog_deployer.py` | 184-189 | Uses `sheets.update_pin_status()` to update blog post status — this function is designed for *pins* in the *Post Log* tab, not blogs. Semantic mismatch. |

### 3.6 Structural Issues

| # | File | Issue |
|---|------|-------|
| S1 | `sheets_api.py` (944 lines) | **God file** managing 4 different Sheet tabs with different schemas, column mappings, read/write patterns. Should be split into per-tab classes or at minimum per-tab method groups. |
| S2 | `blog_deployer.py` (1018 lines) | **God file** handling blog deployment, URL verification, pin scheduling, content logging, AI image swaps, and Slack notification orchestration. |
| S3 | `claude_api.py` (~540 lines) | **God file** handling all LLM interactions for planning, pin copy, blog generation, image prompts, weekly analysis, and monthly review. |
| S4 | `pin_assembler.py` (~996 lines) | Contains both the assembler logic and ~200 lines of test render data. Test data should be external. |
| S5 | No `config.py` or central configuration | Hardcoded values scattered across 15+ files. No single place to change URLs, thresholds, model names, etc. |
| S6 | No shared utility module | Duplicated code (MIME detection, path resolution, content log operations) suggests need for a `src/utils.py` or similar. |

### 3.7 Configuration & Environment

| # | Issue |
|---|-------|
| C1 | No central configuration module. Each file defines its own constants. |
| C2 | `image_gen.py` line 158 uses `data/generated_pins` but everywhere else uses `data/generated/pins`. Potential path mismatch bug. |
| C3 | Environment variable names are consistent but documented in each file's docstring rather than a central reference. `.env.example` exists but may be incomplete. |
| C4 | Google credentials shared between Sheets, Drive, and GCS (`GOOGLE_SHEETS_CREDENTIALS_JSON`) — semantically named for Sheets but used for all Google services. |

---

## Phase 4: Dependency Map

### Module Dependency Graph

```
                    ┌─────────────────────────────┐
                    │   GitHub Actions Workflows   │
                    │  (10 .yml files — triggers)  │
                    └──────────────┬───────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          v                        v                        v
   weekly-review.yml        generate-content.yml     daily-post-*.yml
          │                        │                        │
          v                        v                        v
  ┌───────────────┐     ┌──────────────────┐     ┌──────────────┐
  │ pull_analytics │     │generate_weekly_  │     │  post_pins   │
  │               │     │     plan         │     │              │
  └───────┬───────┘     └────────┬─────────┘     └──────┬───────┘
          │                      │                       │
          v                      v                       │
  ┌───────────────┐     ┌──────────────────┐            │
  │weekly_analysis│     │generate_blog_    │            │
  │               │     │    posts         │            │
  └───────┬───────┘     └────────┬─────────┘            │
          │                      │                       │
          │                      v                       │
          │             ┌──────────────────┐            │
          │             │ blog_generator   │            │
          │             └────────┬─────────┘            │
          │                      │                       │
          │                      v                       │
          │             ┌──────────────────┐            │
          │             │generate_pin_     │            │
          │             │   content        │            │
          │             └────────┬─────────┘            │
          │                      │                       │
          │              ┌───────┼───────┐              │
          │              v       v       v              │
          │        ┌─────────┐ ┌────┐ ┌──────┐         │
          │        │image_   │ │pin_│ │image_│         │
          │        │stock    │ │asm │ │gen   │         │
          │        └─────────┘ └────┘ └──────┘         │
          │                      │                       │
          │                      v                       │
          │             ┌──────────────────┐            │
          │             │publish_content_  │            │
          │             │    queue         │            │
          │             └────────┬─────────┘            │
          │                      │                       │
          │              ┌───────┼───────┐              │
          │              v       v       v              │
          │        ┌─────────┐ ┌────┐ ┌──────┐         │
          │        │gcs_api  │ │drv │ │sheets│         │
          │        └─────────┘ └────┘ └──────┘         │
          │                      │                       │
          │                      v                       │
          │             ┌──────────────────┐            │
          │             │  blog_deployer   │◄───────────┘
          │             └────────┬─────────┘     (uses board map)
          │              ┌───────┼───────┐
          │              v       v       v
          │        ┌─────────┐ ┌────┐ ┌──────┐
          │        │github_  │ │shts│ │slack │
          │        │api      │ │api │ │notfy │
          │        └─────────┘ └────┘ └──────┘
          │
          │         ┌──────────────────┐
          └────────>│  content-log.    │
                    │    jsonl         │
                    └──────────────────┘
```

### Shared API Dependencies (all import these)

| API Module | Used By |
|------------|---------|
| `claude_api.py` | `generate_weekly_plan`, `blog_generator`, `generate_pin_content`, `weekly_analysis`, `monthly_review`, `regen_content` |
| `sheets_api.py` | `generate_weekly_plan`, `generate_blog_posts`, `blog_deployer`, `post_pins`, `publish_content_queue`, `regen_content`, `monthly_review` |
| `slack_notify.py` | `generate_weekly_plan`, `generate_blog_posts`, `blog_deployer`, `post_pins`, `publish_content_queue`, `regen_content`, `token_manager`, `monthly_review` |
| `pinterest_api.py` | `post_pins`, `pull_analytics`, `setup_boards` |
| `gcs_api.py` | `publish_content_queue`, `blog_deployer`, `regen_content`, `backfill_hero_images` |
| `github_api.py` | `blog_deployer` |
| `image_stock.py` | `generate_pin_content`, `regen_content`, `backfill_hero_images` |
| `image_gen.py` | `generate_pin_content`, `regen_content` |

### Highest-Risk Nodes (change cascades)

1. **`sheets_api.py`** — Used by 7+ scripts. Any column index change breaks multiple workflows.
2. **`content-log.jsonl`** — Written by 3 modules, read by 3 modules, with schema inconsistency.
3. **`claude_api.py`** — Used by 6 scripts. Model ID change or prompt format change affects everything.
4. **`slack_notify.py`** — Used by 8+ scripts but low risk (notification-only, graceful degradation).
5. **`pin-generation-results.json`** — Written by 1 module, read by 3+ modules with no schema validation.

---

## Phase 5: Refactoring Plan

### Tier 0: Data (Establish single source of truth — zero logic change)

#### T0-1: Unify content-log.jsonl schema
- **What:** Define a canonical schema for content-log.jsonl entries. Ensure both `blog_deployer._append_to_content_log()` and `post_pins.append_to_content_log()` write identical field sets.
- **Why:** Two writers produce entries with different fields, causing downstream readers to handle missing fields.
- **Files:** `src/blog_deployer.py`, `src/post_pins.py`
- **Verify:** Both functions produce entries with the same keys. `pull_analytics.py` and `weekly_analysis.py` continue to work.

#### T0-2: Create shared content_log module
- **What:** Extract content log read/write operations into `src/content_log.py`. Single `append_entry()`, `load_entries()`, `is_pin_posted()` function set.
- **Why:** Eliminates duplicate write functions and provides consistent schema.
- **Files:** New `src/content_log.py`, modify `src/blog_deployer.py`, `src/post_pins.py`, `src/weekly_analysis.py`, `src/pull_analytics.py`
- **Verify:** All existing tests pass. Content log entries match unified schema.

#### T0-3: Consolidate image hosting (Drive vs GCS)
- **What:** Determine whether Drive or GCS is the canonical image host. Remove the unused one. Update all callers.
- **Why:** Two systems serving the same purpose. Maintaining both wastes API calls and creates confusion.
- **Files:** `src/apis/drive_api.py` (potentially remove), `src/apis/gcs_api.py`, `src/publish_content_queue.py`
- **Verify:** Sheets =IMAGE() formulas still render. No broken image URLs.

#### T0-4: Single-load pin-generation-results.json in blog_deployer
- **What:** Load `pin-generation-results.json` once at the start of deployment and pass the data to all methods that need it.
- **Why:** Currently loaded 3 separate times in a single deployment flow.
- **Files:** `src/blog_deployer.py`
- **Verify:** Deployment still works correctly. AI image swaps still function.

### Tier 1: Safety (Extract hardcoded values, add error handling — zero behavior change)

#### T1-1: Create central config module
- **What:** Create `src/config.py` with all hardcoded values: URLs, model IDs, thresholds, timeouts, path constants, Sheet column indices, tab names.
- **Why:** 27+ hardcoded values across 15+ files (H1-H27). Changes require multi-file edits.
- **Files:** New `src/config.py`, all files with hardcoded values.
- **Verify:** All scripts still work identically. Config values match originals.

#### T1-2: Extract shared MIME detection utility
- **What:** Create `src/utils.py` with `detect_mime_type(file_path_or_bytes)` function.
- **Why:** MIME detection duplicated in 3 files (DU1).
- **Files:** New `src/utils.py`, modify `src/apis/pinterest_api.py`, `src/apis/gcs_api.py`, `src/apis/drive_api.py`
- **Verify:** All image uploads still detect correct MIME type.

#### T1-3: Add schema validation for pin-generation-results.json
- **What:** Add a validation function that checks pin-generation-results.json structure before use.
- **Why:** Multiple files assume specific keys exist without validation (F3).
- **Files:** `src/blog_deployer.py`, potentially new `src/schemas.py`
- **Verify:** Existing valid data passes. Invalid data raises clear errors.

#### T1-4: Make Sheets _clear_and_write() atomic
- **What:** Write new data first (to a temp range), then clear old data, then copy. Or at minimum, catch write failures and log a recovery path.
- **Why:** Current implementation clears then writes — data loss if write fails (E3).
- **Files:** `src/apis/sheets_api.py`
- **Verify:** Tab updates still work. Simulated write failure doesn't lose data.

#### T1-5: Add content-log.jsonl index for idempotency checks
- **What:** Load pin IDs into a set at startup instead of scanning the file line by line for each check.
- **Why:** `is_already_posted()` is O(n) per check and will degrade (E4).
- **Files:** `src/post_pins.py`
- **Verify:** Idempotency still works. Performance improves for large logs.

### Tier 2: Structure (Consolidate duplication, break apart god files)

#### T2-1: Consolidate blog post generation entry points
- **What:** Merge `generate_blog_posts()` and `generate_all_blog_posts()` into one function with an optional `plan` parameter.
- **Why:** 60% duplicated logic (DU3).
- **Files:** `src/generate_blog_posts.py`
- **Verify:** Both workflows still work.

#### T2-2: Consolidate blog generator type methods
- **What:** Replace four `generate_*_post()` methods with a single `_generate_post()` that takes `post_type` as parameter.
- **Why:** Methods are structurally identical (DU4).
- **Files:** `src/blog_generator.py`
- **Verify:** All four post types still generate correctly.

#### T2-3: Consolidate GitHub commit methods
- **What:** Merge `commit_blog_post()`, `commit_blog_posts()`, and `commit_multiple_posts()` into one `commit_posts()` method.
- **Why:** Three overlapping methods (DU5). Remove dead `_create_or_update_file()`.
- **Files:** `src/apis/github_api.py`
- **Verify:** Blog deployment still works.

#### T2-4: Consolidate blog deployer deployment modes
- **What:** Extract shared deployment logic into helper methods. The three modes become thin orchestrators.
- **Why:** 60%+ code duplication across three methods (DU9).
- **Files:** `src/blog_deployer.py`
- **Verify:** All three deployment modes still work.

#### T2-5: Remove trivial aliases
- **What:** Remove `get_boards()`, `read_plan_status()`, `read_content_statuses()`, `update_dashboard_metrics()`, `upload_single_image()`. Update all callers.
- **Why:** Trivial wrappers that add no value (DU6, DU7, DU8).
- **Files:** `src/apis/sheets_api.py`, `src/apis/gcs_api.py`, `src/apis/pinterest_api.py`, callers.
- **Verify:** All callers updated. No broken imports.

#### T2-6: Split sheets_api.py into per-tab modules
- **What:** Create `sheets_weekly_review.py`, `sheets_content_queue.py`, `sheets_post_log.py`, `sheets_dashboard.py` or use inner classes.
- **Why:** 944-line god file (S1).
- **Files:** `src/apis/sheets_api.py` → multiple files
- **Verify:** All Sheet operations still work.

#### T2-7: Extract content memory summary to its own module
- **What:** Move `generate_content_memory_summary()` (220 lines) from `weekly_analysis.py` to `src/content_memory.py`.
- **Why:** It's a standalone function with no coupling to the analysis logic.
- **Files:** `src/weekly_analysis.py`, new `src/content_memory.py`
- **Verify:** Memory summary generation still works. Weekly plan still loads it.

### Tier 3: Robustness (Validation, logging, edge cases)

#### T3-1: Replace custom YAML parser with PyYAML
- **What:** Use `pyyaml` or `ruamel.yaml` in `blog_generator._extract_frontmatter()`.
- **Why:** Custom parser (F5) will break on edge cases.
- **Files:** `src/blog_generator.py`, `requirements.txt`
- **Verify:** All existing MDX frontmatter parses correctly.

#### T3-2: Add Sheet column validation
- **What:** On first read, verify that Sheet headers match expected column order. Raise clear error if mismatched.
- **Why:** Column index hardcoding (F1) causes silent failures on layout changes.
- **Files:** `src/apis/sheets_api.py`
- **Verify:** Correct layout passes. Incorrect layout raises descriptive error.

#### T3-3: Fix image_gen.py output directory inconsistency
- **What:** Change `data/generated_pins` (line 158) to `data/generated/pins` to match the rest of the codebase.
- **Why:** Path mismatch (C2) — generated images may be written to wrong directory.
- **Files:** `src/apis/image_gen.py`
- **Verify:** AI-generated images saved to correct directory.

#### T3-4: Fix pin_assembler JPEG-as-PNG naming
- **What:** When converting oversized PNGs to JPEG, use the `.jpg` extension and update downstream references.
- **Why:** Currently renames `.jpg` to `.png` (S4), creating files with wrong extension for their format.
- **Files:** `src/pin_assembler.py`, downstream callers
- **Verify:** Optimized images have correct extensions. MIME detection still works.

#### T3-5: Add content-log.jsonl rotation/archival
- **What:** Implement log rotation (e.g., archive entries older than 6 months to a separate file).
- **Why:** File grows indefinitely. `is_already_posted()` and `load_content_log()` scan the entire file.
- **Files:** New utility or cron job
- **Verify:** Old data archived. Current operations unaffected.

#### T3-6: Fix stale comment in post_pins.py
- **What:** Line 300 says "random(0, 5400)" but actual value is `INITIAL_JITTER_MAX = 900` (0-15 min, not 0-90 min).
- **Why:** Misleading documentation.
- **Files:** `src/post_pins.py` line 300
- **Verify:** Comment matches code.
