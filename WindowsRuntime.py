"""
Überarbeitetes WindowsRuntime.py - Hauptausführung für Windows-Benachrichtigungen
"""

import threading
import time
import json
import sys
import os
import winreg
import requests
import zipfile
import shutil
from datetime import datetime, timedelta
import re

# Import des neuen Notification-Systems
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import BackupManager as bm
from lib.notifications import NotificationManager

# ========================
# Konfiguration
# ========================
CHECK_INTERVAL = 3600
MAX_DAYS = 64
UPDATE_CHECK_INTERVAL = 3600

GITHUB_REPO = "Dari0o/Backup-Manager"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _get_config_dir():
    """Bestimmen Sie das Konfigurationsverzeichnis."""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        if "_MEI" in exe_dir or "Temp" in exe_dir:
            if hasattr(bm.BackupManager, 'log_file'):
                log_dir = os.path.dirname(bm.BackupManager.log_file)
                if os.path.exists(log_dir):
                    return log_dir
        return exe_dir
    return os.path.dirname(os.path.abspath(__file__))


_CONFIG_DIR = _get_config_dir()
CONFIG_DIR = os.path.join(_CONFIG_DIR, "config")

# Stelle sicher, dass das config-Verzeichnis existiert
os.makedirs(CONFIG_DIR, exist_ok=True)

# Initialisiere Notification Manager
notification_manager = NotificationManager(bm.BackupManager.log, CONFIG_DIR)


# ========================
# Hilfsfunktionen
# ========================

def hide_console():
    """Verstecke das Konsolen-Fenster auf Windows."""
    if getattr(sys, 'frozen', False):
        try:
            import ctypes
            ctypes.windll.user32.ShowWindow(
                ctypes.windll.kernel32.GetConsoleWindow(), 0
            )
        except Exception:
            pass


def ensure_autostart():
    """Stelle sicher, dass das Skript beim Start ausgeführt wird."""
    try:
        task_name = "NAS Backup Manager"
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            pythonw = sys.executable.replace("python.exe", "pythonw.exe")
            exe_path = f'"{pythonw}" "{os.path.abspath(__file__)}"'

        key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run"
        )
        try:
            existing = winreg.QueryValueEx(key, task_name)
            if existing[0] != exe_path:
                winreg.SetValueEx(key, task_name, 0, winreg.REG_SZ, exe_path)
        except WindowsError:
            winreg.SetValueEx(key, task_name, 0, winreg.REG_SZ, exe_path)
        finally:
            winreg.CloseKey(key)

        bm.BackupManager.log("✓ Autostart registriert")
    except Exception as e:
        bm.BackupManager.log(f"✗ Autostart-Fehler: {e}")


def register_protocol_handlers():
    """
    Registriere URL-Protocol Handler für snooze_7days://, backup_now:// und update_now://
    """
    try:
        script_dir = _get_config_dir()
        if getattr(sys, 'frozen', False):
            python_exe = sys.executable
        else:
            python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable

        handlers = {
            "snooze_7days": {
                "script": "snooze_reminder",
                "description": "Snooze NAS Backup Reminder"
            },
            "backup_now": {
                "script": "backup_now",
                "description": "Start NAS Backup Now"
            },
            "update_now": {
                "script": "update_handler",
                "description": "Download and install NAS Backup Update"
            },
        }

        for protocol_name, info in handlers.items():
            script_base = info["script"]
            script_exe = os.path.join(script_dir, f"{script_base}.exe")
            script_py = os.path.join(script_dir, f"{script_base}.py")

            if os.path.exists(script_exe):
                command = f'"{script_exe}"'
            elif os.path.exists(script_py):
                command = f'"{python_exe}" "{script_py}"'
            else:
                bm.BackupManager.log(f"⚠ Script nicht gefunden: {script_base}")
                continue

            protocol_path = rf"Software\Classes\{protocol_name}"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, protocol_path)
            try:
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"URL:{info['description']}")
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                shell_key = winreg.CreateKey(
                    winreg.HKEY_CURRENT_USER,
                    protocol_path + r"\shell\open\command"
                )
                winreg.SetValueEx(shell_key, "", 0, winreg.REG_SZ, command)
                winreg.CloseKey(shell_key)
                bm.BackupManager.log(f"✓ Protocol Handler registriert: {protocol_name}://")
            except Exception as e:
                bm.BackupManager.log(f"✗ Fehler bei {protocol_name}://: {e}")
            finally:
                winreg.CloseKey(key)

    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler bei Protocol Handler: {e}")


# ========================
# GitHub Release Check
# ========================

