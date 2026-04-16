"""
Update Handler - Wird aufgerufen wenn Benutzer Update-Button klickt
Protocol Handler: update_now://
Führt das Update direkt durch
"""

import os
import json
import sys
import zipfile
import shutil
from datetime import datetime

# Importiere BackupManager für Logging
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import BackupManager as bm


def _get_config_dir():
    """Bestimme Konfigurationsverzeichnis."""
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        if "_MEI" in exe_dir or "Temp" in exe_dir:
            if hasattr(bm.BackupManager, 'log_file'):
                log_dir = os.path.dirname(bm.BackupManager.log_file)
                if os.path.exists(log_dir):
                    return log_dir
        return exe_dir
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_DIR = os.path.join(_get_config_dir(), "config")
PENDING_FILE = os.path.join(CONFIG_DIR, "_pending_release.json")


def perform_update():
    """Führe Update durch."""
    
    bm.BackupManager.log("=" * 60)
    bm.BackupManager.log("🔄 Update Handler aufgerufen")
    bm.BackupManager.log("=" * 60)
    
    # Lade Pending Release Info
    if not os.path.exists(PENDING_FILE):
        bm.BackupManager.log("✗ Keine Update-Info vorhanden")
        return False
    
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            release_info = json.load(f)
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler beim Lesen Release-Info: {e}")
        return False
    
    bm.BackupManager.log(f"📦 Update für Version {release_info['version']}")
    
    try:
        import requests
        
        script_dir = _get_config_dir()
        temp_dir = os.path.join(script_dir, "_update_temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Lade Update herunter
        bm.BackupManager.log(f"⬇️  Lade herunter...")
        response = requests.get(release_info["download_url"], timeout=60, stream=True)
        response.raise_for_status()
        
        zip_path = os.path.join(temp_dir, "update.zip")
        with open(zip_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        bm.BackupManager.log("📦 Entpacke...")
        extract_dir = os.path.join(temp_dir, "extracted")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_dir)
        
        # Finde interne Struktur
        internal_source = None
        for root, dirs, _ in os.walk(extract_dir):
            if "BackupManager" in dirs or "Backup-Manager" in dirs:
                internal_source = root
                break
        
        if not internal_source:
            bm.BackupManager.log("✗ Archiv hat unerwartete Struktur")
            shutil.rmtree(temp_dir, ignore_errors=True)
            return False
        
        # Backup alte Dateien
        backup_dir = os.path.join(script_dir, ".backup_old")
        if os.path.exists(backup_dir):
            shutil.rmtree(backup_dir, ignore_errors=True)
        
        bm.BackupManager.log("💾 Backup alte Dateien...")
        os.makedirs(backup_dir, exist_ok=True)
        for item in os.listdir(script_dir):
            if item.startswith("_") or item in (".backup_old", "config"):
                continue
            src = os.path.join(script_dir, item)
            dst = os.path.join(backup_dir, item)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            elif os.path.isdir(src) and item != "__pycache__":
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        
        # Kopiere neue Dateien
        bm.BackupManager.log("📝 Kopiere neue Dateien...")
        for item in os.listdir(internal_source):
            src = os.path.join(internal_source, item)
            dst = os.path.join(script_dir, item)
            if os.path.exists(dst):
                if os.path.isfile(dst):
                    os.remove(dst)
                elif os.path.isdir(dst):
                    shutil.rmtree(dst)
            if os.path.isfile(src):
                shutil.copy2(src, dst)
            elif os.path.isdir(src):
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Lösche Pending File
        try:
            os.remove(PENDING_FILE)
        except Exception:
            pass
        
        bm.BackupManager.log(f"✅ Update zu {release_info['version']} erfolgreich!")
        bm.BackupManager.log("=" * 60)
        return True
        
    except Exception as e:
        bm.BackupManager.log(f"✗ Fehler beim Update: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    perform_update()
