# Code Refactor Analysis

**Date:** 2026-02-27
**Scope:** All Python sources (`src/`, `src/apis/`), GitHub Actions workflows, strategy files, prompt templates
**Purpose:** Identify refactor opportunities across 8 analysis areas with file:line references and severity ratings

Severity scale:
- **CRITICAL** -- Actively causes bugs or will break under foreseeable changes
- **HIGH** -- Significant maintenance burden, likely to cause issues during feature work
- **MEDIUM** -- Code smell or duplication that increases cognitive load
- **LOW** -- Minor improvement, nice-to-have cleanup

---

## 1. HARDCODED VALUES

Values that should be in configuration files, environment variables, or centralized constants.

### 1.1 Hardcoded URLs (HIGH)

| Location | Value | Issue |
|----------|-------|-------|
| `src/generate_pin_content.py:40` | `BLOG_BASE_URL = "https://goslated.com/blog"` | Duplicated in blog_deployer.py |
| `src/blog_deployer.py:40` | `BLOG_BASE_URL = "https://goslated.com/blog"` | Duplicated in generate_pin_content.py |
| `src/apis/github_api.py:43` | `GOSLATED_BASE_URL = "https://goslated.com"` | Third place the base domain appears |
| `src/token_manager.py:52` | `PINTEREST_OAUTH_URL = "https://api.pinterest.com/oauth/"` | Should be alongside BASE_URL constants in pinterest_api.py |
| `src/token_manager.py:53` | `REDIRECT_URI = "http://localhost:8085/"` | Non-configurable OAuth redirect |
| `src/apis/pinterest_api.py:39-40` | `BASE_URL_PRODUCTION` / `BASE_URL_SANDBOX` | OK as constants but should be central |

**Recommendation:** Create a `src/config.py` (or `src/shared/paths.py` per the architecture plan) that centralizes all external URLs. The `BLOG_BASE_URL` duplication is the highest-priority fix -- if the domain ever changes, two files must be updated in sync.

### 1.2 Hardcoded Model Names and Cost Rates (MEDIUM)

| Location | Value | Issue |
|----------|-------|-------|
| `src/apis/claude_api.py:41-43` | `MODEL_ROUTINE`, `MODEL_DEEP`, `MODEL_HAIKU` | Model IDs hardcoded; changing models requires editing this file |
| `src/apis/claude_api.py:46-50` | `COST_PER_MTK` dict | Cost rates hardcoded; outdated the moment Anthropic changes pricing |
| `src/apis/image_gen.py:38-41` | `COST_PER_IMAGE` dict | Same issue for image generation costs |
| `src/apis/image_gen.py:288` | `"gpt-image-1.5"` | OpenAI model name hardcoded in method body |
| `src/apis/image_gen.py:337` | `"black-forest-labs/flux-pro"` | Replicate model name hardcoded in method body |
| `src/apis/claude_api.py` (GPT5 mini method) | OpenAI URL + model name hardcoded | Inside `_call_openai_gpt5_mini()` |

**Recommendation:** Move model names to module-level constants (already done for Claude but not for image_gen models). Cost rates are inherently approximate -- consider loading from a JSON config file or at minimum documenting that they need periodic updates.

### 1.3 Hardcoded Timing and Threshold Constants (LOW)

| Location | Value | Issue |
|----------|-------|-------|
| `src/token_manager.py:54` | `REFRESH_THRESHOLD_DAYS = 5` | Reasonable as constant, but should be documented |
| `src/post_pins.py:66-68` | `INITIAL_JITTER_MAX = 900`, `INTER_PIN_JITTER_MIN/MAX` | Anti-bot jitter windows |
| `src/post_pins.py:71` | `MAX_PIN_FAILURES = 3` | Failure threshold |
| `src/blog_deployer.py:43` | `DEPLOY_VERIFY_TIMEOUT = 180` | 3 min timeout for Vercel deploy verification |
| `src/generate_pin_content.py:43` | `COPY_BATCH_SIZE = 6` | Batch size for Claude copy generation |
| `src/pull_analytics.py:42` | `MAX_LOOKBACK_DAYS = 90` | Analytics lookback window |

