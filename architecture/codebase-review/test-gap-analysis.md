# Test Gap Analysis

Analysis of test coverage for the 20 fixes applied from the codebase review synthesis.
Evaluated against the existing test suite: `test_config.py`, `test_content_log.py`,
`test_paths.py`, `test_pin_schedule.py`, `test_plan_utils.py`, `test_image_cleaner.py`,
`test_image_cleaner_extended.py`, `test_mime_detection.py`, `test_plan_validator.py`.

---

## Already Covered

| Fix | Existing Test | Coverage |
|-----|--------------|----------|
| Fix 8 (`redate_schedule.py` — use `save_pin_schedule()`) | `test_pin_schedule.py` | `save_pin_schedule()` round-trip, overwrite, and empty-schedule behavior are all tested. The fix replaces direct `write_text()` with a call to `save_pin_schedule()`, which is already proven correct by these tests. What is NOT covered: the `redate()` function itself calling `save_pin_schedule()` instead of `path.write_text()`. |

---

## Tests Recommended

### Test 1: Sheets write-then-clear preserves data on clear failure
- **Covers fix:** #1 (H1 — `_clear_and_write` restructured to write-then-clear)
- **File:** `tests/test_sheets_write_pattern.py`
- **Scenario:** Call `_clear_and_write` where the `update` (write) call succeeds but the `clear` call raises an exception. Verify the tab still has the new data (i.e., the write already persisted before the clear was attempted). Then test the inverse: write fails on both attempts. Verify the exception propagates (old data untouched).
- **Mocks:** Mock `self.sheets.values().update().execute()` to succeed. Mock `self.sheets.values().clear().execute()` to raise `Exception("API error")`. For the second scenario, mock `update().execute()` to raise on both calls.
- **Asserts:**
  - Scenario A (clear fails): No exception raised by `_clear_and_write`. Logger emits a warning about stale trailing rows. The write call was executed exactly once.
  - Scenario B (write fails twice): `SheetsAPIError` is raised. The `clear` call was never executed (data not destroyed).
- **Priority:** HIGH

### Test 2: Sheets write failure flag prevents false Slack notification
- **Covers fix:** #2 (H2 — `publish_content_queue.py` conditional Slack on Sheets failure)
- **File:** `tests/test_publish_content_queue.py`
- **Scenario:** Run the Sheets-write + Slack-notification sequence from `publish()`. When the Sheets write raises an exception, verify the Slack notification says "Content Queue write failed" instead of the normal "content ready" message.
- **Mocks:** Mock `SheetsAPI` to raise on `write_content_queue()`. Mock `SlackNotify` to capture the notification text.
- **Asserts:**
  - When Sheets write fails: `slack.notify()` is called with a message containing "write failed", NOT `slack.notify_content_ready()`.
  - When Sheets write succeeds: `slack.notify_content_ready()` is called normally.
- **Priority:** HIGH

### Test 3: Token store atomic write pattern
- **Covers fix:** #3 (H5 — `token_manager.py` temp+rename for `_save_tokens`)
- **File:** `tests/test_token_manager.py`
- **Scenario:** Test that `_save_tokens()` uses temp+rename. Create a valid token-store.json with known content. Call `_save_tokens()` with new data. Verify the file contains the new data. Then test the crash scenario: mock `tmp.replace()` to raise `OSError`. Verify the original file is untouched (the temp file should be cleaned up).
- **Mocks:** For the crash test: `unittest.mock.patch.object(Path, 'replace', side_effect=OSError("disk full"))`.
- **Asserts:**
  - Normal case: file contains new token data after save, no `.tmp` file left behind.
  - Failure case: `OSError` is caught (not raised, per the existing non-raising behavior). Original file content is unchanged. `.tmp` file is cleaned up.
- **Priority:** HIGH

