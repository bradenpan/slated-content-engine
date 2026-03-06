"""TikTok Analytics Puller

Pulls post-level analytics from Publer's post insights API.
Runs as part of the collect-analytics.yml workflow (Monday early AM).

Metrics collected per post:
- views (mapped to impressions), likes, comments, shares, engagement_rate
- saves: included if Publer returns them; 0 otherwise (may need manual entry)

Updates content-log.jsonl with latest performance data.

Data retention: Raw weekly snapshots saved to data/tiktok/analytics/YYYY-wNN-raw.json.
Performance summary (per-attribute averages) written to data/tiktok/performance-summary.json
for the feedback loop (compute_attribute_weights.py).

Data lag: TikTok metrics have 24-48 hour lag. Publer syncs daily.
"""

import json
import logging
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from src.tiktok.apis.publer_api import PublerAPI, PublerAPIError
from src.shared.paths import DATA_DIR, TIKTOK_DATA_DIR
from src.shared.analytics_utils import compute_derived_metrics
from src.shared.utils.content_log import load_content_log, save_content_log

logger = logging.getLogger(__name__)

ANALYTICS_DIR = TIKTOK_DATA_DIR / "analytics"
PERFORMANCE_SUMMARY_PATH = TIKTOK_DATA_DIR / "performance-summary.json"

# TikTok content peaks in 48-72 hours, but we track a 28-day window
MAX_LOOKBACK_DAYS = 28

# Attribute dimensions used for the feedback loop
ATTRIBUTE_DIMS = ["topic", "angle", "structure", "hook_type"]


