import json
from pathlib import Path

import pytest

import scheduler


@pytest.mark.parametrize(
    "interval, unit, expected",
    [
        (1, "days", ["/SC", "DAILY", "/MO", "1"]),
        (50, "days", ["/SC", "DAILY", "/MO", "50"]),
        (3, "months", ["/SC", "MONTHLY", "/MO", "3", "/D", "1"]),
    ],
)
def test_task_schedule_supports_day_and_month_intervals(interval, unit, expected):
    assert scheduler.task_schedule(interval, unit) == expected


@pytest.mark.parametrize(
    "interval, unit",
    [(0, "days"), (-1, "months"), (366, "days"), (13, "months"), (1, "weeks")],
)
def test_task_schedule_rejects_invalid_intervals(interval, unit):
    with pytest.raises(ValueError):
        scheduler.task_schedule(interval, unit)


@pytest.mark.parametrize(
    "time, expected",
    [("9:05", "09:05"), ("23:59", "23:59"), ("00:00", "00:00")],
)
def test_validate_schedule_time_normalizes_valid_time(time, expected):
    assert scheduler.validate_schedule_time(time) == expected


@pytest.mark.parametrize("time", ["24:00", "12:60", "noon", "12"])
def test_validate_schedule_time_rejects_invalid_time(time):
    with pytest.raises(ValueError):
        scheduler.validate_schedule_time(time)


def test_schedule_config_protects_password_and_restores_it(tmp_path, monkeypatch):
    config_path = tmp_path / "scheduled_backup.json"
    monkeypatch.setattr(scheduler, "_protect_password", lambda password: "protected-value")
    monkeypatch.setattr(scheduler, "_unprotect_password", lambda value: "decoded-password")

    scheduler.save_schedule_config(
        {"source": "C:\\Data", "password": "plain-password"},
        config_path,
    )

    saved_data = json.loads(config_path.read_text(encoding="utf-8"))
    assert "plain-password" not in config_path.read_text(encoding="utf-8")
    assert saved_data["protected_password"] == "protected-value"
    assert scheduler.load_schedule_config(config_path) == {
        "source": "C:\\Data",
        "password": "decoded-password",
    }


def test_build_task_action_uses_config_argument_without_credentials():
    action = scheduler.build_task_action(
        config_path=Path(r"C:\Users\Example User\AppData\scheduled_backup.json"),
        script_path=Path(r"C:\Program Files\Backup Manager\BackupManager.py"),
        executable=r"C:\Python\python.exe",
    )

    assert "--console" in action
    assert "--scheduled-config" in action
    assert "scheduled_backup.json" in action
    assert "password" not in action.lower()


def test_build_task_action_uses_short_id_for_task_scheduler_arguments():
    schedule_id = "1234567890abcdef1234567890abcdef"
    action = scheduler.build_task_action(
        config_path=Path(r"C:\Users\Example User\AppData\Local\BackupManager\scheduled_backups\1234567890abcdef1234567890abcdef.json"),
        script_path=Path(r"C:\Users\Example User\Documents\Backup Manager\BackupManager.py"),
        executable=r"C:\Users\Example User\AppData\Local\Programs\Python\Python313\python.exe",
        schedule_id=schedule_id,
    )

    assert "--scheduled-id" in action
    assert schedule_id in action
    assert "scheduled_backups" not in action
    assert len(action) < 256


def test_build_task_action_uses_console_python_when_gui_uses_pythonw(tmp_path):
    pythonw_path = tmp_path / "pythonw.exe"
    python_path = tmp_path / "python.exe"
    pythonw_path.touch()
    python_path.touch()

    action = scheduler.build_task_action(
        config_path=tmp_path / "config.json",
        script_path=tmp_path / "BackupManager.py",
        executable=str(pythonw_path),
        schedule_id="1234567890abcdef1234567890abcdef",
    )

    assert str(python_path) in action
    assert "pythonw.exe" not in action


