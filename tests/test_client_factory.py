"""Offline-first provider selection from keychain credentials."""

import unittest
from types import SimpleNamespace

from ft_tui.api.client_factory import provider_for_device
from ft_tui.api.http_client import HttpProjectProvider


class ClientFactoryTests(unittest.TestCase):
    def test_missing_credentials_select_no_remote_provider(self):
        client = SimpleNamespace(credentials=None)
        self.assertIsNone(provider_for_device(client))

    def test_unavailable_keychain_selects_local_only_mode(self):
        class UnavailableClient:
            @property
            def credentials(self):
                raise RuntimeError("keychain unavailable")

        self.assertIsNone(provider_for_device(UnavailableClient()))

    def test_valid_device_credentials_select_authenticated_provider_and_share_client(self):
        client = SimpleNamespace(credentials=SimpleNamespace(access_token="access", refresh_token="refresh"))
        provider = provider_for_device(client)
        self.assertIsInstance(provider, HttpProjectProvider)
        self.assertIs(provider.api, client)


if __name__ == "__main__":
    unittest.main()
