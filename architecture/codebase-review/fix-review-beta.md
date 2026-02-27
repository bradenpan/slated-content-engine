# Fix Review (Beta Reviewer)

Reviewing 11 fixes against the synthesis prescriptions.

---

## Fix 6 [H4]: `src/generate_weekly_plan.py:309` atomic write

**Verdict: CORRECT**

Lines 309-324 implement the temp+rename pattern correctly:
- Creates `tmp_path = plan_path.with_suffix(".tmp")` (line 311)
- Writes JSON to temp file (lines 313-316)
- Atomically replaces with `tmp_path.replace(plan_path)` (line 317)
- On failure: catches `OSError`, logs error, cleans up temp file with `tmp_path.unlink(missing_ok=True)` in a nested try/except, then re-raises (lines 318-324)

This follows the same pattern used in `content_log.py` and `plan_utils.py`. Temp file cleanup on failure is correct with `missing_ok=True` to handle the case where the temp file was never created.

---

## Fix 9 [H3]: `src/generate_weekly_plan.py` plan validation

**Verdict: CORRECT**

`_validate_plan_structure()` is defined at lines 341-375 and called at line 132 (immediately after Claude response is assigned to `plan` at line 130). The function:

1. Checks `plan` is a dict (line 354) -- handles `plan is None` since `None` is not a dict
2. Checks `"blog_posts"` key exists (line 361)
3. If present, checks it is a list and non-empty (line 363)
4. Same checks for `"pins"` (lines 366-369)
5. Collects all missing/invalid fields and raises a single `ValueError` with a clear message (lines 371-375)
6. Error messages include guidance about Claude possibly returning different key names (line 374)

Edge cases handled correctly: `plan is None` (fails isinstance check at 354), `plan is not a dict` (same), keys exist but are empty lists (caught by `not plan["blog_posts"]` at 363), keys missing entirely (caught by `"blog_posts" not in plan` at 361).

---

## Fix 8 [H4]: `src/redate_schedule.py` use `save_pin_schedule()`

**Verdict: CORRECT**

Line 15 imports `save_pin_schedule` from `src.utils.plan_utils`. Line 41 calls `save_pin_schedule(schedule, path)` which matches the function signature `save_pin_schedule(schedule: list[dict], path: Path = None)` in `plan_utils.py:266`.

The `path` variable is set at line 26 as `schedule_path or (DATA_DIR / "pin-schedule.json")`, which is a `Path` object, matching the expected type. The old direct `path.write_text()` pattern is completely replaced.

---

## Fix 10 [H6]: `src/blog_generator.py` validation

**Verdict: CORRECT**

In `_validate_generated_post()` (lines 407-482):

- Lines 440-446: Hard-fail loop over `("title", "slug", "description")` -- checks each field with `frontmatter.get(critical_field)` and also checks for empty/whitespace strings. Raises `BlogGeneratorError` with a clear message identifying the post_id and missing field.
- Lines 454-468: Word count checks remain as `logger.warning()` only (not raised)
- Lines 471-482: CTA presence checks remain as `logger.warning()` only (not raised)

This matches the synthesis prescription exactly: promote title/slug/description to hard errors, keep word count and CTA as warnings. The empty content check at lines 419-422 also still raises as before.

---

## Fix 12 [H7]: `src/post_pins.py:280-281` bare except

**Verdict: CORRECT**

Lines 280-281 now read:
```python
except Exception as e:
    logger.warning("Failed to update Sheet with failure status for %s: %s", pin_id, e)
```

The `except Exception` captures the exception as `e` (no longer bare). The log message at `logger.warning` level includes both `pin_id` and the exception `e`. This matches the synthesis prescription exactly. The log message is descriptive ("Failed to update Sheet with failure status for %s: %s").

---

## Fix 13 [H7]: `src/post_pins.py:664` bare except

**Verdict: CORRECT**

Lines 664-665 now read:
```python
except Exception as e:
    logger.error("Failed to send permanent failure alert for %s: %s", pin_id, e)
```

Uses `logger.error` (appropriate since this is a permanent failure alert path), includes both `pin_id` and the exception. This matches the synthesis prescription which called for `logger.error` at this location (vs. `logger.warning` for fix 12).

---

## Fix 16 [M3]: `src/apis/openai_chat_api.py:124` exception wrapping

**Verdict: CORRECT**

Lines 123-128 now read:
```python
try:
    response.raise_for_status()
except requests.HTTPError as e:
    raise OpenAIChatAPIError(
        f"OpenAI API HTTP error {response.status_code}: {e}"
    ) from e
```

- Wraps `response.raise_for_status()` in a try/except
- Catches specifically `requests.HTTPError` (not broad Exception)
- Re-raises as `OpenAIChatAPIError` with informative message including status code
- Preserves the exception chain with `from e`
- `requests` is already imported at line 20, `OpenAIChatAPIError` is defined at line 29

