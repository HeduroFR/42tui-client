"""Adapter-owned startup sessions and eagerly hydrated project projections."""
from sqlalchemy import select
from ft_tui.db.models import Cursus,UserConfig
from ft_tui.api.client_interface import CursusSnapshot
from ft_tui.features.catalog.adapters.cursuses import load_cursus_projects, load_project_curriculum
from ft_tui.features.catalog.adapters.cache import load_branches
from ft_tui.features.settings.adapters.storage import save_settings


class SqliteStartupRepository:
    def __init__(self,session_factory):self.session_factory=session_factory

    def preferences(self,keys):
        # Include existing empty values: first-run detection depends on presence.
        with self.session_factory() as session:
            return dict(session.execute(select(UserConfig.key,UserConfig.value).where(UserConfig.key.in_(keys))).all())

    def save(self,values):
        with self.session_factory() as session:save_settings(session,values)

    def cached_cursuses(self):
        with self.session_factory() as session:
            return tuple(CursusSnapshot(row.id,row.name,row.begin_at,row.end_at)
                         for row in session.scalars(select(Cursus).order_by(Cursus.id)))

    def catalog(self,cursus,account,campus,*,allow_cached_owner=True):
        with self.session_factory() as session:
            # The established catalog reader eagerly loads notes/time logs and
            # hydrates scoped catalog/progress before this session closes.
            projects=load_cursus_projects(session,cursus,account,campus)
            curriculum=load_project_curriculum(session,cursus,account,campus_id=campus,
                                               allow_cached_owner=allow_cached_owner)
            return projects,curriculum

    def branches(self,cursus,campus,track):
        with self.session_factory() as session:return load_branches(session,cursus,campus,track)
