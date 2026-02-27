# Code Refactor Plan -- Pinterest Pipeline

**Date:** 2026-02-27
**Status:** Draft -- pending review
**Sources:** audit.md, dead-code-analysis.md, refactor.md, architecture-data-flows.md, multi-channel implementation plan

---

## Executive Summary

The Pinterest pipeline codebase spans ~15,500 lines of Python across 27 files. Three independent audits identified 50 dead code items (~1,069 removable lines), 38 refactoring findings (4 critical, 9 high, 18 medium, 7 low), and 12+ categories of structural issues including duplicated path resolution in 12 files, MIME detection in 3 files, content log operations in 4 files, and no centralized configuration. The two most dangerous patterns are the hardcoded Google Sheets column indices (silent data corruption on column reorder) and cross-module private function imports (breakage on any refactor of `generate_pin_content.py`). This plan organizes all findings into 7 phases ordered by risk, starting with zero-risk dead code removal and ending with testability improvements. Each phase is designed to be independently deployable, with the daily pipeline (plan -> generate -> deploy -> post) remaining fully operational throughout. The plan reduces total LOC by ~15%, eliminates all critical-severity findings, and prepares the codebase for the multi-channel restructure.

---

## Critical Path Reference

The daily pipeline runs on GitHub Actions. These modules are in the **critical posting path** and must never break:

```
CRITICAL PATH (daily posting -- cannot have downtime):
  post_pins.py -> pinterest_api.py -> token_manager.py
  (reads pin-schedule.json, posts to Pinterest, updates content-log.jsonl)

HIGH-VALUE PATH (weekly content generation):
  generate_weekly_plan.py -> generate_blog_posts.py -> blog_generator.py
  -> generate_pin_content.py -> pin_assembler.py -> image_gen.py -> image_cleaner.py
  -> publish_content_queue.py -> sheets_api.py -> gcs_api.py -> drive_api.py

DEPLOYMENT PATH (blog deployment):
  blog_deployer.py -> github_api.py (commits to goslated.com)
  -> pin-schedule.json creation -> content-log.jsonl append

ANALYTICS PATH (weekly analysis):
  pull_analytics.py -> weekly_analysis.py -> generate_content_memory_summary()
```

**Concurrency groups:** `pinterest-pipeline` (9 workflows) and `pinterest-posting` (3 daily post workflows). These groups DO NOT overlap, meaning a daily post could theoretically run concurrently with content generation.

---

## Phase 0: Dead Code Removal (Low Risk)

**Prerequisites:** None
**Risk to live pipeline:** None -- all items confirmed unused by two independent reviews with codebase-wide grep verification
**Estimated scope:** 13 files touched, ~1,069 lines removed
**Rollback plan:** `git revert` the single commit
**Validation steps:**
1. `python -c "from src.apis.claude_api import ClaudeAPI"` (repeat for all modified modules)
2. Trigger `weekly-review.yml` via `workflow_dispatch` and verify completion
3. Trigger `daily-post-morning.yml` via `workflow_dispatch` and verify completion

### 0.1 Dead Functions/Methods (28 items)

| # | File | Function/Method | Line | Est. Lines |
|---|------|-----------------|------|------------|
| 1 | `src/apis/claude_api.py` | `ClaudeAPI.generate_weekly_analysis()` | 584 | 8 |
| 2 | `src/apis/claude_api.py` | `ClaudeAPI.generate_monthly_review()` | 664 | 9 |
| 3 | `src/apis/drive_api.py` | `DriveAPI.delete_image_by_name()` | 257 | 35 |
| 4 | `src/apis/github_api.py` | `GitHubAPI.commit_blog_posts()` | 138 | 33 |
| 5 | `src/apis/github_api.py` | `GitHubAPI.create_branch()` | 327 | 21 |
| 6 | `src/apis/github_api.py` | `GitHubAPI.get_file_contents()` | 349 | 18 |
| 7 | `src/apis/github_api.py` | `GitHubAPI._create_or_update_file()` | 459 | 61 |
| 8 | `src/apis/image_gen.py` | `ImageGenAPI.generate_image()` | 91 | 36 |
| 9 | `src/apis/image_gen.py` | `ImageGenAPI.get_image_status()` | 231 | 29 |
| 10 | `src/apis/pinterest_api.py` | `PinterestAPI.get_boards()` | 219 | 3 |
| 11 | `src/apis/pinterest_api.py` | `PinterestAPI.get_pin()` | 163 | 12 |
| 12 | `src/apis/pinterest_api.py` | `PinterestAPI.delete_pin()` | 176 | 10 |
| 13 | `src/apis/sheets_api.py` | `SheetsAPI.read_plan_status()` | 236 | 3 |
| 14 | `src/apis/sheets_api.py` | `SheetsAPI.read_content_statuses()` | 449 | 3 |
| 15 | `src/apis/sheets_api.py` | `SheetsAPI.update_content_status()` | 661 | 19 |
| 16 | `src/apis/sheets_api.py` | `SheetsAPI.get_approved_pins_for_slot()` | 681 | 62 |
| 17 | `src/apis/sheets_api.py` | `SheetsAPI.read_post_log()` | 804 | 50 |
| 18 | `src/apis/sheets_api.py` | `SheetsAPI.update_dashboard_metrics()` | 878 | 3 |
| 19 | `src/apis/slack_notify.py` | `SlackNotify.notify_content_generation_started()` | 101 | 6 |
| 20 | `src/apis/slack_notify.py` | `SlackNotify.notify_approval_reminder()` | 274 | 27 |
| 21 | `src/apis/slack_notify.py` | `SlackNotify.notify_reminder()` | 460 | 13 |
| 22 | `src/blog_deployer.py` | `BlogDeployer.deploy_approved_content()` | 73 | 149 |
| 23 | `src/blog_deployer.py` | `BlogDeployer.deploy_approved_posts()` | 467 | 71 |
| 24 | `src/blog_deployer.py` | `deploy_approved_content()` (module-level) | 846 | 14 |
| 25 | `src/generate_blog_posts.py` | `generate_all_blog_posts()` | 167 | 75 |
| 26 | `src/generate_blog_posts.py` | `load_approved_plan()` | 280 | 28 |
| 27 | `src/generate_blog_posts.py` | `save_generated_posts()` | 310 | 23 |
| 28 | `src/pin_assembler.py` | `render_pin_sync()` | 785 | 9 |

### 0.2 Dead Constants (12 items)

| # | File | Constant | Line | Est. Lines |
|---|------|----------|------|------------|
| 1 | `src/apis/claude_api.py` | `MODEL_HAIKU` | 43 | 1 |
| 2 | `src/apis/claude_api.py` | `COST_PER_MTK[MODEL_HAIKU]` entry | ~49 | 1 |
| 3 | `src/apis/sheets_api.py` | `PL_COL_PIN_ID` | 61 | 1 |
| 4 | `src/apis/sheets_api.py` | `PL_COL_POST_DATE` | 62 | 1 |
| 5 | `src/apis/sheets_api.py` | `PL_COL_SLOT` | 63 | 1 |
| 6 | `src/apis/sheets_api.py` | `PL_COL_BOARD` | 64 | 1 |
| 7 | `src/apis/sheets_api.py` | `PL_COL_STATUS` | 65 | 1 |
| 8 | `src/apis/sheets_api.py` | `PL_COL_URL` | 66 | 1 |
| 9 | `src/apis/sheets_api.py` | `PL_COL_PINTEREST_PIN_ID` | 67 | 1 |
| 10 | `src/apis/sheets_api.py` | `PL_COL_METRICS` | 68 | 1 |
| 11 | `src/apis/sheets_api.py` | `PL_COL_ERROR` | 69 | 1 |
| 12 | `src/blog_deployer.py` | `DEPLOY_VERIFY_RETRY_DELAY` | 44 | 1 |

