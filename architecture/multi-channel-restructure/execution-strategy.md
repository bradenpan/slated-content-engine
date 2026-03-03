# Multi-Channel Restructure — Execution Strategy

**Date:** 2026-03-02
**Status:** Active — Phases 1-7 complete, Phase 8 next

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

**Risk:** LOW-MEDIUM | **Effort:** 4-6 hours

**UPDATED (Phase 3 execution):** Original plan called for a two-step Claude call split (content plan → pin plan) and `pin_planner.py` creation. Both deferred to Phase 8a (TikTok) because: (1) the two-step split is a behavior change with quality risk, not a refactoring, (2) `pin_planner.py`'s intended contents already exist in `plan_validator.py` and `plan_utils.py`, (3) the file reorganization alone achieves the restructure goal. See Phase 8a pre-requisite in implementation-plan.md.

#### Sub-step 3a: Extract shared planning functions → `src/shared/content_planner.py`
- Extract from `generate_weekly_plan.py`: `load_strategy_context()`, `load_content_memory()`, `load_latest_analysis()`, `get_current_seasonal_window()`
- These are the generic functions that any channel planner would need
- No behavior change — just extraction

#### Sub-step 3b: Move orchestrator → `src/pinterest/generate_weekly_plan.py`
- Move `generate_plan()`, `_validate_plan_structure()`, `_build_reprompt_context()`, `generate_weekly_plan()`, `__main__` block
- Update all imports to canonical `src.shared.*` / `src.pinterest.*` paths
- Identical behavior — same single-shot Claude call, same prompt, same output

#### Sub-step 3c: Move `regen_weekly_plan.py` → `src/pinterest/regen_weekly_plan.py`
- Update imports to canonical paths
- **Cross-dependency resolved:** `load_content_memory` imported from `src.shared.content_planner` instead of `src.generate_weekly_plan`
- Consolidate late import of `TAB_WEEKLY_REVIEW`/`WR_CELL_PLAN_STATUS` into top-level imports

#### Sub-step 3d: Create backward-compat shims
- `src/generate_weekly_plan.py` → shim with `import *`, private re-exports (`_validate_plan_structure`, `_build_reprompt_context`), shared function re-exports, `__main__` block
- `src/regen_weekly_plan.py` → shim with `import *`, `__main__` block
- Both invoked via `python -m` in workflows — `__main__` blocks required

#### Sub-step 3e: Update tests
- `tests/test_plan_structure_validation.py` — update import to `src.pinterest.generate_weekly_plan`

#### Deferred to Phase 8a
- `src/pinterest/pin_planner.py` — houses `generate_pin_plan()` for two-step Claude call
- `prompts/shared/content_strategy.md` — unified planning prompt (topics only)
- Two-step Claude call split: `content_planner.generate_content_plan()` → `pin_planner.generate_pin_plan()`

---

### Phase 4: Move prompts into subdirectories

**Risk:** LOW | **Effort:** 2-3 hours

#### Sub-step 4a: Create prompt subdirectories
- Create `prompts/shared/` and `prompts/pinterest/`

#### Sub-step 4b: Move prompt files
- To `prompts/shared/`: `blog_post_guide.md`, `blog_post_listicle.md`, `blog_post_recipe.md`, `blog_post_weekly_plan.md`, `image_prompt.md`
- **NOTE:** `content_strategy.md` was originally planned for Phase 3 but deferred to Phase 8a (TikTok). It will be created when the two-step Claude call is implemented. Do NOT create it in Phase 4.
- To `prompts/pinterest/`: `weekly_plan.md`, `weekly_plan_replace.md`, `pin_copy.md`, `weekly_analysis.md`, `monthly_review.md`

#### Sub-step 4c: Update all `load_prompt_template()` calls

**All calls live in ONE file:** `src/shared/apis/claude_api.py`. No other file calls `load_prompt_template()`.

The method resolves paths via `PROMPTS_DIR / template_name` (line 91 of `claude_api.py`). Since `PROMPTS_DIR` is `PROJECT_ROOT / "prompts"`, changing `"weekly_plan.md"` to `"pinterest/weekly_plan.md"` will resolve to `prompts/pinterest/weekly_plan.md`. No code change needed to the method itself — just update the template name strings passed to it.

**Exact change map (8 call sites in `claude_api.py`):**

