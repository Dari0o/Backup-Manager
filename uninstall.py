import winreg
import os
import sys


def uninstall():
    """Entfernt den Autostart-Eintrag"""
    try:
        startup_key = winreg.HKEY_CURRENT_USER
        startup_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        # Versuche neue Task-Namen zuerst
        task_names = [
            "NAS Backup Manager",       # Neuer Name
            "NAS Backup Reminder",      # Alternativer neuer Name
            "WindowsRuntime.exe",       # Alter Name (Python-Skript)
            "BackupReminder",           # Möglicher alternativer Name
        ]
        
        key = winreg.OpenKey(startup_key, startup_path, 0, winreg.KEY_ALL_ACCESS)
        removed = False
        
        for task_name in task_names:
            try:
                winreg.DeleteValue(key, task_name)
                print(f"✓ Autostart-Eintrag '{task_name}' wurde entfernt!")
                removed = True
                break
            except WindowsError:
                continue
        
        if not removed:
            print(f"× Kein bekannter Autostart-Eintrag gefunden.")
            print(f"\nGesuchte Namen: {', '.join(task_names)}")
        
        winreg.CloseKey(key)
            
    except Exception as e:
        print(f"× Fehler beim Entfernen: {e}")
        return False
    
    return True


if __name__ == "__main__":
    print("=========================================")
    print("PiServer Backup Reminder - Deinstallation")
    print("=========================================\n")
    
    input("Drücke Enter zum Entfernen aus dem Autostart...")
    
    if uninstall():
        print("\nProgramm wurde erfolgreich deinstalliert.")
        print("Es wird nicht mehr beim Start automatisch geladen.")
    else:
        print("\nFehler bei der Deinstallation!")
    
    input("\nDrücke Enter zum Schließen...")