**Recommendation:** These are fine as module-level constants. No immediate action needed, but they could move to a shared config if the multi-channel restructure happens.

### 1.4 Hardcoded Column Indices in Sheets API (CRITICAL)

| Location | Value | Issue |
|----------|-------|-------|
| `src/apis/sheets_api.py:46-59` | Content Queue column indices (A-N) | 14 column positions as magic numbers |
| `src/apis/sheets_api.py:61-69` | Post Log column indices (A-I) | 9 column positions as magic numbers |
| `src/apis/sheets_api.py:40-43` | Tab names: `TAB_WEEKLY_REVIEW`, etc. | These are fine as named constants |
| `src/backfill_hero_images.py:33-37` | Duplicated column indices from sheets_api.py | Copy-pasted, will drift |

**Recommendation:** The column indices are the most fragile pattern in the codebase. If anyone reorders columns in the Google Sheet, multiple scripts break silently (data goes to wrong columns). These should be either (a) defined as a single dict in sheets_api.py and imported everywhere, or (b) the Sheet should use named ranges. See also Section 8 (Fragile Patterns).

### 1.5 Hardcoded Pin Dimensions and Limits (LOW)

| Location | Value | Issue |
|----------|-------|-------|
| `src/pin_assembler.py:47-48` | `PIN_WIDTH = 1000`, `PIN_HEIGHT = 1500` | Standard Pinterest 2:3 ratio |
| `src/pin_assembler.py:51` | `MAX_PNG_SIZE = 500 * 1024` | 500KB target |
| `src/apis/image_gen.py:44` | `MIN_IMAGE_SIZE = 10_000` | 10KB minimum for valid images |

**Recommendation:** Fine as module-level constants. Pinterest's spec is unlikely to change.

---

## 2. DUPLICATION

Code that is repeated in multiple locations, creating maintenance risk.

### 2.1 MIME Detection via Magic Bytes (HIGH)

Three separate implementations of the same logic:

| Location | Method |
|----------|--------|
| `src/apis/drive_api.py:190-197` | `_detect_mime_type()` -- reads first 16 bytes, checks magic bytes |
| `src/apis/gcs_api.py:133-142` | `_detect_mime_type()` -- nearly identical implementation |
| `src/apis/pinterest_api.py:131-139` | `_detect_content_type()` -- same logic, different function name |

All three check the same magic byte patterns (JPEG `\xff\xd8\xff`, PNG `\x89PNG`, WebP `RIFF`/`WEBP`, GIF `GIF8`). A fourth variant exists in `src/pin_assembler.py:105-112` using file extension mapping instead of magic bytes.

**Recommendation:** Extract to a shared utility: `src/utils.py` or `src/shared/image_utils.py`. A single `detect_mime_type(data: bytes) -> str` function replaces all three. The extension-based mapping in pin_assembler.py serves a different purpose (local files with known extensions) and can stay.

### 2.2 PROJECT_ROOT / DATA_DIR / STRATEGY_DIR Defined Independently (HIGH)

Every major module independently computes its path constants using `Path(__file__).parent.parent`:

| Location | Constants Defined |
|----------|-------------------|
| `src/generate_weekly_plan.py:49-52` | `PROJECT_ROOT`, `STRATEGY_DIR`, `ANALYSIS_DIR`, `DATA_DIR` |
| `src/generate_blog_posts.py:36-39` | `PROJECT_ROOT`, `OUTPUT_DIR`, `DATA_DIR`, `STRATEGY_DIR` |
| `src/generate_pin_content.py:36-38` | `PROJECT_ROOT`, `DATA_DIR`, `STRATEGY_DIR` |
| `src/weekly_analysis.py:51-57` | `PROJECT_ROOT`, `ANALYSIS_DIR`, `DATA_DIR`, `STRATEGY_DIR`, `PROMPTS_DIR` |
| `src/monthly_review.py:53-59` | Same 5 constants |
| `src/pull_analytics.py:36-39` | `PROJECT_ROOT`, `DATA_DIR`, `CONTENT_LOG_PATH`, `ANALYTICS_DIR` |
| `src/blog_generator.py:37-38` | `PROJECT_ROOT`, `STRATEGY_DIR` |
| `src/blog_deployer.py:37-38` | `PROJECT_ROOT`, `DATA_DIR` |
| `src/publish_content_queue.py:38-41` | `PROJECT_ROOT`, `DATA_DIR`, `STRATEGY_DIR` |
| `src/regen_content.py:42-44` | `PROJECT_ROOT`, `DATA_DIR`, `STRATEGY_DIR` |
| `src/pin_assembler.py:37-41` | `_PROJECT_ROOT`, `TEMPLATES_DIR`, `SHARED_DIR` |
| `src/setup_boards.py:29-31` | Uses `os.path` instead of `pathlib` (inconsistent) |

