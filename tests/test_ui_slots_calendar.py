import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from textual.app import App

from ft_tui.features.corrections.model import Slot, interval
from ft_tui.features.corrections.calendar import SlotsCalendar

DAY = date(2026, 10, 26)


class Harness(App):
    def __init__(self):
        super().__init__(); self.edits = []; self.deletes = []; self.choices = []

    def compose(self):
        calendar = SlotsCalendar(DAY, timezone.utc)
        calendar.writable = True
        yield calendar

    def on_slots_calendar_edit_requested(self, event): self.edits.append(event)
    def on_slots_calendar_delete_requested(self, event): self.deletes.append(event)
    def on_slots_calendar_choose_requested(self, event): self.choices.append(event.slots)


def position(cal, day, row):
    x = next(start + 2 for d, start, width in cal.columns if d == day)
    return x, row - round(cal.scroll_offset.y)


class CalendarTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        clock = patch('ft_tui.features.corrections.calendar.datetime', wraps=datetime)
        self.clock = clock.start()
        self.clock.now.return_value = datetime(2026, 10, 25, 10, tzinfo=timezone.utc)
        self.addCleanup(clock.stop)

    async def test_first_available_quarter_and_nearby_existing_slot(self):
        self.clock.now.return_value = datetime(2026, 10, 26, 10, 18, tzinfo=timezone.utc)
        app = Harness()
        async with app.run_test(size=(110, 26)) as pilot:
            cal = app.query_one(SlotsCalendar)
            self.assertEqual(cal.first_row(0), 43)
            cal.request_edit(0, 42)
            await pilot.pause()
            self.assertEqual(app.edits, [])
            cal.request_edit(0, 43)
            await pilot.pause()
            self.assertEqual(app.edits[0].begin.hour, 10)
            self.assertEqual(app.edits[0].begin.minute, 45)
            self.assertEqual(cal.first_row(0, adding=False), 41)
            nearby = Slot(('1',), *interval(DAY, 41, 44, timezone.utc))
            cal.set_slots((nearby,)); cal.show_time(40); await pilot.pause()
            await pilot.mouse_down(cal, offset=position(cal, 0, 42))
            await pilot.hover(cal, offset=position(cal, 0, 43))
            await pilot.mouse_up(cal, offset=position(cal, 0, 43)); await pilot.pause()
            self.assertEqual(app.deletes[0].slots, (nearby,))
            self.clock.now.return_value = datetime(2026, 10, 26, 23, 48, tzinfo=timezone.utc)
            self.assertEqual(cal.first_row(0), 96)
            self.assertEqual(cal.first_row(1), 1)

    async def test_redraw_reuses_cells_and_invalidates_deleted_slots(self):
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            cal = app.query_one(SlotsCalendar)
            slot = Slot(('1',), *interval(DAY, 36, 39, timezone.utc))
            cal.set_slots((slot,)); await p.pause()
            y = 36 - round(cal.scroll_offset.y)
            line = cal.render_line(y)
            with patch.object(cal, 'slots_at', wraps=cal.slots_at) as lookup:
                self.assertIs(cal.render_line(y), line)
                self.assertEqual(lookup.call_count, 0)
            cal.set_slots(())
            self.assertNotIn('09:00–10:00', cal.render_line(y).text)
            self.assertEqual(cal.slots_at(0, 36), ())
            cal.set_slots((slot,)); cal.set_week(date(2026, 11, 2))
            self.assertEqual(cal.slots_at(0, 36), ())

    async def test_week_uses_one_time_axis_after_scrolling(self):
        app = Harness()
        async with app.run_test(size=(166, 26)) as p:
            cal = app.query_one(SlotsCalendar)
            await p.pause()
            for row in (32, 53, 70):
                cal.show_time(row); await p.pause()
                for day, x, _ in cal.columns:
                    self.assertEqual(cal.cell(x + 2, 0), (day, row))
                self.assertEqual(cal.render_line(0).text[:5].strip(),
                                 f'{row // 4:02d}:{row % 4 * 15:02d}')
            self.assertEqual(cal.day_count, 7)
            self.assertLessEqual(max(w for _, _, w in cal.columns) - min(w for _, _, w in cal.columns), 1)

    async def test_click_opens_editor_and_never_deletes(self):
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            cal = app.query_one(SlotsCalendar)
            slot = Slot(('1',), *interval(DAY, 36, 39, timezone.utc))
            cal.set_slots((slot,)); await p.pause()
            await p.click(cal, offset=position(cal, 0, 37)); await p.pause()
            self.assertEqual(app.deletes, [])
            self.assertEqual(len(app.edits), 1)
            self.assertIs(app.edits[0].slot, slot)
            self.assertTrue(app.edits[0].form)

    async def test_drag_selects_available_blocks_for_direct_deletion_and_clears_styling(self):
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            cal = app.query_one(SlotsCalendar)
            first = Slot(('1',), *interval(DAY, 36, 39, timezone.utc))
            booked = Slot(('2',), *interval(DAY, 40, 41, timezone.utc), True)
            last = Slot(('3',), *interval(DAY, 44, 47, timezone.utc))
            cal.set_slots((first, booked, last)); await p.pause()
            begin, end = position(cal, 0, 37), position(cal, 0, 45)
            await p.mouse_down(cal, offset=begin); await p.hover(cal, offset=end)
            self.assertEqual(cal.delete_preview, (first, last))
            self.assertIn('Delete slot', cal.render_line(position(cal, 0, 36)[1]).text)
            await p.mouse_up(cal, offset=end); await p.pause()
            self.assertEqual(len(app.deletes), 1)
            self.assertEqual(app.deletes[0].slots, (first, last))
            self.assertTrue(app.deletes[0].direct)
            self.assertEqual(app.edits, [])
            self.assertEqual(cal.delete_preview, ())
            self.assertIsNone(cal.preview)
            for segment in cal.render_line(begin[1]):
                self.assertFalse(segment.style.underline)
            cal.focus(); await p.press('down'); await p.pause()
            _, y = position(cal, cal.day, cal.row)
            x = cal.columns[0][1]
            self.assertTrue(any(segment.style.underline for segment in cal.render_line(y).crop(x, x + 5)))

    async def test_cancel_horizontal_motion_and_cross_day_drag_never_delete(self):
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            cal = app.query_one(SlotsCalendar)
            cal.set_slots((Slot(('1',), *interval(DAY, 36, 39, timezone.utc)),))
            await p.pause()
            begin, end = position(cal, 0, 36), position(cal, 0, 39)
            await p.mouse_down(cal, offset=begin); await p.hover(cal, offset=end)
            await p.press('escape'); await p.mouse_up(cal, offset=end); await p.pause()
            await p.mouse_down(cal, offset=begin); await p.hover(cal, offset=(begin[0] + 2, begin[1]))
            await p.mouse_up(cal, offset=(begin[0] + 2, begin[1])); await p.pause()
            await p.mouse_down(cal, offset=begin); await p.hover(cal, offset=position(cal, 1, 39))
            await p.mouse_up(cal, offset=position(cal, 1, 39)); await p.pause()
            self.assertEqual(app.deletes, [])
            self.assertEqual(cal.delete_preview, ())

    async def test_empty_click_opens_editor_but_drag_publishes_directly(self):
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            cal = app.query_one(SlotsCalendar)
            await p.pause()
            cal.show_time(20); await p.pause()
            await p.click(cal, offset=position(cal, 0, 20)); await p.pause()
            self.assertEqual((app.edits[-1].begin.hour, app.edits[-1].end.minute), (5, 30))
            self.assertTrue(app.edits[-1].form)
            begin, end = position(cal, 0, 24), position(cal, 0, 27)
            await p.mouse_down(cal, offset=begin); await p.hover(cal, offset=end)
            self.assertIsNotNone(cal.preview)
            await p.mouse_up(cal, offset=end); await p.pause()
            self.assertEqual(app.edits[-1].begin.strftime('%H:%M'), '06:00')
            self.assertEqual(app.edits[-1].end.strftime('%H:%M'), '07:00')
            self.assertFalse(app.edits[-1].form)
            self.assertEqual(app.deletes, [])

    async def test_escape_and_cross_day_drag_do_not_open_editor(self):
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            cal = app.query_one(SlotsCalendar); await p.pause()
            begin, end = position(cal, 0, 36), position(cal, 0, 40)
            await p.mouse_down(cal, offset=begin); await p.hover(cal, offset=end)
            await p.press('escape'); await p.mouse_up(cal, offset=end); await p.pause()
            await p.mouse_down(cal, offset=begin); await p.hover(cal, offset=position(cal, 1, 40))
            await p.mouse_up(cal, offset=position(cal, 1, 40)); await p.pause()
            self.assertEqual(app.edits, [])

    async def test_booked_past_and_read_only_slots_cannot_be_edited(self):
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            cal = app.query_one(SlotsCalendar); await p.pause()
            slot = Slot(('1',), *interval(DAY, 36, 39, timezone.utc), True)
            cal.set_slots((slot,))
            await p.click(cal, offset=position(cal, 0, 36)); await p.pause()
            self.clock.now.return_value = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
            await p.click(cal, offset=position(cal, 0, 40)); await p.pause()
            cal.writable = False
            await p.click(cal, offset=position(cal, 1, 40)); await p.pause()
            self.assertEqual(app.edits, []); self.assertEqual(app.deletes, [])

    async def test_dst_folds_require_a_slot_choice_and_gap_cannot_be_created(self):
        self.clock.now.return_value = datetime(2026, 10, 24, 10, tzinfo=timezone.utc)
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            cal = app.query_one(SlotsCalendar)
            await p.pause()
            cal.zone = ZoneInfo('Europe/Paris'); cal.set_week(date(2026, 10, 19))
            first = Slot(('1',), datetime(2026, 10, 25, 0, 15, tzinfo=timezone.utc), datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc))
            second = Slot(('2',), datetime(2026, 10, 25, 1, 15, tzinfo=timezone.utc), datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc))
            cal.set_slots((first, second)); cal.show_time(8); await p.pause()
            await p.click(cal, offset=position(cal, 6, 9)); await p.pause()
            self.assertEqual(app.choices, [(first, second)])
            cal.set_slots(()); cal.set_week(date(2026, 3, 23))
            self.clock.now.return_value = datetime(2026, 3, 28, tzinfo=timezone.utc)
            await p.click(cal, offset=position(cal, 6, 9)); await p.pause()
            self.assertEqual(app.edits, [])

    async def test_keyboard_and_narrow_view_preserve_the_shared_timeline(self):
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            cal = app.query_one(SlotsCalendar); cal.focus(); await p.pause()
            cal.row = 36; await p.press('right', 'enter'); await p.pause()
            self.assertEqual(app.edits[-1].begin.day, 27)
            before = cal.scroll_offset.y
            await p.press('pagedown'); await p.pause()
            self.assertGreater(cal.scroll_offset.y, before)
            await p.resize_terminal(44, 20); await p.pause()
            self.assertEqual(cal.day_count, 1)
            self.assertEqual(cal.cell(10, 0), (1, round(cal.scroll_offset.y)))
            cal.show_time(0); await p.pause()
            self.assertEqual(cal.cell(10, 0), (1, 0))

    async def test_tall_view_has_no_folded_or_blank_time_ranges(self):
        app = Harness()
        async with app.run_test(size=(110, 60)) as p:
            cal = app.query_one(SlotsCalendar)
            cal.show_time(36); await p.pause()
            for y in range(60):
                self.assertIsNotNone(cal.cell(10, y))
                self.assertEqual(cal.cell(10, y)[1], y + round(cal.scroll_offset.y))
            slot = Slot(('1',), *interval(DAY, 40, 43, timezone.utc))
            cal.set_slots((slot,))
            self.assertEqual(sum(cal.render_line(y).text.count('10:00–11:00') for y in range(60)), 1)
