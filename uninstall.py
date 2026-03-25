import winreg
import os
import sys


def uninstall():
    """Entfernt den Autostart-Eintrag"""
    try:
        task_name = "NAS Backup Reminder"
        startup_key = winreg.HKEY_CURRENT_USER
        startup_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        
        key = winreg.OpenKey(startup_key, startup_path, 0, winreg.KEY_ALL_ACCESS)
        try:
            winreg.DeleteValue(key, task_name)
            print(f"✓ Autostart-Eintrag '{task_name}' wurde entfernt!")
        except WindowsError:
            print(f"× Eintrag '{task_name}' nicht in Autostart gefunden.")
        finally:
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
