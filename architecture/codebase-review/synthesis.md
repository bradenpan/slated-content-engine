# Codebase Review Synthesis

## Executive Summary
- 24 unique findings across 8 dimensions (8 high, 10 medium, 6 low) after deduplication
- 42 raw findings from 4 reviewers reduced to 24 after merging duplicates
- 17 findings need fixes, 7 are accepted risks
- Referential integrity and configuration completeness are clean -- no broken imports, missing files, or missing entry points
- Core weaknesses: non-atomic file writes for critical data, error-swallowing patterns that hide failures, and missing validation on LLM/Sheet responses

## Findings

### HIGH

#### H1. Sheets `_clear_and_write` has a data loss window
- **Dimensions:** Failure modes, Idempotency
- **File(s):** `src/apis/sheets_api.py:804-867`
- **Found by:** reviewer-failures-errors, reviewer-validation-idempotency
- **Description:** `_clear_and_write()` clears the entire tab at line 826, then writes new data with one retry (lines 835-860). If the clear succeeds but both write attempts fail, the tab is left empty. The method logs this and raises `SheetsAPIError`, but the previous data is already gone. Affects Content Queue, Weekly Review, and Dashboard tabs.
- **Verified:** YES -- confirmed clear at line 826-830 is unconditional, and write failure at line 852-860 raises after data is already cleared.
- **Action:** FIX
- **Fix:** Restructure to write-then-clear: write new data to a staging range first, verify success, then clear the old range and copy. Alternatively, use a single `batchUpdate` request that combines clear + write atomically. The simplest pragmatic fix: skip the explicit clear and use `update` (which overwrites) + clear only the rows beyond the new data length.

#### H2. `publish_content_queue.py` sends "content ready" Slack after Sheets write failure
- **Dimensions:** Failure modes, Error propagation
- **File(s):** `src/publish_content_queue.py:227-245`
- **Found by:** reviewer-failures-errors
- **Description:** If the Sheets write fails at line 227-228, the error is logged but execution continues to send a Slack notification (lines 231-245) saying content is ready for review. The reviewer opens the Sheet and sees stale or empty data.
- **Verified:** YES -- lines 227-228 catch `Exception` with only `logger.error`, no raise. Lines 231-245 proceed unconditionally.
- **Action:** FIX
- **Fix:** Set a `sheets_write_failed` flag in the except block. Either skip the Slack notification or modify it to say "Content Queue write failed -- check workflow logs" when the flag is set.

#### H3. LLM JSON responses parsed but never schema-validated
- **Dimensions:** Input validation
- **File(s):** `src/apis/claude_api.py:779-847`, `src/generate_weekly_plan.py:123-130, 318`
- **Found by:** reviewer-validation-idempotency
- **Description:** `_parse_json_response()` extracts JSON from Claude's output robustly, but the result is used without checking expected keys. For weekly plans, `plan.get("blog_posts", [])` at line 318 silently defaults to empty list if Claude returns different key names. An entire week of content would silently not be generated.
- **Verified:** YES -- line 130 assigns raw Claude response to `plan`, and line 318 uses `.get("blog_posts", [])` with silent empty default. No structural validation between parsing and use.
- **Action:** FIX
- **Fix:** Add a `_validate_plan_structure(plan)` function that checks required top-level keys (`blog_posts`, `pins`) exist, are lists, and are non-empty. Raise a clear error on structural mismatch so the failure is visible rather than producing a silent empty week.

#### H4. Non-atomic writes to critical pipeline data files
- **Dimensions:** Data atomicity
- **File(s):** `src/regen_content.py:381-384`, `src/publish_content_queue.py:122-128`, `src/generate_weekly_plan.py:309-312`, `src/regen_weekly_plan.py:208-211`, `src/redate_schedule.py:40`
- **Found by:** reviewer-atomicity-concurrency, reviewer-failures-errors, reviewer-validation-idempotency
- **Description:** Several files write critical pipeline JSON data using `Path.write_text()` or `json.dump()` directly, without the temp-file-then-rename pattern used elsewhere in the codebase. A crash during write could corrupt: `pin-generation-results.json` (written by regen_content.py and publish_content_queue.py), `weekly-plan-{date}.json` (written by generate_weekly_plan.py and regen_weekly_plan.py), and `pin-schedule.json` (written by redate_schedule.py). These files are the single source of truth for pin metadata, weekly plans, and posting schedules.
- **Verified:** YES -- confirmed all five locations use direct `write_text()` or `json.dump()`. The codebase already has the correct pattern in `content_log.py:62-68`, `generate_pin_content.py:793-807`, `generate_blog_posts.py:224-239`, and `plan_utils.py:274-277`.
- **Action:** FIX
- **Fix:** Apply the existing temp+rename pattern to all five locations. For `redate_schedule.py`, use the existing `save_pin_schedule()` from `plan_utils.py` instead of writing directly.

