"""Tests for _validate_plan() in src/tiktok/generate_weekly_plan.py."""

import logging
import sys
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

from src.tiktok.generate_weekly_plan import (
    _validate_plan,
    REQUIRED_CAROUSEL_KEYS,
    VALID_TEMPLATE_FAMILIES,
)


def _make_carousel(**overrides):
    """Build a minimal valid carousel spec dict."""
    base = {
        "carousel_id": "T01",
        "topic": "topic_value",
        "angle": "angle_value",
        "structure": "structure_value",
        "hook_type": "hook_type_value",
        "template_family": "clean_educational",
        "hook_text": "Short hook",
        "content_slides": [
            {"headline": "Slide 1", "body_text": "Body 1"},
            {"headline": "Slide 2", "body_text": "Body 2"},
            {"headline": "Slide 3", "body_text": "Body 3"},
        ],
        "cta_slide": {"cta_primary": "Follow @slatedapp"},
        "caption": "A caption",
        "hashtags": ["#slated"],
        "scheduled_date": "2026-03-10",
        "is_aigc": True,
    }
    base.update(overrides)
    return base


def _make_plan(carousels=None, taxonomy=None):
    """Build a plan dict and taxonomy for _validate_plan."""
    if carousels is None:
        carousels = [_make_carousel()]
    plan = {"carousels": carousels}
    if taxonomy is None:
        taxonomy = {"dimensions": {}}
    return plan, taxonomy


# --- Structural validation (hard failures) ---

def test_missing_required_keys_raises_value_error():
    """Carousel missing a required key raises ValueError."""
    carousel = _make_carousel()
    del carousel["topic"]
    del carousel["angle"]
    plan, taxonomy = _make_plan([carousel])
    with pytest.raises(ValueError, match="missing required keys"):
        _validate_plan(plan, taxonomy)


def test_duplicate_carousel_id_raises_value_error():
    """Two carousels with the same carousel_id raises ValueError."""
    c1 = _make_carousel(carousel_id="DUP-01")
    c2 = _make_carousel(carousel_id="DUP-01")
    plan, taxonomy = _make_plan([c1, c2])
    with pytest.raises(ValueError, match="Duplicate carousel_id"):
        _validate_plan(plan, taxonomy)


def test_valid_plan_passes_without_error():
    """A fully valid plan passes validation without any exception."""
    plan, taxonomy = _make_plan([
        _make_carousel(carousel_id="V01"),
        _make_carousel(carousel_id="V02"),
    ])
    _validate_plan(plan, taxonomy)  # should not raise


# --- Warnings (non-fatal) ---

def test_invalid_template_family_raises():
    """An unrecognised template_family raises ValueError."""
    carousel = _make_carousel(template_family="neon_glow")
    plan, taxonomy = _make_plan([carousel])
    with pytest.raises(ValueError, match="invalid template_family"):
        _validate_plan(plan, taxonomy)


def test_non_list_content_slides_converted_to_empty_list():
    """content_slides that is not a list gets replaced with []."""
    carousel = _make_carousel(content_slides="not a list")
    plan, taxonomy = _make_plan([carousel])
    _validate_plan(plan, taxonomy)
    assert carousel["content_slides"] == []


def test_content_slides_fewer_than_two_logs_warning(caplog):
    """Fewer than 2 content slides logs a warning."""
    carousel = _make_carousel(content_slides=[{"headline": "Solo"}])
    plan, taxonomy = _make_plan([carousel])
    with caplog.at_level(logging.WARNING):
        _validate_plan(plan, taxonomy)
    assert any("only 1 content slides" in m for m in caplog.messages)


def test_hook_text_over_15_words_logs_warning(caplog):
    """hook_text with more than 15 words triggers a warning."""
    long_hook = " ".join(["word"] * 20)
    carousel = _make_carousel(hook_text=long_hook)
    plan, taxonomy = _make_plan([carousel])
    with caplog.at_level(logging.WARNING):
        _validate_plan(plan, taxonomy)
    assert any("hook_text is 20 words" in m for m in caplog.messages)


def test_image_prompts_over_3_logs_warning(caplog):
    """More than 3 image_prompts triggers a warning."""
    carousel = _make_carousel(
        template_family="photo_forward",
        image_prompts=[
            {"slide_index": 0, "prompt": "p1"},
            {"slide_index": 1, "prompt": "p2"},
            {"slide_index": 2, "prompt": "p3"},
            {"slide_index": 3, "prompt": "p4"},
        ],
    )
    plan, taxonomy = _make_plan([carousel])
    with caplog.at_level(logging.WARNING):
        _validate_plan(plan, taxonomy)
    assert any("4 image_prompts (max 3)" in m for m in caplog.messages)


def test_image_prompt_targeting_cta_slide_logs_warning(caplog):
    """image_prompt whose slide_index equals the CTA index logs a warning."""
    # 3 content slides -> CTA index = 3 + 1 = 4
    carousel = _make_carousel(
        template_family="photo_forward",
        image_prompts=[{"slide_index": 4, "prompt": "cta bg"}],
    )
    plan, taxonomy = _make_plan([carousel])
    with caplog.at_level(logging.WARNING):
        _validate_plan(plan, taxonomy)
    assert any("targeting CTA slide" in m for m in caplog.messages)


def test_non_photo_forward_with_image_prompts_logs_warning(caplog):
    """Non-photo_forward family with image_prompts triggers a warning."""
    carousel = _make_carousel(
        template_family="clean_educational",
        image_prompts=[{"slide_index": 0, "prompt": "bg"}],
    )
    plan, taxonomy = _make_plan([carousel])
    with caplog.at_level(logging.WARNING):
        _validate_plan(plan, taxonomy)
    assert any("should be empty" in m for m in caplog.messages)


def test_default_image_prompts_to_empty_list():
    """Carousel without image_prompts key gets it defaulted to []."""
    carousel = _make_carousel()
    # Ensure image_prompts is not in the dict
    carousel.pop("image_prompts", None)
    plan, taxonomy = _make_plan([carousel])
    _validate_plan(plan, taxonomy)
    assert carousel.get("image_prompts") == []


def test_empty_carousel_id_raises():
    """Carousel with empty carousel_id raises ValueError."""
    carousel = _make_carousel(carousel_id="")
    plan, taxonomy = _make_plan([carousel])
    with pytest.raises(ValueError, match="empty or missing carousel_id"):
        _validate_plan(plan, taxonomy)


def test_invalid_scheduled_date_format_raises():
    """Carousel with non-ISO scheduled_date raises ValueError."""
    carousel = _make_carousel(scheduled_date="03/10/2026")
    plan, taxonomy = _make_plan([carousel])
    with pytest.raises(ValueError, match="invalid scheduled_date"):
        _validate_plan(plan, taxonomy)


def test_hyphenated_template_family_normalized():
    """Hyphenated template_family is auto-normalized to underscored."""
    carousel = _make_carousel(template_family="clean-educational")
    plan, taxonomy = _make_plan([carousel])
    _validate_plan(plan, taxonomy)
    assert carousel["template_family"] == "clean_educational"