| Line | Current | New | Method |
|------|---------|-----|--------|
| 158 | `"weekly_plan.md"` | `"pinterest/weekly_plan.md"` | `generate_weekly_plan()` |
| 226 | `"pin_copy.md"` | `"pinterest/pin_copy.md"` | `generate_pin_copy()` |
| 312-316 | `"blog_post_recipe.md"`, `"blog_post_weekly_plan.md"`, `"blog_post_guide.md"`, `"blog_post_listicle.md"` | `"shared/blog_post_recipe.md"`, etc. | `generate_blog_post()` template_map |
| 387 | `"image_prompt.md"` | `"shared/image_prompt.md"` | `generate_image_prompt()` |
| 461 | `"weekly_plan_replace.md"` | `"pinterest/weekly_plan_replace.md"` | `generate_replacement_posts()` |
| 551 | `"weekly_analysis.md"` | `"pinterest/weekly_analysis.md"` | `generate_weekly_analysis()` |
| 615 | `"monthly_review.md"` | `"pinterest/monthly_review.md"` | `generate_monthly_review()` |
| 882 | `"weekly_plan.md"` | `"pinterest/weekly_plan.md"` | `__main__` smoke test |

**Also update:** Line 877 `PROMPTS_DIR.glob("*.md")` in the `__main__` smoke test — after the move, prompts are in subdirectories, so this should become `PROMPTS_DIR.glob("**/*.md")` to find them.

**No shims needed.** Prompt files aren't imported by Python — they're read from disk. Moving them is a straight `git mv` with no backward-compat concern.

#### Sub-step 4d: Verify
- Each prompt loads correctly: `python -c "from src.shared.apis.claude_api import ClaudeAPI; c = ClaudeAPI.__new__(ClaudeAPI); print(len(c.load_prompt_template('shared/image_prompt.md')))"` (repeat for all 10)
- Verify no `.md` files remain in `prompts/` root (all should be in subdirectories)
- All tests pass (`python -m pytest tests/`)
- No `load_prompt_template()` calls use bare filenames without a subdirectory prefix

---

### Phase 5: Update GitHub Actions workflows

**Risk:** MEDIUM | **Effort:** 2-3 hours

#### Sub-step 5a: Update `python -m` invocations in all workflow files

**Complete change map (29 `python -m` invocations across 14 files + 1 action):**

##### `weekly-review.yml` (5 changes)
| Line | Current | New |
|------|---------|-----|
| 44 | `python -m src.token_manager` | `python -m src.pinterest.token_manager` |
| 47 | `python -m src.pull_analytics` | `python -m src.pinterest.pull_analytics` |
| 52 | `python -m src.utils.content_memory` | `python -m src.shared.content_memory` |
| 56 | `python -m src.weekly_analysis` | `python -m src.pinterest.weekly_analysis` |
| 62 | `python -m src.generate_weekly_plan` | `python -m src.pinterest.generate_weekly_plan` |

##### `generate-content.yml` (4 changes)
| Line | Current | New |
|------|---------|-----|
| 54 | `python -m src.token_manager` | `python -m src.pinterest.token_manager` |
| 59 | `python -m src.generate_blog_posts` | `python -m src.shared.generate_blog_posts` |
| 65 | `python -m src.generate_pin_content` | `python -m src.pinterest.generate_pin_content` |
| 71 | `python -m src.publish_content_queue` | `python -m src.pinterest.publish_content_queue` |

##### `deploy-and-schedule.yml` (1 change)
| Line | Current | New |
|------|---------|-----|
| 42 | `python -m src.blog_deployer preview` | `python -m src.shared.blog_deployer preview` |

##### `promote-and-schedule.yml` (3 changes)
| Line | Current | New |
|------|---------|-----|
| 49 | `python -m src.token_manager` | `python -m src.pinterest.token_manager` |
| 57 | `python -m src.blog_deployer promote` | `python -m src.shared.blog_deployer promote` |
| 63 | `python -m src.redate_schedule "$PIN_START_DATE"` | `python -m src.pinterest.redate_schedule "$PIN_START_DATE"` |

##### `daily-post-morning.yml` (2 changes)
| Line | Current | New |
|------|---------|-----|
| 47 | `python -m src.token_manager` | `python -m src.pinterest.token_manager` |
| 50 | `python -m src.post_pins morning ${{ ... date_override ... }}` | `python -m src.pinterest.post_pins morning ${{ ... date_override ... }}` |

**IMPORTANT:** Line 50 has a `date_override` expression — only change the module path, preserve the rest. See "Notes for Phase 5 agent" below.

