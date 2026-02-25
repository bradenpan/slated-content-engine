# Posting, Analytics, and Review Pipeline -- Implementation Report

**Date:** 2026-02-20
**Files implemented:**
- `src/post_pins.py`
- `src/pull_analytics.py`
- `src/weekly_analysis.py`
- `src/monthly_review.py`

---

## 1. What Was Implemented

### post_pins.py -- Daily Pin Posting with Anti-Bot Jitter

The main entry point is `post_pins(time_slot: str)` where time_slot is "morning", "afternoon", or "evening". The function:

1. Initializes TokenManager, PinterestAPI, and SlackNotify
2. Checks the weekly skip (one random window per week is dropped)
3. Applies initial jitter (0-90 minute random sleep)
4. Loads the pin schedule from `data/pin-schedule.json` and filters to today's date + current slot
5. Builds a board name-to-ID mapping by calling `pinterest_api.list_boards()` once
6. For each pin: runs idempotency check, verifies blog URL, constructs UTM link, creates pin via Pinterest API, updates content-log.jsonl and Google Sheet
7. Sends Slack notification with posting results

Supporting functions:
- `apply_jitter()` -- deterministic-seeded random sleep
- `should_skip_window()` -- weekly jitter skip logic
- `is_already_posted()` -- content log scan for idempotency
- `append_to_content_log()` -- JSONL append
- `load_scheduled_pins()` -- reads from pin-schedule.json
- `build_board_map()` -- Pinterest board name -> ID lookup
- `construct_utm_link()` -- UTM parameter construction
- `verify_url_is_live()` -- HEAD request URL verification
- `_create_pin_with_retry()` -- retry logic for 429, 401, and other errors
- `_record_failure()` -- tracks consecutive failures for permanent failure alerting

### pull_analytics.py -- Pinterest Analytics Collection

The main entry point is `pull_analytics(days_back=7)`. The function:

1. Refreshes the Pinterest token via TokenManager
2. Loads all content-log.jsonl entries
3. Filters to pins with a `pinterest_pin_id` that are less than 90 days old (long-tail tracking)
4. For each trackable pin: calls `pinterest_api.get_pin_analytics()` with the full date range from posted_date to today
5. Pulls account-level analytics via `pinterest_api.get_account_analytics()`
6. Computes derived metrics (save_rate, click_through_rate) for every entry
7. Rewrites the entire content-log.jsonl with updated metrics
8. Saves raw analytics to `data/analytics/YYYY-wNN-raw.json`
9. Returns structured data for downstream analysis

Supporting functions:
- `load_content_log()` / `save_content_log()` -- JSONL read/write
- `compute_derived_metrics()` -- save_rate and CTR computation
- `aggregate_by_dimension()` -- groups entries by any field and sums metrics
- `_sum_pin_metrics()` -- handles multiple Pinterest API response formats
- `_save_analytics_snapshot()` -- weekly raw data archival

### weekly_analysis.py -- Weekly Performance Analysis

The main entry point is `run_weekly_analysis(week_number=None)`. The function:

1. Loads content-log.jsonl with freshly updated analytics
2. Loads the current week's content plan (pin-schedule.json)
3. Loads the previous week's analysis from analysis/weekly/ for trend comparison
4. Computes aggregates across all dimensions (pillar, content_type, keyword, board, funnel_layer, template, image_source, pin_type)
5. Calls `claude_api.analyze_weekly_performance()` with Sonnet
6. Falls back to a data-only report if Claude is unavailable
7. Saves to `analysis/weekly/YYYY-wNN-review.md`

Also includes `generate_content_memory_summary()` which is a pure Python computation (no LLM call) that produces a condensed summary of all content created. This is consumed by the weekly planning prompt. It has 7 sections: recent topics, all blog posts, pillar mix, keyword frequency, images used, fresh pin candidates, and treatment tracker.

### monthly_review.py -- Monthly Strategy Review

The main entry point is `run_monthly_review(month=None, year=None)`. The function:

1. Loads content-log.jsonl with the full month of data
2. Loads all weekly analyses from the past month (matches ISO weeks to calendar month)
3. Loads current strategy document from `strategy/current-strategy.md`
4. Computes 30-day multi-dimensional aggregates plus specialized analyses
5. Calls `claude_api.run_monthly_review()` with **Opus** (not Sonnet)
6. Falls back to a data-only report if Opus is unavailable
7. Saves to `analysis/monthly/YYYY-MM-review.md`
8. Updates Google Sheet dashboard
9. Sends Slack notification

