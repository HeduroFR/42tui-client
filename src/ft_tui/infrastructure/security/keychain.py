"""OS-keychain-only storage for device credentials and the installation key."""

import json
from typing import Any, Protocol


class SecureStoreError(RuntimeError):
    """The platform credential manager could not securely access the store."""


class CredentialStoreProtocol(Protocol):
    def load(self) -> dict[str, Any] | None: ...
    def save(self, credentials: dict[str, Any]) -> None: ...
    def delete(self) -> None: ...


# Accepted OS vaults: macOS Keychain, Windows Credential Manager, and Linux Secret
# Service (including libsecret) or KDE Wallet. File/plaintext and third-party
# keyring plugins fail closed until explicitly reviewed and added here.
_SECURE_BACKEND_MODULES = {
    "keyring.backends.macOS",
    "keyring.backends.Windows",
    "keyring.backends.SecretService",
    "keyring.backends.kwallet",
    "keyring.backends.libsecret",
}


class CredentialStore:
    """Store one serialized credential bundle in the operating system keychain."""

    def __init__(self, service: str = "42tui.oauth", username: str = "device", keyring_backend: Any = None):
        self.service = service
        self.username = username
        self._keyring = keyring_backend

    def _backend(self):
        if self._keyring is None:
            try:
                import keyring
                selected_backend = keyring.get_keyring()
                module_name = selected_backend.__class__.__module__
                trusted = any(
                    module_name == module or module_name.startswith(module + ".")
                    for module in _SECURE_BACKEND_MODULES
                )
                if not trusted:
                    raise RuntimeError("The selected keyring backend is not an approved OS credential manager")
                return keyring
            except Exception as error:
                raise SecureStoreError("The OS keychain is unavailable; credentials were not stored") from error
        return self._keyring

    def load(self) -> dict[str, Any] | None:
        try:
            value = self._backend().get_password(self.service, self.username)
            return json.loads(value) if value is not None else None
        except Exception as error:
            if isinstance(error, SecureStoreError):
                raise
            raise SecureStoreError("The OS keychain could not read credentials") from error

    def save(self, credentials: dict[str, Any]) -> None:
        try:
            payload = json.dumps(credentials, separators=(",", ":"), sort_keys=True)
            self._backend().set_password(self.service, self.username, payload)
        except Exception as error:
            if isinstance(error, SecureStoreError):
                raise
            raise SecureStoreError("The OS keychain could not store credentials") from error

    def delete(self) -> None:
        try:
            backend = self._backend()
            # Read first so absence is the only condition treated as idempotent.
            if backend.get_password(self.service, self.username) is None:
                return
            backend.delete_password(self.service, self.username)
        except Exception as error:
            if isinstance(error, SecureStoreError):
                raise
            raise SecureStoreError("The OS keychain could not delete credentials") from error
