"""Selectors share visible-option filtering and locale behavior."""

import unittest

from rich.text import Text
from textual.app import App

from ft_tui.ui.select import AppSelect
from ft_tui.ui.components import Select


class SelectorApp(App):
    language = "en"

    def compose(self):
        yield Select([("Cancel", "cancel"), ("Save settings", "save"), (" ", "space"),
                      (Text("\t"), "tab"), ("Empty value", " ")], value="cancel", id="choices")
        yield AppSelect([], prompt="Loading", id="loading")


class SharedSelectTests(unittest.IsolatedAsyncioTestCase):
    async def test_keyboard_choices_and_translation_have_no_blank_option(self):
        app = SelectorApp()
        async with app.run_test() as pilot:
            selector = app.query_one("#choices", AppSelect)
            self.assertEqual([value for _, value in selector._options], ["cancel", "save"])
            self.assertEqual(selector.value, "cancel")
            selector.focus()
            await pilot.press("enter", "down", "enter")
            self.assertEqual(selector.value, "save")
            app.language = "fr"
            selector.apply_language()
            self.assertEqual(selector.value, "save")
            self.assertEqual(selector._options[0][0], "Annuler")
            self.assertEqual(len(selector._options), 2)

    async def test_language_refresh_does_not_emit_selection_changes(self):
        class TrackingApp(SelectorApp):
            def __init__(self):
                super().__init__()
                self.selection_events = []
            def on_select_changed(self, event):
                self.selection_events.append((event.select.id, event.value))
        app = TrackingApp()
        async with app.run_test() as pilot:
            selector = app.query_one('#choices', Select)
            selector.value = 'save'
            await pilot.pause()
            app.selection_events.clear()
            app.language = 'fr'
            selector.apply_language()
            await pilot.pause()
            self.assertEqual(selector.value, 'save')
            self.assertEqual(app.selection_events, [])
            # Deliberate user choices still produce their normal event.
            selector.focus()
            await pilot.press('enter', 'up', 'enter')
            await pilot.pause()
            self.assertEqual(app.selection_events, [('choices', 'cancel')])

    async def test_async_options_can_be_loaded_cleared_and_reloaded(self):
        app = SelectorApp()
        async with app.run_test():
            selector = app.query_one("#loading", AppSelect)
            self.assertIs(selector.value, AppSelect.NULL)
            self.assertEqual(selector._options, [])
            selector.set_options([(" ", "invalid"), ("Project", 42)])
            self.assertIs(selector.value, AppSelect.NULL)
            self.assertEqual(selector._options, [("Project", 42)])
            selector.set_options([])
            self.assertIs(selector.value, AppSelect.NULL)
            selector.set_options([("Other project", 43)])
            self.assertIs(selector.value, AppSelect.NULL)

    async def test_translated_prompt_keeps_empty_and_populated_choices_intact(self):
        from textual.widgets._select import SelectOverlay
        app = SelectorApp()
        async with app.run_test():
            selector = app.query_one('#loading', AppSelect)
            selector.prompt = 'Chargement'
            self.assertEqual(selector.query_one(SelectOverlay).option_count, 0)
            self.assertIn('Chargement', str(selector.query_one('SelectCurrent Static').render()))
            selector.set_options([('France - Paris', '31')])
            selector.prompt = 'Choisir un campus'
            self.assertEqual(str(selector.query_one(SelectOverlay).get_option_at_index(0).prompt), 'France - Paris')
