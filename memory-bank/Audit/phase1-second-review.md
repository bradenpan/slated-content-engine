# Phase 1 Second-Pass Code Review: Image Metadata Stripping

**Reviewer:** second-pass reviewer agent
**Date:** 2026-02-26
**Prior review:** `memory-bank/Audit/phase1-code-review.md`
**Verdict:** PASS

---

## Summary

The first reviewer identified two medium-severity issues (RGBA-to-white compositing and error handling in `clean_image()`) and both have been fixed. This second-pass review went deeper into byte-level correctness, integration path tracing, edge cases, and test coverage. No critical or medium issues were found. The implementation is correct and well-integrated.

---

## Files Reviewed

| File | Focus |
|------|-------|
| `src/image_cleaner.py` | Core module -- byte flow, metadata stripping mechanism, noise, error handling |
| `src/generate_pin_content.py` | Integration at line 29 (import) and line 748 (`_source_ai_image`) |
| `src/pin_assembler.py` | Integration at lines 508-509 (`render_pin`) and 717-718 (`render_batch`) |
| `src/blog_deployer.py` | Integration at lines 507-508 (`deploy_approved_posts`) and 623-624 (`_deploy_blog_posts`) |
| `src/publish_content_queue.py` | Upstream cleanliness -- verifying images uploaded to GCS/Drive are already cleaned |
| `src/post_pins.py` | Final upload path -- verifying no uncleaned images can reach Pinterest |
| `src/apis/gcs_api.py` | Upload mechanism -- confirms it reads bytes from disk (no metadata re-injection) |
| `src/apis/drive_api.py` | Upload mechanism -- same confirmation |
| `requirements.txt` | numpy dependency |
| `tests/test_image_cleaner.py` | Test quality and coverage |

---

## Issues Found

### LOW-1: `shutil.copy2` preserves filesystem-level timestamps (not a real problem)

**File:** `src/generate_pin_content.py:183`
**Severity:** Low (informational)

```python
shutil.copy2(image_path, slug_hero)
```

`shutil.copy2` copies the file content AND filesystem metadata (modification time, permissions). The embedded image metadata is already stripped (the source file was cleaned at line 748), so the copy is clean from an image-metadata perspective. However, `copy2` preserves the original file's modification timestamp, which means the slug-named hero copy will have the same mtime as the original. This is not a detection vector -- Pinterest does not inspect filesystem timestamps -- but using `shutil.copy` (without the `2`) would be slightly more correct semantically since we do not need to preserve timestamps.

**Recommendation:** Accept as-is. No functional impact. Could be changed to `shutil.copy` in a future cleanup pass.

### LOW-2: `clean_image` always outputs JPEG format regardless of input extension

**File:** `src/image_cleaner.py:88`
**Severity:** Low (already noted by first reviewer as LOW-1)

Confirmed the first reviewer's finding. `clean_image` writes JPEG bytes to whatever path is given, even if the path has a `.png` extension. This is intentional and matches the existing pattern in `_optimize_image()` (line 586-589 in `pin_assembler.py`). Both `gcs_api.py` (line 132-142) and `drive_api.py` (line 188-197) detect MIME type from magic bytes rather than file extension, so uploads work correctly despite the mismatch.

**Recommendation:** Accept as-is. Already documented by first reviewer.

### LOW-3: Double noise application on hero images

**File:** `src/generate_pin_content.py:748` + `src/blog_deployer.py:508,624`
**Severity:** Low (already noted by first reviewer as LOW-2)

Confirmed the first reviewer's finding. Hero images are cleaned in `_source_ai_image()` and then again in `blog_deployer.py`. The second cleaning adds another round of Gaussian noise (sigma=1.5) and another JPEG recompression. With sigma=1.5, two rounds produce an effective sigma of sqrt(1.5^2 + 1.5^2) = ~2.12, which is still imperceptible at Pinterest display sizes. The second recompression at quality 89-94 introduces minimal additional JPEG artifacting on an already-compressed image.

