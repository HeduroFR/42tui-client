"""Review correction availability in an editor before publishing to Intra."""
from datetime import datetime, timedelta
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import TabbedContent
from ft_tui.ui.components import Button, Input, Select, Static
from ft_tui.features.corrections.calendar import SlotsCalendar
from ft_tui.features.corrections.model import Slot, earliest_start, interval, local_datetime, local_zone
from ft_tui.i18n import translate
from .service import CorrectionsService, MutationFailure, StaleCorrectionsContext


def rounded_slot_time(value, zone):
    """Round valid local input to the nearest quarter, including day rollover."""
    wall = datetime.strptime(value.strip(), '%Y-%m-%d %H:%M')
    local_datetime(wall.isoformat(), zone)
    rounded = wall.replace(minute=0) + timedelta(minutes=((wall.minute + 7) // 15) * 15)
    return local_datetime(rounded.isoformat(), zone)


class SlotTimeInput(Input):
    def __init__(self, value, *, zone, **kwargs):
        super().__init__(value, **kwargs)
        self.zone = zone

    def normalize(self):
        result = rounded_slot_time(self.value, self.zone)
        self.value = result.astimezone(self.zone).strftime('%Y-%m-%d %H:%M')
        return result

    def on_blur(self):
        try:
            self.normalize()
        except ValueError:
            # Keep invalid input available to correct; publishing reports it.
            pass


class SlotEditor(ModalScreen):
    DEFAULT_CSS = '''
    SlotEditor { align: center middle; }
    SlotEditor > Vertical { width: 58; max-width: 95%; height: auto; padding: 1 2; border: round $primary; background: $surface; }
    SlotEditor Static { height: auto; margin-bottom: 1; }
    SlotEditor Input { margin-bottom: 1; }
    SlotEditor Horizontal { height: auto; }
    SlotEditor Button { width: 1fr; min-width: 0; margin-right: 1; }
    #slot-editor-cancel { margin-right: 0; }
    #slot-editor-error { color: $error; }
    '''
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, begin, end, zone, slot=None):
        super().__init__(); self.begin = begin; self.end = end; self.zone = zone; self.slot = slot

    def compose(self):
        with Vertical():
            yield Static('Publish correction availability')
            yield Static(f'{self.zone} · YYYY-MM-DD HH:MM', localize=False, markup=False)
            yield Static('Start')
            yield SlotTimeInput(self.begin.astimezone(self.zone).strftime('%Y-%m-%d %H:%M'),
                                zone=self.zone, id='slot-editor-begin')
            yield Static('End')
            yield SlotTimeInput(self.end.astimezone(self.zone).strftime('%Y-%m-%d %H:%M'),
                                zone=self.zone, id='slot-editor-end')
            yield Static('', id='slot-editor-error')
            with Horizontal():
                yield Button('Publish now', id='slot-editor-publish', variant='primary')
                if self.slot and not self.slot.booked:
                    yield Button('Delete slot', id='slot-editor-delete', variant='error')
                yield Button('Cancel', id='slot-editor-cancel')

    def read_time(self, key):
        return self.query_one(f'#slot-editor-{key}', SlotTimeInput).normalize()

    def action_cancel(self):
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == 'slot-editor-cancel':
            self.action_cancel(); return
        if event.button.id == 'slot-editor-delete' and self.slot and not self.slot.booked:
            self.dismiss('delete'); return
        if event.button.id != 'slot-editor-publish':
            return
        try:
            begin = self.read_time('begin')
            end = self.read_time('end')
            Slot(('1',), begin, end)
            if begin < earliest_start(datetime.now(self.zone)):
                self.query_one('#slot-editor-error', Static).update('Choose a later start time.')
                return
            if end - begin > timedelta(hours=48):
                raise ValueError()
        except ValueError:
            self.query_one('#slot-editor-error', Static).update('Use valid, unambiguous local times in 15-minute increments; maximum 48 hours.')
            return
        self.dismiss((begin, end))


class SlotPicker(ModalScreen):
    """Choose between slots that occupy the same local quarter-hour."""
    DEFAULT_CSS = '''
    SlotPicker { align: center middle; }
    SlotPicker > Vertical { width: 58; max-width: 95%; height: auto; padding: 1 2; border: round $primary; background: $surface; }
    SlotPicker Static { height: auto; margin-bottom: 1; }
    SlotPicker Horizontal { height: 3; }
    SlotPicker Button { width: 1fr; min-width: 0; }
    '''
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, slots, zone):
        super().__init__(); self.slots = slots; self.zone = zone

    def compose(self):
        with Vertical():
            yield Static('Choose a slot')
            yield Select([(f'{s.begin.astimezone(self.zone):%a %H:%M %Z}–{s.end.astimezone(self.zone):%H:%M %Z}', i)
                          for i, s in enumerate(self.slots)], value=0, allow_blank=False,
                         localize_options=False, id='slot-picker-choice')
            with Horizontal():
                yield Button('Edit', id='slot-picker-edit', variant='primary')
                yield Button('Cancel', id='slot-picker-cancel')

    def action_cancel(self):
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == 'slot-picker-edit':
            self.dismiss(self.slots[self.query_one(Select).value])
        elif event.button.id == 'slot-picker-cancel':
            self.action_cancel()