### Test 4: Atomic write pattern for pin-generation-results.json (regen_content)
- **Covers fix:** #4 (H4 — `regen_content.py:381-384` temp+rename)
- **File:** `tests/test_atomic_writes.py`
- **Scenario:** Write a known `pin-generation-results.json` file. Simulate the atomic write pattern by calling the save logic. Verify the temp file is not left behind on success. Then simulate a write failure by mocking `tmp.replace()` to raise, and verify the original file is preserved.
- **Mocks:** `Path.replace` (to simulate rename failure), `Path.unlink` (to verify cleanup).
- **Asserts:**
  - Success: file has new content, no `.tmp` leftover.
  - Failure: original file unchanged, `.tmp` cleaned up, `OSError` logged.
- **Priority:** HIGH

### Test 5: Atomic write pattern for pin-generation-results.json (publish_content_queue)
- **Covers fix:** #5 (H4 — `publish_content_queue.py:122-128` temp+rename)
- **File:** `tests/test_atomic_writes.py` (same file as Test 4, shared pattern)
- **Scenario:** Same pattern as Test 4 but exercising the publish_content_queue save path. Since the pattern is identical (temp+rename), this could be a parameterized test that validates the pattern generically on any file path.
- **Mocks:** Same as Test 4.
- **Asserts:** Same as Test 4.
- **Priority:** MEDIUM (same pattern as Test 4 — test one thoroughly, the other can be lighter)

### Test 6: Atomic write pattern for weekly plan JSON
- **Covers fix:** #6 (H4 — `generate_weekly_plan.py:309-312` temp+rename)
- **File:** `tests/test_atomic_writes.py` (shared)
- **Scenario:** Same temp+rename pattern. Could be covered by a single parameterized test helper that validates the atomic write contract.
- **Mocks:** Same as Test 4.
- **Asserts:** Same as Test 4.
- **Priority:** MEDIUM (same pattern)

### Test 7: Atomic write pattern for regen_weekly_plan JSON
- **Covers fix:** #7 (H4 — `regen_weekly_plan.py:208-211` temp+rename)
- **File:** `tests/test_atomic_writes.py` (shared)
- **Scenario:** Same temp+rename pattern.
- **Mocks:** Same as Test 4.
- **Asserts:** Same as Test 4.
- **Priority:** MEDIUM (same pattern)

### Test 8: Plan structure validation rejects bad structures
- **Covers fix:** #9 (H3 — `_validate_plan_structure()` in `generate_weekly_plan.py`)
- **File:** `tests/test_plan_structure_validation.py`
- **Scenario:** Test `_validate_plan_structure()` directly with various invalid inputs:
  (a) plan is a string (not a dict), (b) plan is a dict but missing `blog_posts` key,
  (c) plan has `blog_posts` as an empty list, (d) plan has `pins` key but it's a string
  instead of a list, (e) plan is a valid dict with both keys and non-empty lists.
- **Mocks:** None needed — pure function.
- **Asserts:**
  - Cases a-d: `ValueError` raised with descriptive message mentioning the problem.
  - Case e: No exception raised.
  - Case b message: contains "blog_posts".
  - Case c message: contains "non-empty list".
- **Priority:** HIGH

### Test 9: Blog post validation raises on missing critical frontmatter
- **Covers fix:** #10 (H6 — `_validate_generated_post` raises on missing title/slug/description)
- **File:** `tests/test_blog_validation.py`
- **Scenario:** Call `_validate_generated_post()` with MDX content that has frontmatter but is missing `title`, `slug`, or `description`. Verify it raises `BlogGeneratorError`. Also test that a post with all three fields but missing word count or CTA does NOT raise (only warns).
- **Mocks:** The method is on `BlogGenerator` instance, so instantiate with mocked dependencies or extract the validation logic. May need to mock `ClaudeAPI` and `SheetsAPI` for the constructor.
- **Asserts:**
  - Missing `title`: raises `BlogGeneratorError` with message containing "title".
  - Missing `slug`: raises `BlogGeneratorError` with message containing "slug".
  - Missing `description`: raises `BlogGeneratorError` with message containing "description".
  - Empty `title` (whitespace only): raises `BlogGeneratorError`.
  - All present but low word count: does NOT raise, only logs warning.
- **Priority:** HIGH

