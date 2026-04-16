"""
Snooze Handler - Wird aufgerufen wenn Benutzer Snooze-Button klickt
Protocol Handler: snooze_7days://
Verschiebt Backup-Erinnerung um 7 Tage
"""

import os
import sys
from datetime import datetime, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

import BackupManager as bm
from lib.notifications import NotificationManager

CONFIG_DIR = os.path.join(script_dir, "config")
os.makedirs(CONFIG_DIR, exist_ok=True)

notification_manager = NotificationManager(bm.BackupManager.log, CONFIG_DIR)

bm.BackupManager.log("=" * 60)
bm.BackupManager.log("⏱ Snooze Handler aufgerufen")
bm.BackupManager.log("=" * 60)

try:
    notification_manager.snooze_backup_reminder(days=7)
    bm.BackupManager.log("✓ Erinnerung um 7 Tage verschoben")
    bm.BackupManager.log("=" * 60)
    
except Exception as e:
    bm.BackupManager.log(f"✗ Fehler: {e}")
    import traceback
    traceback.print_exc()
    bm.BackupManager.log("=" * 60)

