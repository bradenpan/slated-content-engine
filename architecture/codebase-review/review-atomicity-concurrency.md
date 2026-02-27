# Review: Data Atomicity + Concurrency

**Reviewer:** Claude Opus 4.6
**Date:** 2026-02-27
**Scope:** All file write operations, concurrency groups, race conditions

---

## Summary

The codebase shows **strong atomic write discipline** in the most critical data files, with the temp-file-then-rename pattern already implemented in content_log.py, post_pins.py, generate_pin_content.py, generate_blog_posts.py, and plan_utils.py. However, several files bypass this pattern, and there are meaningful concurrency gaps in the workflow design.

**Findings:** 3 HIGH, 5 MEDIUM, 3 LOW

---

## Dimension 1: Data Atomicity

### [HIGH] Token store writes are not atomic

- **Dimension:** Data atomicity
- **File(s):** `src/token_manager.py:391`
- **Description:** `_save_tokens()` writes directly to `data/token-store.json` via `json.dump()` into an open file handle. If the process crashes mid-write (e.g., OOM kill during a long-running workflow step), the token store will be left with a truncated/corrupt JSON file. On the next run, `_load_tokens()` will fall back to environment variables (line 358), but the corrupt file on disk will still be there. Since file existence is checked first (line 352), the corrupt file will be read, json.load will fail, and only then will it fall back to env vars. This fallback works, but the corrupt file persists indefinitely.
- **Evidence:** Lines 390-396 show `open(self.token_store_path, "w") -> json.dump()` without a temp+rename pattern. Contrast with `save_content_log()` at content_log.py:62-77 which correctly uses `.with_suffix(".tmp")` then `.replace()`.
- **Impact:** A crash during token refresh leaves a corrupt token-store.json. The next run reads the corrupt file, gets a JSONDecodeError, falls back to env vars (which hold stale tokens), forces a refresh, and succeeds. The corrupt file stays on disk but causes an unnecessary warning every run until manually cleaned up. In the worst case, if env vars also lack valid tokens, the entire pipeline halts.

### [HIGH] regen_content.py saves pin-generation-results.json non-atomically

- **Dimension:** Data atomicity
- **File(s):** `src/regen_content.py:381-384`
- **Description:** The `regen()` function writes pin-generation-results.json directly via `write_text()` without a temp+rename pattern. This is the same file that `generate_pin_content.py:793-807` writes atomically. A crash during the regen save could corrupt the file, breaking the entire content generation and posting pipeline (post_pins.py, blog_deployer.py, and publish_content_queue.py all read this file).
- **Evidence:** Line 381: `pin_results_path.write_text(json.dumps(pin_results, indent=2, ...))` -- direct write. Compare with `_save_pin_results()` at generate_pin_content.py:793 which uses the temp+rename pattern. Similarly, blog_results at regen_content.py:425 is also written non-atomically.
- **Impact:** Corrupt pin-generation-results.json would break blog deployment (blog_deployer.py:467-471), pin posting schedule creation, and content queue publishing. This file is the single source of truth for all generated pin metadata.

### [MEDIUM] publish_content_queue.py saves pin-generation-results.json non-atomically

- **Dimension:** Data atomicity
- **File(s):** `src/publish_content_queue.py:122-128`
- **Description:** After uploading images to GCS/Drive and adding image URLs to the pin data, `publish()` writes pin-generation-results.json directly via `write_text()` without a temp+rename pattern. Same file, same risk as the regen_content.py finding above.
- **Evidence:** Line 122: `pin_results_path.write_text(json.dumps(pin_data, indent=2, ...))` -- direct write with no atomic rename.
- **Impact:** Corrupt pin-generation-results.json would lose all image URLs, requiring a full re-run of publish_content_queue.py to re-upload images.

### [MEDIUM] content-log.jsonl append is not atomic

- **Dimension:** Data atomicity
- **File(s):** `src/utils/content_log.py:80-94`
- **Description:** `append_content_log_entry()` opens the file in append mode and writes a single JSON line. While append-mode writes of small strings on Linux are typically atomic (below PIPE_BUF size), this is not guaranteed on all platforms or filesystems. On GitHub Actions (Ubuntu/ext4), single-line appends under 4096 bytes are effectively atomic, so the practical risk is low. The bigger issue is that there's no `f.flush()` or `os.fsync()` before the file handle closes, meaning the data could be lost if the process is killed before the OS flushes buffers.
- **Evidence:** Lines 89-91: `open(p, "a") -> f.write(json.dumps(entry) + "\n")`. No explicit flush/fsync. The `save_content_log()` full-rewrite function (line 51) uses proper temp+rename, but the append path does not.
- **Impact:** In the worst case, the last appended line could be partially written. The `load_content_log()` function already handles this via the malformed-line skip at line 39-42, so the pipeline would lose one entry but not crash. Low practical risk, but not crash-safe by design.