### Test 10: Sheets header validation raises on mismatch
- **Covers fix:** #11 (M1 — `_validate_headers` raises `SheetsAPIError` on mismatch)
- **File:** `tests/test_sheets_header_validation.py`
- **Scenario:** Call `_validate_headers()` with mismatched headers. Verify it raises `SheetsAPIError` instead of only logging a warning.
- **Mocks:** Mock `self.sheets.values().get().execute()` to return headers that don't match expected.
- **Asserts:**
  - Mismatched headers: `SheetsAPIError` raised with message describing the mismatch.
  - Matching headers: no exception, tab added to `_validated_tabs`.
  - Second call for same tab: no API call (cached).
- **Priority:** HIGH

### Test 11: OpenAI HTTP errors wrapped in OpenAIChatAPIError
- **Covers fix:** #16 (M3 — `openai_chat_api.py` wraps `raise_for_status()` in `OpenAIChatAPIError`)
- **File:** `tests/test_openai_error_wrapping.py`
- **Scenario:** Call `call_gpt5_mini()` with a response that returns HTTP 500. Verify the raised exception is `OpenAIChatAPIError` (not raw `requests.HTTPError`).
- **Mocks:** Mock `requests.post` to return a `Response` object with status 500 and a body. Use `requests_mock` or `unittest.mock.patch('requests.post')`.
- **Asserts:**
  - HTTP 500: raises `OpenAIChatAPIError`, not `requests.HTTPError`.
  - HTTP 400: raises `OpenAIChatAPIError`.
  - The `__cause__` of the exception is the original `requests.HTTPError` (chained via `from e`).
- **Priority:** HIGH

### Test 12: Claude API narrows exception catch for GPT-5 Mini fallback
- **Covers fix:** #17 (M4 — `claude_api.py` narrows `except Exception` to specific types)
- **File:** `tests/test_claude_api_fallback.py`
- **Scenario:** Call `generate_pin_copy_batch()` where `call_gpt5_mini` raises different exception types. Verify that `OpenAIChatAPIError` triggers the Sonnet fallback, but a `TypeError` or `KeyError` (programming bug) propagates uncaught.
- **Mocks:** Mock `call_gpt5_mini` to raise different exception types. Mock `_call_api` (the Sonnet fallback).
- **Asserts:**
  - `OpenAIChatAPIError` from GPT-5 Mini: caught, falls back to `_call_api` (Sonnet).
  - `ValueError` from GPT-5 Mini: caught, falls back to Sonnet.
  - `TypeError` from GPT-5 Mini: NOT caught, propagates up as `TypeError`.
  - `KeyError` from GPT-5 Mini: NOT caught, propagates up as `KeyError`.
- **Priority:** MEDIUM

### Test 13: Blog deployer filters pins with failed URL verification
- **Covers fix:** #18 (M2 — `blog_deployer.py` excludes failed-verification pins from schedule)
- **File:** `tests/test_blog_deployer_pin_filter.py`
- **Scenario:** Call the deployment flow with a set of pins, some of whose blog URLs fail verification. Verify the pin schedule only includes pins with verified URLs.
- **Mocks:** Mock `GitHubAPI.verify_urls()` to return some slugs as failed. Mock `_create_pin_schedule()` to capture the pin list passed to it.
- **Asserts:**
  - Pins for blogs with failed URLs are excluded from the pin schedule.
  - Pins for blogs with verified URLs are included.
  - A warning is logged indicating how many pins were filtered.
- **Priority:** MEDIUM

### Test 14: regen_content drive null guard
- **Covers fix:** #15 (H8 — `regen_content.py:578` null check on `drive`)
- **File:** `tests/test_regen_drive_guard.py`
- **Scenario:** Call `_regen_item()` with `drive=None` and an image URL that is a Drive URL. Verify it does NOT crash with `AttributeError` on `None.download_image()`, but instead skips the Drive download path gracefully.
- **Mocks:** Set `drive=None`. Provide `pin_data` with a Drive image URL. Mock other dependencies (claude, image_gen, assembler, gcs).
- **Asserts:**
  - No `AttributeError` raised.
  - The function either succeeds via a different path (GCS fallback) or logs that Drive is unavailable.
  - If the only image source is Drive and drive is None, the item is handled gracefully (not a crash).
