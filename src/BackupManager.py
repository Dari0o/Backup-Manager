import os
import shutil
import sys
import argparse
import importlib.util
import subprocess
import tempfile
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import tqdm as tqdm_
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from typing import List, Dict, Tuple, Optional, Union, Any
from crypto_utils import encrypt_directory_7z

try:
    from exclude_list import should_ignore_path
except ImportError:
    def should_ignore_path(entry) -> bool:
        return False

try:
    from compression import compress_to_zip
except ImportError:
    compress_to_zip = None

from logger import setup_logger
from storage import LocalStorage, Storage
from storage import SFTPStorage

logger = setup_logger(__name__)


def log(message: str) -> None:
    logger.info(message)


def should_ignore(entry) -> bool:
    if IGNORE_EXCLUDE_LIST:
        return False
    return should_ignore_path(entry)


# ----------------------------
# Global Variables
# ----------------------------
THREADS = 32
VERSION = "1.1.5"  # Current version
IGNORE_EXCLUDE_LIST = False #for -i argument
MIRROR_MODE = False #for --mirror argument

# ----------------------------
# Update Management
# ----------------------------
def get_current_version() -> str:
    """Returns the current version"""
    return VERSION


def compare_versions(current: str, available: str) -> bool:
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


def detect_environment() -> Dict[str, str]:
    """Detects the current operating system and Linux distribution."""
    if sys.platform.startswith("win"):
        return {"os": "windows"}

    if sys.platform == "darwin":
        return {"os": "macos"}

    if sys.platform.startswith("linux"):
        distro = "unknown"
        distro_like = ""
        os_release_path = "/etc/os-release"

        if os.path.exists(os_release_path):
            try:
                with open(os_release_path, "r", encoding="utf-8") as handle:
                    for line in handle:
                        if "=" not in line:
                            continue
                        key, value = line.split("=", 1)
                        key = key.strip().lower()
                        value = value.strip().strip('"')
                        if key == "id":
                            distro = value.lower()
                        elif key == "id_like":
                            distro_like = value.lower()
            except OSError:
                pass

        return {"os": "linux", "distro": distro, "distro_like": distro_like}

    return {"os": "unknown"}


def get_dependency_install_commands(environment: Optional[Dict[str, str]] = None) -> List[List[str]]:
    """Returns the package-manager commands needed to install dependencies."""
    env = environment or detect_environment()
    os_name = env.get("os", "unknown")
    distro = (env.get("distro") or "").lower()
    distro_like = (env.get("distro_like") or "").lower()

    python_packages = [sys.executable, "-m", "pip", "install", "--user", "-U", "prompt_toolkit", "tqdm", "requests"]

    if os_name == "windows":
        return [
            ["winget", "install", "--id", "7zip.7zip", "-e", "--accept-source-agreements", "--accept-package-agreements"],
            python_packages,
        ]

    if os_name == "macos":
        return [
            ["brew", "install", "p7zip"],
            python_packages,
        ]

    if os_name == "linux":
        apt_like = any(item in distro or item in distro_like for item in ["debian", "ubuntu", "linuxmint", "raspbian", "pop"])
        if apt_like:
            return [
                ["apt-get", "update"],
                ["apt-get", "install", "-y", "p7zip-full"],
                python_packages,
            ]

        yum_like = any(item in distro or item in distro_like for item in ["fedora", "rhel", "centos", "rocky", "almalinux"])
        if yum_like:
            return [
                ["dnf", "install", "-y", "p7zip"],
                python_packages,
            ]

        arch_like = any(item in distro or item in distro_like for item in ["arch", "manjaro"])
        if arch_like:
            return [
                ["pacman", "-Sy", "--noconfirm", "p7zip"],
                python_packages,
            ]

        return [
            ["apt-get", "update"],
            ["apt-get", "install", "-y", "p7zip-full"],
            python_packages,
        ]

    return [python_packages]


