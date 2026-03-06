# Pinterest Pipeline — Architecture

**Last verified:** 2026-03-05
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
| 0 | Collect Analytics | Monday 5:30am ET cron | `pull_analytics.py` → `content_memory.py` | Fresh analytics + content memory summary |
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
| 9 | Weekly Analysis | Monday 6am (after analytics collection) | `weekly_analysis.py` | Analysis markdown |
| 10 | Monthly Review | 1st Monday of month | `monthly_review.py` | Strategy recommendations |

### TikTok Pipeline Flow

```
Plan → [Plan Review] → [Plan Regen] → Render → GCS Upload → Sheet → [Content Review] → Schedule → Post (3x daily)
```

| # | Step | Trigger | Script(s) | Output |
|---|------|---------|-----------|--------|
| 1 | Weekly Plan | `tiktok-weekly-review.yml` (Monday 6:30am ET) | `tiktok/generate_weekly_plan.py --plan-only` | 7 carousel specs → plan JSON + Weekly Review tab |
| 1b | Plan Regen *(optional)* | Sheet B5 = "regen" | `tiktok/regen_plan.py` *(Phase C)* | Updated plan JSON + Weekly Review tab |
| 2 | Plan Approval | Sheet B3 = "approved" | Apps Script → `tiktok-generate-content.yml` | — |
| 3 | Content Generation | Workflow | `tiktok/generate_weekly_plan.py --generate-content` | Rendered PNGs + GCS upload + Content Queue sheet (17 cols, per-slide previews) |
| 4 | Content Review | Manual in Sheet | — | Status per row in Column O (approved/rejected/regen_image_N) |
| 4b | Content Regen *(optional)* | Sheet R1 = "run" | `tiktok/regen_content.py` *(Phase F)* | Updated images + Content Queue rows |
| 5 | Promote & Schedule | `repository_dispatch: tiktok-promote-and-schedule` | `tiktok/promote_and_schedule.py` | `carousel-schedule.json` (7d × 3 slots), Sheet status → "scheduled" |
| 6 | Daily Posting | 3x daily cron (10am/4pm/7pm ET) | `tiktok/post_content.py` | Posts via Publer API, updated `content-log.jsonl` |

**Posting modes:** `TIKTOK_POSTING_ENABLED=true` posts via Publer automatically. `=false` sends Slack alerts with GCS links for manual upload.

**Schedule format:** `data/tiktok/carousel-schedule.json` — flat array of carousel objects with `scheduled_date`, `scheduled_slot` (morning/afternoon/evening), `scheduled_at` (ISO datetime with timezone), and `slide_urls`.

**Idempotency:** `is_content_posted(carousel_id, "tiktok")` checks `content-log.jsonl` before posting. Safe to re-run.

---

## 3. Directory Structure

