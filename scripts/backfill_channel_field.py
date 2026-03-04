"""Backfill channel field on existing content-log.jsonl entries.

One-time migration script for Phase 8. Adds "channel": "pinterest" to any
entry that doesn't already have a channel field.

Usage:
    python scripts/backfill_channel_field.py
    python scripts/backfill_channel_field.py --dry-run
"""
import argparse
import sys
from pathlib import Path

# Add project root to path so we can import src modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.shared.utils.content_log import load_content_log, save_content_log


def backfill(dry_run: bool = False) -> None:
    entries = load_content_log()
    if not entries:
        print("Content log is empty or missing. Nothing to backfill.")
        return

    updated = 0
    for entry in entries:
        if "channel" not in entry:
            entry["channel"] = "pinterest"
            updated += 1

    print(f"Entries total: {len(entries)}, needing backfill: {updated}")

    if updated == 0:
        print("All entries already have a channel field. No changes needed.")
        return

    if dry_run:
        print("Dry run — no changes written.")
        return

    save_content_log(entries)
    print(f"Backfilled {updated} entries with channel='pinterest'.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill channel field in content log")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run)
