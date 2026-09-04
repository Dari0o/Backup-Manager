import io
import os
import sys
import zipfile
from unittest.mock import patch, MagicMock

import pytest

import BackupManager as bm
import compression as compression_module

def is_headless():
    """Check if running in a headless environment."""
    return not os.environ.get("DISPLAY") and sys.platform != "win32" and sys.platform != "darwin"


class FakeArchiveStorage:
    def __init__(self):
        self.uploaded = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def upload_file(self, local_path, relative_path, progress):
        with open(local_path, "rb") as archive:
            self.uploaded.append((relative_path, archive.read()))
        progress.update(len(self.uploaded[-1][1]))



# ----------------------------
# Version tests
# ----------------------------

def test_get_current_version():
    assert bm.get_current_version() == bm.VERSION


def test_compare_versions_newer():
    assert bm.compare_versions("1.0.0", "1.0.1") is True


def test_compare_versions_older():
    assert bm.compare_versions("1.2.0", "1.1.9") is False


def test_compare_versions_equal():
    assert bm.compare_versions("1.0.0", "1.0.0") is False


# ----------------------------
# needs_update logic
# ----------------------------

def test_needs_update_no_target():
    assert bm.needs_update(100, 1000.0, None) is True


def test_needs_update_size_diff():
    assert bm.needs_update(100, 1000.0, (200, 1000.0)) is True


def test_needs_update_mtime_diff():
    assert bm.needs_update(100, 1000.0, (100, 9999.0)) is True


def test_needs_update_equal():
    assert bm.needs_update(100, 1000.0, (100, 1000.0)) is False


# ----------------------------
# should_ignore logic
# ----------------------------

def test_should_ignore_flag_true():
    bm.IGNORE_EXCLUDE_LIST = True
    assert bm.should_ignore(MagicMock()) is False


def test_should_ignore_flag_false():
    bm.IGNORE_EXCLUDE_LIST = False
    assert isinstance(bm.should_ignore(MagicMock()), bool)


def test_git_folder_is_ignored_by_default():
    import exclude_list

    class FakeEntry:
        def __init__(self, name, is_dir):
            self.name = name
            self._is_dir = is_dir

        def is_dir(self, follow_symlinks=False):
            return self._is_dir

        def is_file(self, follow_symlinks=False):
            return not self._is_dir

    assert exclude_list.should_ignore_path(FakeEntry(".git", True)) is True
    assert exclude_list.should_ignore_path(FakeEntry(".gitignore", False)) is False


# ----------------------------
# logging setup
# ----------------------------

def test_logger_creates_file_in_src_directory():
    import logger as logger_module
    from pathlib import Path

    logger = logger_module.setup_logger("BackupManager_test")
    logger.info("test message")

    assert Path(logger_module.LOG_FILE).exists()
    assert Path(logger_module.LOG_FILE).parent == Path(__file__).resolve().parent


# ----------------------------
# stat_file
# ----------------------------

@patch("BackupManager.log", new_callable=MagicMock)
@patch("os.makedirs", new_callable=MagicMock)
@patch("os.stat", side_effect=Exception("fail"))
def test_stat_file_fail(mock_stat, mock_makedirs, mock_log):
    result = bm.stat_file("dummy.txt")
    assert result is None


@patch("os.stat")
def test_stat_file_success(mock_stat):
    mock_stat.return_value.st_size = 123
    mock_stat.return_value.st_mtime = 456

    result = bm.stat_file("dummy.txt")

    assert result == ("dummy.txt", 123, 456)


# ----------------------------
# copy_file
# ----------------------------

@patch("BackupManager.log", new_callable=MagicMock)
@patch("os.makedirs", new_callable=MagicMock)
@patch("shutil.copy2", new_callable=MagicMock)
@patch("os.path.getsize", return_value=100)
def test_copy_file(mock_size, mock_copy, mock_mkdir, mock_log):
    progress = MagicMock()

    bm.copy_file(
        "src/file.txt",
        "dst_base",
        "src_base",
        progress
    )

    mock_mkdir.assert_called_once()
    mock_copy.assert_called_once()
    progress.update.assert_called_once_with(100)


# ----------------------------
# compare_versions edge cases
# ----------------------------

