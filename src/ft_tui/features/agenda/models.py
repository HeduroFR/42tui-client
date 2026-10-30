"""Validated, account-scoped agenda snapshots."""
from datetime import datetime
from urllib.parse import urlparse
from ft_tui.features.corrections.model import Slot

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
        if kind == 'available':
            if row.get('end_at') is None:
                raise ValueError('Missing slot end')
            Slot((str(row['id']),), begin, end)
        if row.get('url') is not None:
            url = urlparse(row['url'])
            if url.scheme != 'https' or url.netloc not in {'profile.intra.42.fr', 'projects.intra.42.fr'} or url.query or url.fragment:
                raise ValueError('Invalid agenda link')
    return value['items']


def timeline_cells(rows, week, zone):
    """Map local half-hour cells to overlapping items, including midnight spans."""
    from datetime import timedelta, timezone
    cells = {}
    for item in rows:
        begin = datetime.fromisoformat(item['begin_at']).astimezone(zone)
        end = datetime.fromisoformat(item['end_at']).astimezone(zone) if item['end_at'] else begin + timedelta(minutes=1)
        for day in range(7):
            date = week + timedelta(days=day)
            for half in range(48):
                wall = datetime.combine(date, datetime.min.time()) + timedelta(minutes=half * 30)
                for fold in (0, 1):
                    cell = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
                    if cell.astimezone(zone).replace(tzinfo=None) != wall:
                        continue
                    if begin.astimezone(timezone.utc) < cell + timedelta(minutes=30) and end.astimezone(timezone.utc) > cell:
                        cells.setdefault((half, day), []).append(item)
                        break
    return cells
