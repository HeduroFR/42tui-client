"""Ensure account connection UI copy is translated in supported locales."""

import unittest

from ft_tui.i18n import translate


ACCOUNT_COPY = (
    "No browser opened. Open the login link below to continue.",
    "If no browser opens, copy this link into an available browser (another device works too).",
    "Copy login link",
    "Your session has expired. Reconnect your 42 account?",
    "Reconnect",
    "Later",
    "42 account",
    "Not connected",
    "Connect 42 account",
    "Manage 42 account",
    "Connect your 42 account",
    "Connect / reconnect",
    "Disconnect this device",
    "Opening the 42 authorization page…",
    "Approve 42TUI in your browser. Waiting for authorization…",
    "Pairing timed out. You can try again.",
    "Account connected. Updating your local project list…",
    "Pairing expired or was cancelled. You can start a new connection.",
    "Disconnecting this device…",
    "The OS keychain is unavailable; credentials were not stored",
    "Could not complete 42 account connection. Check your connection and try again.",
    "Could not reach the 42 account service. Your local projects are still available.",
    "Connected · profile unavailable",
    "Not connected · saved projects only",
    "Connected 42 account",
    "Local projects",
    "42 account not connected",
    "42 API",
    "Your projects sync from the centralized 42 API. The local catalog stays available offline.",
    "Your saved projects and activity stay on this device. Connect your 42 account to sync your real projects.",
    "CONNECTED ACCOUNT · LOCAL PROJECTS",
    "LOCAL WORKSPACE · OFFLINE MODE",
    "Default cursus",
    "Choose the cursus used to filter your project list.",
    "Loading cursus list…",
    "Cursus list unavailable. Connect your 42 account to load cursus options.",
    "No cursus memberships found.",
    "Saved cursus unavailable (ID: {cursus_id})",
    "Saved cursus (unavailable)",
    "Select cursus",
)


class AccountLocaleTests(unittest.TestCase):
    def test_account_ui_copy_has_french_and_spanish_translations(self):
        for language in ("fr", "es"):
            with self.subTest(language=language):
                for source in ACCOUNT_COPY:
                    self.assertNotEqual(translate(source, language), source, source)

    def test_connected_login_template_is_translated(self):
        self.assertEqual(translate("Connected as student42", "fr"), "Connecté en tant que student42")
        self.assertEqual(translate("Connected as student42", "es"), "Conectado como student42")


if __name__ == "__main__":
    unittest.main()
