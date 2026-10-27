"""Moving profile ownership cannot change credential binding or persisted keys."""
import unittest
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from ft_tui.api.oauth_client import DeviceCredentials
from ft_tui.db.database import make_session_factory
from ft_tui.features.profiles.adapters.sqlite import SqliteProfileRepository


class ProfileRepositoryTests(unittest.TestCase):
    def test_reconstruction_keeps_bound_profile_and_final_goals_without_token_storage(self):
        with TemporaryDirectory() as directory:
            url = f'sqlite:///{Path(directory)/"profiles.sqlite"}'
            credentials = DeviceCredentials('synthetic-access', 'synthetic-refresh', '2099-01-01T00:00:00Z', 'synthetic-private-key')
            client = SimpleNamespace(base_url='https://example.test', credentials=credentials)
            factory = make_session_factory(url)
            try:
                repo = SqliteProfileRepository(factory)
                repo.save_profile(client, {'account_id': '42', 'login': 'student', 'wallet': 0, 'unexpected': 'discard'})
                repo.save_goals('42', 21, {'status': 'available', 'cc_validated': True})
                repo.save_goals('42', 21, {'status': 'pending'})
            finally:
                factory.kw['bind'].dispose()
            factory = make_session_factory(url)
            try:
                repo = SqliteProfileRepository(factory)
                self.assertEqual(repo.load_profile(client), {'account_id': '42', 'login': 'student', 'wallet': 0})
                self.assertEqual(repo.load_goals('42', 21), {'status': 'available', 'cc_validated': True, 'stale': True})
                self.assertEqual(repo.load_goals('another', 21), {})
                client.credentials = replace(credentials, access_token='rotated')
                self.assertEqual(repo.load_profile(client), {})
                data = Path(directory, 'profiles.sqlite').read_bytes()
                self.assertNotIn(b'synthetic-access', data)
                self.assertNotIn(b'synthetic-private-key', data)
            finally:
                factory.kw['bind'].dispose()
