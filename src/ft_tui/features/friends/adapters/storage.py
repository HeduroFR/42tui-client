"""Account-scoped friend storage and pure project/ranking projections."""
from copy import deepcopy
from sqlalchemy import select, delete
from ft_tui.features.friends.models import friend_snapshot
from ft_tui.db.models import Friend, FriendWatch, FriendObservation
from ft_tui.features.settings.adapters.storage import get_setting, save_settings
from ft_tui.shared.context import normalize_origin
import json
from hashlib import sha256

class FriendIdentityChanged(ValueError):
    """An existing login now identifies a different 42 account."""


from ft_tui.features.friends.projections import (
    ONGOING, ongoing, comparison, validated_project_count, _metric_rankings,
    level_rankings, project_rankings, curriculum_rank_key, curriculum_rankings,
)


def _membership_key(account_id, origin):
    scope = sha256(normalize_origin(origin).encode()).hexdigest()
    return f'mutual_friends:v1:{scope}:{account_id}'


def memberships(session, account_id, *, origin=''):
    if not account_id:
        return []
    # Only server-confirmed mutual relationships count as friends. Old local
    # watches remain available for migration but never imply the other student's consent.
    try:
        accepted = json.loads(get_setting(session, _membership_key(account_id, origin), '[]'))
        if not isinstance(accepted, list):
            return []
        accepted = {(friend['login'], friend['account_id']) for friend in accepted}
    except (ValueError, TypeError, KeyError):
        return []
    return [w for w in session.scalars(select(FriendWatch).where(
        FriendWatch.account_id == account_id).order_by(FriendWatch.login)) if (w.login, w.user_id) in accepted]


def cache_mutual_friends(session, account_id, friends, *, origin=''):
    accepted = {f['account_id'] for f in friends}
    rows = list(session.scalars(select(FriendWatch).where(FriendWatch.account_id == account_id)))
    for row in rows:
        if row.user_id not in accepted or not any(f['login'] == row.login and f['account_id'] == row.user_id for f in friends):
            session.delete(row)
    session.flush()
    for friend in friends:
        if not any(r.login == friend['login'] and r.user_id == friend['account_id'] for r in rows):
            session.add(FriendWatch(account_id=account_id, login=friend['login'], user_id=friend['account_id']))
    # Retain only authorized historical friends plus the owner's observation.
    allowed = {(friend['login'], friend['account_id']) for friend in friends}
    for row in session.scalars(select(FriendObservation).where(FriendObservation.account_id == account_id)):
        envelope = row.data if isinstance(row.data, dict) else {}
        data = envelope.get('snapshot') or {}
        if (envelope.get('origin') == normalize_origin(origin) and isinstance(data, dict)
                and data.get('user_id') != account_id and (row.login, data.get('user_id')) not in allowed):
            session.delete(row)
    save_settings(session, {_membership_key(account_id, origin): json.dumps(friends)})
    session.commit()


def cached_observations(session, account_id, cursus_id, *, origin=''):
    if not account_id or not cursus_id:
        return {}
    rows = session.scalars(select(FriendObservation).where(
        FriendObservation.account_id == account_id, FriendObservation.cursus_id == cursus_id))
    result = {}
    for row in rows:
        envelope = row.data
        if not isinstance(envelope, dict) or envelope.get('version') != 1 or envelope.get('origin') != normalize_origin(origin):
            continue
        data = deepcopy(envelope.get('snapshot'))
        try:
            friend_snapshot(data, row.login, cursus_id)
        except (ValueError, TypeError):
            continue
        # A disk snapshot must never advertise an old workstation as current.
        data['location'] = None
        data['presence'] = {'status': 'unavailable', 'cached_at': None}
        data['meta']['stale'] = True
        result[row.login] = data
    return result


def save_observation(session, account_id, data, *, origin=''):
    watch = session.scalar(select(FriendWatch).where(FriendWatch.account_id == account_id, FriendWatch.login == data['login']))
    if watch in memberships(session, account_id, origin=origin) and watch.user_id and watch.user_id != data['user_id']:
        raise FriendIdentityChanged('Friend identity changed; remove and re-add this login to confirm it.')
    if watch:
        watch.user_id = data['user_id']
    row = session.scalar(select(FriendObservation).where(FriendObservation.account_id == account_id,
        FriendObservation.cursus_id == data['cursus_id'], FriendObservation.login == data['login']))
    # Presence is deliberately not retained on disk.
    saved = deepcopy(data)
    saved['location'] = None
    saved['presence'] = {'status': 'unavailable', 'cached_at': None}
    saved = {'version': 1, 'origin': normalize_origin(origin), 'snapshot': saved}
    if row:
        row.data = saved
    else:
        session.add(FriendObservation(account_id=account_id, cursus_id=data['cursus_id'], login=data['login'], data=saved))
    session.flush()
    # Historical API cache only; user-owned projects, notes and settings survive.
    for old in session.scalars(select(FriendObservation).order_by(FriendObservation.id.desc()).offset(2048)):
        session.delete(old)
    session.commit()


def remove_friend(session, account_id, login):
    session.execute(delete(FriendWatch).where(FriendWatch.account_id == account_id, FriendWatch.login == login))
    session.execute(delete(FriendObservation).where(FriendObservation.account_id == account_id, FriendObservation.login == login))
    session.commit()


def forget_authorization(session, account_id, *, origin=''):
    """Invalidate historical cache eligibility without deleting user-owned data."""
    for row in session.scalars(select(FriendObservation).where(FriendObservation.account_id == account_id)):
        if isinstance(row.data, dict) and row.data.get('origin') == normalize_origin(origin):
            session.delete(row)
    save_settings(session, {_membership_key(account_id, origin): '[]'})


def forget_observation(session, account_id, cursus_id, login, *, origin=''):
    """Drop a denied profile's history without changing confirmed friendships."""
    row = session.scalar(select(FriendObservation).where(
        FriendObservation.account_id == account_id, FriendObservation.cursus_id == cursus_id,
        FriendObservation.login == login))
    if row and isinstance(row.data, dict) and row.data.get('origin') == normalize_origin(origin):
        session.delete(row)
        session.commit()
