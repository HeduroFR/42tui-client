import asyncio
import threading
import unittest
from textual.app import App
from textual.widgets import Static, ListView, Collapsible
from ft_tui.features.catalog.models import CatalogScope
from ft_tui.features.projects.views.activity import ProjectActivityScreen
from activity_fixtures import history, evaluations

class Provider:
    def __init__(self): self.calls = []; self.history_value = history()
    def get_project_activity(self, *args, refresh=False):
        self.calls.append(('history', refresh)); return self.history_value
    def get_team_evaluations(self, p, t, *args, refresh=False):
        self.calls.append((t, refresh)); return evaluations(t)

class Harness(App):
    language = 'en'; account_id = '42'; account_generation = 0
    def __init__(self, provider): super().__init__(); self.provider = provider
    def on_mount(self):
        self.push_screen(ProjectActivityScreen(1001, 'Libft', CatalogScope(21, 31), '42', self.provider, 0,
                                               'https://projects.intra.42.fr/libft/mine'))

class ActivityScreenTests(unittest.IsolatedAsyncioTestCase):
    async def test_current_history_feedback_refresh_and_responsive_layout(self):
        provider = Provider(); app = Harness(provider)
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause(); await pilot.pause()
            screen = app.screen
            self.assertEqual(screen.selected_team_id, 8)
            self.assertIn('125%', str(screen.query_one('#activity-team-summary', Static).render()))
            self.assertIn('Scheduled', str(screen.query_one('#activity-evaluations').children[0].render()))
            self.assertGreater(screen.query_one('#activity-detail').region.x, screen.query_one('#activity-sidebar').region.x)
            peer = screen.query_one('#peer-evaluation-1', Collapsible)
            self.assertTrue(peer.collapsed); peer.collapsed = False
            await pilot.pause()
            self.assertIn('[red]literal', str(screen.query_one('#peer-comment-1', Static).render()))
            screen.query_one('#activity-team-list', ListView).index = 1
            await pilot.pause(); await pilot.pause()
            self.assertEqual(screen.selected_team_id, 7)
            self.assertIn('0%', str(screen.query_one('#activity-team-summary', Static).render()))
            await pilot.press('r'); await pilot.pause(); await pilot.pause()
            self.assertEqual(screen.selected_team_id, 7)
            self.assertIn(('history', True), provider.calls); self.assertIn((7, True), provider.calls)
            await pilot.resize_terminal(80, 40); await pilot.pause()
            self.assertGreaterEqual(screen.query_one('#activity-detail').region.y, screen.query_one('#activity-sidebar').region.bottom)
            await pilot.press('escape'); await pilot.pause(); self.assertNotIsInstance(app.screen, ProjectActivityScreen)
    async def test_missing_current_team_selects_newest_without_current_label(self):
        p = Provider(); p.history_value['current_team_id'] = 99
        app = Harness(p)
        async with app.run_test() as pilot:
            await pilot.pause(); await pilot.pause()
            self.assertEqual(app.screen.selected_team_id, 8)
            self.assertNotIn('Current attempt', str(app.screen.query_one('#activity-team-summary', Static).render()))
    async def test_account_change_clears_visible_private_data(self):
        app = Harness(Provider())
        async with app.run_test() as pilot:
            await pilot.pause(); await pilot.pause()
            app.account_generation = 1; app.account_id = '99'
            await pilot.pause(.35)
            self.assertEqual(app.screen.selected_team_id, None)
            self.assertNotIn("student's group", str(app.screen.query_one('#activity-team-summary', Static).render()))
            self.assertIn('Account changed', str(app.screen.query_one('#activity-status', Static).render()))
    async def test_late_previous_team_response_is_discarded(self):
        gate = threading.Event(); started = threading.Event()
        class Slow(Provider):
            def get_team_evaluations(self, p, t, *args, **kw):
                if t == 8: started.set(); gate.wait(3)
                value = evaluations(t); value['automated']['items'][0]['comment'] = f'team-{t}'
                return value
        app = Harness(Slow())
        try:
            async with app.run_test() as pilot:
                await pilot.pause()
                await asyncio.to_thread(started.wait, 1)
                app.screen.query_one('#activity-team-list', ListView).index = 1
                await pilot.pause(); gate.set(); await pilot.pause(); await pilot.pause()
                self.assertEqual(app.screen.selected_team_id, 7)
                self.assertEqual(str(app.screen.query_one('#automated-output-2', Static).render()), 'team-7')
        finally: gate.set()
    async def test_independent_failure_and_empty_history(self):
        class Partial(Provider):
            def get_team_evaluations(self, p, t, *args, **kw):
                result = evaluations(t); result['peer'] = {'items': [], 'source': {'status': 'unavailable', 'stale': True, 'collected_at': None}}
                return result
        app = Harness(Partial())
        async with app.run_test() as pilot:
            await pilot.pause(); await pilot.pause()
            self.assertTrue(app.screen.query('#automated-evaluation-2'))
            self.assertIn('unavailable', str(app.screen.query_one('#activity-evaluation-status', Static).render()).lower())
        p = Provider(); p.history_value['teams'] = []; p.history_value['current_team_id'] = None
        async with Harness(p).run_test() as pilot:
            await pilot.pause(); await pilot.pause()
            self.assertIn('No attempts', str(pilot.app.screen.query_one('#activity-status', Static).render()))

    async def test_refresh_error_remains_visible_and_authorization_failure_clears_data(self):
        import httpx
        class Failing(Provider):
            fail = False
            unauthorized = False
            def get_project_activity(self, *args, **kwargs):
                if self.unauthorized:
                    request = httpx.Request('GET', 'https://api.example.test/activity')
                    raise httpx.HTTPStatusError('Unauthorized', request=request, response=httpx.Response(401, request=request))
                if self.fail: raise OSError('offline')
                return super().get_project_activity(*args, **kwargs)
        p = Failing(); app = Harness(p)
        async with app.run_test() as pilot:
            await pilot.pause(); await pilot.pause(); p.fail = True
            app.screen.action_refresh(); await pilot.pause(.4)
            self.assertIn('Could not load attempts', str(app.screen.query_one('#activity-status', Static).render()))
            # A manual refresh respects the transient backoff as well.
            cache = app._read_cache
            clock = cache.clock
            cache.clock = lambda: clock() + 5
            p.fail = False; p.unauthorized = True; app.screen.action_refresh(); await pilot.pause(.4)
            self.assertIsNone(app.screen.selected_team_id)
            self.assertNotIn("student's group", str(app.screen.query_one('#activity-team-summary', Static).render()))

    async def test_newest_fallback_uses_instants_and_stale_empty_history_is_explicit(self):
        p = Provider(); p.history_value['current_team_id'] = None
        p.history_value['teams'][0]['created_at'] = '2026-10-22T10:00:00+02:00'
        p.history_value['teams'][1]['created_at'] = '2026-10-22T09:00:00Z'
        app = Harness(p)
        async with app.run_test() as pilot:
            await pilot.pause(); await pilot.pause()
            self.assertEqual(app.screen.selected_team_id, 7)
        p = Provider(); p.history_value['teams'] = []; p.history_value['current_team_id'] = None
        p.history_value['source']['status'] = 'unavailable'; p.history_value['source']['stale'] = True
        app = Harness(p)
        async with app.run_test() as pilot:
            await pilot.pause(); await pilot.pause()
            status = str(app.screen.query_one('#activity-status', Static).render())
            self.assertIn('outdated', status)
            self.assertNotIn('No attempts for this project.', status)

