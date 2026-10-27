from copy import deepcopy
from datetime import datetime, timezone


def attempt(project_id=1001, *, id=1, name='minishell', status='in_progress', validated=None, mark=None):
    return {'id': id, 'project_id': project_id, 'name': name, 'slug': name.lower(),
            'cursus_ids': [21], 'status': status, 'validated': validated, 'final_mark': mark}


def snapshot(login='alice', *, user_id='50', level=8.42, items=None, cursus_id=21):
    now = datetime.now(timezone.utc).isoformat()
    return {'user_id': user_id, 'login': login, 'display_name': '[red]Literal name', 'cursus_id': cursus_id,
            'level': level, 'grade': 'Learner', 'campuses': [{'id': 31, 'name': 'Paris', 'is_primary': True}],
            'location': 'e2r5p3', 'presence': {'status': 'available', 'cached_at': now},
            'items': deepcopy(items if items is not None else [attempt()]),
            'meta': {'cache': 'fresh', 'stale': False, 'cached_at': now}}


def directory_page(items=None, *, campus_id=31, page=1):
    items = items or []
    return {'campus_id': campus_id, 'page': page, 'items': items,
            'next_page': page + 1 if items and page < 100 else None,
            'truncated': bool(items) and page == 100,
            'meta': {'cache': 'fresh', 'stale': False, 'cached_at': datetime.now(timezone.utc).isoformat()}}


def curriculum_rank(rank, track='shared', project_ids=(1001,), section='common-core', stale=False):
    return {'status': 'inferred', 'rank': rank, 'track': track, 'section': section,
            'project_ids': list(project_ids), 'stale': stale}