That is 12 independent computations of `PROJECT_ROOT` using relative `Path(__file__)` resolution. If a file moves (e.g., during the planned multi-channel restructure), its `Path(__file__).parent.parent` breaks silently.

**Recommendation:** Create `src/paths.py` with a single canonical definition. All modules import from there. The architecture plan already calls for `src/shared/paths.py` -- this should be the first step of any restructure.

### 2.3 _load_plan() Duplication (MEDIUM)

| Location | Function |
|----------|----------|
| `src/generate_blog_posts.py` | `_load_plan()` -- finds latest `weekly-plan-*.json`, parses it |
| `src/generate_pin_content.py` | `_load_plan()` -- nearly identical logic |
| `src/regen_weekly_plan.py:46-70` | `find_latest_plan()` + `load_plan()` -- same pattern, separate functions |

**Recommendation:** Extract to a shared utility, e.g., `src/plan_utils.py` with `find_latest_plan() -> Path` and `load_plan(path) -> dict`.

### 2.4 _load_brand_voice() Duplication (MEDIUM)

| Location | Function |
|----------|----------|
| `src/generate_pin_content.py` | `_load_brand_voice()` -- reads `strategy/brand-voice.md` |
| `src/blog_generator.py` | `_load_brand_voice()` -- identical implementation |

**Recommendation:** Move to shared utility or have both import from `generate_weekly_plan.load_strategy_context()`.

### 2.5 Content Log Read/Write Duplication (MEDIUM)

| Location | Function |
|----------|----------|
| `src/pull_analytics.py` | `load_content_log()`, `save_content_log()` -- canonical implementations |
| `src/post_pins.py` | Inline content log append logic (reads JSONL, appends entry, writes) |
| `src/generate_weekly_plan.py:1281-1307` | `_load_content_log()` -- private re-implementation |
| `src/blog_deployer.py` | Content log append logic |

**Recommendation:** `pull_analytics.py` already has the canonical `load_content_log()` / `save_content_log()`. Other modules should import from there instead of re-implementing. `generate_weekly_plan._load_content_log()` is particularly wasteful since it's identical to `pull_analytics.load_content_log()`.

### 2.6 generate_content_memory_summary() Duplication (HIGH)

| Location | Lines |
|----------|-------|
| `src/generate_weekly_plan.py:522-872` | 350-line implementation (7 sections) |
| `src/weekly_analysis.py` | Separate implementation |

The architecture plan (Phase 2) already identifies this as a key extraction target. Both versions produce similar but slightly different output. This is the single largest duplication in the codebase.

**Recommendation:** Consolidate into `src/shared/content_memory.py` as the architecture plan specifies.

### 2.7 Workflow Boilerplate Duplication (MEDIUM)

All 11 GitHub Actions workflows repeat the same patterns:
- Python setup steps (checkout, setup-python, install deps) -- identical across all workflows
- Failure notification step -- identical `python -c` inline script in every workflow
- Git commit step -- similar `git config` + `git add` + `git commit` pattern in 8 workflows
- Environment variable declarations -- large blocks of secrets repeated across workflows

| Pattern | Occurrences |
|---------|-------------|
| Python setup (3 steps) | 11 workflows |
| Failure notification step | 11 workflows |
| Git commit-and-push step | 8 workflows |
| `pinterest-pipeline` concurrency group | 9 workflows |

