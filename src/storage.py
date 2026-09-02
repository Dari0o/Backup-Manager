"""Storage backends used by the uncompressed backup engine."""

import os
import posixpath
import stat
import threading
from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple, Any

from logger import setup_logger

logger = setup_logger(__name__)


class StorageError(Exception):
    """Raised when a storage backend cannot complete an operation."""


class Storage(ABC):
    """Interface required by the backup comparison and copy engine."""

    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def close(self) -> None:
        pass

    @abstractmethod
    def index(self) -> Dict[str, Tuple[int, float]]:
        pass

    @abstractmethod
    def upload_file(self, local_path: str, relative_path: str, progress: Any) -> None:
        pass

    @abstractmethod
    def exists(self, relative_path: str) -> bool:
        pass

    @abstractmethod
    def delete(self, relative_path: str) -> None:
        pass

    def __enter__(self):
        self.connect()
        return self

    def supports_cancellation(self) -> bool:
        return False

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


class LocalStorage(Storage):
    """Adapter retaining the existing local filesystem behavior."""

    def __init__(self, root: str):
        self.root = root

    def connect(self) -> None:
        pass

    def close(self) -> None:
        pass

    def index(self) -> Dict[str, Tuple[int, float]]:
        from BackupManager import collect_files_multithread
        result, _ = collect_files_multithread(self.root, "Scanning Target", as_index=True)
        return result

    def upload_file(self, local_path: str, relative_path: str, progress: Any) -> None:
        destination = os.path.join(self.root, relative_path)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        import shutil
        shutil.copy2(local_path, destination)
        progress.update(os.path.getsize(local_path))

    def exists(self, relative_path: str) -> bool:
        return os.path.exists(os.path.join(self.root, relative_path))

    def delete(self, relative_path: str) -> None:
        destination = os.path.join(self.root, relative_path)
        if os.path.isfile(destination) or os.path.islink(destination):
            os.remove(destination)
        elif os.path.isdir(destination):
            import shutil
            shutil.rmtree(destination)


class SFTPStorage(Storage):
    """Paramiko-backed storage using SSH private-key authentication."""

    def __init__(self, host: str, username: str, key_path: str, remote_root: str,
                 port: int = 22, password: Optional[str] = None, timeout: float = 15,
                 known_hosts_path: Optional[str] = None):
        self.host = host
        self.username = username
        self.key_path = os.path.expanduser(key_path)
        self.remote_root = posixpath.normpath(remote_root)
        self.port = port
        self.password = password
        self.timeout = timeout
        self.known_hosts_path = os.path.expanduser(
            known_hosts_path or "~/.ssh/known_hosts"
        )
        self.client = None
        self.sftp = None
        self._transfer_lock = threading.Lock()
        self.cancel_event = threading.Event()

    def supports_cancellation(self) -> bool:
        return True

    def cancel(self) -> None:
        self.cancel_event.set()

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise StorageError("SFTP backup cancelled")

    def connect(self) -> None:
        if not self.key_path or not os.path.isfile(self.key_path):
            raise StorageError("SSH private key path does not exist")
        try:
            import paramiko
            if self.remote_root.startswith("~/"):
                self.remote_root = posixpath.join("/home", self.username, self.remote_root[2:])
            logger.info("Connecting to SFTP host %s:%s", self.host, self.port)
            self.client = paramiko.SSHClient()
            if not os.path.isfile(self.known_hosts_path):
                raise StorageError(
                    f"SSH known-hosts file does not exist: {self.known_hosts_path}"
                )
            self.client.load_host_keys(self.known_hosts_path)
            self.client.set_missing_host_key_policy(paramiko.RejectPolicy())
            self.client.connect(
                hostname=self.host, port=self.port, username=self.username,
                key_filename=self.key_path, password=self.password,
                timeout=self.timeout, allow_agent=True, look_for_keys=True,
            )
            self.sftp = self.client.open_sftp()
            self._mkdir_p(self.remote_root)
            logger.info("SFTP connection established")
        except Exception as exc:
            self.close()
            logger.error("SFTP connection failed: %s", exc)
            raise StorageError("SFTP connection failed") from exc

    def close(self) -> None:
        if self.sftp is not None:
            try:
                self.sftp.close()
            except Exception:
                pass
            self.sftp = None
        if self.client is not None:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        self.password = None

    def _mkdir_p(self, path: str) -> None:
        current = "/" if path.startswith("/") else ""
        for part in path.split("/"):
            if not part:
                continue
            current = posixpath.join(current, part)
            try:
                self.sftp.stat(current)
            except IOError:
                try:
                    self.sftp.mkdir(current)
                except Exception as exc:
                    raise StorageError("Unable to create remote directory") from exc

    def _remote_path(self, relative_path: str) -> str:
        normalized = posixpath.normpath(relative_path.replace("\\", "/"))
        if normalized in (".", ""):
            return self.remote_root
        if normalized.startswith("../") or normalized == ".." or normalized.startswith("/"):
            raise StorageError("Invalid remote relative path")
        return posixpath.join(self.remote_root, normalized)

    def exists(self, relative_path: str) -> bool:
        try:
            self.sftp.stat(self._remote_path(relative_path))
            return True
        except IOError:
            return False

    def index(self) -> Dict[str, Tuple[int, float]]:
        result = {}

        def visit(remote_dir: str, relative_dir: str) -> None:
            for entry in self.sftp.listdir_attr(remote_dir):
                relative = posixpath.join(relative_dir, entry.filename)
                remote = posixpath.join(remote_dir, entry.filename)
                if stat.S_ISDIR(entry.st_mode):
                    visit(remote, relative)
                elif stat.S_ISREG(entry.st_mode):
                    result[relative] = (entry.st_size, entry.st_mtime)

        try:
            visit(self.remote_root, "")
            return result
        except Exception as exc:
            raise StorageError("Unable to scan remote backup") from exc

    def upload_file(self, local_path: str, relative_path: str, progress: Any) -> None:
        remote = self._remote_path(relative_path)
        try:
            self._check_cancelled()
            with self._transfer_lock:
                self._check_cancelled()
                self._mkdir_p(posixpath.dirname(remote))
                self.sftp.put(local_path, remote)
                source_stat = os.stat(local_path)
                self.sftp.utime(remote, (source_stat.st_atime, source_stat.st_mtime))
            progress.update(os.path.getsize(local_path))
        except Exception as exc:
            self.cancel_event.set()
            logger.error("SFTP upload failed for %s: %s", relative_path, exc)
            raise StorageError("SFTP upload failed") from exc

    def delete(self, relative_path: str) -> None:
        try:
            self.sftp.remove(self._remote_path(relative_path))
        except Exception as exc:
            raise StorageError("SFTP delete failed") from exc