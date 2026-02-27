# Consolidated Fix Plan

**Date:** 2026-02-27
**Source:** Cross-referenced from review-a.md, review-b.md, review-c.md
**Scope:** Refactor commits f534be8..16db0e6 (8 commits, 69 files)

---

## Summary

- **Total unique issues identified:** 22
- **Flagged by 2+ reviewers (high confidence):** 8
- **Flagged by all 3 reviewers:** 4

The three reviews are strongly aligned. All three independently found the `PROJECT_ROOT` NameError, the private function naming issue, the `redate_schedule.py` problems, and the `notify-failure` injection risk. Two of three also flagged the `extract_drive_file_id` docstring/implementation mismatch, missing plan_validator tests, broad `git add` in commit-data, and the `monthly_review.py` indirect import of `load_content_log`.

---

## Critical Fixes

### FIX-1. `NameError`: `PROJECT_ROOT` not imported in `monthly_review.py`

**Flagged by:** A (2.1), B (C1), C (C-1) -- all 3 reviewers
**Severity:** Critical -- runtime crash in production
**File:** `src/monthly_review.py:498`

**Problem:** `_analyze_board_density()` references `PROJECT_ROOT` which is never imported. The imports at line 55 bring in `ANALYSIS_DIR`, `STRATEGY_DIR`, and `DATA_DIR` but not `PROJECT_ROOT`. This crashes every monthly review run.

**Fix:**
1. Open `src/monthly_review.py`
2. At line 498, replace:
   ```python
   board_structure_path = PROJECT_ROOT / "strategy" / "board-structure.json"
   ```
   with:
   ```python
   board_structure_path = STRATEGY_DIR / "board-structure.json"
   ```
3. No import changes needed -- `STRATEGY_DIR` is already imported at line 55.

**Risks:** None. `STRATEGY_DIR` is defined as `PROJECT_ROOT / "strategy"` in `src/paths.py`, so the resolved path is identical.

---

### FIX-2. Shell injection in `promote-and-schedule.yml` workflow input

**Flagged by:** A (2.2) -- 1 reviewer
**Severity:** Critical -- security vulnerability

**File:** `.github/workflows/promote-and-schedule.yml:61`

**Problem:** The `override_pin_start_date` workflow_dispatch input is interpolated directly into a shell command without quoting:
```yaml
run: python -m src.redate_schedule ${{ github.event.inputs.override_pin_start_date }}
```
A specially crafted input could execute arbitrary shell commands.

**Fix:**
1. Open `.github/workflows/promote-and-schedule.yml`
2. Replace the direct interpolation with an environment variable:
   ```yaml
   env:
     PIN_START_DATE: ${{ github.event.inputs.override_pin_start_date }}
   run: python -m src.redate_schedule "$PIN_START_DATE"
   ```

**Risks:** None. The value is passed identically, just safely through an env var.

---

## Important Fixes

### FIX-3. `extract_drive_file_id()` does not handle `/d/FILE_ID/` URLs despite docstring claiming it does

**Flagged by:** B (B1), C (C-2) -- 2 reviewers
**Severity:** Important -- silent failure for a documented code path

**File:** `src/utils/image_utils.py:4-24`

**Problem:** The docstring claims the function handles both `?id=FILE_ID` and `/d/FILE_ID/` URL formats. The implementation only handles `?id=` URLs. The `/d/` format (e.g., `https://drive.google.com/file/d/ABC123/view`) silently returns `None`, causing hero image downloads to fail in `regen_content.py`.

**Fix:**
1. Open `src/utils/image_utils.py`
2. In `extract_drive_file_id()`, add handling for the `/d/` pattern after the existing `id=` check:
   ```python
   def extract_drive_file_id(url: str) -> str | None:
       if not url:
           return None
       # Handle ?id=FILE_ID format
       if "id=" in url:
           file_id = url.split("id=")[1].split("&")[0]
           return file_id if file_id else None
       # Handle /d/FILE_ID/ format
       if "/d/" in url:
           parts = url.split("/d/")[1].split("/")
           file_id = parts[0] if parts else None
           return file_id if file_id else None
       return None
   ```
3. Add a test case in `tests/test_mime_detection.py` (or a new `tests/test_image_utils.py`) for `/d/` URLs.

**Risks:** Low. The new code path only activates for URLs containing `/d/` that did not already contain `id=`. Existing behavior for `?id=` URLs is unchanged.

---

