"""Terminal preferences persist and switch existing widgets without a restart."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image
from textual.app import App
from textual.screen import Screen
from textual.widgets import Static
from ft_tui.db.database import make_session_factory
from ft_tui.features.settings.adapters.storage import save_settings, get_setting
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.features.cluster_map.views.portrait import ClusterPortrait
from ft_tui.ui.components import Button, Select
from ft_tui.features.settings.views.workspace import SettingsWorkspace
from ft_tui.ui.companion import WipSprite


class PortraitHarness(App):
    image_mode = 'auto'
    language = 'en'

    def compose(self):
        yield ClusterPortrait()


class FakeTerminalImage(Static):
    image = None


class PreferenceSprite(WipSprite):
    refresh_count = 0

    def refresh_preferences(self):
        super().refresh_preferences()
        self.refresh_count += 1
        self.saved_preferences = (self.app.companion_visible, self.app.companion_motion)


class PreferencePerch(PreferenceSprite):
    pass


class TerminalSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_self_poke_button_previews_real_delivery_without_sending(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "wip-preview.db"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true', 'language': 'en'})
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.press('f5')
                    app.query_one(SettingsWorkspace).show_category(4)
                    button = app.query_one('#wip-test-poke')
                    button.scroll_visible(animate=False)
                    await pilot.pause()
                    self.assertTrue(await pilot.click('#wip-test-poke'))
                    from ft_tui.features.social.views.pokes import PokeNotification
                    for _ in range(20):
                        await pilot.pause(0.05)
                        if isinstance(app.screen, PokeNotification):
                            break
                    popup = app.screen
                    self.assertIsInstance(popup, PokeNotification)
                    self.assertTrue(popup.preview)
                    self.assertTrue(any('WIP test poke' in entry.poke['message'] for entry in popup.entries.values()))
                    self.assertEqual(popup._delivery_phase, 'travel')
                    self.assertFalse(popup.inbox.snapshot.get('pokes'))
                    await popup.action_close()
                    self.assertEqual(popup.inbox.snapshot.get('pokes'), [])
            finally:
                factory.kw['bind'].dispose()

    async def test_companion_drafts_persist_and_restore(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "companion.db"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true', 'language': 'en'})
                app = FortyTwoTuiApp(factory, None)
                self.assertIs(getattr(app, 'companion_visible', None), True)
                self.assertIs(getattr(app, 'companion_motion', None), True)
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.press('f5')
                    app.query_one(SettingsWorkspace).show_category(4)
                    for selector in ('#wip-companion', '#wip-motion'):
                        self.assertEqual(app.query_one(selector, Select).value, 'true')
                        app.query_one(selector, Select).value = 'false'
                    self.assertTrue(app.companion_visible)
                    self.assertTrue(app.companion_motion)
                    underlying = app.screen
                    perch = PreferencePerch()
                    await underlying.mount(perch)
                    overlay = Screen()
                    await app.push_screen(overlay)
                    sprite = PreferenceSprite()
                    await overlay.mount(sprite)
                    perch.refresh_count = sprite.refresh_count = 0
                    # Save the underlying settings while a modal screen is mounted.
                    with patch.object(app, 'query_one', underlying.query_one):
                        await app._save_settings()
                    self.assertEqual(perch.refresh_count, 1)
                    self.assertEqual(sprite.refresh_count, 1)
                    self.assertEqual(perch.saved_preferences, (False, False))
                    self.assertEqual(sprite.saved_preferences, (False, False))
                    app.pop_screen()
                    await pilot.pause()
                    self.assertFalse(app.companion_visible)
                    self.assertFalse(app.companion_motion)
                    with factory() as session:
                        self.assertEqual(get_setting(session, 'companion_visible'), 'false')
                        self.assertEqual(get_setting(session, 'companion_motion'), 'false')
                restored = FortyTwoTuiApp(factory, None)
                self.assertFalse(restored.companion_visible)
                self.assertFalse(restored.companion_motion)
            finally:
                factory.kw['bind'].dispose()

    async def test_username_gradient_preview_is_draft_then_saved_and_restored(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "gradient.db"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true', 'language': 'en'})
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(120, 40)) as pilot:
                    app.account_login = 'alice'
                    await pilot.press('f5')
                    app.query_one(SettingsWorkspace).show_category(4)
                    self.assertEqual(app.query_one('#username-gradient-preview', Static).render().plain, 'alice')
                    app.query_one('#username-gradient', Select).value = 'ocean'
                    await pilot.pause()
                    preview = app.query_one('#username-gradient-preview', Static).render()
                    self.assertEqual(preview.plain, 'alice')
                    self.assertTrue(preview.spans)
                    self.assertEqual(app.username_gradient, 'off')
                    await pilot.press('ctrl+s')
                    await pilot.pause()
                    self.assertEqual(app.username_gradient, 'ocean')
                    self.assertTrue(app.query_one('#dashboard-login', Static).render().spans)
                self.assertEqual(FortyTwoTuiApp(factory, None).username_gradient, 'ocean')
                with factory() as session:
                    save_settings(session, {'username_gradient': 'invalid'})
                self.assertEqual(FortyTwoTuiApp(factory, None).username_gradient, 'off')
            finally:
                factory.kw['bind'].dispose()

    async def test_auto_uses_wezterm_bundled_icons_on_startup_and_after_saving(self):
        from ft_tui.ui.terminal_capabilities import detect_capabilities
        caps = detect_capabilities({'TERM_PROGRAM': 'WezTerm'}, cell_size=(10, 20))
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "auto.db"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true', 'language': 'en'})
                with patch('ft_tui.ui.app.CAPABILITIES', caps):
                    app = FortyTwoTuiApp(factory, None)
                async with app.run_test() as pilot:
                    await pilot.pause()
                    self.assertEqual(app.icon_mode, 'auto')
                    button = app.query_one('#new-project-note', Button)
                    self.assertEqual(str(button.label), '\uf067')
                    await pilot.press('f5')
                    app.query_one('#terminal-icons', Select).value = 'unicode'
                    await pilot.press('ctrl+s')
                    await pilot.pause()
                    self.assertEqual(str(button.label), '+')
                    app.query_one('#terminal-icons', Select).value = 'auto'
                    await pilot.press('ctrl+s')
                    await pilot.pause()
                    self.assertEqual(str(button.label), '\uf067')
                    self.assertIn('Nerd Font', str(app.query_one('#terminal-capabilities').render()))
            finally:
                factory.kw['bind'].dispose()

    async def test_native_portrait_can_switch_to_blocks_off_and_back(self):
        with patch('ft_tui.features.cluster_map.views.portrait.NATIVE_IMAGES', True), patch(
            'ft_tui.features.cluster_map.views.portrait.TerminalImage', FakeTerminalImage
        ):
            app = PortraitHarness()
            async with app.run_test() as pilot:
                portrait = app.query_one(ClusterPortrait)
                portrait.image = Image.new('RGB', (40, 40), 'red')
                await pilot.pause()
                self.assertIsNotNone(portrait.query_one(FakeTerminalImage).image)
                for mode in ('halfcell', 'off', 'auto'):
                    app.image_mode = mode
                    await portrait.apply_terminal_settings()
                    await pilot.pause()
                    self.assertEqual(bool(portrait.query(FakeTerminalImage)), mode == 'auto')
                    if mode == 'halfcell':
                        self.assertIn('▀', portrait.render().plain)
                    if mode == 'off':
                        self.assertEqual(portrait.render().plain, 'Portrait hidden')

    async def test_save_updates_icons_portraits_and_restores_preferences(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "settings.db"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true', 'language': 'en',
                                            'image_mode': 'halfcell', 'icon_mode': 'nerd'})
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(120, 40)) as pilot:
                    await pilot.press('f5')
                    app.query_one(SettingsWorkspace).show_category(4)
                    await pilot.pause()
                    button = app.query_one('#new-project-note', Button)
                    self.assertEqual(str(button.label), '\uf067')
                    app.query_one('#terminal-icons', Select).value = 'text'
                    app.query_one('#terminal-images', Select).value = 'off'
                    await pilot.pause()
                    self.assertEqual(str(app.query_one('#terminal-icon-preview').render()), 'Projects   Friends   Settings')
                    self.assertEqual(str(button.label), '\uf067')  # Draft only.
                    await pilot.press('ctrl+s')
                    await pilot.pause()
                    self.assertEqual(str(button.label), 'New note')
                    self.assertFalse(button.has_class('icon-button'))
                    self.assertEqual(app.image_mode, 'off')
                    with factory() as session:
                        self.assertEqual(get_setting(session, 'image_mode'), 'off')
                        self.assertEqual(get_setting(session, 'icon_mode'), 'text')
                    app.query_one('#terminal-icons', Select).value = 'unicode'
                    await pilot.press('ctrl+s')
                    await pilot.pause()
                    self.assertEqual(str(button.label), '+')
                    self.assertTrue(button.has_class('icon-button'))
                    # Controls created after saving also respect the current mode.
                    app.icon_mode = 'text'
                    created = Button('New note', icon='\uf067', icon_only=True)
                    self.assertEqual(str(created.label), 'New note')
                    self.assertFalse(created.has_class('icon-button'))
                restored = FortyTwoTuiApp(factory, None)
                self.assertEqual(restored.image_mode, 'off')
                self.assertEqual(restored.icon_mode, 'unicode')
            finally:
                factory.kw['bind'].dispose()
