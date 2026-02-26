# Post-Launch Operations Guide: Pipeline Simplification

After merging `pipeline-simplification` to `main`, follow this guide to complete setup and operate the pipeline going forward.

---

## Section 1: Immediate Post-Merge Actions

These steps MUST be completed right after merging to main. The pipeline will not work correctly until they are done.

### 1.1 Update the Apps Script in Google Sheets

The Apps Script has changed: new trigger cells (B5 for plan regen, N1 for content regen instead of O1), and a new `runPlanRegen()` button function. You must copy the updated script into your Google Sheet.

**Steps:**

1. Open your Google Sheet (the one with the Weekly Review, Content Queue, Post Log, and Dashboard tabs).
2. Go to **Extensions > Apps Script**. This opens the script editor in a new tab.
3. In the script editor, you will see a file called `Code.gs` (or whatever you named it during initial setup).
4. **Select all** the existing code in that file and **delete it**.
5. Open the file `src/apps-script/trigger.gs` from the repository (on the `main` branch, after merging).
6. **Copy the entire contents** of `trigger.gs` and **paste** it into the Apps Script editor, replacing everything.
7. Click the **Save** button (floppy disk icon) or press Ctrl+S.
8. Verify the script saved without errors -- the editor should not show any red error indicators.

**What changed in the script:**
- Cell B5 on the Weekly Review tab now triggers `regen-plan` (plan-level regen -- NEW).
- Cell N1 on the Content Queue tab triggers `regen-content` (was O1, shifted because Column M was removed).
- The `runPlanRegen()` function was added for the "Run Plan Regen" button drawing.
- The `runRegen()` function now writes to N1 instead of O1.
- `use_ai_image` is still in the `terminal` status list in `allContentReviewed()` for backwards compatibility with any in-flight Content Queues.

**Do NOT change the installable trigger setup** -- it should still be pointed at `onSheetEdit` with "On edit" event type. That has not changed.

### 1.2 (Optional) Add a Plan Regen Button to the Weekly Review Tab

To make plan regen easy to trigger from the Sheet:

1. In the Weekly Review tab, go to **Insert > Drawing**.
2. Create a simple button shape (e.g., a rounded rectangle with the text "Run Plan Regen").
3. Click **Save and Close**.
4. Click the drawing, then click the three dots in the upper right, then **Assign script**.
5. Type `runPlanRegen` (no parentheses) and click OK.

Now clicking this button will set B5 to "regen" and trigger the plan regen workflow.

### 1.3 Verify GitHub Secrets

The `pipeline-simplification` branch uses GPT-5 Mini for pin copy and image prompt generation. Verify these secrets exist in your GitHub repo (Settings > Secrets and variables > Actions):

- `OPENAI_API_KEY` -- Required for GPT-5 Mini calls. If this secret is missing or expired, the pipeline will fall back to Claude Sonnet (more expensive but functional).
- All other existing secrets should remain unchanged: `ANTHROPIC_API_KEY`, `PINTEREST_*`, `GOOGLE_SHEETS_CREDENTIALS_JSON`, `GOOGLE_SHEET_ID`, `GOOGLE_SHEET_URL`, `SLACK_WEBHOOK_URL`, `GOSLATED_REPO`, `GOSLATED_GITHUB_TOKEN`, `GCS_BUCKET_NAME`.

No new secrets were added beyond `OPENAI_API_KEY` (which was already present in the workflows before this merge).

### 1.4 Handle In-Flight Content

If there is a Content Queue from the previous week that has not finished its cycle:

- **Rows with `use_ai_image` status** will still work. The system treats `use_ai_image` as equivalent to `approved` for deployment purposes. This is a backwards-compatibility alias and will not be generated for new weeks.
- **If the Content Queue still has 13 columns (A-M including the old "AI Image" column):** The current week's content will be fine -- it was generated under the old pipeline. Let it finish its cycle normally. The next weekly plan will generate a 12-column Content Queue (A-L).
- **Do not manually re-run content generation for the current week.** Let the current week complete, then the next Monday's weekly review will use the new pipeline.

### 1.5 First Run Verification

After the next Monday's Weekly Review workflow runs (6 AM ET, automatic via cron), verify:

