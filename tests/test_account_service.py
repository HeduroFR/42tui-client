"""Account reads remain usable without Textual or a database."""
import unittest
from types import SimpleNamespace
from ft_tui.features.accounts.service import AccountService


class AccountServiceTests(unittest.TestCase):
    def test_returns_independent_account_and_cursus_snapshots(self):
        provider = SimpleNamespace(get_profile=lambda: {'account_id': '42'}, list_cursuses=lambda: [21])
        self.assertEqual(AccountService().read(provider), ({'account_id': '42'}, [21]))

    def test_optional_profile_capability_does_not_break_legacy_provider(self):
        self.assertEqual(AccountService().read(SimpleNamespace(list_cursuses=lambda: [21])), (None, [21]))

    def test_one_failed_source_does_not_discard_the_other(self):
        def fail(): raise RuntimeError('temporary outage')
        with self.assertLogs('ft_tui.features.accounts.service', level='WARNING'):
            self.assertEqual(AccountService().read(SimpleNamespace(get_profile=fail, list_cursuses=lambda: [21])), (None, [21]))
        with self.assertLogs('ft_tui.features.accounts.service', level='WARNING'):
            self.assertEqual(AccountService().read(SimpleNamespace(get_profile=lambda: {'account_id': '42'}, list_cursuses=fail)), ({'account_id': '42'}, None))
