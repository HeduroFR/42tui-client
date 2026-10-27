"""Validate the authenticated cluster snapshot before UI consumption."""
from datetime import datetime
import re
from ft_tui.features.cluster_map.geometry import positions


def _meta(value):
    if not isinstance(value,dict) or type(value.get('stale')) is not bool:
        raise ValueError('Invalid cluster freshness')
    stamp = datetime.fromisoformat(value['cached_at'].replace('Z','+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Invalid cluster freshness')


def cluster_portrait(value: object, hostname: str) -> dict:
    if not isinstance(value,dict) or value.get('hostname')!=hostname or value.get('status') not in ('ready','pending','unavailable'):
        raise ValueError('Invalid cluster portrait')
    source=value.get('image_url');image=value.get('image_base64')
    if source is not None and (not isinstance(source,str) or len(source)>2048):raise ValueError('Invalid cluster portrait')
    if value['status']=='ready':
        if not source or not isinstance(image,str) or not 0<len(image)<=699052:raise ValueError('Invalid cluster portrait')
    elif image is not None:raise ValueError('Invalid cluster portrait')
    _meta(value.get('meta'))
    return value


def cluster_map_snapshot(value: object) -> dict:
    def fail(): raise ValueError('Invalid cluster snapshot')
    if not isinstance(value,dict) or type(value.get('campus_id')) is not int or not isinstance(value.get('machines'),list) or len(value['machines'])>2000:
        fail()
    seen=set()
    for row in value['machines']:
        if not isinstance(row,dict):fail()
        host=row.get('hostname')
        if not isinstance(host,str) or not re.fullmatch(r'[a-zA-Z0-9.-]{1,253}\.42angouleme\.fr',host) or host.lower() in seen:fail()
        seen.add(host.lower())
        if not isinstance(row.get('status'),str) or row.get('is_locked') is not None and type(row['is_locked']) is not bool:fail()
        for key in ('login','exam_user','lock_time'):
            if row.get(key) is not None and (not isinstance(row[key],str) or len(row[key])>128 or any(ord(c)<32 for c in row[key])):fail()
        person=row.get('person')
        if person is not None and (not isinstance(person,dict) or person.get('login')!=row.get('login')):fail()
        if person:
            for key,limit in (('display_name',513),('image_url',2048),('user_id',16)):
                if person.get(key) is not None and (not isinstance(person[key],str) or len(person[key])>limit):fail()
        issues=row.get('issues')
        if issues is not None:
            if not isinstance(issues,dict) or issues.get('availability') not in ('available','unavailable'):fail()
            count=issues.get('open_count')
            if issues['availability']=='available' and (type(count) is not int or not 0<=count<=10000):fail()
            if issues['availability']=='unavailable' and count is not None:fail()
        if row.get('storage') is not None and (not isinstance(row['storage'],dict) or any(v is not None and not isinstance(v,str) for v in row['storage'].values())):fail()
    try:_meta(value.get('meta'))
    except (KeyError,TypeError,AttributeError,ValueError):fail()
    return value


def cluster_issue_page(value: object, hostname: str, include_resolved: bool) -> dict:
    def fail():raise ValueError('Invalid cluster reports')
    if not isinstance(value,dict) or value.get('hostname')!=hostname or value.get('include_resolved') is not include_resolved:fail()
    if not isinstance(value.get('items'),list) or len(value['items'])>50:fail()
    cursor=value.get('next_cursor')
    if cursor is not None and (not isinstance(cursor,str) or not re.fullmatch(r'[1-9]\d{0,2}',cursor) or int(cursor)>200):fail()
    seen=set()
    for item in value['items']:
        if not isinstance(item,dict) or not isinstance(item.get('id'),str) or item['id'] in seen or item.get('hostname')!=hostname:fail()
        seen.add(item['id'])
        if item.get('status') not in (('open','in_progress','resolved') if include_resolved else ('open','in_progress')):fail()
        for field in ('title','description'):
            if not isinstance(item.get(field),str) or len(item[field])>20000:fail()
        if not isinstance(item.get('history'),list) or len(item['history'])>200:fail()
        for entry in item['history']:
            if not isinstance(entry,dict) or not isinstance(entry.get('content'),str) or len(entry['content'])>20000:fail()
    try:_meta(value.get('meta'))
    except (KeyError,TypeError,AttributeError,ValueError):fail()
    return value
