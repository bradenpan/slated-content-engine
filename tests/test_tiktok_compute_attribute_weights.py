"""Tests for src/tiktok/compute_attribute_weights.py — Bayesian explore/exploit weights."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src.tiktok.compute_attribute_weights import (
    load_taxonomy,
    save_taxonomy,
    _composite_score,
    compute_weights,
    update_taxonomy_from_performance,
    METRIC_WEIGHTS,
)


SAMPLE_TAXONOMY = {
    "version": "1.0",
    "cold_start_threshold": 5,
    "exploit_ratio": 0.65,
    "explore_ratio": 0.35,
    "dimensions": {
        "topic": {
            "attributes": {
                "grout": {"weight": 0.2, "post_count": 0, "saves": 0, "shares": 0, "likes": 0, "impressions": 0},
                "tile": {"weight": 0.2, "post_count": 0, "saves": 0, "shares": 0, "likes": 0, "impressions": 0},
                "backsplash": {"weight": 0.2, "post_count": 0, "saves": 0, "shares": 0, "likes": 0, "impressions": 0},
                "bathroom": {"weight": 0.2, "post_count": 0, "saves": 0, "shares": 0, "likes": 0, "impressions": 0},
                "kitchen": {"weight": 0.2, "post_count": 0, "saves": 0, "shares": 0, "likes": 0, "impressions": 0},
            }
        }
    }
}


def test_load_taxonomy_reads_and_parses(tmp_path):
    tax_path = tmp_path / "taxonomy.json"
    tax_path.write_text(json.dumps(SAMPLE_TAXONOMY), encoding="utf-8")
    result = load_taxonomy(path=tax_path)
    assert result["version"] == "1.0"
    assert "topic" in result["dimensions"]
    assert len(result["dimensions"]["topic"]["attributes"]) == 5


def test_save_taxonomy_writes_atomically(tmp_path):
    tax_path = tmp_path / "taxonomy.json"
    save_taxonomy(SAMPLE_TAXONOMY, path=tax_path)
    assert tax_path.exists()
    loaded = json.loads(tax_path.read_text(encoding="utf-8"))
    assert loaded["version"] == "1.0"
    # No leftover .tmp file
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0


def test_composite_score_returns_zero_for_zero_post_count():
    attr = {"post_count": 0, "saves": 0, "shares": 0, "likes": 0, "impressions": 0}
    assert _composite_score(attr) == 0.0


def test_composite_score_computes_weighted_sum():
    attr = {
        "post_count": 10,
        "saves": 100,    # per-post: 10
        "shares": 50,    # per-post: 5
        "likes": 200,    # per-post: 20
        "impressions": 5000,  # per-post: 500
    }
    expected = (
        (100 / 10) * METRIC_WEIGHTS["saves"]
        + (50 / 10) * METRIC_WEIGHTS["shares"]
        + (200 / 10) * METRIC_WEIGHTS["likes"]
        + (5000 / 10) * METRIC_WEIGHTS["impressions"]
    )
    assert _composite_score(attr) == pytest.approx(expected)


def test_compute_weights_equal_when_all_cold_start():
    tax = copy.deepcopy(SAMPLE_TAXONOMY)
    result = compute_weights(tax)
    attrs = result["dimensions"]["topic"]["attributes"]
    for attr_name, attr in attrs.items():
        assert attr["weight"] == pytest.approx(0.2, abs=0.001)


def test_compute_weights_exploit_explore_split_for_mature():
    tax = copy.deepcopy(SAMPLE_TAXONOMY)
    # Make "grout" mature with good performance
    tax["dimensions"]["topic"]["attributes"]["grout"].update({
        "post_count": 10, "saves": 100, "shares": 50, "likes": 200, "impressions": 5000,
    })
    # Make "tile" mature with lower performance
    tax["dimensions"]["topic"]["attributes"]["tile"].update({
        "post_count": 10, "saves": 20, "shares": 10, "likes": 50, "impressions": 2000,
    })
    # Others remain cold-start (post_count=0)

    result = compute_weights(tax)
    attrs = result["dimensions"]["topic"]["attributes"]

    # Grout should have higher weight than tile (better performance)
    assert attrs["grout"]["weight"] > attrs["tile"]["weight"]
    # Cold-start attributes should still have some weight (explore portion)
    assert attrs["backsplash"]["weight"] > 0
    assert attrs["bathroom"]["weight"] > 0
    assert attrs["kitchen"]["weight"] > 0


def test_compute_weights_normalizes_to_sum_one():
    tax = copy.deepcopy(SAMPLE_TAXONOMY)
    # Make some mature, some cold-start
    tax["dimensions"]["topic"]["attributes"]["grout"].update({
        "post_count": 10, "saves": 100, "shares": 50, "likes": 200, "impressions": 5000,
    })
    result = compute_weights(tax)
    attrs = result["dimensions"]["topic"]["attributes"]
    total = sum(a["weight"] for a in attrs.values())
    assert total == pytest.approx(1.0, abs=0.01)


def test_compute_weights_mixed_cold_start_and_mature():
    tax = copy.deepcopy(SAMPLE_TAXONOMY)
    # 2 mature, 3 cold-start
    tax["dimensions"]["topic"]["attributes"]["grout"].update({
        "post_count": 8, "saves": 80, "shares": 40, "likes": 160, "impressions": 4000,
    })
    tax["dimensions"]["topic"]["attributes"]["tile"].update({
        "post_count": 6, "saves": 30, "shares": 12, "likes": 60, "impressions": 1500,
    })
    result = compute_weights(tax)
    attrs = result["dimensions"]["topic"]["attributes"]

    # All weights should be positive
    for attr in attrs.values():
        assert attr["weight"] > 0

    # Total should be 1.0
    total = sum(a["weight"] for a in attrs.values())
    assert total == pytest.approx(1.0, abs=0.01)

    # Mature attributes should have higher combined weight than cold-start ones
    mature_weight = attrs["grout"]["weight"] + attrs["tile"]["weight"]
    cold_weight = attrs["backsplash"]["weight"] + attrs["bathroom"]["weight"] + attrs["kitchen"]["weight"]
    assert mature_weight > cold_weight


def test_update_taxonomy_resets_counters_before_accumulating():
    """Idempotency: calling twice with same data should produce same result."""
    entries = [
        {"topic": "grout", "impressions": 100, "saves": 10, "shares": 5, "likes": 20},
        {"topic": "grout", "impressions": 200, "saves": 20, "shares": 10, "likes": 40},
        {"topic": "tile", "impressions": 150, "saves": 15, "shares": 8, "likes": 30},
    ]

    saved_taxonomies = []

    def mock_save(tax, path=None):
        saved_taxonomies.append(copy.deepcopy(tax))

    with patch("src.tiktok.compute_attribute_weights.load_taxonomy",
               return_value=copy.deepcopy(SAMPLE_TAXONOMY)):
        with patch("src.tiktok.compute_attribute_weights.save_taxonomy", side_effect=mock_save):
            result1 = update_taxonomy_from_performance(entries)

    with patch("src.tiktok.compute_attribute_weights.load_taxonomy",
               return_value=copy.deepcopy(SAMPLE_TAXONOMY)):
        with patch("src.tiktok.compute_attribute_weights.save_taxonomy", side_effect=mock_save):
            result2 = update_taxonomy_from_performance(entries)

    # Should be identical -- counters reset before accumulating
    grout1 = result1["dimensions"]["topic"]["attributes"]["grout"]
    grout2 = result2["dimensions"]["topic"]["attributes"]["grout"]
    assert grout1["post_count"] == grout2["post_count"] == 2
    assert grout1["saves"] == grout2["saves"] == 30
    assert grout1["impressions"] == grout2["impressions"] == 300


def test_update_taxonomy_skips_unknown_attributes():
    entries = [
        {"topic": "grout", "impressions": 100, "saves": 10, "shares": 5, "likes": 20},
        {"topic": "nonexistent_topic", "impressions": 500, "saves": 50, "shares": 25, "likes": 100},
    ]

    with patch("src.tiktok.compute_attribute_weights.load_taxonomy",
               return_value=copy.deepcopy(SAMPLE_TAXONOMY)):
        with patch("src.tiktok.compute_attribute_weights.save_taxonomy"):
            result = update_taxonomy_from_performance(entries)

    attrs = result["dimensions"]["topic"]["attributes"]
    # "nonexistent_topic" should not appear in attributes
    assert "nonexistent_topic" not in attrs
    # "grout" should have its data
    assert attrs["grout"]["post_count"] == 1
    assert attrs["grout"]["saves"] == 10


def test_update_taxonomy_accumulates_metrics_correctly():
    entries = [
        {"topic": "grout", "impressions": 100, "saves": 10, "shares": 5, "likes": 20},
        {"topic": "grout", "impressions": 200, "saves": 20, "shares": 10, "likes": 40},
        {"topic": "tile", "impressions": 300, "saves": 30, "shares": 15, "likes": 60},
        {"topic": "backsplash", "impressions": 50, "saves": 5, "shares": 2, "likes": 10},
    ]

    with patch("src.tiktok.compute_attribute_weights.load_taxonomy",
               return_value=copy.deepcopy(SAMPLE_TAXONOMY)):
        with patch("src.tiktok.compute_attribute_weights.save_taxonomy"):
            result = update_taxonomy_from_performance(entries)

    attrs = result["dimensions"]["topic"]["attributes"]
    assert attrs["grout"]["post_count"] == 2
    assert attrs["grout"]["saves"] == 30
    assert attrs["grout"]["shares"] == 15
    assert attrs["grout"]["likes"] == 60
    assert attrs["grout"]["impressions"] == 300

    assert attrs["tile"]["post_count"] == 1
    assert attrs["tile"]["saves"] == 30
    assert attrs["tile"]["impressions"] == 300

    assert attrs["backsplash"]["post_count"] == 1
    assert attrs["backsplash"]["saves"] == 5

    # bathroom and kitchen should remain at 0
    assert attrs["bathroom"]["post_count"] == 0
    assert attrs["kitchen"]["post_count"] == 0
