"""Pure student profile summaries."""
from datetime import date, timedelta


def latest_attempts(items):
    latest = {}
    for item in items:
        if item['project_id'] not in latest or latest[item['project_id']]['id'] < item['id']:
            latest[item['project_id']] = item
    return sorted(latest.values(), key=lambda item: item['name'].casefold())


def weekly_attendance(data, today=None):
    today = today or date.fromisoformat(data['end'])
    monday = today - timedelta(days=today.weekday())
    weeks = []
    for offset in range(4, 0, -1):
        begin = monday - timedelta(weeks=offset)
        days = [data.get('days', {}).get((begin + timedelta(days=i)).isoformat()) for i in range(7)]
        weeks.append({'begin': begin, 'seconds': sum(d for d in days if d is not None),
                      'known_days': sum(d is not None for d in days)})
    return weeks
