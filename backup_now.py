"""
Hilfsskript zum manuellen Starten eines Backups.
Wird aufgerufen wenn der Benutzer auf "Backup jetzt" klickt.
Öffnet das BackupManager Script in der Konsole.
"""

import os
import sys
import subprocess

# Das Parent-Verzeichnis zum sys.path hinzufügen
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

try:
    import BackupManager as bm
    
    backup_script = os.path.join(script_dir, "BackupManager.py")
    
    # Backup-Skript in neuer Konsole starten
    # Shell=True ermöglicht die Konsoleneingabe
    process = subprocess.Popen(
        [sys.executable, backup_script],
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == 'win32' else 0
    )
    
    bm.BackupManager.log("✓ Backup-Prozess gestartet")
    
    # Warte bis der Prozess endet (optional)
    # process.wait()
    
except Exception as e:
    import BackupManager as bm
    bm.BackupManager.log(f"✗ Fehler beim Starten des Backups: {e}")