Specialized analyses computed:
- Month-over-month comparison with delta and percentage change
- Pillar-level trend detection (improving/declining/stable)
- Keyword saturation analysis (which keywords are plateauing)
- Board density analysis (pins per board, underpopulated boards)
- Fresh pin effectiveness (Treatment 1 vs. 2-5 comparison)
- Content age analysis (compounding measurement across age buckets)
- Plan-level vs. recipe-level pin performance comparison

---

## 2. Anti-Bot Jitter Logic

The jitter system has three layers:

### Layer 1: Initial Window Jitter
When a cron job fires at the start of a posting window (e.g., 10:00 AM ET), the script sleeps for `random(0, 5400)` seconds (0 to 90 minutes). This means the actual post lands anywhere between 10:00 and 11:30 AM.

The sleep duration is derived from a SHA-256 hash of `{date}:{slot}:{pin_index}`. This makes it:
- **Reproducible** for debugging: same date + slot always produces the same jitter
- **Non-repeating** day to day: different dates produce different seeds

### Layer 2: Inter-Pin Spacing
When posting multiple pins in one window (evening slot posts 2 pins), each subsequent pin sleeps `random(300, 1200)` seconds (5-20 minutes) after the previous one. This prevents burst posting.

### Layer 3: Weekly Window Skip
One posting window per week is randomly skipped. The skip target is deterministic: derived from `{iso_year}:W{iso_week}:{salt}` via SHA-256. This produces a consistent (day, slot) pair per week that gets skipped.

There are 21 possible windows per week (7 days x 3 slots). One is dropped, leaving 20 active windows. At 4 pins/day - 1 skip, this produces 27 pins/week instead of 28, which is well within the healthy range of 21-35 pins/week.

When a window is skipped, the pin scheduled for that slot is simply dropped (not rescheduled). The content log shows the pin as never posted. This is intentional -- rescheduling would create a burst elsewhere.

---

## 3. Analytics Data Flow

```
Pinterest API (pin-level + account-level analytics)
        |
        v
pull_analytics.py
  - Fetches metrics for all pins < 90 days old
  - Sums daily metrics into cumulative totals per pin
  - Updates content-log.jsonl with current totals
  - Saves raw snapshot to data/analytics/YYYY-wNN-raw.json
        |
        v
content-log.jsonl (enriched with impressions, saves, clicks, rates)
        |
        +---> weekly_analysis.py
        |       - Computes aggregates by pillar, keyword, board, etc.
        |       - Calls Claude Sonnet for analysis
        |       - Saves to analysis/weekly/YYYY-wNN-review.md
        |       |
        |       +---> generate_content_memory_summary()
        |       |       - Pure Python computation, no LLM call
        |       |       - Produces data/content-memory-summary.md
        |       |       - Fed into generate_weekly_plan.py prompt
        |       |
        |       +---> generate_weekly_plan.py (uses analysis + memory)
        |               - Plans next week's content
        |
        +---> monthly_review.py (1st Monday of month)
                - Loads 4-5 weekly analyses
                - Loads strategy document
                - Computes 30-day aggregates + specialized analyses
                - Calls Claude Opus for deep review
                - Saves to analysis/monthly/YYYY-MM-review.md
                - Strategy recommendations feed back into strategy doc
```

The key insight: analytics flow is a closed loop. Performance data feeds into analysis, analysis feeds into planning, planning drives content creation, content gets posted, and its performance gets measured. The content memory summary ensures the planner knows what has been created and how it performed.

---

## 4. How Idempotency Works in post_pins.py

Before posting any pin, `is_already_posted(pin_id)` scans content-log.jsonl for an entry where:
1. The `pin_id` field matches the pin about to be posted, AND
2. The `pinterest_pin_id` field is non-null (meaning it was successfully posted)

If both conditions are true, the pin is skipped with a log message. This prevents duplicate posts when:
- GitHub Actions retries a failed workflow run
- A partial failure leaves some pins posted and others not
- Manual re-execution of the posting script

The content log is the single source of truth. After successful posting, `append_to_content_log()` writes the pin's data with the `pinterest_pin_id` set, making future runs see it as already posted.

---

## 5. How Long-Tail Tracking Works

Pinterest content has a ~3.75-month half-life. Pins posted weeks or months ago continue to accumulate impressions, saves, and clicks. The analytics pull captures this:

1. **All pins < 90 days old are tracked**, not just this week's. The 90-day limit comes from the Pinterest API's maximum date range.

2. For each trackable pin, the analytics query starts from the pin's `posted_date` (not just 7 days ago). This means a 60-day-old pin's analytics are pulled from its post date through today, giving cumulative lifetime totals.

3. Pins older than 90 days keep their last-known cumulative metrics in the content log. They are no longer queried (the API would return no data), but their historical performance is preserved for all-time aggregation.

