"""Immutable UTC intervals, retaining every upstream slot identity."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo
import os

UTC = timezone.utc


def timestamp(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError('Invalid slot timestamp')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('Slot timestamp needs a timezone')
    return result.astimezone(UTC)


def local_zone() -> tzinfo:
    """Prefer an IANA zone so future dates use their own DST offset."""
    candidates = [os.environ.get('TZ', '').removeprefix(':')]
    try:
        candidates.append(str(Path('/etc/localtime').resolve()).split('/zoneinfo/', 1)[1])
    except (OSError, IndexError):
        pass
    try:
        candidates.append(Path('/etc/timezone').read_text().strip())
    except OSError:
        pass
    for name in candidates:
        try:
            return ZoneInfo(name)
        except (ValueError, KeyError):
            pass
    return UTC


@dataclass(frozen=True)
class Slot:
    ids: tuple[str, ...]
    begin: datetime
    end: datetime
    booked: bool = False

    def __post_init__(self):
        if (not self.ids or len(set(self.ids)) != len(self.ids)
                or any(not isinstance(i, str) or not i.isascii() or not i.isdigit() or int(i) < 1 for i in self.ids)
                or type(self.booked) is not bool):
            raise ValueError('Invalid slot identity')
        for value in (self.begin, self.end):
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError('Slot timestamp needs a timezone')
            if value.minute % 15 or value.second or value.microsecond:
                raise ValueError('Slots use 15-minute increments')
        object.__setattr__(self, 'begin', self.begin.astimezone(UTC))
        object.__setattr__(self, 'end', self.end.astimezone(UTC))
        if self.begin >= self.end:
            raise ValueError('Slot end must follow its beginning')


def group_slots(rows) -> tuple[Slot, ...]:
    result = []
    ids = set()
    for slot in sorted(rows, key=lambda s: (s.begin, s.end)):
        if ids.intersection(slot.ids):
            raise ValueError('Duplicate slot identity')
        ids.update(slot.ids)
        if result and not result[-1].booked and not slot.booked and result[-1].end == slot.begin:
            previous = result.pop()
            result.append(Slot(previous.ids + slot.ids, previous.begin, slot.end))
        else:
            result.append(slot)
    return tuple(result)


def local_datetime(value: str, zone: tzinfo) -> datetime:
    """Reject nonexistent and ambiguous wall times instead of silently shifting."""
    wall = datetime.fromisoformat(value)
    if wall.tzinfo is not None:
        raise ValueError('Enter a local date and time without an offset')
    candidates = set()
    for fold in (0, 1):
        candidate = wall.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        if candidate.astimezone(zone).replace(tzinfo=None) == wall:
            candidates.add(candidate)
    if len(candidates) != 1:
        raise ValueError('This local time is ambiguous or does not exist')
    return candidates.pop()


def interval(day: date, first: int, last: int, zone: tzinfo):
    if not all(type(row) is int and 0 <= row < 96 for row in (first, last)):
        raise ValueError('Invalid calendar row')
    start, finish = sorted((first, last))
    midnight = datetime.combine(day, time())
    begin = local_datetime((midnight + timedelta(minutes=start * 15)).isoformat(), zone)
    end = local_datetime((midnight + timedelta(minutes=(finish + 1) * 15)).isoformat(), zone)
    return begin, end
