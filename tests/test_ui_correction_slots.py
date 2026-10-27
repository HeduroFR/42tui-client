import threading
import unittest
from datetime import datetime, timedelta, timezone
from textual.app import App
from textual.widgets import Static, TabbedContent, TabPane
from unittest.mock import Mock
from ft_tui.ui.correction_slots import CorrectionSlotsWorkspace, SlotEditor, SlotPicker, rounded_slot_time
from ft_tui.ui.components import Input, Select
from ft_tui.ui.slots_calendar import SlotsCalendar
from ft_tui.slots.model import Slot, local_zone

B = datetime.now(timezone.utc).replace(second=0, microsecond=0, minute=0) + timedelta(days=1)
E = B + timedelta(hours=1)
SLOT = Slot(('1',), B, E)

class Provider:
    def __init__(self):
        self.rows = (); self.calls = []; self.gate = None; self.started = threading.Event(); self.fail = False
    def get_correction_slots(self, begin, end):
        if self.fail: raise RuntimeError('unavailable')
        return {'account_id': '42', 'can_write': True, 'slots': self.rows}
    def save_correction_slot(self, slot, begin, end):
        self.calls.append(('save', slot, begin, end)); self.started.set()
        if self.gate: self.gate.wait(5)
        self.rows = (Slot(('1',), begin, end),)
        return {'status': 'saved'}
    def delete_correction_slot(self, slot):
        self.calls.append(('delete', slot)); self.rows = (); return {'status': 'saved'}

class Harness(App):
    account_id = '42'; account_generation = 0; account_connected = True; language = 'en'
    def __init__(self):
        super().__init__(); self.provider = Provider()
    def compose(self):
        yield CorrectionSlotsWorkspace()

