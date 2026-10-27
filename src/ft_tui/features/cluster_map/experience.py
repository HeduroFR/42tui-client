"""Offline 42cursus XP estimates from a community-published threshold table.

Numeric thresholds transcribed from lucas-ht/42calculator on 2026-10-23:
https://github.com/lucas-ht/42calculator/blob/main/data/experience_21.json
Upstream repository license: GPL-3.0 (see its LICENSE.md). No upstream
calculation code is included. This is a community snapshot, not a live 42
guarantee. Current XP is interpolated from the reported level and is estimated.
"""
from decimal import Decimal
from math import isfinite


CURSUS_ID = 21
SOURCE = 'https://github.com/lucas-ht/42calculator/blob/main/data/experience_21.json'
THRESHOLDS = (
    0, 462, 2688, 5885, 11777, 29217, 46255, 63559, 74340, 85483,
    95000, 105630, 124446, 145782, 169932, 197316, 228354, 263508,
    303366, 348516, 399672, 457632, 523320, 597786, 682164, 777756,
    886074, 1008798, 1147902, 1305486, 1484070,
)


def estimate_experience(cursus_id, level):
    """Return XP bounds and an estimate only for levels covered by this table."""
    if cursus_id != CURSUS_ID or type(level) not in (int, float) or not isfinite(level):
        return None
    if level < 0 or level >= len(THRESHOLDS) - 1:
        return None
    current = int(level)
    start, end = THRESHOLDS[current:current + 2]
    fraction = Decimal(str(level)) - current
    earned = int(fraction * (end - start))
    return {
        'total_xp': start + earned,
        'level_start_xp': start,
        'next_level_xp': end,
        'estimated': True,
    }
