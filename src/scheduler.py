import base64
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from logger import APP_DATA_DIR, setup_logger


TASK_NAME = "Backup Manager Scheduled Backup"
SCHEDULE_CONFIG = APP_DATA_DIR / "scheduled_backup.json"
SCHEDULES_DIR = APP_DATA_DIR / "scheduled_backups"
SCHEDULES_MANIFEST = APP_DATA_DIR / "scheduled_backups.json"
logger = setup_logger(__name__)
TASK_NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"


def task_schedule(interval: int, unit: str) -> list[str]:
    """Translate a recurrence interval into schtasks schedule arguments."""
    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 1:
        raise ValueError("The schedule interval must be a positive whole number.")

    normalized_unit = unit.strip().lower()
    if normalized_unit in {"day", "days"}:
        if interval > 365:
            raise ValueError("Daily intervals must be between 1 and 365 days.")
        return ["/SC", "DAILY", "/MO", str(interval)]
    if normalized_unit in {"month", "months"}:
        if interval > 12:
            raise ValueError("Monthly intervals must be between 1 and 12 months.")
        return ["/SC", "MONTHLY", "/MO", str(interval), "/D", "1"]
    raise ValueError("The schedule unit must be days or months.")


def _protect_password(password: str) -> str:
    if os.name != "nt":
        raise OSError("Scheduled password protection is available only on Windows.")

    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    crypt32 = ctypes.WinDLL("Crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("Kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    raw_password = password.encode("utf-8")
    input_buffer = ctypes.create_string_buffer(raw_password)
    input_blob = DataBlob(
        len(raw_password),
        ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    output_blob = DataBlob()
    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob), None, None, None, None, 0x1, ctypes.byref(output_blob)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        kernel32.LocalFree(output_blob.pbData)


def _unprotect_password(encrypted_password: str) -> str:
    if os.name != "nt":
        raise OSError("Scheduled password protection is available only on Windows.")

    from ctypes import wintypes

    class DataBlob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    crypt32 = ctypes.WinDLL("Crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("Kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    encrypted = base64.b64decode(encrypted_password, validate=True)
    input_buffer = ctypes.create_string_buffer(encrypted)
    input_blob = DataBlob(
        len(encrypted),
        ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    output_blob = DataBlob()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob), None, None, None, None, 0x1, ctypes.byref(output_blob)
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        raw_password = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return raw_password.decode("utf-8")
    finally:
        kernel32.LocalFree(output_blob.pbData)


def save_schedule_config(config: dict[str, Any], path: Path = SCHEDULE_CONFIG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stored_config = dict(config)
    password = stored_config.pop("password", "")
    stored_config["protected_password"] = _protect_password(password) if password else None
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(stored_config, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def load_schedule_config(path: Path = SCHEDULE_CONFIG) -> dict[str, Any]:
    path = Path(path)
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Scheduled backup configuration must be a JSON object.")
    protected_password = config.pop("protected_password", None)
    config["password"] = _unprotect_password(protected_password) if protected_password else ""
    return config


def _console_executable(executable: str | None = None) -> str:
    executable = executable or sys.executable
    if Path(executable).name.lower() == "pythonw.exe":
        console_executable = Path(executable).with_name("python.exe")
        if not console_executable.is_file():
            raise FileNotFoundError(f"Console Python executable was not found: {console_executable}")
        return str(console_executable)
    return executable


def build_task_action(
    config_path: Path = SCHEDULE_CONFIG,
    script_path: Path | None = None,
    executable: str | None = None,
    schedule_id: str | None = None,
) -> str:
    """Build a quoted command that runs a saved scheduled backup."""
    executable = _console_executable(executable)
    script_path = script_path or Path(__file__).with_name("BackupManager.py")

    command = [executable]
    if not getattr(sys, "frozen", False):
        command.append(str(script_path))
    if schedule_id is not None:
        command.extend(("--console", "--scheduled-id", schedule_id))
    else:
        command.extend(("--console", "--scheduled-config", str(config_path)))
    return subprocess.list2cmdline(command)


def scheduled_config_path(schedule_id: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", schedule_id):
        raise ValueError("Invalid scheduled backup identifier.")
    return SCHEDULES_DIR / f"{schedule_id}.json"


def _task_action_elements(task_xml: ET.Element) -> tuple[ET.Element, ET.Element]:
    command = next((element for element in task_xml.iter() if element.tag.rsplit("}", 1)[-1] == "Command"), None)
    arguments = next((element for element in task_xml.iter() if element.tag.rsplit("}", 1)[-1] == "Arguments"), None)
    if command is None or arguments is None:
        raise ValueError("The scheduled task does not contain a supported executable action.")
    return command, arguments


def _task_launch_parts(schedule: dict[str, Any]) -> tuple[str, str]:
    executable = _console_executable()
    script_path = Path(__file__).with_name("BackupManager.py")
    arguments = []
    if not getattr(sys, "frozen", False):
        arguments.append(str(script_path))
    arguments.append("--console")
    schedule_id = schedule.get("id")
    if schedule_id == "legacy":
        arguments.extend(("--scheduled-config", str(SCHEDULE_CONFIG)))
    else:
        scheduled_config_path(str(schedule_id))
        arguments.extend(("--scheduled-id", str(schedule_id)))
    return executable, subprocess.list2cmdline(arguments)


def _rewrite_task_action(schedule: dict[str, Any], task_xml_text: str) -> None:
    task_xml = ET.fromstring(task_xml_text)
    command_element, arguments_element = _task_action_elements(task_xml)
    executable, arguments = _task_launch_parts(schedule)
    command_element.text = executable
    arguments_element.text = arguments
    ET.register_namespace("", TASK_NAMESPACE)

    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=".xml",
            prefix="scheduled_task_",
            dir=APP_DATA_DIR,
            delete=False,
        ) as task_file:
            temporary_path = Path(task_file.name)
            task_file.write(ET.tostring(task_xml, encoding="utf-16", xml_declaration=True))
        _run_schtasks(
            [
                "/Create",
                "/TN",
                str(schedule["task_name"]),
                "/XML",
                str(temporary_path),
                "/F",
            ]
        )
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def repair_scheduled_backups() -> int:
    """Replace old oversized task commands without changing their trigger settings."""
    if sys.platform != "win32":
        return 0

    schedules = _read_schedules()
    legacy_schedule = _read_legacy_schedule()
    if legacy_schedule is not None:
        schedules.append(legacy_schedule)

    repaired = 0
    for schedule in schedules:
        task_name = schedule.get("task_name")
        if not task_name:
            logger.error("Skipping scheduled backup with no task name: %s", schedule.get("id"))
            continue
        try:
            task_xml_text = _run_schtasks(["/Query", "/TN", task_name, "/XML"], log_output=False)
            task_xml = ET.fromstring(task_xml_text)
            _, current_arguments = _task_action_elements(task_xml)
            if schedule.get("id") != "legacy" and "--scheduled-id" in (current_arguments.text or ""):
                continue
            _rewrite_task_action(schedule, task_xml_text)
        except (
            OSError,
            RuntimeError,
            ValueError,
            ET.ParseError,
            KeyError,
            TypeError,
            subprocess.SubprocessError,
        ):
            logger.exception("Could not repair scheduled task '%s'.", task_name)
            continue
        logger.info("Updated scheduled task '%s' to use a complete configuration argument.", task_name)
        repaired += 1
    return repaired


def validate_schedule_time(schedule_time: str) -> str:
    try:
        hour_text, minute_text = schedule_time.split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    except (AttributeError, ValueError):
        raise ValueError("Enter the schedule time in 24-hour HH:MM format.") from None
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Enter the schedule time in 24-hour HH:MM format.")
    return f"{hour:02d}:{minute:02d}"


def _run_schtasks(arguments: list[str], log_output: bool = True) -> str:
    executable = shutil.which("schtasks.exe") or shutil.which("schtasks")
    if not executable:
        raise FileNotFoundError("Windows Task Scheduler utility (schtasks.exe) was not found.")
    logger.info("Running Windows Task Scheduler command: %s", " ".join(arguments))
    result = subprocess.run(
        [executable, *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if log_output and result.stdout.strip():
        logger.info("Task Scheduler: %s", result.stdout.strip())
    if result.returncode:
        details = result.stderr.strip() or result.stdout.strip() or "No error details were returned."
        logger.error("Task Scheduler command failed (exit %s): %s", result.returncode, details)
        raise RuntimeError(f"Task Scheduler failed: {details}")
    return result.stdout.strip()


def _read_schedules() -> list[dict[str, Any]]:
    if not SCHEDULES_MANIFEST.exists():
        return []
    schedules = json.loads(SCHEDULES_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(schedules, list) or not all(isinstance(item, dict) for item in schedules):
        raise ValueError(f"Invalid scheduled backup list in {SCHEDULES_MANIFEST}.")
    return schedules


def _write_schedules(schedules: list[dict[str, Any]]) -> None:
    SCHEDULES_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = SCHEDULES_MANIFEST.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(schedules, indent=2), encoding="utf-8")
    temporary_path.replace(SCHEDULES_MANIFEST)


def _read_legacy_schedule() -> dict[str, Any] | None:
    if not SCHEDULE_CONFIG.exists():
        return None

    config = json.loads(SCHEDULE_CONFIG.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"Invalid scheduled backup configuration in {SCHEDULE_CONFIG}.")
    task_xml = ET.fromstring(_run_schtasks(["/Query", "/TN", TASK_NAME, "/XML"], log_output=False))
    local_tag = lambda element: element.tag.rsplit("}", 1)[-1]

    start_boundary = next(
        (element.text for element in task_xml.iter() if local_tag(element) == "StartBoundary"),
        None,
    )
    schedule_time = start_boundary.rsplit("T", 1)[-1][:5] if start_boundary and "T" in start_boundary else None
    schedule_by_day = next(
        (element for element in task_xml.iter() if local_tag(element) == "ScheduleByDay"),
        None,
    )
    schedule_by_month = next(
        (element for element in task_xml.iter() if local_tag(element) == "ScheduleByMonth"),
        None,
    )
    if schedule_by_day is not None:
        interval_element = next(
            (element for element in schedule_by_day.iter() if local_tag(element) == "DaysInterval"),
            None,
        )
        unit = "days"
    elif schedule_by_month is not None:
        interval_element = next(
            (element for element in schedule_by_month.iter() if local_tag(element) == "MonthsInterval"),
            None,
        )
        unit = "months"
    else:
        raise ValueError("The existing Backup Manager task has an unsupported recurrence.")

    if not schedule_time or interval_element is None or not interval_element.text:
        raise ValueError("Could not read the recurrence time from the existing Backup Manager task.")

    return {
        "id": "legacy",
        "task_name": TASK_NAME,
        "config_path": str(SCHEDULE_CONFIG),
        "interval": int(interval_element.text),
        "unit": unit,
        "time": schedule_time,
        "source": config.get("source", ""),
        "target": config.get("target", ""),
        "destination": config.get("destination", "Local"),
        "mirror": bool(config.get("mirror")),
        "ignore_excludes": bool(config.get("ignore_excludes")),
        "compression": config.get("compression"),
        "sevenzip": bool(config.get("sevenzip")),
    }


def list_scheduled_backups() -> list[dict[str, Any]]:
    """Return each registered backup and the non-secret settings shown in the GUI."""
    schedules = _read_schedules()
    legacy_schedule = _read_legacy_schedule()
    if legacy_schedule is not None:
        schedules.append(legacy_schedule)
    return schedules


def create_scheduled_backup(
    config: dict[str, Any],
    interval: int,
    unit: str,
    schedule_time: str,
) -> str:
    """Persist one backup configuration and register its own Windows task."""
    if sys.platform != "win32":
        raise OSError("Scheduled backups are supported only on Windows.")

    schedule_args = task_schedule(interval, unit)
    schedule_time = validate_schedule_time(schedule_time)
    schedule_id = uuid.uuid4().hex
    task_name = f"{TASK_NAME} {schedule_id[:8]}"
    config_path = SCHEDULES_DIR / f"{schedule_id}.json"
    schedule = {
        "id": schedule_id,
        "task_name": task_name,
        "config_path": str(config_path),
        "interval": interval,
        "unit": "days" if unit.strip().lower() in {"day", "days"} else "months",
        "time": schedule_time,
        "source": config["source"],
        "target": config["target"],
        "destination": config.get("destination", "Local"),
        "mirror": bool(config.get("mirror")),
        "ignore_excludes": bool(config.get("ignore_excludes")),
        "compression": config.get("compression"),
        "sevenzip": bool(config.get("sevenzip")),
    }

    save_schedule_config(config, config_path)
    task_registered = False
    try:
        action = build_task_action(config_path, schedule_id=schedule_id)
        logger.info(
            "Registering scheduled backup '%s': every %s %s at %s.",
            task_name,
            interval,
            schedule["unit"],
            schedule_time,
        )
        _run_schtasks(
            [
                "/Create",
                "/TN",
                task_name,
                *schedule_args,
                "/ST",
                schedule_time,
                "/TR",
                action,
                "/IT",
                "/F",
            ]
        )
        task_registered = True
        schedules = _read_schedules()
        schedules.append(schedule)
        _write_schedules(schedules)
    except Exception:
        if task_registered:
            try:
                _run_schtasks(["/Delete", "/TN", task_name, "/F"])
            except Exception:
                logger.exception("Could not roll back task '%s' after registration failed.", task_name)
        config_path.unlink(missing_ok=True)
        raise

    logger.info("Scheduled backup '%s' registered successfully.", task_name)
    return schedule_id


def delete_scheduled_backup(schedule_id: str) -> None:
    """Remove a selected scheduled task and its saved configuration."""
    if sys.platform != "win32":
        raise OSError("Scheduled backups are supported only on Windows.")

    if schedule_id == "legacy":
        _run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])
        SCHEDULE_CONFIG.unlink(missing_ok=True)
        logger.info("Legacy scheduled backup '%s' removed.", TASK_NAME)
        return

    schedules = _read_schedules()
    schedule = next((item for item in schedules if item.get("id") == schedule_id), None)
    if schedule is None:
        raise ValueError("The selected scheduled backup was not found.")

    task_name = schedule.get("task_name")
    config_path = Path(schedule.get("config_path", ""))
    if not task_name or config_path.parent != SCHEDULES_DIR:
        raise ValueError("The selected scheduled backup has invalid task settings.")

    _run_schtasks(["/Delete", "/TN", task_name, "/F"])
    schedules.remove(schedule)
    _write_schedules(schedules)
    config_path.unlink(missing_ok=True)
    logger.info("Scheduled backup '%s' removed.", task_name)


def create_windows_task(
    config: dict[str, Any],
    interval: int,
    unit: str,
    schedule_time: str,
) -> str:
    if sys.platform != "win32":
        raise OSError("Scheduled backups are supported only on Windows.")
    schedule_args = task_schedule(interval, unit)
    schedule_time = validate_schedule_time(schedule_time)
    config_path = SCHEDULE_CONFIG
    previous_config = config_path.read_bytes() if config_path.exists() else None

    try:
        save_schedule_config(config, config_path)
        action = build_task_action(config_path)
        logger.info(
            "Registering task '%s' to run every %s %s at %s.",
            TASK_NAME,
            interval,
            unit,
            schedule_time,
        )
        output = _run_schtasks(
            [
                "/Create",
                "/TN",
                TASK_NAME,
                *schedule_args,
                "/ST",
                schedule_time,
                "/TR",
                action,
                "/IT",
                "/F",
            ]
        )
    except Exception:
        if previous_config is None:
            config_path.unlink(missing_ok=True)
        else:
            config_path.write_bytes(previous_config)
        raise

    logger.info("Task '%s' registered successfully.", TASK_NAME)
    return output


def delete_windows_task() -> str:
    if sys.platform != "win32":
        raise OSError("Scheduled backups are supported only on Windows.")
    output = _run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"])
    SCHEDULE_CONFIG.unlink(missing_ok=True)
    logger.info("Task '%s' removed.", TASK_NAME)
    return output
