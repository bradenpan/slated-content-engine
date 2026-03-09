# Pinterest Pipeline — Progress Tracker

## Overview

Fully automated Pinterest content pipeline for Slated (family meal planning iOS app). Handles the entire lifecycle: weekly content planning, blog post generation, pin creation, deployment, daily posting, and performance analysis — with human approval gates at key decision points.

### Architecture

```
Plan → Generate → Review → Deploy → Post → Analyze → (feeds next Plan)
```

**Orchestration:** GitHub Actions (cron + webhook triggers)
**LLM:** Claude Sonnet 4.6 (routine), Claude Opus 4.6 (deep analysis), GPT-5 Mini (pin copy + image prompts, Claude fallback)
**Content:** Blog posts (MDX) + pin images (AI-generated via gpt-image-1.5) + pin copy
**Deployment:** goslated.com via GitHub/Vercel (blogs), Pinterest API (pins)
**Coordination:** Google Sheets (human review + automation triggers), Slack (notifications)
**Measurement:** Pinterest Analytics API, weekly/monthly Claude-driven analysis

### Pipeline Flow

| Step | Trigger | What Happens | Output |
|------|---------|-------------|--------|
| 1. Weekly Review | Monday 6am ET cron | Pull analytics → Claude generates plan (8-10 blog posts, 28 pins) | Plan in Google Sheet |
| 2. Plan Approval | Sheet B3 = "approved" | Apps Script triggers GitHub Action | — |
| 3. Content Generation | Plan approval webhook | Generate blog MDX + pin copy + pin images + render PNGs | Content Queue in Sheet |
| 4. Content Approval | All Column J != "pending_review" | Apps Script triggers deploy | — |
| 5. Deploy to Preview | Content approval webhook | Commit blogs to goslated.com develop branch (Vercel preview) | Preview URLs |
| 6. Production Approval | Sheet B4 = "approved" | Apps Script triggers promote | — |
| 7. Promote & Schedule | Production approval webhook | Merge develop→main, create pin-schedule.json | Live blog URLs + posting queue |
| 8. Daily Posting | 3x daily cron (10am/3pm/8pm ET) | Post 1-2 pins per slot from schedule | Live pins on Pinterest |
| 9. Weekly Analysis | Part of step 1 | Claude analyzes last week's performance | Feeds next plan |
| 10. Monthly Review | 1st Monday of month | Claude Opus deep strategy review | Strategy recommendations |

### What's Built

**Core Pipeline (src/)**
- `generate_weekly_plan.py` — Claude-driven content planning with strategy/analytics/memory context
- `generate_blog_posts.py` — Blog post orchestrator (4 types: recipe, guide, listicle, weekly-plan)
- `blog_generator.py` — Individual blog MDX generation with frontmatter + Schema.org
- `generate_pin_content.py` — Pin copy generation (GPT-5 Mini) + AI image generation + assembly
- `pin_assembler.py` — HTML/CSS template → PNG renderer via Puppeteer (5 template types, 3 variants each)
- `publish_content_queue.py` — GCS upload (Drive fallback) + Sheet write + Slack notification
- `blog_deployer.py` — GitHub commit to goslated.com → Vercel deploy → URL verification → pin schedule creation
- `post_pins.py` — Daily Pinterest API posting with anti-bot jitter, idempotency, retry logic
- `weekly_analysis.py` — Claude-driven weekly performance analysis
- `monthly_review.py` — Claude Opus deep monthly strategy review
- `pull_analytics.py` — Pinterest Analytics API pull (impressions, saves, clicks, outbound)
- `regen_weekly_plan.py` — Plan-level feedback and regeneration orchestrator
- `plan_validator.py` — Plan validation logic (extracted from generate_weekly_plan.py)
- `redate_schedule.py` — Pin schedule redating (extracted from workflow inline Python)
- `paths.py` — Centralized path constants (PROJECT_ROOT, DATA_DIR, PROMPTS_DIR, etc.)
- `config.py` — Centralized config values (model names, costs, URLs, dimensions, timing)

**Shared Utilities (src/utils/)**
- `image_utils.py` — MIME detection + Drive file ID parsing
- `content_log.py` — JSONL content log CRUD operations
- `plan_utils.py` — Plan loading, validation helpers, atomic pin-schedule writes
- `strategy_utils.py` — Brand voice loading
- `content_memory.py` — Content memory summary generation (canonical version)

**API Wrappers (src/apis/)**
- `claude_api.py` — Claude Sonnet/Opus with prompt templates, GPT-5 Mini integration, token/cost tracking
- `pinterest_api.py` — Pinterest v5 REST API (pins, boards, analytics)
- `sheets_api.py` — Google Sheets (Weekly Review, Content Queue, Post Log, Dashboard tabs)
- `gcs_api.py` — Google Cloud Storage (primary pin/hero image upload for inline Sheet previews)
- `drive_api.py` — Google Drive (fallback pin image upload for inline Sheet previews)
- `github_api.py` — GitHub Git Data API (atomic multi-file blog commits)
- `image_gen.py` — AI image generation via gpt-image-1.5 (Replicate Flux Pro as alternate provider)
- `slack_notify.py` — Slack webhook notifications (Block Kit)
- `token_manager.py` — Pinterest OAuth 2.0 token auto-refresh

**Workflows (.github/workflows/)**
- `collect-analytics.yml`, `pinterest-weekly-review.yml`, `generate-content.yml`, `deploy-and-schedule.yml`, `promote-and-schedule.yml`
- `daily-post-morning.yml`, `daily-post-afternoon.yml`, `daily-post-evening.yml`
- `monthly-review.yml`, `regen-plan.yml`, `regen-content.yml`, `setup-boards.yml`

**Prompt Templates (prompts/)** — 10 templates in `prompts/shared/` (blog generation, image prompts) and `prompts/pinterest/` (planning, pin copy, analysis, review)

**Strategy (strategy/)** — Content strategy, brand voice, board structure, keyword lists, seasonal calendar, CTA variants, product overview

**Pin Templates (templates/pins/)** — 5 template types (recipe, tip, listicle, problem-solution, infographic) × 3 visual variants each, rendered via Puppeteer. Structured JSON content extraction per template type, CTA pill buttons on all 15 variants, mobile-optimized font sizes, and template-specific polish (recipe time badges, listicle truncation, problem/solution weights, dynamic labels).

**Production cadence:** 8-10 blog posts + 28 pins/week, posted 4x daily

---

## Phase 1: Image Quality Gates

**Date:** 2026-02-20
**Commit:** `6542988` — `feat: add image quality gates (stock ranking + AI validation)`

### Problem

Zero programmatic image quality validation. Stock photos auto-selected the first search result regardless of relevance. AI-generated images passed if >10KB and decodable. The only quality gate was manual human review in the Content Queue sheet.

### What Was Added

Two automated quality gates that run during content generation, before images reach human review.

#### Stock Photo Ranking (Tier 1)

- Downloads thumbnails for top 5 search candidates
- Claude Haiku evaluates each thumbnail for relevance to the pin topic
- Scoring is template-aware (recipe-pin checks for correct food, tip-pin checks for text-background suitability, etc.)
- Threshold: **6.5/10** to accept
- Below 6.5: retry with broader/alternative search queries
- Below 5.0 on retry: fall back to AI image generation
- Cost: ~$0.002/pin (Haiku + 5 thumbnails)

#### AI Image Validation (Tier 2)

- Claude Sonnet evaluates each generated image against quality criteria
- Checks for disqualifiers: hands, faces, text, watermarks, unnatural colors
- Template-specific criteria (food accuracy for recipes, text-readability for tips)
- Threshold: **6.5/10** to accept
- Below 6.5: regenerate once with Claude's specific actionable feedback appended to the prompt
- Below 6.5 after retry: accept with `low_confidence` flag
- Cost: ~$0.015/pin (Sonnet + full image)

#### Content Queue Visibility

- Per-pin Notes column shows quality score + retry info + LOW CONFIDENCE flag
- Summary row at bottom: `"Stock: N ranked, N retried, N fell back to AI"` / `"AI: N validated, N regenerated, N low_confidence"`
- Enables threshold calibration — compare scores against actual image quality you see in the Sheet

### Files Changed

| File | Change |
|------|--------|
| `src/apis/claude_api.py` | Vision support in `_call_api()`, `rank_stock_candidates()` (Haiku), `validate_ai_image()` (Sonnet), `stock_retry` in `generate_image_prompt()` |
| `src/generate_pin_content.py` | `_source_stock_image()` ranking flow, `_source_ai_image()` validation flow, quality_meta propagation through return types |
| `src/apis/image_stock.py` | `download_thumbnail()` method |
| `src/publish_content_queue.py` | `_build_quality_note()`, `_compute_quality_stats()`, integrated into `publish()` |
| `src/apis/sheets_api.py` | `quality_gate_stats` param in `write_content_queue()`, per-pin notes, summary row |
| `prompts/image_rank.md` | **New** — Template-aware stock photo ranking prompt |
| `prompts/image_validate.md` | **New** — Template-aware AI image validation prompt |

### Cost Impact

| | Before | After | Delta |
|---|---|---|---|
| Weekly image cost | ~$0.64 | ~$1.08 | +$0.44/week |
| Monthly image cost | ~$2.78 | ~$4.70 | +$1.90/month |

### Status

Implemented, not yet tested in production. First live run will establish baseline quality scores and validate that the 6.5 threshold is calibrated correctly.

### Follow-up: Minor Robustness Fixes

**Date:** 2026-02-20
**Commit:** `d204b4c` — `fix: JPEG detection, regen error handling, and empty-rank guard`

Three minor fixes from code review of the quality gates implementation:

| Fix | File | What |
|-----|------|------|
| JPEG detection | `claude_api.py:763` | `_call_api()` hardcoded `image/png` for raw bytes. Stock thumbnails are JPEG. Now sniffs `\xff\xd8` magic bytes to set correct media type. |
| Regen error handling | `generate_pin_content.py:829` | If `image_gen_api.generate()` throws during feedback-based regeneration, the whole pin failed. Now catches the exception and accepts the original image with `low_confidence=True`. |
| Empty ranked guard | `generate_pin_content.py:658` | `ranked[0]` would crash if `rank_stock_candidates()` returned empty (shouldn't happen in practice, but cheap insurance). Falls back to `filtered[0]`. |

---

## Phase 2: Per-Item Feedback & Targeted Regeneration

**Date:** 2026-02-21

### Problem

Content review was all-or-nothing. Reviewers could only approve or reject the entire Content Queue. If 2 out of 28 pins had bad images or weak copy, the options were: approve everything (lower quality), reject everything and regenerate the entire batch (waste ~$2 in API costs and 15 minutes), or manually edit outside the pipeline. No way to say "this pin's image is wrong, regenerate just the image with this feedback."

### What Was Added

Per-item review workflow allowing reviewers to provide targeted feedback on individual pins and trigger selective regeneration of just the image, just the copy, or both — without touching the other 26 pins.

#### Review Flow

1. Reviewer opens Content Queue in Google Sheet
2. For any pin, sets Column J (Status) to one of:
   - `regen_image` — regenerate only the image
   - `regen_copy` — regenerate only the title/description
   - `regen` — regenerate both image and copy
3. Optionally writes feedback in Column L (Feedback), e.g., "Image shows pasta, should be soup" or "Title too generic, mention slow cooker"
4. Clicks the **Run Regen** button (or sets N1 to "run")
5. Apps Script fires `repository_dispatch: regen-content` to GitHub Actions
6. Regen workflow runs, regenerates only flagged items, re-renders pins, updates Sheet rows in-place
7. Slack notification arrives with per-item results and score changes
8. Reviewer re-checks regenerated items, approves or flags again

#### Regeneration Paths

| Regen Type | What Changes | What's Preserved |
|------------|-------------|-----------------|
| `regen_image` | New image sourced (stock → AI fallback), pin re-rendered | Title, description, CTA, template, board |
| `regen_copy` | New title + description from Claude, pin re-rendered | Image, CTA, template, board |
| `regen` | Both image and copy regenerated | CTA, template, board |

#### Feedback Integration

- **Image feedback** → passed to `generate_image_prompt(regen_feedback=...)` → Claude generates new search terms/AI prompt that addresses the specific issue
- **Copy feedback** → detected as `_copy_feedback` in pin spec → appended to Claude's system message as explicit guidance to address reviewer concerns
- Feedback is optional — regen works without it (random variation) but produces better results with it

#### Deploy Gate

The existing deploy gate (`allContentReviewed()`) blocks on any row with status not in `["approved", "rejected"]`. Regen statuses (`regen_*`) are blocking by design — the reviewer must approve or reject after regen before the week can deploy.

### Files Changed

| File | Change |
|------|--------|
| `src/regen_content.py` | **New** — Core regeneration script. Reads regen requests from Sheet, loads pin data, regenerates flagged items (image/copy/both), re-renders PNGs, uploads to Drive, updates Sheet rows in-place, sends Slack notification |
| `.github/workflows/regen-content.yml` | **New** — GitHub Actions workflow triggered by `repository_dispatch: regen-content` + manual `workflow_dispatch`. Same env/secrets/concurrency as generate-content.yml, includes Puppeteer setup |
| `src/apis/sheets_api.py` | Added Column L (Feedback) to header/rows, `read_regen_requests()`, `update_content_row()`, `reset_regen_trigger()`, widened `read_content_approvals()` from A:K to A:L |
| `src/apis/claude_api.py` | Added `regen_feedback` parameter to `generate_image_prompt()` for image feedback propagation |
| `src/generate_pin_content.py` | `_source_stock_image()` and `_source_ai_image()` read `_regen_feedback` and pass to image prompt/generation |
| `src/publish_content_queue.py` | Writes regen trigger cells M1="Regen →", N1="idle" after content queue publish |
| `src/apis/slack_notify.py` | Added `notify_regen_complete()` — Block Kit message with per-item details, score changes, and success/failure breakdown |
| `src/apis/drive_api.py` | Added `download_image()` and `delete_image_by_name()` methods for regen image management |

#### Google Apps Script Updates

- `onEdit()` trigger detects N1="run" → fires `repository_dispatch: regen-content`
- `runRegen()` button function for manual trigger
- `allContentReviewed()` already blocks on `regen_*` statuses (no change needed)

### Cost Impact

Regen only processes flagged items, so cost scales with the number of items regenerated, not the full batch:

| Regen Type | Cost per Item |
|------------|--------------|
| `regen_image` (stock) | ~$0.002 (Haiku ranking) |
| `regen_image` (AI) | ~$0.06 (DALL-E) or ~$0.07 (Flux Pro) + $0.015 (Sonnet validation) |
| `regen_copy` | ~$0.01 (Sonnet copy generation) |
| `regen` (both) | Image cost + copy cost |

Typical regen cycle (2-3 items): $0.05-$0.25 vs $2+ for full batch regeneration.

### Status

Implemented. First live run scheduled for Monday 2026-02-23 content review cycle.

---

## Phase 2.1: Pre-Launch Bug Fixes

**Date:** 2026-02-21

Pre-launch code review of the regen feature uncovered 5 bugs. Three independent review agents traced every data path, trigger, and failure mode. Two bugs were critical (would cause silent failures), three were medium severity.

### Bug 1 (CRITICAL): Hero images missing on fresh GitHub Actions runner

**Problem:** When `regen_copy` runs, it needs to re-render the pin PNG with the new title/description overlaid on the original hero image. But `*.png` is gitignored — hero images exist only on the runner that originally generated them. The regen runner is fresh; `hero_image_path` from `pin-generation-results.json` points to a nonexistent file. Result: copy is regenerated in JSON but the pin is never re-rendered. Sheet row gets updated text but the thumbnail stays the same.

**Fix:** During initial publish (`publish_content_queue.py`), store each pin's Drive thumbnail URL as `_drive_image_url` in `pin-generation-results.json` (which IS committed to git). During regen, if the local hero image is missing, extract the Drive file ID from the stored URL and download the image via `drive_api.download_image()`. New DriveAPI methods: `download_image()`, `delete_image_by_name()`.

### Bug 2 (CRITICAL): Copy feedback never passed to Claude

**Problem:** Reviewer writes "Title too generic, mention slow cooker" and sets `regen_copy`. The feedback is stored as `_copy_feedback` on the pin spec, but `generate_pin_copy()` in `claude_api.py` never reads it. The spec is passed to Claude as JSON context, but no instruction tells Claude to look for feedback. Result: Claude generates different copy but doesn't address the reviewer's specific concern.

**Fix:** In `generate_pin_copy()`, detect if any pin spec in the batch contains `_copy_feedback`. If so, append explicit guidance to the system message: "IMPORTANT: The reviewer rejected the previous copy with this feedback: {feedback}. Address their concerns specifically."

### Bug 3 (MEDIUM): Blog items silently skip regen

**Problem:** Blog rows have post IDs (e.g., "B12-01") that don't exist in `pin-generation-results.json` (which only contains pins). If a reviewer flags a blog row for regen, the lookup returns `None`, a warning is logged, and the item is silently skipped. The row stays as `regen_*`, permanently blocking the deploy gate.

**Fix:** Detect blog items early in the regen loop (item type = "blog"). Reset status to `pending_review` with a note: "Blog regen not yet supported — approve or reject manually." This unblocks the deploy gate and informs the reviewer.

### Bug 4 (MEDIUM): Duplicate images accumulate in Google Drive

**Problem:** Initial publish uses `upload_pin_images()` which clears the entire Drive folder first. But regen uses `upload_image()` which uploads without clearing. Each regen cycle adds a new file without deleting the old version. Over multiple regen cycles, orphan images accumulate in the Drive folder.

**Fix:** Before uploading a replacement image in regen, call `drive.delete_image_by_name(filename)` to remove the previous version. New DriveAPI method `delete_image_by_name()` finds and deletes files by name in the pins folder.

### Bug 5 (MEDIUM): Failed regens not reported to user

**Problem:** If image generation fails for a specific pin during regen (API error, rate limit), the error is caught and logged, but no entry is added to `regen_results`. The Slack notification only mentions successes. If ALL items fail, no notification is sent at all. Failed rows stay as `regen_*` status, blocking the deploy gate with no visibility into why.

**Fix:** Track failures in `regen_results` with error details. Reset failed rows to `pending_review` with a note ("Regen failed: {error}") so they don't block the deploy gate. Updated `notify_regen_complete()` to show both successes and failures, with orange color when failures are present.

### Files Changed

| File | Bug(s) | Change |
|------|--------|--------|
| `src/regen_content.py` | 1, 3, 4, 5 | Drive download fallback for hero images, blog item detection/reset, delete-before-upload for Drive images, failure tracking in regen_results, Sheet row reset for failed items |
| `src/apis/claude_api.py` | 2 | `_copy_feedback` detection in `generate_pin_copy()` system message |
| `src/publish_content_queue.py` | 1 | Store `_drive_image_url` back to `pin-generation-results.json` after Drive upload |
| `src/apis/drive_api.py` | 1, 4 | `download_image()` method, `delete_image_by_name()` method |
| `src/apis/slack_notify.py` | 5 | `notify_regen_complete()` split into succeeded/failed, shows failure details |

### Status

All 5 fixes implemented. No Google Apps Script changes required — all fixes are server-side Python.

---

## Phase 3: Topic Dedup Window Extension + Targeted Replacement

**Date:** 2026-02-21

### Problem

Two issues with content plan deduplication:

1. **Topic repetition window too short.** The pipeline checked only 4 weeks of history before allowing topic reuse. At 8-10 blog posts/week, that's only 32-40 posts before topics become eligible again — too soon given 96+ untargeted keywords remain available. By week 5, Claude could start recycling topics.

2. **Full plan regeneration for single-post violations.** When `validate_plan()` caught a duplicate topic or negative keyword violation on even one blog post, the entire plan (10 blog posts + 28 pins) was regenerated from scratch. This wasted ~$0.10 in API costs and 15-25 seconds, and risked introducing new violations in the previously-clean posts.

### What Was Changed

#### Change 1: 10-Week Topic Repetition Window

Extended the topic dedup lookback from 4 weeks to 10 weeks (~80-100 posts of history). This ensures topic uniqueness across a much larger content library before allowing reuse.

- `TOPIC_REPETITION_WINDOW_WEEKS` constant: `4` → `10`
- Fixed a hardcoded `timedelta(weeks=4)` that bypassed the constant
- Separated the fresh pin treatment window (stays at 4 weeks) from the topic dedup window (now 10 weeks) — these are different concepts that were previously conflated in the same variable
- Updated prompt template to reference "10 weeks" instead of "4 weeks"

#### Change 2: Targeted Topic Replacement

When only post-attributable violations are found (topic repetition, negative keyword on a specific post), the system now surgically replaces only the offending posts and their derived pins instead of regenerating the full plan.

**How it works:**

1. `validate_plan()` now returns structured violations with severity classification:
   - `"targeted"` — attributable to a specific post (topic repetition, negative keyword on a blog post)
   - `"structural"` — affects the whole plan (wrong pin count, pillar mix, board limits, etc.)

2. If only targeted violations exist:
   - `identify_replaceable_posts()` maps each offending post to its derived pins and their scheduled slots
   - A focused Claude call (`generate_replacement_posts()`) generates replacement posts/pins using a new prompt template that preserves all slot assignments (same `post_id`, `pin_id`, `scheduled_date`, `scheduled_slot`, `target_board`, `funnel_layer`)
   - `splice_replacements()` swaps the offending posts/pins in-place, keeping the rest of the plan untouched

3. Falls back to full regeneration when:
   - Any structural violations exist
   - More than 50% of posts need replacement (surgical approach not worth it)
   - Replacement returns wrong pin count
   - Exception during replacement call

**Cost impact for targeted replacement:**

| Scenario | Full regen (before) | Targeted (1 post, ~3 pins) |
|----------|--------------------|-----------------------------|
| API cost | ~$0.09-0.12 | ~$0.015-0.025 |
| Latency | ~15-25s | ~4-8s |

### Files Changed

| File | Change |
|------|--------|
| `src/generate_weekly_plan.py` | `TOPIC_REPETITION_WINDOW_WEEKS` 4→10, separated `topic_window_start` from `fresh_pin_window_start`, refactored `validate_plan()` to return structured violations, added `identify_replaceable_posts()`, `splice_replacements()`, `_extract_recent_topics()`, `violation_messages()`, rewrote retry loop with two-tier targeted/structural logic |
| `src/apis/claude_api.py` | Added `generate_replacement_posts()` method — loads replacement prompt template, formats context, calls Sonnet with dynamic max_tokens |
| `prompts/weekly_plan.md` | Updated "4 weeks" → "10 weeks" in topic dedup references (3 lines); left fresh pin treatment "4+ weeks" unchanged |
| `prompts/weekly_plan_replace.md` | **New** — Targeted replacement prompt template with constraints (recent topics, kept topics, negative keywords), exact pin slot assignments, and JSON output format matching the main plan schema |

### Status

Implemented, not yet tested in production. First live validation will occur during the next weekly plan generation cycle.

---

## Phase 4: Pre-Launch Pipeline Review & Critical Bug Fixes

**Date:** 2026-02-21

The automated pipeline triggers for the first time Monday 2/23. Five review agents traced every data path, trigger, field name, and failure mode across all 9 workflows, 12 Python scripts, and 13 prompt templates. This phase fixes the critical and medium bugs that would prevent the pipeline from working.

### Critical Bugs Fixed (3)

#### C1: Pin images not available on the posting runner

**Problem:** `.gitignore` excludes `*.png`, so rendered pin PNGs never reach git. The generation runner renders PNGs locally and commits only JSON metadata. `blog_deployer._create_pin_schedule()` wrote `image_path` (local path) but no `image_url`. On the posting runner (fresh checkout), `post_pins.py` tried `image_url` (missing) then `image_path` (file doesn't exist) → `FileNotFoundError`. Additionally, the stored `_drive_image_url` was a 400px thumbnail — far too small for Pinterest (needs 1000x1500+).

**Fix:** Store a full-resolution Google Drive download URL (`_drive_download_url`) alongside the thumbnail URL during publish. Use this for Pinterest posting while keeping the thumbnail for Sheet display.

| File | Change |
|------|--------|
| `src/publish_content_queue.py` | After storing `_drive_image_url`, extract file ID and store `_drive_download_url` (`https://drive.google.com/uc?id=FILE_ID&export=download`) |
| `src/blog_deployer.py` | Add `image_url` field to schedule_entry populated from `_drive_download_url` |
| `src/regen_content.py` | Store `_drive_download_url` after regen re-upload; add to `keys_to_update` list |

#### C2: Evening posting slot gets wrong date (UTC vs ET)

**Problem:** Evening cron (`0 1 * * *`) fires at 01:00 UTC = 8pm ET previous day. `post_pins.py` used `date.today()` which returns the UTC date. At 01:00 UTC Tuesday, `date.today()` = Tuesday, but evening pins are scheduled under Monday. Result: 50% of daily posting volume (2 evening pins) never fires.

**Fix:** Replace all `date.today()` calls with `datetime.now(ZoneInfo("America/New_York")).date()`. Added `tzdata` to `requirements.txt` as a safety net for runners without OS timezone data.

| File | Change |
|------|--------|
| `src/post_pins.py` | Import `ZoneInfo`, define `ET` constant, replace 3 `date.today()` calls in `post_pins()`, `apply_jitter()`, and `__main__` demo mode |
| `requirements.txt` | Add `tzdata>=2024.1` |

#### C3: Drive URLs not persisted to git (publish runs after commit)

**Problem:** In `generate-content.yml`, the commit step ran before the publish step. `publish_content_queue.py` writes `_drive_image_url` and `_drive_download_url` to `pin-generation-results.json`, but this happens after the commit+push. The updated file is never persisted.

**Fix:** Add a second commit step after the publish step.

| File | Change |
|------|--------|
| `.github/workflows/generate-content.yml` | Add "Commit Drive URLs and publish metadata" step after publish, with `[skip ci]` tag |

### Medium Bugs Fixed (6)

#### M1: `PINTEREST_ENVIRONMENT` vs `PINTEREST_ENV` env var name

All workflows set `PINTEREST_ENVIRONMENT: production` but `pinterest_api.py` read `PINTEREST_ENV`. Non-breaking (defaults to production) but would silently ignore sandbox mode.

**Fix:** Changed all references in `src/apis/pinterest_api.py` from `PINTEREST_ENV` to `PINTEREST_ENVIRONMENT` (code + docstrings).

#### M2: Missing fields in pin-schedule.json

`blog_deployer._create_pin_schedule()` omitted 8 fields that `post_pins.py` writes to `content-log.jsonl`. They were always empty, degrading analytics/memory quality.

**Fix:** Added `content_type`, `funnel_layer`, `secondary_keywords`, `template`, `treatment_number`, `source_post_id`, `image_source`, `image_id` to schedule_entry in `src/blog_deployer.py`.

#### M3: Copy-only regen doesn't flag when pin image is stale

When `regen_copy` succeeds but hero image is unavailable, the Sheet shows updated text but the thumbnail is stale. No indication to the reviewer.

**Fix:** Flag `_copy_regen_no_rerender` in `src/regen_content.py`. Warning appears in Sheet notes column and Slack notification via `src/apis/slack_notify.py`.

#### M4: Git push race condition between concurrent workflows

Pipeline workflows (`pinterest-pipeline` group) and posting workflows (`pinterest-posting` group) can run simultaneously. Both do `git add data/ && commit && push` — second push fails if behind HEAD.

**Fix:** Added `git pull --rebase` before `git push` in all commit steps across all 9 workflow files (10 commit steps total, including generate-content.yml's two).

#### M5: Regen workflow timeout too short

`regen-content.yml` had `timeout-minutes: 20`. Full-batch regen could take ~56 minutes.

**Fix:** Increased to `timeout-minutes: 45`.

#### M6: Evening posting workflow timeout too short

`daily-post-evening.yml` had `timeout-minutes: 30`. Worst-case jitter (15 min initial + 20 min inter-pin) = 35 min, exceeding the timeout.

**Fix:** Increased to `timeout-minutes: 45`.

### Files Changed (Summary)

| File | Bug(s) |
|------|--------|
| `src/publish_content_queue.py` | C1 |
| `src/blog_deployer.py` | C1, M2 |
| `src/post_pins.py` | C2 |
| `src/regen_content.py` | C1, M3 |
| `src/apis/pinterest_api.py` | M1 |
| `src/apis/slack_notify.py` | M3 |
| `requirements.txt` | C2 |
| `.github/workflows/generate-content.yml` | C3, M4 |
| `.github/workflows/daily-post-morning.yml` | M4 |
| `.github/workflows/daily-post-afternoon.yml` | M4 |
| `.github/workflows/daily-post-evening.yml` | M4, M6 |
| `.github/workflows/deploy-and-schedule.yml` | M4 |
| `.github/workflows/promote-and-schedule.yml` | M4 |
| `.github/workflows/weekly-review.yml` | M4 |
| `.github/workflows/monthly-review.yml` | M4 |
| `.github/workflows/regen-content.yml` | M4, M5 |

### Status

All 9 fixes implemented and verified by two rounds of automated code review (6 review agents total). End-to-end data flow traces confirmed correct handoffs for: happy-path posting, regen posting, and evening timezone handling.

---

## Phase 5: Deep Pre-Launch Audit & Critical Fixes

**Date:** 2026-02-22

A second, deeper code review before Monday launch. Five review agents examined every workflow, trigger, handoff, approval gate, and failure path. I then personally validated every finding against the actual source code, downgrading several false positives and identifying the correct root causes. Four implementation agents fixed the confirmed issues, and a Sr Staff Engineer agent reviewed all changes for correctness and workflow fit.

### Critical Bugs Fixed (3)

#### C4: Image prompt template variables not injected

**Problem:** `generate_image_prompt()` injected `{"PIN_SPEC": pin_spec, "IMAGE_SOURCE": image_source}` into the context dict, but the templates (`image_search.md`, `image_prompt.md`) use `{{pin_topic}}`, `{{content_type}}`, `{{primary_keyword}}`, `{{pin_template}}`, `{{pillar}}`. None matched — placeholders went unreplaced. Claude received no pin-specific information for image generation, producing generic images for every pin. Additionally, system messages said "Return only the prompt/query text" while templates said "Return valid JSON" — contradictory instructions.

**Fix:**
1. Changed context dict to inject individual fields matching template vars
2. Removed contradictory "Return only the prompt/query text" from system message (templates now control output format)
3. Added JSON parsing in callers (`_source_stock_image`, `_source_ai_image`) with graceful fallback to raw text

| File | Change |
|------|--------|
| `src/apis/claude_api.py` | Context dict keys now match template vars; removed contradictory system message |
| `src/generate_pin_content.py` | JSON parsing for stock image queries (`queries[0].query`) and AI image prompts (`image_prompt`) |

#### C7: Non-recipe pin templates render with empty text

**Problem:** `assemble_pin()` only passed `headline`, `subtitle`, `hero_image_url`. Non-recipe templates need many more variables — tip-pin needs `bullet_1-3`, listicle-pin needs `number`/`list_items`, problem-solution-pin needs `problem_text`/`solution_text`, infographic-pin needs `title`/`steps`/`footer_text`. All defaulted to empty string, so ~40-50% of pins rendered with blank text areas. Also, `text_overlay` from pin copy is a dict (`{headline, sub_text}`) but was being passed as a raw object to the headline parameter.

**Fix:**
1. Fixed `text_overlay` extraction to properly handle dict format
2. Added `extra_context` parameter to `assemble_pin()` for template-specific variables
3. New `_build_template_context()` function derives template-specific variables from pin copy data
4. Helper functions extract bullets, list items, steps, and leading numbers from description text

| File | Change |
|------|--------|
| `src/generate_pin_content.py` | `_build_template_context()` + 4 helpers, fixed text_overlay dict handling |
| `src/pin_assembler.py` | `assemble_pin()` accepts optional `extra_context` dict merged into render context |

#### C6: Fallback auto-approves everything if Sheets is down

**Problem:** If `read_content_approvals()` threw an exception, `_build_fallback_approvals()` marked ALL generated content as "approved" — including items the human explicitly rejected. This was a safety hole: a transient Sheets outage during deploy could silently publish rejected content.

**Fix:** All three fallback sites (`deploy_approved_content`, `deploy_to_preview`, `promote_to_production`) now send a Slack notification explaining the failure and re-raise the exception to halt the pipeline. `_build_fallback_approvals()` retained with a testing-only docstring.

| File | Change |
|------|--------|
| `src/blog_deployer.py` | 3 fallback-to-auto-approve blocks → Slack notification + raise; docstring warning on `_build_fallback_approvals()` |

### Medium Bugs Fixed (6)

#### C1+C2: Validation day names and slot underscore mismatches

**Problem:** `POSTING_DAYS` had day names (`"tuesday"`, etc.) but Claude produces YYYY-MM-DD dates. `TIME_SLOTS` used underscores (`"evening_1"`) but the prompt and posting code use hyphens. Sort key failed for dates; day distribution check always passed vacuously. This wasted 2 Claude retries per Monday run on structural violations that could never pass.

**Fix:** Changed `TIME_SLOTS` to hyphens, sort key uses date strings directly (YYYY-MM-DD sorts lexicographically), day distribution counts by date instead of day name.

| File | Change |
|------|--------|
| `src/generate_weekly_plan.py` | `TIME_SLOTS` hyphens, sort by date string, count distribution by date |

#### M1+M2: Hardcoded image/png MIME types

**Problem:** Pinterest API and Drive API hardcoded `image/png` for all uploads. After pin_assembler's JPEG optimization, actual images may be JPEG — causing MIME mismatch.

**Fix:** Pinterest API detects format from base64 magic bytes (JPEG/PNG/WebP). Drive API uses `mimetypes.guess_type()` from file extension.

| File | Change |
|------|--------|
| `src/apis/pinterest_api.py` | Magic byte detection for content_type |
| `src/apis/drive_api.py` | `mimetypes.guess_type()` for upload MIME type |

#### M9: Prompt says 4-week dedup, code enforces 10

**Fix:** Changed "4 weeks" to "10 weeks" in the prompt's FINAL CHECKLIST.

| File | Change |
|------|--------|
| `prompts/weekly_plan.md` | "4 weeks" → "10 weeks" in checklist |

#### M8: Regen deletes old image before uploading new

**Fix:** Swapped order: upload new image first, then delete old. If upload fails, old image remains intact.

| File | Change |
|------|--------|
| `src/regen_content.py` | Upload-then-delete order; delete by file ID, not name |

### Sr Staff Engineer Review

All 10 files reviewed. 9/10 approved on first pass. One blocking issue caught: a concurrency group rename (`pinterest-pipeline` → `deploy-and-schedule`) would have allowed `deploy-and-schedule.yml` and `promote-and-schedule.yml` to run concurrently, creating race conditions on shared state. Reverted to shared group. Two non-blocking observations addressed (redundant import, dead code).

### Status

All fixes implemented, compiled, and reviewed. Pipeline is ready for Monday 2/23 launch.

---

## Phase 5.1: Incremental Improvements & Fix Verification

**Date:** 2026-02-22

The Phase 5 agent errored out before confirming completion. A 6-agent review team (5 domain reviewers + 1 Sr Staff Engineer) audited all uncommitted changes against the fix plan. Verdict: **all plan items were implemented correctly**, and the uncommitted diff contains additional incremental improvements beyond the plan.

### Changes in This Diff (8 files, +45/-11 lines)

#### Replicate API endpoint fix (`src/apis/image_gen.py`)

**Problem:** Old code called `POST /v1/predictions` with `"version": "black-forest-labs/flux-pro"`. That endpoint requires a version SHA hash, not a model name — would fail at runtime.

**Fix:** Switched to model-based endpoint `POST /v1/models/black-forest-labs/flux-pro/predictions` which accepts model names directly. Removed the `version` field from the request body. Polling code unchanged (uses `/v1/predictions/{id}` which works regardless of creation endpoint).

#### UTM double-tagging fix (`src/generate_pin_content.py`)

**Problem:** `build_utm_link()` was called at content generation time, then `construct_utm_link()` in `post_pins.py` added UTMs again at posting time — double-tagging URLs.

**Fix:** Generation now produces bare URLs (`{BLOG_BASE_URL}/{blog_slug}`). UTM params are added only at posting time by `post_pins.py:construct_utm_link()`. The old `build_utm_link()` function is now dead code (cleanup candidate).

#### JPEG conversion path fix (`src/pin_assembler.py`)

**Problem:** After JPEG optimization, `jpeg_path.rename(image_path.with_suffix(".jpg"))` created a `.jpg` file, but all downstream references (pin data, content logs, posting code) still used the original `.png` path — causing `FileNotFoundError` at posting time. Logging also read the wrong file size (always 0).

**Fix:** Rename JPEG to the original `.png` path so downstream references remain valid. Updated logging to read the correct file size. Minor caveat: file bytes are JPEG but extension says `.png` — mitigated by Pinterest API's magic-byte detection (M1/M2 fix) and Chromium's content-sniffing in data URIs.

#### Prompt template enhancements (`prompts/pin_copy.md`, `prompts/weekly_plan.md`, `src/apis/claude_api.py`)

Added three new template variables for richer context:
- `{{brand_voice_details}}` — loaded from strategy files, gives Claude specific voice/tone guidance per pin
- `{{keyword_targets}}` — per-pillar keyword targets for SEO alignment
- `{{negative_keywords}}` — dynamic negative keyword list from analytics (weekly plan prompt)

Context dicts in `claude_api.py` inject matching values for all three.

#### Regen template context fix (`src/regen_content.py`)

Extended the C7 fix (non-recipe templates get empty text) to the regen path. Now imports `build_template_context` from `generate_pin_content.py`, builds template-specific context for all 5 template types, and passes `extra_context` to `assemble_pin()`. Also properly extracts headline/subtitle from `text_overlay` dict format.

#### Content log `posted_date` field (`src/blog_deployer.py`)

Added `"posted_date": today_str` to content log entries. `weekly_analysis.py` filters on this field — previously missing, which could cause analytics gaps.

### Status

All changes verified by 6-agent review team. Committed as `d2f2342`.

---

## Phase 5.2: Code Hygiene Cleanup

**Date:** 2026-02-22

Addressed the 4 minor items identified during the Phase 5.1 review. All are non-functional cleanup — no behavior changes, just dead code removal and convention fixes.

### Changes

#### 1. Delete `_build_fallback_approvals()` (`src/blog_deployer.py`, -46 lines)

**Problem:** The function auto-approved ALL content (including explicitly rejected items). Its 3 callers were already changed to raise instead of calling it, but the function itself remained — a footgun for future developers.

**Fix:** Deleted entirely. Zero callers confirmed by grep. Function is preserved in git history if ever needed for local testing.

#### 2. Remove dead `build_utm_link()` (`src/generate_pin_content.py`, -33 lines)

**Problem:** No longer called after UTM params were deferred to posting time (`post_pins.py:construct_utm_link()`). Dead code.

**Fix:** Deleted function and its `quote_plus` import (also unused after removal).

#### 3. Magic-byte MIME detection in Drive uploads (`src/apis/drive_api.py`, +8 lines net)

**Problem:** `upload_image()` used `mimetypes.guess_type()` which trusts file extension. After `pin_assembler.py`'s JPEG optimization, files may be JPEG with `.png` extension — causing MIME mismatch on Drive uploads.

**Fix:** Replaced with magic-byte detection (same pattern as `pinterest_api.py`): reads first 12 bytes, detects JPEG (`\xff\xd8`), PNG (`\x89PNG`), WebP (`RIFF...WEBP`), falls back to `image/png`. Removed unused `import mimetypes`.

#### 4. Rename `_build_template_context` → `build_template_context` (`src/generate_pin_content.py`, `src/regen_content.py`)

**Problem:** `regen_content.py` imported a `_`-prefixed (private by convention) function cross-module.

**Fix:** Dropped the underscore prefix since the function is intentionally part of the public API. Updated definition (line 537), internal call (line 163), import (regen line 35), and usage (regen line 425).

### Files Changed

| File | Change |
|------|--------|
| `src/blog_deployer.py` | Deleted `_build_fallback_approvals()` |
| `src/generate_pin_content.py` | Deleted `build_utm_link()` + `quote_plus` import; renamed `_build_template_context` → `build_template_context` |
| `src/regen_content.py` | Updated import and usage of `build_template_context` |
| `src/apis/drive_api.py` | Replaced `mimetypes.guess_type()` with magic-byte detection; removed `import mimetypes` |

### Status

All 4 items implemented. Net -76 lines. Committed as `9d8ad11`.

---

## Phase 6: Final Pre-Launch Review & Fixes

**Date:** 2026-02-22

A 5-agent review team (4 domain reviewers + 1 Sr Staff Engineer) performed a comprehensive pre-launch audit of the entire pipeline. Four parallel reviewers covered: (1) GitHub Actions workflows & triggers, (2) data flow & field handoffs across all 10 pipeline steps, (3) all API integrations & prompt templates, (4) regen flows, error paths & edge cases. The Sr Staff Engineer then verified every finding against actual source code, filtering false positives.

### Review Results

**0 launch blockers found.** The most alarming finding — a schedule format mismatch in `sheets_api.py` initially flagged as a launch blocker — was downgraded after the Sr Staff Engineer traced the actual posting path and confirmed it reads from `pin-schedule.json` (separate fields), not the Sheet method with the mismatch.

**Verified correct across all reviewers:**
- All 5 pin template types get correct context variables
- Full posting path: pin-schedule.json → board resolution → UTM construction → Pinterest API
- Regen flow: feedback injection, image re-sourcing, upload-then-delete, Sheet update
- Drive image handling: thumbnail vs full-res URLs, magic byte MIME detection
- Blog deployment: batch commit, two-phase preview/production deploy
- All 9 GitHub Actions workflows: cron schedules, triggers, concurrency groups, git pull --rebase
- Error handling: retry logic, rate limit backoff, token refresh, failure notifications
- Approval gates: plan, content, production, regen blocking

### Pre-Launch Fixes (3)

#### Fix 1: `generate-content.yml` timeout too short

**Problem:** Content generation workflow had `timeout-minutes: 30`. With 28 pins requiring Claude API calls (search queries, stock ranking, AI validation), image downloads, Puppeteer rendering, and Drive uploads, worst-case execution could approach or exceed 30 minutes. The `regen-content.yml` already used 45 minutes for a subset of this work.

**Fix:** Increased to `timeout-minutes: 45`.

| File | Change |
|------|--------|
| `.github/workflows/generate-content.yml` | `timeout-minutes: 30` → `45` |

#### Fix 2: Weekly analysis template placeholders don't match context dict

**Problem:** `analyze_weekly_performance()` in `claude_api.py` passed 3 context keys (`PERFORMANCE_DATA`, `PREVIOUS_ANALYSIS`, `CONTENT_PLAN`) but the `weekly_analysis.md` template uses 8 different placeholders (`this_week_data`, `last_week_analysis`, `content_plan_vs_actual`, `per_pillar_metrics`, `per_keyword_metrics`, `per_board_metrics`, `per_funnel_layer_metrics`, `account_trends`). None matched — all placeholders went unreplaced. Claude would receive the template structure but no actual performance data, producing a generic analysis with no real numbers.

**Fix:** Replaced the 3 mismatched keys with 8 keys matching the template placeholders. Each key maps to the correct slice of the `build_analysis_context()` return value:
- `this_week_data` → week_summary, top/bottom pins, per-type/template/image-source/pin-type breakdowns
- `last_week_analysis` → previous analysis text (with first-run fallback)
- `content_plan_vs_actual` → content plan dict (with fallback)
- `per_pillar_metrics` → `by_pillar` aggregate
- `per_keyword_metrics` → `by_keyword` aggregate
- `per_board_metrics` → `by_board` aggregate
- `per_funnel_layer_metrics` → `by_funnel_layer` aggregate
- `account_trends` → this week vs last week vs 4-week rolling average

| File | Change |
|------|--------|
| `src/apis/claude_api.py` | Context dict in `analyze_weekly_performance()`: 3 mismatched keys → 8 keys matching template placeholders |

#### Fix 3: Schedule format mismatch in Content Queue

**Problem:** `write_content_queue()` wrote the schedule column as `"2026-02-24 / morning"` (spaces around slash), but `get_approved_pins_for_slot()` compared against `"2026-02-24/morning"` (no spaces). These would never match. The actual posting path reads from `pin-schedule.json` (not the Sheet), so this didn't block posting — but the inconsistency would cause `get_approved_pins_for_slot()` to return zero results if ever called.

**Fix:** Changed write format to `"date/slot"` (no spaces) to match the read format.

| File | Change |
|------|--------|
| `src/apis/sheets_api.py` | `write_content_queue()` schedule format: `" / "` → `"/"` |

### Known Issues (not blocking launch)

1. **Monthly review template placeholder mismatch** — Same pattern as Fix 2, affects `run_monthly_review()` context dict vs `monthly_review.md` template. First monthly review runs March 2. Fix before then.
2. **Vision MIME detection uses file extension** — `claude_api.py` line 878 uses file extension instead of magic bytes for the file-path branch. Masked by fallback score of 7.0. Low practical impact.
3. **Missing `REPLICATE_API_TOKEN`** in workflow env blocks — Only matters if image generation is switched from OpenAI to Replicate.
4. **DST cron drift** — All cron jobs shift 1 hour later during EDT (March–November). Cosmetic, not a failure.

### Status

All 3 fixes implemented and verified by Sr Staff Engineer. Pipeline is ready for Monday 2/23 launch.

---

## Phase 7: Content Queue Thumbnail Fixes + GCS Migration

**Date:** 2026-02-23

### Problem

First live content generation run completed successfully (10 blog posts, 28 pins). The Google Sheets Content Queue has two image issues:

1. **Pin thumbnails show raw local paths** — Column I displays `/home/runner/work/.../W8-19.png` as plain text instead of rendered inline images
2. **Blog thumbnails are empty** — Column I is blank for all blog rows; blog hero image thumbnails were never implemented

### Root Cause (Confirmed)

Google Drive upload fails for ALL 28 pin images with:

```
HttpError 403: "Service Accounts do not have storage quota.
Leverage shared drives or use OAuth delegation instead."
Reason: storageQuotaExceeded
```

The service account (`pinterest-pipeline-sheets@pinterest-pipeline-488017.iam.gserviceaccount.com`) is in a GCP project under a personal Gmail account (`braden.pan@gmail.com`). Service accounts on personal Gmail get zero Drive storage quota because Google Drive is a per-user consumer product. The code falls back to writing useless local runner paths.

### Solution: Replace Google Drive with Google Cloud Storage (GCS)

Six alternatives were researched and evaluated:

| Option | Verdict |
|--------|---------|
| 1. Shared Drives (Workspace) | Blocked — requires Workspace admin to add external SA |
| 2. OAuth Delegation | Security anti-pattern — Google recommends against it |
| **3. Google Cloud Storage** | **Selected — no new credentials, $0/month, same GCP project** |
| 4. Move SA to Workspace | Overkill — high migration effort for same result |
| 5. Cloudflare R2 | Good but requires 3 new secrets + new vendor |
| 6. Deploy to goslated.com | Git repo bloat from binary images over time |

**Why GCS works where Drive doesn't:** GCS is a GCP infrastructure service — storage is billed to the project's billing account, not to any user's personal quota. The service account just needs IAM permissions on the bucket. No storage quota concept.

**Cost analysis:** At ~38 images/week (~14MB rotating), all usage is well within GCS Always Free tier:
- Storage: <1 GB used vs 5 GB free (even after 2 years of blog hero accumulation)
- Class A ops: ~325/mo vs 5,000 free
- Class B ops: ~1,780/mo vs 50,000 free
- Egress: ~0.5 GB/mo vs 100 GB free
- **Total: $0.00/month**

### GCP Setup (Manual, One-Time)

Completed under `braden.pan@gmail.com`, project `pinterest-pipeline-488017`:

1. Enabled Cloud Storage JSON API
2. Created bucket `slated-pipeline-pins` (us-central1, Standard, Uniform access)
3. Granted service account `roles/storage.objectAdmin` in IAM
4. Granted `allUsers` → `roles/storage.objectViewer` on bucket (required for Sheets `=IMAGE()`)

No new GitHub secrets needed — GCS reuses `GOOGLE_SHEETS_CREDENTIALS_JSON`.

### Additional Bug Fixed: Hero Image Naming Mismatch

- `generate_pin_content.py` saves hero images as `{pin_id}-hero.{ext}` (e.g., `W8-01-hero.jpg`)
- `blog_deployer.py` looks for `{slug}-hero.{ext}` (e.g., `one-pan-lemon-herb-chicken-hero.jpg`)
- **Fix:** After downloading, `generate_pin_content.py` now also saves a copy as `{slug}-hero.{ext}` via `shutil.copy2`. Dual-save was chosen over updating `blog_deployer.py` because the deployer's slug-based lookup is correct by convention — it's the generation step that was missing the slug-named copy.

### Additional Fix: Monthly Review Template Context

Same pattern as the Phase 6 weekly analysis template fix — `run_monthly_review()` passed 3 mismatched context keys but the `monthly_review.md` template uses different placeholder names. All template variables now correctly mapped. Also added seasonal context loading.

### Files Changed

| File | Change |
|------|--------|
| `src/apis/gcs_api.py` | **New** — GCS client class. Upload, download, batch upload (pins + blog heroes), delete, public URL generation. Auth via `GOOGLE_SHEETS_CREDENTIALS_JSON` (same SA). Graceful degradation when credentials/library missing (`self.client = None`). Fallback from pyca to python-rsa signer for environments where `cryptography` rejects non-standard key parameters. |
| `src/publish_content_queue.py` | GCS-first with Drive fallback. `publish()` tries GCS for pin images and blog hero images; falls back to Drive if GCS unavailable. Both `_drive_image_url` and `_drive_download_url` fields store GCS public URLs (field names preserved for downstream compatibility). Blog hero upload function added. |
| `src/regen_content.py` | GCS integration in regen path. Hero image download detects GCS URLs (`storage.googleapis.com`) vs Drive URLs and downloads accordingly. Replacement image upload uses GCS-first, Drive fallback. |
| `src/apis/sheets_api.py` | Pin thumbnail fallback: empty string instead of local runner path. Blog thumbnail support: `blog_image_urls` parameter writes `=IMAGE()` formulas for blog rows. Schedule format fix: `" / "` → `"/"` to match read format. |
| `src/generate_pin_content.py` | Hero image dual-save (`{pin_id}-hero` + `{slug}-hero`). |
| `src/apis/claude_api.py` | Monthly review template context: 3 mismatched keys → correct keys matching `monthly_review.md` placeholders. Added `seasonal_context` parameter. |
| `src/monthly_review.py` | Seasonal context loader (`_load_seasonal_context`) — reads seasonal calendar, finds current window, passes to Claude for seasonal awareness. |
| `.github/workflows/monthly-review.yml` | Cron guard for first-Monday-only execution (POSIX cron OR limitation). Separate concurrency group `pinterest-monthly`. Conditional steps gated on guard output. |
| `.github/workflows/generate-content.yml` | Updated commit step comment from "Drive" to "GCS". |
| `requirements.txt` | Added `google-cloud-storage>=2.14.0`. |

### Code Review (Sr Staff Engineer)

Two rounds of review (Phase 7 code + GCS implementation):

**Phase 7 code review:** APPROVE, 0 blocking issues. 4 non-blocking findings (import placement, hardcoded `.jpg` extension, blog row height assumption, seasonal loader DRY). All addressed or accepted.

**GCS implementation review:** APPROVE, 0 blocking regressions. End-to-end URL flow traced through all 9 steps (GCS upload → pin-generation-results.json → blog_deployer → pin-schedule.json → post_pins → Pinterest API) — all correct. 3 non-blocking findings (pre-existing regen Drive fallback bug, docstring wording, hardcoded extension). Docstring and extension fixes applied.

### Smoke Test

Local smoke test verified full round trip:
1. GCS client initialized with service account credentials
2. Test image uploaded to `slated-pipeline-pins` bucket
3. Public URL accessible (HTTP 200)
4. Cleanup (delete) successful

### Known Issue: Private Key Compatibility

The service account's private key has non-standard CRT coefficients. The `cryptography` library (pyca backend) on Python 3.13/Windows rejects it with "Invalid private key". The `python-rsa` library accepts it (with a warning). `gcs_api.py` includes a fallback: if pyca fails with `ValueError`, it falls back to `python-rsa` signer. This won't affect GitHub Actions (Ubuntu, different Python/cryptography versions).

### Status

All changes implemented, reviewed, and locally tested. Ready for commit and first live pipeline run.

---

## Phase 7.1: Bug Fixes (Pre-existing Issues Found During Pipeline Audit)

Five bugs identified during the Phase 7 full pipeline review. All fixed.

### Bug 1: Analytics Double-Counting (content-log.jsonl)

**Problem:** `blog_deployer._append_to_content_log()` writes placeholder entries (pin_id=None, all metrics=0) before pins are posted. `post_pins.py` later writes the real entries (with pin_id and pinterest_pin_id). Both coexist in content-log.jsonl permanently. `weekly_analysis.py` and `monthly_review.py` were including the placeholder entries in metric aggregations, inflating pin counts and diluting averages.

**Root cause:** The placeholders exist intentionally — they let the planning system know what content is in the pipeline before pins post. But the analytics code didn't distinguish them from real posted entries.

**Fix:** Added `and e.get("pin_id")` filter to all metric aggregation entry lists in `weekly_analysis.py` and `monthly_review.py`. The `generate_content_memory_summary()` function is intentionally left unfiltered so the planning system still sees pipeline content for topic/keyword dedup.

**Files changed:** `src/weekly_analysis.py`, `src/monthly_review.py`

### Bug 2: Image Dedup Date Field Mismatch

**Problem:** `generate_pin_content.py:load_used_image_ids()` read `entry.get("date")` from content-log.jsonl, but `post_pins.py` writes `posted_date` (not `date`). Only blog_deployer writes the `date` field. Result: image dedup was only checking blog_deployer placeholder entries, missing all real posted-pin entries.

**Fix:** Changed to `entry.get("posted_date", entry.get("date", ""))` to check both fields.

**File changed:** `src/generate_pin_content.py`

### Bug 3: Regen Feedback Dropped in Stock Image Retry

**Problem:** When stock image search gets low-quality results and retries with broader queries, the retry call to `claude.generate_image_prompt()` was missing the `regen_feedback` parameter. If a reviewer requested a regen with specific feedback (e.g., "no close-up hands"), the retry search wouldn't incorporate that feedback.

**Fix:** Added `regen_feedback=regen_feedback` to the retry call.

**File changed:** `src/generate_pin_content.py`

### Bug 4: Copy Regen Failure Silently Swallowed

**Problem:** In `regen_content.py`, if copy regeneration fails (Claude API error, etc.), the exception was caught and logged but the function returned the old copy as if it were new. The caller cleared the reviewer's feedback and set status to `pending_review` — making it look like regen succeeded when it didn't.

**Fix:** Added `_copy_regen_failed` flag (following existing `_copy_regen_no_rerender` pattern). When set, the caller preserves the reviewer's feedback for retry and adds a warning note to the Sheet.

**File changed:** `src/regen_content.py`

### Bug 5: 28-Pin Skip Window Mismatch

**Problem:** `generate_weekly_plan.py` creates exactly 28 pins (4/day x 7 days, validated by Check 7). But `post_pins.py:should_skip_window()` skipped 1 random posting window per week. If evening was skipped, 2 pins were lost; otherwise 1. Skipped pins were never retried or rescheduled — they silently never posted. Over a year, 52-104 pins wasted.

**Fix:** Removed `should_skip_window()` entirely. The existing anti-bot jitter (0-90 min initial delay, 5-20 min between pins, seeded from date+slot) provides sufficient anti-pattern behavior without sacrificing content.

**File changed:** `src/post_pins.py`

### Code Review (Sr Staff Engineer)

All 5 fixes reviewed and approved. One cosmetic finding (docstring step numbering in post_pins.py after removing step 2) — fixed. No blocking issues. Key verification points:
- Bug 1: All 6 aggregation list comprehensions across 2 files are filtered; content memory intentionally left unfiltered for planning
- Bug 2: Fallback chain handles both `posted_date` (post_pins) and `date` (blog_deployer) fields
- Bug 3: `regen_feedback=""` default means non-regen calls are unaffected
- Bug 4: `_copy_regen_failed` flag is transient (not persisted to pin-generation-results.json)
- Bug 5: No orphaned references; `hashlib` and `random` imports still used by jitter logic

### Status

All 5 bug fixes implemented, reviewed, and ready for commit.

---

## Phase 8: Blog Image Regen Support + Regen Quality Investigation

**Date:** 2026-02-24

### Problem

During W9 content review, 21 regen requests were submitted (6 blog, 15 pin):

- **6 blog rows** (W9-P03, P04, P06, P08, P09, P10) — all rejected by the hard block in `regen_content.py:108-128`. Feedback like "this is a picture of vegetables, not mac and cheese" was ignored. Blog rows got reset to `pending_review` with "Blog regen not supported" — blocking reviewers from fixing bad hero images.
- **15 pin rows** — all succeeded (new images sourced, rendered, uploaded to GCS, sheet updated). But some regenerated images were **worse** than the originals because of quality gaps in the selection process.

Three changes needed:
1. **Add blog image regen support** (the main blocker — implemented)
2. **Improve regen image quality** (planned, not yet implemented)
3. **Store image prompts for debugging** (planned, not yet implemented)

### Why the Hardblock Existed

The block was introduced in commit `b7572cb` (2026-02-22) alongside the initial regen feature. It was **deliberately technical**, not "not yet implemented":

1. **Blog copy lives in MDX files** — pin copy is just JSON metadata, but blog text is persisted as `.mdx` on disk. The generic pin regen workflow couldn't handle blog text regeneration.
2. **Hero images need slug-based filenames** — `blog_deployer.py` searches for heroes at `{slug}-hero{ext}`, not by pin_id. The pin regen path saves images by pin_id, which the deployer wouldn't find.
3. **No downstream breakage risk** — the block wasn't protecting a fragile dependency. It was that the blog regen path needed custom handling (slug-based naming, raw photo upload instead of rendered pin).

### Change 1: Blog Image Regen (Implemented)

**File: `src/regen_content.py`**

Added full blog image regen support:

- **Load blog results** — `blog-generation-results.json` loaded alongside pin results, with a `blog_results_dirty` flag for conditional save
- **Blog regen routing** — replaced the hard block with routing logic:
  - `regen_copy` → rejected with clear message (blog text is MDX, not regenerable via this workflow)
  - `regen` (both) → treated as `regen_image` with a note that copy regen isn't supported
  - `regen_image` → calls new `_regen_blog_image()` function
- **New `_regen_blog_image()` function:**
  1. Builds pin_spec from blog_data (title, content_type, pillar, feedback)
  2. Calls existing `source_image()` — reuses the stock/AI image sourcing pipeline
  3. Saves hero with slug name (`{slug}-hero{ext}`) for `blog_deployer.py` compatibility
  4. Uploads **raw hero photo** to GCS with timestamped name for cache-busting (`{post_id}-hero-{ts}{ext}`)
  5. Key difference from pin regen: no Puppeteer rendering step — blog heroes are raw stock/AI photos, not rendered pins
- **Blog results save** — updated entries saved back to `blog-generation-results.json` after the regen loop

**Scoping verification:** Blog regen is scoped to the single flagged blog — `blog_data = blog_results.get(item_id)` gets only that entry, all mutations apply only to that entry, hero images use unique slug-based filenames, GCS uploads use unique `{post_id}-hero-{timestamp}` names. No cross-contamination possible.

### Change 1B: Apps Script Button Fix

**File: `src/apps-script/trigger.gs`**

The `runRegen()` button function only set `N1="run"`. But `setValue()` from Apps Script does NOT fire installable onEdit triggers — only user edits do. So clicking the "Run Regen" button set the cell value but never dispatched the GitHub workflow.

**Fix:** Added explicit `triggerGitHubWorkflow("regen-content")` call to `runRegen()`.

### Changes 2 & 3: Planned (Not Yet Implemented)

Detailed plans saved in `troubleshooting/regen-quality-improvements.md`. Root cause investigation found:

**Regen image quality issues (Change 2):**
- **Problem A:** Only the first of 3-5 Claude-generated search queries is used during regen. More queries = more candidates = better chance of finding a match.
- **Problem B:** Regen feedback is buried in a raw JSON dump in the ranking prompt. The `image_rank.md` template has no mention of regen feedback. Claude Haiku scores purely on visual match, ignoring why the previous image was rejected.
- **Problem C:** Claude Haiku misidentifies food subjects at thumbnail resolution (gave 8.0/10 to "lemon and vegetables in a bowl" for a lemon herb chicken pin).

**Prompt storage (Change 3):**
- Search queries and AI image prompts are never stored — only the image_id. Makes it impossible to debug why a search returned poor results or compare prompts across regens.

### Code Review (Sr Staff Engineer)

**Verdict: Ship it.** No critical bugs. API call signatures verified correct against `source_image()`, `gcs.upload_image()`, `sheets.update_content_row()`, and `blog_deployer.py` hero image discovery. All edge cases handled (missing blog data, missing slug, source_image failure, GCS unavailable). Blog results save logic correctly gated behind dirty flag.

Low-severity warnings noted:
- First blog regen defaults to stock sourcing (no `_hero_image_source` in original data) — safe fallback
- No old GCS object cleanup (pin path does this) — negligible storage cost
- If GCS unavailable, regen appears to succeed but thumbnail won't update

### Files Changed

| File | Change |
|------|--------|
| `src/regen_content.py` | Blog regen routing, `_regen_blog_image()` function, blog results load/save |
| `src/apps-script/trigger.gs` | `runRegen()` now directly dispatches workflow |
| `troubleshooting/regen-quality-improvements.md` | **New** — Detailed plans for Changes 2 & 3 |

### Status

Change 1 implemented and reviewed. Changes 2 & 3 planned and documented, pending review.

---

## Image Quality Improvement — Side-by-Side AI Comparison (2026-02-24)

### Problem

~55% of generated pins were rejected in the last batch. Root causes:
1. Wrong food subjects in stock images (e.g., pasta photo for a chicken recipe)
2. Broken scoring — images score 8-9 but are actually bad (Claude Haiku misidentifies food at thumbnail resolution)
3. Expensive AI generation ($0.25/image due to gpt-image-1 at high quality + portrait)
4. No way to compare stock vs AI side-by-side before approving

### Solution

Nine coordinated changes across the pipeline:

1. **Cost reduction:** Switch from gpt-image-1 ($0.08-0.25) to gpt-image-1.5 medium ($0.05/image)
2. **Always-on AI comparison:** For every Tier 1/2 pin, generate an AI image alongside the stock search winner — both appear in the Content Queue for side-by-side review
3. **Better image targeting:** Use alt_text visual descriptions as subject hints for both stock search queries and AI image prompts
4. **New sheet column:** Column M ("AI Image") shows the AI alternative thumbnail next to the stock winner in column I
5. **New approval status:** `use_ai_image` — reviewer can pick the AI image instead of stock, triggering automatic swap during promotion
6. **Apps Script update:** `use_ai_image` treated as terminal status (alongside approved/rejected) so deploy-to-preview fires correctly. Regen trigger shifted from N1/col14 to O1/col15 since column M is now AI Image
7. **Regen feedback in validation:** `image_validate.md` prompt now explicitly checks whether regen feedback was addressed, penalizing repeated failures
8. **GCS upload methods:** New `upload_ai_hero_images()` and `upload_single_image()` for AI hero image storage
9. **AI image swap on promote:** When a pin has `use_ai_image` status, `blog_deployer.py` downloads the AI hero, re-renders the pin template with it, uploads to GCS, and updates pin-generation-results.json

### Column Layout Change

The Content Queue sheet column layout changed:

| Column | Before | After |
|--------|--------|-------|
| A-L | ID through Feedback | Same (unchanged) |
| M | Regen label ("Regen →") | **AI Image** (new) |
| N | Regen trigger value | Regen label ("Regen →") |
| O | — | Regen trigger value |

**This requires updating the Apps Script in your Google Sheet** (see below).

### Content Queue Statuses

Pins in column J now support these statuses:
- `pending_review` — Not yet reviewed
- `approved` — Use the stock/current image as-is
- `use_ai_image` — Swap in the AI image from column M before deploying
- `rejected` — Don't publish this pin
- `regen_image` / `regen_copy` — Request regeneration (with feedback in column L)

All three (`approved`, `rejected`, `use_ai_image`) are terminal — once all rows are terminal, the deploy-to-preview workflow fires.

### Files Changed

| File | Change |
|------|--------|
| `src/apis/image_gen.py` | Model → gpt-image-1.5, quality → medium, cost → $0.05 |
| `src/generate_pin_content.py` | Always-gen AI image for Tier 1/2, alt_text injection, `_ai_hero_image_path`/`_ai_image_id`/`_ai_image_score` in pin_data, `filename_prefix` param on `_source_ai_image` |
| `src/apis/claude_api.py` | `_image_subject_hint` appended to image prompt system message |
| `src/apis/sheets_api.py` | `CQ_COL_AI_IMAGE=12`, header includes "AI Image", `write_content_queue` accepts `ai_image_urls`, `update_content_row` accepts `ai_image`, regen trigger N1→O1, read ranges A:L→A:M |
| `src/apis/gcs_api.py` | `upload_ai_hero_images()` + `upload_single_image()` methods |
| `src/publish_content_queue.py` | Upload AI heroes to GCS, pass `ai_image_urls` to sheet write, save `_ai_image_url` to pin results JSON, regen trigger cells M1:N1→N1:O1 |
| `src/blog_deployer.py` | `use_ai_image` in all approved pin filters (deploy_approved, deploy_to_preview, promote), `_process_ai_image_swaps()` method |
| `src/apps-script/trigger.gs` | `use_ai_image` in terminal statuses, regen trigger col 14→15, `runRegen()` N1→O1 |
| `prompts/image_validate.md` | Regen-specific validation section (penalize repeated failures, check feedback addressed) |

### Code Review Fixes (2026-02-24)

Two independent Sr Staff Engineer code reviews identified 2 critical, 1 medium, and 2 minor issues. All fixed:

| Fix | Severity | File | What |
|-----|----------|------|------|
| C1 | Critical | `.github/workflows/promote-and-schedule.yml` | Added Node.js 22 + Puppeteer install steps + `GCS_BUCKET_NAME` env var. Without this, `_process_ai_image_swaps()` silently fails because PinAssembler needs Puppeteer to render HTML→PNG. |
| C2 | Critical | `src/blog_deployer.py` | Added Slack warning when `use_ai_image` pin has no AI URL available. Previously skipped silently — user would never know the swap didn't happen. |
| MEDIUM-1 | Medium | `src/generate_pin_content.py` | Regen filename changed from `{pin_id}-hero-regen.png` to `{prefix}-regen.png`. Prevents filename collision between stock-flow and AI-flow regens. |
| MEDIUM-2 | Minor | `src/apis/sheets_api.py` | Added `ai_image` param to `update_content_row()` docstring. |
| M3 | Minor | `src/apis/sheets_api.py` | `read_content_approvals()` logging now counts `use_ai_image` in approved total. |

### Regen AI Comparison Fix (2026-02-24)

Regen was calling `source_image()` (simple tier router, no AI comparison) instead of generating AI alongside stock. Fixed `src/regen_content.py`:
- Import `_source_ai_image` from generate_pin_content
- After primary image sourcing in `_regen_item()`, generate AI comparison image for Tier 1/2 pins via `_source_ai_image()`
- Upload AI comparison to GCS and write `=IMAGE()` formula to column M via `update_content_row(ai_image=...)`
- Persist `_ai_hero_image_path`, `_ai_image_id`, `_ai_image_score`, `_ai_image_url` in `_update_pin_results()`

### Status

All 9 original changes + 5 review fixes + regen AI comparison fix implemented and verified.

---

## Phase 8.1: Blog AI Comparison Images + Regen Crash Fix

**Date:** 2026-02-24

### Problem

The regen-content workflow crashed mid-cycle with:
```
NameError: name 'pin_id' is not defined (line 355)
```

The crash was caused by a variable name error (`pin_id` instead of `item_id`) in the AI hero upload section of `regen()`. This code was added in the regen AI comparison fix above but used the wrong variable name in the outer `regen()` scope.

Beyond the crash, a full audit revealed that **blog posts never receive AI comparison images** — neither during initial content generation nor during regen. The user requirement is that both pins AND blog posts always show AI comparison images in column M of the Content Queue.

### Root Cause Analysis

Three gaps identified:

1. **Crash bug (line 355):** `pin_id` referenced in `regen()` function scope where only `item_id` exists. Already fixed on disk but not committed/pushed to GitHub.

2. **Blog AI images missing in initial publish:** `sheets_api.py:write_content_queue()` hardcoded `""` for blog rows' AI Image column. Blog hero images come from the first associated pin's hero image — that pin already has an AI comparison image, but it was never mapped to the blog row.

3. **Blog AI images missing in regen:** `_regen_blog_image()` sourced new hero images but never called `_source_ai_image()` to generate an AI comparison. The `regen()` blog section never wrote to column M.

### Fix 1: Crash bug (already on disk)

Lines 350 and 355 of `regen_content.py` had `pin_id` changed to `item_id` in a previous session. Just needed committing.

### Fix 2: Blog AI comparison in regen path

**File: `src/regen_content.py`**

**A) `_regen_blog_image()` — AI comparison generation after hero sourcing:**
- Added `ai_image_url` field to result dict (initialized to `None`)
- After hero image sourcing + slug copy + used_image_ids tracking, added AI comparison block:
  - If winner is NOT `ai_generated`: calls `_source_ai_image()` with `{post_id}-ai-hero` prefix, uploads to GCS as `ai-heroes/{post_id}-ai-hero.png`, stores URL in `result["ai_image_url"]`
  - If winner IS `ai_generated`: the hero image upload below will provide the URL (handled in caller)
  - All AI generation is non-fatal — wrapped in try/except with warning log

**B) `regen()` blog section — column M write:**
- After building `update_kwargs`, reads `ai_image_url` from `blog_result`
- If present, writes `=IMAGE("{ai_url}")` to column M via `update_kwargs["ai_image"]`
- Special case: if image_source is `ai_generated` (winner IS AI), writes the hero URL to column M too

### Fix 3: Blog AI comparison in initial publish path

**File: `src/publish_content_queue.py`**
- After uploading pin AI hero images, builds `blog_ai_image_urls` mapping by looking up each blog post's first associated pin (via `source_post_id`) and using that pin's AI image URL
- Passes `blog_ai_image_urls` to `sheets.write_content_queue()`

**File: `src/apis/sheets_api.py`**
- `write_content_queue()` accepts new `blog_ai_image_urls` parameter
- Blog row AI Image column (previously hardcoded `""`) now writes `=IMAGE("{url}")` if a mapping exists for the post_id

### Fix 4: Dead code cleanup

**File: `src/regen_content.py` line 530**
- Changed `image_tier in ("stock", "Tier 1")` to `image_tier == "stock"` — `"Tier 1"` was dead code since `image_tier` is normalized to `"stock"` or `"ai"` at lines 497-503

### Files Changed

| File | Change |
|------|--------|
| `src/regen_content.py` | AI comparison in `_regen_blog_image()`, column M write in blog regen section, dead code cleanup |
| `src/publish_content_queue.py` | Build blog→AI image mapping from first associated pin, pass to sheets |
| `src/apis/sheets_api.py` | Accept `blog_ai_image_urls` param, write to column M for blog rows |

### Status

All fixes implemented and compiled. Pending review.

---

## Phase 8.2: Blog Hero Images Missing/Stale on Deploy

**Date:** 2026-02-24

### Problem

Deploy-to-preview committed wrong blog hero images to goslated.com. Two root causes:

1. **4 blog images missing entirely** — `*.png` in `.gitignore` (line 37) blocked all PNGs from git. Hero images saved as `.png` were silently excluded by `git add data/`.
2. **Remaining blog images used originals instead of regenerated versions** — When regen produces a `.png` but the original was `.jpg`, both coexist on disk. `blog_deployer.py` iterates extensions in order `[".jpg", ".jpeg", ".png", ".webp"]` and finds the stale `.jpg` first, ignoring the regenerated `.png`.

**Pipeline flow:** generate → commit → regen → commit → deploy (checks out git, finds files on disk). If the correct files are in git, deploy works. No need for fallback download logic.

### Fix 1: `.gitignore` — Allow hero image PNGs

Lines 38-39 already added in a previous session (on disk, not yet committed):
```
!data/generated/pins/*-hero.png
!data/generated/blog/*.png
```
These negation rules un-ignore hero PNGs specifically, while keeping the global `*.png` exclusion for rendered pin templates (which are large and uploaded to GCS instead).

### Fix 2: `src/regen_content.py` — Delete stale hero images after regen

**Location:** `_regen_blog_image()`, after saving hero copy (line 783)

After saving the hero image with the new extension, added cleanup of stale hero files with different extensions:

```python
# Clean up stale hero images with different extensions
for old in slug_hero.parent.glob(f"{slug}-hero.*"):
    if old.suffix != slug_hero.suffix:
        old.unlink()
        logger.info("Removed stale hero %s (replaced by %s)", old.name, slug_hero.name)
```

This ensures that when regen produces a `.png` replacing a `.jpg` original (or vice versa), only the new file remains. The deployer's extension-order iteration then finds the correct image regardless of format.

### Fix 3: `src/blog_deployer.py` — Remove GCS download fallback

**Deleted:** Lines 633-649 (the `# If not on disk, try downloading from GCS` block)

This fallback was added as a workaround for the `.gitignore` exclusion problem. Now that PNGs are properly committed to git, the deployer's filesystem-only hero search is sufficient. Removing the fallback:
- Eliminates a `requests` import dependency in the deploy path
- Removes network I/O during deploy (faster, more reliable)
- Keeps the deploy path simple: files are either in git or they're not

### Fix 4: `_hero_gcs_url` metadata (no change)

`regen_content.py` line 215 stores `blog_data["_hero_gcs_url"] = new_image_url`. Left as-is — harmless debugging metadata, useful for tracing image provenance.

### Files Changed

| File | Change |
|------|--------|
| `.gitignore` | Allow PNG hero images (lines 38-39, already on disk) |
| `src/regen_content.py` | Delete stale hero images with mismatched extensions after regen |
| `src/blog_deployer.py` | Remove GCS fallback download block (-17 lines) |

### Fix 5: `src/blog_deployer.py` — Remove dead `blog_results` load

**Deleted:** Lines 596-603 loaded `blog-generation-results.json` into a `blog_results` variable with the comment "for GCS URL fallback". After removing the GCS fallback (Fix 3), this variable was never used. Removed entirely.

### Fix 6: `src/blog_deployer.py` — Fix heroImage frontmatter extension mismatch

**Problem:** All four blog post prompt templates (`prompts/blog_post_*.md`) hardcode `heroImage: "/assets/blog/{slug}.jpg"` in the frontmatter schema. Claude generates the MDX with this hardcoded `.jpg` extension. But the actual hero image may be `.png` (AI-generated images) or `.webp`. The deployer (`github_api.py:commit_multiple_posts`) commits the image file with its real extension to `public/assets/blog/{slug}{actual_ext}`, but the MDX is committed as-is with the hardcoded `.jpg`. If the extension doesn't match, the website gets a 404 for the hero image.

**Fix:** In both `_deploy_blog_posts()` and `deploy_approved_posts()`, after finding the hero image on disk, update the MDX content to replace the heroImage frontmatter extension with the actual file extension:

```python
if hero_image_path:
    actual_ext = Path(hero_image_path).suffix
    mdx_content = re.sub(
        r'(heroImage:\s*"/assets/blog/' + re.escape(slug) + r')\.[a-z]+"',
        rf'\1{actual_ext}"',
        mdx_content,
    )
```

This ensures the MDX committed to goslated.com always references the correct image file. The regex matches the slug exactly (escaped for safety) and replaces only the extension portion.

Both deploy entry points are covered:
- `_deploy_blog_posts()` — main path (deploy-to-preview workflow)
- `deploy_approved_posts()` — alternative entry point (directory-based deploy)
- `promote_to_production()` — NOT affected (does a git merge, doesn't re-commit MDX)

### Files Changed (Updated)

| File | Change |
|------|--------|
| `.gitignore` | Allow PNG hero images (lines 38-39, already on disk) |
| `src/regen_content.py` | Delete stale hero images with mismatched extensions after regen |
| `src/blog_deployer.py` | Remove GCS fallback (-17 lines), remove dead `blog_results` load (-8 lines), add heroImage frontmatter extension fix in both deploy paths, add `import re` |

### Fix 7: `src/regen_content.py` — Sync pin-schedule.json after regen

**Problem:** When a pin is regenerated, `regen_content.py` deletes the old GCS object (line 642), uploads a new image with a new URL, and updates `pin-generation-results.json`. But `pin-schedule.json` (which `post_pins.py` reads to know what to post) is never updated. The schedule retains the old URL pointing to a deleted GCS object. When `post_pins.py` sends this dead URL to the Pinterest API, the pin fails to post.

Same class of bug as the blog hero issue — stale reference persisting after regen. Also affects copy regen: if title/description changed, the schedule would still have the old text.

**Fix:** After saving updated pin results (Step 6), added Step 6b: load `pin-schedule.json`, find entries matching regenerated pin IDs, update `title`, `description`, `alt_text`, `image_path`, `image_url`, `image_source`, and `image_id` from the freshly-updated `pin-generation-results.json`, and write back. Only updates successfully-regenerated pins (filters out entries with `error` key).

### Re-deploy Steps

1. Commit and push these changes
2. Re-run regen workflow (re-sources images; `git add data/` now picks up PNGs)
3. Re-run deploy-to-preview (overwrites files at same paths on develop branch, now with correct heroImage frontmatter)

### Status

All fixes implemented. Reviewed by two Sr Staff Engineer agents — all blocking issues addressed.

---

## Phase 5: Hero Image Backfill + Frontmatter Slug Fix

**Date:** 2026-02-24
**Commits:** `df5e8cb`, `d53c78e`

### Problem

After the regen image fixes (Phase 4), the correct hero images existed in GCS but were not committed to git. The deploy-to-preview workflow was deploying blog posts with old/missing hero images.

Additionally, 2 of 10 blog posts (W9-P01 and W9-P02) had a **slug mismatch bug**: the MDX file name (e.g., `shrimp-avocado-tacos.mdx`) differed from the frontmatter slug (e.g., `weekly-plan-spring-dinners-under-30-minutes`). The deployer was committing hero images to `public/assets/blog/{file-slug}.jpg` but the MDX `heroImage` frontmatter referenced `public/assets/blog/{frontmatter-slug}.jpg`, causing broken images on the deployed site.

### Fix 1: Hero Image Backfill from Google Sheet

Downloaded all 10 correct blog hero images from GCS URLs in the Content Queue spreadsheet:
- 8 "approved" rows → stock hero from column I
- 2 "use_ai_image" rows (W9-P06, W9-P10) → AI hero from column M

Updated `src/backfill_hero_images.py` to support `--xlsx` flag for local runs when Google Sheets API credentials aren't available locally:
```
python -m src.backfill_hero_images --xlsx path/to/export.xlsx --run
```

### Fix 2: Deploy Images Using Frontmatter Slug (Permanent Fix)

**Root cause:** `blog_deployer._deploy_blog_posts()` passed the file slug to `github_api.commit_multiple_posts()`, which used it for the image commit path. Weekly plan posts have different file slugs vs frontmatter slugs.

**Fix:** The deployer now extracts the frontmatter slug from the MDX content and passes it as `image_slug` to the GitHub API. The image is committed to the path the site actually expects.

| File | Change |
|------|--------|
| `src/blog_deployer.py` | Extract frontmatter slug via regex, pass as `image_slug` in both batch and individual commit paths, use `fm_slug` for heroImage extension regex |
| `src/apis/github_api.py` | `commit_multiple_posts()` and `commit_blog_post()` accept optional `image_slug` param, use it for the deployed image path (defaults to `slug` when they match) |
| `src/backfill_hero_images.py` | Added `--xlsx` flag to read from local spreadsheet export instead of requiring Sheets API credentials |

### Why This Won't Happen Again

The frontmatter slug extraction is permanent — every future deploy reads the actual slug from the MDX frontmatter and uses it for the image commit path. When file slug and frontmatter slug match (most posts), it's a no-op. When they differ (weekly plan posts), the image lands at the correct path.

---

## Phase 8.3: Promote Workflow Bug Fixes

**Date:** 2026-02-24

### Problem

The first promote-to-production workflow run failed:
1. **All 8 blog URL verifications failed** — every blog returned `False` despite being live on goslated.com
2. **All 7 `use_ai_image` pins skipped the AI image swap** — pins scheduled with stock photos instead of chosen AI images
3. **Content log would get duplicates on rerun** — no dedup protection in `_append_to_content_log()`

### Root Cause Analysis (from GitHub Actions logs)

**All 8 blog failures had the same error:**
```
ERROR __main__: Verification error for shrimp-avocado-tacos:
  GitHubAPI.verify_deployment() got an unexpected keyword argument 'slug'
```

The `verify_urls()` method called `self.github.verify_deployment(slug=slug, ...)` but the actual parameter in `github_api.py` is named `slug_or_urls`, not `slug`. This caused a `TypeError` on every single call, caught silently by the `except Exception` block. No blog URL was ever actually checked.

### Fix 1: `verify_urls()` keyword argument bug (ROOT CAUSE)

**File:** `src/blog_deployer.py` line 590

Changed `slug=slug` to positional argument `slug`. This was a simple parameter name mismatch — the function signature uses `slug_or_urls` as the positional parameter name.

### Fix 2: Frontmatter slug for production verification

**File:** `src/blog_deployer.py` lines 386-397

Even after Fix 1, P01 and P02 would fail because `promote_to_production()` built verification URLs from file slugs (column F), not frontmatter slugs. The blog URL uses the frontmatter slug.

Same pattern as the `_deploy_blog_posts()` fix from Phase 5: reads each MDX file, extracts frontmatter slug via `re.search(r'^slug:\s*"(.+?)"', mdx_text, re.MULTILINE)`, falls back to file slug if not found or MDX missing.

### Fix 3: Blog status filter excludes `use_ai_image`

**File:** `src/blog_deployer.py` lines 122, 261, 376

Three locations filtered blogs with `item.get("status") == "approved"`, excluding P06 and P10 which have status `use_ai_image`. Pins already used `in ("approved", "use_ai_image")` — blogs didn't.

Changed all 3 to `item.get("status") in ("approved", "use_ai_image")`.

### Fix 4: Content log dedup for safe reruns

**File:** `src/blog_deployer.py` lines 877-892

`_append_to_content_log()` now loads existing `source_post_id` values before appending. Skips any pin whose ID already exists. Logs count of skipped duplicates.

### AI image swap (no code change needed)

The `_ai_image_url` field was already populated in `pin-generation-results.json` from the spreadsheet in a prior session. Rerunning promote will trigger the swap now that `use_ai_image` blogs/pins are included.

### Files Changed

| File | Change |
|------|--------|
| `src/blog_deployer.py` | Fix keyword arg in `verify_urls()`, frontmatter slug in `promote_to_production()`, `use_ai_image` in 3 blog filters, dedup in `_append_to_content_log()` |

### Status

All 4 fixes implemented and syntax-verified. Pending commit, push, and promote workflow rerun.

## Phase 9: LLM Model Upgrades

### Change

Upgraded Claude model IDs to the latest 4.6 family and corrected pricing:

| Role | Old Model ID | New Model ID |
|------|-------------|-------------|
| Routine (Sonnet) | `claude-sonnet-4-20250514` | `claude-sonnet-4-6` |
| Deep (Opus) | `claude-opus-4-20250514` | `claude-opus-4-6` |
| Fast/Vision (Haiku) | `claude-haiku-4-5-20251001` | No change (already current) |

### Files Changed

| File | Change |
|------|--------|
| `src/apis/claude_api.py` | Updated `MODEL_ROUTINE` and `MODEL_DEEP` to 4.6 model IDs (non-dated aliases); corrected `COST_PER_MTK` pricing |

### Cost Impact

Opus 4.6 is $5/$25 per MTK — 67% cheaper than Opus 4's $15/$75. Haiku 4.5 corrected to $1/$5 (was $0.80/$4). Sonnet 4.6 unchanged at $3/$15.

### Status

Complete.

## Phase 10: Pinterest Rate Limit Header Parsing Fix

### Problem

Pinterest changed their `X-RateLimit-Limit` response header from a simple integer (`"100"`) to an RFC 9110 structured format:
```
100, 100;w=1;name="safety_net_app_id_user_id", 1000;w=60;name="org_read_app_id_user_id"
```
The code did `int(header_value)` on the full string, causing a `ValueError` crash. Since `_update_rate_limits()` is called on every `_make_request()`, this broke **all** Pinterest API calls — blocking all 3 daily posting workflows and both analytics workflows.

### Root Cause

`pinterest_api.py:_update_rate_limits()` (lines 491, 493, 495) and `_get_retry_after()` (line 522) parsed rate limit headers with bare `int()` calls. The structured header format contains commas and semicolons that `int()` cannot parse.

### Fix

Added `PinterestAPI._parse_rate_limit_value()` static method that:
1. Splits the header by `,` to get the first token
2. Splits by `;` to strip metadata (weights, names)
3. Parses the numeric part with `int()`
4. Returns `None` on parse failure (graceful degradation, no crash)

Applied the same defensive parsing pattern to `image_stock.py` for Unsplash and Pexels rate limit headers (not currently broken, but same fragile `int()` pattern).

### Files Changed

| File | Change |
|------|--------|
| `src/apis/pinterest_api.py` | Added `_parse_rate_limit_value()` helper; refactored `_update_rate_limits()` and `_get_retry_after()` to use it |
| `src/apis/image_stock.py` | Defensive parsing for Unsplash (line 207) and Pexels (line 265) rate limit headers |

### Affected Workflows

| Workflow | Impact |
|----------|--------|
| `daily-post-morning.yml` | Blocked — `post_pins morning` crashes at `list_boards()` |
| `daily-post-afternoon.yml` | Blocked — same crash path |
| `daily-post-evening.yml` | Blocked — same crash path |
| `weekly-review.yml` | Blocked — `pull_analytics` crashes at first API call |
| `monthly-review.yml` | Blocked — same crash path |

### Status

Complete. Morning workflow should be manually rerun after merge.

## Phase 11: Pipeline Simplification

**Date:** 2026-02-26
**Branch:** `pipeline-simplification` → merged to `main`
**PR:** [#1](https://github.com/bradenpan/slated-pinterest-bot/pull/1)
**Scope:** 35 files changed, 763 insertions, 2,011 deletions (net -1,248 lines)

### Phase A: Image Pipeline Simplification (HIGH risk)

Removed the entire stock photo pipeline (Unsplash/Pexels search, Claude Haiku ranking, Claude Sonnet validation, AI comparison images). All images now AI-generated via gpt-image-1.5 — no more stock photos.

**Key changes:**
- Deleted `src/apis/image_stock.py`, `prompts/image_rank.md`, `prompts/image_search.md`, `prompts/image_validate.md`
- Removed Column M (AI Image) from Content Queue — now 12 columns (A-L) instead of 13 (A-M)
- Switched pin copy generation and image prompt generation to GPT-5 Mini (Claude Sonnet fallback)
- Removed `upload_ai_hero_images()` from `gcs_api.py`, `upload_single_image()` dead code
- Removed `_process_ai_image_swaps()` from `blog_deployer.py` (kept `use_ai_image` as backwards-compat status alias)
- Shifted regen trigger from O1 to N1 in Content Queue, column 15→14 in `trigger.gs`
- Added configurable model ID via `OPENAI_CHAT_MODEL` env var (defaults to `gpt-5-mini`)
- Added JSON code-fence stripping for GPT-5 Mini responses in `_source_ai_image()`
- Added rate limit retry (429) with Retry-After header support for GPT-5 Mini
- Increased GPT-5 Mini timeout to 90s for pin copy batch operations
- Moved `_parse_json_response()` inside try/except for pin copy so parse failures fall back to Claude
- Removed `UNSPLASH_ACCESS_KEY` and `PEXELS_API_KEY` from all workflow files
- Removed Node.js + Puppeteer steps from `promote-and-schedule.yml` (only needed for deleted `_process_ai_image_swaps`)

### Phase B: Blog Post Double Title Fix (LOW risk)

- Removed `# {Title}` H1 from all 4 blog post prompt templates (recipe, guide, listicle, weekly-plan)
- Removed duplicate H1 from all 4 example templates
- Added H1 stripping safety net in `blog_generator.py` — strips any H1 matching frontmatter title

### Phase C: Plan-Level Feedback & Regeneration (LOW risk)

- New `src/regen_weekly_plan.py` — orchestrator for plan-level regen (320 lines)
- New `.github/workflows/regen-plan.yml` — workflow triggered by `repository_dispatch: regen-plan`
- Extended `sheets_api.py` with `read_plan_regen_requests()`, `reset_plan_regen_trigger()`, weekly review Status/Feedback columns, B5 trigger
- Extended `claude_api.py` `generate_replacement_posts()` with `reviewer_feedback` param
- Added `notify_plan_regen_complete()` to `slack_notify.py`
- Added B5 watcher and `runPlanRegen()` function to `trigger.gs`

### Risk Fixes (applied after main phases)

- JSON code-fence stripping before `json.loads()` in `_source_ai_image()` (GPT-5 Mini wraps JSON in markdown fences)
- `OPENAI_API_KEY` added to `regen-plan.yml` env block
- GPT-5 Mini timeout: configurable parameter, 90s for batch pin copy, 30s default for image prompts
- Rate limit retry with backoff for 429 responses (single retry, reads Retry-After header, caps at 30s)
- Parse failure fallback: `_parse_json_response()` now inside try/except so malformed JSON from GPT-5 Mini falls back to Claude
- Configurable model ID via `OPENAI_CHAT_MODEL` env var
- Dead code cleanup: deleted `image_stock.py`, `upload_single_image()`, stale workflow secrets, stale comments

### Post-Merge Required Action

- Update Apps Script in Google Sheets (copy `src/apps-script/trigger.gs` into script editor)
- Wires up B5 plan regen trigger and shifts content regen trigger O1→N1

### Status

Complete. Merged to main via PR #1.

---

## Phase 12: Pin Template Improvements

**Date:** 2026-02-26
**Branch:** `pin-template-redesign` → merged to `main`
**PR:** [#2](https://github.com/bradenpan/slated-pinterest-bot/pull/2)
**Merge Commit:** `678fbba`

### Problem

Pin templates rendered with generic/empty text because the content extraction pipeline was too simplistic. The `text_overlay` field only contained `headline` and `sub_text` — all template-specific content (bullets, list items, steps, problem/solution text, time badges) was reverse-engineered from the `description` field by splitting on sentence boundaries, producing 1-2 usable items when 3-5 were needed. Font sizes were too small for mobile viewing. No CTA elements existed on any template. Several template-specific features (recipe time badges, listicle item counts, problem/solution visual hierarchy) were missing or broken.

### Phase 1: Prompt + Extraction Overhaul

Expanded `text_overlay` from a flat `{headline, sub_text}` object to structured JSON with template-specific fields:

| Template | New Fields |
|----------|-----------|
| tip-pin | `bullets` (array of 3 tip strings) |
| listicle-pin | `list_items` (array of 5 numbered items) |
| infographic-pin | `steps` (array of 3-5 process steps) |
| problem-solution-pin | `problem_text`, `solution_text` |
| recipe-pin | `time_badge` (e.g., "25 min") |
| All templates | `cta_text` (e.g., "Get the Recipe") |

Rewrote `build_template_context()` with structured-first extraction: reads the new structured fields directly from `text_overlay`, with backwards-compatible fallback paths that derive content from `description` when the AI returns the old flat format. Updated the system message in `claude_api.py` to instruct the LLM to produce the new schema.

### Phase 2: Font Sizes + CTAs

**Font size bumps for mobile readability:**
- `.text-body`: 30px → 32px
- `.text-label`: 22px → 24px
- Template-specific size increases for headlines, subtitles, and body text

**CTA pill button on all 15 template variants** (5 templates x 3 variants):
- Added `.cta-pill` element to every template HTML file
- Class-based hiding (`.hide-cta { display: none }`) so templates degrade gracefully when no CTA text is provided
- Light and dark variants matching each template's color scheme

### Phase 3: Template Polish

- **Recipe time badge** — new `.time-badge` element with class-based hiding (`.hide-time-badge { display: none }`), displayed when `time_badge` is provided
- **Problem/solution font weights** — problem text at weight 500, solution text at weight 800 for visual hierarchy
- **Listicle 5-item truncation** — if more than 5 items provided, truncates to 5 with an "...and more" row
- **Logo opacity** — standardized to 0.6 across all 15 variants for consistent branding
- **Dynamic labels** — category labels and problem/solution labels driven by template variables instead of hardcoded text

### Files Changed

| File | Change |
|------|--------|
| `prompts/pin_copy.md` | Expanded `text_overlay` schema with template-specific fields, added examples for each template type |
| `src/generate_pin_content.py` | Rewrote `build_template_context()` with structured-first extraction + fallback paths for all 5 template types |
| `src/apis/claude_api.py` | Updated system message to instruct LLM to produce structured `text_overlay` per template type |
| `src/pin_assembler.py` | CTA pill injection, time badge injection, class-based hiding logic for optional elements |
| `templates/pins/shared/base-styles.css` | Font size bumps (`.text-body` 30→32px, `.text-label` 22→24px), `.cta-pill` styles, `.hide-cta`/`.hide-time-badge` utility classes |
| `templates/pins/recipe-pin/*.html` (3 files) | CTA pill, time badge element, dynamic category label |
| `templates/pins/tip-pin/*.html` (3 files) | CTA pill, dynamic category label |
| `templates/pins/listicle-pin/*.html` (3 files) | CTA pill, 5-item truncation with "...and more" row, dynamic category label |
| `templates/pins/problem-solution-pin/*.html` (3 files) | CTA pill, dynamic problem/solution labels, font weight adjustments |
| `templates/pins/infographic-pin/*.html` (3 files) | CTA pill, dynamic category label |
| `templates/pins/recipe-pin/recipe-pin.css` | Time badge styles, font size adjustments |
| `templates/pins/listicle-pin/listicle-pin.css` | "...and more" row styles, font size adjustments |
| `templates/pins/infographic-pin/infographic-pin.css` | Step layout adjustments |
| `templates/pins/problem-solution-pin/problem-solution-pin.css` | Problem/solution font weights (500/800), layout adjustments |

### Status

Complete. Merged to main via PR #2 (commit `678fbba`).

## Phase 13: Code Refactor — Architecture Cleanup

**Date:** 2026-02-26 – 2026-02-27
**Commits:** `1893b52` through `16db0e6` (8 commits on main)

### Problem

After 12 phases of feature additions, the codebase had accumulated structural debt: god files (1000+ line modules), duplicated utility code across modules, hardcoded paths/config scattered throughout, tight coupling between orchestration and I/O, no test suite, and ~56 dead code items.

### What Was Done

Eight sequential refactoring commits:

| Commit | Change | Impact |
|--------|--------|--------|
| `1893b52` | Remove dead code — 56 items across 15 files | Eliminated unreachable functions, unused imports, stale parameters |
| `281c184` | Extract composite GitHub Actions | 3 reusable actions (`setup-pipeline`, `commit-data`, `notify-failure`), reduced workflow boilerplate |
| `22bb876` | Update audit documentation | Recorded Phase 0 and Phase 6 execution details |
| `6637e5d` | Centralize configuration | New `paths.py` (path constants) and `config.py` (model names, costs, URLs, dimensions, timing) |
| `33e42e3` | Extract 6 shared utilities | `image_utils.py`, `content_log.py`, `plan_utils.py`, `strategy_utils.py`, `content_memory.py` |
| `d167dc3` | Split god files | Reduced largest modules by 40-50% — extracted `plan_validator.py`, `redate_schedule.py` |
| `53bc8a8` | Fix coupling patterns | Standardized error handling, removed circular dependencies |
| `16db0e6` | Add dependency injection + test suite | DI parameters on all orchestration functions, 93 tests across 7 test files |

### Code Review & Fix Cycle

Three independent code reviews ran in parallel, producing strong consensus on key issues:

**22 unique issues found** (8 flagged by 2+ reviewers independently):

| Issue | Severity | Reviewers | Fix |
|-------|----------|-----------|-----|
| `PROJECT_ROOT` NameError in `monthly_review.py:498` | Critical | 3/3 | Replaced with `STRATEGY_DIR` |
| Shell injection in `promote-and-schedule.yml` | Critical | 1/3 | Moved input to env var |
| `extract_drive_file_id()` missing `/d/` URL pattern | Important | 2/3 | Added regex for `/d/FILE_ID/` format |
| Private `_parse_date`/`_get_entry_date` used cross-module | Important | 3/3 | Renamed to public API |
| `notify-failure` action string interpolation risk | Important | 3/3 | Moved to env vars |
| `redate_schedule.py` hardcoded paths + missing UTF-8 | Important | 3/3 | Used `DATA_DIR`, added encoding |
| `plan_validator.py` zero test coverage | Important | 2/3 | Added 21 tests covering all 8 checks |
| `monthly_review.py` missing DI pattern | Important | 1/3 | Added DI parameters |
| Fragile string parsing in `identify_replaceable_posts` | Important | 1/3 | Added `post_id`/`pin_id` fields to violations |
| `redate_schedule.py` hardcodes 3-day spread | Important | 3/3 | Parameterized with `num_days=7` default |
| 9 minor issues | Minor | Various | Docstrings, encoding, imports, YAML, conftest |

**Round-2 fix cycle** caught 1 logic bug in the initial fixes (dead code path in `identify_replaceable_posts` for negative keyword violations — pin_id was incorrectly placed in `post_id` field) plus 1 minor regression (dangling `__main__` demo block reference in `weekly_analysis.py`). Both fixed and verified.

**Final QA:** 114/114 tests pass, zero stale references, all YAML valid.

### Review Reports

All reports in `architecture/reviews/`:
- `review-a.md`, `review-b.md`, `review-c.md` — 3 independent code reviews
- `fix-plan.md` — Consolidated fix plan (22 issues)
- `fix-review.md`, `qa-report.md` — Round 1 fix review + QA
- `fix-review-round2.md`, `qa-report-round2.md` — Round 2 fix review + QA

### Status

Complete. All fixes applied and verified.

---

## Phase 14 — Full Codebase Review (Post-Refactor)

After the Phase 13 refactor and its targeted code review, a full codebase review was conducted to catch any issues the refactor may have introduced or any pre-existing problems across the entire codebase.

### Process

Three independent reviewers examined every file in the repository (src/, .github/workflows/, .github/actions/, tests/, configuration). A synthesizer agent cross-referenced all findings, verified each against actual source code, and filtered false positives.

### What Was Found

**10 verified issues** (5 false positives filtered out):

| Issue | Severity | Reviewers | Fix |
|-------|----------|-----------|-----|
| Missing `Path` import in `generate_blog_posts.py` — runtime crash | Critical | 2/3 | Added `from pathlib import Path` |
| `commit-data` action missing 5 metadata JSON files — cross-workflow data loss | Critical | 2/3 | Added all 5 files to git add |
| `piexif` + `pytest` missing from `requirements.txt` — broken fresh install | Critical | 1/3 | Added to requirements.txt |
| MIME mismatch in `pin_assembler.py` — JPEG saved as .png | Important | 2/3 | Switched to content-based MIME detection via `detect_mime_type()` |
| `drive_api._clear_folder` no pagination (max 100 files) | Important | 2/3 | Added pagination loop with nextPageToken |
| `openai_chat_api` single retry on 429 rate limit | Important | 2/3 | Added 3-attempt retry with exponential backoff |
| `setup_boards.py` missing `encoding="utf-8"` | Important | 1/3 | Added encoding parameter |
| GCS silent failure mode — no diagnostics | Important | 2/3 | Added `_init_error` field and `is_available` property |
| `regen_content.py` unconditional DriveAPI init — crashes without creds | Important | 1/3 | Made DriveAPI initialization lazy |
| `datetime.utcnow()` deprecated in Python 3.12+ | Important | 1/3 | Replaced with `datetime.now(timezone.utc)` |

### Fix Verification

- **Code review:** 9/10 CORRECT, 1/10 CORRECT WITH NOTES (retry uses linear backoff, adequate given server Retry-After headers)
- **QA:** 114/114 tests pass, all 10 fixes confirmed in code, no stale references, all YAML valid

### Review Reports

All reports in `architecture/reviews/`:
- `codebase-review-a.md`, `codebase-review-b.md`, `codebase-review-c.md` — 3 independent full codebase reviews
- `codebase-synthesis.md` — Synthesized findings with consensus matrix
- `codebase-fix-review.md` — Fix code review
- `codebase-qa-report.md` — QA verification report

### Status

Complete. All fixes applied and verified.

---

## Phase 8: Anti-AI Detection & SEO Readiness for Content Prompts

**Date:** 2026-02-27

### Problem

All content generation prompts (blog posts, pin copy, image prompts) had zero instructions addressing AI content detection or SEO readiness of the generated text. Google's December 2025 core update penalizes content that reads as unedited AI output (87% negative impact on mass-produced AI content), and the pipeline's prompts contained no countermeasures for the two primary detection signals: low perplexity (predictable word choices) and low burstiness (uniform sentence structure). Additionally, prompts lacked E-E-A-T experience signals and semantic keyword coverage.

### Research Basis

Two comprehensive research reports informed the changes:
- `seo-deep-dive.md` — Technical SEO, content strategy, E-E-A-T framework, Google's December 2025 core update analysis
- `ai-content-detection-countermeasures.md` — How Google detects AI text/images, prompt engineering countermeasures, post-processing pipelines

### What Was Changed

**6 prompt files modified** with 4 categories of changes:

#### 1. Writing Style (Natural Voice) — all 4 blog prompts

Added anti-AI writing rules to CONTENT RULES sections:
- **Sentence variation:** Mix short (5-8 word) and long (20-30 word) sentences; vary paragraph openers
- **Voice texture:** Contractions throughout; occasional parenthetical asides
- **Specificity over generality:** Concrete quantities, ages, scenarios instead of vague language
- **Structure variation:** Different section openers; varied paragraph lengths
- Recipe prompt gets a lighter version (4 bullets) matching its 600-800 word target

#### 2. Experience Signals (E-E-A-T) — all 4 blog prompts

Added instructions to include first-hand experience markers:
- Guide/Listicle: First-person experience phrases, honest qualifiers, named brands/products
- Recipe: Write as someone who has cooked it repeatedly; include experience-only tips
- Weekly Plan: Recipe intros as lived experience; practical cooking tips from practice

#### 3. Enhanced SEO Sections — all 4 blog prompts

Added to existing SEO rules:
- **Semantic coverage:** Use synonyms/related terms for primary keyword naturally throughout body
- **Header keywords:** Include primary keyword variant in at least one H2 (where applicable)

#### 4. AI-Detection Vocabulary Ban — 4 blog prompts + pin copy

Banned ~30 words/phrases flagged by AI detectors:
- "delve," "navigate," "landscape," "leverage," "multifaceted," "moreover," "furthermore," "additionally," "it's worth noting," "in today's [adjective] world," "game-changer," "unlock," "harness," "elevate," "seamlessly," "In conclusion," etc.
- Pin copy gets a shorter list appropriate for 250-500 character descriptions

#### 5. Pin Copy Natural Voice — pin_copy.md

- Sentence variation rule (don't start 3+ sentences with same word)
- Contraction requirement (at least one per description)

#### 6. Image Metadata Note — image_prompt.md

- POST-GENERATION NOTE about stripping EXIF/IPTC metadata from AI images
- AI generators embed `trainedAlgorithmicMedia` tags that Google reads

#### 7. Few-Shot Example Fixes — blog_post_weekly_plan.md

- "Here is what is on the menu" → "Here's what's on the menu"
- "That is your week" → "That's your week"

### Files Changed

| File | Changes |
|------|---------|
| `prompts/blog_post_guide.md` | Writing Style, E-E-A-T, enhanced SEO, AI vocab ban |
| `prompts/blog_post_listicle.md` | Writing Style, E-E-A-T, enhanced SEO, AI vocab ban |
| `prompts/blog_post_recipe.md` | Writing Style (short), E-E-A-T (short), enhanced SEO, AI vocab ban |
| `prompts/blog_post_weekly_plan.md` | Writing Style, E-E-A-T, enhanced SEO, AI vocab ban, few-shot fixes |
| `prompts/pin_copy.md` | Sentence variation, contractions, AI vocab ban (short) |
| `prompts/image_prompt.md` | Post-generation metadata stripping note |

### Review

Automated review agent verified all 7 checks PASS:
- Structural integrity, cross-prompt consistency, no contradictions with existing rules, pin copy additions, image prompt addition, few-shot contractions, pipeline compatibility (no new template variables, output formats unchanged)

### Status

Complete. All changes applied and verified.

## Phase 15: Monthly Review Slack Link + Pin Metadata Pipeline Fix

### Problem

Three issues identified during the first monthly strategy review (March 2026):

1. **Slack notification linked to Google Sheet, not the review file.** The monthly review markdown (`analysis/monthly/YYYY-MM-review.md`) was committed to the repo, but the Slack message only contained the Google Sheet link — making the review unfindable.

2. **All pins classified as "unknown" pillar and "unknown" content type.** The weekly plan prompt specified `pillar` and `content_type` for blog posts but not pins. When `generate_pin_content.py` tried `pin_spec.get("pillar")`, it got `None`. Downstream aggregation converted `None` → `"unknown"`, breaking all pillar/content_type analytics in weekly and monthly reviews. This is internal tracking only — does not affect Pinterest or how pins appear to users.

3. **48 existing content-log entries had null pillar/content_type** and needed backfilling.

### Fix 1: Slack Notification — GitHub Link

- Added `GITHUB_REPO_URL` env var to `monthly-review.yml` (from `github.server_url`/`github.repository`)
- `monthly_review.py` now passes the repo-relative review path to the Slack notifier
- `slack_notify.py` constructs a direct GitHub link: `https://github.com/.../blob/main/analysis/monthly/YYYY-MM-review.md`
- Falls back to local file path hint if `GITHUB_REPO_URL` is not set

### Fix 2: Pin Metadata — Prompt + Code Fallback

**Prompt fix** (`prompts/weekly_plan.md`): Added `pillar` and `content_type` to the pin JSON output spec and all few-shot pin examples (3, 4, 5), with instruction that pins inherit these from their parent blog post.

**Code fallback** (`src/generate_pin_content.py`): After pin_data is built, if `pillar` or `content_type` is still `None`, looks up the parent blog post via `source_post_id` — first from `blog-generation-results.json`, then from the plan's `blog_posts` array as secondary fallback.

### Fix 3: Content Log Backfill

Backfilled all 48 entries in `data/content-log.jsonl` using the `source_post_id` → blog post mapping from `data/weekly-plan-2026-02-23.json`. Zero null pillar entries remain.

### Files Changed

- `.github/workflows/monthly-review.yml` — added `GITHUB_REPO_URL` env var
- `src/monthly_review.py` — pass repo-relative review path to Slack notifier
- `src/apis/slack_notify.py` — construct GitHub link in monthly review notification
- `prompts/weekly_plan.md` — add `pillar`/`content_type` to pin spec + few-shot examples
- `src/generate_pin_content.py` — add pillar/content_type inheritance fallback from parent blog post
- `data/content-log.jsonl` — backfill null pillar/content_type on all 48 entries

### Code Review

Automated review agent found 4 issues (1 MEDIUM, 3 LOW), all addressed before commit:
1. (MEDIUM) Brittle path-stripping in Slack link — fixed by passing repo-relative path from caller
2. (LOW) `content_type` overwritten unconditionally — fixed with independent guard
3. (LOW) Dangling emoji line when review_link empty — fixed with conditional
4. (LOW) Few-shot pin examples missing new fields — fixed

### Status

Complete. 206 tests pass.

---

## Phase 16 — Content Memory None-Safety Fix (2026-03-02)

### Problem

Weekly review workflow crashed on GitHub Actions at step 5 (`python -m src.utils.content_memory`):
```
AttributeError: 'NoneType' object has no attribute 'title'
```
at `content_memory.py` line 156 (the `.title()` call on `ctype`).

### Root Cause

Python's `dict.get(key, default)` only returns the default when the key is **absent**. When the key **exists** with a `None` value, `.get()` returns `None`. After the Phase 15 backfill, some content-log entries had keys present with `null` values (e.g., `"content_type": null`), so `.get("content_type", "unknown")` returned `None` instead of `"unknown"`.

### Fix

Changed all vulnerable `.get(key, default)` patterns to `.get(key) or default` across 5 files:

**`src/utils/content_memory.py`** (primary crash site — 18 lines fixed):
- `content_type`, `pillar`, `board`, `funnel_layer`, `blog_title`, `primary_keyword`, `secondary_keywords`, `impressions`, `saves`, `treatment_number`

**`src/generate_weekly_plan.py`** (1 line):
- Line 236: `p.get("pillar") or 0`

**`src/plan_validator.py`** (1 line):
- Line 114: `pin.get("pillar") or 0`

**`src/regen_weekly_plan.py`** (1 line):
- Line 169: `p.get("pillar") or 0`

**`src/monthly_review.py`** (1 line):
- Line 496: `entry.get("board") or "unknown"`

### Verification

- Code review agent audited all changes + found 4 additional missed categories in content_memory.py (blog_title, treatment_number, impressions/saves, secondary_keywords) — all fixed
- Audit testing agent confirmed: all-None entries, mixed entries, edge cases, output correctness, and full 206-test suite all PASS

### Status

Complete. 206 tests pass.

---

## Phase 17 — safe_get Utility + Codebase-Wide None-Safety Hardening (2026-03-02)

### Problem

During live content generation on GitHub Actions, two bugs appeared on every pin:
1. `Generating AI image prompt for: unknown` — wrong field name (`topic` vs `pin_topic`) + `.get(key, default)` returning None
2. `AI image prompt for W10-04: '```json` — markdown fence leak in image prompt fallback paths

A codebase-wide sweep then revealed **~100+ additional `.get(key, default)` sites** across 6 files where the same None-safety bug could manifest.

### Root Cause

Same as Phase 16: Python's `dict.get(key, default)` returns `None` (not the default) when the key exists with a `None` value. External JSON data (weekly plan, pin results, blog results, Sheet data, API responses) frequently has explicit `null` values.

Additionally, `claude_api.py` used `pin_spec.get("topic", "unknown")` but pins use the field name `pin_topic`. And `generate_pin_content.py` fence-stripping fallback paths used `image_prompt_raw` (unstripped) instead of `cleaned` (stripped).

### Fix

**Created `src/utils/safe_get.py`** — central utility function:
```python
def safe_get(d: dict, key: str, default=None):
    value = d.get(key)
    return value if value is not None else default
```

**Converted all `.get()` calls on external JSON data to `safe_get()` across 6 files** in 4 commits:

| File | Sites Converted | Key Areas |
|------|----------------|-----------|
| `generate_pin_content.py` | ~50 | `build_template_context` (text_overlay, pin_copy, pin_spec), `source_ai_image`, `_resolve_blog_slug`, `_generate_all_copy`, `load_used_image_ids` |
| `claude_api.py` | ~30 | `generate_image_prompt` context, `generate_blog_post` context, `analyze_weekly_performance` context (13 fields), `run_monthly_review` context (5 fields), `generate_replacement_posts` |
| `blog_deployer.py` | ~25 | `_create_pin_schedule` (22 fields), `_append_to_content_log` (14 fields), `_read_approved_content`, `_deploy_blog_posts` |
| `post_pins.py` | ~25 | Content log entry (13 fields), pre-posting access, `build_board_map`, `_create_pin_with_retry`, `load_scheduled_pins`, `_record_failure` |
| `regen_content.py` | ~25 | `_regen_item` pin_spec (10 fields), copy regen, schedule patching, `_regen_blog_image`, `_update_pin_results`, `_build_regen_quality_note` |
| `publish_content_queue.py` | ~15 | Blog entries, `_upload_blog_hero_images`, `_find_hero_image`, `_build_quality_note`, `_compute_quality_stats`, frontmatter parsing |

**Also fixed:**
- `claude_api.py` log message: `pin_spec.get("topic")` → `safe_get(pin_spec, "pin_topic") or safe_get(pin_spec, "topic", "unknown")`
- `generate_pin_content.py` fence-stripping: both `else` and `except` fallback paths now use `cleaned` instead of `image_prompt_raw`

### Commits

1. `282df0e` — Image prompt None-safety + fence-stripping fallback fix
2. `baa56a0` — safe_get utility + 14 initial None-safety bugs across 4 files
3. `cae277d` — Complete safe_get conversion across all external JSON access sites
4. `917e721` — Convert all remaining .get() on external JSON to safe_get (secondary paths)
5. `82ff184` — Final sweep: ~70 remaining .get() calls across all 6 files

### What Remains as Raw `.get()`

Only internal dict lookups where we control the data (e.g., looking up keys in dicts we build ourselves, internal results tracking, config constant lookups). These are safe by definition.

### Verification

- All 206 tests pass after every round of changes
- Code review agents verified each commit
- QA agent confirmed safe_get handles edge cases correctly (0, "", False, [] all preserved as non-None values)

### Status

Complete. 206 tests pass. Codebase fully hardened against `.get(key, default)` None-safety bug on all external JSON data paths.

## Phase 18 — GCS Week-Scoped Cleanup Fix + W9 Pin Recovery (2026-03-02)

### Problem

W9-21 pin posting failed with `Pinterest API error 400: Sorry we could not fetch the image` because the GCS image no longer existed. Root cause: when W10 content generation ran `publish_content_queue.py`, it called `gcs_api.py:upload_pin_images()` which called `self.delete_old_images(prefix="W")` — a blanket delete of ALL `W*` objects from GCS, including W9 images still needed for posting (W9-21 through W9-28 were scheduled for Mar 2-3).

### Fix: Week-Scoped GCS Cleanup

**File:** `src/apis/gcs_api.py`

Replaced `delete_old_images(prefix="W")` with `delete_old_week_images(current_week)`:

- Parses week number from pin_ids (e.g., `W10-01` → week 10)
- Validates all pins in the batch share the same week (handles mixed-batch by using max week)
- Deletes only objects from W(current-2) and earlier — keeps W(current) and W(current-1) alive
- Also cleans `ai-heroes/W*` objects with the same week logic
- Year-boundary handling: W1 keeps W52/W53 from the prior year
- Removed `delete_old_images()` entirely (no external callers)

### Recovery Script

**File:** `src/recover_w9_pins.py` (one-time, delete after Mar 4, 2026)

Re-renders and re-uploads 8 W9 pins (W9-21 through W9-28) whose GCS images were deleted:

1. Extracts original W9 pin data from git history (commit `10b5ba6`)
2. Downloads hero images from original sources (Unsplash API for 5 pins, Pexels for 1, AI re-gen for 1, template-only for 1)
3. Re-renders all pins using `PinAssembler.assemble_pin()` with `build_template_context()`
4. Uploads individually to GCS (avoids `upload_pin_images()` bulk delete)
5. Updates `pin-schedule.json` with new GCS URLs (atomic write)

Features: Unsplash API resolution (not CDN guessing), Pexels API with CDN fallback, `safe_get()` on all external JSON, atomic file writes, dependency validation, date expiry warning.

### Documentation Updates

- `memory-bank/architecture/architecture-data-flows.md` — Updated GCS Upload Flow section to document week-scoped cleanup
- `memory-bank/Audit/audit.md` — Marked `delete_old_images` hardcoded prefix issue as fixed
- `memory-bank/Audit/dead-code-analysis.md` — Updated GCS method list

### Verification

- 3 rounds of code review agents (narrowing → holistic scope)
- No critical issues remaining
- W9-24 will get a new AI image (original lost, unavoidable)

### Status

GCS fix complete and committed. Recovery script ready to run.

---

## Phase 19 — Full Pipeline Production-Hardening Review (2026-03-02)

### Trigger

Deploy-to-preview failed with `SheetsAPIError: Header mismatch on tab 'Content Queue'` — the pipeline's own regen workflow writes columns M-N (`Regen →`, `idle`, `idle`) but `_validate_headers` did strict equality, rejecting the extra trailing columns.

### Root Cause (Header Validation)

`sheets_api.py:_validate_headers()` compared `actual == expected` exactly. But `CQ_CELL_REGEN_TRIGGER = "N1"` (same file, line 74) writes to column N, which is beyond the expected headers (A-L). The pipeline's own writes caused its own validation to fail.

### Fix: Prefix-Only Header Matching

Changed `_validate_headers` to compare only the first `len(expected)` columns: `actual_prefix = list(actual[:len(expected_headers)])`. Trailing columns (from regen workflow) are now allowed. Inserted/shifted columns still raise errors.

### Full Pipeline Review (6 Agents)

Spawned 6 review agents covering the entire codebase:
- **sheets_api + header contracts** — found header validation self-contradiction
- **workflow contracts** — found timeout gaps in generate-content and monthly-review
- **GitHub workflows** — found missing SLACK_WEBHOOK_URL in recover workflow
- **API wrappers** — found missing safe_get in pinterest/github/token_manager/image_gen APIs
- **orchestrators** — found safe_get gaps in plan_validator, plan_utils, content_memory
- **utils + templates** — found duplicate CSS rule, render_pin.js CDN dependency

### Findings: 13 Critical + 17 Warning

Fixed by 4 parallel fix agents:
- **safe_get gaps**: Converted all `.get()` on external JSON to `safe_get()` in `plan_validator.py`, `plan_utils.py`, `content_memory.py`
- **API wrappers**: Added retry logic to `github_api.py`, overload-specific delay to `claude_api.py`, IndexError guard to `image_gen.py`, KeyError handling to `token_manager.py`, confirmed `gpt-image-1.5` model name with code comment
- **Orchestrators**: Added `sys.exit(1)` on zero-output in `generate_blog_posts.py` and `generate_pin_content.py`, try/except in `publish_content_queue.py`, drive null guard in `regen_content.py`
- **Templates/workflows**: Deduplicated `.brand-logo-text.logo-secondary` CSS rule, extended workflow timeouts, added SLACK_WEBHOOK_URL to recover workflow

### Review of Fixes (4 Review Agents)

Found 1 critical + 4 warnings:
- **R-C1**: Pinterest rate limit — reverted `wait_seconds = reset_timestamp` back to `wait_seconds = reset_timestamp - int(time.time())` (epoch interpretation)
- **R-W1**: `plan_validator.py:163` chained `.get()` → converted to `safe_get(rules, ...)`
- **R-W2**: `blog_deployer.py:280` trailing-slash edge case → added `.rstrip("/")`
- **R-W3**: `render_pin.js` CDN timeout → added `timeout: 10000` to `setContent`
- **R-W4**: Dead `plan_status` variable in `regen_weekly_plan.py` → removed

### Files Modified

- `src/apis/sheets_api.py` — prefix-only header validation, None-to-empty string fixes
- `src/apis/pinterest_api.py` — rate limit epoch fix (reverted incorrect change)
- `src/apis/github_api.py` — timeout + retry on 429
- `src/apis/claude_api.py` — overload-specific backoff for 529
- `src/apis/image_gen.py` — IndexError guard, model name comment
- `src/apis/token_manager.py` — KeyError handling
- `src/plan_validator.py` — safe_get conversion throughout
- `src/utils/plan_utils.py` — safe_get conversion
- `src/utils/content_memory.py` — safe_get conversion
- `src/blog_deployer.py` — safe_get + trailing-slash fix
- `src/regen_weekly_plan.py` — removed dead plan_status code
- `src/regen_content.py` — drive null guard
- `src/generate_blog_posts.py` — sys.exit(1) on zero blogs
- `src/generate_pin_content.py` — sys.exit(1) on zero pins
- `src/publish_content_queue.py` — try/except with sys.exit(1)
- `src/pin_assembler.py` — output file existence check
- `render_pin.js` — networkidle0 + timeout
- `templates/pins/shared/base-styles.css` — deduplicated logo rule
- `templates/pins/tip-pin/styles.css` — removed duplicate rule
- `.github/workflows/generate-content.yml` — timeout 45→60 min
- `.github/workflows/monthly-review.yml` — timeout 30→45 min
- `.github/workflows/daily-post-evening.yml` — timeout 45→60 min
- `tests/test_sheets_header_validation.py` — updated for prefix-only matching

### Verification

- 207 tests pass (176 core + 31 image cleaner)
- 1 pre-existing flaky test (`test_noise_does_not_produce_uniform_patterns`) — unrelated float rounding issue
- All 5 review-of-fix items resolved

### Status

Complete. Deploy-to-preview should now succeed.

## Phase 19 — .gitignore Fix + W10 Blog Recovery (2026-03-02)

### Problem

`deploy-to-preview` failed with 0 blog posts because the 10 W10 MDX files were never committed to git.

**Root cause:** In commit `862c05a` (Feb 27, paths.py refactor), `.gitignore` was changed from `data/generated_posts/` (wrong path that matched nothing) to `data/generated/blog/` (correct path that now blocks everything). The original gitignore paths were wrong since day one — code always wrote to `data/generated/blog/`, but gitignore said `data/generated_posts/`. MDX files were only ever committed by accident because the gitignore wasn't matching the actual directories. When the stale paths were "fixed", it started actually blocking the files that `deploy-to-preview` reads from git.

**Key insight:** When git sees `dir/` (trailing slash), it ignores the entire directory and won't traverse into it — making all `!` exception rules below it dead code.

### Fix: .gitignore

Removed `data/generated/blog/` and `data/generated/pins/` directory-level rules. The global `*.png` rule with `!` exceptions now works correctly:
- Blog MDX files (`data/generated/blog/*.mdx`) — **not ignored** (deploy-to-preview needs them)
- Rendered pin PNGs (`data/generated/pins/*.png`) — **ignored** (uploaded to GCS)
- Hero PNGs (`data/generated/pins/*-hero.png`) — **not ignored** (excepted)
- Brand element PNGs (`templates/pins/shared/brand-elements/*.png`) — **not ignored** (excepted)
- JSON results files (`data/blog-generation-results.json`) — **not ignored** (no rule matches)

### Fix: Regen Blogs Only Workflow

Created `.github/workflows/regen-blogs-only.yml` — a one-off `workflow_dispatch` workflow that:
1. Checks out repo (gets gitignore fix)
2. Sets up Python + deps via `setup-pipeline` action
3. Runs `python -m src.generate_blog_posts` (picks latest plan via `find_latest_plan()`)
4. Prints MDX count + results JSON to `$GITHUB_STEP_SUMMARY`
5. Commits MDX files via `commit-data` action

Blog generator runs standalone — no pin generation, Node.js, or Puppeteer needed. Only secret required is `ANTHROPIC_API_KEY`.

### Code Review Catch

Summary step originally referenced wrong path `data/generated/blog/blog-generation-results.json` — actual path is `data/blog-generation-results.json` (written to `DATA_DIR`, not `BLOG_OUTPUT_DIR`). Fixed before commit.

### Files Modified

- `.gitignore` — removed `data/generated/blog/` and `data/generated/pins/` directory rules
- `.github/workflows/regen-blogs-only.yml` — new one-off workflow (delete after W10 deploys)

### Recovery Plan

1. Push gitignore fix + workflow
2. Run `regen-blogs-only` via GitHub Actions (regenerates W10 MDX files)
3. Rerun `deploy-to-preview` (blogs deploy, possibly without hero images)
4. Hero images committed when next full `generate-content` runs for W11

### Status

Ready to push. Workflow not yet run.

---

## Phase 19: Pin Scheduling Simplification (2026-03-02)

### Problem

Three separate places manipulated pin scheduling dates, creating confusion and overlap risk:
1. Claude assigned dates during plan generation (prompt said "Tue→Mon")
2. `_create_pin_schedule()` in blog_deployer.py rewrote ALL dates during promote-to-production
3. `redate_schedule.py` manual utility

Additionally, W10 pins had a start date of Tue Mar 3 — overlapping with W9 pins that run through Tue Mar 3 evening.

### Root Cause

Claude was given a vague text rule ("posting week runs Tuesday through next Monday") and expected to do date math. Claude got the dates wrong, and the rescheduling logic in promote added unnecessary complexity.

### Fix

**Single source of truth:** Pin dates are now computed by Python and injected into the Claude prompt. No date arithmetic by Claude, no date rewriting during promote.

1. **`src/apis/claude_api.py`** — `generate_weekly_plan()` now accepts `week_start_date` (the Monday), computes `pin_start = Monday + 2` (Wednesday), generates 7 exact ISO dates with day names, injects as `{{pin_posting_dates}}`
2. **`src/generate_weekly_plan.py`** — all 4 callsites pass `week_start_date=start_date`
3. **`prompts/weekly_plan.md`** — replaced vague "Tuesday through next Monday" rule with explicit `{{pin_posting_dates}}` injection ("Use EXACTLY these 7 posting dates")
4. **`src/blog_deployer.py`** — removed date rescheduling block from `_create_pin_schedule()`. Carry-over logic (preserving unposted prior-week pins) kept intact. Cleaned up unused imports.
5. **`src/plan_validator.py`** — updated comments and POSTING_DAYS to reflect Wed→Tue cycle
6. **`data/weekly-plan-2026-03-02.json`** — shifted all 28 W10 pin dates +1 day (Tue-Mon → Wed-Tue)
7. **`data/pin-generation-results.json`** — shifted all 28 W10 pin dates +1 day to match

### New Posting Cadence

- **Wednesday → Tuesday** (was Tuesday → Monday)
- Plan generates Monday. Content generates Mon-Tue. First pins post Wednesday.
- 28 pins / 4 per day / 7 days. Clean weekly boundaries with no overlap.

### Verification

- W9 pins in pin-schedule.json: Feb 25 → Mar 3 (untouched)
- W10 pins in pin-generation-results.json: Mar 4 → Mar 10 (no overlap)
- Carry-over logic preserves unposted W9 pins during promote
- `save_pin_schedule()` writes combined array (kept W9 + new W10)
- No code path exists that rewrites or discards W9 pins

### Files Modified

- `src/apis/claude_api.py` — week_start_date param + pin date injection
- `src/generate_weekly_plan.py` — pass start_date to all Claude calls
- `prompts/weekly_plan.md` — explicit date injection replaces text rule
- `src/blog_deployer.py` — removed date rescheduling, kept carry-over
- `src/plan_validator.py` — cosmetic: comments updated to Wed-Tue
- `data/weekly-plan-2026-03-02.json` — W10 dates shifted +1 day
- `data/pin-generation-results.json` — W10 dates shifted +1 day
- `architecture/multi-channel-restructure/pin-scheduling-simplification-plan.md` — plan doc

---

## Phase 19 — Multi-Channel Restructure: Phase 1 (Directory Scaffold + File Moves)
**Date:** 2026-03-02

### What Changed
Executed Phase 1 of the multi-channel mono-repo restructure. Split `src/` into `src/shared/` (cross-channel code) and `src/pinterest/` (Pinterest-specific code), with backward-compat shims at all original paths so the live pipeline continues working unchanged.

### New Directory Structure
```
src/
├── shared/              # Cross-channel code (new)
│   ├── apis/            # claude_api, openai_chat_api, sheets_api, gcs_api,
│   │                      drive_api, github_api, slack_notify, image_gen
│   ├── utils/           # safe_get, strategy_utils, image_utils, content_log, plan_utils
│   ├── paths.py         # PROJECT_ROOT (3 levels up from src/shared/)
│   ├── config.py        # Environment config
│   ├── blog_generator.py
│   ├── blog_deployer.py
│   ├── generate_blog_posts.py
│   └── image_cleaner.py
├── pinterest/           # Pinterest-specific code (new)
│   ├── apis/            # pinterest_api
│   ├── generate_pin_content.py
│   ├── pin_assembler.py
│   ├── post_pins.py
│   ├── pull_analytics.py
│   ├── setup_boards.py
│   ├── regen_content.py
│   ├── plan_validator.py
│   ├── redate_schedule.py
│   └── token_manager.py
├── [29 backward-compat shims at original paths]
├── generate_weekly_plan.py  (unmoved — Phase 3)
├── weekly_analysis.py       (unmoved — Phase 2)
├── monthly_review.py        (unmoved — Phase 2)
└── utils/content_memory.py  (unmoved — Phase 2)
```

### Key Decisions
- **Sequential phase execution**: Each phase gets implementation + review agent pair, pytest verification, and user sign-off before proceeding. No multi-phase swarming.
- **Shim pattern**: Every moved file gets a backward-compat shim at its original path (`from src.shared.X import *`) so GitHub Actions workflows and unmoved files keep working
- **Private re-exports**: `import *` skips `_`-prefixed names. Shims for `image_cleaner.py` and `regen_content.py` have explicit imports for `_add_gaussian_noise` and `_regen_item`
- **PROJECT_ROOT**: `src/shared/paths.py` uses `Path(__file__).parent.parent.parent` (3 levels) vs original 2 levels

### Issues Found & Fixed
1. **`import *` doesn't export private names** — Tests importing `_add_gaussian_noise` and `_regen_item` failed. Fixed with explicit private imports in shims.
2. **`@patch` targeting shim namespaces** — 22 `@patch` decorators across 3 test files targeted old module paths. Mocks didn't reach the real code. Updated to canonical `src.shared.*` / `src.pinterest.*` paths.
3. **Lazy imports using old paths** — 4 runtime imports in moved files still used old paths (e.g., `from src.utils.image_utils import ...`). Updated to `src.shared.utils.*`.

### Verification
- 207 tests passed, 0 failed after all fixes
- Review agent checked: PROJECT_ROOT calc, import completeness, shim completeness, private re-exports, unmoved files, `__init__.py` presence, test patch paths — 0 CRITICAL, 0 WARNING
- All shims verified to re-export correctly

### Files Created (35 new files)
- 5 `__init__.py` files: `src/shared/`, `src/shared/apis/`, `src/shared/utils/`, `src/pinterest/`, `src/pinterest/apis/`
- `src/shared/paths.py`, `src/shared/config.py`
- 8 shared API files, 5 shared util files, 4 shared pipeline scripts
- 9 Pinterest pipeline scripts, 1 Pinterest API file
- 29 backward-compat shims at all original locations

### Files Modified (3 test files)
- `tests/test_claude_api_fallback.py` — `@patch` targets → `src.shared.apis.*`
- `tests/test_regen_drive_guard.py` — `@patch` targets → `src.pinterest.*`
- `tests/test_openai_error_wrapping.py` — `@patch` targets → `src.shared.apis.*`

### Documentation Updated
- `ARCHITECTURE.md` — Directory structure section rewritten for new layout
- `architecture/multi-channel-restructure/execution-strategy.md` — Created: full Phase 1-6 execution strategy, agent patterns, failure-mode checklist

### Next Steps
- Phase 2: Extract content memory + analytics utilities, move weekly_analysis.py, monthly_review.py, publish_content_queue.py
- Phase 3: Split generate_weekly_plan.py (highest risk — affects live posting)
- Phase 4: Move prompts into subdirectories
- Phase 5: Update GitHub Actions workflows
- Phase 6: Remove shims + 1-week burn-in

---

## Phase 19b — Shim `__main__` Fix + Date Override for Pin Recovery
**Date:** 2026-03-03

### Incident: Silent Workflow Failure
After Phase 1 deployed, the March 2nd evening posting workflow completed green but **produced zero output**. No pins posted, no Slack notification, no errors. Root cause: shim files (`from src.X import *`) lack `if __name__ == "__main__":` blocks. When workflows run `python -m src.post_pins evening`, the shim imports symbols then exits silently with code 0. The real module's `__main__` block never executes because it's imported as a regular module (not as `__main__`).

### Fix 1: `__main__` blocks for all 10 workflow-invoked shims
Added `runpy.run_module()` delegation to every shim invoked via `python -m` in GitHub Actions:

```python
if __name__ == "__main__":
    import runpy
    runpy.run_module("src.target.module", run_name="__main__", alter_sys=True)
```

**Files fixed (10):** `src/post_pins.py`, `src/token_manager.py`, `src/blog_deployer.py`, `src/pull_analytics.py`, `src/setup_boards.py`, `src/regen_content.py`, `src/redate_schedule.py`, `src/generate_blog_posts.py`, `src/generate_pin_content.py`, `src/apis/slack_notify.py`

### Fix 2: `--date` override for recovering missed posting slots
Added `date_override` parameter to `post_pins()` and `--date=YYYY-MM-DD` CLI flag. When used:
- Targets a specific date's pins instead of today's
- Skips anti-bot jitter (not needed for manual recovery)
- Validates date format upfront (`datetime.strptime`)
- All 3 daily posting workflows accept `date_override` via `workflow_dispatch` input

**Files modified:** `src/pinterest/post_pins.py`, `.github/workflows/daily-post-morning.yml`, `daily-post-afternoon.yml`, `daily-post-evening.yml`

### Recovery
Used the new `--date` override to recover March 2nd evening pins via workflow_dispatch:
- **W9-23** posted to "Family Dinner Ideas Even Picky Eaters Love"
- **W9-24** posted to "Better Than a Meal Kit"
- Both confirmed in `content-log.jsonl` with valid `pinterest_pin_id`

### Documentation Updates
- `execution-strategy.md` — Added checklist items #9 (shim `__main__` blocks) and #10 (workflow output verification). Added "Required Reading" section. Updated Phase 2 sub-steps to explicitly call out `__main__` requirements for each file.
- `ARCHITECTURE.md` — Updated `post_pins.py` description to mention `--date` override
- `progress.md` — This entry

### Lessons Learned
1. **`import *` shims are import-only** — they re-export symbols but don't execute entry points. Every shim invoked via `python -m` needs a `__main__` block.
2. **Green workflow ≠ working workflow** — a silent no-op exits 0. Must verify expected output (log lines, Slack messages, content-log entries), not just exit code.
3. **Review agents must cross-reference workflows** — the Phase 1 review agent checked imports and shims but didn't verify `python -m` execution paths.

---

## Multi-Channel Restructure: Phase 2 — Extract Content Memory & Analytics Utilities
**Date:** 2026-03-03

### Goal
Move the 4 remaining unmoved files to their canonical locations, extract generic analytics functions into a shared module, and ensure all workflow invocations continue working via shims with `__main__` blocks.

### Sub-step 2a: Move content_memory to shared
- Moved `src/utils/content_memory.py` → `src/shared/content_memory.py` (420 lines)
- Updated imports: `src.paths` → `src.shared.paths`, `src.utils.content_log` → `src.shared.utils.content_log`, `src.utils.safe_get` → `src.shared.utils.safe_get`
- Replaced original with shim + `__main__` block (invoked via `python -m src.utils.content_memory` in `weekly-review.yml`)
- Updated downstream imports in `src/shared/utils/plan_utils.py` and `src/pinterest/plan_validator.py`
- **Key finding:** Execution strategy mentioned "consolidating two content_memory implementations" but consolidation was already done — this was purely a file move.

### Sub-step 2b: Extract analytics utilities
- Created `src/shared/analytics_utils.py` with two functions extracted from `src/pinterest/pull_analytics.py`:
  - `compute_derived_metrics()` — adds save_rate and click_through_rate to entries
  - `aggregate_by_dimension()` — groups entries by any field, computes aggregate metrics
- Updated `pull_analytics.py` to import from shared (removed function definitions + unused `defaultdict` import)
- Shim chain preserved: `src/pull_analytics.py` (shim) → `src/pinterest/pull_analytics.py` → imports from `src/shared/analytics_utils.py`

### Sub-step 2c: Move 3 files to src/pinterest/
All three invoked via `python -m` in workflows — all shims have `__main__` blocks.

| File | Moved To | Workflow |
|------|----------|----------|
| `weekly_analysis.py` | `src/pinterest/weekly_analysis.py` | `weekly-review.yml` |
| `monthly_review.py` | `src/pinterest/monthly_review.py` | `monthly-review.yml` |
| `publish_content_queue.py` | `src/pinterest/publish_content_queue.py` | `generate-content.yml` |

Each file had 6-7 imports updated to canonical `src.shared.*` paths.

Updated `tests/test_publish_content_queue.py`: mock `@patch()` targets changed from `src.publish_content_queue.*` to `src.pinterest.publish_content_queue.*` (mocks must patch at the canonical module where names are used, not at the shim).

### Sub-step 2d: Verification
- **207/207 tests pass** (0 failures)
- **16/16 workflow-invoked modules** findable via `importlib.util.find_spec()`
- **4/4 Phase 2 shims** have `__main__` + `runpy.run_module()` blocks
- Shim backward-compat imports verified for all moved files
- `python -m src.utils.content_memory` produces real output (not silent no-op)
- Review agent ran 10-item failure-mode checklist: **all 10 items PASS**
- Review agent found 2 pre-existing stale imports outside Phase 2 scope:
  - `src/generate_weekly_plan.py` still uses `from src.utils.content_memory import` (works via shim, will be fixed in Phase 3)
  - `src/pinterest/token_manager.py` still uses `from src.apis.slack_notify import` (works via shim)

### Deviation from Implementation Plan
The implementation plan said to absorb `content_log.py` into `analytics_utils.py`. Decision: **don't do it** because (1) content_log was already moved to `src/shared/utils/content_log.py` in Phase 1, (2) its CRUD functions are conceptually distinct from analytics computation, (3) following the execution strategy which doesn't include this.

### Files Changed Summary
| Action | Count | Files |
|--------|-------|-------|
| Created | 5 | `shared/content_memory.py`, `shared/analytics_utils.py`, `pinterest/weekly_analysis.py`, `pinterest/monthly_review.py`, `pinterest/publish_content_queue.py` |
| Replaced with shims | 4 | `utils/content_memory.py`, `weekly_analysis.py`, `monthly_review.py`, `publish_content_queue.py` |
| Modified | 4 | `pinterest/pull_analytics.py`, `shared/utils/plan_utils.py`, `pinterest/plan_validator.py`, `tests/test_publish_content_queue.py` |

### What's Left in src/ (Non-Shim)
After Phase 2, only 3 original files remain in `src/` root:
- `generate_weekly_plan.py` — Phase 3 (split into shared planner + Pinterest planner)
- `regen_weekly_plan.py` — Phase 3
- `recover_w9_pins.py` — Phase 6 (evaluate for deletion)

---

## Multi-Channel Restructure: Phase 3 — Split Planning into Shared + Pinterest-Specific
**Date:** 2026-03-03

### Goal
Extract shared planning data-loading functions from `generate_weekly_plan.py` into `src/shared/content_planner.py`. Move the Pinterest orchestration logic to `src/pinterest/generate_weekly_plan.py`. Move `regen_weekly_plan.py` to `src/pinterest/`. Create backward-compat shims. No behavior change.

### Scope Decision
The original plan called for a two-step Claude call split (content plan → pin plan) and `pin_planner.py` creation. Both **deferred to Phase 8a** (TikTok) because: (1) the two-step split is a behavior change with quality risk, not a refactoring, (2) `pin_planner.py`'s intended contents already exist in `plan_validator.py` and `plan_utils.py`, (3) the file reorganization alone achieves the restructure goal. See Phase 8a pre-requisite in implementation-plan.md.

### Sub-step 3a: Create `src/shared/content_planner.py`
Extracted 4 pure data-loading functions from `generate_weekly_plan.py`:
- `load_strategy_context()` — loads all strategy/brand-voice/keyword/seasonal files
- `load_content_memory()` — reads content memory from disk, falls back to generating fresh
- `load_latest_analysis()` — finds and reads latest `*-review.md` in `analysis/weekly/`
- `get_current_seasonal_window()` — matches today's month to seasonal calendar publish windows

These are channel-agnostic — any channel's planner needs them.

### Sub-step 3b: Move orchestrator → `src/pinterest/generate_weekly_plan.py`
Moved `generate_plan()`, `_validate_plan_structure()`, `_build_reprompt_context()`, `generate_weekly_plan()`, and `__main__` block. Updated all imports to canonical `src.shared.*` / `src.pinterest.*` paths. Identical behavior — same single-shot Claude call, same prompt, same output.

### Sub-step 3c: Move `regen_weekly_plan.py` → `src/pinterest/regen_weekly_plan.py`
Updated all imports. Key changes:
- **Cross-dependency resolved:** `load_content_memory` now imported from `src.shared.content_planner` (was `src.generate_weekly_plan`)
- **Late import consolidated:** `TAB_WEEKLY_REVIEW` and `WR_CELL_PLAN_STATUS` moved from late import (line 239) to top-level import from `src.shared.apis.sheets_api`

### Sub-step 3d: Create backward-compat shims
Both shims have `__main__` blocks with `runpy.run_module()` delegation (lesson from Phase 19b incident).

| Shim | Key re-exports |
|------|---------------|
| `src/generate_weekly_plan.py` | `import *` from pinterest, private `_validate_plan_structure`/`_build_reprompt_context`, shared `load_content_memory`/`load_strategy_context`/`load_latest_analysis`/`get_current_seasonal_window` |
| `src/regen_weekly_plan.py` | `import *` from pinterest |

### Sub-step 3e: Update tests
`tests/test_plan_structure_validation.py` — updated import from `src.generate_weekly_plan` to `src.pinterest.generate_weekly_plan`.

### Verification
- **207/207 tests pass** (0 failures)
- **All canonical imports verified** via AST analysis (anthropic SDK not installed locally)
- **Both shims structurally correct** with `__main__` + `runpy` delegation
- **2 workflow references** found and verified (`weekly-review.yml` line 62, `regen-plan.yml` line 36)
- **Zero stale old-path imports** in non-shim files
- **Both modules discoverable** via `importlib.util.find_spec()`
- **Code review (round 1): all 10 failure-mode checklist items PASS** — APPROVED
- **Code review (round 2): all 10 checklist items PASS + 6 additional checks PASS** — APPROVED
  - Additional checks verified: content_planner.py has no Pinterest-specific logic, all canonical imports correct, cross-dependency resolved, shim private re-exports correct, shim shared function re-exports correct, test imports canonical path
  - 1 minor finding: unused `from pathlib import Path` in `regen_weekly_plan.py` — fixed
  - Design note validated: `generate_weekly_plan.py` calls `generate_content_memory_summary()` directly (always fresh) while `regen_weekly_plan.py` uses `load_content_memory()` wrapper (reads cached) — this asymmetry is intentional
- No pre-existing stale imports found (the `src/generate_weekly_plan.py` stale import noted in Phase 2 review is now resolved)

### Files Changed Summary
| Action | Count | Files |
|--------|-------|-------|
| Created | 3 | `shared/content_planner.py`, `pinterest/generate_weekly_plan.py`, `pinterest/regen_weekly_plan.py` |
| Replaced with shims | 2 | `generate_weekly_plan.py`, `regen_weekly_plan.py` |
| Modified | 3 | `tests/test_plan_structure_validation.py`, `ARCHITECTURE.md`, execution-strategy.md |

### What's Left in src/ (Non-Shim)
After Phase 3, only 1 original file remains in `src/` root:
- `recover_w9_pins.py` — Phase 6 (evaluate for deletion)

### Deferred to Phase 8a
- Two-step Claude call: `content_planner.generate_content_plan()` → `pin_planner.generate_pin_plan()`
- `src/pinterest/pin_planner.py` creation
- `prompts/shared/content_strategy.md` creation

---

## Multi-Channel Restructure — Phase 4: Move Prompts into Subdirectories
**Date:** 2026-03-03
**Risk:** LOW | **Effort:** <1 hour
**Status:** COMPLETE

### Goal
Reorganize `prompts/` into `prompts/shared/` (cross-channel) and `prompts/pinterest/` (Pinterest-specific). No logic changes — file moves + string updates only.

### Sub-step 4a: Create prompt subdirectories
- Created `prompts/shared/` and `prompts/pinterest/`

### Sub-step 4b: Move prompt files (10 total)
**To `prompts/shared/` (5 files):**
- `blog_post_guide.md`, `blog_post_listicle.md`, `blog_post_recipe.md`, `blog_post_weekly_plan.md`, `image_prompt.md`

**To `prompts/pinterest/` (5 files):**
- `weekly_plan.md`, `weekly_plan_replace.md`, `pin_copy.md`, `weekly_analysis.md`, `monthly_review.md`

**Not created:** `prompts/shared/content_strategy.md` — deferred to Phase 8a (two-step planning split).

### Sub-step 4c: Update `src/shared/apis/claude_api.py`
All `load_prompt_template()` calls updated with subdirectory prefixes (8 call sites + 2 glob patterns):
- `"weekly_plan.md"` → `"pinterest/weekly_plan.md"` (2 sites: generate_weekly_plan + smoke test)
- `"pin_copy.md"` → `"pinterest/pin_copy.md"`
- `"weekly_plan_replace.md"` → `"pinterest/weekly_plan_replace.md"`
- `"weekly_analysis.md"` → `"pinterest/weekly_analysis.md"`
- `"monthly_review.md"` → `"pinterest/monthly_review.md"`
- `"blog_post_recipe.md"` → `"shared/blog_post_recipe.md"` (+ guide, listicle, weekly_plan variants)
- `"image_prompt.md"` → `"shared/image_prompt.md"`
- `PROMPTS_DIR.glob("*.md")` → `PROMPTS_DIR.glob("**/*.md")` (2 sites: error message + smoke test)

No shims needed — prompt files are read from disk, not imported by Python.

### Verification
- **207/207 tests pass** (0 failures)
- **No `.md` files remain in `prompts/` root** — all in subdirectories
- **No bare prompt filenames** in `load_prompt_template()` calls — all prefixed with `shared/` or `pinterest/`

### Files Changed Summary
| Action | Count | Files |
|--------|-------|-------|
| Moved | 5 | `prompts/*.md` → `prompts/shared/` (blog_post_guide, blog_post_listicle, blog_post_recipe, blog_post_weekly_plan, image_prompt) |
| Moved | 5 | `prompts/*.md` → `prompts/pinterest/` (weekly_plan, weekly_plan_replace, pin_copy, weekly_analysis, monthly_review) |
| Modified | 1 | `src/shared/apis/claude_api.py` (8 call sites + 2 glob patterns) |
| Modified | 2 | `ARCHITECTURE.md`, `execution-strategy.md` (doc updates) |

---

## Multi-Channel Restructure — Phase 5: Update GitHub Actions Workflows
**Date:** 2026-03-03
**Risk:** MEDIUM | **Effort:** <1 hour
**Status:** COMPLETE

### Goal
Update all `python -m` invocations in workflow and action YAML files to use canonical module paths (`src.pinterest.*` / `src.shared.*`). Remove dependency on backward-compat shims for workflow execution. Delete two expired one-time workflows.

### Sub-step 5a: Update `python -m` invocations (26 changes across 11 workflows + 1 action)

**Workflow changes:**
| Workflow | Changes | New paths |
|----------|---------|-----------|
| `weekly-review.yml` (5) | L44, L47, L52, L56, L62 | `src.pinterest.token_manager`, `src.pinterest.pull_analytics`, `src.shared.content_memory`, `src.pinterest.weekly_analysis`, `src.pinterest.generate_weekly_plan` |
| `generate-content.yml` (4) | L54, L59, L65, L71 | `src.pinterest.token_manager`, `src.shared.generate_blog_posts`, `src.pinterest.generate_pin_content`, `src.pinterest.publish_content_queue` |
| `promote-and-schedule.yml` (3) | L49, L57, L63 | `src.pinterest.token_manager`, `src.shared.blog_deployer`, `src.pinterest.redate_schedule` |
| `monthly-review.yml` (3) | L66, L70, L78 | `src.pinterest.token_manager`, `src.pinterest.pull_analytics`, `src.pinterest.monthly_review` |
| `daily-post-morning.yml` (2) | L47, L50 | `src.pinterest.token_manager`, `src.pinterest.post_pins` (date_override expression preserved) |
| `daily-post-afternoon.yml` (2) | L47, L50 | `src.pinterest.token_manager`, `src.pinterest.post_pins` (date_override expression preserved) |
| `daily-post-evening.yml` (2) | L49, L52 | `src.pinterest.token_manager`, `src.pinterest.post_pins` (date_override expression preserved) |
| `setup-boards.yml` (2) | L30, L33 | `src.pinterest.token_manager`, `src.pinterest.setup_boards` |
| `deploy-and-schedule.yml` (1) | L42 | `src.shared.blog_deployer` |
| `regen-plan.yml` (1) | L36 | `src.pinterest.regen_weekly_plan` |
| `regen-content.yml` (1) | L54 | `src.pinterest.regen_content` |

**Action file change:**
| Action | Change |
|--------|--------|
| `notify-failure/action.yml` (1) | L22: `src.apis.slack_notify` → `src.shared.apis.slack_notify` |

### Sub-step 5b: Update inline Python import (1 change)
- `year-wrap-reminder.yml` L42: `from src.apis.slack_notify import SlackNotify` → `from src.shared.apis.slack_notify import SlackNotify`

### Sub-step 5c: Delete expired one-time workflows (2 files)
- `recover-w9-pins.yml` — header said "DELETE after W9 pins posted by Mar 4, 2026." Deleted.
- `regen-blogs-only.yml` — header said "DELETE after W10 blogs have deployed successfully." Deleted.

### Verification
- **207/207 tests pass** (0 failures)
- **Zero old-style `python -m src.` paths** remaining in YAML files — all use `src.pinterest.*` or `src.shared.*`
- **Zero old-style inline imports** (`from src.apis.*` / `from src.utils.*`) in YAML files
- **date_override expressions** on all 3 daily-post workflows fully preserved
- **CLI arg passthrough** verified for: `blog_deployer preview|promote`, `post_pins morning|afternoon|evening`, `pull_analytics 30`, `redate_schedule "$PIN_START_DATE"`

### Files Changed Summary
| Action | Count | Files |
|--------|-------|-------|
| Modified | 11 | Workflow files: `weekly-review.yml`, `generate-content.yml`, `deploy-and-schedule.yml`, `promote-and-schedule.yml`, `daily-post-morning.yml`, `daily-post-afternoon.yml`, `daily-post-evening.yml`, `monthly-review.yml`, `regen-plan.yml`, `regen-content.yml`, `setup-boards.yml` |
| Modified | 1 | Action file: `.github/actions/notify-failure/action.yml` |
| Modified | 1 | Workflow (inline import): `year-wrap-reminder.yml` |
| Deleted | 2 | `recover-w9-pins.yml`, `regen-blogs-only.yml` |
| Modified | 4 | Doc updates: `ARCHITECTURE.md`, `execution-strategy.md`, `implementation-plan.md`, `memory-bank/progress.md` |

---

## Phase 6 — Multi-Channel Restructure: Delete backward-compat shims and clean up (2026-03-04)

**Risk:** LOW | **Effort:** <1 hour
**Status:** COMPLETE

### Goal
Remove all backward-compat shim files (no longer needed since Phase 5 updated all workflows to use canonical module paths). Delete orphaned `recover_w9_pins.py`. Update test imports. Clean up docs.

### Sub-step 6a: Delete all backward-compat shim files (37 files + 2 directories)

**Shim files deleted from `src/` (20 files):**
`blog_deployer.py`, `blog_generator.py`, `config.py`, `generate_blog_posts.py`, `generate_pin_content.py`, `generate_weekly_plan.py`, `image_cleaner.py`, `monthly_review.py`, `paths.py`, `pin_assembler.py`, `plan_validator.py`, `post_pins.py`, `pull_analytics.py`, `publish_content_queue.py`, `regen_content.py`, `regen_weekly_plan.py`, `redate_schedule.py`, `setup_boards.py`, `token_manager.py`, `weekly_analysis.py`

**Shim files deleted from `src/apis/` (10 files):**
`claude_api.py`, `drive_api.py`, `gcs_api.py`, `github_api.py`, `image_gen.py`, `openai_chat_api.py`, `pinterest_api.py`, `sheets_api.py`, `slack_notify.py`, `__init__.py`

**Shim files deleted from `src/utils/` (7 files):**
`content_log.py`, `image_utils.py`, `plan_utils.py`, `safe_get.py`, `strategy_utils.py`, `content_memory.py`, `__init__.py`

**Orphaned file deleted:**
`src/recover_w9_pins.py` — one-time W9 pin recovery script, workflow already deleted in Phase 5.

**Empty directories deleted:**
`src/apis/`, `src/utils/`

### Sub-step 6b: Update test imports (16 test files)

All test files updated from old shim paths to canonical `src.shared.*` / `src.pinterest.*` paths:
- `test_blog_deployer_pin_filter.py`: `src.blog_deployer` → `src.shared.blog_deployer`
- `test_blog_validation.py`: `src.blog_generator` → `src.shared.blog_generator`
- `test_claude_api_fallback.py`: `src.apis.openai_chat_api` / `src.apis.claude_api` → `src.shared.apis.*`
- `test_config.py`: `src.config` → `src.shared.config`
- `test_content_log.py`: `src.utils.content_log` → `src.shared.utils.content_log`
- `test_image_cleaner.py`: `src.image_cleaner` → `src.shared.image_cleaner`
- `test_image_cleaner_extended.py`: `src.image_cleaner` → `src.shared.image_cleaner`
- `test_mime_detection.py`: `src.utils.image_utils` → `src.shared.utils.image_utils`
- `test_openai_error_wrapping.py`: `src.apis.openai_chat_api` → `src.shared.apis.openai_chat_api`
- `test_paths.py`: `src.paths` → `src.shared.paths`
- `test_pin_schedule.py`: `src.utils.plan_utils` → `src.shared.utils.plan_utils`
- `test_plan_utils.py`: `src.utils.plan_utils` → `src.shared.utils.plan_utils`
- `test_plan_validator.py`: `src.plan_validator` → `src.pinterest.plan_validator`
- `test_publish_content_queue.py`: `src.publish_content_queue` → `src.pinterest.publish_content_queue` (4 inline imports)
- `test_regen_drive_guard.py`: `src.regen_content` → `src.pinterest.regen_content`
- `test_sheets_header_validation.py`: `src.apis.sheets_api` → `src.shared.apis.sheets_api`
- `test_sheets_write_pattern.py`: `src.apis.sheets_api` → `src.shared.apis.sheets_api`

### Sub-step 6c: Fix stale imports in canonical source files (2 files)

- `src/pinterest/token_manager.py` L107: `from src.apis.slack_notify` → `from src.shared.apis.slack_notify` (lazy import in `_get_slack_notifier()`)
- `src/shared/image_cleaner.py` L10: docstring usage example updated to `from src.shared.image_cleaner`

### Sub-step 6d: Update documentation (4 files)

- **ARCHITECTURE.md**: Removed `src/apis/`, `src/utils/`, shim references, `recover_w9_pins.py` from directory tree and file tables. Restructured Section 4 into Shared/Pinterest subsections. Updated deep-dive references to canonical paths.
- **CLAUDE.md**: Replaced `src/apis/`, `src/utils/` key paths with `src/shared/apis/`, `src/shared/utils/`, `src/pinterest/`, `src/pinterest/apis/`, `prompts/shared/`, `prompts/pinterest/`.
- **execution-strategy.md**: Status updated to "Phases 1-6 complete, Phase 7 next"
- **implementation-plan.md**: Status updated to "Phases 1-6 complete, Phase 7 next"

### Verification
- **207/207 tests pass** (0 failures)
- **Zero old-style imports** (`from src.X`, `from src.apis.X`, `from src.utils.X`) in `src/` or `tests/`
- **Zero references to deleted files** (`recover_w9_pins`, old shim paths) in Python code
- **`src/` directory clean**: only `__init__.py`, `shared/`, `pinterest/`, `apps-script/`

### Files Changed Summary
| Action | Count | Files |
|--------|-------|-------|
| Deleted | 37 | Shim files: 20 in `src/`, 10 in `src/apis/`, 7 in `src/utils/` |
| Deleted | 1 | Orphaned: `src/recover_w9_pins.py` |
| Deleted | 2 | Empty directories: `src/apis/`, `src/utils/` |
| Modified | 16 | Test files: import path updates |
| Modified | 2 | Source fixes: `src/pinterest/token_manager.py`, `src/shared/image_cleaner.py` |
| Modified | 4 | Doc updates: `ARCHITECTURE.md`, `CLAUDE.md`, `execution-strategy.md`, `implementation-plan.md` |

### Phase 6 addendum: Phase 7 prep audit

Deep audit of `board-structure.json` references (5 breaking path refs in Python) and repo name references (1 breaking + 12 functional + many cosmetic). Full change maps with file/line/classification written to `execution-strategy.md` "Notes from Phase 6 (for the Phase 7 agent)" section.

---

## Phase 7 — Multi-Channel Restructure: Migrate TikTok Research + Rename Repo (2026-03-03)

### What changed

**TikTok research docs migrated** from `tiktok-automation/` repo into the mono-repo:
- 8 research files + carousel automation plan → `docs/research/tiktok/`
- 18 community research files → `docs/research/tiktok/community/`
- Archetypes + brand guidelines → `strategy/tiktok/`
- `product-overview.md` already identical — no merge needed
- `brand-guidelines.md` is distinct from `brand-voice.md` (brand identity vs Pinterest voice) — kept as separate file

**`board-structure.json` moved** to `strategy/pinterest/board-structure.json`:
- 5 breaking path references updated (setup_boards, post_pins, plan_validator, monthly_review, content_planner)
- 3 cosmetic references updated (docstrings, YAML comments)

**Repo name references updated** (`pinterest-pipeline` / `slated-pinterest-bot` → `slated-content-engine`):
- `trigger.gs` repo name (BREAKING — requires Apps Script redeployment)
- 10 workflow concurrency groups (7 `slated-content-engine` + 3 `slated-content-engine-posting`)
- `commit-data/action.yml` git user name/email
- `drive_api.py` Drive folder name (auto-creates new folder on next upload)
- Cosmetic: `__init__.py`, `github_api.py`, `slack_notify.py`, `blog_deployer.py`, `ARCHITECTURE.md`, `implementation-plan.md`

### Human steps required after commit
1. Deploy updated `trigger.gs` via Google Apps Script editor
2. Rename repo on GitHub: `slated-pinterest-bot` → `slated-content-engine`
3. Update local remote: `git remote set-url origin git@github.com:bradenpan/slated-content-engine.git`
4. Optionally rename local folder: `pinterest-pipeline` → `slated-content-engine`

### File counts

| Action | Count | Details |
|--------|-------|---------|
| Added | 28 | TikTok research + strategy docs |
| Moved | 1 | `board-structure.json` → `strategy/pinterest/` |
| Modified | 20 | Path refs, concurrency groups, repo name refs, docs |

---

## Phase 8 — Multi-Channel Restructure: Shared Context Layer + Workflow Restructure (2026-03-03)

### What changed

**Content log: channel tagging**
- Added `channel` field to content log entries in `blog_deployer.py` and `post_pins.py` (both tag as "pinterest")
- Created `scripts/backfill_channel_field.py` — one-time migration script to add `channel: "pinterest"` to existing entries
- Backward-compatible: missing `channel` field defaults to "pinterest" on read

**Content memory: channel-aware output**
- `generate_content_memory_summary()` gains `channel` parameter for filtering
- Multi-channel mode: entries show `[channel]` tags when multiple channels exist in the log
- Section 3 (PILLAR MIX) gains a "Channel Distribution" subsection
- Header includes channel filter info

**Content planner: remove Pinterest hardcoding**
- Removed `board_structure` (pinterest/board-structure.json) from shared `load_strategy_context()`
- Pinterest's `generate_weekly_plan.py` now loads board structure directly

**Content log utility: generalized idempotency**
- Added `is_content_posted(content_id, channel)` — maps channel to platform ID field (`pinterest_pin_id`, `publer_post_id`, etc.)
- `is_pin_posted()` retained as backward-compatible wrapper

**Workflow restructure: split analytics from planning**
- **New:** `collect-analytics.yml` — runs Monday 5:30am ET. Pulls analytics (all channels), refreshes content memory, commits data files
- **New:** `pinterest-weekly-review.yml` — runs Monday 6:00am ET. Performance analysis + plan generation only (reads fresh data from collection step)
- **Deleted:** `weekly-review.yml` (replaced by the two workflows above)

**Strategy file cleanup**
- Moved `strategy/tiktok/archetypes.md` → `strategy/archetypes.md`
- Moved `strategy/tiktok/brand-guidelines.md` → `strategy/brand-guidelines.md`
- Deleted `strategy/tiktok/` directory (brand-level docs are not TikTok-specific)

### Tests
- Added `is_content_posted()` tests (Pinterest, TikTok, unknown channel, nonexistent file)
- Added `test_content_memory.py` — channel attribution, channel filtering, channel distribution, missing channel defaults
- All 217 tests pass

### File counts

| Action | Count | Details |
|--------|-------|---------|
| Added | 4 | `collect-analytics.yml`, `pinterest-weekly-review.yml`, `scripts/backfill_channel_field.py`, `tests/test_content_memory.py` |
| Deleted | 1 | `weekly-review.yml` (replaced by collect-analytics + pinterest-weekly-review) |
| Moved | 2 | `strategy/tiktok/archetypes.md` + `brand-guidelines.md` → `strategy/` root |
| Modified | 8 | `content_log.py`, `content_memory.py`, `content_planner.py`, `blog_deployer.py`, `post_pins.py`, `generate_weekly_plan.py`, `test_content_log.py`, `ARCHITECTURE.md` |

---

## Phase 8b — Enrich Weekly Analysis with Strategy Context + Performance History (2026-03-04)

### What changed

**Content memory: Section 8 — Performance History**
- Added Section 8 to `content_memory.py` with 5 subsections:
  1. Per-Pillar Lifetime — totals + trend direction (last 4wk vs prior 4wk)
  2. Top Keywords by Saves (All-Time) — top 15 by total saves
  3. Compounding Signal — 3-bucket age analysis (<30d, 30-60d, 60-90d, 90+d), verdict: active/flat/decaying
  4. Top All-Time Performers — top 10 by save_rate (min 100 impressions, deduped by pin_id)
  5. Pillar Trend Direction — per-pillar last 4wk vs prior 4wk save rate comparison
- Pure Python, no LLM call. Content memory grows from ~12K to ~15K total chars.
- Flows automatically to planner (already loads content memory) — no changes to `generate_weekly_plan.py` needed.

**Weekly analysis: strategy + content memory injection**
- `weekly_analysis.py` gains `channel: str = "pinterest"` parameter
- Channel filter applied before `compute_derived_metrics()` — ensures only target channel entries are analyzed
- Loads `strategy_doc` via `load_strategy_context()` and `content_memory` via `load_content_memory()`
- Both passed to `claude_api.analyze_weekly_performance()` as new params

**Claude API: enriched signatures**
- `analyze_weekly_performance()` gains `strategy_doc`, `content_memory`, `cross_channel_summary` params (all default to "")
- Context dict gains `strategy_context`, `content_memory_summary`, `cross_channel_summary` keys
- System prompt updated: evaluate performance against strategic intent, use content memory for keyword saturation/coverage gaps
- `run_monthly_review()` gains `cross_channel_summary`, `content_memory` params (all default to "")
- Context dict gains `cross_channel_summary`, `content_memory_summary` keys

**Monthly review: content memory injection**
- `monthly_review.py` imports `load_content_memory`, loads it, passes to `claude.run_monthly_review()`

**Prompt templates: strategy-aware analysis + cross-channel readiness**
- `weekly_analysis.md`:
  - SYSTEM paragraph: strategic awareness, content memory connection, cross-channel context
  - 3 new context sections: `{{strategy_context}}`, `{{content_memory_summary}}`, `{{cross_channel_summary}}`
  - Step 5 (Trends): strategic validation — cross-reference underperformance with strategy expectations
  - Step 6 (Recommendations): align with strategy, distinguish tactical vs strategic concerns
  - New output sections: "Strategic Alignment Check" + "Cross-Channel Notes"
- `weekly_plan.md`:
  - Step 1: topic dedup scoped to Pinterest-only ("Topics only covered on other channels are NOT off-limits")
  - Step 1: review Performance History section of content memory
  - Cross-channel framing note after content memory section
- `monthly_review.md`:
  - 2 new context sections: `{{content_memory_summary}}`, `{{cross_channel_summary}}`
  - Level 2 (Why It Happened): cross-channel pattern analysis
  - Level 3 (What It Means): cross-channel efficiency question
  - New output section: "Cross-Channel Observations"

### Design decisions

- **Separate calls preserved:** Analysis and planning remain separate Claude calls. Competing objectives, easier debugging, retry granularity, and token pressure all favor separation.
- **Cross-channel params empty today:** `cross_channel_summary` defaults to "Single channel (Pinterest only). No cross-channel data." — ready for TikTok without code changes.
- **3-bucket vs 5-bucket compounding:** Weekly gets simpler 3-bucket compounding signal via content memory. Deep 5-bucket forensic analysis stays monthly-only.
- **This work was planned for Phase 10b but pulled forward** because the strategy vacuum in weekly analysis was causing the planner to receive under-informed recommendations.

### Token budget impact

| Call | Before | After | Annual cost |
|------|--------|-------|-------------|
| Weekly analysis (Sonnet) | ~10K input | ~31K input | +$3.30/year |
| Monthly review (Opus) | ~25K input | ~40K input | +$0.90/year |

### Tests
- All 217 tests pass (no new tests needed — existing content_memory tests cover Section 8 implicitly)
- Placeholder alignment verified: all `{{...}}` in prompts have matching context keys in claude_api.py

### File counts

| Action | Count | Details |
|--------|-------|---------|
| Modified | 7 | `content_memory.py`, `weekly_analysis.py`, `claude_api.py`, `monthly_review.py`, `weekly_analysis.md`, `weekly_plan.md`, `monthly_review.md` |

---

## Multi-Channel Restructure — Phase 9: Carousel Rendering Engine

**Date:** 2026-03-04

**Goal:** Build the TikTok carousel rendering infrastructure — HTML/CSS templates + Python assembler. Reuses the existing Puppeteer-based `render_pin.js` for rendering, but with TikTok-specific templates (1080x1920px, 9:16 vertical).

### What was built

**TikTok carousel templates** — 4 visual families × 3 slide types each (12 HTML + 4 CSS + 1 shared base CSS):
- `clean-educational` — Light background, bold dark headlines, numbered slides (listicles, how-tos)
- `dark-bold` — High-contrast white/accent on dark (bold claims, contrarian takes)
- `photo-forward` — Real photo background with gradient text overlay (recipes, food photography)
- `comparison-grid` — Split panels with before/after layout (comparisons, pros/cons)

Each family has 3 slide types:
- **Hook slide** — Attention-grabbing headline + subtitle
- **Content slide** — Headline + body text + slide number indicator
- **CTA slide** — Call-to-action + @handle + secondary text

**`src/tiktok/carousel_assembler.py`** — `CarouselAssembler` class:
- Loads HTML template per slide type + family
- Inlines shared base CSS + family-specific CSS (same pattern as `pin_assembler.py`)
- Injects `{{mustache}}` variables with HTML escaping
- Converts local image paths to base64 data URIs
- Builds a manifest JSON and calls `render_pin.js --manifest` (single Puppeteer browser session for all slides)
- Validates output PNGs (exists, >10KB)

**Config/paths additions:**
- `config.py`: `TIKTOK_SLIDE_WIDTH = 1080`, `TIKTOK_SLIDE_HEIGHT = 1920`
- `paths.py`: `TIKTOK_OUTPUT_DIR = DATA_DIR / "generated" / "tiktok"`
- `src/tiktok/__init__.py` package init

### Design decisions

- **No variant system:** Unlike Pinterest's A/B/C variants per template, TikTok uses 3 distinct slide types (hook/content/CTA) per family. Simpler and more appropriate for multi-slide carousels.
- **Reuse `render_pin.js`:** The existing Puppeteer renderer already supports custom dimensions and batch mode via `--manifest`. No new Node.js script needed.
- **Safe zones:** top 100px, left/right 60px, bottom 280px — avoids TikTok UI overlay (status bar, caption, action buttons).
- **`{{handle}}` is a template variable, not hardcoded:** The TikTok handle is injected at render time, so when Open Decision #2 is resolved, no template changes are needed.

### Placeholder: TikTok handle

**`@slated` is a placeholder.** The actual TikTok handle has not been finalized (Open Decision #2 in implementation-plan.md). When decided:
1. Pass the correct handle to `carousel_assembler.render_carousel()` — no template edits needed
2. Update Open Decision #2
3. Grep for `@slated` in test fixtures/sample data and update

### Code review cleanup

After initial build, a code review identified and fixed:
- **L1:** Extracted `_image_to_data_uri` from both assemblers to `src/shared/utils/image_utils.py` as `image_to_data_uri()` (public shared function). Both `pin_assembler.py` and `carousel_assembler.py` now import from shared.
- **L3:** Updated implementation-plan.md Phase 9 section — `render_carousel.js` struck through, notes `render_pin.js` reuse. Reuse table updated from 60% → 100%.
- **L5:** Optimized `wait_ms` — first slide 500ms (font loading), subsequent slides 100ms (fonts cached in browser session).
- **L6:** All 4 family CSS files — replaced hardcoded `bottom: 300px` with `calc(var(--safe-bottom) + 20px)`. Photo-forward content panel padding now uses CSS variables.
- **N5:** Moved `import subprocess` to top-level in `carousel_assembler.py`, removed stale deferred import.
- **M1 (deferred to Phase 10):** Added explicit step 5 to Phase 10 spec for post-render `_optimize_image()` + `clean_image()` on carousel output PNGs.

### File counts

| Action | Count | Details |
|--------|-------|---------|
| Created | 18 | `src/tiktok/__init__.py`, `src/tiktok/carousel_assembler.py`, 12 HTML templates, 4 family CSS files, 1 shared base CSS |
| Modified | 7 | `config.py` (TikTok dimensions), `paths.py` (TikTok output dir), `image_utils.py` (extracted `image_to_data_uri`), `pin_assembler.py` (import from shared), `implementation-plan.md` (Phase 9 status + placeholder notes + reuse table), `ARCHITECTURE.md` (TikTok sections), `progress.md` |

---

## Phase 10: TikTok Content Generation Pipeline (2026-03-04)

TikTok content generation pipeline built on top of Phase 9's carousel rendering engine. Generates 7 carousel specs per week via Claude, renders them to slide PNGs, and publishes to a separate TikTok Google Sheet for human review.

### Resolved decisions
- **Handle:** @slatedapp, Creator account
- **Subcommunity:** Invisible Labor (#MentalLoad, #FairPlay) bridging to Daily Question (#WhatsForDinner)
- **Cadence:** 7 posts/week from day one (no ramp)
- **AI disclosure:** `is_aigc: true` for photo-forward carousels only
- **Image gen:** OpenAI gpt-image-1.5 (same as Pinterest)
- **Google Sheet:** Separate TikTok spreadsheet (`TIKTOK_SPREADSHEET_ID`)
- **GCS:** Same bucket, `tiktok/` prefix

### What was built

**Attribute taxonomy** (`strategy/tiktok/attribute-taxonomy.json`):
4 dimensions × 20 total attributes for explore/exploit content optimization:
- topic (6): invisible-labor, whats-for-dinner, meal-prep-hack, picky-eaters, budget-meals, weeknight-speed
- angle (5): empathy-first, tactical-tip, myth-bust, hot-take, relatable-rant
- structure (5): listicle, before-after, story-arc, step-by-step, comparison
- hook_type (4): question, bold-claim, pattern-interrupt, curiosity-gap

Cold-start even weights, Bayesian updates via `compute_attribute_weights.py` (65/35 exploit/explore split, Phase 12 activates this).

**3 Claude prompt templates** (`prompts/tiktok/`):
- `weekly_plan.md` — Generates 7 carousel specs with taxonomy attributes, subcommunity targeting, posting schedule. Slim taxonomy injection (weights only, not full metrics).
- `carousel_copy.md` — Reserved for two-step copy expansion (not wired into pipeline yet).
- `image_prompt.md` — Generates DALL-E prompts for photo-forward carousel backgrounds. Brand visual guidelines embedded in template.

**3 Claude API methods** (`claude_api.py`):
- `generate_tiktok_plan()` — Sonnet, 8192 tokens, taxonomy pre-processed to slim format
- `generate_carousel_copy()` — GPT-5 Mini primary / Sonnet fallback (reserved stub)
- `generate_tiktok_image_prompt()` — GPT-5 Mini primary / Sonnet fallback

**Main orchestrator** (`src/tiktok/generate_weekly_plan.py`):
Mirrors Pinterest pattern: load shared context → load taxonomy → call Claude → validate (3 layers: structural/taxonomy/quality) → generate image prompts for photo-forward → render carousels → save JSON → publish to Sheet → Slack notify. Supports `--dry-run` flag.

**Carousel rendering** (`src/tiktok/generate_carousels.py`):
Handles family name translation (taxonomy underscores → assembler hyphens), background image generation for photo-forward via OpenAI (1024×1536), CarouselAssembler rendering, image cleaning (metadata strip + noise on final slides only, no double-noising).

**Sheet publishing** (`src/tiktok/publish_content_queue.py` + `sheets_api.py`):
14-column TikTok Content Queue schema (ID, Topic, Angle, Structure, Hook Type, Template Family, Hook Text, Caption, Hashtags, Slide Count, Preview, Schedule, Status, Notes). `SheetsAPI.write_tiktok_content_queue()` method with header validation. `=IMAGE()` formula previews via `USER_ENTERED`.

**Apps Script trigger** (`src/apps-script/tiktok-trigger.gs`):
Watches column M (Status) in TikTok Content Queue. When all rows have terminal status (approved/rejected), fires `tiktok-batch-approved` repository_dispatch event.

**image_cleaner.py fixes:**
- PNG format preservation (carousel slides stay PNG, JPEG stays JPEG)
- Alpha-safe Gaussian noise (only RGB channels get noise, alpha preserved)

### File counts

| Action | Count | Details |
|--------|-------|---------|
| Created | 9 | `strategy/tiktok/attribute-taxonomy.json`, `src/tiktok/compute_attribute_weights.py`, `src/tiktok/generate_weekly_plan.py`, `src/tiktok/generate_carousels.py`, `src/tiktok/publish_content_queue.py`, `prompts/tiktok/weekly_plan.md`, `prompts/tiktok/carousel_copy.md`, `prompts/tiktok/image_prompt.md`, `src/apps-script/tiktok-trigger.gs` |
| Modified | 4 | `claude_api.py` (3 TikTok methods), `sheets_api.py` (`write_tiktok_content_queue` + `write_tiktok_weekly_review` stub), `image_cleaner.py` (PNG preservation + alpha-safe noise), `ARCHITECTURE.md` (TikTok Phase 10 sections) |

---

## Phase 11: TikTok Posting via Publer (2026-03-05)

Automated posting pipeline for TikTok carousels via Publer's REST API. Bridges the gap between human approval in the TikTok Google Sheet and live posting. Includes scheduling orchestrator, daily posting with idempotency, manual-upload fallback mode, and failure tracking.

### What was built

**Publer API wrapper** (`src/tiktok/apis/publer_api.py`):
REST API wrapper for Publer v1. Auth via `PUBLER_API_KEY` + `PUBLER_WORKSPACE_ID`. Methods: `import_media()` (bulk URL import), `poll_job()` (exponential backoff polling), `create_post()` (scheduled carousel post). Retry on 429/5xx with backoff. Custom `PublerAPIError` exception class.

**Scheduling orchestrator** (`src/tiktok/promote_and_schedule.py`):
Reads approved carousels from TikTok Content Queue sheet, distributes across 7 days × 3 slots (morning/afternoon/evening) round-robin, resolves GCS slide URLs from deterministic path convention (`tiktok/{carousel_id}/slide-{i}.png`), writes `data/tiktok/carousel-schedule.json`, updates Sheet status to "scheduled". Cap at 21 carousels/week with warning. DST-correct `scheduled_at` timestamps via `ZoneInfo("America/New_York")`. Warns via Slack if any carousels have missing slide URLs.

**Daily posting orchestrator** (`src/tiktok/post_content.py`):
Posts carousels for a specific time slot. Two modes: `TIKTOK_POSTING_ENABLED=true` → full Publer pipeline (import slides → poll → create post → poll → log); `=false` → Slack notification with GCS links for manual upload. Idempotency via `is_content_posted(carousel_id, "tiktok")`. Anti-bot jitter: deterministic seed, 0-120 seconds. Failure tracking in `data/tiktok/posting-failures.json` with Slack alert after 3 failures. CLI: `python -m src.tiktok.post_content morning [--date=YYYY-MM-DD] [--demo]`.

**GCS upload step** added to `generate_weekly_plan.py`:
Step 12 uploads rendered carousel slides to GCS after rendering and before Sheet publishing. Deterministic path convention: `tiktok/{carousel_id}/slide-{i}.png`. Handles partial upload failures (updates `slide_count` to match actual uploads). Passes `slide_preview_urls` to `publish_content_queue()` for Sheet preview column.

**Sheets API methods** (`sheets_api.py`):
- `read_tiktok_approved_carousels()` — Reads Content Queue rows where Status (col M) = "approved"
- `update_tiktok_content_status(carousel_id, status, publer_post_id, error_message)` — Updates Status + Notes columns by carousel_id

**GitHub Actions workflows:**
- `tiktok-promote-and-schedule.yml` — Trigger: `repository_dispatch: tiktok-promote-and-schedule` + manual. Concurrency: `slated-tiktok-scheduling`.
- `tiktok-daily-post.yml` — 3 cron triggers (10am/4pm/7pm ET), `workflow_dispatch` with `time_slot` + `date_override`. Concurrency: `slated-tiktok-posting`.

**Config additions** (`config.py`):
`PUBLER_BASE_URL`, `TIKTOK_JITTER_MAX=120`, `TIKTOK_MAX_POST_FAILURES=3`.

### Bugs found and fixed during review (3 rounds)
- **slide_urls gap:** No GCS upload existed between rendering and Sheet publishing. Fixed with two-part solution (upload step in generate_weekly_plan.py + URL resolution in promote_and_schedule.py).
- **DST bug:** Hardcoded `-05:00` offset. Fixed with `datetime(..., tzinfo=ET).isoformat()`.
- **Slack "pins" wording:** `notify_posting_complete()` says "pins". Replaced with `notify()` using TikTok-specific messages.
- **Partial upload mismatch:** `slide_count` not updated on partial GCS failure. Fixed by syncing count with actual uploads.
- **Silent unpostable scheduling:** No warning when carousels had missing slide_urls. Added Slack warning listing affected IDs.
- **Dead code + redundant env vars + format string nit** cleaned up.

### Required secrets (GitHub Actions)
- `PUBLER_API_KEY` — Publer API key from app.publer.com/settings
- `PUBLER_WORKSPACE_ID` — Publer workspace ID
- `TIKTOK_POSTING_ENABLED` — "true" for Publer posting, "false" for Slack fallback

### File counts

| Action | Count | Details |
|--------|-------|---------|
| Created | 4 | `src/tiktok/apis/__init__.py`, `src/tiktok/apis/publer_api.py`, `src/tiktok/post_content.py`, `src/tiktok/promote_and_schedule.py` |
| Created (workflows) | 2 | `tiktok-promote-and-schedule.yml`, `tiktok-daily-post.yml` |
| Modified | 4 | `config.py` (Publer constants + TikTok timing), `sheets_api.py` (2 TikTok methods), `generate_weekly_plan.py` (GCS upload step), `ARCHITECTURE.md` (TikTok posting sections) |

---

## Phase 12: Analytics + Feedback Loop

**Date:** 2026-03-05

### Goal

Pull TikTok performance data, analyze it weekly via Claude, and close the feedback loop so next week's content generation shifts toward what's working via Bayesian attribute weight updates.

### What Was Built

**TikTok analytics puller** (`src/tiktok/pull_analytics.py`):
Fetches post-level analytics from Publer's post insights API. Filters content log to `channel="tiktok"` entries with `publer_post_id`, within 28-day lookback window. Metrics: views (→ impressions), likes, comments, shares, saves, engagement_rate. Updates content-log.jsonl with cumulative metrics (max() guard). Writes raw snapshot to `data/tiktok/analytics/YYYY-wNN-raw.json`. Writes `data/tiktok/performance-summary.json` with per-attribute averages for feedback loop. Identifies top/bottom 5 posts. CLI: `python -m src.tiktok.pull_analytics [--demo]`.

**Publer analytics method** (`src/tiktok/apis/publer_api.py`):
`get_post_insights(account_id)` — paginates through `GET /analytics/{account_id}/post_insights` (10/page). New env var: `PUBLER_ACCOUNT_ID`.

**TikTok weekly analysis** (`src/tiktok/weekly_analysis.py`):
Claude-powered weekly performance analysis mirroring Pinterest's pattern. Aggregates by TikTok attribute dimensions (topic, angle, structure, hook_type, template_family) instead of Pinterest's pillars/boards/templates. Loads strategy context + content memory + cross-channel summary (Pinterest digest). Saves to `analysis/tiktok/weekly/YYYY-wNN-review.md`. Fallback data-only report if Claude unavailable. CLI: `python -m src.tiktok.weekly_analysis [--demo]`.

**TikTok analysis prompt** (`prompts/tiktok/weekly_analysis.md`):
TikTok-specific analysis prompt. Evaluates explore/exploit effectiveness, virality patterns (not evergreen compounding), attribute taxonomy performance. Includes Strategic Alignment Check + Cross-Channel Notes output sections. Context vars: `{{this_week_data}}`, `{{per_attribute_metrics}}`, `{{strategy_context}}`, `{{content_memory_summary}}`, `{{cross_channel_summary}}`.

**Claude API method** (`src/shared/apis/claude_api.py`):
`analyze_tiktok_performance()` — same enriched signature as Pinterest's `analyze_weekly_performance()`. Loads `prompts/tiktok/weekly_analysis.md`. Sonnet model, temp 0.5, 4096 max tokens.

**Cross-channel summary** (`src/shared/content_memory.py`):
`generate_cross_channel_summary(exclude_channel)` — filters content log to non-target channel entries from last 7 days, computes quick aggregates (post count, top performer, engagement rate), returns 200-300 char summary. Wired into both Pinterest and TikTok weekly analysis.

**Feedback loop wiring** (`src/tiktok/compute_attribute_weights.py`):
`__main__` block gains `--update` flag: reads `data/tiktok/performance-summary.json`, feeds entries into `update_taxonomy_from_performance()`, shifts attribute weights toward high performers.

**Workflow: collect-analytics.yml**:
Uncommented TikTok analytics pull step. Runs alongside Pinterest pull before content memory refresh. Env vars: `PUBLER_API_KEY`, `PUBLER_WORKSPACE_ID`, `PUBLER_ACCOUNT_ID`.

**Workflow: tiktok-weekly-review.yml** (new):
Monday 6am ET (parallel to Pinterest). Steps: weekly analysis → attribute weight update (`--update`) → plan generation. Concurrency group: `slated-content-engine-tiktok`.

### Feedback Loop Data Flow

```
pull_analytics.py → content-log.jsonl (updated metrics)
                  → performance-summary.json (per-attribute averages)
                  ↓
compute_attribute_weights.py --update
                  → attribute-taxonomy.json (shifted weights)
                  ↓
generate_weekly_plan.py (reads updated taxonomy)
                  → content favors high-performing attributes
                  ↓
content-log.jsonl (new posts with channel="tiktok")
                  → surfaces in content memory for all planners
```

### Required Secrets (GitHub Actions)
- `PUBLER_ACCOUNT_ID` — Publer social account ID (for analytics endpoint)

### File Counts

| Action | Count | Details |
|--------|-------|---------|
| Created | 3 | `src/tiktok/pull_analytics.py`, `src/tiktok/weekly_analysis.py`, `prompts/tiktok/weekly_analysis.md` |
| Created (workflows) | 1 | `tiktok-weekly-review.yml` |
| Modified | 5 | `publer_api.py` (+analytics method), `claude_api.py` (+analyze_tiktok_performance), `content_memory.py` (+cross-channel summary), `compute_attribute_weights.py` (--update flag), `collect-analytics.yml` (uncomment TikTok step) |
| Modified (docs) | 2 | `ARCHITECTURE.md` (Phase 12 gotchas), `progress.md` (this entry) |

---

## Phase 13A — TikTok Two-Phase Approval: Split Plan from Rendering (2026-03-05)

Split `generate_weekly_plan.py` into plan-only and full-render modes. First step of the two-phase approval flow where carousel specs are reviewed before any rendering happens.

### What Changed

**`src/shared/paths.py`** — Added `TIKTOK_DATA_DIR = DATA_DIR / "tiktok"`. Promoted from local definition in `generate_weekly_plan.py` so future scripts (`regen_plan.py`, `regen_content.py`) can import it.

**`prompts/tiktok/weekly_plan.md`** — Updated output schema: each carousel spec now includes `image_prompts` array of `{slide_index, prompt}` entries. Added Image Prompt Rules section with per-family rules (`photo_forward`: 1-3 images, all others: empty array) and brand visual guidelines (migrated from deleted `image_prompt.md`).

**`src/tiktok/generate_weekly_plan.py`** — Core changes:
- Added `plan_only: bool = False` parameter to `generate_plan()`
- Removed Step 9 (`generate_tiktok_image_prompt()` loop) — image prompts now come from Claude's planning output
- Added `image_prompts` validation in `_validate_plan()`: defaults to `[]`, max 3, non-photo_forward must be empty, CTA slide index never targeted
- Plan-only branch: saves JSON → writes Weekly Review tab → returns (skips rendering, GCS, Content Queue, Slack)
- Full pipeline branch preserved (broken between Phase A and D; Phase B switches cron to `--plan-only`)
- Added `--plan-only` CLI flag
- Import `TIKTOK_DATA_DIR` from `paths.py` instead of local definition

**`src/shared/apis/sheets_api.py`** — New constants + 3 methods:
- `TIKTOK_TAB_WEEKLY_REVIEW`, `TIKTOK_WR_CELL_PLAN_STATUS` (B3), `TIKTOK_WR_CELL_REGEN_TRIGGER` (B5), `TIKTOK_WR_DATA_START_ROW` (7), `TIKTOK_WR_HEADERS` (11 cols A-K)
- `write_tiktok_weekly_review(plan)` — writes control cells (B3=pending_review, B5=idle) + header + carousel spec rows with slide text preview
- `read_tiktok_plan_status()` — reads B3, returns None if tab missing (handles first-run edge case)
- `read_tiktok_plan_regen_requests()` — reads regen-flagged rows with feedback from cols J/K

**`src/shared/apis/claude_api.py`** — Deleted `generate_tiktok_image_prompt()` method (~40 lines). Dead code after Step 9 removal.

**`prompts/tiktok/image_prompt.md`** — Deleted. Dead code after method deletion.

**`src/tiktok/pull_analytics.py`** — Replaced local `TIKTOK_DATA_DIR` definition with import from `src.shared.paths` (centralizing the constant).

### TikTok Weekly Review Tab Schema (new)

Control cells: B3 (plan status), B5 (regen trigger). Data starts row 7.
Columns A-K: ID, Topic, Angle, Structure, Hook Type, Template Family, Hook Text, Slide Text Preview, Caption, Status, Feedback.

### Deployment Note

Phase A must deploy with Phase B (workflow update to `--plan-only`). Between A and D, the non-plan-only code path is broken (Step 9 removed but `generate_carousels.py` still reads `_image_prompt`).

### File Counts

| Action | Count | Details |
|--------|-------|---------|
| Deleted | 2 | `prompts/tiktok/image_prompt.md`, `generate_tiktok_image_prompt()` method in `claude_api.py` |
| Modified | 5 | `generate_weekly_plan.py` (plan_only branch + validation), `sheets_api.py` (+3 methods + constants), `paths.py` (+TIKTOK_DATA_DIR), `weekly_plan.md` (image_prompts schema), `pull_analytics.py` (centralized import) |
| Modified (docs) | 2 | `ARCHITECTURE.md` (two-phase flow, updated tables/gotchas), `progress.md` (this entry) |

## Phase 13B — TikTok Two-Phase Approval: Workflow Update + Collision Guard (2026-03-05)

Updated `tiktok-weekly-review.yml` to use `--plan-only` mode and added a cron collision guard so the weekly cron doesn't overwrite specs under active review.

### What Changed

**`src/tiktok/generate_weekly_plan.py`** — Added `--check-plan-status` CLI flag. Reads B3 from Sheet; exits 0 (proceed) if status is idle/rejected/empty/None, exits 78 (GitHub Actions neutral) if review is in progress.

**`.github/workflows/tiktok-weekly-review.yml`** — Rewritten:
- Removed Node.js/Puppeteer setup (rendering moved to Phase D)
- Added "Check plan status" step using `--check-plan-status`
- Gated all downstream steps on `steps.check.outcome == 'success'`
- Uses `--plan-only` flag for plan generation
- Removed `OPENAI_API_KEY` and `GCS_BUCKET_NAME` env vars (not needed for plan-only)

### Design Decision
- Exit code 78 maps to GitHub Actions "neutral" outcome — the workflow shows as grey (skipped), not red (failed)
- Collision guard prevents cron from overwriting specs that a reviewer is actively editing

### File Counts

| Action | Count | Details |
|--------|-------|---------|
| Modified | 2 | `generate_weekly_plan.py` (+`--check-plan-status`), `tiktok-weekly-review.yml` (rewritten for plan-only + collision guard) |
| Modified (docs) | 2 | `ARCHITECTURE.md`, `progress.md` |

## Phase 13C — TikTok Two-Phase Approval: Plan-Level Regen Orchestrator (2026-03-06)

Added `regen_plan.py` — a plan-level regeneration orchestrator that processes reviewer feedback from the Weekly Review tab. When a reviewer sets a carousel's status to "regen" with optional feedback, this script parses the feedback and either applies direct edits or calls Claude for regeneration.

### What Changed

**`src/tiktok/regen_plan.py`** — New file (~310 lines). Core orchestrator with:
- `parse_feedback()` — Regex-based parser supporting: `change hook to "..."`, `change slide N to "..."`, `regen hook`, `regen slide N`, `regen`/empty (full), free-form fallback
- `apply_direct_edit()` — Returns `(success, description)` tuple; failed edits (e.g., slide index out of range) fall through to Claude regen
- `regen_plan()` — Full orchestration: read requests → load plan → parse feedback → apply direct edits → Claude regen (fault-tolerant per-carousel loop) → write Sheet first → reset B5 → save JSON (atomic write) → Slack notification

**`src/shared/apis/claude_api.py`** — Added `regenerate_tiktok_carousel_spec()` method. Loads `prompts/tiktok/regen_plan.md`, builds context with slim taxonomy + kept specs, calls Claude Sonnet with 4096 max_tokens. Returns replacement carousel dict.

**`src/shared/apis/sheets_api.py`** — Added `reset_tiktok_plan_regen_trigger()` method. Writes "idle" to B5 after regen completes.

**`prompts/tiktok/regen_plan.md`** — New prompt template for carousel regen. Template variables: `{{carousel_to_replace}}`, `{{feedback}}`, `{{target}}`, `{{kept_specs}}`, `{{attribute_taxonomy}}`.

**`.github/workflows/tiktok-regen-plan.yml`** — New workflow. Triggered by `repository_dispatch: tiktok-regen-plan` (from Apps Script when B5 = "regen"). Has `git pull --rebase` before regen (plan JSON may have been updated by another runner), `commit-data` after. Concurrency group: `slated-content-engine-tiktok`.

### Key Design Decisions
- **Sheet-first-then-JSON ordering**: Write Sheet before saving plan JSON to prevent divergence if either step fails
- **Fault-tolerant Claude loop**: Per-carousel errors caught and tracked; failures don't block other carousels. Successes and failures reported separately in Slack
- **Direct edit fallback**: If a direct edit fails (e.g., slide index out of range), it falls through to full Claude regen with the original feedback as context
- **B5 reset wrapped in try/except**: A failure resetting the trigger cell doesn't prevent saving the updated plan JSON
- **Guard against list response**: Claude may wrap single-carousel output in an array; `if isinstance(replacement, list): replacement = replacement[0]`

### File Counts

| Action | Count | Details |
|--------|-------|---------|
| New | 3 | `regen_plan.py` (orchestrator), `regen_plan.md` (prompt), `tiktok-regen-plan.yml` (workflow) |
| Modified | 2 | `claude_api.py` (+`regenerate_tiktok_carousel_spec()`), `sheets_api.py` (+`reset_tiktok_plan_regen_trigger()`) |
| Modified (docs) | 2 | `ARCHITECTURE.md` (updated tables), `progress.md` (this entry) |

## Phase 13D+E — TikTok Two-Phase Approval: Content Generation + Apps Script Wiring (2026-03-06)

Split content rendering into a separate step triggered by plan approval (B3=approved). Per-slide AI image generation replaces the old one-shared-background model. Content Queue schema expanded to 17 columns with per-slide `=IMAGE()` previews. Apps Script fully rewritten with 6 triggers and concurrency guards.

### What Changed

**`src/tiktok/generate_carousels.py`** — Major rewrite:
- Per-slide image model: reads `image_prompts` array from carousel spec, generates separate AI image per `{slide_index, prompt}` entry via `_generate_slide_images()`
- Extracted `build_slides_for_render(spec, image_paths_by_index)` for reuse by Phase F's `regen_content.py`
- Tracks `image_gen_failures` per carousel (slides render as text-only on failure)
- Removed old one-shared-background model (`_image_prompt` field no longer referenced)

**`src/tiktok/generate_weekly_plan.py`** — Added `generate_content_from_plan()`:
- New function loads approved plan JSON, renders all specs via `generate_carousels()`, uploads ALL slides to GCS, publishes to Content Queue with per-slide URLs
- Added `--generate-content` CLI flag
- Deleted old broken Steps 11-14 (rendering code that was dead since Phase A)
- GCS upload builds `slide_preview_urls: dict[str, list[str]]` (all URLs, not just first)

**`src/shared/apis/sheets_api.py`** — TikTok Content Queue rewrite:
- `TIKTOK_CQ_HEADERS`: expanded from 14 to 17 columns (A-Q). Cols D-L = per-slide `=IMAGE()` previews (hook + 7 content + CTA). O=Status, P=Feedback, Q=Notes.
- `write_tiktok_content_queue()`: builds 9 `=IMAGE()` formulas from URL list, skips header validation (schema transition safety), surfaces `render_error`, `image_gen_failures`, and `gcs_upload_failed` in Notes
- `read_tiktok_approved_carousels()`: Status moved from col M(12) to O(14), uses FORMULA render option to derive `slide_count` from `=IMAGE()` formulas, range A:Q
- `update_tiktok_content_status()`: Status writes to col O, Notes to col Q, row lookup uses `.strip()` for whitespace safety
- New: `read_tiktok_content_regen_requests()` — reads regen-flagged rows from Content Queue (for Phase F)
- New: `reset_tiktok_content_regen_trigger()` — writes "idle" to R1
- New constant: `TIKTOK_CQ_CELL_REGEN_TRIGGER = "R1"`

**`src/tiktok/publish_content_queue.py`** — Changed `slide_urls` parameter type from `dict[str, str]` to `dict[str, list[str]]` (all slide URLs, not just first).

**`.github/workflows/tiktok-generate-content.yml`** — New workflow:
- Triggered by `repository_dispatch: tiktok-generate-content` (from Apps Script when B3=approved)
- `git pull --rebase` (plan JSON from previous runner), Node.js 22 + Puppeteer setup, `--generate-content` flag
- Concurrency group: `slated-content-engine-tiktok`
- Env: OPENAI_API_KEY, GCS_BUCKET_NAME (for image gen + upload)

**`src/apps-script/tiktok-trigger.gs`** — Full rewrite (6 triggers):
1. Weekly Review B3=`approved` → `tiktok-generate-content` (guarded: blocked while B5≠idle, resets B3 to `pending_review` on block)
2. Weekly Review B5=`regen` → `tiktok-regen-plan`
3. Weekly Review B3=`pending_review` → writes stale indicator to Content Queue S1
4. Content Queue col O all reviewed → `tiktok-promote-and-schedule` (guarded: only if B3=approved)
5. Content Queue R1=`run` → `tiktok-regen-content`
6. Uses `range.getValue()` (not `e.value`) for programmatic `setValue()` compatibility
- `allContentReviewed()` tracks `foundValidRow` — returns false on empty sheets
- Timestamp tracking (B6, R2). Convenience button functions.

**`.github/workflows/tiktok-promote-and-schedule.yml`** — Added `git pull --rebase` step (plan JSON from previous runner).

### Key Design Decisions
- **Schema transition**: `write_tiktok_content_queue` skips `_validate_headers` and relies on `_clear_and_write` overwriting from A1 — old 14-col headers replaced atomically
- **Per-slide images**: `image_prompts` array drives `_generate_slide_images()`. Per-slide failures are non-fatal — slide renders as text-only, tracked in `image_gen_failures`
- **Apps Script concurrency**: B3 approval blocked while B5 regen is in flight (resets B3 to prevent silent no-op). Promote-and-schedule blocked while B3≠approved (prevents scheduling stale renders)
- **`build_slides_for_render` extraction**: Shared function avoids duplicating ~50 lines of slide construction logic between initial render and Phase F re-render

### File Counts

| Action | Count | Details |
|--------|-------|---------|
| New | 1 | `tiktok-generate-content.yml` (workflow) |
| Major rewrite | 2 | `generate_carousels.py` (per-slide images + extracted builder), `tiktok-trigger.gs` (6 triggers + guards) |
| Modified | 4 | `generate_weekly_plan.py` (+`generate_content_from_plan()`, deleted Steps 11-14), `sheets_api.py` (17-col schema + 2 new methods), `publish_content_queue.py` (slide_urls type), `tiktok-promote-and-schedule.yml` (+git pull) |
| Modified (docs) | 2 | `ARCHITECTURE.md` (updated tables/gotchas), `progress.md` (this entry) |

## Phase 13F — TikTok Two-Phase Approval: Image-Level Regen (2026-03-06)

Final phase of the two-phase approval system. Content-level regeneration of AI-generated images for specific slides, triggered from the Content Queue tab.

### What Changed

**`src/tiktok/regen_content.py`** — New file (~250 lines). Content-level regen orchestrator:
- `_parse_regen_status()` — Parses `regen_image_N`, comma-separated targets, or full `regen`
- `_col_position_to_slide_index()` — Translates fixed Content Queue column-position (0=hook, 1-7=content, 8=CTA) to actual slide_index using content_slides length
- `_find_image_prompt()` — Looks up image_prompt entry by slide_index; no-op if slide has no AI image
- `regen_content()` — Full orchestration: read requests → load plan → parse targets → generate new AI images (with feedback appended to prompt) → re-render full carousel via `build_slides_for_render()` + `CarouselAssembler` → upload to GCS with cache-bust `?t=TIMESTAMP` → update Content Queue row → save plan JSON → reset R1 → Slack notification
- Per-carousel error isolation (failures don't block others)

**`src/shared/apis/sheets_api.py`** — Added `update_tiktok_content_row()` method:
- Batch-updates specific cells for a carousel row: Status (O), Notes (Q), and optionally slide preview URLs (D-L with `=IMAGE()` formulas)
- Uses `USER_ENTERED` value input option for formula evaluation
- Row lookup uses `.strip()` for whitespace safety

**`.github/workflows/tiktok-regen-content.yml`** — New workflow:
- Triggered by `repository_dispatch: tiktok-regen-content` (from Apps Script when R1=run)
- `git pull --rebase` + Node.js 22 + Puppeteer (for re-rendering)
- Concurrency group: `slated-content-engine-tiktok`

### Key Design Decisions
- **Image regen only in Phase 2**: Text was approved in Phase 1. Phase 2 regen targets visual output only — no Claude API calls needed, only `ImageGenAPI.generate()`
- **Column-position to slide_index translation**: Fixed CQ layout (0-8) maps to variable carousel structure. Out-of-range positions logged and skipped.
- **No-op for text-only slides**: `regen_image_N` on a slide without an image prompt writes a note and skips — no crash, no silent corruption
- **Feedback modifies prompt**: Reviewer feedback (e.g., "make it brighter") is appended to the existing image prompt. Updated prompt saved to plan JSON for audit trail.
- **Cache-bust for Sheet refresh**: `?t=TIMESTAMP` appended to GCS URLs forces Google Sheets to re-fetch `=IMAGE()` formulas after image replacement
- **Full carousel re-render**: Even if only one slide's image changes, the entire carousel is re-rendered. Reuses existing `build_slides_for_render()` + `CarouselAssembler` with zero changes to rendering code.

### Two-Phase Approval System Complete

All 6 phases are now implemented:
- **A+B**: Plan/render split + workflow updates (plan-only mode, cron collision guard)
- **C**: Plan-level regen (direct edits + Claude regen from Weekly Review feedback)
- **D+E**: Content generation as separate step + Apps Script wiring (per-slide images, 17-col Content Queue, 6 triggers with concurrency guards)
- **F**: Image-level regen (AI image regeneration from Content Queue feedback)

### File Counts

| Action | Count | Details |
|--------|-------|---------|
| New | 2 | `regen_content.py` (orchestrator), `tiktok-regen-content.yml` (workflow) |
| Modified | 1 | `sheets_api.py` (+`update_tiktok_content_row()`) |
| Modified (docs) | 2 | `ARCHITECTURE.md` (updated tables), `progress.md` (this entry) |

### Phase F Fixes (Post-Review)

Three fixes applied after code review:

1. **Per-image error handling** — Individual `image_gen.generate()` calls in the regen loop now wrapped in try/except. Failures tracked in `image_failures` list; surviving images still render. Previously, one failed image generation would crash the entire carousel regen.

2. **Missing carousel note** — When `carousel_id` not found in the plan JSON, `regen_content.py` now calls `sheets.update_tiktok_content_row()` with status `pending_review` and a descriptive note ("Carousel not found in plan JSON — cannot regenerate"), instead of silently skipping.

3. **GCS-down note** — When GCS is unavailable, appends "GCS unavailable — slide previews not updated" to the Notes column, so the reviewer knows why thumbnails didn't refresh.

---

## Phase 13: TikTok Pipeline Audit + Hardening (2026-03-06)

Three rounds of 4-agent code review across the full TikTok workflow, producing 14 + 8 + 8 = 30 fixes total. Key improvements:

### Round 3 Fixes (this session)

1. **Missing `git pull` in weekly review workflow** — `tiktok-weekly-review.yml` was running on stale checkout data, missing analytics committed 30 min earlier by `collect-analytics.yml`. Added `git pull --rebase origin main` step.
2. **Rolling 4-week average included incomplete current week** — `_compute_account_trends` in `weekly_analysis.py` used `range(4)` starting at current week (0-1 days of data on Monday mornings), deflating the average by ~25%. Changed to `range(1, 5)` to use 4 prior completed weeks.
3. **Slide count mismatch accepted silently** — `carousel_assembler.py` `_render_batch` only warned when `render_pin.js` returned fewer slides than requested with `ok: true`. Now raises `CarouselAssemblerError` to prevent index misalignment.
4. **Regen skipped full validation** — `regen_plan.py` only checked `REQUIRED_CAROUSEL_KEYS` on Claude replacements. Now validates `template_family` (hyphen→underscore normalization + allowlist check) and coerces `is_aigc` to bool.
5. **Regen wrote Sheet even when all regens failed** — Wiped reviewer feedback for nothing. Now skips Sheet write + JSON save when `not direct_edits and not claude_successes`.
6. **Photo-forward missing image_prompts not warned** — `generate_weekly_plan.py` validation now warns when `photo_forward` family has empty `image_prompts`.
7. **Logger args swapped in template normalization** — Captured original family name before overwriting so the log shows `'clean-educational' -> 'clean_educational'` instead of the carousel_id.
8. **Overflow slot collision** — `promote_and_schedule.py` overflow logic could place carousels in slots already occupied by other dates' carousels. Added `occupied_slots` tracking dict that checks target slot availability before placing overflow.

### Earlier Fixes (rounds 1-2, same session)

- 12-week rolling window for performance summary (`pull_analytics.py`)
- `scheduled_date` enrichment from plan (`promote_and_schedule.py`)
- GCS upload stop-on-first-failure for index alignment (`generate_weekly_plan.py`)
- PENDING/MANUAL sentinel filter in analytics (`pull_analytics.py`)
- Apps Script `row >= 2` guard, timestamp consolidation (`tiktok-trigger.gs`)
- `is_aigc` boolean coercion in plan validation (`generate_weekly_plan.py`)
- Timezone-consistent failure timestamps (`post_content.py`)
- `is_aigc` forwarding to Publer (`post_content.py`)
- Consistent date boundary exclusion in analysis (`weekly_analysis.py`)

### Technical Debt Tracking

Created `architecture/tiktok-two-phase-approval/technical-debt-and-design-todos.md` with 7 tracked algorithmic/design issues:
1. Composite score scale mismatch (HIGH — fix before ~20 posts)
2. Unbounded performance history (MEDIUM — mitigated by 12-week window fix)
3. Top/bottom performer overlap (LOW — self-resolves at 10+ posts)
4. Partial render index mapping (LOW — mitigated by reject-all strategy)
5. `pin_id` naming for TikTok (LOW — next schema change)
6. Workflow data freshness gap (MEDIUM — mitigated by `git pull` fix)
7. Sheets API rate limiting (MEDIUM — at scale >15 carousels)

### File Counts

| Action | Count | Details |
|--------|-------|---------|
| Modified | 8 | `weekly_analysis.py`, `carousel_assembler.py`, `regen_plan.py`, `generate_weekly_plan.py`, `promote_and_schedule.py`, `pull_analytics.py`, `post_content.py`, `tiktok-trigger.gs` |
| Modified (workflow) | 1 | `tiktok-weekly-review.yml` |
| Modified (test) | 3 | `test_tiktok_carousel_assembler.py`, `test_tiktok_promote_and_schedule.py`, `test_tiktok_validate_plan.py` |
| Modified (docs) | 3 | `ARCHITECTURE.md`, `progress.md`, `technical-debt-and-design-todos.md` (new) |
| Tests | 427 passing |

---

## Hotfix: LLM Response Truncation Detection + max_tokens Increase (2026-03-09)

### Problem
`pinterest-weekly-review` workflow failed: Claude's response hit the `max_tokens=8192` ceiling, producing truncated JSON that failed `_validate_plan_structure()`. Root cause: growing input context (36K input tokens — 71KB strategy doc, 12KB content memory, 13KB weekly analysis) caused more detailed output that exceeded the 8192 output token limit. The prompt also had contradictory instructions ("analyze first" vs "output only JSON"), causing the model to waste tokens on reasoning preamble before the JSON.

### Changes

**Truncation detection (`_call_api()` + `call_gpt5_mini()`):**
- `_call_api()` gains `require_complete` parameter (default `False`). When `True`, raises `ClaudeAPIError` on truncation (`stop_reason == "max_tokens"`). When `False`, logs a warning and returns partial text.
- All JSON-producing callers pass `require_complete=True`: `generate_weekly_plan`, `generate_pin_copy` (fallback), `generate_replacement_posts`, `generate_tiktok_plan`, `generate_carousel_copy` (fallback), `regenerate_tiktok_carousel_spec`.
- Free-text callers (blog posts, analysis, monthly review) use default `False` — truncated text is still usable.
- `call_gpt5_mini()` checks `finish_reason == "length"` and raises `OpenAIChatAPIError`.

**max_tokens increases:**
- `generate_weekly_plan()`: 8192 → 16384
- `generate_tiktok_plan()`: 8192 → 16384
- `run_monthly_review()`: 8192 → 16384
- `generate_blog_post()` weekly-plan type: 8192 → 12288
- `generate_replacement_posts()` cap: 4096 → 8192

**Prompt tightening:**
- Pinterest `weekly_plan.md`: "Do the analysis internally" + reasoning goes in `planning_notes` (max 4 short paragraphs) + explicit no-preamble instruction.
- TikTok `weekly_plan.md`: Added `planning_notes` field as reasoning relief valve with same constraint.

### Files Modified
| File | Change |
|------|--------|
| `src/shared/apis/claude_api.py` | `require_complete` param, truncation detection, max_tokens increases |
| `src/shared/apis/openai_chat_api.py` | `finish_reason` truncation detection |
| `prompts/pinterest/weekly_plan.md` | Reasoning → `planning_notes`, no-preamble instruction |
| `prompts/tiktok/weekly_plan.md` | Added `planning_notes` relief valve |
| `ARCHITECTURE.md` | Updated `claude_api.py` and `openai_chat_api.py` descriptions |