```
slated-content-engine/              # Renamed from pinterest-pipeline
├── src/
│   ├── shared/                   # Cross-channel code
│   │   ├── apis/                 # Shared API wrappers (Claude, Sheets, GCS, GitHub, etc.)
│   │   ├── utils/                # Shared utilities (safe_get, content_log, plan_utils, etc.)
│   │   ├── paths.py              # Centralized path constants (PROJECT_ROOT, DATA_DIR, etc.)
│   │   ├── config.py             # Model names, costs, URLs, dimensions, timing
│   │   ├── image_cleaner.py      # AI detection avoidance post-processing
│   │   ├── blog_generator.py     # Individual blog MDX generation
│   │   ├── blog_deployer.py      # GitHub commit to goslated.com → Vercel deploy
│   │   ├── generate_blog_posts.py # Blog post orchestrator
│   │   ├── content_memory.py     # Content memory summary generation
│   │   ├── content_planner.py    # Shared planning utilities: strategy/memory/analysis loading
│   │   └── analytics_utils.py    # Channel-agnostic derived metrics + aggregation
│   ├── pinterest/                # Pinterest-specific code
│   │   ├── apis/                 # Pinterest API wrapper
│   │   ├── token_manager.py      # Pinterest OAuth 2.0 token auto-refresh
│   │   ├── pin_assembler.py      # HTML/CSS template → PNG renderer
│   │   ├── generate_pin_content.py # Pin copy + image generation
│   │   ├── generate_weekly_plan.py # Weekly planning orchestrator
│   │   ├── regen_weekly_plan.py  # Plan-level regen orchestrator
│   │   ├── post_pins.py          # Daily Pinterest API posting
│   │   ├── pull_analytics.py     # Pinterest Analytics API pull
│   │   ├── weekly_analysis.py    # Claude-driven weekly performance analysis
│   │   ├── monthly_review.py     # Claude Opus deep monthly strategy review
│   │   ├── publish_content_queue.py # Content Queue sheet publisher
│   │   ├── regen_content.py      # Selective content regeneration
│   │   ├── plan_validator.py     # Plan constraint validation
│   │   ├── setup_boards.py       # One-time board creation
│   │   └── redate_schedule.py    # Pin schedule redating
│   ├── tiktok/                  # TikTok-specific code
│   │   ├── apis/                 # TikTok API wrappers
│   │   │   └── publer_api.py    # Publer REST API wrapper (media import → post)
│   │   ├── generate_weekly_plan.py # Weekly planning orchestrator (7 carousels)
│   │   ├── generate_carousels.py  # Carousel rendering + image gen orchestrator
│   │   ├── publish_content_queue.py # Content Queue sheet publisher
│   │   ├── promote_and_schedule.py # Approved → scheduled (7d×3 slots, schedule JSON)
│   │   ├── post_content.py       # Daily posting via Publer (3x daily cron)
│   │   ├── compute_attribute_weights.py # Explore/exploit weight updater
│   │   └── carousel_assembler.py # HTML/CSS template → multi-slide PNG renderer
│   └── apps-script/              # Google Apps Script source
├── prompts/
│   ├── shared/                   # Cross-channel prompts (blog generation, image prompts)
│   ├── pinterest/                # Pinterest-specific prompts (planning, analysis, review)
│   └── tiktok/                   # TikTok prompts (weekly_plan, carousel_copy, weekly_analysis)
├── templates/
│   ├── pins/                    # HTML/CSS pin templates (5 types × 3 variants)
│   └── tiktok/carousels/        # TikTok carousel templates (4 families × 3 slide types)
├── strategy/                     # Content strategy, brand voice, keywords, CTAs, archetypes
│   ├── pinterest/                # Pinterest-specific strategy (board-structure.json)
│   └── tiktok/                   # TikTok-specific strategy (attribute-taxonomy.json)
├── scripts/                      # One-time migration scripts (e.g., backfill_channel_field.py)
├── docs/
│   └── research/
│       └── tiktok/               # TikTok research docs + community/ subfolder
├── data/                         # Runtime data (gitignored except JSON results)
│   └── generated/                # Generated blog MDX + pin images (gitignored)
├── .github/workflows/            # GitHub Actions workflow definitions
├── analysis/                     # Weekly/monthly analysis outputs
├── architecture/                 # Restructuring plans and execution strategy
├── memory-bank/                  # Project documentation and progress tracking
├── ARCHITECTURE.md               # ← This file
├── CLAUDE.md                     # Agent instructions and project rules
└── render_pin.js                 # Puppeteer renderer (called by pin_assembler.py + carousel_assembler.py)
```

---

## 4. Key Files & Responsibilities

### Shared Scripts (`src/shared/`)

