"""Headless catalog synchronization with explicit context and storage boundaries."""
import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from .models import CatalogScope
from .ports import CatalogReader, CatalogRepository
from .preferences import preference_key, select_track, select_rank

Current = Callable[[], bool]


@dataclass(frozen=True)
class CatalogSnapshot:
    snapshot_id: str
    meta: dict | None = None


class CatalogService:
    def __init__(self, repository: CatalogRepository):
        self.repository = repository

    def configured_cursus(self):
        return self.repository.configured_cursus()

    def scope(self, account: str | None, campuses: Sequence[dict]) -> CatalogScope | None:
        cursus = self.repository.configured_cursus()
        campus = self.repository.preference(preference_key(account, cursus, None, 'campus'))
        try:
            campus = int(campus)
        except (TypeError, ValueError):
            fallback = campuses[0]['id'] if campuses else None
            campus = next((c['id'] for c in campuses if c.get('is_primary')), fallback)
        return CatalogScope(cursus, campus) if cursus and campus and campus > 0 else None

    def resolve(self, curriculum: dict, account: str | None, scope: CatalogScope | None) -> dict:
        if not scope:
            return dict(curriculum)
        preference = self.repository.preference(preference_key(account, scope.cursus_id, scope.campus_id, 'track'))
        return {**curriculum, 'selected_track': select_track(curriculum.get('track', {}), preference),
                'selected_rank': select_rank(curriculum.get('rank', {}))}

    def cached(self, scope: CatalogScope):
        return self.repository.cached(scope)

    async def refresh_account(self, provider: CatalogReader, account: str, scope: CatalogScope, current: Current):
        if not current():
            return None
        curriculum = await asyncio.to_thread(provider.get_curriculum, scope)
        if not current():
            return None
        if curriculum.get('account_id') != account:
            raise ValueError('Account identity changed')
        attempts, cursor, seen, snapshot, attempt_ids = [], None, set(), None, set()
        for _ in range(100):
            page = await asyncio.to_thread(provider.get_account_projects, scope.cursus_id, cursor)
            if not current():
                return None
            if page.get('account_id') != account or snapshot and page.get('snapshot_id') != snapshot:
                raise ValueError('Personal snapshot changed')
            ids = [item['id'] for item in page['items']]
            if len(set(ids)) != len(ids) or attempt_ids.intersection(ids):
                raise ValueError('Repeated personal attempt')
            attempt_ids.update(ids)
            snapshot = page['snapshot_id']
            attempts.extend(page['items'])
            cursor = page.get('next_cursor')
            if not cursor:
                break
            if cursor in seen:
                raise ValueError('Repeated personal cursor')
            seen.add(cursor)
        else:
            raise ValueError('Personal scan limit')
        return self.repository.save_personal(account, scope, curriculum, attempts)

    async def refresh_catalog(self, provider: CatalogReader, scope: CatalogScope, current: Current, *, force=False):
        if not current():
            return None
        cached = self.repository.cached(scope)
        if cached and not force:
            return CatalogSnapshot(cached['snapshot_id'])
        staged, project_ids, snapshot = [], set(), None
        # Shared projects overlap between tracks, but duplicates within a scan do not.
        for filters in ({'track': 'old'}, {'track': 'new'}, {'section': 'other'}):
            cursor, seen, scan_ids = None, set(), set()
            for _ in range(1000):
                query = {**filters, 'limit': 100, 'cursor': cursor}
                page = await asyncio.to_thread(provider.list_catalog_page, scope, **query)
                if not current():
                    return None
                if snapshot and page['snapshot_id'] != snapshot:
                    raise ValueError('Catalog snapshot changed')
                ids = {item['project_id'] for item in page['items']}
                if len(ids) != len(page['items']) or scan_ids.intersection(ids):
                    raise ValueError('Repeated catalog project')
                scan_ids.update(ids)
                project_ids.update(ids)
                snapshot = page['snapshot_id']
                staged.append((page, query))
                cursor = page.get('next_cursor')
                if not cursor:
                    break
                if cursor in seen:
                    raise ValueError('Repeated catalog cursor')
                seen.add(cursor)
            else:
                raise ValueError('Catalog scan limit')
        self.repository.publish(scope, staged, snapshot, project_ids)
        return CatalogSnapshot(snapshot, staged[-1][0]['meta'])

    async def load_branches(self, provider: CatalogReader, scope: CatalogScope, track: str, current: Current,
                            *, cursor=None, snapshot=None, items=()):
        if not current():
            return None
        args = (scope, track, cursor) if cursor else (scope, track)
        page = await asyncio.to_thread(provider.list_branches, *args)
        if not current():
            return None
        if cursor and (page['snapshot_id'] != snapshot or page.get('next_cursor') == cursor):
            raise ValueError('Branch snapshot or cursor changed')
        merged = {**page, 'items': list(items) + page['items']} if cursor else page
        self.repository.save_branches(scope, track, merged)
        return merged

    async def load_detail(self, provider: CatalogReader, scope: CatalogScope, project_id: int,
                          snapshot: str | None, current: Current):
        if not current():
            return None
        detail = self.repository.detail(scope, project_id, snapshot)
        if detail is not None:
            return detail
        await asyncio.sleep(.15)
        if not current():
            return None
        detail = await asyncio.to_thread(provider.get_catalog_project, project_id, scope, snapshot)
        if not current() or not self.repository.save_detail(scope, detail):
            return None
        return detail