##### `daily-post-afternoon.yml` (2 changes)
| Line | Current | New |
|------|---------|-----|
| 47 | `python -m src.token_manager` | `python -m src.pinterest.token_manager` |
| 50 | `python -m src.post_pins afternoon ${{ ... date_override ... }}` | `python -m src.pinterest.post_pins afternoon ${{ ... date_override ... }}` |

**IMPORTANT:** Line 50 has a `date_override` expression — only change the module path, preserve the rest.

##### `daily-post-evening.yml` (2 changes)
| Line | Current | New |
|------|---------|-----|
| 49 | `python -m src.token_manager` | `python -m src.pinterest.token_manager` |
| 52 | `python -m src.post_pins evening ${{ ... date_override ... }}` | `python -m src.pinterest.post_pins evening ${{ ... date_override ... }}` |

**IMPORTANT:** Line 52 has a `date_override` expression — only change the module path, preserve the rest.

##### `monthly-review.yml` (3 changes)
| Line | Current | New |
|------|---------|-----|
| 66 | `python -m src.token_manager` | `python -m src.pinterest.token_manager` |
| 70 | `python -m src.pull_analytics 30` | `python -m src.pinterest.pull_analytics 30` |
| 78 | `python -m src.monthly_review` | `python -m src.pinterest.monthly_review` |

##### `regen-plan.yml` (1 change)
| Line | Current | New |
|------|---------|-----|
| 36 | `python -m src.regen_weekly_plan` | `python -m src.pinterest.regen_weekly_plan` |

##### `regen-content.yml` (1 change)
| Line | Current | New |
|------|---------|-----|
| 54 | `python -m src.regen_content` | `python -m src.pinterest.regen_content` |

##### `regen-blogs-only.yml` (1 change)
| Line | Current | New |
|------|---------|-----|
| 35 | `python -m src.generate_blog_posts` | `python -m src.shared.generate_blog_posts` |

##### `setup-boards.yml` (2 changes)
| Line | Current | New |
|------|---------|-----|
| 30 | `python -m src.token_manager` | `python -m src.pinterest.token_manager` |
| 33 | `python -m src.setup_boards` | `python -m src.pinterest.setup_boards` |

##### `recover-w9-pins.yml` (1 change — or delete entirely)
| Line | Current | New |
|------|---------|-----|
| 45 | `python -m src.recover_w9_pins` | Delete workflow (header says "DELETE after W9 pins posted by Mar 4, 2026") |

##### `.github/actions/notify-failure/action.yml` (1 change — highest leverage, fixes all 13+ workflows)
| Line | Current | New |
|------|---------|-----|
| 22 | `python -m src.apis.slack_notify ...` | `python -m src.shared.apis.slack_notify ...` |

#### Sub-step 5b: Update inline Python in workflows (1 change)
- `year-wrap-reminder.yml` line 42: `from src.apis.slack_notify import SlackNotify` → `from src.shared.apis.slack_notify import SlackNotify`

#### Sub-step 5c: Handle one-time workflows
- `recover-w9-pins.yml` — header says "DELETE THIS WORKFLOW after W9 pins have posted successfully (by Mar 4, 2026)." Evaluate whether to delete it now or update its path. `src/recover_w9_pins.py` was never moved to `src/pinterest/` — it's still in `src/` root (non-shim). If kept, needs a move + shim + workflow path update.
- `regen-blogs-only.yml` — header says "DELETE THIS WORKFLOW after W10 blogs have deployed successfully." Evaluate whether to delete.

#### Sub-step 5d: Verify workflow syntax
- `actionlint` or manual YAML validation
- Trigger each workflow via `workflow_dispatch` if possible

#### Notes for Phase 5 agent
- **CLI arguments:** Several modules accept positional args (`blog_deployer preview|promote`, `post_pins morning|afternoon|evening`, `pull_analytics 30`, `redate_schedule "$PIN_START_DATE"`). After updating paths, verify the `__main__` block in each canonical file properly handles `sys.argv`. Shims already delegate via `runpy.run_module(..., alter_sys=True)` which preserves argv.
- **`date_override` in daily-post workflows (CRITICAL — do not clobber):** The three `daily-post-*.yml` files have a `workflow_dispatch` input called `date_override` and a conditional `format()` expression on the `post_pins` run line. When updating the module path from `src.post_pins` to `src.pinterest.post_pins`, preserve the FULL run line including the `date_override` expression. The current line looks like:
  ```yaml
  run: python -m src.post_pins morning ${{ inputs.date_override && format('--date={0}', inputs.date_override) || '' }}
  ```
  After Phase 5, it should be:
  ```yaml
  run: python -m src.pinterest.post_pins morning ${{ inputs.date_override && format('--date={0}', inputs.date_override) || '' }}
  ```
  Only the module path changes. The `workflow_dispatch` inputs block, the `format()` expression, and the `--date=` flag must remain intact. These were added in Phase 19b (post-Phase 1 incident recovery) and are used for manual recovery of missed posting windows.