| File | Purpose |
|------|---------|
| `paths.py` | Centralized path constants (PROJECT_ROOT, DATA_DIR, TIKTOK_DATA_DIR, PROMPTS_DIR, etc.) |
| `config.py` | Centralized config: model names, costs, URLs, dimensions (pin + TikTok slide), timing constants |
| `blog_generator.py` | Individual blog MDX generation with frontmatter + Schema.org (4 types: recipe, guide, listicle, weekly-plan) |
| `blog_deployer.py` | Commits blogs to goslated.com repo (Vercel deploy), URL verification, pin schedule creation |
| `generate_blog_posts.py` | Blog post orchestrator — reads plan, generates MDX via `blog_generator.py` |
| `image_cleaner.py` | AI detection avoidance post-processing. Preserves input format (PNG stays PNG, JPEG stays JPEG). Alpha-safe noise for RGBA images. |
| `content_memory.py` | Channel-aware content memory summary generation (8 sections: dedup, topic tracking, pillar mix, keyword frequency, images, fresh pins, treatments, performance history with compounding signal) |
| `content_planner.py` | Shared planning data loading: strategy context, content memory, latest analysis, seasonal windows (no channel-specific files) |
| `analytics_utils.py` | Channel-agnostic `compute_derived_metrics()` + `aggregate_by_dimension()` |

### Shared API Wrappers (`src/shared/apis/`)

| File | Purpose |
|------|---------|
| `claude_api.py` | Claude Sonnet/Opus + GPT-5 Mini integration, prompt template loading, cost tracking. TikTok methods: `generate_tiktok_plan()`, `generate_carousel_copy()` (reserved), `regenerate_tiktok_carousel_spec()` |
| `openai_chat_api.py` | GPT-5 Mini HTTP wrapper (used by claude_api.py for pin copy + image prompts) |
| `sheets_api.py` | Google Sheets CRUD (Weekly Review, Content Queue, Post Log, Dashboard tabs). TikTok: `write_tiktok_content_queue()` (14-col Content Queue), `write_tiktok_weekly_review()` (11-col Weekly Review with B3/B5 control cells), `read_tiktok_plan_status()`, `read_tiktok_plan_regen_requests()`, `reset_tiktok_plan_regen_trigger()`. Separate TikTok spreadsheet (`TIKTOK_SPREADSHEET_ID`). |
| `gcs_api.py` | Google Cloud Storage uploads (primary image hosting for Sheet previews + Pinterest) |
| `drive_api.py` | Google Drive uploads (fallback if GCS fails) |
| `github_api.py` | GitHub Git Data API (atomic multi-file blog commits to goslated.com) |
| `image_gen.py` | AI image generation via gpt-image-1.5 (Replicate Flux Pro as alternate provider) |
| `slack_notify.py` | Slack webhook notifications (Block Kit formatted) |

### Shared Utilities (`src/shared/utils/`)

| File | Purpose |
|------|---------|
| `content_log.py` | JSONL content log read/append operations + channel-aware idempotency check (`is_content_posted()`) |
| `plan_utils.py` | Plan loading, validation helpers, atomic pin-schedule writes |
| `image_utils.py` | MIME detection, Drive file ID parsing, `image_to_data_uri()` for headless rendering |
| `strategy_utils.py` | Brand voice loading |
| `safe_get.py` | Safe dictionary access helper |

### Pinterest Scripts (`src/pinterest/`)

| File | Purpose |
|------|---------|
| `generate_weekly_plan.py` | Claude-driven weekly content planning (8-10 blog posts + 28 pin specs) |
| `generate_pin_content.py` | Pin content pipeline: copy generation (GPT-5 Mini) → AI image generation → pin assembly/rendering |
| `pin_assembler.py` | HTML/CSS template → PNG renderer via Puppeteer (5 template types × 3 variants) |
| `publish_content_queue.py` | Uploads images to GCS, writes Content Queue sheet, stores GCS URLs back to results JSON |
| `post_pins.py` | Daily Pinterest API posting with anti-bot jitter, idempotency, retry logic. Supports `--date=YYYY-MM-DD` override for recovering missed slots (skips jitter when used). |
| `pull_analytics.py` | Pinterest Analytics API pull (impressions, saves, clicks, outbound). Derived metrics computed via `shared/analytics_utils.py`. |
| `weekly_analysis.py` | Claude-driven weekly performance analysis (channel-filtered, strategy-aware, receives content memory + cross-channel context) |
| `monthly_review.py` | Claude Opus deep monthly strategy review (receives content memory + cross-channel context) |
| `regen_content.py` | Selective content regeneration (image/copy/both) based on reviewer feedback |
| `regen_weekly_plan.py` | Plan-level topic replacement based on reviewer feedback |
| `plan_validator.py` | Plan constraint validation (pin counts, board distribution, etc.) |
| `redate_schedule.py` | Pin schedule redating utility |
| `setup_boards.py` | One-time Pinterest board creation |
| `token_manager.py` | Pinterest OAuth 2.0 token auto-refresh |

