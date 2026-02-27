"""Redate pin schedule entries to start from a given date.

Redistributes all pins across 3 days with 4 slots per day
(morning, afternoon, evening-1, evening-2).

Usage: python -m src.redate_schedule 2026-03-01
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path


def redate(start_date: str, schedule_path: str = "data/pin-schedule.json") -> None:
    """Redate all pins in the schedule starting from start_date."""
    path = Path(schedule_path)
    if not path.exists():
        print("No pin-schedule.json found, skipping redate")
        return

    schedule = json.loads(path.read_text())
    slots = ["morning", "afternoon", "evening-1", "evening-2"]
    num_days = 3  # spread across 3 days

    start = datetime.strptime(start_date, "%Y-%m-%d").date()

    for i, pin in enumerate(schedule):
        day_offset = (i // len(slots)) % num_days
        pin["scheduled_date"] = (start + timedelta(days=day_offset)).isoformat()
        pin["scheduled_slot"] = slots[i % len(slots)]

    path.write_text(json.dumps(schedule, indent=2))
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