def test_create_windows_task_persists_config_and_registers_task(tmp_path, monkeypatch):
    config_path = tmp_path / "scheduled_backup.json"
    captured = {}
    monkeypatch.setattr(scheduler.sys, "platform", "win32")
    monkeypatch.setattr(scheduler, "SCHEDULE_CONFIG", config_path)
    monkeypatch.setattr(
        scheduler,
        "build_task_action",
        lambda path: f"python BackupManager.py --scheduled-config {path}",
    )
    monkeypatch.setattr(
        scheduler,
        "_run_schtasks",
        lambda arguments: captured.setdefault("arguments", arguments) or "SUCCESS",
    )

    scheduler.create_windows_task(
        {"source": "C:\\Data", "target": "D:\\Backups", "password": ""},
        50,
        "days",
        "9:05",
    )

    assert config_path.exists()
    assert captured["arguments"][:6] == [
        "/Create",
        "/TN",
        scheduler.TASK_NAME,
        "/SC",
        "DAILY",
        "/MO",
    ]
    assert captured["arguments"][7:9] == ["/ST", "09:05"]
    assert "/IT" in captured["arguments"]


def test_create_windows_task_restores_config_when_registration_fails(tmp_path, monkeypatch):
    config_path = tmp_path / "scheduled_backup.json"
    config_path.write_text('{"existing": true}', encoding="utf-8")
    monkeypatch.setattr(scheduler.sys, "platform", "win32")
    monkeypatch.setattr(scheduler, "SCHEDULE_CONFIG", config_path)
    monkeypatch.setattr(scheduler, "build_task_action", lambda path: "backup command")

    def fail_registration(arguments):
        raise RuntimeError("Task Scheduler unavailable")

    monkeypatch.setattr(scheduler, "_run_schtasks", fail_registration)

    with pytest.raises(RuntimeError, match="Task Scheduler unavailable"):
        scheduler.create_windows_task(
            {"source": "C:\\Data", "target": "D:\\Backups", "password": ""},
            3,
            "months",
            "09:00",
        )

    assert config_path.read_text(encoding="utf-8") == '{"existing": true}'


def test_scheduled_backups_can_be_listed_and_deleted(tmp_path, monkeypatch):
    task_commands = []
    monkeypatch.setattr(scheduler.sys, "platform", "win32")
    monkeypatch.setattr(scheduler, "SCHEDULES_DIR", tmp_path / "configs")
    monkeypatch.setattr(scheduler, "SCHEDULES_MANIFEST", tmp_path / "scheduled_backups.json")
    monkeypatch.setattr(scheduler, "_protect_password", lambda password: "protected-value")
    monkeypatch.setattr(
        scheduler,
        "build_task_action",
        lambda config_path, schedule_id=None: f"python --scheduled-id {schedule_id}",
    )
    monkeypatch.setattr(
        scheduler,
        "_run_schtasks",
        lambda arguments: task_commands.append(arguments) or "SUCCESS",
    )

    schedule_id = scheduler.create_scheduled_backup(
        {
            "source": "C:\\Data",
            "target": "D:\\Backups",
            "destination": "Local",
            "compression": 3,
            "password": "",
        },
        3,
        "months",
        "09:15",
    )

    schedules = scheduler.list_scheduled_backups()
    assert len(schedules) == 1
    assert schedules[0]["id"] == schedule_id
    assert schedules[0]["time"] == "09:15"
    assert schedules[0]["compression"] == 3
    assert task_commands[0][0:3] == ["/Create", "/TN", schedules[0]["task_name"]]
    assert "--scheduled-id" in task_commands[0][task_commands[0].index("/TR") + 1]
    assert schedule_id in task_commands[0][task_commands[0].index("/TR") + 1]
    assert "/IT" in task_commands[0]

    scheduler.delete_scheduled_backup(schedule_id)

    assert scheduler.list_scheduled_backups() == []
    assert task_commands[1] == ["/Delete", "/TN", schedules[0]["task_name"], "/F"]
    assert not Path(schedules[0]["config_path"]).exists()


