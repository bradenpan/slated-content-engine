# Pin Scheduling Simplification Plan

## Problem Statement

There are **three places** that manipulate pin scheduling dates, creating confusion and overlap risk:

1. **`prompts/weekly_plan.md`** — Claude assigns `scheduled_date` during plan generation (Tue→Mon)
2. **`src/blog_deployer.py` `_create_pin_schedule()`** — Rewrites dates during promote-to-production based on carry-over logic (lines 571-627)
3. **`src/redate_schedule.py`** — Manual redate utility (used as optional override step in workflow)

**Current overlap problem:** W9 pins run through **2026-03-03 (Tuesday)** evening-2. W10 pins in the weekly plan are also scheduled starting **2026-03-03 (Tuesday)** morning. If W10 promotes, the carry-over logic in `_create_pin_schedule()` would actually handle this correctly by pushing W10 after W9 — but it's doing unnecessary date rewriting that makes the system hard to reason about.

**Goal:** Simplify to **one source of truth** — the dates Claude assigns during weekly plan generation — and remove the redundant rescheduling in `_create_pin_schedule()`.

---

## Changes

### Change 1: Programmatically inject exact pin dates into the prompt

**Problem:** Claude was given a text rule ("posting week runs Tuesday through next Monday") and `{{current_date}}`, then expected to do date math. Claude is bad at date math — this caused the wrong dates last week.

**Fix:** Compute the exact 7 posting dates in Python and inject them into the prompt so Claude does zero date arithmetic.

**File: `src/apis/claude_api.py`** — `generate_weekly_plan()` method

- Add a `week_start_date` parameter (the Monday, passed from `generate_weekly_plan.py`)
- Compute `pin_start = week_start_date + timedelta(days=2)` (Monday + 2 = Wednesday)
- Generate the 7 exact dates with day names
- Add `pin_posting_dates` to the template context

**File: `src/generate_weekly_plan.py`** — `generate_plan()` function

- Pass `start_date` through to `claude.generate_weekly_plan(week_start_date=start_date)`

**File: `prompts/weekly_plan.md`** — SCHEDULING RULES section (lines 316-324)

Replace the vague "posting week runs X through Y" rule with:
```
- Use EXACTLY these 7 posting dates (do NOT calculate your own):
{{pin_posting_dates}}
```

This way Claude gets told "use 2026-03-05 (Wednesday), 2026-03-06 (Thursday), ..." — zero date math required.

### Change 2: Remove date rescheduling from `_create_pin_schedule()`

**File:** `src/blog_deployer.py` lines 538-627

**Current behavior:** When carry-over pins exist from the prior week, the function finds the last occupied slot and rewrites ALL new pin dates sequentially after it.

**New behavior:** Keep the carry-over logic (preserving unposted W9 pins) but **do NOT rewrite dates on the new pins**. The new pins already have correct dates from Claude's plan (starting Wednesday), which won't overlap with W9 pins (ending Tuesday evening-2).

Specifically:
- **KEEP** lines 538-569: The carry-over detection logic that preserves unposted prior-week pins (the `kept` list)
- **DELETE** lines 571-627: The date rescheduling block (`if kept: ... slots = ... reschedule ...`)
- **KEEP** line 629: `combined = kept + schedule` — still merge old + new
- **KEEP** line 632: `save_pin_schedule(combined)` — still save the merged result

The new pins' `scheduled_date` and `scheduled_slot` values come directly from `pin-generation-results.json` (line 520-521), which inherits them from the Claude-generated weekly plan. No rewriting needed.

### Change 3: Redate W10 pins to start Wednesday March 4th

**Action:** Edit the W10 weekly plan JSON (`data/weekly-plan-2026-03-02.json`) to shift all 28 pin dates forward by 1 day:
- `2026-03-03` → `2026-03-04` (Wed)
- `2026-03-04` → `2026-03-05` (Thu)
- `2026-03-05` → `2026-03-06` (Fri)
- `2026-03-06` → `2026-03-07` (Sat)
- `2026-03-07` → `2026-03-08` (Sun)
- `2026-03-08` → `2026-03-09` (Mon)
- `2026-03-09` → `2026-03-10` (Tue)

This way, when W10 promotes and `_create_pin_schedule()` reads the data, the dates are already correct. No post-promote redate needed.

### Change 4: Review promote-to-production end-to-end

After changes 1-3, here's what the promote flow does:

1. **Merge develop → main** (unchanged)
2. **Read approvals from Sheets** (unchanged)
3. **Verify blog URLs** (unchanged)
4. **`_create_pin_schedule()`** — builds schedule entries from `pin-generation-results.json`, which has dates from Claude's plan (now Wed→Tue). Loads existing `pin-schedule.json` (W9 pins, ending Tue evening-2). Identifies unposted W9 pins → puts them in `kept`. Combines `kept + schedule` → saves.
5. **Result:** `pin-schedule.json` contains:
   - W9 unposted pins (scheduled through Tue Mar 3 evening-2)
   - W10 new pins (scheduled Wed Mar 4 → Tue Mar 10)
   - **No overlap** — W9 ends Tue evening-2, W10 starts Wed morning
6. **`post_pins.py`** reads `pin-schedule.json` for today's date + slot — correct behavior, unchanged
7. **Idempotency** — `post_pins.py` checks `is_pin_posted()` before posting, so already-posted W9 pins are skipped even if they're still in the schedule

**Key safety check:** The W9 pins in `pin-schedule.json` will NOT be overwritten because the carry-over logic (lines 560-569) explicitly checks: if a pin_id is NOT in the new pin set and NOT already posted, it's kept. W9 pin IDs (W9-01 through W9-28) won't match W10 pin IDs (W10-01 through W10-28), so all unposted W9 pins are preserved.

---

## Execution Order

1. **Edit `src/apis/claude_api.py`** — add `week_start_date` param, compute pin dates, inject into context
2. **Edit `src/generate_weekly_plan.py`** — pass `start_date` to `claude.generate_weekly_plan()`
3. **Edit `prompts/weekly_plan.md`** — replace vague scheduling rule with `{{pin_posting_dates}}` injection
4. **Edit `src/blog_deployer.py`** — remove the date rescheduling block in `_create_pin_schedule()` (lines 571-627), keep carry-over logic
5. **Edit `data/weekly-plan-2026-03-02.json`** — shift all 28 W10 pin dates forward by 1 day
6. **Verify** — review the updated `_create_pin_schedule()` to confirm it still correctly merges kept + new pins without date conflicts

---

## What This Does NOT Change

- `redate_schedule.py` — kept as-is for emergency manual use
- The `override_pin_start_date` workflow input — kept as-is for manual overrides
- `post_pins.py` — unchanged, reads schedule as-is
- W9 pins currently in `pin-schedule.json` — untouched, they continue posting through Tuesday
- The carry-over logic that preserves unposted prior-week pins — kept, just without the date rewriting

---

## Risk Assessment

**Low risk:**
- W9 pins are untouched in `pin-schedule.json`
- W10 dates shift forward by 1 day with no overlap
- Carry-over logic still preserves unposted pins
- `post_pins.py` is fully idempotent
- Pin dates are now computed by Python (correct) instead of Claude (error-prone)

**Edge case:** If W10 promote runs and some W9 pins haven't posted yet, they're preserved in the schedule. The only scenario where this could cause issues is if W9 has pins scheduled for dates AFTER W10 starts — but W9 ends on Tue Mar 3 and W10 starts Wed Mar 4, so no overlap.
