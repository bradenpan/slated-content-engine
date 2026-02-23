# Content Queue Thumbnail Fix — Handoff Document

## The Problem

The Google Sheets Content Queue (the human review interface for the Pinterest automation pipeline) has broken image thumbnails:

1. **Pin rows (column I)**: Show raw GitHub Actions runner paths as plain text (e.g., `/home/runner/work/slated-pinterest-bot/slated-pinterest-bot/data/generated/pins/W8-19.png`) instead of rendered inline images
2. **Blog rows (column I)**: Show nothing — blog thumbnails were never implemented

## Root Cause (Confirmed from workflow logs)

The Google Drive upload fails with this error:

```
<HttpError 403 when requesting https://www.googleapis.com/upload/drive/v3/files?fields=id&alt=json&uploadType=multipart
returned "Service Accounts do not have storage quota. Leverage shared drives
(https://developers.google.com/workspace/drive/api/guides/about-shareddrives),
or use OAuth delegation (http://support.google.com/a/answer/7281227) instead.".
Details: "[{'message': 'Service Accounts do not have storage quota...', 'domain': 'usageLimits', 'reason': 'storageQuotaExceeded'}]">
```

**Result**: 0 out of 28 pin images uploaded. `pin_image_urls` dict is empty. The code falls back to writing the local runner path as plain text in the Sheet.

The service account is in a GCP project under a **personal Gmail account**. The user also has a **Google Workspace account** (separate). There was a deliberate reason the service account was put on the personal account — possibly related to Drive policies — but the user doesn't remember the exact reason.

## Architecture Overview

### How pin thumbnails are supposed to work
1. `generate_pin_content.py` renders pin PNGs to `data/generated/pins/{pin_id}.png` on the GitHub Actions runner
2. `publish_content_queue.py` uploads PNGs to Google Drive folder `pinterest-pipeline-pins` via `drive_api.py`
3. `drive_api.py` sets each file to "anyone with link can view" and returns thumbnail URLs
4. `sheets_api.py` writes `=IMAGE("https://drive.google.com/thumbnail?id={file_id}&sz=w400")` in column I
5. Google Sheets renders the image inline

The upload fails at step 2 because service accounts on personal Gmail don't have Drive storage quota.

### How blog thumbnails work (or don't)
- Blog generation creates MDX files with `heroImage: "/assets/blog/{slug}.jpg"` in frontmatter — this is a relative website path, not a viewable URL
- The actual hero image (stock photo from Unsplash/Pexels) is sourced during PIN generation and saved as `{pin_id}-hero.jpg`
- `sheets_api.py` hardcodes `""` for blog thumbnail column — never implemented

### Key files
- `src/apis/drive_api.py` — Google Drive upload client (this is what fails)
- `src/apis/sheets_api.py` — Google Sheets writer (writes =IMAGE() formulas or fallback)
- `src/publish_content_queue.py` — Orchestrates: load results → upload to Drive → write Sheet
- `src/generate_pin_content.py` — Generates pin copy + images + rendered PNGs
- `src/generate_blog_posts.py` — Generates blog post MDX files
- `src/blog_deployer.py` — Deploys blog posts to goslated.com
- `.github/workflows/generate-content.yml` — The workflow that runs all of this

### Additional bug found: hero image naming mismatch
- `generate_pin_content.py:858` saves stock hero images as `{pin_id}-hero.jpg` (e.g., `W8-01-hero.jpg`)
- `blog_deployer.py:583-587` looks for `{slug}-hero.{ext}` (e.g., `one-pan-lemon-herb-chicken-hero.jpg`)
- These are different strings — the deployer never finds the hero image
- This means blog posts may be deploying to goslated.com WITHOUT their hero images

## Code Changes Already Made (saved to disk, NOT committed)

### 1. `src/apis/sheets_api.py`
- **Pin fallback**: Line 353 changed from `thumbnail = str(pin.get("image_path", ""))` to `thumbnail = ""` — stops writing useless local paths
- **Blog thumbnail support**: Added `blog_image_urls` parameter to `write_content_queue()`. When provided, writes `=IMAGE()` formulas for blog rows

### 2. `src/publish_content_queue.py`
- Full rewrite saved. Added `_upload_blog_hero_images()` and `_find_hero_image()` functions
- Added `blog_image_urls` passthrough to `sheets.write_content_queue()`
- Better Drive error logging with specific diagnostic messages
- Row heights set for blog rows with thumbnails too

### 3. `src/generate_pin_content.py`
- After downloading a hero image as `{pin_id}-hero.{ext}`, also saves a copy as `{slug}-hero.{ext}` so blog_deployer.py can find it

## What Still Needs to Be Done

### Critical: Fix the Drive storage quota issue
The core problem is that service accounts on personal Gmail can't upload to Drive. Possible solutions to research and evaluate:

1. **Shared Drives** — Upload to a Shared Drive in the user's Google Workspace. Need to research: can a service account from a personal GCP project access a Workspace Shared Drive?
2. **OAuth delegation** — Impersonate a real user. Need to research: does this work cross-org (personal GCP → Workspace user)?
3. **Google Cloud Storage (GCS)** — Use a GCS bucket instead of Drive. The service account already has GCP access. Need public URLs for =IMAGE().
4. **Move the service account to Workspace** — Create a new GCP project under the Workspace org. May fix the quota issue. Need to research implications.
5. **Alternative image hosting** — Imgur, Cloudflare R2, etc.
6. **Deploy images to goslated.com** — Pin images could go to the Vercel-deployed site and use those URLs.

Each option needs: exact implementation steps, effort estimate, ongoing cost, reliability assessment, and confirmation that it works for Google Sheets =IMAGE() formulas (images must be publicly accessible).

**Important**: The user wants a RECOMMENDATION, not just a list. Research the options, evaluate them, and present a recommendation with clear reasoning.

### After Drive fix is resolved
- Verify the three code changes already made are correct
- Test end-to-end (or at least verify the code paths make sense)
- Commit all changes

## Environment
- Platform: Windows 11, bash shell
- Python 3.11 on GitHub Actions (ubuntu-latest)
- The `.env` file contains live API keys — NEVER read it. Use `.env.example` for reference.
- `data/token-store.json` also contains secrets — never read it.

## User Preferences
- Do NOT make assumptions. Ask questions when uncertain.
- Provide evidence for claims (specific file paths, line numbers, log output).
- When presenting options, include real pros/cons with enough detail to make a decision.
- Present a recommendation, don't just list options.
