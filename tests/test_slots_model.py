import unittest
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from ft_tui.features.corrections.model import Slot, group_slots, local_datetime, interval


def at(hour, minute=0):
    return datetime(2026, 10, 26, hour, minute, tzinfo=timezone.utc)


class SlotModelTests(unittest.TestCase):
    def test_grouping_preserves_ids_and_booking_boundaries(self):
        rows = [Slot(('2',), at(10, 15), at(10, 30)), Slot(('1',), at(10), at(10, 15)),
                Slot(('3',), at(10, 30), at(10, 45), True), Slot(('4',), at(11), at(11, 15))]
        result = group_slots(rows)
        self.assertEqual(result[0], Slot(('1', '2'), at(10), at(10, 30)))
        self.assertEqual(len(result), 3)
        self.assertTrue(result[1].booked)

    def test_rejects_bad_slots(self):
        for args in [((), at(10), at(11)), (('1',), at(11), at(10)),
                     (('1',), at(10).replace(tzinfo=None), at(11)),
                     (('1',), at(10, 1), at(11))]:
            with self.assertRaises(ValueError):
                Slot(*args)
        with self.assertRaises(ValueError):
            group_slots([Slot(('1',), at(10), at(11)), Slot(('1',), at(11), at(12))])

    def test_dst_gap_and_fold_are_rejected(self):
        zone = ZoneInfo('Europe/Paris')
        for text in ('2026-03-29T02:15', '2026-10-25T02:15'):
            with self.assertRaises(ValueError):
                local_datetime(text, zone)
        self.assertEqual(local_datetime('2026-10-26T10:15', zone).hour, 9)

    def test_interval_reverses_drag_and_allows_midnight(self):
        a, b = interval(date(2026, 10, 26), 95, 93, timezone.utc)
        self.assertEqual(a, at(23, 15))
        self.assertEqual(b, datetime(2026, 10, 27, tzinfo=timezone.utc))
        with self.assertRaises(ValueError):
            interval(date(2026, 10, 26), -1, 2, timezone.utc)
