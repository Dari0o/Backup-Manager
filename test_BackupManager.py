import pytest
from unittest.mock import patch, MagicMock

import BackupManager as bm
import compression as compression_module


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


# ----------------------------
# log (fully mocked)
# ----------------------------

@patch("builtins.open", new_callable=MagicMock)
@patch("os.makedirs", new_callable=MagicMock)
def test_log_function(mock_mkdir, mock_open):
    bm.log("test message")

    mock_mkdir.assert_called_once()
    mock_open.assert_called_once()


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