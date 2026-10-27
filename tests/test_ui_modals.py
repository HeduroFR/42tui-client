"""Modal overlays must not inherit the main screen's one-column gutter."""
import unittest

from textual.app import App
from textual.containers import Vertical
from textual.widgets import Static

from ft_tui.ui.modal import AppModal
from ft_tui.ui.styles.base import BASE_CSS


class Dialog(AppModal[str]):
    DEFAULT_CSS = '#dialog { width: 44; height: 12; background: $surface; }'
    def compose(self):
        with Vertical(id='dialog'):
            yield Static('Dialog')


class Harness(App):
    CSS = BASE_CSS

    def compose(self):
        yield Static('Background', id='background')


class ModalLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_overlay_uses_full_viewport_and_preserves_background_geometry(self):
        app = Harness()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            background = app.query_one('#background')
            before = background.region
            self.assertEqual(before.x, 1)
            results = []
            modal = Dialog()
            await app.push_screen(modal, results.append)
            await pilot.pause()
            self.assertEqual(tuple(modal.styles.padding), (0, 0, 0, 0))
            self.assertEqual(modal.content_region.x, 0)
            self.assertEqual(modal.content_region.width, 100)
            self.assertEqual(background.region, before)
            self.assertTrue(modal.has_class('app-modal'))
            dialog=modal.query_one('#dialog').region
            self.assertLessEqual(abs(dialog.x-(100-dialog.right)),1)
            self.assertLessEqual(abs(dialog.y-(35-dialog.bottom)),1)
            self.assertAlmostEqual(modal.styles.background.a,.55,places=2)
            modal.dismiss('done')
            await pilot.pause()
            self.assertEqual(results, ['done'])
            self.assertEqual(background.region, before)
