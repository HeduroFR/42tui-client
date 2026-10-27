import unittest
from types import ModuleType
from unittest.mock import patch

from ft_tui.infrastructure.security.keychain import CredentialStore, SecureStoreError
from ft_tui.api.oauth_client import DeviceCredentials


class FakeKeyring:
    def __init__(self):
        self.values = {}
        self.fail = False

    def get_password(self, service, username):
        if self.fail:
            raise RuntimeError("keychain unavailable")
        return self.values.get((service, username))

    def set_password(self, service, username, password):
        if self.fail:
            raise RuntimeError("keychain unavailable")
        self.values[(service, username)] = password

    def delete_password(self, service, username):
        if self.fail:
            raise RuntimeError("keychain unavailable")
        del self.values[(service, username)]


class CredentialStoreTests(unittest.TestCase):
    def test_round_trip_and_delete_use_keychain(self):
        keyring = FakeKeyring()
        store = CredentialStore(service="test-service", keyring_backend=keyring)
        credentials = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": "2030-01-01T00:00:00Z",
            "private_key_pem": "private",
        }
        store.save(credentials)
        self.assertEqual(store.load(), credentials)
        self.assertEqual(len(keyring.values), 1)
        self.assertIn(("test-service", "device"), keyring.values)
        store.delete()
        self.assertIsNone(store.load())

    def test_automatically_selected_file_backend_fails_closed(self):
        plaintext_backend = type("FileKeyring", (), {"__module__": "keyrings.alt.file"})()
        keyring_module = ModuleType("keyring")
        keyring_module.get_keyring = lambda: plaintext_backend
        keyring_module.get_password = lambda service, username: '{"access_token":"plaintext-secret"}'
        store = CredentialStore(service="test-service")
        with patch.dict("sys.modules", {"keyring": keyring_module}):
            with self.assertRaises(SecureStoreError):
                store.load()

    def test_known_platform_keyring_backend_is_accepted(self):
        selected_backend = type("MacOSKeyring", (), {"__module__": "keyring.backends.macOS"})()
        keyring_module = ModuleType("keyring")
        keyring_module.get_keyring = lambda: selected_backend
        keyring_module.get_password = lambda service, username: '{"access_token":"secure"}'
        store = CredentialStore(service="test-service")
        with patch.dict("sys.modules", {"keyring": keyring_module}):
            self.assertEqual(store.load(), {"access_token": "secure"})

    def test_only_confirmed_missing_item_is_ignored_on_delete(self):
        class PasswordDeleteError(Exception):
            pass

        class BrokenDeleteKeyring(FakeKeyring):
            def get_password(self, service, username):
                return "stored-secret"

            def delete_password(self, service, username):
                raise PasswordDeleteError("backend could not delete")

        store = CredentialStore(service="test-service", keyring_backend=BrokenDeleteKeyring())
        with self.assertRaises(SecureStoreError):
            store.delete()

    def test_device_credential_repr_never_exposes_secrets(self):
        credentials = DeviceCredentials("access-secret", "refresh-secret", "2030-01-01T00:00:00Z", "private-key-secret")
        representation = repr(credentials)
        self.assertNotIn("access-secret", representation)
        self.assertNotIn("refresh-secret", representation)
        self.assertNotIn("private-key-secret", representation)

    def test_unavailable_keychain_fails_closed(self):
        keyring = FakeKeyring()
        keyring.fail = True
        store = CredentialStore(service="test-service", keyring_backend=keyring)
        with self.assertRaises(SecureStoreError):
            store.load()
        with self.assertRaises(SecureStoreError):
            store.save({"access_token": "secret"})
