"""Refresh scheduling and real HTTP coverage for the Friends workspace."""
import asyncio
import os
import unittest
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.api.oauth_client import DeviceCredentials, OAuthClient
from ft_tui.db.database import make_session_factory
from ft_tui.features.friends.views.workspace import FriendsWorkspace
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
    async def test_selected_detail_starts_during_summary_sync(self):
        started = asyncio.Event()
        release = asyncio.Event()
        calls = []
        class Service:
            async def detail(self, provider, login, cursus, **options):
                calls.append(login)
                started.set()
                await release.wait()
                return {'login': login, 'user_id': '2', 'details_complete': True}
            def save(self, *args, **kwargs): pass
        class Harness:
            _ensure_details = FriendsWorkspace._ensure_details
            _enrich_details = FriendsWorkspace._enrich_details
            busy = True
            detail_busy = False
            selected_login = 'selected'
            comparing = False
            epoch = 0
            context = (0, '1', 21, 0, 'backend')
            _force_details = False
            detail_attempted = set()
            snapshots = {'selected': {'details_complete': False}, 'other': {'projects_loaded': False}}
            detail_snapshots = {}
            errors = {}
            app = SimpleNamespace(account_connected=True, account_login='you',
                                  provider=SimpleNamespace(get_friend_summary=lambda: None))
            valid = True
            def _valid(self, *args): return self.valid
            def _sync_targets(self): return ['selected', 'other']
            def _refresh_view(self): pass
            def run_worker(self, coroutine, **kwargs): return asyncio.create_task(coroutine)
            async def _read(self, resource, parts, loader, **kwargs): return await loader()
        workspace = Harness()
        with patch('ft_tui.features.friends.views.workspace.friends_service_for', return_value=Service()), \
             patch('ft_tui.features.friends.views.workspace.friend_snapshot'):
            workspace._ensure_details()
            try:
                await asyncio.wait_for(started.wait(), 0.1)
                self.assertEqual(calls, ['selected'])
            finally:
                release.set()
                if workspace.detail_busy:
                    await workspace.detail_worker
            self.assertEqual(calls, ['selected'])

            # A result arriving after an account change must not be installed.
            started.clear()
            release.clear()
            workspace.detail_attempted.clear()
            workspace.detail_snapshots.clear()
            workspace.snapshots['selected'] = {'details_complete': False}
            workspace._ensure_details()
            await asyncio.wait_for(started.wait(), 0.5)
            workspace.valid = False
            release.set()
            await workspace.detail_worker
            self.assertEqual(workspace.detail_snapshots, {})

    async def test_cached_summary_batches_overlap_with_bounded_concurrency(self):
        workspace = SyncHarness([f'friend{i}' for i in range(101)])
        workspace.app = SimpleNamespace(provider=SimpleNamespace(get_friend_summaries=lambda: None), account_login='you')
        workspace.context = (0, '42', 21, 0, 'backend')
        started = asyncio.Event()
        release = asyncio.Event()
        calls = []
        class Service:
            async def batch(self, provider, logins, cursus, **kwargs):
                calls.append(tuple(logins))
                if len(calls) == 2:
                    started.set()
                await release.wait()
                return []
        async def read(resource, parts, fetch, **kwargs):
            return await fetch()
        workspace._read = read
        with patch('ft_tui.features.friends.views.workspace.friends_service_for', return_value=Service()):
            task = asyncio.create_task(workspace._sync(0, workspace.context, False))
            try:
                await asyncio.wait_for(started.wait(), .5)
                self.assertEqual([len(batch) for batch in calls], [50, 50])
                workspace.valid = False
            finally:
                release.set()
                await task

    async def test_completed_summary_batches_are_shown_before_later_batches_finish(self):
        workspace = SyncHarness([f'friend{i}' for i in range(101)])
        workspace.app = SimpleNamespace(provider=SimpleNamespace(get_friend_summaries=lambda: None), account_login='you')
        workspace.context = (0, '42', 21, 0, 'backend')
        last_started = asyncio.Event()
        release = asyncio.Event()
        class Service:
            async def batch(self, provider, logins, cursus, **kwargs):
                if logins[0] == 'friend100':
                    last_started.set()
                    await release.wait()
                return [{'login': logins[0], 'user_id': '50'}]
            def save(self, *args, **kwargs): pass
        async def read(resource, parts, fetch, **kwargs): return await fetch()
        workspace._read = read
        with patch('ft_tui.features.friends.views.workspace.friends_service_for', return_value=Service()), \
             patch('ft_tui.features.friends.views.workspace.friend_snapshot'):
            task = asyncio.create_task(workspace._sync(0, workspace.context, False))
            try:
                await asyncio.wait_for(last_started.wait(), .5)
                self.assertIn('friend0', workspace.snapshots)
                self.assertIn('friend50', workspace.snapshots)
                workspace.valid = False
            finally:
                release.set()
                await task

    async def test_later_batch_authorization_failure_clears_earlier_results(self):
        workspace = SyncHarness([f'friend{i}' for i in range(101)])
        workspace.app = SimpleNamespace(provider=SimpleNamespace(get_friend_summaries=lambda: None), account_login='you')
        workspace.context = (0, '42', 21, 0, 'backend')
        class Service:
            async def batch(self, provider, logins, cursus, **kwargs):
                if logins[0] == 'friend100':
                    self.assert_prior = dict(workspace.snapshots)
                    request = httpx.Request('GET', 'https://example.test')
                    raise httpx.HTTPStatusError('unauthorized', request=request, response=httpx.Response(401, request=request))
                return [{'login': logins[0], 'user_id': '50'}]
            def save(self, *args, **kwargs): pass
        service = Service()
        async def read(resource, parts, fetch, **kwargs): return await fetch()
        workspace._read = read
        with patch('ft_tui.features.friends.views.workspace.friends_service_for', return_value=service), \
             patch('ft_tui.features.friends.views.workspace.friend_snapshot'):
            await workspace._sync(0, workspace.context, False)
        self.assertIn('friend0', service.assert_prior)
        self.assertEqual(workspace.snapshots, {})
        self.assertIn('Reconnect', workspace.errors['friend0'])

    async def test_batch_authorization_failure_cancels_other_batch(self):
        workspace = SyncHarness([f'friend{i}' for i in range(100)])
        workspace.app = SimpleNamespace(provider=SimpleNamespace(get_friend_summaries=lambda: None), account_login='you')
        workspace.context = (0, '42', 21, 0, 'backend')
        other_started = asyncio.Event()
        other_cancelled = asyncio.Event()
        class Service:
            async def batch(self, provider, logins, cursus, **kwargs):
                if logins[0] == 'friend0':
                    await other_started.wait()
                    request = httpx.Request('GET', 'https://example.test')
                    raise httpx.HTTPStatusError('unauthorized', request=request, response=httpx.Response(401, request=request))
                other_started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    other_cancelled.set()
        async def read(resource, parts, fetch, **kwargs): return await fetch()
        workspace._read = read
        with patch('ft_tui.features.friends.views.workspace.friends_service_for', return_value=Service()):
            await asyncio.wait_for(workspace._sync(0, workspace.context, False), 1)
        self.assertTrue(other_cancelled.is_set())
        self.assertFalse(workspace.snapshots)
        self.assertIn('Reconnect', workspace.errors['friend0'])

    async def test_fast_friend_updates_are_coalesced_and_selected_is_shown(self):
        workspace = SyncHarness(['selected'] + [f'friend{i}' for i in range(30)])
        workspace.selected_login = 'selected'
        async def fetch(login, *args):
            await asyncio.sleep(0)
        workspace._fetch = fetch
        await workspace._sync(0, (), False)
        self.assertIn(1, workspace.progress)
        self.assertEqual(workspace.progress[-1], 31)
        self.assertLess(len(workspace.progress), 10)

    async def test_coalesced_progress_is_shown_while_another_friend_is_slow(self):
        workspace = SyncHarness(['first', 'second', 'slow'])
        slow_started = asyncio.Event()
        release = asyncio.Event()
        async def fetch(login, *args):
            if login == 'slow':
                slow_started.set()
                await release.wait()
        workspace._fetch = fetch
        task = asyncio.create_task(workspace._sync(0, (), False))
        try:
            await asyncio.wait_for(slow_started.wait(), 1)
            await asyncio.sleep(.15)
            self.assertIn(2, workspace.progress)
            self.assertTrue(workspace.busy)
        finally:
            release.set()
            await task

    async def test_denied_friend_is_removed_before_a_slow_refresh_finishes(self):
        workspace = SyncHarness(['first', 'second', 'restricted', 'slow'])
        workspace.snapshots['restricted'] = {'user_id': '50'}
        workspace._profile_forbidden = lambda login, context: workspace.snapshots.pop(login, None)
        slow_started = asyncio.Event()
        release = asyncio.Event()
        async def fetch(login, *args):
            if login == 'restricted':
                request = httpx.Request('GET', 'https://example.test')
                raise httpx.HTTPStatusError('restricted', request=request, response=httpx.Response(403, request=request))
            if login == 'slow':
                slow_started.set()
                await release.wait()
        workspace._fetch = fetch
        task = asyncio.create_task(workspace._sync(0, (), False))
        try:
            await asyncio.wait_for(slow_started.wait(), 1)
            self.assertNotIn('restricted', workspace.snapshots)
            self.assertIn(3, workspace.progress)
            self.assertTrue(workspace.busy)
        finally:
            release.set()
            await task

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
    async def test_summary_batches_overlap_through_authenticated_http(self):
        url = os.environ['FRIENDS_REFRESH_SIMULATION_URL']
        with TemporaryDirectory() as directory:
            client = OAuthClient(url, MemoryStore(), lock_directory=directory)
            client._save_credentials(DeviceCredentials('a' * 43, 'r' * 43,
                '2099-01-01T00:00:00Z', client._new_private_key_pem()))
            factory = make_session_factory(f'sqlite:///{directory}/friends.db')
            workspace = SyncHarness(['you'] + [f'friend{i}' for i in range(100)])
            workspace.app = SimpleNamespace(provider=HttpProjectProvider(oauth_client=client),
                account_login='you', account_id='42', account_generation=0, session_factory=factory)
            workspace.context = (0, '42', 21, id(workspace.app.provider), url)
            try:
                httpx.post(f'{url}/reset').raise_for_status()
                await asyncio.wait_for(workspace._sync(0, workspace.context, False), 15)
                stats = httpx.get(f'{url}/stats').json()
                self.assertEqual(stats['peak'], 2)
                self.assertEqual(stats['completed'], 3)
                self.assertEqual(stats['invalid'], 0)
                self.assertEqual(len(workspace.snapshots), 101)
            finally:
                client.close()
                factory.kw['bind'].dispose()

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
                from ft_tui.features.friends.adapters.storage import cached_observations
                with factory() as session:
                    self.assertEqual(len(cached_observations(session, '42', 21, origin=url)), 15)
            finally:
                client.close()
                factory.kw['bind'].dispose()

class FriendsRefreshLatencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_paints_from_cached_batch_then_refreshes_profiles(self):
        workspace = SyncHarness([f'friend{i}' for i in range(4)])
        workspace.app = SimpleNamespace(provider=SimpleNamespace(get_friend_summaries=lambda: None), account_login='you')
        workspace.context = (0, '42', 21, 0, 'backend')
        calls = {'batch': 0, 'summary': 0}
        class Service:
            async def batch(self, provider, logins, cursus, **kw):
                calls['batch'] += 1
                return [{'login': login, 'user_id': str(100 + i), 'details_complete': False}
                        for i, login in enumerate(logins)]
            async def summary(self, provider, login, cursus, **kw):
                calls['summary'] += 1
                return {'login': login, 'user_id': '100', 'details_complete': False}
            def save(self, *args, **kwargs): pass
        async def read(resource, parts, fetch, **kwargs): return await fetch()
        workspace._read = read
        with patch('ft_tui.features.friends.views.workspace.friends_service_for', return_value=Service()), \
             patch('ft_tui.features.friends.views.workspace.friend_snapshot', lambda value, *a, **k: value), \
             patch('ft_tui.features.friends.views.workspace.current_location', lambda data, **k: 'Campus'):
            await workspace._sync(0, workspace.context, True)
        self.assertEqual(calls['batch'], 1)
        self.assertEqual(calls['summary'], 4)

    async def test_detail_enrichment_runs_two_at_a_time(self):
        class Service:
            inflight = peak = done = 0
            async def detail(self, provider, login, cursus, **kw):
                Service.inflight += 1
                Service.peak = max(Service.peak, Service.inflight)
                await asyncio.sleep(.05)
                Service.inflight -= 1
                Service.done += 1
                return {'login': login, 'user_id': str(100), 'details_complete': True}
            def save(self, *args, **kwargs): pass
        class Harness:
            _ensure_details = FriendsWorkspace._ensure_details
            _enrich_details = FriendsWorkspace._enrich_details
            busy = False; detail_busy = False; selected_login = None; comparing = False
            epoch = 0; context = (0, '42', 21, 0, 'backend'); _force_details = False
            detail_attempted = set(); detail_snapshots = {}; errors = {}
            app = SimpleNamespace(account_connected=True, account_login='you',
                                  provider=SimpleNamespace(get_friend_summary=lambda: None))
            def _valid(self, *args): return True
            def _sync_targets(self): return list(self.snapshots)
            def _refresh_view(self): pass
            def run_worker(self, coroutine, **kwargs): return asyncio.create_task(coroutine)
            async def _read(self, resource, parts, loader, **kwargs): return await loader()
        workspace = Harness()
        workspace.snapshots = {f'friend{i}': {'projects_loaded': False} for i in range(6)}
        with patch('ft_tui.features.friends.views.workspace.friends_service_for', return_value=Service()), \
             patch('ft_tui.features.friends.views.workspace.friend_snapshot', lambda value, *a, **k: value):
            workspace._ensure_details()
            await workspace.detail_worker
        self.assertEqual(Service.done, 6)
        self.assertEqual(Service.peak, 2)


