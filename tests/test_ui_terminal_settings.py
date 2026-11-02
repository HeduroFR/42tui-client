"""Terminal preferences persist and switch existing widgets without a restart."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PIL import Image
from textual.app import App
from textual.widgets import Static
from ft_tui.db.database import make_session_factory
from ft_tui.features.settings.adapters.storage import save_settings, get_setting
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.features.cluster_map.views.portrait import ClusterPortrait
from ft_tui.ui.components import Button, Select
from ft_tui.features.settings.views.workspace import SettingsWorkspace


class PortraitHarness(App):
    image_mode = 'auto'
    language = 'en'

    def compose(self):
        yield ClusterPortrait()


class FakeTerminalImage(Static):
    image = None


class TerminalSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_theme_selection_previews_before_save_and_persists_on_save(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "theme.db"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true', 'favorite_theme': 'textual-dark'})
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(100, 36)) as pilot:
                    await pilot.press('f5')
                    selector = app.query_one('#favorite-theme', Select)
                    original = app.theme
                    selector.focus()
                    await pilot.press('enter', 'down')
                    await pilot.pause()
                    self.assertNotEqual(app.theme, original)
                    await pilot.press('escape')
                    await pilot.pause()
                    self.assertEqual(app.theme, original)
                    choice = next(name for name in app.available_themes if name != app.theme)
                    selector.value = choice
                    await pilot.pause()
                    self.assertEqual(app.theme, choice)
                    with factory() as session:
                        self.assertEqual(get_setting(session, 'favorite_theme'), 'textual-dark')
                    await pilot.press('ctrl+s')
                    await pilot.pause()
                    with factory() as session:
                        self.assertEqual(get_setting(session, 'favorite_theme'), choice)
            finally:
                factory.kw['bind'].dispose()

    async def test_onboarding_theme_preview_is_restored_if_dismissed(self):
        from ft_tui.ui.onboarding import OnboardingScreen
        from ft_tui.ui.select import Select as OnboardingSelect
        app = App()
        async with app.run_test(size=(100, 36)) as pilot:
            initial = app.theme
            choice = next(name for name in app.available_themes if name != initial)
            screen = OnboardingScreen(projects_root='/tmp', favorite_editor='vim',
                                      favorite_theme=initial, language='en', themes=list(app.available_themes))
            app.push_screen(screen)
            await pilot.pause()
            screen.query_one('#onboarding-theme', OnboardingSelect).value = choice
            await pilot.pause()
            self.assertEqual(app.theme, choice)
            screen.dismiss(None)
            await pilot.pause()
            self.assertEqual(app.theme, initial)

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
                    self.assertFalse(app.query('#terminal-capabilities, #terminal-icon-preview'))
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
                    images = app.query_one('#terminal-images', Select)
                    icons = app.query_one('#terminal-icons', Select)
                    self.assertEqual(images.region.y, icons.region.y)
                    self.assertGreater(icons.region.x - images.region.right, 0)
                    button = app.query_one('#new-project-note', Button)
                    self.assertEqual(str(button.label), '\uf067')
                    app.query_one('#terminal-icons', Select).value = 'text'
                    app.query_one('#terminal-images', Select).value = 'off'
                    await pilot.pause()
                    self.assertFalse(app.query('#terminal-capabilities, #terminal-icon-preview'))
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
