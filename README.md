# NAS Backup Manager

A fast and multithreaded backup tool.

The program intelligently compares files based on size and modification date, and copies only new or changed files.

---

## Features

* Multithreaded file scanning
* Fast parallel copying
* Intelligent file comparison (size + modification time)
* Easy CLI usage for automation
* Optional Mirror Mode
* GitHub update system
* Supports large directories
* Symlink-safe (`follow_symlinks=False`)
* Progress bars with `tqdm`
* Optimized for NAS / SMB shares

---

## Installation

### Requirements

* Python 3.10+
* Windows or Linux
* Network share / NAS (optional)

### Required Packages

```bash
pip install tqdm prompt_toolkit requests
```

---

## Usage

### Standard run (interactive mode)

```bash
python backup_manager.py
```

---

### CLI Arguments

You can also run the tool with arguments:

```bash
python BackupManager.py
python BackupManager.py --source D:\Data --target \\nas\backup
python BackupManager.py --source D:\Data --target \\nas\backup --mirror
python BackupManager.py --source D:\Data --target \\nas\backup --i
python BackupManager.py --update
```

**Arguments:**

* `--source` → Source directory
* `--target` → Target directory
* `--mirror` → Enables mirror mode (deletes files in target that do not exist in source)
* `--i` → Ignore exclude list and copy all files
* `--update` → Checks and installs latest GitHub release

---

## Update System

Check for a new version:

```bash
python backup_manager.py --update
```

The tool automatically downloads and installs the latest GitHub release.

---

## Mirror-Mode

Mirror Mode keeps the destination folder an exact copy of the source folder.

In addition to copying new and updated files, it also removes files and directories from the destination that no longer exist in the source.

This is useful for maintaining a synchronized backup without obsolete files.

```bash
python backup_manager.py --mirror
```

**Example**

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
* Optional compression
* Optional encryption
* Backup profiles

---

## License

MIT License
