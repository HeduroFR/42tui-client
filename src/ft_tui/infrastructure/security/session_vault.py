"""Passphrase-encrypted credential storage; the caller owns session locking."""

import base64
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .keychain import SecureStoreError


def session_vault_path() -> Path:
    from ft_tui.config.settings import data_dir
    return data_dir() / 'credentials' / 'session-v1.json'


class LockedSessionStore:
    """A saved vault must be unlocked before it can be read or overwritten."""

    def load(self):
        raise SecureStoreError('The saved session is locked')

    def save(self, credentials):
        raise SecureStoreError('The saved session is locked')

    def delete(self):
        raise SecureStoreError('The saved session is locked')


def discard_locked_vault(path: Path) -> None:
    """Discard only the local vault; this does not revoke the server session."""
    try:
        SessionVault._read_file(path)
        path.unlink()
    except (OSError, ValueError) as error:
        raise SecureStoreError('Could not discard the saved session') from error


class SessionVault:
    """A versioned encrypted credential bundle, unlocked for this process."""

    MAX_SIZE = 65536
    N, R, P = 2**17, 8, 1

    def __init__(self, path: Path, key: bytes, salt: bytes, *, existing: bool = True):
        self.path, self._key, self._salt = path, key, salt
        self._existing = existing

    @classmethod
    def _derive(cls, passphrase: str, salt: bytes) -> bytes:
        return Scrypt(salt=salt, length=32, n=cls.N, r=cls.R, p=cls.P).derive(passphrase.encode('utf-8'))

    @staticmethod
    def _check_directory(path: Path) -> None:
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or (hasattr(os, 'getuid') and info.st_uid != os.getuid()) or info.st_mode & 0o077:
            raise ValueError('unsafe session directory')

    @classmethod
    def create(cls, path: Path, passphrase: str) -> 'SessionVault':
        if not passphrase or len(passphrase.encode('utf-8')) > 4096:
            raise SecureStoreError('A passphrase is required')
        if path.exists() or path.is_symlink():
            raise SecureStoreError('A saved session already exists')
        salt = os.urandom(16)
        return cls(path, cls._derive(passphrase, salt), salt, existing=False)

    @classmethod
    def unlock(cls, path: Path, passphrase: str) -> 'SessionVault':
        try:
            if len(passphrase.encode('utf-8')) > 4096:
                raise ValueError('passphrase too large')
            data = cls._read_file(path)
            header = json.loads(data)
            if not isinstance(header, dict) or set(header) != {'version', 'salt', 'nonce', 'ciphertext'} or type(header['version']) is not int or header['version'] != 1:
                raise ValueError('invalid vault format')
            salt = base64.b64decode(header['salt'], validate=True)
            if len(salt) != 16:
                raise ValueError('invalid salt')
            vault = cls(path, cls._derive(passphrase, salt), salt)
            vault._decode(header)
            return vault
        except (OSError, ValueError, TypeError, KeyError, InvalidTag) as error:
            raise SecureStoreError('Could not unlock saved session') from error

    @classmethod
    def _read_file(cls, path: Path) -> bytes:
        cls._check_directory(path.parent)
        flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(path, flags)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or (hasattr(os, 'getuid') and info.st_uid != os.getuid()) or info.st_mode & 0o077:
                raise ValueError('unsafe session file')
            with os.fdopen(fd, 'rb') as stream:
                fd = -1
                data = stream.read(cls.MAX_SIZE + 1)
            if len(data) > cls.MAX_SIZE:
                raise ValueError('session file too large')
            return data
        finally:
            if fd >= 0:
                os.close(fd)

    def _decode(self, header: dict) -> dict[str, Any]:
        if not isinstance(header, dict) or set(header) != {'version', 'salt', 'nonce', 'ciphertext'} or type(header['version']) is not int or header['version'] != 1:
            raise ValueError('invalid vault format')
        salt = base64.b64decode(header['salt'], validate=True)
        nonce = base64.b64decode(header['nonce'], validate=True)
        ciphertext = base64.b64decode(header['ciphertext'], validate=True)
        if salt != self._salt or len(nonce) != 12:
            raise ValueError('vault changed')
        payload = AESGCM(self._key).decrypt(nonce, ciphertext, b'42tui-session-v1' + salt)
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError('invalid credentials')
        return result

    def load(self) -> dict[str, Any] | None:
        try:
            return self._decode(json.loads(self._read_file(self.path)))
        except FileNotFoundError:
            if not self._existing and not self.path.is_symlink():
                return None
            raise SecureStoreError('Saved session is missing') from None
        except (OSError, ValueError, TypeError, KeyError, InvalidTag) as error:
            raise SecureStoreError('Could not read saved session') from error

    def save(self, credentials: dict[str, Any]) -> None:
        temp = None
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            self._check_directory(self.path.parent)
            if self.path.is_symlink():
                raise ValueError('unsafe session file')
            # An unlocked vault must still exist and authenticate before replacement.
            if self._existing:
                self.load()
            elif self.path.exists():
                raise ValueError('a saved session already exists')
            nonce = os.urandom(12)
            payload = json.dumps(credentials, separators=(',', ':'), sort_keys=True).encode()
            ciphertext = AESGCM(self._key).encrypt(nonce, payload, b'42tui-session-v1' + self._salt)
            header = {'version': 1, 'salt': base64.b64encode(self._salt).decode(), 'nonce': base64.b64encode(nonce).decode(), 'ciphertext': base64.b64encode(ciphertext).decode()}
            data = json.dumps(header, separators=(',', ':')).encode()
            if len(data) > self.MAX_SIZE:
                raise ValueError('session file too large')
            fd, temp = tempfile.mkstemp(prefix='.session-', dir=self.path.parent)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if self._existing:
                os.replace(temp, self.path)
            else:
                # Link exclusively so a concurrent creator cannot be overwritten.
                os.link(temp, self.path)
                os.unlink(temp)
            temp = None
            for directory in (self.path.parent, self.path.parent.parent):
                descriptor = os.open(directory, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            self._existing = True
        except (OSError, ValueError, TypeError) as error:
            raise SecureStoreError('Could not save session securely') from error
        finally:
            if temp is not None:
                os.unlink(temp)

    def delete(self) -> None:
        try:
            self.load()
            self.path.unlink(missing_ok=True)
            self._existing = False
        except OSError as error:
            raise SecureStoreError('Could not delete saved session') from error