All requirements met.

---

## Fix 17 [M4]: `src/apis/claude_api.py:254` narrow exception

**Verdict: CORRECT**

Line 256 now reads:
```python
except (OpenAIChatAPIError, ValueError, requests.HTTPError) as e:
```

Checking imports:
- `OpenAIChatAPIError`: imported at line 36 (`from src.apis.openai_chat_api import OpenAIChatAPIError, call_gpt5_mini`)
- `ValueError`: built-in, no import needed
- `requests`: imported at line 34 (`import requests`), so `requests.HTTPError` is accessible

All three exception types are present in the imports. The narrowed exception list matches the synthesis prescription exactly. Programming errors (`TypeError`, `KeyError`, etc.) will now properly surface instead of being silently caught and retried on the more expensive Claude Sonnet model.

---

## Fix 18 [M2]: `src/blog_deployer.py` filter unverified URLs

**Verdict: CORRECT**

In `promote_to_production()`, lines 266-282 implement the filter:

1. Line 267-270: Builds `failed_slugs` set from `verification_results` where `ok` is `False`
2. Line 271: Only applies filter if there are actually failed slugs (avoids unnecessary processing)
3. Lines 273-276: Filters `approved_pins` to exclude pins whose `blog_slug` (or fallback `slug`) is in `failed_slugs`
4. Lines 272, 277-282: Tracks `original_count` vs filtered count and logs a warning with the count and which slugs were excluded

The filter uses `pin.get("blog_slug", pin.get("slug", ""))` which correctly handles both possible key names for the blog slug in pin data. The filter is applied before `_create_pin_schedule()` at line 284, so excluded pins never enter the schedule.

One subtle point: the filter only fires when `failed_slugs` is non-empty (line 271), so no pins are accidentally excluded when all verifications pass. This is correct.

---

## Fix 19 [M7/L5]: `.env.example`

**Verdict: PROBLEM**

The synthesis prescribed:
- Add `PINTEREST_ENVIRONMENT=sandbox` (or with default value)
- Add `IMAGE_GEN_PROVIDER=openai` (or with default value)
- Add `GCS_BUCKET_NAME=slated-pipeline-pins` (or with default value)
- Remove `UNSPLASH_ACCESS_KEY`
- Remove `PEXELS_API_KEY`

Current `.env.example` content shows:
- `UNSPLASH_ACCESS_KEY=` is still present (NOT removed)
- `PEXELS_API_KEY=` is still present (NOT removed)
- `PINTEREST_ENVIRONMENT` is NOT present (not added)
- `IMAGE_GEN_PROVIDER` is NOT present (not added)
- `GCS_BUCKET_NAME` is NOT present (not added)

None of the five prescribed changes were made. The `.env.example` file appears unchanged from its pre-fix state.

---

## Fix 20 [M8]: Workflow files `REPLICATE_API_TOKEN`

**Verdict: PROBLEM**

The synthesis prescribed adding `REPLICATE_API_TOKEN: ${{ secrets.REPLICATE_API_TOKEN }}` to both workflow env blocks.

Checking `generate-content.yml` env block: `REPLICATE_API_TOKEN` is NOT present. The env block lists Pinterest, Anthropic, Google Sheets, Slack, GitHub, OpenAI, and GCS secrets, but no Replicate.

Checking `regen-content.yml` env block: `REPLICATE_API_TOKEN` is NOT present. Same set of secrets as generate-content.yml.

Neither workflow file has the `REPLICATE_API_TOKEN` added.

---

## Summary

| Fix | Finding | Verdict |
|-----|---------|---------|
| 6  | H4: atomic write for weekly plan | CORRECT |
| 9  | H3: plan validation | CORRECT |
| 8  | H4: redate_schedule use save_pin_schedule | CORRECT |
| 10 | H6: blog validation hard errors | CORRECT |
| 12 | H7: post_pins:280 bare except | CORRECT |
| 13 | H7: post_pins:664 bare except | CORRECT |
| 16 | M3: openai_chat_api exception wrapping | CORRECT |
| 17 | M4: claude_api narrow exception | CORRECT |
| 18 | M2: blog_deployer filter unverified URLs | CORRECT |
| 19 | M7/L5: .env.example updates | PROBLEM |
| 20 | M8: workflow REPLICATE_API_TOKEN | PROBLEM |

**9/11 correct, 2 problems, 0 minor issues.**

The two problems (fixes 19 and 20) are both configuration file changes that appear to not have been applied at all. The `.env.example` still contains vestigial entries and is missing three new variables. Neither workflow file has the `REPLICATE_API_TOKEN` secret added.