def get_latest_release():
    """
    Hole das neueste Release von GitHub API.
    
    Returns:
        Dict mit Version, Download-URL, etc. oder None bei Fehler
    """
    try:
        response = requests.get(GITHUB_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        return {
            "version": data["tag_name"],
            "download_url": data["assets"][0]["browser_download_url"] if data["assets"] else None,
            "release_name": data["name"],
            "body": data.get("body", ""),
        }
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler beim Abrufen des Releases: {e}")
        return None


def check_for_update():
    """
    Prüfe auf verfügbare Updates.
    
    Returns:
        release_info Dict wenn neue Version verfügbar, sonst None
    """
    config = notification_manager.load_update_config()
    now = datetime.now()

    # Prüfe Interval - nur alle UPDATE_CHECK_INTERVAL Sekunden prüfen
    if config["last_check"] and now - config["last_check"] < timedelta(seconds=UPDATE_CHECK_INTERVAL):
        return None

    bm.BackupManager.log("=" * 60)
    bm.BackupManager.log("🔍 Prüfe auf Updates...")

    config["last_check"] = now
    notification_manager.save_update_config(config)

    latest = get_latest_release()
    if not latest:
        bm.BackupManager.log("✗ Konnte Release-Info nicht laden")
        bm.BackupManager.log("=" * 60)
        return None

    bm.BackupManager.log(f"  💾 Verfügbare Version: {latest['version']}")
    bm.BackupManager.log(f"  📦 Letzte Anzeige    : {config.get('notification_shown_version', 'KEINE')}")

    # Prüfe ob diese Version bereits angezeigt wurde
    if config.get("notification_shown_version") == latest["version"]:
        bm.BackupManager.log(f"✓ Update {latest['version']} bereits angezeigt")
        bm.BackupManager.log("=" * 60)
        return None

    bm.BackupManager.log(f"✓ 🎉 NEUES UPDATE: {latest['version']}")
    bm.BackupManager.log("=" * 60)

    return latest


# ========================
# Update-Durchführung
# ========================

# ========================
# Backup-Erinnerung
# ========================

def get_last_backup():
    """
    Hole Zeitstempel des letzten erfolgreichen Backups aus Log-Datei.
    
    Returns:
        datetime oder None wenn kein Backup gefunden
    """
    try:
        last_time = None
        with open(bm.BackupManager.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if "=== Script gestartet ===" in line:
                    match = re.search(r"\[(.*?)\]", line)
                    if match:
                        try:
                            last_time = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass
        return last_time
    except Exception:
        return None


def check_backup():
    """
    Prüfe ob Backup-Erinnerung angezeigt werden soll.
    """
    config = notification_manager.load_reminder_config()
    last_backup = get_last_backup()
    now = datetime.now()

    # Prüfe ob Erinnerung verschoben wurde
    if config.get("next_reminder_time") and now < config["next_reminder_time"]:
        return

    if last_backup is None:
        notification_manager.show_backup_reminder(float("inf"))
        return

    delta_days = (now - last_backup).total_seconds() / 86400

    if delta_days >= MAX_DAYS:
        notification_manager.show_backup_reminder(delta_days)
    else:
        # Backup ist aktuell, zurücksetzen
        if config.get("next_reminder_time") or config.get("last_notification_sent_at"):
            notification_manager.reset_backup_reminder()


# ========================
# Haupt-Loops
# ========================


def update_check_loop():
    """
    Haupt-Update-Check Loop.
    Prüft regelmäßig auf verfügbare Updates und zeigt Benachrichtigung an.
    """
    while True:
        try:
            release_info = check_for_update()
            if release_info:
                notification_manager.show_update_notification(release_info)
        except Exception as e:
            bm.BackupManager.log(f"✗ Fehler im Update-Check: {e}")
        
        time.sleep(UPDATE_CHECK_INTERVAL)


def backup_check_loop():
    """
    Haupt-Backup-Check Loop.
    Prüft regelmäßig ob Backup-Erinnerung gezeigt werden soll.
    """
    while True:
        try:
            check_backup()
        except Exception as e:
            bm.BackupManager.log(f"✗ Fehler im Backup-Check: {e}")
        
        time.sleep(CHECK_INTERVAL)


# ========================
# Hauptprogramm
# ========================

def main():
    """Starten Sie das WindowsRuntime."""
    hide_console()
    ensure_autostart()
    register_protocol_handlers()

    bm.BackupManager.log("=" * 60)
    bm.BackupManager.log("🚀 WindowsRuntime gestartet")
    bm.BackupManager.log("=" * 60)

    # Starte alle Loops in separaten Threads
    threading.Thread(target=update_check_loop, daemon=True).start()
    threading.Thread(target=backup_check_loop, daemon=True).start()

    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        bm.BackupManager.log("⏹ WindowsRuntime beendet")


if __name__ == "__main__":
    main()