### 0.3 Unused Imports (10 items)

| # | File | Import | Line |
|---|------|--------|------|
| 1 | `src/apis/slack_notify.py` | `import json` | 25 |
| 2 | `src/blog_deployer.py` | `datetime` (from `from datetime import date, datetime`) | 24 |
| 3 | `src/blog_generator.py` | `date` (from `from datetime import date`) | 28 |
| 4 | `src/generate_blog_posts.py` | `datetime` (from `from datetime import datetime`) | 26 |
| 5 | `src/generate_blog_posts.py` | `SlackNotify` import | 32 |
| 6 | `src/generate_weekly_plan.py` | `import os` | 36 |
| 7 | `src/generate_weekly_plan.py` | `import re` | 37 |
| 8 | `src/post_pins.py` | `date` (from `from datetime import datetime, date, timedelta`) | 35 |
| 9 | `src/post_pins.py` | `timedelta` (from same line) | 35 |
| 10 | `src/weekly_analysis.py` | `import re` | 36 |

### 0.4 Smoke-Test-Only Methods (consider keeping)

These 5 items are only called from `__main__` smoke tests. They have zero production callers but provide developer debugging value. **Recommendation:** Remove but note in commit message that they can be restored from git history if needed.

| File | Method | Line |
|------|--------|------|
| `src/pin_assembler.py` | `PinAssembler.render_batch()` | 599 |
| `src/pin_assembler.py` | `PinAssembler.select_variant()` | 720 |
| `src/pin_assembler.py` | `PinAssembler.get_available_templates()` | 761 |
| `src/pin_assembler.py` | `_run_test_renders()` (208 lines of test data) | 800 |
| `src/apis/pinterest_api.py` | `get_boards()` (smoke test alias) | 219 |

### 0.5 Entire Module Review

**`src/backfill_hero_images.py` (~200 lines):** No workflow trigger. Self-documented as "largely obsolete." References Column M which no longer exists. **Recommendation:** Delete the entire file. If a future backfill is needed, it should be rewritten to match the current schema.

### Phase 0 Total

| Category | Count | Lines |
|----------|-------|-------|
| Dead functions/methods | 28 | ~814 |
| Dead constants | 12 | ~12 |
| Unused imports | 10 | ~10 |
| Smoke-test-only methods | 5 | ~186 |
| Obsolete module | 1 | ~200 |
| **Total** | **56** | **~1,222** |

**Items flagged for extra caution:**
- Removing `deploy_approved_content()` and `deploy_approved_posts()` from `blog_deployer.py` touches the deployment path. Verify `deploy_to_preview()` and `promote_to_production()` still work by running `deploy-and-schedule.yml` and `promote-and-schedule.yml` via `workflow_dispatch`.
- Removing `get_approved_pins_for_slot()` from `sheets_api.py` touches the Sheet wrapper. Verify `post_pins.py` (which reads `pin-schedule.json` directly) is unaffected.

---

## Phase 1: Configuration Centralization (Low-Medium Risk)

**Prerequisites:** Phase 0 complete (dead code removed to reduce noise)
**Risk to live pipeline:** LOW if done as pure extraction (no behavior change). MEDIUM if env var validation is added (could reject missing vars that were previously lazy-loaded).
**Estimated scope:** 2 new files created, 15+ files updated, ~200 lines added, ~150 lines removed (net +50)
**Rollback plan:** `git revert` the commit(s). Since this is a rename/move of constants, the old code still works.
**Validation steps:**
1. `python -c "from src.config import BLOG_BASE_URL, ANTHROPIC_API_KEY; print('config OK')"` (without .env -- should fail fast)
2. Run `generate-content.yml` via `workflow_dispatch` end-to-end
3. Run `daily-post-morning.yml` via `workflow_dispatch` end-to-end
4. Verify all env vars load correctly in GitHub Actions (check workflow logs)

### 1.1 Create `src/paths.py` -- Centralized Path Resolution

**What to create:** `src/paths.py`

```python
"""Canonical path constants for the Pinterest pipeline.

All modules import paths from here instead of computing Path(__file__).parent.parent.
"""
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STRATEGY_DIR = PROJECT_ROOT / "strategy"
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
TEMPLATES_DIR = PROJECT_ROOT / "templates"
PIN_OUTPUT_DIR = DATA_DIR / "generated" / "pins"
BLOG_OUTPUT_DIR = DATA_DIR / "generated" / "blog"
CONTENT_LOG_PATH = DATA_DIR / "content-log.jsonl"
```

**Files to update (replace local `PROJECT_ROOT`/`DATA_DIR`/etc. definitions with imports):**

| File | Lines to Replace | Constants to Import |
|------|------------------|---------------------|
| `src/generate_weekly_plan.py` | 49-52 | `PROJECT_ROOT`, `STRATEGY_DIR`, `ANALYSIS_DIR`, `DATA_DIR` |
| `src/generate_blog_posts.py` | 36-39 | `PROJECT_ROOT`, `DATA_DIR`, `STRATEGY_DIR` |
| `src/generate_pin_content.py` | 36-38 | `PROJECT_ROOT`, `DATA_DIR`, `STRATEGY_DIR` |
| `src/weekly_analysis.py` | 51-57 | `PROJECT_ROOT`, `ANALYSIS_DIR`, `DATA_DIR`, `STRATEGY_DIR`, `PROMPTS_DIR` |
| `src/monthly_review.py` | 53-59 | `PROJECT_ROOT`, `ANALYSIS_DIR`, `DATA_DIR`, `STRATEGY_DIR`, `PROMPTS_DIR` |
| `src/pull_analytics.py` | 36-39 | `PROJECT_ROOT`, `DATA_DIR`, `CONTENT_LOG_PATH` |
| `src/blog_generator.py` | 37-38 | `PROJECT_ROOT`, `STRATEGY_DIR` |
| `src/blog_deployer.py` | 37-38 | `PROJECT_ROOT`, `DATA_DIR` |
| `src/publish_content_queue.py` | 38-41 | `PROJECT_ROOT`, `DATA_DIR`, `STRATEGY_DIR` |
| `src/regen_content.py` | 42-44 | `PROJECT_ROOT`, `DATA_DIR`, `STRATEGY_DIR` |
| `src/pin_assembler.py` | 37-41 | `PROJECT_ROOT`, `TEMPLATES_DIR` (note: uses `_PROJECT_ROOT` -- rename) |
| `src/setup_boards.py` | 29-31 | `PROJECT_ROOT` (also convert `os.path` to `pathlib` per refactor.md 5.2) |

**Interface:** Every module replaces its local `PROJECT_ROOT = Path(__file__).parent.parent` with `from src.paths import PROJECT_ROOT, DATA_DIR, ...`

