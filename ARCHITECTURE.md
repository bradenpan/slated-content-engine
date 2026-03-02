# Pinterest Pipeline — Architecture

**Last verified:** 2026-03-02
**Update this doc when:** a file is added/removed from `src/`, a workflow is added/removed, an external integration changes, a major feature is added/removed, or data schemas change.

---

## 1. What This Is

Fully automated Pinterest content pipeline for **Slated** (family meal planning iOS app). Takes a content strategy as input and runs the full weekly loop: content planning, blog post generation, pin image creation, deployment to goslated.com, daily posting to Pinterest, performance analytics, and strategy review. Human approval gates at plan review, content review, and production deploy.

**Weekly output:** 8-10 blog posts + 28 pins, posted 4 pins/day across 3 daily windows.

---

## 2. Pipeline Flow

```
Plan → [Plan Regen] → Generate → Review → [Content Regen] → Deploy → Post → Analyze
  ↑                                                                              |
  └──────────────────────── feeds next week's plan ────────────────────────────────┘
```

| # | Step | Trigger | Script(s) | Output |
|---|------|---------|-----------|--------|
| 1 | Weekly Plan | Monday 6am ET cron | `generate_weekly_plan.py` | Plan JSON + Weekly Review sheet |
| 1b | Plan Regen *(optional)* | Sheet B5 = "regen" | `regen_weekly_plan.py` | Updated plan JSON + sheet |
| 2 | Plan Approval | Sheet B3 = "approved" | Apps Script → `generate-content.yml` | — |
| 3 | Content Generation | Workflow | `generate_blog_posts.py` → `generate_pin_content.py` → `publish_content_queue.py` | Blog MDX files, pin PNGs, GCS URLs, Content Queue sheet |
| 4 | Content Review | Human in Sheet | — | Status per row in Column J |
| 4b | Content Regen *(optional)* | Sheet N1 = "run" | `regen_content.py` | Updated pins/images/sheet rows |
| 5 | Deploy Preview | All rows terminal | `blog_deployer.py` → `deploy_to_preview()` | Blogs on goslated.com `develop` branch |
| 6 | Production Approval | Sheet B4 = "approved" | Apps Script → `promote-and-schedule.yml` | — |
| 7 | Promote & Schedule | Workflow | `blog_deployer.py` → `promote_to_production()` | Merge develop→main, `pin-schedule.json`, initial content log entries |
| 8 | Daily Posting | 3x daily cron | `post_pins.py` | Live Pinterest pins, updated `content-log.jsonl` |
| 9 | Weekly Analysis | Monday 6am (part of step 1) | `pull_analytics.py` → `weekly_analysis.py` | Updated metrics, analysis markdown |
| 10 | Monthly Review | 1st Monday of month | `monthly_review.py` | Strategy recommendations |

---

## 3. Directory Structure

**Note: Multi-channel restructure in progress (Phase 1 complete).** Files are being migrated from `src/` into `src/shared/` (cross-channel) and `src/pinterest/` (Pinterest-specific). Backward-compat shims exist at old locations until Phase 6.

