"""Configuration of the client-facing OAuth service."""

import os
import unittest
from unittest.mock import patch

from ft_tui.config.settings import oauth_api_url


class OAuthApiSettingsTests(unittest.TestCase):
    def test_uses_deployed_backend_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(oauth_api_url(), "https://oauth.42wip.in")

    def test_uses_configured_backend_origin(self):
        with patch.dict(os.environ, {"FT_TUI_API_URL": "http://localhost:3000"}):
            self.assertEqual(oauth_api_url(), "http://localhost:3000")


if __name__ == "__main__":
    unittest.main()
