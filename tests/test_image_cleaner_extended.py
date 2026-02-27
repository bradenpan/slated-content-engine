"""Extended QA tests for src/image_cleaner.py — edge cases, metadata deep verification,
idempotency, robustness, and noise behavior.

Second-pass QA to cover gaps not addressed by the original 21-test suite.
"""

import os
import struct
import tempfile
from pathlib import Path

import numpy as np
import piexif
import pytest
from PIL import Image, PngImagePlugin

from conftest import create_jpeg_with_exif as _create_jpeg_with_exif
from src.image_cleaner import _add_gaussian_noise, clean_image


def _create_simple_rgb(path: Path, size=(100, 100), color=(128, 128, 128), fmt="JPEG"):
    """Create a simple RGB image in the specified format."""
    img = Image.new("RGB", size, color)
    img.save(str(path), format=fmt, quality=95 if fmt == "JPEG" else None)
    return path


# ===========================================================================
# 1. Edge Cases — unusual image modes and sizes
# ===========================================================================

class TestEdgeCases:

    def test_very_small_image_1x1(self, tmp_dir):
        """A 1x1 pixel image should clean without error."""
        src = tmp_dir / "tiny.png"
        img = Image.new("RGB", (1, 1), (255, 0, 0))
        img.save(str(src), format="PNG")

        dst = tmp_dir / "tiny_out.jpg"
        result = clean_image(src, dst, add_noise=True)

        assert result == dst
        assert dst.exists()
        with Image.open(dst) as cleaned:
            assert cleaned.size == (1, 1)
            assert cleaned.mode == "RGB"

    def test_large_image_5000x5000(self, tmp_dir):
        """A 5000x5000 image should clean without crashing (memory test)."""
        src = tmp_dir / "large.png"
        # Use a solid color to keep memory lower (no need for random data)
        img = Image.new("RGB", (5000, 5000), (100, 150, 200))
        img.save(str(src), format="PNG")

        dst = tmp_dir / "large_out.jpg"
        result = clean_image(src, dst, add_noise=True, jpeg_quality=85)

        assert result == dst
        assert dst.exists()
        with Image.open(dst) as cleaned:
            assert cleaned.size == (5000, 5000)

    def test_grayscale_image_mode_L(self, tmp_dir):
        """A grayscale (mode 'L') image should convert to RGB correctly."""
        src = tmp_dir / "gray.png"
        img = Image.new("L", (80, 80), 128)
        img.save(str(src), format="PNG")

        dst = tmp_dir / "gray_out.jpg"
        result = clean_image(src, dst, add_noise=False, jpeg_quality=95)

        assert result == dst
        with Image.open(dst) as cleaned:
            assert cleaned.mode == "RGB"
            arr = np.array(cleaned)
            # After grayscale->RGB, all channels should be equal (near 128)
            assert arr.shape[2] == 3
            # R, G, B should be approximately equal
            assert np.allclose(arr[:, :, 0], arr[:, :, 1], atol=2)
            assert np.allclose(arr[:, :, 1], arr[:, :, 2], atol=2)

    def test_palette_image_mode_P(self, tmp_dir):
        """A palette (mode 'P') image should convert to RGB correctly."""
        src = tmp_dir / "palette.png"
        # Create an RGB image then convert to palette mode
        rgb = Image.new("RGB", (80, 80), (200, 100, 50))
        palette_img = rgb.quantize(colors=256)
        palette_img.save(str(src), format="PNG")

        dst = tmp_dir / "palette_out.jpg"
        result = clean_image(src, dst, add_noise=False, jpeg_quality=95)

        assert result == dst
        with Image.open(dst) as cleaned:
            assert cleaned.mode == "RGB"
            arr = np.array(cleaned)
            # Should be close to the original color (200, 100, 50)
            mean_color = arr.mean(axis=(0, 1))
            assert abs(mean_color[0] - 200) < 10
            assert abs(mean_color[1] - 100) < 10
            assert abs(mean_color[2] - 50) < 10

    def test_16bit_image_mode_I(self, tmp_dir):
        """A 16-bit integer image (mode 'I') should convert to RGB via clean_image."""
        src = tmp_dir / "16bit.png"
        # Create a 32-bit integer image (mode 'I') — PNG supports this
        arr = np.full((80, 80), 32768, dtype=np.int32)
        img = Image.fromarray(arr, mode="I")
        img.save(str(src), format="PNG")

        dst = tmp_dir / "16bit_out.jpg"
        result = clean_image(src, dst, add_noise=False, jpeg_quality=95)

        assert result == dst
        with Image.open(dst) as cleaned:
            assert cleaned.mode == "RGB"

    def test_already_clean_jpeg(self, tmp_dir):
        """Re-cleaning a JPEG that has no metadata should not corrupt it."""
        src = tmp_dir / "clean_input.jpg"
        img = Image.new("RGB", (100, 100), (64, 128, 192))
        img.save(str(src), format="JPEG", quality=92)

        # Verify no EXIF before cleaning
        with Image.open(src) as pre:
            assert len(pre.getexif()) == 0

        dst = tmp_dir / "clean_output.jpg"
        result = clean_image(src, dst, add_noise=False, jpeg_quality=92)

        assert result == dst
        with Image.open(dst) as cleaned:
            assert cleaned.format == "JPEG"
            assert cleaned.mode == "RGB"
            assert len(cleaned.getexif()) == 0
            # Image should still be valid and have correct dimensions
            assert cleaned.size == (100, 100)

    def test_la_mode_image(self, tmp_dir):
        """An LA (luminance + alpha) image should convert to RGB correctly."""
        src = tmp_dir / "la_image.png"
        img = Image.new("LA", (60, 60), (200, 128))
        img.save(str(src), format="PNG")

        dst = tmp_dir / "la_out.jpg"
        result = clean_image(src, dst, add_noise=False, jpeg_quality=95)

        assert result == dst
        with Image.open(dst) as cleaned:
            assert cleaned.mode == "RGB"

    def test_pa_mode_image(self, tmp_dir):
        """A PA (palette + alpha) image should convert to RGB via the RGBA path."""
        src = tmp_dir / "pa_image.png"
        # Create RGBA, then convert to PA
        rgba = Image.new("RGBA", (60, 60), (255, 100, 50, 128))
        pa = rgba.quantize(colors=256)
        pa.save(str(src), format="PNG")

        dst = tmp_dir / "pa_out.jpg"
        result = clean_image(src, dst, add_noise=False, jpeg_quality=95)

        assert result == dst
        with Image.open(dst) as cleaned:
            assert cleaned.mode == "RGB"


