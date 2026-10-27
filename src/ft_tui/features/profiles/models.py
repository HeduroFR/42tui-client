"""Validate the on-demand profile projection independently of Friends sync."""
import math
import re
from datetime import date, datetime
from urllib.parse import urlsplit

from ft_tui.features.catalog.models import positive
from ft_tui.features.friends.models import LOGIN
from ft_tui.features.profiles.goals import goals_response


def _fail():
    raise ValueError('Invalid student profile response')


def _text(value, limit=512):
    return isinstance(value, str) and len(value) <= limit


def _stamp(value):
    try:
        if not isinstance(value, str) or datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is None:
            _fail()
    except (ValueError, TypeError):
        _fail()


def _day(value):
    try:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            _fail()
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        _fail()


def student_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9]\d{0,15}', value) or int(value) > 9007199254740991:
        _fail()
    return value


def portrait_url(value):
    if not _text(value, 4096):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == 'https' and url.hostname == 'cdn.intra.42.fr'
                and not url.username and not url.password and url.port in (None, 443))
    except ValueError:
        return False


def student_portrait(value, user_id):
    student_id(user_id)
    if (not isinstance(value, dict) or value.get('user_id') != user_id
            or value.get('status') not in ('ready', 'pending', 'unavailable')):
        raise ValueError('Invalid student portrait')
    url, encoded = value.get('image_url'), value.get('image_base64')
    if url is not None and not portrait_url(url):
        raise ValueError('Invalid student portrait')
    if value['status'] == 'ready':
        if not url or not isinstance(encoded, str) or not 0 < len(encoded) <= 699052:
            raise ValueError('Invalid student portrait')
    elif encoded is not None:
        raise ValueError('Invalid student portrait')
    return value


def student_profile(value, user_id):
    student_id(user_id)
    if not isinstance(value, dict) or value.get('user_id') != user_id:
        _fail()
    if not isinstance(value.get('login'), str) or not LOGIN.fullmatch(value['login']) or not _text(value.get('display_name'), 1025):
        _fail()
    for key in ('email', 'pool_month', 'pool_year'):
        if value.get(key) is not None and not _text(value[key]):
            _fail()
    if value.get('image_url') is not None and not portrait_url(value['image_url']):
        _fail()
    for key in ('wallet', 'correction_point', 'achievements_count'):
        if value.get(key) is not None and (type(value[key]) is not int or value[key] < 0):
            _fail()
    memberships = value.get('cursus_users')
    if not isinstance(memberships, list) or len(memberships) > 1000:
        _fail()
    ids = set()
    for item in memberships:
        if not isinstance(item, dict) or not positive(item.get('cursus_id')) or item['cursus_id'] in ids or not _text(item.get('name')):
            _fail()
        ids.add(item['cursus_id'])
        if item.get('grade') is not None and not _text(item['grade']):
            _fail()
        level = item.get('level')
        if level is not None and (type(level) not in (float, int) or not math.isfinite(level) or level < 0):
            _fail()
        if item.get('slug') is not None and (not isinstance(item['slug'], str) or not re.fullmatch(r'[-a-z0-9]{1,128}', item['slug'])):
            _fail()
    if value.get('main_cursus_id') is not None and value['main_cursus_id'] not in ids:
        _fail()
    for key in ('campuses', 'coalitions', 'achievements'):
        items = value.get(key)
        if items is None and key != 'campuses':
            continue
        if not isinstance(items, list) or len(items) > 10000:
            _fail()
        seen = set()
        for item in items:
            if not isinstance(item, dict) or not positive(item.get('id')) or item['id'] in seen or not _text(item.get('name')):
                _fail()
            seen.add(item['id'])
            if key == 'campuses' and type(item.get('is_primary')) is not bool:
                _fail()
            if key == 'achievements':
                for field, limit in (('description', 8192), ('tier', 64)):
                    if item.get(field) is not None and not _text(item[field], limit):
                        _fail()
    titles = value.get('titles')
    if titles is not None and (not isinstance(titles, list) or len(titles) > 10000 or any(not _text(t) for t in titles)):
        _fail()
    meta = value.get('meta')
    if not isinstance(meta, dict) or meta.get('cache') not in ('fresh', 'miss', 'stale') or type(meta.get('stale')) is not bool or meta['stale'] != (meta['cache'] == 'stale'):
        _fail()
    _stamp(meta.get('cached_at'))
    return value


def student_attendance(value, user_id):
    if not isinstance(value, dict) or value.get('user_id') != student_id(user_id):
        _fail()
    begin, end = _day(value.get('begin')), _day(value.get('end'))
    if not 0 <= (end - begin).days <= 124 or value.get('status') not in ('available', 'unavailable') or type(value.get('stale')) is not bool:
        _fail()
    if value.get('collected_at') is not None:
        _stamp(value['collected_at'])
    if value['status'] == 'available':
        _stamp(value.get('collected_at'))
        days = value.get('days')
        if not isinstance(days, dict) or len(days) > 125:
            _fail()
        for key, seconds in days.items():
            if not begin <= _day(key) <= end or type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 <= seconds <= 86400:
                _fail()
    if value.get('retry_after') is not None and (type(value['retry_after']) is not int or not 1 <= value['retry_after'] <= 86400):
        _fail()
    return value


def student_goals(value, user_id, cursus_id):
    if not isinstance(value, dict) or value.get('user_id') != student_id(user_id):
        _fail()
    goals_response({**value, 'account_id': user_id}, user_id, cursus_id)
    return value
