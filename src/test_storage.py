import stat
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from storage import SFTPStorage, StorageError


class FakeSFTP:
    def __init__(self):
        self.directories = {"/"}
        self.files = {}
        self.closed = False
        self.put_calls = []

    def stat(self, path):
        if path not in self.directories and path not in self.files:
            raise IOError("missing")
        return MagicMock()

    def mkdir(self, path):
        self.directories.add(path)

    def listdir_attr(self, path):
        entries = []
        for name, (mode, size, mtime) in self.files.items():
            parent = "/".join(name.rstrip("/").split("/")[:-1]) or "/"
            if parent == path.rstrip("/"):
                entries.append(SimpleNamespace(
                    filename=name.rsplit("/", 1)[-1], st_mode=mode,
                    st_size=size, st_mtime=mtime,
                ))
        for directory in self.directories:
            if directory != "/" and "/".join(directory.rstrip("/").split("/")[:-1]) == path.rstrip("/"):
                entries.append(SimpleNamespace(
                    filename=directory.rsplit("/", 1)[-1], st_mode=stat.S_IFDIR,
                    st_size=0, st_mtime=0,
                ))
        return entries

    def put(self, local, remote):
        self.put_calls.append((local, remote))

    def utime(self, path, times):
        pass

    def remove(self, path):
        self.files.pop(path, None)

    def close(self):
        self.closed = True


class FakeParamiko:
    def __init__(self, sftp, connect_error=None):
        self.sftp = sftp
        self.connect_error = connect_error
        self.client = None

    class AutoAddPolicy:
        pass

    def SSHClient(self):
        owner = self

        class Client:
            def set_missing_host_key_policy(self, policy):
                self.policy = policy

            def connect(self, **kwargs):
                self.kwargs = kwargs
                if owner.connect_error:
                    raise owner.connect_error

            def open_sftp(self):
                return owner.sftp

            def close(self):
                self.closed = True

        self.client = Client()
        return self.client


def make_storage(tmp_path, remote_root="/backups/my-backup"):
    key = tmp_path / "id_ed25519"
    key.write_text("test key", encoding="utf-8")
    return SFTPStorage("example.test", "backup", str(key), remote_root)


def test_connect_creates_remote_root_and_cleanup(tmp_path):
    fake_sftp = FakeSFTP()
    fake_paramiko = FakeParamiko(fake_sftp)
    storage = make_storage(tmp_path)

    with patch.dict(sys.modules, {"paramiko": fake_paramiko}):
        storage.connect()
        assert "/backups" in fake_sftp.directories
        assert "/backups/my-backup" in fake_sftp.directories
        storage.close()

    assert fake_sftp.closed is True
    assert fake_paramiko.client.closed is True


def test_authentication_failure_closes_partial_connection(tmp_path):
    fake_sftp = FakeSFTP()
    fake_paramiko = FakeParamiko(fake_sftp, connect_error=RuntimeError("authentication failed"))
    storage = make_storage(tmp_path)

    with patch.dict(sys.modules, {"paramiko": fake_paramiko}):
        with pytest.raises(StorageError):
            storage.connect()

    assert fake_paramiko.client.closed is True


def test_index_returns_remote_file_metadata(tmp_path):
    fake_sftp = FakeSFTP()
    fake_sftp.directories.update({"/backups", "/backups/my-backup", "/backups/my-backup/sub"})
    fake_sftp.files["/backups/my-backup/file.txt"] = (stat.S_IFREG, 12, 100.0)
    fake_sftp.files["/backups/my-backup/sub/child.txt"] = (stat.S_IFREG, 20, 200.0)
    storage = make_storage(tmp_path)
    storage.sftp = fake_sftp

    assert storage.index() == {
        "file.txt": (12, 100.0),
        "sub/child.txt": (20, 200.0),
    }


def test_exists_checks_remote_file(tmp_path):
    fake_sftp = FakeSFTP()
    fake_sftp.directories.add("/backups/my-backup")
    storage = make_storage(tmp_path)
    storage.sftp = fake_sftp
    fake_sftp.files["/backups/my-backup/file.txt"] = (stat.S_IFREG, 1, 1.0)

    assert storage.exists("file.txt") is True
    assert storage.exists("missing.txt") is False


def test_upload_creates_parent_and_updates_progress(tmp_path):
    fake_sftp = FakeSFTP()
    storage = make_storage(tmp_path)
    storage.sftp = fake_sftp
    local_file = tmp_path / "source.txt"
    local_file.write_text("hello", encoding="utf-8")
    progress = MagicMock()

    storage.upload_file(str(local_file), "nested/source.txt", progress)

    assert "/backups/my-backup/nested" in fake_sftp.directories
    assert fake_sftp.put_calls == [(str(local_file), "/backups/my-backup/nested/source.txt")]
    progress.update.assert_called_once_with(5)


def test_upload_failure_is_wrapped(tmp_path):
    fake_sftp = FakeSFTP()
    fake_sftp.put = MagicMock(side_effect=PermissionError("denied"))
    storage = make_storage(tmp_path)
    storage.sftp = fake_sftp
    local_file = tmp_path / "source.txt"
    local_file.write_text("hello", encoding="utf-8")

    with pytest.raises(StorageError):
        storage.upload_file(str(local_file), "source.txt", MagicMock())
    assert storage.cancel_event.is_set() is True


def test_invalid_key_path_is_rejected(tmp_path):
    storage = SFTPStorage("host", "user", str(tmp_path / "missing"), "/backup")

    with pytest.raises(StorageError):
        storage.connect()