### [MEDIUM] generate_weekly_plan.py saves plan JSON non-atomically

- **Dimension:** Data atomicity
- **File(s):** `src/generate_weekly_plan.py:309-312`
- **Description:** The weekly plan JSON is written directly via `plan_path.write_text()` without a temp+rename pattern. A crash during write would corrupt the plan file, which is the input to the entire content generation pipeline.
- **Evidence:** Lines 309-312: `plan_path.write_text(json.dumps(plan, indent=2, ...))`. No temp file.
- **Impact:** Corrupt plan file would prevent content generation from running until manually fixed or the plan is regenerated.

### [MEDIUM] regen_weekly_plan.py saves plan JSON non-atomically

- **Dimension:** Data atomicity
- **File(s):** `src/regen_weekly_plan.py:208-211`
- **Description:** Same issue as generate_weekly_plan.py -- the updated plan is written directly via `plan_path.write_text()`.
- **Evidence:** Lines 208-211: `plan_path.write_text(json.dumps(updated_plan, indent=2, ...))`.
- **Impact:** Same as above -- corrupt plan file blocks the pipeline.

### [MEDIUM] redate_schedule.py saves pin-schedule.json non-atomically

- **Dimension:** Data atomicity
- **File(s):** `src/redate_schedule.py:40`
- **Description:** `redate()` writes pin-schedule.json directly via `path.write_text()`. This is inconsistent with `save_pin_schedule()` in plan_utils.py:266-277 which uses the temp+rename pattern for the same file.
- **Evidence:** Line 40: `path.write_text(json.dumps(schedule, indent=2))` -- direct write. Compare with `save_pin_schedule()` at plan_utils.py:274 which uses `tmp.replace(p)`.
- **Impact:** Corrupt pin-schedule.json would cause pin posting to fail for the entire week.

### [LOW] Analytics snapshot writes are not atomic

- **Dimension:** Data atomicity
- **File(s):** `src/pull_analytics.py:454-456`
- **Description:** `_save_analytics_snapshot()` writes the raw analytics snapshot directly via `json.dump()` into an open file handle. Unlike the content log rewrite (which is done atomically via `save_content_log()`), the snapshot file uses a direct write.
- **Evidence:** Lines 454-456: `open(snapshot_path, "w") -> json.dump(snapshot, f)`. No temp+rename.
- **Impact:** Low severity because analytics snapshots are historical records that don't affect pipeline operation. A corrupt snapshot can be regenerated by re-running analytics. The content log update in the same function (line 206: `save_content_log(entries)`) is properly atomic.

### [LOW] Weekly analysis and monthly review markdown writes are not atomic

- **Dimension:** Data atomicity
- **File(s):** `src/weekly_analysis.py:283-284`, `src/monthly_review.py:390-391`
- **Description:** Both `save_analysis()` and `save_monthly_review()` use `output_path.write_text()` directly without temp+rename.
- **Evidence:** weekly_analysis.py:284: `output_path.write_text(analysis)`. monthly_review.py:391: `output_path.write_text(review)`.
- **Impact:** Very low. These are human-readable analysis reports that don't drive any automated pipeline logic. A corrupt file just means the analysis needs to be re-run.

### [LOW] content_memory.py summary write is not atomic

- **Dimension:** Data atomicity
- **File(s):** `src/utils/content_memory.py:407`
- **Description:** `_write_summary()` writes `content-memory-summary.md` directly via `write_text()`. This file is read by the planning prompt as context.
- **Evidence:** Line 407: `memory_path.write_text(summary)`.
- **Impact:** Very low. The content memory summary is regenerated every Monday before use. A corrupt file would result in incomplete context for the planning prompt but would not cause a pipeline failure.

### [LOW] blog_generator.py save_post is not atomic

- **Dimension:** Data atomicity
- **File(s):** `src/blog_generator.py:647`
- **Description:** `save_post()` writes MDX files directly via `write_text()`. These generated blog post files are inputs to blog_deployer.py.
- **Evidence:** Line 647: `file_path.write_text(mdx_content)`.
- **Impact:** Low. A corrupt MDX file would be caught by the blog deployer when it tries to read and parse frontmatter. The blog post could be regenerated.

---

## Dimension 2: Concurrency

### [HIGH] Posting workflows share a concurrency group but can still race on data