### Pinterest API (`src/pinterest/apis/`)

| File | Purpose |
|------|---------|
| `pinterest_api.py` | Pinterest v5 REST API (pins, boards, analytics) |

### TikTok Scripts (`src/tiktok/`)

| File | Purpose |
|------|---------|
| `generate_weekly_plan.py` | TikTok weekly planning orchestrator. `--plan-only`: Claude generates 7 carousel specs → saves plan JSON → writes Weekly Review tab. `--generate-content`: loads approved plan JSON → renders all specs → uploads ALL slides to GCS → publishes Content Queue (17-col, per-slide previews). `--check-plan-status`: reads B3 for cron collision guard. |
| `generate_carousels.py` | Carousel rendering orchestrator: per-slide AI image generation from `image_prompts` array, translates taxonomy family names (underscores→hyphens), renders slides via `carousel_assembler.py`, cleans output PNGs. Exports `build_slides_for_render()` for reuse by `regen_content.py`. |
| `publish_content_queue.py` | Publishes rendered carousels to TikTok Google Sheet "Content Queue" tab via `SheetsAPI.write_tiktok_content_queue()`. Passes all slide URLs (not just first) for per-slide previews. |
| `pull_analytics.py` | Publer post insights pull → `performance-summary.json`. 28-day lookback, derived metrics via `analytics_utils.py`. |
| `weekly_analysis.py` | Claude-driven weekly performance analysis. TikTok attribute dimensions (topic, angle, structure, hook_type, template_family). |
| `compute_attribute_weights.py` | Bayesian attribute weight updater for explore/exploit feedback loop. 65/35 exploit/explore split, cold-start even distribution until 5+ posts per attribute. `--update` reads performance summary. |
| `regen_plan.py` | Plan-level regen orchestrator: parses reviewer feedback (direct text edits or Claude regen), updates carousel specs, re-writes Weekly Review tab. Supports `change hook/slide to "..."`, `regen hook/slide N`, full regen, and free-form feedback fallback. |
| `carousel_assembler.py` | Multi-slide carousel renderer: loads HTML/CSS templates (4 families × 3 slide types), injects variables, renders all slides in one Puppeteer batch via `render_pin.js --manifest`. Output: 1080×1920px PNGs. |

---

## 5. Data Flow

### Critical Data Files

| File | Written By | Read By |
|------|-----------|---------|
| `data/weekly-plan-W{N}-{date}.json` | `generate_weekly_plan.py`, `regen_weekly_plan.py` | `generate_blog_posts.py`, `generate_pin_content.py`, `regen_weekly_plan.py` |
| `data/blog-generation-results.json` | `blog_generator.py` | `generate_pin_content.py`, `publish_content_queue.py`, `blog_deployer.py`, `regen_content.py` |
| `data/pin-generation-results.json` | `generate_pin_content.py` | `publish_content_queue.py` (adds GCS URLs), `regen_content.py` (updates), `blog_deployer.py` |
| `data/pin-schedule.json` | `blog_deployer.py` | `post_pins.py`, `regen_content.py` |
| `data/content-log.jsonl` | `blog_deployer.py` (initial), `post_pins.py` (posted) | `pull_analytics.py` (update), `content_memory.py`, `weekly_analysis.py`, `monthly_review.py`, `generate_weekly_plan.py` |
| `data/content-memory-summary.md` | `content_memory.py` (8 sections incl. performance history) | `weekly_analysis.py`, `monthly_review.py`, `generate_weekly_plan.py` (via `load_content_memory()`) |
| `data/tiktok/weekly-plan-{date}.json` | `src/tiktok/generate_weekly_plan.py` | (Phase 11 posting pipeline) |
| `strategy/tiktok/attribute-taxonomy.json` | `compute_attribute_weights.py` (Phase 12 updates weights) | `src/tiktok/generate_weekly_plan.py` (reads weights for planning prompt) |

