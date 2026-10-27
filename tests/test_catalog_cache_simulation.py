"""CATALOG_CACHE_SIMULATION_URL=http://127.0.0.1:4901/backend runs real HTTP checks."""
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import httpx

from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.api.oauth_client import DeviceCredentials, OAuthClient
from ft_tui.db.database import make_session_factory
from ft_tui.services.catalog_cache import cache_key, complete_catalog, load_context_projects
from ft_tui.db.models import CatalogCache
from ft_tui.services.user_settings import save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Input, Select
from tests.test_oauth_client import MemoryStore


@unittest.skipUnless(os.environ.get('CATALOG_CACHE_SIMULATION_URL'), 'requires local catalog-cache simulation')
class CatalogCacheSimulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_catalog_survives_restart_and_details_and_filters_reuse_disk(self):
        url = os.environ['CATALOG_CACHE_SIMULATION_URL']
        with TemporaryDirectory() as directory:
            client = OAuthClient(url, MemoryStore(), lock_directory=directory)
            client._save_credentials(DeviceCredentials('a' * 43, 'r' * 43, '2099-01-01T00:00:00Z', client._new_private_key_pem()))
            provider = HttpProjectProvider(oauth_client=client)
            database = f'sqlite:///{Path(directory) / "cache.db"}'
            factory = make_session_factory(database)
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21',
                                       'catalog_last_account': '42', 'catalog_last_campuses': '[{"id":31}]'})
            try:
                for restart in (False, True):
                    httpx.get(f'{url}/control').raise_for_status()
                    app = FortyTwoTuiApp(factory, None)
                    async with app.run_test(size=(100, 35)) as pilot:
                        await pilot.pause()
                        app.account_id = '42'
                        app.account_campuses = [{'id': 31}]
                        app.account_connected = True
                        app.provider = provider
                        await app._refresh_catalog_context(provider, app.account_generation)
                        self.assertEqual({p.official_project_id for p in app.projects.values()}, {1, 2, 3, 4})
                        self.assertEqual({p.official_project_id for p in app._visible_projects()}, {1, 3})
                        app.selected_project_key = '3'
                        await app._load_selected_catalog_detail(app.projects['3'])
                        await app._reload_project_catalog()
                        app.selected_project_key = '3'
                        await app._load_selected_catalog_detail(app.projects['3'])
                        self.assertEqual(app.projects['3'].catalog_data['description'], 'Saved project description')
                        app.query_one('#project-view', Select).value = 'all'
                        app.query_one('#project-search', Input).value = 'project'
                        await pilot.pause(.3)
                        calls = httpx.get(f'{url}/stats').json()
                        pages = [c for c in calls if c.startswith('/v1/catalog/projects?')]
                        details = [c for c in calls if c.startswith('/v1/catalog/projects/3?')]
                        self.assertEqual(len(pages), 0 if restart else 5)
                        self.assertEqual(len(details), 0 if restart else 1)
                        with factory() as session:
                            self.assertIsNotNone(complete_catalog(session, 21, 31))
                            self.assertIsNone(complete_catalog(session, 21, 1))
                    factory.kw['bind'].dispose()
                    factory = make_session_factory(database)

                # An expired catalog stays readable if a replacement fails or mixes snapshots.
                for mode in ('fail', 'mixed'):
                    httpx.get(f'{url}/control', params={'mode': mode}).raise_for_status()
                    with factory() as session:
                        row = session.get(CatalogCache, cache_key('complete', [21, 31]))
                        row.payload = {**row.payload, 'saved_at': '2000-01-01T00:00:00+00:00'}
                        session.commit()
                    app = FortyTwoTuiApp(factory, None)
                    async with app.run_test(size=(100, 35)) as pilot:
                        await pilot.pause()
                        app.account_connected = True
                        app.provider = provider
                        await app._refresh_catalog_context(provider, app.account_generation)
                        self.assertEqual(app.catalog_status, 'Catalog unavailable. Showing saved data.')
                        with factory() as session:
                            self.assertIsNone(complete_catalog(session, 21, 31))
                            saved = load_context_projects(session, 21, 31, '42')
                            self.assertEqual({p.official_project_id for p in saved}, {1, 2, 3, 4})
                            self.assertEqual({p.catalog_data['snapshot_id'] for p in saved}, {'11111111-1111-4111-8111-111111111111'})
            finally:
                client.close()
                factory.kw['bind'].dispose()