```
pinterest-pipeline/
├── src/
│   ├── shared/                   # Cross-channel code (Phase 1+)
│   │   ├── apis/                 # Shared API wrappers (Claude, Sheets, GCS, GitHub, etc.)
│   │   ├── utils/                # Shared utilities (safe_get, content_log, plan_utils, etc.)
│   │   ├── paths.py              # Centralized path constants (PROJECT_ROOT, DATA_DIR, etc.)
│   │   ├── config.py             # Model names, costs, URLs, dimensions, timing
│   │   ├── image_cleaner.py      # AI detection avoidance post-processing
│   │   ├── blog_generator.py     # Individual blog MDX generation
│   │   ├── blog_deployer.py      # GitHub commit to goslated.com → Vercel deploy
│   │   └── generate_blog_posts.py # Blog post orchestrator
│   ├── pinterest/                # Pinterest-specific code (Phase 1+)
│   │   ├── apis/                 # Pinterest API wrapper
│   │   ├── token_manager.py      # Pinterest OAuth 2.0 token auto-refresh
│   │   ├── pin_assembler.py      # HTML/CSS template → PNG renderer
│   │   ├── generate_pin_content.py # Pin copy + image generation
│   │   ├── post_pins.py          # Daily Pinterest API posting
│   │   ├── pull_analytics.py     # Pinterest Analytics API pull
│   │   ├── regen_content.py      # Selective content regeneration
│   │   ├── plan_validator.py     # Plan constraint validation
│   │   ├── setup_boards.py       # One-time board creation
│   │   └── redate_schedule.py    # Pin schedule redating
│   ├── apis/                     # Backward-compat shims → src/shared/apis/ or src/pinterest/apis/
│   ├── utils/                    # Backward-compat shims → src/shared/utils/ (content_memory.py still original)
│   ├── generate_weekly_plan.py   # NOT YET MOVED (Phase 3) — Claude-driven weekly planning
│   ├── weekly_analysis.py        # NOT YET MOVED (Phase 2)
│   ├── monthly_review.py         # NOT YET MOVED (Phase 2)
│   ├── regen_weekly_plan.py      # NOT YET MOVED (Phase 3)
│   ├── publish_content_queue.py  # NOT YET MOVED (Phase 2)
│   └── *.py                      # Backward-compat shims for moved files
├── prompts/                      # Claude/GPT prompt templates (10 files)
├── templates/pins/               # HTML/CSS pin templates (5 types × 3 variants)
├── strategy/                     # Content strategy, brand voice, keywords, CTAs
├── data/                         # Runtime data (gitignored except JSON results)
│   └── generated/                # Generated blog MDX + pin images (gitignored)
├── .github/workflows/            # GitHub Actions workflow definitions
├── analysis/                     # Weekly/monthly analysis outputs
├── architecture/                 # Restructuring plans and execution strategy
├── memory-bank/                  # Project documentation and progress tracking
├── ARCHITECTURE.md               # ← This file
├── CLAUDE.md                     # Agent instructions and project rules
└── render_pin.js                 # Puppeteer pin renderer (called by pin_assembler.py)
```

---

## 4. Key Files & Responsibilities

### Pipeline Scripts (`src/`)

| File | Purpose |
|------|---------|
| `generate_weekly_plan.py` | Claude-driven weekly content planning (8-10 blog posts + 28 pin specs) |
| `generate_blog_posts.py` | Blog post orchestrator — reads plan, generates MDX via `blog_generator.py` |
| `blog_generator.py` | Individual blog MDX generation with frontmatter + Schema.org (4 types: recipe, guide, listicle, weekly-plan) |
| `generate_pin_content.py` | Pin content pipeline: copy generation (GPT-5 Mini) → AI image generation → pin assembly/rendering |
| `pin_assembler.py` | HTML/CSS template → PNG renderer via Puppeteer (5 template types × 3 variants) |
| `publish_content_queue.py` | Uploads images to GCS, writes Content Queue sheet, stores GCS URLs back to results JSON |
| `blog_deployer.py` | Commits blogs to goslated.com repo (Vercel deploy), URL verification, pin schedule creation |
| `post_pins.py` | Daily Pinterest API posting with anti-bot jitter, idempotency, retry logic |
| `pull_analytics.py` | Pinterest Analytics API pull (impressions, saves, clicks, outbound) |
| `weekly_analysis.py` | Claude-driven weekly performance analysis |
| `monthly_review.py` | Claude Opus deep monthly strategy review |
| `regen_content.py` | Selective content regeneration (image/copy/both) based on reviewer feedback |
| `regen_weekly_plan.py` | Plan-level topic replacement based on reviewer feedback |
| `plan_validator.py` | Plan constraint validation (pin counts, board distribution, etc.) |
| `redate_schedule.py` | Pin schedule redating utility |
| `image_cleaner.py` | AI detection avoidance post-processing for generated images |
| `setup_boards.py` | One-time Pinterest board creation |
| `token_manager.py` | Pinterest OAuth 2.0 token auto-refresh |
| `config.py` | Centralized config: model names, costs, URLs, dimensions, timing constants |
| `paths.py` | Centralized path constants (PROJECT_ROOT, DATA_DIR, PROMPTS_DIR, etc.) |
| `recover_w9_pins.py` | One-time recovery script (likely dead code) |