def _run_command(command: List[str], env: Optional[Dict[str, str]] = None) -> bool:
    """Executes a command and logs failures without crashing the update flow."""
    try:
        if os.name != "nt" and command and command[0] in {"apt-get", "dnf", "pacman", "brew"}:
            if os.geteuid() != 0 and shutil.which("sudo"):
                command = ["sudo"] + command

        subprocess.run(command, check=True, env=env)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.error(f"Dependency installation failed for {' '.join(command)}: {exc}")
        return False


def _python_module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def ensure_dependencies() -> bool:
    """Installs missing system and Python dependencies needed by BackupManager."""
    env_info = detect_environment()
    logger.info(f"Detected environment: {env_info.get('os', 'unknown')} / {env_info.get('distro', 'unknown')}")

    seven_zip_available = shutil.which("7z") is not None or os.path.exists(r"C:\Program Files\7-Zip\7z.exe")
    required_modules = ["prompt_toolkit", "tqdm", "requests"]
    missing_modules = [module for module in required_modules if not _python_module_available(module)]

    if seven_zip_available and not missing_modules:
        logger.info("All dependencies already available")
        return True

    commands = get_dependency_install_commands(env_info)
    success = True

    for command in commands:
        if not command:
            continue

        if command[0] == sys.executable and len(command) >= 3 and command[1:3] == ["-m", "pip"]:
            if not missing_modules:
                continue

        env = os.environ.copy()
        if command[0] in {"apt-get", "dnf", "pacman"}:
            env.setdefault("DEBIAN_FRONTEND", "noninteractive")

        if not _run_command(command, env=env):
            success = False

    return success


def check_for_update() -> Optional[Dict[str, Any]]:
    """Checks GitHub for a new version"""
    try:
        import requests

        GITHUB_REPO = "Dari0o/Backup-Manager"
        GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

        response = requests.get(GITHUB_API, timeout=5)
        response.raise_for_status()
        release_data = response.json()

        tag = release_data.get("tag_name", "").lstrip("v")

        if not tag:
            return None

        assets = release_data.get("assets", [])

        download_url = None

        # Find uploaded release ZIP
        for asset in assets:
            if asset["name"].endswith(".zip"):
                download_url = asset["browser_download_url"]
                break

        if not download_url:
            return None

        return {
            "version": tag,
            "release_name": release_data.get("name", ""),
            "download_url": download_url,
            "body": release_data.get("body", ""),
        }

    except Exception as e:
        logger.error(f"Update check failed: {e}")
        return None


def install_update(release_info: Dict[str, Any]) -> bool:
    """Installs a new release.

    Downloads the newest GitHub release, extracts it to a temp folder,
    then replaces everything in the project root directory with the
    newest release's contents.
    """
    try:
        import requests
        import zipfile

        logger.info(f"Installing update {release_info['version']}...")

        # Project root directory (one level above src/)
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # Support both layouts:
        # 1. project/src/BackupManager.py
        #   2. project/BackupManager.py (tests / old versions)

        if os.path.basename(current_dir) == "src":
            install_dir = os.path.dirname(current_dir)
        else:
            install_dir = current_dir

        # Current running script
        current_file = os.path.abspath(__file__)

        zip_path = os.path.join(install_dir, "update.zip")

        response = requests.get(release_info["download_url"], timeout=30)
        response.raise_for_status()

        with open(zip_path, "wb") as f:
            f.write(response.content)

        extract_dir = os.path.join(install_dir, "update_temp")

        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir, ignore_errors=True)

        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)

        extracted_contents = os.listdir(extract_dir)

        if not extracted_contents:
            logger.error("Error: ZIP file is empty")
            shutil.rmtree(extract_dir, ignore_errors=True)
            os.remove(zip_path)
            return False

        # Handle GitHub ZIP structure
        if (
            len(extracted_contents) == 1
            and os.path.isdir(os.path.join(extract_dir, extracted_contents[0]))
        ):
            source_dir = os.path.join(extract_dir, extracted_contents[0])
        else:
            source_dir = extract_dir

        # Remove old files and folders
        for item in os.listdir(install_dir):

            old_path = os.path.join(install_dir, item)

            # Keep update files until cleanup
            if old_path == zip_path or old_path == extract_dir:
                continue

            # Never delete the currently running python file
            if os.path.abspath(old_path) == current_file:
                continue

            try:
                if os.path.isdir(old_path) and not os.path.islink(old_path):
                    shutil.rmtree(old_path, ignore_errors=True)

                else:
                    os.remove(old_path)

            except OSError as e:
                logger.error(f"Error removing old file {old_path}: {e}")

        # Copy new release files
        for item in os.listdir(source_dir):

            src = os.path.join(source_dir, item)
            dst = os.path.join(install_dir, item)

            try:
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

            except OSError as e:
                logger.warning(f"Skipping update file due to copy error: {src} -> {dst}: {e}")

        # Cleanup
        shutil.rmtree(extract_dir, ignore_errors=True)

        if os.path.exists(zip_path):
            os.remove(zip_path)

        logger.info("Update installed successfully")
        return True

    except Exception as e:
        logger.error(f"Update installation error: {e}")
        return False