- **Priority:** MEDIUM

### Test 15: Atomic write helper (shared pattern test)
- **Covers fixes:** #3, #4, #5, #6, #7 (all temp+rename atomic writes)
- **File:** `tests/test_atomic_writes.py`
- **Scenario:** Rather than testing each file's save logic individually, write a generic test that validates the temp+rename contract: (a) write to `.tmp`, (b) rename to target, (c) on failure, clean up `.tmp` and preserve original. Test with a helper function that accepts a file path and data, then verifies the pattern.
- **Mocks:** For the crash scenario: patch `Path.replace` to raise `OSError` after the temp file is written.
- **Asserts:**
  - After successful write: target file has new content, `.tmp` does not exist.
  - After failed rename: target file has old content (or doesn't exist if first write), `.tmp` is cleaned up.
  - After successful write: file is valid JSON (parseable).
- **Priority:** HIGH (covers 5 fixes at once)

---

## Not Worth Testing

| Fix | Reason |
|-----|--------|
| Fix 12 — `post_pins.py:280-281` add `logger.warning` to bare except | Pure log-message change. The except block previously had `pass`; it now logs a warning. Testing that `logger.warning` is called in an error path is possible but low-value: the risk of regression is someone reverting to `pass`, which is a code-review issue, not a test issue. If desired, a test could mock `logger.warning` and verify it is called, but the priority is LOW. |
| Fix 13 — `post_pins.py:664` add `logger.error` to bare except | Same rationale as fix 12. Pure log addition. |
| Fix 14 — `regen_content.py` add `logger.warning` to four bare except blocks | Same rationale as fix 12. Four locations, all the same pattern: `except Exception: pass` changed to `except Exception as e: logger.warning(...)`. Low regression risk. |
| Fix 19 — `.env.example` changes | Config template file. No runtime code to test. Changes are adding/removing documentation lines. |
| Fix 20 — Workflow YAML changes (`generate-content.yml`, `regen-content.yml`) | GitHub Actions workflow configuration. Requires integration testing against actual GitHub Actions infrastructure, not unit tests. |

---

## Summary

| Category | Count | Fixes |
|----------|-------|-------|
| Already covered | 1 | Fix 8 (partially) |
| Tests recommended | 15 tests covering 15 fixes | Fixes 1-7, 9-11, 15-18 |
| Not worth unit-testing | 5 | Fixes 12, 13, 14, 19, 20 |

### Priority Breakdown

| Priority | Tests | Fixes Covered |
|----------|-------|---------------|
| HIGH | Tests 1, 3, 4, 8, 9, 10, 11, 15 | Fixes 1, 3, 4-7, 9, 10, 11, 16 |
| MEDIUM | Tests 2, 5, 6, 7, 12, 13, 14 | Fixes 2, 5, 6, 7, 17, 18, 15 |

### Implementation Recommendation

Start with these three test files, in order:

1. **`tests/test_atomic_writes.py`** — A single parameterized test that validates the temp+rename pattern. Covers fixes 3-7 in one file. Use `tmp_path` fixture, write known JSON, simulate the atomic write, verify round-trip. Then simulate crash (mock `Path.replace` to raise), verify original preserved.

2. **`tests/test_plan_structure_validation.py`** — Direct tests of `_validate_plan_structure()`. Pure function, no mocks needed, high regression value. Covers fix 9. Can import and test directly since it is a module-level function.

3. **`tests/test_blog_validation.py`** — Tests for `_validate_generated_post()` raising `BlogGeneratorError` on missing critical frontmatter. Covers fix 10. Requires instantiating `BlogGenerator` with mocked dependencies, or extracting the validation call.

4. **`tests/test_sheets_header_validation.py`** + **`tests/test_sheets_write_pattern.py`** — Mock-heavy tests for the Sheets API changes. Cover fixes 1 and 11.

5. **`tests/test_openai_error_wrapping.py`** — Verify HTTP errors are wrapped. Covers fix 16.

These 5 test files (with approximately 15-20 test functions total) would cover the 15 highest-value fixes and catch regressions on every data-integrity and validation change.