# ===========================================================================
# 2. Metadata Deep Verification — Pinterest's specific detection fields
# ===========================================================================

class TestMetadataDeepVerification:

    def test_iptc_digital_source_type_stripped(self, tmp_dir):
        """IPTC DigitalSourceType is Pinterest's primary AI detection field.
        Verify it is completely absent from the cleaned output.

        IPTC DigitalSourceType lives in the IPTC-IIM dataset as record 2,
        but it's practically embedded via Photoshop APP13 or XMP. We embed
        it via XMP (the modern path) and verify it's gone after cleaning.
        """
        src = tmp_dir / "iptc_src.jpg"
        img = Image.new("RGB", (100, 100), (128, 128, 128))

        # Embed XMP with DigitalSourceType (this is how DALL-E / Midjourney set it)
        xmp_data = (
            b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            b'<rdf:Description rdf:about=""'
            b' xmlns:Iptc4xmpExt="http://iptc.org/std/Iptc4xmpExt/2008-02-29/">'
            b'<Iptc4xmpExt:DigitalSourceType>'
            b'http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia'
            b'</Iptc4xmpExt:DigitalSourceType>'
            b'</rdf:Description>'
            b'</rdf:RDF>'
            b'</x:xmpmeta>'
            b'<?xpacket end="w"?>'
        )

        # Save JPEG then inject XMP into the raw bytes (APP1 XMP segment)
        img.save(str(src), format="JPEG", quality=95)
        raw = src.read_bytes()

        # Build XMP APP1 marker: FF E1 + length (2 bytes) + namespace + XMP data
        xmp_namespace = b'http://ns.adobe.com/xap/1.0/\x00'
        xmp_payload = xmp_namespace + xmp_data
        xmp_length = len(xmp_payload) + 2  # +2 for the length field itself
        xmp_segment = b'\xff\xe1' + struct.pack('>H', xmp_length) + xmp_payload

        # Insert after SOI marker (FF D8)
        modified = raw[:2] + xmp_segment + raw[2:]
        src.write_bytes(modified)

        # Verify the source actually contains the DigitalSourceType string
        assert b"DigitalSourceType" in src.read_bytes(), "Test setup failure"
        assert b"trainedAlgorithmicMedia" in src.read_bytes(), "Test setup failure"

        # Clean it
        dst = tmp_dir / "iptc_cleaned.jpg"
        clean_image(src, dst, add_noise=False)

        # Verify DigitalSourceType is completely gone
        cleaned_bytes = dst.read_bytes()
        assert b"DigitalSourceType" not in cleaned_bytes, \
            "DigitalSourceType still present in cleaned image"
        assert b"trainedAlgorithmicMedia" not in cleaned_bytes, \
            "trainedAlgorithmicMedia value still present in cleaned image"

    def test_exif_software_dalle_stripped(self, tmp_dir):
        """Pinterest scans EXIF Software tag for 'DALL-E 3', 'Midjourney', etc.
        Verify Software='DALL-E 3' is stripped after cleaning."""
        src = tmp_dir / "dalle_exif.jpg"
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        exif_dict = {
            "0th": {
                piexif.ImageIFD.Software: b"DALL-E 3",
                piexif.ImageIFD.ImageDescription: b"AI generated image",
            },
        }
        exif_bytes = piexif.dump(exif_dict)
        img.save(str(src), format="JPEG", quality=95, exif=exif_bytes)

        # Verify source has the software tag
        with Image.open(src) as original:
            exif = original.getexif()
            assert exif.get(piexif.ImageIFD.Software) is not None, "Test setup failure"

        dst = tmp_dir / "dalle_cleaned.jpg"
        clean_image(src, dst, add_noise=False)

        # Verify Software tag is gone
        with Image.open(dst) as cleaned:
            exif = cleaned.getexif()
            assert piexif.ImageIFD.Software not in exif, \
                f"Software EXIF tag still present: {exif.get(piexif.ImageIFD.Software)}"

        # Also verify raw bytes don't contain "DALL-E"
        cleaned_bytes = dst.read_bytes()
        assert b"DALL-E" not in cleaned_bytes, "DALL-E string found in raw bytes"

    def test_xmp_data_completely_absent(self, tmp_dir):
        """Create image with XMP metadata, clean, verify XMP namespace is absent."""
        src = tmp_dir / "xmp_src.jpg"
        img = Image.new("RGB", (100, 100), (128, 128, 128))

        # Save then inject XMP manually
        img.save(str(src), format="JPEG", quality=95)
        raw = src.read_bytes()

        xmp_data = (
            b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
            b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            b'<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            b'<dc:creator>MidJourney AI</dc:creator>'
            b'</rdf:Description>'
            b'</rdf:RDF>'
            b'</x:xmpmeta>'
            b'<?xpacket end="w"?>'
        )
        xmp_namespace = b'http://ns.adobe.com/xap/1.0/\x00'
        xmp_payload = xmp_namespace + xmp_data
        xmp_length = len(xmp_payload) + 2
        xmp_segment = b'\xff\xe1' + struct.pack('>H', xmp_length) + xmp_payload

        modified = raw[:2] + xmp_segment + raw[2:]
        src.write_bytes(modified)

        assert b"MidJourney AI" in src.read_bytes(), "Test setup failure"

        dst = tmp_dir / "xmp_cleaned.jpg"
        clean_image(src, dst, add_noise=False)

        cleaned_bytes = dst.read_bytes()
        assert b"http://ns.adobe.com/xap" not in cleaned_bytes, \
            "XMP namespace still present in cleaned image"
        assert b"MidJourney" not in cleaned_bytes, \
            "MidJourney string still present in cleaned image"

    def test_icc_profile_stripped(self, tmp_dir):
        """ICC profiles are metadata that can fingerprint the generating tool.
        Verify they are stripped by clean_image."""
        src = tmp_dir / "icc_src.jpg"
        img = Image.new("RGB", (100, 100), (128, 128, 128))

        # Create a minimal ICC profile (sRGB-like header)
        # A real ICC profile is complex; we use Pillow's built-in sRGB profile
        from PIL import ImageCms
        srgb_profile = ImageCms.createProfile("sRGB")
        icc_data = ImageCms.ImageCmsProfile(srgb_profile).tobytes()

        img.save(str(src), format="JPEG", quality=95, icc_profile=icc_data)

        # Verify source has ICC profile
        with Image.open(src) as original:
            assert "icc_profile" in original.info, "Test setup failure: no ICC profile"

        dst = tmp_dir / "icc_cleaned.jpg"
        clean_image(src, dst, add_noise=False)

        # Verify ICC profile is gone
        with Image.open(dst) as cleaned:
            assert "icc_profile" not in cleaned.info, \
                "ICC profile still present in cleaned image"