def copy_file(src: str, dst_base: str, src_base: str, progress: Any) -> bool:
    """Copy a single file. Locked/inaccessible files are skipped without aborting the backup."""

    rel = os.path.relpath(src, src_base)
    dst = os.path.join(dst_base, rel)

    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        progress.update(os.path.getsize(src))
        return True

    except (OSError, IOError, PermissionError, shutil.Error) as e:
        # Never abort the whole backup because one file is locked or inaccessible.
        logger.warning(f"Skipping file due to copy error: {src} -> {dst}: {e}")
        return False

    except Exception as e:
        logger.warning(f"Skipping file due to unexpected copy error: {src} -> {dst}: {e}")
        return False


def copy_to_storage(src: str, src_base: str, storage: Storage, progress: Any) -> bool:
    """Upload one source file through the selected storage backend."""
    rel = os.path.relpath(src, src_base)
    try:
        storage.upload_file(src, rel, progress)
        return True
    except Exception as e:
        logger.warning(f"Skipping file due to storage error: {src} -> {rel}: {e}")
        return False


# ----------------------------
# Check if file needs replacement
# ----------------------------
def needs_update(src_size: int, src_mtime: float, target_info: Optional[Tuple[int, float]]) -> bool:

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
def stat_file(path: str) -> Optional[Tuple[str, int, float]]:

    try:
        stat = os.stat(path)
        return (path, stat.st_size, stat.st_mtime)

    except Exception:
        log(f"Error accessing file: {path}")
        return None


# ----------------------------
# Scan source directory (generic)
# ----------------------------
def collect_files_multithread(base_dir: str, desc: str, as_index: bool = False) -> Tuple[Union[List[Tuple[str, int, float]], Dict[str, Tuple[int, float]]], int]:
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
    scan_pbar = tqdm_.tqdm(
        desc=f"{desc} (scanning...)", unit=" dirs", position=0, leave=False)

    def scan_dir(path):

        try:

            for entry in os.scandir(path):

                if should_ignore(entry):
                    continue

                if entry.is_file(follow_symlinks=False):
                    file_list.append(entry.path)

                elif entry.is_dir(follow_symlinks=False):
                    scan_pbar.update(1)
                    scan_dir(entry.path)

        except (PermissionError, OSError):
            pass

    # Parallelize directory scanning
    dir_queue = [base_dir]
    with ThreadPoolExecutor(max_workers=THREADS) as scan_executor:
        while dir_queue:
            try:
                for entry in os.scandir(dir_queue.pop(0)):
                    if should_ignore(entry):
                        continue

                    if entry.is_file(follow_symlinks=False):
                        file_list.append(entry.path)
                    elif entry.is_dir(follow_symlinks=False):
                        scan_pbar.update(1)
                        dir_queue.append(entry.path)
            except (PermissionError, OSError):
                pass

    scan_pbar.close()

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


def scan_files_multithread(base: str, desc: str) -> Tuple[List[Tuple[str, int, float]], int]:
    """Scans files and returns a list with absolute paths"""
    return collect_files_multithread(base, desc, as_index=False)


def load_target_index_multithread(target_dir: str, desc: str) -> Tuple[Dict[str, Tuple[int, float]], int]:
    """Scans files and returns a dictionary with relative paths as keys"""
    return collect_files_multithread(target_dir, desc, as_index=True)