**Recommendation:** Extract reusable composite actions: `actions/setup-pipeline`, `actions/commit-data`, `actions/notify-failure`. This would reduce each workflow from ~40-60 lines to ~15-20 lines.

---

## 3. COUPLING

Dependencies between modules that make changes risky or prevent independent testing.

### 3.1 regen_content.py Imports Private Functions (CRITICAL)

`src/regen_content.py` imports multiple private (underscore-prefixed) functions from `src/generate_pin_content.py`:

```python
from src.generate_pin_content import (
    _source_ai_image,       # private
    _load_brand_voice,      # private
    _load_keyword_targets,  # private
    build_template_context, # public
)
```

File: `src/regen_content.py:21-25` (approximate)

Private functions are not part of a module's public API and can change without notice. If `generate_pin_content.py` renames or refactors `_source_ai_image()`, `regen_content.py` breaks.

**Recommendation:** Either (a) make these functions public by removing the underscore prefix, or (b) extract them to a shared module that both files import from.

### 3.2 regen_weekly_plan.py Imports from generate_weekly_plan.py (MEDIUM)

```python
from src.generate_weekly_plan import (
    identify_replaceable_posts,
    splice_replacements,
    load_content_memory,
    DATA_DIR,
)
```

File: `src/regen_weekly_plan.py:36-41`

This is a more reasonable coupling (importing public functions), but it means `generate_weekly_plan.py` is both an orchestrator script AND a library of reusable planning utilities. This dual role makes the file harder to refactor.

**Recommendation:** Extract `identify_replaceable_posts()`, `splice_replacements()`, and related validation functions into a `src/plan_utils.py` module. The orchestrator (`generate_weekly_plan.py`) and the regen script both import from the utility module.

### 3.3 sheets_api.py Direct Google API Calls in Orchestrators (MEDIUM)

`src/regen_weekly_plan.py:268-273` makes a raw Google Sheets API call instead of using the SheetsAPI wrapper:

```python
sheets.sheets.values().update(
    spreadsheetId=sheets.sheet_id,
    range=f"'Weekly Review'!B3",
    valueInputOption="RAW",
    body={"values": [[plan_status]]},
).execute()
```

This bypasses the abstraction layer, creating a hidden dependency on the internal structure of SheetsAPI.

**Recommendation:** Add a method to SheetsAPI (e.g., `write_cell(tab, cell, value)`) and use that instead.

### 3.4 Circular-ish Import Risk: image_cleaner in pin_assembler (LOW)

`src/pin_assembler.py:508` and `src/pin_assembler.py:717` both do:
```python
from src.image_cleaner import clean_image
```

These are inline imports (inside methods), which avoids actual circular import issues but is unusual. The pattern suggests the author was aware of potential import ordering problems.

**Recommendation:** Move the import to the top of the file. There is no actual circular dependency -- `image_cleaner.py` does not import from `pin_assembler.py`.

### 3.5 SheetsAPI Tightly Coupled to Sheet Layout (HIGH)

`src/apis/sheets_api.py` has hardcoded tab names, column indices, and range strings (e.g., `'Weekly Review'!B3`). Any change to the Google Sheet layout requires code changes.

This is coupling to an external system's structure, which the code has no control over. A user editing the Sheet could break the pipeline.

**Recommendation:** (a) Define the Sheet schema in a single configuration block at the top of sheets_api.py (already partially done with tab name constants). (b) Add validation that checks expected column headers before writing. (c) Consider using named ranges in the Sheet, which decouple from column positions.

---

## 4. ERROR HANDLING

Inconsistent or inadequate error handling patterns.

### 4.1 Inconsistent Failure Modes (MEDIUM)

The codebase has three different error handling philosophies:

1. **Raise immediately** -- `token_manager.py`, `pin_assembler.py` raise custom exceptions
2. **Log and return None/empty** -- `image_cleaner.py:99-101` catches all exceptions, logs warning, returns input path
3. **Log and continue** -- many orchestrator scripts catch exceptions in notification steps and continue

There is no documented convention for when to use which pattern.

