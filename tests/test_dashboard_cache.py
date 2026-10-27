"""Restore the complete scoped dashboard before any startup network result."""
import asyncio
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.api.oauth_client import DeviceCredentials, OAuthClient
from ft_tui.db.database import make_session_factory
from ft_tui.features.catalog.adapters.cache import apply_catalog_page, save_account_data
from ft_tui.features.profiles.adapters.cache import PROFILE_KEY, load_goals, load_profile, save_goals, save_profile
from ft_tui.features.settings.adapters.storage import get_setting, save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import ProjectRankHeader, Static
from tests.test_oauth_client import MemoryStore


class DashboardCacheTests(unittest.TestCase):
    def test_profile_is_bound_to_credentials_and_backend_and_stores_no_secrets(self):
        factory = make_session_factory('sqlite:///:memory:')
        credentials = DeviceCredentials('access-secret', 'refresh-secret', '2099-01-01', 'key-secret')
        client = SimpleNamespace(credentials=credentials, base_url='https://api.example.test')
        profile = {'account_id': '42', 'login': 'student', 'campuses': [{'id': 31}],
                   'access_token': 'must-not-cache'}
        try:
            with factory() as session:
                save_profile(session, client, profile)
                self.assertEqual(load_profile(session, client)['account_id'], '42')
                raw = get_setting(session, PROFILE_KEY)
                for secret in ('access-secret', 'refresh-secret', 'key-secret', 'must-not-cache'):
                    self.assertNotIn(secret, raw)
                client.base_url = 'https://another.example.test'
                self.assertEqual(load_profile(session, client), {})
                client.base_url = 'https://api.example.test'
                client.credentials = DeviceCredentials('different', 'different', '2099', 'key-secret')
                self.assertEqual(load_profile(session, client), {})
                client.credentials = None
                self.assertEqual(load_profile(session, client), {})
                client.credentials = credentials
                save_settings(session, {PROFILE_KEY: 'broken'})
                self.assertEqual(load_profile(session, client), {})
        finally:
            factory.kw['bind'].dispose()

    def test_goals_are_isolated_and_unavailable_refresh_preserves_saved_observation(self):
        factory = make_session_factory('sqlite:///:memory:')
        try:
            with factory() as session:
                save_goals(session, '42', 21, {'status': 'available', 'cc_validated': True})
                save_goals(session, '42', 21, {'status': 'unavailable'})
                self.assertEqual(load_goals(session, '42', 21),
                                 {'status': 'available', 'cc_validated': True, 'stale': True})
                self.assertEqual(load_goals(session, 'other', 21), {})
                self.assertEqual(load_goals(session, '42', 9), {})
        finally:
            factory.kw['bind'].dispose()

    def test_unknown_curriculum_keeps_saved_rank_until_a_concrete_replacement(self):
        from ft_tui.features.catalog.adapters.cache import load_curriculum
        factory = make_session_factory('sqlite:///:memory:')
        context = {'account_id': '42', 'cursus_id': 21, 'campus_id': 31}
        try:
            with factory() as session:
                save_account_data(session, '42', 21, 31, {**context,
                    'rank': {'rank': 2, 'source': 'quest'}, 'track': {'track': 'new', 'source': 'quest'}}, [])
                pending = {**context, 'rank': {'rank': None, 'source': 'unknown'},
                           'track': {'track': None, 'source': 'unknown'},
                           'sources': {'projects': {'status': 'unavailable', 'stale': True}}}
                save_account_data(session, '42', 21, 31, pending, [])
                cached = load_curriculum(session, '42', 21, 31)
                self.assertEqual(cached['rank']['rank'], 2)
                self.assertTrue(cached['rank']['stale'])
                self.assertEqual(cached['track']['track'], 'new')
                fresh = {**pending, 'sources': {'projects': {'status': 'available', 'stale': False}}}
                save_account_data(session, '42', 21, 31, fresh, [])
                self.assertEqual(load_curriculum(session, '42', 21, 31)['rank']['rank'], 2)
                save_account_data(session, '42', 21, 31, {
                    **fresh, 'rank': {'rank': 3, 'source': 'quest'},
                    'track': {'track': 'new', 'source': 'quest'}}, [])
                self.assertEqual(load_curriculum(session, '42', 21, 31)['rank']['rank'], 3)
        finally:
            factory.kw['bind'].dispose()


class DashboardStartupCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_dashboard_frame_restores_rank_journey_and_profile_before_network(self):
        with TemporaryDirectory() as directory:
            client = OAuthClient('https://api.example.test', MemoryStore(), lock_directory=directory)
            client._save_credentials(DeviceCredentials('a' * 43, 'r' * 43, '2099-01-01T00:00:00Z', client._new_private_key_pem()))
            database = f'sqlite:///{Path(directory) / "dashboard.db"}'
            factory = make_session_factory(database)
            profile = {'account_id': '42', 'login': 'cached-student', 'first_name': 'Jane',
                       'wallet': 12, 'campuses': [{'id': 31, 'is_primary': True}]}
            now = datetime.now(timezone.utc).isoformat()
            rows = [{'project_id': n, 'slug': f'p{n}', 'name': f'Project {n}', 'track': 'new',
                     'rank': rank, 'kind': 'project', 'section': section}
                    for n, rank, section in ((1, 2, 'common-core'), (2, 3, 'common-core'),
                                             (3, None, 'specialization'))]
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
                save_profile(session, client, profile)
                save_goals(session, '42', 21, {'status': 'available', 'cc_validated': True})
                apply_catalog_page(session, {'items': rows, 'snapshot_id': 'graph',
                                             'meta': {'cursus_id': 21, 'campus_id': 31}})
                save_account_data(session, '42', 21, 31, {
                    'account_id': '42', 'cursus_id': 21, 'campus_id': 31,
                    'rank': {'rank': 2, 'source': 'quest', 'completed': False},
                    'track': {'track': 'new', 'source': 'quest'},
                    'sources': {'projects': {'status': 'available', 'stale': False, 'collected_at': now}},
                }, [])
            factory.kw['bind'].dispose()
            factory = make_session_factory(database)
            app = FortyTwoTuiApp(factory, HttpProjectProvider(oauth_client=client))
            pending = asyncio.Event()
            async def wait_for_network(*args):
                await pending.wait()
            async def no_detail(*args):
                pass
            app._sync_online_provider = wait_for_network
            app._start_goals_refresh = lambda: None
            app._load_selected_catalog_detail = no_detail
            app._load_project_registration = lambda *args: None
            frames = []
            refresh = app._refresh_dashboard
            async def record_frame():
                frames.append(app.project_curriculum.get('selected_rank', {}).get('rank'))
                await refresh()
            app._refresh_dashboard = record_frame
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    await pilot.pause()
                    self.assertFalse(pending.is_set())
                    self.assertTrue(frames)
                    self.assertEqual(set(frames), {2})
                    self.assertEqual(app.account_id, '42')
                    self.assertEqual(str(app.query_one('#dashboard-login', Static).render()), 'cached-student')
                    self.assertEqual(str(app.query_one('#dashboard-wallet', Static).render()), '12 ₳')
                    self.assertEqual(str(app.query_one('#dashboard-progress-value', Static).render()), '00 / 01')
                    self.assertEqual({header.rank for header in app.query(ProjectRankHeader)}, {2, 3})
                    # Outage/queued goals retain the same last-known final stage.
                    app.provider = SimpleNamespace(get_goals=lambda *args: {'status': 'unavailable'})
                    await app._refresh_goals((app.account_generation, '42', 21))
                    self.assertTrue(app.account_goals['cc_validated'])
                    self.assertTrue(app.account_goals['stale'])
                    self.assertEqual(str(app.query_one('#dashboard-progress-value', Static).render()), '00 / 01')
                    # A refresh must never publish its intermediate unknown view,
                    # including while branches/catalog are still being fetched.
                    from tests.test_ui_project_rank import RankProvider
                    class RefreshProvider(RankProvider):
                        def get_curriculum(self, scope):
                            value = super().get_curriculum(scope)
                            value['sources'] = {'projects': {'status': 'available', 'stale': False,
                                                            'collected_at': now}}
                            return value
                        def list_branches(self, *args):
                            observed_ranks.append(app.project_curriculum['selected_rank']['rank'])
                            return super().list_branches(*args)
                    observed_ranks = []
                    provider = RefreshProvider()
                    provider.rows = rows
                    app.provider = provider
                    await app._refresh_catalog_context(provider, app.account_generation)
                    self.assertEqual(app.project_curriculum['selected_rank']['rank'], 2)
                    provider.rank = {'rank': 3, 'source': 'quest', 'completed': False}
                    await app._refresh_catalog_context(provider, app.account_generation)
                    self.assertEqual(app.project_curriculum['selected_rank']['rank'], 3)
                    self.assertEqual(observed_ranks, [2, 2])
                    self.assertNotIn(None, frames)
            finally:
                client.close()
                factory.kw['bind'].dispose()

    async def test_language_updates_never_switch_to_the_first_cached_cursus(self):
        from ft_tui.db.models import Cursus
        from ft_tui.ui.components import Select
        factory = make_session_factory('sqlite:///:memory:')
        try:
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21',
                                        'default_cursus_source': 'manual', 'catalog_last_account': '42',
                                        'catalog_last_campuses': '[{"id":31}]'})
                for cursus, rank in ((9, None), (21, 1)):
                    row = {'project_id': cursus, 'slug': str(cursus), 'name': str(cursus),
                           'rank': rank, 'track': 'new', 'section': 'common-core', 'kind': 'project'}
                    apply_catalog_page(session, {'items': [row], 'snapshot_id': str(cursus),
                                                 'meta': {'cursus_id': cursus, 'campus_id': 31}})
                    save_account_data(session, '42', cursus, 31, {
                        'account_id': '42', 'cursus_id': cursus, 'campus_id': 31,
                        'rank': {'rank': rank, 'source': 'quest' if rank is not None else 'unknown'},
                        'track': {'track': 'new', 'source': 'quest'},
                    }, [])
                session.get(Cursus, 9).name = 'C Piscine'
                session.get(Cursus, 21).name = '42cursus'
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            frames = []
            refresh = app._refresh_dashboard
            async def record_frame():
                frames.append((app.project_curriculum.get('cursus_id'),
                               app.project_curriculum.get('selected_rank', {}).get('rank')))
                await refresh()
            app._refresh_dashboard = record_frame
            async with app.run_test(size=(120, 42)) as pilot:
                await pilot.pause()
                app.language = 'fr'
                app._apply_language()
                await pilot.pause()
                self.assertTrue(frames)
                self.assertEqual(set(frames), {(21, 1)})
                selector = app.query_one('#default-cursus', Select)
                self.assertEqual(selector.value, '21')
                # A delayed event for an option which is no longer selected is ignored.
                await app.on_select_changed(Select.Changed(selector, '9'))
                with factory() as session:
                    self.assertEqual(get_setting(session, 'default_cursus_id'), '21')
        finally:
            factory.kw['bind'].dispose()
