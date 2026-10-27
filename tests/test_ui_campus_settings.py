"""Readable campus choices retain the account's numeric catalog scope."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Cursus
from ft_tui.services.user_settings import get_setting, save_settings
from ft_tui.services.curriculum_selection import preference_key
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Select


class CampusSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_readable_cached_campuses_save_the_selected_id(self):
        campuses = [
            {'id': 31, 'name': '42 Paris', 'country': 'France', 'city': 'Paris', 'is_primary': True},
            {'id': 44, 'name': '42 Barcelona', 'country': 'Spain', 'city': 'Barcelona', 'is_primary': False},
        ]
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "ui.sqlite"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21',
                                            'catalog_last_account': '42', 'catalog_last_campuses': json.dumps(campuses)})
                    session.add(Cursus(id=21, name='42cursus')); session.commit()
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(140, 50)):
                    selector = app.query_one('#catalog-campus', Select)
                    self.assertEqual(selector._options, [('France - Paris', '31'), ('Spain - Barcelona', '44')])
                    self.assertEqual(selector.value, '31')
                    selector.value = '44'
                    await app._save_settings()
                    with factory() as session:
                        self.assertEqual(get_setting(session, preference_key('42', 21, None, 'campus')), '44')
                    self.assertEqual(app._catalog_scope().campus_id, 44)
                    app._load_curriculum_setting_widgets()
                    self.assertEqual(selector.value, '44')
                    app.account_campuses = [{'id': 31, 'name': '42 Paris', 'is_primary': True}]
                    app._load_curriculum_setting_widgets()
                    self.assertIn(('42 Paris', '31'), selector._options)
                    self.assertEqual(selector.value, '44')
                    app.campus_directory = [
                        {'id': 31, 'name': 'Paris', 'country': 'France', 'city': 'Paris'},
                        {'id': 44, 'name': 'Barcelona', 'country': 'Spain', 'city': 'Barcelona'},
                        {'id': 55, 'name': 'Porto', 'country': 'Portugal', 'city': 'Porto'},
                    ]
                    app._load_curriculum_setting_widgets()
                    self.assertIn(('Portugal - Porto', '55'), selector._options)
                    self.assertEqual(selector.value, '44')
                    self.assertEqual(app.account_campuses, [{'id': 31, 'name': '42 Paris', 'is_primary': True}])
                    selector.value = '55'
                    await app._save_settings()
                    self.assertEqual(app._catalog_scope().campus_id, 55)
                    app.campus_directory = []
                    app.account_campuses = []; app.account_id = None
                    app._load_curriculum_setting_widgets()
                    self.assertEqual(selector._options, [])
            finally:
                factory.kw['bind'].dispose()

    async def test_directory_refresh_is_cached_for_offline_startup_and_account_fenced(self):
        class Provider:
            def list_campuses(self):
                return [{'id': 55, 'name': 'Porto', 'country': 'Portugal', 'city': 'Porto', 'active': True}]
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "directory.sqlite"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true'})
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(140, 50)):
                    provider = Provider()
                    app.provider = provider
                    self.assertTrue(await app._refresh_campus_directory(provider, app.account_generation))
                    self.assertIn(('Portugal - Porto', '55'), app.query_one('#catalog-campus', Select)._options)
                    self.assertFalse(await app._refresh_campus_directory(provider, app.account_generation - 1))
                restored = FortyTwoTuiApp(factory, None)
                self.assertEqual(restored.campus_directory[0]['id'], 55)
            finally:
                factory.kw['bind'].dispose()
