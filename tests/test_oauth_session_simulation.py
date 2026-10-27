"""Run against the local Postman simulation; no real accounts or keychain writes."""
import os
import tempfile
import unittest

from ft_tui.api.oauth_client import DeviceCredentials, OAuthClient
from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.db.database import make_session_factory
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.features.accounts.views.connection import SessionExpiredScreen
from tests.test_oauth_client import MemoryStore


@unittest.skipUnless(os.environ.get('OAUTH_SIMULATION_URL'), 'requires local OAuth simulation')
class OAuthSessionSimulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_checks_real_http_session_and_only_prompts_on_auth_failure(self):
        for scenario, should_prompt in [('expired', True), ('renewable', False), ('outage', False), ('revoked', True), ('reauthorize', True)]:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as directory:
                client = OAuthClient(f"{os.environ['OAUTH_SIMULATION_URL']}/{scenario}", MemoryStore(), lock_directory=directory)
                expiry = '2099-01-01T00:00:00Z' if scenario in ('revoked', 'reauthorize') else '2000-01-01T00:00:00Z'
                client._save_credentials(DeviceCredentials('a' * 43, 'r' * 43, expiry, client._new_private_key_pem()))
                factory = make_session_factory(f'sqlite:///{directory}/workspace.db')
                app = FortyTwoTuiApp(factory, HttpProjectProvider(oauth_client=client), oauth_client=client)
                try:
                    async with app.run_test(size=(120, 45)) as pilot:
                        for _ in range(20):
                            await pilot.pause(.1)
                            if isinstance(app.screen, SessionExpiredScreen) or app.account_login:
                                break
                        self.assertEqual(isinstance(app.screen, SessionExpiredScreen), should_prompt)
                        self.assertEqual(app.account_connected, not should_prompt)
                        if scenario == 'renewable':
                            self.assertEqual(client.credentials.access_token, 'b' * 43)
                            self.assertEqual(app.account_login, 'synthetic-student')
                finally:
                    client.close()
                    factory.kw['bind'].dispose()
