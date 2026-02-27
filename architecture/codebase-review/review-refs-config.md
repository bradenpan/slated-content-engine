# Review: Referential Integrity + Configuration Completeness

**Reviewer:** reviewer-refs-config
**Date:** 2026-02-27
**Scope:** All Python source files (src/), GitHub Actions workflows (.github/workflows/),
composite actions (.github/actions/), templates, prompts, strategy files, .env.example,
requirements.txt

---

## Dimension 1: Referential Integrity

### 1.1 Python Module Imports

All cross-module `from src.X import Y` references were verified against actual exports.

**Result: PASS -- no broken imports found.**

Verified chains include:
- `regen_content.py` imports `generate_copy_batch`, `load_used_image_ids`, `source_ai_image`,
  `load_keyword_targets`, `build_template_context` from `generate_pin_content` -- all exist
- `weekly_analysis.py` imports `compute_derived_metrics`, `aggregate_by_dimension` from
  `pull_analytics` -- both exist
- `monthly_review.py` imports the same `pull_analytics` functions -- exist
- `regen_weekly_plan.py` imports `load_content_memory` from `generate_weekly_plan` and
  `TAB_WEEKLY_REVIEW`, `WR_CELL_PLAN_STATUS` from `sheets_api` -- all exist
- `blog_deployer.py` inline-imports `clean_image` from `image_cleaner` (line ~386) -- exists
- `publish_content_queue.py` imports from `gcs_api`, `drive_api`, `sheets_api`,
  `slack_notify`, `image_utils` -- all exist
- All `src/utils/` modules (`content_log`, `content_memory`, `plan_utils`, `plan_validator`,
  `strategy_utils`, `image_utils`) are imported correctly by their consumers

### 1.2 `python -m` Module Calls in Workflows

Every `python -m src.*` call in GitHub Actions workflows was checked for a corresponding
`if __name__ == "__main__"` block.

**Result: PASS -- all 16 module entry points have `__main__` blocks.**

| Workflow | Module | `__main__` |
|----------|--------|:----------:|
| generate-content.yml | `src.generate_weekly_plan` | Yes |
| generate-content.yml | `src.generate_blog_posts` | Yes |
| generate-content.yml | `src.generate_pin_content` | Yes |
| generate-content.yml | `src.publish_content_queue` | Yes |
| promote-and-schedule.yml | `src.blog_deployer` | Yes |
| promote-and-schedule.yml | `src.post_pins` | Yes |
| daily-post-morning.yml | `src.post_pins` | Yes |
| daily-post-afternoon.yml | `src.post_pins` | Yes |
| daily-post-evening.yml | `src.post_pins` | Yes |
| weekly-review.yml | `src.pull_analytics` | Yes |
| weekly-review.yml | `src.weekly_analysis` | Yes |
| monthly-review.yml | `src.monthly_review` | Yes |
| regen-content.yml | `src.regen_content` | Yes |
| regen-weekly-plan.yml | `src.regen_weekly_plan` | Yes |
| setup-boards.yml | `src.setup_boards` | Yes |
| refresh-token.yml | `src.token_manager` | Yes |

### 1.3 GitHub Actions Composite Action References

All `./.github/actions/*` references in workflows resolve to real action directories.

**Result: PASS.**

| Action Reference | Directory Exists | action.yml Present |
|------------------|:----------------:|:------------------:|
| `./.github/actions/setup-pipeline` | Yes | Yes |
| `./.github/actions/commit-data` | Yes | Yes |
| `./.github/actions/notify-failure` | Yes | Yes |

### 1.4 Prompt Template File References

`src/apis/claude_api.py` loads prompt files from `prompts/` using `PROMPTS_DIR / name`.

**Result: PASS -- all referenced prompt files exist.**

| Template Key | File | Exists |
|-------------|------|:------:|
| `blog_post_recipe` | `prompts/blog_post_recipe.md` | Yes |
| `blog_post_weekly_plan` | `prompts/blog_post_weekly_plan.md` | Yes |
| `blog_post_guide` | `prompts/blog_post_guide.md` | Yes |
| `blog_post_listicle` | `prompts/blog_post_listicle.md` | Yes |
| `weekly_plan` | `prompts/weekly_plan.md` | Yes |
| `pin_copy` | `prompts/pin_copy.md` | Yes |
| `image_prompt` | `prompts/image_prompt.md` | Yes |
| `weekly_analysis` | `prompts/weekly_analysis.md` | Yes |
| `monthly_review` | `prompts/monthly_review.md` | Yes |
| `weekly_plan_replace` | `prompts/weekly_plan_replace.md` | Yes |

