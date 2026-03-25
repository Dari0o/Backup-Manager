import threading
import time
import json
from datetime import datetime, timedelta
from winotify import Notification
import sys
import os
import BackupManager as bm
import winreg
import requests
import zipfile
import shutil
import subprocess

# ----------------------------
# Einstellungen
# ----------------------------
CHECK_INTERVAL = 3600  # Sekunden zwischen Checks (1 Stunde)
MAX_DAYS = 64           # Tage nach denen erinnert wird
LOG_FILE = bm.BackupManager.log_file
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "reminder_config.json")
UPDATE_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "update_config.json")
UPDATE_CHECK_INTERVAL = 3600  # Sekunden zwischen Update-Checks (1 Stunde)
GITHUB_REPO = "Dari0o/Backup-Manager"  # GitHub Repository im Format owner/repo
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
UPDATE_TRIGGER_FILE = os.path.join(os.path.dirname(__file__), "_update_trigger.json")
PENDING_RELEASE_FILE = os.path.join(os.path.dirname(__file__), "_pending_release.json")
last_notification_time = None

# ----------------------------
# Konsole verstecken (nur bei .exe)
# ----------------------------
def hide_console():
    """Versteckt die Konsole wenn das Script als .exe läuft"""
    if getattr(sys, 'frozen', False):  # Nur wenn als .exe kompiliert
        import ctypes
        import subprocess
        # Aktuelle Konsole verstecken
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)

# ----------------------------
# Autostart sicherstellen
# ----------------------------
def ensure_autostart():
    """Registriert die .exe/das Script im Windows Autostart"""
    try:
        task_name = "NAS Backup Reminder"
        
        # Wenn als .exe kompiliert, direkt exe-Pfad benutzen
        if getattr(sys, 'frozen', False):
            exe_path = sys.executable
        else:
            # Wenn als Script, pythonw.exe benutzen (ohne Konsole)
            pythonw_path = sys.executable.replace("python.exe", "pythonw.exe")
            exe_path = f'"{pythonw_path}" "{os.path.abspath(__file__)}"'

        # Registry-Pfad für Autostart
        startup_key = winreg.HKEY_CURRENT_USER
        startup_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        # Registry öffnen/erstellen
        key = winreg.CreateKey(startup_key, startup_path)
        try:
            # Prüfen, ob Eintrag existiert
            existing = winreg.QueryValueEx(key, task_name)
            # Nur aktualisieren, wenn Pfad anders ist
            if existing[0] != exe_path:
                winreg.SetValueEx(key, task_name, 0, winreg.REG_SZ, exe_path)
        except WindowsError:
            # Key existiert noch nicht → setzen
            winreg.SetValueEx(key, task_name, 0, winreg.REG_SZ, exe_path)
        finally:
            winreg.CloseKey(key)
            
        bm.BackupManager.log("✓ Autostart erfolgreich registriert")
    except Exception as e:
        bm.BackupManager.log(f"✗ Autostart konnte nicht gesetzt werden: {e}")

