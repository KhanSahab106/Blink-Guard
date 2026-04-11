"""
dnd.py — Do Not Disturb schedule logic.

Checks whether the current day+time falls within any DND window.
DND suppresses alert sounds but detection continues normally.
"""

import datetime
import logging
from typing import Any

logger = logging.getLogger("BlinkGuard")

DAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}


def is_dnd_active(settings: dict) -> tuple[bool, str | None]:
    """Check if DND is currently active.

    Returns:
        (is_active, end_time_str)  —  end_time_str is "HH:MM" if active, else None
    """
    if not settings.get("dnd_enabled", False):
        return False, None

    schedule: list[dict[str, Any]] = settings.get("dnd_schedule", [])
    if not schedule:
        return False, None

    now = datetime.datetime.now()
    current_day_idx = now.weekday()  # 0=Mon .. 6=Sun
    current_time = now.strftime("%H:%M")

    for rule in schedule:
        days = rule.get("days", [])
        start = rule.get("start", "")
        end = rule.get("end", "")

        if not days or not start or not end:
            continue

        # Check if current day matches
        day_matches = False
        for d in days:
            if DAY_MAP.get(d.lower()) == current_day_idx:
                day_matches = True
                break

        if not day_matches:
            continue

        # Compare times as strings (HH:MM format)
        if start <= current_time < end:
            return True, end

    return False, None


def validate_rule(rule: dict) -> str | None:
    """Validate a DND rule dict. Returns error message or None if valid."""
    days = rule.get("days", [])
    start = rule.get("start", "")
    end = rule.get("end", "")

    if not days:
        return "No days selected"
    for d in days:
        if d.lower() not in DAY_MAP:
            return f"Invalid day: {d}"
    if not start or not end:
        return "Start and end times required"
    try:
        datetime.datetime.strptime(start, "%H:%M")
        datetime.datetime.strptime(end, "%H:%M")
    except ValueError:
        return "Invalid time format (use HH:MM)"
    if start >= end:
        return "Start time must be before end time"
    return None
