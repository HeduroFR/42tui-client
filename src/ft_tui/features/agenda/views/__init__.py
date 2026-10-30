"""Read-only agenda shared by projects, corrections and the dashboard."""
import asyncio
import webbrowser
from datetime import datetime, timedelta
from textual.containers import Horizontal, Vertical, VerticalScroll
from ft_tui.ui.modal import AppModal
from textual.widgets import DataTable, ListItem, ListView, TabbedContent
from ft_tui.ui.components import Button, Select, Static
from ft_tui.features.corrections.model import Slot, timestamp, local_zone, local_datetime
from ft_tui.features.corrections.calendar import SlotsCalendar
from ft_tui.features.corrections.views import SlotPicker
from ft_tui.i18n import translate
from ..models import snapshot
from ft_tui.app.read_cache import account_scope, app_cache, ReadInvalidated

LABELS = {'event': 'Campus event', 'evaluating': 'I evaluate', 'evaluated': 'I am evaluated', 'available': 'Available'}

class AgendaWorkspace(Vertical):
    DEFAULT_CSS = """
    AgendaWorkspace { height: 1fr; min-height: 8; }
    AgendaWorkspace Horizontal { height: 3; layout: grid; grid-size: 5; grid-columns: 1fr 2fr 1fr 2fr 3fr; }
    AgendaWorkspace Horizontal > Button { width: 1fr; min-width: 0; padding: 0; }
    AgendaWorkspace Button { width: auto; min-width: 5; }
    AgendaWorkspace .agenda-actions { layout: horizontal; align: center middle; margin-top: 1; }
    AgendaWorkspace .agenda-actions > Button { width: 20; max-width: 50%; margin: 0; padding: 0; text-wrap: nowrap; }
    AgendaWorkspace .agenda-actions #agenda-intra { margin-right: 2; }
    AgendaWorkspace Select { width: 1fr; }
    AgendaWorkspace ListView { height: 1fr; min-height: 3; }
    AgendaWorkspace ListItem { height: auto; padding: 0 1; }
    AgendaWorkspace DataTable { height: 1fr; }
    AgendaWorkspace .agenda-status { height: auto; margin: 1 0; color: $text-muted; }
    AgendaWorkspace .project-slot-headings { height: 1; }
    AgendaWorkspace .project-slot-nav { grid-size: 3; grid-columns: 1fr 2fr 1fr; }
    AgendaWorkspace .project-slot-hours { content-align: center middle; height: 3; }

    AgendaWorkspace .agenda-detail { height: auto; max-height: 6; display: none; }
    """
    def __init__(self, *, project_id=None, project_url=None, evaluations_only=False, **kwargs):
        super().__init__(**kwargs)
        self.project_id, self.project_url = project_id, project_url
        self.evaluations_only = evaluations_only
        self.zone = local_zone()
        today = datetime.now(self.zone).date()
        self.week = today - timedelta(days=today.weekday())
        self.rows, self.shown, self.sources = [], [], {}
        self.context = None
        self.epoch = 0
        self.loading = False
        self.needs_read = True
        self.calendar = bool(project_id)
        self.project_not_ready = False
        self._slot_window = None
        self.selected = None

    def t(self, text):
        return translate(text, getattr(self.app, 'language', 'en'))

    def compose(self):
        yield Static('Evaluation slots' if self.project_id else 'My evaluations' if self.evaluations_only else 'Agenda')
        with Horizontal():
            yield Button('‹', id='agenda-prev')
            yield Button('Today', id='agenda-today')
            yield Button('›', id='agenda-next')
            yield Button('Refresh', id='agenda-refresh')
            yield Button('Weekly calendar', id='agenda-view')
        options = [('All', 'all')] + [(label, kind) for kind, label in LABELS.items() if (kind == 'available') == bool(self.project_id) and (not self.evaluations_only or kind != 'event')]
        yield Select([(self.t(label), value) for label, value in options], value='all', allow_blank=False, id='agenda-filter')
        yield Static('', classes='agenda-period', markup=False, localize=False)
        yield Static('', classes='agenda-status', markup=False, localize=False)
        yield ListView(id='agenda-items')
        yield DataTable(id='agenda-calendar', cursor_type='cell')
        if self.project_id:
            with Horizontal(classes='project-slot-nav'):
                yield Button('Previous day', id='agenda-day-prev')
                yield Static('', classes='project-slot-hours', localize=False, markup=False)
                yield Button('Next day', id='agenda-day-next')
            yield Static('', classes='project-slot-headings', localize=False)
            yield SlotsCalendar(self.week, self.zone, id='project-slot-timeline')
        with VerticalScroll(classes='agenda-detail'):
            yield Static('', id='agenda-detail', markup=False, localize=False)
        if self.project_id:
            with Horizontal(classes='agenda-actions'):
                yield Button('Open on Intra', id='agenda-intra', disabled=True)
                yield Button('Close', id='project-slots-close')
        else:
            yield Button('Open on Intra', id='agenda-intra', disabled=True)

    def identity(self):
        scope = getattr(self.app, '_catalog_scope', lambda: None)()
        return (getattr(self.app, 'provider', None), getattr(self.app, 'account_id', None), getattr(self.app, 'account_generation', None), getattr(scope, 'campus_id', None))

    def on_mount(self):
        self.query_one(DataTable).display = False
        if self.project_id:
            self.query_one(Select).display = False
            self.query_one(ListView).display = False
            self.query_one('#agenda-view', Button).set_source_label('List view')
            self.query_one('#agenda-intra', Button).set_source_label('Open Intra')
            for button in self.query('.agenda-actions Button'):
                button.styles.line_pad = 0
        self.set_interval(1, self.check_context)
        self.set_interval(60, self.refresh_visible)
        self.check_context()

    def active(self):
        tabs = self.app.query('#main-tabs')
        if self.project_id or not tabs:
            return True
        target = 'dashboard' if isinstance(self, UpcomingEvaluations) else 'my-evaluations' if self.evaluations_only else 'agenda'
        return tabs.first().active == target

    def refresh_visible(self):
        if self.active() and not self.loading:
            self.run_worker(self.reload(), group='agenda-read', exclusive=True)

    def check_context(self):
        context = self.identity()
        if context != self.context:
            self.context = context
            self.epoch += 1
            self.loading = False
            self.rows, self.sources = [], {}
            self.selected = None
            self.query_one('#agenda-detail', Static).update('')
            self.query_one('#agenda-intra', Button).disabled = True
            self.needs_read = True
        if self.needs_read and self.active():
            self.needs_read = False
            self.run_worker(self.reload(), group='agenda-read', exclusive=True)

    async def reload(self, *, refresh=False):
        if self.loading:
            return
        self.loading = True
        self.epoch += 1
        epoch, context, week = self.epoch, self.identity(), self.week
        provider, account_id, _, campus = context
        self.query_one('.agenda-status', Static).update(self.t('Loading agenda…'))
        self.query_one('#agenda-intra', Button).disabled = True
        begin = local_datetime(f'{week}T00:00', self.zone)
        end = local_datetime(f'{week + timedelta(days=7)}T00:00', self.zone)
        kinds = [('available', self.project_id)] if self.project_id else [('evaluating', None), ('evaluated', None)]
        if not self.project_id and not self.evaluations_only:
            kinds.append(('event', campus))
        async def read(kind, target):
            try:
                if not account_id or not callable(getattr(provider, 'get_agenda', None)) or kind == 'event' and not target:
                    raise ValueError('Agenda unavailable')
                async def load():
                    args = (begin, end, kind, target, campus) if kind == 'available' else (begin, end, kind, target)
                    value = await asyncio.to_thread(provider.get_agenda, *args)
                    return snapshot(value, account_id, kind)
                key = (account_scope(self.app), 'agenda', kind, target, campus, begin.isoformat(), end.isoformat())
                rows = await app_cache(self.app).read(key, load, refresh=refresh, ttl=30, current=lambda: context == self.identity())
                return kind, rows, True
            except ReadInvalidated:
                return kind, [], False
            except Exception as error:
                try:
                    if kind == 'available' and error.response.json().get('error') == 'project_not_ready':
                        return kind, [], 'project_not_ready'
                except (AttributeError, TypeError, ValueError):
                    pass
                denied = getattr(getattr(error, 'response', None), 'status_code', None) in {401, 403}
                return kind, [] if denied else self.sources.get(kind, []), False
        results = await asyncio.gather(*(read(kind, target) for kind, target in kinds))
        if not self.is_mounted or epoch != self.epoch or context != self.identity() or week != self.week:
            return
        self.loading = False
        self.rows = []
        failures = []
        self.project_not_ready = False
        for kind, rows, ok in results:
            self.sources[kind] = rows
            if ok == 'project_not_ready':
                self.project_not_ready = True
            elif not ok:
                failures.append(self.t(LABELS[kind]))
            self.rows.extend(rows)
        self.rows.sort(key=lambda row: row['begin_at'])
        self.query_one('.agenda-status', Static).update(self.t('Unavailable or stale') + ': ' + ', '.join(failures) if failures else self.t('Up to date'))
        if self.project_not_ready:
            self.query_one('.agenda-status', Static).update(self.t('Set the project as finished on Intra before looking for evaluation slots.'))
        elif self.project_id and not failures:
            self.query_one('.agenda-status', Static).update(self.t('Confirm these times and book on Intra.'))
        await self.render_rows()

    async def render_rows(self):
        value = self.query_one(Select).value
        rows = self.rows
        if isinstance(self, UpcomingEvaluations):
            rows = [row for row in rows if datetime.fromisoformat(row['begin_at']) >= datetime.now(self.zone)][:3]
        self.shown = [row for row in rows if value == 'all' or row['kind'] == value]
        self.selected = None
        self.query_one('#agenda-detail', Static).update('')
        self.query_one('.agenda-detail').display = False
        self.query_one('#agenda-intra', Button).disabled = not bool(self.project_url)
        listing = self.query_one(ListView)
        await listing.clear()
        items = []
        for row in self.shown:
            local = datetime.fromisoformat(row['begin_at']).astimezone(self.zone)
            end = datetime.fromisoformat(row['end_at']).astimezone(self.zone).strftime('%H:%M') if row['end_at'] else ''
            parts = [f"{local:%a %d %b %H:%M}" + (f"–{end}" if end else '')]
            if not self.project_id:
                parts.extend((self.t(LABELS[row['kind']]), row['title']))
            if row['counterpart']:
                parts.append(row['counterpart'])
            items.append(ListItem(Static(' · '.join(parts), markup=False, localize=False)))
        await listing.extend(items)
        table = self.query_one(DataTable)
        table.clear(columns=True)
        table.add_columns(*(f'{self.week + timedelta(days=i):%a %d}' for i in range(7)))
        days = [[row for row in self.shown if datetime.fromisoformat(row['begin_at']).astimezone(self.zone).date() == self.week + timedelta(days=i)] for i in range(7)]
        for index in range(max((len(day) for day in days), default=0)):
            table.add_row(*(self.cell(day[index]) if index < len(day) else '' for day in days))
        self.days = days
        if self.project_id:
            calendar = self.query_one(SlotsCalendar)
            calendar.set_week(self.week)
            calendar.set_slots(Slot((str(row['id']),), timestamp(row['begin_at']), timestamp(row['end_at'])) for row in self.shown)
            if self.shown and self._slot_window != self.week:
                first = datetime.fromisoformat(self.shown[0]['begin_at']).astimezone(self.zone)
                calendar.set_day(first.weekday())
                calendar.row = first.hour * 4 + first.minute // 15
                calendar.show_time(calendar.row)
                self._slot_window = self.week
            self.screen.set_class(self.project_not_ready, 'project-slot-blocked')
            calendar.display = self.calendar and not self.project_not_ready
            self.query_one(ListView).display = not self.calendar and not self.project_not_ready
            self.query_one('.project-slot-nav').display = calendar.display
            self.query_one('.project-slot-headings').display = calendar.display
            for key in ('prev', 'next', 'today', 'view'):
                self.query_one('#agenda-' + key, Button).disabled = self.project_not_ready
            self.update_slot_heading()
        self.query_one('.agenda-period', Static).update(f'{self.week:%d %b %Y} – {self.week + timedelta(days=6):%d %b %Y} · {self.zone}' + ('' if self.shown else ' · ' + self.t('No items in this view.')))

    def update_slot_heading(self):
        if self.project_id and self.is_mounted:
            calendar = self.query_one(SlotsCalendar)
            self.query_one('.project-slot-headings', Static).update(calendar.headings())
            self.query_one('.project-slot-hours', Static).update(calendar.visible_hours())

    def on_slots_calendar_view_changed(self, event):
        event.stop()
        self.update_slot_heading()

    def on_slots_calendar_selection_changed(self, event):
        event.stop()
        if event.slot:
            row = next((row for row in self.shown if str(row['id']) in event.slot.ids), None)
            if row:
                self.select_row(row)

    def on_slots_calendar_choose_requested(self, event):
        event.stop()
        def chosen(slot):
            if slot and self.is_mounted:
                row = next((row for row in self.shown if str(row['id']) in slot.ids), None)
                if row:
                    self.select_row(row)
        self.app.push_screen(SlotPicker(event.slots, self.zone, action_label='View details'), chosen)

    def cell(self, row):
        from rich.text import Text
        return Text(f"{datetime.fromisoformat(row['begin_at']).astimezone(self.zone):%H:%M} {self.t(LABELS[row['kind']])} · {row['title']}")

    def select_row(self, row):
        self.query_one('.agenda-detail').display = True
        self.selected = row
        end = datetime.fromisoformat(row['end_at']).astimezone(self.zone).strftime('%c') if row['end_at'] else self.t('End time unavailable')
        self.query_one('#agenda-detail', Static).update('\n'.join((row['title'], f"{self.t(LABELS[row['kind']])} · {row['counterpart']}", f"{datetime.fromisoformat(row['begin_at']).astimezone(self.zone):%c} – {end} · {self.zone}", row['description'])))
        self.query_one('#agenda-intra', Button).disabled = not bool(row['url'] or self.project_url)

    def on_list_view_selected(self, event):
        event.stop()
        if event.index is not None and 0 <= event.index < len(self.shown):
            self.select_row(self.shown[event.index])

    def on_data_table_cell_selected(self, event):
        event.stop()
        row, col = event.coordinate
        if col < len(self.days) and row < len(self.days[col]):
            self.select_row(self.days[col][row])

    async def on_select_changed(self, event):
        event.stop()
        if self.is_mounted:
            await self.render_rows()

    async def on_button_pressed(self, event):
        key = event.button.id
        if not key or not key.startswith('agenda-'):
            return
        event.stop()
        if key in {'agenda-day-prev', 'agenda-day-next'}:
            cal = self.query_one(SlotsCalendar)
            cal.set_day(cal.day + (-1 if key.endswith('prev') else 1))
        elif key == 'agenda-view':
            self.calendar = not self.calendar
            self.query_one(DataTable).display = self.calendar and not self.project_id
            if self.project_id:
                self.query_one(SlotsCalendar).display = self.calendar
                self.query_one('.project-slot-nav').display = self.calendar
                self.query_one('.project-slot-headings').display = self.calendar
            event.button.set_source_label('List view' if self.calendar else 'Weekly calendar')
            self.query_one(ListView).display = not self.calendar
        elif key == 'agenda-intra':
            url = self.selected.get('url') if self.selected else None
            if url or self.project_url:
                try:
                    if not await asyncio.to_thread(webbrowser.open, url or self.project_url):
                        raise OSError()
                except Exception:
                    self.notify(self.t('Could not open the project page.'), severity='error')
        elif key == 'agenda-refresh':
            await self.reload(refresh=True)
        elif key in {'agenda-prev', 'agenda-next', 'agenda-today'}:
            today = datetime.now(self.zone).date()
            self.week = today - timedelta(days=today.weekday()) if key == 'agenda-today' else self.week + timedelta(days=-7 if key == 'agenda-prev' else 7)
            self.sources, self.rows = {}, []
            self.loading = False
            await self.render_rows()
            await self.reload()