4. The content age analysis in monthly_review.py groups pins into age buckets (1-7d, 8-14d, 15-30d, 31-60d, 61-90d) and measures whether older pins are "still generating" engagement. This is the compounding measurement -- a pin posted 60 days ago that still gets saves is a compounding asset.

5. Raw analytics snapshots are saved weekly (`data/analytics/YYYY-wNN-raw.json`), creating a time series that shows how each pin's metrics grew over time.

---

## 6. Assumptions About Pinterest API Response Formats

The `_sum_pin_metrics()` function in pull_analytics.py handles three possible response formats from the Pinterest v5 API:

### Format 1: Nested with summary_metrics (preferred)
```json
{
  "all": {
    "daily_metrics": [...],
    "summary_metrics": {
      "IMPRESSION": 1050,
      "SAVE": 35,
      "PIN_CLICK": 80,
      "OUTBOUND_CLICK": 15
    }
  }
}
```
When `summary_metrics` is present, those pre-summed values are used directly.

### Format 2: Nested with daily_metrics only
```json
{
  "all": {
    "daily_metrics": [
      {"date": "2026-02-13", "metrics": {"IMPRESSION": 150, "SAVE": 5, ...}},
      {"date": "2026-02-14", "metrics": {"IMPRESSION": 200, "SAVE": 8, ...}}
    ]
  }
}
```
When only daily_metrics are present, the function sums across all days.

### Format 3: Flat metric lists
```json
{
  "IMPRESSION": [100, 150, 200, ...],
  "SAVE": [5, 8, 3, ...]
}
```
This is a fallback for alternative response structures where metrics are flat lists.

**These formats are based on the Pinterest v5 API documentation as of early 2026. The actual response format should be verified during integration testing against the sandbox API.**

Additional assumptions:
- Board list response from `GET /v5/boards` returns items with `id` and `name` fields
- Pin creation response from `POST /v5/pins` returns a dict with an `id` field
- Rate limit headers (`X-RateLimit-Remaining`, `X-RateLimit-Limit`, `X-RateLimit-Reset`) are present on responses (handled by pinterest_api.py)
- Account analytics endpoint (`GET /v5/user_account/analytics`) uses the same metric names as pin analytics

---

## 7. What Needs to Be Tested First

### Priority 1: API Integration (must work before anything else)
1. **Pinterest sandbox API connection**: Create a pin, list boards, pull analytics. Verify response formats match the three handled cases in `_sum_pin_metrics()`.
2. **Token refresh flow**: Verify `TokenManager.get_valid_token()` correctly refreshes tokens when they are within 5 days of expiry.
3. **Board name resolution**: Post a pin to a board by name, verifying the board_map lookup works with the actual board names returned by the API.

### Priority 2: Data Pipeline Integrity
4. **Content log round-trip**: Write entries via `append_to_content_log()`, read via `load_content_log()`, update via analytics pull + `save_content_log()`. Verify no data loss or corruption.
5. **Idempotency**: Post a pin, verify it appears in the log, run `post_pins()` again for the same slot/date, verify it is skipped.
6. **Analytics aggregation**: Seed the content log with test entries, run `aggregate_by_dimension()` for each dimension, verify correct grouping and arithmetic.

### Priority 3: Anti-Bot Jitter
7. **Jitter determinism**: Call `should_skip_window()` and `apply_jitter()` multiple times with the same inputs, verify they produce the same results. Then change the date and verify they produce different results.
8. **Skip distribution**: Simulate 52 weeks of `should_skip_window()` calls and verify that skips are distributed across all days/slots, not clustered.

### Priority 4: Error Handling
9. **Pin creation retry**: Mock a 429 response, verify retry with backoff. Mock a 401, verify token refresh and retry. Mock a persistent failure, verify it stops after 3 attempts and alerts via Slack.
10. **Partial analytics failure**: Mock a failure for one pin's analytics, verify the pull continues for other pins and the failed pin retains its previous metrics.

### Priority 5: End-to-End
11. **Full Monday workflow**: Run `pull_analytics()` -> `run_weekly_analysis()` -> verify output files exist and contain expected sections.
12. **Full monthly workflow**: Seed weekly analysis files, run `run_monthly_review()`, verify output contains all expected analysis dimensions.

### Priority 6: Dependencies Not Yet Implemented
The following are called by these scripts but implemented by another agent:
- `ClaudeAPI.analyze_weekly_performance()` -- used by weekly_analysis.py
- `ClaudeAPI.run_monthly_review()` -- used by monthly_review.py
- `SheetsAPI.update_pin_status()` -- used by post_pins.py
- `SheetsAPI.update_dashboard()` -- used by monthly_review.py

Both analysis scripts have fallback data-only report generation that produces useful output even when Claude is unavailable. The sheet updates are wrapped in try/except so they fail gracefully.
