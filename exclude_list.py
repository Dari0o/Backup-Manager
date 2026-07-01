import json
import os
from typing import Any, Dict, List
from BackupManager import log as logger

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "exclude_list.json")

DEFAULT_CONFIG: Dict[str, List[str]] = {
    "ignored_folder_names": [
        ".git",
        "__pycache__",
        "node_modules",
        "temp",
        "tmp",
    ],
    "ignored_file_names": [
        "Thumbs.db",
        ".DS_Store",
        "desktop.ini",
    ],
    "ignored_extensions": [
        ".tmp",
        ".log",
        ".bak",
        ".swp",
    ],
}


def _normalize_names(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []
    return [str(item).strip().lower() for item in items if str(item).strip()]


def _normalize_extensions(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items:
        ext = str(item).strip().casefold()
        if not ext:
            continue
        if not ext.startswith('.'):
            ext = f".{ext}"
        normalized.append(ext)
    return normalized


def _write_default_config() -> None:
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
    except OSError:
        logger("Error writing default config file")


def load_exclude_config() -> Dict[str, List[str]]:
    if not os.path.exists(CONFIG_FILE):
        _write_default_config()
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

        if not isinstance(config, dict):
            return DEFAULT_CONFIG.copy()

        return {
            "ignored_folder_names": _normalize_names(config.get("ignored_folder_names", DEFAULT_CONFIG["ignored_folder_names"])),
            "ignored_file_names": _normalize_names(config.get("ignored_file_names", DEFAULT_CONFIG["ignored_file_names"])),
            "ignored_extensions": _normalize_extensions(config.get("ignored_extensions", DEFAULT_CONFIG["ignored_extensions"])),
        }

    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()


CONFIG = load_exclude_config()
IGNORED_FOLDER_NAMES = set(CONFIG["ignored_folder_names"])
IGNORED_FILE_NAMES = set(CONFIG["ignored_file_names"])
IGNORED_EXTENSIONS = set(CONFIG["ignored_extensions"])


def is_ignored_name(name: str, is_dir: bool = False) -> bool:
    lower_name = name.strip().lower()

    if is_dir:
        return lower_name in IGNORED_FOLDER_NAMES

    if lower_name in IGNORED_FILE_NAMES:
        return True

    _, ext = os.path.splitext(lower_name)
    return ext in IGNORED_EXTENSIONS


def should_ignore_path(entry) -> bool:
    try:
        if entry.is_dir(follow_symlinks=False):
            return is_ignored_name(entry.name, is_dir=True)

        if entry.is_file(follow_symlinks=False):
            return is_ignored_name(entry.name, is_dir=False)

    except (PermissionError, OSError):
        logger(f"Error accessing path: {entry.path}")
        return True

    return False
