"""Unit tests for src/image_cleaner.py — metadata stripping and post-processing."""

import struct
import tempfile
from pathlib import Path

import numpy as np
import piexif
import pytest
from PIL import Image

from src.image_cleaner import clean_image


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test images."""
    return tmp_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_jpeg_with_exif(path: Path, size=(100, 100), color=(128, 128, 128)):
    """Create a JPEG file with EXIF metadata baked in."""
    img = Image.new("RGB", size, color)
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Software: b"Adobe Photoshop",
            piexif.ImageIFD.Make: b"TestCamera",
            piexif.ImageIFD.ImageDescription: b"Test image with metadata",
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: b"2025:01:01 12:00:00",
            piexif.ExifIFD.UserComment: b"secret metadata",
        },
    }
    exif_bytes = piexif.dump(exif_dict)
    img.save(str(path), format="JPEG", quality=95, exif=exif_bytes)
    return path


def _create_png_with_text(path: Path, size=(80, 80), color=(200, 100, 50)):
    """Create a PNG file with text-chunk metadata."""
    from PIL import PngImagePlugin

    img = Image.new("RGB", size, color)
    info = PngImagePlugin.PngInfo()
    info.add_text("Software", "AI Generator v3")
    info.add_text("Comment", "this is metadata")
    img.save(str(path), format="PNG", pnginfo=info)
    return path


def _create_rgba_image(path: Path, size=(60, 60)):
    """Create a PNG with RGBA mode (semi-transparent red on transparent bg)."""
    img = Image.new("RGBA", size, (255, 0, 0, 128))
    img.save(str(path), format="PNG")
    return path


def _create_solid_image(path: Path, size=(50, 50), color=(128, 128, 128)):
    """Create a solid-color JPEG — every pixel identical."""
    img = Image.new("RGB", size, color)
    # Save as BMP to avoid JPEG lossy compression changing pixel values
    img.save(str(path), format="BMP")
    return path


def _create_complex_image(path: Path, size=(400, 400)):
    """Create a photo-like image with gradients and noise for quality tests.

    Solid-color images compress identically at all quality levels.
    This image has enough entropy to show quality differences.
    """
    rng = np.random.RandomState(42)
    arr = rng.randint(0, 256, (*size, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    img.save(str(path), format="BMP")
    return path


# ---------------------------------------------------------------------------
# 1. Metadata stripping (CRITICAL)
# ---------------------------------------------------------------------------

class TestMetadataStripping:

    def test_exif_data_removed(self, tmp_dir):
        """Cleaned JPEG should have no EXIF data."""
        src = _create_jpeg_with_exif(tmp_dir / "exif_input.jpg")
        dst = tmp_dir / "exif_output.jpg"
        clean_image(src, dst, add_noise=False)

        with Image.open(dst) as cleaned:
            exif = cleaned.getexif()
            assert len(exif) == 0, f"EXIF tags still present: {dict(exif)}"

    def test_info_dict_has_no_metadata_keys(self, tmp_dir):
        """Cleaned image .info should not contain exif, icc_profile, etc."""
        src = _create_jpeg_with_exif(tmp_dir / "meta_input.jpg")
        dst = tmp_dir / "meta_output.jpg"
        clean_image(src, dst, add_noise=False)

        with Image.open(dst) as cleaned:
            metadata_keys = {"exif", "icc_profile", "xmp", "photoshop"}
            found = metadata_keys & set(cleaned.info.keys())
            assert not found, f"Metadata keys still present in .info: {found}"

    def test_no_exif_bytes_in_file(self, tmp_dir):
        """Raw file bytes should not contain an Exif APP1 marker."""
        src = _create_jpeg_with_exif(tmp_dir / "raw_input.jpg")
        dst = tmp_dir / "raw_output.jpg"
        clean_image(src, dst, add_noise=False)

        raw = dst.read_bytes()
        # JPEG APP1 marker for Exif: FF E1 followed by "Exif\x00\x00"
        assert b"Exif" not in raw, "Exif signature found in raw file bytes"

    def test_no_xmp_in_file(self, tmp_dir):
        """Raw file bytes should not contain XMP data."""
        src = _create_jpeg_with_exif(tmp_dir / "xmp_input.jpg")
        dst = tmp_dir / "xmp_output.jpg"
        clean_image(src, dst, add_noise=False)

        raw = dst.read_bytes()
        assert b"http://ns.adobe.com/xap" not in raw, "XMP namespace found in raw bytes"

    def test_no_iptc_in_file(self, tmp_dir):
        """Raw file bytes should not contain IPTC marker."""
        src = _create_jpeg_with_exif(tmp_dir / "iptc_input.jpg")
        dst = tmp_dir / "iptc_output.jpg"
        clean_image(src, dst, add_noise=False)

        raw = dst.read_bytes()
        # IPTC lives in APP13 (0xFFED) with "Photoshop 3.0" header
        assert b"Photoshop 3.0" not in raw, "IPTC/Photoshop marker found in raw bytes"


# ---------------------------------------------------------------------------
# 2. PNG to JPEG conversion
# ---------------------------------------------------------------------------

class TestPngToJpeg:

    def test_png_converted_to_valid_jpeg(self, tmp_dir):
        """A PNG input should produce a valid JPEG output."""
        src = _create_png_with_text(tmp_dir / "input.png")
        dst = tmp_dir / "output.jpg"
        clean_image(src, dst, add_noise=False)

        with Image.open(dst) as cleaned:
            assert cleaned.format == "JPEG", f"Expected JPEG, got {cleaned.format}"

    def test_png_text_chunks_not_in_output(self, tmp_dir):
        """PNG text chunks (Software, Comment) must not leak into output."""
        src = _create_png_with_text(tmp_dir / "text_input.png")
        dst = tmp_dir / "text_output.jpg"
        clean_image(src, dst, add_noise=False)

        raw = dst.read_bytes()
        assert b"AI Generator" not in raw
        assert b"this is metadata" not in raw


# ---------------------------------------------------------------------------
# 3. RGBA to RGB conversion
# ---------------------------------------------------------------------------

class TestRgbaConversion:

    def test_output_is_rgb_mode(self, tmp_dir):
        """RGBA input should be converted to RGB."""
        src = _create_rgba_image(tmp_dir / "rgba_input.png")
        dst = tmp_dir / "rgba_output.jpg"
        clean_image(src, dst, add_noise=False)

        with Image.open(dst) as cleaned:
            assert cleaned.mode == "RGB", f"Expected RGB, got {cleaned.mode}"

    def test_transparent_areas_composited_on_white(self, tmp_dir):
        """When converting RGBA with alpha, transparent areas should be
        composited onto a white background."""
        # Create fully transparent image
        img = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
        src = tmp_dir / "transparent.png"
        img.save(str(src), format="PNG")
        dst = tmp_dir / "transparent_output.jpg"
        clean_image(src, dst, add_noise=False, jpeg_quality=95)

        with Image.open(dst) as cleaned:
            px = np.array(cleaned)
            # Transparent areas should composite on white (255, 255, 255)
            # All pixels should be near 255
            assert px.mean() > 245, (
                f"Expected near-white pixels from transparent RGBA, got mean={px.mean():.1f}"
            )


# ---------------------------------------------------------------------------
# 4. Noise addition
# ---------------------------------------------------------------------------

class TestNoiseAddition:

    def test_noise_applied_alters_pixels(self, tmp_dir):
        """With add_noise=True, pixel values should NOT all be identical."""
        src = _create_solid_image(tmp_dir / "solid.bmp", color=(128, 128, 128))
        dst = tmp_dir / "noisy.jpg"
        clean_image(src, dst, add_noise=True, jpeg_quality=100)

        with Image.open(dst) as cleaned:
            arr = np.array(cleaned)
            unique_values = np.unique(arr)
            assert len(unique_values) > 1, "Noise was not applied — all pixels identical"

    def test_no_noise_preserves_uniformity(self, tmp_dir):
        """With add_noise=False, a solid-color image should remain largely uniform."""
        src = _create_solid_image(tmp_dir / "solid2.bmp", color=(128, 128, 128))
        dst = tmp_dir / "clean.jpg"
        clean_image(src, dst, add_noise=False, jpeg_quality=100)

        with Image.open(dst) as cleaned:
            arr = np.array(cleaned)
            # JPEG compression at q=100 might introduce minor artifacts
            # but std should be very low compared to noisy version
            std = float(np.std(arr))
            assert std < 3.0, f"Unexpected variation without noise: std={std:.2f}"

    def test_noise_is_subtle(self, tmp_dir):
        """Noise should be subtle — max pixel deviation within reasonable bounds."""
        src = _create_solid_image(tmp_dir / "solid3.bmp", color=(128, 128, 128))
        dst = tmp_dir / "subtle_noisy.jpg"
        sigma = 1.5
        clean_image(src, dst, add_noise=True, noise_sigma=sigma, jpeg_quality=100)

        with Image.open(dst) as cleaned:
            arr = np.array(cleaned, dtype=np.float32)
            # Max deviation from 128 should be small (within ~5*sigma)
            max_diff = float(np.max(np.abs(arr - 128.0)))
            assert max_diff < 5 * sigma + 5, (
                f"Noise too large: max pixel diff = {max_diff:.1f}, expected < {5*sigma+5}"
            )


# ---------------------------------------------------------------------------
# 5. JPEG quality randomization
# ---------------------------------------------------------------------------

class TestJpegQuality:

    def test_random_quality_produces_varying_sizes(self, tmp_dir):
        """Multiple cleans with random quality should produce varying file sizes."""
        sizes = []
        for i in range(10):
            src = _create_complex_image(tmp_dir / f"q_input_{i}.bmp")
            dst = tmp_dir / f"q_output_{i}.jpg"
            clean_image(src, dst, add_noise=False, jpeg_quality=None)
            sizes.append(dst.stat().st_size)
        # With random quality in 89-94, we'd expect at least 2 distinct sizes
        unique_sizes = len(set(sizes))
        assert unique_sizes >= 2, (
            f"Expected varying file sizes from random quality, got {unique_sizes} unique"
        )

    def test_explicit_quality_respected(self, tmp_dir):
        """Lower explicit quality should produce a smaller file than higher quality."""
        src_lo = _create_complex_image(tmp_dir / "q_lo_in.bmp")
        src_hi = _create_complex_image(tmp_dir / "q_hi_in.bmp")
        dst_lo = tmp_dir / "q_lo_out.jpg"
        dst_hi = tmp_dir / "q_hi_out.jpg"
        clean_image(src_lo, dst_lo, add_noise=False, jpeg_quality=50)
        clean_image(src_hi, dst_hi, add_noise=False, jpeg_quality=99)
        assert dst_lo.stat().st_size < dst_hi.stat().st_size, (
            "Lower quality should produce a smaller file"
        )


# ---------------------------------------------------------------------------
# 6. Overwrite in-place
# ---------------------------------------------------------------------------

class TestOverwriteInPlace:

    def test_overwrites_when_no_output_path(self, tmp_dir):
        """When output_path is None, the original file should be overwritten."""
        src = _create_jpeg_with_exif(tmp_dir / "inplace.jpg")
        original_bytes = src.read_bytes()

        result = clean_image(src, add_noise=False)

        assert result == src, "Return path should match input path"
        assert src.exists(), "File should still exist"
        new_bytes = src.read_bytes()
        assert new_bytes != original_bytes, "File contents should have changed"

    def test_inplace_result_has_no_exif(self, tmp_dir):
        """In-place cleaned file should have no EXIF."""
        src = _create_jpeg_with_exif(tmp_dir / "inplace_meta.jpg")
        clean_image(src, add_noise=False)

        with Image.open(src) as cleaned:
            exif = cleaned.getexif()
            assert len(exif) == 0, f"EXIF still present after in-place clean: {dict(exif)}"


# ---------------------------------------------------------------------------
# 7. Explicit output path
# ---------------------------------------------------------------------------

class TestExplicitOutputPath:

    def test_both_files_exist(self, tmp_dir):
        """Original and cleaned file should both exist when output_path differs."""
        src = _create_jpeg_with_exif(tmp_dir / "orig.jpg")
        dst = tmp_dir / "subdir" / "cleaned.jpg"

        result = clean_image(src, dst, add_noise=False)

        assert src.exists(), "Original file should still exist"
        assert dst.exists(), "Cleaned file should exist at output_path"
        assert result == dst

    def test_original_untouched(self, tmp_dir):
        """Original file should not be modified when writing to a different path."""
        src = _create_jpeg_with_exif(tmp_dir / "keep.jpg")
        original_bytes = src.read_bytes()
        dst = tmp_dir / "other.jpg"

        clean_image(src, dst, add_noise=False)

        assert src.read_bytes() == original_bytes, "Original file was modified"


# ---------------------------------------------------------------------------
# 8. Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_nonexistent_path_returns_input_path(self, tmp_dir):
        """Calling clean_image with a missing file should return input_path
        (the function catches exceptions and falls back gracefully)."""
        fake_path = tmp_dir / "does_not_exist.jpg"
        result = clean_image(fake_path)
        assert result == fake_path, (
            f"Expected input_path returned on error, got {result}"
        )


# ---------------------------------------------------------------------------
# 9. Pillow metadata behavior verification
# ---------------------------------------------------------------------------

class TestPillowMetadataBehavior:

    def test_pillow_resave_strips_exif(self, tmp_dir):
        """Directly verify: opening a JPEG with Pillow and re-saving WITHOUT
        passing exif= drops all EXIF data. This is the core assumption of
        the metadata-stripping approach."""
        src = _create_jpeg_with_exif(tmp_dir / "pillow_test.jpg")

        # Verify source actually has exif
        with Image.open(src) as original:
            original_exif = original.getexif()
            assert len(original_exif) > 0, "Test setup failure: source has no EXIF"

        # Re-save without passing exif=
        with Image.open(src) as img:
            rgb = img.convert("RGB")
        resaved = tmp_dir / "pillow_resaved.jpg"
        rgb.save(str(resaved), format="JPEG", quality=92)

        # Verify resaved has no exif
        with Image.open(resaved) as cleaned:
            cleaned_exif = cleaned.getexif()
            assert len(cleaned_exif) == 0, (
                f"Pillow resave still has EXIF: {dict(cleaned_exif)}"
            )

    def test_pillow_resave_strips_info_metadata(self, tmp_dir):
        """Verify .info dict is clean after Pillow round-trip."""
        src = _create_jpeg_with_exif(tmp_dir / "pillow_info.jpg")

        with Image.open(src) as img:
            rgb = img.convert("RGB")
        resaved = tmp_dir / "pillow_info_resaved.jpg"
        rgb.save(str(resaved), format="JPEG", quality=92)

        with Image.open(resaved) as cleaned:
            metadata_keys = {"exif", "icc_profile", "xmp", "photoshop"}
            found = metadata_keys & set(cleaned.info.keys())
            assert not found, f"Metadata keys still present: {found}"
