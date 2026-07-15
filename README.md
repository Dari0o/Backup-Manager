[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/) [![MIT license](https://img.shields.io/badge/License-MIT-blue.svg)](https://lbesson.mit-license.org/) [![Python application](https://github.com/Dari0o/Backup-Manager/actions/workflows/python-app.yml/badge.svg)](https://github.com/Dari0o/Backup-Manager/actions/workflows/python-app.yml) ![GitHub Downloads (all assets, all releases)](https://img.shields.io/github/downloads/Dari0o/Backup-Manager/total?color=green) ![GitHub contributors](https://img.shields.io/github/contributors/Dari0o/Backup-Manager)


# NAS Backup Manager

A fast and multithreaded backup tool.

The program intelligently compares files based on size and modification date, and copies only new or changed files.

---

## Features

* Multithreaded file scanning
* Fast parallel copying
* Intelligent file comparison (size + modification time)
* Easy CLI usage for automation
* Optional Mirror Mode (synchronization)
* Fast ZIP compression with adjustable compression level using 7-Zip
* Optional AES-256 encrypted 7z archives
* GitHub update system
* Supports large directories
* Symlink-safe (`follow_symlinks=False`)
* Progress bars with `tqdm`
* Optimized for NAS / SMB shares

---

## Installation

### Requirements

* Python 3.10+
* Windows, Ubuntu, macOS
* Network share / NAS (optional)
* 7-Zip (required for compression and encrypted 7z archives)

### Required Packages

```bash
pip install tqdm prompt_toolkit requests
```

---

## Usage

### Standard run (interactive mode)

```bash
python BackupManager.py
```

---

## CLI Arguments

You can also run the tool with arguments:

```bash
python BackupManager.py --source D:\Data --target \\nas\backup
python BackupManager.py --source D:\Data --target \\nas\backup --mirror
python BackupManager.py --source D:\Data --target \\nas\backup -i
python BackupManager.py --source D:\Data --target \\nas\backup -c 6
python BackupManager.py -c 6
python BackupManager.py --encrypt --source D:\Data --target \\nas\backup
python BackupManager.py --sevenzip --password MyPassword --source D:\Data --target \\nas\backup
python BackupManager.py --update
```

### Arguments

| Argument | Description |
|----------|-------------|
| `--source SOURCE` | Source directory path |
| `--target TARGET` | Target directory path |
| `-c, --compression` | Enable ZIP compression (0-9). `0` = no compression (fastest), `9` = maximum compression (slowest) |
| `--mirror` | Enable mirror mode (delete files in target that no longer exist in source) |
| `--sevenzip` | Create an encrypted 7z archive |
| `--password PASSWORD` | Password used for 7z encryption |
| `--update` | Check for and install updates |
| `-i` | Ignore the exclude list and copy all files |

---

## Update System

Check for a new version:

```bash
python BackupManager.py --update
```

The tool automatically downloads and installs the latest GitHub release and all requirements.

---

## Compression

Create compressed ZIP backups with adjustable compression levels using 7-Zip.

### Compression Levels

* `0` → No compression (fastest)
* `3` → Standard (balanced speed & compression)
* `9` → Maximum compression (slowest)


### With explicit paths

```bash
python BackupManager.py --source D:\Data --target D:\backup.zip -c 6
```

The compression process displays:

* File count
* Original size
* Compressed size

---

## Encryption

Create a password-protected AES-256 encrypted 7z archive.

```bash
python BackupManager.py --sevenzip --password MySecurePassword --source D:\Data --target D:\Backup.7z
```

Features:

* AES-256 encryption
* Password-protected archive
* Uses 7-Zip for maximum compatibility
* Supports large backups
* Fast multithreaded compression

---

## Mirror Mode

Mirror Mode keeps the destination folder an exact copy of the source folder.

In addition to copying new and updated files, it also removes files and directories from the destination that no longer exist in the source.

This is useful for maintaining a synchronized backup without obsolete files.

```bash
python BackupManager.py --mirror
```

### Example

Source:

```text
Documents/
├── Report.pdf
└── Photo.jpg
```

Target before backup:

```text
Documents/
├── Report.pdf
├── Photo.jpg
└── OldFile.txt
```

Target after Mirror Mode:

```text
Documents/
├── Report.pdf
└── Photo.jpg
```

`OldFile.txt` is automatically deleted because it no longer exists in the source directory.

> **Warning**
>
> Mirror Mode permanently deletes files from the destination that are not present in the source. Use this mode with caution.

---

## How does the backup work?

The program scans:

* Source files
* Destination files

It then compares:

* File size
* Modification time (`mtime`)

Only changed files are copied.

This makes the backup very fast, especially for large folders.

---

## Planned Features

* GUI version
* ~~Exclusion filters (`.git`, `node_modules`, etc.)~~ (v1.1.0)
* ~~Optional compression~~ (v1.1.2)
* ~~Optional encryption~~ (v1.1.2)
* Backup profiles

---

## License

MIT License
