import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from ft_tui.ui.friends import current_location


class CurrentLocationTests(unittest.TestCase):
    def test_invalid_presence_timestamps_use_map_observation_or_unavailable(self):
        now = datetime.now(timezone.utc)
        presences = [None, {}, {'status': 'available'}]
        for value in (None, '', 'invalid', 42, [], {}, now.replace(tzinfo=None).isoformat()):
            presences.append({'status': 'available', 'cached_at': value})
        for presence in presences:
            data = {'login': 'alice', 'user_id': '50', 'location': '2A1', 'presence': presence}
            with self.subTest(presence=presence):
                self.assertEqual(current_location(data), 'Unavailable')
                with patch('ft_tui.ui.cluster_map.observed_seat', return_value=('1A1', now)):
                    self.assertEqual(current_location(data, app=object()), '1A1')
                with patch('ft_tui.ui.cluster_map.observed_seat', return_value=None):
                    self.assertEqual(current_location(data, app=object()), 'Unavailable')

    def test_presence_freshness_and_map_precedence(self):
        now = datetime(2026, 10, 25, 18, 53, tzinfo=timezone.utc)
        cases = [
            (0, '2A1', 'available', '2A1'),
            (59, '2A1', 'available', '2A1'),
            (60, '2A1', 'available', 'Unavailable'),
            (-1, '2A1', 'available', 'Unavailable'),
            (0, None, 'available', 'No active session'),
            (0, '2A1', 'unavailable', 'Unavailable'),
        ]
        with patch('ft_tui.ui.friends.datetime', wraps=datetime) as clock:
            clock.now.return_value = now
            for age, location, status, expected in cases:
                data = {'location': location, 'presence': {'status': status,
                        'cached_at': (now - timedelta(seconds=age)).isoformat().replace('+00:00', 'Z')}}
                with self.subTest(age=age, location=location, status=status):
                    self.assertEqual(current_location(data), expected)
            data = {'location': '2A1', 'presence': {'status': 'available', 'cached_at': now.isoformat()}}
            for offset, expected in ((-1, '2A1'), (0, '1A1'), (1, '1A1')):
                with self.subTest(map_offset=offset), patch('ft_tui.ui.cluster_map.observed_seat',
                        return_value=('1A1', now + timedelta(seconds=offset))):
                    self.assertEqual(current_location(data, app=object()), expected)
