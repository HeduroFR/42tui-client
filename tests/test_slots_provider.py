import unittest
from datetime import datetime, timezone
from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.features.corrections.model import Slot

B = datetime(2026, 10, 26, 10, tzinfo=timezone.utc)
E = datetime(2026, 10, 26, 11, tzinfo=timezone.utc)

class API:
    def __init__(self):
        self.calls = []
        self.value = {'account_id': '7', 'can_write': True, 'slots': [
            {'id': 12, 'begin_at': B.isoformat(), 'end_at': E.isoformat(), 'booked': False}]}
    def request(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.value

class SlotProviderTests(unittest.TestCase):
    def test_load_validates_slots_and_retains_ids(self):
        api = API(); provider = HttpProjectProvider(api)
        result = provider.get_correction_slots(B, E)
        self.assertEqual(result['slots'][0].ids, ('12',))
        self.assertEqual(api.calls[0][0], ('GET', '/v1/me/slots'))
        api.value['slots'][0]['booked'] = 'false'
        with self.assertRaises(ValueError):
            provider.get_correction_slots(B, E)

    def test_writes_have_operation_keys_and_do_not_retry(self):
        api = API(); api.value = {'status': 'saved'}; provider = HttpProjectProvider(api)
        slot = Slot(('12',), B, E)
        provider.save_correction_slot(None, B, E)
        provider.delete_correction_slot(slot)
        self.assertEqual(len(api.calls), 2)
        self.assertEqual(api.calls[0][1]['json']['ids'], [])
        self.assertEqual(api.calls[1][1]['json'], {'action': 'delete', 'ids': [12]})
        self.assertNotEqual(api.calls[0][1]['headers']['Idempotency-Key'], api.calls[1][1]['headers']['Idempotency-Key'])