### 1.2 Create `src/config.py` -- Centralized Configuration

**What to create:** `src/config.py`

Centralizes all hardcoded values that might change. Organized by concern:

```python
"""Centralized configuration for the Pinterest pipeline.

All hardcoded values, URL constants, model names, and cost rates live here.
Environment variables are read once and validated at import time.
"""
import os

# --- External URLs ---
BLOG_BASE_URL = "https://goslated.com/blog"
GOSLATED_BASE_URL = "https://goslated.com"

# --- Pinterest ---
PINTEREST_BASE_URL_PRODUCTION = "https://api.pinterest.com/v5"
PINTEREST_BASE_URL_SANDBOX = "https://api-sandbox.pinterest.com/v5"
PINTEREST_OAUTH_URL = "https://api.pinterest.com/oauth/"
PINTEREST_REDIRECT_URI = "http://localhost:8085/"
PINTEREST_REFRESH_THRESHOLD_DAYS = 5

# --- LLM Models ---
CLAUDE_MODEL_ROUTINE = "claude-sonnet-4-6"
CLAUDE_MODEL_DEEP = "claude-opus-4-6"
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")

# --- Cost Tracking (approximate, update periodically) ---
CLAUDE_COST_PER_MTK = {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "claude-opus-4-6": {"input": 5.0, "output": 25.0},
}
IMAGE_COST_PER_IMAGE = {"gpt-image-1.5": 0.080, "flux-pro": 0.050}
GPT5_MINI_COST_PER_MTK = {"input": 0.40, "output": 1.60}

# --- Pin Dimensions ---
PIN_WIDTH = 1000
PIN_HEIGHT = 1500
MAX_PNG_SIZE = 500 * 1024
MIN_IMAGE_SIZE = 10_000

# --- Timing ---
DEPLOY_VERIFY_TIMEOUT = 180
COPY_BATCH_SIZE = 6
MAX_LOOKBACK_DAYS = 90
MAX_PIN_FAILURES = 3
INITIAL_JITTER_MAX = 900
INTER_PIN_JITTER_MIN = 180
INTER_PIN_JITTER_MAX = 600
```

**Files to update (replace local constants with imports from config):**

| File | Constants to Move | refactor.md Ref |
|------|-------------------|-----------------|
| `src/generate_pin_content.py:40` | `BLOG_BASE_URL` | 1.1 |
| `src/blog_deployer.py:40` | `BLOG_BASE_URL` | 1.1 |
| `src/apis/github_api.py:43` | `GOSLATED_BASE_URL` | 1.1 |
| `src/token_manager.py:52-53` | `PINTEREST_OAUTH_URL`, `REDIRECT_URI` | 1.1 |
| `src/apis/pinterest_api.py:39-40` | `BASE_URL_PRODUCTION`, `BASE_URL_SANDBOX` | 1.1 |
| `src/apis/claude_api.py:41-43` | `MODEL_ROUTINE`, `MODEL_DEEP` | 1.2 |
| `src/apis/claude_api.py:46-50` | `COST_PER_MTK` | 1.2 |
| `src/apis/image_gen.py:38-41` | `COST_PER_IMAGE` | 1.2 |
| `src/apis/image_gen.py:44` | `MIN_IMAGE_SIZE` | 1.2 |
| `src/pin_assembler.py:47-48,51` | `PIN_WIDTH`, `PIN_HEIGHT`, `MAX_PNG_SIZE` | 1.5 |
| `src/post_pins.py:66-68,71` | Jitter constants, `MAX_PIN_FAILURES` | 1.3 |
| `src/blog_deployer.py:43` | `DEPLOY_VERIFY_TIMEOUT` | 1.3 |
| `src/generate_pin_content.py:43` | `COPY_BATCH_SIZE` | 1.3 |
| `src/pull_analytics.py:42` | `MAX_LOOKBACK_DAYS` | 1.3 |

### 1.3 Fix .gitignore Stale Entries

**What to fix:** `.gitignore` references `data/generated_posts/` and `data/generated_pins/` but actual directories are `data/generated/blog/` and `data/generated/pins/` (audit.md NEW-17).

**Items flagged for extra caution:**
- `BLOG_BASE_URL` is used in the critical deployment and posting paths. The refactor is purely moving a string constant, but verify with `grep -rn "BLOG_BASE_URL" src/` after the change to ensure no file still has a local definition.
- Adding env var validation at import time could cause modules to fail at import rather than at first use. Phase this in carefully -- start with a `config.py` that reads env vars lazily (same behavior as today) and add validation in a later PR.

---

## Phase 2: Extract Shared Utilities (Medium Risk)

**Prerequisites:** Phase 1 complete (paths.py and config.py exist)
**Risk to live pipeline:** MEDIUM -- changes function signatures and import paths. Each extraction should be a separate commit.
**Estimated scope:** 3-4 new files created, 10+ files updated, ~300 lines added, ~400 lines removed (net -100)
**Rollback plan:** Each extraction is a separate commit. `git revert` individual commits as needed.
**Validation steps:**
1. After each extraction: run the specific workflow that exercises the changed code path
2. After all extractions: run `weekly-review.yml` and `generate-content.yml` end-to-end

### 2.1 Extract MIME Detection -- `src/utils/image_utils.py`

**What to create:** `src/utils/__init__.py` + `src/utils/image_utils.py`

```python
"""Shared image utilities."""

def detect_mime_type(data: bytes) -> str:
    """Detect MIME type from magic bytes.

    Checks JPEG, PNG, WebP, and GIF signatures.
    Returns 'application/octet-stream' for unknown formats.
    """
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    if data[:4] == b'GIF8':
        return 'image/gif'
    return 'application/octet-stream'
```

**Files to update:**

| File | Current Function | Lines | Change |
|------|------------------|-------|--------|
| `src/apis/drive_api.py` | `_detect_mime_type()` | 190-197 | Replace body with `from src.utils.image_utils import detect_mime_type`, keep method as thin wrapper or call directly |
| `src/apis/gcs_api.py` | `_detect_mime_type()` | 133-142 | Same replacement |
| `src/apis/pinterest_api.py` | `_detect_content_type()` | 131-139 | Same replacement (note different function name -- update callers) |

**Note:** `src/pin_assembler.py:105-112` uses file-extension-based detection, not magic bytes. Leave it as-is -- it serves a different purpose (local files with known extensions).

### 2.2 Extract Content Log Operations -- `src/utils/content_log.py`

**What to create:** `src/utils/content_log.py`

```python
"""Canonical content log operations.

Single source of truth for reading, appending, and querying content-log.jsonl.
"""
import json
from pathlib import Path
from src.paths import CONTENT_LOG_PATH

def load_content_log(path: Path = None) -> list[dict]:
    """Load all entries from content-log.jsonl."""
    p = path or CONTENT_LOG_PATH
    if not p.exists():
        return []
    entries = []
    for line in p.read_text().strip().split('\n'):
        if line.strip():
            entries.append(json.loads(line))
    return entries

def save_content_log(entries: list[dict], path: Path = None) -> None:
    """Write all entries to content-log.jsonl."""
    p = path or CONTENT_LOG_PATH
    with open(p, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')

def append_content_log_entry(entry: dict, path: Path = None) -> None:
    """Append a single entry to content-log.jsonl (atomic append)."""
    p = path or CONTENT_LOG_PATH
    with open(p, 'a') as f:
        f.write(json.dumps(entry) + '\n')

def is_pin_posted(pin_id: str, path: Path = None) -> bool:
    """Check if a pin has already been posted (idempotency guard)."""
    entries = load_content_log(path)
    return any(e.get('pin_id') == pin_id and e.get('posted') for e in entries)
```

