"""Tests for src/utils/content_log.py — content log CRUD operations."""

import json

from src.utils.content_log import (
    append_content_log_entry,
    is_pin_posted,
    load_content_log,
    save_content_log,
)


def test_load_returns_empty_list_for_nonexistent_file(tmp_path):
    result = load_content_log(path=tmp_path / "does-not-exist.jsonl")
    assert result == []


def test_save_and_load_roundtrip(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    entries = [
        {"pin_id": "W1-01", "topic": "slate tile"},
        {"pin_id": "W1-02", "topic": "porcelain care"},
    ]
    save_content_log(entries, path=log_path)
    loaded = load_content_log(path=log_path)
    assert loaded == entries


def test_append_content_log_entry(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    entry1 = {"pin_id": "W2-01", "topic": "grout cleaning"}
    entry2 = {"pin_id": "W2-02", "topic": "backsplash ideas"}

    append_content_log_entry(entry1, path=log_path)
    append_content_log_entry(entry2, path=log_path)

    loaded = load_content_log(path=log_path)
    assert len(loaded) == 2
    assert loaded[0] == entry1
    assert loaded[1] == entry2


def test_is_pin_posted_true_when_has_pinterest_pin_id(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    entries = [
        {"pin_id": "W3-01", "pinterest_pin_id": "123456789"},
    ]
    save_content_log(entries, path=log_path)
    assert is_pin_posted("W3-01", path=log_path) is True


def test_is_pin_posted_false_when_no_pinterest_pin_id(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    entries = [
        {"pin_id": "W3-02", "pinterest_pin_id": None},
    ]
    save_content_log(entries, path=log_path)
    assert is_pin_posted("W3-02", path=log_path) is False


def test_is_pin_posted_false_for_nonexistent_file(tmp_path):
    assert is_pin_posted("W99-01", path=tmp_path / "nope.jsonl") is False


def test_is_pin_posted_false_for_unknown_pin_id(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    entries = [
        {"pin_id": "W4-01", "pinterest_pin_id": "111"},
    ]
    save_content_log(entries, path=log_path)
    assert is_pin_posted("W4-99", path=log_path) is False


def test_load_skips_malformed_lines(tmp_path):
    log_path = tmp_path / "content-log.jsonl"
    log_path.write_text(
        '{"pin_id": "W5-01"}\n'
        'NOT JSON\n'
        '{"pin_id": "W5-02"}\n',
        encoding="utf-8",
    )
    loaded = load_content_log(path=log_path)
    assert len(loaded) == 2
    assert loaded[0]["pin_id"] == "W5-01"
    assert loaded[1]["pin_id"] == "W5-02"
