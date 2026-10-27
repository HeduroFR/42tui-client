"""Startup remains offline-capable; release notes and automatic update opt-out."""
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from ft_tui.db.database import make_session_factory
from ft_tui.services.updates import Installation, UpdateService
from ft_tui.services.user_settings import get_setting, save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.updates import ChangelogScreen
from ft_tui.ui.select import Select


class StartupUpdateTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.factory = make_session_factory(f'sqlite:///{self.tmp.name}/test.db')
        self.addCleanup(self.factory.kw['bind'].dispose)
        self.addCleanup(self.tmp.cleanup)
        self.save({'onboarding_completed': 'true', 'language': 'en'})

    def save(self, values):
        with self.factory() as session:
            save_settings(session, values)

    def get(self, key):
        with self.factory() as session:
            return get_setting(session, key)

    def app(self, check=None, managed=True):
        installation = Installation('uv', '/fake/uv', Path('/fake/ft-tui'), Path('/fake/42tui'), '0.3.0')
        service = UpdateService(current='0.3.0', installation=installation if managed else None,
                                check=check or Mock(return_value='0.4.0'))
        return FortyTwoTuiApp(self.factory, None, update_service=service)

    async def test_initial_launch_baseline_and_new_release(self):
        app = self.app()
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(self.get('updates:last_seen_version'), '0.3.0')
            self.assertNotIsInstance(app.screen, ChangelogScreen)
            self.assertEqual(app.pending_update, '0.4.0')
        # The persisted cooldown suppresses repeated checks, including failures.
        check = Mock(return_value='0.4.0')
        async with self.app(check).run_test() as pilot:
            await pilot.pause()
            check.assert_not_called()

    async def test_notes_are_acknowledged_only_on_dismissal(self):
        self.save({'updates:last_seen_version': '0.2.0', 'automatic_updates': 'false'})
        async with self.app().run_test() as pilot:
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ChangelogScreen)
            self.assertEqual(self.get('updates:last_seen_version'), '0.2.0')
            await pilot.press('escape')
            self.assertEqual(self.get('updates:last_seen_version'), '0.3.0')
        async with self.app().run_test() as pilot:
            await pilot.pause()
            self.assertNotIsInstance(pilot.app.screen, ChangelogScreen)

    async def test_optout_no_network_and_setting_persists(self):
        self.save({'automatic_updates': 'false'})
        check = Mock()
        app = self.app(check)
        async with app.run_test() as pilot:
            await pilot.pause()
            check.assert_not_called()
            self.assertIsNone(app.pending_update)
            self.assertEqual(app.query_one('#automatic-updates', Select).value, 'false')
            app.query_one('#automatic-updates', Select).value = 'true'
            await app._save_settings()
            self.assertEqual(self.get('automatic_updates'), 'true')
            app.pending_update = '0.4.0'
            app.query_one('#automatic-updates', Select).value = 'false'
            await app._save_settings()
            self.assertIsNone(app.pending_update)
            self.assertFalse(app.automatic_updates_enabled())

    async def test_optout_while_check_is_pending(self):
        app = self.app()
        with self.factory() as session:
            save_settings(session, {'updates:last_check': '9999999999'})
        async with app.run_test() as pilot:
            await pilot.pause()
            app.pending_update = None
            self.save({'updates:last_check': '0'})
            started, finish = asyncio.Event(), asyncio.Event()
            async def check(*args):
                started.set()
                await finish.wait()
                return '0.4.0'
            from unittest.mock import patch
            with patch('ft_tui.ui.updates.asyncio.to_thread', side_effect=check):
                worker = asyncio.create_task(app._check_updates())
                await started.wait()
                self.save({'automatic_updates': 'false'})
                finish.set()
                await worker
            self.assertIsNone(app.pending_update)

    async def test_offline_or_non_newer_release_never_installs(self):
        for check in (Mock(side_effect=OSError('offline')), Mock(return_value='0.3.0'),
                      Mock(return_value='0.2.2'), Mock(return_value='0.5.0rc1')):
            self.save({'updates:last_check': '0'})
            app = self.app(check)
            async with app.run_test() as pilot:
                await pilot.pause()
                self.assertIsNone(app.pending_update)

    async def test_development_install_never_queues_install(self):
        app = self.app(managed=False)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIsNone(app.pending_update)