### API Wrappers (`src/apis/`)

| File | Purpose |
|------|---------|
| `claude_api.py` | Claude Sonnet/Opus + GPT-5 Mini integration, prompt template loading, cost tracking |
| `openai_chat_api.py` | GPT-5 Mini HTTP wrapper (used by claude_api.py for pin copy + image prompts) |
| `pinterest_api.py` | Pinterest v5 REST API (pins, boards, analytics) |
| `sheets_api.py` | Google Sheets CRUD (Weekly Review, Content Queue, Post Log, Dashboard tabs) |
| `gcs_api.py` | Google Cloud Storage uploads (primary image hosting for Sheet previews + Pinterest) |
| `drive_api.py` | Google Drive uploads (fallback if GCS fails) |
| `github_api.py` | GitHub Git Data API (atomic multi-file blog commits to goslated.com) |
| `image_gen.py` | AI image generation via gpt-image-1.5 (Replicate Flux Pro as alternate provider) |
| `slack_notify.py` | Slack webhook notifications (Block Kit formatted) |

### Utilities (`src/utils/`)

| File | Purpose |
|------|---------|
| `content_log.py` | JSONL content log read/append operations |
| `content_memory.py` | Content memory summary generation (dedup, topic tracking, pillar mix) |
| `plan_utils.py` | Plan loading, validation helpers, atomic pin-schedule writes |
| `image_utils.py` | MIME detection + Drive file ID parsing |
| `strategy_utils.py` | Brand voice loading |
| `safe_get.py` | Safe dictionary access helper |

---

## 5. Data Flow

### Critical Data Files

| File | Written By | Read By |
|------|-----------|---------|
| `data/weekly-plan-W{N}-{date}.json` | `generate_weekly_plan.py`, `regen_weekly_plan.py` | `generate_blog_posts.py`, `generate_pin_content.py`, `regen_weekly_plan.py` |
| `data/blog-generation-results.json` | `blog_generator.py` | `generate_pin_content.py`, `publish_content_queue.py`, `blog_deployer.py`, `regen_content.py` |
| `data/pin-generation-results.json` | `generate_pin_content.py` | `publish_content_queue.py` (adds GCS URLs), `regen_content.py` (updates), `blog_deployer.py` |
| `data/pin-schedule.json` | `blog_deployer.py` | `post_pins.py`, `regen_content.py` |
| `data/content-log.jsonl` | `blog_deployer.py` (initial), `post_pins.py` (posted) | `pull_analytics.py` (update), `weekly_analysis.py`, `monthly_review.py`, `generate_weekly_plan.py` |

### ID Conventions

- **Post IDs:** `W{week}-P{seq}` (e.g., `W12-P01`) — identify blog posts within a week
- **Pin IDs:** `W{week}-{seq}` (e.g., `W12-01`) — identify pins within a week
- **Pin-to-Blog link:** Pin's `source_post_id` field → parent blog's `post_id`
- **Blog slugs:** lowercase-hyphenated (e.g., `easy-weeknight-chicken-tacos`) — used as filename AND URL path

### Key Data Flows

**Image URL flow:**
```
image_gen → {pin_id}-hero.png (local) → pin_assembler renders → {pin_id}.png (local)
  → GCS upload → public URL stored as _drive_download_url in pin-generation-results.json
  → blog_deployer copies to pin-schedule.json as image_url
  → post_pins.py passes to Pinterest API
```

**Blog slug flow:**
```
Claude generates slug in blog frontmatter
  → blog_generator extracts → blog-generation-results.json["slug"]
  → generate_pin_content reads → dual-saves hero as {slug}-hero.{ext}
  → blog_deployer commits {slug}.mdx + {slug}-hero.{ext} to goslated.com
  → pin-schedule.json + content-log.jsonl carry blog_slug throughout
```

**Link flow:**
```
generate_pin_content → bare URL "https://goslated.com/blog/{slug}"
  → carried through pin-generation-results → pin-schedule.json
  → post_pins.py appends UTM params at posting time
  → content-log.jsonl stores the final UTM-tagged link
```