class CorrectionSlotsWorkspace(Vertical):
    DEFAULT_CSS = '''
    CorrectionSlotsWorkspace { height: 1fr; min-height: 0; width: 1fr; padding: 0 1; overflow: hidden hidden; }
    #slots-toolbar { height: 3; }
    #slots-toolbar Button { min-width: 5; width: auto; margin-right: 1; }
    #slots-period { height: 1; text-style: bold; color: $accent; margin-top: 1; }
    #slots-status, #slots-detail, #slots-help { height: 1; margin: 0; }
    #slots-status { color: $text-muted; }
    #slots-headings { height: 1; text-style: bold; background: $surface; }
    #slots-day-nav { height: 3; display: none; }
    #slots-day-nav Button { min-width: 5; width: 1fr; }
    #slots-time-nav { height: 3; }
    #slots-time-nav Button { width: 5; min-width: 3; }
    #slots-hours { width: 1fr; height: 3; content-align: center middle; color: $text-muted; }
    CorrectionSlotsWorkspace.narrow #slots-day-nav { display: block; }
    CorrectionSlotsWorkspace.narrow #slots-toolbar Button { width: auto; min-width: 3; margin-right: 0; padding: 0; text-wrap: nowrap; }
    #slots-help { color: $text-muted; }
    CorrectionSlotsWorkspace.compact #slots-help { display: none; }
    CorrectionSlotsWorkspace.tiny #slots-period,
    CorrectionSlotsWorkspace.tiny #slots-time-nav,
    CorrectionSlotsWorkspace.tiny #slots-day-nav,
    CorrectionSlotsWorkspace.tiny #slots-detail { display: none; }
    '''

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.zone = local_zone()
        self.week = datetime.now(self.zone).date()
        self.week -= timedelta(days=self.week.weekday())
        self.context = None
        self.epoch = 0
        self.busy = False
        self.loading = False
        self.trusted = False
        self.can_write = False
        self.loaded = False

    def t(self, message):
        return translate(message, getattr(self.app, 'language', 'en'))

    def compose(self):
        with Horizontal(id='slots-toolbar'):
            yield Button('‹', id='slots-prev', tooltip='Previous week')
            yield Button('Today', id='slots-today')
            yield Button('›', id='slots-next', tooltip='Next week')
            yield Button('Refresh', id='slots-refresh')
            yield Button('Add availability', id='slots-add', variant='primary', disabled=True, tooltip='Add availability')
        yield Static('', id='slots-period', localize=False, markup=False)
        yield Static('Connect your 42 account to manage correction slots.', id='slots-status')
        with Horizontal(id='slots-day-nav'):
            yield Button('Previous day', id='slots-day-prev')
            yield Button('Next day', id='slots-day-next')
        with Horizontal(id='slots-time-nav'):
            yield Button('↑', id='slots-earlier', tooltip='Earlier hours')
            yield Static('', id='slots-hours', localize=False, markup=False)
            yield Button('↓', id='slots-later', tooltip='Later hours')
        yield Static('', id='slots-headings', localize=False, markup=False)
        yield SlotsCalendar(self.week, self.zone, id='slots-calendar')
        yield Static(self.legend(), id='slots-detail', localize=False, markup=False)
        yield Static('Drag empty time to add · Drag slots to delete · Click a slot to edit · Esc to cancel', id='slots-help')

    def service(self):
        return getattr(self.app, 'corrections_service', None) or CorrectionsService()

    def scope(self):
        return (getattr(self.app, 'account_generation', 0), getattr(self.app, 'account_id', None),
                id(getattr(self.app, 'provider', None)), getattr(self.app, 'account_connected', False))

    def legend(self):
        return f'▎ {self.t("Available")}   ■ {self.t("Booked")}'

    def active(self):
        tabs = self.app.query(TabbedContent)
        return not tabs or tabs.first().active == 'correction-slots'

    def connected(self):
        return (getattr(self.app, 'account_connected', False) and getattr(self.app, 'account_id', None)
                and callable(getattr(getattr(self.app, 'provider', None), 'get_correction_slots', None)))

    def on_mount(self):
        self.set_interval(.5, self.tick)
        self.tick(); self.update_heading()
        now = datetime.now(self.zone)
        cal = self.query_one(SlotsCalendar)
        cal.set_day(now.weekday()); cal.row = max(32, now.hour * 4)
        self.call_after_refresh(cal.show_time, cal.row)

    def on_unmount(self):
        self.epoch += 1

    def on_resize(self):
        self.call_after_refresh(self.update_heading)

    def update_heading(self):
        if not self.is_mounted:
            return
        cal = self.query_one(SlotsCalendar)
        self.set_class(cal.day_count == 1, "narrow")
        self.set_class(self.size.height < 20, "compact")
        self.set_class(self.size.height < 12, "tiny")
        for button in self.query('#slots-toolbar Button'):
            button.styles.line_pad = 0
        self.query_one('#slots-add', Button).set_source_label('Add' if cal.day_count == 1 else 'Add availability')
        self.query_one('#slots-headings', Static).update(cal.headings())
        self.query_one('#slots-hours', Static).update(cal.visible_hours())
        self.query_one('#slots-period', Static).update(f'{self.week:%d %b %Y} – {self.week + timedelta(days=6):%d %b %Y}  ·  {self.zone}')

    def on_slots_calendar_view_changed(self):
        self.update_heading()

    def tick(self):
        scope = self.scope()
        if self.context != scope:
            self.context = scope; self.epoch += 1
            self.busy = self.loading = self.loaded = self.trusted = self.can_write = False
            cal = self.query_one(SlotsCalendar)
            cal.action_cancel(); cal.set_slots(()); cal.pending = None
            self.query_one('#slots-detail', Static).update(self.legend())
            self.query_one('#slots-status', Static).update('Connect your 42 account to manage correction slots.')
            self.controls()
        # Warm the first week while another tab is visible, rather than waiting
        # for the user to open this tab and then paying the entire network wait.
        if self.connected() and not self.loaded and not self.loading and not self.busy:
            self.loaded = True
            self.run_worker(self.reload(), group='slots-load')

    def valid(self, epoch, context):
        return self.is_mounted and epoch == self.epoch and context == self.scope()

    def controls(self):
        writable = bool(self.connected() and self.trusted and self.can_write and not self.busy and not self.loading)
        cal = self.query_one(SlotsCalendar); cal.writable = writable; cal.refresh()
        self.query_one('#slots-add', Button).disabled = not writable
        for key in ('prev', 'next', 'today', 'refresh'):
            self.query_one('#slots-' + key, Button).disabled = self.busy or self.loading

    def window(self):
        return (local_datetime(f'{self.week}T00:00', self.zone),
                local_datetime(f'{self.week + timedelta(days=7)}T00:00', self.zone))

    async def reload(self):
        if not self.connected() or self.loading:
            return
        self.epoch += 1; epoch = self.epoch; context = self.scope()
        self.loading = True; self.trusted = False; self.controls()
        self.query_one('#slots-status', Static).update('Loading correction slots…')
        provider = self.app.provider
        try:
            begin, end = self.window()
            snapshot = await self.service().snapshot(
                begin, end, account_id=context[1], provider=provider,
                current=lambda: self.valid(epoch, context))
            if not self.valid(epoch, context):
                return
            if snapshot['account_id'] != str(context[1]):
                raise ValueError('Account changed')
            self.query_one(SlotsCalendar).set_slots(snapshot['slots'])
            self.query_one('#slots-detail', Static).update(self.legend())
            self.can_write = snapshot['can_write']; self.trusted = True
            if not self.can_write:
                message = 'Reconnect your 42 account with projects permission to edit slots.'
            else:
                message = ('Select availability to edit. Booked corrections are read-only.' if snapshot['slots']
                           else 'No correction slots this week. Click or drag to add availability.')
            self.query_one('#slots-status', Static).update(message)
        except Exception as error:
            if self.valid(epoch, context):
                try:
                    code = error.response.json().get('error')
                except (AttributeError, ValueError):
                    code = None
                message = ('Reconnect your 42 account with projects permission to edit slots.'
                           if code in {'slot_permission_denied', 'upstream_permission_denied', 'reauthorization_required'}
                           else 'Could not refresh slots; displayed data is stale. Refresh before editing.')
                self.query_one('#slots-status', Static).update(message)
        finally:
            if self.valid(epoch, context):
                self.loading = False; self.controls()

    async def change(self, slot, begin=None, end=None, *, delete=False, delete_slots=None):
        if self.context != self.scope():
            self.tick()
            return
        if self.busy or not self.query_one(SlotsCalendar).writable or slot and slot.booked:
            return
        targets = tuple(delete_slots) if delete_slots is not None else (slot,)
        if delete and (not targets or any(s is None or s.booked for s in targets)):
            return
        if not delete:
            try:
                Slot(('1',), begin, end)
            except ValueError:
                return
            if begin < earliest_start(datetime.now(self.zone)):
                self.query_one('#slots-status', Static).update('Choose a later start time.')
                return
        context = self.scope(); epoch = self.epoch; provider = self.app.provider
        self.busy = True; self.trusted = False
        cal = self.query_one(SlotsCalendar)
        previous = cal.slots
        if delete:
            removed = {identity for target in targets for identity in target.ids}
            cal.set_slots(s for s in previous if not removed.intersection(s.ids))
            self.query_one('#slots-detail', Static).update(self.legend())
        cal.pending = (min(s.begin for s in targets), max(s.end for s in targets)) if delete else (begin, end)
        cal.pending_label = "Deleting…" if delete else "Saving…"
        self.controls()
        self.query_one('#slots-status', Static).update('Deleting…' if delete else 'Saving…')
        failure = None
        try:
            if delete:
                await self.service().delete(targets, provider=provider,
                                            current=lambda: self.valid(epoch, context))
            else:
                await self.service().save(slot, begin, end, provider=provider,
                                          current=lambda: self.valid(epoch, context))
        except StaleCorrectionsContext:
            return
        except MutationFailure as error:
            failure = ('Only part of the change was applied. Review the calendar before editing.'
                       if delete and error.completed else self.failure_message(error.error))
        except Exception as error:
            failure = self.failure_message(error)
        if not self.valid(epoch, context):
            return
        cal.pending = None; self.busy = False
        if delete and failure is None:
            # The server has confirmed every DELETE. The remaining records and
            # their IDs are unchanged; fetching the whole week adds no value.
            self.trusted = True
            self.controls()
            self.query_one('#slots-status', Static).update('Availability deleted.')
            return
        if delete:
            cal.set_slots(previous)
        await self.reload()
        if failure and self.context == context and context == self.scope():
            if self.trusted:
                self.query_one('#slots-status', Static).update(failure)
            else:
                self.query_one('#slots-status', Static).update(self.t(failure) + ' ' + self.t('Could not refresh slots; displayed data is stale. Refresh before editing.'))

    def failure_message(self, error):
        try:
            code = error.response.json().get('error')
        except (AttributeError, ValueError):
            code = None
        messages = {
            'slot_partial_outcome': 'Only part of the change was applied. Review the calendar before editing.',
            'slot_outcome_unknown': 'The change outcome is unknown. Review the calendar before trying again.',
            'slot_operation_pending': 'Another slot operation is pending. Refresh before trying again.',
            'slot_permission_denied': 'Reconnect your 42 account with projects permission to edit slots.',
            'slot_window_invalid': 'Choose availability from the current quarter-hour plus 30 minutes and within the next two weeks.',
            'slot_overlap': 'This interval overlaps existing availability. Refresh and choose another time.',
            'slot_booked': 'This slot has been booked and cannot be changed.',
            'slot_changed': 'This slot changed on Intra. Review the calendar before editing.',
            'slot_rejected': 'Intra rejected this change. Check your campus slot duration and scheduling rules.',
            'upstream_rate_limited': 'Intra is rate limiting requests. Wait before refreshing.',
        }
        return messages.get(code, 'Could not confirm the change. Review the calendar before trying again.')

    def open_editor(self, begin, end, slot=None):
        context = self.scope()
        def completed(result):
            if result and self.is_mounted and context == self.scope():
                if result == 'delete':
                    self.run_worker(self.change(slot, delete=True), group='slots-write')
                else:
                    self.run_worker(self.change(slot, *result), group='slots-write')
        self.app.push_screen(SlotEditor(begin, end, self.zone, slot), completed)

    def on_slots_calendar_choose_requested(self, event):
        event.stop()
        if self.busy or not self.query_one(SlotsCalendar).writable:
            return
        context = self.scope()
        def chosen(slot):
            if slot and self.is_mounted and context == self.scope():
                self.on_slots_calendar_selection_changed(SlotsCalendar.SelectionChanged(slot))
                if not slot.booked:
                    self.open_editor(slot.begin, slot.end, slot)
        self.app.push_screen(SlotPicker(event.slots, self.zone), chosen)

    def on_slots_calendar_edit_requested(self, event):
        event.stop()
        if self.busy or not self.query_one(SlotsCalendar).writable:
            return
        if event.form or event.slot is not None:
            self.open_editor(event.begin, event.end, event.slot)
        else:
            self.run_worker(self.change(None, event.begin, event.end), group='slots-write')

    def on_slots_calendar_delete_requested(self, event):
        event.stop()
        if not self.busy and self.query_one(SlotsCalendar).writable and not event.slot.booked:
            if event.direct:
                self.run_worker(self.change(event.slot, delete=True, delete_slots=event.slots), group='slots-write')
            else:
                self.open_editor(event.slot.begin, event.slot.end, event.slot)

    def on_slots_calendar_preview_changed(self, event):
        if event.deleting:
            self.query_one('#slots-detail', Static).update(self.t('Release to delete {count} slots · Esc to cancel').format(count=event.deleting))
        elif event.preview:
            begin, end = event.preview
            self.query_one('#slots-detail', Static).update(f'{begin.astimezone(self.zone):%a %H:%M} – {end.astimezone(self.zone):%H:%M}')
        else:
            self.query_one('#slots-detail', Static).update(self.legend())

    def on_slots_calendar_selection_changed(self, event):
        slot = event.slot
        text = self.legend() if not slot else f'{slot.begin.astimezone(self.zone):%a %H:%M} – {slot.end.astimezone(self.zone):%H:%M} · {self.t("Booked" if slot.booked else "Available")} · {len(slot.ids)} {self.t("slots")}'
        self.query_one('#slots-detail', Static).update(text)

    async def on_button_pressed(self, event: Button.Pressed):
        key = event.button.id or ''
        if not key.startswith('slots-'):
            return
        event.stop()
        cal = self.query_one(SlotsCalendar)
        # Local browsing stays responsive while a write or reload is in flight.
        if key in ('slots-earlier', 'slots-later'):
            cal.action_time(-1 if key == 'slots-earlier' else 1)
            return
        if key.startswith('slots-day-'):
            cal.set_day(cal.day + (-1 if key.endswith('prev') else 1))
            return
        if self.busy or self.loading:
            return
        if key == 'slots-refresh':
            await self.reload()
        elif key in ('slots-prev', 'slots-next', 'slots-today'):
            if key == 'slots-today':
                today = datetime.now(self.zone).date(); self.week = today - timedelta(days=today.weekday()); cal.set_day(today.weekday())
            else:
                self.week += timedelta(days=-7 if key == 'slots-prev' else 7)
            cal.set_week(self.week); cal.set_slots(()); self.update_heading(); await self.reload()
            if key == 'slots-today':
                cal.row = datetime.now(self.zone).hour * 4
                cal.show_time(cal.row)
        elif key == 'slots-add' and cal.writable:
            now = earliest_start(datetime.now(self.zone))
            try:
                begin, _ = interval(self.week + timedelta(days=cal.day), cal.row, cal.row, self.zone)
            except ValueError:
                begin = now
            begin = max(now, begin)
            self.open_editor(begin, begin + timedelta(hours=1))
