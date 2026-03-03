"""Tests for src/config.py — verify configuration constants are well-formed."""

from src.shared.config import (
    BLOG_BASE_URL,
    CLAUDE_COST_PER_MTK,
    CLAUDE_MODEL_DEEP,
    CLAUDE_MODEL_ROUTINE,
    PIN_HEIGHT,
    PIN_WIDTH,
)


def test_claude_model_routine_is_nonempty_string():
    assert isinstance(CLAUDE_MODEL_ROUTINE, str)
    assert len(CLAUDE_MODEL_ROUTINE) > 0


def test_claude_model_deep_is_nonempty_string():
    assert isinstance(CLAUDE_MODEL_DEEP, str)
    assert len(CLAUDE_MODEL_DEEP) > 0


def test_claude_cost_per_mtk_has_expected_keys():
    assert isinstance(CLAUDE_COST_PER_MTK, dict)
    # Each model key should map to a dict with "input" and "output"
    for model_key, costs in CLAUDE_COST_PER_MTK.items():
        assert isinstance(model_key, str)
        assert "input" in costs
        assert "output" in costs
        assert isinstance(costs["input"], (int, float))
        assert isinstance(costs["output"], (int, float))


def test_pin_dimensions_are_positive_integers():
    assert isinstance(PIN_WIDTH, int)
    assert isinstance(PIN_HEIGHT, int)
    assert PIN_WIDTH > 0
    assert PIN_HEIGHT > 0


def test_blog_base_url_starts_with_https():
    assert BLOG_BASE_URL.startswith("https://")
