"""
Handler für die Update-Installation.
Wird aufgerufen wenn der Benutzer auf "Jetzt aktualisieren" Button klickt.
"""

import os
import sys
import json

# Das Parent-Verzeichnis zum sys.path hinzufügen
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

try:
    import WindowsRuntime as wr
    import BackupManager as bm
    
    # Lade das neueste Release erneut
    release_info = wr.get_latest_release()
    
    if release_info:
        bm.BackupManager.log(f"Starte Update zu Version {release_info['version']}...")
        
        # Führe das Update durch
        success = wr.perform_update(release_info)
        
        if success:
            bm.BackupManager.log("✓ Update abgeschlossen!")
            # Neustarten des WindowsRuntime (optional - kann zur Reinitialisierung nötig sein)
            # subprocess.Popen([sys.executable, os.path.join(script_dir, "WindowsRuntime.py")])
        else:
            bm.BackupManager.log("✗ Update fehlgeschlagen")
    else:
        bm.BackupManager.log("✗ Konnte Release-Informationen nicht abrufen")
        
except Exception as e:
    try:
        import BackupManager as bm
        bm.BackupManager.log(f"✗ Fehler im Update Handler: {e}")
    except:
        print(f"Fehler: {e}")
