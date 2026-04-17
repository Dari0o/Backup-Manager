"""windows_reminder.py - Autostart Manager für Backup Manager"""

import os
import sys
import json
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from BackupManager import BackupManager


class WindowsReminder:
    
    GITHUB_REPO = "Dari0o/Backup-Manager"
    GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    
    def __init__(self):
        self.script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.setup_file = os.path.join(self.script_dir, "setup.json")
        self.log_file = BackupManager.log_file
        self.config = self._load_config()
    
    def _load_config(self):
        """Lade setup.json Konfiguration"""
        if os.path.exists(self.setup_file):
            with open(self.setup_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}
    
    def _is_running_as_exe(self):
        """Prüfe ob das Script über .exe oder Konsole läuft"""
        return hasattr(sys, 'frozen') or os.path.basename(sys.argv[0]).endswith('.exe')
    
    def _hide_window(self):
        """Verstecke das Console-Fenster"""
        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.kernel32.FreeConsole()
            except:
                pass
    
    def check_for_update(self):
        """Prüfe auf neuen Release auf GitHub"""
        try:
            import requests
            response = requests.get(self.GITHUB_API, timeout=5)
            response.raise_for_status()
            release_data = response.json()
            
            tag = release_data.get("tag_name", "").lstrip('v')
            if not tag:
                return None
            
            return {
                "version": tag,
                "release_name": release_data.get("name", ""),
                "download_url": release_data.get("zipball_url", ""),
                "body": release_data.get("body", ""),
            }
        except Exception as e:
            BackupManager.log(f"Update Check Fehler: {e}")
            return None
    
    def install_update(self, release_info):
        """Installiere neuen Release"""
        try:
            import requests, zipfile, shutil
            
            BackupManager.log(f"Installiere Update {release_info['version']}...")
            
            zip_path = os.path.join(self.script_dir, "update.zip")
            response = requests.get(release_info["download_url"], timeout=30)
            response.raise_for_status()
            
            with open(zip_path, "wb") as f:
                f.write(response.content)
            
            extract_dir = os.path.join(self.script_dir, "update_temp")
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            extracted_contents = os.listdir(extract_dir)
            if extracted_contents:
                source_dir = os.path.join(extract_dir, extracted_contents[0])
            else:
                BackupManager.log("Fehler: ZIP ist leer")
                return False
            
            backup_dir = os.path.join(self.script_dir, ".backup_old")
            os.makedirs(backup_dir, exist_ok=True)
            
            for item in os.listdir(self.script_dir):
                if item.startswith('.') or item in ['update.zip', 'update_temp', '.backup_old']:
                    continue
                item_path = os.path.join(self.script_dir, item)
                backup_path = os.path.join(backup_dir, item)
                if os.path.isdir(item_path):
                    if os.path.exists(backup_path):
                        shutil.rmtree(backup_path)
                    shutil.copytree(item_path, backup_path)
                else:
                    shutil.copy2(item_path, backup_path)
            
            for item in os.listdir(source_dir):
                src = os.path.join(source_dir, item)
                dst = os.path.join(self.script_dir, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            
            shutil.rmtree(extract_dir)
            os.remove(zip_path)
            
            BackupManager.log(f"Update erfolgreich installiert")
            self._register_autostart()
            return True
        except Exception as e:
            BackupManager.log(f"Update Installation Fehler: {e}")
            return False
    
    def _register_autostart(self):
        """Registriere Script im Windows Autostart"""
        try:
            import winreg
            python_exe = sys.executable
            script_path = os.path.join(self.script_dir, "lib", "windows_reminder.py")
            cmd = f'"{python_exe}" "{script_path}"'
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.STARTUP_KEY)
            winreg.SetValueEx(key, "BackupManager", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            BackupManager.log("Autostart registriert")
        except Exception as e:
            BackupManager.log(f"Autostart Fehler: {e}")
    
    def check_backup_reminder(self):
        """Prüfe ob Backup-Erinnerung fällig ist"""
        try:
            if not os.path.exists(self.log_file):
                self._show_reminder_notification(None)
                return
            
            last_backup_date = self._parse_last_backup_from_log()
            if last_backup_date is None:
                self._show_reminder_notification(None)
                return
            
            days_diff = (datetime.now() - last_backup_date).days
            reminder_days = self.config.get("backup_reminder_days", 7)
            
            if days_diff >= reminder_days:
                self._show_reminder_notification(last_backup_date)
        except Exception as e:
            BackupManager.log(f"Backup Reminder Fehler: {e}")
    
    def _parse_last_backup_from_log(self):
        """Parse Datum des letzten Backups aus Log-Datei"""
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            for line in reversed(lines):
                if " Backup abgeschlossen" in line:
                    match = re.match(r'\[(\d{4}-\d{2}-\d{2})', line)
                    if match:
                        return datetime.strptime(match.group(1), "%Y-%m-%d")
            return None
        except Exception as e:
            BackupManager.log(f"Log Parse Fehler: {e}")
            return None
    
    def _show_reminder_notification(self, last_backup_date):
        """Zeige Backup-Erinnerung (ohne Audio)"""
        try:
            from winotify import Notification
            
            if last_backup_date is None:
                msg = "Noch kein Backup vorhanden!"
            else:
                days_diff = (datetime.now() - last_backup_date).days
                msg = self._format_time_diff(days_diff)
            
            notification = Notification(
                app_id="NAS Backup Manager",
                title=" Backup Erinnerung",
                msg=msg,
                duration="long"
            )
            notification.add_actions(label="OK", launch="snooze_7days://trigger")
            notification.show()
            BackupManager.log(f"Backup-Erinnerung angezeigt")
        except Exception as e:
            BackupManager.log(f"Notification Fehler: {e}")
    
    def _format_time_diff(self, days):
        """Formatiere Zeit-Differenz als Tage/Monate/Jahre"""
        if days < 30:
            return f"Letztes Backup: {days} Tag(e) her"
        elif days < 365:
            months = days // 30
            return f"Letztes Backup: {months} Monat(e) her"
        else:
            years = days // 365
            remaining = days % 365
            if remaining == 0:
                return f"Letztes Backup: {years} Jahr(e) her"
            return f"Letztes Backup: {years}J {remaining // 30}M her"
    
    def run(self):
        """Hauptschleife - läuft im Hintergrund"""
        # Verstecke Fenster sowohl als .exe als auch als Python-Script
        self._hide_window()
        
        BackupManager.setup()
        BackupManager.log("=== Reminder gestartet ===" )
        
        if self.config.get("recieve_update_messages", True):
            release_info = self.check_for_update()
            if release_info:
                BackupManager.log(f"Update verfügbar: {release_info['version']}")
                self.install_update(release_info)
        
        if self.config.get("recieve_backup_messages", True):
            self.check_backup_reminder()
        
        BackupManager.log("=== Reminder beendet ===")


if __name__ == "__main__":
    reminder = WindowsReminder()
    reminder.run()
