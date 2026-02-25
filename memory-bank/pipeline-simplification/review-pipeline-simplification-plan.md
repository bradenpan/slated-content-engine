# Review: Pipeline Simplification Plan

**Reviewed:** 2026-02-25
**Plan file:** `troubleshooting/plan-pipeline-simplification.md`
**Reference file:** `troubleshooting/reference-data-flows-and-naming.md`
**Architecture reference:** `troubleshooting/architecture-data-flows.md`

---

## Overall Assessment

The plan is **directionally correct and well-structured**. The core idea — remove stock APIs, remove ranking/validation gates, simplify to AI-only images, switch two LLM calls to GPT-5 Mini — is sound. The reference data flows document is largely accurate.

However, the plan has **several gaps and inaccuracies** that would cause bugs if implemented as-written. None are show-stoppers, but all need to be addressed before coding begins.

---

## Issues Found (By Severity)

### CRITICAL — Will break the pipeline if not fixed

#### C1: `blog_deployer.py` has 6 approval filter locations, not 3

The plan says "Remove `use_ai_image` from approval filters — 3 locations (lines ~122, ~261, ~376)."

**Actual count: 6 locations across 3 methods:**
- `deploy_approved_content()` — Lines 123 + 129 (blogs + pins)
- `deploy_to_preview()` — Lines 262 + 267 (blogs + pins)
- `promote_to_production()` — Lines 378 + 383 (blogs + pins)

Each method has TWO filter lines (one for blogs, one for pins). Missing any of these means `use_ai_image`-status items from previous weeks could still be processed incorrectly, or more importantly, the new simplified flow won't include items that only have `"approved"` status.

**Fix:** Update all 6 locations.

---

#### C2: Column shift requires updating range reads (`A:M` → `A:L`)

The plan mentions removing Column M and shifting regen triggers, but doesn't mention that `read_content_approvals()` and `read_regen_requests()` in `sheets_api.py` both read range `A:M`. After removing Column M, these should read `A:L` to avoid reading into the regen trigger columns.

**Affected locations:**
- `sheets_api.py` line ~419: `read_content_approvals()` range `A:M`
- `sheets_api.py` line ~475: `read_regen_requests()` range `A:M`

**Fix:** Change both to `A:L`.

---

#### C3: Apps Script column numbers need exact update

The plan says "Shift regen trigger from col 15 (O1) to col 14 (N1)" but the correct mapping after removing Column M is:

- Old Column O (col 15, 1-based) → New Column N (col 14, 1-based)
- `trigger.gs` line ~48: `getColumn() === 15` → `getColumn() === 14`
- `trigger.gs` `runRegen()`: `"O1"` → `"N1"`

However, the plan says column shift is N→M (13) and O→N (14). Since Column M is being REMOVED (not shifted), the correct 1-based column numbers are:
- Regen label: was col 14 (N), becomes col 13 (M)
- Regen trigger: was col 15 (O), becomes col 14 (N)

**Fix:** Verify: `getColumn() === 14` for trigger detection (0-based: 13).

---

#### C4: `reset_regen_trigger()` in sheets_api.py writes to `O1`

The plan doesn't mention this function, but `sheets_api.py` line ~575-579 has `reset_regen_trigger()` which writes to cell `O1`. This must change to `N1`.

**Fix:** Update `reset_regen_trigger()` to write to `N1`.

---

#### C5: `publish_content_queue.py` writes regen trigger to `N1:O1`

Line ~252 writes `["Regen >", "idle"]` to range `N1:O1`. Must change to `M1:N1`.

**Fix:** Update range from `N1:O1` to `M1:N1`.

---

### HIGH — Significant gap in the plan that needs design decisions

#### H1: `_source_pin_image()` and `source_image()` serve different purposes — "collapse" is under-specified

The plan says to collapse these into a single function. But:
- `source_image()` (lines 308-363) is a **ROUTER** that dispatches by tier
- `_source_pin_image()` (lines 681-734) is a **WRAPPER** that calls `source_image()` and ALSO generates an AI comparison image

Since the simplification removes both stock routing AND AI comparisons, the correct approach is:
1. Delete `_source_pin_image()` entirely
2. Delete `source_image()` entirely
3. Delete `_source_stock_image()` entirely
4. Simplify `_source_ai_image()` (remove validation/regen)
5. In `generate_pin_content()`, call the simplified `_source_ai_image()` directly (or inline it)

**Fix:** Replace "collapse" language with explicit deletion/rewrite plan.

---

#### H2: `regen_content.py` imports `source_image` and `_source_ai_image` directly

