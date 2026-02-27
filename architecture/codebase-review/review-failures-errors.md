# Review: Failure Modes + Error Propagation

**Reviewer:** reviewer-failures-errors
**Date:** 2026-02-27
**Scope:** All `src/*.py`, `src/apis/*.py`, `.github/workflows/*.yml`, `.github/actions/*/action.yml`

---

## Summary

Reviewed every `try/except` block and external call across the codebase, tracing what happens when each API call, file I/O, or external service interaction fails. Found **19 findings** across two dimensions:

| Severity | Count |
|----------|-------|
| HIGH     | 7     |
| MEDIUM   | 8     |
| LOW      | 4     |

**Dimension breakdown:** Failure modes (10), Error propagation (9)

**Patterns observed:**
- Several places where errors are caught and silently swallowed with `except Exception: pass`
- A data loss window in the Sheets "clear then write" pattern
- Multiple cases where `None` return values or missing null checks lead to downstream `AttributeError`
- Error type mismatches between what callers catch and what callees raise
- Intentional best-effort patterns (Slack notifications, row height formatting) that are appropriate

---

## Findings

### [HIGH] OpenAI Chat API raises wrong exception type on HTTP errors

- **Dimension:** Error propagation
- **File(s):** `src/apis/openai_chat_api.py:124`
- **Description:** `call_gpt5_mini()` calls `response.raise_for_status()` at line 124 after exhausting retries. This raises `requests.HTTPError`, not `OpenAIChatAPIError`. The function's docstring declares it raises both, but callers in `claude_api.py` (line 254) catch `Exception` broadly on the GPT-5 Mini path, so it happens to work. However, any caller that specifically catches `OpenAIChatAPIError` (as one would expect from the module name) will miss HTTP 400/500 errors.
- **Evidence:** Line 124: `response.raise_for_status()` raises `requests.HTTPError`. Lines 86-100 correctly wrap `requests.RequestException` into `OpenAIChatAPIError`, but only for network-level failures, not for HTTP error responses.
- **Impact:** If a caller adds targeted `OpenAIChatAPIError` handling (instead of the broad `except Exception`), HTTP errors from OpenAI will bypass the handler and propagate as unhandled `requests.HTTPError`.

### [HIGH] Sheets `_clear_and_write` has a data loss window

- **Dimension:** Failure modes
- **File(s):** `src/apis/sheets_api.py:804-867`
- **Description:** `_clear_and_write()` first clears the entire tab (line 826-830), then writes new data with one retry (lines 835-860). If the clear succeeds but both write attempts fail, the tab is left empty. The method correctly logs this ("Tab may be empty -- manual recovery needed") and raises `SheetsAPIError`, but by that point the previous data is already gone.
- **Evidence:** The clear operation at line 826 is unconditional. If the subsequent write at line 837 fails twice, the exception at line 858-860 is raised but the cleared data cannot be recovered.
- **Impact:** A transient Google Sheets API outage during write (after successful clear) would leave the Content Queue, Post Log, or Dashboard tab completely empty. The user would need to re-run the workflow to regenerate the data.

### [HIGH] `regen_content.py` calls `drive.download_image` without null check

- **Dimension:** Failure modes
- **File(s):** `src/regen_content.py:578`
- **Description:** In `_regen_item()`, when attempting to download a hero image from Drive as a fallback (line 578), the code calls `drive.download_image(drive_file_id, hero_path)` without checking if `drive` is `None`. The lazy init at lines 283-289 sets `drive = None` if `DriveAPI()` init fails. The `drive` parameter type hint on `_regen_item()` at line 461 is `DriveAPI` (not `Optional[DriveAPI]`), giving a false sense of safety.
- **Evidence:** Line 283-288: if `DriveAPI()` raises, `drive = None`. Line 578: `drive.download_image(...)` called unconditionally. Line 461: parameter typed as `DriveAPI`, not `Optional[DriveAPI]`.
- **Impact:** If GCS download fails and Drive initialization also failed, line 578 will raise `AttributeError: 'NoneType' object has no attribute 'download_image'`. The outer try/except at line 305 catches this, but the error message will be confusing (AttributeError instead of a clear "Drive not available" message).

