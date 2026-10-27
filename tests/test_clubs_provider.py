import unittest
from copy import deepcopy
from ft_tui.api.http_client import HttpProjectProvider
from tests.test_ui_clubs import fixture, CLUB


class Api:
    def __init__(self, value):
        self.value = value
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        return deepcopy(self.value)


class ClubsProviderTests(unittest.TestCase):
    def test_overview_and_preferences_validate_types(self):
        api = Api(fixture())
        provider = HttpProjectProvider(api)
        self.assertEqual(provider.get_clubs(31)['account_id'], '2')
        self.assertEqual(api.calls[0], ('GET', '/v1/clubs', {'params': {'campus_id': 31}}))
        api.value['dnd'] = 'false'
        with self.assertRaises(ValueError):
            provider.get_clubs(31)
        with self.assertRaises(ValueError):
            provider.get_clubs(True)

    def test_activity_capacity_and_notification_validation(self):
        api = Api(fixture())
        provider = HttpProjectProvider(api)
        api.value['clubs'][0]['activities'][0]['capacity'] = 0
        with self.assertRaises(ValueError):
            provider.get_clubs(31)
        api.value = {'dnd': False, 'bells': {CLUB: True}, 'notifications': [{'club_id': CLUB, 'club_name': 'Babyfoot', 'event': fixture()['clubs'][0]['events'][0]}]}
        self.assertEqual(len(provider.poll_clubs()['notifications']), 1)
        api.value['notifications'][0]['event']['kind'] = 'unknown'
        with self.assertRaises(ValueError):
            provider.poll_clubs()

    def test_explicit_capability_and_announcement_metadata_are_validated(self):
        from ft_tui.features.clubs.models import overview
        value = fixture()
        value['clubs'][0]['can_announce'] = 'true'
        with self.assertRaises(ValueError):
            overview(value)
        value['clubs'][0]['can_announce'] = True
        event = value['clubs'][0]['events'][0]
        event.update(actor_login='alice', location='Cafeteria', event_at='2026-12-01T18:00:00+01:00')
        self.assertTrue(overview(value)['clubs'][0]['can_announce'])
        event['event_at'] = '2026-12-01T18:00'
        with self.assertRaises(ValueError):
            overview(value)
