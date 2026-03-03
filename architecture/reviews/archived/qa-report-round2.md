# QA Report Round 2

**Date:** 2026-02-27
**Agent:** qa-agent-2
**Scope:** Verify 4 round-2 fixes (FIX-9, FIX-10, FIX-17, FIX-18)

---

## Overall Verdict: PASS

All 7 QA checks passed. 114 tests pass, all fixes are correctly applied, no stale references found.

---

## Check Results

### 1. Full Test Suite

**Result: PASS**

```
114 passed, 2 warnings in 5.71s
```

All 114 tests pass. The 2 warnings are pre-existing Pillow deprecation notices (mode I PNG saving, palette transparency) -- not related to the fixes.

### 2. test_plan_validator.py Specifically

**Result: PASS**

```
21 passed in 0.07s
```

All 21 tests pass, including:
- `test_pin_targets_negative_keyword` -- asserts `post_id is None` and `pin_id == plan["pins"][0]["pin_id"]` (validates FIX-9 structure)
- `test_post_targets_negative_keyword` -- asserts `post_id` is set correctly for post-level violations
- `test_pin_topic_contains_negative_keyword` -- asserts topic-match violations also carry the corrected structure

### 3. Image Cleaner Tests

**Result: PASS**

```
52 passed, 2 warnings in 6.22s
```

Both `test_image_cleaner.py` (21 tests) and `test_image_cleaner_extended.py` (31 tests) pass. Both files correctly import `create_jpeg_with_exif` from `conftest.py`:
- `tests/test_image_cleaner.py:11` -- `from conftest import create_jpeg_with_exif as _create_jpeg_with_exif`
- `tests/test_image_cleaner_extended.py:17` -- `from conftest import create_jpeg_with_exif as _create_jpeg_with_exif`

No local duplicates of `_create_jpeg_with_exif` exist in either file. The shared helper lives in `tests/conftest.py:16`.

### 4. FIX-18: weekly_analysis __main__

**Result: PASS**

- `src/weekly_analysis.py:505` has `if __name__ == "__main__":` block
- `src/weekly_analysis.py:508` has `from src.utils.content_memory import generate_content_memory_summary` import inside the `__main__` block
- Both `--demo` (line 525) and `--memory` (line 530) paths reference `generate_content_memory_summary`
- Direct import test (`from src.weekly_analysis import *`) fails with `ModuleNotFoundError: No module named 'anthropic'` -- this is an expected environment dependency (the `anthropic` package is not installed in the test environment), not a code defect. The module-level import of `ClaudeAPI` triggers this. The `__main__` block fix itself is correct.

### 5. FIX-9: plan_utils Tracing (No Stale References)

**Result: PASS**

Searched for the old pattern where `post_id` was set to `pin_id` for `negative_keyword_pin` violations:
- `grep "post_id.*=.*pin_id"` in `src/` -- no matches
- `grep '"post_id": pin_id'` in `src/` -- no matches

Current code at `src/plan_validator.py:257-258` and `:268-269` correctly emits `"post_id": None, "pin_id": pin_id`.

Current code at `src/utils/plan_utils.py:79-89` correctly branches:
- Line 80: `if pid:` -- handles post-level violations
- Line 83: `elif v.get("pin_id"):` -- handles pin-level violations, traces to source post via `pin_to_source`

### 6. Stale References Check

**Result: PASS**

- No references to old private name `_generate_content_memory_summary` in `src/`
- No stale "3 days" text in `promote-and-schedule.yml` (line 11 correctly says "7 days")
- No broken imports detected

### 7. YAML Validation

**Result: PASS**

```python
import yaml; yaml.safe_load(open('.github/workflows/promote-and-schedule.yml'))
# -> YAML valid
```

`.github/workflows/promote-and-schedule.yml` parses without errors.

---

## Summary Table

| Check | Status | Details |
|-------|--------|---------|
| Full test suite (114 tests) | PASS | 114 passed, 2 warnings |
| test_plan_validator.py (21 tests) | PASS | All pass including updated negative keyword tests |
| Image cleaner tests (52 tests) | PASS | Both files use conftest helper, no duplicates |
| FIX-18 weekly_analysis __main__ | PASS | Import present at line 508, both code paths covered |
| FIX-9 plan_utils tracing | PASS | No stale post_id=pin_id pattern, correct branching |
| Stale references | PASS | No broken imports or outdated references |
| YAML validation | PASS | promote-and-schedule.yml is valid YAML |

**All checks pass. Round-2 fixes are verified.**