- **Dimension:** Concurrency
- **File(s):** `.github/workflows/daily-post-morning.yml:12`, `daily-post-afternoon.yml:12`, `daily-post-evening.yml:12`
- **Description:** The three daily posting workflows use concurrency group `pinterest-posting`, which correctly prevents two posting slots from running simultaneously. However, this is a **different** concurrency group from the `pinterest-pipeline` group used by the content generation, deployment, and review workflows. This means a posting workflow CAN run concurrently with content generation, deployment, or analytics pull -- and they all touch the same data files:
  - `data/content-log.jsonl` -- appended by post_pins.py, rewritten by pull_analytics.py
  - `data/pin-schedule.json` -- read by post_pins.py, written by blog_deployer.py
  - `data/posting-failures.json` -- read/written by post_pins.py

  The most dangerous scenario: **pull_analytics.py rewrites content-log.jsonl (via `save_content_log()`) while post_pins.py is appending to it.** The analytics pull reads all entries, updates metrics, then rewrites the entire file. If a pin was posted and appended to the log after the analytics pull read the file but before it wrote, the new pin entry would be silently lost.
- **Evidence:** Workflow files show `group: pinterest-posting` for daily posts but `group: pinterest-pipeline` for weekly-review.yml (which runs pull_analytics). The weekly review runs Monday 6am ET; the morning post runs at 10am ET. These don't overlap in normal scheduling, but manual `workflow_dispatch` triggers could cause overlap. Also, content-log.jsonl is appended to by blog_deployer.py (promote step) which runs in `pinterest-pipeline` group and could overlap with posting.
- **Impact:** In the normal cron schedule, the weekly review (6am) completes before the first post (10am), so this race is unlikely under normal operation. However, manual dispatch, delayed workflow queuing, or long-running analytics pulls could cause overlap. The result would be a **silently lost content log entry** -- a posted pin that disappears from analytics tracking.

### [MEDIUM] commit-data action has a push race that handles rebases but not content conflicts

- **Dimension:** Concurrency
- **File(s):** `.github/actions/commit-data/action.yml:22-39`
- **Description:** The commit-data action handles push races well: it does `git pull --rebase` and retries up to 3 times with random sleep. However, it treats rebase conflicts as fatal (line 28: `git rebase --abort; exit 1`). Since all workflows modify files in `data/` and `analysis/`, two concurrent workflows could edit different files (no conflict) or the same file (conflict). The `git add data/ analysis/` at line 14 stages ALL changes in those directories, not just the changes made by the current workflow. This means a workflow could accidentally commit another workflow's uncommitted changes if they share a runner workspace (they don't, since each gets a fresh checkout, but the `git pull --rebase` could pull in changes to the same files).

  The key risk: if two workflows touch the same file (e.g., both modify content-log.jsonl), the rebase will conflict and the second workflow's commit will fail. The content-log.jsonl changes from the second workflow are then lost.
- **Evidence:** Lines 22-39 show the retry loop. Line 28 aborts rebase on conflict. The `cancel-in-progress: false` setting on all workflows means queued workflows wait rather than cancel, which helps but doesn't eliminate the race window.
- **Impact:** Under normal operation, the `pinterest-pipeline` concurrency group serializes most workflows, and `pinterest-posting` serializes posting workflows. The real risk is between the two groups (a posting workflow running concurrently with a pipeline workflow, both trying to commit to `data/`). In practice, this would cause the second workflow's commit to fail with a rebase conflict, and the pipeline step that committed the data would be marked as failed. The data written by the Python script would be lost (since it's in a ephemeral runner workspace).

### [MEDIUM] Token refresh race between concurrent workflows

- **Dimension:** Concurrency
- **File(s):** `src/token_manager.py:167-265`
- **Description:** Every workflow that uses the Pinterest API runs `python -m src.token_manager` to refresh the token if needed. If two workflows run concurrently (from different concurrency groups), they could both decide the token needs refresh, both call the Pinterest API, and both receive new tokens. The second refresh would invalidate the first refresh's tokens (Pinterest invalidates old tokens on refresh). Since token_manager.py caches tokens in memory (`self._token_data` at line 348), the first workflow would continue using the now-invalid token from its first refresh.

  On GitHub Actions, each workflow gets a fresh checkout and runs independently. Token store is committed to `data/token-store.json` via git. If Workflow A refreshes and commits the new token, then Workflow B (running concurrently) still has the old token in its checkout. When Workflow B tries to refresh, it would use the old refresh token. After Workflow A's refresh, the old refresh token may or may not still be valid (depends on Pinterest's behavior -- they document that "both tokens change on refresh").