**Files to update:**

| File | Current Implementation | Lines | Change |
|------|------------------------|-------|--------|
| `src/pull_analytics.py` | `load_content_log()`, `save_content_log()` | various | Keep as canonical source during transition; then replace with imports from `content_log.py` |
| `src/post_pins.py` | Inline append logic, `is_already_posted()` | various | Replace with `append_content_log_entry()` and `is_pin_posted()` |
| `src/generate_weekly_plan.py` | `_load_content_log()` (private re-implementation) | 1281-1307 | Delete; import `load_content_log()` from `content_log.py` |
| `src/blog_deployer.py` | `_append_to_content_log()` inline logic | various | Replace with `append_content_log_entry()` |

### 2.3 Extract Plan Loading -- `src/utils/plan_utils.py`

**What to create:** `src/utils/plan_utils.py`

```python
"""Shared weekly plan loading utilities."""
import json
from pathlib import Path
from src.paths import DATA_DIR

def find_latest_plan(data_dir: Path = None) -> Path | None:
    """Find the most recent weekly-plan-*.json file."""
    d = data_dir or DATA_DIR
    plans = sorted(d.glob("weekly-plan-*.json"), reverse=True)
    return plans[0] if plans else None

def load_plan(path: Path) -> dict:
    """Load and parse a weekly plan JSON file."""
    return json.loads(path.read_text())
```

**Files to update:**

| File | Current Function | Change |
|------|------------------|--------|
| `src/generate_blog_posts.py` | `_load_plan()` | Replace with `from src.utils.plan_utils import find_latest_plan, load_plan` |
| `src/generate_pin_content.py` | `_load_plan()` | Same replacement |
| `src/regen_weekly_plan.py` | `find_latest_plan()` + `load_plan()` | Same replacement (these already have the right names) |

### 2.4 Extract Brand Voice Loading -- `src/utils/strategy_utils.py`

**What to create:** `src/utils/strategy_utils.py`

```python
"""Shared strategy file loading utilities."""
from pathlib import Path
from src.paths import STRATEGY_DIR

def load_brand_voice(strategy_dir: Path = None) -> str:
    """Load brand-voice.md content."""
    d = strategy_dir or STRATEGY_DIR
    path = d / "brand-voice.md"
    return path.read_text() if path.exists() else ""
```

**Files to update:**

| File | Current Function | Change |
|------|------------------|--------|
| `src/generate_pin_content.py` | `_load_brand_voice()` | Replace with import from `strategy_utils.py` |
| `src/blog_generator.py` | `_load_brand_voice()` | Same replacement |

### 2.5 Extract Drive File ID Extraction

**What to create:** Add to `src/utils/image_utils.py`:

```python
def extract_drive_file_id(url: str) -> str | None:
    """Extract Google Drive file ID from a sharing URL."""
    if "id=" in url:
        return url.split("id=")[1].split("&")[0]
    if "/d/" in url:
        return url.split("/d/")[1].split("/")[0]
    return None
```

**Files to update:**

| File | Current Implementation | Change |
|------|------------------------|--------|
| `src/regen_content.py` | `_extract_drive_file_id()` (lines 667-676) | Replace body with call to shared function |
| `src/publish_content_queue.py` | Inline `url.split("id=")` (line 118) | Replace with call to shared function |

### 2.6 Extract Content Memory Summary (largest duplication)

**What to create:** `src/utils/content_memory.py`

This consolidates the two implementations of `generate_content_memory_summary()`:
- `src/generate_weekly_plan.py:522-872` (350 lines, 7 sections -- the more comprehensive version)
- `src/weekly_analysis.py` (220 lines -- the simpler version)

**Interface:**
```python
def generate_content_memory_summary(
    content_log_path: Path = None,
    output_path: Path = None,
) -> str:
    """Generate the content memory summary markdown.

    Produces 7 sections: recent topics, all blog posts, pillar mix,
    keyword frequency, images used, fresh pin candidates, treatment tracker.
    Returns the markdown string and writes to output_path.
    """
```

**Files to update:**

| File | Change |
|------|--------|
| `src/generate_weekly_plan.py` | Delete `generate_content_memory_summary()` (lines 522-872) and its helpers. Import from `content_memory.py`. |
| `src/weekly_analysis.py` | Delete local `generate_content_memory_summary()`. Import from `content_memory.py`. |
| `weekly-review.yml` (line 58) | Update inline Python: `from src.utils.content_memory import generate_content_memory_summary` |

**CAUTION:** This is the single largest extraction (~350 lines). The two implementations produce slightly different output. Before merging, diff the output of both versions against a saved baseline to ensure no regression.

**Items flagged for extra caution:**
- Content log operations (2.2) touch the `content-log.jsonl` file which is written by the deployment path and read by the posting path. Test thoroughly with `promote-and-schedule.yml` and `daily-post-*.yml`.
- Content memory extraction (2.6) is referenced in the `weekly-review.yml` inline Python. If the import path changes and the workflow fires before the change is committed, the Monday cron will fail. Merge this during the week, not on Sunday/Monday.
- The `weekly-review.yml` inline Python call at line 58 must update to the new import path.

---

## Phase 3: Reduce God Files (Medium-High Risk)

**Prerequisites:** Phase 2 complete (shared utilities exist to receive extracted code)
**Risk to live pipeline:** MEDIUM-HIGH -- splitting files changes import paths throughout the codebase. Each split should be a separate PR with its own validation.
**Estimated scope:** 4-6 new files created, 8+ files updated
**Rollback plan:** Each split is a separate PR. Revert individual PRs if needed.
**Validation steps:**
1. After each split: full import test for all affected modules
2. After `generate_weekly_plan.py` split: run `weekly-review.yml` end-to-end
3. After `claude_api.py` split: run `generate-content.yml` end-to-end (exercises both Claude and GPT-5 Mini paths)
4. After `sheets_api.py` changes: run every workflow that reads/writes to Sheets

### 3.1 Split `generate_weekly_plan.py` (1,395 lines -> ~400 lines)

Currently this file is 8 things at once. After Phase 2 extractions (content memory, content log, plan utilities), split the remaining logic:

**New file: `src/plan_validator.py`**
Extract from `generate_weekly_plan.py`:
- `validate_plan()` (~240 lines, lines ~380-620 approximately)
- `violation_messages()` (helper for formatting violations)
- All constraint constants (`PILLAR_MIX_TARGETS`, `TOTAL_WEEKLY_PINS`, `MAX_PINS_PER_BOARD`, etc.)
- Pin ID parsing from violation messages (refactor.md 8.3 -- add `pin_id` as structured field in violation dict)

**New file: `src/plan_utils.py`** (extend the Phase 2 file)
Extract from `generate_weekly_plan.py`:
- `identify_replaceable_posts()` (~60 lines)
- `splice_replacements()` (~80 lines)
- `_build_keyword_performance_data()` (~50 lines)
- `_extract_recent_topics()` (~30 lines)