1. The Weekly Review tab has a row 5 with `PLAN REGEN | idle` (cells A5 and B5).
2. Blog post rows in the plan have Status (column F) and Feedback (column G) columns.
3. No `image_source_tier` appears anywhere in the plan.

After you approve the plan and content generates, verify:

1. The Content Queue has 12 columns: A (ID) through L (Feedback). No Column M "AI Image".
2. Cells M1:N1 show `Regen -> | idle`.
3. All pin images are listed as "AI generated" in the Notes column (column K).

---

## Section 2: Weekly Pipeline Operations -- Step by Step

This is the complete weekly lifecycle, from Monday morning plan generation through the following week.

### Stage 1: Weekly Plan Generation

- **Trigger:** Automatic. Cron runs every Monday at 6:00 AM ET (11:00 UTC). Workflow: `weekly-review.yml`.
- **Can also trigger manually:** Go to GitHub Actions > "Weekly Review" > Run workflow.
- **What it does:**
  1. Pulls Pinterest analytics for the past week.
  2. Generates a content memory summary (no LLM call -- pure computation).
  3. Runs weekly performance analysis via Claude Sonnet.
  4. Generates the weekly content plan (8-10 blog posts + derived pins) via Claude Sonnet, reading your content strategy, performance data, seasonal context, and content memory.
  5. Writes the plan to the **Weekly Review** tab in Google Sheets.
  6. Sends a Slack notification that the plan is ready for review.
  7. Commits updated data/analytics files back to the repo.
- **How to verify:** Open the Weekly Review tab. You should see:
  - Row 1: "Pinterest Weekly Review" with the date.
  - Row 3: `STATUS | pending_review`.
  - Row 4: `PRODUCTION | (blank or previous status)`.
  - Row 5: `PLAN REGEN | idle`.
  - Performance summary and analysis sections.
  - A "CONTENT PLAN" section with blog post rows (columns: ID, Type, Topic, Pillar, Keywords, Status, Feedback) and pin rows.
- **If it fails:** Check the GitHub Actions run log. Also check Slack -- a failure notification is sent automatically. You can re-run the workflow manually from GitHub Actions.

### Stage 2: Plan Review in the Weekly Review Sheet

- **Trigger:** Manual. You review the plan.
- **What to do:**
  1. Open the Weekly Review tab.
  2. Review the blog post topics, pillars, and keywords.
  3. Review the pin assignments (topics, boards, schedules).
  4. If everything looks good, skip to Stage 4 (Plan Approval).
  5. If some blog posts need replacement, go to Stage 3 (Plan-Level Regen).

### Stage 3: Plan-Level Regen (NEW)

Use this if you want to replace specific blog post topics BEFORE content generation runs. This is the time to catch bad topics, duplicates, or off-strategy posts.

- **Trigger:** Manual, from the Google Sheet.
- **When to use:** During plan review (Stage 2), before you approve the plan (B3 = "approved").
- **Steps:**
  1. In the Weekly Review tab, find the blog post rows under "CONTENT PLAN".
  2. For each blog post you want replaced, set its **Status** column (column F) to `regen`.
  3. Optionally, write feedback in the **Feedback** column (column G) explaining what to change. Example: "too similar to last week's chicken recipe" or "need something more seasonal for spring".
  4. Leave blog posts you are happy with as-is (blank Status = approved by default).
  5. Click the **Run Plan Regen** button (if you set one up in step 1.2), OR manually set cell **B5** to `regen`.
  6. Wait for the workflow to complete (typically 2-5 minutes). You will get a Slack notification when it finishes.
  7. The Weekly Review tab will be refreshed with the updated plan. Replaced posts will have new topics, and their derived pins will also be updated.
  8. B5 will automatically reset to "idle".
  9. Review the updated plan again. If you need more changes, repeat this process.
- **Important timing note:** Plan regen is designed for BEFORE content generation. If you trigger it after B3 = "approved" has already run content generation, the updated plan will not retroactively change already-generated content. You would need to re-approve B3 to regenerate content from the updated plan.
- **If it fails:** Check the GitHub Actions run log for "Regenerate Weekly Plan". The Slack failure notification will include a link to the run. B5 will be reset to "idle" even on failure.

### Stage 4: Plan Approval

