"""Pure projections: physical positions never depend on presence or filters."""
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from .geometry import positions


@dataclass(frozen=True)
class SeatState:
    hostname: str
    login: str | None = None
    person: dict | None = None
    machine: str = 'unknown'
    session: str = 'unknown'
    friend: bool = False
    open_count: int | None = None
    storage: dict | None = None
    lock_time: str | None = None
    lock_observed_at: str | None = None


def seat_states(snapshot: dict, friend_logins: frozenset[str]) -> dict[str, SeatState]:
    rows = {m['hostname'].split('.')[0].upper():m for m in snapshot.get('machines', [])}
    seen = set()
    result = {}
    stale = snapshot.get('meta', {}).get('stale', False)
    for host in positions('all'):
        row = rows.get(host)
        if not row:
            result[host] = SeatState(host)
            continue
        login = row.get('login') or row.get('exam_user') or None
        duplicate = bool(login and login in seen)
        if login:
            seen.add(login)
        online = row.get('status') == 'up'
        machine = 'online' if online else 'offline' if row.get('status') == 'down' else 'unknown'
        session = 'unknown' if duplicate else 'locked' if login and row.get('is_locked') else 'signed in' if login else 'no active session'
        issues = row.get('issues') or {}
        count = issues.get('open_count') if issues.get('availability') == 'available' and not stale else None
        result[host] = SeatState(host, None if duplicate else login, None if duplicate else row.get('person'),
            machine, session, bool(login in friend_logins and machine=='online' and not duplicate and not stale), count, row.get('storage'), row.get('lock_time') if session=='locked' else None,
            snapshot.get('meta',{}).get('cached_at') if session=='locked' else None)
    return result


def matching_hosts(states: dict[str, SeatState], query: str, filter_name: str, friends_only: bool) -> tuple[str, ...]:
    query = query.strip().casefold()
    def matches(s):
        if friends_only and not s.friend:
            return False
        free = s.machine == 'online' and s.session == 'no active session'
        if filter_name == 'free' and not free or filter_name == 'healthy' and not (free and s.open_count == 0):
            return False
        if filter_name == 'occupied' and not s.login or filter_name == 'issues' and not (s.open_count or 0):
            return False
        return not query or query in ' '.join([s.hostname, s.login or '', (s.person or {}).get('display_name') or '']).casefold()
    return tuple(host for host in positions('all') if host in states and matches(states[host]))


def status_label(status: str, translate) -> str:
    """Capitalize translated display labels while preserving internal status values."""
    label = translate(status)
    return label[:1].upper() + label[1:]


def session_label(seat: SeatState, translate, now: datetime | None = None) -> str:
    """Advance elapsed lock durations from their snapshot, or use a lock timestamp."""
    if seat.session != 'locked' or not seat.lock_time or seat.lock_time == 'N/A':
        return status_label(seat.session, translate)
    now = now or datetime.now(timezone.utc)
    elapsed = re.fullmatch(r'(\d+):([0-5]\d):([0-5]\d)', seat.lock_time)
    if elapsed:
        hours, minutes, seconds = map(int, elapsed.groups())
        seconds += hours * 3600 + minutes * 60
        if seat.lock_observed_at:
            try:
                observed = datetime.fromisoformat(seat.lock_observed_at.replace('Z', '+00:00'))
                seconds += max(0, int((now - observed).total_seconds()))
            except (ValueError, TypeError, OverflowError):
                pass
    else:
        try:
            started = datetime.fromisoformat(seat.lock_time.replace('Z', '+00:00'))
            if started.tzinfo is None:
                raise ValueError('Unknown lock timezone')
            seconds = max(0, int((now - started).total_seconds()))
        except (ValueError, TypeError, OverflowError):
            return translate('Locked since {time}').format(time=seat.lock_time)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    duration = f'{hours}h {minutes:02d}m {seconds:02d}s' if hours else f'{minutes}m {seconds:02d}s'
    return translate('Locked for {duration}').format(duration=duration)