# ===========================================================================
# 3. Idempotency — double-clean and pipeline-pattern simulation
# ===========================================================================

class TestIdempotency:

    def test_double_clean_produces_valid_output(self, tmp_dir):
        """Clean an image twice. The second clean should still produce a valid,
        metadata-free JPEG. This matters because hero images may be cleaned
        at generation time AND again at deployment time."""
        src = _create_jpeg_with_exif(tmp_dir / "double_src.jpg")

        # First clean
        intermediate = tmp_dir / "double_first.jpg"
        clean_image(src, intermediate, add_noise=True, jpeg_quality=92)

        # Second clean
        final = tmp_dir / "double_second.jpg"
        result = clean_image(intermediate, final, add_noise=True, jpeg_quality=90)

        assert result == final
        assert final.exists()

        with Image.open(final) as cleaned:
            assert cleaned.format == "JPEG"
            assert cleaned.mode == "RGB"
            assert len(cleaned.getexif()) == 0

        # Verify no metadata in raw bytes
        raw = final.read_bytes()
        assert b"Exif" not in raw
        assert b"http://ns.adobe.com/xap" not in raw
        assert b"Photoshop 3.0" not in raw

    def test_double_clean_no_noise_preserves_dimensions(self, tmp_dir):
        """Double-clean without noise should preserve image dimensions exactly."""
        src = tmp_dir / "dim_src.png"
        img = Image.new("RGB", (200, 300), (100, 150, 200))
        img.save(str(src), format="PNG")

        first = tmp_dir / "dim_first.jpg"
        clean_image(src, first, add_noise=False, jpeg_quality=95)

        second = tmp_dir / "dim_second.jpg"
        clean_image(first, second, add_noise=False, jpeg_quality=95)

        with Image.open(second) as cleaned:
            assert cleaned.size == (200, 300)

    def test_optimize_then_clean_pattern(self, tmp_dir):
        """Simulate what _optimize_image does: open PNG, re-save as JPEG,
        rename back to .png extension. Then clean that file.

        This is the exact pattern in pin_assembler.py lines 576-589:
        the file at .png path may actually contain JPEG data."""
        src = tmp_dir / "optimize_sim.png"
        img = Image.new("RGB", (200, 200), (100, 150, 200))
        img.save(str(src), format="PNG")

        # Simulate _optimize_image: save as JPEG, rename to .png
        jpeg_path = src.with_suffix(".jpg")
        with Image.open(src) as im:
            if im.mode == "RGBA":
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[3])
                bg.save(str(jpeg_path), "JPEG", quality=88, optimize=True)
            else:
                im.save(str(jpeg_path), "JPEG", quality=88, optimize=True)

        src.unlink()
        jpeg_path.rename(src)  # Now .png file contains JPEG data

        # Clean the mismatched-extension file (this is what happens in production)
        result = clean_image(src, add_noise=True)

        assert result == src
        assert src.exists()

        # File should be a valid image
        with Image.open(src) as cleaned:
            assert cleaned.mode == "RGB"
            assert len(cleaned.getexif()) == 0