class ActivityEntryTests(unittest.IsolatedAsyncioTestCase):
    async def test_project_entry_opens_screen_and_escape_preserves_selection(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from ft_tui.db.database import make_session_factory
        from ft_tui.db.models import Project
        from ft_tui.features.settings.adapters.storage import save_settings
        from ft_tui.ui.app import FortyTwoTuiApp
        from textual.widgets import Button, TabbedContent
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "activity.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
                session.add(Project(slug='libft', name='Libft', official_project_id=1001, setup_status='completed'))
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 50)) as pilot:
                    app.query_one(TabbedContent).active = 'projects-tab'
                    await pilot.pause()
                    project = next(iter(app.projects.values()))
                    app.selected_project_key = project.ui_key; app._render_project_details(project)
                    self.assertTrue(app.query_one('#show-project-activity', Button).disabled)
                    app.account_id = '42'; app.provider = Provider()
                    with patch.object(app, '_catalog_scope', return_value=CatalogScope(21, 31)):
                        app._render_project_details(project)
                        button = app.query_one('#show-project-activity', Button)
                        self.assertFalse(button.disabled); button.press()
                        await pilot.pause(); await pilot.pause()
                        self.assertIsInstance(app.screen, ProjectActivityScreen)
                        await pilot.press('escape'); await pilot.pause()
                        self.assertEqual(app.selected_project_key, project.ui_key)
            finally:
                factory.kw['bind'].dispose()

class CachedActivityTests(unittest.IsolatedAsyncioTestCase):
    async def test_reopen_displays_cached_evaluations_while_backend_is_blocked(self):
        provider = Provider()
        app = Harness(provider)
        gate = threading.Event()
        try:
            async with app.run_test() as pilot:
                await pilot.pause(); await pilot.pause()
                self.assertIsNotNone(app.screen.evaluations)
                await pilot.press('escape'); await pilot.pause()
                original = provider.get_project_activity
                def blocked(*args, **kwargs):
                    gate.wait(timeout=5)
                    return original(*args, **kwargs)
                provider.get_project_activity = blocked
                app.push_screen(ProjectActivityScreen(1001, 'Libft', CatalogScope(21, 31), '42', provider, 0, ''))
                await pilot.pause(); await pilot.pause()
                self.assertFalse(gate.is_set())
                self.assertEqual(app.screen.selected_team_id, 8)
                self.assertIsNotNone(app.screen.evaluations)
                self.assertTrue(app.screen.query_one('#activity-evaluations').display)
                self.assertGreater(len(app.screen.query_one('#activity-evaluations').children), 0)
                gate.set()
                await pilot.pause()
        finally:
            gate.set()