> **Content log `channel` field:** Every entry carries a `channel` field (e.g., `"pinterest"`, `"tiktok"`). Missing channel defaults to `"pinterest"` on read for backward compatibility.
>
> **Weekly analysis channel filter:** `weekly_analysis.py` filters content log entries to the target channel before computing metrics. Default: `"pinterest"`.

### ID Conventions

- **Post IDs:** `W{week}-P{seq}` (e.g., `W12-P01`) — identify blog posts within a week
- **Pin IDs:** `W{week}-{seq}` (e.g., `W12-01`) — identify pins within a week
- **TikTok Carousel IDs:** `TK-W{week}-{seq}` (e.g., `TK-W12-01`) — identify TikTok carousels within a week
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
| `collect-analytics.yml` | Cron: Monday 5:30am ET | Analytics pull (all channels) → content memory refresh → commit data |
| `pinterest-weekly-review.yml` | Cron: Monday 6am ET | Weekly analysis → plan generation (reads fresh analytics from collect step) |
| `generate-content.yml` | Dispatch: `generate-content` | Blog generation → pin generation → content queue publish |
| `regen-plan.yml` | Dispatch: `regen-plan` | Plan-level topic replacement |
| `regen-content.yml` | Dispatch: `regen-content` | Selective image/copy regeneration |
| `deploy-and-schedule.yml` | Dispatch: `deploy-to-preview` | Blog deploy to goslated.com develop branch |
| `promote-and-schedule.yml` | Dispatch: `promote-and-schedule` | Merge develop→main, create pin schedule |
| `daily-post-morning.yml` | Cron: 10am ET | Post scheduled pins (morning slot) |
| `daily-post-afternoon.yml` | Cron: 3pm ET | Post scheduled pins (afternoon slot) |
| `daily-post-evening.yml` | Cron: 8pm ET | Post scheduled pins (evening slot) |
| `monthly-review.yml` | Cron: 1st Monday | Monthly deep strategy review |
| `setup-boards.yml` | Manual only | One-time Pinterest board creation |
| **TikTok Workflows** | | |
| `tiktok-weekly-review.yml` | Cron: Monday 6:30am ET | Weekly analysis → attribute weight update → plan generation (`--plan-only`) |
| `tiktok-regen-plan.yml` | Dispatch: `tiktok-regen-plan` | Regen flagged carousel specs from Weekly Review feedback |
| `tiktok-generate-content.yml` | Dispatch: `tiktok-generate-content` | Render approved specs → per-slide AI images → GCS upload → Content Queue (17-col) |
| `tiktok-promote-and-schedule.yml` | Dispatch: `tiktok-promote-and-schedule` | Read approved carousels → schedule JSON → Sheet status "scheduled" |
| `tiktok-daily-post.yml` | Cron: 10am/4pm/7pm ET | Post scheduled carousels via Publer (or Slack fallback) |

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

11. **TikTok slide URLs use deterministic GCS paths.** Convention: `tiktok/{carousel_id}/slide-{i}.png`. `promote_and_schedule.py` reconstructs URLs from `carousel_id` + `slide_count` without listing blobs. If `generate_weekly_plan.py` fails to upload slides to GCS, the schedule will have missing `slide_urls` (Slack warning sent but carousels still scheduled).

12. **TikTok has a two-phase approval flow.** Phase 1: Weekly Review tab (11 cols A-K, control cells B3/B5, data row 7+) for plan-level spec review. Phase 2: Content Queue tab (17 cols A-Q, cols D-L = per-slide `=IMAGE()` previews, O=Status, P=Feedback, Q=Notes, R1=regen trigger) for rendered slide review. Plan approval (B3) gates content generation. Apps Script guards: B3 blocked while B5=regen, promote-and-schedule blocked while B3≠approved.

