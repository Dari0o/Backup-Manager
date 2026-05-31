# Raspberry Pi NAS Backup Manager

Ein schnelles und multithreaded Backup-Tool für Windows und Raspberry Pi NAS-Systeme.
Das Programm vergleicht Dateien intelligent anhand von Größe und Änderungsdatum und kopiert nur neue oder geänderte Dateien.

---

## Features

* Multithreaded Datei-Scanning
* Schnelles paralleles Kopieren
* Fortschrittsanzeigen mit `tqdm`
* Automatische Ordnerstruktur-Erstellung
* GitHub Update-System
* Unterstützt große Verzeichnisse
* Symlink-sicher (`follow_symlinks=False`)
* Optimiert für NAS / SMB Shares
* Einfache CLI-Bedienung

---

## Installation

### Voraussetzungen

* Python 3.10+
* Windows oder Linux
* Netzwerkfreigabe / NAS optional

### Benötigte Pakete

```bash
pip install tqdm prompt_toolkit requests
```

---

## Verwendung

Programm starten:

```bash
python backup_manager.py
```

Danach:

1. Source-Ordner auswählen
2. Ziel-Ordner auswählen
3. Backup startet automatisch

---

## Update-System

Auf neue Version prüfen:

```bash
python backup_manager.py --update
```

Das Tool lädt automatisch den neuesten GitHub Release herunter und installiert ihn.

---

## Wie funktioniert das Backup?

Das Programm scannt:

* Quelldateien
* Zieldateien

und vergleicht anschließend:

* Dateigröße
* Änderungszeit (`mtime`)

Nur geänderte Dateien werden kopiert.

Das macht das Backup sehr schnell, besonders bei großen Ordnern.

---

## Performance

Das Tool verwendet automatisch:

```python
min(8, max(1, os.cpu_count() // 2))
```

Threads.

Dadurch wird:

* die CPU nicht vollständig ausgelastet
* NAS-Systeme nicht überlastet
* HDD-Seeking reduziert

---

## Geplante Features

* GUI-Version
* Ausschlussfilter (`.git`, `node_modules`, etc.)
* Kompression
* Verschlüsselung
* Backup-Profile

---

## Lizenz

MIT License

---

## Autor

Entwickelt von Dario.
