import os
import shutil
import sys
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
import tqdm as tqdm_
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from typing import List, Dict, Tuple, Optional, Union, Any

try:
    from exclude_list import should_ignore_path
except ImportError:
    def should_ignore_path(entry) -> bool:
        return False

try:
    from compression import compress_to_zip
except ImportError:
    compress_to_zip = None


def should_ignore(entry) -> bool:
    if IGNORE_EXCLUDE_LIST:
        return False
    return should_ignore_path(entry)


# ----------------------------
# Global Variables
# ----------------------------
log_dir = r"\\pi4\Share\Backup"
log_file = os.path.join(log_dir, "backup.log")
THREADS = 32  # min(8, max(1, os.cpu_count() // 1.5))
VERSION = "1.1.1"  # Current version
IGNORE_EXCLUDE_LIST = False


# ----------------------------
# Logging
# ----------------------------
def log(message: str) -> None:
    time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{time}] {message}"
    print(entry)

    os.makedirs(log_dir, exist_ok=True)

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


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


def check_for_update() -> Optional[Dict[str, Any]]:
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


def install_update(release_info: Dict[str, Any]) -> bool:
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


def copy_file(src: str, dst_base: str, src_base: str, progress: Any) -> None:

    rel = os.path.relpath(src, src_base)
    dst = os.path.join(dst_base, rel)

    try:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        progress.update(os.path.getsize(src))

    except Exception as e:
        log(f"Error copying {src} to {dst}: {e}")


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
                log("ERROR: Enter a directory path")
                continue

            if not os.path.exists(source_dir):

                log(f"ERROR: Source folder does not exist: {source_dir}")
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
                log("ERROR: Enter a directory path")
                continue

            if not os.path.exists(target_dir):
                log(f"ERROR: Target folder does not exist: {target_dir}")
            else:
                break

        if source_dir == target_dir:
            log("ERROR: Source and target folders cannot be the same")
        else:
            break
    
    return source_dir, target_dir


def main(source_dir: Optional[str] = None, target_dir: Optional[str] = None) -> None:

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

B a c k u p  -  M a n a g e r 
          v 1.1.1
    """)

    # If directories not provided as arguments, prompt interactively
    if source_dir is None or target_dir is None:
        source_dir, target_dir = get_directories_interactive()
    else:
        # Validate provided directories
        if not os.path.exists(source_dir):
            log(f"ERROR: Source folder does not exist: {source_dir}")
            sys.exit(1)
        
        if not os.path.exists(target_dir):
            log(f"ERROR: Target folder does not exist: {target_dir}")
            sys.exit(1)
        
        if source_dir == target_dir:
            log("ERROR: Source and target folders cannot be the same")
            sys.exit(1)

    os.makedirs(target_dir, exist_ok=True)

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

    # If mirror mode: delete files in target that are not present in source
    if globals().get('MIRROR_MODE'):

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
                log("Mirror mode: deletion aborted by user")
                answer = "n"

            if answer not in ("y", "yes"):
                log("Mirror mode: deletion aborted by user")
            else:
                log(f"Mirror mode: deleting {len(to_delete)} items from target")

                deleted = 0
                with tqdm_.tqdm(total=len(to_delete), desc="Deleting", unit="items") as del_pbar:
                    for rel in to_delete:
                        target_path = os.path.join(target_dir, rel)
                        try:
                            if os.path.isfile(target_path) or os.path.islink(target_path):
                                os.remove(target_path)
                                deleted += 1
                                log(f"Deleted: {target_path}")
                            elif os.path.isdir(target_path):
                                shutil.rmtree(target_path)
                                deleted += 1
                                log(f"Deleted dir: {target_path}")
                        except Exception as e:
                            log(f"Error deleting {target_path}: {e}")
                        finally:
                            del_pbar.update(1)

                # Remove any now-empty directories under target
                for root, dirs, files in os.walk(target_dir, topdown=False):
                    try:
                        if not os.listdir(root):
                            os.rmdir(root)
                    except Exception:
                        pass

                log(f"Mirror mode: deleted {deleted} items")

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


if __name__ == "__main__":

    # Create argument parser
    parser = argparse.ArgumentParser(
        description="BackupManager - A fast backup tool with mirror mode support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python BackupManager.py
  python BackupManager.py --source D:\\Data --target \\\\nas\\backup
  python BackupManager.py --source D:\\Data --target \\\\nas\\backup --mirror
  python BackupManager.py --source D:\\Data --target \\\\nas\\backup -c 6
  python BackupManager.py -c 6
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
        '-i',
        action='store_true',
        dest='ignore_excludes',
        help='Ignore exclude list and copy all files'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='Check for and install updates'
    )
    
    args = parser.parse_args()
    
    # Set ignore-exclude-list flag before any scanning begins
    IGNORE_EXCLUDE_LIST = args.ignore_excludes

    # Check if compression mode is enabled
    compression_level = args.compression
    if compression_level is not None:
        if not (0 <= compression_level <= 9):
            print(f"ERROR: Compression level must be between 0 and 9, got: {compression_level}")
            sys.exit(0)
        
        if not compress_to_zip:
            print("ERROR: compression.py could not be imported")
            sys.exit(0)
        


        # Compression mode
        if args.source is None:
            # Interactive input for compression mode
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

B a c k u p  -  M a n a g e r 
          v 1.1.1
            """)
            
            while True:
                source_dir = prompt(
                    "Please enter the source directory: ",
                    completer=PathCompleter(
                        expanduser=True, only_directories=True),
                    complete_while_typing=True
                ).strip()
                
                if not source_dir:
                    print("ERROR: Please enter a path")
                    continue
                
                if not os.path.exists(source_dir):
                    print(f"ERROR: Source directory does not exist: {source_dir}")
                    continue
                
                break
            
            # Output filename
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            output_zip = os.path.join(os.path.expanduser("~"), f"backup_{timestamp}.zip")
            user_output = prompt(
                f"Output ZIP file [{output_zip}]: ",
                complete_while_typing=False
            ).strip()
            
            if user_output:
                output_zip = user_output
        else:
            # Source provided
            source_dir = args.source
            
            if not os.path.exists(source_dir):
                print(f"ERROR: Source directory does not exist: {source_dir}")
                sys.exit(1)
            
            # Determine output filename
            if args.target:
                output_zip = args.target
            else:
                timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
                output_zip = os.path.join(os.path.expanduser("~"), f"backup_{timestamp}.zip")
        
        # Start compression
        try:
            compress_to_zip(source_dir, output_zip, compression_level, log_func=log, should_ignore_func=should_ignore, num_threads=THREADS)
        except KeyboardInterrupt:
            log("Compression aborted by user")
            if os.path.exists(output_zip):
                try:
                    os.remove(output_zip)
                    log(f"Incomplete ZIP file deleted: {output_zip}")
                except:
                    pass
        except Exception as e:
            log(f"Compression error: {e}")
            sys.exit(1)
        
        sys.exit(0)

    # Check if update mode is enabled
    is_update = args.update
    # Mirror/Delete-Sync mode
    MIRROR_MODE = args.mirror

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

        # print(f"BackupManager v{current_version}")

        release_info = check_for_update()

        if release_info:

            # Check if available version is newer
            if compare_versions(current_version, release_info['version']):

                print(f"\n✓ Update available: v{release_info['version']}")
                print(
                    "Run BackupManager.py --update to install the update\n"
                )

        try:

            main(source_dir=args.source, target_dir=args.target)

        except KeyboardInterrupt:

            log("Aborted by user")

        except Exception as e:

            log(f"Unexpected error: {e}")

        input("Press Enter to exit...")
        sys.exit(0)
