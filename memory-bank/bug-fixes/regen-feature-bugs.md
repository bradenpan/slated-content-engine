# Regen Feature: Bug Fixes Required Before Monday Launch

**Date:** 2026-02-21
**Source:** Three-agent deep code review of the regen feature implementation

---

## Bug 1: Hero Images Don't Exist on Regen Runner (CRITICAL)

### The Problem

When a user sets a pin to `regen_copy` ("keep the image, redo the title/description"), the regen workflow needs the original hero image to re-render the pin with new text overlay. But pin PNGs are gitignored (`*.png` in `.gitignore` line 37), so they're never committed to the repo. On a fresh GitHub Actions runner, `hero_image_path` points to a file that doesn't exist.

**Result:** `regen_copy` silently produces no visible output. The Sheet row gets updated title/description but the thumbnail doesn't change and no re-rendered pin is created.

### Options

#### Option A: Store Drive File ID + Download on Regen (Recommended)

During initial publish (`publish_content_queue.py`), after uploading each pin image to Google Drive, save the Drive file ID back into `pin-generation-results.json`. During regen, when the local hero image file doesn't exist, download it from Drive to a temp path, then proceed with re-rendering.

**Files changed:**
- `src/publish_content_queue.py` — after `drive.upload_pin_images()`, merge the Drive file IDs/URLs back into pin data and re-save `pin-generation-results.json`
- `src/apis/drive_api.py` — add `download_image(file_id, output_path)` method
- `src/regen_content.py` — before re-rendering, check if hero image exists locally; if not, download from Drive using stored file ID

**Pros:**
- Fully correct behavior: the user's original image is preserved and re-rendered with new text
- Honors the user's intent — they explicitly chose `regen_copy` to keep the image
- Clean architecture: Drive becomes the durable image store, local paths are ephemeral
- Works for any number of regen cycles

**Cons:**
- Most code to write (~30 min)
- Adds a Drive download dependency to the regen workflow (adds ~5-10 sec per image)
- Requires modifying `publish_content_queue.py` to save Drive metadata back to JSON (this is a new data flow)

---

#### Option B: Skip Re-Render for `regen_copy`

For `regen_copy`, only update the title, description, and alt text in the Sheet. Don't attempt to re-render the pin image or update the thumbnail. The pin image retains its old text overlay.

**Files changed:**
- `src/regen_content.py` — when `regen_type == "regen_copy"` and hero image doesn't exist, skip the assembly/upload block entirely; only update text columns in the Sheet

**Pros:**
- Simplest fix (5 min)
- No new dependencies or data flows
- Zero risk of breaking anything else

**Cons:**
- The pin IMAGE still shows the old text overlay (e.g., old headline baked into the PNG)
- The Sheet shows updated title/description but the thumbnail is stale — potentially confusing
- Only the metadata changes; the actual pin posted to Pinterest will have old text overlay unless the user also does a `regen_image` later
- Feels incomplete — users may wonder why the pin image didn't change

---

#### Option C: Promote `regen_copy` to Full `regen`

Treat any `regen_copy` request as a full `regen` — re-source both the image and the copy. This sidesteps the missing file problem entirely because a new image is always sourced.

**Files changed:**
- `src/regen_content.py` — change the `do_image` / `do_copy` logic: if `regen_type == "regen_copy"` and hero image doesn't exist locally, set `do_image = True`

**Pros:**
- Simple code change (5 min)
- Always produces a complete output (new image + new copy)
- No new dependencies

**Cons:**
- Wastes API calls re-sourcing an image the user was happy with
- The user specifically said "keep the image, fix the copy" — this ignores their intent
- New image may be worse than the original (the user liked the original image)
- More expensive (stock API + Claude ranking calls per regen_copy request)
- Slower (~30 sec extra per item for image sourcing)

---

#### Option D: Commit Pin Images to Git (Not Recommended)

Remove `*.png` from `.gitignore` so hero images and rendered PNGs get committed to the repo.

**Files changed:**
- `.gitignore` — remove `*.png` line

**Pros:**
- No code changes needed at all
- Images are always available on every runner

**Cons:**
- Bloats the repo significantly (~28 PNGs x ~500KB each = ~14MB per week, accumulating)
- Git is not designed for binary blob storage
- Slows down every checkout (every workflow, not just regen)
- Cannot be undone easily (git history retains all binary files forever)
- **Not recommended for any project**