### FIX-4. Private functions (`_parse_date`, `_get_entry_date`) used as cross-module public API

**Flagged by:** A (3.1), B (D1), C (C-4) -- all 3 reviewers
**Severity:** Important -- API design / maintenance hazard

**Files:**
- Defined in: `src/utils/content_memory.py:28,41`
- Imported by: `src/plan_validator.py:16`, `src/utils/plan_utils.py:10`

**Problem:** These underscore-prefixed functions are imported by two other modules, making them de facto public API while signaling "private" to developers. A refactorer could break two external modules thinking they are safe to rename.

**Fix (Option A -- preferred, minimal change):**
1. In `src/utils/content_memory.py`, rename `_parse_date` to `parse_date` and `_get_entry_date` to `get_entry_date` (remove leading underscores).
2. Update all internal call sites within `content_memory.py`.
3. Update imports in `src/plan_validator.py:16` and `src/utils/plan_utils.py:10` to use the new names.

**Fix (Option B -- cleaner separation):**
1. Create `src/utils/date_helpers.py` with `parse_date()` and `get_entry_date()`.
2. Update all three consuming modules to import from `date_helpers`.
3. Remove the functions from `content_memory.py`.

**Risks:** Low. Pure rename/move. All call sites are known (3 files total).

---

### FIX-5. `notify-failure` composite action has string interpolation injection risk

**Flagged by:** A (3.6), B (S1), C (C-6) -- all 3 reviewers
**Severity:** Important -- fragile/insecure pattern

**File:** `.github/actions/notify-failure/action.yml:17`

**Problem:** Inputs are interpolated directly into a Python string literal. If any input contains a single quote, it breaks Python syntax. While inputs currently come from hardcoded strings, this is a bad pattern.

**Fix:**
1. Open `.github/actions/notify-failure/action.yml`
2. Replace the direct interpolation with environment variables:
   ```yaml
   env:
     WORKFLOW_NAME: ${{ inputs.workflow_name }}
     RUN_URL: ${{ inputs.run_url }}
   run: |
     python -c "
     import os
     from src.apis.slack_notify import SlackNotify
     notifier = SlackNotify()
     notifier.notify_failure(os.environ['WORKFLOW_NAME'], 'Workflow failed. Check: ' + os.environ['RUN_URL'])
     "
   ```

**Risks:** None. Functionally identical, just safer value passing.

---

### FIX-6. `redate_schedule.py` bypasses centralized paths and lacks UTF-8 encoding

**Flagged by:** A (3.2, 3.3), B (B2), C (C-7 partially) -- all 3 reviewers
**Severity:** Important -- inconsistency + potential data corruption on Windows

**File:** `src/redate_schedule.py:15,22,33`

**Problem:** Two issues in one file:
1. Default path is hardcoded as `"data/pin-schedule.json"` (relative string), bypassing `src/paths.py` centralization. Breaks if run from a non-root directory.
2. Both `read_text()` (line 22) and `write_text()` (line 33) omit `encoding="utf-8"`. On Windows, this defaults to cp1252 and can corrupt non-ASCII characters.

**Fix:**
1. Open `src/redate_schedule.py`
2. Add import: `from src.paths import DATA_DIR`
3. Change the function signature:
   ```python
   def redate(start_date: str, schedule_path: Path = None) -> None:
       path = schedule_path or (DATA_DIR / "pin-schedule.json")
   ```
4. Add encoding to read:
   ```python
   schedule = json.loads(path.read_text(encoding="utf-8"))
   ```
5. Add encoding to write:
   ```python
   path.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
   ```

**Risks:** Low. The resolved path is the same (`DATA_DIR` = `PROJECT_ROOT / "data"`). Encoding change is strictly safer.

---

### FIX-7. `plan_validator.py` has no tests

**Flagged by:** A (3.5), B (implied via D3), C (C-5) -- 3 reviewers (2 explicitly, 1 implicitly)
**Severity:** Important -- test coverage gap for critical business logic

**File:** `src/plan_validator.py` (298 lines, 8 validation checks)

**Problem:** The plan validator is the gatekeeper preventing bad plans from reaching production. It has zero tests despite complex logic: pillar mix tolerances, fuzzy topic similarity, consecutive template detection, negative keyword matching.

