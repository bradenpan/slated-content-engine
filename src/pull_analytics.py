"""
Pinterest Analytics Puller

Pulls pin-level and account-level analytics from Pinterest API.
Runs as part of the weekly-review.yml workflow (Monday early AM).

Data collected per pin:
- IMPRESSION, SAVE, PIN_CLICK, OUTBOUND_CLICK
- Date range: last 7 days (+ older pins still tracked, up to 90 days)
- Granularity: DAY

Updates content-log.jsonl with latest performance data.
The file is small enough to rewrite entirely each week (~100KB after a year).

Long-tail tracking: pulls analytics for ALL pins less than 90 days old,
not just this week's pins. Captures the compounding effect of older pins.

Data retention: All data stored indefinitely. Pinterest API only serves
90 days, so local storage is the long-term record.

Raw weekly snapshots saved to data/analytics/YYYY-wNN-raw.json.
"""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from src.apis.pinterest_api import PinterestAPI, PinterestAPIError
from src.token_manager import TokenManager
from src.paths import DATA_DIR
from src.config import MAX_LOOKBACK_DAYS
from src.utils.content_log import load_content_log, save_content_log

logger = logging.getLogger(__name__)

ANALYTICS_DIR = DATA_DIR / "analytics"

# Metrics to pull from Pinterest
METRICS = ["IMPRESSION", "SAVE", "PIN_CLICK", "OUTBOUND_CLICK"]


