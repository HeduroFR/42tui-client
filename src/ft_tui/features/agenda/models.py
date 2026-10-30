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
        if row.get('location') is not None and (not isinstance(row['location'], str) or len(row['location']) > 512):
            raise ValueError('Invalid event location')
        for key in ('subscribers', 'capacity'):
            if row.get(key) is not None and (type(row[key]) is not int or row[key] < 0):
                raise ValueError('Invalid event occupancy')
        if 'projects' in row and (not isinstance(row['projects'], list) or len(row['projects']) > 1000 or any(not isinstance(name, str) or len(name) > 512 for name in row['projects'])):
            raise ValueError('Invalid exam projects')
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
            if url.scheme != 'https' or url.netloc not in {'profile.intra.42.fr', 'profile-v3.intra.42.fr', 'projects.intra.42.fr'} or url.query or url.fragment:
                raise ValueError('Invalid agenda link')
    return value['items']


def timeline_cells(rows, week, zone):
    """Map local half-hour cells to overlapping items, including midnight spans."""
    from datetime import timedelta, timezone
    cells = {}
    spans = []
    for day in range(7):
        date = week + timedelta(days=day)
        for half in range(48):
            wall = datetime.combine(date, datetime.min.time()) + timedelta(minutes=half * 30)
            starts = set()
            for fold in (0, 1):
                cell = wall.replace(tzinfo=zone, fold=fold).astimezone(timezone.utc)
                if cell.astimezone(zone).replace(tzinfo=None) == wall:
                    starts.add(cell)
            spans.append(((half, day), starts))
    for item in rows:
        begin = datetime.fromisoformat(item['begin_at']).astimezone(timezone.utc)
        end = datetime.fromisoformat(item['end_at']).astimezone(timezone.utc) if item['end_at'] else begin + timedelta(minutes=1)
        for key, starts in spans:
            if any(begin < cell + timedelta(minutes=30) and end > cell for cell in starts):
                cells.setdefault(key, []).append(item)
    return cells


def timeline_blocks(cells):
    """Give overlapping events separate lanes without narrowing unrelated events."""
    blocks = []
    for day in range(7):
        events = {}
        for (half, column), items in cells.items():
            if column != day:
                continue
            for item in items:
                key = (item['kind'], item['id'])
                if key not in events:
                    events[key] = {'item': item, 'day': day, 'start': half, 'end': half + 1}
                else:
                    events[key]['start'] = min(events[key]['start'], half)
                    events[key]['end'] = max(events[key]['end'], half + 1)
        group, ends = [], []
        for block in sorted(events.values(), key=lambda b: (b['start'], b['end'])):
            if ends and block['start'] >= max(ends):
                for previous in group:
                    previous['lanes'] = len(ends)
                blocks.extend(group)
                group, ends = [], []
            lane = next((i for i, end in enumerate(ends) if end <= block['start']), len(ends))
            if lane == len(ends):
                ends.append(block['end'])
            else:
                ends[lane] = block['end']
            block['lane'] = lane
            group.append(block)
        for block in group:
            block['lanes'] = len(ends)
        blocks.extend(group)
    return blocks
