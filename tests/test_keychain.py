import unittest
from types import ModuleType
from unittest.mock import patch

from ft_tui.infrastructure.security.keychain import CredentialStore, SecureStoreError, SessionCredentialStore
from ft_tui.api.oauth_client import DeviceCredentials


class SessionCredentialStoreTests(unittest.TestCase):
    def test_credentials_are_isolated_and_discarded(self):
        first = SessionCredentialStore()
        second = SessionCredentialStore()
        credentials = {"access_token": "token"}
        first.save(credentials)
        credentials["access_token"] = "changed"
        loaded = first.load()
        self.assertEqual(loaded, {"access_token": "token"})
        loaded["access_token"] = "changed again"
        self.assertEqual(first.load(), {"access_token": "token"})
        self.assertIsNone(second.load())
        first.delete()
        self.assertIsNone(first.load())
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


class SessionVaultTests(unittest.TestCase):
    def test_round_trip_wrong_passphrase_and_tampering(self):
        import tempfile
        from pathlib import Path
        from ft_tui.infrastructure.security.session_vault import SessionVault

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vault'
            vault = SessionVault.create(path, 'a long test passphrase')
            vault.save({'access_token': 'secret'})
            self.assertNotIn(b'secret', path.read_bytes())
            self.assertEqual(SessionVault.unlock(path, 'a long test passphrase').load(), {'access_token': 'secret'})
            original = path.read_bytes()
            with self.assertRaises(SecureStoreError):
                SessionVault.unlock(path, 'incorrect')
            self.assertEqual(path.read_bytes(), original)
            path.write_bytes(original[:-3] + b'xxx')
            with self.assertRaises(SecureStoreError):
                SessionVault.unlock(path, 'a long test passphrase')

    def test_corrupt_or_missing_existing_vault_cannot_be_overwritten(self):
        import tempfile
        from pathlib import Path
        from ft_tui.infrastructure.security.session_vault import SessionVault

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vault'
            vault = SessionVault.create(path, 'a long test passphrase')
            vault.save({'access_token': 'secret'})
            path.write_bytes(b'corrupt')
            with self.assertRaises(SecureStoreError):
                vault.save({'access_token': 'replacement'})
            self.assertEqual(path.read_bytes(), b'corrupt')
            path.unlink()
            with self.assertRaises(SecureStoreError):
                vault.save({'access_token': 'replacement'})
            self.assertFalse(path.exists())

    def test_concurrent_creation_never_replaces_an_existing_vault(self):
        import tempfile
        from pathlib import Path
        from ft_tui.infrastructure.security.session_vault import SessionVault

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vault'
            first = SessionVault.create(path, 'first passphrase')
            second = SessionVault.create(path, 'second passphrase')
            first.save({'access_token': 'first'})
            with self.assertRaises(SecureStoreError):
                second.save({'access_token': 'second'})
            self.assertEqual(first.load(), {'access_token': 'first'})

    def test_rejects_insecure_or_symlinked_vault_directory(self):
        import tempfile
        from pathlib import Path
        from ft_tui.infrastructure.security.session_vault import SessionVault

        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / 'private'
            parent.mkdir(mode=0o700)
            path = parent / 'vault'
            vault = SessionVault.create(path, 'a long test passphrase')
            vault.save({'access_token': 'secret'})
            parent.chmod(0o755)
            with self.assertRaises(SecureStoreError):
                SessionVault.unlock(path, 'a long test passphrase')
            parent.chmod(0o700)
            link = Path(directory) / 'link'
            link.symlink_to(parent, target_is_directory=True)
            with self.assertRaises(SecureStoreError):
                SessionVault.unlock(link / 'vault', 'a long test passphrase')

    def test_two_unlocked_instances_reload_latest_credentials(self):
        import tempfile
        from pathlib import Path
        from ft_tui.infrastructure.security.session_vault import SessionVault

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vault'
            first = SessionVault.create(path, 'a long test passphrase')
            first.save({'refresh_token': 'old'})
            second = SessionVault.unlock(path, 'a long test passphrase')
            first.save({'refresh_token': 'new'})
            self.assertEqual(second.load(), {'refresh_token': 'new'})

    def test_oversized_write_preserves_existing_credentials(self):
        import tempfile
        from pathlib import Path
        from ft_tui.infrastructure.security.session_vault import SessionVault

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vault'
            vault = SessionVault.create(path, 'a long test passphrase')
            vault.save({'access_token': 'original'})
            before = path.read_bytes()
            with self.assertRaises(SecureStoreError):
                vault.save({'access_token': 'x' * SessionVault.MAX_SIZE})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(vault.load(), {'access_token': 'original'})

    def test_failed_atomic_replace_preserves_original(self):
        import tempfile
        from pathlib import Path
        from ft_tui.infrastructure.security.session_vault import SessionVault

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vault'
            vault = SessionVault.create(path, 'a long test passphrase')
            vault.save({'refresh_token': 'original'})
            before = path.read_bytes()
            with patch('ft_tui.infrastructure.security.session_vault.os.replace', side_effect=OSError('disk error')):
                with self.assertRaises(SecureStoreError):
                    vault.save({'refresh_token': 'replacement'})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(vault.load(), {'refresh_token': 'original'})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_locked_store_never_treats_vault_as_empty(self):
        from ft_tui.infrastructure.security.session_vault import LockedSessionStore

        store = LockedSessionStore()
        for operation in (store.load, lambda: store.save({}), store.delete):
            with self.assertRaises(SecureStoreError):
                operation()
