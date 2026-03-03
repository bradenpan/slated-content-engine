"""Tests for src/paths.py — verify path constants resolve correctly."""

from pathlib import Path

from src.shared.paths import (
    CONTENT_LOG_PATH,
    DATA_DIR,
    PROMPTS_DIR,
    PROJECT_ROOT,
    STRATEGY_DIR,
    TEMPLATES_DIR,
)


def test_project_root_exists_and_is_directory():
    assert PROJECT_ROOT.exists()
    assert PROJECT_ROOT.is_dir()


def test_directory_paths_are_absolute():
    for p in [DATA_DIR, STRATEGY_DIR, PROMPTS_DIR, TEMPLATES_DIR]:
        assert p.is_absolute(), f"{p} is not absolute"


def test_directory_paths_are_children_of_project_root():
    for p in [DATA_DIR, STRATEGY_DIR, PROMPTS_DIR, TEMPLATES_DIR]:
        assert str(p).startswith(str(PROJECT_ROOT)), (
            f"{p} is not under PROJECT_ROOT ({PROJECT_ROOT})"
        )


def test_content_log_path_has_expected_filename():
    assert CONTENT_LOG_PATH.name == "content-log.jsonl"