def pull_analytics() -> dict:
    """Pull analytics for all tracked TikTok posts and update the content log.

    Steps:
    1. Load content-log.jsonl, filter to tiktok entries with publer_post_id
    2. Fetch post insights from Publer
    3. Join insights with content log entries
    4. Update cumulative metrics in content log
    5. Compute derived metrics
    6. Save updated content log
    7. Save raw analytics snapshot
    8. Write performance-summary.json (per-attribute averages)
    9. Identify top/bottom performers

    Returns:
        dict with keys: post_level, summary, entries, errors,
                        top_posts, bottom_posts, snapshot_path
    """
    publer = PublerAPI()

    entries = load_content_log()
    if not entries:
        logger.info("No entries in content log.")
        return _empty_result()

    today = date.today()
    cutoff_date = (today - timedelta(days=MAX_LOOKBACK_DAYS)).isoformat()

    # Filter to TikTok entries with a publer_post_id and within lookback window
    trackable = []
    for entry in entries:
        if (entry.get("channel") or "pinterest") != "tiktok":
            continue
        pid = entry.get("publer_post_id")
        if not pid or pid in ("PENDING", "MANUAL"):
            continue
        posted = entry.get("posted_date", "")
        if posted and posted < cutoff_date:
            continue
        trackable.append(entry)

    logger.info(
        "Pulling TikTok analytics for %d posts (out of %d total entries)",
        len(trackable), len(entries),
    )

    if not trackable:
        logger.info("No trackable TikTok posts in the lookback window.")
        entries = compute_derived_metrics(entries)
        save_content_log(entries)
        return _empty_result(entries=entries)

    # Fetch all post insights from Publer
    errors = []
    try:
        insights = publer.get_post_insights()
    except PublerAPIError as e:
        logger.error("Failed to fetch post insights: %s", e)
        errors.append(f"Publer insights fetch failed: {e}")
        insights = []

    # Index insights by Publer post ID for fast lookup
    insights_by_id = {}
    for insight in insights:
        pid = insight.get("id") or insight.get("post_id") or ""
        if pid:
            insights_by_id[pid] = insight

    # Join insights with trackable entries
    post_level_data = {}
    for entry in trackable:
        publer_id = entry.get("publer_post_id", "")
        content_id = entry.get("pin_id", publer_id)
        insight = insights_by_id.get(publer_id)

        if not insight:
            logger.debug("No insight data for post %s (publer_id=%s)", content_id, publer_id)
            continue

        metrics = _extract_metrics(insight)
        post_level_data[content_id] = {
            "publer_post_id": publer_id,
            "metrics": metrics,
        }

        # Update cumulative metrics (use max() guard like Pinterest)
        entry["impressions"] = max(metrics.get("views", 0), entry.get("impressions", 0))
        entry["saves"] = max(metrics.get("saves", 0), entry.get("saves", 0))
        entry["likes"] = max(metrics.get("likes", 0), entry.get("likes", 0))
        entry["comments"] = max(metrics.get("comments", 0), entry.get("comments", 0))
        entry["shares"] = max(metrics.get("shares", 0), entry.get("shares", 0))
        entry["last_analytics_pull"] = today.isoformat()

    # Compute derived metrics for ALL entries
    entries = compute_derived_metrics(entries)

    # Rewrite content log
    save_content_log(entries)

    # Save raw snapshot
    snapshot_path = _save_analytics_snapshot(post_level_data, today)

    # Build performance summary for feedback loop
    # Skip if insights fetch failed entirely — avoid overwriting valid data with zeros
    tiktok_entries = [e for e in entries if (e.get("channel") or "pinterest") == "tiktok"]
    weight_cutoff = (today - timedelta(days=84)).isoformat()  # 12-week rolling window
    windowed_entries = [e for e in tiktok_entries if (e.get("posted_date") or "") >= weight_cutoff]
    if post_level_data:
        perf_summary = _build_performance_summary(windowed_entries)
        _save_performance_summary(perf_summary)
    else:
        perf_summary = {}
        logger.warning("Skipping performance summary write — no post insights data")

    # Top / bottom performers
    scored = [
        e for e in tiktok_entries
        if e.get("impressions", 0) > 10
    ]
    scored.sort(key=lambda x: x.get("save_rate", 0), reverse=True)
    top_posts = scored[:5]
    bottom_posts = scored[-5:] if len(scored) >= 5 else []

    # Summary stats
    total_views = sum(e.get("impressions", 0) for e in tiktok_entries)
    total_saves = sum(e.get("saves", 0) for e in tiktok_entries)
    total_shares = sum(e.get("shares", 0) for e in tiktok_entries)
    total_likes = sum(e.get("likes", 0) for e in tiktok_entries)

    summary = {
        "total_views": total_views,
        "total_saves": total_saves,
        "total_shares": total_shares,
        "total_likes": total_likes,
        "posts_tracked": len(trackable),
        "posts_with_data": len(post_level_data),
        "errors": len(errors),
        "date_range": f"{cutoff_date} to {today.isoformat()}",
    }

    logger.info(
        "TikTok analytics pull complete: %d posts tracked, %d views, %d saves, "
        "%d shares, %d errors",
        len(trackable), total_views, total_saves, total_shares, len(errors),
    )

    return {
        "post_level": post_level_data,
        "summary": summary,
        "entries": entries,
        "errors": errors,
        "top_posts": [_post_summary(p) for p in top_posts],
        "bottom_posts": [_post_summary(p) for p in bottom_posts],
        "snapshot_path": str(snapshot_path) if snapshot_path else None,
        "performance_summary": perf_summary,
    }


def _extract_metrics(insight: dict) -> dict:
    """Extract standardized metrics from a Publer post insight object."""
    return {
        "views": insight.get("views", 0) or insight.get("impressions", 0) or 0,
        "likes": insight.get("likes", 0) or 0,
        "comments": insight.get("comments", 0) or 0,
        "shares": insight.get("shares", 0) or 0,
        "saves": insight.get("saves", 0) or 0,
        "engagement_rate": insight.get("engagement_rate", 0.0) or 0.0,
    }


def _post_summary(entry: dict) -> dict:
    """Create a concise summary of a post for analysis context."""
    return {
        "pin_id": entry.get("pin_id"),
        "title": entry.get("title", ""),
        "topic": entry.get("topic"),
        "angle": entry.get("angle"),
        "structure": entry.get("structure"),
        "hook_type": entry.get("hook_type"),
        "template_family": entry.get("template_family"),
        "impressions": entry.get("impressions", 0),
        "saves": entry.get("saves", 0),
        "shares": entry.get("shares", 0),
        "likes": entry.get("likes", 0),
        "comments": entry.get("comments", 0),
        "save_rate": entry.get("save_rate", 0),
    }