# ===========================================================================
# 4. Robustness — corrupt files, read-only paths, zero-byte files
# ===========================================================================

class TestRobustness:

    def test_corrupt_truncated_file(self, tmp_dir):
        """A corrupt/truncated image file should return the original path
        gracefully (the function catches exceptions)."""
        src = tmp_dir / "corrupt.jpg"
        # Write a JPEG SOI marker followed by garbage
        src.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 20 + b'garbage data')

        result = clean_image(src)
        # Should return input_path on failure (graceful fallback)
        assert result == src

    def test_zero_byte_file(self, tmp_dir):
        """A zero-byte file should return the original path gracefully."""
        src = tmp_dir / "empty.jpg"
        src.write_bytes(b"")

        result = clean_image(src)
        assert result == src

    def test_non_image_file(self, tmp_dir):
        """A text file disguised as an image should return original path."""
        src = tmp_dir / "fake.jpg"
        src.write_text("This is not an image file", encoding="utf-8")

        result = clean_image(src)
        assert result == src

    def test_output_to_nonexistent_deep_directory(self, tmp_dir):
        """Output path in a deeply nested nonexistent directory should
        succeed (clean_image creates parent dirs via mkdir(parents=True))."""
        src = tmp_dir / "nested_src.png"
        img = Image.new("RGB", (50, 50), (128, 128, 128))
        img.save(str(src), format="PNG")

        dst = tmp_dir / "a" / "b" / "c" / "d" / "nested_out.jpg"
        result = clean_image(src, dst, add_noise=False)

        assert result == dst
        assert dst.exists()

    def test_string_path_input(self, tmp_dir):
        """clean_image should accept string paths (not just Path objects),
        since callers may pass str."""
        src = tmp_dir / "str_input.png"
        img = Image.new("RGB", (50, 50), (128, 128, 128))
        img.save(str(src), format="PNG")

        dst = tmp_dir / "str_output.jpg"
        # Pass strings, not Path objects
        result = clean_image(str(src), str(dst), add_noise=False)

        assert Path(result) == dst
        assert dst.exists()