def test_scheduled_backup_list_includes_previous_single_task(tmp_path, monkeypatch):
    legacy_config = tmp_path / "scheduled_backup.json"
    legacy_config.write_text(
        json.dumps(
            {
                "source": "C:\\Data",
                "target": "D:\\Backups",
                "destination": "Local",
                "mirror": True,
            }
        ),
        encoding="utf-8",
    )
    task_xml = """<?xml version="1.0"?>
    <Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
      <Triggers>
        <CalendarTrigger>
          <StartBoundary>2026-11-16T09:30:00</StartBoundary>
          <ScheduleByMonth>
            <MonthsInterval>3</MonthsInterval>
            <DaysOfMonth><Day>1</Day></DaysOfMonth>
          </ScheduleByMonth>
        </CalendarTrigger>
      </Triggers>
    </Task>"""
    monkeypatch.setattr(scheduler, "SCHEDULE_CONFIG", legacy_config)
    monkeypatch.setattr(scheduler, "SCHEDULES_MANIFEST", tmp_path / "missing.json")
    monkeypatch.setattr(scheduler, "_run_schtasks", lambda arguments, **kwargs: task_xml)

    schedules = scheduler.list_scheduled_backups()

    assert len(schedules) == 1
    assert schedules[0]["id"] == "legacy"
    assert schedules[0]["interval"] == 3
    assert schedules[0]["unit"] == "months"
    assert schedules[0]["time"] == "09:30"
    assert schedules[0]["mirror"] is True


def test_repair_scheduled_backup_rewrites_only_action_and_preserves_task_triggers(tmp_path, monkeypatch):
    schedule_id = "1234567890abcdef1234567890abcdef"
    schedule = {
        "id": schedule_id,
        "task_name": f"{scheduler.TASK_NAME} {schedule_id[:8]}",
        "config_path": str(tmp_path / "configs" / f"{schedule_id}.json"),
        "interval": 50,
        "unit": "days",
        "time": "09:05",
        "source": "C:\\Data",
        "target": "D:\\Backups",
        "destination": "Local",
        "mirror": False,
        "ignore_excludes": False,
        "compression": None,
        "sevenzip": False,
    }
    task_xml = f"""<?xml version="1.0"?>
    <Task xmlns="{scheduler.TASK_NAMESPACE}">
      <Principals><Principal><LogonType>InteractiveToken</LogonType></Principal></Principals>
      <Triggers><CalendarTrigger><StartBoundary>2026-01-01T09:05:00</StartBoundary>
        <ScheduleByDay><DaysInterval>50</DaysInterval></ScheduleByDay>
      </CalendarTrigger></Triggers>
      <Actions><Exec><Command>python.exe</Command>
        <Arguments>BackupManager.py --console --scheduled-config truncated.json</Arguments>
      </Exec></Actions>
    </Task>"""
    calls = []

    monkeypatch.setattr(scheduler, "APP_DATA_DIR", tmp_path)
    monkeypatch.setattr(scheduler, "SCHEDULES_DIR", tmp_path / "configs")
    monkeypatch.setattr(scheduler, "SCHEDULES_MANIFEST", tmp_path / "scheduled_backups.json")
    monkeypatch.setattr(scheduler, "SCHEDULE_CONFIG", tmp_path / "legacy.json")
    monkeypatch.setattr(scheduler, "_read_schedules", lambda: [schedule])

    def run_schtasks(arguments, log_output=True):
        if arguments[0] == "/Query":
            return task_xml
        calls.append(arguments)
        migrated_xml = Path(arguments[arguments.index("/XML") + 1]).read_text(encoding="utf-16")
        root = __import__("xml.etree.ElementTree", fromlist=["ElementTree"]).fromstring(migrated_xml)
        tags = lambda name: [item.text for item in root.iter() if item.tag.rsplit("}", 1)[-1] == name]
        assert tags("LogonType") == ["InteractiveToken"]
        assert tags("StartBoundary") == ["2026-01-01T09:05:00"]
        assert tags("DaysInterval") == ["50"]
        assert "--scheduled-id" in tags("Arguments")[0]
        assert schedule_id in tags("Arguments")[0]
        return "SUCCESS"

    monkeypatch.setattr(scheduler, "_run_schtasks", run_schtasks)

    assert scheduler.repair_scheduled_backups() == 1
    assert calls[0][:3] == ["/Create", "/TN", schedule["task_name"]]
