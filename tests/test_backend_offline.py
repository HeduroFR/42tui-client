import unittest
from unittest.mock import patch

import httpx
from textual.app import App
from textual.widgets import TabbedContent, TabPane

from ft_tui.api.health import backend_available
from ft_tui.ui.button import Button
from ft_tui.ui.offline import OfflineMixin, OfflineScreen


class HealthTests(unittest.TestCase):
    def test_health_requires_the_expected_response(self):
        with patch('ft_tui.api.health.httpx.get') as get:
            get.return_value = httpx.Response(200, json={'status': 'ok'})
            self.assertTrue(backend_available('https://example.test/'))
            self.assertEqual(get.call_args.args[0], 'https://example.test/health')
            get.return_value = httpx.Response(503, json={'status': 'ok'})
            self.assertFalse(backend_available('https://example.test'))
            get.return_value = httpx.Response(200, text='not json')
            self.assertFalse(backend_available('https://example.test'))
            get.side_effect = httpx.ConnectError('offline')
            self.assertFalse(backend_available('https://example.test'))


class Harness(OfflineMixin, App):
    language = 'en'
    backend_available = None
    _normal_sub_title = 'version'
    oauth_client = None

    def compose(self):
        yield Button('Cluster Map', id='dashboard-cluster-map')
        with TabbedContent(initial='projects-tab', id='main-tabs'):
            with TabPane('Projects', id='projects-tab'):
                pass
            with TabPane('Cluster Map', id='cluster-map'):
                pass


class OfflineTests(unittest.IsolatedAsyncioTestCase):
    async def test_outage_warning_and_recovery_preserve_navigation(self):
        app = Harness()
        async with app.run_test() as pilot:
            app._set_backend_available(False)
            await pilot.pause()
            self.assertIsInstance(app.screen, OfflineScreen)
            self.assertTrue(app.query_one('#dashboard-cluster-map', Button).disabled)
            await pilot.press('escape')
            await pilot.pause()
            app._set_backend_available(True)
            await pilot.pause()
            self.assertFalse(app.query_one('#dashboard-cluster-map', Button).disabled)
            self.assertEqual(app.sub_title, 'version')
            app.query_one(TabbedContent).active = 'cluster-map'
            await pilot.pause()
            app._set_backend_available(False)
            await pilot.pause()
            self.assertEqual(app.query_one(TabbedContent).active, 'projects-tab')

    async def test_full_app_switches_while_a_modal_is_open(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from ft_tui.db.database import make_session_factory
        from ft_tui.features.settings.adapters.storage import save_settings
        from ft_tui.ui.app import FortyTwoTuiApp

        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "test.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
            app = FortyTwoTuiApp(factory, None)
            with patch.object(app, '_start_backend_check'):
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    app._set_backend_available(False)
                    await pilot.pause()
                    main = app.screen_stack[0]
                    self.assertTrue(main.query_one('#settings-refresh-catalog', Button).disabled)
                    app._set_backend_available(True)
                    await pilot.pause()
                    self.assertTrue(app.backend_available)
                    self.assertFalse(main.query_one('#settings-refresh-catalog', Button).disabled)
            factory.kw['bind'].dispose()

    async def test_first_run_can_continue_offline(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from ft_tui.db.database import make_session_factory
        from ft_tui.ui.app import FortyTwoTuiApp
        from ft_tui.ui.onboarding import OnboardingScreen

        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "first-run.sqlite"}')
            app = FortyTwoTuiApp(factory, None)
            with patch.object(app, '_start_backend_check'):
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.pause()
                    self.assertIsInstance(app.screen, OnboardingScreen)
                    self.assertFalse(app.screen._valid_account())
                    app._set_backend_available(False)
                    self.assertTrue(app.screen._valid_account())
                    self.assertIn('continue offline', str(app.screen.query_one('#onboarding-account-help').render()))
                    screen = app.screen
                    screen._continue()
                    screen._continue()
                    screen._finish()
                    await pilot.pause()
                    from ft_tui.features.settings.adapters.storage import get_setting
                    with factory() as session:
                        self.assertEqual(get_setting(session, 'onboarding_completed'), 'true')
            factory.kw['bind'].dispose()
