"""Bayesian attribute weight updater for TikTok explore/exploit feedback loop.

Updates attribute weights in the taxonomy based on post performance data.
Uses a 65/35 exploit/explore split: 65% of weight allocation goes to
top-performing attributes, 35% ensures even exploration of untested ones.

Cold-start behavior: until an attribute has 5+ posts, it receives equal
weight (pure exploration). After threshold, weights reflect a composite
performance score based on saves, shares, likes, and impressions.

Called by Phase 12 analytics pipeline after weekly performance data is collected.
"""

import json
import logging
from pathlib import Path

from src.shared.paths import STRATEGY_DIR

logger = logging.getLogger(__name__)

TAXONOMY_PATH = STRATEGY_DIR / "tiktok" / "attribute-taxonomy.json"

# Composite score weights — saves and shares matter most on TikTok.
# Completions excluded: Publer insights API doesn't provide watch-through
# data. Revisit if TikTok Display API is added (Phase 12 future upgrade).
METRIC_WEIGHTS = {
    "saves": 0.40,
    "shares": 0.35,
    "likes": 0.15,
    "impressions": 0.10,
}


def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    """Load the attribute taxonomy JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_taxonomy(taxonomy: dict, path: Path = TAXONOMY_PATH) -> None:
    """Save the updated taxonomy JSON (atomic write)."""
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
        logger.info("Saved updated taxonomy to %s", path)
    except OSError as e:
        logger.error("Failed to save taxonomy: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _composite_score(attr: dict) -> float:
    """Compute a normalized composite performance score for an attribute.

    Returns 0.0 if post_count is 0 (cold-start).
    """
    post_count = attr.get("post_count", 0)
    if post_count == 0:
        return 0.0

    score = 0.0
    for metric, weight in METRIC_WEIGHTS.items():
        per_post = attr.get(metric, 0) / post_count
        score += per_post * weight

    return score


def compute_weights(taxonomy: dict) -> dict:
    """Recompute attribute weights across all dimensions.

    For each dimension:
    1. Attributes below cold_start_threshold get equal weight (explore).
    2. Attributes above threshold get score-proportional weight (exploit).
    3. Final weights = exploit_ratio * exploit_weights + explore_ratio * explore_weights.
    4. Weights are normalized to sum to 1.0 within each dimension.

    Args:
        taxonomy: Full taxonomy dict (mutated in place and returned).

    Returns:
        The updated taxonomy dict.
    """
    cold_start_threshold = taxonomy.get("cold_start_threshold", 5)
    exploit_ratio = taxonomy.get("exploit_ratio", 0.65)
    explore_ratio = taxonomy.get("explore_ratio", 0.35)

    for dim_name, dim in taxonomy.get("dimensions", {}).items():
        attributes = dim.get("attributes", {})
        if not attributes:
            continue

        n = len(attributes)
        equal_weight = 1.0 / n

        # Separate cold-start vs mature attributes
        cold = []
        mature = []
        for attr_name, attr in attributes.items():
            if attr.get("post_count", 0) < cold_start_threshold:
                cold.append(attr_name)
            else:
                mature.append(attr_name)

        # If ALL attributes are cold-start, use even distribution
        if not mature:
            for attr_name in attributes:
                attributes[attr_name]["weight"] = round(equal_weight, 4)
            continue

        # Compute exploit weights (score-proportional for mature attrs)
        scores = {name: _composite_score(attributes[name]) for name in mature}
        total_score = sum(scores.values())

        exploit_weights = {}
        if total_score > 0:
            for name in mature:
                exploit_weights[name] = scores[name] / total_score
        else:
            # Mature but all scores are 0 — equal among mature
            for name in mature:
                exploit_weights[name] = 1.0 / len(mature)

        # Explore weights: equal share for all attributes
        explore_weights = {name: equal_weight for name in attributes}

        # Combine: exploit portion goes to mature, explore to all
        for attr_name in attributes:
            exploit_w = exploit_weights.get(attr_name, 0.0) * exploit_ratio
            explore_w = explore_weights[attr_name] * explore_ratio
            attributes[attr_name]["weight"] = round(exploit_w + explore_w, 4)

        # Normalize to sum to 1.0
        total = sum(a["weight"] for a in attributes.values())
        if total > 0:
            for attr_name in attributes:
                attributes[attr_name]["weight"] = round(
                    attributes[attr_name]["weight"] / total, 4
                )

        logger.info(
            "Updated %s weights: %s",
            dim_name,
            {k: v["weight"] for k, v in attributes.items()},
        )

    return taxonomy


def update_taxonomy_from_performance(post_log_entries: list[dict]) -> dict:
    """Load taxonomy, recompute performance data from scratch, update weights, save.

    Resets all attribute counters before accumulating, so this function is
    idempotent — calling it multiple times with the same full entry list
    produces the same result (no double-counting).

    Args:
        post_log_entries: List of post log dicts, each with keys:
            topic, angle, structure, hook_type, impressions, saves, shares, likes.

    Returns:
        The updated taxonomy dict.
    """
    taxonomy = load_taxonomy()
    dimensions = taxonomy.get("dimensions", {})

    # Reset all counters to avoid double-counting on repeated runs
    for dim in dimensions.values():
        for attr in dim.get("attributes", {}).values():
            attr["post_count"] = 0
            for metric in METRIC_WEIGHTS:
                attr[metric] = 0

    for entry in post_log_entries:
        for dim_name in dimensions:
            attr_value = entry.get(dim_name, "")
            if not attr_value:
                continue
            attrs = dimensions[dim_name].get("attributes", {})
            if attr_value not in attrs:
                logger.warning("Unknown %s attribute: %s", dim_name, attr_value)
                continue

            attr = attrs[attr_value]
            attr["post_count"] += 1
            for metric in METRIC_WEIGHTS:
                attr[metric] += entry.get(metric, 0)

    taxonomy = compute_weights(taxonomy)
    save_taxonomy(taxonomy)
    return taxonomy


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    PERFORMANCE_SUMMARY_PATH = Path(__file__).parent.parent.parent / "data" / "tiktok" / "performance-summary.json"

    if "--update" in sys.argv:
        # Feed performance data into taxonomy weights
        if not PERFORMANCE_SUMMARY_PATH.exists():
            print(f"No performance summary found at {PERFORMANCE_SUMMARY_PATH}")
            print("Run pull_analytics.py first to generate performance data.")
            sys.exit(1)

        perf = json.loads(PERFORMANCE_SUMMARY_PATH.read_text(encoding="utf-8"))

        # Staleness check: warn if performance data is more than 2 days old
        from datetime import date, datetime as dt_cls, timedelta
        generated_at = perf.get("generated_at", "")
        if generated_at:
            try:
                gen_date = dt_cls.fromisoformat(generated_at).date() if "T" in generated_at else date.fromisoformat(generated_at)
                if (date.today() - gen_date).days > 2:
                    print(f"WARNING: Performance summary is stale (generated {generated_at}). "
                          f"Analytics may not have been collected this week.")
            except ValueError:
                print(f"WARNING: Could not parse generated_at date: {generated_at}")

        entries = perf.get("entries", [])
        if not entries:
            print("Performance summary has no entries. Nothing to update.")
            sys.exit(0)

        print(f"Updating taxonomy from {len(entries)} performance entries...")
        tax = update_taxonomy_from_performance(entries)
        print(f"Updated taxonomy v{tax.get('version')}")
        for dim_name, dim in tax.get("dimensions", {}).items():
            attrs = dim.get("attributes", {})
            print(f"\n{dim_name} ({len(attrs)} attributes):")
            for attr_name, attr in attrs.items():
                print(f"  {attr_name}: weight={attr['weight']}, posts={attr.get('post_count', 0)}")
    else:
        # Display current taxonomy (no update)
        tax = load_taxonomy()
        print(f"Loaded taxonomy v{tax.get('version')}")
        for dim_name, dim in tax.get("dimensions", {}).items():
            attrs = dim.get("attributes", {})
            print(f"\n{dim_name} ({len(attrs)} attributes):")
            for attr_name, attr in attrs.items():
                print(f"  {attr_name}: weight={attr['weight']}, posts={attr.get('post_count', 0)}")
        print("\nTip: Run with --update to feed performance data into weights.")