**What remains in `generate_weekly_plan.py` (~400 lines):**
- `generate_plan()` orchestration with retry loop
- `generate_weekly_plan()` top-level entry point
- `load_strategy_context()`
- `load_latest_analysis()`
- `get_current_seasonal_window()`

**Also extract: `_build_reprompt_context()` helper** (refactor.md 7.7) to consolidate the 3 duplicated reprompt construction paths (lines 172-178, 218-222, 200-203) in the retry loop into a single helper.

**Files to update for imports:**

| File | What It Imports | New Import Path |
|------|-----------------|-----------------|
| `src/regen_weekly_plan.py:36-41` | `identify_replaceable_posts`, `splice_replacements`, `load_content_memory`, `DATA_DIR` | Import from `src.plan_utils` (for plan functions) and `src.paths` (for DATA_DIR) |

### 3.2 Split `claude_api.py` (955 lines -> ~600 + ~350 lines)

The file now handles both Claude and GPT-5 Mini. Split along model boundaries:

**New file: `src/apis/openai_chat_api.py` (~350 lines)**
Extract from `claude_api.py`:
- `_call_openai_gpt5_mini()` method and all GPT-5 Mini-related logic
- GPT-5 Mini cost tracking
- The dual-model branching from `generate_image_prompt()` and `generate_pin_copy_batch()`

**Refactored `claude_api.py` (~600 lines):**
- All Claude-specific API calls remain
- Import `OpenAIChatAPI` from the new module
- Orchestration methods (`generate_image_prompt()`, `generate_pin_copy_batch()`) call GPT-5 Mini first via `OpenAIChatAPI`, fall back to Claude Sonnet

**Also fix (audit.md NEW-13):** Migrate raw `requests` HTTP calls to the `openai` Python SDK (already in `requirements.txt`). This eliminates manual auth header construction, error parsing, and retry logic.

**Also fix (audit.md NEW-14):** Make GPT-5 Mini fallback explicit -- log a warning when falling back to Claude Sonnet, not silent.

### 3.3 Reduce `sheets_api.py` (1,018 lines)

Rather than a full split (which is high-risk given 8 consumer scripts), add structure within the file:

**Option A (recommended -- lower risk):** Add clear section markers and consolidate column definitions into a single schema block at the top. Defer full split to the multi-channel restructure.

**Option B (higher impact, higher risk):** Split into `sheets_api.py` (core + Weekly Review + Dashboard) and `content_queue_api.py` (Content Queue + Post Log). This would require updating imports in 8 files.

**Recommended for now:** Option A. Consolidate the column index definitions and add the header validation from Phase 4.

### 3.4 Reduce `blog_deployer.py` (920 lines)

Extract shared deployment logic from the 4 deployment methods (60%+ duplication per audit.md DU9):

**Refactored structure:**
- Extract `_deploy_posts(posts, target_branch, verify=True)` common logic (~200 lines)
- `deploy_to_preview()` becomes: load content, call `_deploy_posts(posts, "develop", verify=True)`, update Sheet
- `promote_to_production()` becomes: merge develop->main, verify URLs, create schedule, update Sheet
- Delete `deploy_approved_content()` and `deploy_approved_posts()` (already dead -- removed in Phase 0)

**Result:** ~920 lines -> ~600 lines

### 3.5 Consolidate `blog_generator.py` Type Methods

`blog_generator.py` has four near-identical `generate_*_post()` methods (audit.md DU4). Consolidate to a single parameterized `generate_post(post_type, ...)` method with a config dict mapping post types to their specific template paths and parameters.

### 3.6 Consolidate `github_api.py` Commit Methods

`github_api.py` has three overlapping commit methods (audit.md DU5). After Phase 0 removes the dead ones (`commit_blog_posts`, `_create_or_update_file`), only `commit_blog_post()` and `commit_multiple_posts()` remain. These share logic and can be unified: `commit_multiple_posts()` handles both single and batch cases.

**Items flagged for extra caution:**
- **generate_weekly_plan.py split (3.1) is the highest-risk item in the entire plan.** This file is called by `weekly-review.yml` (Monday cron) and consumed by `regen_weekly_plan.py`. Split during mid-week. Have the old file available for instant `git revert`.
- **claude_api.py split (3.2)** affects every content generation workflow. The GPT-5 Mini fallback logic is in the daily-use `generate-content.yml` path.
- **sheets_api.py** is used by 8 scripts. Any import path change cascades widely.

---

## Phase 4: Fix Coupling and Fragile Patterns (High Risk)

**Prerequisites:** Phase 2 complete (shared utilities exist), Phase 3 preferred but not required
**Risk to live pipeline:** HIGH -- these changes fix actively dangerous patterns but touch core pipeline logic
**Estimated scope:** 5-8 files updated, ~150 lines changed
**Rollback plan:** Each fix is a separate commit/PR. Critical fixes should be deployed individually with 24h soak time between them.
**Validation steps:**
1. After Sheet column changes: manually inspect Google Sheet to verify column headers match code expectations
2. After private import fix: run `regen-content.yml` via `workflow_dispatch`
3. After header validation: run all workflows that read from Sheets (5+ workflows)

### 4.1 Fix Private Function Imports -- CRITICAL (refactor.md 3.1)

`src/regen_content.py:21-25` imports private (underscore-prefixed) functions from `src/generate_pin_content.py`:

```python
from src.generate_pin_content import (
    _source_ai_image,       # private
    _load_brand_voice,      # private
    _load_keyword_targets,  # private
    build_template_context, # public
)
```

**Fix:** After Phase 2, `_load_brand_voice()` and `_load_keyword_targets()` move to shared utilities. For `_source_ai_image()`:
- **Option A:** Rename to `source_ai_image()` (remove underscore, make it part of the public API)
- **Option B:** Extract to `src/utils/image_utils.py` as a shared function

**Recommended:** Option A for `_source_ai_image()` (it is genuinely used externally and should be public), combined with shared utilities for the other two.

**Result after fix:**
```python
# regen_content.py
from src.utils.strategy_utils import load_brand_voice
from src.utils.strategy_utils import load_keyword_targets
from src.generate_pin_content import source_ai_image, build_template_context
```

### 4.2 Add Sheet Column Header Validation -- CRITICAL (refactor.md 8.1)

The hardcoded column indices in `src/apis/sheets_api.py:46-69` are the most fragile pattern in the codebase. If anyone reorders columns in the Google Sheet, the pipeline silently corrupts data.

**What to add to `sheets_api.py`:**

```python
EXPECTED_CQ_HEADERS = [
    "Status", "Pin ID", "Post ID", "Title", "Pin Type",
    "Template", "Board", "Pin Image", "Blog Image",
    "Approval", "Copy Preview", "Blog Summary"
]

EXPECTED_WR_HEADERS = [...]  # Weekly Review headers

def _validate_headers(self, tab_name: str, expected: list[str]) -> None:
    """Read row 1 of a tab and verify column names match expected positions.

    Raises ValueError if headers don't match, preventing silent data corruption.
    """
    result = self.sheets.values().get(
        spreadsheetId=self.sheet_id,
        range=f"'{tab_name}'!A1:Z1",
    ).execute()
    actual = result.get("values", [[]])[0]
    for i, expected_name in enumerate(expected):
        if i >= len(actual) or actual[i] != expected_name:
            raise ValueError(
                f"Sheet '{tab_name}' column {chr(65+i)} expected '{expected_name}' "
                f"but found '{actual[i] if i < len(actual) else '(missing)'}'. "
                f"Column layout has changed -- update sheets_api.py column indices."
            )
```

