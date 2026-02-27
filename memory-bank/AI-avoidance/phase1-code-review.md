# Phase 1 Code Review: Image Metadata Stripping

**Reviewer:** reviewer agent
**Date:** 2026-02-26
**Verdict:** PASS WITH FIXES

---

## Files Reviewed

| File | Type | Lines Changed |
|------|------|---------------|
| `src/image_cleaner.py` | NEW | 93 lines |
| `src/generate_pin_content.py` | Modified | +4 lines |
| `src/pin_assembler.py` | Modified | +6 lines |
| `src/blog_deployer.py` | Modified | +8 lines |
| `requirements.txt` | Modified | +1 line |

---

## Issues Found

### MEDIUM-1: RGBA-to-RGB conversion drops alpha to black instead of white

**File:** `src/image_cleaner.py:73-74`
**Severity:** Medium

`img.convert("RGB")` fills transparent regions with black. Compare with `_optimize_image()` in `pin_assembler.py:577-581` which correctly composites RGBA on a white background before JPEG conversion.

In practice, AI-generated hero images are almost always RGB and Puppeteer screenshots are opaque PNGs, so this is unlikely to trigger. But if an RGBA image (e.g., a logo overlay or stylized pin) reaches `clean_image()`, transparent areas will become black.

**Recommendation:** Replace the simple `convert("RGB")` with alpha compositing on white:
```python
if img.mode in ("RGBA", "LA", "PA"):
    background = Image.new("RGB", img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[-1])  # use alpha as mask
    img = background
elif img.mode != "RGB":
    img = img.convert("RGB")
else:
    img = img.copy()
```

### MEDIUM-2: No error handling in `clean_image()` — can crash the pipeline

**File:** `src/image_cleaner.py` (entire function), integration in `src/pin_assembler.py:717-718` and `src/blog_deployer.py:506-508, 622-624`
**Severity:** Medium

`clean_image()` has no try/except. Compare with `_optimize_image()` which wraps everything in try/except and logs warnings on failure.

- In `render_pin()` (pin_assembler.py:507-509): The call is inside an existing try/except block, so failures are caught and wrapped as `PinAssemblerError`. **OK.**
- In `render_batch()` (pin_assembler.py:717-718): The call is NOT inside any try/except. A failure here would crash the entire batch loop, meaning subsequent pins in the batch are never processed. **Problem.**
- In `deploy_approved_posts()` (blog_deployer.py:506-508): NOT inside try/except. A failure on one hero image would crash the entire deployment loop. **Problem.**
- In `_deploy_blog_posts()` (blog_deployer.py:622-624): NOT inside try/except at this scope. A failure would crash the for-loop over `approved_blogs`. **Problem.**

**Recommendation:** Add a try/except inside `clean_image()` itself, matching the pattern of `_optimize_image()`:
```python
try:
    # ... existing logic ...
except Exception as e:
    logger.warning("Image cleaning failed for %s: %s", input_path, e)
    return input_path  # return original path so pipeline continues
```

### LOW-1: File extension mismatch (JPEG content with `.png` extension)

**File:** `src/image_cleaner.py:83`
**Severity:** Low

`clean_image()` always saves as `format="JPEG"` but writes to the original path, which may be `.png`. This creates files with mismatched extension and content type. Note: `_optimize_image()` does the same thing (line 589: renames `.jpg` to original `.png` path), so this is an existing pattern in the codebase.

In practice, browsers and Pinterest detect format by magic bytes, not extension. The blog deployer reads `actual_ext` from the path (not the file), so frontmatter will say `.png` while the file is JPEG. This works because Vercel/Next.js also uses content sniffing.

**Recommendation:** Low priority. Accept as-is since it matches existing codebase pattern. Could be improved later by having `clean_image()` return the path with the correct extension, but that would require downstream changes.

### LOW-2: Double-cleaning of hero images

**File:** `src/generate_pin_content.py:748` + `src/blog_deployer.py:508,624`
**Severity:** Low (informational)

Hero images are cleaned in `_source_ai_image()` when first generated, and then cleaned again in both `deploy_approved_posts()` and `_deploy_blog_posts()` when deploying. This means the same hero image may be cleaned twice (noise added twice, re-compressed twice).

