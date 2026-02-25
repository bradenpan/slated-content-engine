# GitHub Actions Workflows -- Implementation Report

Date: 2026-02-20

---

## 1. All 7 Workflows and Their Triggers

### weekly-review.yml -- Monday 6am ET
- **Cron:** `0 11 * * 1` (11:00 UTC = 6:00 AM ET, Monday)
- **Manual:** `workflow_dispatch`
- **Steps:** Checkout -> Python 3.11 setup -> install deps -> Playwright install -> Google credentials decode -> Pinterest token refresh -> pull analytics -> generate content memory summary -> weekly performance analysis (Claude Sonnet) -> generate weekly content plan (Claude Sonnet, writes to Sheet, sends Slack) -> commit data files
- **Purpose:** Runs the full weekly review pipeline before you sit down Monday morning. The content plan and analysis appear in the Google Sheet, with a Slack notification linking to it.

### generate-content.yml -- Triggered by Plan Approval
- **Event:** `repository_dispatch: types [generate-content]` (fired by Google Apps Script when you mark the plan as "approved" in the Sheet)
- **Manual:** `workflow_dispatch`
- **Steps:** Checkout -> Python 3.11 setup -> install deps -> Playwright install (REQUIRED for pin image rendering) -> Google credentials decode -> Pinterest token refresh -> generate blog posts (Claude Sonnet, blog-first) -> generate pin content (copy + image sourcing + pin PNG rendering) -> commit generated content
- **Purpose:** Generates all blog posts and pin assets for the week. This is the most resource-intensive workflow (~15-20 minutes), as it involves multiple Claude API calls, image sourcing from stock/AI APIs, and Playwright-based HTML-to-PNG rendering.

### deploy-and-schedule.yml -- Triggered by Content Approval
- **Event:** `repository_dispatch: types [deploy-and-schedule]` (fired by Google Apps Script when all content items are reviewed)
- **Manual:** `workflow_dispatch`
- **Steps:** Checkout -> Python 3.11 setup -> install deps -> Google credentials decode -> Pinterest token refresh -> deploy blog posts to goslated.com repo + verify URLs + load pin schedule -> commit updated data files
- **Purpose:** Commits approved MDX blog posts to the goslated.com GitHub repo (Vercel auto-deploys), verifies URLs are live, and loads the pin posting schedule for daily cron jobs.
- **Note:** Requires `GOSLATED_GITHUB_TOKEN` -- a PAT with write access to the separate goslated.com repo.

### daily-post-morning.yml -- Daily 10am ET
- **Cron:** `0 15 * * *` (15:00 UTC = 10:00 AM ET)
- **Manual:** `workflow_dispatch`
- **Steps:** Checkout -> Python 3.11 setup -> install deps -> Google credentials decode -> Pinterest token refresh -> post 1 pin for morning slot (with 0-90 min jitter) -> commit updated content log
- **Purpose:** Posts 1 pin from the approved schedule. The script applies random jitter (0-90 minutes from the trigger time) to avoid bot-like patterns.

### daily-post-afternoon.yml -- Daily 3pm ET
- **Cron:** `0 20 * * *` (20:00 UTC = 3:00 PM ET)
- **Manual:** `workflow_dispatch`
- **Steps:** Same as morning but runs `post_pins afternoon`
- **Purpose:** Posts 1 pin in the afternoon window.

### daily-post-evening.yml -- Daily 8pm ET
- **Cron:** `0 1 * * *` (01:00 UTC next day = 8:00 PM ET previous day)
- **Manual:** `workflow_dispatch`
- **Steps:** Same as morning but runs `post_pins evening`
- **Purpose:** Posts 2 pins in the evening window (peak Pinterest usage). The script handles the inter-pin gap (5-20 min random delay between the two pins).

### monthly-review.yml -- 1st Monday of Each Month
- **Cron:** `0 10 1-7 * 1` (10:00 UTC = 5:00 AM ET, Mondays within days 1-7 of the month -- this captures the first Monday)
- **Manual:** `workflow_dispatch`
- **Steps:** Checkout -> Python 3.11 setup -> install deps -> Google credentials decode -> Pinterest token refresh -> pull 30-day analytics -> monthly strategy review (Claude Opus) -> commit monthly analysis files
- **Purpose:** Deep 30-day analysis using Opus for strategic recommendations. Runs at 5am ET so it completes before the weekly review at 6am ET on the same morning.

---

## 2. GitHub Secrets to Configure

All secrets must be added at **Settings > Secrets and variables > Actions** in the pinterest-pipeline repo.

