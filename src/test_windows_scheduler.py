from unittest.mock import patch

import windows_scheduler


def test_get_runner_path():
    path = windows_scheduler.get_runner_path()

    assert path.name == "scheduler_runner.py"
    assert path.parent.name == "src"


@patch("windows_scheduler.subprocess.run")
def test_create_task(mock_run):
    mock_run.return_value.returncode = 0

    result = windows_scheduler.create_task()

    assert result is True
    mock_run.assert_called_once()

    command = mock_run.call_args.args[0]

    assert command[0] == "schtasks"
    assert "/Create" in command
    assert windows_scheduler.TASK_NAME in command
    assert "/SC" in command
    assert "ONLOGON" in command


@patch("windows_scheduler.subprocess.run")
def test_create_task_failure(mock_run):
    mock_run.return_value.returncode = 1

    result = windows_scheduler.create_task()

    assert result is False


@patch("windows_scheduler.subprocess.run")
def test_remove_task(mock_run):
    mock_run.return_value.returncode = 0

    result = windows_scheduler.remove_task()

    assert result is True

    command = mock_run.call_args.args[0]

    assert command[0] == "schtasks"
    assert "/Delete" in command
    assert windows_scheduler.TASK_NAME in command


@patch("windows_scheduler.subprocess.run")
def test_task_exists(mock_run):
    mock_run.return_value.returncode = 0

    result = windows_scheduler.task_exists()

    assert result is True


@patch("windows_scheduler.subprocess.run")
def test_task_does_not_exist(mock_run):
    mock_run.return_value.returncode = 1

    result = windows_scheduler.task_exists()

    assert result is False