---

### Recommendation: Option A

Option A is the correct long-term fix. It adds ~25 minutes of implementation time but produces the right behavior: the user's original image is preserved and the pin is properly re-rendered with new copy. The Drive download adds minimal latency and the architecture is clean — Drive is already the durable store for pin images, this just makes it accessible to the regen workflow.

If time is truly critical before Monday, Option B is an acceptable stopgap — it prevents the silent failure and at least updates the Sheet text, even if the thumbnail doesn't reflect the new overlay. But Option A should be done before the second week of use.

---

## Bug 2: Copy Feedback Ignored by Claude (CRITICAL)

### The Problem

When a user writes copy feedback (e.g., "Title is too generic, reference slow cooker") and sets status to `regen_copy`, the feedback is stored in the pin spec as `_copy_feedback`. But `generate_pin_copy()` in `claude_api.py` never reads or uses this field. The pin spec JSON is passed to Claude as part of the prompt context, but there's no instruction telling Claude to look for or act on feedback.

**Contrast:** Image feedback works correctly — it's explicitly appended to the system message with "IMPORTANT: The previous image was rejected..."

### Fix

In `src/apis/claude_api.py`, in the `generate_pin_copy()` method, check if any pin spec in the batch contains `_copy_feedback`. If so, append to the system message:

```
"IMPORTANT: The reviewer rejected the previous copy for one or more pins.
Check each pin's _copy_feedback field and address the feedback specifically.
The previous version was rejected because of the stated reason — make sure
the new copy directly addresses the concern."
```

**Files:** `src/apis/claude_api.py` (generate_pin_copy method, ~5 lines added)

---

## Bug 3: Blog Regen Silently Fails (MEDIUM)

### The Problem

Blog items (type="blog") have post IDs like "B12-01" but `pin-generation-results.json` only contains pins. The regen script looks up `pin_index.get("B12-01")`, gets `None`, logs a warning, and skips the item. The Sheet row stays as `regen_*` status, permanently blocking the deploy gate.

### Fix

In `src/regen_content.py`, before the pin lookup, check if `item_type == "blog"`. If so, reset the row to `pending_review` with a note "Blog regen not yet supported — please approve or reject manually" and continue to the next item. This prevents the deploy gate from being permanently blocked.

**Files:** `src/regen_content.py` (~10 lines added before the pin_index lookup)

---

## Bug 4: Duplicate Images Accumulate in Drive (MEDIUM)

### The Problem

Each regen cycle calls `drive.upload_image()` which adds a new file without deleting the old version. Over time, orphan images accumulate in the Drive folder.

### Fix

Add a `delete_image_by_name()` method to `DriveAPI` that searches for and deletes a file by name in the pins folder. Call it in `_regen_item()` before uploading the replacement.

**Files:** `src/apis/drive_api.py` (new method), `src/regen_content.py` (call before upload)

---

## Bug 5: Failed Regens Not Reported (MEDIUM)

### The Problem

If image generation fails for a pin during regen, the error is caught and logged, but: (1) no entry is added to `regen_results` for the failure, (2) the Slack notification only mentions successes, (3) if all items fail no notification is sent, (4) failed rows stay as `regen_*` blocking the deploy gate.

### Fix

Track failures alongside successes. For failed items, reset Sheet status to `pending_review` with note "Regen failed — [error reason]". Include failure count in Slack notification: "2 regenerated, 1 failed — ready for re-review."

**Files:** `src/regen_content.py` (failure tracking + Sheet reset), `src/apis/slack_notify.py` (failure count in message)

---

## Summary

| # | Bug | Severity | Recommended Fix | Est. Effort |
|---|-----|----------|----------------|-------------|
| 1 | Hero images missing on runner | CRITICAL | Option A: Store Drive ID + download | 30 min |
| 2 | Copy feedback ignored | CRITICAL | Add to system message in generate_pin_copy() | 15 min |
| 3 | Blog regen silent failure | MEDIUM | Reset to pending_review with note | 10 min |
| 4 | Drive image accumulation | MEDIUM | Delete old image before upload | 10 min |
| 5 | Failed regens unreported | MEDIUM | Track + notify + reset status | 15 min |

**Total: ~1.5 hours**
