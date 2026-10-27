"""Context ownership and compatibility must not depend on a running UI."""
import unittest
from types import SimpleNamespace

from ft_tui.shared.context import AccountContext, normalize_origin
from ft_tui.app.state import StateField
from ft_tui.features.accounts.state import AccountState
from ft_tui.features.catalog.state import CatalogState


class ContextTests(unittest.TestCase):
    def test_origin_is_canonical_and_never_contains_credentials_or_query(self):
        context = AccountContext('HTTPS://user:private@Example.test:443/api/?token=x#f', '42', 2, 123)
        self.assertEqual(context.key, ('https://example.test/api', '42', 2, 123))
        self.assertEqual(normalize_origin('http://[::1]:80/'), 'http://[::1]')
        with self.assertRaises(Exception):
            context.generation = 3

    def test_identity_generation_and_provider_all_partition_requests(self):
        first = AccountContext('https://example.test', '42', 1, 100)
        self.assertNotEqual(first, AccountContext(first.origin, '43', 1, 100))
        self.assertNotEqual(first, AccountContext(first.origin, '42', 2, 100))
        self.assertNotEqual(first, AccountContext(first.origin, '42', 1, 101))
        self.assertEqual(first.key, (first.origin, '42', 1, 100))

    def test_feature_state_defaults_do_not_share_containers(self):
        first, second = AccountState(), AccountState()
        first.profile['login'] = 'one'
        first.campuses.append({'id': 31})
        self.assertEqual(second.profile, {})
        self.assertEqual(second.campuses, [])
        one, two = CatalogState(), CatalogState()
        one.branch_items.append({'branch_id': 'a'})
        self.assertEqual(two.branch_items, [])

    def test_legacy_attribute_access_forwards_to_one_feature_owned_state(self):
        class Shell:
            account_id = StateField('account_state', 'account_id')
            catalog_status = StateField('catalog_state', 'status')
        shell = Shell()
        shell.account_state, shell.catalog_state = AccountState(), CatalogState()
        shell.account_id = '42'
        self.assertEqual(shell.account_state.account_id, '42')
        shell.account_state.account_id = '43'
        self.assertEqual(shell.account_id, '43')
        shell.catalog_status = 'Saved catalog'
        self.assertEqual(shell.catalog_state.status, shell.catalog_status)