### 1.5 Pin Template Directory References

`src/pin_assembler.py` defines `TEMPLATE_CONFIGS` with 5 template types. Each must have
a subdirectory under `templates/pins/` containing `template.html` and `styles.css`.

**Result: PASS -- all pin templates exist.**

| Template Name | template.html | styles.css |
|--------------|:-------------:|:----------:|
| `recipe-pin` | Yes | Yes |
| `tip-pin` | Yes | Yes |
| `listicle-pin` | Yes | Yes |
| `problem-solution-pin` | Yes | Yes |
| `infographic-pin` | Yes | Yes |

Shared resources also confirmed:
- `templates/pins/shared/base-styles.css` -- exists
- `templates/pins/shared/brand-elements/slated-cloche-amber.svg` -- exists
- `templates/pins/shared/brand-elements/slated-cloche-white.svg` -- exists

### 1.6 Blog Template Example Files

`src/blog_generator.py` loads example posts from `templates/blog/`.

**Result: PASS -- all 4 example post files exist.**

| File | Exists |
|------|:------:|
| `templates/blog/recipe-post-example.md` | Yes |
| `templates/blog/guide-post-example.md` | Yes |
| `templates/blog/listicle-post-example.md` | Yes |
| `templates/blog/weekly-plan-post-example.md` | Yes |

### 1.7 Strategy File References

Various modules load files from `strategy/`. All referenced files verified.

**Result: PASS.**

| File | Referenced By | Exists |
|------|--------------|:------:|
| `strategy/keyword-lists.json` | generate_pin_content, generate_weekly_plan | Yes |
| `strategy/negative-keywords.json` | generate_weekly_plan | Yes |
| `strategy/cta-variants.json` | generate_pin_content | Yes |
| `strategy/seasonal-calendar.json` | generate_weekly_plan | Yes |
| `strategy/board-structure.json` | generate_pin_content, setup_boards | Yes |
| `strategy/brand-voice.md` | strategy_utils | Yes |
| `strategy/current-strategy.md` | generate_weekly_plan | Yes |
| `strategy/product-overview.md` | generate_weekly_plan | Yes |

### 1.8 Render Script Reference

`src/pin_assembler.py` references `render_pin.js` at `PROJECT_ROOT`.

**Result: PASS -- `render_pin.js` exists at project root.**

### 1.9 Runtime Directory Creation

`src/paths.py` defines `ANALYSIS_DIR = PROJECT_ROOT / "analysis"` which does not exist
on disk. However, all consumers create it at runtime with `mkdir(parents=True, exist_ok=True)`
before writing, and readers (`generate_weekly_plan.py`) handle the missing case gracefully.

**Result: PASS -- no issue, runtime-created directories are handled correctly.**

---

## Dimension 7: Configuration Completeness

### 7.1 Environment Variables: Code vs .env.example

#### [MEDIUM] Env vars used in code but MISSING from .env.example

These variables are read by code at runtime but are not documented in `.env.example`,
so developers setting up the project may not know they exist.

| Variable | Used In | Default | Impact |
|----------|---------|---------|--------|
| `IMAGE_GEN_PROVIDER` | `src/apis/image_gen.py` | `"openai"` | Low -- defaults to openai, but undocumented |
| `GCS_BUCKET_NAME` | `src/apis/gcs_api.py` | `"slated-pipeline-pins"` | Low -- has default, but undocumented |
| `PINTEREST_ENVIRONMENT` | `src/apis/pinterest_api.py` | `"sandbox"` | **Medium** -- defaults to sandbox in code, but workflows override to production. Missing from .env.example means local dev defaults to sandbox silently, which may confuse devs who don't realize they're hitting the sandbox API. |

#### [LOW] Env vars in .env.example but NOT used in any code

These entries in `.env.example` have no corresponding `os.environ.get()` or `os.getenv()`
call anywhere in the Python source.

