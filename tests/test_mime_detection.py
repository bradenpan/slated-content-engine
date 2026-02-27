"""Tests for src/utils/image_utils.py — MIME detection and Drive URL parsing."""

from src.utils.image_utils import detect_mime_type, extract_drive_file_id


# --- detect_mime_type ---

def test_jpeg_magic_bytes():
    data = b'\xff\xd8\xff\xe0' + b'\x00' * 100
    assert detect_mime_type(data) == "image/jpeg"


def test_png_magic_bytes():
    data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
    assert detect_mime_type(data) == "image/png"


def test_webp_magic_bytes():
    # WebP: RIFF....WEBP
    data = b'RIFF' + b'\x00\x00\x00\x00' + b'WEBP' + b'\x00' * 100
    assert detect_mime_type(data) == "image/webp"


def test_gif_magic_bytes():
    data = b'GIF89a' + b'\x00' * 100
    assert detect_mime_type(data) == "image/gif"


def test_unknown_bytes_returns_octet_stream():
    data = b'\x00\x01\x02\x03\x04\x05'
    assert detect_mime_type(data) == "application/octet-stream"


# --- extract_drive_file_id ---

def test_standard_drive_thumbnail_url():
    url = "https://drive.google.com/thumbnail?id=1aBcDeFgHiJkLmNoPqRsT&sz=w1000"
    assert extract_drive_file_id(url) == "1aBcDeFgHiJkLmNoPqRsT"


def test_drive_url_with_id_param_only():
    url = "https://drive.google.com/uc?id=FILE123"
    assert extract_drive_file_id(url) == "FILE123"


def test_drive_url_with_d_path():
    url = "https://drive.google.com/file/d/ABC123XYZ/view?usp=sharing"
    assert extract_drive_file_id(url) == "ABC123XYZ"


def test_drive_open_url_with_d_path():
    url = "https://drive.google.com/open?id=&d/FILEID456/"
    # Has id= before /d/ so id= path takes priority (empty id -> None via id= branch)
    # Actually "id=" is present so it takes the id= branch, split gives "" after id=
    # then split("&") gives ["", "d/FILEID456/"] -> first element is "" -> returns None
    assert extract_drive_file_id(url) is None


def test_drive_d_path_no_trailing_slash():
    url = "https://drive.google.com/file/d/MYFILEID"
    assert extract_drive_file_id(url) == "MYFILEID"


def test_non_drive_url_returns_none():
    url = "https://example.com/image.png"
    assert extract_drive_file_id(url) is None


def test_empty_string_returns_none():
    assert extract_drive_file_id("") is None


def test_none_input_returns_none():
    assert extract_drive_file_id(None) is None
