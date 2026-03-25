"""
Hilfsskript zum Verschieben der Backup-Erinnerung um 7 Tage.
Wird aufgerufen wenn der Benutzer auf "In 7 Tagen erinnern" klickt.
"""

import os
import sys

# Das Parent-Verzeichnis zum sys.path hinzufügen damit wir WindowsRuntime importieren können
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

try:
    import WindowsRuntime as wr
    import BackupManager as bm
    
    # Erinnerung um 7 Tage verschieben
    wr.snooze_reminder(days=7)
    bm.BackupManager.log("✓ Erinnerung erfolgreich um 7 Tage verschoben")
except Exception as e:
    import BackupManager as bm
    bm.BackupManager.log(f"✗ Fehler beim Verschieben der Erinnerung: {e}")