**Fix:**
1. Create `tests/test_plan_validator.py`
2. Write tests covering at minimum:
   - Pin count validation (exact 28, too few, too many)
   - Pillar mix tolerance (within and outside 15% tolerance)
   - Topic repetition detection (word overlap > 60% threshold)
   - Board limit validation (max 4 pins per board)
   - Treatment limit validation (max 4 of same treatment)
   - Consecutive template detection
   - Day distribution (4 pins per day)
   - Negative keyword matching
3. Use injected `content_log`, `board_structure`, and `negative_keywords` parameters to avoid needing real data files.
4. Consider adding `today: date = None` parameter to `validate_plan()` for deterministic date testing (see FIX-10).

**Risks:** None -- adding tests only. May reveal bugs in the validation logic.

---

### FIX-8. `monthly_review.py` does not use dependency injection

**Flagged by:** A (3.7) -- 1 reviewer
**Severity:** Important -- inconsistency with refactor pattern

**File:** `src/monthly_review.py:112-144`

**Problem:** `run_monthly_review()` creates `ClaudeAPI()`, `SheetsAPI()`, and `SlackNotify()` directly inside the function body, unlike every other orchestration function which accepts these as optional parameters. This makes the monthly review impossible to unit test without live API credentials.

**Fix:**
1. Open `src/monthly_review.py`
2. Change `run_monthly_review()` signature to accept optional API parameters:
   ```python
   def run_monthly_review(claude=None, sheets=None, slack=None):
       claude = claude or ClaudeAPI()
       sheets = sheets or SheetsAPI()
       slack = slack or SlackNotify()
   ```
3. Update any internal references to use the local variables instead of creating new instances.

**Risks:** Low. Default behavior is identical (creates instances when None is passed). Just enables testing.

---

### FIX-9. Fragile string parsing in `identify_replaceable_posts()`

**Flagged by:** B (D2) -- 1 reviewer
**Severity:** Important -- brittle coupling between validator messages and downstream code

**File:** `src/utils/plan_utils.py:87-89`

**Problem:** `identify_replaceable_posts()` extracts pin IDs by parsing violation message strings (`msg.split("'")[1]`). This depends on the exact message format from `plan_validator.py`. If message wording changes, this silently extracts wrong values.

**Fix:**
1. In `src/plan_validator.py`, add a `pin_id` field to the violation dict for `negative_keyword_pin` violations (the pin_id is already available in the validation loop at that point):
   ```python
   violations.append({
       "category": "negative_keyword_pin",
       "message": f"Pin '{pin_id}' targets keyword '...'",
       "post_id": pin_id,  # <-- already set, but ensure it's consistent
       "severity": "targeted",
   })
   ```
2. In `src/utils/plan_utils.py`, update `identify_replaceable_posts()` to read `v.get("post_id")` instead of parsing the message string.
3. Verify all violation categories set `post_id` when the violation is targeted.

**Risks:** Low. The `post_id` field already exists in most violation types; this just ensures consistent usage.

---

### FIX-10. `redate_schedule.py` hardcodes 3-day spread, inconsistent with 7-day posting week

**Flagged by:** A (3.4), B (B3), C (C-7) -- all 3 reviewers
**Severity:** Important -- behavioral inconsistency

**File:** `src/redate_schedule.py:24`

**Problem:** `num_days = 3` hardcodes a 3-day spread, but the pipeline assumes a 7-day posting week (Tue-Mon, 4 pins/day = 28 pins). Spreading 28 pins across 3 days creates ~9 pins/day, violating the `PINS_PER_DAY` constraint in `plan_validator.py`.

**Fix (choose one):**
- **Option A (if intentional):** Add a clear comment and docstring explaining this is for partial/override schedules, not the main pipeline path:
  ```python
  num_days = 3  # Override mode: compress schedule for testing or catch-up
  ```
- **Option B (if unintentional):** Import from config or default to 7:
  ```python
  num_days = 7  # Standard posting week: Tue-Mon
  ```
- **Option C (flexible):** Make it a parameter:
  ```python
  def redate(start_date: str, schedule_path: Path = None, num_days: int = 7) -> None:
  ```

**Recommendation:** Option C is best -- it makes the function flexible while defaulting to the correct pipeline behavior. The workflow can pass `num_days=3` if that's the intended override behavior.

**Risks:** If changed from 3 to 7, existing override workflows that depend on the 3-day spread will behave differently. Verify `promote-and-schedule.yml` usage before changing.

---

## Minor Fixes

### FIX-11. `apply_jitter()` docstring contradicts implementation

**Flagged by:** C (C-3) -- 1 reviewer
**File:** `src/post_pins.py:305`

