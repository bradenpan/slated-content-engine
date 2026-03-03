# Fix Review Round 2

**Date:** 2026-02-27
**Reviewer:** fix-reviewer-2 agent
**Scope:** 4 fixes addressing issues found in the round-1 fix review

---

## Summary

**Overall Assessment: PASS**

All 4 fixes are correctly implemented. No regressions introduced. The two logic/completeness issues from round 1 (FIX-9 dead code path, FIX-17 duplication) are properly resolved, the FIX-18 NameError is fixed, and the FIX-10 doc inconsistency is corrected.

---

## Per-Fix Review

### FIX-9: Logic bug in `negative_keyword_pin` violation structure

**Verdict: CORRECT**

**What changed:**

1. `src/plan_validator.py:257-258` — `negative_keyword_pin` violations now emit `"post_id": None, "pin_id": pin_id` (previously `"post_id": pin_id` with no `pin_id` field). This applies to both keyword-match violations (line 257-258) and topic-match violations (line 268-269). The structure is now semantically correct: pin-level violations carry the pin_id and leave post_id as None since a pin is not a post.

2. `src/utils/plan_utils.py:79-89` — The `identify_replaceable_posts` function now has two distinct branches:
   - Line 79-82: `if pid:` — handles violations that already carry a `post_id` (e.g., `negative_keyword_post`, `topic_repetition`). Adds the post_id directly.
   - Line 83-89: `elif v.get("pin_id"):` — handles pin-level violations (e.g., `negative_keyword_pin`). Looks up the pin's `source_post_id` via the `pin_to_source` mapping, checks it is not an `existing:` prefixed post (which cannot be replaced), and adds the resolved source post_id.

   Previously, `post_id` was set to the pin_id value, making the `if pid` branch always fire and add a pin_id into `offending_post_ids`, which would never match anything in `post_index`. The `elif` branch was dead code. Now `post_id` is `None` for pin-level violations, so `if pid` is `False` and control falls through to the `elif` which correctly traces pin -> source post.

3. `tests/test_plan_validator.py:252-253` — The negative keyword pin test now asserts `neg_violations[0]["post_id"] is None` and `neg_violations[0]["pin_id"] == plan["pins"][0]["pin_id"]`, matching the new violation structure.

**Tracing the fix end-to-end:** A pin with pin_id="W1-00" and source_post_id="P1" that matches a negative keyword will emit `{"post_id": None, "pin_id": "W1-00", ...}`. In `identify_replaceable_posts`, `v.get("post_id")` returns `None` (falsy), so the `elif v.get("pin_id")` branch fires. It looks up `pin_to_source.get("W1-00")` which returns `"P1"`. Since `"P1"` does not start with `"existing:"`, it adds `"P1"` to `offending_post_ids`. Then `post_index.get("P1")` finds the actual post object, and the result dict is correctly populated.

The previously dead code path is now reachable and correct.

---

### FIX-18: NameError in `weekly_analysis.py` `__main__` block

**Verdict: CORRECT**

**What changed:**

`src/weekly_analysis.py:508` now has `from src.utils.content_memory import generate_content_memory_summary` inside the `if __name__ == "__main__":` block (line 505).

**Verification:**
- The function `generate_content_memory_summary` exists at `src/utils/content_memory.py:55` and is a public function (renamed from `_generate_content_memory_summary` in FIX-4).
- The import is correctly scoped inside `__main__` so it does not affect the module's normal import behavior (no circular import risk, no unnecessary import at module load time).
- Both `--demo` mode (line 524-527) and `--memory` mode (line 529-531) reference `generate_content_memory_summary`, so both paths are now covered.
- The production workflow (`weekly-review.yml`) imports this function directly via `from src.utils.content_memory import generate_content_memory_summary`, so it is unaffected by this change.

No regression. The round-1 review identified this exact NameError and recommended this exact fix location.

---

### FIX-17: Test deduplication via conftest.py

**Verdict: CORRECT**

**What changed:**

1. `tests/conftest.py:16` — The `create_jpeg_with_exif` helper is defined as a module-level function (not a fixture). The `tmp_dir` fixture at line 10-13 now returns `tmp_path` (the return value was already there from round 1).

2. `tests/test_image_cleaner.py:11` — Imports `create_jpeg_with_exif` from conftest with a local alias: `from conftest import create_jpeg_with_exif as _create_jpeg_with_exif`. All test methods that used the old local `_create_jpeg_with_exif` helper now call this imported version. No local `_create_jpeg_with_exif` function definition exists in this file anymore.

3. `tests/test_image_cleaner_extended.py:17` — Same import pattern: `from conftest import create_jpeg_with_exif as _create_jpeg_with_exif`. No local duplicate definition exists in this file.

**Verification of no remaining duplicates:**
- `test_image_cleaner.py` has no function named `_create_jpeg_with_exif` defined locally. It imports from conftest at line 11.
- `test_image_cleaner_extended.py` has no function named `_create_jpeg_with_exif` defined locally. It imports from conftest at line 17.
- Both files use the `tmp_dir` fixture from conftest (via pytest's automatic fixture discovery).
- The alias pattern (`as _create_jpeg_with_exif`) preserves the call sites unchanged, minimizing diff churn.

No regression. The deduplication is complete.

---

### FIX-10: Doc fix in `promote-and-schedule.yml`

**Verdict: CORRECT**

**What changed:**

`.github/workflows/promote-and-schedule.yml:11` — The input description now reads:
```
'Override pin schedule start date (YYYY-MM-DD). Redistributes all pins across 7 days starting from this date. Leave empty for normal scheduling.'
```

Previously it said "3 days". The default in `redate_schedule.py:17` is `num_days: int = 7`, confirmed by reading the file. The workflow calls `redate(sys.argv[1])` at line 52 of `redate_schedule.py`, which uses the default `num_days=7`.

Documentation now matches the code behavior.

---

## Regressions Check

- **FIX-9:** No regressions. The validator's output structure changed for `negative_keyword_pin` violations only. The only consumers are `plan_utils.py:identify_replaceable_posts` (updated) and test assertions (updated). The `negative_keyword_post` violations are unchanged (still carry `post_id`).
- **FIX-18:** No regressions. The import is scoped to `__main__` only. Module-level behavior unchanged.
- **FIX-17:** No regressions. Both test files import from conftest. All test methods continue to use the same function signature. The `tmp_dir` fixture is auto-discovered by pytest from conftest.
- **FIX-10:** No regressions. Documentation-only change.

---

## Verdict Summary

| Fix | Status | Notes |
|-----|--------|-------|
| FIX-9 (logic bug) | CORRECT | Dead code path now reachable; pin->post tracing works correctly |
| FIX-18 (NameError) | CORRECT | Import in correct scope; function exists in content_memory |
| FIX-17 (dedup) | CORRECT | No remaining duplicates; alias pattern preserves call sites |
| FIX-10 (doc fix) | CORRECT | "7 days" matches redate_schedule.py default |

**All 4 round-2 fixes pass review.**
