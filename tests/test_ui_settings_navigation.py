"""Settings categories retain drafts and support the complete keyboard flow."""

import tempfile
import unittest
from pathlib import Path

from textual.widgets import Input, ListView, TabbedContent
from textual.app import App, ComposeResult

from ft_tui.db.database import make_session_factory
from ft_tui.features.settings.adapters.storage import get_setting, save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.features.settings.views.workspace import SETTINGS_CATEGORIES
from ft_tui.features.settings.views.workspace import SettingsMixin
from ft_tui.ui.components import Static
from ft_tui.ui.select import Select


class SettingsNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_callback_clears_message_and_tolerates_removed_widget(self):
        class SettingsStatusApp(SettingsMixin, App):
            def compose(self) -> ComposeResult:
                yield Static('Settings saved locally.', id='settings-status')

        app = SettingsStatusApp()
        async with app.run_test() as pilot:
            status = app.query_one('#settings-status', Static)
            app.settings_status_timer = app.set_timer(60, app._clear_settings_status)
            app._clear_settings_status()
            self.assertEqual(str(status.render()), '')
            self.assertIsNone(app.settings_status_timer)

            # Force a queued timer callback to run after the widget is gone,
            # without relying on runner load or the three-second save timeout.
            await status.remove()
            app.settings_status_timer = app.set_timer(60, app._clear_settings_status)
            app.call_after_refresh(app._clear_settings_status)
            await pilot.pause()
            self.assertIsNone(app.settings_status_timer)

    async def test_account_storage_moves_session_without_saving_other_drafts(self):
        from contextlib import nullcontext
        from types import SimpleNamespace
        from unittest.mock import patch
        from ft_tui.infrastructure.security.keychain import CredentialStore, SessionCredentialStore
        from tests.test_keychain import FakeKeyring

        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            with factory() as session:
                save_settings(session, {"onboarding_completed": "true"})
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(100, 36)) as pilot:
                    await pilot.press('f5')
                    source = SessionCredentialStore()
                    source.save({'access_token': 'synthetic'})
                    app.oauth_client = SimpleNamespace(store=source, _credentials=None, _credential_lock=lambda: nullcontext())
                    app.account_connected = True
                    app._update_account_connection_widgets()
                    self.assertTrue(app.query_one('#settings-storage-card').display)
                    selector = app.query_one('#settings-storage', Select)
                    await pilot.pause()
                    button = app.query_one('#settings-storage-apply')
                    self.assertEqual(selector.region.y, button.region.y)
                    self.assertGreater(button.region.x - selector.region.right, 0)
                    self.assertEqual(selector.value, 'session')
                    selector.value = 'keyring'
                    backend = FakeKeyring()
                    with patch('ft_tui.features.accounts.adapters.storage_transfer.session_vault_path', return_value=Path(directory) / 'missing'), patch.object(CredentialStore, '_backend', return_value=backend):
                        app.query_one('#settings-storage-apply').press()
                        for _ in range(30):
                            await pilot.pause(.05)
                            if isinstance(app.oauth_client.store, CredentialStore):
                                break
                        self.assertIsInstance(app.oauth_client.store, CredentialStore)
                        self.assertEqual(app.oauth_client.store.load(), {'access_token': 'synthetic'})
                        self.assertIn('updated', str(app.query_one('#settings-storage-status', Static).render()))
                        await pilot.resize_terminal(64, 24)
                        await pilot.pause()
                        self.assertEqual(selector.region.y, button.region.y)
                        self.assertGreater(button.region.x - selector.region.right, 0)
                        await pilot.resize_terminal(45, 24)
                        await pilot.pause()
                        self.assertGreaterEqual(button.region.y, selector.region.bottom)
            finally:
                factory.kw['bind'].dispose()

    async def test_community_links_and_reminders_persist_independently(self):
        from unittest.mock import patch
        from ft_tui.features.settings.views.workspace import SettingsWorkspace
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            with factory() as session:
                save_settings(session, {"onboarding_completed": "true"})
            try:
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(100, 36)) as pilot:
                    await pilot.press('f5')
                    workspace = app.query_one(SettingsWorkspace)
                    workspace.show_category(len(SETTINGS_CATEGORIES) - 1)
                    await pilot.pause()
                    self.assertTrue(app.query_one('#community-github-reminder').display)
                    self.assertTrue(app.query_one('#community-discord-reminder').display)
                    with patch('ft_tui.features.settings.views.workspace.webbrowser.open', return_value=True) as browser:
                        app.query_one('#community-github').press()
                        await pilot.pause()
                        browser.assert_called_with('https://github.com/HeduroFR/42tui-client')
                        app.query_one('#community-discord').press()
                        await pilot.pause()
                        browser.assert_called_with('https://tui.42wip.in/discord')
                    app.query_one('#community-github-dismiss').press()
                    await pilot.pause()
                    self.assertFalse(app.query_one('#community-github-reminder').display)
                    self.assertTrue(app.query_one('#community-discord-reminder').display)
                    with factory() as session:
                        self.assertEqual(get_setting(session, 'community_github_reminder_seen'), 'true')
                        self.assertNotEqual(get_setting(session, 'community_discord_reminder_seen'), 'true')
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(100, 36)) as pilot:
                    await pilot.press('f5')
                    await pilot.resize_terminal(64, 24)
                    app.query_one(SettingsWorkspace).show_category(len(SETTINGS_CATEGORIES) - 1)
                    await pilot.pause()
                    self.assertFalse(app.query_one('#community-github-reminder').display)
                    self.assertTrue(app.query_one('#community-discord-reminder').display)
                    app.query_one('#community-discord-dismiss').press()
                    await pilot.pause()
                    self.assertFalse(app.query_one('#community-discord-reminder').display)
            finally:
                factory.kw['bind'].dispose()

    async def test_categories_edit_save_and_return_with_keyboard(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            try:
                with factory() as session:
                    save_settings(session, {"onboarding_completed": "true", "language": "en"})
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(100, 36)) as pilot:
                    await pilot.press("f5")
                    categories = app.query_one("#settings-categories", ListView)
                    self.assertIs(app.focused, categories)
                    content = app.query_one('#settings-content')
                    panel = app.query_one('#settings-panel-account')
                    self.assertEqual(panel.region.x, content.content_region.x)
                    self.assertEqual(panel.region.width, content.scrollable_content_region.width)
                    for index, (key, _) in enumerate(SETTINGS_CATEGORIES):
                        if index:
                            await pilot.press("down")
                        await pilot.pause()
                        visible = [panel.id for panel in app.query(".settings-panel") if panel.display]
                        self.assertEqual(visible, [f"settings-panel-{key}"])
                        self.assertEqual(str(app.query_one('#settings-category-title', Static).render()), SETTINGS_CATEGORIES[index][1])
                        self.assertTrue(str(app.query_one('#settings-category-description', Static).render()))
                    await pilot.press(*(["up"] * (len(SETTINGS_CATEGORIES) - 3)), "enter")
                    field = app.query_one("#projects-root", Input)
                    self.assertIs(app.focused, field)
                    field.value = str(Path(directory) / "projects")
                    await pilot.press("home", "end", "j", "k", "h", "l")
                    self.assertTrue(field.value.endswith("jkhl"))
                    self.assertEqual(app.query_one(TabbedContent).active, "settings")
                    await pilot.press("escape", "down", "up", "right")
                    self.assertIs(app.focused, field)
                    self.assertTrue(field.value.endswith("jkhl"))
                    self.assertTrue(app.club_notification_sound)
                    app.query_one("#club-notification-sound", Select).value = "false"
                    await pilot.press("ctrl+s")
                    await pilot.pause()
                    with factory() as session:
                        self.assertEqual(get_setting(session, "projects_root"), field.value)
                        self.assertEqual(get_setting(session, "club_notification_sound"), "false")
                    self.assertFalse(app.club_notification_sound)
                    await pilot.press("tab", "enter")
                    await pilot.pause()
                    await pilot.press("escape")
                    self.assertIsNot(app.focused, categories)  # Close the selector first.
                    await pilot.press("escape")
                    self.assertIs(app.focused, categories)
                    await pilot.resize_terminal(64, 24)
                    await pilot.pause()
                    self.assertTrue(app.query_one("#settings-workspace").has_class("compact"))
                    self.assertGreater(app.query_one('#settings-category-title').region.width, 0)
                    save = app.query_one("#save-settings")
                    self.assertGreater(save.region.width, 0)
                    self.assertLessEqual(save.region.bottom, 24)
                self.assertFalse(FortyTwoTuiApp(factory, None).club_notification_sound)
            finally:
                factory.kw["bind"].dispose()
