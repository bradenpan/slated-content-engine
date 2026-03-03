# Multi-Channel Restructure — Execution Strategy

**Date:** 2026-03-02
**Status:** Active — Phase 1 complete, Phase 2 next

---

## Table of Contents

- [Approach](#approach)
- [Why Not a Multi-Phase Swarm](#why-not-a-multi-phase-swarm)
- [Agent Pattern Per Phase](#agent-pattern-per-phase)
- [Failure-Mode Checklist (Review Agent)](#failure-mode-checklist-review-agent)
- [Phase Breakdown and Sub-Steps](#phase-breakdown-and-sub-steps)
  - [Phase 1: Create structure, move purely shared code](#phase-1-create-structure-move-purely-shared-code)
  - [Phase 2: Extract content memory and analytics utilities](#phase-2-extract-content-memory-and-analytics-utilities)
  - [Phase 3: Split planning into unified + channel-specific](#phase-3-split-planning-into-unified--channel-specific)
  - [Phase 4: Move prompts into subdirectories](#phase-4-move-prompts-into-subdirectories)
  - [Phase 5: Update GitHub Actions workflows](#phase-5-update-github-actions-workflows)
  - [Phase 6: Cleanup and burn-in](#phase-6-cleanup-and-burn-in)
- [Folder and Repo Rename](#folder-and-repo-rename)
- [Verification Between Phases](#verification-between-phases)

---

## Required Reading (Before Starting Any Phase)

An agent executing any phase MUST read these documents first:

1. **`ARCHITECTURE.md`** — Current system architecture, directory structure, file responsibilities, data flows, gotchas
2. **`architecture/multi-channel-restructure/execution-strategy.md`** — This document. Failure-mode checklist (items 1-10), sub-steps, verification requirements
3. **`architecture/multi-channel-restructure/implementation-plan.md`** — Master restructure plan with all phases, directory structure, and effort estimates
4. **`.github/workflows/*.yml` and `.github/actions/*/action.yml`** — All workflow files. Cross-reference against any file being moved to determine if it's invoked via `python -m` (see checklist item #9)
5. **`memory-bank/architecture/architecture-data-flows.md`** — Schema details, column layouts, field mappings (relevant when moving files that interact with Sheets or content log)

---

## Approach

Execute **one phase at a time**, sequentially. Each phase gets two agents:

1. **Implementation Agent** — Makes the actual file moves, import rewrites, new files. Runs in an isolated git worktree.
2. **Review Agent** — Reads the implementation diff and checks every import path, workflow reference, column constant, and filename convention against a checklist derived from 8 known historical failure modes.

After both agents complete, run `python -m pytest tests/` and import smoke tests. Only proceed to the next phase after tests pass and the user confirms the live pipeline works.

---

## Why Not a Multi-Phase Swarm

The restructure has **114 cross-module imports** across 39 Python files, 14 workflows, and 20 test files. A multi-phase swarm was rejected because:

1. **Phases are strictly sequential** — Phase 2 depends on Phase 1's output, etc. No parallelism to exploit.
2. **Cross-agent path consistency** — A Phase 1 agent makes path decisions. A Phase 5 agent updating workflows must use *exactly* those paths. Different agents making independent decisions about 114 imports is where naming/path bugs emerge.
3. **Real verification requires the live pipeline** — Tests cover syntax, but the actual proof is the Monday weekly cycle running end-to-end.
4. **History of path/naming failures** — 8 categories of production failures documented (see checklist below), all related to naming/path consistency. This codebase punishes subtle misalignments.

---

## Agent Pattern Per Phase

```
For each Phase (1 through 6):
  ├── Implementation Agent (general-purpose, worktree isolation)
  │     - Receives detailed sub-step instructions
  │     - Makes file moves, import rewrites, creates new files
  │     - Creates backward-compat shims where needed
  │     - Runs pytest at end
  │
  ├── Review Agent (general-purpose, reads diff)
  │     - Reads all changed files
  │     - Runs failure-mode checklist (see below)
  │     - Checks every import path against the canonical import map
  │     - Reports issues or gives approval
  │
  └── Post-phase verification
        - pytest passes
        - Import smoke tests pass
        - User confirms live pipeline works (daily posting, no errors)
        - Only then proceed to next phase
```

---

## Failure-Mode Checklist (Review Agent)

These are the 8 historical failure categories. The review agent checks every changed file against ALL of these:

### 1. Slug/Filename Consistency
- Every blog MDX filename IS the slug — goslated.com routes by filename, not frontmatter
- If any code touches slug handling, verify filename and frontmatter stay in sync

### 2. Dual Hero Image Naming
- Every hero image must exist as BOTH `{pin_id}-hero.png` AND `{slug}-hero.png`
- If code that saves/reads hero images moved, verify both paths still work

### 3. Column Index Hardcoding
- Content Queue is 12 columns (A-L), indices hardcoded in `sheets_api.py` (`CQ_COL_*`)
- If `sheets_api.py` moved, verify all column constants preserved exactly
- Apps Script uses 1-based indices; Python uses 0-based

### 4. Field Name Alignment
- Same data has different names in different systems (e.g., `slug` vs `Blog URL` vs `id`)
- If files that read/write these fields moved, verify field name usage unchanged

### 5. Directory Existence
- All directories referenced in `git add` commands need `.gitkeep` files
- New directories (`src/shared/`, `src/pinterest/`) need `__init__.py`
- Verify no `git add` in workflows references a path that won't exist

### 6. Safe Null Handling
- All external JSON access must use `safe_get()`, not bare `dict.get()`
- If `safe_get.py` moved, verify all imports updated

### 7. Import Path Completeness
- Every `from src.X` must resolve after the move
- Shims must re-export everything the old path exported
- `python -m src.X` invocations in workflows must still resolve
- **`@patch()` decorators in tests must target the canonical module path** (where the real code lives), not the shim path — mocking the shim namespace doesn't reach the real code's references

### 8. Private Function Coupling
- `regen_content.py` imports private functions from `generate_pin_content.py`
- Both files must end up in the same package OR the imports must be updated
- Functions: `_source_ai_image`, `_load_brand_voice`, `_load_keyword_targets`, `build_template_context`, `generate_copy_batch`, `load_used_image_ids`

### 9. Shim Entry Point Execution (`python -m` / `__main__`)
- **LEARNED FROM PHASE 1 INCIDENT:** Shims using `from src.X import *` only re-export symbols for import purposes. They do NOT execute the target module's `if __name__ == "__main__":` block when invoked via `python -m`.
- Every shim file that is invoked via `python -m` in a GitHub Actions workflow MUST have its own `__main__` block that delegates to the real module:
  ```python
  if __name__ == "__main__":
      import runpy
      runpy.run_module("src.target.module", run_name="__main__", alter_sys=True)
  ```
- **How to verify:** Cross-reference every `python -m src.X` in `.github/workflows/*.yml` and `.github/actions/*/action.yml` against the file at `src/X.py`. If it's a shim, it needs a `__main__` block.
- **Failure mode:** Silent no-op. The workflow step exits 0 with zero output. No error, no Slack notification, no indication anything went wrong. Extremely hard to detect without checking workflow logs for missing output.
- Shims that are only imported by other modules (never invoked via `python -m`) do NOT need `__main__` blocks.

### 10. Workflow Output Verification
- **LEARNED FROM PHASE 1 INCIDENT:** A green workflow does not mean the step did anything. After deploying changes that affect files invoked by workflows, check that workflow steps produce **expected output** (log lines, print statements), not just that they exit 0.
- For posting workflows specifically: verify Slack notification arrives AND content-log.jsonl has new entries.

---

## Phase Breakdown and Sub-Steps

### Phase 1: Create structure, move purely shared code

**Risk:** LOW | **Effort:** 4-6 hours

#### Sub-step 1a: Create directory structure
- Create `src/shared/`, `src/shared/apis/`, `src/shared/utils/`
- Create `src/pinterest/`, `src/pinterest/apis/`
- Add `__init__.py` to each new directory

#### Sub-step 1b: Create new `src/shared/paths.py`
- Replace `src/paths.py` with version at `src/shared/paths.py`
- `PROJECT_ROOT = Path(__file__).parent.parent.parent` (one more `.parent` since it's deeper)
- All constants identical: `DATA_DIR`, `STRATEGY_DIR`, `ANALYSIS_DIR`, `PROMPTS_DIR`, `TEMPLATES_DIR`, `PIN_OUTPUT_DIR`, `BLOG_OUTPUT_DIR`, `CONTENT_LOG_PATH`
- Create shim at `src/paths.py`: `from src.shared.paths import *`

#### Sub-step 1c: Move `src/config.py` → `src/shared/config.py`
- No internal imports to update (config.py only imports `os`)
- Create shim at `src/config.py`: `from src.shared.config import *`

#### Sub-step 1d: Move shared API wrappers → `src/shared/apis/`
Files (8):
- `claude_api.py` — update: `from src.apis.openai_chat_api` → `from src.shared.apis.openai_chat_api`, `from src.config` → `from src.shared.config`, `from src.paths` → `from src.shared.paths`, `from src.utils.safe_get` → `from src.shared.utils.safe_get`
- `openai_chat_api.py` — update: `from src.config` → `from src.shared.config`
- `sheets_api.py` — no internal imports
- `github_api.py` — update: `from src.config` → `from src.shared.config`
- `gcs_api.py` — no internal imports
- `drive_api.py` — no internal imports
- `slack_notify.py` — no internal imports
- `image_gen.py` — update: `from src.config` → `from src.shared.config`, `from src.paths` → `from src.shared.paths`

Create shims at old locations (`src/apis/X.py`): `from src.shared.apis.X import *`

#### Sub-step 1e: Move `pinterest_api.py` → `src/pinterest/apis/`
- Update: `from src.config` → `from src.shared.config`
- Create shim at `src/apis/pinterest_api.py`: `from src.pinterest.apis.pinterest_api import *`

#### Sub-step 1f: Move shared utilities → `src/shared/utils/`
Files (5 — NOT content_memory.py, that's Phase 2):
- `safe_get.py` — no internal imports
- `strategy_utils.py` — update: `from src.paths` → `from src.shared.paths`
- `image_utils.py` — no internal imports
- `content_log.py` — update: `from src.paths` → `from src.shared.paths`
- `plan_utils.py` — update: `from src.paths` → `from src.shared.paths`, `from src.utils.content_log` → `from src.shared.utils.content_log`, `from src.utils.content_memory` → `from src.utils.content_memory` (stays — Phase 2), `from src.utils.safe_get` → `from src.shared.utils.safe_get`

Create shims at old locations (`src/utils/X.py`): `from src.shared.utils.X import *`

#### Sub-step 1g: Move shared pipeline scripts → `src/shared/`
Files (4):
- `image_cleaner.py` — no internal imports, create shim
- `blog_generator.py` — update: `from src.apis.claude_api` → `from src.shared.apis.claude_api`, `from src.paths` → `from src.shared.paths`, `from src.utils.strategy_utils` → `from src.shared.utils.strategy_utils`. Create shim.
- `blog_deployer.py` — update all imports to `src.shared.*`. Create shim.
- `generate_blog_posts.py` — update: `from src.blog_generator` → `from src.shared.blog_generator`, `from src.paths` → `from src.shared.paths`, `from src.utils.plan_utils` → `from src.shared.utils.plan_utils`. Create shim.

#### Sub-step 1h: Move Pinterest-specific scripts → `src/pinterest/`
Files (9):
- `token_manager.py` — update: `from src.config` → `from src.shared.config`, `from src.paths` → `from src.shared.paths`. Create shim.
- `generate_pin_content.py` — update all `src.*` imports to `src.shared.*` equivalents. `from src.image_cleaner` → `from src.shared.image_cleaner`, `from src.pin_assembler` → `from src.pinterest.pin_assembler`. Create shim.
- `pin_assembler.py` — update: `from src.config` → `from src.shared.config`, `from src.image_cleaner` → `from src.shared.image_cleaner`, `from src.paths` → `from src.shared.paths`, `from src.utils.image_utils` → `from src.shared.utils.image_utils`. Create shim.
- `post_pins.py` — update all imports. Note: `from src.token_manager` → `from src.pinterest.token_manager`, `from src.apis.pinterest_api` → `from src.pinterest.apis.pinterest_api`. Create shim.
- `pull_analytics.py` — update: `from src.apis.pinterest_api` → `from src.pinterest.apis.pinterest_api`, `from src.token_manager` → `from src.pinterest.token_manager`, others to `src.shared.*`. Create shim.
- `setup_boards.py` — update similarly. Create shim.
- `regen_content.py` — update all imports. Note: `from src.generate_pin_content` → `from src.pinterest.generate_pin_content` (same package). Create shim.
- `plan_validator.py` — update: `from src.paths` → `from src.shared.paths`, `from src.utils.*` → `from src.shared.utils.*`. Create shim.
- `redate_schedule.py` — update: `from src.paths` → `from src.shared.paths`, `from src.utils.plan_utils` → `from src.shared.utils.plan_utils`. Create shim.

#### Sub-step 1i: Verify
- `python -m pytest tests/` — all tests pass
- Import smoke test for every moved module (via new path AND via shim)
- No orphaned imports: `grep -r "from src\." src/ --include="*.py"` shows only `src.shared.*`, `src.pinterest.*`, or shim files

#### Files that stay in `src/` for now (moved in later phases):
- `generate_weekly_plan.py` (Phase 3)
- `weekly_analysis.py` (Phase 2)
- `monthly_review.py` (Phase 2)
- `regen_weekly_plan.py` (Phase 3)
- `publish_content_queue.py` (Phase 2)
- `utils/content_memory.py` (Phase 2)
- `recover_w9_pins.py` (evaluate for deletion in Phase 6)

---

### Phase 2: Extract content memory and analytics utilities

**Risk:** MEDIUM | **Effort:** 3-4 hours

**CRITICAL:** For every file moved in this phase, check if it's invoked via `python -m` in any workflow (see checklist item #9). If so, the shim at the old location MUST include a `__main__` block using `runpy.run_module()`. Failure to do this causes silent no-ops — the workflow step exits 0 with zero output.

#### Sub-step 2a: Consolidate content memory
- Create `src/shared/content_memory.py` from the canonical `generate_weekly_plan.py` implementation
- Delete `src/utils/content_memory.py` (replace with shim pointing to shared)
- **Note:** `python -m src.utils.content_memory` is invoked in `weekly-review.yml` — the shim MUST have a `__main__` block
- Diff output against baseline to ensure identical results

#### Sub-step 2b: Extract analytics utilities
- Create `src/shared/analytics_utils.py` with functions extracted from `pull_analytics.py`:
  - `compute_derived_metrics()`
  - `aggregate_by_dimension()`
- Update `monthly_review.py` and `weekly_analysis.py` to import from shared

#### Sub-step 2c: Move remaining files to `src/pinterest/`
- `weekly_analysis.py` → `src/pinterest/weekly_analysis.py`
  - **Workflow:** `python -m src.weekly_analysis` in `weekly-review.yml` — shim needs `__main__` block
- `monthly_review.py` → `src/pinterest/monthly_review.py`
  - **Workflow:** `python -m src.monthly_review` in `monthly-review.yml` — shim needs `__main__` block
- `publish_content_queue.py` → `src/pinterest/publish_content_queue.py`
  - **Workflow:** `python -m src.publish_content_queue` in `generate-content.yml` — shim needs `__main__` block
- Create shims at old locations (all 3 need `__main__` + `runpy.run_module()`)

#### Sub-step 2d: Verify
- Content memory output identical to previous version
- All tests pass
- Shims work for both import AND `python -m` execution
- Cross-reference ALL `python -m` invocations in workflows against shim files — every shim invoked via `python -m` must have a `__main__` block

---

### Phase 3: Split planning into unified + channel-specific

**Risk:** HIGH | **Effort:** 8-12 hours

**This phase is broken into 4 sub-steps due to complexity.**

#### Sub-step 3a: Extract shared planning functions → `src/shared/content_planner.py`
- Extract from `generate_weekly_plan.py`: `load_strategy_context()`, `load_content_memory()`, `load_latest_analysis()`, `get_current_seasonal_window()`
- These are the generic functions that any channel planner would need
- No behavior change — just extraction

#### Sub-step 3b: Extract Pinterest constraints → `src/pinterest/pin_planner.py`
- Extract: board distribution, template distribution, scheduling logic
- All Pinterest-specific validation and constraint checking
- **NOTE (Phase 2 finding):** `validate_plan()`, `PILLAR_MIX_TARGETS`, `TOTAL_WEEKLY_PINS`, `MAX_PINS_PER_BOARD` are already in `src/pinterest/plan_validator.py` (moved Phase 1, imports updated Phase 2). Decide whether `pin_planner.py` absorbs `plan_validator.py` or calls it — do not duplicate.
- **NOTE (Phase 2 finding):** `identify_replaceable_posts()`, `splice_replacements()`, `build_keyword_performance_data()`, `extract_recent_topics()` are already in `src/shared/utils/plan_utils.py` (moved Phase 1). Do not re-extract.

#### Sub-step 3c: Rewrite orchestrator → `src/pinterest/generate_weekly_plan.py`
- New file that calls `content_planner.generate_content_plan()` then `pin_planner.generate_pin_plan()`
- Must produce structurally identical output to the old single-step approach
- Keep old single-step as a fallback flag during transition

#### Sub-step 3d: Side-by-side output comparison
- Generate a plan with old code, generate with new code, diff
- Verify constraint compliance, pin counts, blog topic quality
- Move `regen_weekly_plan.py` → `src/pinterest/regen_weekly_plan.py`
- **NOTE (Phase 2 finding):** `regen_weekly_plan.py` imports `load_content_memory` from `src.generate_weekly_plan`. This cross-dependency must be resolved during the split — likely by importing from `src.shared.content_planner` (where `load_content_memory` will live after sub-step 3a) instead.

#### Sub-step 3e: Create `prompts/shared/content_strategy.md`
- New prompt for unified planning (topics only, no pin specs)

---

### Phase 4: Move prompts into subdirectories

**Risk:** LOW | **Effort:** 2-3 hours

#### Sub-step 4a: Create prompt subdirectories
- Create `prompts/shared/` and `prompts/pinterest/`

#### Sub-step 4b: Move prompt files
- To `prompts/shared/`: `blog_post_guide.md`, `blog_post_listicle.md`, `blog_post_recipe.md`, `blog_post_weekly_plan.md`, `image_prompt.md`, `content_strategy.md` (from Phase 3)
- To `prompts/pinterest/`: `weekly_plan.md`, `weekly_plan_replace.md`, `pin_copy.md`, `weekly_analysis.md`, `monthly_review.md`

#### Sub-step 4c: Update all `load_prompt_template()` calls
- Every `ClaudeAPI.load_prompt_template("X.md")` → `load_prompt_template("shared/X.md")` or `load_prompt_template("pinterest/X.md")`

#### Sub-step 4d: Verify
- Each prompt loads correctly via import test
- All tests pass

---

### Phase 5: Update GitHub Actions workflows

**Risk:** MEDIUM | **Effort:** 2-3 hours

#### Sub-step 5a: Update `python -m` invocations in all workflow files
Full mapping documented in implementation-plan.md Phase 5 table.

#### Sub-step 5b: Update inline Python in workflows
- All `from src.apis.slack_notify import SlackNotify` → `from src.shared.apis.slack_notify import SlackNotify`

#### Sub-step 5c: Verify workflow syntax
- `actionlint` or manual YAML validation
- Trigger each workflow via `workflow_dispatch` if possible

---

### Phase 6: Cleanup and burn-in

**Risk:** LOW + 1-week gate | **Effort:** 2-3 hours + 1 week

#### Sub-step 6a: Delete all backward-compat shim files
- Remove shims from `src/`, `src/apis/`, `src/utils/`
- Delete empty directories

#### Sub-step 6b: Verify no old-path imports remain
- `grep -r "from src\." src/ --include="*.py" | grep -v "src.shared\|src.pinterest"` should return nothing

#### Sub-step 6c: Update documentation
- Update `ARCHITECTURE.md` directory structure section
- Update `CLAUDE.md` key paths
- Update `memory-bank/architecture/architecture-data-flows.md`

#### Sub-step 6d: Burn-in (1 full weekly cycle)
- Monday: weekly-review workflow runs
- Plan approval → generate-content workflow
- Content approval → promote-and-schedule
- Tue-Mon: daily posting (4 pins/day)
- Slack notifications arrive
- No import errors in any workflow logs

**Do not proceed to Phase 7 until burn-in passes.**

---

## Folder and Repo Rename

### When to rename
- **Local folder:** Safe to rename anytime after Phase 6 burn-in passes. The local folder name does not affect any code paths — Python imports use `src.`, not the folder name.
- **GitHub repo:** Phase 7 of the implementation plan. Must update `src/apps-script/trigger.gs` line 71 first.

### Recommended name
- **`slated-content-engine`** — matches the implementation plan and reflects the multi-channel purpose.
- Local folder: `C:\dev\slated-content-engine`
- GitHub repo: `bradenpan/slated-content-engine`

### What must happen before rename
1. Phase 6 burn-in passes (pipeline stable with new structure)
2. Update `trigger.gs` line 71: `var repo = "bradenpan/slated-content-engine";`
3. Deploy updated Apps Script to Google Sheets
4. Rename on GitHub
5. Update local remote: `git remote set-url origin https://github.com/bradenpan/slated-content-engine.git`
6. Rename local folder

---

## Verification Between Phases

Each phase boundary requires:

1. **`python -m pytest tests/`** — all tests pass
2. **Import smoke tests** — `python -c "from src.shared.X import Y; print('OK')"` for moved modules
3. **Shim verification** — old import paths still resolve (until Phase 6 removes shims)
4. **User confirmation** — daily posting works, no workflow errors in GitHub Actions logs
5. **No regression in Slack notifications** — all pipeline steps still notify

Only proceed to the next phase after ALL checks pass.
