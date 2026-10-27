"""Validate the read-only friend snapshot before persisting or displaying it."""
import math
import re
from datetime import datetime
from ft_tui.features.catalog.models import positive

# Preserve source spelling; consumers encode the login in URL paths/queries.
LOGIN = re.compile(r"(?!\.{1,2}\Z)(?=[\s\S]*\S)[^\x00-\x1f\x7f-\x9f]{1,100}")


def friend_snapshot(value, login, cursus_id, *, user_id=None):
    def fail():
        raise ValueError('Invalid friend snapshot')

    if isinstance(value, dict) and ('details_complete' in value or 'projects_loaded' in value):
        if value.get('details_complete') is not False or type(value.get('projects_loaded')) is not bool:
            fail()

    def text(item, limit=512):
        return isinstance(item, str) and len(item) <= limit

    def number(item):
        return item is None or type(item) in (int, float) and math.isfinite(item)

    def timestamp(item):
        if not isinstance(item, str):
            fail()
        try:
            parsed = datetime.fromisoformat(item.replace('Z', '+00:00'))
            if parsed.tzinfo is None:
                fail()
        except ValueError:
            fail()

    if not isinstance(value, dict) or value.get('cursus_id') != cursus_id:
        fail()
    if user_id is None and value.get('login') != login or not isinstance(value.get('login'), str) or not LOGIN.fullmatch(value['login']):
        fail()
    if user_id is not None and value.get('user_id') != user_id:
        fail()
    if not isinstance(value.get('user_id'), str) or not re.fullmatch(r'[1-9]\d*', value['user_id']):
        fail()
    if not text(value.get('display_name'), 1025) or not number(value.get('level')) or value.get('level') is not None and value['level'] < 0:
        fail()
    if value.get('grade') is not None and not text(value['grade']):
        fail()
    if value.get('main_cursus_id') is not None and not positive(value['main_cursus_id']):
        fail()
    if value.get('cursus_name') is not None and not text(value['cursus_name']):
        fail()
    for key in ('wallet', 'correction_point', 'achievements_count'):
        item = value.get(key)
        if item is not None and (type(item) is not int or item < 0):
            fail()
    for key in ('pool_month', 'pool_year'):
        if value.get(key) is not None and not text(value[key], 64):
            fail()
    titles = value.get('titles')
    xp = value.get('xp_progress')
    if xp is not None:
        if not isinstance(xp, dict) or any(type(xp.get(k)) is not int or xp[k] < 0 for k in ('total_xp', 'level_start_xp', 'next_level_xp')):
            fail()
        if not xp['level_start_xp'] <= xp['total_xp'] < xp['next_level_xp']:
            fail()
    if titles is not None and (not isinstance(titles, list) or len(titles) > 10000 or not all(text(title) and title for title in titles)):
        fail()
    coalitions = value.get('coalitions')
    if coalitions is not None:
        if not isinstance(coalitions, list) or len(coalitions) > 10000:
            fail()
        ids = set()
        for coalition in coalitions:
            if not isinstance(coalition, dict) or not positive(coalition.get('id')) or coalition['id'] in ids or not text(coalition.get('name')) or not coalition['name']:
                fail()
            ids.add(coalition['id'])
    campuses = value.get('campuses')
    if not isinstance(campuses, list) or len(campuses) > 100:
        fail()
    for campus in campuses:
        if not isinstance(campus, dict) or not positive(campus.get('id')) or not text(campus.get('name')) or type(campus.get('is_primary')) is not bool:
            fail()
    if value.get('location') is not None and not text(value['location'], 256):
        fail()
    presence = value.get('presence')
    if not isinstance(presence, dict) or presence.get('status') not in ('available', 'unavailable'):
        fail()
    if presence['status'] == 'available':
        timestamp(presence.get('cached_at'))
    elif value.get('location') is not None or presence.get('cached_at') is not None:
        fail()
    meta = value.get('meta')
    if not isinstance(meta, dict) or type(meta.get('stale')) is not bool or meta.get('cache') not in ('fresh', 'miss', 'stale'):
        fail()
    if meta['stale'] != (meta['cache'] == 'stale'):
        fail()
    timestamp(meta.get('cached_at'))
    items = value.get('items')
    if not isinstance(items, list) or len(items) > 10000:
        fail()
    seen = set()
    for item in items:
        if not isinstance(item, dict) or not positive(item.get('id')) or item['id'] in seen or not positive(item.get('project_id')):
            fail()
        seen.add(item['id'])
        if not text(item.get('slug'), 256) or not item['slug'] or not text(item.get('name')) or not item['name'] or not text(item.get('status'), 64) or not item['status']:
            fail()
        if not isinstance(item.get('cursus_ids'), list) or not all(positive(c) for c in item['cursus_ids']) or cursus_id not in item['cursus_ids']:
            fail()
        if item.get('validated') is not None and type(item['validated']) is not bool or not number(item.get('final_mark')):
            fail()
    rank = value.get('curriculum_rank')
    if rank is not None:
        if not isinstance(rank, dict) or rank.get('status') not in ('inferred', 'unknown', 'ambiguous', 'pending', 'unavailable', 'no_active_projects') or type(rank.get('stale')) is not bool:
            fail()
        ids = rank.get('project_ids')
        if not isinstance(ids, list) or len(ids) > 10000 or not all(positive(i) for i in ids) or len(set(ids)) != len(ids):
            fail()
        if rank.get('status') == 'inferred':
            if rank.get('track') not in ('old', 'new', 'shared') or rank.get('section') not in ('common-core', 'specialization') or not ids:
                fail()
            if rank['section'] == 'common-core' and (type(rank.get('rank')) is not int or rank['rank'] < 0):
                fail()
            if rank['section'] == 'specialization' and rank.get('rank') is not None:
                fail()
        elif any(rank.get(k) is not None for k in ('rank', 'track', 'section')):
            fail()
        latest = {}
        for item in items:
            if item['project_id'] not in latest or latest[item['project_id']]['id'] < item['id']:
                latest[item['project_id']] = item
        ongoing_ids = {item['project_id'] for item in latest.values() if item.get('validated') is not True and item['status'] in ('creating_group', 'searching_a_group', 'waiting_for_correction', 'waiting_to_start', 'in_progress')}
        evidence_ids = ongoing_ids
        if 'source' in rank:
            if rank['source'] != 'failed_attempt' or ongoing_ids:
                fail()
            evidence_ids = {item['project_id'] for item in latest.values() if item.get('validated') is False and item['status'] == 'finished'}
            if not evidence_ids:
                fail()
        if set(ids) != evidence_ids or value.get('projects_loaded') is not False and (rank['status'] == 'no_active_projects') != (not evidence_ids):
            fail()
    return value