# ----------------------------
# Protocol Handler für Snooze-Button registrieren
# ----------------------------
def register_protocol_handlers():
    """Registriert Protocol Handler für Buttons"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Bestimme Python-Executable - nutze pythonw.exe für Update Handler (ohne Konsole)
        if getattr(sys, 'frozen', False):
            python_exe = sys.executable
        else:
            # Für Scripts: nutze pythonw.exe (ohne Konsole)
            python_exe = sys.executable.replace("python.exe", "pythonw.exe")
            if not os.path.exists(python_exe):
                python_exe = sys.executable
        
        hkey = winreg.HKEY_CURRENT_USER
        
        # Handler registrieren
        handlers = {
            "snooze_7days://": {
                "script": "snooze_reminder.py",
                "description": "Snooze NAS Backup Reminder"
            },
            "backup_now://": {
                "script": "backup_now.py",
                "description": "Start NAS Backup Now"
            },
            "update_now://": {
                "script": "update_handler.py",
                "description": "Update WindowsRuntime"
            }
        }
        
        for protocol, info in handlers.items():
            protocol_name = protocol.replace("://", "")
            script_path = os.path.join(script_dir, info["script"])
            
            if not os.path.exists(script_path):
                bm.BackupManager.log(f"⚠ Script nicht gefunden: {script_path}")
                continue
            
            protocol_path = rf"Software\Classes\{protocol_name}"
            
            key = winreg.CreateKey(hkey, protocol_path)
            try:
                # Standard Value setzen
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f"URL:{info['description']}")
                
                # URL-Protokoll-Flag
                winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
                
                # Shell\Open\command - direkt Python aufrufen mit Anführungszeichen
                shell_key = winreg.CreateKey(hkey, protocol_path + r"\shell\open\command")
                command = f'"{python_exe}" "{script_path}"'
                winreg.SetValueEx(shell_key, "", 0, winreg.REG_SZ, command)
                winreg.CloseKey(shell_key)
                
                bm.BackupManager.log(f"✓ Protocol Handler registriert: {protocol_name}:// -> {script_path}")
                bm.BackupManager.log(f"  Command: {command}")
            except Exception as e:
                bm.BackupManager.log(f"✗ Fehler beim Registrieren von {protocol_name}://: {e}")
            finally:
                winreg.CloseKey(key)
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler bei der Protocol Handler Registrierung: {e}")


# ----------------------------# Update-Konfiguration laden/speichern
# ----------------------------
def load_update_config():
    """Lädt die Update-Konfiguration"""
    try:
        if os.path.exists(UPDATE_CONFIG_FILE):
            with open(UPDATE_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                if "last_check" in config and config["last_check"]:
                    config["last_check"] = datetime.fromisoformat(config["last_check"])
                return config
    except Exception:
        pass
    
    return {
        "last_check": None,
        "last_known_version": None,
        "ignored_version": None
    }

def save_update_config(config):
    """Speichert die Update-Konfiguration"""
    try:
        save_data = config.copy()
        if save_data["last_check"]:
            save_data["last_check"] = save_data["last_check"].isoformat()
        
        os.makedirs(os.path.dirname(UPDATE_CONFIG_FILE), exist_ok=True)
        with open(UPDATE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler beim Speichern der Update-Konfiguration: {e}")

# ----------------------------
# GitHub Release Check
# ----------------------------
def get_latest_release():
    """Lädt die neueste Release-Information von GitHub"""
    try:
        response = requests.get(GITHUB_API_URL, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        return {
            "version": data["tag_name"],
            "download_url": data["assets"][0]["browser_download_url"] if data["assets"] else None,
            "release_name": data["name"],
            "body": data["body"]
        }
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler beim Abrufen des neuesten Releases: {e}")
        return None

def check_for_update():
    """Prüft ob ein neues Update verfügbar ist"""
    config = load_update_config()
    now = datetime.now()
    
    # Prüfe nicht öfter als UPDATE_CHECK_INTERVAL
    if config["last_check"] and now - config["last_check"] < timedelta(seconds=UPDATE_CHECK_INTERVAL):
        return None
    
    bm.BackupManager.log("Prüfe auf Updates...")
    config["last_check"] = now
    save_update_config(config)
    
    latest = get_latest_release()
    if not latest:
        return None
    
    # Vergleiche Versionen
    if config["last_known_version"] == latest["version"]:
        return None  # Keine neue Version
    
    # Prüfe ob diese Version ignoriert wurde
    if config["ignored_version"] == latest["version"]:
        return None
    
    bm.BackupManager.log(f"✓ Neues Update verfügbar: {latest['version']}")
    config["last_known_version"] = latest["version"]
    save_update_config(config)
    
    return latest

def show_update_notification(release_info):
    """Zeigt eine Update-Benachrichtigung mit Button"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Speichere Release-Info für später Verwendung
        with open(PENDING_RELEASE_FILE, "w") as f:
            json.dump({
                "version": release_info['version'],
                "release_name": release_info['release_name'],
                "download_url": release_info['download_url'],
                "body": release_info['body'],
                "timestamp": datetime.now().isoformat()
            }, f)
        
        bm.BackupManager.log(f"✓ Release-Info gespeichert in {PENDING_RELEASE_FILE}")
        bm.BackupManager.log(f"✓ Update-Benachrichtigung wird angezeigt für Version {release_info['version']}")
        
        toast = Notification(
            app_id="NAS Backup",
            title="Update verfügbar",
            msg=f"Version {release_info['version']} ist verfügbar!\n\n{release_info['release_name']}"
        )
        
        # Füge Button hinzu - möglicherweise wird das Button-Click über Update-Trigger-File erkannt
        try:
            toast.add_actions(label="Jetzt aktualisieren", launch="update_now://")
            bm.BackupManager.log("✓ Update Button mit Protocol Handler hinzugefügt")
        except Exception as e:
            bm.BackupManager.log(f"⚠ Konnte Button nicht mit Protocol Handler hinzufügen: {e}")
        
        toast.show()
        bm.BackupManager.log("✓ Update-Benachrichtigung angezeigt - bitte auf 'Jetzt aktualisieren' klicken")
        
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler beim Anzeigen der Update-Benachrichtigung: {e}")