| Variable | Status |
|----------|--------|
| `UNSPLASH_ACCESS_KEY` | Not used in any Python file -- likely vestigial from a removed feature |
| `PEXELS_API_KEY` | Not used in any Python file -- likely vestigial from a removed feature |

**Recommendation:** Remove these from `.env.example` to avoid misleading developers into
thinking they need to set up Unsplash/Pexels API keys.

### 7.2 Workflow Secrets vs Code Requirements

#### [MEDIUM] `REPLICATE_API_TOKEN` not passed through any workflow

`src/apis/image_gen.py` reads `REPLICATE_API_TOKEN` when `IMAGE_GEN_PROVIDER=replicate`.
The token is listed in `.env.example` and `requirements.txt` includes the `replicate`
package. However, no workflow passes this secret in its `env:` block.

**Impact:** If someone switches `IMAGE_GEN_PROVIDER` to `replicate`, the workflow will
fail at runtime because the token won't be in the environment. Currently safe because
the default provider is `openai`, but the infrastructure is inconsistent -- the replicate
package is installed, the env var is documented, but the secret isn't wired up.

**Recommendation:** Either:
1. Add `REPLICATE_API_TOKEN: ${{ secrets.REPLICATE_API_TOKEN }}` to `generate-content.yml`
   and `regen-content.yml` (the two workflows that do image generation), OR
2. Remove `REPLICATE_API_TOKEN` from `.env.example` and `replicate` from
   `requirements.txt` if Replicate support is deprecated.

#### [LOW] `IMAGE_GEN_PROVIDER` not passed through workflows

This variable controls which image generation backend to use. It defaults to `"openai"`
when absent. Since the workflows don't set it, the default is always used in CI.

**Impact:** None currently -- works fine with the default. But if you want to switch
providers in CI, you'd need to add it as a secret and wire it through.

#### [LOW] `OPENAI_CHAT_MODEL` not passed through workflows

`src/config.py` reads this at import time with default `"gpt-5-mini"`. It's listed in
`.env.example` but not passed through any workflow `env:` block.

**Impact:** CI always uses the default model. This is probably intentional -- the env var
exists for local override only -- but it's undocumented.

### 7.3 Environment Variable Defaults Audit

All env vars with defaults were checked for sensible fallback values.

| Variable | Default | Sensible? |
|----------|---------|:---------:|
| `IMAGE_GEN_PROVIDER` | `"openai"` | Yes |
| `GCS_BUCKET_NAME` | `"slated-pipeline-pins"` | Yes |
| `PINTEREST_ENVIRONMENT` | `"sandbox"` | See note below |
| `OPENAI_CHAT_MODEL` | `"gpt-5-mini"` | Yes |

**Note on `PINTEREST_ENVIRONMENT`:** The code defaults to `"sandbox"` but all workflows
hardcode `PINTEREST_ENVIRONMENT: production`. This is a reasonable safety pattern --
local dev defaults to sandbox, CI explicitly sets production. No issue here, but the
variable should be documented in `.env.example` so devs know it exists.

### 7.4 Required Variables Without Fallbacks

These variables have **no default** -- if missing, the code raises an error or the
feature is disabled:

| Variable | Module | Behavior When Missing |
|----------|--------|-----------------------|
| `ANTHROPIC_API_KEY` | `claude_api.py` | Raises error at init |
| `PINTEREST_ACCESS_TOKEN` | `pinterest_api.py` | Raises error at init |
| `PINTEREST_APP_ID` | `token_manager.py` | Raises error at token refresh |
| `PINTEREST_APP_SECRET` | `token_manager.py` | Raises error at token refresh |
| `PINTEREST_REFRESH_TOKEN` | `token_manager.py` | Raises error at token refresh |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | `sheets_api.py` | Raises error at init |
| `GOOGLE_SHEET_ID` | `sheets_api.py` | Raises error at init |
| `OPENAI_API_KEY` | `image_gen.py`, `openai_chat_api.py` | Raises error at init |
| `GOSLATED_GITHUB_TOKEN` | `github_api.py` | Raises error at init |
| `GOSLATED_REPO` | `github_api.py` | Raises error at init |

All of these are documented in `.env.example`. **No gaps for required variables.**

