"""Validate server-owned friendships before publishing them to local caches."""
from datetime import datetime
from uuid import UUID
from ft_tui.features.friends.models import LOGIN


def identity(value):
    if (not isinstance(value, dict) or not isinstance(value.get('account_id'), str)
            or not value['account_id'].isdigit() or not 0 < int(value['account_id']) <= 9007199254740991
            or not isinstance(value.get('login'), str) or not LOGIN.fullmatch(value['login'])):
        raise ValueError('Invalid social identity')
    return value


def timestamp(value):
    if not isinstance(value, str) or datetime.fromisoformat(value.replace('Z', '+00:00')).tzinfo is None:
        raise ValueError('Invalid social timestamp')


def poke(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid poke')
    UUID(value['id'])
    identity(value['recipient'])
    senders = value['senders']
    if not isinstance(senders, list) or not 1 <= len(senders) <= 8:
        raise ValueError('Invalid poke senders')
    ids = [identity(s)['account_id'] for s in senders]
    if len(ids) != len(set(ids)) or value['recipient']['account_id'] in ids:
        raise ValueError('Invalid poke senders')
    if (value.get('status') not in ('pending', 'sent', 'cancelled') or type(value.get('dismissed')) is not bool
            or not isinstance(value.get('approved'), list) or len(set(value['approved'])) != len(value['approved'])
            or any(s not in ids for s in value['approved'])
            or value['status'] == 'sent' and set(value['approved']) != set(ids)
            or not isinstance(value.get('message'), str) or not 1 <= len(value['message']) <= 500
            or any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value['message'])):
        raise ValueError('Invalid poke')
    timestamp(value['created_at'])
    timestamp(value['expires_at'])
    return value


def overview(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid social overview')
    if type(value.get('dnd')) is not bool:
        raise ValueError('Invalid social preferences')
    owner = value.get('account_id')
    identity({'account_id': owner, 'login': 'owner'})
    if any(not isinstance(value.get(k), list) for k in ('friends', 'incoming', 'outgoing', 'pokes')):
        raise ValueError('Invalid social overview')
    seen = {owner}
    for friend in value['friends']:
        fid = identity(friend)['account_id']
        if fid in seen:
            raise ValueError('Duplicate social identity')
        seen.add(fid)
    for key in ('incoming', 'outgoing'):
        for pair in value[key]:
            members = pair['members']
            ids = [identity(m)['account_id'] for m in members]
            if (len(ids) != 2 or len(set(ids)) != 2 or owner not in ids or pair.get('status') != 'pending'
                    or pair.get('requested_by') not in ids or (pair['requested_by'] == owner) != (key == 'outgoing')):
                raise ValueError('Invalid friend request')
            timestamp(pair['created_at'])
    for message in value['pokes']:
        p = poke(message)
        if not (p['status'] == 'sent' and p['recipient']['account_id'] == owner
                or p['status'] == 'pending' and any(s['account_id'] == owner for s in p['senders'])):
            raise ValueError('Invalid poke recipient')
    return value
