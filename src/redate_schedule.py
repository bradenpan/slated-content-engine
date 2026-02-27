"""Redate pin schedule entries to start from a given date.

Redistributes all pins across N days with 4 slots per day
(morning, afternoon, evening-1, evening-2).

Usage: python -m src.redate_schedule 2026-03-01
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.paths import DATA_DIR


def redate(start_date: str, schedule_path: Path = None, num_days: int = 7) -> None:
    """Redate all pins in the schedule starting from start_date.

    Args:
        start_date: Start date in YYYY-MM-DD format.
        schedule_path: Path to pin-schedule.json. Defaults to DATA_DIR / "pin-schedule.json".
        num_days: Number of days to spread pins across. Defaults to 7 (standard posting week).
    """
    path = schedule_path or (DATA_DIR / "pin-schedule.json")
    if not path.exists():
        print("No pin-schedule.json found, skipping redate")
        return

    schedule = json.loads(path.read_text(encoding="utf-8"))
    slots = ["morning", "afternoon", "evening-1", "evening-2"]

    start = datetime.strptime(start_date, "%Y-%m-%d").date()

    for i, pin in enumerate(schedule):
        day_offset = (i // len(slots)) % num_days
        pin["scheduled_date"] = (start + timedelta(days=day_offset)).isoformat()
        pin["scheduled_slot"] = slots[i % len(slots)]

    path.write_text(json.dumps(schedule, indent=2), encoding="utf-8")
    print(f"Redated {len(schedule)} pins across {num_days} days starting {start}")
    for d in range(num_days):
        day = start + timedelta(days=d)
        day_pins = [p for p in schedule if p["scheduled_date"] == day.isoformat()]
        print(f"  {day}: {len(day_pins)} pins")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.redate_schedule YYYY-MM-DD")
        sys.exit(1)
    redate(sys.argv[1])
