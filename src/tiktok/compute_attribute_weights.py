"""Bayesian attribute weight updater for TikTok explore/exploit feedback loop.

Updates attribute weights in the taxonomy based on post performance data.
Uses a 65/35 exploit/explore split: 65% of weight allocation goes to
top-performing attributes, 35% ensures even exploration of untested ones.

Cold-start behavior: until an attribute has 5+ posts, it receives equal
weight (pure exploration). After threshold, weights reflect a composite
performance score based on saves, shares, completions, and impressions.

Called by Phase 12 analytics pipeline after weekly performance data is collected.
"""

import json
import logging
from pathlib import Path

from src.shared.paths import STRATEGY_DIR

logger = logging.getLogger(__name__)

TAXONOMY_PATH = STRATEGY_DIR / "tiktok" / "attribute-taxonomy.json"

# Composite score weights — saves and shares matter most on TikTok
METRIC_WEIGHTS = {
    "saves": 0.35,
    "shares": 0.30,
    "completions": 0.25,
    "impressions": 0.10,
}


def load_taxonomy(path: Path = TAXONOMY_PATH) -> dict:
    """Load the attribute taxonomy JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_taxonomy(taxonomy: dict, path: Path = TAXONOMY_PATH) -> None:
    """Save the updated taxonomy JSON (atomic write)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(taxonomy, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)
    logger.info("Saved updated taxonomy to %s", path)


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
    """Load taxonomy, accumulate performance data, recompute weights, save.

    Args:
        post_log_entries: List of post log dicts, each with keys:
            topic, angle, structure, hook_type, impressions, saves, shares, completions.

    Returns:
        The updated taxonomy dict.
    """
    taxonomy = load_taxonomy()
    dimensions = taxonomy.get("dimensions", {})

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
            attr["post_count"] = attr.get("post_count", 0) + 1
            for metric in METRIC_WEIGHTS:
                attr[metric] = attr.get(metric, 0) + entry.get(metric, 0)

    taxonomy = compute_weights(taxonomy)
    save_taxonomy(taxonomy)
    return taxonomy


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    tax = load_taxonomy()
    print(f"Loaded taxonomy v{tax.get('version')}")
    for dim_name, dim in tax.get("dimensions", {}).items():
        attrs = dim.get("attributes", {})
        print(f"\n{dim_name} ({len(attrs)} attributes):")
        for attr_name, attr in attrs.items():
            print(f"  {attr_name}: weight={attr['weight']}, posts={attr['post_count']}")
