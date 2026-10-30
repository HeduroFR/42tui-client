"""Regression tests for the shared OAuth account connection UI."""

import asyncio
import tempfile
import threading
import unittest
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Cursus, Project, ProjectCursus, UserConfig
from ft_tui.i18n import translate
from ft_tui.features.settings.adapters.storage import get_setting
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.features.projects.views.settings import ProjectSettingsScreen


class FakeOAuthClient:
    def __init__(self):
        self.disconnect_calls = 0
        self.pairing_calls = 0
        self.poll_calls = 0
        self.request_thread_ids = []
        self.pairing_status = "approved"
        self.browser_opened = True
        self.block_poll = False
        self.poll_entered = threading.Event()
        self.release_poll = threading.Event()

    def create_pairing(self, *, theme=None):
        self.pairing_theme = theme
        self.pairing_calls += 1
        return SimpleNamespace(handle="pairing-handle", expires_at="later",
                               browser_opened=self.browser_opened,
                               authorization_url="https://api.example/oauth/42/start?pairing=" + "h" * 43)

    def poll_pairing(self, handle):
        self.poll_calls += 1
        if self.block_poll:
            self.poll_entered.set()
            self.release_poll.wait(timeout=3)
        return SimpleNamespace(status=self.pairing_status)

    def disconnect(self):
        self.disconnect_calls += 1

    def request(self, method, path, **kwargs):
        self.request_thread_ids.append(threading.get_ident())
        if path == "/v1/me":
            return {"account_id":"42", "login": "student42", "campuses":[{"id":31,"name":"Campus","is_primary":True}]}
        if path == "/v1/cursuses":
            return {"cursuses": []}
        raise AssertionError(path)