- **Trigger:** Manual. You set B3 = "approved" in the Weekly Review tab.
- **What happens:** The Apps Script detects the edit and dispatches the `generate-content` event to GitHub Actions.
- **How to verify:** Check GitHub Actions -- the "Generate Content" workflow should appear as "queued" or "in progress" within 30 seconds.

### Stage 5: Content Generation

- **Trigger:** Automatic, triggered by Stage 4.
- **Workflow:** `generate-content.yml`. Timeout: 45 minutes.
- **What it does:**
  1. Generates all blog posts from the approved plan (MDX files with frontmatter).
  2. Generates pin content: titles, descriptions, alt text, and text overlays via GPT-5 Mini (with Claude Sonnet fallback).
  3. Generates AI image prompts via GPT-5 Mini (with Claude Sonnet fallback).
  4. Generates AI images via gpt-image-1.5.
  5. Renders final pin PNGs using Puppeteer (HTML/CSS templates + hero images + text overlays).
  6. Commits generated content to the repo.
  7. Uploads pin images and blog hero images to GCS (or Google Drive as fallback) for inline Sheet preview.
  8. Writes the **Content Queue** tab with all generated items, IMAGE() formulas for thumbnails, and quality notes.
  9. Sends a Slack notification that content is ready for review.
- **How to verify:** Open the Content Queue tab. You should see:
  - Header row: ID, Type, Title, Description, Board, Blog URL, Schedule, Pillar, Thumbnail, Status, Notes, Feedback (12 columns, A-L).
  - Blog rows at the top (type = "blog"), with hero image thumbnails.
  - Pin rows below (type = "pin"), with rendered pin image thumbnails.
  - All rows have Status = "pending_review".
  - Notes column shows "AI generated" (or "AI generated (retry N)" if retries were needed).
  - Cells M1:N1 show "Regen -> | idle".