### [HIGH] Token save failure silently drops on-disk persistence

- **Dimension:** Error propagation
- **File(s):** `src/token_manager.py:390-396`
- **Description:** `_save_tokens()` catches `OSError` on file write failure (line 394) and logs it, but does NOT raise. The in-memory `self._token_data` is updated (line 385), so the current workflow run continues fine. However, the next workflow run will load stale tokens from disk (or fall back to env vars with `expires_at: 0`), triggering an unnecessary refresh. If the save failure persists across runs, each run refreshes the token, eventually exhausting the refresh token chain faster than necessary.
- **Evidence:** Line 394-396: `except OSError as e: logger.error(...)` with comment "Don't raise -- the in-memory token data is still valid for this run."
- **Impact:** Persistent file system issues (e.g., read-only filesystem, full disk) would cause every workflow run to re-refresh tokens. Since Pinterest tokens change on every refresh, the previous refresh token is invalidated. If two runs overlap with save failures, the second run's refresh token (loaded from disk) may already be revoked.

### [HIGH] `post_pins.py` silently swallows Sheet failure status updates

- **Dimension:** Error propagation
- **File(s):** `src/post_pins.py:280-281`
- **Description:** When a pin posting fails, the code attempts to update the Google Sheet with status="failed" (lines 274-279). If that Sheet update itself fails, the exception is caught with a bare `except Exception: pass` (lines 280-281). This means pin failures can go completely unreported in the Sheet -- the pin shows no status change despite having failed.
- **Evidence:** Lines 280-281: `except Exception: pass`. Compare with line 257-258 where the success path at least logs the warning: `logger.warning("Failed to update Google Sheet for pin %s: %s", pin_id, e)`.
- **Impact:** A pin that failed to post may appear in the Sheet as still "approved" (never updated), leading the reviewer to believe it hasn't been attempted yet. The Slack notification (lines 287-296) is a partial safety net, but it too is wrapped in a try/except that swallows errors.

### [HIGH] `publish_content_queue.py` continues after Sheets write failure

- **Dimension:** Failure modes
- **File(s):** `src/publish_content_queue.py:227-228`
- **Description:** The core purpose of `publish()` is to write the Content Queue to Google Sheets. If this write fails (line 227-228), the error is logged but execution continues to send a Slack notification saying "content is ready for review." The reviewer then opens the Sheet and sees either stale or empty data.
- **Evidence:** Line 227-228: `except Exception as e: logger.error("Failed to write Content Queue to Google Sheets: %s", e)` -- no raise, no flag to prevent the Slack notification. Lines 231-245: Slack notification proceeds unconditionally.
- **Impact:** The Slack notification tells the user to review content that isn't in the Sheet. They waste time investigating, or worse, approve stale content from a previous week.

### [HIGH] `_record_failure` in `post_pins.py` uses non-atomic JSON write pattern during the critical failure path

