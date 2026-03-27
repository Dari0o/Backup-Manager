# 🖥️ Home Server Backup

**by Dario**

---

## 📌 Übersicht

Ein einfaches Tool zum Erstellen von Backups auf einem Home-Server (z. B. Raspberry Pi) mit integrierter Erinnerungsfunktion, damit regelmäßige Sicherungen nicht vergessen werden.

---

## ⚙️ Features

* 🔔 Automatische Backup-Erinnerung alle 2 Monate
* 🔁 Wiederholung der Erinnerung alle 7 Tage, falls kein Backup erfolgt
* 📂 Frei wählbare Quell- und Zielpfade
* 🆕 Automatische Update-Prüfung + Download des neuesten Releases
* 🛠️ Möglichkeit, Python-Skripte in `.exe` umzuwandeln

---

## 🚀 Verwendung

### 🔹 Erinnerungen aktivieren

Starte **`WindowsRuntime.exe`** einmal:

* Läuft anschließend dauerhaft im Hintergrund
* Startet automatisch beim Hochfahren
* Erinnerung nach 2 Monaten ohne Backup
* Danach alle 7 Tage erneut

---

### 🔹 Backup erstellen

Starte **`PiServerBackup.exe`**

**Ablauf:**

1. Quellpfad eingeben (zu sichernde Dateien/Ordner)
2. Zielpfad wählen innerhalb von:

   ```
   \\pi4\Share\Backup
   ```
3. Falls der Ordner nicht existiert, wird er automatisch erstellt

---

## 🧹 Deinstallation

Zum Deaktivieren der Erinnerungen:

* **`uninstall.exe`** ausführen

---

## 🛠️ Build / Entwicklung

Im Ordner **`build_exe`** befinden sich `.bat`-Dateien zum Erstellen von `.exe`-Dateien aus Python-Skripten.

**Wichtig:**

* Der Zielordner (*Destination Folder*) ist fest im Code hinterlegt (hardcoded)

---

## 🔄 Updates

* Automatische Suche nach neuen Versionen
* Download des neuesten Repository-Releases per Knopfdruck

---

## 📎 Hinweise

* Netzwerkpfad `\\pi4\Share\Backup` muss erreichbar sein
* Nur für Windows-Systeme geeignet

---
