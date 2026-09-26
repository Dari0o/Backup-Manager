[![made-with-python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg)](https://www.python.org/)
[![MIT license](https://img.shields.io/badge/License-MIT-blue.svg)](https://lbesson.mit-license.org/)
[![Python application](https://github.com/Dari0o/Backup-Manager/actions/workflows/python-app.yml/badge.svg)](https://github.com/Dari0o/Backup-Manager/actions/workflows/python-app.yml)
![GitHub contributors](https://img.shields.io/github/contributors/Dari0o/Backup-Manager)

# Backup Manager

A fast and multithreaded backup tool for local folders, NAS/SMB shares and SFTP servers.

The program intelligently compares files based on size and modification date and copies only new or changed files.

---

## Features

- Fast multithreaded scanning and copying
- Intelligent file comparison
- Local, NAS/SMB and SFTP backups
- Mirror mode
- ZIP compression with adjustable compression levels
- AES-256 encrypted 7z archives
- SSH key authentication and host verification
- CLI and GUI
- GitHub update system

---

## Installation

### Requirements

- Python 3.10+
- 7-Zip (required for compression and encrypted 7z archives)

Install the required Python packages:

    python -m pip install -r requirements.txt

---

## Usage

### Standard / Interactive Mode

    python BackupManager.py

### GUI Mode

    python BackupManager.py -gui

### Examples

    python BackupManager.py --source D:\Data --target \\nas\backup

    python BackupManager.py --source D:\Data --target \\nas\backup --mirror

    python BackupManager.py --source D:\Data --target \\nas\backup -i

    python BackupManager.py --source D:\Data --target \\nas\backup -c 6

    python BackupManager.py -c 6

    python BackupManager.py --sevenzip --password MyPassword --source D:\Data --target D:\Backup.7z

    python BackupManager.py --update

---

## CLI Arguments

| Argument | Description |
|---|---|
| `--source SOURCE` | Source directory |
| `--target TARGET` | Target directory or archive |
| `-c, --compression LEVEL` | ZIP compression level (`0-9`) |
| `--mirror` | Mirror source to target and delete obsolete files |
| `--sevenzip` | Create an encrypted 7z archive |
| `--password PASSWORD` | Password for 7z encryption |
| `--update` | Check for and install updates |
| `-i` | Ignore the exclude list |
| `--sftp-host HOST` | SFTP server hostname |
| `--sftp-port PORT` | SFTP port (default: `22`) |
| `--sftp-username USER` | SFTP username |
| `--sftp-key PATH` | Local SSH private key |
| `--sftp-path PATH` | Remote backup root |
| `--sftp-known-hosts PATH` | SSH known-hosts file |

---

## SFTP Backups

SFTP backups use SSH private-key authentication and an explicit remote root.

    python BackupManager.py --source D:\Data --sftp-host 192.168.2.21 --sftp-port 22 --sftp-username backup --sftp-key C:\Users\me\.ssh\id_ed25519 --sftp-path /backups/my-backup

The SSH private key is read locally and never written to logs or configuration.

Before connecting, add the server host key to the default `~/.ssh/known_hosts` file, for example with `ssh-keyscan`.

Unknown or changed host keys are rejected.

Use `--sftp-known-hosts PATH` when a different known-hosts file is required.

The GUI provides the same fields after selecting `SFTP` as the destination.

For SFTP archive backups, ZIP and 7z files are created temporarily, uploaded under the remote root and removed locally afterward.

---

## Update System

Install the latest GitHub release with:

    python BackupManager.py --update
Or press the 'Install Update' button in the gui version.
The tool then downloads and installs the latest release and required dependencies.



---

## Compression

ZIP compression uses 7-Zip and supports levels `0-9`.

- `0` — No compression / fastest
- `3` — Balanced speed and compression
- `9` — Maximum compression / slowest

Example:

    python BackupManager.py --source D:\Data --target D:\backup.zip -c 6

The compression process displays:

- File count
- Original size
- Compressed size

---

## Encryption

Create a password-protected AES-256 encrypted 7z archive:

    python BackupManager.py --sevenzip --password MySecurePassword --source D:\Data --target D:\Backup.7z

The encryption system provides:

- AES-256 encryption
- Password-protected archives
- 7-Zip compatibility
- Support for large backups
- Multithreaded compression

The `--target` value can be a specific `.7z` file. If a directory is specified, a timestamped archive is created inside it.

---

## Mirror Mode

Mirror Mode keeps the destination synchronized with the source.

New and changed files are copied, while files and directories that no longer exist in the source are removed from the destination.

    python BackupManager.py --source D:\Data --target D:\backup --mirror

> **Warning:** Mirror Mode permanently deletes files from the destination that are not present in the source. Use with caution.

---

## How the Backup Works

The program scans the source and destination and compares:

- File size
- Modification time (`mtime`)

Only new or changed files are copied.

This makes backups fast, especially for large folders.

---

## Planned Features

- Installer
- Backup profiles
- Scheduled backups

---

## License

MIT License