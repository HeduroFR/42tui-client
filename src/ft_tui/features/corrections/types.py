"""Strict correction slot response boundary."""
from ft_tui.features.corrections.model import Slot, group_slots, timestamp


def slot_snapshot(value):
    if (not isinstance(value, dict) or not isinstance(value.get('account_id'), str)
            or not value['account_id'].isascii() or not value['account_id'].isdigit()
            or int(value['account_id']) < 1 or type(value.get('can_write')) is not bool
            or not isinstance(value.get('slots'), list) or len(value['slots']) > 3000):
        raise ValueError('Invalid correction slots response')
    rows = []
    for row in value['slots']:
        if (not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] < 1
                or type(row.get('booked')) is not bool):
            raise ValueError('Invalid correction slot')
        rows.append(Slot((str(row['id']),), timestamp(row.get('begin_at')),
                         timestamp(row.get('end_at')), row['booked']))
    return {**value, 'slots': group_slots(rows)}