**Recommendation:** Accept as-is. The redundancy is a safety net. Quality impact is negligible.

---

## Things Confirmed Correct

### 1. Byte-flow analysis: metadata cannot leak through

Traced the complete path for each code branch in `clean_image()`:

**RGB path (most common for AI-generated images):**
1. `Image.open(input_path)` loads pixel data; `.info` dict may contain `{'exif': bytes}`
2. `img.copy()` copies pixel data and `.info` dict into a new object
3. Context manager closes the file handle (safe because `.copy()` loaded all data)
4. `_add_gaussian_noise()` calls `Image.fromarray()` which creates a brand-new Image with empty `.info` -- even if the copy carried residual metadata, it is discarded here
5. `img.save(output_path, format="JPEG", quality=jpeg_quality)` writes a clean JPEG; Pillow's JPEG save plugin does NOT auto-serialize `img.info['exif']` -- EXIF is only written when the `exif=` keyword argument is explicitly passed

**RGBA/LA/PA path:**
1. `Image.new("RGB", ...)` creates a completely new image with empty `.info`
2. `background.paste(img, mask=...)` copies pixels only, not metadata
3. The resulting `img` (reassigned to `background`) has zero metadata

**Other mode path (grayscale, P-mode, etc.):**
1. `img.convert("RGB")` creates a new Image; `.convert()` may copy some `.info` entries
2. However, the noise step (if enabled) runs `Image.fromarray()` which discards `.info`
3. Even without noise, Pillow's JPEG save does not auto-serialize `.info['exif']`

**Conclusion:** No metadata can leak through any code path. This is confirmed by the Pillow project's documented behavior: EXIF data is not preserved during JPEG save operations unless explicitly passed via the `exif=` parameter.

### 2. Overwrite-in-place is safe

When `output_path == input_path` (the default), the sequence is:
1. `Image.open(input_path)` + `.copy()` / `.convert()` loads all pixel data into memory
2. The `with` block closes the file handle
3. `img.save(output_path, ...)` writes to the same path

The data is fully in memory before the write begins. If the write fails (disk full, permissions), the original file may be corrupted (partially written). However, this is caught by the `try/except` at line 99, which logs a warning and returns `input_path`. The caller (pipeline) continues without crashing. In the worst case, the image file is corrupted and a later step fails on that specific pin, but the pipeline does not halt entirely.

For production robustness, a write-to-temp-then-rename pattern would be safer, but this is a low-probability edge case and the error handling is adequate.

### 3. Noise sigma of 1.5 is appropriate

Sigma 1.5 on a 0-255 pixel range means ~68% of noise values fall within +/- 1.5 of zero, and ~99.7% within +/- 4.5. At Pinterest's typical display sizes (236px wide in feed, up to 600px in closeup), noise at this level is imperceptible. Meanwhile, it meaningfully alters the frequency-domain fingerprint that automated detectors use, because the noise is random per-pixel and per-image (no fixed seed).

### 4. JPEG quality randomization works correctly

`random.randint(89, 94)` is inclusive on both ends (6 possible values). The randomization happens per call, so different images get different quality levels. This varies the compression fingerprint without visible quality loss. Confirmed by the `TestJpegQuality` tests.

### 5. All image paths to Pinterest are covered

Traced every path from image creation to Pinterest upload:

**Path A: Pin images (rendered composites)**
1. `pin_assembler.render_pin()` renders HTML -> PNG via Puppeteer (line 500)
2. `_optimize_image()` may convert to JPEG (line 505)
3. `clean_image(output_path)` strips metadata + adds noise (line 509)
4. Image saved as `{pin_id}.png` in `PIN_OUTPUT_DIR`
5. `publish_content_queue.py` uploads to GCS/Drive (reads from disk -- already clean)
6. `post_pins.py` reads from schedule; uses either hosted URL or reads from disk and base64-encodes (line 179-196). Either way, the bytes are already clean.

