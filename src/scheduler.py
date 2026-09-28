"""
Scheduled backup support for Backup Manager.

This module stores backup schedules in a JSON file and provides
functions for creating, loading, removing, and checking schedules.
"""

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


SCHEDULE_FILE = Path(__file__).resolve().parent / "schedules.json"


@dataclass
class BackupSchedule:
    """Configuration for one scheduled backup."""

    schedule_id: str
    schedule_type: str
    scheduled_time: str
    source: str
    target: str
    enabled: bool = True
    last_run: Optional[str] = None


def load_schedules() -> list[BackupSchedule]:
    """Load saved schedules from the JSON configuration file."""

    if not SCHEDULE_FILE.exists():
        return []

    try:
        with SCHEDULE_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (json.JSONDecodeError, OSError):
        return []

    return [BackupSchedule(**item) for item in data]


def save_schedules(schedules: list[BackupSchedule]) -> None:
    """Save all schedules to the JSON configuration file."""

    SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with SCHEDULE_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            [asdict(schedule) for schedule in schedules],
            file,
            indent=4,
        )


def add_schedule(schedule: BackupSchedule) -> None:
    """Add a new backup schedule."""

    schedules = load_schedules()
    schedules.append(schedule)
    save_schedules(schedules)


def remove_schedule(schedule_id: str) -> bool:
    """Remove a schedule by ID."""

    schedules = load_schedules()

    updated = [
        schedule
        for schedule in schedules
        if schedule.schedule_id != schedule_id
    ]

    if len(updated) == len(schedules):
        return False

    save_schedules(updated)
    return True


def get_schedule(schedule_id: str) -> Optional[BackupSchedule]:
    """Return a schedule by ID, if it exists."""

    for schedule in load_schedules():
        if schedule.schedule_id == schedule_id:
            return schedule

    return None


def parse_datetime(value: str) -> datetime:
    """Convert an ISO datetime string into a datetime object."""

    return datetime.fromisoformat(value)


def _weekly_occurrence(
    schedule: BackupSchedule,
    reference: datetime,
) -> datetime:
    """Return the most recent weekly occurrence at or before reference."""

    weekday, time_value = schedule.scheduled_time.split("|", 1)

    hour, minute = map(int, time_value.split(":"))
    weekday = int(weekday)

    days_since_schedule = (reference.weekday() - weekday) % 7

    occurrence = reference - timedelta(days=days_since_schedule)

    return occurrence.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )


def _monthly_occurrence(
    schedule: BackupSchedule,
    reference: datetime,
) -> Optional[datetime]:
    """Return the most recent monthly occurrence at or before reference."""

    day, time_value = schedule.scheduled_time.split("|", 1)

    hour, minute = map(int, time_value.split(":"))
    day = int(day)

    if reference.day >= day:
        try:
            return reference.replace(
                day=day,
                hour=hour,
                minute=minute,
                second=0,
                microsecond=0,
            )
        except ValueError:
            return None

    # The scheduled day has not happened this month.
    # Check the previous month instead.
    first_day = reference.replace(
        day=1,
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    previous_month = first_day - timedelta(days=1)

    try:
        return previous_month.replace(day=day)
    except ValueError:
        return None


def is_due(
    schedule: BackupSchedule,
    now: Optional[datetime] = None,
) -> bool:
    """
    Check whether a schedule is currently due.

    For recurring schedules, a missed occurrence is considered due
    when the application starts again.
    """

    if not schedule.enabled:
        return False

    if now is None:
        now = datetime.now()

    last_run = None

    if schedule.last_run:
        last_run = parse_datetime(schedule.last_run)

    # ---------------------------------------------------------
    # Custom schedule
    # Format:
    # 2026-09-28T18:00:00
    # ---------------------------------------------------------
    if schedule.schedule_type == "custom":

        scheduled = parse_datetime(schedule.scheduled_time)

        return (
            scheduled <= now
            and (last_run is None or last_run < scheduled)
        )

    # ---------------------------------------------------------
    # Weekly schedule
    # Format:
    # weekday|HH:MM
    #
    # Monday = 0
    # Tuesday = 1
    # ...
    # Sunday = 6
    # ---------------------------------------------------------
    if schedule.schedule_type == "weekly":

        scheduled = _weekly_occurrence(
            schedule,
            now,
        )

        return (
            scheduled <= now
            and (last_run is None or last_run < scheduled)
        )

    # ---------------------------------------------------------
    # Monthly schedule
    # Format:
    # day|HH:MM
    # ---------------------------------------------------------
    if schedule.schedule_type == "monthly":

        scheduled = _monthly_occurrence(
            schedule,
            now,
        )

        if scheduled is None:
            return False

        return (
            scheduled <= now
            and (last_run is None or last_run < scheduled)
        )

    return False