13. **TikTok posting has two modes.** `TIKTOK_POSTING_ENABLED=true` posts via Publer API. `=false` sends Slack notifications with GCS links for manual upload. Both modes log to `content-log.jsonl` (with `publer_post_id` or `MANUAL_UPLOAD_REQUIRED`).

14. **TikTok cron triggers are UTC.** Morning=`0 15 * * *` (10am ET), Afternoon=`0 21 * * *` (4pm ET), Evening=`0 0 * * *` (7pm ET = midnight UTC next day). DST shifts these by 1 hour (9am/3pm/6pm during EDT).

15. **TikTok analytics flow (Phase 12).** `collect-analytics.yml` pulls TikTok post insights via Publer API alongside Pinterest analytics. `tiktok-weekly-review.yml` runs: analysis → attribute weight update → plan generation. Feedback loop: `pull_analytics.py` → `performance-summary.json` → `compute_attribute_weights.py --update` → shifted taxonomy weights → `generate_weekly_plan.py` reads updated weights. Cross-channel summaries flow both directions (Pinterest analysis sees TikTok digest, and vice versa) via `generate_cross_channel_summary()`.

16. **TikTok analytics env vars.** `PUBLER_ACCOUNT_ID` is required for the analytics endpoint (`GET /analytics/{account_id}/post_insights`). Different from `PUBLER_WORKSPACE_ID` which is used for posting.

17. **TikTok `image_prompts` replaces `_image_prompt`.** Claude specifies per-slide image prompts in the carousel spec (`image_prompts: [{slide_index, prompt}]`). Only `photo_forward` family gets images (max 3). Other families have empty arrays. `generate_carousels.py` reads `image_prompts` and generates a separate AI image per entry via `_generate_slide_images()`. Slides without image prompts render as text-only CSS.

---

## 10. Deep-Dive References

| Document | What It Covers |
|----------|---------------|
| [`memory-bank/architecture/architecture-data-flows.md`](memory-bank/architecture/architecture-data-flows.md) | Exhaustive data flow reference: schemas, column layouts, field mappings, cross-file dependencies (1,176 lines) |
| [`memory-bank/Audit/audit.md`](memory-bank/Audit/audit.md) | Living codebase audit: file-by-file analysis, known issues, dependency maps |
| [`memory-bank/Audit/dead-code-analysis.md`](memory-bank/Audit/dead-code-analysis.md) | Dead code tracking with line numbers |
| [`architecture/codebase-review/synthesis.md`](architecture/codebase-review/synthesis.md) | Code quality: 24 findings across 8 dimensions, prioritized fix plan |
| [`memory-bank/progress.md`](memory-bank/progress.md) | Chronological changelog of all pipeline phases and features |
| [`architecture/multi-channel-restructure/`](architecture/multi-channel-restructure/) | Multi-channel restructure plan (Phases 1-8 complete) |
| [`src/shared/config.py`](src/shared/config.py) | All hardcoded constants: model names, costs, URLs, dimensions, timing |
| [`src/shared/paths.py`](src/shared/paths.py) | All path constants: PROJECT_ROOT, DATA_DIR, PROMPTS_DIR, etc. |

---

## 11. Tech Stack Summary

- **Language:** Python 3.11
- **Orchestration:** GitHub Actions (cron + `repository_dispatch` from Apps Script)
- **LLMs:** Anthropic Claude (Sonnet/Opus), OpenAI GPT-5 Mini, OpenAI gpt-image-1.5
- **Rendering:** Puppeteer (via `render_pin.js`) — HTML/CSS templates → PNG (pins: 1000×1500, TikTok carousel slides: 1080×1920)
- **Blog hosting:** Vercel (auto-deploys from GitHub commits to goslated.com repo)
- **Image hosting:** Google Cloud Storage (public URLs)
- **Human review:** Google Sheets + Google Apps Script
- **Notifications:** Slack webhooks (Block Kit)
- **Auth:** Pinterest OAuth 2.0 (auto-refresh), Google service account, GitHub PAT
