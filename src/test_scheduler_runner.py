from datetime import datetime
from unittest.mock import patch

from scheduler import BackupSchedule
import scheduler_runner


def test_run_scheduled_backup_success():
    schedule = BackupSchedule(
        schedule_id="test-1",
        schedule_type="custom",
        scheduled_time="2026-09-28T18:00:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    with patch.object(scheduler_runner.BackupManager, "main") as mock_backup:
        result = scheduler_runner.run_scheduled_backup(schedule)

    assert result is True

    mock_backup.assert_called_once_with(
        source_dir="C:\\Data",
        target_dir="C:\\Backup",
    )


def test_run_scheduled_backup_failure():
    schedule = BackupSchedule(
        schedule_id="test-2",
        schedule_type="custom",
        scheduled_time="2026-09-28T18:00:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    with patch.object(
        scheduler_runner.BackupManager,
        "main",
        side_effect=Exception("Backup failed"),
    ):
        result = scheduler_runner.run_scheduled_backup(schedule)

    assert result is False


def test_check_schedules_runs_due_backup():
    schedule = BackupSchedule(
        schedule_id="test-3",
        schedule_type="custom",
        scheduled_time="2026-09-28T18:00:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    now = datetime(2026, 9, 28, 19, 0)

    with patch.object(
        scheduler_runner,
        "load_schedules",
        return_value=[schedule],
    ), patch.object(
        scheduler_runner,
        "run_scheduled_backup",
        return_value=True,
    ) as mock_backup, patch.object(
        scheduler_runner,
        "save_schedules",
    ) as mock_save:

        result = scheduler_runner.check_schedules(now)

    assert result == 1
    assert schedule.last_run == now.isoformat()
    mock_backup.assert_called_once_with(schedule)
    mock_save.assert_called_once()


def test_check_schedules_does_not_run_future_backup():
    schedule = BackupSchedule(
        schedule_id="test-4",
        schedule_type="custom",
        scheduled_time="2026-09-28T20:00:00",
        source="C:\\Data",
        target="C:\\Backup",
    )

    now = datetime(2026, 9, 28, 19, 0)

    with patch.object(
        scheduler_runner,
        "load_schedules",
        return_value=[schedule],
    ), patch.object(
        scheduler_runner,
        "run_scheduled_backup",
    ) as mock_backup:

        result = scheduler_runner.check_schedules(now)

    assert result == 0
    mock_backup.assert_not_called()