class FriendRankLabelTests(unittest.TestCase):
    def workspace(self):
        class Harness:
            app = SimpleNamespace(language='en')
            t = FriendsWorkspace.t
            _curriculum_short = FriendsWorkspace._curriculum_short
            _curriculum_label = FriendsWorkspace._curriculum_label
        return Harness()

    def test_short_rank_cells_keep_the_explanation_in_details(self):
        workspace = self.workspace()
        self.assertEqual(workspace._curriculum_short({'curriculum_rank': {'status': 'pending'}}), 'Loading')
        self.assertEqual(workspace._curriculum_label({'curriculum_rank': {'status': 'pending'}}), 'Loading campus graph…')
        self.assertEqual(workspace._curriculum_short({'curriculum_rank': {'status': 'unavailable'}}), 'No rank')
        self.assertEqual(workspace._curriculum_label({'curriculum_rank': {'status': 'unavailable'}}),
                         'Campus graph temporarily unavailable')
        self.assertEqual(workspace._curriculum_short({'curriculum_rank': {'status': 'inferred',
                         'section': 'common-core', 'rank': 5}}), 'Rank 05')

    def test_short_rank_copy_is_translated(self):
        from ft_tui.i18n import translate
        for language in ('fr', 'es'):
            self.assertNotEqual(translate('No rank', language), 'No rank')