# ----------------------------
# MAIN
# ----------------------------
def get_directories_interactive() -> Tuple[str, str]:
    try:
        """Prompts the user interactively for source and target directories"""
        while True:
            while True:
                source_dir = prompt(
                    "Please enter the source folder: ",
                    completer=PathCompleter(
                        expanduser=True, only_directories=True),
                    complete_while_typing=True
                ).strip()

                if not source_dir:
                    logger.error("ERROR: Enter a directory path")
                    continue

                if not os.path.exists(source_dir):

                    logger.error(f"ERROR: Source folder does not exist: {source_dir}")
                else:
                    break

            while True:
                target_dir = prompt(
                    "Please enter the target folder: ",
                    completer=PathCompleter(
                        expanduser=True, only_directories=True),
                    complete_while_typing=True
                ).strip()

                if not target_dir:
                    logger.error("ERROR: Enter a directory path")
                    continue

                if not os.path.exists(target_dir):
                    logger.error(f"ERROR: Target folder does not exist: {target_dir}")
                else:
                    break

            if source_dir == target_dir:
                logger.error("ERROR: Source and target folders cannot be the same")
            else:
                break
            
    except KeyboardInterrupt:
        logger.info("Aborted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    
    return source_dir, target_dir

def print_logo() -> None:
        print(fr"""
██████╗  █████╗  ██████╗██╗  ██╗██╗   ██╗██████╗
██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██║   ██║██╔══██╗
██████╔╝███████║██║     █████╔╝ ██║   ██║██████╔╝
██╔══██╗██╔══██║██║     ██╔═██╗ ██║   ██║██╔═══╝
██████╔╝██║  ██║╚██████╗██║  ██╗╚██████╔╝██║
╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝

███╗   ███╗ █████╗ ███╗   ██╗ █████╗  ██████╗ ███████╗██████╗
████╗ ████║██╔══██╗████╗  ██║██╔══██╗██╔════╝ ██╔════╝██╔══██╗
██╔████╔██║███████║██╔██╗ ██║███████║██║  ███╗█████╗  ██████╔╝
██║╚██╔╝██║██╔══██║██║╚██╗██║██╔══██║██║   ██║██╔══╝  ██╔══██╗
██║ ╚═╝ ██║██║  ██║██║ ╚████║██║  ██║╚██████╔╝███████╗██║  ██║
╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═╝
v {VERSION}
    """)

def main(source_dir: Optional[str] = None, target_dir: Optional[str] = None,
         storage: Optional[Storage] = None) -> None:
    """Run a backup, using local storage unless another backend is supplied."""
    if storage is None and (source_dir is None or target_dir is None):
        source_dir, target_dir = get_directories_interactive()
    if target_dir is None:
        target_dir = ""
    selected_storage = storage or LocalStorage(target_dir)
    with selected_storage:
        _run_backup(source_dir, target_dir, selected_storage)


def _run_backup(source_dir: Optional[str], target_dir: str, storage: Storage) -> None:

    print_logo()

    # If directories not provided as arguments, prompt interactively
    if source_dir is None or target_dir is None:
        source_dir, target_dir = get_directories_interactive()
    else:
        # Validate provided directories
        if not os.path.exists(source_dir):
            logger.error(f"ERROR: Source folder does not exist: {source_dir}")
            input("Press Enter to exit...")
            sys.exit(1)
        
        if isinstance(storage, LocalStorage) and not os.path.exists(target_dir):
            logger.error(f"ERROR: Target folder does not exist: {target_dir}")
            input("Press Enter to exit...")
            sys.exit(1)
        
        if source_dir == target_dir:
            logger.error("ERROR: Source and target folders cannot be the same")
            input("Press Enter to exit...")
            sys.exit(1)

    if isinstance(storage, LocalStorage):
        os.makedirs(target_dir, exist_ok=True)

    logger.info(f"Target folder set: {target_dir}")
    logger.info("=== Script started ===")

    source_files, source_size = scan_files_multithread(
        source_dir, "Scanning Source"
    )

    logger.info(f"Files found in source: {len(source_files)}")
    logger.info("Please wait, scanning target directory...")

    target_index = storage.index()

    # If mirror mode: delete files in target that are not present in source
    if MIRROR_MODE:

        # Build set of relative paths present in source
        source_rels = set()
        for src, _, _ in source_files:
            source_rels.add(os.path.relpath(src, source_dir))

        to_delete = [rel for rel in target_index.keys()
                     if rel not in source_rels]

        if to_delete:
            # Ask for confirmation before destructive action
            try:
                answer = input(
                    f"Mirror mode: delete {len(to_delete)} items from target? (y/N): ").strip().lower()
            except KeyboardInterrupt:
                logger.info("Mirror mode: deletion aborted by user")
                answer = "n"

            if answer not in ("y", "yes"):
                logger.info("Mirror mode: deletion aborted by user")
                input("Press Enter to exit...")
                sys.exit(0)
            else:
                logger.info(f"Mirror mode: deleting {len(to_delete)} items from target")

                deleted = 0
                with tqdm_.tqdm(total=len(to_delete), desc="Deleting", unit="items") as del_pbar:
                    for rel in to_delete:
                        try:
                            storage.delete(rel)
                            deleted += 1
                        except Exception as e:
                            logger.error(f"Error deleting {rel}: {e}")
                        finally:
                            del_pbar.update(1)

                logger.info(f"Mirror mode: deleted {deleted} items")

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

    logger.info(f"New files: {new_files}")
    logger.info(f"Replacing existing files: {replace_files}")

    if len(files_to_copy) > 0:

        logger.info("Copy process started")
        skipped_files = 0

        with tqdm_.tqdm(
            total=copy_size,
            unit="B",
            unit_scale=True,
            desc="Copying",
        ) as pbar:
            if storage.supports_cancellation():
                for file_index, (path, size) in enumerate(files_to_copy):
                    if getattr(storage, "cancel_event", None) is not None and storage.cancel_event.is_set():
                        logger.warning("Copy process cancelled")
                        skipped_files += len(files_to_copy) - file_index
                        break
                    if not copy_to_storage(path, source_dir, storage, pbar):
                        skipped_files += 1
            else:
                with ThreadPoolExecutor(max_workers=THREADS) as executor:
                    futures = [
                        executor.submit(copy_to_storage, path, source_dir, storage, pbar)
                        for path, size in files_to_copy
                    ]
                    for f in as_completed(futures):
                        if not f.result():
                            skipped_files += 1

        if skipped_files:
            logger.warning(f"Copy process completed with {skipped_files} skipped file(s) due to access errors")
        else:
            logger.info("Copy process completed")

    else:

        logger.info("No files need to be copied")

    logger.info("=== Script finished ===")


def run_archive_sftp(source_dir: str, storage: SFTPStorage, archive_type: str,
                     compression_level: int = 3, password: Optional[str] = None) -> bool:
    """Create an archive temporarily, upload it to SFTP, then remove the local copy."""
    extension = ".7z" if archive_type == "7z" else ".zip"
    archive_name = f"backup_{datetime.now().strftime('%Y_%m_%d_%H_%M_%S')}{extension}"

    with tempfile.TemporaryDirectory(prefix="backup_manager_") as temp_dir:
        local_archive = os.path.join(temp_dir, archive_name)
        try:
            with storage:
                if archive_type == "7z":
                    created = encrypt_directory_7z(
                        source_dir=source_dir,
                        output_file=local_archive,
                        password=password or "",
                        log_func=logger.info,
                    )
                else:
                    created = compress_to_zip(
                        source_dir,
                        local_archive,
                        compression_level,
                        log_func=logger.info,
                        should_ignore_func=should_ignore,
                        num_threads=THREADS,
                    )
                if not created:
                    return False

                archive_size = os.path.getsize(local_archive)
                with tqdm_.tqdm(total=archive_size, unit="B", unit_scale=True,
                                desc="Uploading archive") as progress:
                    storage.upload_file(local_archive, archive_name, progress)
            logger.info("Backup completed: %s", archive_name)
            return True
        except Exception as exc:
            logger.error("SFTP archive backup failed: %s", exc)
            return False


if __name__ == "__main__":

    # Create argument parser
    parser = argparse.ArgumentParser(
        description="BackupManager - A fast backup utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python BackupManager.py
  python BackupManager.py --source D:\\Data --target \\\\nas\\backup
  python BackupManager.py --source D:\\Data --target \\\\nas\\backup --mirror
  python BackupManager.py --source D:\\Data --target \\\\nas\\backup -c 6
  python BackupManager.py -c 6
  python BackupManager.py --sevenzip --password 1234  --source D:\\Data --target \\\\nas\\backup
  python BackupManager.py --update
        """
    )
    
    parser.add_argument(
        '--source',
        type=str,
        help='Source directory path',
        default=None
    )
    parser.add_argument(
        '--target',
        type=str,
        help='Target directory path',
        default=None
    )
    parser.add_argument('--sftp-host', type=str, default=None, help='SFTP host')
    parser.add_argument('--sftp-port', type=int, default=22, help='SFTP port')
    parser.add_argument('--sftp-username', type=str, default=None, help='SFTP username')
    parser.add_argument('--sftp-key', type=str, default=None, help='SSH private key path')
    parser.add_argument('--sftp-path', type=str, default=None, help='Remote SFTP backup path')
    parser.add_argument('--sftp-known-hosts', type=str, default=None, help='SSH known-hosts file path')
    parser.add_argument(
        '-c', '--compression',
        type=int,
        help='Enable compression and set compression level (0-9). 0=no compression (fastest), 9=maximum compression (slowest)',
        default=None
    )
    parser.add_argument(
        '--mirror',
        action='store_true',
        help='Enable mirror mode (delete files in target that are not in source)'
    )
    parser.add_argument(
        '--sevenzip',
        action='store_true',
        help='Enable 7z encrypted backup mode'
    )
    parser.add_argument(
        '--password',
        type=str,
        help='Password for 7z encryption',
        default=None
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Check for and install updates'
    )
    parser.add_argument(
        '-i',
        action='store_true',
        dest='ignore_excludes',
        help='Ignore exclude list and copy all files'
    )
    parser.add_argument(
        '-gui', '--gui',
        action='store_true',
        help='Start BackupManager in GUI mode'
    )
    args = parser.parse_args()

    # ==========================================
    # DEVELOPMENT ONLY: Launch GUI mode
    # ==========================================
    if args.gui:
        try:
            import BackupGui
            BackupGui.start_gui(args)
            sys.exit(0)
        except Exception as e:
            logger.error(f"ERROR: Failed to start GUI: {e}")
            sys.exit(1)
    # ==========================================
    
    # Set ignore-exclude-list flag before any scanning begins
    IGNORE_EXCLUDE_LIST = args.ignore_excludes

    # Validate argument combinations
    if args.mirror and (args.sevenzip or args.password):
        logger.error("ERROR: Mirror mode is not compatible with 7z encrypted backup")
        input("Press Enter to exit...")
        sys.exit(0)

    if args.mirror and IGNORE_EXCLUDE_LIST:
       logger.error("ERROR: Mirror mode is not compatible with the ignore-exclude-list argument")
       input("Press Enter to exit...")
       sys.exit(0)

    if args.update and (args.sevenzip or args.password or args.source or args.target or args.mirror or args.compression or args.ignore_excludes):
        logger.error("ERROR: Update mode cannot be combined with other options.")
        input("Press Enter to exit...")
        sys.exit(0)

    # Check if compression mode is enabled
    compression_level = args.compression
    if compression_level is not None:
        if not (0 <= compression_level <= 9):
            print(f"ERROR: Compression level must be between 0 and 9, got: {compression_level}")
            sys.exit(0)
        
        if not compress_to_zip:
            print("ERROR: compression.py could not be imported")
            sys.exit(0)
        
    sftp_requested = any((args.sftp_host, args.sftp_username, args.sftp_key, args.sftp_path))
    if sftp_requested:
        if not all((args.sftp_host, args.sftp_username, args.sftp_key, args.sftp_path, args.source)):
            logger.error("ERROR: SFTP requires --source, --sftp-host, --sftp-username, --sftp-key, and --sftp-path")
            sys.exit(1)
        sftp_storage = SFTPStorage(
            host=args.sftp_host,
            port=args.sftp_port,
            username=args.sftp_username,
            key_path=args.sftp_key,
            remote_root=args.sftp_path,
            known_hosts_path=args.sftp_known_hosts,
        )
        if args.sevenzip:
            if not args.password:
                logger.warning("WARNING: --password is required")
                sys.exit(1)
            success = run_archive_sftp(args.source, sftp_storage, "7z", password=args.password)
        elif args.compression is not None:
            success = run_archive_sftp(args.source, sftp_storage, "zip", compression_level=args.compression)
        else:
            main(source_dir=args.source, target_dir=args.sftp_path, storage=sftp_storage)
            success = True
        sys.exit(0 if success else 1)

    if args.sevenzip:
        logger.info("Initializing 7z encrypted backup...")

        if not args.password:
            logger.warning("WARNING: --password is required")
            sys.exit(1)

        if not args.source:
            logger.warning("WARNING: --source is required")
            sys.exit(1)

        if not args.target:
            logger.warning("WARNING: --target is required")
            sys.exit(1)

        # target is folder → not file
        target_dir = args.target or os.getcwd()

        os.makedirs(target_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

        output_file = os.path.join(
            target_dir,
            f"backup_{timestamp}.7z"
        )

        success = encrypt_directory_7z(
            source_dir=args.source,
            output_file=output_file,
            password=args.password,
            log_func=logger.info
        )

        if success:
            logger.info(f"Backup completed: {output_file}")
        else:
            logger.error("Backup failed")

        sys.exit(0)

    if args.mirror:
        MIRROR_MODE = True

    # Interactive compression mode
    if args.compression:
        
        print_logo()
            
        # Interactive mode
        if args.source is None:

            source_dir, target_dir = get_directories_interactive()

            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            output_zip = os.path.join(
                os.path.expanduser("~"),
                f"backup_{timestamp}.zip"
            )

            if target_dir:
                output_zip = target_dir

        # CLI mode
        else:

            source_dir = args.source

            if not os.path.exists(source_dir):
                print(f"ERROR: Source directory does not exist: {source_dir}")
                sys.exit(1)

            if args.target:
                output_zip = args.target
            else:
                timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
                output_zip = os.path.join(
                    os.path.expanduser("~"),
                    f"backup_{timestamp}.zip"
                )
        
        # Start compression
        try:
            compress_to_zip(source_dir, output_zip, compression_level, log_func=logger.info, should_ignore_func=should_ignore, num_threads=THREADS)
        except KeyboardInterrupt:
            logger.info("Compression aborted by user")
            if os.path.exists(output_zip):
                try:
                    os.remove(output_zip)
                    logger.info(f"Incomplete ZIP file deleted: {output_zip}")
                except:
                    pass
        except Exception as e:
            logger.error(f"Compression error: {e}")
            sys.exit(1)
        
        sys.exit(0)

    # Check if update mode is enabled
    is_update = args.update

    if is_update:

        print("Checking dependencies for this system...")
        ensure_dependencies()

        # Update mode: check for updates and install them
        print("Checking for updates...")

        release_info = check_for_update()
        current_version= get_current_version()

        # Check if available version is newer
        if release_info and compare_versions(current_version, release_info['version']):

            print(f"Update available: {release_info['version']}")
            print("Installing update...")
            install_update(release_info)

        else:
            print("No new updates available.")

    else:

        # Normal mode: run backup
        current_version = get_current_version()

        # print(f"BackupManager v{current_version}")

        release_info = check_for_update()
        if release_info and compare_versions(current_version, release_info['version']):
                print(f"\n✓ Update available: v{release_info['version']}")
                print(
                    "Run BackupManager.py --update to install the update\n"
                )

        try:

            main(source_dir=args.source, target_dir=args.target)

        except KeyboardInterrupt:

            logger.info("Aborted by user")

        except Exception as e:

            logger.error(f"Unexpected error: {e}")

        input("Press Enter to exit...")
        sys.exit(0)