Lines 34-42 of regen_content.py:
```python
from src.generate_pin_content import (
    source_image,        # Used for image regen routing
    _source_ai_image,    # Used for AI comparison generation
    ...
)
```

After removing `source_image()` and simplifying `_source_ai_image()`, the regen script must be updated to:
- Call the simplified AI image function directly instead of `source_image()`
- Remove all AI comparison generation code (lines ~578-586, ~831-843)
- Remove tier detection logic (lines ~542-549 which read `image_source` to determine tier)

The plan mentions some of this but doesn't call out the **import breakage** that will occur.

**Fix:** Update regen_content.py imports and all call sites to match new function signatures.

---

#### H3: `_process_ai_image_swaps()` has critical side effects not documented in the plan

The plan says "Delete `_process_ai_image_swaps()`" but this function (blog_deployer.py:774-851) does more than swap images:
1. Downloads AI hero from GCS
2. Re-renders the pin template with the AI hero
3. Uploads re-rendered pin to GCS
4. **Updates `_drive_download_url` in pin-generation-results.json** (line 846)
5. **Updates `image_source` to "ai_generated"** (line 843)
6. **Saves the modified data back to disk** (lines 446-449)

After simplification, ALL images are AI-generated from the start, so this function is truly unnecessary. But the calling code at lines 428-453 must also be removed (not just the function definition).

**Fix:** Delete both the function AND the call block at lines 428-453 in `promote_to_production()`.

---

#### H4: Existing pins with `use_ai_image` status — no migration plan

If someone has a Content Queue with existing `use_ai_image` status rows from a previous week, and the simplified code removes this status from the terminal set, those rows would block the deploy gate (they'd be treated as non-terminal).

**Fix:** Either:
- Do a one-time cleanup of any active Content Queue before deploying the code change
- OR keep `use_ai_image` in the terminal set as a backwards-compat alias (simpler, no migration needed)

---

#### H5: `generate_image_prompt()` signature change needs careful handling

The plan says to remove the `image_source` parameter from `generate_image_prompt()`. But regen_content.py calls this function too. The signature change must be coordinated across:
- `claude_api.py` — function definition
- `generate_pin_content.py` — call site (line ~969)
- `regen_content.py` — call site (wherever it calls for image regen)

Additionally, after removing the `image_source` param, the function no longer needs to load `image_search.md` (stock query prompt). It should only load `image_prompt.md` (AI prompt).

**Fix:** Grep for all `generate_image_prompt(` calls and update signatures in one pass.

---

### MEDIUM — Should be addressed but won't immediately break things

#### M1: Quality metadata fields — what happens to them?

The plan mentions removing several quality fields from pin_data but doesn't specify whether to:
- Stop populating them entirely (leave them absent from JSON)
- Set them to defaults (score=None, retries=0, low_confidence=False)
- Keep the keys with null values for schema consistency

**Recommendation:** Stop populating them entirely. Downstream consumers (analytics) never read these fields. Only the Content Queue Notes column uses them, and that's being simplified too.

Fields to stop populating:
- `image_quality_score`
- `image_low_confidence`
- `image_source_original`
- `image_quality_issues`
- `_ai_hero_image_path`, `_ai_image_id`, `_ai_image_score`

Fields to KEEP:
- `image_retries` — still relevant (image_gen_api has its own retry logic)
- `image_source` — always "ai_generated" now
- `image_id` — still tracked for dedup

---

#### M2: `image_search.md` prompt should be deleted too

The plan lists `image_rank.md`, `image_search.md`, and `image_validate.md` for deletion. This is correct. But the plan's "What Stays" section says `generate_image_prompt()` stays — which is true, but the function currently loads `image_search.md` when `image_source="stock"`. After removing the stock path, `image_search.md` becomes dead code.

**Fix:** Confirmed — `image_search.md` IS listed for deletion in the plan's "Prompt files" section. This is consistent.

---

#### M3: `generate_image_search_query()` should be deleted

`claude_api.py` line ~436-448 has a convenience wrapper `generate_image_search_query()` that calls `generate_image_prompt(image_source="stock")`. The plan mentions "Remove if it exists (line 436)". It does exist and should be removed.

**Fix:** Delete `generate_image_search_query()`.

---

#### M4: Image dedup for AI images is weak

Current dedup uses `ai_{md5_hash_of_prompt[:12]}` as the image ID. Since prompts are generated per-pin, two pins about "chicken tacos" could get different prompts and therefore different hashes, even though the resulting images might look similar.

This isn't new (it's the current behavior), but worth noting that switching to 100% AI images means dedup is essentially based on prompt text, not visual similarity.