def pull_analytics(days_back: int = 7) -> dict:
    """
    Pull analytics for all tracked pins and update the content log.

    Steps:
    1. Refresh Pinterest token
    2. Read content-log.jsonl for all pins with a non-null pinterest_pin_id
    3. For each pin < 90 days old: pull pin-level analytics
    4. Pull account-level analytics
    5. Compute derived metrics per pin
    6. Rewrite content-log.jsonl with updated metrics
    7. Save raw analytics snapshot
    8. Return aggregated data for downstream analysis

    Args:
        days_back: Number of days of data to pull (default 7).
                   Used for the date range query. Pins older than
                   90 days are excluded regardless.

    Returns:
        dict: Aggregated analytics data with:
            - pin_level: dict of pin_id -> metrics
            - account_level: Account aggregate metrics
            - summary: Quick stats (total impressions, saves, clicks)
            - entries: Updated content log entries (with derived metrics)
    """
    # Initialize services
    token_manager = TokenManager()
    access_token = token_manager.get_valid_token()
    pinterest = PinterestAPI(access_token=access_token)

    # Load all content log entries
    entries = load_content_log()
    if not entries:
        logger.info("No entries in content log. Nothing to pull analytics for.")
        return {
            "pin_level": {},
            "account_level": {},
            "summary": {"total_impressions": 0, "total_saves": 0, "total_clicks": 0},
            "entries": [],
        }

    # Determine date range for the analytics query
    today = date.today()
    end_date = today.isoformat()
    start_date = (today - timedelta(days=days_back)).isoformat()

    # For long-tail tracking, also determine which pins are < 90 days old
    cutoff_date = (today - timedelta(days=MAX_LOOKBACK_DAYS)).isoformat()

    # Filter to pins that have a pinterest_pin_id and are < 90 days old
    trackable_entries = []
    for entry in entries:
        pinterest_pin_id = entry.get("pinterest_pin_id")
        if not pinterest_pin_id:
            continue

        posted_date = entry.get("posted_date", "")
        if posted_date and posted_date < cutoff_date:
            # Pin is older than 90 days -- Pinterest API won't have data
            # Keep cumulative totals as-is, skip the API call
            logger.debug(
                "Pin %s posted on %s is > 90 days old, skipping API call",
                entry.get("pin_id"), posted_date,
            )
            continue

        trackable_entries.append(entry)

    logger.info(
        "Pulling analytics for %d pins (out of %d total in log) from %s to %s",
        len(trackable_entries), len(entries), start_date, end_date,
    )

    # Pull pin-level analytics
    pin_level_data = {}
    errors = []

    for entry in trackable_entries:
        pinterest_pin_id = entry.get("pinterest_pin_id")
        pin_id = entry.get("pin_id", pinterest_pin_id)

        try:
            # Determine the start date for this pin's analytics
            # Use the later of: (days_back ago) or (pin posted date)
            # For long-tail: use the pin's posted_date as start if it's
            # within the 90-day window to get cumulative data
            pin_posted = entry.get("posted_date", start_date)
            pin_start = max(pin_posted, cutoff_date) if pin_posted else start_date

            analytics = pinterest.get_pin_analytics(
                pin_id=pinterest_pin_id,
                start_date=pin_start,
                end_date=end_date,
                metric_types=METRICS,
                granularity="DAY",
            )

            # Sum metrics across the date range
            # Pinterest returns data in a dict with metric names as keys,
            # each containing a list of daily values
            summed = _sum_pin_metrics(analytics)
            pin_level_data[pin_id] = {
                "pinterest_pin_id": pinterest_pin_id,
                "raw_analytics": analytics,
                "period_metrics": summed,
                "query_start": pin_start,
                "query_end": end_date,
            }

            # Update the entry's cumulative metrics
            # We use the summed values from the full available range
            # Use max() guard — metrics are monotonically increasing.
            # Prevents data loss if API returns narrower window than expected.
            entry["impressions"] = max(summed.get("IMPRESSION", 0), entry.get("impressions", 0))
            entry["saves"] = max(summed.get("SAVE", 0), entry.get("saves", 0))
            entry["pin_clicks"] = max(summed.get("PIN_CLICK", 0), entry.get("pin_clicks", 0))
            entry["outbound_clicks"] = max(summed.get("OUTBOUND_CLICK", 0), entry.get("outbound_clicks", 0))
            entry["last_analytics_pull"] = today.isoformat()

            logger.debug(
                "Pin %s: impressions=%d, saves=%d, clicks=%d",
                pin_id, summed.get("IMPRESSION", 0),
                summed.get("SAVE", 0), summed.get("OUTBOUND_CLICK", 0),
            )

            # Rate-limit: small delay between API calls to avoid 429
            time.sleep(0.2)

        except PinterestAPIError as e:
            error_msg = f"Failed to pull analytics for pin {pin_id}: {e}"
            logger.warning(error_msg)
            errors.append(error_msg)
            # Individual pin failures shouldn't crash the whole pull
            continue

        except Exception as e:
            error_msg = f"Unexpected error pulling analytics for pin {pin_id}: {e}"
            logger.warning(error_msg, exc_info=True)
            errors.append(error_msg)
            continue

    # Pull account-level analytics
    account_data = {}
    try:
        account_data = pinterest.get_account_analytics(
            start_date=start_date,
            end_date=end_date,
            granularity="DAY",
            metric_types=METRICS,
        )
        logger.info("Account analytics pulled successfully")
    except PinterestAPIError as e:
        logger.warning("Failed to pull account analytics: %s", e)
        errors.append(f"Account analytics failed: {e}")

    # Compute derived metrics for all entries
    entries = compute_derived_metrics(entries)

    # Rewrite the entire content log with updated metrics
    save_content_log(entries)

    # Save raw analytics snapshot
    snapshot = _save_analytics_snapshot(pin_level_data, account_data, start_date, end_date)

    # Compute summary
    total_impressions = sum(e.get("impressions", 0) for e in entries)
    total_saves = sum(e.get("saves", 0) for e in entries)
    total_clicks = sum(e.get("outbound_clicks", 0) for e in entries)
    total_pin_clicks = sum(e.get("pin_clicks", 0) for e in entries)

    summary = {
        "total_impressions": total_impressions,
        "total_saves": total_saves,
        "total_outbound_clicks": total_clicks,
        "total_pin_clicks": total_pin_clicks,
        "pins_tracked": len(trackable_entries),
        "pins_total": len(entries),
        "errors": len(errors),
        "date_range": f"{start_date} to {end_date}",
    }

    logger.info(
        "Analytics pull complete: %d pins tracked, %d impressions, %d saves, "
        "%d outbound clicks, %d errors",
        len(trackable_entries), total_impressions, total_saves, total_clicks, len(errors),
    )

    return {
        "pin_level": pin_level_data,
        "account_level": account_data,
        "summary": summary,
        "entries": entries,
        "errors": errors,
        "snapshot_path": str(snapshot) if snapshot else None,
    }


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
            "pin_type", "treatment_number".

    Returns:
        dict: Mapping of dimension value -> {
            "count": int,
            "impressions": int,
            "saves": int,
            "pin_clicks": int,
            "outbound_clicks": int,
            "save_rate": float,
            "click_through_rate": float,
        }
    """
    aggregates = defaultdict(lambda: {
        "count": 0,
        "impressions": 0,
        "saves": 0,
        "pin_clicks": 0,
        "outbound_clicks": 0,
    })

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

    # Compute aggregate rates
    result = {}
    for dim_value, agg in aggregates.items():
        impressions = agg["impressions"]
        result[dim_value] = {
            **agg,
            "save_rate": round(agg["saves"] / impressions, 6) if impressions > 0 else 0.0,
            "click_through_rate": round(agg["outbound_clicks"] / impressions, 6) if impressions > 0 else 0.0,
        }

    return result


def _sum_pin_metrics(analytics_response: dict) -> dict:
    """
    Sum metrics from a Pinterest pin analytics response across all days.

    The Pinterest API returns analytics data in varying formats. This function
    handles the expected format where metrics are keyed by date or returned
    as lists.

    Expected response format (Pinterest v5):
    {
        "all": {
            "daily_metrics": [
                {
                    "date": "2026-02-13",
                    "data_status": "READY",
                    "metrics": {
                        "IMPRESSION": 150,
                        "SAVE": 5,
                        "PIN_CLICK": 10,
                        "OUTBOUND_CLICK": 3
                    }
                },
                ...
            ],
            "summary_metrics": {
                "IMPRESSION": 1050,
                "SAVE": 35,
                ...
            }
        }
    }

    We prefer summary_metrics if available, otherwise sum daily_metrics.

    Args:
        analytics_response: Raw response from pinterest_api.get_pin_analytics().

    Returns:
        dict: Summed metrics {IMPRESSION: N, SAVE: N, PIN_CLICK: N, OUTBOUND_CLICK: N}.
    """
    summed = {metric: 0 for metric in METRICS}

    if not analytics_response:
        return summed

    # Try to extract from the "all" wrapper
    data = analytics_response.get("all", analytics_response)

    # Check for summary_metrics first (pre-summed by Pinterest)
    summary = data.get("summary_metrics")
    if summary:
        for metric in METRICS:
            summed[metric] = summary.get(metric, 0)
        return summed

    # Fall back to summing daily_metrics
    daily = data.get("daily_metrics", [])
    if daily:
        for day_data in daily:
            metrics = day_data.get("metrics", {})
            for metric in METRICS:
                summed[metric] += metrics.get(metric, 0)
        return summed

    # Alternative format: flat dict with metric names as keys, lists as values
    # e.g., {"IMPRESSION": [100, 150, ...], "SAVE": [5, 10, ...]}
    for metric in METRICS:
        values = analytics_response.get(metric)
        if isinstance(values, list):
            summed[metric] = sum(v for v in values if isinstance(v, (int, float)))
        elif isinstance(values, (int, float)):
            summed[metric] = int(values)

    return summed


def _save_analytics_snapshot(
    pin_data: dict,
    account_data: dict,
    start_date: str,
    end_date: str,
) -> Optional[Path]:
    """
    Save raw analytics data to a weekly snapshot file.

    Filename: data/analytics/YYYY-wNN-raw.json

    Args:
        pin_data: Per-pin analytics data.
        account_data: Account-level analytics data.
        start_date: Query start date.
        end_date: Query end date.

    Returns:
        Path to the saved snapshot file, or None on failure.
    """
    ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    filename = f"{iso_year}-w{iso_week:02d}-raw.json"
    snapshot_path = ANALYTICS_DIR / filename

    snapshot = {
        "generated_at": datetime.now().isoformat(),
        "date_range": {"start": start_date, "end": end_date},
        "pins_tracked": len(pin_data),
        "pin_analytics": {
            pin_id: {
                "pinterest_pin_id": data.get("pinterest_pin_id"),
                "period_metrics": data.get("period_metrics", {}),
                "query_start": data.get("query_start"),
                "query_end": data.get("query_end"),
            }
            for pin_id, data in pin_data.items()
        },
        "account_analytics": account_data,
    }

    try:
        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        logger.info("Saved analytics snapshot to %s", snapshot_path)
        return snapshot_path
    except OSError as e:
        logger.error("Failed to save analytics snapshot: %s", e)
        return None


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7

    if "--demo" in sys.argv:
        # Demo mode: show content log stats without calling the API
        print("=== Demo mode: pull_analytics ===")
        entries = load_content_log()
        print(f"Content log entries: {len(entries)}")
        trackable = [e for e in entries if e.get("pinterest_pin_id")]
        print(f"Trackable pins (have pinterest_pin_id): {len(trackable)}")

        if entries:
            entries = compute_derived_metrics(entries)
            for dim in ["pillar", "content_type", "board", "primary_keyword"]:
                agg = aggregate_by_dimension(entries, dim)
                print(f"\nAggregation by {dim}:")
                for key, metrics in sorted(agg.items()):
                    print(f"  {key}: {metrics['count']} pins, "
                          f"{metrics['impressions']} impr, "
                          f"{metrics['saves']} saves, "
                          f"save_rate={metrics['save_rate']:.4f}")
    else:
        print(f"Pulling Pinterest analytics (last {days} days)...")
        data = pull_analytics(days_back=days)
        summary = data.get("summary", {})
        print(f"\nSummary:")
        print(f"  Pins tracked: {summary.get('pins_tracked', 0)}")
        print(f"  Total impressions: {summary.get('total_impressions', 0)}")
        print(f"  Total saves: {summary.get('total_saves', 0)}")
        print(f"  Total outbound clicks: {summary.get('total_outbound_clicks', 0)}")
        print(f"  Errors: {summary.get('errors', 0)}")