- **`src.utils.content_memory` → `src.shared.content_memory`:** This is the only path that changes structurally (drops the `utils/` level). The shim at `src/utils/content_memory.py` already has a `__main__` block, but after Phase 5 the workflow should point directly to the canonical module.
- **No `setup-pipeline/action.yml` or `commit-data/action.yml` changes needed** — neither references `src/` Python modules.
- **No prompt file references in any workflow** — all prompt loading goes through `claude_api.py` (handled in Phase 4).
- **After Phase 5, backward-compat shims are no longer needed by workflows.** Phase 6 can safely delete them — but only after verifying all workflows run successfully with the new paths.

---

### Phase 6: Cleanup

**Risk:** LOW | **Effort:** 2-3 hours

#### Notes from Phase 5 (for the Phase 6 agent)

**Shim status after Phase 5:** No workflow or action file references any shim path. All `python -m` invocations point directly to canonical modules in `src/shared/` or `src/pinterest/`. Shims are only needed by: (a) other shims that chain-import, (b) test files that haven't been updated yet, or (c) any Python files still using old `from src.X` imports. The Phase 6 agent should grep for all shim consumers before deleting.

**Files already deleted in Phase 5:**
- `.github/workflows/recover-w9-pins.yml` — workflow deleted, but `src/recover_w9_pins.py` (the Python script) still exists in `src/` root. It was never moved to `src/pinterest/` and has no shim. Phase 6 should delete this Python file too.
- `.github/workflows/regen-blogs-only.yml` — workflow deleted, no orphaned Python files.
- `regen-blogs-only.yml` and `recover-w9-pins.yml` have already been removed from ARCHITECTURE.md's workflow table.

**`year-wrap-reminder.yml`:** This workflow was updated in Phase 5 (inline import changed from `src.apis.slack_notify` to `src.shared.apis.slack_notify`). It was already an untracked new file before Phase 5. It will be included in the Phase 5 commit.

**Test files:** All 207 tests pass with the current shim setup. When Phase 6 deletes shims, any test that imports via old paths (e.g., `from src.apis.X`) will break. Phase 6 must update test imports to canonical paths before or alongside shim deletion.

#### Sub-step 6a: Delete all backward-compat shim files
- Remove shims from `src/`, `src/apis/`, `src/utils/`
- Delete `src/recover_w9_pins.py` (orphaned — workflow deleted in Phase 5)
- Delete empty directories (`src/apis/`, `src/utils/` if empty after shim removal)

#### Sub-step 6b: Update test imports
- Update any test files that import via old shim paths to use canonical `src.shared.*` / `src.pinterest.*` paths
- Run `grep -rn "from src\." tests/ --include="*.py" | grep -v "src.shared\|src.pinterest"` to find them

#### Sub-step 6c: Verify no old-path imports remain
- `grep -r "from src\." src/ --include="*.py" | grep -v "src.shared\|src.pinterest"` should return nothing
- `grep -r "from src\." tests/ --include="*.py" | grep -v "src.shared\|src.pinterest"` should return nothing

#### Sub-step 6d: Update documentation
- Update `ARCHITECTURE.md` directory structure section (remove shim directories, remove `recover_w9_pins.py`)
- Update `CLAUDE.md` key paths
- Update `memory-bank/architecture/architecture-data-flows.md`

#### Sub-step 6e: Verify
- **1 full day of posting** (all 3 daily slots fire successfully with no shim safety net)
- If something breaks, it will be an immediate import error (not a silent no-op) — restore the shim file and investigate
- No week-long gate — Phase 7 and TikTok pre-build can start in parallel (see below)

#### Notes from Phase 6 (for the Phase 7 agent)

##### 1. `board-structure.json` — 5 path references that will break

The implementation plan says to move `strategy/board-structure.json` → `strategy/pinterest/board-structure.json`. All 5 Python files that load this file construct the path via `STRATEGY_DIR / "board-structure.json"` and must be updated to `STRATEGY_DIR / "pinterest" / "board-structure.json"`.