This is harmless — re-cleaning an already-clean JPEG just adds another round of noise and recompression. The visual quality impact is negligible at sigma=1.5 and quality 89-94. However, it's technically unnecessary work and slightly degrades quality each pass.

**Recommendation:** Accept as-is. The redundancy is a safety net: if the hero image somehow skips the first cleaning (e.g., sourced from an existing file, not freshly generated), the deploy step still catches it. The quality loss from double-processing is imperceptible.

### LOW-3: Import style inconsistency

**File:** `src/generate_pin_content.py:29` vs `src/pin_assembler.py:508,717` and `src/blog_deployer.py:507,623`
**Severity:** Low (style)

`generate_pin_content.py` imports `clean_image` at the top of the file (line 29), while `pin_assembler.py` and `blog_deployer.py` use local imports inside the function body. The local import pattern is fine (avoids circular imports, defers import until needed), but the inconsistency is worth noting.

**Recommendation:** Accept as-is. Both patterns work correctly. The local imports in pin_assembler.py and blog_deployer.py are reasonable since image_cleaner is a new dependency and the lazy import pattern reduces coupling.

---

## Things That Look Correct

1. **Metadata stripping works correctly.** Pillow's `Image.open()` + `Image.save()` without passing `exif=` or other metadata kwargs produces a clean JPEG with no EXIF, IPTC, or XMP data. This is the documented Pillow behavior.

2. **Gaussian noise implementation is correct.** Uses `np.float32` for arithmetic to avoid overflow (line 32), clips to `[0, 255]` (line 34), converts back to `uint8`. No fixed random seed, so each call produces different noise.

3. **JPEG quality randomization works.** `random.randint(89, 94)` is inclusive on both ends, giving quality values 89, 90, 91, 92, 93, or 94. This is a reasonable range that varies the compression fingerprint without visible quality loss.

4. **`_optimize_image()` is NOT modified.** Verified via `git diff` — only new lines were added after the call to `_optimize_image()`, the function itself is untouched.

5. **Both blog deployer entry points are covered.** Both `deploy_approved_posts()` (line 506-508) and `_deploy_blog_posts()` (line 622-624) have `clean_image()` integration with proper `if hero_image_path:` guards.

6. **Infographic pins (no hero image) are handled.** The blog deployer checks `if hero_image_path:` before calling `clean_image()`, so `None` image paths are safely skipped.

7. **numpy is properly pinned.** `numpy>=1.24.0,<3.0` in requirements.txt provides both a minimum version and an upper bound.

8. **No circular import risk.** `image_cleaner.py` only imports standard library (`logging`, `random`, `pathlib`, `typing`) and third-party (`numpy`, `PIL`). No imports from the `src` package.

9. **`img.copy()` is called for RGB images (line 76).** This ensures the image data is loaded into memory before the `with` block closes the file handle. Without this, the `img.save()` on line 83 could fail because the file handle would be closed.

10. **`output_path.parent.mkdir(parents=True, exist_ok=True)` (line 82).** Ensures the output directory exists before writing, even for new paths.

11. **Overwrite-in-place works correctly.** When `output_path is None`, it defaults to `input_path` (line 63). The image data is fully loaded into memory via `Image.open()` + `.copy()` or `.convert()`, so writing back to the same path is safe.

---

## Recommendations

1. **Fix MEDIUM-2 (error handling) before merging.** This is the most impactful issue. A corrupt or locked image file should not crash the entire pipeline. Add a try/except wrapper inside `clean_image()` that logs a warning and returns the original path.

2. **Fix MEDIUM-1 (RGBA handling) before merging.** While unlikely to trigger in the current pipeline, it's a latent correctness bug that's easy to fix now.

3. **Accept LOW issues as-is.** The extension mismatch, double-cleaning, and import style inconsistency are all minor and either match existing codebase patterns or are harmless.

---

## Summary

The implementation is clean, focused, and well-integrated. The core metadata stripping mechanism is correct — Pillow's re-save approach is the standard way to strip EXIF/IPTC/XMP data. The Gaussian noise and JPEG quality randomization add meaningful anti-detection properties.

Two medium-severity issues should be addressed: (1) RGBA alpha compositing should use a white background instead of the default black fill, and (2) `clean_image()` needs error handling to prevent pipeline crashes. Both are straightforward fixes.