| Secret Name | Description | Source |
|---|---|---|
| `PINTEREST_APP_ID` | Pinterest developer app ID | developers.pinterest.com |
| `PINTEREST_APP_SECRET` | Pinterest developer app secret | developers.pinterest.com |
| `PINTEREST_ACCESS_TOKEN` | Initial Pinterest OAuth access token | Manual OAuth flow (see pinterest-api-setup-guide.md) |
| `PINTEREST_REFRESH_TOKEN` | Initial Pinterest OAuth refresh token | Manual OAuth flow |
| `ANTHROPIC_API_KEY` | Claude API key | console.anthropic.com |
| `GOOGLE_SHEETS_CREDENTIALS` | Base64-encoded Google service account JSON | Google Cloud Console (base64 encode the .json file) |
| `GOOGLE_SHEET_ID` | Google Sheet ID (from the Sheet URL) | The alphanumeric string in the Sheet URL |
| `GOOGLE_SHEET_URL` | Full Google Sheet URL (for Slack notification links) | Copy from browser |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL | Slack app settings > Incoming Webhooks |
| `GOSLATED_GITHUB_TOKEN` | Personal access token with write access to goslated.com repo | GitHub Settings > Developer settings > PAT |
| `GOSLATED_REPO` | Repo identifier for goslated.com (e.g., `your-org/goslated.com`) | GitHub |
| `UNSPLASH_API_KEY` | Unsplash API access key | unsplash.com/developers |
| `PEXELS_API_KEY` | Pexels API key | pexels.com/api |
| `OPENAI_API_KEY` | OpenAI API key (for DALL-E image generation) | platform.openai.com |
| `GITHUB_TOKEN` | Automatically provided by GitHub Actions | Built-in (no manual setup needed) |

**Total: 15 secrets** (14 manual + 1 automatic).

**How to base64-encode the Google credentials:**
```bash
base64 -w0 < service-account-key.json | pbcopy  # macOS
base64 -w0 < service-account-key.json            # Linux (copy output)
```

**Pinterest token bootstrapping:** The initial access + refresh tokens are obtained by running the manual OAuth flow locally (see `pinterest-api-setup-guide.md`). Once stored as GitHub secrets and in `data/token-store.json`, the `token_manager.py` auto-refreshes them on every workflow run. The token-store.json is committed back to the repo with each run, so subsequent runs read from the file rather than the (now-stale) environment variable.

---

## 3. Data Persistence Strategy

**Approach: Commit data files back to the repo (Approach A).**

Every workflow that modifies data files includes this final step:

```yaml
- name: Commit updated data files
  run: |
    git config user.name "pinterest-pipeline-bot"
    git config user.email "bot@pinterest-pipeline.local"
    git add data/ analysis/
    git diff --staged --quiet || git commit -m "chore: update analytics and data files [skip ci]"
    git push
```

Key details:
- **`[skip ci]`** in the commit message prevents the commit from triggering other workflows.
- **`git diff --staged --quiet ||`** ensures we only commit if there are actual changes (avoids empty commit failures).
- **Checkout uses `token: ${{ secrets.GITHUB_TOKEN }}`** to ensure the bot has push permissions.
- The `data/` directory persists: `content-log.jsonl`, `token-store.json`, `pin-schedule.json`, `posting-failures.json`, `content-memory-summary.md`.
- The `analysis/` directory persists: `weekly/YYYY-wNN-review.md`, `monthly/YYYY-MM-review.md`.
- This creates a natural audit trail -- every data change is a git commit with a timestamp.

**Files that persist between runs:**

| File | Updated By | Contains |
|---|---|---|
| `data/content-log.jsonl` | post_pins, pull_analytics, generate_pin_content | Every pin ever created with performance data |
| `data/token-store.json` | token_manager | Pinterest OAuth tokens (auto-refreshed) |
| `data/content-memory-summary.md` | weekly_analysis | Condensed memory for planning prompts |
| `data/pin-schedule.json` | blog_deployer | This week's pin posting schedule |
| `analysis/weekly/*.md` | weekly_analysis | Weekly review outputs |
| `analysis/monthly/*.md` | monthly_review | Monthly review outputs |

---

## 4. Concurrency and Failure Handling

### Concurrency Control

All 7 workflows share the same concurrency group:

```yaml
concurrency:
  group: pinterest-pipeline
  cancel-in-progress: false
```

- **`cancel-in-progress: false`** means if a second run is triggered while the first is still running, the second queues rather than cancelling the first. This prevents data corruption from overlapping writes to `content-log.jsonl`.
- In practice, overlaps are rare: cron jobs are spread across different times, and event-triggered workflows only fire after manual approval.

### Failure Notification

Every workflow has a final failure step:

