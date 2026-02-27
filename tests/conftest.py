"""Shared test fixtures for the Pinterest pipeline test suite."""

from pathlib import Path

import piexif
import pytest
from PIL import Image


@pytest.fixture
def tmp_dir(tmp_path):
    """Provide a temporary directory for test files."""
    return tmp_path


def create_jpeg_with_exif(path: Path, size=(100, 100), color=(128, 128, 128)):
    """Create a JPEG file with EXIF metadata baked in.

    Shared helper used by image_cleaner tests. Moved here from duplicated
    copies in test_image_cleaner.py and test_image_cleaner_extended.py.
    """
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
