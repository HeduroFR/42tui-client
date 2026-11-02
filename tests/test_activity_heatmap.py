"""Activity heatmap gradient and per-day hover details."""
import unittest
from ft_tui.features.dashboard.views.heatmap import ActivityHeatmap, activity_color, format_duration


class ActivityHeatmapTests(unittest.TestCase):
    def test_gradient_brightens_with_hours_and_skips_zero_or_missing(self):
        self.assertIsNone(activity_color(None))
        self.assertIsNone(activity_color(0))
        low, high = activity_color(600), activity_color(8 * 3600)
        self.assertNotEqual(low, high)
        self.assertLess(sum(int(low[i:i + 2], 16) for i in (1, 3, 5)),
                        sum(int(high[i:i + 2], 16) for i in (1, 3, 5)))
        self.assertEqual(format_duration(0), '0m')
        self.assertEqual(format_duration(3660), '1h 01m')

    def test_hover_maps_day_cells_and_ignores_labels_and_header(self):
        heatmap = ActivityHeatmap()
        heatmap.set_snapshot('grid', {(1, 2): 'Wed 04 Nov · 2h 00m\nWeek to date: 4h 00m'})

        class Event:
            x = 12
            y = 2

        heatmap.on_mouse_move(Event())
        self.assertIn('Wed 04 Nov', heatmap.tooltip)
        self.assertEqual(heatmap.cell_tooltip(1, 2), heatmap.tooltip)
        Event.x = 11
        heatmap.on_mouse_move(Event())
        self.assertIsNone(heatmap.tooltip)
        Event.x, Event.y = 12, 0
        heatmap.on_mouse_move(Event())
        self.assertIsNone(heatmap.tooltip)
