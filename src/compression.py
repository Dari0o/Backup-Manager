import os
import subprocess
import tempfile
from datetime import datetime


class _ArchiveEntry:
    def __init__(self, path: str, name: str):
        self.path = path
        self.name = name

    def is_dir(self, follow_symlinks=False):
        return os.path.isdir(self.path)

    def is_file(self, follow_symlinks=False):
        return os.path.isfile(self.path)


def _get_store_without_compression_extensions():
    try:
        from exclude_list import load_exclude_config

        config = load_exclude_config()
        return {
            ext.lower()
            for ext in config.get("store_without_compression_extensions", [".wav"])
            if isinstance(ext, str) and ext.strip()
        }
    except Exception:
        return {".wav"}


def _should_store_without_compression(path: str, extensions=None) -> bool:
    if extensions is None:
        extensions = _get_store_without_compression_extensions()
    return os.path.splitext(path)[1].lower() in extensions


def _collect_files_for_archiving(source_path: str, should_ignore_func=None):
    files_to_archive = []

    if os.path.isfile(source_path):
        return [source_path]

    for root, _, files in os.walk(source_path):
        for filename in files:
            full_path = os.path.join(root, filename)
            entry = _ArchiveEntry(full_path, filename)
            if should_ignore_func and should_ignore_func(entry):
                continue
            files_to_archive.append(full_path)

    return files_to_archive


def _write_file_list(file_list_path: str, paths: list[str], base_dir: str) -> None:
    with open(file_list_path, "w", encoding="utf-8") as handle:
        for path in paths:
            rel_path = os.path.relpath(path, base_dir).replace("\\", "/")
            handle.write(rel_path + "\n")


def compress_to_zip(source_path: str, output_zip: str, compression_level: int = 3, log_func=None, should_ignore_func=None, num_threads: int = 32) -> bool:
    """
    Compresses a directory or file into a ZIP archive using 7-Zip.

    Args:
        source_path: Path to source directory or file
        output_zip: Path to output ZIP file or directory (if directory, ZIP is created there)
        compression_level: Compression strength (0-9)
        log_func: Optional logging function
        should_ignore_func: Optional function to determine if a path should be ignored
        num_threads: Number of CPU threads 7-Zip may use for compression (7-Zip -mmt)

    Returns:
        True if successful, False on error
    """

    if not log_func:
        log_func = print

    if not should_ignore_func:
        should_ignore_func = lambda x: False

    try:
        if not os.path.exists(source_path):
            log_func(f"ERROR: Source path does not exist: {source_path}")
            return False

        if compression_level < 0 or compression_level > 9:
            log_func(f"ERROR: Compression level must be between 0 and 9")
            return False

        if os.path.isdir(output_zip):
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            output_zip = os.path.join(output_zip, f"backup_{timestamp}.zip")

        log_func(f"Starting compression with level {compression_level}...")

        store_extensions = _get_store_without_compression_extensions()
        archive_files = _collect_files_for_archiving(source_path, should_ignore_func)
        if not archive_files:
            log_func("WARNING: No files found to compress")
            return False

        if os.path.isfile(source_path):
            archive_root = os.path.dirname(source_path) or os.getcwd()
            regular_files = [source_path] if not _should_store_without_compression(source_path, store_extensions) else []
            store_files = [source_path] if _should_store_without_compression(source_path, store_extensions) else []
        else:
            archive_root = source_path
            regular_files = [path for path in archive_files if not _should_store_without_compression(path, store_extensions)]
            store_files = [path for path in archive_files if _should_store_without_compression(path, store_extensions)]

        def run_archive_command(file_paths, compression_level_value):
            if not file_paths:
                return

            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".txt") as handle:
                list_path = handle.name

            try:
                _write_file_list(list_path, file_paths, archive_root)
                command = [
                    r"C:\Program Files\7-Zip\7z.exe",
                    "a",
                    "-tzip",
                    f"-mx={compression_level_value}",
                    f"-mmt={num_threads}",
                    output_zip,
                    "@" + list_path,
                ]
                subprocess.run(command, check=True, cwd=archive_root)
            finally:
                if os.path.exists(list_path):
                    os.remove(list_path)

        run_archive_command(regular_files, compression_level)
        run_archive_command(store_files, 0)

        if os.path.exists(output_zip):
            output_size = os.path.getsize(output_zip)
            log_func("Compression completed!")
            log_func(f"ZIP size: {_format_size(output_size)}")
            return True

        log_func("WARNING: 7-Zip reported success but no ZIP file was created")
        return True

    except Exception as e:
        log_func(f"ERROR: Compression failed: {e}")
        return False


def _format_size(bytes_size: int) -> str:
    """Format file size in readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} PB"



