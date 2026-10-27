"""Shared buttons keep focus visible without inverting their labels."""

import importlib
import inspect
from pathlib import Path
import unittest
from types import SimpleNamespace

from textual.app import App, ComposeResult
from textual.geometry import Region
from textual.widgets import Button as TextualButton

from ft_tui.ui.button import Button as AppButton
from ft_tui.ui.components import Button


class ButtonApp(App):
    def __init__(self):
        super().__init__()
        self.pressed = []
        self.language = "en"
        self.icon_mode = 'nerd'
        self.terminal_capabilities=SimpleNamespace(cell_size=(10,20))

    def compose(self) -> ComposeResult:
        yield Button("Connect / reconnect", variant="primary", id="connect")
        yield Button("Cancel", id="cancel")
        yield Button("Save settings", flat=True, id="flat")
        yield Button("Disconnect this device", disabled=True, id="disabled")
        yield AppButton("Close", id="plain")
        yield Button("Success", variant="success", id="success")
        yield Button("Warning", variant="warning", id="warning")
        yield Button("Error", variant="error", id="error")
        yield Button("Delete", variant="danger", id="danger")
        yield Button("Flat primary", variant="primary", flat=True, id="flat-primary")
        yield Button("New note", icon='\uf067', icon_only=True, id="icon")
        yield AppButton('+',square=True,id='square')
        yield AppButton('×',square=True,compact=True,id='square-compact')

    def on_button_pressed(self, event: TextualButton.Pressed):
        self.pressed.append(event.button.id)