| File | Pattern | Risk |
|------|---------|------|
| `src/image_cleaner.py:99-101` | Catches `Exception`, returns input path silently | Corrupted images could be uploaded without metadata stripping |
| `src/apis/gcs_api.py` | Returns None when credentials missing | Callers may not check for None, causing AttributeError downstream |
| `src/blog_deployer.py` | Mixed: some methods raise, some return dicts with error fields | Inconsistent caller expectations |
| `src/generate_weekly_plan.py:336-337` | Catches Sheet write failure, logs, continues | Plan saved locally but Sheet out of sync -- user has no plan to review |

**Recommendation:** Establish a convention:
- API wrappers (apis/) should raise on failure -- callers decide how to handle
- Orchestrator scripts (top-level) should catch and report
- "Best effort" operations (Slack notifications, analytics writes) can log-and-continue
- Document this in CLAUDE.md or a CONTRIBUTING.md

### 4.2 Bare Exception Catches (MEDIUM)

Several places catch `Exception` broadly:

| Location | Issue |
|----------|-------|
| `src/image_cleaner.py:99` | `except Exception as e` -- hides PIL errors, file permission errors, etc. |
| `src/regen_weekly_plan.py:252-253` | `except Exception: plan_status = "pending_review"` -- silently defaults on any error |
| `src/regen_weekly_plan.py:256-257` | `except Exception: deploy_status = "pending_review"` -- same pattern |
| `src/pin_assembler.py:598-599` | `except ImportError` then `except Exception` -- optimization failure silently swallowed |

**Recommendation:** Narrow exception types where possible. For `image_cleaner.py`, catch `PIL.UnidentifiedImageError`, `OSError`, `ValueError` specifically.

### 4.3 No Retry Logic in Critical API Calls (MEDIUM)

- `src/apis/claude_api.py` has no retry logic for transient Anthropic API errors (rate limits, 500s)
- `src/apis/pinterest_api.py` has `MAX_RETRIES = 3` with backoff -- good pattern
- `src/apis/image_gen.py` has retry logic for image generation -- good pattern
- `src/apis/sheets_api.py` has no retry logic

**Recommendation:** Add retry with exponential backoff to `claude_api.py` and `sheets_api.py`. The Anthropic SDK may handle some of this internally, but rate limit (429) handling should be explicit.

---

## 5. CONFIGURATION

How the application manages configuration, environment variables, and settings.

### 5.1 No Centralized Configuration (HIGH)

The codebase has no configuration management layer. Settings are spread across:
- Environment variables (read via `os.environ` or `os.getenv` in 8+ files)
- Module-level constants (in every Python file)
- Strategy JSON files (in `strategy/`)
- Hardcoded values in method bodies

There is no single place to see "what does this application need to run?"

**Recommendation:** The architecture plan's `src/shared/paths.py` is a start. Consider a broader `src/config.py` that:
1. Centralizes all env var reads with validation and defaults
2. Exposes typed configuration objects (e.g., `PinterestConfig`, `ClaudeConfig`)
3. Fails fast at startup if required env vars are missing

### 5.2 setup_boards.py Uses os.path Instead of pathlib (LOW)

`src/setup_boards.py:29-31` uses `os.path.join` and `os.path.dirname` while every other file in the codebase uses `pathlib.Path`.

**Recommendation:** Convert to `pathlib.Path` for consistency.

### 5.3 Environment Variable Access Scattered (MEDIUM)

Direct `os.environ` / `os.getenv` calls are scattered across many files:

| File | Variables Read |
|------|---------------|
| `src/apis/claude_api.py` | `ANTHROPIC_API_KEY` |
| `src/apis/pinterest_api.py` | `PINTEREST_ACCESS_TOKEN`, `PINTEREST_ENVIRONMENT`, etc. |
| `src/apis/sheets_api.py` | `GOOGLE_SHEETS_CREDENTIALS_JSON`, `GOOGLE_SHEET_ID`, `GOOGLE_SHEET_URL` |
| `src/apis/github_api.py` | `GOSLATED_GITHUB_TOKEN`, `GOSLATED_REPO` |
| `src/apis/gcs_api.py` | `GCS_BUCKET_NAME`, `GCS_CREDENTIALS_JSON` |
| `src/apis/drive_api.py` | `GOOGLE_SHEETS_CREDENTIALS_JSON` (reuses Sheets creds) |
| `src/apis/image_gen.py` | `OPENAI_API_KEY`, `REPLICATE_API_TOKEN` |
| `src/apis/slack_notify.py` | `SLACK_WEBHOOK_URL` |
| `src/token_manager.py` | `PINTEREST_APP_ID`, `PINTEREST_APP_SECRET`, etc. |

