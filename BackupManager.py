import os
import shutil
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import tqdm as tqdm_
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter

# ----------------------------
# Global Variables
# ----------------------------
log_dir = r"\\pi4\Share\Backup"
log_file = os.path.join(log_dir, "backup.log")
THREADS = min(8, max(1, os.cpu_count() // 2))
VERSION = "1.0.2"  # Current version


# ----------------------------
# Logging
# ----------------------------
def log(message):
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{time}] {message}"
    print(entry)

    os.makedirs(log_dir, exist_ok=True)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


# ----------------------------
# Update Management
# ----------------------------
def get_current_version():
    """Returns the current version"""
    return VERSION


def compare_versions(current, available):
    """
    Compares two version numbers (e.g. '1.0.0' and '1.0.1')
    Returns True if a newer version is available
    """
    try:
        current_parts = [int(x) for x in current.split('.')]
        available_parts = [int(x) for x in available.split('.')]

        # Pad with zeros if lengths differ
        max_len = max(len(current_parts), len(available_parts))
        current_parts += [0] * (max_len - len(current_parts))
        available_parts += [0] * (max_len - len(available_parts))

        return available_parts > current_parts

    except Exception:
        return False


def check_for_update():
    """Checks GitHub for a new version"""
    try:
        import requests

        GITHUB_REPO = "Dari0o/Backup-Manager"
        GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

        response = requests.get(GITHUB_API, timeout=5)
        response.raise_for_status()
        release_data = response.json()

        tag = release_data.get("tag_name", "").lstrip('v')

        if not tag:
            return None

        return {
            "version": tag,
            "release_name": release_data.get("name", ""),
            "download_url": release_data.get("zipball_url", ""),
            "body": release_data.get("body", ""),
        }

    except Exception as e:
        log(f"Update check error: {e}")
        return None


def install_update(release_info):
    """Installs a new release"""
    try:
        import requests
        import zipfile

        log(f"Installing update {release_info['version']}...")

        script_dir = os.path.dirname(os.path.abspath(__file__))
        zip_path = os.path.join(script_dir, "update.zip")

        response = requests.get(release_info["download_url"], timeout=30)
        response.raise_for_status()

        with open(zip_path, "wb") as f:
            f.write(response.content)

        extract_dir = os.path.join(script_dir, "update_temp")
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        extracted_contents = os.listdir(extract_dir)

        if extracted_contents:
            source_dir = os.path.join(extract_dir, extracted_contents[0])
        else:
            log("Error: ZIP file is empty")
            return False

        for item in os.listdir(source_dir):

            src = os.path.join(source_dir, item)
            dst = os.path.join(script_dir, item)

            if os.path.isdir(src):

                if os.path.exists(dst):
                    shutil.rmtree(dst)

                shutil.copytree(src, dst)

            else:

                try:
                    shutil.copy2(src, dst)

                except OSError as e:
                    log(f"Error copying {src} to {dst}: {e}")

        shutil.rmtree(extract_dir)
        os.remove(zip_path)

        log("Update installed successfully")
        return True

    except Exception as e:
        log(f"Update installation error: {e}")
        return False


def copy_file(src, dst_base, src_base, progress):

    rel = os.path.relpath(src, src_base)
    dst = os.path.join(dst_base, rel)

    os.makedirs(os.path.dirname(dst), exist_ok=True)

    shutil.copy2(src, dst)

    progress.update(os.path.getsize(src))


# ----------------------------
# Check if file needs replacement
# ----------------------------
def needs_update(src_size, src_mtime, target_info):

    if target_info is None:
        return True

    dst_size, dst_mtime = target_info

    if src_size != dst_size:
        return True

    if abs(src_mtime - dst_mtime) > 2:
        return True

    return False


# ----------------------------
# File stat for multithreading
# ----------------------------
def stat_file(path):

    try:
        stat = os.stat(path)
        return (path, stat.st_size, stat.st_mtime)

    except Exception:
        return None


# ----------------------------
# Scan source directory (generic)
# ----------------------------
def collect_files_multithread(base_dir, desc, as_index=False):
    """
    Collects file information from a directory using multithreading

    Args:
        base_dir: Base directory to scan
        desc: tqdm description
        as_index: If True, returns a dictionary with relative paths
                  If False, returns a list with absolute paths

    Returns:
        (results, total_size)
    """

    file_list = []

    def scan_dir(path):

        try:

            for entry in os.scandir(path):

                if entry.is_file(follow_symlinks=False):
                    file_list.append(entry.path)

                elif entry.is_dir(follow_symlinks=False):
                    scan_dir(entry.path)

        except (PermissionError, OSError):
            pass

    scan_dir(base_dir)

    results = {} if as_index else []
    total_size = 0

    with tqdm_.tqdm(total=len(file_list), desc=desc, unit=" files") as pbar:

        with ThreadPoolExecutor(max_workers=THREADS) as executor:

            futures = {
                executor.submit(stat_file, f): f
                for f in file_list
            }

            for future in as_completed(futures):

                res = future.result()

                if res:

                    if as_index:
                        rel = os.path.relpath(res[0], base_dir)
                        results[rel] = (res[1], res[2])

                    else:
                        results.append(res)

                    total_size += res[1]

                pbar.update(1)

    return results, total_size


def scan_files_multithread(base, desc):
    """Scans files and returns a list with absolute paths"""
    return collect_files_multithread(base, desc, as_index=False)


def load_target_index_multithread(target_dir, desc):
    """Scans files and returns a dictionary with relative paths as keys"""
    return collect_files_multithread(target_dir, desc, as_index=True)


# ----------------------------
# MAIN
# ----------------------------
def main():

    try:

        print(r"""
    .~~.   .~~.
   '. \ ' ' / .'
    .~ .~~~..~.
   : .~.'~'.~. :
  ~ (   ) (   ) ~
 ( : '~'.~.'~' : )
  ~ .~ (   ) ~. ~
   (  : '~' :  )
    '~ .~~~. ~'
        '~'


R A S P B E R R Y   P I   N A S
    B A C K U P

    """)

        source_dir = prompt(
            "Please enter the source folder: ",
            completer=PathCompleter(expanduser=True, only_directories=True),
            complete_while_typing=True
        ).strip()

        if not os.path.exists(source_dir):

            log(
                f"ERROR: Source folder does not exist: {source_dir}"
            )

            return

        while True:

            user_input = prompt(
                "Please enter the target folder: ",
                completer=PathCompleter(expanduser=True, only_directories=True),
                complete_while_typing=True
            ).strip()

            target_dir = user_input

            os.makedirs(target_dir, exist_ok=True)

            break

        log(f"Target folder set: {target_dir}")
        log("=== Script started ===")

        source_files, source_size = scan_files_multithread(
            source_dir, "Scanning Source"
        )

        log(f"Files found in source: {len(source_files)}")
        log("Please wait, scanning target directory...")

        target_index, target_size = load_target_index_multithread(
            target_dir, "Scanning Target"
        )

        files_to_copy = []

        copy_size = 0
        new_files = 0
        replace_files = 0

        with tqdm_.tqdm(
            total=source_size,
            unit="B",
            unit_scale=True,
            desc="Comparing Files",
        ) as pbar:

            for src, size, mtime in source_files:

                rel = os.path.relpath(src, source_dir)

                target_info = target_index.get(rel)

                if needs_update(size, mtime, target_info):

                    files_to_copy.append((src, size))

                    copy_size += size

                    if target_info is None:
                        new_files += 1

                    else:
                        replace_files += 1

                pbar.update(size)

        log(f"New files: {new_files}")
        log(f"Replacing existing files: {replace_files}")

        if len(files_to_copy) > 0:

            log("Copy process started")

            with tqdm_.tqdm(
                total=copy_size,
                unit="B",
                unit_scale=True,
                desc="Copying",
            ) as pbar:

                with ThreadPoolExecutor(
                    max_workers=THREADS
                ) as executor:

                    futures = []

                    for path, size in files_to_copy:

                        futures.append(
                            executor.submit(
                                copy_file,
                                path,
                                target_dir,
                                source_dir,
                                pbar,
                            )
                        )

                    for f in as_completed(futures):
                        f.result()

            log("Copy process completed")

        else:

            log("No files need to be copied")

        log("=== Script finished ===")

    except KeyboardInterrupt:

        log("Aborted by user")

    except Exception as e:

        log(f"ERROR: {e}")


# Allow direct script execution
if __name__ == "__main__":

    # Check if update mode is enabled (--update flag)
    is_update = "--update" in sys.argv

    if is_update:

        # Update mode: check for updates and install them
        print("Checking for updates...")

        release_info = check_for_update()

        if release_info:

            print(f"Update available: {release_info['version']}")
            print("Installing update...")

            if install_update(release_info):
                print("Update installed successfully!")

            else:
                print("Update installation failed!")

        else:
            print("No new updates available.")

    else:

        # Normal mode: run backup
        current_version = get_current_version()

        print(f"BackupManager v{current_version}")

        release_info = check_for_update()

        if release_info:

            # Check if available version is newer
            if compare_versions(current_version, release_info['version']):

                print(f"\n✓ Update available: v{release_info['version']}")
                print(
                    "Run BackupManager.exe --update to install the update\n"
                )

        main()

        print("Program finished.")

