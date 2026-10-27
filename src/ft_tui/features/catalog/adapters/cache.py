"""Persist only validated public projections; hydrate account state separately."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ft_tui.db.models import Project,Cursus,ProjectCursus,CatalogCache,UserProjectState,AccountCurriculumCache,UserConfig

def cache_key(category,context):
    return sha256(json.dumps([category,context],sort_keys=True).encode()).hexdigest()

def save_cache(session,category,cursus,campus,context,payload):
    key=cache_key(category,context)
    row=session.get(CatalogCache,key)
    if row is None:
        row=CatalogCache(key=key,cursus_id=cursus,campus_id=campus,category=category,payload=payload)
        session.add(row)
    else:
        row.payload=payload
    return row

def ensure_project(session,data,cursus):
    official=data['project_id']
    p=session.scalar(select(Project).where(Project.official_project_id==official))
    if p is None:
        p=Project(official_project_id=official,slug=data['slug'],name=data['name'],setup_status='unknown')
        session.add(p)
        session.flush()
    p.slug=data['slug'];p.name=data['name']
    if session.get(Cursus,cursus) is None:
        session.add(Cursus(id=cursus,name=str(cursus)));session.flush()
    if session.get(ProjectCursus,(p.id,cursus)) is None:
        session.add(ProjectCursus(project_id=p.id,cursus_id=cursus))
    return p

def apply_catalog_page(session,page,query=None,*,commit=True):
    meta=page['meta'];cursus=meta['cursus_id'];campus=meta['campus_id']
    for item in page['items']:
        ensure_project(session,item,cursus)
        save_cache(session,'project',cursus,campus,[cursus,campus,item['project_id']],{**item,'snapshot_id':page['snapshot_id']})
    save_cache(session,'page',cursus,campus,[cursus,campus,query or {}],page)
    save_cache(session,'active',cursus,campus,[cursus,campus],{'snapshot_id':page['snapshot_id'],**page.get('meta',{})})
    if commit:session.commit()

CATALOG_MAX_AGE_SECONDS = 24 * 60 * 60


def complete_catalog(session, cursus, campus):
    """Return a fresh, fully downloaded snapshot for this public scope."""
    row = session.get(CatalogCache, cache_key('complete', [cursus, campus]))
    active = session.get(CatalogCache, cache_key('active', [cursus, campus]))
    if not row or not active or row.payload.get('snapshot_id') != active.payload.get('snapshot_id'):
        return None
    try:
        saved = datetime.fromisoformat(row.payload['saved_at'])
        age = (datetime.now(timezone.utc) - saved).total_seconds()
    except (KeyError, TypeError, ValueError):
        return None
    return dict(row.payload) if 0 <= age < CATALOG_MAX_AGE_SECONDS else None


def load_project_detail(session, cursus, campus, official, snapshot=None):
    row = session.get(CatalogCache, cache_key('detail', [cursus, campus, official]))
    active = session.get(CatalogCache, cache_key('active', [cursus, campus]))
    expected = active.payload.get('snapshot_id') if active else snapshot
    if snapshot and expected != snapshot:
        return None
    if not row or not expected or row.payload.get('snapshot_id') != expected:
        return None
    return dict(row.payload)


def save_project_detail(session,detail,cursus,campus):
    active = session.get(CatalogCache, cache_key('active', [cursus, campus]))
    if active and active.payload.get('snapshot_id') != detail.get('snapshot_id'):
        return False
    ensure_project(session,detail,cursus)
    save_cache(session,'detail',cursus,campus,[cursus,campus,detail['project_id']],detail)
    save_cache(session,'project',cursus,campus,[cursus,campus,detail['project_id']],detail)
    session.commit()
    return True

def save_account_data(session,account,cursus,campus,curriculum,attempts):
    if curriculum.get('account_id')!=account or curriculum.get('cursus_id')!=cursus or curriculum.get('campus_id')!=campus:
        raise ValueError('Account curriculum context mismatch')
    meta=curriculum.get('sources',{}).get('projects',{})
    if meta.get('status')=='available' and meta.get('stale') is False:
        observed={a['project_id'] for a in attempts}
        for state in session.scalars(select(UserProjectState).where(UserProjectState.account_id==account)):
            if state.official_project_id not in observed and cursus in state.payload.get('cursus_ids',[]):
                remaining=[c for c in state.payload['cursus_ids'] if c!=cursus]
                if remaining:state.payload={**state.payload,'cursus_ids':remaining}
                else:session.delete(state)
        session.flush()
    for a in sorted(attempts,key=lambda a:a['id']):
        ensure_project(session,a,cursus)
        row=session.get(UserProjectState,(account,a['project_id']))
        if row is None:
            session.add(UserProjectState(account_id=account,official_project_id=a['project_id'],payload=a))
        else:
            row.payload=a
    key=(account,cursus,campus);row=session.get(AccountCurriculumCache,key)
    if row:
        # Unknown resolution can mean the catalog/quest refresh is still pending,
        # even when the raw API observations themselves are fresh. It must not
        # temporarily replace a known view for the same account/cursus/campus.
        incoming_track = curriculum.get('track', {})
        previous_track = row.payload.get('track', {})
        same_track = incoming_track.get('track') in (None, previous_track.get('track'))
        for field in ('rank', 'track'):
            incoming, previous = curriculum.get(field, {}), row.payload.get(field, {})
            if (incoming.get(field) is None and previous.get(field) is not None
                    and not incoming.get('conflict') and not incoming_track.get('conflict')
                    and (field == 'track' or same_track)):
                curriculum = {**curriculum, field: {**previous, 'stale': True}}
    if row is None:
        session.add(AccountCurriculumCache(account_id=account,cursus_id=cursus,campus_id=campus,payload={**curriculum,'_project_attempts':attempts}))
    else:
        row.payload={**curriculum,'_project_attempts':attempts}
    owner=session.get(UserConfig,'catalog_last_account')
    if owner is None:session.add(UserConfig(key='catalog_last_account',value=account))
    else:owner.value=account
    session.commit()

def load_curriculum(session,account,cursus,campus):
    row=session.get(AccountCurriculumCache,(account,cursus,campus)) if account and cursus and campus else None
    value=deepcopy(row.payload) if row else {}
    def dated(meta,seconds):
        try:
            at=datetime.fromisoformat(meta['collected_at'].replace('Z','+00:00'))
            expired=(datetime.now(timezone.utc)-at).total_seconds()>seconds
        except (KeyError,TypeError,ValueError,AttributeError):expired=True
        return {**meta,'stale':meta.get('stale',True) or meta.get('status')!='available' or expired}
    if 'registration' in value:value['registration']=dated(value['registration'],300)
    if 'sources' in value:value['sources']={name:dated(meta,300 if name=='registration' else 900) for name,meta in value['sources'].items()}
    return value

def load_context_projects(session,cursus,campus,account):
    q=select(Project).options(selectinload(Project.notes),selectinload(Project.time_logs))
    if cursus is not None:q=q.join(ProjectCursus).where(ProjectCursus.cursus_id==cursus)
    projects=list(session.scalars(q.order_by(Project.name)))
    scoped=session.get(AccountCurriculumCache,(account,cursus,campus)) if account and cursus and campus else None
    scoped_attempts=scoped.payload.get('_project_attempts') if scoped else None
    by_project={a['project_id']:a for a in sorted(scoped_attempts,key=lambda a:a['id'])} if scoped_attempts is not None else None
    # Hydrate the scope in bulk rather than issuing several SELECTs per project.
    rows = list(session.scalars(select(CatalogCache).where(
        CatalogCache.cursus_id == cursus, CatalogCache.campus_id == campus,
        CatalogCache.category.in_(['project', 'detail', 'active']),
    )))
    active = next((row.payload for row in rows if row.category == 'active'), {})
    metadata = {}
    for category in ('project', 'detail'):
        for row in rows:
            if row.category == category and (not active or row.payload.get('snapshot_id') == active.get('snapshot_id')):
                metadata.setdefault(row.payload['project_id'], {}).update(row.payload)
    states = {row.official_project_id: row.payload for row in session.scalars(
        select(UserProjectState).where(UserProjectState.account_id == account)
    )} if account and by_project is None else {}
    for p in projects:
        p._catalog_data = dict(metadata.get(p.official_project_id, {}))
        state = states.get(p.official_project_id, {})
        p._progress_data = (dict(by_project.get(p.official_project_id, {})) if by_project is not None else
                            dict(state) if cursus is None or cursus in state.get('cursus_ids', []) else {})
    curriculum=load_curriculum(session,account,cursus,campus)
    known={p.official_project_id for p in projects}
    for official in curriculum.get('registration',{}).get('project_ids',[]):
        if official not in known:
            # ID-only registration evidence is personal, never a shared membership.
            placeholder=Project(official_project_id=official,slug='',name=f'Project #{official}',setup_status='unknown')
            placeholder._catalog_data={};placeholder._progress_data={}
            projects.append(placeholder);known.add(official)
    return projects

def load_branches(session,cursus,campus,track):
    row=session.get(CatalogCache,cache_key('branches',[cursus,campus,track]))
    active=session.get(CatalogCache,cache_key('active',[cursus,campus]))
    if not row or active and active.payload.get('snapshot_id')!=row.payload.get('snapshot_id'):return []
    return list(row.payload.get('items',[]))