**Path B: Pin images (batch rendered)**
1. `pin_assembler.render_batch()` renders all pins via Puppeteer (line 677)
2. `_optimize_image(output_path)` runs per image (line 716)
3. `clean_image(output_path)` runs per image (line 718)
4. Same downstream as Path A

**Path C: Hero images (AI-generated)**
1. `_source_ai_image()` generates image via API (line 739-745)
2. `clean_image(generated_path)` strips metadata (line 748)
3. Hero image used in pin assembly (goes through Path A or B, cleaned again)
4. Slug-named copy created via `shutil.copy2` at line 183 (already-clean bytes)
5. Blog deployer cleans hero again at deploy time (line 508 or 624) -- redundant but safe

**Path D: Blog hero images (deployed to goslated.com)**
1. `blog_deployer._deploy_blog_posts()` finds hero image (line 606-617)
2. `clean_image(hero_image_path)` called at line 624
3. Image committed to GitHub repo via GitHubAPI

**Path E: Blog hero images (uploaded for Sheet preview)**
1. `publish_content_queue.py` calls `gcs.upload_blog_hero_images()` (line 134)
2. GCS API finds `{slug}-hero.{ext}` files (line 266-270 in gcs_api.py)
3. These files were already cleaned in Path C step 2

**Conclusion:** No uncleaned image can reach Pinterest, GCS, Drive, or the goslated.com repo. Every path has at least one `clean_image()` call before the image leaves the local filesystem.

### 6. Integration guards are sufficient

**`_source_ai_image()` (line 748):** `clean_image(generated_path)` is called after `image_gen_api.generate()` returns. The API writes the file and returns the path. If generation fails, the exception propagates before reaching `clean_image`, so it is never called on a nonexistent file. If it were somehow called on a missing file, the `try/except` in `clean_image` would catch `FileNotFoundError` and return the input path. Safe.

