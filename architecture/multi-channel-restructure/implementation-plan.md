# Multi-Channel Content Pipeline — Implementation Plan

**Date:** 2026-02-27 (updated 2026-03-03)
**Status:** Active — Phases 1-5 complete, Phase 6 next

---

## Table of Contents

- [Context](#context)
- [Target Architecture](#target-architecture)
- [Target Directory Structure](#target-directory-structure)
- [Part 1: Restructure](#part-1-restructure-pinterest-stays-live-throughout)
  - [Phase 1: Create structure, move purely shared code](#phase-1-create-structure-move-purely-shared-code)
  - [Phase 2: Extract content memory and analytics utilities](#phase-2-extract-content-memory-and-analytics-utilities)
  - [Phase 3: Split planning into unified + channel-specific](#phase-3-split-planning-into-unified--channel-specific)
  - [Phase 4: Move prompts into subdirectories](#phase-4-move-prompts-into-subdirectories)
  - [Phase 5: Update GitHub Actions workflows](#phase-5-update-github-actions-workflows)
  - [Phase 6: Cleanup and burn-in](#phase-6-cleanup-and-burn-in)
- [Part 2: TikTok Integration](#part-2-tiktok-integration)
  - [Phase 7: Migrate TikTok research + rename repo](#phase-7-migrate-tiktok-research--rename-repo)
  - [Phase 8: Build TikTok pipeline](#phase-8-build-tiktok-pipeline)
- [Effort Summary](#effort-summary)
- [What This Enables](#what-this-enables)

---

## Context

The current `pinterest-pipeline` is a vertically integrated Pinterest automation. We're restructuring it into a multi-channel content engine that can serve Pinterest, TikTok, and eventually paid channels. Rather than building separate pipelines per channel, we're extracting content planning and blog generation into a shared layer, with channel-specific workflows branching off.

**Decisions made:**
- Monorepo structure (`src/shared/`, `src/pinterest/`, `src/tiktok/`, etc.)
- Incremental migration — Pinterest pipeline stays live and posting daily throughout
- Restructure first, verify Pinterest works, then build TikTok
- Rename repo to `slated-content-engine` after restructure is stable
- TikTok content is independent from blogs — the unified planner handles topic selection, but each channel owns its own format/creative decisions
- Paid channels are a future concern, not addressed in this plan

---

## Target Architecture

```
Layer 1: Unified Content Planning (src/shared/)
  ├── Topic selection: "what subjects to cover this week"
  ├── Cross-channel content memory & dedup
  ├── Strategy + seasonal calendar + keyword targets
  ├── Reads analytics from ALL active channels
  └── Outputs: topic plan with pillar assignments and channel suitability hints

Layer 2: Blog Generation & Deployment (src/shared/)
  ├── Generates MDX blog posts (channel-agnostic)
  └── Deploys to goslated.com

Layer 3: Channel-Specific Workflows (fully independent per channel)
  ├── src/pinterest/ — pin planning, creation, posting, analytics
  └── src/tiktok/    — carousel/video planning, creation, posting, analytics
```

### Two-Step Planning Design

The current `weekly_plan.md` prompt generates both blog topics AND 28 pin specs in one Claude call. This must be split:

1. **Unified Content Strategy** (`prompts/shared/content_strategy.md`) — "What topics should we cover this week?" Reads analytics from all channels, content memory, seasonal calendar. Outputs topic plan with pillar assignments and channel suitability hints. One Claude call.

2. **Channel-Specific Planning** (e.g., `prompts/pinterest/pin_planning.md`) — Each channel takes the topic plan and derives its own content. Pinterest: 28 pin specs with board distribution, template selection, scheduling. TikTok: carousel/video specs with format selection, hook styles, posting cadence. Each channel can also generate content with no topic-plan counterpart (e.g., TikTok trend-reactive posts).

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
│   │   ├── content_planner.py        # NEW: unified topic selection
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
│   │   ├── pin_planner.py            # NEW: extracted Pinterest constraints
│   │   ├── generate_weekly_plan.py   # Orchestrator: content_planner → pin_planner
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
│   │   ├── content_strategy.md       # NEW: unified planning prompt
│   │   ├── blog_post_guide.md        # Moved from prompts/
│   │   ├── blog_post_listicle.md
│   │   ├── blog_post_recipe.md
│   │   ├── blog_post_weekly_plan.md
│   │   └── image_prompt.md
│   ├── pinterest/
│   │   ├── pin_planning.md           # NEW or refactored from weekly_plan.md
│   │   ├── weekly_plan.md            # Moved from prompts/
│   │   ├── weekly_plan_replace.md
│   │   ├── pin_copy.md
│   │   ├── weekly_analysis.md
│   │   └── monthly_review.md
│   └── tiktok/                       # Built in Phase 9
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

### Phase 3: Split planning into unified + channel-specific

**Goal:** Extract generic planning logic from `generate_weekly_plan.py` into `src/shared/content_planner.py`. Leave Pinterest-specific constraints in `src/pinterest/pin_planner.py`.

**Effort:** 8-12 hours | **Risk:** HIGH (largest and most complex phase)

#### What gets created

1. **`src/shared/content_planner.py`** — unified content planning:
   - `generate_content_plan()` — calls Claude with `prompts/shared/content_strategy.md`
   - Extracted from `generate_weekly_plan.py`: `load_strategy_context()`, `load_content_memory()`, `load_latest_analysis()`, `get_current_seasonal_window()`
   - Outputs: topic plan with pillar assignments, keyword targets, funnel layers, content type recommendations
   - Does NOT validate pin counts, board distribution, template distribution, or any channel-specific constraints
   - Designed so TikTok (or any channel) can call the same function later

2. **`src/pinterest/pin_planner.py`** — Pinterest-specific planning:
   - `generate_pin_plan()` — takes unified content plan, calls Claude to derive 28 pin specs
   - Contains all Pinterest constraints: `validate_plan()`, `PILLAR_MIX_TARGETS`, `TOTAL_WEEKLY_PINS`, `MAX_PINS_PER_BOARD`, board distribution, template distribution, scheduling
   - `identify_replaceable_posts()`, `splice_replacements()` for retry logic

3. **`prompts/shared/content_strategy.md`** — new prompt for unified planning (topics only, no pin specs)

4. **`src/pinterest/generate_weekly_plan.py`** — orchestrator:
   ```python
   def generate_plan():
       content_plan = content_planner.generate_content_plan()
       full_plan = pin_planner.generate_pin_plan(content_plan)
       # Write to Sheets, save JSON, notify Slack
   ```

#### What moves
- `src/generate_weekly_plan.py` → split into `src/shared/content_planner.py` + `src/pinterest/pin_planner.py` + `src/pinterest/generate_weekly_plan.py`
- `src/regen_weekly_plan.py` → `src/pinterest/regen_weekly_plan.py`

#### Critical file to split

`src/generate_weekly_plan.py` (1395 lines) currently interleaves:
- **Generic** (→ content_planner): strategy loading, content memory, seasonal calendar, keyword performance
- **Pinterest-specific** (→ pin_planner): board validation, pillar mix targets, pin-per-day scheduling, template distribution, constraint validation with retry

#### Key risk

Two-step planning (content plan → pin plan) may change output quality vs the current single-step approach. **Mitigation:** Run side-by-side comparison of 2-3 generated plans. Keep old single-step as a fallback flag during transition.

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
- ~~`content_strategy.md` (created in Phase 3)~~ **Deferred to Phase 8a.** Do NOT create this file.

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

### Phase 8: Build TikTok pipeline

**Goal:** Implement `src/tiktok/` using the research from `tiktok-automation` and adapted Pinterest pipeline patterns.

**Effort:** TBD — requires its own detailed implementation plan | **Risk:** HIGH

This phase is a separate planning effort. High-level outline based on the TikTok research:

#### Pre-requisite: Two-step planning split (deferred from Phase 3)

Phase 3 extracted shared data-loading functions into `src/shared/content_planner.py` but kept the single-shot Claude call (blog topics + pin specs in one call) unchanged. Before TikTok can share the content planning layer, the single-shot call must be split into two steps:

1. **Add `generate_content_plan()` to `src/shared/content_planner.py`** — new Claude call using `prompts/shared/content_strategy.md` that outputs topics only (pillar assignments, keyword targets, content type recommendations, no pin/channel specs)
2. **Create `src/pinterest/pin_planner.py`** with `generate_pin_plan(content_plan)` — takes the topic plan and calls Claude to derive 28 pin specs (board distribution, template selection, scheduling). Calls existing `plan_validator.validate_plan()` for constraint checking.
3. **Create `prompts/shared/content_strategy.md`** — unified planning prompt (topics only, no pin specs)
4. **Update `src/pinterest/generate_weekly_plan.py`** to call `content_planner.generate_content_plan()` → `pin_planner.generate_pin_plan()` instead of the single-shot `claude.generate_weekly_plan()`
5. **Side-by-side output comparison** — generate plans with old single-shot and new two-step, verify equivalent quality. Keep single-shot as a fallback flag during transition.

This split enables `src/tiktok/tiktok_planner.py` to call the same `content_planner.generate_content_plan()` and derive TikTok-specific content from the shared topic plan.

#### Posting via Publer (not direct TikTok API)

**Decision (2026-03-03):** Use Publer (publer.com) as the posting and analytics intermediary instead of integrating the TikTok Content Posting API and Display API directly. Rationale:

- **No API audit required.** The TikTok Content Posting API requires a fully built app with mandatory UX elements, demo videos, and a 2-4 week audit. Publer handles TikTok's OAuth and API integration on their end.
- **No token management burden.** TikTok access tokens expire every 24 hours. Publer uses a static API key.
- **Analytics included.** Publer's post insights endpoint returns views, likes, comments, shares, and engagement rate — sufficient for our weekly review workflow. Avoids the separate TikTok Display API approval process (sandbox prototype + demo video + privacy policy page + 1-3 week review).
- **Cost:** Publer Business plan, 1 TikTok account, annual billing = **$8/month**.
- **Fallback:** If we outgrow Publer's analytics (need audience demographics, traffic sources, daily granularity), we can apply for the TikTok Display API later. By then we'll have real TikTok posts to show in the required demo video, making approval easier.

**Service evaluated against:** Late (getlate.dev), Metricool, OneUp. Publer chosen for best balance of maturity (13+ years, 300K users, bootstrapped), API documentation quality, pricing, and analytics-via-API support. Full comparison in `docs/research/tiktok/posting-service-comparison.md` (to be created in Phase 7).

**Publer API base URL:** `https://app.publer.com/api/v1`

**Rate limit:** ~100 requests per 2 minutes per user (unverified — implement exponential backoff on 429 responses)

**New env vars:** `PUBLER_API_KEY`, `PUBLER_WORKSPACE_ID`, `PUBLER_TIKTOK_ACCOUNT_ID`, `TIKTOK_POSTING_ENABLED`, `TIKTOK_GOOGLE_SHEET_ID`, `TIKTOK_GOOGLE_SHEET_URL`

**Open questions to verify during Publer trial:**
- Confirm Business plan (not just Enterprise) includes API access
- Confirm TikTok **saves** are returned in post insights (critical for feedback loop)
- Confirm `is_aigc` (AI content disclosure) flag is available through Publer's TikTok options — unlabeled AI content gets -73% reach suppression

#### Phase 8a: Carousels + posting (Weeks 1-2)
- **Two-step planning split** (see pre-requisite above)
- `src/tiktok/apis/publer_api.py` — Publer REST API wrapper (~80 lines, API key auth via `Bearer-API` header + workspace ID). Handles: media import from GCS URLs, carousel post scheduling, job status polling, post insights retrieval. Same pattern as `pinterest_api.py`.
- `src/tiktok/tiktok_planner.py` — takes unified content plan, generates carousel specs (can also generate independent trend-reactive content)
- `src/tiktok/carousel_assembler.py` — adapt Puppeteer renderer for 1080x1920 multi-slide
- `src/tiktok/post_content.py` — posting via Publer API (schedules posts with ISO 8601 timestamps + timezone)
- `prompts/tiktok/carousel_copy.md` — TikTok-native hooks and copy
- TikTok-specific Google Sheet tabs for approval
- `.github/workflows/tiktok-*.yml` — planning, generation, posting workflows
- Target: 3 carousels/day
- **Publer-specific:** Media uploaded via `/media/from-url` endpoint (accepts GCS URLs directly). Post creation returns a job ID — poll `/job_status/{job_id}` to confirm success. Up to 35 images per carousel. TikTok options: privacy level, allow comments, auto-add music.

#### Phase 8b: Video + audio (Weeks 3-5)
- **Pre-requisite:** Verify Publer supports TikTok video posting via API (likely yes based on their docs, but must confirm before starting). If not, evaluate adding direct TikTok Content Posting API for video only.
- Video rendering via Creatomate (Phase 1 bridge) or Remotion (long-term)
- ElevenLabs TTS integration
- Epidemic Sound music licensing
- `src/tiktok/video_renderer.py`
- Target: mix of carousels + video, 3 posts/day total

#### Phase 8c: Analytics feedback loop (Week 6)
- `src/tiktok/pull_analytics.py` — pulls TikTok post metrics via Publer's `GET /api/v1/analytics/{account_id}/post_insights` endpoint. Returns: views, likes, comments, shares, engagement rate. Paginated (10 posts/page). Data synced daily from TikTok by Publer, with manual refresh option.
- `src/tiktok/weekly_analysis.py` — performance analysis (same pattern as Pinterest's)
- Feed TikTok analytics into `src/shared/content_planner.py` alongside Pinterest data
- Attribute-based feedback loop (70/30 exploit/explore)
- **Future option:** If deeper analytics needed (audience demographics, traffic sources, daily time-series), apply for TikTok Display API (`video.list` scope). The Display API returns lifetime totals only (must store snapshots and diff), has 24-hour token expiry, and requires sandbox prototype + demo video for approval. Estimated effort: 15-25 hours + 1-3 week approval.

#### Key TikTok-specific decisions (to be resolved before Phase 8)
- Account type: Creator vs. Business
- First subcommunity target (#MomTok, #FoodTok, #MealPrep)
- AI content disclosure policy (TikTok requires labeling; unlabeled = -73% reach)
- Engagement staffing (20-30 min post-publish required for ranking)
- Publer Business plan setup + API key provisioning (do before Phase 8a starts)

---

## Effort Summary

| Phase | Description | Hours | Risk | Depends on |
|-------|-------------|-------|------|------------|
| 1 | Create structure, move shared code | 4-6 | LOW | — |
| 2 | Extract content memory & analytics utils | 3-4 | MEDIUM | Phase 1 |
| 3 | Split planning into unified + channel-specific | 8-12 | HIGH | Phase 2 |
| 4 | Move prompts into subdirectories | 2-3 | LOW | Phase 3 |
| 5 | Update GitHub Actions workflows | 2-3 | MEDIUM | Phase 4 |
| 6 | Cleanup (delete shims, update docs) | 2-3 | LOW | Phase 5 |
| 7 | Migrate TikTok research + rename repo | 2-3 | LOW | Phase 6 |
| 8a | TikTok carousels + posting (via Publer) | 140-198 | MEDIUM | Phase 7 |
| 8b | TikTok video + audio | TBD | HIGH | Phase 8a |
| 8c | TikTok analytics feedback loop (via Publer) | (included in 8a) | LOW | Phase 8a |
| **Restructure total (Phases 1-7)** | | **23-34** | | |
| **TikTok MVP (Phase 8a+c)** | | **140-198** | | |

---

## What This Enables

After the restructure (Phases 1-7), adding any new channel means:

1. Create `src/{channel}/` with channel-specific modules (planner, content creator, poster, analytics)
2. Create `prompts/{channel}/` with channel-specific prompts
3. The channel planner calls `src/shared/content_planner.generate_content_plan()` to get the weekly topic plan, then derives channel-specific content — or generates independent content
4. Channel analytics feed back into the shared content planner alongside all other channels
5. Content memory automatically deduplicates across all channels
6. Add `.github/workflows/{channel}-*.yml` for channel-specific scheduling

No changes needed to the shared layer or existing channel code.