- **If it fails:** Check the GitHub Actions run log for "Generate Content". Common failure causes:
  - GPT-5 Mini API timeout or rate limit (Claude fallback should handle this -- check logs for "falling back to Claude" messages).
  - Image generation failures (gpt-image-1.5 API issues).
  - GCS upload failures (pin images won't show thumbnails, but content is still generated).

### Stage 6: Content Review in the Content Queue

- **Trigger:** Manual. You review the generated content.
- **What to do:**
  1. Open the Content Queue tab.
  2. Review each blog post: title, description, hero image thumbnail.
  3. Review each pin: title, description, board assignment, schedule, thumbnail image.
  4. For each item, set the **Status** column (column J) to one of:
     - `approved` -- good to go.
     - `rejected` -- do not deploy/post this item.
     - `regen` -- regenerate this item (go to Stage 7).
     - `regen_image` -- regenerate only the image.
     - `regen_copy` -- regenerate only the text (title, description, alt text).
  5. If you flag items for regen, go to Stage 7 before completing approval.

### Stage 7: Content-Level Regen

Use this if specific pins or blog images need regeneration after content generation.

- **Trigger:** Manual, from the Google Sheet.
- **Steps:**
  1. In the Content Queue, set the **Status** (column J) of items to regenerate:
     - `regen` -- regenerate both image and copy.
     - `regen_image` -- regenerate only the image.
     - `regen_copy` -- regenerate only the copy (pin text; not available for blog posts).
  2. Optionally, write feedback in the **Feedback** column (column L). Example: "image too dark" or "title doesn't match the blog topic".
  3. Click the **Run Regen** button in the Content Queue (if one exists), OR set cell **N1** to `run`.
  4. Wait for the workflow to complete. You will get a Slack notification.
  5. Regenerated items will have their Status reset to `pending_review` with updated thumbnails and/or text.
  6. Review the regenerated items and set their Status to `approved` or repeat the regen cycle.
- **Note on blog copy regen:** Blog body text lives in MDX files and cannot be regenerated through the Content Queue. Only blog hero image regen is supported. If you need to change blog copy, you would need to manually edit the MDX file or re-run full content generation.
- **If it fails:** Check the GitHub Actions run log for "Regenerate Content".

### Stage 8: Content Approval (Triggers Preview Deploy)

- **Trigger:** Automatic, when ALL Content Queue rows have a terminal status.
- **Terminal statuses:** `approved`, `rejected`, `use_ai_image` (backwards compat).
- **What happens:** When you set the last pending item to `approved` or `rejected`, the Apps Script detects that all rows are reviewed and dispatches the `deploy-to-preview` event.
- **Workflow:** `deploy-and-schedule.yml`.
- **What it does:**
  1. Reads approved blog posts and pins from the Content Queue.
  2. Commits approved blog post MDX files and hero images to the `develop` branch of the goslated.com repository.
  3. Vercel auto-creates a preview deployment from the develop branch.
  4. Writes `PRODUCTION | pending_review` to cell B4 in the Weekly Review tab, with a note to check the Vercel preview.
  5. Sends a Slack notification with instructions to review the preview and approve for production.
- **How to verify:**
  - Check the Weekly Review tab: row 4 should show `PRODUCTION | pending_review`.
  - Check your Vercel dashboard for a preview deployment on the develop branch.
  - Visit the preview URL and verify blog posts look correct (no duplicate H1 titles, images load, content reads well).
- **If it fails:** Check the GitHub Actions run log for "Deploy to Preview".

### Stage 9: Production Promotion + Pin Scheduling

- **Trigger:** Manual. You set B4 = "approved" in the Weekly Review tab.
- **Workflow:** `promote-and-schedule.yml`.
- **What it does:**
  1. Merges the `develop` branch into `main` on goslated.com, triggering Vercel production deploy.
  2. Verifies all blog post URLs are live on https://goslated.com/blog/{slug} (retries for up to 3 minutes).
  3. Creates the pin posting schedule (`data/pin-schedule.json`) from approved pins.
  4. Appends entries to `data/content-log.jsonl` for analytics tracking.
  5. Updates the Sheet deploy status to "deployed".
  6. Sends a Slack notification confirming content is live.
- **How to verify:**
  - Visit https://goslated.com/blog and confirm new posts are visible.
  - Check the Slack notification for the count of verified blogs and scheduled pins.
  - Check that `data/pin-schedule.json` exists in the repo with the correct pins and schedule dates.
- **If it fails:** Check the GitHub Actions run log for "Promote to Production & Schedule Pins". Common issues:
  - Vercel deployment taking longer than expected (URL verification timeout).
  - Merge conflicts on the goslated.com repo (rare -- this should be clean if only the pipeline writes to develop).

### Stage 10: Daily Pin Posting

- **Trigger:** Automatic via cron, daily.
- **Schedule:**
  - Morning: 10:00 AM ET (15:00 UTC) -- 1 pin. Workflow: `daily-post-morning.yml`.
  - Afternoon: 3:00 PM ET (20:00 UTC) -- 1 pin. Workflow: `daily-post-afternoon.yml`.
  - Evening: 8:00 PM ET (01:00 UTC) -- 2 pins. Workflow: `daily-post-evening.yml`.
- **What it does:**
  1. Reads `data/pin-schedule.json` for pins matching today's date and the current time slot.
  2. Downloads the pin image from GCS/Drive.
  3. Posts the pin to Pinterest via the Pinterest API, with the correct board, title, description, alt text, and link to the blog post.
  4. Logs the result (success or failure) to the Post Log tab in Google Sheets.
  5. Commits updated data files to the repo.
- **How to verify:** Check the Post Log tab in Google Sheets for new entries. Verify the status is "posted" with a Pinterest pin ID.
- **If it fails:** Check the GitHub Actions run log for the specific daily post workflow. Common issues:
  - Pinterest API rate limits.
  - Expired Pinterest access token (the token manager refreshes it, but if the refresh token itself is expired, manual intervention is needed).
  - Pin image URL no longer accessible (GCS bucket permissions, Drive sharing).

### Stage 11: Weekly Review + Analytics

- **Trigger:** Automatic. The next Monday's Weekly Review workflow (Stage 1) pulls analytics for the previous week and generates the next plan.
- **Monthly review:** Runs automatically on the first Monday of each month at 4:00 AM ET (before the weekly review). Uses Claude Opus for deeper strategic analysis: pillar performance, keyword strategy, board architecture, posting cadence, template effectiveness, and strategy update recommendations. Workflow: `monthly-review.yml`.

---

## Section 3: How to Trigger Regeneration

Two types of regeneration exist. They operate at different stages of the pipeline and affect different things.

### Plan-Level Regen (NEW)

**Purpose:** Replace blog post topics in the weekly plan BEFORE content is generated. This swaps out the plan entry and all its derived pin assignments.

**When to use:**
- During plan review (between Stages 1 and 4).
- Before you set B3 = "approved".
- When a blog topic is off-strategy, too similar to a recent post, not seasonal enough, or just not right.

**Step-by-step:**

1. Open the **Weekly Review** tab in Google Sheets.
2. Scroll to the "CONTENT PLAN" section. Find the blog post rows (they have columns: ID, Type, Topic, Pillar, Keywords, Status, Feedback).
3. For each blog post you want replaced:
   - Set the **Status** column (column F) to `regen`.
   - Optionally fill in the **Feedback** column (column G) with specific guidance. Examples:
     - "too similar to W8-P03, need a different angle"
     - "need something about spring grilling instead"
     - "this pillar is over-represented this week, swap for pillar 3"
4. Leave all other blog posts with a blank Status (blank = keep as-is).
5. Trigger the regen in one of two ways:
   - **Button:** Click the "Run Plan Regen" button drawing (if you set one up).
   - **Manual cell edit:** Set cell **B5** to `regen`.
6. The `regen-plan` GitHub Actions workflow will run (typically 2-5 minutes).
7. When complete:
   - The Weekly Review tab will refresh with updated blog posts and pins.
   - Replaced posts will have new topics. Their derived pins will also be new.
   - B5 will automatically reset to "idle".
   - A Slack notification will summarize what was replaced.
8. Review the updated plan. If you need more changes, repeat from step 3.
9. When satisfied, proceed to plan approval (B3 = "approved").

**What happens behind the scenes:**
- `regen_weekly_plan.py` reads the regen requests from the Sheet.
- It loads the current weekly plan JSON from `data/weekly-plan-YYYY-MM-DD.json`.
- It identifies the flagged posts and all their derived pins.
- It calls Claude to generate replacement posts/pins, incorporating your feedback.
- It splices the replacements into the plan and saves the updated JSON.
- It re-writes the Weekly Review sheet (preserving B3 and B4 values).
- It resets B5 to "idle" and sends a Slack notification.

### Content-Level Regen (Existing, Simplified)

**Purpose:** Regenerate specific pin images, pin copy, or blog hero images AFTER content has been generated. This does not change blog post body text.

**When to use:**
- During content review (between Stages 5 and 8).
- After content generation has populated the Content Queue.
- When a pin image is low quality, text is wrong, or a blog hero image does not fit.

**Step-by-step:**

1. Open the **Content Queue** tab in Google Sheets.
2. For each item you want regenerated, set the **Status** column (column J) to one of:
   - `regen` -- regenerate both image and copy.
   - `regen_image` -- regenerate only the image.
   - `regen_copy` -- regenerate only the copy (title, description, alt text, text overlay). Not available for blog posts.
3. Optionally fill in the **Feedback** column (column L) with specific guidance. Examples:
   - "image is too dark, needs brighter colors"
   - "title should mention 'weeknight' not 'weekend'"
   - "wrong cuisine -- this should be Italian not Asian"
4. Trigger the regen in one of two ways:
   - **Button:** Click the "Run Regen" button drawing in the Content Queue (if one exists).
   - **Manual cell edit:** Set cell **N1** to `run`.
5. The `regen-content` GitHub Actions workflow will run (may take 5-15 minutes depending on how many items need regen).
6. When complete:
   - Regenerated items will have their Status reset to `pending_review`.
   - Thumbnails and/or text will be updated in-place.
   - Feedback column will be cleared for successfully regenerated items.
   - A Slack notification will summarize results.
7. Review the regenerated items and set their Status to `approved` or `rejected`.
8. If you need more changes, repeat the regen cycle.
9. Once all items have terminal statuses, the deploy-to-preview workflow triggers automatically.

**Regen types explained:**

| Status value | Image regenerated? | Copy regenerated? | Notes |
|---|---|---|---|
| `regen` | Yes | Yes (pins only) | Full regeneration. Blog posts get image only. |
| `regen_image` | Yes | No | New AI image, existing text preserved. |
| `regen_copy` | No | Yes | New text, existing image preserved. Pins only -- not available for blogs. |

---

## Section 4: What Changed (Quick Reference)

These are the key differences from the previous pipeline version:

1. **No more stock photos.** All images (pin heroes and blog heroes) are AI-generated via gpt-image-1.5. Stock photo APIs (Unsplash, Pexels) are no longer called during content generation. The `UNSPLASH_ACCESS_KEY` and `PEXELS_API_KEY` secrets are still present in some workflow files for backwards compatibility but are not used by the generation code.

2. **No more Column M (AI Image) in the Content Queue.** Previously, the Content Queue had a 13th column showing an AI-generated comparison image alongside the stock photo. Since all images are now AI-generated, there is only one image per item, shown in column I (Thumbnail). The Content Queue is now 12 columns (A-L).

3. **No more `use_ai_image` review step.** Previously, reviewers could set an item's status to `use_ai_image` to swap the stock photo for the AI alternative. Since all images are AI from the start, this status is no longer generated. It is still accepted as a terminal status for backwards compatibility with any in-flight Content Queues.

4. **Pin copy and image prompt generation now use GPT-5 Mini.** The `generate_pin_copy()` and `generate_image_prompt()` methods in `claude_api.py` now call GPT-5 Mini first (via the OpenAI API), with automatic fallback to Claude Sonnet if the OpenAI call fails. This is approximately 10x cheaper for these routine generation tasks. Check workflow logs for "falling back to Claude" warnings if you suspect GPT-5 Mini issues.

5. **Blog posts no longer have duplicate H1 headers.** The blog prompt templates have been updated to not include `# {Title}` in the body, and `blog_generator.py` has a safety net that strips any H1 matching the frontmatter title. Existing blog posts on goslated.com are not affected -- only newly generated posts.

6. **New plan-level regen capability.** You can now flag individual blog posts for regeneration during plan review (before content generation), provide feedback, and get replacement topics. See Section 3 for full instructions.

7. **Regen trigger column shifted.** The Content Queue regen trigger moved from cells N1:O1 to M1:N1 (because Column M was removed). The Apps Script has been updated to match.

---

## Section 5: Troubleshooting

### GPT-5 Mini Failures

**Symptoms:** Content generation takes longer than usual, or you see "falling back to Claude Sonnet" in the workflow logs.

**What to check:**
1. Go to GitHub Actions > the relevant workflow run > expand the step logs.
2. Search for "falling back to Claude" or "OpenAI" in the logs.
3. If you see fallback messages, the content was still generated successfully using Claude Sonnet. No action needed -- it is just more expensive.

**Possible causes:**
- `OPENAI_API_KEY` secret is missing, expired, or has billing issues.
- OpenAI API is experiencing an outage or rate limiting.
- Network timeout on the GitHub Actions runner.

**Resolution:**
- If the key is invalid, update `OPENAI_API_KEY` in GitHub repo secrets (Settings > Secrets and variables > Actions).
- If OpenAI is down, the fallback to Claude handles it automatically. No manual intervention needed.

### Plan Regen Trigger Not Firing

**Symptoms:** You set B5 to "regen" but no workflow runs in GitHub Actions.

**What to check:**
1. Verify you updated the Apps Script (Section 1.1). The old script did not have a B5 watcher.
2. Verify the installable trigger is set up:
   - In the Apps Script editor, click the clock icon (Triggers) in the left sidebar.
   - Confirm there is a trigger for `onSheetEdit` with event type "On edit".
   - If missing, add one: click "Add Trigger" > Function: `onSheetEdit` > Event type: "On edit".
3. Verify the `GITHUB_TOKEN` script property is set:
   - In the Apps Script editor, click the gear icon (Project Settings) in the left sidebar.
   - Scroll to "Script Properties".
   - Confirm `GITHUB_TOKEN` exists with a valid GitHub PAT that has `repo` scope.
4. Check the Apps Script execution log:
   - In the Apps Script editor, click "Executions" in the left sidebar.
   - Look for recent executions of `onSheetEdit` and check for errors.

### Content Queue Column Mismatch

**Symptoms:** Content Queue has 13 columns (old layout with AI Image column), or regen trigger is in the wrong place.

**What to check:**
1. If this is a Content Queue from before the merge, it is expected to have the old layout. Let it complete its cycle normally.
2. If this is a NEW Content Queue (generated after the merge) and it has the wrong number of columns, verify that the `main` branch has the merged `pipeline-simplification` code:
   - Check `src/apis/sheets_api.py` -- the `CQ_COL_FEEDBACK` constant should be index 11 (column L), and there should be no `CQ_COL_AI_IMAGE` constant.
   - Check `src/publish_content_queue.py` -- the `write_content_queue()` call should not pass `ai_image_urls`.

**Resolution:** If the merge was incomplete or had conflicts, re-merge the branch cleanly.

### Image Generation Failures

**Symptoms:** Pins show no thumbnail in the Content Queue, or the Notes column says something about image failure.

**What to check:**
1. Check the "Generate Content" workflow logs for image generation errors.
2. Look for "gpt-image-1.5" errors or timeout messages.
3. Check if GCS upload succeeded (look for "GCS upload" or "upload" messages in the logs).

**Possible causes:**
- OpenAI image generation API is experiencing issues.
- The image prompt was too long or contained prohibited content.
- GCS bucket permissions changed or the bucket does not exist.

**Resolution:**
- If image generation failed for a few pins, use content-level regen (`regen_image`) to retry those specific items.
- If GCS upload failed but images were generated, the images are stored in the repo at `data/generated/pins/`. The next regen or manual workflow run can re-upload them.
- If the GCS bucket is misconfigured, check the `GCS_BUCKET_NAME` secret and verify the service account has write access.

### Blog Deployment Failures

**Symptoms:** Blog posts do not appear on goslated.com after promotion, or the Slack notification reports verification failures.

**What to check:**
1. Check the "Promote to Production & Schedule Pins" workflow logs.
2. Look for merge errors (develop -> main on goslated.com repo).
3. Look for verification timeout messages.
4. Check the Vercel dashboard for the goslated.com project -- is the production deployment succeeding?

**Possible causes:**
- Merge conflict on the goslated.com repo (someone else pushed directly to main).
- Vercel deployment failed (build error in the Next.js/Astro site).
- Vercel deployment took longer than 3 minutes (the verification timeout).
- `GOSLATED_GITHUB_TOKEN` or `GOSLATED_REPO` secrets are incorrect.

**Resolution:**
- If the merge failed, manually resolve conflicts on the goslated.com repo and re-run the promote workflow.
- If Vercel deployment failed, check the Vercel dashboard for build errors. Fix the site and re-deploy.
- If verification timed out but the site eventually came up, the blog posts are live -- the pins just may not have been scheduled. Re-run the promote workflow or manually trigger "Promote to Production & Schedule Pins" from GitHub Actions.

### Pinterest Posting Failures

**Symptoms:** Post Log tab shows "failed" status for pins, or pins are not appearing on Pinterest boards.

**What to check:**
1. Check the daily post workflow logs (morning/afternoon/evening).
2. Look for Pinterest API error messages.
3. Check the Post Log tab for error details in column I.

**Possible causes:**
- Pinterest access token expired and could not be refreshed.
- Pinterest API rate limit exceeded.
- Pin image URL is no longer accessible (GCS object deleted, Drive sharing changed).
- Board ID in the schedule does not match an existing Pinterest board.

**Resolution:**
- For token issues: Check `PINTEREST_ACCESS_TOKEN` and `PINTEREST_REFRESH_TOKEN` secrets. If the refresh token is expired, you may need to re-authenticate through the Pinterest developer portal and update both secrets.
- For rate limits: The posting schedule already spaces pins throughout the day. If you are still hitting limits, check if other tools or manual posting are consuming your API quota.
- For image URL issues: Re-run content-level regen for the affected pins to re-upload images.
- For board issues: Run the "Setup Pinterest Boards" workflow (manual trigger) to ensure all boards exist, then re-run the daily post workflow.

### Workflow Concurrency Issues

**Symptoms:** Workflows are queued for a long time, or multiple workflows appear to conflict.

**What to know:** All pipeline workflows (except daily posting) use a shared concurrency group `pinterest-pipeline` with `cancel-in-progress: false`. This means they queue rather than cancel each other. Daily posting workflows use a separate concurrency group `pinterest-posting`.

**Resolution:** If a workflow is stuck in the queue, check if another pipeline workflow is currently running. Wait for it to complete, or cancel it if it is stuck.
