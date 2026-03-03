# TikTok Pipeline — Detailed Implementation Plan

**Date:** 2026-03-02
**Status:** PARTIALLY SUPERSEDED (2026-03-03) — see note below
**Prerequisite:** Multi-channel restructure (Phases 1-7) complete and burned in

> **Important (2026-03-03):** Phases 3, 4, Pre-Build P2, and Environment Variables in this document describe direct TikTok API integration (Content Posting API + Display API). That approach has been replaced with **Publer** (publer.com) as the posting and analytics intermediary. See `implementation-plan.md` Phase 8 for the current approach. The rest of this document (Phases 1-2, 5-7, Open Decisions, strategy, templates, attribute taxonomy, cadence ramp) remains valid.

---

## Table of Contents

- [Context](#context)
- [Open Decisions](#open-decisions-must-resolve-before-build)
- [Pre-Build: Parallel Track](#pre-build-parallel-track-start-immediately)
- **MVP: Automated Carousel Pipeline with Feedback Loop**
  - [Phase 1: Carousel Rendering Engine](#phase-1-carousel-rendering-engine)
  - [Phase 2: Content Generation Pipeline](#phase-2-content-generation-pipeline)
  - [Phase 3: Posting to TikTok](#phase-3-posting-to-tiktok)
  - [Phase 4: Analytics + Feedback Loop](#phase-4-analytics--feedback-loop)
- **Post-MVP Enhancements**
  - [Phase 5: Video Pipeline](#phase-5-video-pipeline)
  - [Phase 6: Engagement Automation](#phase-6-engagement-automation)
  - [Phase 7: Remotion Migration](#phase-7-remotion-migration)
- **Reference**
  - [Cadence Ramp Plan](#cadence-ramp-plan)
  - [Cost Summary](#cost-summary)
  - [Effort Summary](#effort-summary)
  - [Reuse from Pinterest Pipeline](#reuse-from-pinterest-pipeline)
  - [Risks & Mitigations](#risks--mitigations)
  - [Environment Variables](#environment-variables-env-additions)
  - [What Success Looks Like](#what-success-looks-like)

---

## Context

This is the detailed plan for Phase 8 of the multi-channel restructure. It covers building the full TikTok automation pipeline inside the `slated-content-engine` mono-repo, from carousel rendering through video creation through analytics feedback loops.

**What exists today:**
- 25+ research documents covering TikTok algorithm, tools, build-vs-buy, content strategy, AI detection
- Detailed carousel automation blueprint (`tiktok-carousel-automation-plan.md`)
- Restructured mono-repo with `src/shared/` infrastructure ready for channel plugins

**What we're building:**
- `src/tiktok/` — full pipeline: planning → generation → posting → analytics → feedback
- `prompts/tiktok/` — TikTok-native prompt templates
- `templates/tiktok/` — carousel and video templates
- `.github/workflows/tiktok-*.yml` — automated weekly cycle

---

## Open Decisions (Must Resolve Before Build)

These decisions need to be made before writing code. Some can be made now, others need research or business input.

| # | Decision | Options | Recommendation | Impact |
|---|----------|---------|----------------|--------|
| 1 | **Account type** | Creator vs. Business | **Creator** — 2.75-4.4x higher engagement; full trending sound access; switch to Business later at 10K+ followers | Affects API access, sound library, ad capabilities |
| 2 | **TikTok handle** | e.g., @slated, @slatedapp, @slatedmeals | Short, brand-forward, no numbers, under 15 chars | Hardcoded in CTA templates |
| 3 | **First subcommunity** | #MomTok, #FoodTok, #MealPrep, #DinnerIdeas | Research scored these — need final pick | Drives initial content angles, hashtags, engagement targets |
| 4 | **Starting posting cadence** | 3/week → 5/week → 7/week ramp | **3/week first 2 weeks, 5/week weeks 3-4, 7/week weeks 5+** — algorithm rewards consistency over volume | Template count, generation batch size, cost |
| 5 | **Link-in-bio strategy** | Linktree, direct app store, goslated.com | Creator accounts get link-in-bio at 1K followers; pin app store link in comments until then | CTA slide copy, bio text |
| 6 | **AI content disclosure** | Always label / label realistic only / never label | **Label realistic images, skip for text-on-background carousels** — unlabeled AI content gets -73% reach suppression | `is_aigc` flag in API calls, image generation approach |
| 7 | **Engagement staffing** | Human only / automated / hybrid | **Automated with human escalation** — NapoleonCat + Claude for replies, human reviews negative comments | Phase order, tooling cost |
| 8 | **Initial topic taxonomy** | Needs niche-specific topics defined | Start with 8-10 topics derived from Pinterest strategy pillars, expand based on performance | Attribute weights, prompt templates |
| 9 | **"Face" of the account** | Faceless / founder / hired creator | Research says accounts with a consistent face dramatically outperform faceless — but this is a staffing decision | Video approach, content authenticity |

---

## Pre-Build: Parallel Track (Start Immediately)

These can and should start during or before the mono-repo restructure. They have lead times that would otherwise block the build.

### P1. Create TikTok account + 14-day warmup

**Timeline:** 14 days | **Effort:** 30-60 min/day | **Owner:** Human

The algorithm needs to learn the account's niche before posting. Per the warmup playbook:

- **Day 0:** Create account. Username, logo profile photo (200x200px min), bio (80-120 chars describing value prop).
- **Days 1-3:** Pure consumption. Spend 30-60 min/day consuming content in target niches (#MealPrep, #DinnerIdeas, etc.). Like and comment on 10-15 videos. Follow 20-30 creators in target niche. Do NOT post.
- **Days 4-7:** Light posting. Post 2-3 test videos/carousels (manual, testing formats). Continue 30-40 min daily engagement. Comment on 15-20 videos daily.
- **Days 8-14:** Ramp up. Post 3-5 pieces. Monitor which formats drive saves/shares. Participate in trending sounds/hashtags relevant to niche.

**Why this matters:** Skipping warmup or posting immediately confuses the algorithm's categorization of the account. The 14 days of consumption trains the "For You" feed signals that the algorithm uses to categorize outgoing content.

### P2. Set up Publer account + API access

> **Updated 2026-03-03:** Replaced direct TikTok API applications with Publer. See `implementation-plan.md` Phase 8 for full rationale.

**Timeline:** Same day (no audit) | **Effort:** 30-60 min | **Cost:** $8/mo (Business plan, annual billing, 1 TikTok account)

Steps:
1. Sign up for Publer Business plan (14-day free trial available)
2. Connect TikTok account to Publer workspace
3. Generate API key: Settings > Access & Log In > API Key > Manage API Keys
4. Note your Workspace ID (from Settings or `GET /api/v1/workspaces`)
5. Note your TikTok Account ID (from `GET /api/v1/accounts` or the Publer dashboard)
6. Add to `.env`: `PUBLER_API_KEY`, `PUBLER_WORKSPACE_ID`, `PUBLER_TIKTOK_ACCOUNT_ID`
7. Verify: test `GET /api/v1/accounts` returns your TikTok account

**Confirm during trial:** (a) Business plan includes API access (some docs reference Enterprise-only — verify at signup), (b) TikTok carousel posting works via API, (c) post insights endpoint returns TikTok metrics.

**If Publer doesn't work out:** Fall back to direct TikTok Content Posting API + Display API (original plan preserved in Phases 3-4 below for reference). That path requires 2-4 week audit + sandbox prototype + demo video.

### P3. Set up Google Sheet

**Timeline:** 1-2 hours | **Effort:** Human

Create TikTok-specific Google Sheet with 4 tabs:

| Tab | Purpose | Key Columns |
|-----|---------|-------------|
| **Weekly Review** | Approve/reject weekly content plan | Week #, status, plan summary, exploit/explore split, feedback |
| **Content Queue** | Review individual carousels before posting | Carousel ID, date, slot, attributes (6 cols), caption, thumbnail (IMAGE formula), status, feedback |
| **Post Log** | Track what's been posted | Carousel ID, date posted, TikTok post ID, status, error message, attributes |
| **Performance Data** | Weekly analytics per post | Carousel ID, views, saves, shares, comments, save rate, share rate, attributes, days since posted |

---

# MVP: Automated Carousel Pipeline with Feedback Loop

Phases 1-4 deliver a complete, self-improving carousel pipeline: plan content → generate carousels → post to TikTok → pull analytics → feed performance data back into next week's plan. This is the minimum viable pipeline.

**MVP total effort:** 140-195 hours | **MVP monthly cost:** $22-44/mo

---

## Phase 1: Carousel Rendering Engine

**Goal:** Render multi-slide TikTok carousels from HTML/CSS templates. No external APIs needed — purely local infrastructure.

**Timeline:** Weeks 1-2 | **Effort:** 35-50 hours | **Risk:** LOW

### What gets built

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

#### 2. `render_carousel.js` — Puppeteer multi-slide renderer

Adapt the existing Pinterest `render_pin.js` for multi-slide rendering:
- Input: manifest JSON listing slides + output paths
- For each slide: load HTML, set viewport to 1080x1920, screenshot to PNG
- Validate output: minimum 10KB per slide, correct dimensions
- Batch mode: render all slides for a carousel in one Puppeteer session (reuse browser instance)

**Key difference from Pinterest:** Pinterest renders one image per pin. TikTok carousels need 3-10 slides per post, so batch rendering within a single browser session is important for performance.

**Effort:** 10-15 hours

#### 3. `src/tiktok/carousel_assembler.py`

Orchestrates the rendering pipeline:
- Select template family based on spec
- Inject content variables (headline, body, CTA text, image URLs) into HTML
- Convert images to base64 data URIs (same pattern as `pin_assembler.py`)
- Write temporary HTML files
- Call `render_carousel.js` via subprocess
- Validate output PNGs
- Return list of slide image paths

**Effort:** 10-15 hours

### Verify
- Render sample carousels across all 4 template families
- Verify dimensions (1080x1920), file sizes (>10KB), readability at mobile scale
- Test with 3, 5, 7, and 10 slide counts
- Visual QA: text within safe zones, no clipping

---

## Phase 2: Content Generation Pipeline

**Goal:** Generate 7-21 carousel specs per week via Claude, render them, and publish to Google Sheets for human review.

**Timeline:** Weeks 2-3 | **Effort:** 55-75 hours | **Risk:** MEDIUM

### What gets built

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

Orchestrator that calls the shared content planner then derives TikTok-specific content:

```python
def generate_plan():
    # Get unified topic plan from shared layer
    content_plan = content_planner.generate_content_plan()

    # Compute attribute allocations based on TikTok performance data
    weights = compute_attribute_weights.compute(week_number)

    # Generate TikTok carousel specs via Claude
    carousel_specs = call_claude(
        prompt="prompts/tiktok/weekly_plan.md",
        context={content_plan, weights, performance_data, content_memory}
    )

    # Can also generate independent content not tied to the content plan
    # (trend-reactive, community engagement posts)

    # Validate and write to Sheets + JSON
    write_to_sheets(carousel_specs)
    save_plan_json(carousel_specs)
    slack_notify("TikTok plan ready for review")
```

**Key design point:** The TikTok planner receives the shared content plan as *input context*, not as a rigid constraint. It can derive carousels from those topics, ignore topics that don't suit TikTok, or generate entirely independent content.

**Effort:** 15-20 hours

#### 8. `src/tiktok/generate_carousels.py`

Full orchestrator for rendering a week's carousels:

For each approved carousel spec:
1. Generate slide text + caption via Claude (`carousel_copy.md`)
2. Generate images via DALL-E/Replicate (for photo-forward template; skip for text-only templates)
3. Strip C2PA metadata from AI-generated images (reduces AI detection risk)
4. Call `carousel_assembler.py` to render all slides
5. Upload slide PNGs to GCS
6. Write to Content Queue sheet with `IMAGE()` thumbnail formulas

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

### Verify
- Generate a test week of 7 carousel specs
- Verify Claude output parses to valid JSON with correct attribute tags
- Render all carousels, verify visual quality
- Content Queue sheet populates correctly with thumbnails
- Apps Script trigger fires on approval

---

## Phase 3: Posting to TikTok

> **Updated 2026-03-03:** This phase now uses Publer as the posting intermediary instead of the direct TikTok Content Posting API. The original direct-API approach is preserved below in collapsed form for reference/fallback.

**Goal:** Post carousels automatically via Publer's API, with a manual-posting fallback. Get content live on the platform.

**Timeline:** Weeks 3-4 | **Effort:** 25-35 hours | **Risk:** MEDIUM (no API audit dependency)

### What gets built

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

#### ~~12. `src/tiktok/token_manager.py`~~ — NOT NEEDED

Publer uses a static API key. No OAuth flow, no token refresh, no token store. This eliminates ~5-8 hours of work and ongoing 24-hour token expiry management.

#### 13. `src/tiktok/post_content.py`

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

#### 14. GitHub Actions posting workflows

| Workflow | Trigger | Steps |
|----------|---------|-------|
| `tiktok-promote-and-schedule.yml` | `repository_dispatch` (Sheet approval) | Read approved carousels → distribute across 7 days → write schedule JSON |
| `tiktok-daily-post.yml` | Cron 3x daily (10am, 4pm, 7pm ET) | Read schedule → post via Publer (or log manual) → update logs → Slack |

Each workflow: single concurrency group, Slack failure notifications, timeout guards.

**Effort:** 5-7 hours

### Verify
- Post a test carousel via Publer API (sandbox first, then real)
- Verify GCS image URLs are accessible from Publer's servers (must be publicly readable)
- Verify idempotency — re-running doesn't double-post
- Verify Slack notifications arrive for both success and manual-upload fallback
- Post Log sheet updates correctly
- Content-log.jsonl entries have correct attribute tags
- Verify `is_aigc` handling (or document the gap)

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

---

## Phase 4: Analytics + Feedback Loop

> **Updated 2026-03-03:** Analytics now pulled via Publer's post insights endpoint instead of the TikTok Display API. Original approach preserved in collapsed form below.

**Goal:** Pull TikTok performance data, analyze it, and close the loop so next week's content generation shifts toward what's working.

**Timeline:** Weeks 4-5 | **Effort:** 25-38 hours | **Risk:** LOW-MEDIUM

### What gets built

#### 15. `src/tiktok/pull_analytics.py`

Publer post insights integration (uses the same `publer_api.py` from Phase 3):
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

**Future upgrade:** If deeper analytics needed (audience demographics, traffic sources, daily time-series, saves if not available via Publer), apply for TikTok Display API (`video.list` scope). Estimated effort: 15-25 hours + 1-3 week approval. See `implementation-plan.md` Phase 8c for details.

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

#### 16. `src/tiktok/weekly_analysis.py`

Claude-powered weekly performance analysis:
- Load performance summary + content log
- Compute aggregate trends (which attributes improving/declining)
- Call Claude with analysis prompt
- Output: `analysis/tiktok/weekly/YYYY-wNN-review.md`
- Feed into next week's content planner alongside Pinterest analytics

**Effort:** 10-15 hours

#### 17. GitHub Actions analytics workflows

| Workflow | Trigger | Steps |
|----------|---------|-------|
| `tiktok-weekly-analysis.yml` | Cron Sunday 7pm ET | Pull analytics → compute performance summary → update content memory |
| `tiktok-weekly-generate.yml` | Cron Sunday 8pm ET (after analysis) | Compute attribute weights → generate plan → render carousels → publish to Sheets |

**Effort:** 6-8 hours

#### 18. Wire the feedback loop

This is the integration work that makes the system self-improving:
- `pull_analytics.py` writes `performance-summary.json`
- `compute_attribute_weights.py` reads `performance-summary.json` and shifts allocation toward high performers
- `generate_weekly_plan.py` receives shifted weights, generates content that reflects what's working
- Content memory prevents topic repetition across the 2-week window
- TikTok analytics also feed into `src/shared/content_planner.py` alongside Pinterest data

**Effort:** 4-7 hours

### Verify
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

# MVP COMPLETE

At this point, the pipeline is operational and self-improving:
- Carousels are generated weekly based on strategy + performance data
- Human reviews and approves in Google Sheets
- Carousels post automatically (or via manual fallback)
- Analytics feed back into the next week's planning
- The system learns what attribute combinations work and allocates accordingly

**MVP effort total:** 140-198 hours
**MVP monthly cost:** $30-52/mo (Claude + DALL-E + GCS + GitHub Actions + Publer $8/mo)

Everything below is additive. Prioritize based on performance data and capacity.

---

# Post-MVP Enhancements

## Phase 5: Video Pipeline

**Goal:** Add video content alongside carousels — voiceover + background music + visual composition.

**Timeline:** Weeks 6-8 after MVP stable | **Effort:** 45-70 hours | **Risk:** MEDIUM | **Monthly cost addition:** +$128-130/mo

**Prerequisite:** MVP pipeline is stable and posting consistently. Video is additive, not a replacement for carousels.

### What gets built

#### 19. ElevenLabs TTS integration

- API client wrapper for text-to-speech
- Voice selection (pre-selected voice ID stored in env)
- Character limit tracking (Creator plan: 100K chars/month, ~150K needed → may need Professional at $99/mo depending on volume)
- Output: MP3/WAV audio file per video

**Plan:** ElevenLabs Creator ($11/mo) for initial volumes, upgrade if needed.

**Effort:** 5-8 hours

#### 20. Epidemic Sound integration

- Music track selection (manual curation of 20-30 tracks matching brand vibe, or API if available)
- Licensing tracking per video
- Commercial license ($19/mo) covers TikTok + all platforms

**Effort:** 3-5 hours

#### 21. Audio mixing (FFmpeg)

- Combine voiceover + background music
- Volume leveling (voice at 100%, music at 15-25%)
- Normalization to TikTok-compatible format
- Output: mixed audio track ready for video composition

**Effort:** 8-12 hours

#### 22. Video rendering — Creatomate (bridge solution)

**Why Creatomate first:** Building custom Remotion templates is 60-80 hours. Creatomate ($99/mo) lets us ship video immediately while we build the long-term solution in Phase 7.

- Set up 3-5 core video templates in Creatomate (listicle, tutorial, problem-solution, recipe walkthrough)
- API integration: send script + images + audio → receive rendered MP4
- Template variables: text overlays, image sequences, timing, transitions
- Output: 1080x1920 MP4 ready for posting

**Effort:** 15-20 hours

#### 23. Extend content generation for video

- Add video specs to weekly plan generation (2-3 videos/week alongside carousels)
- New prompt: `prompts/tiktok/video_script.md` — generates narration script, shot list, timing cues
- Orchestrator: `src/tiktok/generate_videos.py` — script generation → TTS → music selection → Creatomate render → GCS upload
- Extend Content Queue sheet for video rows
- Extend `post_content.py` to handle video uploads (TikTok Content Posting API supports both photo and video)

**Effort:** 20-30 hours

### Verify
- Render a test video end-to-end (script → TTS → music → Creatomate → MP4)
- Post video via API (or manual fallback)
- Verify audio quality, timing, text overlay readability
- Run mixed week: 4 carousels + 2 videos

---

## Phase 6: Engagement Automation

**Goal:** Automated comment monitoring, classification, and reply generation.

**Timeline:** Can start anytime after MVP | **Effort:** 25-40 hours | **Risk:** LOW | **Monthly cost addition:** +$52-62/mo

This phase is optional and can be deferred. It improves post-publish performance but isn't required for the core pipeline.

### What gets built

#### 24. Comment ingestion + classification

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

#### 25. Auto-reply with rate limiting

- Claude generates unique replies (no templates — every reply different)
- Brand voice enforcement via system prompt
- Rate limits: 5-15 replies/hour, 20-50/day
- Random delay between replies: 2-15 minutes (avoid obvious automation)
- Reply timing after comment: 5-30 minutes

**Effort:** 10-15 hours

#### 26. `tiktok-engagement.yml` workflow

- Cron every 4 hours
- Fetch → classify → generate → post replies
- Alert on negative comments
- Log all interactions

**Effort:** 5-10 hours

### Verify
- Fetch comments from a test post
- Verify classification accuracy on 20+ comments
- Confirm rate limiting prevents bursts
- Verify human escalation works for complaints

---

## Phase 7: Remotion Migration

**Goal:** Replace Creatomate ($99/mo) with custom Remotion templates for video rendering. Full control, lower marginal cost.

**Timeline:** Weeks 10-14 after Phase 5 stable | **Effort:** 65-95 hours | **Risk:** MEDIUM-HIGH (significant React/TS learning curve)

Only worth doing once the video pipeline is proven and running consistently. Creatomate works fine in the interim.

### What gets built

#### 27. Remotion templates (React/TypeScript)

- Convert Creatomate templates to Remotion compositions
- 3-5 video types: listicle, tutorial, problem-solution, recipe walkthrough, before-after
- Timeline composition: image sequences + text overlays + transitions + audio sync
- Parameterized: all content injected via JSON props

**Effort:** 40-60 hours

#### 28. AWS Lambda rendering

- Remotion Lambda for serverless video rendering
- S3 output → GCS transfer (or direct S3 serving)
- Cost: ~$0.01 per render on Lambda + Remotion license ($100/mo Automators plan)

**Effort:** 15-20 hours

#### 29. Migration + Creatomate cancellation

- Swap Creatomate API calls for Remotion Lambda calls in `generate_videos.py`
- Side-by-side quality comparison
- Cancel Creatomate subscription ($99/mo savings, net +$1/mo for Remotion)

**Effort:** 10-15 hours

### Verify
- Render same video through both Creatomate and Remotion, compare quality
- Verify Lambda rendering completes within timeout
- Run full week with Remotion-rendered videos
- Monitor cost per render

---

# Reference

## Cadence Ramp Plan

| Week | Posts/week | Mix | Notes |
|------|-----------|-----|-------|
| 1-2 | 3 | 3 carousels | Warmup period. Manual posting likely (API audit pending). |
| 3-4 | 5 | 5 carousels | Automated posting live (if API approved). Cold-start attribute allocation. |
| 5-6 | 7 | 7 carousels | 1/day. First performance data feeding back into planner. |
| 7-8 | 10-14 | 7-10 carousels + 2-4 videos | Video pipeline online (Phase 5). Mixed content. |
| 9+ | 14-21 | 10-14 carousels + 4-7 videos | Full cadence. Feedback loop mature. Scale based on performance data. |

**Don't rush to 21/week.** The research says 3-5/week is the data-optimal range for engagement per post. Scale only when content quality and engagement signals justify it. Algorithm rewards consistency over volume.

## Cost Summary

| Milestone | Monthly Cost | What's running |
|-----------|-------------|----------------|
| **MVP (Phases 1-4)** | $30-52/mo | Carousel pipeline with feedback loop (includes Publer $8/mo) |
| **+ Phase 5 (Video)** | $150-175/mo | + Creatomate + ElevenLabs + Epidemic Sound |
| **+ Phase 6 (Engagement)** | $200-235/mo | + NapoleonCat + additional Claude API |
| **+ Phase 7 (Remotion)** | $200-235/mo | Creatomate dropped, Remotion replaces it (cost-neutral) |

## Effort Summary

| Phase | Description | Hours | Risk | Depends on |
|-------|-------------|-------|------|------------|
| Pre-build | Account warmup, Publer setup, Sheet setup | 14 days + 3hrs | LOW | Nothing |
| **1** | **Carousel rendering engine** | **35-50** | **LOW** | Pre-build |
| **2** | **Content generation pipeline** | **55-75** | **MEDIUM** | Phase 1 |
| **3** | **Posting to TikTok (via Publer)** | **25-35** | **MEDIUM** | Phase 2 |
| **4** | **Analytics + feedback loop (via Publer)** | **25-38** | **LOW-MEDIUM** | Phase 3 |
| | **MVP TOTAL** | **140-198** | | |
| 5 | Video pipeline (Creatomate) | 45-70 | MEDIUM | MVP stable |
| 6 | Engagement automation | 25-40 | LOW | MVP stable |
| 7 | Remotion migration | 65-95 | MEDIUM-HIGH | Phase 5 stable |
| | **Full build total** | **295-428** | | |

## Reuse from Pinterest Pipeline

| Component | Reuse Level | Notes |
|-----------|------------|-------|
| `src/shared/apis/claude_api.py` | 100% | Same module, new prompts |
| `src/shared/apis/image_gen.py` | 100% | DALL-E/Replicate calls identical |
| `src/shared/apis/gcs_api.py` | 100% | GCS upload identical |
| `src/shared/apis/sheets_api.py` | 80% | Same patterns, TikTok-specific sheet config |
| `src/shared/apis/slack_notify.py` | 80% | Add TikTok event types |
| `src/shared/content_planner.py` | 100% | TikTok calls same unified planner |
| `src/shared/content_memory.py` | 90% | Extend for TikTok content dedup |
| `src/shared/analytics_utils.py` | 70% | Shared log format, TikTok-specific metrics |
| `src/shared/image_cleaner.py` | 80% | Same validation, different dimensions |
| `render_pin.js` → `render_carousel.js` | 60% | Puppeteer patterns reused, multi-slide is new |
| `pin_assembler.py` → `carousel_assembler.py` | 50% | Template injection reused, multi-slide orchestration new |
| `post_pins.py` → `post_content.py` | 50% | Posting patterns reused, Publer API simpler than Pinterest direct API |
| `generate_weekly_plan.py` | 30% | Architecture reused, attribute system is new |
| GitHub Actions workflow patterns | 70% | Same structure, TikTok-specific steps |
| Apps Script trigger pattern | 80% | Same dispatch mechanism, different sheet |
| Token management patterns | N/A | Not needed — Publer uses static API key (no OAuth flow) |

**Estimated reuse savings:** 150-190 hours (40-50% reduction from building from scratch)

## Risks & Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Publer service disruption or API changes | Can't post programmatically | Low | Manual posting fallback built into every workflow; can fall back to direct TikTok API if needed (preserved in Phase 3 reference) |
| Publer Business plan doesn't include API access | Must upgrade to Enterprise | Low | Verify during 14-day trial before committing |
| AI content detection on images | Reach suppression on photo-forward carousels | Medium | Strip C2PA metadata; use Replicate/Flux (lower detection); self-label when uncertain |
| Cold start — no performance data for 2-3 weeks | Blind attribute allocation | High (expected) | Cold-start mode: even distribution, learn fast |
| Algorithm doesn't reward carousels in our niche | Lower-than-expected reach | Low-Medium | Research says carousels get 81% higher engagement — but monitor and adjust mix |
| ElevenLabs TTS flagged as AI voice | Video reach suppressed | Low | Use stock voices that sound natural; human voiceover backup |
| TikTok US regulatory disruption | Platform unavailable | Low | Build TikTok-native; keep unwatermarked source assets for reuse on Reels/Shorts |
| Remotion learning curve (React/TS) | Phase 7 timeline slip | Medium | Creatomate bridge removes time pressure; Remotion migration is optional upgrade |
| Engagement automation triggers spam detection | Account penalty | Low | Conservative rate limits (20-50 replies/day); all replies unique via Claude; random delays |
| Template fatigue | Declining engagement | Low-Medium | 4 families from day 1; add 1-2 new families every 4-6 weeks |

## Environment Variables (.env additions)

```bash
# TikTok posting via Publer (updated 2026-03-03 — replaces direct TikTok API vars)
PUBLER_API_KEY=                        # Generated in Publer dashboard
PUBLER_WORKSPACE_ID=                   # From Publer dashboard or GET /api/v1/workspaces
PUBLER_TIKTOK_ACCOUNT_ID=             # From GET /api/v1/accounts or Publer dashboard
TIKTOK_POSTING_ENABLED=false           # Set to true when Publer integration verified

# TikTok Google Sheet (separate from Pinterest sheet)
TIKTOK_GOOGLE_SHEET_ID=
TIKTOK_GOOGLE_SHEET_URL=

# Video — Phase 5
CREATOMATE_API_KEY=                   # Phase 5 only, dropped in Phase 7
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
EPIDEMIC_SOUND_API_KEY=

# Video — Phase 7 (replaces Creatomate)
REMOTION_AWS_ROLE_ARN=

# Engagement — Phase 6
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

### Month 3 (+ Phase 5)
- Mixed content: carousels + videos
- 10-14 posts/week automated cadence
- Performance data driving 65/35 exploit/explore allocation
- 500-3,000 followers
- 1-2 breakout posts

### Month 6 (+ Phases 6-7)
- Full pipeline: carousels + Remotion videos + engagement automation
- 14-21 posts/week
- Feedback loop mature — clear signal on what works
- 2,000-15,000 followers
- Proven content formats, community forming

### Month 12
- Established presence, 10,000-50,000+ followers
- Content engine self-improving weekly
- TikTok analytics feeding back into shared content planner alongside Pinterest
- Ready to evaluate paid promotion of top performers