def perform_update(release_info):
    """Lädt und installiert das Update"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        temp_dir = os.path.join(script_dir, "_update_temp")
        
        # Temp-Verzeichnis erstellen
        os.makedirs(temp_dir, exist_ok=True)
        
        bm.BackupManager.log(f"Lade Update {release_info['version']} herunter...")
        
        # Download der Release
        response = requests.get(release_info["download_url"], timeout=30, stream=True)
        response.raise_for_status()
        
        zip_path = os.path.join(temp_dir, "update.zip")
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        bm.BackupManager.log("✓ Update heruntergeladen, entpacke...")
        
        # Entpacke die ZIP
        extract_dir = os.path.join(temp_dir, "extracted")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Suche die internal Ordner (die aktuelle Struktur)
        internal_source = None
        for root, dirs, files in os.walk(extract_dir):
            if "internal" in dirs:
                internal_source = os.path.join(root, "internal")
                break
        
        if not internal_source or not os.path.exists(internal_source):
            bm.BackupManager.log("✗ Update konnte nicht entpackt werden (internal Ordner nicht gefunden)")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False
        
        # Backup der alten Dateien erstellen
        backup_dir = os.path.join(script_dir, ".backup_old")
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir, ignore_errors=True)
        
        bm.BackupManager.log("Erstelle Backup der alten Dateien...")
        # Backup ALLER Dateien (Python, Batch, Spec, etc.)
        os.makedirs(backup_dir, exist_ok=True)
        for item in os.listdir(script_dir):
            if item.startswith("_") or item == ".backup_old":
                continue  # Ignoriere Temp-Dateien
            src_path = os.path.join(script_dir, item)
            dst_path = os.path.join(backup_dir, item)
            if os.path.isfile(src_path):
                shutil.copy2(src_path, dst_path)
            elif os.path.isdir(src_path) and not item == "__pycache__":
                shutil.copytree(src_path, dst_path, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        
        bm.BackupManager.log("✓ Backup erstellt, kopiere ALLE neuen Dateien...")
        # Kopiere die neuen Dateien - alles aus internal wird kopiert
        for item in os.listdir(internal_source):
            src = os.path.join(internal_source, item)
            dst = os.path.join(script_dir, item)
            
            # Lösche alte Version
            if os.path.exists(dst):
                if os.path.isfile(dst):
                    os.remove(dst)
                elif os.path.isdir(dst):
                    shutil.rmtree(dst)
            
            # Kopiere neue Version
            if os.path.isfile(src):
                shutil.copy2(src, dst)
                bm.BackupManager.log(f"  ✓ Datei aktualisiert: {item}")
            elif os.path.isdir(src):
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                bm.BackupManager.log(f"  ✓ Verzeichnis aktualisiert: {item}")
        
        # Aktualisiere Autostart mit neuem Pfad
        bm.BackupManager.log("Aktualisiere Autostart...")
        ensure_autostart()
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        bm.BackupManager.log(f"✓ Update zu {release_info['version']} erfolgreich durchgeführt!")
        
        # Update-Konfiguration zurücksetzen
        config = load_update_config()
        config["ignored_version"] = None
        save_update_config(config)
        
        return True
        
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler beim Update: {e}")
        return False

# ----------------------------# Letztes Backup aus Log lesen
# ----------------------------
def get_last_backup():
    try:
        import re
        last_time = None
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "=== Script gestartet ===" in line:
                    match = re.search(r"\[(.*?)\]", line)
                    if match:
                        timestamp = match.group(1)
                        try:
                            last_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                        except:
                            pass
        return last_time
    except Exception:
        return None

# ----------------------------
# Konfiguration laden/speichern
# ----------------------------
def load_reminder_config():
    """Lädt die Erinnerungs-Konfiguration"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Konvertiere String zurück zu datetime
                if "next_reminder_time" in config and config["next_reminder_time"]:
                    config["next_reminder_time"] = datetime.fromisoformat(config["next_reminder_time"])
                return config
    except Exception:
        pass
    
    return {
        "next_reminder_time": None,
        "last_action": None  # "snooze_7days" oder "dismissed"
    }

