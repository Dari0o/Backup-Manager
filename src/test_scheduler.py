from datetime import datetime

from scheduler import BackupSchedule, is_due


def test_custom_schedule_is_due():
    schedule = BackupSchedule(
        schedule_id="custom-1",
        schedule_type="custom",
        scheduled_time="2026-09-28T18:00:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    now = datetime(2026, 9, 28, 19, 0)

    assert is_due(schedule, now) is True


def test_custom_schedule_not_due_before_time():
    schedule = BackupSchedule(
        schedule_id="custom-2",
        schedule_type="custom",
        scheduled_time="2026-09-28T18:00:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    now = datetime(2026, 9, 28, 17, 0)

    assert is_due(schedule, now) is False


def test_weekly_schedule_is_due():
    # Monday = 0
    schedule = BackupSchedule(
        schedule_id="weekly-1",
        schedule_type="weekly",
        scheduled_time="0|18:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    now = datetime(2026, 9, 28, 19, 0)

    assert is_due(schedule, now) is True


def test_weekly_schedule_missed_backup_is_due():
    # Scheduled Monday at 18:00.
    # PC starts Tuesday, so the missed Monday backup should run.
    schedule = BackupSchedule(
        schedule_id="weekly-2",
        schedule_type="weekly",
        scheduled_time="0|18:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    now = datetime(2026, 9, 29, 19, 0)

    assert is_due(schedule, now) is True


def test_weekly_schedule_already_run_is_not_due():
    schedule = BackupSchedule(
        schedule_id="weekly-3",
        schedule_type="weekly",
        scheduled_time="0|18:00",
        source="C:\\Data",
        target="C:\\Backup",
        last_run="2026-09-28T19:00:00",
    )

    now = datetime(2026, 9, 29, 19, 0)

    assert is_due(schedule, now) is False


def test_monthly_schedule_is_due():
    schedule = BackupSchedule(
        schedule_id="monthly-1",
        schedule_type="monthly",
        scheduled_time="28|18:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    now = datetime(2026, 9, 28, 19, 0)

    assert is_due(schedule, now) is True


def test_monthly_schedule_missed_backup_is_due():
    # Scheduled on the 28th.
    # PC starts on the 29th, so the missed backup should run.
    schedule = BackupSchedule(
        schedule_id="monthly-2",
        schedule_type="monthly",
        scheduled_time="28|18:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    now = datetime(2026, 9, 29, 19, 0)

    assert is_due(schedule, now) is True


def test_disabled_schedule_is_not_due():
    schedule = BackupSchedule(
        schedule_id="disabled-1",
        schedule_type="custom",
        scheduled_time="2026-09-28T18:00:00",
        source="C:\\Data",
        target="C:\\Backup",
        enabled=False,
    )

    now = datetime(2026, 9, 28, 19, 0)

    assert is_due(schedule, now) is False


def test_already_run_schedule_is_not_due():
    schedule = BackupSchedule(
        schedule_id="custom-3",
        schedule_type="custom",
        scheduled_time="2026-09-28T18:00:00",
        source="C:\\Data",
        target="C:\\Backup",
        last_run="2026-09-28T18:30:00",
    )

    now = datetime(2026, 9, 28, 19, 0)

    assert is_due(schedule, now) is False