#### H5. Token store writes are not atomic
- **Dimensions:** Data atomicity, Error propagation
- **File(s):** `src/token_manager.py:390-396`
- **Found by:** reviewer-atomicity-concurrency, reviewer-failures-errors
- **Description:** `_save_tokens()` writes directly via `json.dump()` into an open file handle (line 391). A crash mid-write leaves corrupt `data/token-store.json`. The next run reads the corrupt file, gets `JSONDecodeError`, falls back to env vars, and forces an unnecessary token refresh. Additionally, save failures are caught with `except OSError` (line 394) and only logged -- the in-memory token is updated but disk persistence is silently lost.
- **Verified:** YES -- line 391 uses direct `open/json.dump`, no temp+rename. Line 394-396 catches `OSError` without raising.
- **Action:** FIX
- **Fix:** Apply temp+rename pattern to `_save_tokens()`. The existing error swallowing (don't raise on save failure) is acceptable since the in-memory token is valid for the current run, but the write itself must be atomic.

#### H6. Blog post validation warnings never block deployment
- **Dimensions:** Input validation
- **File(s):** `src/blog_generator.py:407-473`
- **Found by:** reviewer-validation-idempotency
- **Description:** `_validate_generated_post()` checks frontmatter fields, word count, CTAs, and schema fields, but all checks except empty content are logged as `logger.warning()` and never raise. A blog post with no title, no slug, or no description will pass validation and be deployed to production.
- **Verified:** YES -- confirmed only the empty-content check at line 419-422 raises `BlogGeneratorError`. All other checks (lines 425-473) only log warnings.
- **Action:** FIX
- **Fix:** Promote critical frontmatter fields (`title`, `slug`, `description`) to hard errors -- raise `BlogGeneratorError` if any are missing. Keep word count and CTA checks as warnings (they're quality issues, not deployment blockers).

#### H7. `post_pins.py` silently swallows Sheet failure status updates
- **Dimensions:** Error propagation
- **File(s):** `src/post_pins.py:280-281`
- **Found by:** reviewer-failures-errors
- **Description:** When pin posting fails, the code attempts to update the Sheet with status="failed" (lines 274-279). If that update itself fails, it's caught with bare `except Exception: pass` (lines 280-281). The pin failure goes unreported in the Sheet -- it appears as still "approved." Compare with the success path at line 257-258 which at least logs a warning.
- **Verified:** YES -- line 280-281 is `except Exception: pass`. Success path at 257-258 has `logger.warning`.
- **Action:** FIX
- **Fix:** Add `logger.warning("Failed to update Sheet with failure status for pin %s: %s", pin_id, e)` to the except block at line 280-281. Same treatment for the permanent failure Slack alert at line 664 (currently `except Exception: pass`).

#### H8. `regen_content.py` calls `drive.download_image` without null check
- **Dimensions:** Failure modes
- **File(s):** `src/regen_content.py:578, 461, 283-289`
- **Found by:** reviewer-failures-errors
- **Description:** In `_regen_item()`, the Drive fallback at line 578 calls `drive.download_image()` without checking if `drive` is `None`. The lazy init at lines 283-289 sets `drive = None` if `DriveAPI()` fails. The function parameter at line 461 is typed as `DriveAPI` (not `Optional[DriveAPI]`), giving false safety.
- **Verified:** YES -- line 461 types `drive` as `DriveAPI`, line 288 can set it to `None`, and line 578 calls `drive.download_image()` unconditionally. The outer try/except at line 305 would catch the `AttributeError` but produce a confusing error message.
- **Action:** FIX
- **Fix:** Add `if drive is not None:` guard before line 578. Update the type hint on `_regen_item()` parameter to `Optional[DriveAPI]`.

### MEDIUM

#### M1. Sheets header validation only warns, never raises
- **Dimensions:** Input validation, Error propagation
- **File(s):** `src/apis/sheets_api.py:142-176`
- **Found by:** reviewer-failures-errors, reviewer-validation-idempotency
- **Description:** `_validate_headers()` checks that tab headers match expected columns but only logs a warning on mismatch (line 169-174). A TODO at line 148-149 acknowledges this should raise. If headers are reordered manually, all reads/writes use hardcoded column indices and silently operate on wrong columns.
- **Verified:** YES -- confirmed line 149 has the TODO, line 169-174 only warn.
- **Action:** FIX
- **Fix:** Upgrade to raise `SheetsAPIError` on header mismatch. The TODO has been in the code long enough -- this prevents silent data corruption from manual Sheet edits.

#### M2. `blog_deployer.py` continues pin scheduling after URL verification failure
- **Dimensions:** Failure modes
- **File(s):** `src/blog_deployer.py:240-270`
- **Found by:** reviewer-failures-errors
- **Description:** URL verification failures (step 3) are logged and Slack-alerted, but pin scheduling (step 5, line 267-270) proceeds regardless. Pins are scheduled with links to blog posts that may not be live, resulting in 404s when posted.
- **Verified:** YES -- lines 237-251 handle failed URLs, but line 267-270 creates pin schedule unconditionally with no check on verification results.
- **Action:** FIX
- **Fix:** Filter `approved_pins` to exclude pins whose blog URLs failed verification before passing to `_create_pin_schedule()`.

#### M3. OpenAI Chat API raises wrong exception type on HTTP errors
- **Dimensions:** Error propagation
- **File(s):** `src/apis/openai_chat_api.py:124`
- **Found by:** reviewer-failures-errors
- **Description:** `call_gpt5_mini()` calls `response.raise_for_status()` at line 124, which raises `requests.HTTPError`. Network-level failures (lines 91-98) are correctly wrapped to `OpenAIChatAPIError`, but HTTP 400/500 responses are not. Currently safe because the caller at `claude_api.py:254` uses broad `except Exception`, but any caller using targeted `except OpenAIChatAPIError` would miss HTTP errors.
- **Verified:** YES -- line 124 is bare `response.raise_for_status()` without wrapping.
- **Action:** FIX
- **Fix:** Wrap line 124 in `try/except requests.HTTPError as e: raise OpenAIChatAPIError(...) from e`.

#### M4. `claude_api.py` batch copy generation uses broad `except Exception` for GPT-5 Mini fallback
- **Dimensions:** Error propagation
- **File(s):** `src/apis/claude_api.py:254`
- **Found by:** reviewer-failures-errors
- **Description:** `generate_pin_copy_batch()` catches `except Exception as e` when GPT-5 Mini fails, then falls back to Claude Sonnet. This masks programming errors (TypeError, KeyError) as API failures, preventing them from being caught during development. Claude Sonnet costs more.
- **Verified:** YES -- line 254 catches bare `Exception`.
- **Action:** FIX
- **Fix:** Narrow to `except (OpenAIChatAPIError, ValueError, requests.HTTPError) as e:`. Programming errors will then surface properly instead of being silently retried on the more expensive model.

#### M5. `regen_content.py` multiple Sheet update failures caught with bare `except Exception: pass`
- **Dimensions:** Error propagation
- **File(s):** `src/regen_content.py:167-168, 198-199, 267-269, 314-315`
- **Found by:** reviewer-failures-errors
- **Description:** Throughout `regen()`, Sheet update failures in error-handling paths are caught with `except Exception: pass`. If regen fails AND the Sheet update to record the failure also fails, no record of either failure exists except in ephemeral workflow logs.
- **Verified:** YES -- confirmed all four locations are bare `except Exception: pass`.
- **Action:** FIX
- **Fix:** Add `logger.warning("Failed to update Sheet for %s: %s", item_id, e)` to each bare except block. This ensures at least log-level visibility.

#### M6. `github_api.py` deployment verification swallows all connection errors
- **Dimensions:** Error propagation
- **File(s):** `src/apis/github_api.py:220-221`
- **Found by:** reviewer-failures-errors
- **Description:** During URL verification polling, `requests.RequestException` is caught with `pass`. This is intentional for "not ready yet" scenarios, but also swallows DNS failures, SSL errors, and auth errors that indicate configuration problems. The verification loop polls for the full timeout before returning False.
- **Verified:** YES -- line 220-221 catches `requests.RequestException` with `pass`.
- **Action:** ACCEPT
- **Fix:** N/A. The polling pattern is correct for deployment verification. The worst case is wasted time (120s), not data loss. Adding exception-type filtering (e.g., failing fast on DNS errors) would add complexity for minimal practical benefit since this runs rarely.

#### M7. Missing env vars from `.env.example` and vestigial entries
- **Dimensions:** Configuration completeness
- **File(s):** `.env.example`
- **Found by:** reviewer-refs-config
- **Description:** Three env vars used in code are missing from `.env.example` (`PINTEREST_ENVIRONMENT`, `GCS_BUCKET_NAME`, `IMAGE_GEN_PROVIDER`). Two env vars in `.env.example` are unused (`UNSPLASH_ACCESS_KEY`, `PEXELS_API_KEY`). All have sensible defaults, so the impact is developer confusion, not runtime failure.
- **Verified:** YES -- confirmed the three vars are read with defaults in the code, and the two unused vars have no `os.environ.get` calls.
- **Action:** FIX
- **Fix:** Add the three missing vars (with their default values as comments) to `.env.example`. Remove the two vestigial entries.

#### M8. `REPLICATE_API_TOKEN` not passed through workflow env blocks
- **Dimensions:** Configuration completeness
- **File(s):** `.github/workflows/generate-content.yml`, `.github/workflows/regen-content.yml`
- **Found by:** reviewer-refs-config
- **Description:** `image_gen.py` reads `REPLICATE_API_TOKEN` when `IMAGE_GEN_PROVIDER=replicate`. The token is in `.env.example` and `replicate` is in `requirements.txt`, but no workflow passes this secret. If someone switches providers, the workflow will fail.
- **Verified:** YES
- **Action:** FIX
- **Fix:** Either wire `REPLICATE_API_TOKEN` through the two workflows that do image generation, or remove Replicate support entirely (delete from `.env.example` and `requirements.txt`) if it's deprecated.

#### M9. `generate_copy_batch` does not validate batch result count
- **Dimensions:** Input validation
- **File(s):** `src/generate_pin_content.py` (generate_copy_batch), `src/apis/claude_api.py:258-264`
- **Found by:** reviewer-validation-idempotency
- **Description:** Batch pin copy generation sends N pin specs and expects N results. Results are processed by index. If Claude returns fewer items, some pins silently get no copy. The code at `claude_api.py:258-264` handles dict vs list format but doesn't check count.
- **Verified:** YES -- line 258-264 processes results without checking length against input batch size.
- **Action:** ACCEPT
- **Fix:** N/A. The downstream code at `generate_pin_content.py:118-121` already handles pins with no copy by skipping them with a warning. Adding count validation would improve error messages but wouldn't change behavior. The batch fallback to individual generation also mitigates total failure.

#### M10. Content-log.jsonl concurrency risk between posting and analytics workflows
- **Dimensions:** Concurrency, Data atomicity
- **File(s):** `src/utils/content_log.py:51-94`, `.github/workflows/daily-post-*.yml`, `.github/workflows/weekly-review.yml`
- **Found by:** reviewer-atomicity-concurrency
- **Description:** The `pinterest-posting` and `pinterest-pipeline` concurrency groups are separate. A posting workflow (appending to content-log.jsonl) and analytics pull (rewriting content-log.jsonl) could theoretically run concurrently. On GitHub Actions, each workflow gets its own checkout, so the risk is at the git level: if both commit changes to the same file, the rebase in `commit-data` would conflict.
- **Verified:** YES -- confirmed different concurrency groups. However, the normal schedule (review at 6am, first post at 10am) makes overlap extremely unlikely. Only manual `workflow_dispatch` could trigger it.
- **Action:** ACCEPT
- **Fix:** N/A. The normal cron schedule prevents overlap. The commit-data action's rebase-and-retry handles the git-level race. The risk is limited to manual dispatch scenarios, and the failure mode is a visible rebase conflict (not silent data loss).

### LOW

#### L1. Non-atomic analytics snapshot and analysis/review markdown writes
- **Dimensions:** Data atomicity
- **File(s):** `src/pull_analytics.py:454-456`, `src/weekly_analysis.py:283-284`, `src/monthly_review.py:390-391`
- **Found by:** reviewer-atomicity-concurrency
- **Description:** Analytics snapshots and analysis markdown files use direct `write_text()` or `json.dump()`. These are historical records / human-readable reports that don't drive pipeline logic.
- **Verified:** YES
- **Action:** ACCEPT
- **Fix:** N/A. These files are regeneratable and don't affect pipeline operation. The risk of a mid-write crash corrupting them is extremely low and consequences are negligible.

#### L2. Non-atomic content-log.jsonl append (no fsync)
- **Dimensions:** Data atomicity
- **File(s):** `src/utils/content_log.py:80-94`
- **Found by:** reviewer-atomicity-concurrency
- **Description:** `append_content_log_entry()` uses append mode without explicit `f.flush()` or `os.fsync()`. A process kill could lose the last appended line. The `load_content_log()` function handles malformed lines gracefully.
- **Verified:** YES
- **Action:** ACCEPT
- **Fix:** N/A. Single-line appends under 4096 bytes are effectively atomic on Linux (GitHub Actions). The reader handles partial lines. Adding fsync would hurt performance for negligible safety gain.

#### L3. GCS init swallows all initialization errors (intentional graceful degradation)
- **Dimensions:** Error propagation
- **File(s):** `src/apis/gcs_api.py:60-116`
- **Found by:** reviewer-failures-errors
- **Description:** `GcsAPI.__init__()` catches all init failures and sets `self.client = None`. This is intentional for GCS-to-Drive fallback. Callers check `gcs.is_available` before use.
- **Verified:** YES -- confirmed `is_available` property at line 119-121, and callers check it (e.g., `publish_content_queue.py:64`).
- **Action:** ACCEPT
- **Fix:** N/A. The graceful degradation pattern is correct. The `_init_error` field stores the reason for debugging.

#### L4. `image_gen.py` `_validate_image` returns True when Pillow unavailable
- **Dimensions:** Failure modes
- **File(s):** `src/apis/image_gen.py:383-386`
- **Found by:** reviewer-failures-errors
- **Description:** Image validation skips decode checks when Pillow isn't installed. In CI, Pillow is always installed via `requirements.txt`.
- **Verified:** YES
- **Action:** ACCEPT
- **Fix:** N/A. Pillow is a hard dependency in `requirements.txt`. This only matters in incomplete local dev environments.

#### L5. Vestigial env vars in `.env.example` (UNSPLASH, PEXELS)
- **Dimensions:** Configuration completeness
- **File(s):** `.env.example`
- **Found by:** reviewer-refs-config
- **Description:** `UNSPLASH_ACCESS_KEY` and `PEXELS_API_KEY` are in `.env.example` but no code reads them.
- **Verified:** YES
- **Action:** FIX (merged into M7 fix)

#### L6. Non-atomic blog post MDX and content-memory-summary writes
- **Dimensions:** Data atomicity
- **File(s):** `src/blog_generator.py:647`, `src/utils/content_memory.py:407`
- **Found by:** reviewer-atomicity-concurrency
- **Description:** MDX files and the content memory summary use direct `write_text()`. Both are regeneratable and caught by downstream readers if corrupt.
- **Verified:** YES
- **Action:** ACCEPT
- **Fix:** N/A. These files are regenerated each run and don't have the same criticality as pin-generation-results.json or the weekly plan.

## Fix Plan

### Priority 1: Data integrity -- prevent data loss and silent failures

1. **`src/apis/sheets_api.py`** (`_clear_and_write`): Replace clear-then-write with a pattern that doesn't leave tabs empty on write failure. Options: (a) write to all rows first via `update` (which overwrites), then clear only rows beyond the new data length; (b) use `batchUpdate` with both operations. [H1]

2. **`src/publish_content_queue.py`**: Add a `sheets_write_ok` flag (default `True`). Set to `False` in the Sheets write `except` block. Conditionally modify the Slack notification based on the flag. [H2]

3. **`src/token_manager.py`** (`_save_tokens`): Replace `open/json.dump` with temp file + `replace()` pattern. Keep the `except OSError` non-raising behavior. [H5]

4. **`src/regen_content.py:381-384`**: Replace `pin_results_path.write_text()` with temp+rename pattern. [H4]

5. **`src/publish_content_queue.py:122-128`**: Replace `pin_results_path.write_text()` with temp+rename pattern. [H4]

6. **`src/generate_weekly_plan.py:309-312`**: Replace `plan_path.write_text()` with temp+rename pattern. [H4]

7. **`src/regen_weekly_plan.py:208-211`**: Replace `plan_path.write_text()` with temp+rename pattern. [H4]

8. **`src/redate_schedule.py:40`**: Replace direct `path.write_text()` with a call to `save_pin_schedule()` from `plan_utils.py` (which already uses atomic writes). [H4]

### Priority 2: Validation -- catch bad data before it propagates

9. **`src/generate_weekly_plan.py`**: Add `_validate_plan_structure(plan)` after line 130. Check that `plan` is a dict with non-empty `blog_posts` (list) and `pins` (list) keys. Raise `ValueError` if structure is wrong. [H3]

10. **`src/blog_generator.py`** (`_validate_generated_post`): Promote missing `title`, `slug`, and `description` from warnings to `BlogGeneratorError` raises. Keep word count and CTA checks as warnings. [H6]

11. **`src/apis/sheets_api.py`** (`_validate_headers`): Change warning to `raise SheetsAPIError(...)` on header mismatch. Remove the TODO comment. [M1]

### Priority 3: Error propagation -- stop swallowing important errors

12. **`src/post_pins.py:280-281`**: Replace `except Exception: pass` with `except Exception as e: logger.warning("Failed to update Sheet with failure status for %s: %s", pin_id, e)`. [H7]

13. **`src/post_pins.py:664`**: Replace `except Exception: pass` with `except Exception as e: logger.error("Failed to send permanent failure alert for %s: %s", pin_id, e)`. [H7]

14. **`src/regen_content.py:167-168, 198-199, 267-269, 314-315`**: Add `logger.warning(...)` to all four bare `except Exception: pass` blocks. [M5]

15. **`src/regen_content.py:578`**: Add `if drive is not None:` guard. Update `_regen_item()` type hint to `Optional[DriveAPI]`. [H8]

16. **`src/apis/openai_chat_api.py:124`**: Wrap `response.raise_for_status()` in `try/except requests.HTTPError as e: raise OpenAIChatAPIError(...) from e`. [M3]

17. **`src/apis/claude_api.py:254`**: Narrow `except Exception` to `except (OpenAIChatAPIError, ValueError, requests.HTTPError)`. [M4]

### Priority 4: Configuration and deployment safety

18. **`src/blog_deployer.py:267-270`**: Filter `approved_pins` to exclude those whose blog URLs failed verification before creating pin schedule. [M2]

19. **`.env.example`**: Add `PINTEREST_ENVIRONMENT=sandbox`, `IMAGE_GEN_PROVIDER=openai`, `GCS_BUCKET_NAME=slated-pipeline-pins`. Remove `UNSPLASH_ACCESS_KEY` and `PEXELS_API_KEY`. [M7, L5]

20. **`.github/workflows/generate-content.yml` and `regen-content.yml`**: Add `REPLICATE_API_TOKEN: ${{ secrets.REPLICATE_API_TOKEN }}` to env blocks, OR remove `replicate` from `requirements.txt` and `.env.example` if deprecated. [M8]

## Accepted Risks

| Finding | Why accepted |
|---------|-------------|
| M6. github_api.py deployment verification swallows connection errors | Polling pattern is correct for deployment checks. Worst case is 120s wasted time, not data loss. Adding error-type filtering adds complexity for minimal gain. |
| M9. Batch copy generation doesn't validate result count | Downstream code already handles pins with no copy by skipping with a warning. Count validation would improve error messages but not change behavior. |
| M10. Content-log.jsonl concurrency between posting and analytics | Normal cron schedule prevents overlap. commit-data rebase handles git-level race. Only manual dispatch could trigger, and failure is visible (rebase conflict). |
| L1. Non-atomic analytics/analysis/review writes | Regeneratable historical records that don't drive pipeline logic. Negligible risk. |
| L2. Non-atomic content-log.jsonl append (no fsync) | Small writes on Linux are effectively atomic. Reader handles partial lines. Performance cost of fsync not justified. |
| L4. Image validation returns True without Pillow | Pillow is a hard dependency in requirements.txt. Only relevant in incomplete local dev. |
| L6. Non-atomic blog MDX and content-memory writes | Regeneratable files caught by downstream readers if corrupt. Low criticality. |
