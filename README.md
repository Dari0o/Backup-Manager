# 🖥️ Home Server Backup

**by Dario**

---

## 📌 Overview

A simple tool for creating backups to a home server (e.g., Raspberry Pi) with a built-in reminder system to ensure regular backups are not forgotten.

---

## ⚙️ Features

* 🔔 Automatic backup reminder every 2 months
* 🔁 Repeating reminder every 7 days if no backup was performed
* 📂 Configurable source and destination paths
* 🆕 Automatic update check and download of the latest release
* 🛠️ Ability to convert Python scripts into `.exe` files

---

## 🚀 Usage

### 🔹 Enable reminders

Run **`WindowsRuntime.exe`** once:

* Runs continuously in the background
* Starts automatically on system startup
* Sends a reminder after 2 months without a backup
* Then repeats every 7 days

---

### 🔹 Create a backup

Run **`PiServerBackup.exe`**

**Steps:**

1. Enter the source path (files/folders to back up)
2. Choose a destination path within:

   ```
   \\pi4\Share\Backup
   ```
3. If the folder does not exist, it will be created automatically

---

## 🧹 Uninstall

To disable reminders:

* Run **`uninstall.exe`**

---

## 🛠️ Build / Development

The **`build_exe`** folder contains `.bat` files to convert Python scripts into `.exe` files.

**Important:**

* The destination folder is currently hardcoded

---

## 🔄 Updates

* Automatically checks for new versions
* Allows downloading the latest repository release with one click

---

## 📎 Notes

* Ensure the network path `\\pi4\Share\Backup` is accessible
* Designed for Windows systems only
* Note that the software and everything around it is written in German

---