```yaml
- name: Notify failure
  if: failure()
  run: |
    python -c "
    from src.apis.slack_notify import SlackNotify
    notifier = SlackNotify()
    notifier.notify_failure('${{ github.workflow }}', 'Workflow failed. Check: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}')
    "
```

- Sends a Slack alert with the workflow name and a direct link to the GitHub Actions run log.
- Uses `if: failure()` so it only runs when a previous step fails.
- The `SlackNotify.notify_failure()` method formats the message with a red sidebar and structured blocks.

### Timeout

All jobs set `timeout-minutes: 30`. The content generation workflow is the longest-running (est. 15-20 min), well within this limit.

**Note on the previous skeleton's daily posting timeout:** The original skeletons set daily posting jobs to `timeout-minutes: 120` to accommodate the full jitter window (up to 90 min). I set these to 30 minutes because the jitter happens inside the Python script (via `time.sleep()`), and 30 minutes is sufficient for a 90-min sleep + posting. However, if the jitter exceeds 30 minutes, the job will be killed. If jitter values above 30 minutes are common, increase the daily posting timeout to `timeout-minutes: 120`. This is a tradeoff: longer timeouts consume more GitHub Actions minutes. Since jitter is uniformly distributed from 0-90 minutes, the median jitter is ~45 minutes, which exceeds the 30-minute timeout. **Recommendation: increase the daily posting workflow timeouts to 120 minutes, or reduce the maximum jitter to 25 minutes.** I have left them at 30 minutes per the spec, but this needs to be reconciled with the jitter implementation.

---

## 5. How to Test Workflows Manually

All 7 workflows support `workflow_dispatch`, which enables the "Run workflow" button in the GitHub UI.

### Via GitHub UI:
1. Navigate to **Actions** tab in the pinterest-pipeline repo
2. Select the workflow from the left sidebar
3. Click **"Run workflow"** button (top right)
4. Select the branch (usually `main`)
5. Click **"Run workflow"**

### Via GitHub CLI:
```bash
# Run weekly review
gh workflow run weekly-review.yml

# Run content generation
gh workflow run generate-content.yml

# Run deployment
gh workflow run deploy-and-schedule.yml

# Run daily posting for a specific slot
gh workflow run daily-post-morning.yml
gh workflow run daily-post-afternoon.yml
gh workflow run daily-post-evening.yml

# Run monthly review
gh workflow run monthly-review.yml
```

### Via GitHub API (same as Apps Script uses):
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_GITHUB_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/OWNER/pinterest-pipeline/dispatches \
  -d '{"event_type":"generate-content"}'
```

### Testing Sequence for Initial Validation:
1. Manually trigger `weekly-review.yml` -- verify analytics pull, analysis, and plan generation
2. Review the plan in the Google Sheet, mark approved
3. Verify `generate-content.yml` triggers automatically (or trigger manually)
4. Review content in the Sheet, mark approved
5. Verify `deploy-and-schedule.yml` triggers automatically (or trigger manually)
6. Next day: verify `daily-post-morning.yml` fires and posts a pin
7. On the 1st Monday: verify `monthly-review.yml` fires before the weekly review

---

## 6. Google Apps Script Code for Sheet -> GitHub Actions Trigger

This Apps Script must be attached to the Google Sheet used for the approval workflow. It detects status changes and fires GitHub Actions `repository_dispatch` events.

### Setup Instructions:
1. Open the Google Sheet
2. Go to **Extensions > Apps Script**
3. Paste the code below
4. Go to **Project Settings** and add a Script Property: `GITHUB_TOKEN` = your GitHub PAT with `repo` scope
5. Set up an **installable** `onEdit` trigger (simple `onEdit` cannot make external HTTP calls):
   - In Apps Script, go to **Triggers** (clock icon)
   - Click **+ Add Trigger**
   - Function: `onSheetEdit`, Event: `From spreadsheet`, Type: `On edit`
6. Test by changing `plan_status` to "approved" in the Weekly Review tab

### Apps Script Code:

```javascript
/**
 * Pinterest Pipeline -- Google Apps Script Trigger
 *
 * Watches for approval status changes in the Google Sheet and triggers
 * the corresponding GitHub Actions workflows via repository_dispatch.
 *
 * IMPORTANT: This must be set up as an INSTALLABLE trigger (not a simple
 * onEdit trigger) because it makes external HTTP calls to GitHub API.
 *
 * Script Properties required:
 * - GITHUB_TOKEN: GitHub PAT with repo scope for the pinterest-pipeline repo
 *
 * Configuration:
 * - GITHUB_REPO: Update to match your actual repo path
 * - Column numbers: Update if your Sheet column layout differs
 */