def save_reminder_config(config):
    """Speichert die Erinnerungs-Konfiguration"""
    try:
        save_data = config.copy()
        # Konvertiere datetime zu String
        if save_data["next_reminder_time"]:
            save_data["next_reminder_time"] = save_data["next_reminder_time"].isoformat()
        
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(save_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler beim Speichern der Konfiguration: {e}")

def snooze_reminder(days=7):
    """Verschiebt die nächste Erinnerung um X Tage"""
    config = load_reminder_config()
    config["next_reminder_time"] = datetime.now() + timedelta(days=days)
    config["last_action"] = "snooze_7days"
    save_reminder_config(config)
    bm.BackupManager.log(f"✓ Erinnerung um {days} Tage verschoben bis {config['next_reminder_time'].strftime('%Y-%m-%d %H:%M:%S')}")

# ----------------------------
# Notification anzeigen
# ----------------------------
def show_notification(days):
    global last_notification_time
    
    if days == float('inf'):
        msg = "Noch kein Backup vorhanden. Bitte Backup durchführen!"
    else:
        msg = f"Letztes Backup ist {int(round(days))} Tage her. Bitte Backup durchführen!"
    
    toast = Notification(
        app_id="NAS Backup",
        title="NAS Backup Erinnerung",
        msg=msg
    )
    
    # Ein Button hinzufügen
    try:
        toast.add_actions(label="In 7 Tagen erinnern", 
                          launch="snooze_7days://")
    except Exception:
        # Falls add_actions nicht unterstützt wird, zeige einfach die Notification ohne Buttons
        pass
    
    toast.show()
    last_notification_time = datetime.now()



# ----------------------------
# Backup prüfen
# ----------------------------
def check_backup():
    global last_notification_time
    
    config = load_reminder_config()
    last_backup = get_last_backup()
    now = datetime.now()

    # Prüfen ob die Snooze-Zeit noch aktiv ist
    if config["next_reminder_time"] and now < config["next_reminder_time"]:
        # Snooze-Zeit noch nicht vorbei → Keine Erinnerung
        return

    # Wenn noch kein Backup gefunden
    if last_backup is None:
        if last_notification_time is None or now - last_notification_time > timedelta(days=1):
            show_notification(float('inf'))
        return

    delta_days = (now - last_backup).total_seconds() / 86400
    
    # Wenn Backup zu alt ist
    if delta_days >= MAX_DAYS:
        # Täglich erinnern, wenn keine Snooze aktiv ist
        if last_notification_time is None or now - last_notification_time > timedelta(days=1):
            show_notification(delta_days)
    else:
        # Backup ist aktuell → Reset der Konfiguration
        config["next_reminder_time"] = None
        config["last_action"] = None
        save_reminder_config(config)


# ----------------------------
# Update Trigger Prüfung
# ----------------------------
def check_update_trigger():
    """Prüft ob ein Update ausgelöst wurde und führt es durch"""
    try:
        # Prüfe ob Update-Trigger-Datei existiert
        if os.path.exists(UPDATE_TRIGGER_FILE):
            try:
                with open(UPDATE_TRIGGER_FILE, "r") as f:
                    trigger_data = json.load(f)
                os.remove(UPDATE_TRIGGER_FILE)
                
                bm.BackupManager.log("✓ Update-Trigger erkannt!")
                # Führe Update mit den gespeicherten Daten aus
                if "release_info" in trigger_data:
                    bm.BackupManager.log("Starte Update...")
                    perform_update(trigger_data["release_info"])
            except Exception as e:
                bm.BackupManager.log(f"✗ Fehler beim Verarbeiten des Update-Triggers: {e}")
        
        # Alternative: Prüfe ob Release-Info mit gespeicherter Zeit vorhanden ist
        if os.path.exists(PENDING_RELEASE_FILE):
            try:
                with open(PENDING_RELEASE_FILE, "r") as f:
                    release_data = json.load(f)
                
                # Prüfe ob die Nachricht älter als 60 Sekunden ist (Hinweis dass Button geklickt wurde)
                timestamp = datetime.fromisoformat(release_data["timestamp"])
                if datetime.now() - timestamp > timedelta(seconds=3) and datetime.now() - timestamp < timedelta(minutes=5):
                    # Wahrscheinlich wurde der Button geklickt
                    bm.BackupManager.log("✓ Update-Button Klick erkannt!")
                    os.remove(PENDING_RELEASE_FILE)
                    
                    # Baue Release-Info zurück
                    release_info = {
                        "version": release_data["version"],
                        "release_name": release_data["release_name"],
                        "download_url": release_data["download_url"],
                        "body": release_data["body"]
                    }
                    bm.BackupManager.log(f"Starte Update zu Version {release_info['version']}...")
                    perform_update(release_info)
            except Exception as e:
                bm.BackupManager.log(f"⚠ Fehler bei Button-Click Detection: {e}")
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler in update trigger check: {e}")

# ----------------------------
# Update Loop (prüft auf Trigger)
# ----------------------------
def update_trigger_loop():
    """Prüft regelmäßig auf Update-Trigger"""
    while True:
        try:
            check_update_trigger()
        except Exception as e:
            bm.BackupManager.log(f"✗ Fehler im Update Trigger Loop: {e}")
        time.sleep(2)  # Prüfe häufiger auf Trigger

# ----------------------------
# Update Check Loop
# ----------------------------
def update_check_loop():
    """Prüft in regelmäßigen Abständen auf Updates"""
    while True:
        try:
            release_info = check_for_update()
            if release_info:
                show_update_notification(release_info)
        except Exception as e:
            bm.BackupManager.log(f"✗ Fehler im Update-Check Loop: {e}")
        time.sleep(UPDATE_CHECK_INTERVAL)

def background_loop():
    while True:
        try:
            check_backup()
        except Exception:
            pass
        time.sleep(CHECK_INTERVAL)

# ----------------------------
# Main
# ----------------------------
def main():
    # Konsole verstecken wenn als .exe
    hide_console()
    
    # Autostart registrieren
    ensure_autostart()
    
    # Protocol Handler registrieren (Snooze + Backup + Update)
    register_protocol_handlers()
    
    # Update Trigger Loop Thread starten (prüft auf Button-Clicks)
    trigger_thread = threading.Thread(target=update_trigger_loop, daemon=True)
    trigger_thread.start()
    
    # Update-Check-Thread starten (Daemon)
    update_thread = threading.Thread(target=update_check_loop, daemon=True)
    update_thread.start()
    
    # Backup-Erinnerungs-Thread starten (Daemon)
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    
    # App im Hintergrund am Laufen halten (mit minimaler CPU)
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        pass

# ----------------------------
# Test Function (nur für Debugging)
# ----------------------------
def test_update():
    """Test-Funktion um Update-Funktionalität zu testen"""
    bm.BackupManager.log("=" * 70)
    bm.BackupManager.log("TEST: Update-Check wird durchgeführt...")
    bm.BackupManager.log("=" * 70)
    
    release_info = get_latest_release()
    if release_info:
        bm.BackupManager.log(f"✓ Latest Release gefunden: {release_info['version']}")
        bm.BackupManager.log(f"  Name: {release_info['release_name']}")
        bm.BackupManager.log(f"  Download URL: {release_info['download_url']}")
        print("\nUpdate-Benachrichtigung wird angezeigt...")
        show_update_notification(release_info)
    else:
        bm.BackupManager.log("✗ Konnte Release-Informationen nicht laden")

# ----------------------------
# Script starten
# ----------------------------
if __name__ == "__main__":
    # Überprüfe Parameter für Test-Modus
    if len(sys.argv) > 1 and sys.argv[1] == "--test-update":
        test_update()
    else:
        main()
