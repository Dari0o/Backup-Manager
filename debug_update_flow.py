"""
DEBUG-Script: Zeigt den kompletten Update-Trigger Flow
"""

import os
import sys
import json

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

print("=" * 80)
print("🔍 UPDATE-TRIGGER FLOW - DIAGNOSE & ERKLÄRUNG")
print("=" * 80)

# Step 1: Erklärung des Flow
print("\n📋 FLOW SCHRITT-FÜR-SCHRITT:\n")

print("SCHRITT 1️⃣  NOTIFICATION WIRD GEZEIGT")
print("-" * 80)
print("""
  → Check-Loop findet neue Version auf GitHub
  → show_update_notification() wird aufgerufen mit:
    - release_info (Version, URL, Name)
    - handler_launch = "update_now://" ← PROTOKOLL HANDLER!
  → pending_release.json wird geschrieben (config/folder)
  → Toast Notification wird angezeigt mit Button
  → watch_for_update_trigger() Thread wird gestartet (wartet auf Trigger)
""")

print("\nSCHRITT 2️⃣  BENUTZER KLICKT 'JETZT AKTUALISIEREN' BUTTON")
print("-" * 80)
print("""
  → Windows erkennt "update_now://" Protokoll
  → Schaut in Registry nach Handler für update_now://
  → Findet: pythonw.exe update_handler.py
  → Startet: update_handler.py
""")

print("\nSCHRITT 3️⃣  UPDATE_HANDLER.PY WIRD AUSGEFÜHRT")
print("-" * 80)
print("""
  → update_handler.py startet
  → Liest _pending_release.json aus config/
  → Liest Release-Info (Version, URL, Name)
  → Schreibt _update_trigger.json zu 2 Pfaden:
    1️⃣  config/_update_trigger.json (neu)
    2️⃣  _update_trigger.json (alt, Fallback)
  → Log: "✓ Update-Trigger geschrieben"
  → Script endet
""")

print("\nSCHRITT 4️⃣  WATCHER ERKENNT TRIGGER-DATEI")
print("-" * 80)
print("""
  → watch_for_update_trigger() Thread prüft beide Pfade:
    - config/_update_trigger.json
    - _update_trigger.json
  → Findet _update_trigger.json
  → Liest Release-Info aus der Datei
  → Löscht _update_trigger.json
  → Ruft perform_update() auf
""")

print("\nSCHRITT 5️⃣  PERFORM_UPDATE() LÄDT HERUNTER UND INSTALLIERT")
print("-" * 80)
print("""
  → Lädt ZIP vom GitHub Release herunter
  → Entpackt zu _update_temp/
  → Sichert alte Dateien als Backup
  → Kopiert neue Dateien from ZIP
  → Startet Registry und Autostart neu
  → Löscht temporäre Dateien
  → Update abgeschlossen! ✅
""")

# Step 2: Prüfe aktuelle Konfiguration
print("\n" + "=" * 80)
print("🧪 AKTUELLE KONFIGURATION PRÜFEN:\n")

try:
    import BackupManager as bm
    from lib.notifications import NotificationManager
    
    config_dir = os.path.join(script_dir, "config")
    nm = NotificationManager(print, config_dir)
    
    print("✅ NotificationManager initialisiert")
    print(f"   - Config-Dir: {config_dir}")
    print(f"   - Pending Release: {nm.pending_release_file}")
    print(f"   - Update Trigger: {nm.update_trigger_file}")
    
except Exception as e:
    print(f"❌ Fehler: {e}")

# Step 3: Prüfe Protocol Handler
print("\n" + "=" * 80)
print("🔗 PROTOCOL HANDLER REGISTRIERUNG:\n")

print("Folgender Code registriert den Handler beim Start:")
print("""
  handlers = {
      "update_now": {
          "script": "update_handler",
          "description": "Download and install NAS Backup Update"
      }
  }
  
  → Windows Registry: HKEY_CURRENT_USER\\Software\\Classes\\update_now
  → Command: pythonw.exe update_handler.py
""")

print("\n⚠️  WAS KÖNNTE NICHT FUNKTIONIEREN:\n")

issues = [
    ("update_handler.py nicht gefunden", "Prüfe ob update_handler.py im Verzeichnis existiert"),
    ("Protokoll Handler nicht registriert", "Starte WindowsRuntime.py einmal komplett"),
    ("Pending Release wird nicht geschrieben", "Prüfe ob config/ Ordner beschreibbar ist"),
    ("_update_trigger.json wird nicht gelesen", "Prüfe ob Watcher läuft (daemon Thread)"),
    ("Toast zeigt keinen Button", "Prüfe winotify Version und Windows Version"),
]

for i, (issue, solution) in enumerate(issues, 1):
    print(f"{i}. {issue}")
    print(f"   → Lösung: {solution}\n")

# Step 4: Test-Anleitung
print("=" * 80)
print("🧪 TESTEN SIE DEN FLOW:\n")

print("1. Starten Sie WindowsRuntime.py (registriert Handler):")
print("   python WindowsRuntime.py\n")

print("2. Prüfen Sie die Registry für update_now Handler:")
print("   reg query HKEY_CURRENT_USER\\Software\\Classes\\update_now\n")

print("3. Testen Sie die Notification:")
print("   python WindowsRuntime.py --test-update\n")

print("4. Schauen Sie ins Backup-Log auf dem NAS:")
print("   \\\\pi4\\Share\\Backup\\backup.log\n")

print("5. Wenn kein Update kommt, prüfen Sie manuell:")
script_dir_example = r"C:\path\to\BackupManager"
print(f"   - Existiert: {script_dir_example}\\config\\_pending_release.json?")
print(f"   - Existiert: {script_dir_example}\\config\\_update_trigger.json?")
print(f"   - Existiert: {script_dir_example}\\_update_trigger.json (Fallback)?")

print("\n" + "=" * 80)
print("✅ Der Flow sollte jetzt funktionieren!")
print("=" * 80)