---

## 6. External Systems

| System | Purpose | Integration Point |
|--------|---------|-------------------|
| **Google Sheets** | Human review UI — plan approval, content review, regen feedback | `sheets_api.py` — 4 tabs: Weekly Review, Content Queue, Post Log, Dashboard |
| **Google Apps Script** | Bridges Sheet edits to GitHub Actions | `trigger.gs` — watches cell changes, fires `repository_dispatch` events |
| **Google Cloud Storage** | Primary image hosting — pin thumbnails for Sheet previews + Pinterest image source | `gcs_api.py` — public URLs used in Sheet `=IMAGE()` formulas and pin schedule |
| **Google Drive** | Fallback image hosting if GCS fails | `drive_api.py` |
| **Pinterest API v5** | Pin posting, board management, analytics | `pinterest_api.py` — OAuth 2.0 with auto-refresh via `token_manager.py` |
| **goslated.com (GitHub/Vercel)** | Blog hosting — MDX files committed via GitHub API, Vercel auto-deploys | `github_api.py` — commits to develop branch (preview) then merges to main (production) |
| **Slack** | Pipeline notifications (Block Kit) | `slack_notify.py` — webhook-based |

### Google Sheets Tab Layout

**Content Queue (12 columns A-L):** ID, Type, Title, Description, Board, Blog URL, Schedule, Pillar, Thumbnail, Status, Notes, Feedback. Regen trigger at M1:N1.

**Weekly Review:** Plan summary with blog/pin rows, approval cells at B3 (plan), B4 (production), B5 (plan regen).

---

## 7. Workflows

| Workflow | Trigger | What It Runs |
|----------|---------|-------------|
| `weekly-review.yml` | Cron: Monday 6am ET | Analytics pull → weekly analysis → plan generation |
| `generate-content.yml` | Dispatch: `generate-content` | Blog generation → pin generation → content queue publish |
| `regen-plan.yml` | Dispatch: `regen-plan` | Plan-level topic replacement |
| `regen-content.yml` | Dispatch: `regen-content` | Selective image/copy regeneration |
| `regen-blogs-only.yml` | Manual | Blog-only regeneration |
| `deploy-and-schedule.yml` | Dispatch: `deploy-to-preview` | Blog deploy to goslated.com develop branch |
| `promote-and-schedule.yml` | Dispatch: `promote-and-schedule` | Merge develop→main, create pin schedule |
| `daily-post-morning.yml` | Cron: 10am ET | Post scheduled pins (morning slot) |
| `daily-post-afternoon.yml` | Cron: 3pm ET | Post scheduled pins (afternoon slot) |
| `daily-post-evening.yml` | Cron: 8pm ET | Post scheduled pins (evening slot) |
| `monthly-review.yml` | Cron: 1st Monday | Monthly deep strategy review |
| `setup-boards.yml` | Manual only | One-time Pinterest board creation |

**Dispatch triggers** come from Google Apps Script watching cell edits in the Google Sheet.

---

## 8. LLM & AI Usage

| Model | Used For | Called By |
|-------|----------|----------|
| **Claude Sonnet 4.6** | Weekly planning, blog generation, weekly analysis, replacement posts | `claude_api.py` — routine tasks |
| **Claude Opus 4.6** | Monthly deep strategy review | `claude_api.py` — deep analysis |
| **GPT-5 Mini** | Pin copy generation, image prompt generation | `openai_chat_api.py` via `claude_api.py` — falls back to Claude Sonnet on failure |
| **gpt-image-1.5** | AI hero image generation (1000×1500, natural style) | `image_gen.py` — all images are AI-generated |

Cost: ~$3-5/week for a full cycle (planning + 8-10 blogs + 28 pins + analysis).

---

## 9. Critical Gotchas

**READ THIS SECTION BEFORE MAKING ANY CHANGES.**

1. **goslated.com routes by FILENAME, not frontmatter.** The blog MDX filename IS the slug. `content/blog/easy-chicken-tacos.mdx` → URL is `/blog/easy-chicken-tacos`. Do not change filenames without understanding this.

