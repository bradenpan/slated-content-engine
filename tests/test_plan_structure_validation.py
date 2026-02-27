"""Tests for _validate_plan_structure() in generate_weekly_plan.py.

Validates that malformed plans from Claude are rejected early with
clear error messages, rather than silently producing empty weeks.

Covers fix 9 from the codebase review.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Stub out heavy dependencies so we can import generate_weekly_plan
# without requiring anthropic, google-auth, etc.
_STUBS = [
    "anthropic",
    "google.auth",
    "google.oauth2",
    "google.oauth2.service_account",
    "googleapiclient",
    "googleapiclient.discovery",
    "google.cloud",
    "google.cloud.storage",
    "requests_oauthlib",
]
for _mod in _STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from src.generate_weekly_plan import _validate_plan_structure


# --- Valid plans ---


def test_valid_plan_with_both_keys():
    """A plan with non-empty blog_posts and pins lists passes validation."""
    plan = {
        "blog_posts": [{"post_id": "P1", "topic": "slate tiles"}],
        "pins": [{"pin_id": "W1-01", "title": "Best Slate Tiles"}],
    }
    # Should not raise
    _validate_plan_structure(plan)


def test_valid_plan_with_extra_keys():
    """Extra keys beyond blog_posts and pins are allowed."""
    plan = {
        "blog_posts": [{"post_id": "P1"}],
        "pins": [{"pin_id": "W1-01"}],
        "week_number": "W12",
        "date_range": "2026-03-16 to 2026-03-22",
    }
    _validate_plan_structure(plan)


# --- None input ---


def test_plan_none_raises_valueerror():
    """plan=None raises ValueError."""
    with pytest.raises(ValueError, match="must be a dict"):
        _validate_plan_structure(None)


# --- Wrong type (not a dict) ---


def test_plan_string_raises_valueerror():
    """A string plan raises ValueError mentioning the type."""
    with pytest.raises(ValueError, match="got str"):
        _validate_plan_structure("this is not a plan")


def test_plan_list_raises_valueerror():
    """A list plan raises ValueError."""
    with pytest.raises(ValueError, match="got list"):
        _validate_plan_structure([{"post_id": "P1"}])


def test_plan_integer_raises_valueerror():
    """An integer plan raises ValueError."""
    with pytest.raises(ValueError, match="got int"):
        _validate_plan_structure(42)


# --- Missing keys ---


def test_plan_missing_blog_posts_raises_valueerror():
    """A dict missing 'blog_posts' key raises ValueError."""
    plan = {"pins": [{"pin_id": "W1-01"}]}
    with pytest.raises(ValueError, match="blog_posts"):
        _validate_plan_structure(plan)


def test_plan_missing_pins_raises_valueerror():
    """A dict missing 'pins' key raises ValueError."""
    plan = {"blog_posts": [{"post_id": "P1"}]}
    with pytest.raises(ValueError, match="pins"):
        _validate_plan_structure(plan)


def test_plan_missing_both_keys_raises_valueerror():
    """An empty dict raises ValueError mentioning both keys."""
    with pytest.raises(ValueError) as exc_info:
        _validate_plan_structure({})
    assert "blog_posts" in str(exc_info.value)
    assert "pins" in str(exc_info.value)


# --- Empty lists ---


def test_plan_empty_blog_posts_raises_valueerror():
    """blog_posts as empty list raises ValueError with 'non-empty' message."""
    plan = {"blog_posts": [], "pins": [{"pin_id": "W1-01"}]}
    with pytest.raises(ValueError, match="non-empty list"):
        _validate_plan_structure(plan)


def test_plan_empty_pins_raises_valueerror():
    """pins as empty list raises ValueError with 'non-empty' message."""
    plan = {"blog_posts": [{"post_id": "P1"}], "pins": []}
    with pytest.raises(ValueError, match="non-empty list"):
        _validate_plan_structure(plan)


# --- Wrong value types ---


def test_plan_blog_posts_as_string_raises_valueerror():
    """blog_posts as a string raises ValueError."""
    plan = {"blog_posts": "not a list", "pins": [{"pin_id": "W1-01"}]}
    with pytest.raises(ValueError, match="non-empty list"):
        _validate_plan_structure(plan)


def test_plan_pins_as_string_raises_valueerror():
    """pins as a string raises ValueError."""
    plan = {"blog_posts": [{"post_id": "P1"}], "pins": "not a list"}
    with pytest.raises(ValueError, match="non-empty list"):
        _validate_plan_structure(plan)


def test_plan_blog_posts_as_dict_raises_valueerror():
    """blog_posts as a dict (not list) raises ValueError."""
    plan = {"blog_posts": {"post_id": "P1"}, "pins": [{"pin_id": "W1-01"}]}
    with pytest.raises(ValueError, match="non-empty list"):
        _validate_plan_structure(plan)


# --- Error message quality ---


def test_error_message_mentions_claude():
    """Error messages mention Claude as the likely source of the problem."""
    with pytest.raises(ValueError, match="Claude"):
        _validate_plan_structure("bad plan")