- **Evidence:** The `pinterest-pipeline` group serializes weekly-review, generate-content, deploy, regen-plan, regen-content. The `pinterest-posting` group serializes posting. But a posting workflow can run concurrently with a pipeline workflow. Both start with `python -m src.token_manager`. If the token is near expiry, both could attempt refresh simultaneously. The `_save_tokens()` call at line 256 writes to disk, but the concurrent workflow has its own disk copy.
- **Impact:** In practice, this is mitigated because: (1) tokens have a 30-day lifetime with 5-day threshold, so refreshes are rare; (2) each workflow gets a fresh checkout so they don't share the token file on disk; (3) the `pinterest-posting` group handles its own token refresh. The real risk is if one workflow refreshes and invalidates the old refresh token while another workflow is about to use it. Pinterest's continuous_refresh tokens should handle this gracefully (each refresh gives a new valid refresh token), but a race could cause one workflow to fail with an auth error. The retry logic in `_create_pin_with_retry()` (post_pins.py:584-593) handles 401 errors by refreshing again, which mitigates this.

### [MEDIUM] No file locking on content-log.jsonl

- **Dimension:** Concurrency
- **File(s):** `src/utils/content_log.py:51-77`, `src/utils/content_log.py:80-94`
- **Description:** `save_content_log()` (full rewrite) and `append_content_log_entry()` have no file locking. If two processes attempt to operate on the file simultaneously:
  - Two appends: Both could interleave writes, producing garbled JSON on a single line. This is mitigated by OS-level atomicity of small writes in append mode on Linux.
  - An append during a rewrite: The append targets the original file, which the rewrite replaces atomically via `tmp.replace()`. The append's file descriptor still points to the old file (now unlinked), so the appended data is lost.
  - Two rewrites: The last one wins. Data from the first rewrite is lost.

  On GitHub Actions, each workflow runs in its own environment, so direct process-level concurrency doesn't happen. The risk is at the git level (see commit-data finding above).
- **Evidence:** No `fcntl.flock()` or `msvcrt.locking()` calls anywhere in the codebase. The content_log.py module relies on OS-level guarantees and workflow serialization.
- **Impact:** Under normal workflow serialization, this is not a problem. The risk exists only when workflows from different concurrency groups run simultaneously and both touch content-log.jsonl (posting + analytics pull). The impact would be lost content log entries.

---

## Positive Findings (Already Correct)

The following writes are properly atomic (temp file + rename pattern):

1. **`src/utils/content_log.py:62-68`** -- `save_content_log()` uses `.with_suffix(".tmp")` then `.replace()`. Correct.
2. **`src/post_pins.py:639-649`** -- `_record_failure()` writes posting-failures.json atomically. Correct.
3. **`src/generate_pin_content.py:793-807`** -- `_save_pin_results()` writes pin-generation-results.json atomically. Correct.
4. **`src/generate_blog_posts.py:224-239`** -- `_save_generation_metadata()` writes blog-generation-results.json atomically. Correct.
5. **`src/utils/plan_utils.py:274-277`** -- `save_pin_schedule()` writes pin-schedule.json atomically. Correct.

The concurrency group design is mostly sound:

1. **`pinterest-pipeline`** group serializes all planning, generation, deployment, and review workflows. This prevents most races.
2. **`pinterest-posting`** group serializes all three daily posting windows. This prevents posting races.
3. **`cancel-in-progress: false`** on all workflows means workflows queue rather than cancel, preserving work.
4. **commit-data action** has a 3-attempt retry with rebase for push races. This handles the most common concurrency scenario.

---

## Recommended Fixes (Priority Order)

1. **[HIGH] Make token store writes atomic** -- Add temp+rename pattern to `TokenManager._save_tokens()`.
2. **[HIGH] Make regen_content.py pin-generation-results.json write atomic** -- Use the same temp+rename pattern already used in generate_pin_content.py.
3. **[MEDIUM] Unify concurrency groups or add content-log.jsonl protections** -- Either move daily posting into the `pinterest-pipeline` group (simplest, but adds wait time) or add a lightweight advisory lock around content-log.jsonl operations.
4. **[MEDIUM] Make generate_weekly_plan.py and regen_weekly_plan.py plan writes atomic** -- Add temp+rename.
5. **[MEDIUM] Make redate_schedule.py use `save_pin_schedule()` from plan_utils** -- The function already exists and is atomic.
6. **[MEDIUM] Make publish_content_queue.py pin-generation-results.json write atomic** -- Add temp+rename.
