import pytest
from unittest.mock import patch, MagicMock

import BackupManager as bm


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