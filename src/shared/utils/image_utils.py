"""Shared image utilities."""

import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def image_to_data_uri(image_path: str) -> str:
    """Convert a local image file path to a base64 data URI.

    Critical for headless rendering — external file:// URLs and network
    requests may not work reliably in headless Chromium.
    """
    path = Path(image_path)
    if not path.exists():
        logger.warning("Image not found at %s, using empty placeholder", image_path)
        return ""

    with open(path, "rb") as img_f:
        header = img_f.read(12)
    detected = detect_mime_type(header)
    mime = detected if detected != "application/octet-stream" else "image/jpeg"

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")

    return f"data:{mime};base64,{encoded}"


def extract_drive_file_id(url: str) -> str | None:
    """Extract the Google Drive file ID from a Drive URL.

    Handles thumbnail URLs (``?id=FILE_ID&sz=...``) and open/uc URLs
    (``/d/FILE_ID/``).

    Args:
        url: A Google Drive URL string.

    Returns:
        The file ID string, or None if no ID could be extracted.
    """
    if not url:
        return None
    # Handle ?id=FILE_ID format
    if "id=" in url:
        try:
            file_id = url.split("id=")[1].split("&")[0]
            return file_id if file_id else None
        except (IndexError, ValueError):
            return None
    # Handle /d/FILE_ID/ format
    if "/d/" in url:
        try:
            parts = url.split("/d/")[1].split("/")
            file_id = parts[0] if parts else None
            return file_id if file_id else None
        except (IndexError, ValueError):
            return None
    return None


def detect_mime_type(data: bytes) -> str:
    """Detect MIME type from magic bytes.

    Checks JPEG, PNG, WebP, and GIF signatures.
    Returns 'application/octet-stream' for unknown formats.
    """
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'image/png'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'image/webp'
    if data[:4] == b'GIF8':
        return 'image/gif'
    return 'application/octet-stream'
