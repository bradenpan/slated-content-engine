# Multi-Channel Content Pipeline — Implementation Plan

**Date:** 2026-02-27 (updated 2026-03-04)
**Status:** Active — Phases 1-9 complete, Phase 10b complete (pulled forward as Phase 8b), Phase 10 next

---

## Table of Contents

- [Context](#context)
- [Target Architecture](#target-architecture)
- [Target Directory Structure](#target-directory-structure)
- [Part 1: Restructure](#part-1-restructure-pinterest-stays-live-throughout)
  - [Phase 1: Create structure, move purely shared code](#phase-1-create-structure-move-purely-shared-code)
  - [Phase 2: Extract content memory and analytics utilities](#phase-2-extract-content-memory-and-analytics-utilities)
  - [Phase 3: Extract shared data-loading into content planner](#phase-3-extract-shared-data-loading-into-content-planner)
  - [Phase 4: Move prompts into subdirectories](#phase-4-move-prompts-into-subdirectories)
  - [Phase 5: Update GitHub Actions workflows](#phase-5-update-github-actions-workflows)
  - [Phase 6: Cleanup and burn-in](#phase-6-cleanup-and-burn-in)
- [Part 2: TikTok Integration](#part-2-tiktok-integration)
  - [Phase 7: Migrate TikTok research + rename repo](#phase-7-migrate-tiktok-research--rename-repo)
  - [Phase 8: Shared context layer + workflow restructure](#phase-8-shared-context-layer--workflow-restructure)
  - [Phase 9: Carousel rendering engine](#phase-9-carousel-rendering-engine)
  - [Phase 10: Content generation pipeline](#phase-10-content-generation-pipeline)
  - [Phase 11: Posting via Publer](#phase-11-posting-via-publer)
  - [Phase 12: Analytics + feedback loop](#phase-12-analytics--feedback-loop)
- [Post-MVP Enhancements](#post-mvp-enhancements)
  - [Phase 13: Video pipeline](#phase-13-video-pipeline)
  - [Phase 14: Engagement automation](#phase-14-engagement-automation)
  - [Phase 15: Remotion migration](#phase-15-remotion-migration)
- [Reference](#reference)
  - [Open Decisions](#open-decisions)
  - [Pre-Build Parallel Track](#pre-build-parallel-track)
  - [Publer Decision Record](#publer-decision-record)
  - [Cadence Ramp Plan](#cadence-ramp-plan)
  - [Cost Summary](#cost-summary)
  - [Effort Summary](#effort-summary)
  - [Reuse from Pinterest Pipeline](#reuse-from-pinterest-pipeline)
  - [Risks & Mitigations](#risks--mitigations)
  - [Environment Variables](#environment-variables)
  - [What Success Looks Like](#what-success-looks-like)
  - [What This Enables](#what-this-enables)

---

## Context

The current `slated-content-engine` (formerly `pinterest-pipeline`) is a vertically integrated Pinterest automation being restructured into a multi-channel content engine that can serve Pinterest, TikTok, and eventually paid channels. Rather than building separate pipelines per channel, we're extracting shared data-loading utilities, content memory, and blog generation into a shared context layer, with each channel running independent planning and workflows informed by cross-channel data.

**Decisions made:**
- Monorepo structure (`src/shared/`, `src/pinterest/`, `src/tiktok/`, etc.)
- Incremental migration — Pinterest pipeline stays live and posting daily throughout
- Restructure first, verify Pinterest works, then build TikTok
- Rename repo to `slated-content-engine` after restructure is stable
- TikTok content is independent from blogs — each channel owns its own topic selection, format, and creative decisions, informed by shared cross-channel context
- Paid channels are a future concern, not addressed in this plan

---

## Target Architecture

```
Layer 1: Shared Context Layer (src/shared/)
  ├── Data-loading utilities: strategy context, content memory, seasonal windows
  ├── Cross-channel content memory with channel attribution
  ├── Strategy + seasonal calendar + keyword targets
  ├── Analytics collection runs before planning (collect-analytics.yml)
  └── No unified topic plan — each channel plans independently

Layer 2: Blog Generation & Deployment (src/shared/)
  ├── Generates MDX blog posts (Pinterest asset, not shared)
  └── Deploys to goslated.com

Layer 3: Channel-Specific Workflows (fully independent per channel)
  ├── src/pinterest/ — pin planning, creation, posting, analytics
  └── src/tiktok/    — carousel/video planning, creation, posting, analytics
  Each channel reads shared context + its own channel-specific context,
  then runs its own planning call with its own prompt.
```

### Multi-Channel Planning Design

Each channel runs its own independent planning call with its own prompt, constraints, and output format. There is no shared topic plan or unified content strategy step. Instead, a **shared context layer** ensures every planner sees the same fresh data:

1. **Shared Context Layer** (`src/shared/`) — Provides data-loading utilities that all planners use: `load_strategy_context()` (brand voice, keywords, seasonal calendar), `generate_content_memory_summary()` (cross-channel content history with channel attribution and performance data), and `get_current_seasonal_window()`. A dedicated `collect-analytics.yml` workflow refreshes this data before any planner runs.

2. **Channel-Specific Planning** (e.g., `src/pinterest/generate_weekly_plan.py`, `src/tiktok/generate_weekly_plan.py`) — Each channel loads shared context, adds its own channel-specific context (Pinterest: board structure; TikTok: attribute taxonomy), and makes its own Claude call with its own prompt. Cross-channel awareness is informative, not prescriptive — planners see what other channels have published and how it performed, then make independent decisions.

---

## Target Directory Structure

```
slated-content-engine/                # Renamed from pinterest-pipeline
│
├── src/
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── paths.py                  # Centralized PROJECT_ROOT, DATA_DIR, etc.
│   │   ├── config.py                 # Models, costs, timeouts, batch sizes
│   │   ├── content_planner.py        # NEW: shared data-loading utilities (strategy context, content memory, seasonal windows)
│   │   ├── content_memory.py         # Consolidated from 2 implementations
│   │   ├── analytics_utils.py        # Extracted: load_content_log, aggregation
│   │   ├── blog_generator.py         # Moved from src/
│   │   ├── blog_deployer.py          # Moved from src/
│   │   ├── generate_blog_posts.py    # Moved from src/
│   │   ├── image_cleaner.py          # Moved from src/
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   ├── safe_get.py           # Moved from src/utils/
│   │   │   ├── strategy_utils.py     # Moved from src/utils/
│   │   │   ├── image_utils.py        # Moved from src/utils/
│   │   │   ├── content_log.py        # Moved from src/utils/
│   │   │   └── plan_utils.py         # Moved from src/utils/
│   │   └── apis/
│   │       ├── __init__.py
│   │       ├── claude_api.py          # Moved from src/apis/
│   │       ├── openai_chat_api.py     # Moved from src/apis/
│   │       ├── sheets_api.py          # Moved from src/apis/
│   │       ├── github_api.py          # Moved from src/apis/
│   │       ├── gcs_api.py             # Moved from src/apis/
│   │       ├── drive_api.py           # Moved from src/apis/
│   │       ├── slack_notify.py        # Moved from src/apis/
│   │       └── image_gen.py           # Moved from src/apis/
│   │
│   ├── pinterest/
│   │   ├── __init__.py
│   │   ├── generate_weekly_plan.py   # Reads shared context + Pinterest-specific context, single-shot Claude call
│   │   ├── generate_pin_content.py   # Moved from src/
│   │   ├── pin_assembler.py          # Moved from src/
│   │   ├── post_pins.py              # Moved from src/
│   │   ├── pull_analytics.py         # Moved from src/
│   │   ├── weekly_analysis.py        # Moved from src/
│   │   ├── monthly_review.py         # Moved from src/
│   │   ├── publish_content_queue.py  # Moved from src/
│   │   ├── plan_validator.py         # Moved from src/
│   │   ├── regen_content.py          # Moved from src/
│   │   ├── regen_weekly_plan.py      # Moved from src/
│   │   ├── setup_boards.py           # Moved from src/
│   │   ├── token_manager.py          # Moved from src/
│   │   ├── redate_schedule.py        # Moved from src/
│   │   └── apis/
│   │       ├── __init__.py
│   │       └── pinterest_api.py      # Moved from src/apis/
│   │
│   └── tiktok/                       # Built in Phase 9
│       └── ...
│
├── prompts/
│   ├── shared/
│   │   ├── blog_post_guide.md        # Moved from prompts/
│   │   ├── blog_post_listicle.md
│   │   ├── blog_post_recipe.md
│   │   ├── blog_post_weekly_plan.md
│   │   └── image_prompt.md
│   ├── pinterest/
│   │   ├── weekly_plan.md            # Moved from prompts/
│   │   ├── weekly_plan_replace.md
│   │   ├── pin_copy.md
│   │   ├── weekly_analysis.md
│   │   └── monthly_review.md
│   └── tiktok/                       # Built in Phase 10
│       └── ...
│
├── strategy/
│   ├── current-strategy.md           # Shared (as-is)
│   ├── brand-voice.md
│   ├── product-overview.md
│   ├── keyword-lists.json
│   ├── negative-keywords.json
│   ├── cta-variants.json
│   ├── seasonal-calendar.json
│   ├── pinterest/
│   │   └── board-structure.json      # Moved from strategy/
│   ├── tiktok/                       # Migrated from tiktok-automation repo
│   │   └── ...
│   └── reference/                    # As-is
│
├── templates/
│   ├── blog/                         # As-is
│   ├── pins/                         # As-is (Pinterest-specific)
│   └── tiktok/                       # Built in Phase 9
│
├── docs/
│   └── research/
│       └── tiktok/                   # Migrated from tiktok-automation repo
│
├── .github/workflows/                # Updated module paths
├── data/                             # Runtime data (gitignored, as-is)
├── analysis/                         # As-is
├── memory-bank/                      # As-is
├── tests/                            # Updated imports
└── render_pin.js                     # As-is
```

---

## Part 1: Restructure (Pinterest stays live throughout)

### Phase 1: Create structure, move purely shared code

**Goal:** Establish `src/shared/` and `src/pinterest/` directories. Move files that have zero Pinterest-specific logic. Update imports in moved files. No behavior changes.

**Effort:** 4-6 hours | **Risk:** LOW

#### What moves where

**To `src/shared/paths.py`** (new, replaces `src/paths.py`):
- Centralized path constants — all `Path(__file__).parent.parent` patterns switch to imports from here
  ```python
  from pathlib import Path
  PROJECT_ROOT = Path(__file__).parent.parent.parent
  DATA_DIR = PROJECT_ROOT / "data"
  STRATEGY_DIR = PROJECT_ROOT / "strategy"
  ANALYSIS_DIR = PROJECT_ROOT / "analysis"
  PROMPTS_DIR = PROJECT_ROOT / "prompts"
  TEMPLATES_DIR = PROJECT_ROOT / "templates"
  ```

**To `src/shared/config.py`** (moved from `src/config.py`):
- Models, costs, timeouts, batch sizes — no Pinterest-specific logic

**To `src/shared/apis/`:**
- `src/apis/claude_api.py`
- `src/apis/openai_chat_api.py`
- `src/apis/sheets_api.py`
- `src/apis/github_api.py`
- `src/apis/gcs_api.py`
- `src/apis/drive_api.py`
- `src/apis/slack_notify.py`
- `src/apis/image_gen.py`

**To `src/shared/utils/`:**
- `src/utils/safe_get.py`
- `src/utils/strategy_utils.py`
- `src/utils/image_utils.py`
- `src/utils/content_log.py`
- `src/utils/plan_utils.py`

**To `src/shared/`:**
- `src/image_cleaner.py`
- `src/blog_generator.py`
- `src/blog_deployer.py`
- `src/generate_blog_posts.py`

**To `src/pinterest/apis/`:**
- `src/apis/pinterest_api.py`

**To `src/pinterest/`:**
- `src/token_manager.py`
- `src/generate_pin_content.py`
- `src/pin_assembler.py`
- `src/post_pins.py`
- `src/pull_analytics.py`
- `src/setup_boards.py`
- `src/regen_content.py`
- `src/plan_validator.py`
- `src/redate_schedule.py`

**Stays in `src/` for now (mixed shared+Pinterest logic, split in later phases):**
- `src/generate_weekly_plan.py` (Phase 3)
- `src/weekly_analysis.py` (Phase 2)
- `src/monthly_review.py` (Phase 2)
- `src/regen_weekly_plan.py` (Phase 3)
- `src/publish_content_queue.py` (Phase 2)

**One-off scripts (evaluate for deletion):**
- `src/recover_w9_pins.py` — one-time recovery script, likely dead code. Delete if confirmed.

#### Key implementation details

1. **Create backward-compat shim files** at old locations. Example — `src/image_cleaner.py` becomes:
   ```python
   # Backward-compat shim — remove in Phase 6
   from src.shared.image_cleaner import *  # noqa: F401,F403
   ```
   This lets unmoved files and GitHub Actions workflows keep working during migration.

2. **Update all imports in moved files** — every `from src.apis.X` becomes `from src.shared.apis.X`, etc. Every inline `PROJECT_ROOT = Path(__file__).parent.parent` switches to `from src.shared.paths import PROJECT_ROOT`.

3. **Create `__init__.py` files** in `src/shared/`, `src/shared/apis/`, `src/shared/utils/`, `src/pinterest/`, `src/pinterest/apis/`.

4. **`src/utils/content_memory.py`** stays put for now — it's consolidated in Phase 2.

#### Verify
- `python -c "from src.shared.apis.claude_api import ClaudeAPI; print('OK')"` for every moved module
- Shims work: `python -c "from src.apis.claude_api import ClaudeAPI; print('OK')"`
- `python -m pytest tests/`

---

### Phase 2: Extract content memory and analytics utilities

**Goal:** Consolidate the duplicated `generate_content_memory_summary()` implementations. Extract generic analytics functions into shared utilities. Move remaining unmixed files.

**Effort:** 3-4 hours | **Risk:** MEDIUM

#### What gets created

1. **`src/shared/analytics_utils.py`** — extracted from `pull_analytics.py` and `src/utils/content_log.py`:
   - `load_content_log()` — reads `content-log.jsonl`
   - `save_content_log()` — writes updated entries
   - `compute_derived_metrics()` — save_rate, click_through_rate, etc.
   - `aggregate_by_dimension()` — generic grouping function
   - Channel-agnostic: works with any content log entries regardless of source platform

2. **`src/shared/content_memory.py`** — consolidated from two implementations:
   - `generate_content_memory_summary()` — the canonical version (based on the more comprehensive 380-line version from `generate_weekly_plan.py` line 522)
   - Produces 7 sections: recent topics, all blog posts, pillar mix, keyword frequency, images used, fresh pin candidates, treatment tracker
   - Replaces `src/utils/content_memory.py`

#### What moves

- `src/weekly_analysis.py` → `src/pinterest/weekly_analysis.py`
- `src/monthly_review.py` → `src/pinterest/monthly_review.py`
- `src/publish_content_queue.py` → `src/pinterest/publish_content_queue.py`
- Delete `src/utils/content_memory.py` (replaced by `src/shared/content_memory.py`)
- Delete `src/utils/content_log.py` (absorbed into `src/shared/analytics_utils.py`)

#### Key risk

Two different `generate_content_memory_summary()` implementations exist with slightly different field names and formatting. Must consolidate without changing output. **Mitigation:** Diff output against a saved baseline before merging.

#### Verify
- Content memory output identical to previous version (diff against baseline)
- `python -m pytest tests/`
- Shims still work for unmoved references

---

### Phase 3: Extract shared data-loading into content planner

**Goal:** Extract generic data-loading functions from `generate_weekly_plan.py` into `src/shared/content_planner.py`. The Pinterest planning call itself stays as a single-shot Claude call — no two-step split.

**Effort:** 8-12 hours | **Risk:** HIGH (largest and most complex phase)

#### What gets created

1. **`src/shared/content_planner.py`** — shared data-loading utilities:
   - Extracted from `generate_weekly_plan.py`: `load_strategy_context()`, `load_content_memory()`, `load_latest_analysis()`, `get_current_seasonal_window()`
   - Loads shared strategy files (brand voice, keywords, seasonal calendar, negative keywords)
   - Does NOT contain any planning logic or Claude calls — purely data loading
   - Designed so any channel's planner can call these functions to get shared context

#### What moves
- `src/generate_weekly_plan.py` → `src/pinterest/generate_weekly_plan.py` (with shared data-loading extracted to `content_planner.py`)
- `src/regen_weekly_plan.py` → `src/pinterest/regen_weekly_plan.py`

#### Key risk

Extracting data-loading functions changes import paths and function boundaries. **Mitigation:** Verify Pinterest planning output is identical before and after extraction. No changes to the Claude call itself.

#### Verify
- Generated plan structurally equivalent to previous output (same blog topics, same pin count, same constraint compliance)
- All constraint validation passes
- Retry/validation loop works
- `python -m pytest tests/`

---

### Phase 4: Move prompts into subdirectories

**Goal:** Reorganize `prompts/` into `prompts/shared/` and `prompts/pinterest/`.

**Effort:** 2-3 hours | **Risk:** LOW

#### What moves

**To `prompts/shared/` (5 files):**
- `blog_post_guide.md`, `blog_post_listicle.md`, `blog_post_recipe.md`, `blog_post_weekly_plan.md`
- `image_prompt.md`
- ~~`content_strategy.md`~~ **Cancelled.** No unified planning prompt needed — each channel uses its own planning prompt.

**To `prompts/pinterest/` (5 files):**
- `weekly_plan.md`, `weekly_plan_replace.md`
- `pin_copy.md`
- `weekly_analysis.md`
- `monthly_review.md`

#### Implementation details

**All `load_prompt_template()` calls are in ONE file:** `src/shared/apis/claude_api.py`. No other file calls this method.

The method (line 91) resolves paths via `PROMPTS_DIR / template_name`. Since `PROMPTS_DIR` points to `{PROJECT_ROOT}/prompts`, changing `"weekly_plan.md"` to `"pinterest/weekly_plan.md"` resolves to `prompts/pinterest/weekly_plan.md` automatically. No change needed to the method implementation.

**Exact change map (8 call sites, all in `claude_api.py`):**

| Line | Current | New | Method |
|------|---------|-----|--------|
| 158 | `"weekly_plan.md"` | `"pinterest/weekly_plan.md"` | `generate_weekly_plan()` |
| 226 | `"pin_copy.md"` | `"pinterest/pin_copy.md"` | `generate_pin_copy()` |
| 312-316 | `"blog_post_recipe.md"`, `"blog_post_weekly_plan.md"`, `"blog_post_guide.md"`, `"blog_post_listicle.md"` | `"shared/blog_post_recipe.md"`, `"shared/blog_post_weekly_plan.md"`, `"shared/blog_post_guide.md"`, `"shared/blog_post_listicle.md"` | `generate_blog_post()` template_map |
| 387 | `"image_prompt.md"` | `"shared/image_prompt.md"` | `generate_image_prompt()` |
| 461 | `"weekly_plan_replace.md"` | `"pinterest/weekly_plan_replace.md"` | `generate_replacement_posts()` |
| 551 | `"weekly_analysis.md"` | `"pinterest/weekly_analysis.md"` | `generate_weekly_analysis()` |
| 615 | `"monthly_review.md"` | `"pinterest/monthly_review.md"` | `generate_monthly_review()` |
| 882 | `"weekly_plan.md"` | `"pinterest/weekly_plan.md"` | `__main__` smoke test |

**Also update:** Line 877 `PROMPTS_DIR.glob("*.md")` in the `__main__` smoke test — should become `PROMPTS_DIR.glob("**/*.md")` since prompts are now in subdirectories.

**No shims or backward-compat needed.** Prompt files are read from disk at runtime, not imported by Python. Moving them is a straight `git mv` with no backward-compat concern.

#### Verify
- Each prompt loads: `python -c "from src.shared.apis.claude_api import ClaudeAPI; c = ClaudeAPI.__new__(ClaudeAPI); print(len(c.load_prompt_template('shared/image_prompt.md')))"` (repeat for all 10)
- No `.md` files remain in `prompts/` root (all should be in subdirectories)
- All tests pass (`python -m pytest tests/`)
- No `load_prompt_template()` calls use bare filenames without a subdirectory prefix
- Grep for hardcoded prompt filenames: `grep -rn "blog_post_recipe\|weekly_plan\|pin_copy\|image_prompt\|monthly_review\|weekly_analysis" src/ --include="*.py"` — should only show paths with `shared/` or `pinterest/` prefix

---

### Phase 5: Update GitHub Actions workflows

**Goal:** Update all `python -m` invocations in workflow files to use new module paths. Remove dependency on shim files.

**Effort:** 2-3 hours | **Risk:** MEDIUM

#### Changes per workflow

| Workflow | `python -m` path changes |
|----------|--------------------------|
| `weekly-review.yml` (5) | `src.token_manager` → `src.pinterest.token_manager`, `src.pull_analytics` → `src.pinterest.pull_analytics`, `src.utils.content_memory` → `src.shared.content_memory`, `src.weekly_analysis` → `src.pinterest.weekly_analysis`, `src.generate_weekly_plan` → `src.pinterest.generate_weekly_plan` |
| `generate-content.yml` (4) | `src.token_manager` → `src.pinterest.token_manager`, `src.generate_blog_posts` → `src.shared.generate_blog_posts`, `src.generate_pin_content` → `src.pinterest.generate_pin_content`, `src.publish_content_queue` → `src.pinterest.publish_content_queue` |
| `deploy-and-schedule.yml` (1) | `src.blog_deployer` → `src.shared.blog_deployer` |
| `promote-and-schedule.yml` (3) | `src.token_manager` → `src.pinterest.token_manager`, `src.blog_deployer` → `src.shared.blog_deployer`, `src.redate_schedule` → `src.pinterest.redate_schedule` |
| `daily-post-morning.yml` (2) | `src.token_manager` → `src.pinterest.token_manager`, `src.post_pins` → `src.pinterest.post_pins` |
| `daily-post-afternoon.yml` (2) | `src.token_manager` → `src.pinterest.token_manager`, `src.post_pins` → `src.pinterest.post_pins` |
| `daily-post-evening.yml` (2) | `src.token_manager` → `src.pinterest.token_manager`, `src.post_pins` → `src.pinterest.post_pins` |
| `monthly-review.yml` (3) | `src.token_manager` → `src.pinterest.token_manager`, `src.pull_analytics` → `src.pinterest.pull_analytics`, `src.monthly_review` → `src.pinterest.monthly_review` |
| `regen-plan.yml` (1) | `src.regen_weekly_plan` → `src.pinterest.regen_weekly_plan` |
| `regen-content.yml` (1) | `src.regen_content` → `src.pinterest.regen_content` |
| `regen-blogs-only.yml` (1) | `src.generate_blog_posts` → `src.shared.generate_blog_posts` |
| `setup-boards.yml` (2) | `src.token_manager` → `src.pinterest.token_manager`, `src.setup_boards` → `src.pinterest.setup_boards` |
| `recover-w9-pins.yml` (1) | `src.recover_w9_pins` — delete workflow (header says "DELETE after W9 pins posted by Mar 4, 2026") or update to `src.pinterest.recover_w9_pins` if kept |

**Total: 28 `python -m` changes across 13 workflows** (or 27 if `recover-w9-pins.yml` is deleted).

#### Changes per action file

| Action | Changes |
|--------|---------|
| `.github/actions/notify-failure/action.yml` (1) | `python -m src.apis.slack_notify` → `python -m src.shared.apis.slack_notify` — this single change fixes failure notifications for all 13+ workflows that use it |
| `.github/actions/setup-pipeline/action.yml` | No changes needed — no `src/` references |
| `.github/actions/commit-data/action.yml` | No changes needed — only references `data/` and `analysis/` |

#### Inline Python imports in workflows

| Workflow | Line | Change |
|----------|------|--------|
| `year-wrap-reminder.yml` | 42 | `from src.apis.slack_notify import SlackNotify` → `from src.shared.apis.slack_notify import SlackNotify` |

#### Notes
- `src.utils.content_memory` → `src.shared.content_memory` is the only path that changes structurally (drops `utils/` level)
- Several modules accept CLI args that must pass through: `blog_deployer preview|promote`, `post_pins morning|afternoon|evening`, `pull_analytics 30`, `redate_schedule "$PIN_START_DATE"`. All shims use `runpy.run_module(..., alter_sys=True)` which preserves `sys.argv`.
- After Phase 5, shims are no longer invoked by any workflow — Phase 6 can safely delete them

#### Verify
- Trigger each workflow via `workflow_dispatch`
- Monitor daily posting for one full day
- Check cron schedules unchanged

---

### Phase 6: Cleanup

**Goal:** Remove backward-compat shims, update docs.

**Effort:** 2-3 hours | **Risk:** LOW

#### Cleanup

1. Delete all shim files from `src/` and `src/apis/` and `src/utils/`
2. Delete empty `src/apis/` and `src/utils/` directories
3. Verify no imports reference old paths: `grep -r "from src\." src/ --include="*.py" | grep -v "src.shared\|src.pinterest"`
4. Update `CLAUDE.md` Key Paths section with new directory structure
5. Update `memory-bank/architecture/architecture-data-flows.md`
6. Delete `src/recover_w9_pins.py` if confirmed dead

#### Verify

- All 3 daily posting slots fire successfully (1 full day, no shim safety net)
- If something breaks, it will be an immediate import error — restore the shim file and investigate
- Phase 7 and TikTok pre-build can start in parallel once posting is confirmed (see execution-strategy.md "Parallel Work After Phase 5")

---

## Part 2: TikTok Integration

### Phase 7: Migrate TikTok research + rename repo

**Goal:** Bring TikTok research and strategy docs into the mono-repo. Rename the repo.

**Effort:** 2-3 hours | **Risk:** LOW

#### Migrate TikTok research

From `tiktok-automation/` into the mono-repo:

| Source | Destination |
|--------|-------------|
| `tiktok-automation-research/*.md` (7 files) | `docs/research/tiktok/` |
| `tiktok-carousel-automation-plan.md` | `docs/research/tiktok/` |
| `memory-bank/Research/*.md` (18 files) | `docs/research/tiktok/community/` |
| `memory-bank/archetypes.md` | `strategy/tiktok/archetypes.md` |
| `memory-bank/brand-guidelines.md` | Already exists at `strategy/brand-voice.md` — diff and merge |
| `memory-bank/slated-product-overview.md` | Already exists at `strategy/product-overview.md` — diff and merge |

#### Rename repo

**Pre-rename checklist:**
1. Update `src/apps-script/trigger.gs` line 71:
   ```javascript
   // BEFORE:
   var repo = "bradenpan/slated-pinterest-bot";
   // AFTER:
   var repo = "bradenpan/slated-content-engine";
   ```
2. Deploy the updated Apps Script to Google Sheets

**Safe to rename because:**
- All GitHub Actions workflows use dynamic `${{ github.repository }}` — no hardcoded repo name
- Blog deployment uses `GOSLATED_REPO` env var (points to the goslated.com repo, not this one)
- No Vercel config references this repo

**After rename on GitHub:**
- Update git committer name in `.github/actions/commit-data/action.yml` (cosmetic)
- Update `package.json` name field (cosmetic)
- Update local clone remote: `git remote set-url origin git@github.com:bradenpan/slated-content-engine.git`

#### Move `strategy/board-structure.json` → `strategy/pinterest/board-structure.json`

This is Pinterest-specific and should live under a channel subdirectory now that we have TikTok strategy alongside it.

#### Verify
- Apps Script triggers a test workflow via `repository_dispatch`
- Daily posting continues uninterrupted
- All research docs accessible in new locations

---

### Phase 8: Shared context layer + workflow restructure

**Goal:** Make the shared context layer channel-aware and restructure the weekly automation so cross-channel data is fresh when planners run. This enables TikTok (and future channels) to plug into the same shared data and workflow infrastructure.

**Effort:** 5-7 hours | **Risk:** LOW-MEDIUM

**Context:** Phase 3 extracted shared data-loading functions into `src/shared/content_planner.py`. The shared context layer works but is Pinterest-specific in places (hardcoded board structure loading, no channel tagging on content log entries). Before TikTok can use this infrastructure, the shared layer needs to be channel-agnostic and analytics collection needs to run before any channel-specific planning.

#### What gets built

1. **Content log: add channel tagging** — Add `channel` field to content log entries. Backfill existing entries as `"pinterest"`. Update `content_log.py` write functions to accept and include channel. Update `blog_deployer.py` and `post_pins.py` to tag entries with `"pinterest"`. Backward-compatible: missing `channel` field defaults to `"pinterest"` on read.

2. **Content memory: channel-aware output** — The summary generated by `content_memory.py` includes channel attribution on entries — so a planner reading the summary can distinguish "this topic was covered on Pinterest and got 400 saves" from "this topic was covered on TikTok and got 50K views." Function signature gains an optional `channel` parameter for filtering, but defaults to showing all channels.

3. **Content planner: remove Pinterest hardcoding** — `load_strategy_context()` currently hardcodes loading `pinterest/board-structure.json`. Refactor to load only shared strategy files by default (brand voice, keywords, seasonal calendar, negative keywords). Channel-specific planners load their own structure files directly.

4. **Content log utility: generalize idempotency check** — Add `is_content_posted(content_id, channel)` that checks for the appropriate platform ID field (`pinterest_pin_id`, `publer_post_id`, etc.). Keep `is_pin_posted()` as a backward-compatible wrapper.

5. **Workflow restructure: split analytics from planning** — Extract analytics pull + content memory refresh from `weekly-review.yml` into a new `collect-analytics.yml` workflow. `collect-analytics.yml` runs Monday ~5:30am ET: pulls analytics from all active channels, refreshes content memory, commits updated data files. Rename `weekly-review.yml` → `pinterest-weekly-review.yml`, runs Monday ~6:00am ET after `collect-analytics` completes (via `workflow_run` trigger or time offset). Contains only: weekly analysis → plan generation → Sheet write → Slack notify. This pattern is ready for `tiktok-weekly-review.yml` to plug in later (Phase 10).

6. **Strategy file cleanup** — Move `strategy/tiktok/archetypes.md` and `strategy/tiktok/brand-guidelines.md` to `strategy/` root — they're brand-level docs, not TikTok-specific.

#### What does NOT change
- Pinterest planning logic (`generate_weekly_plan.py`) — untouched
- `ClaudeAPI.generate_weekly_plan()` — untouched
- `prompts/pinterest/weekly_plan.md` — untouched
- Plan validator — stays Pinterest-specific in `src/pinterest/`
- No new prompts or Claude calls
- Pinterest weekly output is identical — same plan structure, same Sheet output

#### Key risk

Workflow restructure changes automation timing (planning runs before analytics completes). **Mitigation:** Use `workflow_run` trigger or sufficient time offset. Test end-to-end before merging.

#### Verify
- `collect-analytics.yml` runs cleanly, pulls Pinterest data, refreshes content memory
- `pinterest-weekly-review.yml` runs after collection, produces identical plan output
- `python -m pytest tests/`
- Existing content log entries without `channel` field are treated as `"pinterest"` by default
- Content memory summary includes channel attribution on entries
- End-to-end: Monday automation produces the same Weekly Review Sheet output as before

---

### Phase 9: Carousel rendering engine

**Status:** COMPLETE (2026-03-04)

**Goal:** Render multi-slide TikTok carousels from HTML/CSS templates. No external APIs needed — purely local infrastructure.

**Effort:** 35-50 hours | **Risk:** LOW

> **PLACEHOLDER — must fix before first TikTok post:**
> All CTA slide templates use `{{handle}}` with a default value of `@slated`. The actual TikTok handle has not been decided yet (see Open Decision #2 below). When the handle is finalized:
> 1. The content generation pipeline (Phase 10) should pass the correct handle to `carousel_assembler.render_carousel()` — no template changes needed, the handle is a variable.
> 2. Update Open Decision #2 to record the final choice.
> 3. If the handle differs from `@slated`, grep for `@slated` in any test fixtures or sample data and update them.

#### 1. Carousel HTML/CSS templates (4 visual families)

**Dimensions:** 1080 x 1920px (9:16 vertical, TikTok Photo Mode standard)

**Safe zones** (avoid TikTok UI overlap):
- Top: 100px
- Left/Right: 60px each
- Bottom: 280px (caption + button overlay)

**Template families** (rotated to prevent visual fatigue):

| Family | Style | Best for |
|--------|-------|----------|
| `clean-educational` | Light background, bold dark headlines, numbered slides | Listicles, how-tos, tips |
| `dark-bold` | High-contrast white/accent on dark, dramatic | Bold claims, contrarian takes |
| `photo-forward` | Real photo background with semi-transparent text overlay (70% image) | Recipes, food photography, transformations |
| `comparison-grid` | Split panels, structured data, balanced layout | Before/after, comparisons, pros/cons |

Each family has 3 slide types:
- **Hook slide** — headline + subtitle + background. Captures attention.
- **Content slide** — headline + body text + slide number indicator. The substance.
- **CTA slide** — call-to-action + @handle + primary/secondary CTA text.

**File structure:**
```
templates/tiktok/carousels/
├── clean-educational/
│   ├── hook-slide.html
│   ├── content-slide.html
│   ├── cta-slide.html
│   └── styles.css
├── dark-bold/
│   └── ...
├── photo-forward/
│   └── ...
├── comparison-grid/
│   └── ...
└── shared/
    ├── base-styles.css          # Brand colors, fonts, safe zone margins
    └── assets/
        ├── logo.png
        └── icons/
```

**Effort:** 15-20 hours

#### 2. ~~`render_carousel.js`~~ — Not needed (reuses `render_pin.js`)

The existing `render_pin.js` already supports batch rendering via `--manifest` mode with configurable `width`/`height` per job. No new Node.js script was needed — `carousel_assembler.py` builds a manifest JSON with 1080×1920 dimensions and calls `render_pin.js --manifest` directly. All slides render in a single Puppeteer browser session.

**Effort:** ~~10-15 hours~~ 0 hours (reused existing infrastructure)

#### 3. `src/tiktok/carousel_assembler.py`

Orchestrates the rendering pipeline:
- Select template family based on spec
- Inject content variables (headline, body, CTA text, image URLs) into HTML
- Convert images to base64 data URIs (via shared `image_to_data_uri()` in `src/shared/utils/image_utils.py`)
- Write temporary HTML files
- Call `render_pin.js --manifest` via subprocess (batch mode, one browser session)
- Validate output PNGs (>10KB)
- Return list of slide image paths

**Effort:** 10-15 hours

#### Verify
- Render sample carousels across all 4 template families
- Verify dimensions (1080x1920), file sizes (>10KB), readability at mobile scale
- Test with 3, 5, 7, and 10 slide counts
- Visual QA: text within safe zones, no clipping

---

### Phase 10: Content generation pipeline

**Goal:** Generate 7-21 carousel specs per week via Claude, render them, and publish to Google Sheets for human review. Also update Pinterest prompts to surface cross-channel context now that two channels exist.

**Effort:** 60-83 hours | **Risk:** MEDIUM

#### 4. Attribute taxonomy (`strategy/tiktok/attribute-taxonomy.json`)

Every TikTok post is tagged with attributes for the feedback loop:

```json
{
  "topics": ["grocery_savings", "meal_prep", "weeknight_dinners", "picky_eaters",
             "kitchen_hacks", "batch_cooking", "family_meals", "seasonal_recipes"],
  "angles": ["contrarian", "transformation", "social_proof", "problem_solution",
             "comparison", "lifestyle", "data_driven"],
  "structures": ["listicle", "tutorial", "comparison", "story_arc",
                  "problem_solution", "before_after", "data_dump"],
  "hook_types": ["curiosity_gap", "bold_claim", "relatable_problem", "proof_first",
                  "question", "shocking_stat", "mistake"],
  "slide_counts": [3, 5, 7, 8, 10],
  "visual_templates": ["clean_educational", "dark_bold", "photo_forward", "comparison_grid"]
}
```

**Allocation strategy:**
- 65% exploit: weight toward high-performing attribute combinations
- 35% explore: underrepresented or untested combinations
- Cold-start mode (first 2-3 weeks): even distribution across all attributes

**Effort:** 3-5 hours

#### 5. `src/tiktok/compute_attribute_weights.py`

Deterministic Python — no LLM calls. Reads performance data + taxonomy, outputs 7-21 allocated slots:
- Load `data/tiktok/performance-summary.json` (or use cold-start defaults)
- For each attribute dimension, compute performance-weighted probabilities
- Allocate N slots with 65/35 exploit/explore split
- Enforce minimums: every attribute value gets at least 1 post per 3 weeks
- Output: `data/tiktok/attribute-weights-W{N}.json`

**Effort:** 12-15 hours

#### 6. Claude prompt templates

**`prompts/tiktok/weekly_plan.md`** — 6-section prompt:
1. Role: "Generate N TikTok carousel specs for Slated"
2. Attribute taxonomy: full set of available values
3. Pre-computed allocations: the N topic+structure slots from `compute_attribute_weights.py`
4. Performance data: per-attribute save rate, share rate, top/bottom posts
5. Content constraints: brand voice, no repeats from last 2 weeks, variety rules
6. Cold-start handling: if <3 weeks of data, use even distribution

**`prompts/tiktok/carousel_copy.md`** — Per-carousel slide text + caption generation:
- Hook rules: capture attention in 1.5-3 seconds of reading, text overlay required
- TikTok-native voice: conversational, not blog-like, save-worthy
- Caption: max 2,200 chars, 2-3 searchable keywords, 3-5 hashtags
- "Save this for later" encouragement (high-weight algorithm signal)

**`prompts/tiktok/image_prompt.md`** — Adapt from Pinterest `image_prompt.md`:
- Food photography style for photo-forward template
- Adjust for vertical 1080x1920 composition

**Effort:** 13-18 hours

#### 7. `src/tiktok/generate_weekly_plan.py`

Independent TikTok planner that reads shared context and makes its own planning decisions:

```python
def generate_plan():
    # Load shared context (brand voice, keywords, seasonal calendar)
    strategy_context = content_planner.load_strategy_context()

    # Load cross-channel content memory (already fresh from collect-analytics)
    # Includes Pinterest performance data with channel attribution
    content_memory = content_memory_mod.generate_content_memory_summary()

    # Load TikTok-specific context
    attribute_taxonomy = load_attribute_taxonomy()
    weights = compute_attribute_weights.compute(week_number)

    # Generate TikTok carousel specs via Claude — independent planning call
    carousel_specs = claude.generate_tiktok_plan(
        strategy_context=strategy_context,
        content_memory=content_memory,
        attribute_weights=weights,
        taxonomy=attribute_taxonomy
    )

    # Validate and write to Sheets + JSON
    write_to_sheets(carousel_specs)
    save_plan_json(carousel_specs)
    slack_notify("TikTok plan ready for review")
```

**Key design point:** The TikTok planner reads shared context and cross-channel content memory, sees what's been published on other channels and how it performed, and makes independent planning decisions. There is no shared topic plan — the planner uses shared *data* (strategy, content history, performance metrics) but owns its own topic selection, driven by TikTok-specific signals (hooks, trends, attribute weights, explore/exploit ratio).

**Effort:** 15-20 hours

#### 8. `src/tiktok/generate_carousels.py`

Full orchestrator for rendering a week's carousels:

For each approved carousel spec:
1. Generate slide text + caption via Claude (`carousel_copy.md`)
2. Generate images via DALL-E/Replicate (for photo-forward template; skip for text-only templates)
3. Strip C2PA metadata from AI-generated images (reduces AI detection risk — see `docs/research/tiktok/07-ai-content-detection-technical-report.md`)
4. Call `carousel_assembler.py` to render all slides
5. **Post-render cleaning on output PNGs:** Run `_optimize_image()` (Pillow re-save, JPEG fallback if over 500KB) + `clean_image()` from `src/shared/image_cleaner.py` (strips Puppeteer/Chromium metadata fingerprints, adds subtle noise to defeat pixel-level classifiers). Same pattern as `pin_assembler.py` lines 496-501. This must be added to `carousel_assembler.py` at build time — it is NOT there yet (Phase 9 deferred this to Phase 10).
6. Upload slide PNGs to GCS
7. Write to Content Queue sheet with `IMAGE()` thumbnail formulas

**Effort:** 20-25 hours

#### 9. `src/tiktok/publish_content_queue.py`

Write generated carousels to the Google Sheet Content Queue tab:
- One row per carousel
- Thumbnail via `IMAGE()` formula pointing to GCS
- All 6 attribute columns populated
- Status column: `pending_review`
- Adapt from Pinterest `publish_content_queue.py`

**Effort:** 8-10 hours

#### 10. Apps Script trigger (`src/apps-script/tiktok-trigger.gs`)

Watch the Weekly Review tab for approval, fire `repository_dispatch` to trigger generation and scheduling workflows. Same pattern as Pinterest trigger — adapt for TikTok sheet ID and event types.

**Effort:** 5-8 hours

#### 10b. Cross-channel awareness in Pinterest prompts — COMPLETED (Phase 8b)

**Status:** Done. Pulled forward into Phase 8b because the strategy vacuum in weekly analysis was causing under-informed recommendations. All changes below are implemented and tested.

**What was done (Phase 8b, 2026-03-04):**
- `weekly_analysis.py`: channel filter (`channel="pinterest"`), loads strategy context + content memory, passes to Claude
- `claude_api.py`: `analyze_weekly_performance()` and `run_monthly_review()` gain `strategy_doc`, `content_memory`, `cross_channel_summary` params
- `content_memory.py`: Section 8 (Performance History) — pillar lifetime, top keywords by saves, compounding signal, top performers
- `weekly_analysis.md`: `{{strategy_context}}`, `{{content_memory_summary}}`, `{{cross_channel_summary}}` sections + strategic alignment check + cross-channel notes output
- `weekly_plan.md`: Pinterest-scoped topic dedup + cross-channel framing note
- `monthly_review.md`: `{{content_memory_summary}}`, `{{cross_channel_summary}}` sections + cross-channel observations output

**What remains for Phase 10 (when TikTok actually launches):**
- Wire a real `cross_channel_summary` generator (see Phase 12, item 15b) — currently defaults to "Single channel (Pinterest only)"
- Verify cross-channel observations render correctly with live TikTok data

**Effort:** 0 hours remaining (completed)

#### Verify
- Generate a test week of 7 carousel specs
- Verify Claude output parses to valid JSON with correct attribute tags
- Render all carousels, verify visual quality
- Content Queue sheet populates correctly with thumbnails
- Apps Script trigger fires on approval
- Pinterest weekly analysis includes cross-channel observations section
- Pinterest weekly plan correctly scopes topic dedup to Pinterest-only (TikTok topics don't block Pinterest topics)
- Cross-channel summary renders correctly in analysis/review prompts

---

### Phase 11: Posting via Publer

**Goal:** Post carousels automatically via Publer's API, with a manual-posting fallback. Get content live on the platform.

**Effort:** 25-35 hours | **Risk:** MEDIUM (no API audit dependency)

#### 11. `src/tiktok/apis/publer_api.py`

Publer REST API wrapper (~80-100 lines). Same pattern as `src/pinterest/apis/pinterest_api.py`.

**Base URL:** `https://app.publer.com/api/v1`

**Auth headers (every request):**
```
Authorization: Bearer-API {PUBLER_API_KEY}
Publer-Workspace-Id: {PUBLER_WORKSPACE_ID}
Content-Type: application/json
```

**Photo carousel posting flow:**
1. `POST /media/from-url` — import slide images from GCS URLs (async, returns job_id)
2. `GET /job_status/{job_id}` — poll until `"complete"`, extract media IDs
3. `POST /posts/schedule/publish` — create scheduled TikTok carousel with media IDs
4. `GET /job_status/{job_id}` — poll until post is confirmed published

**Rate limits:** ~100 requests per 2 minutes per user (unverified — implement exponential backoff on 429)

**Carousel constraints:**
- Min 2 slides, max 35 slides
- JPEG, PNG, or WebP, max 20MB per image
- Caption max 2,200 characters (TikTok limit; Publer allows 4,000)
- Title max 90 characters
- Privacy level required (no default)

**TikTok-specific options:** `privacy` (PUBLIC_TO_EVERYONE / MUTUAL_FOLLOW_FRIENDS / SELF_ONLY), `allow_comments`, `auto_add_music`, `branded_content`, `paid_partnership`

**Fallback mode (`TIKTOK_POSTING_ENABLED=false`):** Log `MANUAL_UPLOAD_REQUIRED` to Sheets + send Slack notification with GCS links for manual posting.

**Effort:** 8-12 hours

#### Token management — NOT NEEDED

Publer uses a static API key. No OAuth flow, no token refresh, no token store. This eliminates ~5-8 hours of work and ongoing 24-hour token expiry management.

#### 12. `src/tiktok/post_content.py`

Daily posting orchestrator (called 1-3x daily depending on cadence ramp):
- Read from `data/tiktok/carousel-schedule.json`
- Idempotency check against `data/tiktok/content-log.jsonl`
- Add random jitter (0-120 seconds before API call)
- Call Publer API to schedule post (or log manual upload)
- Poll job status to confirm post published
- Update content-log.jsonl with attribute tags
- Update Post Log sheet
- Slack notification

**AI disclosure logic:** Check carousel spec — if `image_source == "ai_generated"` and template is `photo_forward`, the AI content disclosure must be handled. **Open question:** Verify whether Publer exposes TikTok's `is_aigc` flag. If not, label AI-generated content manually in the TikTok app post-upload, or investigate Publer's branded content options. Unlabeled AI content gets -73% reach suppression.

**Effort:** 12-16 hours

#### 13. GitHub Actions posting workflows

| Workflow | Trigger | Steps |
|----------|---------|-------|
| `tiktok-promote-and-schedule.yml` | `repository_dispatch` (Sheet approval) | Read approved carousels → distribute across 7 days → write schedule JSON |
| `tiktok-daily-post.yml` | Cron 3x daily (10am, 4pm, 7pm ET) | Read schedule → post via Publer (or log manual) → update logs → Slack |

Each workflow: single concurrency group, Slack failure notifications, timeout guards.

**Effort:** 5-7 hours

<details>
<summary>Original direct TikTok API approach (preserved for fallback reference)</summary>

**`src/tiktok/apis/tiktok_api.py`** — TikTok Content Posting API wrapper:
- Photo carousel posting flow (3-step): `POST /v2/post/publish/creator_info/query/` → `POST /v2/post/publish/content/init/` → `GET /v2/post/publish/status/fetch/`
- Rate limits: 6 requests/minute per user token
- Requires 2-4 week API audit approval

**`src/tiktok/token_manager.py`** — TikTok OAuth token management:
- Client ID + Client Secret auth flow, refresh token rotation
- Access tokens expire every 24 hours (vs Publer's static API key)
- Store tokens in `data/tiktok/token-store.json`

</details>

#### Verify
- Post a test carousel via Publer API (sandbox first, then real)
- Verify GCS image URLs are accessible from Publer's servers (must be publicly readable)
- Verify idempotency — re-running doesn't double-post
- Verify Slack notifications arrive for both success and manual-upload fallback
- Post Log sheet updates correctly
- Content-log.jsonl entries have correct attribute tags
- Verify `is_aigc` handling (or document the gap)

---

### Phase 12: Analytics + feedback loop

**Goal:** Pull TikTok performance data, analyze it, and close the loop so next week's content generation shifts toward what's working.

**Effort:** 25-38 hours | **Risk:** LOW-MEDIUM

#### 14. `src/tiktok/pull_analytics.py`

Publer post insights integration (uses the same `publer_api.py` from Phase 11):
- Fetch metrics via `GET /api/v1/analytics/{account_id}/post_insights` for all posts in the last 4-week window
- Metrics: views, likes, comments, shares, engagement rate
- **Open question:** Verify whether Publer returns **saves** for TikTok posts (saves are a critical algorithm signal). If not, saves may need manual tracking or future TikTok Display API integration.
- Pagination: 10 posts per page, 0-based page index
- Join with attribute tags from content-log.jsonl
- Compute per-attribute averages (save rate, share rate by topic, angle, structure, etc.)
- Write `data/tiktok/performance-summary.json`
- Update content memory summary
- Identify top 5 and bottom 5 posts

**Data lag:** TikTok metrics have 24-48 hour lag. Publer syncs data daily with a manual refresh option. Pull runs Sunday evening, giving Saturday posts ~24 hours to accumulate.

**Fallback:** Manual metric entry via the Performance Data sheet tab. `pull_analytics.py` reads from sheet instead of API.

**Future upgrade:** If deeper analytics needed (audience demographics, traffic sources, daily time-series, saves if not available via Publer), apply for TikTok Display API (`video.list` scope). Estimated effort: 15-25 hours + 1-3 week approval.

**Effort:** 10-15 hours

<details>
<summary>Original TikTok Display API approach (preserved for fallback/future reference)</summary>

**TikTok Display API integration:**
- Requires separate API approval (sandbox prototype + demo video + privacy policy page)
- Access token expires every 24 hours (refresh token lasts 365 days)
- Metrics: views, likes, comments, shares (lifetime totals only, no daily granularity)
- Must store snapshots and diff for weekly deltas
- Endpoint: `POST /v2/video/list/` (paginated, 20 per page)
- Rate limit: 600 req/min
- `TIKTOK_DISPLAY_API_ENABLED=false` fallback to manual entry

</details>

#### 15. `src/tiktok/weekly_analysis.py`

Claude-powered weekly performance analysis — follows the same enriched pattern established for Pinterest in Phase 8b:

**Data loading (via shared infrastructure):**
- Filter `content-log.jsonl` to `channel="tiktok"` before computing metrics (same pattern as Pinterest's channel filter)
- Load strategy context via `load_strategy_context()` — TikTok's analyzer should evaluate performance against strategic intent, not operate in a vacuum
- Load content memory via `load_content_memory()` — cross-channel history with channel attribution (includes Pinterest data)
- Generate a cross-channel summary (Pinterest performance digest) to pass as `cross_channel_summary`

**Attribute-based aggregation (differs from Pinterest):**
- Aggregate by TikTok's attribute taxonomy (topic, angle, structure, hook_type, visual_template) instead of Pinterest's pillars/boards/templates
- Compute per-attribute trends (which attributes improving/declining)
- No board analysis (TikTok doesn't have boards)

**Compounding vs. virality:**
- Pinterest content memory includes a "Compounding Signal" section (3.75-month evergreen half-life). TikTok content has fundamentally different dynamics — 48-72 hour peak, then rapid decay. The TikTok analysis prompt should assess explore/exploit effectiveness and virality patterns, not evergreen compounding.

**Claude API integration:**
- Add `analyze_tiktok_performance()` to `claude_api.py` (or use a channel-generic analysis method) with the same enriched signature pattern: `strategy_doc`, `content_memory`, `cross_channel_summary` params
- New prompt: `prompts/tiktok/weekly_analysis.md` — must include `{{strategy_context}}`, `{{content_memory_summary}}`, `{{cross_channel_summary}}` context sections (same pattern as Pinterest's prompt)
- Output sections should include "Strategic Alignment Check" and "Cross-Channel Notes" (same pattern)

**Output:**
- `analysis/tiktok/weekly/YYYY-wNN-review.md`
- Feed into next week's TikTok content planner
- Cross-channel summary also visible to Pinterest's weekly analysis

**Monthly review (future consideration):**
TikTok's faster feedback cycles may warrant a monthly strategy review equivalent. The shared infrastructure (`run_monthly_review()` signature with `cross_channel_summary` and `content_memory` params) is ready. Decide based on data volume and strategic complexity after MVP stabilizes.

**Effort:** 10-15 hours

#### 15b. Cross-channel summary generation

When TikTok launches, both channels need a focused "other channels this week" digest for their `cross_channel_summary` param. Content memory already contains full cross-channel history, but `cross_channel_summary` should be a short, targeted summary:

- Small Python function: filter content log to non-target channel entries from the last 7 days, compute quick aggregates (post count, top performer, engagement rate), return a 200-300 char summary
- Pinterest's analyzer receives a TikTok digest; TikTok's analyzer receives a Pinterest digest
- Alternative (simpler first pass): pass the full content memory as `cross_channel_summary` — the LLM can extract what it needs, at the cost of ~900 extra input tokens

**Effort:** 2-3 hours

#### 16. GitHub Actions analytics workflows

TikTok analytics plug into the shared collection pattern established in Phase 8:

| Workflow | Integration |
|----------|-------------|
| `collect-analytics.yml` (Phase 8) | Add TikTok analytics pull as a new step — runs alongside Pinterest pull before content memory refresh |
| `tiktok-weekly-review.yml` | Runs after `collect-analytics` completes (parallel to `pinterest-weekly-review.yml`). Steps: compute attribute weights → generate plan → render carousels → publish to Sheets |

No separate Sunday evening timing needed — TikTok review runs at the same time as Pinterest, both triggered after the shared analytics collection.

**Effort:** 6-8 hours

#### 17. Wire the feedback loop

This is the integration work that makes the system self-improving:
- `pull_analytics.py` writes `performance-summary.json`
- `compute_attribute_weights.py` reads `performance-summary.json` and shifts allocation toward high performers
- `generate_weekly_plan.py` receives shifted weights, generates content that reflects what's working
- Content memory prevents topic repetition across the 2-week window
- TikTok analytics flow into the content log with `channel: "tiktok"`, which automatically surfaces in content memory for all planners — no explicit wiring to content_planner needed

**Effort:** 4-7 hours

#### Verify
- Pull analytics for posted content (API or manual entry)
- Verify performance-summary.json populates with per-attribute breakdowns
- Confirm feedback loop: Week N analytics → Week N+1 attribute weights visibly shift
- Run one full automated weekly cycle end-to-end:
  - [ ] Sunday 7pm: analytics pull
  - [ ] Sunday 8pm: plan generation + carousel rendering + Sheet publish
  - [ ] Human approval in Sheet
  - [ ] Carousels scheduled across the week
  - [ ] Daily posts fire (API or manual fallback)
  - [ ] Next Sunday: analytics reflect new posts

---

**MVP COMPLETE** — At this point (Phases 8-12), the pipeline is operational and self-improving: carousels generated weekly based on strategy + performance data, human reviews in Google Sheets, carousels post automatically (or via manual fallback), analytics feed back into next week's planning.

**MVP effort total:** 145-205 hours (5-7 shared context layer + 140-198 build)
**MVP monthly cost:** $30-52/mo (Claude + DALL-E + GCS + GitHub Actions + Publer $8/mo)

---

## Post-MVP Enhancements

Everything below is additive. Prioritize based on performance data and capacity.

### Phase 13: Video pipeline

**Goal:** Add video content alongside carousels — voiceover + background music + visual composition.

**Effort:** 45-70 hours | **Risk:** MEDIUM | **Monthly cost addition:** +$128-130/mo

**Prerequisite:** MVP pipeline is stable and posting consistently. Video is additive, not a replacement for carousels.

#### 18. ElevenLabs TTS integration

- API client wrapper for text-to-speech
- Voice selection (pre-selected voice ID stored in env)
- Character limit tracking (Creator plan: 100K chars/month, ~150K needed → may need Professional at $99/mo depending on volume)
- Output: MP3/WAV audio file per video

**Plan:** ElevenLabs Creator ($11/mo) for initial volumes, upgrade if needed.

**Effort:** 5-8 hours

#### 19. Epidemic Sound integration

- Music track selection (manual curation of 20-30 tracks matching brand vibe, or API if available)
- Licensing tracking per video
- Commercial license ($19/mo) covers TikTok + all platforms

**Effort:** 3-5 hours

#### 20. Audio mixing (FFmpeg)

- Combine voiceover + background music
- Volume leveling (voice at 100%, music at 15-25%)
- Normalization to TikTok-compatible format
- Output: mixed audio track ready for video composition

**Effort:** 8-12 hours

#### 21. Video rendering — Creatomate (bridge solution)

**Why Creatomate first:** Building custom Remotion templates is 60-80 hours. Creatomate ($99/mo) lets us ship video immediately while we build the long-term solution in Phase 15.

- Set up 3-5 core video templates in Creatomate (listicle, tutorial, problem-solution, recipe walkthrough)
- API integration: send script + images + audio → receive rendered MP4
- Template variables: text overlays, image sequences, timing, transitions
- Output: 1080x1920 MP4 ready for posting

**Effort:** 15-20 hours

#### 22. Extend content generation for video

- Add video specs to weekly plan generation (2-3 videos/week alongside carousels)
- New prompt: `prompts/tiktok/video_script.md` — generates narration script, shot list, timing cues
- Orchestrator: `src/tiktok/generate_videos.py` — script generation → TTS → music selection → Creatomate render → GCS upload
- Extend Content Queue sheet for video rows
- Extend `post_content.py` to handle video uploads
- **Pre-requisite:** Verify Publer supports TikTok video posting via API (likely yes, must confirm). If not, evaluate direct TikTok Content Posting API for video only.

**Effort:** 20-30 hours

#### Verify
- Render a test video end-to-end (script → TTS → music → Creatomate → MP4)
- Post video via API (or manual fallback)
- Verify audio quality, timing, text overlay readability
- Run mixed week: 4 carousels + 2 videos

---

### Phase 14: Engagement automation

**Goal:** Automated comment monitoring, classification, and reply generation.

**Effort:** 25-40 hours | **Risk:** LOW | **Monthly cost addition:** +$52-62/mo

This phase is optional and can be deferred. It improves post-publish performance but isn't required for the core pipeline.

#### 23. Comment ingestion + classification

- NapoleonCat ($32/mo Pro) or Ayrshare ($49/mo) for comment API access
- Fetch new comments on a schedule (every 4 hours)
- Claude classifies each comment:
  - **SPAM** → auto-hide
  - **QUESTION** → generate helpful answer
  - **COMPLIMENT** → generate brief friendly reply
  - **COMPLAINT** → flag for human review
  - **NEUTRAL** → generate casual reply
  - **COLLAB_REQUEST** → flag for human review

**Effort:** 10-15 hours

#### 24. Auto-reply with rate limiting

- Claude generates unique replies (no templates — every reply different)
- Brand voice enforcement via system prompt
- Rate limits: 5-15 replies/hour, 20-50/day
- Random delay between replies: 2-15 minutes (avoid obvious automation)
- Reply timing after comment: 5-30 minutes

**Effort:** 10-15 hours

#### 25. `tiktok-engagement.yml` workflow

- Cron every 4 hours
- Fetch → classify → generate → post replies
- Alert on negative comments
- Log all interactions

**Effort:** 5-10 hours

#### Verify
- Fetch comments from a test post
- Verify classification accuracy on 20+ comments
- Confirm rate limiting prevents bursts
- Verify human escalation works for complaints

---

### Phase 15: Remotion migration

**Goal:** Replace Creatomate ($99/mo) with custom Remotion templates for video rendering. Full control, lower marginal cost.

**Effort:** 65-95 hours | **Risk:** MEDIUM-HIGH (significant React/TS learning curve)

Only worth doing once the video pipeline is proven and running consistently. Creatomate works fine in the interim.

#### 26. Remotion templates (React/TypeScript)

- Convert Creatomate templates to Remotion compositions
- 3-5 video types: listicle, tutorial, problem-solution, recipe walkthrough, before-after
- Timeline composition: image sequences + text overlays + transitions + audio sync
- Parameterized: all content injected via JSON props

**Effort:** 40-60 hours

#### 27. AWS Lambda rendering

- Remotion Lambda for serverless video rendering
- S3 output → GCS transfer (or direct S3 serving)
- Cost: ~$0.01 per render on Lambda + Remotion license ($100/mo Automators plan)

**Effort:** 15-20 hours

#### 28. Migration + Creatomate cancellation

- Swap Creatomate API calls for Remotion Lambda calls in `generate_videos.py`
- Side-by-side quality comparison
- Cancel Creatomate subscription ($99/mo savings, net +$1/mo for Remotion)

**Effort:** 10-15 hours

#### Verify
- Render same video through both Creatomate and Remotion, compare quality
- Verify Lambda rendering completes within timeout
- Run full week with Remotion-rendered videos
- Monitor cost per render

---

# Reference

## Open Decisions

These decisions must be resolved before starting Phase 9 (carousel rendering). They can be resolved in parallel with Phases 5-8.

| # | Decision | Options | Recommendation | Impact |
|---|----------|---------|----------------|--------|
| 1 | **Account type** | Creator vs. Business | **Creator** — 2.75-4.4x higher engagement; full trending sound access; switch to Business later at 10K+ followers | Affects API access, sound library, ad capabilities |
| 2 | **TikTok handle** | e.g., @slated, @slatedapp, @slatedmeals | Short, brand-forward, no numbers, under 15 chars | **PLACEHOLDER `@slated` in Phase 9 CTA templates** — passed as `{{handle}}` variable, no template edits needed when decided. Must resolve before first TikTok post. |
| 3 | **First subcommunity** | #MomTok, #FoodTok, #MealPrep, #DinnerIdeas | Research scored these — need final pick | Drives initial content angles, hashtags, engagement targets |
| 4 | **Starting posting cadence** | 3/week → 5/week → 7/week ramp | **3/week first 2 weeks, 5/week weeks 3-4, 7/week weeks 5+** — algorithm rewards consistency over volume | Template count, generation batch size, cost |
| 5 | **Link-in-bio strategy** | Linktree, direct app store, goslated.com | Creator accounts get link-in-bio at 1K followers; pin app store link in comments until then | CTA slide copy, bio text |
| 6 | **AI content disclosure** | Always label / label realistic only / never label | **Label realistic images, skip for text-on-background carousels** — unlabeled AI content gets -73% reach suppression | `is_aigc` flag in API calls, image generation approach |
| 7 | **Engagement staffing** | Human only / automated / hybrid | **Automated with human escalation** — NapoleonCat + Claude for replies, human reviews negative comments | Phase order, tooling cost |
| 8 | **Initial topic taxonomy** | Needs niche-specific topics defined | Start with 8-10 topics derived from Pinterest strategy pillars, expand based on performance | Attribute weights, prompt templates |
| 9 | **"Face" of the account** | Faceless / founder / hired creator | Research says accounts with a consistent face dramatically outperform faceless — but this is a staffing decision | Video approach, content authenticity |

## Pre-Build Parallel Track

These can and should start during or before the restructure completes. They have lead times that would otherwise block the build.

### P1. Create TikTok account + 14-day warmup

**Timeline:** 14 days | **Effort:** 30-60 min/day | **Owner:** Human

The algorithm needs to learn the account's niche before posting. Per the warmup playbook:

- **Day 0:** Create account. Username, logo profile photo (200x200px min), bio (80-120 chars describing value prop).
- **Days 1-3:** Pure consumption. Spend 30-60 min/day consuming content in target niches (#MealPrep, #DinnerIdeas, etc.). Like and comment on 10-15 videos. Follow 20-30 creators in target niche. Do NOT post.
- **Days 4-7:** Light posting. Post 2-3 test videos/carousels (manual, testing formats). Continue 30-40 min daily engagement. Comment on 15-20 videos daily.
- **Days 8-14:** Ramp up. Post 3-5 pieces. Monitor which formats drive saves/shares. Participate in trending sounds/hashtags relevant to niche.

### P2. Set up Publer account + API access

**Timeline:** Same day (no audit) | **Effort:** 30-60 min | **Cost:** $8/mo (Business plan, annual billing, 1 TikTok account)

Steps:
1. Sign up for Publer Business plan (14-day free trial available)
2. Connect TikTok account to Publer workspace
3. Generate API key: Settings > Access & Log In > API Key > Manage API Keys
4. Note your Workspace ID (from Settings or `GET /api/v1/workspaces`)
5. Note your TikTok Account ID (from `GET /api/v1/accounts` or the Publer dashboard)
6. Add to `.env`: `PUBLER_API_KEY`, `PUBLER_WORKSPACE_ID`, `PUBLER_TIKTOK_ACCOUNT_ID`
7. Verify: test `GET /api/v1/accounts` returns your TikTok account

**Confirm during trial:** (a) Business plan includes API access, (b) TikTok carousel posting works via API, (c) post insights endpoint returns TikTok metrics.

### P3. Set up Google Sheet

**Timeline:** 1-2 hours | **Effort:** Human

Create TikTok-specific Google Sheet with 4 tabs:

| Tab | Purpose | Key Columns |
|-----|---------|-------------|
| **Weekly Review** | Approve/reject weekly content plan | Week #, status, plan summary, exploit/explore split, feedback |
| **Content Queue** | Review individual carousels before posting | Carousel ID, date, slot, attributes (6 cols), caption, thumbnail (IMAGE formula), status, feedback |
| **Post Log** | Track what's been posted | Carousel ID, date posted, TikTok post ID, status, error message, attributes |
| **Performance Data** | Weekly analytics per post | Carousel ID, views, saves, shares, comments, save rate, share rate, attributes, days since posted |

## Publer Decision Record

**Decision (2026-03-03):** Use Publer (publer.com) as the posting and analytics intermediary instead of integrating the TikTok Content Posting API and Display API directly.

**Rationale:**
- **No API audit required.** The TikTok Content Posting API requires a fully built app with mandatory UX elements, demo videos, and a 2-4 week audit. Publer handles TikTok's OAuth and API integration on their end.
- **No token management burden.** TikTok access tokens expire every 24 hours. Publer uses a static API key.
- **Analytics included.** Publer's post insights endpoint returns views, likes, comments, shares, and engagement rate — sufficient for our weekly review workflow. Avoids the separate TikTok Display API approval process.
- **Cost:** Publer Business plan, 1 TikTok account, annual billing = **$8/month**.
- **Fallback:** If we outgrow Publer's analytics, we can apply for the TikTok Display API later.

**Services evaluated:** Late (getlate.dev), Metricool, OneUp. Publer chosen for best balance of maturity (13+ years, 300K users, bootstrapped), API documentation quality, pricing, and analytics-via-API support.

**Open questions to verify during Publer trial:**
- Confirm Business plan (not just Enterprise) includes API access
- Confirm TikTok **saves** are returned in post insights (critical for feedback loop)
- Confirm `is_aigc` (AI content disclosure) flag is available through Publer's TikTok options

## Cadence Ramp Plan

| Week | Posts/week | Mix | Notes |
|------|-----------|-----|-------|
| 1-2 | 3 | 3 carousels | Warmup period. Manual posting likely (API audit pending). |
| 3-4 | 5 | 5 carousels | Automated posting live. Cold-start attribute allocation. |
| 5-6 | 7 | 7 carousels | 1/day. First performance data feeding back into planner. |
| 7-8 | 10-14 | 7-10 carousels + 2-4 videos | Video pipeline online (Phase 13). Mixed content. |
| 9+ | 14-21 | 10-14 carousels + 4-7 videos | Full cadence. Feedback loop mature. Scale based on performance data. |

**Don't rush to 21/week.** The research says 3-5/week is the data-optimal range for engagement per post. Scale only when content quality and engagement signals justify it.

## Cost Summary

| Milestone | Monthly Cost | What's running |
|-----------|-------------|----------------|
| **MVP (Phases 8-12)** | $30-52/mo | Carousel pipeline with feedback loop (includes Publer $8/mo) |
| **+ Phase 13 (Video)** | $150-175/mo | + Creatomate + ElevenLabs + Epidemic Sound |
| **+ Phase 14 (Engagement)** | $200-235/mo | + NapoleonCat + additional Claude API |
| **+ Phase 15 (Remotion)** | $200-235/mo | Creatomate dropped, Remotion replaces it (cost-neutral) |

## Effort Summary

| Phase | Description | Hours | Risk | Depends on |
|-------|-------------|-------|------|------------|
| 1 | Create structure, move shared code | 4-6 | LOW | — |
| 2 | Extract content memory & analytics utils | 3-4 | MEDIUM | Phase 1 |
| 3 | Extract shared data-loading into content planner | 8-12 | HIGH | Phase 2 |
| 4 | Move prompts into subdirectories | 2-3 | LOW | Phase 3 |
| 5 | Update GitHub Actions workflows | 2-3 | MEDIUM | Phase 4 |
| 6 | Cleanup (delete shims, update docs) | 2-3 | LOW | Phase 5 |
| 7 | Migrate TikTok research + rename repo | 2-3 | LOW | Phase 6 |
| | **Restructure total (Phases 1-7)** | **23-34** | | |
| 8 | Shared context layer + workflow restructure | 5-7 | LOW-MEDIUM | Phase 7 |
| 9 | Carousel rendering engine | 35-50 | LOW | Phase 8 |
| 10 | Content generation pipeline + cross-channel prompts | 60-83 | MEDIUM | Phase 9 |
| 11 | Posting via Publer | 25-35 | MEDIUM | Phase 10 |
| 12 | Analytics + feedback loop | 25-38 | LOW-MEDIUM | Phase 11 |
| | **TikTok MVP total (Phases 8-12)** | **150-213** | | |
| 13 | Video pipeline (Creatomate) | 45-70 | MEDIUM | MVP stable |
| 14 | Engagement automation | 25-40 | LOW | MVP stable |
| 15 | Remotion migration | 65-95 | MEDIUM-HIGH | Phase 13 stable |
| | **Full build total (Phases 1-15)** | **343-497** | | |

## Reuse from Pinterest Pipeline

| Component | Reuse Level | Notes |
|-----------|------------|-------|
| `src/shared/apis/claude_api.py` | 100% | Same module, new prompts |
| `src/shared/apis/image_gen.py` | 100% | DALL-E/Replicate calls identical |
| `src/shared/apis/gcs_api.py` | 100% | GCS upload identical |
| `src/shared/apis/sheets_api.py` | 80% | Same patterns, TikTok-specific sheet config |
| `src/shared/apis/slack_notify.py` | 80% | Add TikTok event types |
| `src/shared/content_planner.py` | 100% | TikTok uses same data-loading functions (strategy, memory, seasonal) |
| `src/shared/content_memory.py` | 90% | Extend with channel attribution on entries |
| `src/shared/analytics_utils.py` | 70% | Shared log format, TikTok-specific metrics |
| `src/shared/image_cleaner.py` | 80% | Same validation, different dimensions |
| `render_pin.js` — reused directly for carousel rendering | 100% | Batch rendering via `--manifest` mode already supported multi-slide; no new JS file needed |
| `pin_assembler.py` → `carousel_assembler.py` | 50% | Template injection + shared `image_to_data_uri()` reused, multi-slide orchestration new |
| `post_pins.py` → `post_content.py` | 50% | Posting patterns reused, Publer API simpler than Pinterest direct API |
| `generate_weekly_plan.py` | 30% | Architecture reused, attribute system is new |
| GitHub Actions workflow patterns | 70% | Same structure, TikTok-specific steps |
| Apps Script trigger pattern | 80% | Same dispatch mechanism, different sheet |
| Token management patterns | N/A | Not needed — Publer uses static API key |

**Estimated reuse savings:** 150-190 hours (40-50% reduction from building from scratch)

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Publer service disruption or API changes | Can't post programmatically | Low | Manual posting fallback built into every workflow; can fall back to direct TikTok API if needed |
| Publer Business plan doesn't include API access | Must upgrade to Enterprise | Low | Verify during 14-day trial before committing |
| AI content detection on images | Reach suppression on photo-forward carousels | Medium | Strip C2PA metadata; use Replicate/Flux (lower detection); self-label when uncertain |
| Cold start — no performance data for 2-3 weeks | Blind attribute allocation | High (expected) | Cold-start mode: even distribution, learn fast |
| Algorithm doesn't reward carousels in our niche | Lower-than-expected reach | Low-Medium | Research says carousels get 81% higher engagement — but monitor and adjust mix |
| ElevenLabs TTS flagged as AI voice | Video reach suppressed | Low | Use stock voices that sound natural; human voiceover backup |
| TikTok US regulatory disruption | Platform unavailable | Low | Build TikTok-native; keep unwatermarked source assets for reuse on Reels/Shorts |
| Remotion learning curve (React/TS) | Phase 15 timeline slip | Medium | Creatomate bridge removes time pressure; Remotion migration is optional upgrade |
| Engagement automation triggers spam detection | Account penalty | Low | Conservative rate limits (20-50 replies/day); all replies unique via Claude; random delays |
| Template fatigue | Declining engagement | Low-Medium | 4 families from day 1; add 1-2 new families every 4-6 weeks |

## Environment Variables

```bash
# TikTok posting via Publer
PUBLER_API_KEY=                        # Generated in Publer dashboard
PUBLER_WORKSPACE_ID=                   # From Publer dashboard or GET /api/v1/workspaces
PUBLER_TIKTOK_ACCOUNT_ID=             # From GET /api/v1/accounts or Publer dashboard
TIKTOK_POSTING_ENABLED=false           # Set to true when Publer integration verified

# TikTok Google Sheet (separate from Pinterest sheet)
TIKTOK_GOOGLE_SHEET_ID=
TIKTOK_GOOGLE_SHEET_URL=

# Video — Phase 13
CREATOMATE_API_KEY=                   # Phase 13 only, dropped in Phase 15
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
EPIDEMIC_SOUND_API_KEY=

# Video — Phase 15 (replaces Creatomate)
REMOTION_AWS_ROLE_ARN=

# Engagement — Phase 14
NAPOLEONCAT_API_KEY=
ENGAGEMENT_AUTOMATION_ENABLED=false

# Shared (already in .env from Pinterest)
# ANTHROPIC_API_KEY, OPENAI_API_KEY, GCS_BUCKET_NAME,
# GOOGLE_SHEETS_CREDENTIALS_JSON, SLACK_WEBHOOK_URL
```

## What Success Looks Like

### Month 1 (MVP)
- 12-20 carousels posted
- Attribute performance data accumulating
- Feedback loop producing shifted weights for week 3+
- 100-500 followers (per research growth curves)

### Month 3 (+ Phase 13)
- Mixed content: carousels + videos
- 10-14 posts/week automated cadence
- Performance data driving 65/35 exploit/explore allocation
- 500-3,000 followers
- 1-2 breakout posts

### Month 6 (+ Phases 14-15)
- Full pipeline: carousels + Remotion videos + engagement automation
- 14-21 posts/week
- Feedback loop mature — clear signal on what works
- 2,000-15,000 followers
- Proven content formats, community forming

### Month 12
- Established presence, 10,000-50,000+ followers
- Content engine self-improving weekly
- TikTok analytics feeding into content memory alongside Pinterest, surfacing cross-channel performance for all planners
- Ready to evaluate paid promotion of top performers

---

## What This Enables

After the restructure (Phases 1-8), adding any new channel means:

1. Create `src/{channel}/` with channel-specific modules (planner, content creator, poster, analytics)
2. Create `prompts/{channel}/` with channel-specific prompts
3. The channel planner reads shared context via `content_planner.load_strategy_context()` and cross-channel content memory (with channel attribution and performance data), then runs its own planning call — no shared topic plan
4. Channel analytics plug into `collect-analytics.yml` — one new step per channel
5. Content memory automatically surfaces cross-channel performance with channel attribution
6. Add `.github/workflows/{channel}-*.yml` for channel-specific scheduling

No changes needed to the shared layer or existing channel code.
