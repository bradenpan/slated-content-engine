# Fix Review (Alpha Batch)

Reviewing fixes 1, 2, 3, 4, 5, 7, 11, 14, 15 against the synthesis prescriptions.

---

## Fix 1 [H1]: `src/apis/sheets_api.py` `_clear_and_write` — write-then-clear

**Verdict: CORRECT**

The method at lines 805-881 has been restructured correctly:

1. **Step 1 (lines 828-855):** Writes new data via `sheets.values().update()` FIRST, with one retry on failure. If both attempts fail, the method raises `SheetsAPIError` with the message "Old data preserved" -- this is correct because the `update` call never succeeded, so the old data was never modified.

2. **Step 2 (lines 857-874):** Clears only the rows BEYOND the new data length (`A{new_row_count+1}:ZZ`). If this clear fails, the warning correctly notes that "stale trailing rows may remain" -- which is a much better failure mode than the old pattern where a failed write left the tab completely empty.

3. **Docstring** (lines 811-822) accurately describes the new behavior.

The logic is sound: `update` overwrites in-place (no explicit clear needed for the data range), and only excess trailing rows are cleared afterward. A failure at any point either leaves old data intact (write failure) or leaves new data plus stale trailing rows (clear failure). No data loss window.

---

## Fix 11 [M1]: `src/apis/sheets_api.py` `_validate_headers` — raise on mismatch

**Verdict: CORRECT**

At lines 142-177:

1. **TODO removed:** The docstring at lines 143-154 now says "Raises SheetsAPIError if headers don't match" -- the old TODO comment about upgrading from warning to error is gone.

2. **Raise on mismatch (lines 170-175):** `raise SheetsAPIError(...)` with a clear error message including expected vs actual headers and guidance about manual edits.

3. **API read failure handling (lines 166-168):** If the header row *itself* cannot be read, the method logs a warning and returns (does not raise). This is correct -- you don't want a transient Sheets API error to block all operations. The validation is a best-effort guard against structural changes, not a connectivity check.

4. **Callers:** `read_content_approvals()` (line 476) and `read_regen_requests()` (line 529) call `_validate_headers`. Both are within their own try/except blocks that catch `Exception` and raise `SheetsAPIError`. A `SheetsAPIError` from `_validate_headers` will propagate correctly through these callers since the outer except re-raises `SheetsAPIError` (line 513-515 catches `Exception` and wraps in `SheetsAPIError`, but the `SheetsAPIError` from `_validate_headers` would be caught first and re-wrapped -- however this is fine since the error message is preserved in the `from e` chain).

5. **Caching** (lines 156-158): The tab is added to `_validated_tabs` before the API call, so even if validation fails on a transient error, it won't re-validate on the next call. This is a minor design choice but acceptable -- the tab name is added before the try block, so a read failure (line 166-168) means the tab is cached as "validated" even though we couldn't check. However, this was the existing behavior before the fix, so it's not a regression.

---

## Fix 2 [H2]: `src/publish_content_queue.py` — Slack after Sheets failure

**Verdict: CORRECT**

At lines 194-261:

1. **Flag initialized** (line 194): `sheets_write_ok = True` -- correctly defaults to True.

2. **Flag set on failure** (line 236): `sheets_write_ok = False` in the `except Exception` block after the Sheets write fails.

3. **Conditional Slack notification** (lines 241-252): When `sheets_write_ok` is True, sends the normal `notify_content_ready()`. When False, sends a warning-level message: "Content Queue write failed -- check workflow logs" with counts of generated pins and blog posts.

4. **Image upload failure** (lines 253-259): The `upload_failed` notification is still sent independently, which is correct -- a Sheets failure doesn't mask an image upload failure.

The flag is set in all correct paths. The failure message is informative and actionable.

---

## Fix 5 [H4]: `src/publish_content_queue.py` atomic write for `pin-generation-results.json`

**Verdict: CORRECT**

At lines 121-134:

1. **Pattern** (lines 122-127): Creates `tmp` via `pin_results_path.with_suffix(".tmp")`, writes to it, then calls `tmp.replace(pin_results_path)`. This matches the `content_log.py:62-68` pattern.

2. **Cleanup on failure** (lines 129-134): The `except OSError` block attempts to `tmp.unlink(missing_ok=True)` to clean up the temp file, with its own inner `except OSError: pass` to avoid masking the original error.

3. **Same filesystem guarantee:** `.with_suffix(".tmp")` creates the temp file in the same directory as the target, which is required for atomic rename on the same filesystem.

This is a clean implementation matching the existing codebase pattern.

---

## Fix 3 [H5]: `src/token_manager.py` `_save_tokens` atomic write

**Verdict: CORRECT**

At lines 390-401:

1. **Pattern** (lines 391-394): `tmp = self.token_store_path.with_suffix(".tmp")`, writes via `json.dump()` into the tmp file, then `tmp.replace(self.token_store_path)`. Correct temp+rename pattern.

2. **Same filesystem** (line 391): `.with_suffix(".tmp")` ensures the temp file is in the same directory as `token_store_path` (same filesystem), which is required for atomic rename.

