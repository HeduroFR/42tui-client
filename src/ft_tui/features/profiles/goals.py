"""Validated, credential-free Goals projection from the backend."""
from datetime import date, datetime
import math


def goals_response(value, account_id, cursus_id):
    if not isinstance(value, dict) or value.get('account_id') != account_id or value.get('cursus_id') != cursus_id:
        raise ValueError('Goals scope mismatch')
    if value.get('status') not in {'pending', 'unavailable', 'not_applicable', 'available'} or type(value.get('stale')) is not bool:
        raise ValueError('Invalid goals state')
    if value.get('reason') is not None and (not isinstance(value['reason'], str) or len(value['reason']) > 128):
        raise ValueError('Invalid goals reason')
    timestamp = value.get('collected_at')
    if timestamp is not None:
        if not isinstance(timestamp, str) or datetime.fromisoformat(timestamp.replace('Z', '+00:00')).tzinfo is None:
            raise ValueError('Invalid goals timestamp')
    if value['status'] == 'available':
        for field in ('cc_validated', 'probationary_period'):
            if type(value.get(field)) is not bool:
                raise ValueError('Invalid goals flag')
        for field in ('next_milestone', 'cc_eta'):
            if value.get(field) is not None:
                if not isinstance(value[field], str) or date.fromisoformat(value[field]).isoformat() != value[field]:
                    raise ValueError('Invalid goals date')
        weeks = value.get('edtrax_weeks')
        if not isinstance(weeks, list) or len(weeks) > 4:
            raise ValueError('Invalid Intra activity')
        for week in weeks:
            if not isinstance(week, dict) or not isinstance(week.get('name'), str) or not isinstance(week.get('text'), str):
                raise ValueError('Invalid Intra activity')
            hours = week.get('hours')
            if type(hours) not in (int, float) or not math.isfinite(hours) or not 0 <= hours <= 168:
                raise ValueError('Invalid Intra activity hours')
    return value
