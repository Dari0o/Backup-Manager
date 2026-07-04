import os
import subprocess
import shutil
import re
import tqdm


# ----------------------------
# 7z PATH RESOLUTION
# ----------------------------
def get_7z_path() -> str:
    """
    Resolves 7z.exe path from environment, default install paths, or PATH.
    """

    env_path = os.environ.get("SEVENZIP_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    default_paths = [
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
    ]

    for path in default_paths:
        if os.path.exists(path):
            return path

    path = shutil.which("7z")
    if path:
        return path

    raise FileNotFoundError("7z.exe not found. Install 7-Zip or set SEVENZIP_PATH.")


# ----------------------------
# INTERNAL PROGRESS PARSER
# ----------------------------
def _parse_progress(line: str, last_value: int, progress_bar: tqdm.tqdm) -> int:
    """
    Extracts percentage from 7z output safely.
    """
    match = re.search(r"(\d{1,3})%", line)
    if match:
        value = int(match.group(1))
        if value > last_value:
            progress_bar.update(value - last_value)
            return value
    return last_value


# ----------------------------
# ENCRYPT DIRECTORY
# ----------------------------
def encrypt_directory_7z(
    source_dir: str,
    output_file: str,
    password: str,
    log_func=print
) -> bool:

    try:
        if not os.path.exists(source_dir):
            log_func(f"Source does not exist: {source_dir}")
            return False

        sevenzip = get_7z_path()

        cmd = [
            sevenzip,
            "a",
            "-t7z",
            "-mhe=on",
            "-p" + password,
            output_file,
            source_dir,
            "-bsp1",
            "-bso0"
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        progress = tqdm.tqdm(
            desc="7z Encrypting",
            total=100,
            unit="%"
        )

        last = 0

        for line in process.stdout:
            try:
                last = _parse_progress(line, last, progress)
            except Exception:
                pass

        process.wait()
        progress.close()

        if process.returncode != 0:
            log_func("7z encryption failed")
            return False

        return True

    except FileNotFoundError as e:
        log_func(str(e))
        return False

    except Exception as e:
        log_func(f"Encryption error: {e}")
        return False


# ----------------------------
# EXTRACT ARCHIVE
# ----------------------------
def extract_7z(
    archive_file: str,
    output_dir: str,
    password: str,
    log_func=print
) -> bool:

    try:
        if not os.path.exists(archive_file):
            log_func(f"Archive not found: {archive_file}")
            return False

        sevenzip = get_7z_path()
        os.makedirs(output_dir, exist_ok=True)

        cmd = [
            sevenzip,
            "x",
            "-o" + output_dir,
            "-p" + password,
            archive_file,
            "-y",
            "-bsp1",
            "-bso0"
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        progress = tqdm.tqdm(
            desc="7z Extracting",
            total=100,
            unit="%"
        )

        last = 0

        for line in process.stdout:
            try:
                last = _parse_progress(line, last, progress)
            except Exception:
                pass

        process.wait()
        progress.close()

        return process.returncode == 0

    except Exception as e:
        log_func(f"Extraction error: {e}")
        return False