class ProjectSlotsScreen(AppModal):
    BINDINGS = [('escape', 'dismiss', 'Close')]
    DEFAULT_CSS = '''
    #project-slots-dialog { width: 112; max-width: 96%; height: 88%; padding: 1 2; border: round $primary; background: $surface; }
    #project-slots-title { height: 1; text-style: bold; color: $accent; margin-bottom: 1; }
    ProjectSlotsScreen.project-slot-blocked #project-slots-dialog { height: auto; }
    ProjectSlotsScreen.project-slot-blocked AgendaWorkspace { height: auto; }
    '''
    def __init__(self, project_id, url, project_name=None):
        super().__init__()
        self.project_id, self.url = project_id, url
        self.project_name = project_name
    def compose(self):
        with Vertical(id='project-slots-dialog'):
            yield Static(self.project_name or 'Evaluation slots', id='project-slots-title', markup=False, localize=False)
            yield AgendaWorkspace(project_id=self.project_id, project_url=self.url)
    def on_button_pressed(self, event):
        if event.button.id == 'project-slots-close':
            self.dismiss()

class UpcomingEvaluations(AgendaWorkspace):
    """Use the same feed and lifecycle as the full agenda."""
    DEFAULT_CSS = '''
    UpcomingEvaluations { height: 10; border: round $primary; }
    UpcomingEvaluations Horizontal, UpcomingEvaluations Select,
    UpcomingEvaluations DataTable, UpcomingEvaluations .agenda-detail { display: none; }
    UpcomingEvaluations .agenda-period { height: 1; }
    UpcomingEvaluations ListView { height: 3; }
    '''
    def __init__(self, **kwargs):
        super().__init__(evaluations_only=True, **kwargs)
        self.week = datetime.now(self.zone).date()

    def on_mount(self):
        super().on_mount()
        self.query_one('#agenda-intra', Button).set_source_label('Agenda')
        self.query_one('#agenda-intra', Button).disabled = False

    async def render_rows(self):
        await super().render_rows()
        self.query_one('#agenda-intra', Button).disabled = False

    async def on_button_pressed(self, event):
        if event.button.id == 'agenda-intra':
            event.stop()
            self.app.query_one('#main-tabs', TabbedContent).active = 'agenda'
        else:
            await super().on_button_pressed(event)
