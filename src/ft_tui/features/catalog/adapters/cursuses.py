"""Local cursus metadata. Catalog/progress snapshots live in catalog_cache."""
from sqlalchemy import select
from ft_tui.db.models import Cursus,UserConfig
from ft_tui.features.catalog.adapters.cache import load_context_projects,load_curriculum

def sync_cursuses(session,cursuses):
    for item in cursuses:
        row=session.get(Cursus,item.id)
        if row is None:
            row=Cursus(id=item.id,name=item.name);session.add(row)
        row.name=item.name;row.begin_at=item.begin_at;row.end_at=item.end_at
    session.commit()
    return list(session.scalars(select(Cursus).order_by(Cursus.id)))

def load_cursus_projects(session,cursus_id,account_id=None,campus_id=None):
    return load_context_projects(session,cursus_id,campus_id,account_id)

def load_project_curriculum(session,cursus_id,account_id=None,*,campus_id=None,allow_cached_owner=True):
    if account_id is None and allow_cached_owner:
        row=session.get(UserConfig,'catalog_last_account');account_id=row.value if row else None
    return load_curriculum(session,account_id,cursus_id,campus_id)