**Call `_validate_headers()` on first access to each tab** (cache the result so it only checks once per session).

### 4.3 Consolidate Column Index Definitions

`src/backfill_hero_images.py:33-37` duplicates column indices from `sheets_api.py`. After Phase 0 deletes `backfill_hero_images.py`, this is resolved. If the file is kept, update it to import from `sheets_api.py`.

### 4.4 Fix Hardcoded Sheet Cell References (refactor.md 8.2)

Define all cell references as named constants in `sheets_api.py`:

```python
# Weekly Review control cells
WR_CELL_PLAN_STATUS = "B3"       # Plan approval status
WR_CELL_DEPLOY_STATUS = "B4"     # Deploy approval status
WR_CELL_REGEN_TRIGGER = "B5"     # Plan regen trigger
WR_CELL_PLAN_SUMMARY = "A4:C4"   # Plan summary range

# Content Queue control cells
CQ_CELL_REGEN_TRIGGER = "N1"     # Content regen trigger
```

**Files to update:**
- `src/regen_weekly_plan.py:269` -- replace `'Weekly Review'!B3` with constant
- All cell references in `sheets_api.py` methods

### 4.5 Fix Raw Google Sheets API Call (refactor.md 3.3)

`src/regen_weekly_plan.py:268-273` bypasses the `SheetsAPI` wrapper and makes a raw `sheets.values().update()` call.

**Fix:** Add `SheetsAPI.write_cell(tab: str, cell: str, value: str)` method:

```python
def write_cell(self, tab: str, cell: str, value: str) -> None:
    """Write a single value to a specific cell."""
    self.sheets.values().update(
        spreadsheetId=self.sheet_id,
        range=f"'{tab}'!{cell}",
        valueInputOption="RAW",
        body={"values": [[value]]},
    ).execute()
```

Update `regen_weekly_plan.py` to call `sheets.write_cell(...)` instead.

### 4.6 Make pin-schedule.json Writes Atomic (refactor.md 8.4)

`data/pin-schedule.json` is now written by two modules (`blog_deployer.py`, `regen_content.py`) with non-atomic load-modify-write.

**Fix:** Add to `src/utils/plan_utils.py`:

```python
import tempfile

def save_pin_schedule(schedule: list[dict], path: Path = None) -> None:
    """Atomically write pin-schedule.json using temp file + rename."""
    p = path or (DATA_DIR / "pin-schedule.json")
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(schedule, indent=2))
    tmp.replace(p)  # atomic on POSIX; best-effort on Windows
```

**Items flagged for extra caution:**
- **Header validation (4.2) could cause immediate failures** if the Sheet headers don't exactly match expected values. Test against the live Sheet before deploying. Consider a "warn" mode first that logs mismatches without raising.
- **Cell reference constants (4.4)** -- verify every constant against the live Google Sheet layout documented in `architecture-data-flows.md` Section 7.
- **Atomic writes (4.6)** -- `Path.replace()` is atomic on POSIX but not guaranteed on Windows. The pipeline runs on Ubuntu (GitHub Actions), so this is fine for production.

---

## Phase 5: Error Handling Standardization (Medium Risk)

**Prerequisites:** Phase 2 complete (shared utilities have defined error patterns)
**Risk to live pipeline:** MEDIUM -- changing error handling could surface previously-swallowed errors
**Estimated scope:** 8-10 files updated, ~100 lines changed
**Rollback plan:** Revert individual commits
**Validation steps:**
1. Run full pipeline end-to-end with all environment variables set
2. Run with one non-critical env var missing (e.g., `SLACK_WEBHOOK_URL`) to verify graceful degradation
3. Monitor pipeline for 48 hours after deployment

### 5.1 Establish Error Handling Convention

Document in `CONTRIBUTING.md` or `CLAUDE.md`:

| Layer | Pattern | Example |
|-------|---------|---------|
| API wrappers (`src/apis/`) | Raise on failure | `raise APIError("Pinterest API returned 429")` |
| Shared utilities (`src/utils/`) | Raise on failure | `raise ValueError("Column headers mismatch")` |
| Orchestrator scripts (top-level `src/`) | Catch, log, and decide (fail or continue) | `try: sheets.write(...) except: logger.error(...); continue` |
| Best-effort operations (Slack, analytics writes) | Log and continue | `try: notify(...) except: logger.warning(...)` |

### 5.2 Narrow Bare Exception Catches (refactor.md 4.2)

| File | Line | Current | Fix |
|------|------|---------|-----|
| `src/image_cleaner.py` | 99 | `except Exception as e` | `except (PIL.UnidentifiedImageError, OSError, ValueError) as e` |
| `src/regen_weekly_plan.py` | 252-253 | `except Exception: plan_status = "pending_review"` | `except (KeyError, ValueError): plan_status = "pending_review"` + log warning |
| `src/regen_weekly_plan.py` | 256-257 | `except Exception: deploy_status = "pending_review"` | Same pattern |
| `src/pin_assembler.py` | 598-599 | `except ImportError` then `except Exception` | Keep `except ImportError`, narrow inner to `except (OSError, ValueError)` |

### 5.3 Add Retry Logic to Missing API Calls (refactor.md 4.3)

| File | Current State | Fix |
|------|---------------|-----|
| `src/apis/claude_api.py` | No retry logic | Add retry with exponential backoff for 429 (rate limit) and 5xx errors. The Anthropic SDK may handle retries internally -- verify before adding. |
| `src/apis/sheets_api.py` | No retry logic | Add retry for Google API 429/5xx errors. Use `tenacity` or a simple `for` loop with backoff. |

Model pattern after `src/apis/pinterest_api.py` which already has `MAX_RETRIES = 3` with backoff.

### 5.4 Fix `gcs_api.py` Silent None Returns (refactor.md 4.1, audit.md E1)

`gcs_api.py` returns `None` when credentials are missing. Callers don't check for `None`.

**Fix:** Raise an exception when credentials are missing or API calls fail. Let orchestrator scripts handle the error.

### 5.5 Replace Custom YAML Parser (refactor.md 7.6)

`src/blog_generator.py:543-628` has an 85-line custom YAML parser for MDX frontmatter. The rest of the codebase uses `yaml.safe_load`.

**Fix:** Replace with `yaml.safe_load()` (already a dependency). If edge cases exist, document them as comments above the call.

**Items flagged for extra caution:**
- Narrowing exception catches (5.2) in `image_cleaner.py` could surface previously-hidden PIL errors. Test with a variety of image formats.
- Adding retry logic (5.3) to `claude_api.py` could increase execution time if Anthropic API has transient issues. Set reasonable timeouts.

---

## Phase 6: Workflow Improvements (Low-Medium Risk)