class SharedButtonTests(unittest.IsolatedAsyncioTestCase):
    def test_all_application_buttons_inherit_from_app_button(self):
        import ft_tui.ui

        ui_root = Path(ft_tui.ui.__file__).parent
        for path in sorted(ui_root.rglob('*.py')):
            relative = path.relative_to(ui_root).with_suffix('')
            parts = relative.parts
            if parts[-1] == '__init__':
                parts = parts[:-1]
            module = importlib.import_module('.'.join(('ft_tui', 'ui', *parts)))
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if module.__name__ == 'ft_tui.ui.button' and name == 'TextualButton':
                    continue
                if issubclass(cls, TextualButton):
                    with self.subTest(module=module.__name__, name=name):
                        self.assertTrue(issubclass(cls, AppButton))

    async def test_danger_uses_error_palette_and_supports_variant_changes(self):
        app = ButtonApp()
        async with app.run_test(size=(100, 50)) as pilot:
            danger = app.query_one('#danger')
            error = app.query_one('#error')
            for theme in ('textual-dark', 'textual-light', 'ansi-dark', 'ansi-light'):
                app.theme = theme
                for hovered, active, disabled in ((False, False, False), (True, False, False),
                                                  (True, True, False), (False, False, True)):
                    styles = []
                    app.set_focus(None)
                    for button in (danger, error):
                        button.disabled = disabled
                        button.set_class(active, '-active')
                        await pilot.hover(button if hovered else '#plain')
                        await pilot.pause()
                        styles.append((button.styles.background, button.styles.color, button.styles.tint))
                    self.assertEqual(styles[0], styles[1])
                danger.disabled = error.disabled = False
                danger.remove_class('-active'); error.remove_class('-active')
            app.theme = 'textual-dark'
            app.set_focus(None)
            await pilot.hover('#plain')
            await pilot.pause()
            from textual.color import Color
            self.assertEqual(danger.styles.background, Color.parse(app.get_css_variables()['error-muted']))
            self.assertEqual(danger.styles.color, Color.parse(app.get_css_variables()['foreground']))
            self.assertEqual(danger.variant, 'danger')
            danger.variant = 'primary'
            self.assertFalse(danger.has_class('-danger'))
            self.assertFalse(danger.has_class('-error'))
            danger.variant = 'error'
            self.assertTrue(danger.has_class('-error'))
            danger.variant = 'danger'
            self.assertTrue(danger.has_class('-danger'))
            self.assertTrue(danger.has_class('-error'))
            danger.focus()
            await pilot.press('enter')
            self.assertEqual(app.pressed, ['danger'])

    async def test_focus_follows_outer_button_edges_through_hover_and_press(self):
        app = ButtonApp()
        async with app.run_test(size=(100, 40)) as pilot:
            for theme in ('textual-dark', 'textual-light', 'ansi-dark', 'ansi-light'):
                app.theme = theme
                for selector in ('#cancel', '#connect', '#success', '#warning', '#error', '#danger', '#flat', '#flat-primary', '#square'):
                    button = app.query_one(selector)
                    button.focus()
                    await pilot.pause()
                    size = button.region.size
                    for hovered, active in ((False, False), (True, False), (True, True), (False, True)):
                        await pilot.hover(selector if hovered else '#disabled')
                        button.set_class(active, '-active')
                        await pilot.pause()
                        with self.subTest(theme=theme, button=selector, hovered=hovered, active=active):
                            self.assertEqual(button.region.size, size)
                            self.assertFalse(button.rich_style.reverse)
                            lines = button.render_lines(Region(0, 0, size.width, size.height))
                            button_background = button.background_colors[1].rich_color
                            for segment in lines[0]:
                                self.assertEqual(segment.style.bgcolor, button_background)
                                self.assertTrue(segment.style.overline)
                            self.assertEqual(lines[0].text, '▏' + ' ' * (size.width - 2) + '▕')
                            self.assertEqual(lines[-1].text, '🭼' + '▁' * (size.width - 2) + '🭿')
                            for segment in lines[-1]:
                                self.assertFalse(segment.style.underline)
                            for line in lines[1:-1]:
                                self.assertTrue(line.text.startswith('▏'))
                                self.assertTrue(line.text.endswith('▕'))
                    button.remove_class('-active')

    async def test_thin_focus_frame_crops_without_changing_border_background(self):
        app = ButtonApp()
        async with app.run_test(size=(100, 40)) as pilot:
            for selector in ('#connect', '#flat', '#square'):
                button = app.query_one(selector)
                button.focus()
                await pilot.pause()
                width, height = button.region.size
                full = button.render_lines(Region(0, 0, width, height))
                for crop in (Region(0, 0, 1, height), Region(width - 1, 0, 1, height),
                             Region(1, 0, width - 2, height), Region(0, 1, width, 1),
                             Region(0, height - 1, width, 1)):
                    actual = button.render_lines(crop)
                    expected = [line.crop(crop.x, crop.right) for line in full[crop.y:crop.bottom]]
                    self.assertEqual([list(line.simplify()) for line in actual],
                                     [list(line.simplify()) for line in expected])

    async def test_compact_buttons_keep_labels_and_size_during_press(self):
        class CompactApp(App):
            def compose(self):
                for flat in (False, True):
                    for variant in ('default', 'primary', 'success', 'warning', 'error'):
                        yield AppButton('Label', compact=True, flat=flat, variant=variant)
                yield AppButton('+', square=True, compact=True)
                yield AppButton('+', square=True, id='one-row')

        app = CompactApp()
        async with app.run_test(size=(100, 40)) as pilot:
            app.query_one('#one-row').styles.height = 1
            for theme in ('textual-dark', 'textual-light', 'ansi-dark', 'ansi-light'):
                app.theme = theme
                for button in app.query(AppButton):
                    app.set_focus(None)
                    await pilot.pause()
                    size = button.region.size
                    for focused in (False, True):
                        app.set_focus(button if focused else None)
                        await pilot.hover(button)
                        for active in (False, True):
                            button.set_class(active, '-active')
                            await pilot.pause()
                            with self.subTest(theme=theme, button=button, focused=focused, active=active):
                                self.assertEqual(button.region.size, size)
                                self.assertEqual(size.height, 1)
                                lines = button.render_lines(Region(0, 0, size.width, size.height))
                                self.assertIn(str(button.label), lines[0].text)
                    button.remove_class('-active')

    async def test_unfocused_sides_fill_the_button_background_without_shifting_focus(self):
        app = ButtonApp()
        async with app.run_test(size=(100, 40)) as pilot:
            for theme in ('textual-dark', 'textual-light'):
                app.theme = theme
                for selector in ('#cancel', '#connect', '#success', '#warning', '#error'):
                    button = app.query_one(selector)
                    for hovered in (False, True):
                        app.set_focus(None)
                        await pilot.hover(selector if hovered else '#disabled')
                        await pilot.pause()
                        with self.subTest(theme=theme, button=selector, hovered=hovered):
                            region = button.region
                            background = app.screen.get_style_at(region.x + region.width // 2, region.y + 1).bgcolor
                            for x in (region.x, region.right - 1):
                                self.assertEqual(app.screen.get_style_at(x, region.y + 1).bgcolor, background)
                                for y in (region.y, region.bottom - 1):
                                    self.assertEqual(app.screen.get_style_at(x, y).bgcolor,
                                        app.screen.get_style_at(region.x + region.width // 2, y).bgcolor)
                            content_width = button.content_size.width
                            button.focus()
                            await pilot.pause()
                            self.assertEqual(button.content_size.width, content_width)

    async def test_icon_action_keeps_localized_description(self):
        app = ButtonApp()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            button = app.query_one('#icon')
            self.assertEqual(str(button.label), '\uf067')
            self.assertEqual(button.region.width, 6)
            self.assertTrue(button.square)
            app.language = 'fr'
            button.apply_language()
            self.assertEqual(str(button.label), '\uf067')
            self.assertEqual(str(button.tooltip), 'Nouvelle note')
            button.focus()
            await pilot.press('enter')
            self.assertEqual(app.pressed, ['icon'])

    async def test_square_buttons_follow_cell_proportions_and_button_height(self):
        app=ButtonApp()
        async with app.run_test(size=(100,40)) as pilot:
            for cell_width,cell_height in ((10,20),(10,10),(8,20)):
                app.terminal_capabilities=SimpleNamespace(cell_size=(cell_width,cell_height))
                for selector in ('#square','#square-compact'):
                    button=app.query_one(selector)
                    button.square=False;button.square=True
                await pilot.pause()
                for selector in ('#square','#square-compact'):
                    button=app.query_one(selector)
                    self.assertLessEqual(abs(button.region.width*cell_width-button.region.height*cell_height),cell_width/2)
            button=app.query_one('#square')
            button.styles.height=1;await pilot.pause()
            self.assertEqual(button.region.width,round(cell_height/cell_width))
            button.focus();await pilot.press('enter')
            self.assertEqual(app.pressed,['square'])

    async def test_icon_text_fallback_restores_regular_width_and_explicit_mode_restores_inline_styles(self):
        app=ButtonApp()
        async with app.run_test(size=(100,40)) as pilot:
            button=app.query_one('#icon')
            app.icon_mode='text';button.apply_language();await pilot.pause()
            self.assertFalse(button.square)
            self.assertEqual(str(button.label),'New note')
            self.assertGreaterEqual(button.content_size.width,len('New note'))
            app.icon_mode='unicode';button.apply_language();await pilot.pause()
            self.assertTrue(button.square);self.assertEqual(button.region.width,6)
            plain=app.query_one('#plain')
            plain.styles.width=19;plain.styles.padding=(0,3)
            plain.square=True;await pilot.pause();self.assertEqual(plain.region.width,6)
            self.assertEqual(plain.region.height,3)
            plain.square=False;await pilot.pause()
            self.assertEqual(plain.region.width,19)
            self.assertEqual(tuple(plain.styles.padding),(0,3,0,3))

    async def test_focus_outline_uses_variant_palette_instead_of_accent(self):
        app = ButtonApp()
        async with app.run_test(size=(100, 50)) as pilot:
            for theme in ('textual-dark', 'textual-light', 'ansi-dark', 'ansi-light'):
                app.theme = theme
                colors = app.get_css_variables()
                from textual.color import Color
                for selector, palette in (('#cancel', 'foreground'), ('#connect', 'primary'),
                                          ('#success', 'success'), ('#warning', 'warning'),
                                          ('#error', 'error-muted'), ('#danger', 'error-muted')):
                    button = app.query_one(selector)
                    button.focus()
                    await pilot.hover(button)
                    for active in (False, True):
                        button.set_class(active, '-active')
                        await pilot.pause()
                        value = colors[palette].split()
                        expected = Color.parse(value[0])
                        if len(value) > 1 and not value[0].startswith('ansi_'):
                            expected = expected.with_alpha(float(value[1].rstrip('%')) / 100)
                        self.assertEqual(button.styles.border_top[1], expected)
                    button.remove_class('-active')

    async def test_danger_hover_and_press_tint_the_entire_square_uniformly(self):
        class CloseApp(App):
            def compose(self):
                yield Button('×', variant='danger', square=True, id='close')
                yield Button('Other', id='other')

        app = CloseApp()
        async with app.run_test(size=(60, 20)) as pilot:
            close = app.query_one('#close')
            for theme in ('textual-dark', 'textual-light', 'ansi-dark', 'ansi-light'):
                app.theme = theme
                for focused in (False, True):
                    (close if focused else app.query_one('#other')).focus()
                    await pilot.hover(close)
                    for active in (False, True):
                        close.set_class(active, '-active')
                        await pilot.pause()
                        region = close.region
                        backgrounds = [app.screen.get_style_at(x, region.y + 1).bgcolor
                                       for x in range(region.x, region.right)]
                        self.assertEqual(len(set(backgrounds)), 1, (theme, focused, active))
                    close.remove_class('-active')

    async def test_focus_and_hover_preserve_label_space(self):
        app = ButtonApp()
        async with app.run_test(size=(100, 40)) as pilot:
            button = app.query_one('#connect')
            button.styles.width = 24
            app.set_focus(None)
            await pilot.hover('#disabled')
            await pilot.pause()
            width = button.content_size.width
            button.focus()
            await pilot.hover('#connect')
            await pilot.pause()
            self.assertEqual(button.content_size.width, width)
            self.assertGreaterEqual(width, button.label.cell_length)

    async def test_hover_keeps_focus_on_outer_edges_for_all_variants(self):
        app = ButtonApp()
        async with app.run_test(size=(100, 40)) as pilot:
            for selector in ('#connect', '#cancel', '#flat', '#plain', '#success', '#warning', '#error', '#danger', '#flat-primary'):
                with self.subTest(button=selector):
                    button = app.query_one(selector)
                    await pilot.hover('#disabled')
                    button.focus()
                    await pilot.pause()
                    await pilot.hover(selector)
                    await pilot.pause()
                    self.assertTrue(button.mouse_hover)
                    self.assertFalse(button.rich_style.reverse)
                    for edge in ('top', 'bottom', 'left', 'right'):
                        self.assertEqual(getattr(button.styles, f'border_{edge}')[0],
                                         'blank')

    async def test_focus_does_not_invert_labels_across_themes_and_styles(self):
        app = ButtonApp()
        async with app.run_test() as pilot:
            for theme in app.available_themes:
                app.theme = theme
                for selector in ("#connect", "#cancel", "#flat", "#plain"):
                    with self.subTest(theme=theme, button=selector):
                        button = app.query_one(selector)
                        app.set_focus(None)
                        await pilot.pause()
                        button.focus()
                        await pilot.pause()
                        self.assertTrue(button.has_focus)
                        self.assertFalse(button.rich_style.reverse)
                        self.assertEqual(button.styles.border_top[0], 'blank')
                        self.assertGreater(button.styles.background_tint.a, 0)
                        self.assertEqual(button.styles.border_left, button.styles.border_top)
                        self.assertEqual(button.styles.border_right, button.styles.border_top)
                        self.assertEqual(button.styles.border_bottom, button.styles.border_top)

    async def test_click_and_keyboard_keep_activation_and_disabled_behavior(self):
        app = ButtonApp()
        async with app.run_test() as pilot:
            await pilot.click("#connect")
            await pilot.pause()
            await pilot.press("tab", "enter")
            await pilot.pause()
            await pilot.click("#disabled")
            await pilot.pause()
            self.assertEqual(app.pressed, ["connect", "cancel"])
            self.assertFalse(app.query_one("#connect").allow_select)

    async def test_labels_still_follow_language_and_dynamic_updates(self):
        app = ButtonApp()
        async with app.run_test() as pilot:
            button = app.query_one("#cancel")
            app.language = "fr"
            button.apply_language()
            self.assertEqual(str(button.label), "Annuler")
            button.set_source_label("Reconnect")
            self.assertEqual(str(button.label), "Reconnecter")
            await pilot.pause()
