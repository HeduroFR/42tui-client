"""Controller checks for complete, persistent catalogs without a network server."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from sqlalchemy import event

from ft_tui.api.catalog_types import CatalogScope
from ft_tui.app.bootstrap import build_catalog_service
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import CatalogCache
from ft_tui.services.catalog_cache import (
    apply_catalog_page, cache_key, complete_catalog, load_context_projects, save_project_detail,
)
from ft_tui.ui.project_catalog_controller import ProjectCatalogControllerMixin
from tests.test_ui_project_rank import RankProvider


class Controller(ProjectCatalogControllerMixin):
    def __init__(self, factory, provider):
        self.session_factory = factory
        self.catalog_service = build_catalog_service(factory)
        self.provider = provider
        self.account_id = '42'
        self.account_generation = 0
        self._catalog_generation = 0
        self.selected_project_key = None
        self.projects = {}
        self.project_curriculum = {}
        self.rendered = None

    def _catalog_scope(self):
        return CatalogScope(21, 31)

    def _resolved_curriculum(self, value):
        return {**value, 'selected_track': {'track': 'new'}}

    def _set_branch_options(self, items):
        pass

    def query_one(self, *args):
        return SimpleNamespace(disabled=False)

    async def _reload_project_catalog(self):
        with self.session_factory() as session:
            self.projects = {p.ui_key: p for p in load_context_projects(session, 21, 31, self.account_id)}

    def _render_project_details(self, project):
        self.rendered = project.catalog_data


class PagedProvider(RankProvider):
    def __init__(self):
        super().__init__()
        self.failure = None
        self.detail_calls = 0
        self.after_page = None

    def list_catalog_page(self, scope, **query):
        if self.after_page:
            self.after_page()
        page = super().list_catalog_page(scope, **query)
        offset = int(query.get('cursor') or 0)
        if offset and self.failure == 'error':
            raise RuntimeError('interrupted download')
        if offset and self.failure == 'snapshot':
            page['snapshot_id'] = 'different'
        page['items'] = page['items'][offset:offset + 1]
        page['next_cursor'] = str(offset + 1) if offset + 1 < len(super_rows(self, query)) else None
        if offset and self.failure == 'cursor':
            page['next_cursor'] = query['cursor']
        return page

    def get_catalog_project(self, *args):
        self.detail_calls += 1
        return super().get_catalog_project(*args)


def super_rows(provider, query):
    return [row for row in provider.rows
            if (not query.get('track') or row['track'] in (query['track'], 'shared'))
            and (not query.get('section') or row['section'] == query['section'])]


class CatalogCacheControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_campus_graph_retries_automatically_and_discards_a_retry_after_account_change(self):
        import httpx
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "pending.db"}')
            try:
                provider = PagedProvider()
                original = provider.list_catalog_page

                def pending(*args, **kwargs):
                    response = httpx.Response(503, json={'error': 'catalog_pending'},
                                              request=httpx.Request('GET', 'https://example.test/v1/catalog/projects'))
                    raise httpx.HTTPStatusError('catalog_pending', request=response.request, response=response)

                provider.list_catalog_page = pending
                controller = Controller(factory, provider)
                timers, workers = [], []
                controller.set_timer = lambda delay, callback: timers.append((delay, callback))
                controller.run_worker = lambda operation, **kwargs: workers.append(operation)
                await controller._refresh_catalog_context(provider, 0)
                self.assertEqual(controller.catalog_status, 'Loading campus graph…')
                self.assertEqual(timers[0][0], 30)
                with factory() as session:
                    self.assertIsNone(complete_catalog(session, 21, 31))
                timers[0][1]()
                self.assertEqual(len(workers), 1)
                provider.list_catalog_page = original
                await workers[0]()
                self.assertEqual(len(controller.projects), len(provider.rows))
                workers.clear()
                controller.account_generation += 1
                timers[0][1]()
                self.assertEqual(workers, [])
            finally:
                factory.kw['bind'].dispose()

    async def test_restart_reuses_all_pages_and_details(self):
        with TemporaryDirectory() as directory:
            database = f'sqlite:///{Path(directory) / "cache.db"}'
            provider = PagedProvider()
            for restart in (False, True):
                factory = make_session_factory(database)
                try:
                    provider.queries.clear()
                    controller = Controller(factory, provider)
                    await controller._refresh_catalog_context(provider, 0)
                    self.assertEqual(len(controller.projects), len(provider.rows))
                    self.assertEqual(bool(provider.queries), not restart)
                    controller.selected_project_key = '3'
                    await controller._load_selected_catalog_detail(controller.projects['3'])
                    await controller._reload_project_catalog()
                    await controller._load_selected_catalog_detail(controller.projects['3'])
                    self.assertEqual(provider.detail_calls, 1)
                    self.assertIn('description', controller.rendered)
                    with factory() as session:
                        self.assertIsNotNone(complete_catalog(session, 21, 31))
                        self.assertIsNone(complete_catalog(session, 21, 1))
                        # Summary refreshes preserve richer details in the same snapshot.
                        apply_catalog_page(session, {'snapshot_id': 'graph', 'items': [provider.rows[2]],
                                                     'meta': {'cursus_id': 21, 'campus_id': 31}})
                        self.assertIn('description', next(p for p in load_context_projects(session,21,31,'42')
                                                         if p.official_project_id == 3).catalog_data)
                finally:
                    factory.kw['bind'].dispose()

    async def test_forced_refresh_updates_ranks_despite_a_fresh_local_catalog(self):
        factory = make_session_factory('sqlite:///:memory:')
        try:
            provider = PagedProvider()
            provider.rows = [dict(row) for row in provider.rows]
            controller = Controller(factory, provider)
            await controller._refresh_catalog_context(provider, 0)
            corrected = provider.rows[0]
            previous_rank = corrected['rank']
            corrected['rank'] = 2 if previous_rank != 2 else 3
            provider.queries.clear()
            await controller._refresh_catalog_context(provider, 0)
            self.assertFalse(provider.queries)
            cached = next(p for p in controller.projects.values()
                          if p.official_project_id == corrected['project_id'])
            self.assertEqual(cached.catalog_data['rank'], previous_rank)
            await controller._refresh_catalog_context(provider, 0, force=True)
            self.assertTrue(provider.queries)
            refreshed = next(p for p in controller.projects.values()
                             if p.official_project_id == corrected['project_id'])
            self.assertEqual(refreshed.catalog_data['rank'], corrected['rank'])
            provider.failure = 'error'
            await controller._refresh_catalog_context(provider, 0, force=True)
            self.assertEqual(controller.catalog_status, 'Catalog unavailable. Showing saved data.')
            preserved = next(p for p in controller.projects.values()
                             if p.official_project_id == corrected['project_id'])
            self.assertEqual(preserved.catalog_data['rank'], corrected['rank'])
            with factory() as session:
                self.assertIsNotNone(complete_catalog(session, 21, 31))
        finally:
            factory.kw['bind'].dispose()

    async def test_failed_scans_preserve_the_previous_snapshot(self):
        factory = make_session_factory('sqlite:///:memory:')
        try:
            provider = PagedProvider()
            controller = Controller(factory, provider)
            await controller._refresh_catalog_context(provider, 0)
            for failure in ('error', 'snapshot', 'cursor'):
                with self.subTest(failure=failure):
                    with factory() as session:
                        row = session.get(CatalogCache, cache_key('complete', [21, 31]))
                        row.payload = {**row.payload, 'saved_at': '2000-01-01T00:00:00+00:00'}
                        session.commit()
                    provider.failure = failure
                    await controller._refresh_catalog_context(provider, 0)
                    self.assertEqual(controller.catalog_status, 'Catalog unavailable. Showing saved data.')
                    with factory() as session:
                        self.assertIsNone(complete_catalog(session, 21, 31))
                        self.assertEqual({p.catalog_data['snapshot_id'] for p in load_context_projects(session,21,31,'42')}, {'graph'})
        finally:
            factory.kw['bind'].dispose()

    async def test_detail_from_a_replaced_snapshot_cannot_overwrite_the_new_catalog(self):
        factory = make_session_factory('sqlite:///:memory:')
        try:
            item = RankProvider.rows[0]
            with factory() as session:
                apply_catalog_page(session, {'snapshot_id': 'new', 'items': [item],
                                             'meta': {'cursus_id': 21, 'campus_id': 31}})
                self.assertFalse(save_project_detail(session, {**item, 'snapshot_id': 'old'}, 21, 31))
                self.assertEqual(load_context_projects(session, 21, 31, None)[0].catalog_data['snapshot_id'], 'new')
        finally:
            factory.kw['bind'].dispose()

    async def test_account_switch_discards_inflight_catalog_pages(self):
        factory = make_session_factory('sqlite:///:memory:')
        try:
            provider = PagedProvider()
            controller = Controller(factory, provider)
            provider.after_page = lambda: setattr(controller, 'account_generation', 1)
            await controller._refresh_catalog_context(provider, 0)
            with factory() as session:
                self.assertIsNone(complete_catalog(session, 21, 31))
                self.assertFalse(list(session.query(CatalogCache).filter_by(category='project')))
        finally:
            factory.kw['bind'].dispose()

    async def test_hydration_query_count_does_not_grow_with_project_count(self):
        factory = make_session_factory('sqlite:///:memory:')
        engine = factory.kw['bind']
        try:
            with factory() as session:
                items = [{'project_id': n, 'slug': f'p{n}', 'name': f'P{n}', 'track': 'new'} for n in range(1, 101)]
                apply_catalog_page(session, {'snapshot_id': 'graph', 'items': items,
                                             'meta': {'cursus_id': 21, 'campus_id': 31}})
            calls = []
            def record(*args):
                calls.append(args[2])
            event.listen(engine, 'before_cursor_execute', record)
            with factory() as session:
                projects = load_context_projects(session, 21, 31, '42')
            self.assertEqual(len(projects), 100)
            self.assertLessEqual(len(calls), 8)
        finally:
            engine.dispose()
