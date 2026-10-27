"""Real provider, DPoP and SSE parser against the contract-derived Postman fixture."""
import os
import threading
import unittest
from tempfile import TemporaryDirectory
from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.api.oauth_client import OAuthClient, DeviceCredentials
from tests.test_oauth_client import MemoryStore


@unittest.skipUnless(os.environ.get('SOCIAL_SIMULATION_URL'), 'requires local social simulation')
class SocialSimulationTests(unittest.TestCase):
    def test_real_http_inbox_actions_and_authenticated_event_stream(self):
        url = os.environ['SOCIAL_SIMULATION_URL']
        if not url.startswith('http://127.0.0.1:'):
            raise ValueError('Local simulation only')
        with TemporaryDirectory() as directory:
            client = OAuthClient(url, MemoryStore(), lock_directory=directory)
            client._save_credentials(DeviceCredentials('a' * 43, 'r' * 43, '2099-01-01T00:00:00Z', client._new_private_key_pem()))
            provider = HttpProjectProvider(oauth_client=client)
            try:
                value = provider.get_social()
                self.assertEqual(value['account_id'], '1')
                self.assertEqual(value['pokes'][0]['message'], '[bold]Lunch?[/bold]')
                provider.social_action({'action': 'accept', 'account_id': '3'})
                self.assertIn('3', [f['account_id'] for f in provider.get_social()['friends']])
                self.assertEqual(list(provider.event_stream(threading.Event())), ['resync', 'social'])
                provider.social_action({'action': 'dismiss', 'id': value['pokes'][0]['id']})
                self.assertEqual(provider.get_social()['pokes'], [])
            finally:
                client.close()
