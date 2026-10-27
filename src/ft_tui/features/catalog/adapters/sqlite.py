"""Own session lifetimes and atomic publication of validated catalog snapshots."""
from datetime import datetime, timezone
from ft_tui.features.settings.adapters.storage import get_setting
from .cache import (apply_catalog_page, save_account_data, load_curriculum,
                    complete_catalog, save_cache, load_project_detail, save_project_detail)


class SqliteCatalogRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def configured_cursus(self):
        value = self.preference('default_cursus_id')
        try:
            parsed = int(value) if value else None
        except ValueError:
            return None
        return parsed if parsed and parsed > 0 else None

    def preference(self, key):
        with self.session_factory() as session:
            return get_setting(session, key)

    def save_personal(self, account, scope, curriculum, attempts):
        with self.session_factory() as session:
            save_account_data(session, account, scope.cursus_id, scope.campus_id, curriculum, attempts)
            return load_curriculum(session, account, scope.cursus_id, scope.campus_id)

    def cached(self, scope):
        with self.session_factory() as session:
            return complete_catalog(session, scope.cursus_id, scope.campus_id)

    def save_branches(self, scope, track, page):
        with self.session_factory() as session:
            save_cache(session, 'branches', scope.cursus_id, scope.campus_id,
                       [scope.cursus_id, scope.campus_id, track], page)
            session.commit()

    def publish(self, scope, pages, snapshot, project_ids):
        with self.session_factory() as session:
            for page, query in pages:
                apply_catalog_page(session, page, query, commit=False)
            save_cache(session, 'complete', scope.cursus_id, scope.campus_id,
                       [scope.cursus_id, scope.campus_id], {
                           'snapshot_id': snapshot, 'saved_at': datetime.now(timezone.utc).isoformat(),
                           'project_ids': sorted(project_ids),
                       })
            session.commit()

    def detail(self, scope, project_id, snapshot):
        with self.session_factory() as session:
            return load_project_detail(session, scope.cursus_id, scope.campus_id, project_id, snapshot)

    def save_detail(self, scope, detail):
        with self.session_factory() as session:
            return save_project_detail(session, detail, scope.cursus_id, scope.campus_id)