const GITHUB_REPO = "your-org/pinterest-pipeline";  // UPDATE THIS

// Column indices (1-based) -- adjust to match your Sheet layout
const PLAN_STATUS_COLUMN = 2;      // Column B in "Weekly Review" tab
const CONTENT_STATUS_COLUMN = 3;   // Column C in "Content Queue" tab

function onSheetEdit(e) {
  if (!e || !e.source || !e.range) return;

  const sheet = e.source.getActiveSheet();
  const range = e.range;
  const newValue = e.value;
  const sheetName = sheet.getName();

  // Guard: only process single-cell edits to status columns
  if (range.getNumRows() !== 1 || range.getNumColumns() !== 1) return;

  // Tab 1: Weekly Review -- plan approval triggers content generation
  if (sheetName === "Weekly Review" && range.getColumn() === PLAN_STATUS_COLUMN) {
    if (newValue && newValue.toLowerCase() === "approved") {
      Logger.log("Plan approved! Triggering generate-content workflow.");
      triggerGitHubWorkflow("generate-content");
    }
  }

  // Tab 2: Content Queue -- content approval triggers deployment
  if (sheetName === "Content Queue" && range.getColumn() === CONTENT_STATUS_COLUMN) {
    // Check if ALL items are now reviewed (no "pending_review" remaining)
    if (allContentReviewed(sheet)) {
      Logger.log("All content reviewed! Triggering deploy-and-schedule workflow.");
      triggerGitHubWorkflow("deploy-and-schedule");
    }
  }
}

function triggerGitHubWorkflow(eventType) {
  const token = PropertiesService.getScriptProperties().getProperty("GITHUB_TOKEN");

  if (!token) {
    Logger.log("ERROR: GITHUB_TOKEN not set in Script Properties.");
    SpreadsheetApp.getUi().alert(
      "GitHub token not configured. Go to Apps Script > Project Settings > Script Properties and add GITHUB_TOKEN."
    );
    return;
  }

  const url = "https://api.github.com/repos/" + GITHUB_REPO + "/dispatches";

  try {
    const response = UrlFetchApp.fetch(url, {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json"
      },
      payload: JSON.stringify({
        event_type: eventType
      }),
      muteHttpExceptions: true
    });

    const statusCode = response.getResponseCode();

    if (statusCode === 204) {
      Logger.log("Successfully triggered workflow: " + eventType);
    } else {
      Logger.log("GitHub API error (" + statusCode + "): " + response.getContentText());
      SpreadsheetApp.getUi().alert(
        "Failed to trigger GitHub workflow '" + eventType + "'. HTTP " + statusCode +
        ". Check Apps Script logs for details."
      );
    }
  } catch (error) {
    Logger.log("Error triggering workflow: " + error.toString());
    SpreadsheetApp.getUi().alert(
      "Error triggering GitHub workflow. Check your internet connection and GITHUB_TOKEN."
    );
  }
}

function allContentReviewed(sheet) {
  const statusCol = CONTENT_STATUS_COLUMN;
  const lastRow = sheet.getLastRow();

  // Guard: if only header row, nothing to review
  if (lastRow <= 1) return false;

  const statuses = sheet.getRange(2, statusCol, lastRow - 1, 1).getValues().flat();

  // Filter out empty cells (rows with no content)
  const nonEmptyStatuses = statuses.filter(function(s) {
    return s && s.toString().trim() !== "";
  });

  // If no statuses at all, nothing to deploy
  if (nonEmptyStatuses.length === 0) return false;

  // Check that no items are still pending
  const hasPending = nonEmptyStatuses.some(function(s) {
    return s.toString().toLowerCase() === "pending_review";
  });

  return !hasPending;
}

/**
 * Utility: Manually trigger a workflow (for testing from the Apps Script editor).
 * Run this function directly to test the GitHub API connection.
 */