**PATH references (BREAKING — file won't load if not updated):**

| File | Line | Code |
|------|------|------|
| `src/pinterest/setup_boards.py` | 25 | `BOARD_STRUCTURE_PATH = STRATEGY_DIR / "board-structure.json"` |
| `src/pinterest/post_pins.py` | 59 | `BOARD_STRUCTURE_PATH = STRATEGY_DIR / "board-structure.json"` |
| `src/pinterest/plan_validator.py` | 88 | `(STRATEGY_DIR / "board-structure.json").read_text(encoding="utf-8")` |
| `src/pinterest/monthly_review.py` | 500 | `board_structure_path = STRATEGY_DIR / "board-structure.json"` |
| `src/shared/content_planner.py` | 54 | `"board_structure": "board-structure.json",` (strategy file mapping dict) |

**Cosmetic references (won't break, but should update for accuracy):**

| File | Line | Type |
|------|------|------|
| `src/pinterest/generate_weekly_plan.py` | 19 | Docstring |
| `src/pinterest/setup_boards.py` | 4, 39 | Docstring, log message |
| `.github/workflows/setup-boards.yml` | 4 | YAML comment |

**Variable names like `board_structure` (parameter names, dict keys) do NOT need changes** — they're just Python identifiers, not path references.

**Verification:** After the move, run `python -m pytest tests/test_plan_validator.py` — this test exercises `validate_plan()` which reads the file.

##### 2. Repo name references — complete change map

Phase 7 renames the GitHub repo from `slated-pinterest-bot` to `slated-content-engine`. The local folder is `pinterest-pipeline`. Both names appear across the codebase. Here is the exhaustive list:

**BREAKING (runtime failure if not updated):**

| File | Line | Current | New | Impact |
|------|------|---------|-----|--------|
| `src/apps-script/trigger.gs` | 71 | `"bradenpan/slated-pinterest-bot"` | `"bradenpan/slated-content-engine"` | Apps Script dispatch events target wrong repo — all Sheet-triggered workflows stop working |

**FUNCTIONAL (affects behavior, should update):**

| File | Line | Current | New | Impact |
|------|------|---------|-----|--------|
| `.github/workflows/weekly-review.yml` | 11 | `group: pinterest-pipeline` | `group: slated-content-engine` | Concurrency serialization |
| `.github/workflows/generate-content.yml` | 10 | `group: pinterest-pipeline` | `group: slated-content-engine` | Concurrency serialization |
| `.github/workflows/deploy-and-schedule.yml` | 12 | `group: pinterest-pipeline` | `group: slated-content-engine` | Concurrency serialization |
| `.github/workflows/promote-and-schedule.yml` | 16 | `group: pinterest-pipeline` | `group: slated-content-engine` | Concurrency serialization |
| `.github/workflows/monthly-review.yml` | 15 | `group: pinterest-pipeline` | `group: slated-content-engine` | Concurrency serialization |
| `.github/workflows/regen-content.yml` | 10 | `group: pinterest-pipeline` | `group: slated-content-engine` | Concurrency serialization |
| `.github/workflows/regen-plan.yml` | 10 | `group: pinterest-pipeline` | `group: slated-content-engine` | Concurrency serialization |
| `.github/workflows/daily-post-morning.yml` | 16 | `group: pinterest-posting` | `group: slated-content-engine-posting` | Posting serialization |
| `.github/workflows/daily-post-afternoon.yml` | 16 | `group: pinterest-posting` | `group: slated-content-engine-posting` | Posting serialization |
| `.github/workflows/daily-post-evening.yml` | 18 | `group: pinterest-posting` | `group: slated-content-engine-posting` | Posting serialization |
| `.github/actions/commit-data/action.yml` | 12 | `user.name "pinterest-pipeline-bot"` | `user.name "slated-content-engine-bot"` | Git commit author |
| `.github/actions/commit-data/action.yml` | 13 | `user.email "bot@pinterest-pipeline.local"` | `user.email "bot@slated-content-engine.local"` | Git commit email |

**COSMETIC (comments, docs, display strings):**

| File | Line | Current |
|------|------|---------|
| `ARCHITECTURE.md` | 44 | `pinterest-pipeline/` in directory tree |
| `src/__init__.py` | 1 | `# pinterest-pipeline src package` |
| `src/shared/apis/github_api.py` | 260 | `"Merge develop into main (pinterest pipeline deploy)"` |
| `src/shared/apis/slack_notify.py` | 514 | Smoke test message string |
| `src/shared/blog_deployer.py` | 542 | Code comment |
| `architecture/multi-channel-restructure/implementation-plan.md` | 48, 537 | Planning docs |

**RENAME SAFE (auto-creates new folder):**

| File | Line | Current | New |
|------|------|---------|-----|
| `src/shared/apis/drive_api.py` | 26 | `DRIVE_FOLDER_NAME = "pinterest-pipeline-pins"` | `DRIVE_FOLDER_NAME = "slated-content-engine-pins"` |

The Drive folder is in the service account's space (user never sees it). `_get_or_create_folder()` searches by name and auto-creates if missing, so renaming the constant just creates a new folder on next upload. The old folder becomes harmless orphaned data.

**Data files (`data/*.json`) contain GitHub Actions runner workspace paths** like `/home/runner/work/slated-pinterest-bot/...`. These are runtime artifacts that auto-regenerate on the next workflow run — do NOT manually edit them.

##### 3. Concurrency group rename must be atomic

All 7 `pinterest-pipeline` concurrency group workflows and all 3 `pinterest-posting` workflows must be renamed in the same commit. If some have the old name and some have the new name, they won't serialize against each other, potentially causing race conditions (e.g., `generate-content.yml` and `promote-and-schedule.yml` running simultaneously).

##### 4. Apps Script deployment is a human step

After updating `trigger.gs`, the human must manually deploy the updated script via Google Apps Script editor → Deploy → Deploy as API executable (or re-publish the trigger). The code change alone doesn't take effect until deployed.

---

## Parallel Work After Phase 5

Once Phase 5 is deployed and verified (next scheduled pin posts successfully), the remaining work can be parallelized:

### What can run in parallel

| Work | Can start after | Why it's safe |
|------|----------------|---------------|
| **Phase 6** (delete shims) | Phase 5 verified (1 posting cycle) | Shims are no longer referenced by any workflow |
| **Phase 7** (migrate TikTok docs, rename repo) | Phase 6 verified (1 full day of posting) | Pure file moves and rename — no Python code or workflow behavior changes |
| **TikTok Pre-Build P1** (create account, 14-day warmup) | Immediately — human task | Zero code impact |
| **TikTok Pre-Build P2** (Publer signup, API key) | Immediately — human task | Zero code impact |
| **TikTok Pre-Build P3** (Google Sheet setup) | Immediately — human task | Zero code impact |

### What must wait

| Work | Must wait for | Why |
|------|---------------|-----|
| **TikTok Phase 1+** (building `src/tiktok/`) | Phase 7 complete (repo renamed) | Building in `pinterest-pipeline` then renaming is messy. Start clean in `slated-content-engine`. |

### Verification per phase (no week-long gates)

| After | Verify | Duration |
|-------|--------|----------|
| Phase 5 | Next scheduled pin posts successfully (any 1 of 3 daily slots) | Hours, not days. Shims still exist as safety net. |
| Phase 6 | All 3 daily posting slots fire successfully | 1 day. If something breaks, it's an immediate import error — restore the shim and investigate. |
| Phase 7 (repo rename) | Apps Script trigger fires, next posting cycle works | 1 posting cycle. |

### Fastest possible timeline

- Phase 5 deployed → verified by next posting slot (same day)
- Phase 6 deployed → verified by end of next day
- Phase 7 + TikTok pre-build → start that same day
- TikTok Phase 1 (carousel rendering) → start once Phase 7 rename is done

---

## Folder and Repo Rename

### When to rename
- **Local folder:** Safe to rename anytime after Phase 6 is verified. The local folder name does not affect any code paths — Python imports use `src.`, not the folder name.
- **GitHub repo:** Phase 7 of the implementation plan. Must update `src/apps-script/trigger.gs` line 71 first.

### Recommended name
- **`slated-content-engine`** — matches the implementation plan and reflects the multi-channel purpose.
- Local folder: `C:\dev\slated-content-engine`
- GitHub repo: `bradenpan/slated-content-engine`

### What must happen before rename
1. Phase 6 verified (1 full day of posting without shims)
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
3. **User confirmation** — daily posting works, no workflow errors in GitHub Actions logs
4. **No regression in Slack notifications** — all pipeline steps still notify

Only proceed to the next phase after ALL checks pass.