**No action needed** — just documenting the limitation.

---

#### M5: Weekly plan prompt will continue generating `image_source_tier` if not explicitly removed

The plan correctly identifies that `image_source_tier` must be removed from:
- `prompts/weekly_plan.md` — schema, examples, IMAGE SOURCE ASSIGNMENT section
- `prompts/weekly_plan_replace.md` — schema, examples, constraints

But `generate_weekly_plan.py` doesn't validate this field, so if it's accidentally left in the prompt, Claude will still generate it and it'll just be ignored. Low risk but sloppy.

**Fix:** Ensure ALL references are removed from both prompt files. Test by generating a plan and verifying the field is absent.

---

#### M6: `strategy/current-strategy.md` tier documentation is embedded in strategic guidance

The plan says "Remove tier documentation row." But the tier system is described in TWO sections:
- Section 5.3 "Image Source Assignment" (lines ~382-391) — detailed table with rationale
- Section 12.1 "Planning Fields" (line ~651) — field reference

Both need to be updated. Section 5.3 should be rewritten to say "All images are AI-generated" rather than just deleting the tier table, since the strategy doc is consumed by Claude for plan generation.

**Fix:** Rewrite Section 5.3 rather than just deleting it.

---

### LOW — Nice to have, won't cause bugs

#### L1: `_build_quality_note()` simplification not fully specified

The plan says "simplified — just 'AI generated' instead of scores." The current function in sheets_api.py builds notes like:
```
"AI | Score: 7.5 | Retries: 1 | LOW CONFIDENCE"
```

After simplification, it could just be `"AI generated"` or removed entirely. The plan should specify the exact new format.

---

#### L2: Blog H1 safety net implementation details

The plan correctly identifies the double-title bug and proposes a safety net in `blog_generator.py`. The implementation should:
1. After extracting frontmatter, get the first non-empty line of the body
2. If it starts with `# ` and the text matches the frontmatter title (fuzzy), strip it
3. This is a fallback — the primary fix is removing `# {Title}` from the 4 prompt templates and 4 example templates

---

#### L3: No mention of testing strategy for the GPT-5 Mini switch

The plan says "Test fallback by temporarily unsetting OPENAI_API_KEY." But doesn't mention testing that GPT-5 Mini produces compatible output format (JSON for pin copy, JSON for image prompts). Different models may format JSON differently.

**Recommendation:** Run a test batch with GPT-5 Mini and verify JSON parsing succeeds before deploying.

---

## Reference Document Review

The `reference-data-flows-and-naming.md` document is **accurate** with these notes:

1. **Pin schedule schema** — Shows `"morning|afternoon|evening"` slots but the actual pin-schedule.json groups by date first, then slot. The schema example is correct.

2. **Content Queue column layout** — Correctly shows before/after layouts. The "after" layout correctly removes Column M.

3. **`image_source_tier` trace** — Accurately identifies all locations. The conclusion "safe to remove" is correct — the tier is only used for routing, which is being eliminated.

4. **Pipeline step-by-step** — Accurately traces all 8 steps. One minor inaccuracy: Step 7 mentions `"evening"` as a slot, but the actual workflows use `"evening-1"` and `"evening-2"` (two evening slots → combined to a single evening workflow).

5. **Apps Script trigger map** — Correctly shows the new B5 watcher and the N1 shift for regen trigger.

---

## Summary: What to Fix Before Implementation

### Must Fix (will break things)
1. Update all 6 `use_ai_image` filter locations in `blog_deployer.py`
2. Update `read_content_approvals()` and `read_regen_requests()` ranges from `A:M` to `A:L`
3. Update `reset_regen_trigger()` to write `N1` instead of `O1`
4. Update `publish_content_queue.py` regen trigger range from `N1:O1` to `M1:N1`
5. Update Apps Script column detection number (15 → 14)
6. Update regen_content.py imports and call sites for removed/renamed functions
7. Remove the `_process_ai_image_swaps()` CALL BLOCK (lines 428-453), not just the function

### Should Clarify (design decisions needed)
1. Specify exactly what replaces `_source_pin_image()` / `source_image()` — don't say "collapse"
2. Decide what to do with existing `use_ai_image` status rows
3. Decide whether quality metadata fields are omitted or set to defaults
4. Specify `_build_quality_note()` new format

### Nice to Have
1. Test GPT-5 Mini JSON output compatibility before deploying Change 5
2. Add blog H1 stripping safety net with specific implementation
3. Rewrite (not just delete) strategy/current-strategy.md Section 5.3