**Prerequisites:** None (can be done independently of other phases)
**Risk to live pipeline:** LOW for composite action extraction, MEDIUM for inline Python extraction
**Estimated scope:** 3-4 new files created, 11 workflow files updated
**Rollback plan:** `git revert` workflow changes
**Validation steps:**
1. After composite action creation: trigger one workflow via `workflow_dispatch` and verify it completes
2. After inline Python extraction: trigger `promote-and-schedule.yml` with a test `override_pin_start_date`

### 6.1 Extract Reusable Composite Actions (refactor.md 2.7)

**Create `.github/actions/setup-pipeline/action.yml`:**
```yaml
# Replaces the 3 repeated Python setup steps across all 11 workflows
name: Setup Pipeline
runs:
  using: composite
  steps:
    - uses: actions/setup-python@v5
      with:
        python-version: '3.11'
        cache: 'pip'
    - run: pip install -r requirements.txt
      shell: bash
```

**Create `.github/actions/commit-data/action.yml`:**
```yaml
# Replaces the repeated git commit-and-push pattern across 8 workflows
name: Commit Data Files
inputs:
  message:
    required: true
runs:
  using: composite
  steps:
    - run: |
        git config user.name "pinterest-pipeline-bot"
        git config user.email "bot@pinterest-pipeline.local"
        git add data/ analysis/
        git diff --staged --quiet || git commit -m "${{ inputs.message }}"
        git pull --rebase
        git push
      shell: bash
```

**Create `.github/actions/notify-failure/action.yml`:**
```yaml
# Replaces the repeated failure notification step across all 11 workflows
name: Notify Failure
inputs:
  workflow_name:
    required: true
  run_url:
    required: true
runs:
  using: composite
  steps:
    - if: failure()
      run: |
        python -c "
        from src.apis.slack_notify import SlackNotify
        notifier = SlackNotify()
        notifier.notify_failure('${{ inputs.workflow_name }}', 'Workflow failed. Check: ${{ inputs.run_url }}')
        "
      shell: bash
```

### 6.2 Extract Inline Pin Schedule Redating

`promote-and-schedule.yml:68-96` has a 28-line inline Python script for redating pin schedules.

**What to create:** `src/redate_schedule.py`

Move the inline logic to a proper Python module with a `redate(start_date: str)` function, callable via `python -m src.redate_schedule 2026-03-01`.

---

## Phase 7: Testability Improvements (Low Risk, High Value)

**Prerequisites:** Phases 1-2 complete (config centralized, shared utilities extracted)
**Risk to live pipeline:** ZERO -- adding test infrastructure doesn't change production code
**Estimated scope:** New `tests/` directory, ~500 lines of test stubs
**Rollback plan:** Delete test files
**Validation steps:** `python -m pytest tests/` passes

### 7.1 Add Dependency Injection Points (refactor.md 6.1)

Update orchestrator functions to accept API clients as optional parameters:

```python
# Before (src/generate_weekly_plan.py)
def generate_plan():
    claude = ClaudeAPI()
    sheets = SheetsAPI()

# After
def generate_plan(claude: ClaudeAPI = None, sheets: SheetsAPI = None):
    claude = claude or ClaudeAPI()
    sheets = sheets or SheetsAPI()
```

**Files to update:**

| File | Functions to Update |
|------|---------------------|
| `src/generate_weekly_plan.py` | `generate_plan()`, `generate_weekly_plan()` |
| `src/regen_weekly_plan.py` | `regen_plan()` |
| `src/generate_blog_posts.py` | `generate_blog_posts()` |
| `src/generate_pin_content.py` | `generate_pin_content()` |
| `src/blog_deployer.py` | `deploy_to_preview()`, `promote_to_production()` |
| `src/post_pins.py` | `post_pins()` |
| `src/regen_content.py` | `regen()` |

### 7.2 Separate I/O from Business Logic (refactor.md 6.2)

Key functions to refactor:
- `validate_plan()` -- accept negative keywords as a parameter instead of loading from disk mid-validation
- `_build_keyword_performance_data()` -- accept content log as a parameter instead of calling `_load_content_log()` internally
- `blog_generator.py` type methods -- separate YAML parsing, frontmatter generation, and MDX output into distinct steps

### 7.3 Move Module-Level Side Effects (refactor.md 6.3)

| File | Side Effect | Fix |
|------|-------------|-----|
| `src/setup_boards.py` | `logging.basicConfig()` at module level | Move to `if __name__ == "__main__"` block |
| `src/backfill_hero_images.py` | `dotenv` import at module level | N/A if deleted in Phase 0 |

### 7.4 Add Integration Test Stubs

Create `tests/` with stubs that exercise the key interfaces:

```
tests/
  test_config.py           # Verify config.py loads and validates
  test_paths.py            # Verify all paths resolve correctly
  test_content_log.py      # Test load/append/save with temp files
  test_plan_utils.py       # Test plan loading/validation
  test_mime_detection.py    # Test magic byte detection
  test_pin_schedule.py     # Test atomic write
```

---

## Appendix A: Cross-Reference Matrix

Every item from audit.md, dead-code-analysis.md, and refactor.md mapped to its phase in this plan.

### From refactor.md

| ID | Finding | Severity | Phase |
|----|---------|----------|-------|
| 1.1 | Hardcoded URLs (BLOG_BASE_URL duplication) | HIGH | Phase 1.2 |
| 1.2 | Hardcoded model names and cost rates | MEDIUM | Phase 1.2 |
| 1.3 | Hardcoded timing/threshold constants | LOW | Phase 1.2 |
| 1.4 | Hardcoded column indices in Sheets API | CRITICAL | Phase 4.2, 4.3 |
| 1.5 | Hardcoded pin dimensions | LOW | Phase 1.2 |
| 2.1 | MIME detection duplication (3 files) | HIGH | Phase 2.1 |
| 2.2 | PROJECT_ROOT duplication (12 files) | HIGH | Phase 1.1 |
| 2.3 | _load_plan() duplication (3 files) | MEDIUM | Phase 2.3 |
| 2.4 | _load_brand_voice() duplication (2 files) | MEDIUM | Phase 2.4 |
| 2.5 | Content log read/write duplication (4 files) | MEDIUM | Phase 2.2 |
| 2.6 | generate_content_memory_summary() duplication | HIGH | Phase 2.6 |
| 2.7 | Workflow boilerplate duplication | MEDIUM | Phase 6.1 |
| 3.1 | regen_content.py imports private functions | CRITICAL | Phase 4.1 |
| 3.2 | regen_weekly_plan.py imports from generate_weekly_plan | MEDIUM | Phase 3.1 |
| 3.3 | Raw Google Sheets API call in orchestrator | MEDIUM | Phase 4.5 |
| 3.4 | Circular-ish import risk in pin_assembler | LOW | Phase 2 (move import to top) |
| 3.5 | SheetsAPI tightly coupled to Sheet layout | HIGH | Phase 4.2, 4.4 |
| 4.1 | Inconsistent failure modes | MEDIUM | Phase 5.1 |
| 4.2 | Bare exception catches | MEDIUM | Phase 5.2 |
| 4.3 | No retry in claude_api.py and sheets_api.py | MEDIUM | Phase 5.3 |
| 5.1 | No centralized configuration | HIGH | Phase 1.2 |
| 5.2 | setup_boards.py uses os.path | LOW | Phase 1.1 |
| 5.3 | Environment variable access scattered | MEDIUM | Phase 1.2 |
| 6.1 | No dependency injection | HIGH | Phase 7.1 |
| 6.2 | File I/O mixed with business logic | HIGH | Phase 7.2 |
| 6.3 | Module-level side effects | LOW | Phase 7.3 |
| 7.1 | generate_weekly_plan.py complexity (1395 lines) | CRITICAL | Phase 3.1 |
| 7.2 | sheets_api.py complexity (1018 lines) | HIGH | Phase 3.3 |
| 7.3 | claude_api.py complexity (955 lines) | MEDIUM | Phase 3.2 |
| 7.4 | monthly_review.py complexity (865 lines) | MEDIUM | Deferred (not critical) |
| 7.5 | regen_content.py complexity (822 lines) | MEDIUM | Deferred (not critical) |
| 7.6 | Custom YAML parser in blog_generator.py | MEDIUM | Phase 5.5 |
| 7.7 | generate_plan() retry loop duplication | MEDIUM | Phase 3.1 |
| 8.1 | Google Sheets column indices fragility | CRITICAL | Phase 4.2 |
| 8.2 | Hardcoded Sheet cell references | HIGH | Phase 4.4 |
| 8.3 | Pin ID parsing via string splitting | MEDIUM | Phase 3.1 |
| 8.4 | JSONL content log shared mutable state | MEDIUM | Phase 4.6 |
| 8.5 | Variant activation via line-by-line HTML parsing | MEDIUM | Deferred (template rework needed) |
| 8.6 | Workflow inline Python | LOW | Phase 6.2 |