- **Dimension:** Failure modes
- **File(s):** `src/post_pins.py:608-665`
- **Description:** `_record_failure()` writes the posting-failures.json file using a temp file + replace pattern (lines 639-643), which is good. However, the initial read at lines 623-628 has a race condition: if two concurrent posting windows (which shouldn't happen due to GitHub Actions concurrency groups, but could happen in manual runs) both read the file, both increment the count, and both write, one increment is lost. More critically, the Slack alert for permanent failure at lines 657-664 is wrapped in `except Exception: pass` (line 664), so if Slack is down, permanent pin failures go completely unreported.
- **Evidence:** Line 664: `except Exception: pass` around the permanent failure Slack alert. Lines 623-628: non-locked read of the failures JSON.
- **Impact:** A pin that has permanently failed (3+ consecutive failures) may not trigger any alert if Slack is unreachable. The only record is in log output, which is ephemeral in GitHub Actions.

### [MEDIUM] GCS `__init__` swallows all initialization errors

- **Dimension:** Error propagation
- **File(s):** `src/apis/gcs_api.py:60-116`
- **Description:** `GcsAPI.__init__()` catches all initialization failures (missing credentials, import errors, auth failures) and sets `self.client = None` with a warning log. This is an intentional design for graceful degradation (GCS -> Drive fallback), but it means callers must always check `gcs.is_available` or `gcs.client` before use. Several callers do check correctly (e.g., `publish_content_queue.py:64`), but the pattern is error-prone for new code.
- **Evidence:** Lines 62-67, 69-75, 108-116: Three separate `except` blocks all set `self._init_error` and `return` instead of raising. `_init_error` is stored but never checked by most callers.
- **Impact:** A misconfigured GCS bucket or expired credentials will silently fall back to Drive (or no upload) without any actionable alert. The error message is only in logs, which may be overlooked.

### [MEDIUM] `image_gen.py` `_validate_image` returns True when Pillow is unavailable

- **Dimension:** Failure modes
- **File(s):** `src/apis/image_gen.py:383-386`
- **Description:** `_validate_image()` catches `ImportError` when Pillow is not installed and returns `True` (lines 383-386), skipping all image format and dimension validation. This means corrupt or blank images (above the minimum byte size) will pass validation in environments without Pillow.
- **Evidence:** Lines 383-386: `except ImportError: logger.debug("Pillow not available; skipping image decode validation.") return True`.
- **Impact:** In the GitHub Actions environment, Pillow is installed via requirements.txt, so this is unlikely to trigger in production. However, it's a latent risk if the dependency is ever removed or in local development environments.

### [MEDIUM] `image_gen.py` no retry on image URL download

- **Dimension:** Failure modes
- **File(s):** `src/apis/image_gen.py:242-244`
- **Description:** In `_generate_openai()`, when the API returns a URL (instead of base64), the image is downloaded with a single `requests.get()` call (line 242). If this download fails, `raise_for_status()` at line 243 raises immediately with no retry. The outer `generate()` method does have retry logic, but it retries the entire generation (new API call + new image), not just the download.
- **Evidence:** Lines 242-244: `img_response = requests.get(image_url, timeout=30); img_response.raise_for_status(); return img_response.content` -- single attempt, no retry.
- **Impact:** A transient network blip during image download wastes an image generation API call (and its cost) because the retry generates a completely new image instead of re-downloading the already-generated one.

### [MEDIUM] `claude_api.py` batch copy generation uses broad `except Exception` for GPT-5 Mini fallback

- **Dimension:** Error propagation
- **File(s):** `src/apis/claude_api.py:254`
- **Description:** `generate_pin_copy_batch()` catches `except Exception as e` (line 254) when GPT-5 Mini fails, then falls back to Claude Sonnet. This broad catch includes programming errors (TypeError, KeyError, etc.) in addition to API errors. A bug in prompt formatting or response parsing would silently fall back to Claude instead of surfacing the bug.
- **Evidence:** Line 254: `except Exception as e:` catches everything. Compare with `_call_api()` (line 647+) which specifically catches `anthropic.RateLimitError` and `anthropic.APIError`.
- **Impact:** Development bugs in the GPT-5 Mini code path would be masked as "GPT-5 Mini failed, falling back to Claude" instead of being caught and fixed. Claude Sonnet costs more, so this also has a cost impact.

### [MEDIUM] `sheets_api.py` header validation only warns, never raises

- **Dimension:** Error propagation
- **File(s):** `src/apis/sheets_api.py:142-169`
- **Description:** `_validate_headers()` checks that Sheet tab headers match expected columns, but only logs a warning on mismatch (line 169+). The code has a TODO comment (line 149) noting this should be upgraded to raise ValueError. If the Sheet structure changes (columns reordered, renamed, or deleted), all subsequent row writes will silently put data in wrong columns.
- **Evidence:** Line 145-146: "Logs a warning if headers don't match. Does NOT raise an exception." Line 149: "TODO: Once confirmed working in production, this can be upgraded to raise ValueError on mismatch to prevent silent data corruption."
- **Impact:** If someone manually edits the Sheet structure, the pipeline writes data to wrong columns. For example, pin descriptions could end up in the status column, or image URLs in the title column. The warning log is the only indication.

### [MEDIUM] `github_api.py` `verify_deployment` silently swallows connection errors during polling

- **Dimension:** Error propagation
- **File(s):** `src/apis/github_api.py:220-221`
- **Description:** During deployment verification polling, `requests.RequestException` is caught with `pass` (lines 220-221). This is intentional for the polling pattern (the URL isn't ready yet), but it also swallows auth errors, DNS failures, and SSL errors that indicate a configuration problem rather than "not deployed yet."
- **Evidence:** Lines 220-221: `except requests.RequestException: pass  # Not ready yet`
- **Impact:** If the blog URL domain is misconfigured or DNS is broken, the verification loop will poll for the full `max_wait_seconds` (default 120s) before returning False, instead of failing fast with a useful error. The `blog_deployer.py` then logs a warning and continues scheduling pins to URLs that may never resolve.

### [MEDIUM] `blog_deployer.py` continues pin scheduling after URL verification failure

- **Dimension:** Failure modes
- **File(s):** `src/blog_deployer.py:240-270`
- **Description:** In `promote_to_production()`, URL verification failures (step 3) are logged and a Slack alert is sent (lines 245-251), but the pipeline continues to step 5 (create pin schedule, line 267-270). Pins are scheduled with links to blog posts that may not be live. When posted, these pins will link to 404 pages.
- **Evidence:** Lines 240-244: failed URLs logged, Slack alert sent. Line 267-270: pin schedule creation proceeds regardless of verification results. No check on `results["verification_results"]` before scheduling.
- **Impact:** Pins posted with dead blog links create a poor user experience and waste Pinterest engagement. The links persist until the blog eventually deploys or the pins are manually removed.

### [MEDIUM] `regen_content.py` multiple Sheet update failures caught with bare `except Exception: pass`

- **Dimension:** Error propagation
- **File(s):** `src/regen_content.py:167-168, 198-199, 267-269, 314-315`
- **Description:** Throughout `regen()`, Sheet update failures in error-handling paths are caught with `except Exception: pass`. This creates a cascading silence: the regen fails, the Sheet update to record the failure also fails, and no record of either failure exists except in ephemeral logs.
- **Evidence:** Lines 167-168, 198-199, 267-269, 314-315: all `except Exception: pass` blocks.
- **Impact:** A Sheet API outage during regen would result in the Sheet showing stale regen status (e.g., "regen_image") with no indication that regen was attempted and failed. The user would trigger regen again, wasting API credits.

### [MEDIUM] `Slack _send_message` is best-effort by default

- **Dimension:** Error propagation
- **File(s):** `src/apis/slack_notify.py` (approximately line 424+)
- **Description:** `_send_message()` defaults to `raise_on_error=False`, meaning all Slack notification failures are logged but never raised. This is an intentional design decision (Slack is a notification channel, not critical path), but it means the pipeline has no alerting mechanism for its own failures when Slack is down.
- **Evidence:** The parameter default `raise_on_error=False` and the pattern of callers wrapping Slack calls in try/except blocks (e.g., `post_pins.py:295-296`, `regen_content.py:442-443`).
- **Impact:** When Slack is down, all pipeline failure notifications are silently lost. The only remaining record is GitHub Actions log output, which requires manual checking. This is a known trade-off but worth noting since Slack is the primary alerting mechanism.

### [LOW] `drive_api.py` `_get_or_create_folder` swallows search errors before create attempt

- **Dimension:** Failure modes
- **File(s):** `src/apis/drive_api.py:110-111`
- **Description:** `_get_or_create_folder()` catches the folder search error (line 110-111) with `logger.warning` and then attempts to create a new folder. If the search failed due to an auth error, the create will also fail and raise `DriveAPIError`. This is not harmful (the error surfaces eventually), but it means the auth error is logged as a "search" warning, then re-raised as a "create" error, which makes debugging confusing.
- **Evidence:** Lines 110-111: `except Exception as e: logger.warning("Error searching for Drive folder: %s", e)` then falls through to create at lines 114-129.
- **Impact:** Confusing log messages during Drive auth failures. Two errors logged instead of one clear error.

### [LOW] `generate_pin_content.py` pins with no copy are silently skipped

- **Dimension:** Failure modes
- **File(s):** `src/generate_pin_content.py:118-121`
- **Description:** In the main pin generation loop, if `all_pin_copy.get(pin_id)` returns empty/None, the pin is skipped with a warning and added to the failures list. This is correct behavior, but the failure is not propagated to the Sheet or Slack. The user sees fewer pins than expected in the Content Queue with no explanation.
- **Evidence:** Lines 118-121: `if not pin_copy: logger.warning("No copy generated for pin %s, skipping", pin_id); failures.append(...)`.
- **Impact:** Minor -- the pin count mismatch is visible in the Content Queue, and the user can check workflow logs. But there's no proactive alert about which specific pins failed copy generation.

### [LOW] GitHub Actions `notify-failure` composite action swallows its own failures

- **Dimension:** Failure modes
- **File(s):** `.github/actions/notify-failure/action.yml`
- **Description:** The notify-failure action uses `|| echo "Slack notification failed"` to prevent the Slack notification failure from failing the workflow step. This means if the workflow fails AND Slack is down, the failure notification is silently dropped.
- **Evidence:** The `|| echo` pattern in the action's run step.
- **Impact:** Low -- GitHub Actions already records the workflow failure status, so the user can see it in the Actions tab. The Slack alert is a convenience, not the sole failure record.

### [LOW] Non-atomic `pin-generation-results.json` write in `regen_content.py`

- **Dimension:** Failure modes
- **File(s):** `src/regen_content.py:380-387`
- **Description:** `pin_results_path.write_text()` at line 381 is not an atomic write (no temp file + rename). If the process is interrupted mid-write, the JSON file could be left in a corrupted (partial) state, breaking the next workflow run.
- **Evidence:** Line 381-384: `pin_results_path.write_text(json.dumps(pin_results, indent=2, ensure_ascii=False), encoding="utf-8")` -- direct write, no temp file.
- **Impact:** Low -- GitHub Actions runners rarely get interrupted mid-write, and the file is regenerated each workflow run. But it's inconsistent with the atomic write pattern used elsewhere (e.g., `post_pins.py:639-643`).

---

## Summary of Recommended Fixes (Priority Order)

1. **[HIGH] Fix OpenAI exception type:** Wrap `response.raise_for_status()` in a try/except that converts `requests.HTTPError` to `OpenAIChatAPIError` in `openai_chat_api.py:124`.

2. **[HIGH] Fix null check in regen Drive fallback:** Add `if drive is not None:` guard before `drive.download_image()` in `regen_content.py:578`. Update type hint on `_regen_item()` to `Optional[DriveAPI]`.

3. **[HIGH] Don't send "content ready" Slack if Sheets write failed:** Set a flag on Sheets write failure in `publish_content_queue.py` and either skip or modify the Slack notification.

4. **[HIGH] Add logging to bare `except Exception: pass` blocks:** At minimum, add `logger.warning(...)` to `post_pins.py:280-281` and `regen_content.py:167-168, 198-199, 267-269, 314-315`.

5. **[HIGH] Add Slack fallback for permanent pin failure alerts:** In `post_pins.py:657-664`, if Slack fails, write the alert to a file or set the GitHub Actions step output so the workflow can surface it.

6. **[MEDIUM] Consider write-before-clear for Sheets:** Instead of clear-then-write, write to a temp range, then swap (or at least batch the clear+write in a single batchUpdate request).

7. **[MEDIUM] Narrow the GPT-5 Mini fallback catch:** In `claude_api.py:254`, catch `(OpenAIChatAPIError, ValueError, requests.HTTPError)` instead of `Exception`.

8. **[MEDIUM] Upgrade header validation to raise:** Remove the TODO and make `_validate_headers()` raise on mismatch in `sheets_api.py:142-169`.

9. **[MEDIUM] Gate pin scheduling on URL verification:** In `blog_deployer.py`, skip scheduling pins whose blog URLs failed verification.

10. **[LOW] Add retry for image URL downloads:** In `image_gen.py:242-244`, add a simple 1-retry loop for the `requests.get()` call before falling back to full regeneration.