**`render_batch()` (lines 715-721):** `clean_image(output_path)` is inside `if output_path.exists():` guard. If the render failed (file doesn't exist), the branch takes `results.append(None)` instead. No risk of calling `clean_image` on None. Safe.

**`blog_deployer._deploy_blog_posts()` (lines 622-624):** `clean_image(hero_image_path)` is inside `if hero_image_path:` guard. The `hero_image_path` is set from a loop that checks `candidate.exists()` (line 612-613), so it is always a real Path object pointing to an existing file, or None. Could `hero_image_path` be the string `"None"` or empty string? No -- it is set either from `candidate` (a Path object) or remains `None` (line 606). Safe.

**`blog_deployer.deploy_approved_posts()` (lines 506-508):** Same pattern -- `if hero_image_path:` guard, and `hero_image_path` is set from a `candidate.exists()` check or remains None. Safe.

### 7. First reviewer's fixes are correctly applied

- **RGBA compositing (MEDIUM-1):** Verified at lines 74-81. The code now creates a white background, pastes with alpha mask, and properly handles RGBA, LA, and PA modes. The `else: img = img.copy()` for RGB mode ensures data is loaded before the `with` block closes.

- **Error handling (MEDIUM-2):** Verified at lines 99-101. The entire function body is wrapped in `try/except Exception`, logging a warning and returning `input_path` on failure. This matches the pattern used by `_optimize_image()` and prevents pipeline crashes.

### 8. `publish_content_queue.py` does not re-introduce metadata

`publish_content_queue.py` reads image files from disk and uploads them to GCS/Drive. Both upload APIs (`gcs_api.upload_image` and `drive_api.upload_image`) use `upload_from_filename` / `MediaFileUpload` which read raw bytes from the file. They do not process or modify the image in any way. Since the on-disk files are already cleaned, the uploaded versions are also clean.

### 9. `post_pins.py` does not re-introduce metadata

`post_pins.py` either:
- Uses a hosted URL (`image_url` from GCS/Drive) -- already clean on the server
- Reads from disk and base64-encodes (lines 191-192) -- raw bytes, already clean

Neither path adds metadata. Clean.

---

## Test Coverage Assessment

### Tests present (21 tests across 9 test classes):

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestMetadataStripping` | 5 | EXIF removal, .info dict, raw bytes (Exif, XMP, IPTC) |
| `TestPngToJpeg` | 2 | Valid JPEG output, PNG text chunks not in output |
| `TestRgbaConversion` | 2 | Output is RGB, transparent areas composited on white |
| `TestNoiseAddition` | 3 | Noise applied, no noise preserves uniformity, noise is subtle |
| `TestJpegQuality` | 2 | Random quality varies sizes, explicit quality respected |
| `TestOverwriteInPlace` | 2 | File overwritten, in-place result has no EXIF |
| `TestExplicitOutputPath` | 2 | Both files exist, original untouched |
| `TestErrorHandling` | 1 | Nonexistent path returns input_path |
| `TestPillowMetadataBehavior` | 2 | Core assumption verification (resave strips EXIF and .info) |

### Strengths:
- Raw byte-level checks (`b"Exif" not in raw`) catch metadata that higher-level APIs might miss
- The `TestPillowMetadataBehavior` class explicitly validates the core assumption the entire module depends on
- Noise tests verify both presence and subtlety (bounded max deviation)
- RGBA compositing test verifies white background (catches the exact bug the first reviewer found)

### Coverage gaps (low priority):

1. **No test for corrupt/truncated image graceful handling.** `TestErrorHandling` only tests a nonexistent file. A corrupt file (e.g., truncated JPEG, zero-byte file) would exercise a different code path in Pillow (`Image.open()` might raise `UnidentifiedImageError` or `SyntaxError`). The `try/except Exception` at line 99 should catch these, but there is no test verifying it.

2. **No test for palette-mode (P) images.** The code handles `"PA"` mode at line 74 but plain `"P"` mode (common in GIFs and some PNGs) would hit the `img.convert("RGB")` branch at line 79. This works correctly, but is untested.

3. **No test for the `_add_gaussian_noise` function stripping `.info`.** While the noise function creates a new image via `Image.fromarray()` (which drops `.info`), no test explicitly verifies that passing a metadata-laden image through noise produces a metadata-free result.

4. **No integration-level test** verifying that `clean_image` + `Image.open` round-trip produces zero metadata in `.info` (as opposed to just zero EXIF in `.getexif()`). The `test_info_dict_has_no_metadata_keys` test checks this but only for a subset of keys (`exif`, `icc_profile`, `xmp`, `photoshop`).

5. **No test for `piexif` not being installed.** The test file imports `piexif` at the top level (line 8). If `piexif` were removed from the test environment, all metadata-creation helpers would fail. This is fine (it is a test dependency), but worth noting that the production code itself does not depend on `piexif`.

6. **No test for DigitalSourceType specifically.** The docstring mentions Pinterest scans for `DigitalSourceType`, but no test creates an image with IPTC `DigitalSourceType` metadata and verifies it is stripped. The existing raw-byte tests would catch it if present, but no test explicitly creates this specific field.

### Assessment: Test coverage is solid for a first implementation. The 21 tests cover the critical paths well. The gaps listed above are all low-priority and could be added in a future pass.

---

## Recommendations

1. **No blocking issues.** The code is ready for merge.

2. **Consider adding a corrupt-image test** in a future pass to verify the `try/except` handles `Pillow.UnidentifiedImageError` gracefully.

3. **Consider a write-to-temp-then-rename pattern** for the overwrite-in-place case in a future hardening pass. This would prevent partial writes from corrupting the file if disk space runs out mid-write.

4. **The `piexif` package used in tests is not in `requirements.txt`.** If there is a separate test requirements file (e.g., `requirements-test.txt`), `piexif` should be listed there. If not, it should be documented as a test dependency somewhere.

---

## Verdict: PASS

The Phase 1 metadata stripping implementation is correct, well-integrated, and adequately tested. The first reviewer's two fixes (RGBA compositing and error handling) have been properly applied. No critical or medium issues remain. The three low-severity observations are all informational and do not require action before merging.
