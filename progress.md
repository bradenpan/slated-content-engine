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