**Problem:** Docstring says "random(0, 5400)" but code uses `INITIAL_JITTER_MAX` which is `900` (15 minutes).

**Fix:** Update the docstring at line 305 to say `random(0, 900)` or, better, reference the constant name: "random(0, INITIAL_JITTER_MAX)".

---

### FIX-12. `monthly_review.py` imports `load_content_log` from `pull_analytics` instead of canonical `content_log`

**Flagged by:** A (5.10), B (N2), C (C-14) -- all 3 reviewers
**File:** `src/monthly_review.py:50-54`

**Problem:** The refactor extracted `load_content_log` to `src/utils/content_log.py`, but `monthly_review.py` still imports it from `src/pull_analytics` (which re-exports it). This creates an unnecessary indirection.

**Fix:**
1. In `src/monthly_review.py`, change:
   ```python
   from src.pull_analytics import load_content_log, compute_derived_metrics, aggregate_by_dimension
   ```
   to:
   ```python
   from src.utils.content_log import load_content_log
   from src.pull_analytics import compute_derived_metrics, aggregate_by_dimension
   ```

---

### FIX-13. `commit-data` composite action uses broad `git add data/ analysis/`

**Flagged by:** A (4.5), B (N3), C (C-11) -- all 3 reviewers
**File:** `.github/actions/commit-data/action.yml:13`

**Problem:** Stages all files in `data/` and `analysis/`, which could accidentally commit debug or temp files.

**Fix:** Replace with targeted file patterns:
```yaml
git add data/content-log.jsonl data/pin-schedule.json analysis/
```
Or use a `.gitignore` in `data/` to exclude unwanted files (if not already present). Verify which files in `data/` and `analysis/` are expected to be committed before narrowing.

---

### FIX-14. Fragile base64 slice for MIME detection in `pinterest_api.py`

**Flagged by:** A (4.1) -- 1 reviewer
**File:** `src/apis/pinterest_api.py:134`

**Problem:** Decodes first 16 base64 characters (12 bytes). WebP magic number check needs bytes 8-12. This works but has no margin.

**Fix:** Change `[:16]` to `[:24]` (yields 18 bytes, comfortable margin):
```python
raw_bytes = base64.b64decode(image_base64[:24])
```

---

### FIX-15. Duplicate `_parse_date` calls in content_memory list comprehensions

**Flagged by:** A (4.4) -- 1 reviewer
**File:** `src/utils/content_memory.py:117-118, 262-263, 347-348`

**Problem:** `_parse_date(_get_entry_date(e))` is called twice per entry in list comprehensions -- once to check truthiness, once to compare against the window start.

**Fix:** Use walrus operator:
```python
recent_entries = [
    e for e in content_log
    if (d := parse_date(get_entry_date(e)))
    and d >= topic_window_start
]
```
Apply to all three occurrences.

---

### FIX-16. `token_manager.py` opens file without `encoding` parameter

**Flagged by:** A (4.6) -- 1 reviewer
**File:** `src/token_manager.py:354,392`

**Problem:** Both `open()` calls omit `encoding="utf-8"`. Inconsistent with the rest of the codebase, though token data is ASCII-only.

**Fix:** Add `encoding="utf-8"` to both file opens:
```python
with open(self.token_store_path, "r", encoding="utf-8") as f:
```
```python
with open(self.token_store_path, "w", encoding="utf-8") as f:
```

---

### FIX-17. No `conftest.py` in tests directory

**Flagged by:** A (4.8), B (N4) -- 2 reviewers

**Problem:** No shared fixtures; test helpers are duplicated across files (e.g., `_create_jpeg_with_exif()` in both `test_image_cleaner.py` and `test_image_cleaner_extended.py`).

**Fix:**
1. Create `tests/conftest.py`
2. Move shared helpers (like `_create_jpeg_with_exif`) into shared fixtures.
3. Add commonly needed fixtures (temp directories, sample plan data, mock API clients) as the test suite grows.

---

### FIX-18. `weekly_analysis.py` re-exports `generate_content_memory_summary` for workflow

**Flagged by:** C (C-8) -- 1 reviewer
**File:** `src/weekly_analysis.py:47`

**Problem:** The function lives in `src.utils.content_memory` but the workflow imports through `src.weekly_analysis`. This is an unnecessary indirection.

**Fix:** Update `.github/workflows/weekly-review.yml:52` to import directly:
```yaml
python -c "from src.utils.content_memory import generate_content_memory_summary; generate_content_memory_summary()"
```
Then remove the re-export from `src/weekly_analysis.py`.

