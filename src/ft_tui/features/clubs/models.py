"""Validation for the shared Clubs contract before rendering server data."""
from uuid import UUID
from datetime import datetime


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError('Invalid club timestamp')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Missing club timezone')
    return value


def club_id(value):
    if not isinstance(value, str):
        raise ValueError('Invalid club ID')
    if value.startswith('campus-') and value[7:].isdigit() and int(value[7:]) > 0:
        return value
    UUID(value)
    return value


def preferences(value):
    if not isinstance(value, dict) or type(value.get('dnd')) is not bool or not isinstance(value.get('bells'), dict):
        raise ValueError('Invalid club preferences')
    for key, bell in value['bells'].items():
        club_id(key)
        if type(bell) is not bool:
            raise ValueError('Invalid club bell')
    return value


def club(value):
    if not isinstance(value, dict):
        raise ValueError('Invalid club')
    club_id(value.get('id'))
    if (type(value.get('campus_id')) is not int or value['campus_id'] < 1
            or any(not isinstance(value.get(k), str) for k in ('name', 'description'))
            or any(type(value.get(k)) is not bool for k in ('system', 'archived'))
            or 'can_announce' in value and type(value['can_announce']) is not bool
            or value.get('my_role') not in ('creator', 'delegate', 'member', None)
            or not isinstance(value.get('members'), list) or len(value['members']) > 100
            or not isinstance(value.get('activities'), list) or len(value['activities']) > 100
            or not isinstance(value.get('events'), list) or len(value['events']) > 100):
        raise ValueError('Invalid club data')
    for member in value['members']:
        if (not isinstance(member, dict) or not isinstance(member.get('account_id'), str)
                or not member['account_id'].isdigit() or not isinstance(member.get('login'), str)
                or member.get('role') not in ('creator', 'delegate', 'member')):
            raise ValueError('Invalid club member')
    for item in value['activities']:
        UUID(item['id'])
        timestamp(item.get('created_at'))
        timestamp(item.get('expires_at'))
        if (item.get('status') not in ('recruiting', 'ready', 'started', 'finished', 'cancelled', 'expired')
                or any(not isinstance(item.get(k), str) for k in ('title', 'location', 'organizer_id', 'created_at', 'expires_at'))
                or type(item.get('minimum')) is not int or type(item.get('capacity')) is not int
                or not 1 <= item['minimum'] <= item['capacity'] <= 100
                or any(not isinstance(item.get(k), list) or len(item[k]) > 100
                       or any(not isinstance(i, str) or not i.isdigit() for i in item[k])
                       for k in ('participants', 'waitlist'))
                or len(item['participants']) > item['capacity']):
            raise ValueError('Invalid club activity')
    for item in value['events']:
        event(item)
    return value


def event(value):
    if (not isinstance(value, dict) or type(value.get('sequence')) is not int
            or value.get('kind') not in ('activity', 'ready', 'started', 'cancelled', 'announcement')
            or any(not isinstance(value.get(k), str) for k in ('actor_id', 'title', 'message', 'created_at', 'expires_at'))):
        raise ValueError('Invalid club event')
    for key, limit in (('actor_login', 100), ('location', 200)):
        if key in value and (not isinstance(value[key], str) or not 1 <= len(value[key]) <= limit):
            raise ValueError('Invalid announcement metadata')
    if 'event_at' in value:
        timestamp(value['event_at'])
    timestamp(value.get('created_at'))
    timestamp(value.get('expires_at'))
    if value.get('activity_id') is not None:
        UUID(value['activity_id'])
    return value


def overview(value):
    preferences(value)
    if (not isinstance(value.get('account_id'), str) or not value['account_id'].isdigit()
            or not isinstance(value.get('clubs'), list)):
        raise ValueError('Invalid clubs overview')
    for item in value['clubs']:
        club(item)
    return value


def poll(value):
    preferences(value)
    if not isinstance(value.get('notifications'), list) or len(value['notifications']) > 5:
        raise ValueError('Invalid club notifications')
    for item in value['notifications']:
        club_id(item['club_id'])
        if not isinstance(item.get('club_name'), str):
            raise ValueError('Invalid club notification')
        event(item['event'])
    return value
