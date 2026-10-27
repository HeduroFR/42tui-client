"""Literal display copy for project teams and corrections."""
from datetime import datetime, timedelta, timezone
from ft_tui.i18n import translate


def format_mark(value):
    return '—' if value is None else f'{value:g}%'


def format_date(value):
    if not value:
        return '—'
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def correction_phase(item, *, now=None):
    if item.get('filled_at'):
        return 'Completed'
    if not item.get('begin_at'):
        return 'Pending'
    when = datetime.fromisoformat(item['begin_at'].replace('Z', '+00:00'))
    return 'Scheduled' if when >= (now or datetime.now(timezone.utc)) else 'Overdue · not filled'


def team_summary(team, *, current=False, language='en'):
    t = lambda text: translate(text, language)
    status = t({'finished': 'Finished', 'in_progress': 'In progress', 'waiting_for_correction': 'Awaiting correction',
                'creating_group': 'Creating team', 'searching_a_group': 'Searching for a team',
                'waiting_to_start': 'Waiting to start'}.get(team['status'], team['status']))
    result = t('Passed') if team['validated'] is True else t('Failed') if team['validated'] is False else t('Result pending')
    members = ', '.join(m['login'] + (' ★' if m['leader'] else '') for m in team['members'])
    return '\n'.join([team['name'] + (' · ' + t('Current attempt') if current else ''),
                      f"{status} · {result} · {format_mark(team['final_mark'])}",
                      f"{t('Members')}: {members or '—'}",
                      f"{t('Repository')}: {team['repo_url'] or '—'}",
                      f"{t('Created')}: {format_date(team['created_at'])}",
                      f"{t('Locked')}: {format_date(team['locked_at'])} · {t('Closed')}: {format_date(team['closed_at'])}"])


def source_text(label, source, language='en', *, now=None):
    t = lambda text: translate(text, language)
    at = source.get('collected_at')
    expired = not at or datetime.fromisoformat(at.replace('Z', '+00:00')) + timedelta(seconds=60) <= (now or datetime.now(timezone.utc))
    state = 'Last known · outdated' if at and (source['stale'] or expired) else 'Unavailable' if source['status'] != 'available' else 'Up to date'
    if source['status'] == 'available' and (source['stale'] or expired):
        state = 'Cached · Refresh to update'
    if source.get('reason_code') == 'permission_denied':
        state = 'Access denied by 42 · Open on Intra'
    return f"{t(label)} · {t(state)}" + (f" · {format_date(at)}" if at else '')