If an env var name changes, you must grep the entire codebase. No validation happens at startup -- missing vars fail at first use, potentially mid-workflow.

**Recommendation:** Centralize env var reads in a config module with early validation.

---

## 6. TESTABILITY

Patterns that make unit testing difficult.

### 6.1 No Dependency Injection (HIGH)

API clients are instantiated inside orchestrator functions with no way to override:

```python
# src/generate_weekly_plan.py:139
claude = ClaudeAPI()

# src/regen_weekly_plan.py:137
sheets = SheetsAPI()
```

Every function that calls an API creates its own client instance. This makes it impossible to test these functions without mocking at the import level.

**Recommendation:** Pass API clients as parameters with defaults:
```python
def generate_plan(claude: ClaudeAPI = None, sheets: SheetsAPI = None):
    claude = claude or ClaudeAPI()
    sheets = sheets or SheetsAPI()
```

### 6.2 File I/O Mixed with Business Logic (HIGH)

Many functions interleave file reads, business logic, and API calls:

| Function | File I/O + Logic Mixed |
|----------|------------------------|
| `generate_content_memory_summary()` | Reads JSONL + JSON files, computes aggregates, writes markdown -- all in one 350-line function |
| `validate_plan()` | Loads negative keywords from disk mid-validation if not provided |
| `_build_keyword_performance_data()` | Calls `_load_content_log()` internally instead of receiving data as parameter |
| `blog_generator.py` custom YAML parser | Parses YAML, validates frontmatter, generates MDX -- all coupled |

**Recommendation:** Separate data loading from processing. Pass data as function parameters so business logic can be tested with synthetic data.

### 6.3 Module-Level Side Effects (LOW)

| File | Side Effect |
|------|-------------|
| `src/setup_boards.py` | Calls `logging.basicConfig()` at module level (line ~15) |
| `src/backfill_hero_images.py` | Imports `dotenv` at module level |

**Recommendation:** Move `logging.basicConfig()` to `if __name__ == "__main__"` blocks only.

---

## 7. COMPLEXITY HOTSPOTS

Functions or files that are disproportionately complex and would benefit from decomposition.

### 7.1 generate_weekly_plan.py (1395 lines) -- CRITICAL

This is the largest and most complex file in the codebase. It serves as:
1. Orchestrator for weekly planning (`generate_plan()` -- 280 lines including retry loop)
2. Strategy context loader (`load_strategy_context()`)
3. Content memory generator (`generate_content_memory_summary()` -- 350 lines)
4. Plan validator (`validate_plan()` -- 240 lines with 8 constraint checks)
5. Replacement identifier and splicer (`identify_replaceable_posts()`, `splice_replacements()`)
6. Content log loader (`_load_content_log()`)
7. Keyword performance builder (`_build_keyword_performance_data()`)
8. Helper utilities (`_parse_date()`, `_get_entry_date()`, `_extract_recent_topics()`)

The architecture plan (Phase 3) correctly identifies this as the hardest file to split. The validation logic alone has 8 constraint checks at 30 lines each. The retry loop in `generate_plan()` has 3 different code paths (structural regen, too-many-replacements regen, surgical replacement) with duplicated reprompt construction.

**Recommendation:** Split into at minimum 3 files:
- `src/plan_validator.py` -- `validate_plan()`, constraint constants, violation helpers
- `src/content_memory.py` -- `generate_content_memory_summary()` and its helpers
- `src/generate_weekly_plan.py` -- orchestration only (calls the above)

### 7.2 sheets_api.py (1018 lines) -- HIGH

The Sheets API wrapper is the second-largest file. It handles 4 different Sheet tabs with different column layouts, formatting, and validation. Each tab's read/write methods are 50-100 lines.