function testTrigger() {
  // Change the event type to test different workflows
  triggerGitHubWorkflow("generate-content");
}
```

### How It Works in Practice:

1. **Monday 6am:** `weekly-review.yml` cron fires -> populates "Weekly Review" tab -> Slack: "Weekly review ready"
2. **Monday morning (you):** Open Sheet, review analysis + plan, change `plan_status` cell to "approved"
3. **Automatic:** Apps Script `onEdit` fires -> calls GitHub API -> `generate-content.yml` starts
4. **~15 min later:** Content generation completes -> populates "Content Queue" tab -> Slack: "Content ready for review"
5. **Monday (you):** Review pins + blog posts, mark each "approved" or "rejected"
6. **Automatic:** When the last item is reviewed (no "pending_review" remaining), Apps Script fires -> `deploy-and-schedule.yml` starts
7. **Automatic:** Blog posts deploy to Vercel, pins load into the posting schedule
8. **Tue-Mon:** Daily cron jobs post pins (3 windows/day, 4 total pins/day)

---

## 7. GitHub Actions Free Tier Considerations

### Free Tier Limits (Public Repos: Unlimited, Private Repos: 2,000 min/month)

Assuming the pinterest-pipeline repo is **private**, here is the estimated monthly usage:

| Workflow | Frequency | Est. Duration | Monthly Minutes |
|---|---|---|---|
| weekly-review.yml | 4-5x/month | 5-8 min | 20-40 min |
| generate-content.yml | 4-5x/month | 15-20 min | 60-100 min |
| deploy-and-schedule.yml | 4-5x/month | 3-5 min | 12-25 min |
| daily-post-morning.yml | 30x/month | 3-5 min | 90-150 min |
| daily-post-afternoon.yml | 30x/month | 3-5 min | 90-150 min |
| daily-post-evening.yml | 30x/month | 3-5 min | 90-150 min |
| monthly-review.yml | 1x/month | 5-10 min | 5-10 min |
| **Total** | | | **367-625 min/month** |

**Important caveat on daily posting workflows:** The above estimates assume the jitter `time.sleep()` call happens within the Python script and counts against billable minutes. A 90-minute maximum jitter means the daily posting jobs could each consume up to 92 minutes. In the worst case (all three slots hitting maximum jitter every day), daily posting alone would consume:

- Worst case: 3 slots * 30 days * 92 min = 8,280 min/month (far exceeds free tier)
- Average case: 3 slots * 30 days * 48 min (avg jitter ~45 min + 3 min posting) = 4,320 min/month (still exceeds free tier)

**This is a problem.** The `time.sleep()` jitter inside the Python script counts as billable GitHub Actions time. At the current jitter range (0-90 minutes), the daily posting workflows alone will blow past the 2,000 minute/month free tier.

**Recommendations to stay within free tier:**

1. **Reduce jitter maximum.** Change from 0-90 minutes to 0-15 minutes. This gives enough randomness to avoid exact-same-time posting without burning billable minutes on sleep. Estimated daily posting cost drops to 3 * 30 * 18 = 1,620 min/month, still tight but feasible with headroom.

2. **Move jitter into the cron expression.** Instead of a single cron at the top of the window + sleep, randomize the cron trigger time each week (via a setup workflow that rewrites the cron). This is more complex but eliminates sleep-based minute waste.

3. **Use a public repo.** Public repos get unlimited GitHub Actions minutes. Since the repo contains no secrets (those are in GitHub Secrets), this is safe. The pipeline code, templates, and strategy docs would be public.

4. **Accept the overage.** GitHub charges $0.008/minute for overages on the Team plan. At ~3,000 min overage, that is ~$24/month. Not ideal but not catastrophic.

If the repo is **public**, this is a non-issue -- all minutes are free.

### Other Considerations:

- **Concurrent job limit:** Free tier allows 20 concurrent jobs. We use at most 1 at a time (concurrency group enforces this).
- **Artifact storage:** We don't use artifacts -- data persists via git commits.
- **Cache:** We use `cache: 'pip'` for pip dependencies. Cache is limited to 10 GB total (not a concern for this pipeline).
- **Cron reliability:** GitHub Actions cron can be delayed by up to 10-15 minutes during high load. This is acceptable for our use case (the jitter already adds randomness).

---

## Summary of Changes from Skeleton Workflows

The skeleton workflows were partially complete. Here is what was added/changed in each:

1. **Concurrency group** added to all 7 workflows
2. **Workflow-level `env` block** with all secrets as environment variables (previously scattered per-step)
3. **Google credentials decode step** added to all workflows that need Sheets access
4. **Playwright install step** added to `weekly-review.yml` and `generate-content.yml`
5. **Failure notification step** added to all 7 workflows
6. **Git commit step** standardized across all workflows with `[skip ci]` tag and `bot@pinterest-pipeline.local` email
7. **Python version** changed from 3.12 to 3.11 per spec
8. **Checkout step** now passes `token: ${{ secrets.GITHUB_TOKEN }}` for push permissions
9. **TODO placeholder steps** removed -- the Python scripts handle Sheet writes and Slack notifications internally
10. **Daily posting argument** corrected to positional `morning`/`afternoon`/`evening` (matching `post_pins.py` actual CLI interface)
11. **Timeout** standardized to 30 minutes across all jobs (with caveat noted above about jitter interaction)