---

### FIX-19. `config.py` reads `OPENAI_CHAT_MODEL` from env at import time

**Flagged by:** C (C-10) -- 1 reviewer
**File:** `src/config.py:24`

**Problem:** All other config values are pure constants, but this one reads from environment at import time, making it inconsistent and hard to override in tests.

**Fix:** Document this as intentional (it allows runtime model override) or convert to a function:
```python
def get_openai_chat_model() -> str:
    return os.getenv("OPENAI_CHAT_MODEL", "gpt-5-mini")
```
**Recommendation:** This is low-priority. The env-based override is arguably the right pattern for a model name. Add a comment explaining why it differs from the other constants.

---

## Deferred / Won't Fix

### D-1. `content_log.py` `is_pin_posted()` reads the full file on each call

**Flagged by:** B (D6), C (C-9) -- 2 reviewers

**Reason to defer:** Current content log is ~200 entries. The O(n) per-pin-check is negligible at this scale. Optimizing (e.g., caching, loading once per posting run) would add complexity for no measurable benefit. Revisit if the content log grows beyond ~5,000 entries.

### D-2. OpenAI chat API has minimal retry logic

**Flagged by:** B (D4) -- 1 reviewer

**Reason to defer:** The OpenAI API is used for lower-priority tasks (pin copy, image prompts) with Claude as fallback. Adding exponential backoff would be good but is not urgent -- the existing fallback behavior handles transient failures. Can be improved when OpenAI becomes a reliability bottleneck.

### D-3. `date.today()` not injected for testability

**Flagged by:** B (D3, D5), C (implicit in C-12) -- 2 reviewers

**Reason to defer:** Multiple modules use `date.today()` directly. While injecting it would improve testability, it affects many files and the validation tests (FIX-7) can use monkeypatching via pytest's `monkeypatch` fixture in the near term. Consider adding date injection when writing the plan_validator tests, but don't retrofit it across all modules now.

### D-4. `regen_content.py` remains large (~810 lines)

**Flagged by:** C (observation 9) -- 1 reviewer

**Reason to defer:** The file was already reduced in this refactor. Further splitting (blog regen vs. pin regen) is a valid future improvement but not a bug or correctness issue. Defer to a future refactor pass.

### D-5. Topic repetition uses word overlap instead of semantic similarity

**Flagged by:** C (C-12) -- 1 reviewer

**Reason to defer:** The word-overlap approach is a known simplification. Semantic similarity would require an embedding model or NLP library, adding complexity and cost. The current approach works adequately for the topic naming conventions in use. Revisit if false positives/negatives become a problem in practice.

### D-6. `SlackNotify` silently degrades when webhook URL is missing

**Flagged by:** A (4.7) -- 1 reviewer

**Reason to defer:** Silent degradation is the intended design for a notification service -- crashing the pipeline because Slack is misconfigured would be worse. The warning log is sufficient. No change needed.

### D-7. `image_cleaner.py` always outputs JPEG regardless of output path extension

**Flagged by:** B (N5) -- 1 reviewer

**Reason to defer:** This is documented as intentional behavior. The pipeline only produces JPEG pins. No change needed.

### D-8. Claude cost rates in `config.py` may become stale

**Flagged by:** C (C-15) -- 1 reviewer

**Reason to defer:** Cost tracking is approximate by design. Adding an automated staleness check would over-engineer this. Periodically verify manually when reviewing costs.

---

## Implementation Order

Recommended sequence for implementing fixes:

1. **FIX-1** (NameError) -- 1-line fix, prevents production crash
2. **FIX-2** (shell injection in workflow) -- 2-line fix, security
3. **FIX-5** (notify-failure injection) -- small YAML change, security
4. **FIX-6** (redate_schedule paths + encoding) -- small file, self-contained
5. **FIX-3** (extract_drive_file_id /d/ pattern) -- add missing functionality
6. **FIX-4** (private function naming) -- rename across 3 files
7. **FIX-9** (violation string parsing) -- structural improvement to plan_validator
8. **FIX-10** (redate 3-day hardcode) -- needs decision on intended behavior
9. **FIX-8** (monthly_review DI) -- consistency improvement
10. **FIX-7** (plan_validator tests) -- largest effort, benefits from FIX-4 and FIX-9 being done first
11. **FIX-11 through FIX-19** (minor fixes) -- can be batched
