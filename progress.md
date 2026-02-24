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
