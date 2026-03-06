"""Tests for src/shared/analytics_utils.py — derived metrics and aggregation."""

from src.shared.analytics_utils import compute_derived_metrics, aggregate_by_dimension


def test_compute_derived_metrics_adds_rates():
    entries = [
        {"impressions": 1000, "saves": 50, "outbound_clicks": 20, "shares": 10},
    ]
    result = compute_derived_metrics(entries)
    assert len(result) == 1
    assert result[0]["save_rate"] == round(50 / 1000, 6)
    assert result[0]["click_through_rate"] == round(20 / 1000, 6)
    assert result[0]["share_rate"] == round(10 / 1000, 6)


def test_compute_derived_metrics_zero_impressions():
    entries = [
        {"impressions": 0, "saves": 5, "outbound_clicks": 3, "shares": 1},
    ]
    result = compute_derived_metrics(entries)
    assert result[0]["save_rate"] == 0.0
    assert result[0]["click_through_rate"] == 0.0
    assert result[0]["share_rate"] == 0.0


def test_compute_derived_metrics_missing_shares_key():
    """Entries without a 'shares' key should still get share_rate = 0.0."""
    entries = [
        {"impressions": 500, "saves": 10, "outbound_clicks": 5},
    ]
    result = compute_derived_metrics(entries)
    assert result[0]["share_rate"] == 0.0
    assert result[0]["save_rate"] == round(10 / 500, 6)


def test_aggregate_by_dimension_groups_and_sums():
    entries = [
        {"topic": "grout", "impressions": 100, "saves": 10, "pin_clicks": 5, "outbound_clicks": 2},
        {"topic": "grout", "impressions": 200, "saves": 20, "pin_clicks": 8, "outbound_clicks": 4},
        {"topic": "tile", "impressions": 300, "saves": 15, "pin_clicks": 12, "outbound_clicks": 6},
    ]
    result = aggregate_by_dimension(entries, "topic")
    assert result["grout"]["count"] == 2
    assert result["grout"]["impressions"] == 300
    assert result["grout"]["saves"] == 30
    assert result["tile"]["count"] == 1
    assert result["tile"]["impressions"] == 300


def test_aggregate_by_dimension_computes_rates():
    entries = [
        {"topic": "grout", "impressions": 100, "saves": 10, "pin_clicks": 5, "outbound_clicks": 20},
    ]
    result = aggregate_by_dimension(entries, "topic")
    assert result["grout"]["save_rate"] == round(10 / 100, 6)
    assert result["grout"]["click_through_rate"] == round(20 / 100, 6)


def test_aggregate_by_dimension_includes_share_rate_with_extra_metrics():
    entries = [
        {"topic": "tile", "impressions": 200, "saves": 10, "pin_clicks": 5,
         "outbound_clicks": 4, "shares": 8},
    ]
    result = aggregate_by_dimension(entries, "topic", extra_metrics=["shares"])
    assert result["tile"]["shares"] == 8
    assert result["tile"]["share_rate"] == round(8 / 200, 6)


def test_aggregate_by_dimension_share_rate_zero_at_zero_impressions():
    entries = [
        {"topic": "tile", "impressions": 0, "saves": 0, "pin_clicks": 0,
         "outbound_clicks": 0, "shares": 0},
    ]
    result = aggregate_by_dimension(entries, "topic", extra_metrics=["shares"])
    assert result["tile"]["share_rate"] == 0.0


def test_aggregate_by_dimension_handles_list_dimension():
    entries = [
        {"boards": ["board-a", "board-b"], "impressions": 100, "saves": 5,
         "pin_clicks": 2, "outbound_clicks": 1},
    ]
    result = aggregate_by_dimension(entries, "boards")
    # List is converted to its string representation
    key = str(["board-a", "board-b"])
    assert key in result
    assert result[key]["count"] == 1


def test_aggregate_by_dimension_handles_none_dimension():
    entries = [
        {"topic": None, "impressions": 100, "saves": 5, "pin_clicks": 2, "outbound_clicks": 1},
    ]
    result = aggregate_by_dimension(entries, "topic")
    assert "unknown" in result
    assert result["unknown"]["count"] == 1


def test_aggregate_by_dimension_extra_metrics_summed():
    entries = [
        {"topic": "grout", "impressions": 100, "saves": 5, "pin_clicks": 2,
         "outbound_clicks": 1, "likes": 30, "comments": 3},
        {"topic": "grout", "impressions": 200, "saves": 10, "pin_clicks": 4,
         "outbound_clicks": 2, "likes": 50, "comments": 7},
    ]
    result = aggregate_by_dimension(entries, "topic", extra_metrics=["likes", "comments"])
    assert result["grout"]["likes"] == 80
    assert result["grout"]["comments"] == 10


def test_aggregate_by_dimension_empty_entries():
    result = aggregate_by_dimension([], "topic")
    assert result == {}
