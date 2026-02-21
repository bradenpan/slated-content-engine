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
