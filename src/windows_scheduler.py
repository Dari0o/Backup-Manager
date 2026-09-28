"""
Windows Task Scheduler integration for Backup Manager.

Provides helpers for registering and removing the Backup Manager
scheduled-backup runner with Windows Task Scheduler.
"""

import subprocess
import sys
from pathlib import Path


TASK_NAME = "BackupManagerScheduler"


def get_runner_path() -> Path:
    """Return the absolute path to scheduler_runner.py."""

    return Path(__file__).resolve().parent / "scheduler_runner.py"


def create_task() -> bool:
    """
    Register the scheduler runner with Windows Task Scheduler.

    The task runs when the current user logs into Windows.
    """

    runner_path = get_runner_path()

    command = [
        "schtasks",
        "/Create",
        "/TN",
        TASK_NAME,
        "/TR",
        f'"{sys.executable}" "{runner_path}"',
        "/SC",
        "ONLOGON",
        "/F",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


def remove_task() -> bool:
    """Remove the Backup Manager scheduler task."""

    command = [
        "schtasks",
        "/Delete",
        "/TN",
        TASK_NAME,
        "/F",
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


def task_exists() -> bool:
    """Check whether the Backup Manager scheduler task exists."""

    command = [
        "schtasks",
        "/Query",
        "/TN",
        TASK_NAME,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    return result.returncode == 0


if __name__ == "__main__":
    if create_task():
        print(f"Created Windows task: {TASK_NAME}")
    else:
        print(f"Failed to create Windows task: {TASK_NAME}")