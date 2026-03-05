# TikTok Carousel Pipeline — Approval Flow

---

## Step 1: Weekly Review runs automatically (Monday 6:30am ET)

- `tiktok-weekly-review.yml` fires on cron schedule (30 min after Pinterest)
- Pulls TikTok analytics from Publer (runs earlier at 5:30am via `collect-analytics.yml`)
- Generates weekly performance analysis via Claude
- Updates attribute taxonomy weights (explore/exploit feedback loop)
- Generates 7 TikTok carousel specs via Claude (topic, angle, structure, hook type, template family)
- Renders carousel slide PNGs via Puppeteer (1080x1920)
- Uploads slide images to GCS
- Writes carousel specs to the **Content Queue** tab in the TikTok Google Sheet
- You get a Slack notification: "TikTok plan generated: 7 carousels for week of ..."

## Step 2: You review the carousels

- Open TikTok Google Sheet → **Content Queue** tab
- The Content Queue has 14 columns (A-N):
  - **A:** ID (carousel_id)
  - **B:** Topic
  - **C:** Angle
  - **D:** Structure
  - **E:** Hook Type
  - **F:** Template Family
  - **G:** Hook Text (first slide headline)
  - **H:** Caption (TikTok post caption)
  - **I:** Hashtags
  - **J:** Slide Count
  - **K:** Preview (inline slide image via =IMAGE())
  - **L:** Schedule (posting date)
  - **M:** Status
  - **N:** Notes
- For each carousel, change **column M (Status)** to:
  - `approved` — good to go
  - `rejected` — won't be posted

## Step 3: Approval triggers scheduling

- When ALL rows have a terminal status (`approved` or `rejected`), the Apps Script fires automatically
- Triggers `tiktok-promote-and-schedule.yml` via repository_dispatch
- Reads approved carousels from the Sheet
- Distributes them across 7 days × 3 time slots (morning/afternoon/evening)
- Resolves GCS slide URLs for each carousel
- Writes `carousel-schedule.json`
- Updates Sheet status to "scheduled"
- You get a Slack notification: "7 carousels scheduled for 2026-03-07 to 2026-03-13"

## Step 4: Daily posting (3x daily, automatic)

- `tiktok-daily-post.yml` fires on cron:
  - **Morning:** 10am ET
  - **Afternoon:** 4pm ET
  - **Evening:** 7pm ET
- For each time slot:
  - Loads carousels from the schedule
  - Checks idempotency (skip if already posted)
  - Applies anti-bot jitter (random delay)
  - If `TIKTOK_POSTING_ENABLED=true`: posts via Publer API (import slides → create post)
  - If `TIKTOK_POSTING_ENABLED=false`: sends Slack message with GCS links for manual upload
  - Updates Sheet status to "posted"
  - Logs to content-log.jsonl
- You get a Slack notification: "TikTok morning: Posted 1/1 carousels"

---

## Your touch points: Steps 2 and 3 only.

Everything else is automated. Review the carousels, set statuses, done.

---

## Key differences from Pinterest

| | Pinterest | TikTok |
|---|---|---|
| **Content type** | Blog posts + derived pins | Carousel slides (1080x1920 PNG) |
| **Plan review** | Weekly Review tab with blog topics, pillars, keywords | Content Queue tab with carousel specs |
| **Plan-level regen** | Yes (Step 2.5 — flag blog topics for replacement) | Not yet (Phase 13) |
| **Content-level regen** | Yes (regen_image, regen_copy, regen) | Not yet (Phase 13) |
| **Blog deployment** | Yes (Vercel preview → production) | N/A |
| **Posting** | Direct Pinterest API | Via Publer API |
| **Posting schedule** | 4 pins/day (3 slots) | Up to 3 carousels/day (3 slots) |
| **Feedback loop** | Pillar/board/template performance | Topic/angle/structure/hook_type Bayesian weights |
| **Approval steps** | 4 (plan, content, preview, production) | 1 (content approval only) |

---

## Troubleshooting

- **Carousels show no preview image:** GCS upload may have failed during plan generation. Check the workflow run log.
- **Posting says "manual upload required":** `TIKTOK_POSTING_ENABLED` is not set to `true` in GitHub Secrets.
- **Same carousel posted twice:** Extremely unlikely — idempotency guard checks content-log.jsonl. If it happens, check for PENDING entries in the log.
- **Attribute weights not updating:** The weight update step has `continue-on-error: true`. Check if `performance-summary.json` exists in `data/tiktok/`.
