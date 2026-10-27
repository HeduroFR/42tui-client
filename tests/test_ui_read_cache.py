import asyncio
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace

from textual.widgets import Collapsible, DataTable, Static, TabbedContent
from ft_tui.ui.button import Button

from ft_tui.features.catalog.models import CatalogScope
from ft_tui.db.database import make_session_factory
from ft_tui.features.friends.adapters.storage import cache_mutual_friends
from ft_tui.app.read_cache import app_cache
from ft_tui.features.friends.views.workspace import FriendsWorkspace
from ft_tui.features.projects.views.activity import ProjectActivityScreen
from tests.manual.cache_profile import FriendsHarness, ActivityHarness, MeasuredProvider, wait_until


class PilotReadCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_forbidden_friend_profile_keeps_other_friends_and_memberships(self):
        import httpx
        from tests.friends_fixtures import snapshot
        from ft_tui.features.friends.adapters.storage import memberships, cached_observations

        class Restricted(MeasuredProvider):
            restricted = False

            def get_friend(self, login, cursus_id, *, refresh=False, **kwargs):
                if login == 'alice' and self.restricted:
                    request = httpx.Request('GET', 'https://example.test/friends/alice')
                    raise httpx.HTTPStatusError('restricted', request=request,
                        response=httpx.Response(403, request=request))
                return snapshot(login, user_id={'you': '42', 'alice': '50', 'bob': '51'}[login])

        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{directory}/friends.sqlite')
            try:
                with factory() as session:
                    cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'},
                                                       {'account_id': '51', 'login': 'bob'}])
                provider = Restricted()
                app = FriendsHarness(factory, provider)
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    app.account_connected = True
                    workspace = app.query_one(FriendsWorkspace)
                    await wait_until(lambda: app.query_one(TabbedContent).active == 'friends')
                    await workspace.reload()
                    workspace.start_sync(refresh=True)
                    await workspace.worker.wait()
                    self.assertIn('alice', workspace.snapshots)
                    provider.restricted = True
                    workspace.start_sync(refresh=True)
                    await workspace.worker.wait()
                    self.assertIn('bob', workspace.snapshots)
                    self.assertNotIn('alice', workspace.snapshots)
                    self.assertEqual({watch.login for watch in workspace.watches}, {'alice', 'bob'})
                    with factory() as session:
                        self.assertEqual({watch.login for watch in memberships(session, '42')}, {'alice', 'bob'})
                        self.assertNotIn('alice', cached_observations(session, '42', 21))
                        self.assertIn('bob', cached_observations(session, '42', 21))
            finally:
                factory.kw['bind'].dispose()

    async def test_closing_during_refresh_does_not_disable_refresh_on_reopen(self):
        from ft_tui.features.projects.views.activity import open_project_activity
        provider = MeasuredProvider()
        app = ActivityHarness(provider)
        try:
            async with app.run_test(size=(120, 40)) as pilot:
                await open_project_activity(app, 1001, 'Libft', CatalogScope(21, 31), '42', provider, 0, None)
                await pilot.pause(.1)
                screen = app.screen
                await wait_until(lambda: screen.evaluations is not None and all(w.is_finished for w in screen.workers))
                provider.mode = 'delayed'
                provider.gate.clear()
                screen.action_refresh()
                await pilot.pause(.05)
                screen.action_close()
                await wait_until(lambda: app.screen is not screen)
                await wait_until(lambda: all(w.is_finished for w in screen.workers))
                await open_project_activity(app, 1001, 'Libft', CatalogScope(21, 31), '42', provider, 0, None)
                await pilot.pause(.1)
                self.assertIs(app.screen, screen)
                self.assertFalse(screen.query_one('#activity-refresh', Button).disabled)
                provider.gate.set()
                screen.query_one('#activity-refresh', Button).press()
                await pilot.pause(.1)
                await wait_until(lambda: all(w.is_finished for w in screen.workers))
                self.assertFalse(screen.query_one('#activity-refresh', Button).disabled)
        finally:
            provider.gate.set()

    async def test_project_entry_reuses_last_authorized_activity_screen(self):
        from ft_tui.features.projects.views.details import ProjectDetailsMixin
        provider = MeasuredProvider()
        app = ActivityHarness(provider)
        app.projects = {'libft': SimpleNamespace(official_project_id=1001, name='Libft', slug='libft')}
        app.selected_project_key = 'libft'
        app._catalog_scope = lambda: CatalogScope(21, 31)
        async with app.run_test(size=(120, 40)) as pilot:
            ProjectDetailsMixin.action_project_activity(app)
            await pilot.pause(.1)
            cold = app.screen
            await wait_until(lambda: cold.evaluations is not None and all(w.is_finished for w in cold.workers))
            peer = cold.query_one('#peer-evaluation-1', Collapsible)
            peer.collapsed = False
            cold.action_close()
            await wait_until(lambda: app.screen is not cold)
            ProjectDetailsMixin.action_project_activity(app)
            await pilot.pause(.1)
            self.assertIs(app.screen, cold)
            self.assertIs(app.screen.query_one('#peer-evaluation-1'), peer)
            self.assertFalse(peer.collapsed)
            app.screen.action_close()
            await wait_until(lambda: app.screen is not cold)
            app_cache(app).invalidate()
            ProjectDetailsMixin.action_project_activity(app)
            await pilot.pause(.1)
            replaced = app.screen
            self.assertIsNot(replaced, cold)
            replaced.action_close()
            await wait_until(lambda: app.screen is not replaced)
            app.account_generation += 1
            ProjectDetailsMixin.action_project_activity(app)
            await pilot.pause(.1)
            self.assertIsNot(app.screen, replaced)

    async def test_pruning_activity_screen_rejects_late_rendering(self):
        from ft_tui.features.projects.views.activity import open_project_activity
        provider = MeasuredProvider()
        app = ActivityHarness(provider)
        async with app.run_test(size=(120, 40)):
            await open_project_activity(app, 1001, 'Libft', CatalogScope(21, 31), '42', provider, 0, None)
            screen = app.screen
            await wait_until(lambda: screen.evaluations is not None and all(w.is_finished for w in screen.workers))
            await app.pop_screen()
            removal = screen.remove()
            self.assertFalse(screen._same_account())
            screen._check_identity()
            self.assertFalse(screen._invalidated)
            await removal
            screen._show_source_status()

    async def test_retained_activity_reconciles_reads_completed_while_closed(self):
        from ft_tui.features.projects.views.details import ProjectDetailsMixin
        provider = MeasuredProvider()
        app = ActivityHarness(provider)
        app.projects = {'libft': SimpleNamespace(official_project_id=1001, name='Libft', slug='libft')}
        app.selected_project_key = 'libft'
        app._catalog_scope = lambda: CatalogScope(21, 31)
        async with app.run_test(size=(120, 40)) as pilot:
            ProjectDetailsMixin.action_project_activity(app)
            await pilot.pause(.1)
            screen = app.screen
            await wait_until(lambda: screen.evaluations is not None and all(w.is_finished for w in screen.workers))
            screen.action_close()
            await wait_until(lambda: app.screen is not screen)
            cached = app_cache(app).peek(screen._cache_key())
            cached['teams'][0]['name'] = 'Updated while closed'
            async def updated():
                return cached
            await app_cache(app).read(screen._cache_key(), updated, refresh=True)
            ProjectDetailsMixin.action_project_activity(app)
            await pilot.pause(.1)
            self.assertIs(app.screen, screen)
            self.assertIn('Updated while closed', str(screen.query_one('#activity-team-summary', Static).render()))

    async def test_warm_activity_first_render_contains_cached_history(self):
        class ObservedActivity(ProjectActivityScreen):
            def render(self):
                if not hasattr(self, 'first_render_had_history'):
                    self.first_render_had_history = bool(self.history and self.evaluations
                        and not self.history['source']['stale']
                        and not self.evaluations['peer']['source']['stale']
                        and '125%' in str(self.query_one('#activity-team-summary', Static).render())
                        and self.query_one('#activity-evaluations').children)
                return super().render()

        provider = MeasuredProvider()
        app = ActivityHarness(provider)
        async with app.run_test(size=(120, 40)) as pilot:
            cold = ProjectActivityScreen(1001, 'Libft', CatalogScope(21, 31), '42', provider, 0, None)
            await app.push_screen(cold)
            await pilot.pause(.1)
            await wait_until(lambda: cold.evaluations is not None and all(w.is_finished for w in cold.workers))
            cold.action_close()
            await wait_until(lambda: app.screen is not cold)
            warm = ObservedActivity(1001, 'Libft', CatalogScope(21, 31), '42', provider, 0, None)
            await app.push_screen(warm)
            await pilot.pause(.1)
            self.assertTrue(warm.first_render_had_history,
                            'Warm navigation rendered an empty skeleton before restoring cached history')
            self.assertEqual(warm.selected_team_id, 8)

    async def test_activity_reopen_reuses_fresh_reads_and_refresh_preserves_widgets(self):
        provider = MeasuredProvider()
        app = ActivityHarness(provider)
        async with app.run_test(size=(120, 40)) as pilot:
            async def open_screen():
                screen = ProjectActivityScreen(1001, 'Libft', CatalogScope(21, 31), '42', provider, 0, None)
                await app.push_screen(screen)
                await pilot.pause(.1)
                await wait_until(lambda: screen.evaluations is not None and all(w.is_finished for w in screen.workers))
                return screen

            screen = await open_screen()
            self.assertEqual(len(provider.calls), 2)
            screen.action_close()
            # A queued timer during ordinary close must not revoke the app cache.
            screen._check_identity()
            await wait_until(lambda: app.screen is not screen)
            screen = await open_screen()
            self.assertEqual(len(provider.calls), 2)
            peer = screen.query_one('#peer-evaluation-1', Collapsible)
            peer.collapsed = False
            screen.action_refresh()
            await pilot.pause(.1)
            await wait_until(lambda: all(w.is_finished for w in screen.workers))
            self.assertEqual(len(provider.calls), 4)
            self.assertIs(screen.query_one('#peer-evaluation-1'), peer)
            self.assertFalse(peer.collapsed)

    async def test_friends_shared_read_survives_consumer_detach_and_write_fences_old_result(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{directory}/friends.sqlite')
            provider = MeasuredProvider()
            with factory() as session:
                cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}])
            app = FriendsHarness(factory, provider)
            try:
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    workspace = app.query_one(FriendsWorkspace)
                    app.account_connected = True
                    await wait_until(lambda: app.query_one(TabbedContent).active == 'friends')
                    await workspace.reload()
                    workspace.start_sync(refresh=True)
                    await workspace.worker.wait()
                    workspace.selected_login = 'alice'
                    workspace._refresh_view()
                    table = workspace.query_one('#friend-projects', DataTable)
                    old_row = table.ordered_rows[0]
                    workspace._refresh_view()
                    self.assertIs(table.ordered_rows[0], old_row)

                    cache = app_cache(app)
                    cache.invalidate()
                    gate = asyncio.Event()
                    started = asyncio.Event()
                    count = []
                    async def load():
                        count.append(1)
                        started.set()
                        await gate.wait()
                        return {'items': [1]}
                    first = asyncio.create_task(workspace._read('friend-detail', ('alice',), load))
                    second = asyncio.create_task(workspace._read('friend-detail', ('alice',), load))
                    await started.wait()
                    first.cancel()
                    with self.assertRaises(asyncio.CancelledError):
                        await first
                    gate.set()
                    self.assertEqual(await second, {'items': [1]})
                    self.assertEqual(len(count), 1)
                    # A membership change discards all earlier friend revisions.
                    cache.invalidate(lambda key: key[1].startswith('friend-'))
                    self.assertIsNone(cache.peek(workspace._read_key('friend-detail', 'alice')))
            finally:
                provider.gate.set()
                factory.kw['bind'].dispose()
