"""Refresh scheduling and real HTTP coverage for the Friends workspace."""
import asyncio
import os
import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import httpx

from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.api.oauth_client import DeviceCredentials, OAuthClient
from ft_tui.db.database import make_session_factory
from ft_tui.ui.friends import FriendsWorkspace
from tests.test_oauth_client import MemoryStore


class SyncHarness:
    _sync = FriendsWorkspace._sync
    _fetch = FriendsWorkspace._fetch
    _error = staticmethod(FriendsWorkspace._error)
    _read = FriendsWorkspace._read
    _read_key = FriendsWorkspace._read_key
    _authorization_lost = FriendsWorkspace._authorization_lost

    def _scope(self):
        return self.context

    def __init__(self, logins):
        self.logins = logins
        self.sync_done = self.sync_successes = self.sync_errors = 0
        self.pending_logins = set()
        self.errors = {}
        self.snapshots = {}
        self.busy = True
        self.progress = []
        self.valid = True
        self.detail_snapshots = {}
        self.detail_attempted = set()

    def _ensure_details(self):
        pass

    def _sync_targets(self):
        return self.logins

    def _valid(self, *args):
        return self.valid

    def _refresh_view(self):
        self.progress.append(self.sync_done)


class FriendsRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_slow_profile_does_not_block_others_and_concurrency_is_bounded(self):
        workspace = SyncHarness(['selected'] + [f'friend{i}' for i in range(15)])
        slow = asyncio.Event()
        first_wave = asyncio.Event()
        started, finished = [], []
        active = peak = 0

        async def fetch(login, *args):
            nonlocal active, peak
            started.append(login)
            active += 1
            peak = max(peak, active)
            try:
                if len(started) == 2:
                    first_wave.set()
                await (slow.wait() if login == 'selected' else first_wave.wait())
                finished.append(login)
            finally:
                active -= 1

        workspace._fetch = fetch
        task = asyncio.create_task(workspace._sync(0, (), False))
        try:
            await asyncio.wait_for(first_wave.wait(), 1)
            for _ in range(30):
                await asyncio.sleep(0)
            self.assertEqual(started[0], 'selected')
            self.assertEqual(len(finished), 15)
            self.assertEqual(workspace.sync_done, 15)
            self.assertTrue(workspace.busy)
            self.assertEqual(peak, 2)
        finally:
            slow.set()
            await task
        self.assertEqual(workspace.sync_done, 16)
        self.assertEqual(workspace.sync_successes, 16)
        self.assertFalse(workspace.pending_logins)
        self.assertFalse(workspace.busy)

    async def test_cancellation_stops_consumers_without_starting_queued_profiles(self):
        workspace = SyncHarness([str(i) for i in range(15)])
        started, cancelled = [], []
        ready = asyncio.Event()

        async def fetch(login, *args):
            started.append(login)
            if len(started) == 2:
                ready.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(login)

        workspace._fetch = fetch
        task = asyncio.create_task(workspace._sync(0, (), False))
        await asyncio.wait_for(ready.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(len(started), 2)
        self.assertCountEqual(cancelled, started)
        self.assertEqual(workspace.sync_done, 0)

    async def test_authorization_failure_stops_queued_requests(self):
        workspace = SyncHarness([str(i) for i in range(15)])
        started = []

        async def fetch(login, *args):
            started.append(login)
            response = httpx.Response(401, request=httpx.Request('GET', 'http://localhost'))
            raise httpx.HTTPStatusError('unauthorized', request=response.request, response=response)

        workspace._fetch = fetch
        await workspace._sync(0, (), False)
        self.assertEqual(started, ['0'])
        self.assertEqual(workspace.sync_errors, 1)
        self.assertEqual(workspace.sync_done, 1)


@unittest.skipUnless(os.environ.get('FRIENDS_REFRESH_SIMULATION_URL'), 'requires local Friends refresh simulation')
class FriendsRefreshSimulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_fifteen_profiles_overlap_through_real_authenticated_http_and_save(self):
        url = os.environ['FRIENDS_REFRESH_SIMULATION_URL']
        with TemporaryDirectory() as directory:
            client = OAuthClient(url, MemoryStore(), lock_directory=directory)
            client._save_credentials(DeviceCredentials('a' * 43, 'r' * 43,
                '2099-01-01T00:00:00Z', client._new_private_key_pem()))
            factory = make_session_factory(f'sqlite:///{directory}/friends.db')
            workspace = SyncHarness(['you'] + [f'friend{i}' for i in range(14)])
            workspace.app = SimpleNamespace(provider=HttpProjectProvider(oauth_client=client),
                account_login='you', account_id='42', account_generation=0, session_factory=factory)
            workspace.context = (0, '42', 21, id(workspace.app.provider), url)
            try:
                httpx.post(f'{url}/reset').raise_for_status()
                await asyncio.wait_for(workspace._sync(0, workspace.context, True), 15)
                self.assertEqual(workspace.sync_successes, 15, workspace.errors)
                self.assertEqual(len(workspace.snapshots), 15)
                stats = httpx.get(f'{url}/stats').json()
                self.assertEqual(stats['peak'], 2)
                self.assertEqual(stats['completed'], 15)
                self.assertEqual(stats['invalid'], 0)
                from ft_tui.services.friends import cached_observations
                with factory() as session:
                    self.assertEqual(len(cached_observations(session, '42', 21, origin=url)), 15)
            finally:
                client.close()
                factory.kw['bind'].dispose()