**Recommendation:** Consider splitting into per-tab helper classes or at least grouping methods by tab with clear section markers.

### 7.3 claude_api.py (955 lines) -- MEDIUM

Large file but well-organized around individual API call methods. Each method loads a prompt template, fills placeholders, calls Claude, and parses the response.

The main complexity issue is that each method has its own JSON parsing and retry logic. A shared `_call_and_parse_json()` helper could reduce this.

### 7.4 monthly_review.py (865 lines) -- MEDIUM

Long file with multiple analysis helper functions. Most functions are straightforward data aggregation, but the file could be split into `monthly_analysis.py` (computation) and `monthly_review.py` (orchestration + Sheet writing).

### 7.5 regen_content.py (822 lines) -- MEDIUM

The `_regen_item()` function is particularly long with multiple code paths depending on what is being regenerated (image only, copy only, both). The image download fallback logic (GCS -> Drive -> original URL) adds additional branching.

**Recommendation:** Extract the image sourcing fallback chain into a dedicated function.

### 7.6 blog_generator.py Custom YAML Parser (MEDIUM)

`src/blog_generator.py:543-628` contains an 85-line custom YAML parser for MDX frontmatter. The rest of the codebase (`publish_content_queue.py`) uses `yaml.safe_load` for the same task.

**Recommendation:** Replace the custom parser with `yaml.safe_load` (already a dependency per `publish_content_queue.py`'s usage). The custom parser exists likely because of edge cases with MDX frontmatter, but these should be documented and handled rather than writing a bespoke parser.

### 7.7 generate_plan() Retry Loop (MEDIUM)

`src/generate_weekly_plan.py:155-319` -- The retry loop has 3 different code paths that all do similar things (build reprompt context, call Claude, re-validate). The reprompt construction is duplicated in the structural and too-many-replacements branches (lines 172-178, 218-222, 200-203).

**Recommendation:** Extract a `_build_reprompt_context(violations)` helper and reduce the 3 code paths to 2 (full regen vs. surgical replacement).

---

## 8. FRAGILE PATTERNS

Code that works now but will break easily under foreseeable changes.

### 8.1 Google Sheets Column Indices (CRITICAL)

The most fragile pattern in the entire codebase. `src/apis/sheets_api.py:46-69` defines column positions as integer constants:

```python
CQ_COL_STATUS = 0      # Column A
CQ_COL_PIN_ID = 1      # Column B
CQ_COL_POST_ID = 2     # Column C
# ... 11 more
```

If a user inserts a column in the Google Sheet, every index after that position is wrong. Data writes to wrong columns. The pipeline silently corrupts Sheet data.

There is no validation that column headers match expected positions.

`src/backfill_hero_images.py:33-37` duplicates a subset of these indices, compounding the risk.

**Recommendation:**
1. Add a header validation step: on first access to a tab, read row 1 and verify column names match expected positions
2. Consider a column-name-based approach: map column names to positions dynamically at runtime
3. At minimum, consolidate all column index definitions into `sheets_api.py` and have `backfill_hero_images.py` import from there

### 8.2 Hardcoded Sheet Cell References (HIGH)

Throughout the codebase, specific cells are referenced by hard-coded A1 notation:

| Location | Cell Reference | Purpose |
|----------|---------------|---------|
| `src/regen_weekly_plan.py:269` | `'Weekly Review'!B3` | Plan approval status |
| Various in `sheets_api.py` | `B3`, `B4`, `B5` | Trigger cells for plan approval, deploy, regen |
| `src/apis/sheets_api.py` | Multiple `!A1:Z` range patterns | Full-tab reads |

These cell references are the "contract" between the Google Sheet and the Python pipeline. If the Sheet layout changes, there is no validation or error that explains which cell is now wrong.

**Recommendation:** Define all cell references as named constants in `sheets_api.py` with comments explaining their purpose.

### 8.3 Pin ID Parsing via String Splitting (MEDIUM)

`src/generate_weekly_plan.py:921-922`:
```python
if "'" in msg:
    pin_id = msg.split("'")[1]
```

This extracts a pin ID from a violation message string by splitting on single quotes. If the message format changes, the ID extraction fails silently.

**Recommendation:** Add the `pin_id` as a structured field in the violation dict instead of parsing it from the message string.

### 8.4 JSONL Content Log as Shared Mutable State (MEDIUM)

`data/content-log.jsonl` is read and written by multiple scripts (`pull_analytics.py`, `post_pins.py`, `blog_deployer.py`, `generate_weekly_plan.py`). There is no file locking or atomic write pattern.

If two GitHub Actions jobs run concurrently and both modify `content-log.jsonl`, one write will overwrite the other. The `concurrency` groups in workflows mitigate this, but `pinterest-posting` and `pinterest-pipeline` are separate concurrency groups -- a posting job and a content generation job could theoretically collide.

**Recommendation:** Use `fcntl`/file locking or write to the file using append mode only (JSONL is append-friendly). Alternatively, read-modify-write with a temp file and atomic rename.

### 8.5 Variant Activation via Line-by-Line HTML Parsing (MEDIUM)

`src/pin_assembler.py:261-291` -- `_activate_variant()` parses HTML line by line, counting div opens and closes to skip non-active variant blocks. This is fragile if:
- A div tag spans multiple lines
- A self-closing div or non-standard HTML is used
- The `data-variant` / `pin-canvas` class pattern changes

**Recommendation:** Use an HTML parser (e.g., `html.parser` from stdlib or `beautifulsoup4`) instead of line-by-line string manipulation. Or ensure templates are validated against this pattern as part of a template test.

### 8.6 Workflow Inline Python (LOW)

Several workflows contain inline Python scripts in `run:` blocks:

| Workflow | Lines of Inline Python |
|----------|----------------------|
| `promote-and-schedule.yml:68-96` | 28-line pin schedule redating script |
| `weekly-review.yml:58` | Single-line content memory generation |
| `monthly-review.yml:76` | Single-line analytics call |
| All workflows (failure step) | 4-line Slack notification |

The 28-line inline script in `promote-and-schedule.yml` is particularly problematic -- it has no tests, no linting, and no syntax highlighting in the YAML editor.

**Recommendation:** Move the pin schedule redating logic to a proper Python module (e.g., `src/redate_schedule.py`). Keep single-line invocations as-is.

---

## Summary

### By Severity

| Severity | Count | Key Items |
|----------|-------|-----------|
| CRITICAL | 4 | Sheet column indices, private function imports, generate_weekly_plan.py complexity, Sheet column duplication in backfill |
| HIGH | 9 | URL duplication, MIME detection duplication, path constants duplication, content memory duplication, Sheet coupling, no DI, no centralized config, Sheet cell references, file I/O mixed with logic |
| MEDIUM | 18 | Model/cost hardcoding, plan loader duplication, brand voice duplication, content log duplication, workflow boilerplate, regen_weekly_plan coupling, raw Sheet API calls, inconsistent error handling, bare exceptions, no retry in claude_api, env var scatter, sheets_api complexity, claude_api complexity, monthly_review size, regen_content size, custom YAML parser, retry loop duplication, pin ID string parsing |
| LOW | 7 | Timing constants, pin dimensions, os.path inconsistency, module-level side effects, inline imports, workflow inline Python, JSONL shared state |

### Top 5 Recommendations (Highest Impact)

1. **Create `src/paths.py`** -- Centralize PROJECT_ROOT, DATA_DIR, STRATEGY_DIR, ANALYSIS_DIR. Every module imports from there. Eliminates 12 duplicate definitions and prevents `Path(__file__)` depth bugs during restructure.

2. **Extract MIME detection utility** -- Single function in `src/utils.py` replaces 3 identical implementations across API wrappers.

3. **Add Sheet column header validation** -- Read row 1 headers on first access; fail loudly if they don't match expected positions. Prevents silent data corruption.

4. **Split generate_weekly_plan.py** -- Extract `validate_plan()`, `generate_content_memory_summary()`, and planning utilities into separate modules. Reduces the 1395-line file to ~400 lines.

5. **Make private cross-module imports public** -- Either rename `_source_ai_image` etc. to public API or extract to shared utility. Prevents breakage when `generate_pin_content.py` is refactored.