# ===========================================================================
# 5. Noise Verification — non-determinism and sigma=0
# ===========================================================================

class TestNoiseVerification:

    def test_noise_is_nondeterministic(self, tmp_dir):
        """Clean the same image twice with noise. The noise pattern should
        be different each time (not deterministic). This prevents
        fingerprinting via noise pattern matching."""
        src = tmp_dir / "determ_src.bmp"
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        img.save(str(src), format="BMP")

        dst1 = tmp_dir / "determ_out1.jpg"
        dst2 = tmp_dir / "determ_out2.jpg"

        clean_image(src, dst1, add_noise=True, jpeg_quality=100, noise_sigma=3.0)
        clean_image(src, dst2, add_noise=True, jpeg_quality=100, noise_sigma=3.0)

        with Image.open(dst1) as img1, Image.open(dst2) as img2:
            arr1 = np.array(img1, dtype=np.float32)
            arr2 = np.array(img2, dtype=np.float32)
            diff = np.abs(arr1 - arr2)
            # The two noise applications should produce different pixel values
            # With sigma=3.0 on a 100x100x3 image, max diff should be > 0
            assert diff.max() > 0, \
                "Two noise applications produced identical results — noise may be deterministic"

    def test_noise_sigma_zero_produces_minimal_change(self, tmp_dir):
        """With sigma=0, noise should produce no visible change (all noise values are 0)."""
        src = tmp_dir / "sigma0_src.bmp"
        img = Image.new("RGB", (50, 50), (128, 128, 128))
        img.save(str(src), format="BMP")

        dst = tmp_dir / "sigma0_out.jpg"
        clean_image(src, dst, add_noise=True, noise_sigma=0.0, jpeg_quality=100)

        with Image.open(dst) as cleaned:
            arr = np.array(cleaned, dtype=np.float32)
            # With sigma=0, noise is all zeros; pixel values should be very close to 128
            # (only JPEG compression artifacts)
            std = float(np.std(arr))
            assert std < 3.0, (
                f"sigma=0 should produce near-zero change, got std={std:.2f}"
            )

    def test_noise_does_not_produce_uniform_patterns(self, tmp_dir):
        """Noise should not produce visible banding or uniform patterns.
        Verify that per-pixel noise varies across different regions."""
        src = tmp_dir / "pattern_src.bmp"
        img = Image.new("RGB", (200, 200), (128, 128, 128))
        img.save(str(src), format="BMP")

        dst = tmp_dir / "pattern_out.jpg"
        clean_image(src, dst, add_noise=True, noise_sigma=2.0, jpeg_quality=100)

        with Image.open(dst) as cleaned:
            arr = np.array(cleaned, dtype=np.float32)
            # Check that different quadrants have different noise patterns
            q1 = arr[:100, :100, :]
            q2 = arr[:100, 100:, :]
            q3 = arr[100:, :100, :]
            q4 = arr[100:, 100:, :]
            # The mean of each quadrant should differ slightly (noise is random)
            means = [q1.mean(), q2.mean(), q3.mean(), q4.mean()]
            # Not all quadrant means should be exactly equal
            assert len(set(round(m, 2) for m in means)) > 1, (
                f"All quadrants have identical mean — noise may be uniform: {means}"
            )


# ===========================================================================
# 6. Internal function _add_gaussian_noise direct tests
# ===========================================================================

