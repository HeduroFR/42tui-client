"""Validate the shared public campus directory before caching it locally."""
from ft_tui.features.catalog.models import positive


def campus_directory(value):
    rows = value.get('campuses') if isinstance(value, dict) else None
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('Invalid campus directory')
    result, ids = [], set()
    for row in rows:
        if not isinstance(row, dict) or not positive(row.get('id')) or row['id'] in ids:
            raise ValueError('Invalid campus directory')
        if not isinstance(row.get('name'), str) or not row['name'].strip() or len(row['name']) > 512:
            raise ValueError('Invalid campus directory')
        for field in ('country', 'city'):
            if row.get(field) is not None and (not isinstance(row[field], str) or len(row[field]) > 512):
                raise ValueError('Invalid campus directory')
        if row.get('active') is not None and type(row['active']) is not bool:
            raise ValueError('Invalid campus directory')
        ids.add(row['id'])
        result.append({key: row.get(key) for key in ('id', 'name', 'country', 'city', 'active')})
    return result
