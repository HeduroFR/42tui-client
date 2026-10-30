"""Validated, account-scoped agenda snapshots."""
from datetime import datetime
from urllib.parse import urlparse

def snapshot(value, account_id, kind):
    if not isinstance(value, dict) or value.get('account_id') != str(account_id) or not isinstance(value.get('items'), list) or len(value['items']) > 3000:
        raise ValueError('Invalid agenda account or snapshot')
    seen = set()
    for row in value['items']:
        if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] < 1 or row['id'] in seen or row.get('kind') != kind:
            raise ValueError('Invalid agenda identity')
        seen.add(row['id'])
        for key in ('title', 'description', 'counterpart'):
            if not isinstance(row.get(key), str) or len(row[key]) > 1048576:
                raise ValueError('Invalid agenda text')
        begin = datetime.fromisoformat(row['begin_at'])
        if begin.tzinfo is None:
            raise ValueError('Missing agenda timezone')
        if row.get('end_at') is not None:
            end = datetime.fromisoformat(row['end_at'])
            if end.tzinfo is None or end <= begin:
                raise ValueError('Invalid agenda interval')
        if row.get('url') is not None:
            url = urlparse(row['url'])
            if url.scheme != 'https' or url.netloc not in {'profile.intra.42.fr', 'projects.intra.42.fr'} or url.query or url.fragment:
                raise ValueError('Invalid agenda link')
    return value['items']