class TestAddGaussianNoiseDirectly:

    def test_noise_clamps_to_valid_range(self):
        """Noise applied near pixel boundaries (0 or 255) should clamp to [0, 255]."""
        # White image — noise can only go down or stay
        white = Image.new("RGB", (100, 100), (255, 255, 255))
        noisy = _add_gaussian_noise(white, sigma=5.0)
        arr = np.array(noisy)
        assert arr.max() <= 255, "Pixel values exceed 255"
        assert arr.min() >= 0, "Pixel values below 0"

        # Black image — noise can only go up or stay
        black = Image.new("RGB", (100, 100), (0, 0, 0))
        noisy_b = _add_gaussian_noise(black, sigma=5.0)
        arr_b = np.array(noisy_b)
        assert arr_b.max() <= 255
        assert arr_b.min() >= 0

    def test_noise_preserves_mode(self):
        """_add_gaussian_noise should preserve the image mode."""
        img = Image.new("RGB", (50, 50), (128, 128, 128))
        noisy = _add_gaussian_noise(img, sigma=1.5)
        assert noisy.mode == "RGB"

    def test_noise_preserves_size(self):
        """_add_gaussian_noise should preserve the image dimensions."""
        img = Image.new("RGB", (73, 41), (128, 128, 128))
        noisy = _add_gaussian_noise(img, sigma=1.5)
        assert noisy.size == (73, 41)


# ===========================================================================
# 7. Integration-like tests — verifying behavior that matters for callers
# ===========================================================================

class TestIntegrationBehavior:

    def test_return_value_is_output_path(self, tmp_dir):
        """clean_image must return the output_path, not input_path, on success.
        pin_assembler.py and generate_pin_content.py depend on this."""
        src = tmp_dir / "ret_src.png"
        img = Image.new("RGB", (50, 50), (128, 128, 128))
        img.save(str(src), format="PNG")

        dst = tmp_dir / "ret_dst.jpg"
        result = clean_image(src, dst, add_noise=False)
        assert result == dst, f"Expected {dst}, got {result}"

    def test_return_value_is_input_on_failure(self, tmp_dir):
        """On failure, clean_image must return input_path so the pipeline
        can continue with the original file."""
        fake = tmp_dir / "nonexistent.jpg"
        result = clean_image(fake)
        assert result == fake

    def test_overwrite_inplace_returns_same_path(self, tmp_dir):
        """When output_path is None, clean_image overwrites in place and
        returns input_path. This is how pin_assembler.py calls it:
        clean_image(output_path) with no second arg."""
        src = tmp_dir / "inplace.png"
        img = Image.new("RGB", (50, 50), (128, 128, 128))
        img.save(str(src), format="PNG")

        result = clean_image(src)
        assert result == src
        assert src.exists()

    def test_output_always_jpeg_format(self, tmp_dir):
        """clean_image always saves as JPEG (format='JPEG'), regardless
        of input format. This is important for Pinterest optimization."""
        for fmt, ext in [("PNG", ".png"), ("BMP", ".bmp")]:
            src = tmp_dir / f"fmt_test{ext}"
            img = Image.new("RGB", (50, 50), (128, 128, 128))
            img.save(str(src), format=fmt)

            dst = tmp_dir / f"fmt_out_{ext}.jpg"
            clean_image(src, dst, add_noise=False)

            with Image.open(dst) as cleaned:
                assert cleaned.format == "JPEG", \
                    f"Input format {fmt} should still produce JPEG output"

    def test_jpeg_quality_range(self, tmp_dir):
        """When jpeg_quality is None, random quality should be in [89, 94]."""
        # We can't directly observe the quality, but we can verify that
        # the function doesn't crash and produces varying file sizes
        src = tmp_dir / "qrange_src.bmp"
        rng = np.random.RandomState(99)
        arr = rng.randint(0, 256, (200, 200, 3), dtype=np.uint8)
        img = Image.fromarray(arr, mode="RGB")
        img.save(str(src), format="BMP")

        sizes = set()
        for i in range(20):
            dst = tmp_dir / f"qrange_{i}.jpg"
            clean_image(src, dst, add_noise=False, jpeg_quality=None)
            sizes.add(dst.stat().st_size)

        # With random quality in [89, 94], we should see multiple distinct sizes
        assert len(sizes) >= 2, \
            f"Expected varying sizes from random quality, got {len(sizes)} distinct"
