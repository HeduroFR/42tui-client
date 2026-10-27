"""Catalog use cases run headlessly and never publish an incomplete/stale scan."""
import unittest
from ft_tui.features.catalog.models import CatalogScope
from ft_tui.features.catalog.service import CatalogService


class MemoryRepository:
    def __init__(self):
        self.complete = None
        self.published = []
        self.personal = []
        self.saved_branches = []
        self.saved_detail = []
        self.accept_detail = True
    def cached(self, scope): return self.complete
    def publish(self, scope, pages, snapshot, project_ids):
        self.published.append((snapshot, set(project_ids)))
        self.complete = {'snapshot_id': snapshot}
    def save_personal(self, account, scope, curriculum, attempts):
        self.personal.append((account, curriculum, attempts))
        return curriculum
    def save_branches(self, scope, track, value): self.saved_branches.append(value)
    def detail(self, scope, project_id, snapshot): return None
    def save_detail(self, scope, detail):
        if self.accept_detail: self.saved_detail.append(detail)
        return self.accept_detail
    def configured_cursus(self): return 21
    def preference(self, key): return None


class Provider:
    def __init__(self):
        self.calls = 0
        self.fail = False
        self.mixed = False
        self.repeated = False
        self.after_page = lambda: None
    def list_catalog_page(self, scope, **query):
        self.calls += 1
        self.after_page()
        if self.fail and query.get('cursor'): raise RuntimeError('page interrupted')
        return {'snapshot_id': 'other' if self.mixed and query.get('cursor') else 'graph',
                'items': [{'project_id': 2 if query.get('cursor') else 1}],
                'next_cursor': 'again' if not query.get('cursor') or self.repeated else None,
                'meta': {'cursus_id': 21, 'campus_id': 31}}
    def get_curriculum(self, scope): return {'account_id': '42'}
    def get_account_projects(self, cursus, cursor):
        return {'account_id': '42', 'snapshot_id': 'personal', 'items': [{'id': 7}], 'next_cursor': None}
    def get_catalog_project(self, project, scope, snapshot): return {'project_id': project, 'snapshot_id': snapshot}
    def list_branches(self, scope, track, cursor=None):
        return {'items': [{'branch_id': 'b'}], 'snapshot_id': 'graph', 'next_cursor': cursor}


class CatalogServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = MemoryRepository()
        self.service = CatalogService(self.repo)
        self.scope = CatalogScope(21, 31)
        self.provider = Provider()

    async def test_complete_scan_is_committed_once_after_all_tracks(self):
        result = await self.service.refresh_catalog(self.provider, self.scope, lambda: True)
        self.assertEqual(self.provider.calls, 6)
        self.assertEqual(self.repo.published, [('graph', {1, 2})])
        self.assertEqual(result.snapshot_id, 'graph')

    async def test_partial_mixed_and_repeated_pages_never_replace_saved_snapshot(self):
        for mode in ('fail', 'mixed', 'repeated'):
            self.repo.complete = {'snapshot_id': 'saved'}
            provider = Provider(); setattr(provider, mode, True)
            with self.subTest(mode=mode), self.assertRaises((RuntimeError, ValueError)):
                await self.service.refresh_catalog(provider, self.scope, lambda: True, force=True)
            self.assertEqual(self.repo.complete, {'snapshot_id': 'saved'})
            self.assertEqual(self.repo.published, [])

    async def test_account_change_during_network_read_discards_result_before_persistence(self):
        active = [True]
        self.provider.after_page = lambda: active.__setitem__(0, False)
        result = await self.service.refresh_catalog(self.provider, self.scope, lambda: active[0])
        self.assertIsNone(result)
        self.assertEqual(self.repo.published, [])

    async def test_saved_complete_catalog_reuses_storage_without_network(self):
        self.repo.complete = {'snapshot_id': 'saved'}
        result = await self.service.refresh_catalog(self.provider, self.scope, lambda: True)
        self.assertEqual(result.snapshot_id, 'saved')
        self.assertIsNone(result.meta)
        self.assertEqual(self.provider.calls, 0)

    async def test_wrong_personal_identity_and_repeated_attempts_are_rejected(self):
        self.provider.get_curriculum = lambda scope: {'account_id': 'another'}
        with self.assertRaises(ValueError):
            await self.service.refresh_account(self.provider, '42', self.scope, lambda: True)
        self.assertEqual(self.repo.personal, [])
        self.provider.get_curriculum = lambda scope: {'account_id': '42'}
        self.provider.get_account_projects = lambda *args: {'account_id': '42', 'snapshot_id': 'a', 'items': [{'id': 1}, {'id': 1}]}
        with self.assertRaises(ValueError):
            await self.service.refresh_account(self.provider, '42', self.scope, lambda: True)
        self.assertEqual(self.repo.personal, [])

    async def test_rejected_detail_and_stale_context_never_return_publishable_data(self):
        self.repo.accept_detail = False
        self.assertIsNone(await self.service.load_detail(self.provider, self.scope, 1, 'graph', lambda: True))
        self.assertEqual(self.repo.saved_detail, [])
        self.assertIsNone(await self.service.load_detail(self.provider, self.scope, 1, 'graph', lambda: False))

    async def test_branch_snapshot_change_is_rejected_before_storage(self):
        with self.assertRaises(ValueError):
            await self.service.load_branches(self.provider, self.scope, 'new', lambda: True,
                                             cursor='page', snapshot='previous', items=[])
        self.assertEqual(self.repo.saved_branches, [])