def test_compare_versions_different_length():
    assert bm.compare_versions("1.0", "1.0.1") is True


def test_compare_versions_invalid():
    assert bm.compare_versions("a.b.c", "1.0.0") is False


def test_compress_to_zip_uses_7z(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    with patch("compression.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock()
        result = compression_module.compress_to_zip(
            str(source_dir),
            str(output_dir),
            compression_level=1,
            log_func=lambda _: None,
        )

    assert result is True
    mock_run.assert_called_once()
    command = mock_run.call_args[0][0]
    assert command[0].endswith("7z.exe")
    assert command[1] == "a"
    assert command[2] == "-tzip"
    assert command[3] == "-mx=1"
    assert command[4] == "-mmt=1"


def test_compress_to_zip_stores_wav_without_compression(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("hello", encoding="utf-8")
    (source_dir / "audio.wav").write_bytes(b"\x00" * 64)
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    with patch("compression.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock()
        result = compression_module.compress_to_zip(
            str(source_dir),
            str(output_dir),
            compression_level=1,
            log_func=lambda _: None,
        )

    assert result is True
    assert mock_run.call_count == 2
    commands = [call.args[0] for call in mock_run.call_args_list]
    assert commands[0][3] == "-mx=1"
    assert commands[1][3] == "-mx=0"


def test_compress_to_zip_reports_real_7z_percentages(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("hello", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    class FakeProcess:
        def __init__(self):
            self.stdout = iter([" 10% done\n", " 45% done\n", " 100% done\n"])
            self.returncode = 0

        def wait(self):
            return 0

    seen = []
    with patch("compression.subprocess.Popen", return_value=FakeProcess()):
        result = compression_module.compress_to_zip(
            str(source_dir),
            str(output_dir),
            compression_level=1,
            log_func=lambda _: None,
            progress_callback=seen.append,
        )

    assert result is True
    assert seen == [10, 45, 100]


def test_zip_archive_can_be_uploaded_to_sftp_storage(tmp_path, monkeypatch):
    storage = FakeArchiveStorage()

    def create_archive(source, output, *args, **kwargs):
        with open(output, "wb") as archive:
            archive.write(b"zip archive")
        return True

    monkeypatch.setattr(bm, "compress_to_zip", create_archive)

    assert bm.run_archive_sftp(str(tmp_path), storage, "zip") is True
    assert storage.uploaded[0][0].endswith(".zip")
    assert storage.uploaded[0][1] == b"zip archive"


def test_7z_archive_can_be_uploaded_to_sftp_storage(tmp_path, monkeypatch):
    storage = FakeArchiveStorage()

    def create_archive(source_dir, output_file, **kwargs):
        with open(output_file, "wb") as archive:
            archive.write(b"7z archive")
        return True

    monkeypatch.setattr(bm, "encrypt_directory_7z", create_archive)

    assert bm.run_archive_sftp(str(tmp_path), storage, "7z", password="secret") is True
    assert storage.uploaded[0][0].endswith(".7z")
    assert storage.uploaded[0][1] == b"7z archive"


def _build_fake_release_zip(root_folder_name: str, files: dict) -> bytes:
    """Builds an in-memory zip mimicking a GitHub zipball download:
    a single top-level folder containing the release's files."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for rel_path, content in files.items():
            zf.writestr(f"{root_folder_name}/{rel_path}", content)
    return buf.getvalue()


def test_install_update_removes_old_files_not_in_new_release(tmp_path, monkeypatch):
    # Simulate the current install directory with src structure
    script_dir = tmp_path / "Backup-Manager"
    src_dir = script_dir / "src"
    script_dir.mkdir()
    src_dir.mkdir()

    # Old files that should NOT survive the update
    (src_dir / "BackupManager.py").write_text(
        "old script content",
        encoding="utf-8"
    )

    (script_dir / "old_helper.py").write_text(
        "stale helper",
        encoding="utf-8"
    )

    old_pkg_dir = script_dir / "old_package"
    old_pkg_dir.mkdir()

    (old_pkg_dir / "module.py").write_text(
        "stale package file",
        encoding="utf-8"
    )

    # Point __file__ to the actual src location
    monkeypatch.setattr(
        bm,
        "__file__",
        str(src_dir / "BackupManager.py")
    )

    # Build fake GitHub release ZIP
    zip_bytes = _build_fake_release_zip(
        "Dari0o-Backup-Manager-abcdef1",
        {
            "src/BackupManager.py": "new script content",
            "README.md": "new readme",
        },
    )

    mock_response = MagicMock()
    mock_response.content = zip_bytes
    mock_response.raise_for_status = MagicMock()

    with patch(
        "requests.get",
        return_value=mock_response
    ):
        result = bm.install_update(
            {
                "version": "1.1.2",
                "download_url": "http://example.com/release.zip"
            }
        )

    assert result is True

    remaining = set(os.listdir(script_dir))

    # Only new release top-level items should remain
    assert remaining == {
        "src",
        "README.md"
    }

    # Old files/dirs must be removed
    assert not (script_dir / "old_helper.py").exists()
    assert not old_pkg_dir.exists()

    # New files must exist
    assert (
        script_dir / "src" / "BackupManager.py"
    ).read_text(encoding="utf-8") == "new script content"

    assert (
        script_dir / "README.md"
    ).read_text(encoding="utf-8") == "new readme"

    # Update artifacts cleaned
    assert not (script_dir / "update_temp").exists()
    assert not (script_dir / "update.zip").exists()


def test_install_update_handles_empty_zip(tmp_path, monkeypatch):
    script_dir = tmp_path / "Backup-Manager"
    script_dir.mkdir()
    (script_dir / "BackupManager.py").write_text("old script", encoding="utf-8")

    monkeypatch.setattr(bm, "__file__", str(script_dir / "BackupManager.py"))

    # Empty zip: no top-level entries at all
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w"):
        pass
    zip_bytes = buf.getvalue()

    mock_response = MagicMock()
    mock_response.content = zip_bytes
    mock_response.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_response):
        result = bm.install_update(
            {"version": "1.1.2", "download_url": "http://example.com/release.zip"}
        )

    assert result is False
    # Nothing should have been deleted since we bail out before cleanup
    assert (script_dir / "BackupManager.py").read_text(encoding="utf-8") == "old script"


# ----------------------------
# GUI Tests
# ----------------------------

@pytest.mark.skipif(is_headless(), reason="No X11 display available")
def test_gui_arguments_mapping():
    import argparse
    from unittest.mock import MagicMock
    import tkinter as tk
    import BackupGui
    
    # Mock CLI arguments passed to GUI (non-conflicting)
    mock_args = argparse.Namespace(
        source="/path/to/source",
        target="/path/to/target",
        mirror=False,
        ignore_excludes=True,
        compression=6,
        sevenzip=False,
        password=None
    )
    
    # We create a tkinter root instance but prevent loop execution
    root = tk.Tk()
    try:
        app = BackupGui.BackupGuiApp(root, mock_args)
        
        # Verify CLI args are mapped to Tk GUI Variables
        assert app.source_var.get() == os.path.abspath("/path/to/source")
        assert app.target_var.get() == os.path.abspath("/path/to/target")
        assert app.mirror_var.get() is False
        assert app.ignore_excludes_var.get() is True
        assert app.zip_var.get() is True
        assert app.zip_level_var.get() == 6
        assert app.sevenzip_var.get() is False
    finally:
        root.destroy()


def test_gui_options_exclusivity():
    import tkinter as tk
    import BackupGui
    
    root = tk.Tk()
    try:
        app = BackupGui.BackupGuiApp(root)
        
        # 1. Select sevenzip -> should disable zip and mirror
        app.sevenzip_var.set(True)
        app.update_options_states()
        assert app.zip_var.get() is False
        assert app.mirror_var.get() is False
        
        # 2. Select zip -> should disable sevenzip
        app.sevenzip_var.set(False)
        app.zip_var.set(True)
        app.update_options_states()
        assert app.sevenzip_var.get() is False
        
        # 3. Select mirror -> should disable sevenzip and ignore excludes
        app.zip_var.set(False)
        app.mirror_var.set(True)
        app.ignore_excludes_var.set(True)
        app.update_options_states()
        assert app.sevenzip_var.get() is False
        assert app.ignore_excludes_var.get() is False
        
    finally:
        root.destroy()