class WorkspaceTests(unittest.IsolatedAsyncioTestCase):
    def test_rounding_supports_every_minute_and_day_rollover(self):
        for minute in range(60):
            rounded = rounded_slot_time(f'2026-10-26 10:{minute:02d}', timezone.utc)
            self.assertIn(rounded.minute, (0, 15, 30, 45))
        self.assertEqual(rounded_slot_time('2026-10-26 10:07', timezone.utc).strftime('%H:%M'), '10:00')
        self.assertEqual(rounded_slot_time('2026-10-26 10:08', timezone.utc).strftime('%H:%M'), '10:15')
        self.assertEqual(rounded_slot_time('2026-10-26 23:58', timezone.utc),
                         datetime(2026, 10, 27, tzinfo=timezone.utc))
        from zoneinfo import ZoneInfo
        for value in ('2026-03-29 02:58', '2026-10-25 02:08', '2026-10-25 01:58'):
            with self.assertRaises(ValueError):
                rounded_slot_time(value, ZoneInfo('Europe/Paris'))

    async def test_editor_rounds_text_on_blur_and_before_publishing(self):
        app = Harness()
        async with app.run_test(size=(60, 40)) as p:
            await p.pause()
            ws = app.query_one(CorrectionSlotsWorkspace)
            ws.open_editor(B, E); await p.pause()
            editor = app.screen
            begin = editor.query_one('#slot-editor-begin', Input)
            end = editor.query_one('#slot-editor-end', Input)
            begin.value = B.astimezone(ws.zone).replace(minute=8).strftime('%Y-%m-%d %H:%M')
            begin.focus(); end.focus(); await p.pause()
            self.assertTrue(begin.value.endswith(':15'))
            end.value = E.astimezone(ws.zone).replace(minute=52).strftime('%Y-%m-%d %H:%M')
            await p.click('#slot-editor-publish'); await p.pause(.2)
            self.assertEqual(len(app.provider.calls), 1)
            self.assertEqual(app.provider.calls[0][2].astimezone(ws.zone).minute, 15)
            self.assertEqual(app.provider.calls[0][3].astimezone(ws.zone).minute, 45)
            self.assertNotIsInstance(app.screen, SlotEditor)

    async def test_editor_rejects_a_range_collapsed_by_rounding(self):
        app = Harness()
        async with app.run_test(size=(60, 40)) as p:
            await p.pause()
            ws = app.query_one(CorrectionSlotsWorkspace)
            ws.open_editor(B, E); await p.pause()
            editor = app.screen
            for key, minute in (('begin', 1), ('end', 6)):
                editor.query_one(f'#slot-editor-{key}', Input).value = B.astimezone(ws.zone).replace(minute=minute).strftime('%Y-%m-%d %H:%M')
            await p.click('#slot-editor-publish'); await p.pause()
            self.assertIs(app.screen, editor)
            self.assertEqual(app.provider.calls, [])

    async def test_drag_deletes_without_a_modal_but_click_still_opens_editor(self):
        app = Harness()
        # Keep the complete gesture on one local day, even when run at night.
        begin = (datetime.now(local_zone()) + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0,
        )
        end = begin + timedelta(hours=1)
        available = Slot(('1',), begin, end)
        booked = Slot(('2',), begin + timedelta(hours=1), end + timedelta(hours=1), True)
        other = Slot(('3',), begin + timedelta(hours=2), end + timedelta(hours=2))
        untouched = Slot(('4',), begin + timedelta(hours=4), end + timedelta(hours=4))
        app.provider.rows = (available, booked, other, untouched)
        def delete(slot):
            app.provider.calls.append(('delete', slot))
            app.provider.rows = tuple(s for s in app.provider.rows if s != slot)
            return {'status': 'saved'}
        app.provider.delete_correction_slot = delete
        async with app.run_test(size=(60, 40)) as p:
            await p.pause()
            ws = app.query_one(CorrectionSlotsWorkspace); cal = app.query_one(SlotsCalendar)
            local = begin.astimezone(ws.zone)
            ws.week = local.date() - timedelta(days=local.weekday())
            cal.set_week(ws.week); cal.set_day(local.weekday())
            cal.show_time(local.hour * 4); await p.pause()
            first = local.hour * 4 - round(cal.scroll_offset.y)
            await p.mouse_down(cal, offset=(10, first + 1))
            await p.hover(cal, offset=(10, first + 9))
            await p.mouse_up(cal, offset=(10, first + 9)); await p.pause(.2)
            self.assertNotIsInstance(app.screen, SlotEditor)
            self.assertEqual(app.provider.calls, [('delete', available), ('delete', other)])
            self.assertEqual(cal.slots, (booked, untouched))
            await p.click(cal, offset=(10, first + 17)); await p.pause()
            self.assertIsInstance(app.screen, SlotEditor)
            self.assertEqual(app.screen.slot, untouched)
            self.assertEqual(len(app.provider.calls), 2)

    async def test_partial_drag_deletion_reconciles_before_another_edit(self):
        app = Harness()
        other = Slot(('2',), B + timedelta(hours=2), E + timedelta(hours=2))
        app.provider.rows = (SLOT, other)
        def delete(slot):
            app.provider.calls.append(('delete', slot))
            if slot == other:
                raise RuntimeError('connection lost')
            app.provider.rows = (other,)
            return {'status': 'saved'}
        app.provider.delete_correction_slot = delete
        async with app.run_test(size=(110, 40)) as p:
            await p.pause()
            ws = app.query_one(CorrectionSlotsWorkspace)
            await ws.change(SLOT, delete=True, delete_slots=(SLOT, other))
            self.assertEqual(app.query_one(SlotsCalendar).slots, (other,))
            self.assertTrue(ws.trusted)
            self.assertIn('Only part', str(app.query_one('#slots-status', Static).render()))

    async def test_first_week_prefetches_before_the_tab_is_opened(self):
        class TabsHarness(Harness):
            def compose(self):
                with TabbedContent(initial='overview'):
                    with TabPane('Overview', id='overview'):
                        yield Static('Overview')
                    with TabPane('Slots', id='correction-slots'):
                        yield CorrectionSlotsWorkspace()
        app = TabsHarness()
        original = app.provider.get_correction_slots
        app.provider.get_correction_slots = Mock(wraps=original)
        async with app.run_test(size=(110, 40)) as p:
            await p.pause()
            self.assertEqual(app.query_one(TabbedContent).active, 'overview')
            self.assertTrue(app.query_one(CorrectionSlotsWorkspace).trusted)
            self.assertEqual(app.provider.get_correction_slots.call_count, 1)
            app.query_one(TabbedContent).active = 'correction-slots'
            await p.pause()
            self.assertEqual(app.provider.get_correction_slots.call_count, 1)

    async def test_pending_delete_renders_immediately_and_keeps_local_navigation(self):
        app = Harness()
        other = Slot(('2',), B + timedelta(hours=2), E + timedelta(hours=2))
        app.provider.rows = (SLOT, other)
        app.provider.get_correction_slots = Mock(wraps=app.provider.get_correction_slots)
        gate, started = threading.Event(), threading.Event()
        def delayed_delete(slot):
            started.set()
            gate.wait(5)
            app.provider.rows = (other,)
            return {'status': 'saved'}
        app.provider.delete_correction_slot = delayed_delete
        try:
            async with app.run_test(size=(60, 32)) as p:
                await p.pause()
                ws = app.query_one(CorrectionSlotsWorkspace); cal = app.query_one(SlotsCalendar)
                ws.run_worker(ws.change(SLOT, delete=True)); await p.pause()
                self.assertTrue(started.is_set()); self.assertTrue(ws.busy)
                self.assertEqual(cal.slots, (other,))
                self.assertIsNotNone(cal.pending); self.assertFalse(cal.writable)
                before = cal.scroll_offset.y
                await p.click('#slots-earlier'); await p.pause()
                self.assertLess(cal.scroll_offset.y, before)
                day = cal.day
                await p.click('#slots-day-next' if day < 6 else '#slots-day-prev'); await p.pause()
                self.assertNotEqual(cal.day, day)
                gate.set(); await p.pause(.2)
                self.assertFalse(ws.busy); self.assertTrue(cal.writable)
                self.assertIsNone(cal.pending); self.assertEqual(cal.slots, (other,))
                self.assertEqual(app.provider.get_correction_slots.call_count, 1)
        finally:
            gate.set()

    async def test_failed_delete_restores_the_authoritative_snapshot(self):
        app = Harness(); app.provider.rows = (SLOT,)
        def failed_delete(slot):
            raise RuntimeError('connection lost')
        app.provider.delete_correction_slot = failed_delete
        async with app.run_test(size=(110, 40)) as p:
            await p.pause()
            ws = app.query_one(CorrectionSlotsWorkspace)
            await ws.change(SLOT, delete=True)
            self.assertEqual(app.query_one(SlotsCalendar).slots, (SLOT,))
            self.assertTrue(ws.trusted)
            app.provider.fail = True
            await ws.change(SLOT, delete=True)
            self.assertEqual(app.query_one(SlotsCalendar).slots, (SLOT,))
            self.assertFalse(ws.trusted)
            self.assertFalse(app.query_one(SlotsCalendar).writable)

    async def test_drag_publishes_exact_times_without_a_modal(self):
        app = Harness()
        async with app.run_test(size=(110, 40)) as p:
            await p.pause()
            ws = app.query_one(CorrectionSlotsWorkspace); cal = app.query_one(SlotsCalendar)
            ws.week = (B + timedelta(days=7)).date()
            ws.week -= timedelta(days=ws.week.weekday())
            cal.set_week(ws.week); ws.update_heading(); await p.pause()
            cal.show_time(20); await p.pause()
            await p.mouse_down(cal, offset=(10, 0)); await p.hover(cal, offset=(10, 1))
            await p.mouse_up(cal, offset=(10, 1)); await p.pause(.2)
            self.assertNotIsInstance(app.screen, SlotEditor)
            self.assertEqual(len(app.provider.calls), 1)
            action, slot, begin, end = app.provider.calls[0]
            self.assertEqual(action, 'save'); self.assertIsNone(slot)
            self.assertEqual(end - begin, timedelta(minutes=30))
            self.assertEqual(begin.astimezone(ws.zone).strftime('%H:%M'), '05:00')
            self.assertEqual(end.astimezone(ws.zone).strftime('%H:%M'), '05:30')
            self.assertFalse(isinstance(app.screen, SlotEditor))

    async def test_day_headings_align_with_the_time_grid(self):
        app = Harness()
        async with app.run_test(size=(110, 26)) as p:
            await p.pause()
            heading = app.query_one('#slots-headings', Static)
            cal = app.query_one(SlotsCalendar)
            for day, start, width in cal.columns:
                label = cal.t((cal.week + timedelta(days=day)).strftime('%a'))
                self.assertIn(label, heading.render_line(0).text[start:start + width])

    async def test_narrow_toolbar_and_tiny_calendar_stay_inside_the_viewport(self):
        app = Harness()
        async with app.run_test(size=(44, 20)) as p:
            await p.pause()
            toolbar = app.query_one('#slots-toolbar')
            self.assertLessEqual(app.query_one('#slots-add').region.right, toolbar.region.right)
            await p.resize_terminal(60, 10); await p.pause()
            ws = app.query_one(CorrectionSlotsWorkspace)
            cal = app.query_one(SlotsCalendar)
            self.assertGreater(cal.size.height, 0)
            self.assertLessEqual(cal.region.bottom, ws.region.bottom)

    async def test_slot_choice_edits_and_explicitly_deletes_the_chosen_slot(self):
        app = Harness()
        other = Slot(('2',), B + timedelta(hours=2), E + timedelta(hours=2))
        app.provider.rows = (SLOT, other)
        async with app.run_test(size=(60, 26)) as p:
            await p.pause()
            cal = app.query_one(SlotsCalendar)
            cal.post_message(SlotsCalendar.ChooseRequested((SLOT, other)))
            await p.pause()
            self.assertIsInstance(app.screen, SlotPicker)
            app.screen.query_one(Select).value = 1
            await p.click('#slot-picker-edit'); await p.pause()
            self.assertIsInstance(app.screen, SlotEditor)
            self.assertEqual(app.screen.slot, other)
            await p.click('#slot-editor-delete'); await p.pause(.2)
            self.assertEqual(app.provider.calls, [('delete', other)])

    async def test_short_workspace_keeps_calendar_and_controls_without_scrolling(self):
        app = Harness()
        async with app.run_test(size=(60, 20)) as p:
            await p.pause()
            ws = app.query_one(CorrectionSlotsWorkspace)
            cal = app.query_one(SlotsCalendar)
            self.assertGreater(cal.size.height, 0)
            self.assertEqual(ws.max_scroll_y, 0)
            self.assertGreater(cal.max_scroll_y, 0)
            self.assertLessEqual(cal.region.bottom, ws.region.bottom)
            await p.resize_terminal(110, 26); await p.pause()
            cal.set_week((B + timedelta(days=7)).date())
            cal.show_time(0); await p.pause()
            self.assertEqual(cal.cell(10, 0)[1], 0)

    async def test_immediate_save_pending_then_delete(self):
        app = Harness()
        async with app.run_test(size=(110, 40)) as p:
            await p.pause(); ws = app.query_one(CorrectionSlotsWorkspace); cal = app.query_one(SlotsCalendar)
            app.provider.gate = threading.Event()
            ws.run_worker(ws.change(None, B, E)); await p.pause()
            self.assertTrue(app.provider.started.is_set()); self.assertTrue(ws.busy)
            self.assertFalse(cal.writable); self.assertIsNotNone(cal.pending)
            cal.post_message(SlotsCalendar.EditRequested(B, E)); await p.pause()
            self.assertEqual(len(app.provider.calls), 1)
            app.provider.gate.set(); await p.pause(.2)
            self.assertFalse(ws.busy); self.assertEqual(cal.slots, (SLOT,))
            cal.post_message(SlotsCalendar.DeleteRequested(SLOT)); await p.pause()
            self.assertIsInstance(app.screen, SlotEditor)
            self.assertEqual(app.provider.calls[-1][0], 'save')
            await p.click('#slot-editor-delete'); await p.pause(.2)
            self.assertEqual(app.provider.calls[-1][0], 'delete'); self.assertEqual(cal.slots, ())

    async def test_account_switch_discards_inflight_result(self):
        app = Harness()
        async with app.run_test(size=(110, 40)) as p:
            await p.pause(); ws = app.query_one(CorrectionSlotsWorkspace); cal = app.query_one(SlotsCalendar)
            app.provider.gate = threading.Event(); ws.run_worker(ws.change(None, B, E)); await p.pause()
            app.account_generation += 1; app.account_id = '99'; app.account_connected = False; ws.tick()
            self.assertEqual(cal.slots, ()); app.provider.gate.set(); await p.pause(.2)
            self.assertFalse(cal.writable); self.assertEqual(cal.slots, ())

    async def test_refresh_failure_retains_rows_but_disables_writes(self):
        app = Harness(); app.provider.rows = (SLOT,)
        async with app.run_test(size=(110, 40)) as p:
            await p.pause(); ws = app.query_one(CorrectionSlotsWorkspace); cal = app.query_one(SlotsCalendar)
            app.provider.fail = True; await ws.reload()
            self.assertEqual(cal.slots, (SLOT,)); self.assertFalse(cal.writable)
            self.assertIn('stale', str(app.query_one('#slots-status', Static).render()).lower())

    async def test_editor_cancel_does_not_publish(self):
        app = Harness()
        async with app.run_test(size=(60, 32)) as p:
            await p.pause(); app.push_screen(SlotEditor(B, E, timezone.utc))
            await p.press('escape'); await p.pause()
            self.assertEqual(app.provider.calls, [])

    async def test_old_context_cannot_dispatch_before_timer_tick(self):
        app = Harness()
        async with app.run_test(size=(110, 40)) as p:
            await p.pause(); ws = app.query_one(CorrectionSlotsWorkspace)
            app.account_generation += 1; app.account_id = '99'
            await ws.change(None, B, E)
            self.assertEqual(app.provider.calls, [])

    async def test_uncertain_write_with_failed_reconciliation_stays_stale(self):
        app = Harness(); app.provider.rows = (SLOT,)
        def fail(*args):
            app.provider.fail = True
            raise RuntimeError('connection lost')
        app.provider.save_correction_slot = fail
        async with app.run_test(size=(110, 40)) as p:
            await p.pause(); ws = app.query_one(CorrectionSlotsWorkspace)
            await ws.change(None, B, E)
            self.assertFalse(ws.trusted)
            self.assertIn('stale', str(app.query_one('#slots-status', Static).render()).lower())

    async def test_day_navigation_matches_calendar_at_responsive_boundary(self):
        app = Harness()
        async with app.run_test(size=(85, 34)) as p:
            ws = app.query_one(CorrectionSlotsWorkspace); cal = app.query_one(SlotsCalendar)
            for width in (84, 85, 86, 87, 100):
                await p.resize_terminal(width, 34); await p.pause()
                self.assertEqual(ws.has_class('narrow'), cal.day_count == 1)
                if cal.day_count == 1:
                    self.assertTrue(app.query_one('#slots-day-next').display)

    async def test_read_scope_denied_explains_reconnect(self):
        from types import SimpleNamespace
        class Denied(RuntimeError):
            response = SimpleNamespace(json=lambda: {'error': 'slot_permission_denied'})
        app = Harness()
        def denied(*args):
            raise Denied()
        app.provider.get_correction_slots = denied
        async with app.run_test(size=(110, 40)) as p:
            await p.pause()
            self.assertIn('Reconnect', str(app.query_one('#slots-status', Static).render()))
            self.assertFalse(app.query_one(SlotsCalendar).writable)