def _build_performance_summary(tiktok_entries: list[dict]) -> dict:
    """Build per-attribute performance averages for the feedback loop.

    Returns a dict structured for compute_attribute_weights.py:
    {
        "generated_at": "...",
        "post_count": N,
        "by_attribute": {
            "topic": {"value1": {saves, shares, ...}, ...},
            "angle": {...},
            ...
        },
        "entries": [condensed entry dicts for weight updater]
    }
    """
    by_attr: dict[str, dict[str, dict]] = {dim: defaultdict(
        lambda: {"impressions": 0, "saves": 0, "shares": 0, "likes": 0, "post_count": 0}
    ) for dim in ATTRIBUTE_DIMS}

    for entry in tiktok_entries:
        for dim in ATTRIBUTE_DIMS:
            val = entry.get(dim, "")
            if not val:
                continue
            agg = by_attr[dim][val]
            agg["impressions"] += entry.get("impressions", 0)
            agg["saves"] += entry.get("saves", 0)
            agg["shares"] += entry.get("shares", 0)
            agg["likes"] += entry.get("likes", 0)
            agg["post_count"] += 1

    # Build condensed entries for update_taxonomy_from_performance
    condensed = []
    for entry in tiktok_entries:
        if not entry.get("impressions", 0):
            continue
        condensed.append({
            dim: entry.get(dim, "") for dim in ATTRIBUTE_DIMS
        } | {
            "impressions": entry.get("impressions", 0),
            "saves": entry.get("saves", 0),
            "shares": entry.get("shares", 0),
            "likes": entry.get("likes", 0),
        })

    return {
        "generated_at": date.today().isoformat(),
        "post_count": len(tiktok_entries),
        "by_attribute": {dim: dict(vals) for dim, vals in by_attr.items()},
        "entries": condensed,
    }


def _save_performance_summary(summary: dict) -> Optional[Path]:
    """Write performance-summary.json for the feedback loop."""
    TIKTOK_DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        tmp = PERFORMANCE_SUMMARY_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(PERFORMANCE_SUMMARY_PATH)
        logger.info("Saved performance summary to %s", PERFORMANCE_SUMMARY_PATH)
        return PERFORMANCE_SUMMARY_PATH
    except OSError as e:
        logger.error("Failed to save performance summary: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _save_analytics_snapshot(post_data: dict, today: date) -> Optional[Path]:
    """Save raw analytics data to a weekly snapshot file."""
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    iso_year, iso_week, _ = today.isocalendar()
    filename = f"{iso_year}-w{iso_week:02d}-raw.json"
    snapshot_path = ANALYTICS_DIR / filename

    snapshot = {
        "generated_at": today.isoformat(),
        "posts_tracked": len(post_data),
        "post_analytics": post_data,
    }

    try:
        tmp = snapshot_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        tmp.replace(snapshot_path)
        logger.info("Saved analytics snapshot to %s", snapshot_path)
        return snapshot_path
    except OSError as e:
        logger.error("Failed to save analytics snapshot: %s", e)
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _empty_result(entries: list[dict] | None = None) -> dict:
    return {
        "post_level": {},
        "summary": {"total_views": 0, "total_saves": 0, "total_shares": 0,
                     "total_likes": 0, "posts_tracked": 0, "posts_with_data": 0,
                     "errors": 0},
        "entries": entries or [],
        "errors": [],
        "top_posts": [],
        "bottom_posts": [],
        "snapshot_path": None,
        "performance_summary": {},
    }


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    if "--demo" in sys.argv:
        print("=== Demo mode: pull_analytics (TikTok) ===")
        all_entries = load_content_log()
        tiktok = [e for e in all_entries if (e.get("channel") or "pinterest") == "tiktok"]
        print(f"Content log entries: {len(all_entries)}")
        print(f"TikTok entries: {len(tiktok)}")
        trackable = [e for e in tiktok if e.get("publer_post_id")]
        print(f"Trackable (have publer_post_id): {len(trackable)}")
    else:
        print("Pulling TikTok analytics via Publer...")
        try:
            data = pull_analytics()
            summary = data.get("summary", {})
            print(f"\nSummary:")
            print(f"  Posts tracked: {summary.get('posts_tracked', 0)}")
            print(f"  Posts with data: {summary.get('posts_with_data', 0)}")
            print(f"  Total views: {summary.get('total_views', 0)}")
            print(f"  Total saves: {summary.get('total_saves', 0)}")
            print(f"  Total shares: {summary.get('total_shares', 0)}")
            print(f"  Errors: {summary.get('errors', 0)}")
        except Exception as e:
            logger.error("TikTok analytics pull failed: %s", e, exc_info=True)
            sys.exit(1)