2. **Dual hero image save.** Every hero image is saved twice: `{pin_id}-hero.png` (for pin assembly + GCS upload) AND `{slug}-hero.png` (for blog deployment to goslated.com). Both must exist. See `generate_pin_content.py:177-183`.

3. **Column indices are hardcoded.** Google Sheets columns are referenced by numeric index throughout `sheets_api.py`. Content Queue is 12 columns (A-L). Adding/removing/reordering columns breaks reads AND writes silently. The column constants are in `sheets_api.py` (`CQ_COL_*`).

4. **Apps Script column references are 1-based.** While Python uses 0-based column indices, `trigger.gs` uses 1-based column numbers. Regen trigger check: `getColumn() === 14` (column N). Content status for deploy gate: `getColumn() === 10` (column J).

5. **`_` prefixed fields are internal.** Fields like `_drive_image_url`, `_drive_download_url`, `_copy_feedback`, `_regen_feedback` in `pin-generation-results.json` are added by `publish_content_queue.py` or `regen_content.py`, not by `generate_pin_content.py`.

6. **UTM params are added at posting time, not before.** `pin-schedule.json` contains bare blog URLs. `post_pins.py` adds UTM parameters via `construct_utm_link()` when actually posting to Pinterest.

7. **Pin images live on GCS, not in git.** Generated images are gitignored. Pin posting uses GCS public URLs (stored in `pin-schedule.json` as `image_url`). Regen on a fresh CI runner must download hero images from GCS/Drive before re-rendering.

8. **Terminal statuses for deploy gate:** `["approved", "rejected", "use_ai_image"]`. Any `regen_*` status blocks deployment. The `allContentReviewed()` Apps Script function checks this.

9. **Evening posting slots.** The weekly plan assigns `evening-1` and `evening-2` slots. The evening posting workflow matches both via `startswith("evening")`.

10. **`regen_content.py` imports private functions** from `generate_pin_content.py` (`_source_ai_image`, `_load_brand_voice`, `_load_keyword_targets`). These are tightly coupled — changes to the private functions affect regen.

---

## 10. Deep-Dive References

| Document | What It Covers |
|----------|---------------|
| [`memory-bank/architecture/architecture-data-flows.md`](memory-bank/architecture/architecture-data-flows.md) | Exhaustive data flow reference: schemas, column layouts, field mappings, cross-file dependencies (1,176 lines) |
| [`memory-bank/Audit/audit.md`](memory-bank/Audit/audit.md) | Living codebase audit: file-by-file analysis, known issues, dependency maps |
| [`memory-bank/Audit/dead-code-analysis.md`](memory-bank/Audit/dead-code-analysis.md) | Dead code tracking with line numbers |
| [`architecture/codebase-review/synthesis.md`](architecture/codebase-review/synthesis.md) | Code quality: 24 findings across 8 dimensions, prioritized fix plan |
| [`memory-bank/progress.md`](memory-bank/progress.md) | Chronological changelog of all pipeline phases and features |
| [`architecture/multi-channel-restructure/`](architecture/multi-channel-restructure/) | **FUTURE/DRAFT** — planned multi-channel restructure (Pinterest + TikTok) |
| [`src/config.py`](src/config.py) | All hardcoded constants: model names, costs, URLs, dimensions, timing |
| [`src/paths.py`](src/paths.py) | All path constants: PROJECT_ROOT, DATA_DIR, PROMPTS_DIR, etc. |

---

## 11. Tech Stack Summary

- **Language:** Python 3.11
- **Orchestration:** GitHub Actions (cron + `repository_dispatch` from Apps Script)
- **LLMs:** Anthropic Claude (Sonnet/Opus), OpenAI GPT-5 Mini, OpenAI gpt-image-1.5
- **Pin rendering:** Puppeteer (via `render_pin.js`) — HTML/CSS templates → PNG
- **Blog hosting:** Vercel (auto-deploys from GitHub commits to goslated.com repo)
- **Image hosting:** Google Cloud Storage (public URLs)
- **Human review:** Google Sheets + Google Apps Script
- **Notifications:** Slack webhooks (Block Kit)
- **Auth:** Pinterest OAuth 2.0 (auto-refresh), Google service account, GitHub PAT