### From audit.md

| ID | Finding | Severity | Phase |
|----|---------|----------|-------|
| D1 | content-log.jsonl schema inconsistency | HIGH | Phase 2.2 |
| D2 | pin-generation-results.json loaded multiple times | HIGH | Phase 3.4 |
| D3 | Google Drive and GCS redundancy | MEDIUM | Deferred (requires migration plan) |
| D4 | BLOG_BASE_URL defined in 3 places | MEDIUM | Phase 1.2 |
| D5 | pin-schedule.json second writer | LOW | Phase 4.6 |
| H1-H29 | Hardcoded values (27+ instances) | Various | Phase 1.2 |
| F1-F10 | Fragile coupling (10 instances) | Various | Phase 4 |
| DU1-DU12 | Duplication (12 instances) | Various | Phases 0, 2, 3 |
| E1-E5 | Error handling gaps | Various | Phase 5 |
| S1-S7 | Structural issues | Various | Phases 0, 3 |
| C1-C4 | Configuration issues | Various | Phase 1 |
| NEW-1 | JSON code-fence stripping fragility | MEDIUM | Phase 5 (harden parsing) |
| NEW-2 | Image retry count always 0 | LOW | Deferred (cosmetic) |
| NEW-3 | Assumes image_gen returns Path | LOW | Phase 5 (add type check) |
| NEW-4 | Non-atomic pin-schedule.json writes | MEDIUM | Phase 4.6 |
| NEW-5 | Hero image download assumes field exists | LOW | Phase 5 (add guard) |
| NEW-6 | Malformed pins silently skip URL backup | MEDIUM | Phase 5 (add warning) |
| NEW-7 | H1 stripping blank line edge case | LOW | Deferred (cosmetic) |
| NEW-8 | Tight coupling to splice_replacements() | HIGH | Phase 3.1 |
| NEW-9 | Silent exception defaults in regen_weekly_plan | MEDIUM | Phase 5.2 |
| NEW-10 | No validation for Sheet cell restoration | MEDIUM | Phase 4.5 |
| NEW-11 | Post identification failures silently skipped | LOW | Phase 5 (add logging) |
| NEW-12 | GPT-5 model name partially configurable | LOW | Phase 1.2 (already has env var) |
| NEW-13 | Manual HTTP for OpenAI instead of SDK | HIGH | Phase 3.2 |
| NEW-14 | Fragile GPT-5 Mini fallback | HIGH | Phase 3.2 |
| NEW-15 | Dual-model branching complexity | MEDIUM | Phase 3.2 |
| NEW-16 | Hardcoded GPT-5 Mini cost rates | LOW | Phase 1.2 |
| NEW-17 | Stale .gitignore entries | MEDIUM | Phase 1.3 |

### From dead-code-analysis.md

| Category | Count | Phase |
|----------|-------|-------|
| Dead functions/methods | 28 | Phase 0.1 |
| Dead constants | 12 | Phase 0.2 |
| Unused imports | 10 | Phase 0.3 |
| Smoke-test-only methods | 5 | Phase 0.4 |
| Obsolete module (backfill_hero_images.py) | 1 | Phase 0.5 |
| **Total** | **56** | **Phase 0** |

### Deferred Items

These items are acknowledged but deferred because they require larger architectural changes or have low impact:

| Item | Reason for Deferral |
|------|---------------------|
| D3: Google Drive vs GCS redundancy | Requires data migration plan; low urgency while both work |
| 7.4: monthly_review.py complexity | Not in critical path; functional as-is |
| 7.5: regen_content.py complexity | Not in critical path; functional as-is |
| 8.5: Variant HTML parsing fragility | Requires template system rework; current templates are stable |
| NEW-2: Image retry count always 0 | Cosmetic quality note issue |
| NEW-7: H1 stripping blank line edge case | Very unlikely to trigger in practice |

---

## Appendix B: Relationship to Multi-Channel Restructure

The `architecture/multi-channel-restructure/implementation-plan.md` describes a 6-phase restructure to support TikTok and future channels. This refactor plan is designed to **precede and support** that restructure:

| This Plan | Enables Multi-Channel Phase |
|-----------|----------------------------|
| Phase 1: `src/paths.py` | Multi-Channel Phase 1: becomes `src/shared/paths.py` |
| Phase 2: content_memory extraction | Multi-Channel Phase 2: becomes `src/shared/content_memory.py` |
| Phase 2: content_log extraction | Multi-Channel Phase 2: becomes `src/shared/analytics_utils.py` |
| Phase 3.1: generate_weekly_plan split | Multi-Channel Phase 3: planning split into shared + Pinterest |
| Phase 3.2: claude_api split | Multi-Channel Phase 1: `claude_api.py` moves to `src/shared/apis/` |
| Phase 0: dead code removal | Multi-Channel Phase 6: less code to move |

Completing this refactor plan first means the multi-channel restructure will be moving cleaner, smaller, well-structured files instead of tangled god files.

---

## Appendix C: Execution Priority

If time is limited, execute phases in this priority order:

1. **Phase 0** (dead code removal) -- zero risk, immediate LOC reduction
2. **Phase 1.1** (paths.py) -- eliminates 12 duplicate definitions, prevents path bugs
3. **Phase 4.2** (Sheet header validation) -- prevents the #1 silent failure mode
4. **Phase 4.1** (fix private imports) -- prevents the most likely breakage during future refactoring
5. **Phase 2.1** (MIME detection) -- quick win, eliminates obvious duplication
6. **Phase 1.2** (config.py) -- centralizes hardcoded values
7. **Phase 2.2** (content log) -- reduces duplication in critical data path
8. **Phase 3.1** (split generate_weekly_plan.py) -- highest-impact structural improvement
9. Everything else in phase order