def friend_directory_page(value, campus_id, page):
    """Validate candidate identities and bounded pagination independently of profiles."""
    def invalid():
        raise ValueError('Invalid friend directory page')
    if not isinstance(value, dict) or type(value.get('campus_id')) is not int or type(value.get('page')) is not int or value.get('campus_id') != campus_id or value.get('page') != page:
        invalid()
    items, next_page = value.get('items'), value.get('next_page')
    if 'next_page' not in value or not isinstance(items, list) or len(items) > 100 or type(value.get('truncated')) is not bool:
        invalid()
    more = len(items) > 0
    if next_page != (page + 1 if more and page < 100 else None) or next_page is not None and type(next_page) is not int:
        invalid()
    if value['truncated'] != (more and page == 100):
        invalid()
    ids, logins = set(), set()
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get('user_id'), str) or not re.fullmatch(r'[1-9]\d*', item['user_id']):
            invalid()
        if not isinstance(item.get('login'), str) or not LOGIN.fullmatch(item['login']):
            invalid()
        if item['user_id'] in ids or item['login'] in logins or not isinstance(item.get('display_name'), str) or len(item['display_name']) > 1025:
            invalid()
        ids.add(item['user_id']); logins.add(item['login'])
    meta = value.get('meta')
    if not isinstance(meta, dict) or type(meta.get('stale')) is not bool or meta.get('cache') not in ('fresh', 'miss', 'stale'):
        invalid()
    if meta['stale'] != (meta['cache'] == 'stale'):
        invalid()
    try:
        if not isinstance(meta.get('cached_at'), str) or datetime.fromisoformat(meta['cached_at'].replace('Z', '+00:00')).tzinfo is None:
            invalid()
    except ValueError:
        invalid()
    return value


def student_search_result(value, limit=20):
    """Validate database-backed search results without a downloaded directory."""
    def invalid():
        raise ValueError('Invalid student search response')
    if not isinstance(value, dict) or not isinstance(value.get('items'), list) or len(value['items']) > limit:
        invalid()
    ids, logins = set(), set()
    for item in value['items']:
        if not isinstance(item, dict) or not isinstance(item.get('user_id'), str) or not re.fullmatch(r'[1-9]\d*', item['user_id']):
            invalid()
        if not isinstance(item.get('login'), str) or not LOGIN.fullmatch(item['login']) or not isinstance(item.get('display_name'), str) or len(item['display_name']) > 1025:
            invalid()
        if item['user_id'] in ids or item['login'] in logins:
            invalid()
        ids.add(item['user_id']); logins.add(item['login'])
    index = value.get('index')
    if not isinstance(index, dict) or 'updated_at' not in index or index.get('status') not in ('building', 'ready') or type(index.get('count')) is not int or index['count'] < 0 or type(index.get('stale')) is not bool:
        invalid()
    if index.get('updated_at') is not None:
        try:
            if not isinstance(index['updated_at'], str) or datetime.fromisoformat(index['updated_at'].replace('Z', '+00:00')).tzinfo is None:
                invalid()
        except ValueError:
            invalid()
    return value
