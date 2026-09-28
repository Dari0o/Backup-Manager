"""
Scheduler runner for Backup Manager.

Checks saved schedules and runs backups when they are due.
"""

import logging
import time
from datetime import datetime

import BackupManager
from scheduler import (
    BackupSchedule,
    is_due,
    load_schedules,
    save_schedules,
)


logger = logging.getLogger(__name__)


def run_scheduled_backup(schedule: BackupSchedule) -> bool:
    """
    Run a backup for one scheduled backup configuration.

    Returns True when the backup starts successfully.
    Returns False when an error occurs.
    """

    logger.info(
        "Starting scheduled backup: %s -> %s",
        schedule.source,
        schedule.target,
    )

    try:
        BackupManager.main(
            source_dir=schedule.source,
            target_dir=schedule.target,
        )

        logger.info(
            "Scheduled backup completed: %s",
            schedule.schedule_id,
        )

        return True

    except SystemExit as error:
        logger.error(
            "Scheduled backup exited with status %s: %s",
            error.code,
            schedule.schedule_id,
        )
        return False

    except Exception:
        logger.exception(
            "Scheduled backup failed: %s",
            schedule.schedule_id,
        )
        return False


def check_schedules(now: datetime | None = None) -> int:
    """
    Check all saved schedules and run the backups that are due.

    Returns the number of successfully completed backups.
    """

    if now is None:
        now = datetime.now()

    schedules = load_schedules()
    successful_backups = 0
    schedules_changed = False

    for schedule in schedules:

        if not is_due(schedule, now):
            continue

        logger.info(
            "Schedule is due: %s",
            schedule.schedule_id,
        )

        if run_scheduled_backup(schedule):

            schedule.last_run = now.isoformat()
            successful_backups += 1
            schedules_changed = True

    if schedules_changed:
        save_schedules(schedules)

    return successful_backups


def run_scheduler(interval_seconds: int = 60) -> None:
    """
    Continuously check schedules.

    The scheduler checks once every interval_seconds.
    """

    logger.info("Backup scheduler started.")

    while True:

        try:
            check_schedules()

        except Exception:
            logger.exception("Unexpected scheduler error.")

        time.sleep(interval_seconds)


if __name__ == "__main__":
    BackupManager.setup_logger()

    run_scheduler()