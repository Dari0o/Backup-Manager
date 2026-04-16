"""
Vereinfachtes Notification-System für Windows Benachrichtigungen.
Nur noch Toast-Anzeige. Klicks werden über Protocol Handler gehandhabt.
"""

import threading
import json
import os
from datetime import datetime, timedelta
from winotify import Notification


class NotificationManager:
    """Zentrale Verwaltung für Windows Benachrichtigungen."""
    
    def __init__(self, log_func, config_dir):
        self.log = log_func
        self.config_dir = config_dir
        
        # Dateipfade
        self.update_config_file = os.path.join(config_dir, "update_config.json")
        self.reminder_config_file = os.path.join(config_dir, "reminder_config.json")
        self.pending_release_file = os.path.join(config_dir, "_pending_release.json")
    
    # ========================
    # CONFIG-VERWALTUNG
    # ========================
    
    def load_update_config(self):
        """Lade Update-Konfiguration."""
        try:
            if os.path.exists(self.update_config_file):
                with open(self.update_config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                for key in ("last_check", "notification_shown_at"):
                    if config.get(key):
                        config[key] = datetime.fromisoformat(config[key])
                return config
        except Exception as e:
            self.log(f"⚠ Fehler beim Laden Update-Config: {e}")
        
        return {
            "last_check": None,
            "last_known_version": None,
            "notification_shown_version": None,
            "notification_shown_at": None,
        }
    
    def save_update_config(self, config):
        """Speichere Update-Konfiguration."""
        try:
            save_data = config.copy()
            for key in ("last_check", "notification_shown_at"):
                if save_data.get(key) and isinstance(save_data[key], datetime):
                    save_data[key] = save_data[key].isoformat()
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.update_config_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log(f"✗ Fehler beim Speichern Update-Config: {e}")
    
    def load_reminder_config(self):
        """Lade Erinnerungs-Konfiguration."""
        try:
            if os.path.exists(self.reminder_config_file):
                with open(self.reminder_config_file, "r", encoding="utf-8") as f:
                    config = json.load(f)
                for key in ("next_reminder_time", "last_notification_sent_at"):
                    if config.get(key):
                        config[key] = datetime.fromisoformat(config[key])
                return config
        except Exception as e:
            self.log(f"⚠ Fehler beim Laden Reminder-Config: {e}")
        
        return {
            "next_reminder_time": None,
            "last_notification_sent_at": None,
        }
    
    def save_reminder_config(self, config):
        """Speichere Erinnerungs-Konfiguration."""
        try:
            save_data = config.copy()
            for key in ("next_reminder_time", "last_notification_sent_at"):
                if save_data.get(key) and isinstance(save_data[key], datetime):
                    save_data[key] = save_data[key].isoformat()
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.reminder_config_file, "w", encoding="utf-8") as f:
                json.dump(save_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log(f"✗ Fehler beim Speichern Reminder-Config: {e}")
    
    # ========================
    # UPDATE-NOTIFICATION
    # ========================
    
    def show_update_notification(self, release_info):
        """
        Zeige Update-Benachrichtigung an (nur einmal pro Version).
        Klick wird über Protocol Handler update_now:// gehandhabt.
        
        Args:
            release_info: Dict mit Version, Release-Name, Download-URL
        """
        config = self.load_update_config()
        now = datetime.now()
        
        # Prüfe ob diese Version bereits angezeigt wurde
        if config.get("notification_shown_version") == release_info["version"]:
            self.log(f"⊘ Update {release_info['version']} bereits angezeigt")
            return
        
        # SOFORT speichern dass diese Version angezeigt wird
        config["notification_shown_version"] = release_info["version"]
        config["notification_shown_at"] = now
        config["last_known_version"] = release_info["version"]
        self.save_update_config(config)
        
        # Speichere Pending Release Info
        try:
            pending = {
                "version": release_info["version"],
                "release_name": release_info["release_name"],
                "download_url": release_info["download_url"],
                "body": release_info.get("body", ""),
            }
            with open(self.pending_release_file, "w", encoding="utf-8") as f:
                json.dump(pending, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log(f"⚠ Fehler Pending Release: {e}")
        
        self.log(f"✓ Update {release_info['version']} - Config gespeichert")
        
        # Zeige Toast asynchron
        threading.Thread(
            target=self._show_update_toast,
            args=(release_info,),
            daemon=True
        ).start()
    
    def _show_update_toast(self, release_info):
        """Zeige Update-Toast an (läuft in separatem Thread)."""
        try:
            self.log(f"📢 Zeige Update-Toast für {release_info['version']}")
            
            toast = Notification(
                app_id="NAS Backup Manager",
                title=f"🔄 Update verfügbar: {release_info['version']}",
                msg=f"{release_info['release_name']}\n\nKlicken Sie zum Aktualisieren.",
            )
            
            toast.add_actions(
                label="↓ Jetzt aktualisieren",
                launch="update_now://"
            )
            
            try:
                toast.show()
            except Exception as e:
                self.log(f"⚠ Fehler toast.show(): {e}")
            
            self.log(f"✓ Update-Toast angezeigt")
            
        except Exception as e:
            self.log(f"✗ Fehler Update-Toast: {e}")
    
    # ========================
    # BACKUP-ERINNERUNG
    # ========================
    
    def show_backup_reminder(self, days_since_backup):
        """
        Zeige Backup-Benachrichtigung an (maximal einmal pro Tag).
        Klick auf Snooze wird über Protocol Handler snooze_7days:// gehandhabt.
        
        Args:
            days_since_backup: Tage seit letztem Backup (oder inf wenn nie)
        """
        config = self.load_reminder_config()
        now = datetime.now()
        
        # Prüfe ob heute bereits gesendet
        sent_at = config.get("last_notification_sent_at")
        if sent_at and isinstance(sent_at, datetime) and sent_at.date() == now.date():
            self.log(f"⊘ Backup-Benachrichtigung heute bereits gesendet")
            return
        
        # SOFORT speichern dass heute Benachrichtigung gesendet wird
        config["last_notification_sent_at"] = now
        self.save_reminder_config(config)
        
        self.log(f"✓ Backup-Benachrichtigung - Config gespeichert")
        
        # Zeige Toast asynchron
        threading.Thread(
            target=self._show_backup_toast,
            args=(days_since_backup,),
            daemon=True
        ).start()
    
    def _show_backup_toast(self, days_since_backup):
        """Zeige Backup-Toast an (läuft in separatem Thread)."""
        try:
            # Konstruiere Nachricht
            if days_since_backup == float("inf"):
                msg = "⚠️ Noch kein Backup vorhanden!\nBitte führen Sie ein Backup durch."
            else:
                days_int = int(round(days_since_backup))
                msg = f"⏰ Letztes Backup: vor {days_int} Tagen\n\nBitte Backup durchführen!"
            
            self.log(f"📢 Zeige Backup-Toast")
            
            toast = Notification(
                app_id="NAS Backup Manager",
                title="📦 Backup Erinnerung",
                msg=msg,
            )
            
            toast.add_actions(
                label="⏱ In 7 Tagen erinnern",
                launch="snooze_7days://"
            )
            
            try:
                toast.show()
            except Exception as e:
                self.log(f"⚠ Fehler toast.show(): {e}")
            
            self.log(f"✓ Backup-Toast angezeigt")
            
        except Exception as e:
            self.log(f"✗ Fehler Backup-Toast: {e}")
    
    def snooze_backup_reminder(self, days=7):
        """Verschiebe Backup-Erinnerung um X Tage."""
        config = self.load_reminder_config()
        config["next_reminder_time"] = datetime.now() + timedelta(days=days)
        self.save_reminder_config(config)
        self.log(f"✓ Erinnerung um {days} Tage verschoben")
    
    def reset_backup_reminder(self):
        """Setze Backup-Erinnerung zurück."""
        config = self.load_reminder_config()
        config["next_reminder_time"] = None
        config["last_notification_sent_at"] = None
        self.save_reminder_config(config)
        self.log("✓ Backup-Erinnerung zurückgesetzt")
