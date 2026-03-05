"""Channel-agnostic analytics utilities.

Generic metric computation and aggregation functions that work with any
content log entries regardless of source platform. Extracted from
pull_analytics.py to enable reuse across Pinterest, TikTok, and future channels.
"""
from collections import defaultdict


def compute_derived_metrics(entries: list[dict]) -> list[dict]:
    """
    Compute derived metrics (save rate, CTR) for each entry.

    - save_rate = saves / impressions (0 if no impressions)
    - click_through_rate = outbound_clicks / impressions (0 if no impressions)

    Args:
        entries: Content log entries with raw analytics.

    Returns:
        list[dict]: Entries with added save_rate and click_through_rate fields.
    """
    for entry in entries:
        impressions = entry.get("impressions", 0)
        saves = entry.get("saves", 0)
        outbound_clicks = entry.get("outbound_clicks", 0)

        if impressions > 0:
            entry["save_rate"] = round(saves / impressions, 6)
            entry["click_through_rate"] = round(outbound_clicks / impressions, 6)
        else:
            entry["save_rate"] = 0.0
            entry["click_through_rate"] = 0.0

    return entries


def aggregate_by_dimension(
    entries: list[dict],
    dimension: str,
    extra_metrics: list[str] | None = None,
) -> dict:
    """
    Aggregate performance metrics by a given dimension.

    Groups entries by the specified dimension field and sums metrics
    within each group. Also computes aggregate save rate and CTR.

    Args:
        entries: Content log entries with analytics.
        dimension: Field name to group by. One of:
            "pillar", "content_type", "board", "template",
            "primary_keyword", "image_source", "funnel_layer",
            "pin_type", "treatment_number",
            "topic", "angle", "structure", "hook_type" (TikTok).
        extra_metrics: Additional metric field names to aggregate
            (e.g., ["shares", "likes", "comments"] for TikTok).

    Returns:
        dict: Mapping of dimension value -> {
            "count": int,
            "impressions": int,
            "saves": int,
            "pin_clicks": int,
            "outbound_clicks": int,
            "save_rate": float,
            "click_through_rate": float,
            ... plus any extra_metrics ...
        }
    """
    extras = extra_metrics or []

    def _make_agg():
        base = {
            "count": 0,
            "impressions": 0,
            "saves": 0,
            "pin_clicks": 0,
            "outbound_clicks": 0,
        }
        for m in extras:
            base[m] = 0
        return base

    aggregates = defaultdict(_make_agg)

    for entry in entries:
        dim_value = entry.get(dimension, "unknown")
        # Handle list-type dimension values (some boards map to multiple pillars)
        if isinstance(dim_value, list):
            dim_value = str(dim_value)
        dim_value = str(dim_value) if dim_value is not None else "unknown"

        agg = aggregates[dim_value]
        agg["count"] += 1
        agg["impressions"] += entry.get("impressions", 0)
        agg["saves"] += entry.get("saves", 0)
        agg["pin_clicks"] += entry.get("pin_clicks", 0)
        agg["outbound_clicks"] += entry.get("outbound_clicks", 0)
        for m in extras:
            agg[m] += entry.get(m, 0)

    # Compute aggregate rates
    result = {}
    for dim_value, agg in aggregates.items():
        impressions = agg["impressions"]
        derived = {
            "save_rate": round(agg["saves"] / impressions, 6) if impressions > 0 else 0.0,
            "click_through_rate": round(agg["outbound_clicks"] / impressions, 6) if impressions > 0 else 0.0,
        }
        if "shares" in agg and impressions > 0:
            derived["share_rate"] = round(agg["shares"] / impressions, 6)
        result[dim_value] = {**agg, **derived}

    return result