class AccountConnectionUiTests(unittest.IsolatedAsyncioTestCase):
    async def test_locked_vault_is_offered_on_startup_and_cancel_preserves_it(self):
        from unittest.mock import patch
        from ft_tui.api.oauth_client import OAuthClient
        from ft_tui.features.accounts.views.connection import VaultPassphraseScreen
        from ft_tui.infrastructure.security.session_vault import LockedSessionStore, SessionVault

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'vault'
            vault = SessionVault.create(path, 'a long test passphrase')
            vault.save({'access_token': 'secret'})
            original = path.read_bytes()
            client = OAuthClient('https://example.org', credential_store=LockedSessionStore(), lock_directory=Path(directory) / 'locks')
            factory = make_session_factory('sqlite:///:memory:')
            app = FortyTwoTuiApp(factory, None, oauth_client=client)
            with patch('ft_tui.infrastructure.security.session_vault.session_vault_path', return_value=path):
                async with app.run_test(size=(120, 45)) as pilot:
                    for _ in range(20):
                        await pilot.pause(0.1)
                        if isinstance(app.screen, VaultPassphraseScreen):
                            break
                    self.assertIsInstance(app.screen, VaultPassphraseScreen)
                    await pilot.press('escape')
                    await pilot.pause()
                    self.assertEqual(path.read_bytes(), original)
                    self.assertIsInstance(client.store, LockedSessionStore)

    async def test_vault_passphrase_confirmation_and_cancel(self):
        from textual.app import App
        from textual.widgets import Input
        from ft_tui.features.accounts.views.connection import VaultPassphraseScreen

        app = App()
        async with app.run_test(size=(100, 35)) as pilot:
            screen = VaultPassphraseScreen(False)
            app.push_screen(screen)
            await pilot.pause()
            screen.query_one('#vault-passphrase', Input).value = 'long passphrase'
            screen.query_one('#vault-confirm', Input).value = 'different passphrase'
            await pilot.click('#vault-continue')
            self.assertIn('matching', str(screen.query_one('#vault-error').render()))
            await pilot.press('escape')
            self.assertIsNot(app.screen, screen)

    async def test_keyring_migration_verifies_before_deleting_and_reset_is_local(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.api.oauth_client import OAuthClient
        from ft_tui.features.accounts.views.connection import AccountConnectionScreen
        from ft_tui.infrastructure.security.keychain import CredentialStore
        from ft_tui.infrastructure.security.session_vault import SessionVault, discard_locked_vault
        from test_keychain import FakeKeyring

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'credentials' / 'vault'
            keyring = FakeKeyring()
            old = CredentialStore(keyring_backend=keyring)
            credentials = {'access_token': 'a', 'refresh_token': 'r', 'expires_at': '2030-01-01T00:00:00Z', 'private_key_pem': 'key'}
            old.save(credentials)
            client = OAuthClient('https://example.org', credential_store=old, lock_directory=Path(directory) / 'locks')
            app = App()
            with patch('ft_tui.infrastructure.security.session_vault.session_vault_path', return_value=path):
                async with app.run_test(size=(120, 45)) as pilot:
                    screen = AccountConnectionScreen(client, connected=True)
                    app.push_screen(screen)
                    await pilot.pause()
                    await screen._migrate_vault('a long test passphrase')
                    self.assertIsNone(old.load())
                    self.assertEqual(SessionVault.unlock(path, 'a long test passphrase').load(), credentials)
                    self.assertIsInstance(client.store, SessionVault)
                    discard_locked_vault(path)
                    self.assertFalse(path.exists())

    async def test_vault_creation_and_unlock_reuse_saved_credentials(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.accounts.views.connection import AccountConnectionScreen
        from ft_tui.infrastructure.security.session_vault import SessionVault

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'credentials' / 'session.json'
            client = FakeOAuthClient()
            client.store = object()
            client._credentials = None
            client.pairing_status = 'pending'
            app = App()
            with patch('ft_tui.infrastructure.security.session_vault.session_vault_path', return_value=path):
                async with app.run_test(size=(120, 45)) as pilot:
                    screen = AccountConnectionScreen(client)
                    app.push_screen(screen)
                    await pilot.pause()
                    await screen._open_vault('a long test passphrase')
                    self.assertIsInstance(client.store, SessionVault)
                    self.assertEqual(client.pairing_calls, 1)
                    client.store.save({'access_token': 'access', 'refresh_token': 'refresh', 'expires_at': '2030-01-01T00:00:00Z', 'private_key_pem': 'key'})
                    await pilot.click('#account-connection-cancel')
                    self.assertEqual(SessionVault.unlock(path, 'a long test passphrase').load()['refresh_token'], 'refresh')

                    screen = AccountConnectionScreen(client)
                    app.push_screen(screen)
                    await pilot.pause()
                    await screen._open_vault('wrong passphrase')
                    self.assertIn('Could not open', str(screen.query_one('#account-connection-status').render()))
                    self.assertTrue(path.exists())
                    await screen._open_vault('a long test passphrase')
                    await pilot.pause()
                    self.assertIsInstance(client.store, SessionVault)

    async def test_session_only_approved_pairing_keeps_memory_store(self):
        from textual.app import App
        from ft_tui.features.accounts.views.connection import AccountConnectionScreen
        from ft_tui.infrastructure.security.keychain import SessionCredentialStore

        client = FakeOAuthClient()
        client.store = object()
        client._credentials = None
        app = App()
        async with app.run_test(size=(120, 45)) as pilot:
            screen = AccountConnectionScreen(client)
            app.push_screen(screen)
            await pilot.pause()
            await pilot.click("#account-session-only")
            await screen._poll_pairing()
            await pilot.pause()
            self.assertIsInstance(client.store, SessionCredentialStore)

    async def test_session_only_pairing_cancellation_restores_existing_store(self):
        from textual.app import App
        from ft_tui.features.accounts.views.connection import AccountConnectionScreen
        from ft_tui.infrastructure.security.keychain import SessionCredentialStore

        client = FakeOAuthClient()
        client.pairing_status = "pending"
        original = object()
        client.store = original
        client._credentials = None
        app = App()
        async with app.run_test(size=(120, 45)) as pilot:
            screen = AccountConnectionScreen(client)
            app.push_screen(screen)
            await pilot.pause()
            await pilot.click("#account-session-only")
            self.assertIsInstance(client.store, SessionCredentialStore)
            self.assertEqual(client.pairing_calls, 1)
            await pilot.click("#account-connection-cancel")
            self.assertIs(client.store, original)

    async def test_pairing_uses_resolved_active_theme_for_light_and_dark_apps(self):
        from textual.app import App
        from textual.color import Color
        from ft_tui.features.accounts.views.connection import AccountConnectionScreen

        for name in ("textual-dark", "textual-light"):
            with self.subTest(theme=name):
                client = FakeOAuthClient()
                client.pairing_status = "pending"
                app = App()
                app.theme = name
                async with app.run_test() as pilot:
                    screen = AccountConnectionScreen(client)
                    app.push_screen(screen)
                    await pilot.pause()
                    await screen._start_pairing()
                    variables = app.get_css_variables()
                    expected = {key: Color.parse(variables[key]).hex6 for key in ("background", "surface", "foreground", "primary", "success")}
                    self.assertEqual(client.pairing_theme, expected)

    async def test_onboarding_cannot_skip_or_complete_without_account_connection(self):
        factory = make_session_factory("sqlite:///:memory:")
        app = FortyTwoTuiApp(factory, None, oauth_client=FakeOAuthClient())
        async with app.run_test() as pilot:
            onboarding = app.screen
            self.assertFalse(onboarding.query("#onboarding-skip"))
            await pilot.press("escape")
            self.assertIs(app.screen, onboarding)
            await pilot.click("#onboarding-next")
            self.assertEqual(onboarding.step, 0)
            self.assertIn("Connect your 42 account", str(onboarding.query_one("#onboarding-error").render()))
            onboarding._finish()
            await app._finish_onboarding(None)
            await app._finish_onboarding({})
            with factory() as session:
                self.assertNotEqual(get_setting(session, "onboarding_completed"), "true")

            app.account_connected = True
            await pilot.click("#onboarding-next")
            await pilot.pause()
            await pilot.click("#onboarding-next")
            await pilot.pause()
            self.assertEqual(onboarding.step, 2)
            app.account_connected = False
            await pilot.click("#onboarding-finish")
            self.assertIs(app.screen, onboarding)
            self.assertEqual(onboarding.step, 0)
            with factory() as session:
                self.assertNotEqual(get_setting(session, "onboarding_completed"), "true")

    async def test_connect_button_starts_pairing_and_reports_failed_browser_launch(self):
        from textual.app import App
        from ft_tui.features.accounts.views.connection import AccountConnectionScreen

        client = FakeOAuthClient()
        client.pairing_status = "pending"
        client.browser_opened = False
        app = App()
        async with app.run_test() as pilot:
            screen = AccountConnectionScreen(client)
            app.push_screen(screen)
            await pilot.pause()
            await pilot.click("#account-connect")
            await pilot.pause()
            self.assertEqual(client.pairing_calls, 1)
            self.assertTrue(screen.polling)
            self.assertTrue(screen.query_one("#account-manual-link").display)
            self.assertIn("No browser opened", str(screen.query_one("#account-connection-status").render()))

    async def test_manual_pairing_link_can_be_copied_and_cleared_on_timeout(self):
        from textual.app import App
        from ft_tui.features.accounts.views.connection import AccountConnectionScreen

        client = FakeOAuthClient()
        client.pairing_status = "pending"
        app = App()
        async with app.run_test(size=(120, 45)) as pilot:
            screen = AccountConnectionScreen(client, start_pairing=True)
            app.push_screen(screen)
            await pilot.pause()
            self.assertTrue(screen.polling)
            self.assertTrue(screen.query_one("#account-manual-link").display)
            await pilot.click("#account-copy-link")
            self.assertEqual(app.clipboard, client.create_pairing().authorization_url)
            screen.poll_count = 300
            await screen._poll_pairing()
            self.assertFalse(screen.query_one("#account-manual-link").display)
            self.assertEqual(screen._authorization_url, "")

    async def test_expired_session_prompts_once_with_centered_reconnect_and_quit(self):
        from unittest.mock import patch
        from ft_tui.features.accounts.views.connection import SessionExpiredScreen
        from ft_tui.ui.app import SessionExpired
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            client = FakeOAuthClient()
            client.session_expired = True
            app = FortyTwoTuiApp(factory, None, oauth_client=client)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause()
                app.post_message(SessionExpired())
                app.post_message(SessionExpired())
                await pilot.pause()
                self.assertIsInstance(app.screen, SessionExpiredScreen)
                self.assertEqual(sum(isinstance(screen, SessionExpiredScreen) for screen in app.screen_stack), 1)
                actions = app.screen.query_one('#session-expired-actions')
                reconnect = app.screen.query_one('#session-reconnect')
                quit_button = app.screen.query_one('#session-quit')
                self.assertEqual(str(quit_button.label), 'Quit TUI')
                self.assertNotIn('?', str(app.screen.query_one('#session-expired-message').render()))
                left_gap = reconnect.region.x - actions.content_region.x
                right_gap = actions.content_region.right - quit_button.region.right
                self.assertLessEqual(abs(left_gap - right_gap), 1)
                with patch.object(app, 'exit') as quit_app:
                    await pilot.click("#session-quit")
                    await pilot.pause()
                    quit_app.assert_called_once_with()
                self.assertFalse(app.account_connected)
                self.assertIsNone(app.provider)
                app.post_message(SessionExpired())
                await pilot.pause()
                self.assertFalse(isinstance(app.screen, SessionExpiredScreen))

    async def test_expired_session_reconnect_starts_pairing_without_second_click(self):
        from ft_tui.features.accounts.views.connection import AccountConnectionScreen
        from ft_tui.ui.app import SessionExpired
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            client = FakeOAuthClient()
            client.session_expired = True
            app = FortyTwoTuiApp(factory, None, oauth_client=client)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause()
                app.post_message(SessionExpired())
                await pilot.pause()
                await pilot.click("#session-reconnect")
                await pilot.pause()
                self.assertIsInstance(app.screen, AccountConnectionScreen)
                self.assertEqual(client.pairing_calls, 1)
                self.assertTrue(app.screen.polling)
                self.assertTrue(app.screen.query_one("#account-connect").disabled)

    async def test_expiry_while_account_dialog_is_open_prompts_after_cancel(self):
        from ft_tui.features.accounts.views.connection import SessionExpiredScreen
        from ft_tui.ui.app import SessionExpired
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            client = FakeOAuthClient()
            client.session_expired = True
            app = FortyTwoTuiApp(factory, None, oauth_client=client)
            async with app.run_test(size=(120, 45)) as pilot:
                await pilot.pause()
                app.open_account_connection()
                await pilot.pause()
                app.post_message(SessionExpired())
                await pilot.pause()
                await pilot.click("#account-connection-cancel")
                await pilot.pause()
                self.assertIsInstance(app.screen, SessionExpiredScreen)

    async def test_startup_auth_failure_from_worker_opens_popup_but_outage_does_not(self):
        import httpx
        from ft_tui.api.oauth_client import OAuthClient, DeviceCredentials
        from ft_tui.features.accounts.views.connection import SessionExpiredScreen
        from tests.test_oauth_client import MemoryStore
        for status in (401, 503):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as directory:
                code = "invalid_device_credentials" if status == 401 else "session_service_unavailable"
                transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"error": code}))
                client = OAuthClient("https://api.example", MemoryStore(), http_client=httpx.Client(transport=transport), lock_directory=directory)
                client._save_credentials(DeviceCredentials("access", "refresh", "2000-01-01T00:00:00Z", client._new_private_key_pem()))
                factory = make_session_factory(f"sqlite:///{directory}/settings.db")
                app = FortyTwoTuiApp(factory, HttpProjectProvider(oauth_client=client), oauth_client=client)
                try:
                    async with app.run_test(size=(120, 45)) as pilot:
                        await pilot.pause()
                        self.assertEqual(isinstance(app.screen, SessionExpiredScreen), status == 401)
                        self.assertEqual(app.account_connected, status != 401)
                finally:
                    client.close()
                    factory.kw["bind"].dispose()

    async def test_project_checkout_suggestion_uses_only_the_safe_project_slug(self):
        project = Project(slug="libft", name="Libft")
        screen = ProjectSettingsScreen(project, "/workspace/42")
        self.assertEqual(screen.suggested_path, "/workspace/42/libft")

    async def test_project_checkout_suggestion_rejects_unsafe_slugs(self):
        for slug in ("/tmp/escape", "../escape", "nested/project", r"nested\project", ".", ".."):
            with self.subTest(slug=slug), self.assertRaises(ValueError):
                ProjectSettingsScreen(Project(slug=slug, name="Unsafe"), "/workspace/42")

    async def test_project_checkout_suggestion_resolves_symlinks_inside_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "projects"
            outside = Path(directory) / "outside"
            root.mkdir()
            outside.mkdir()
            (root / "libft").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                ProjectSettingsScreen(Project(slug="libft", name="Libft"), str(root))

    async def test_saved_custom_path_remains_authoritative_even_if_slug_is_unsafe(self):
        project = Project(slug="../renamed", name="Renamed", local_path="/custom/checkout")
        screen = ProjectSettingsScreen(project, "/workspace/42")
        self.assertEqual(screen.suggested_path, "/custom/checkout")

    async def test_default_cursus_selector_saves_choice_without_overwriting_other_settings(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            factory = make_session_factory(f"sqlite:///{temporary_directory}/settings.db")
            with factory() as session:
                session.add(UserConfig(key="projects_root", value="/workspace/42"))
                session.commit()
            app = FortyTwoTuiApp(factory, None, oauth_client=FakeOAuthClient())
            async with app.run_test() as pilot:
                await pilot.pause()
                app.set_cursus_choices(
                    [SimpleNamespace(id=21, name="42cursus")], loading=False, available=True
                )
                selector = app.query_one("#default-cursus")
                self.assertIn(("42cursus", "21"), selector._source_options)
                selector.value = "21"
                await app._save_settings()
                with factory() as session:
                    self.assertEqual(get_setting(session, "default_cursus_id"), "21")
                    self.assertEqual(get_setting(session, "projects_root"), "/workspace/42")

    async def test_unavailable_saved_cursus_remains_selected_after_choices_load(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            factory = make_session_factory(f"sqlite:///{temporary_directory}/settings.db")
            with factory() as session:
                session.add_all(
                    [
                        UserConfig(key="projects_root", value="/workspace/42"),
                    UserConfig(key="project_view_21", value="active"),
                    UserConfig(key="project_view_7", value="active"),
                        UserConfig(key="default_cursus_id", value="99"),
                    ]
                )
                session.commit()
            app = FortyTwoTuiApp(factory, None, oauth_client=FakeOAuthClient())
            async with app.run_test() as pilot:
                await pilot.pause()
                selector = app.query_one("#default-cursus")
                self.assertEqual(str(selector.value), "99")
                app.set_cursus_choices(
                    [SimpleNamespace(id=21, name="42cursus")], loading=False, available=True
                )
                self.assertEqual(str(selector.value), "99")
                self.assertIn("99", {str(value) for _, value in selector._source_options})
                status = app.query_one("#default-cursus-status")
                self.assertIn("Saved cursus unavailable (ID: 99)", str(status.render()))
                for language in ("fr", "es"):
                    app.language = language
                    app.set_cursus_choices(
                        [SimpleNamespace(id=21, name="42cursus")],
                        loading=False,
                        available=True,
                    )
                    translated_label = translate("Saved cursus (unavailable)", language)
                    self.assertIn(
                        translated_label,
                        {
                            str(label)
                            for label, value in selector._options
                            if str(value) == "99"
                        },
                    )
                    translated_status = translate(
                        "Saved cursus unavailable (ID: {cursus_id})", language
                    ).format(cursus_id="99")
                    self.assertEqual(str(status.render()), translated_status)
                app.language = "en"
                app.set_cursus_choices([], loading=True, available=False)
                self.assertIn("Loading cursus list", str(status.render()))
                app.set_cursus_choices([], loading=False, available=False)
                self.assertIn("Cursus list unavailable", str(status.render()))

    async def test_login_is_not_editable_and_both_flows_offer_account_connection(self):
        factory = make_session_factory("sqlite:///:memory:")
        app = FortyTwoTuiApp(factory, None, oauth_client=FakeOAuthClient())
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertFalse(app.query("#student-login"))
            self.assertIsNotNone(app.query_one("#settings-connect-account"))
            onboarding = app.screen
            self.assertEqual(onboarding.__class__.__name__, "OnboardingScreen")
            self.assertIsNotNone(onboarding.query_one("#onboarding-connect-account"))

    async def test_cancelled_connection_returns_to_caller_and_settings_uses_same_flow(self):
        factory = make_session_factory("sqlite:///:memory:")
        client = FakeOAuthClient()
        client.pairing_status = "pending"
        app = FortyTwoTuiApp(factory, None, oauth_client=client)
        async with app.run_test() as pilot:
            await pilot.pause()
            onboarding = app.screen
            await pilot.click("#onboarding-connect-account")
            await pilot.pause()
            screen = app.screen
            self.assertEqual(screen.__class__.__name__, "AccountConnectionScreen")
            await screen._start_pairing()
            await screen._poll_pairing()
            await pilot.pause()  # Allow the manual-link section to finish layout before clicking.
            self.assertFalse(screen.query_one("#account-connection-cancel").disabled)
            await pilot.click("#account-connection-cancel")
            await pilot.pause()
            self.assertIs(app.screen, onboarding)
            self.assertEqual(client.poll_calls, 1)

            app.account_connected = True
            await pilot.click("#onboarding-next")
            await pilot.pause()
            await pilot.click("#onboarding-next")
            await pilot.pause()
            await pilot.click("#onboarding-finish")
            await pilot.pause()
            app.action_show_settings()
            await pilot.pause()
            await pilot.click("#settings-connect-account")
            await pilot.pause()
            self.assertEqual(app.screen.__class__.__name__, "AccountConnectionScreen")
            await pilot.click("#account-connection-cancel")
            await pilot.pause()

    async def test_connection_modal_applies_current_language_on_mount(self):
        factory = make_session_factory("sqlite:///:memory:")
        app = FortyTwoTuiApp(factory, None, oauth_client=FakeOAuthClient())
        async with app.run_test() as pilot:
            await pilot.pause()
            app.language = "fr"
            app.open_account_connection("settings")
            await pilot.pause()
            modal = app.screen
            self.assertEqual(str(modal.query_one("#account-connection-title").render()), "Connectez votre compte 42")
            self.assertEqual(str(modal.query_one("#account-connect").label), "Connecter / reconnecter")

    async def test_expired_pairing_returns_to_connect_state(self):
        factory = make_session_factory("sqlite:///:memory:")
        client = FakeOAuthClient()
        client.pairing_status = "expired"
        app = FortyTwoTuiApp(factory, None, oauth_client=client)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#onboarding-connect-account")
            await pilot.pause()
            screen = app.screen
            await screen._start_pairing()
            await screen._poll_pairing()
            self.assertFalse(screen.query_one("#account-connect").disabled)
            self.assertIs(app.screen, screen)

    async def test_cancel_is_disabled_while_approval_poll_can_store_credentials(self):
        factory = make_session_factory("sqlite:///:memory:")
        client = FakeOAuthClient()
        client.block_poll = True
        app = FortyTwoTuiApp(factory, None, oauth_client=client)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#onboarding-connect-account")
            await pilot.pause()
            screen = app.screen
            await screen._start_pairing()
            poll = asyncio.create_task(screen._poll_pairing())
            self.assertTrue(await asyncio.to_thread(client.poll_entered.wait, 2))
            self.assertTrue(screen.query_one("#account-connection-cancel").disabled)
            client.release_poll.set()
            await poll
            await pilot.pause()
            self.assertTrue(app.account_connected)

    async def test_offline_startup_keeps_existing_sqlite_catalog(self):
        factory = make_session_factory("sqlite:///:memory:")
        with factory() as session:
            session.add(Project(slug="local-project", name="Local project", local_path="/workspace/local"))
            session.commit()
        app = FortyTwoTuiApp(factory, None)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIn("local-project", [p.slug for p in app.projects.values()])
            self.assertEqual({p.slug for p in app.projects.values()}, {"local-project"})

    async def test_offline_startup_shows_only_projects_linked_to_saved_cursus(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            with factory() as session:
                session.add_all([
                    Cursus(id=21, name="42cursus"),
                    Cursus(id=7, name="Piscine"),
                    UserConfig(key="default_cursus_id", value="21"),
                    UserConfig(key="projects_root", value="/workspace/42"),
                ])
                selected = Project(slug="selected", name="Selected cursus project", local_path="/selected")
                other = Project(
                    slug="other", name="Other cursus project", local_path="/kept/path/other"
                )
                legacy = Project(slug="legacy", name="Unassociated legacy project")
                session.add_all([selected, other, legacy])
                session.flush()
                session.add_all([
                    ProjectCursus(project_id=selected.id, cursus_id=21),
                    ProjectCursus(project_id=other.id, cursus_id=7),
                ])
                session.commit()

            app = FortyTwoTuiApp(factory, None)
            async with app.run_test() as pilot:
                await pilot.pause()
                self.assertEqual({p.slug for p in app.projects.values()}, {"selected"})
                await app._toggle_project_rank(app.query_one("ProjectRankHeader"))
                self.assertEqual(
                    [entry.project.slug for entry in app.query("#project-list-view ProjectEntry")],
                    ["selected"],
                )
                app.query_one("#default-cursus").value = "7"
                await pilot.pause()
                self.assertEqual({p.slug for p in app.projects.values()}, {"other"})
                app._open_project_settings_for_key(next(p.ui_key for p in app.projects.values() if p.slug == "other"))
                await pilot.pause()
                self.assertEqual(app.screen.suggested_path, "/kept/path/other")
                await pilot.press("escape")
                await pilot.pause()
                with factory() as session:
                    self.assertEqual(session.query(Project).count(), 3)
                    self.assertEqual(get_setting(session, "default_cursus_id"), "7")
                    self.assertEqual(get_setting(session, "projects_root"), "/workspace/42")
                    self.assertEqual(
                        session.query(Project).filter_by(slug="other").one().local_path,
                        "/kept/path/other",
                    )

    async def test_offline_missing_cursus_cache_shows_connection_needed_state(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            with factory() as session:
                session.add_all([
                    UserConfig(key="default_cursus_id", value="99"),
                    Project(slug="legacy", name="Legacy project"),
                ])
                session.commit()

            app = FortyTwoTuiApp(factory, None)
            async with app.run_test() as pilot:
                await pilot.pause()
                self.assertEqual(app.projects, {})
                self.assertIn(
                    "Connect your 42 account to load projects for this cursus.",
                    str(app.query_one("#dashboard-continue-activity").render()),
                )
                self.assertIn(
                    "Connect your 42 account to load projects for this cursus.",
                    str(app.query_one("#project-empty").render()),
                )
                with factory() as session:
                    self.assertEqual(get_setting(session, "default_cursus_id"), "99")

    async def test_new_project_note_button_recovers_after_catalog_becomes_empty_then_populated(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            with factory() as session:
                cursus = Cursus(id=21, name="42cursus")
                project = Project(slug="libft", name="Libft", local_path="/work")
                session.add_all([cursus, project, UserConfig(key="default_cursus_id", value="21"), UserConfig(key="project_view_21", value="active")])
                session.flush()
                membership = ProjectCursus(project_id=project.id, cursus_id=cursus.id)
                session.add(membership)
                session.commit()

            app = FortyTwoTuiApp(factory, None)
            async with app.run_test() as pilot:
                await pilot.pause()
                new_note_button = app.query_one("#new-project-note")
                self.assertTrue(new_note_button.disabled)
                await app._toggle_project_rank(app.query_one("ProjectRankHeader"))
                await pilot.pause()
                app.query_one("#project-list-view").index = 1
                await pilot.pause()
                self.assertFalse(new_note_button.disabled)

                with factory() as session:
                    session.delete(session.get(ProjectCursus, (project.id, cursus.id)))
                    session.commit()
                await app._reload_project_catalog()
                self.assertTrue(new_note_button.disabled)

                with factory() as session:
                    session.add(ProjectCursus(project_id=project.id, cursus_id=cursus.id))
                    session.commit()
                await app._reload_project_catalog()
                self.assertFalse(new_note_button.disabled)

    async def test_online_refresh_syncs_memberships_then_projects_for_saved_cursus(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")

            class Provider:
                def __init__(self):
                    self.requested_cursuses = []

                def get_profile(self):
                    return {"account_id":"42", "login": "student42", "campuses":[{"id":31,"name":"Campus","is_primary":True}]}

                def list_cursuses(self):
                    return [
                        SimpleNamespace(
                            id=21, name="42cursus", begin_at=datetime(2022, 1, 1),
                            end_at=datetime(2025, 1, 1),
                        ),
                        SimpleNamespace(
                            id=7, name="Piscine", begin_at=datetime(2024, 1, 1), end_at=None,
                        ),
                    ]

                def get_curriculum(self, scope):
                    return {"account_id":"42", "cursus_id":scope.cursus_id, "campus_id":scope.campus_id, "track":{"track":"new","source":"project"}, "rank":{"rank":None,"source":"unknown"}}

                def get_account_projects(self, cursus_id, cursor=None):
                    self.requested_cursuses.append(cursus_id)
                    return {"account_id":"42", "snapshot_id":"personal", "items":[{"id":cursus_id,"project_id":100+cursus_id,"slug":f"project-{cursus_id}","name":f"Project {cursus_id}","cursus_ids":[cursus_id],"status":"in_progress","validated":None,"final_mark":None,"vogsphere_url":None}], "next_cursor":None}

                def list_branches(self, scope, track, cursor=None):
                    return {"items":[],"next_cursor":None}

            provider = Provider()
            app = FortyTwoTuiApp(factory, None)
            async with app.run_test() as pilot:
                await pilot.pause()
                app.provider = provider
                app.account_connected = True
                await app._sync_online_provider(provider)
                self.assertEqual(provider.requested_cursuses, [7])
                self.assertEqual({p.slug for p in app.projects.values()}, {"project-7"})
                with factory() as session:
                    self.assertEqual(session.query(Cursus).count(), 2)
                    self.assertEqual(session.query(ProjectCursus).count(), 1)
                    self.assertEqual(get_setting(session, "default_cursus_id"), "7")

                await pilot.click("#onboarding-next")
                await pilot.pause()
                await pilot.click("#onboarding-next")
                await pilot.pause()
                await pilot.click("#onboarding-finish")
                await pilot.pause()
                app.action_show_settings()
                await pilot.pause()
                app.query_one("#default-cursus").value = "21"
                await pilot.pause()
                self.assertEqual(provider.requested_cursuses, [7, 21])
                self.assertEqual({p.slug for p in app.projects.values()}, {"project-21"})
                with factory() as session:
                    self.assertEqual(get_setting(session, "default_cursus_id"), "21")

    async def test_onboarding_initializes_account_state_from_existing_connection(self):
        factory = make_session_factory("sqlite:///:memory:")
        app = FortyTwoTuiApp(factory, None, oauth_client=FakeOAuthClient())
        app.account_connected = True
        app.account_login = "student42"
        async with app.run_test() as pilot:
            await pilot.pause()
            onboarding = app.screen
            self.assertIn("student42", str(onboarding.query_one("#onboarding-account-state").render()))
            self.assertIn("Manage", str(onboarding.query_one("#onboarding-connect-account").label))

    async def test_onboarding_updates_account_state_after_connection(self):
        factory = make_session_factory("sqlite:///:memory:")
        app = FortyTwoTuiApp(factory, None, oauth_client=FakeOAuthClient())
        async with app.run_test() as pilot:
            await pilot.pause()
            onboarding = app.screen
            app.account_connected = True
            app.account_login = "student42"
            app._update_account_connection_widgets()
            self.assertIn("student42", str(onboarding.query_one("#onboarding-account-state").render()))
            self.assertIn("Manage", str(onboarding.query_one("#onboarding-connect-account").label))

    async def test_stale_sync_snapshot_is_discarded_after_account_changes(self):
        factory = make_session_factory("sqlite:///:memory:")
        client = FakeOAuthClient()
        app = FortyTwoTuiApp(factory, None, oauth_client=client)
        provider = HttpProjectProvider(oauth_client=client)
        app.provider = provider
        app.account_connected = True
        app.account_generation = 7
        snapshots = [SimpleNamespace(slug="stale-project", name="Stale", status="available",
                                     last_defense_score=None, blackhole_date=None,
                                     dev_repo_url=None, vogsphere_url=None)]
        def delayed_fetch(_provider):
            app.account_generation += 1
            app.provider = None
            return {"login": "old-user"}, snapshots
        app._sync_online_data = delayed_fetch
        await app._sync_online_provider(provider, generation=7)
        with factory() as session:
            self.assertIsNone(session.query(Project).filter_by(slug="stale-project").first())

    async def test_approved_pairing_uses_profile_login_and_disconnect_revokes_this_device(self):
        factory = make_session_factory("sqlite:///:memory:")
        client = FakeOAuthClient()
        app = FortyTwoTuiApp(factory, None, oauth_client=client)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#onboarding-connect-account")
            await pilot.pause()
            pairing_screen = app.screen
            await pairing_screen._start_pairing()
            await pairing_screen._poll_pairing()
            await pilot.pause()
            await app.workers.wait_for_complete()
            self.assertEqual(app.account_login, "student42")
            self.assertTrue(app.account_connected)
            self.assertIsInstance(app.provider, HttpProjectProvider)
            self.assertTrue(client.request_thread_ids)
            self.assertNotIn(threading.get_ident(), client.request_thread_ids)

            app.open_account_connection("settings")
            await pilot.pause()
            await pilot.click("#account-disconnect")
            await pilot.pause()
            self.assertEqual(client.disconnect_calls, 1)
            self.assertFalse(app.account_connected)
            self.assertIsNone(app.provider)


class CursusPersistenceTests(unittest.TestCase):
    """Persistence policy does not need the app's widgets or message loop."""

    def test_first_connection_persists_latest_active_cursus_only_when_unset(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            try:
                context = SimpleNamespace(session_factory=factory, is_mounted=False)
                selected = FortyTwoTuiApp._select_default_cursus_if_unset(
                    context,
                    [
                        SimpleNamespace(id=21, name="42cursus", begin_at=datetime(2022, 1, 1),
                                        end_at=datetime(2025, 1, 1)),
                        SimpleNamespace(id=7, name="Piscine", begin_at=datetime(2024, 1, 1), end_at=None),
                    ],
                    today=date(2026, 10, 20),
                )
                self.assertEqual(selected, 7)
                with factory() as session:
                    self.assertEqual(get_setting(session, "default_cursus_id"), "7")
            finally:
                factory.kw["bind"].dispose()

    def test_first_connection_does_not_replace_a_saved_unavailable_cursus(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            try:
                with factory() as session:
                    session.add(UserConfig(key="default_cursus_id", value="99"))
                    session.commit()
                context = SimpleNamespace(session_factory=factory, is_mounted=False)
                selected = FortyTwoTuiApp._select_default_cursus_if_unset(
                    context,
                    [SimpleNamespace(id=21, name="42cursus")], today=date(2026, 10, 20),
                )
                self.assertEqual(selected, 99)
                with factory() as session:
                    self.assertEqual(get_setting(session, "default_cursus_id"), "99")
            finally:
                factory.kw["bind"].dispose()


if __name__ == "__main__":
    unittest.main()
