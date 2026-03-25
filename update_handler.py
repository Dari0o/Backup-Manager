"""
Handler für die Update-Installation.
Wird aufgerufen wenn der Benutzer auf "Jetzt aktualisieren" Button klickt.
"""

import os
import sys
import json
import traceback
import subprocess

# Das Parent-Verzeichnis zum sys.path hinzufügen
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Logge sofort den Aufruf
def log_message(msg):
    """Einfaches Logging das sicher funktioniert"""
    try:
        import BackupManager as bm
        bm.BackupManager.log(msg)
    except:
        print(msg)

log_message("═" * 60)
log_message("✓✓✓ UPDATE HANDLER WURDE AUFGERUFEN ✓✓✓")
log_message("═" * 60)

try:
    import WindowsRuntime as wr
    import BackupManager as bm
    
    log_message("Versuche, das neueste Release zu laden...")
    
    # Lade das neueste Release erneut
    release_info = wr.get_latest_release()
    
    if release_info:
        log_message(f"✓ Release Info gefunden: {release_info['version']}")
        log_message(f"  Name: {release_info['release_name']}")
        log_message(f"  Download URL: {release_info['download_url']}")
        log_message(f"Starte Update-Installation zu Version {release_info['version']}...")
        log_message("━" * 60)
        
        # Führe das Update durch
        success = wr.perform_update(release_info)
        
        log_message("━" * 60)
        if success:
            log_message("✓✓✓ UPDATE ERFOLGREICH ABGESCHLOSSEN ✓✓✓")
            log_message("Die Dateien wurden aktualisiert und Autostart neu registriert.")
        else:
            log_message("✗✗✗ UPDATE FEHLGESCHLAGEN ✗✗✗")
            log_message("Überprüfen Sie die Log-Einträge oben für Details.")
    else:
        log_message("✗ Konnte Release-Informationen nicht abrufen")
        log_message("  Überprüfen Sie: GitHub Repo URL, Internet-Verbindung, GitHub API Rate Limit")
        
except Exception as e:
    log_message(f"✗ FEHLER IM UPDATE HANDLER ✗")
    log_message(f"Exception: {e}")
    log_message(f"Traceback:")
    log_message(traceback.format_exc())

log_message("═" * 60)