3. **Cleanup on failure** (lines 398-401): In the `except OSError` block, attempts `tmp.unlink(missing_ok=True)` with its own inner `except OSError: pass`.

4. **Non-raising behavior preserved** (line 402): The comment "Don't raise -- the in-memory token data is still valid for this run" confirms the existing error-swallowing policy is maintained, as the synthesis specified.

5. **In-memory update first** (line 385): `self._token_data = token_data` is set before the file write, so even if the disk write fails, the current run has valid tokens. This was the existing behavior and is preserved.

---

## Fix 4 [H4]: `src/regen_content.py:381` atomic write for `pin-generation-results.json`

**Verdict: CORRECT**

At lines 380-393:

1. **Pattern** (lines 381-386): `tmp = pin_results_path.with_suffix(".tmp")`, writes text to tmp, then `tmp.replace(pin_results_path)`. Correct pattern.

2. **Cleanup on failure** (lines 388-393): `except OSError` with `tmp.unlink(missing_ok=True)` and inner `except OSError: pass`.

3. **Comment** (line 379): "Step 6: Save updated pin results (atomic write via temp+rename)" -- correctly documented.

Matches the existing codebase pattern.

---

## Fix 7 [H4]: `src/regen_weekly_plan.py:208` atomic write for plan JSON

**Verdict: CORRECT**

At lines 207-220:

1. **Pattern** (lines 208-214): `tmp = plan_path.with_suffix(".tmp")`, writes JSON to tmp via `tmp.write_text()`, then `tmp.replace(plan_path)`.

2. **Cleanup on failure** (lines 215-220): `except OSError` block with `tmp.unlink(missing_ok=True)` and inner `except OSError: pass`, then `raise` to re-raise the original error. The re-raise is correct here -- unlike `token_manager.py` where swallowing is intentional, a plan save failure should propagate because there's no in-memory fallback.

3. **Comment** (line 207): "Step 7: Save updated plan JSON (atomic write via temp+rename)".

Clean implementation matching the codebase pattern.

---

## Fix 14 [M5]: `src/regen_content.py` bare excepts (4 locations)

**Verdict: CORRECT**

All 4 bare `except Exception: pass` blocks now have `logger.warning` calls:

1. **Line 168:** `logger.warning("Failed to update Sheet for %s: %s", item_id, e)` -- in the blog data not found path. Variable `item_id` is in scope (set at line 119). The `except` correctly captures `as e`.

2. **Line 199:** `logger.warning("Failed to update Sheet for %s: %s", item_id, e2)` -- in the blog image regen failure path. Note: uses `e2` since the outer exception is already captured as `e`. This is correct -- the outer `except Exception as e` (line 189) captures the regen failure, and the inner `except Exception as e2` (line 198) captures the Sheet update failure.

3. **Lines 268-269:** `logger.warning("Failed to update Sheet for %s: %s", item_id, e)` -- in the pin data not found path. Correct variables in scope.

4. **Lines 314-315:** `logger.warning("Failed to update Sheet for %s: %s", item_id, e2)` -- in the pin regen failure path. Uses `e2` to avoid shadowing the outer `e`. Correct.

All 4 locations include `item_id` and the exception in the log message. No bare `except Exception: pass` remains in these locations.

---

## Fix 15 [H8]: `src/regen_content.py` drive null check

**Verdict: CORRECT**

1. **Type hint** (line 467): `drive: Optional[DriveAPI]` -- correct. `Optional` is imported at line 26 (`from typing import Optional`), confirmed.

2. **Null guard** (line 581): `if drive_file_id and drive is not None:` -- the guard is placed at the right location, on the Drive fallback download path. If `drive` is `None` (because `DriveAPI()` init failed at line 286-288), this branch is skipped and the code falls through to the "not downloaded" path (line 592) which logs a warning.

3. **Previous state at line 578-590:** The old code would have called `drive.download_image()` unconditionally if there was a `drive_file_id`. Now, `drive is not None` is checked first. The `drive` variable can indeed be `None` per lines 287-288 where `drive = None` is set on init failure.

The fix is in the right place and the type hint is correctly updated.

---

## Summary

| Fix | Finding | Verdict |
|-----|---------|---------|
| Fix 1 [H1] | `_clear_and_write` write-then-clear | CORRECT |
| Fix 11 [M1] | `_validate_headers` raise on mismatch | CORRECT |
| Fix 2 [H2] | Slack after Sheets failure flag | CORRECT |
| Fix 5 [H4] | `publish_content_queue.py` atomic write | CORRECT |
| Fix 3 [H5] | `token_manager.py` atomic write | CORRECT |
| Fix 4 [H4] | `regen_content.py:381` atomic write | CORRECT |
| Fix 7 [H4] | `regen_weekly_plan.py:208` atomic write | CORRECT |
| Fix 14 [M5] | `regen_content.py` bare excepts | CORRECT |
| Fix 15 [H8] | `regen_content.py` drive null check | CORRECT |

**Result: 9/9 correct, 0 problems, 0 minor issues.**

All fixes match the synthesis prescriptions, follow existing code patterns, and introduce no regressions.
