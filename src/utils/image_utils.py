"""Shared image utilities."""


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
    if "id=" in url:
        try:
            file_id = url.split("id=")[1].split("&")[0]
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
