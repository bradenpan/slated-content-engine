# Pinterest Pipeline — Progress Tracker

## Overview

Fully automated Pinterest content pipeline for Slated (family meal planning iOS app). Handles the entire lifecycle: weekly content planning, blog post generation, pin creation, deployment, daily posting, and performance analysis — with human approval gates at key decision points.

### Architecture

```
Plan → Generate → Review → Deploy → Post → Analyze → (feeds next Plan)
```

**Orchestration:** GitHub Actions (cron + webhook triggers)
**LLM:** Claude API (Sonnet for routine, Opus for deep analysis, Haiku for image evaluation)
**Content:** Blog posts (MDX) + pin images (stock/AI/template) + pin copy
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
- `generate_pin_content.py` — Pin copy generation + image sourcing (3-tier) + assembly
- `pin_assembler.py` — HTML/CSS template → PNG renderer via Puppeteer (5 template types, 3 variants each)
- `publish_content_queue.py` — Drive upload + Sheet write + Slack notification
- `blog_deployer.py` — GitHub commit to goslated.com → Vercel deploy → URL verification → pin schedule creation
- `post_pins.py` — Daily Pinterest API posting with anti-bot jitter, idempotency, retry logic
- `weekly_analysis.py` — Claude-driven weekly performance analysis
- `monthly_review.py` — Claude Opus deep monthly strategy review
- `pull_analytics.py` — Pinterest Analytics API pull (impressions, saves, clicks, outbound)

**API Wrappers (src/apis/)**
- `claude_api.py` — Claude Sonnet/Opus/Haiku with prompt templates, vision support, token/cost tracking
- `pinterest_api.py` — Pinterest v5 REST API (pins, boards, analytics)
- `sheets_api.py` — Google Sheets (Weekly Review, Content Queue, Post Log, Dashboard tabs)
- `drive_api.py` — Google Drive (pin image upload for inline Sheet previews)
- `github_api.py` — GitHub Git Data API (atomic multi-file blog commits)
- `image_stock.py` — Unsplash + Pexels stock photo search/download/dedup
- `image_gen.py` — OpenAI DALL-E / Replicate Flux Pro image generation
- `slack_notify.py` — Slack webhook notifications (Block Kit)
- `token_manager.py` — Pinterest OAuth 2.0 token auto-refresh

**Workflows (.github/workflows/)**
- `weekly-review.yml`, `generate-content.yml`, `deploy-and-schedule.yml`, `promote-and-schedule.yml`
- `daily-post-morning.yml`, `daily-post-afternoon.yml`, `daily-post-evening.yml`
- `monthly-review.yml`

**Prompt Templates (prompts/)** — 12 templates covering planning, blog generation, pin copy, image sourcing, image quality, and performance analysis

**Strategy (strategy/)** — Content strategy, brand voice, board structure, keyword lists, seasonal calendar, CTA variants, product overview

**Pin Templates (templates/pins/)** — 5 template types (recipe, tip, listicle, problem-solution, infographic) × 3 visual variants each, rendered via Puppeteer

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

## Phase 7: Content Queue Thumbnail Fixes (In Progress)

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

The service account is in a GCP project under a personal Gmail account. Service accounts on personal Gmail cannot upload to their own Drive space. The code falls back to writing the useless local runner path (`sheets_api.py:353`).

### Additional Bug Found: Hero Image Naming Mismatch

- `generate_pin_content.py:858` saves stock hero images as `{pin_id}-hero.jpg` (e.g., `W8-01-hero.jpg`)
- `blog_deployer.py:583-587` looks for `{slug}-hero.{ext}` (e.g., `one-pan-lemon-herb-chicken-hero.jpg`)
- Pin IDs and slugs are different strings, so the deployer never finds hero images — blog posts may deploy to goslated.com without their hero images

### Code Changes Made (saved to disk, NOT committed)

#### 1. `src/apis/sheets_api.py`
- **Pin fallback fix**: Changed line 353 from `thumbnail = str(pin.get("image_path", ""))` to `thumbnail = ""` — stops writing useless local runner paths when Drive upload fails
- **Blog thumbnail support**: Added `blog_image_urls` parameter to `write_content_queue()`. When provided, writes `=IMAGE()` formulas for blog rows in column I

#### 2. `src/publish_content_queue.py`
- Added `_upload_blog_hero_images()` function — uploads blog hero images to Drive for Sheet preview
- Added `_find_hero_image()` helper — locates hero images by slug or pin_id naming
- Passes `blog_image_urls` to `sheets.write_content_queue()`
- Better Drive error logging with specific diagnostic messages
- Sets row heights for blog rows that have thumbnails (150px)

#### 3. `src/generate_pin_content.py`
- After downloading a hero image as `{pin_id}-hero.{ext}`, also saves a copy as `{slug}-hero.{ext}` — fixes the naming mismatch so `blog_deployer.py` can find hero images

### Still Needs to Be Done

- **Fix the Drive storage quota issue** — The core blocker. Need to replace Google Drive with an alternative that works with service accounts on personal Gmail. Options under evaluation: Google Cloud Storage bucket, Shared Drive via Workspace, alternative image hosting. See `HANDOFF.md` for full details.
- Test and commit code changes after Drive fix is resolved