| Variable | Module | Behavior When Missing |
|----------|--------|-----------------------|
| `SLACK_WEBHOOK_URL` | `slack_notify.py` | Logs warning, notifications disabled |
| `GOOGLE_SHEET_URL` | `slack_notify.py` | Logs warning, sheet links omitted |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | `gcs_api.py` | Logs warning, GCS uploads skipped |

These graceful-degradation patterns are correct -- optional features degrade cleanly.

### 7.5 External Dependencies in requirements.txt

All Python packages imported in source code were checked against `requirements.txt`.

**Result: PASS -- all required packages are listed.**

| Package | Used By | In requirements.txt |
|---------|---------|:-------------------:|
| `anthropic` | claude_api.py | Yes |
| `requests` | pinterest_api.py, post_pins.py, slack_notify.py | Yes |
| `Pillow` (PIL) | image_cleaner.py, pin_assembler.py | Yes |
| `numpy` | image_cleaner.py | Yes |
| `openai` | image_gen.py, openai_chat_api.py | Yes |
| `replicate` | image_gen.py | Yes |
| `google-api-python-client` | sheets_api.py, drive_api.py | Yes |
| `google-auth` | sheets_api.py, drive_api.py, gcs_api.py | Yes |
| `google-cloud-storage` | gcs_api.py | Yes |
| `PyGithub` | github_api.py | Yes |
| `python-slugify` | blog_generator.py | Yes |
| `pyyaml` | blog_generator.py, blog_deployer.py | Yes |
| `python-dotenv` | (local dev .env loading) | Yes |
| `tzdata` | (zoneinfo fallback) | Yes |

---

## Summary of Findings

### Issues to Fix

| # | Severity | Category | Description |
|---|----------|----------|-------------|
| 1 | MEDIUM | Config | `PINTEREST_ENVIRONMENT` missing from `.env.example` (defaults to sandbox in code, production in CI) |
| 2 | MEDIUM | Config | `GCS_BUCKET_NAME` missing from `.env.example` |
| 3 | MEDIUM | Config | `IMAGE_GEN_PROVIDER` missing from `.env.example` |
| 4 | MEDIUM | Config | `REPLICATE_API_TOKEN` not wired through workflow env blocks (generate-content.yml, regen-content.yml) |
| 5 | LOW | Config | `UNSPLASH_ACCESS_KEY` in `.env.example` but unused in code -- vestigial |
| 6 | LOW | Config | `PEXELS_API_KEY` in `.env.example` but unused in code -- vestigial |
| 7 | LOW | Config | `OPENAI_CHAT_MODEL` not passed through workflows (has sensible default) |

### Clean Areas (No Issues Found)

- All Python cross-module imports resolve correctly
- All `python -m` entry points have `__main__` blocks
- All composite action references resolve
- All prompt template files exist
- All pin template directories and files exist
- All blog example template files exist
- All strategy files exist
- `render_pin.js` exists at project root
- All required env vars (no-default) are in `.env.example`
- All external Python packages are in `requirements.txt`
- Runtime-created directories are handled with `mkdir(parents=True, exist_ok=True)`
- Optional features degrade gracefully when credentials are missing

### Recommended Fixes (Priority Order)

1. **Add missing env vars to `.env.example`:**
   ```
   PINTEREST_ENVIRONMENT=sandbox
   IMAGE_GEN_PROVIDER=openai
   GCS_BUCKET_NAME=slated-pipeline-pins
   ```

2. **Remove unused env vars from `.env.example`:**
   ```
   # Remove these lines:
   UNSPLASH_ACCESS_KEY=your_unsplash_access_key
   PEXELS_API_KEY=your_pexels_api_key
   ```

3. **Wire `REPLICATE_API_TOKEN` through workflows** (or remove Replicate support entirely
   if deprecated):
   - Add to `generate-content.yml` env block: `REPLICATE_API_TOKEN: ${{ secrets.REPLICATE_API_TOKEN }}`
   - Add to `regen-content.yml` env block: `REPLICATE_API_TOKEN: ${{ secrets.REPLICATE_API_TOKEN }}`

4. **Optionally pass `OPENAI_CHAT_MODEL` through workflows** if CI should respect overrides.
