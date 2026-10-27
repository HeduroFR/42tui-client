"""Shared campus clubs, activity recruitment and account-wide notification controls."""
from datetime import datetime, timezone
from time import monotonic
from uuid import uuid4

from rich.text import Text
from rich.cells import cell_len
from textual import on
from textual.containers import VerticalScroll, Grid
from textual.widgets import DataTable, ContentSwitcher, Collapsible
from ft_tui.i18n import translate
from ft_tui.features.clubs.service import ClubsService
from ft_tui.ui.components import Button, Horizontal, Input, Select, Static, Vertical
from ft_tui.ui.modal import AppModal
from ft_tui.features.clubs.views.inbox import InboxColumns, InboxMessages, message_row, event_time


DEFAULT_TEMPLATE = {'title': 'Babyfoot', 'location': 'Cafeteria', 'minimum': 4, 'capacity': 4, 'minutes': 10}
TEMPLATES = {
    'babyfoot': DEFAULT_TEMPLATE,
    'smash': {'title': 'Smash Bros', 'location': 'Gaming room', 'minimum': 2, 'capacity': 8, 'minutes': 10},
    'custom': {'title': '', 'location': '', 'minimum': 2, 'capacity': 4, 'minutes': 10},
}


class ClubForm(AppModal[dict | None]):
    DEFAULT_CSS = """
    ClubForm > VerticalScroll { width: 64; max-width: 95%; height: auto; max-height: 90%;
        background: $surface; border: round $accent; padding: 1 2; }
    ClubForm Input, ClubForm Select { margin-bottom: 1; }
    ClubForm .club-form-title { text-style: bold; margin-bottom: 1; }
    ClubForm .club-field-label { color: $text-muted; height: 1; }
    ClubForm .form-actions { height: auto; align-horizontal: center; }
    ClubForm .form-actions Button { width: auto; margin: 0 1; }
    ClubForm #club-form-error { color: $error; height: auto; }
    """
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, title, fields, *, confirm=False, advanced=(), templates=None, submit_label=None):
        super().__init__()
        self.title_text, self.fields, self.confirm = title, fields, confirm
        self.advanced = advanced
        self.templates = templates
        self.submit_label = submit_label

    def compose(self):
        with VerticalScroll():
            yield Static(self.title_text, classes='club-form-title')
            if self.templates:
                yield Static('Choose a starting point')
                yield Select([(label, key) for key, (label, _) in self.templates.items()],
                             value='default', id='club-form-template')
            for field in self.fields:
                if field[0] not in self.advanced:
                    yield from self.compose_field(field)
            if self.advanced:
                with Collapsible(title=translate('More options', getattr(self.app, 'language', 'en')), collapsed=True):
                    for field in self.fields:
                        if field[0] in self.advanced:
                            yield from self.compose_field(field)
            yield Static('', id='club-form-error')
            with Horizontal(classes='form-actions'):
                yield Button('Cancel', id='club-form-cancel')
                yield Button(self.submit_label or ('Confirm' if self.confirm else 'Save'), id='club-form-save', variant='primary')

    def compose_field(self, field):
        name, label, value, kind = field
        yield Static(label, classes='club-field-label')
        if isinstance(kind, list):
            yield Select(kind, value=value, id=f'club-field-{name}', localize_options=False)
        else:
            yield Input(str(value), id=f'club-field-{name}', type='integer' if kind == 'number' else 'text', max_length=2000)

    @on(Select.Changed, '#club-form-template')
    def change_template(self, event):
        event.stop()
        if self.templates and event.value in self.templates:
            for key, value in self.templates[event.value][1].items():
                self.query_one(f'#club-field-{key}', Input).value = str(value)

    @on(Input.Changed, '#club-field-minimum')
    def adjust_capacity(self, event):
        if not event.value.isdigit():
            return
        capacity = self.query('#club-field-capacity')
        if capacity and capacity.first().value.isdigit() and int(event.value) > int(capacity.first().value):
            capacity.first().value = event.value

    def action_cancel(self):
        self.dismiss(None)

    @on(Button.Pressed)
    def pressed(self, event):
        event.stop()
        if event.button.id == 'club-form-cancel':
            self.dismiss(None)
            return
        if event.button.id != 'club-form-save':
            return
        values = {}
        try:
            for name, _, _, kind in self.fields:
                widget = self.query_one(f'#club-field-{name}')
                value = widget.value if isinstance(kind, list) else widget.value.strip()
                if kind == 'number':
                    value = int(value)
                    if value < 1:
                        raise ValueError()
                elif value in ('', Select.NULL) and name != 'description':
                    raise ValueError()
                values[name] = value
            if 'minimum' in values and not 1 <= values['minimum'] <= values['capacity'] <= 100:
                raise ValueError()
            if 'minutes' in values and values['minutes'] > (10080 if 'message' in values else 120):
                raise ValueError()
        except (ValueError, TypeError):
            for section in self.query(Collapsible):
                section.collapsed = False
            self.query_one('#club-form-error', Static).update('Check required fields, player counts and duration.')
            return
        self.dismiss(values)


class ClubActivityDetails(AppModal[None]):
    DEFAULT_CSS = """
    ClubActivityDetails > VerticalScroll { width: 68; max-width: 95%; height: auto;
        max-height: 90%; border: round $accent; background: $surface; padding: 1 2; }
    ClubActivityDetails Static { height: auto; margin-bottom: 1; }
    ClubActivityDetails Button { height: 3; min-width: 14; }
    """
    BINDINGS = [('escape', 'close', 'Close')]

    def __init__(self, activity, members):
        super().__init__()
        self.activity, self.members = activity, members

    def compose(self):
        a = self.activity
        t = lambda text: translate(text, getattr(self.app, 'language', 'en'))
        names = {m['account_id']: m['login'] for m in self.members}
        with VerticalScroll():
            yield Static(Text(a['title'], style='bold'), localize=False)
            yield Static(a['location'], markup=False, localize=False)
            yield Static(t('Players: {players}').format(players=', '.join(names.get(i, i) for i in a['participants'])), markup=False, localize=False)
            if a['waitlist']:
                yield Static(t('Waitlist: {players}').format(players=', '.join(names.get(i, i) for i in a['waitlist'])), markup=False, localize=False)
            if a['status'] in ('recruiting', 'ready'):
                yield Static(t('Recruitment ends at {time}').format(time=a['expires_at'][11:16]+' UTC'), markup=False, localize=False)
            yield Button('Close', id='club-details-close', variant='danger')

    def action_close(self):
        self.dismiss(None)

    @on(Button.Pressed, '#club-details-close')
    def close(self, event):
        event.stop()
        self.dismiss(None)


class ClubsGlobalControls(Horizontal):
    DEFAULT_CSS = """
    ClubsGlobalControls { width: auto; height: 1; align-horizontal: right; }
    ClubsGlobalControls Button { width: auto; min-width: 0; padding: 0 1; }
    """

    def compose(self):
        yield Button('DND OFF', icon='\uf204', id='clubs-global-dnd',
                     tooltip='Toggle Do Not Disturb · Ctrl+Shift+D', compact=True)

    def on_resize(self):
        from ft_tui.ui.navigation import MainTabbedContent
        for ancestor in self.ancestors:
            if isinstance(ancestor, MainTabbedContent):
                self.call_after_refresh(ancestor.align_settings)
                break

    @on(Button.Pressed, '#clubs-global-dnd')
    def toggle(self, event):
        event.stop()
        self.app.query_one(ClubsWorkspace).toggle_dnd()


class ClubsInvitations(Vertical):
    """A single queued invitation, mounted on the main screen without taking focus."""
    DEFAULT_CSS = """
    ClubsInvitations { overlay: screen; layer: clubs; dock: right; width: 48; max-width: 95%;
        height: auto; max-height: 22; margin: 2 1; background: $surface;
        border: round $accent; padding: 1; display: none; }
    ClubsInvitations Static { height: auto; }
    ClubsInvitations Horizontal { height: auto; }
    ClubsInvitations Button { min-width: 9; width: 1fr; }
    """

    def __init__(self):
        super().__init__(id='clubs-invitations')
        self.items = []
        self.scope = None
        self._seen = {}
        self._last_sound = float('-inf')

    def compose(self):
        yield Static('', id='clubs-invitation-text', markup=False, localize=False)
        with Horizontal():
            yield Button('Join', id='clubs-invitation-join')
            yield Button('Details', id='clubs-invitation-details')
            yield Button('Dismiss', id='clubs-invitation-dismiss')

    def enqueue(self, notifications, scope):
        if self.scope != scope:
            self.items = []
            self.scope = scope
            self._seen = {}
        now = datetime.now(timezone.utc)
        self._seen = {key: expiry for key, expiry in self._seen.items() if expiry > now}
        fresh = []
        for item in notifications:
            event = item['event']
            key = (item['club_id'], event['sequence'])
            expiry = datetime.fromisoformat(event['expires_at'].replace('Z', '+00:00'))
            if expiry > now and key not in self._seen:
                fresh.append(item)
                self._seen[key] = expiry
        self.items = (self.items + fresh)[-10:]
        self.update_card()
        if fresh and getattr(self.app, 'club_notification_sound', True) and monotonic() - self._last_sound >= 5:
            self.app.bell()
            self._last_sound = monotonic()

    def clear(self):
        self.items = []
        self.update_card()

    def update_card(self):
        now = datetime.now(timezone.utc)
        self.items = [i for i in self.items if datetime.fromisoformat(i['event']['expires_at'].replace('Z', '+00:00')) > now]
        self.display = bool(self.items)
        if not self.items:
            return
        item = self.items[0]
        e = item['event']
        label = translate(e['kind'].capitalize(), getattr(self.app, 'language', 'en'))
        self.query_one('#clubs-invitation-text', Static).update(
            f"{item['club_name']} · {label}\n{e['title']}\n{e['message']}\n({len(self.items)})")
        self.query_one('#clubs-invitation-join', Button).display = e['kind'] == 'activity'

    @on(Button.Pressed)
    def pressed(self, event):
        if not (event.button.id or '').startswith('clubs-invitation-'):
            return
        event.stop()
        if not self.items:
            return
        workspace = self.app.query_one(ClubsWorkspace)
        item = self.items.pop(0)
        self.update_card()
        if self.scope != workspace.scope():
            return
        if event.button.id == 'clubs-invitation-join':
            workspace.mutate({'action': 'join', 'activity_id': item['event']['activity_id']}, club_id=item['club_id'])
        elif event.button.id == 'clubs-invitation-details':
            workspace.selected_club = item['club_id']
            workspace.page = 'inbox' if item['event']['kind'] == 'announcement' else 'activities'
            workspace.selected_activity = item['event']['activity_id']
            self.app._activate_main_tab('clubs')
            workspace.refresh_data()


class MemberActions(Grid):
    """Keep actions in a row when they fit, otherwise wrap without clipping."""
    DEFAULT_CSS = """
    MemberActions { height: auto; grid-size: 4; grid-columns: 1fr;
        grid-rows: 3; grid-gutter: 1 2; margin-top: 1; }
    MemberActions Button { width: 100%; height: 3; margin: 0; padding: 0 1; }
    """

    def on_resize(self):
        self.reflow()

    def reflow(self):
        buttons = [b for b in self.query(Button) if b.display]
        if not buttons:
            self.display = False
            return
        self.display = True
        minimum = max(cell_len(str(b.label)) + 4 for b in buttons)
        self.styles.grid_size_columns = max(1, min(len(buttons), (self.content_size.width + 2) // (minimum + 2)))


class ClubsWorkspace(VerticalScroll):
    DEFAULT_CSS = """
    ClubsWorkspace { width: 1fr; height: 1fr; padding: 1 1; align: left top; }
    ClubsWorkspace.wide { overflow-y: hidden; }
    ClubsWorkspace #clubs-layout { height: 1fr; min-height: 0; }
    ClubsWorkspace #clubs-sidebar { width: 26; padding-right: 2; border-right: solid $surface-lighten-1; margin-right: 2; }
    ClubsWorkspace #clubs-sidebar > Static { height: 1; color: $text-muted; margin-bottom: 1; }
    ClubsWorkspace #clubs-campus-section { height: auto; padding-bottom: 1; margin-bottom: 1; border-bottom: solid $surface-lighten-1; }
    ClubsWorkspace #clubs-campus-section > Static { height: 1; color: $text-muted; margin-bottom: 1; }
    ClubsWorkspace #clubs-campus-section > .panel-title { display: none; }
    ClubsWorkspace #clubs-campus { width: 100%; }
    ClubsWorkspace #clubs-campus-name { display: none; height: 1; margin-bottom: 1; }
    ClubsWorkspace.single-campus #clubs-campus-name { display: block; }
    ClubsWorkspace #clubs-campus-news { width: 100%; margin: 0; }
    ClubsWorkspace #clubs-list { height: 1fr; min-height: 4; }
    ClubsWorkspace #clubs-list > .datatable--cursor { background: $primary 20%; color: $text; text-style: bold; }
    ClubsWorkspace.campus-selected #clubs-list > .datatable--cursor { background: $surface; text-style: none; }
    ClubsWorkspace #clubs-sidebar-actions { height: 3; margin-top: 1; }
    ClubsWorkspace #clubs-sidebar Button { width: auto; min-width: 0; margin-right: 1; padding: 0 1; }
    ClubsWorkspace #clubs-sidebar-actions Button { height: 3; margin: 0; }
    ClubsWorkspace #clubs-sidebar-actions #clubs-create { width: 1fr; margin-right: 1; }
    ClubsWorkspace #clubs-select { display: none; }
    ClubsWorkspace #clubs-main { width: 1fr; }
    ClubsWorkspace #clubs-heading { height: 3; margin-bottom: 1; padding: 0 1; border-left: thick $accent; background: $surface; }
    ClubsWorkspace #clubs-heading-copy { height: 3; width: 1fr; align-vertical: middle; }
    ClubsWorkspace #club-summary { height: 1; text-style: bold; color: $accent; }
    ClubsWorkspace #club-meta, ClubsWorkspace #club-description { display: none; }
    ClubsWorkspace #clubs-bell { width: auto; min-width: 5; padding: 0 1; margin-right: 0; }
    ClubsWorkspace .clubs-actions { height: auto; margin-bottom: 1; }
    ClubsWorkspace Button { width: auto; min-width: 0; height: 3; padding: 0 1; margin-right: 1; }
    ClubsWorkspace #clubs-sections { height: 3; margin-bottom: 1; }
    ClubsWorkspace .clubs-section { width: auto; min-width: 0; padding: 0 1; }
    ClubsWorkspace .clubs-section.active { border-bottom: solid $accent; }
    ClubsWorkspace #clubs-nav-manage { dock: right; margin-right: 0; }
    ClubsWorkspace #clubs-pages { height: 1fr; }
    ClubsWorkspace .clubs-page { height: 1fr; }
    ClubsWorkspace DataTable { height: auto; max-height: 10; margin-bottom: 1; }
    ClubsWorkspace #clubs-activities { min-height: 3; }
    ClubsWorkspace #clubs-activity-toolbar { height: 3; margin-bottom: 1; align-horizontal: right; }
    ClubsWorkspace #clubs-now { display: none; }
    ClubsWorkspace #club-activity-card { height: auto; border: round $surface-lighten-2; border-left: thick $accent; background: $surface; padding: 0 1; }
    ClubsWorkspace #club-activity-state { height: 1; color: $accent; }
    ClubsWorkspace #club-activity-title { height: auto; text-style: bold; }
    ClubsWorkspace #club-activity-detail { height: auto; color: $text-muted; }
    ClubsWorkspace #clubs-participation { height: auto; color: $success; }
    ClubsWorkspace #clubs-activity-actions { height: auto; margin-top: 1; margin-bottom: 0; }
    ClubsWorkspace #clubs-do-join, ClubsWorkspace #clubs-do-start { min-width: 20; }
    ClubsWorkspace .clubs-help, ClubsWorkspace #club-event-detail,
    ClubsWorkspace #clubs-status { height: auto; color: $text-muted; }
    ClubsWorkspace #clubs-status { margin-top: 1; }
    ClubsWorkspace #clubs-empty { height: auto; padding: 2; }
    ClubsWorkspace #clubs-inbox-toolbar { height: 3; margin-bottom: 1; }
    ClubsWorkspace #clubs-inbox-filter { width: 1fr; max-width: 32; margin-right: 2; }
    ClubsWorkspace #clubs-inbox-list { width: 2fr; height: 1fr; padding-right: 2; }
    ClubsWorkspace #clubs-events { height: 1fr; min-height: 6; max-height: 100%; margin: 0; background: $surface; }
    ClubsWorkspace #club-event-reader { width: 3fr; height: 1fr; border-left: solid $primary; padding: 1 2; }
    ClubsWorkspace #club-event-kind { height: auto; color: $accent; }
    ClubsWorkspace #club-event-title { height: auto; text-style: bold; margin-bottom: 1; }
    ClubsWorkspace #club-event-detail { height: auto; color: $text-muted; margin-bottom: 1; }
    ClubsWorkspace #club-event-place { height: auto; margin-bottom: 1; color: $text-muted; }
    ClubsWorkspace #club-event-body { height: auto; }
    ClubsWorkspace #clubs-inbox-columns.stacked #clubs-inbox-list { width: 100%; height: auto; padding-right: 0; margin-bottom: 1; }
    ClubsWorkspace #clubs-inbox-columns.stacked #clubs-events { height: 9; max-height: 9; }
    ClubsWorkspace #clubs-inbox-columns.stacked #club-event-reader { width: 100%; height: auto; min-height: 6;
        max-height: 18; border-left: none; border-top: solid $primary; padding: 1; }
    ClubsWorkspace.narrow { padding: 0 1; }
    ClubsWorkspace.narrow #clubs-layout { layout: vertical; height: auto; min-height: 0; }
    ClubsWorkspace.narrow #clubs-sidebar { width: 100%; height: auto; padding: 0; margin: 0 0 1 0; border: none; }
    ClubsWorkspace.narrow #clubs-campus-section { padding: 0; margin: 0 0 1 0; border: none; }
    ClubsWorkspace.narrow #clubs-campus-section > Static { display: none; }
    ClubsWorkspace.narrow #clubs-campus-name { display: none; }
    ClubsWorkspace.narrow #clubs-campus-section { layout: horizontal; height: auto; }
    ClubsWorkspace.narrow #clubs-campus { width: 1fr; margin-right: 1; }
    ClubsWorkspace.narrow #clubs-campus-news { width: auto; }
    ClubsWorkspace.narrow #clubs-sidebar > Static { display: none; }
    ClubsWorkspace.narrow #clubs-list { display: none; }
    ClubsWorkspace.narrow #clubs-select { display: block; }
    ClubsWorkspace.narrow #clubs-sidebar-actions { display: none; }
    ClubsWorkspace.narrow #clubs-main { width: 100%; height: auto; }
    ClubsWorkspace.narrow #clubs-heading { height: 3; padding: 0 1; margin-bottom: 1; }
    ClubsWorkspace.narrow #clubs-sections { margin-bottom: 1; }
    ClubsWorkspace.narrow .clubs-section { width: auto; min-width: 5; padding: 0 1; margin-right: 1; }
    ClubsWorkspace.narrow #clubs-nav-inbox, ClubsWorkspace.narrow #clubs-nav-manage { width: auto; min-width: 5; padding: 0 1; }
    ClubsWorkspace.narrow #clubs-nav-manage { dock: none; }
    ClubsWorkspace.narrow #clubs-pages { height: auto; }
    ClubsWorkspace.narrow .clubs-page { height: auto; }
    ClubsWorkspace.narrow #club-activity-card { padding: 0 1; }
    ClubsWorkspace.narrow #club-activity-title { margin-bottom: 0; }
    ClubsWorkspace.narrow #club-activity-detail { margin-bottom: 0; }
    ClubsWorkspace.narrow #clubs-activity-actions { margin-top: 0; }
    ClubsWorkspace #clubs-member-actions Button { width: 100%; margin: 0; padding: 0 1; }
    ClubsWorkspace #clubs-quick-actions { height: 3; margin-top: 1; }
    ClubsWorkspace #clubs-quick-actions Button { min-width: 10; }
    ClubsWorkspace.wide #clubs-quick-actions { display: none; }
    """

    def __init__(self, service=None):
        super().__init__(id='clubs-workspace')
        self._service = service
        self.snapshot = {}
        self.selected_club = None
        self.selected_activity = None
        self.selected_member = None
        self.context = None
        self.busy = False
        self.polling = False
        self.mutating = False
        self.next_refresh = 0
        self.next_poll = 0
        self.dnd = False
        self._club_options = None
        self._campus_options = None
        self.revision = 0
        self.page = 'activities'
        self.show_history = False
        self._table_rows = {}
        self.selected_event = None

    @property
    def service(self):
        if self._service is not None:
            return self._service
        configured = getattr(self.app, 'clubs_service', None)
        if configured is not None:
            return configured
        # Small existing App harnesses can use the same stateless implementation
        # without requiring production bootstrap or any persistence dependency.
        self._service = ClubsService()
        return self._service

    def t(self, text):
        return translate(text, getattr(self.app, 'language', 'en'))

    def scope(self):
        return (getattr(self.app, 'account_generation', 0), getattr(self.app, 'account_id', None), id(getattr(self.app, 'provider', None)))

    def compose(self):
        with Horizontal(id='clubs-layout'):
            with Vertical(id='clubs-sidebar'):
                with Vertical(id='clubs-campus-section'):
                    yield Static('Campus', classes='panel-title')
                    yield Select([], prompt='Campus', id='clubs-campus', localize_options=False)
                    yield Static('', id='clubs-campus-name', markup=False, localize=False)
                    yield Button('Announcements', icon='✉', id='clubs-campus-news')
                yield Static('YOUR CLUBS', classes='panel-title')
                yield Select([], prompt='Club', id='clubs-select', localize_options=False)
                yield DataTable(id='clubs-list', cursor_type='row', show_header=False, show_cursor=True)
                with Horizontal(id='clubs-sidebar-actions'):
                    yield Button('New club', id='clubs-create')
                    yield Button('Refresh', icon='\uf021', icon_only=True, id='clubs-refresh', square=True)
            with Vertical(id='clubs-main'):
                yield Static('Choose a club to see what is happening. Create one to bring people together.', id='clubs-empty')
                with Horizontal(id='clubs-heading'):
                    with Vertical(id='clubs-heading-copy'):
                        yield Static('', id='club-summary', markup=False, localize=False)
                        yield Static('', id='club-meta', markup=False, localize=False)
                        yield Static('', id='club-description', markup=False, localize=False)
                    yield Button('Bell: off', icon='\uf1f6', icon_only=True, id='clubs-bell')
                with Horizontal(classes='clubs-actions', id='clubs-sections'):
                    for label, page, icon in [('Activities', 'activities', '▶'), ('Inbox', 'inbox', '✉'),
                                              ('Members', 'members', '\uf0c0'), ('Settings', 'manage', '\uf013')]:
                        yield Button(label, icon=icon, icon_only=True,
                                     tooltip=label, id='clubs-nav-'+page, classes='clubs-section')
                with ContentSwitcher(initial='clubs-page-activities', id='clubs-pages'):
                    with VerticalScroll(id='clubs-page-activities', classes='clubs-page'):
                        with Horizontal(id='clubs-activity-toolbar'):
                            yield Static('NOW', id='clubs-now')
                            yield Button('Past activities', icon='↶', icon_only=True, id='clubs-history')
                            yield Button('New activity', icon='\uf067', icon_only=True, id='clubs-activity', variant='primary')
                        yield Static('', id='clubs-activities-empty', classes='clubs-help')
                        yield DataTable(id='clubs-activities', cursor_type='row')
                        with Vertical(id='club-activity-card'):
                            yield Static('', id='club-activity-state', markup=False, localize=False)
                            yield Static('', id='club-activity-title', markup=False, localize=False)
                            yield Static('', id='club-activity-detail', markup=False, localize=False)
                            yield Static('', id='clubs-participation')
                            with Horizontal(id='clubs-activity-actions'):
                                for label, action in [('Join', 'join'), ('Leave', 'leave_activity'), ('Start', 'start'), ('Finish', 'finish'), ('Cancel', 'cancel')]:
                                    yield Button(label, id=f'clubs-do-{action}', variant='primary' if action in ('join', 'start') else 'default')
                                yield Button('Details', icon='≡', icon_only=True, id='clubs-activity-details')
                    with VerticalScroll(id='clubs-page-inbox', classes='clubs-page'):
                        with Horizontal(id='clubs-inbox-toolbar'):
                            yield Select([('Messages', 'highlights'), ('Announcements', 'announcements'),
                                          ('All updates', 'all')], value='highlights', id='clubs-inbox-filter')
                            yield Button('New announcement', id='clubs-announce', variant='primary')
                        yield Static('No announcements or invitations yet.', id='clubs-events-empty', classes='clubs-help')
                        with InboxColumns(id='clubs-inbox-columns'):
                            with Vertical(id='clubs-inbox-list'):
                                yield InboxMessages(id='clubs-events', cursor_type='row', show_header=False, cell_padding=1)
                            with VerticalScroll(id='club-event-reader'):
                                yield Static('', id='club-event-kind', markup=False, localize=False)
                                yield Static('', id='club-event-title', markup=False, localize=False)
                                yield Static('', id='club-event-detail', markup=False, localize=False)
                                yield Static('', id='club-event-place', markup=False, localize=False)
                                yield Static('', id='club-event-body', markup=False, localize=False)
                    with VerticalScroll(id='clubs-page-members', classes='clubs-page'):
                        yield Static('Select a member to see available actions.', id='clubs-members-help', classes='clubs-help')
                        yield DataTable(id='clubs-members', cursor_type='row')
                        with MemberActions(id='clubs-member-actions'):
                            for label, action in [('Add member', 'add_member'), ('Remove member', 'remove_member'), ('Delegate', 'delegate'), ('Revoke delegate', 'revoke_delegate'), ('Transfer ownership', 'transfer')]:
                                yield Button(label, id=f'clubs-member-{action}', variant='primary' if action == 'add_member' else 'default')
                    with VerticalScroll(id='clubs-page-manage', classes='clubs-page'):
                        yield Static('Save a default activity to make the next invitation quicker.', id='clubs-template-help', classes='clubs-help')
                        yield Button('Save template', id='clubs-template-save')
                        yield Static('Membership', classes='panel-title')
                        yield Static('Leaving stops invitations. Archiving closes the club and cancels its activities.', classes='clubs-help')
                        yield Button('Leave club', id='clubs-leave')
                        yield Button('Archive club', id='clubs-archive')
        with Horizontal(id='clubs-quick-actions'):
            yield Button('New club', id='clubs-create-quick')
            yield Button('Refresh', id='clubs-refresh-quick')
        yield Static('Connect your 42 account to use Clubs.', id='clubs-status')

    async def on_mount(self):
        self.query_one('#clubs-list', DataTable).add_column('Club')
        self.query_one('#clubs-activities', DataTable).add_columns(*(self.t(k) for k in ('Activity', 'Status', 'Players')))
        self.query_one('#clubs-members', DataTable).add_columns(*(self.t(k) for k in ('Login', 'Role')))
        self.query_one('#clubs-events', DataTable).add_column('Message')
        self.set_interval(1, self.tick)
        self.render_data()
        self.tick()

    def on_resize(self):
        self.set_class(self.size.width < 95, 'narrow')
        self.set_class(self.size.width >= 95, 'wide')

    def active(self):
        from textual.widgets import TabbedContent
        return self.app.query_one(TabbedContent).active == 'clubs'

    def connected(self):
        return (getattr(self.app, 'account_connected', False) and getattr(self.app, 'account_id', None)
                and callable(getattr(getattr(self.app, 'provider', None), 'get_clubs', None)))

    def tick(self):
        if self.context != self.scope():
            self.context = self.scope()
            self.snapshot = {}
            self.selected_club = self.selected_activity = self.selected_member = None
            self.busy = self.polling = self.mutating = False
            self.dnd = False
            self.next_poll = self.next_refresh = 0
            self.app.query_one(ClubsInvitations).clear()
            self.render_data()
        self.update_campuses()
        if not self.connected():
            return
        if self.active() and self.next_refresh == 0 and not self.busy:
            self.refresh_data()
        self.app.query_one(ClubsInvitations).update_card()
        now = datetime.now(timezone.utc)
        expired = False
        for club in self.snapshot.get('clubs', []):
            for activity in club.get('activities', []):
                if activity['status'] in ('recruiting', 'ready') and datetime.fromisoformat(activity['expires_at'].replace('Z', '+00:00')) <= now:
                    activity['status'] = 'expired'
                    expired = True
        if expired:
            self.render_data()

    def update_campuses(self):
        campuses = getattr(self.app, 'account_campuses', []) or []
        options = [(str(c.get('name') or self.t('Campus {id}').format(id=c['id'])), c['id']) for c in campuses]
        self.query_one('#clubs-campus').display = len(options) > 1
        if options != self._campus_options:
            self._campus_options = options
            selector = self.query_one('#clubs-campus', Select)
            previous = selector.value
            with selector.prevent(Select.Changed):
                selector.set_options(options)
                if options:
                    selector.value = previous if previous in [v for _, v in options] else next((c['id'] for c in campuses if c.get('is_primary')), options[0][1])
            self.next_refresh = 0
        campus_name = next((name for name, key in options if key == self.query_one('#clubs-campus', Select).value), '')
        self.query_one('#clubs-campus-name', Static).update(campus_name)
        self.set_class(len(options) == 1, 'single-campus')

    def refresh_data(self):
        self.run_worker(self.reload(), group='clubs-refresh', exclusive=False)

    async def reload(self):
        if self.busy or not self.connected():
            return
        campus = self.query_one('#clubs-campus', Select).value
        if type(campus) is not int:
            return
        context = self.scope()
        revision = self.revision
        self.busy = True
        self.next_refresh = monotonic() + 10
        if not self.snapshot.get('clubs'):
            self.query_one('#clubs-status', Static).update('Loading clubs…')
        try:
            value = await self.service.read(
                self.app.provider, campus, context[1],
                lambda: context == self.scope() and revision == self.revision
                and campus == self.query_one('#clubs-campus', Select).value,
            )
            if value is None:
                return
            self.snapshot = value
            self.dnd = value['dnd']
            self.render_data()
            self.query_one('#clubs-status', Static).update('' if not self.dnd else 'Do not disturb is on. Invitations are saved in your inbox.')
        except Exception:
            if context == self.scope():
                self.query_one('#clubs-status', Static).update('Clubs unavailable. Refresh to retry; saved view may be out of date.')
        finally:
            if context == self.scope():
                self.busy = False

    async def poll(self):
        context = self.scope()
        revision = self.revision
        self.polling = True
        self.next_poll = monotonic() + 10
        try:
            value = await self.service.poll(
                self.app.provider, lambda: context == self.scope() and revision == self.revision,
            )
            if value is None:
                return
            self.dnd = value['dnd']
            self.snapshot.update(dnd=value['dnd'], bells=value['bells'])
            host = self.app.query_one(ClubsInvitations)
            if self.dnd:
                host.clear()
            else:
                host.items = [i for i in host.items if value['bells'].get(i['club_id'], False)]
                host.enqueue([i for i in value['notifications'] if value['bells'].get(i['club_id'], False)], context)
            self.update_controls()
        except Exception:
            if context == self.scope():
                self.next_poll = monotonic() + 30
        finally:
            if context == self.scope():
                self.polling = False

    def current(self):
        return next((c for c in self.snapshot.get('clubs', []) if c['id'] == self.selected_club), None)

    def fill_table(self, selector, rows, selected=None):
        table = self.query_one(selector, DataTable)
        signature = tuple((key, tuple(str(cell) for cell in cells)) for key, cells in rows)
        if self._table_rows.get(selector) != signature:
            self._table_rows[selector] = signature
            table.clear()
            for key, cells in rows:
                table.add_row(*cells, key=key, height=3 if selector == '#clubs-events' else 1)
        if selector not in ('#clubs-list', '#clubs-events'):
            table.styles.height = min(12, len(rows) + 3)
        keys = [key for key, _ in rows]
        if selected in keys and table.cursor_row != keys.index(selected):
            table.move_cursor(row=keys.index(selected))

    def club_label(self, club):
        if not club['system']:
            return club['name']
        campus = next((c.get('name') or str(c['id']) for c in (getattr(self.app, 'account_campuses', []) or []) if c['id'] == club['campus_id']), str(club['campus_id']))
        return self.t('Campus · {name}').format(name=campus)

    def render_data(self):
        clubs = sorted(self.snapshot.get('clubs', []), key=lambda c: not c['system'])
        ids = [c['id'] for c in clubs]
        if self.selected_club not in ids:
            self.selected_club = next((c['id'] for c in clubs if not c['system']), ids[0] if ids else None)
        ordinary = [c for c in clubs if not c['system']]
        self.fill_table('#clubs-list', [(c['id'], [Text(self.club_label(c))]) for c in ordinary], self.selected_club)
        self.set_class(bool((self.current() or {}).get('system')), 'campus-selected')
        campus_button = self.query_one('#clubs-campus-news', Button)
        campus_button.display = any(c['system'] for c in clubs)
        campus_button.variant = 'primary' if (self.current() or {}).get('system') else 'default'
        selector = self.query_one('#clubs-select', Select)
        options = [(self.club_label(c), c['id']) for c in ordinary]
        with selector.prevent(Select.Changed):
            if self._club_options != options:
                self._club_options = options
                selector.set_options(options)
            selector.value = self.selected_club if self.selected_club in [key for _, key in options] else Select.NULL
        c = self.current()
        self.query_one('#clubs-empty').display = c is None
        self.query_one('#clubs-heading').display = c is not None
        self.query_one('#clubs-sections').display = c is not None
        self.query_one('#clubs-pages').display = c is not None
        summary = ''
        if c:
            count = self.t('Campus announcements') if c['system'] else self.t('{count} members').format(count=len(c['members']))
            summary = self.club_label(c)
            self.query_one('#club-meta', Static).update(count)
            self.query_one('#club-description', Static).update(' '.join(c['description'].split()))
            self.query_one('#club-description', Static).tooltip = c['description']
            self.query_one('#club-summary', Static).tooltip = '\n'.join(filter(None, (count, c['description'])))
        self.query_one('#club-summary', Static).update(summary)
        activities = sorted((a for a in c['activities'] if self.show_history or a['status'] in ('recruiting', 'ready', 'started')),
                            key=lambda a: a['created_at'], reverse=True) if c else []
        if self.selected_activity not in [a['id'] for a in activities]:
            self.selected_activity = activities[0]['id'] if activities else None
        self.fill_table('#clubs-activities', [(a['id'], [Text(a['title']), self.t(a['status'].capitalize()),
            f"{len(a['participants'])}/{a['capacity']}" + (f" +{len(a['waitlist'])}" if a['waitlist'] else '')]) for a in activities], self.selected_activity)
        self.query_one('#clubs-activities').display = len(activities) > 1
        self.query_one('#clubs-now', Static).update('HISTORY' if self.show_history else 'NOW')
        empty = 'Nothing happening yet. Start an activity and invite your club.'
        if c and c['system']:
            empty = 'Campus news lives in the inbox.'
        self.query_one('#clubs-activities-empty', Static).update(empty)
        self.query_one('#clubs-activities-empty').display = not activities
        self.query_one('#clubs-history', Button).display = bool(c and any(a['status'] in ('finished', 'cancelled', 'expired') for a in c['activities']))
        members = c['members'] if c else []
        if self.selected_member not in [m['account_id'] for m in members]:
            self.selected_member = members[0]['account_id'] if members else None
        self.fill_table('#clubs-members', [(m['account_id'], [Text(m['login']), self.t(m['role'].capitalize())]) for m in members], self.selected_member)
        events = self.inbox_events()
        if self.selected_event not in [str(e['sequence']) for e in events]:
            self.selected_event = str(events[0]['sequence']) if events else None
        self.fill_table('#clubs-events', [(str(e['sequence']), [message_row(e, self.t)]) for e in events], self.selected_event)
        self.query_one('#clubs-events').display = bool(events)
        self.query_one('#clubs-events-empty').display = not events
        self.query_one('#clubs-inbox-columns').display = bool(events)
        self.render_event()
        if c and c['system'] and self.page in ('activities', 'members', 'manage'):
            self.page = 'inbox'
        self.show_page(self.page)
        self.update_controls()

    def inbox_events(self):
        c = self.current()
        mode = self.query_one('#clubs-inbox-filter', Select).value
        return [e for e in reversed(c['events'] if c else [])
                if mode == 'all' or e['kind'] == 'announcement' or mode == 'highlights' and e['kind'] == 'activity']

    def render_event(self):
        e = next((e for e in self.inbox_events() if str(e['sequence']) == self.selected_event), None)
        self.query_one('#club-event-reader').display = e is not None
        if not e:
            return
        self.query_one('#club-event-kind', Static).update(self.t(e['kind'].capitalize()).upper())
        self.query_one('#club-event-title', Static).update(e['title'])
        self.query_one('#club-event-detail', Static).update(' · '.join(filter(None, (e.get('actor_login'), event_time(e['created_at'])))))
        place = ' · '.join(filter(None, (e.get('location'), event_time(e.get('event_at')))))
        self.query_one('#club-event-place', Static).update(place)
        self.query_one('#club-event-place').display = bool(place)
        self.query_one('#club-event-body', Static).update(e['message'])

    def show_page(self, page):
        self.page = page
        self.query_one('#clubs-pages', ContentSwitcher).current = 'clubs-page-'+page
        for name in ('activities', 'inbox', 'members', 'manage'):
            self.query_one('#clubs-nav-'+name, Button).variant = 'primary' if name == page else 'default'
            self.query_one('#clubs-nav-'+name, Button).set_class(name == page, 'active')

    def update_controls(self):
        c = self.current()
        connected = bool(self.connected()) and not self.mutating
        manager = bool(c and c['my_role'] in ('creator', 'delegate'))
        creator = bool(c and c['my_role'] == 'creator')
        ordinary = bool(c and not c['system'])
        for button in self.app.query('#clubs-global-dnd'):
            button.icon = '\uf205' if self.dnd else '\uf204'
            button.set_source_label('DND ON' if self.dnd else 'DND OFF')
            button.variant = 'warning' if self.dnd else 'default'
            button.disabled = not connected
        bell = bool(c and self.snapshot.get('bells', {}).get(c['id'], False))
        bell_button = self.query_one('#clubs-bell', Button)
        bell_button.icon = '\uf0f3' if bell else '\uf1f6'
        bell_button.set_source_tooltip('Bell: on · Click to mute club notifications' if bell
                                       else 'Bell: off · Click to receive club notifications')
        bell_button.set_source_label('Bell: on' if bell else 'Bell: off')
        bell_button.variant = 'primary' if bell else 'default'
        for name in ('activities', 'members', 'manage'):
            self.query_one('#clubs-nav-'+name, Button).display = ordinary
        self.query_one('#clubs-template-help').display = manager and ordinary
        self.query_one('#clubs-members-help', Static).update('Select a member to see available actions.' if manager else 'People in this club.')
        for selector, enabled in {
            'clubs-create': connected, 'clubs-create-quick': connected, 'clubs-refresh-quick': connected, 'clubs-bell': connected and bool(c),
            'clubs-activity': connected and ordinary, 'clubs-template-save': connected and ordinary and manager,
            'clubs-announce': connected and bool(c and c.get('can_announce', False)), 'clubs-leave': connected and ordinary and not creator,
            'clubs-archive': connected and ordinary and creator,
        }.items():
            button = self.query_one('#'+selector, Button)
            button.disabled = not enabled
            if selector not in ('clubs-create', 'clubs-create-quick', 'clubs-refresh-quick', 'clubs-bell'):
                button.display = bool(c) and (ordinary if selector == 'clubs-activity' else manager if selector == 'clubs-template-save' else bool(c.get('can_announce', False)) if selector == 'clubs-announce' else enabled)
        member = next((m for m in c['members'] if m['account_id'] == self.selected_member), None) if c else None
        target_role = member['role'] if member else None
        for action, applicable in {
            'add_member': manager,
            'remove_member': manager and member and target_role != 'creator' and (creator or target_role == 'member'),
            'delegate': creator and target_role == 'member',
            'revoke_delegate': creator and target_role == 'delegate',
            'transfer': creator and member and target_role != 'creator',
        }.items():
            button = self.query_one('#clubs-member-'+action, Button)
            button.display = bool(ordinary and applicable)
            button.disabled = not connected
        self.query_one(MemberActions).reflow()
        a = next((a for a in c['activities'] if a['id'] == self.selected_activity), None) if c else None
        account = self.scope()[1]
        recruiting = bool(a and a['status'] in ('recruiting', 'ready'))
        organizer = bool(a and a['organizer_id'] == account)
        for action, enabled in {
            'join': recruiting and account not in (a['participants']+a['waitlist'] if a else []),
            'leave_activity': recruiting and not organizer and account in (a['participants']+a['waitlist'] if a else []),
            'start': organizer and a['status'] == 'ready', 'finish': organizer and a['status'] == 'started',
            'cancel': organizer and a['status'] in ('recruiting', 'ready', 'started'),
        }.items():
            button = self.query_one('#clubs-do-'+action, Button)
            button.disabled = not (connected and enabled)
            button.display = bool(enabled)
            if action == 'join':
                button.set_source_label('Join waitlist' if a and len(a['participants']) >= a['capacity'] else 'Join')
        self.query_one('#club-activity-card').display = a is not None
        self.query_one('#clubs-activity-details', Button).disabled = a is None
        if a:
            count = len(a['participants'])
            remaining = max(0, a['minimum'] - count)
            self.query_one('#club-activity-title', Static).update(a['title'])
            self.query_one('#club-activity-state', Static).update(self.t(a['status'].capitalize()).upper())
            detail = self.t('{location} · {count}/{capacity} players').format(location=a['location'], count=count, capacity=a['capacity'])
            if a['status'] == 'recruiting' and remaining:
                detail += ' · ' + self.t('{count} more needed').format(count=remaining)
            self.query_one('#club-activity-detail', Static).update(detail)
            participation = 'You are on the waitlist.' if account in a['waitlist'] else 'You are in.' if account in a['participants'] else ''
            self.query_one('#clubs-participation', Static).update(participation)
            self.query_one('#clubs-participation').display = bool(participation)

    @on(Select.Changed)
    def selected(self, event):
        if event.select.id == 'clubs-inbox-filter':
            event.stop()
            self.selected_event = None
            self.render_data()
        elif event.select.id == 'clubs-select':
            event.stop()
            if event.value != Select.NULL and event.value != self.selected_club:
                self.select_club(str(event.value))
        elif event.select.id == 'clubs-campus':
            event.stop()
            self.snapshot = {}
            self.selected_club = None
            self.render_data()
            self.refresh_data()

    @on(DataTable.RowHighlighted)
    def highlighted(self, event):
        if not self.is_mounted:
            return
        event.stop()
        if event.cursor_row != event.data_table.cursor_row:
            return
        key = str(event.row_key.value)
        if event.data_table.id == 'clubs-list':
            if key != self.selected_club and any(c['id'] == key for c in self.snapshot.get('clubs', [])):
                self.select_club(key)
        elif event.data_table.id == 'clubs-activities':
            self.selected_activity = key
            self.update_controls()
        elif event.data_table.id == 'clubs-members':
            self.selected_member = key
            self.update_controls()
        elif event.data_table.id == 'clubs-events':
            if any(str(e['sequence']) == key for e in self.inbox_events()):
                self.selected_event = key
                self.render_event()

    @on(DataTable.RowSelected, '#clubs-list')
    def club_selected(self, event):
        event.stop()
        key = str(event.row_key.value)
        if key != self.selected_club:
            self.select_club(key)

    def select_club(self, key):
        self.selected_club = key
        self.selected_activity = self.selected_member = self.selected_event = None
        self.show_history = False
        self.query_one('#clubs-history', Button).set_source_label('Past activities')
        self.page = 'inbox' if (self.current() or {}).get('system') else 'activities'
        self.render_data()

    def open_form(self, title, fields, done, *, confirm=False, **options):
        scope, club_id = self.scope(), self.selected_club
        def closed(values):
            if values is not None and scope == self.scope() and club_id == self.selected_club:
                done(values)
        self.app.push_screen(ClubForm(title, fields, confirm=confirm, **options), closed)

    def template_fields(self):
        values = (self.current() or {}).get('template', DEFAULT_TEMPLATE)
        return [(k, label, values[k], kind) for k, label, kind in (
            ('title', 'Activity title', 'text'), ('location', 'Meeting point', 'text'),
            ('minimum', 'Players needed to start', 'number'), ('capacity', 'Maximum players', 'number'),
            ('minutes', 'Recruitment duration (minutes)', 'number'))]

    def mutate(self, draft, *, club_id=None, create=False, preference=False):
        if self.mutating or not self.connected():
            return
        self.mutating = True
        self.revision += 1
        self.update_controls()
        scope = self.scope()
        target = club_id or self.selected_club
        async def work():
            try:
                result = await self.service.mutate(
                    self.app.provider, draft, lambda: scope == self.scope(),
                    club_id=target, create=create, preference=preference,
                )
                if result is None:
                    return
                if preference:
                    self.snapshot.update(result)
                    self.dnd = result['dnd']
                    host = self.app.query_one(ClubsInvitations)
                    if self.dnd:
                        host.clear()
                    else:
                        host.items = [i for i in host.items if result['bells'].get(i['club_id'], False)]
                        host.update_card()
                elif create:
                    self.selected_club = result['id']
                    self.page = 'activities'
                self.query_one('#clubs-status', Static).update('Saved.')
                self.next_refresh = 0
                await self.reload()
            except Exception as error:
                if scope == self.scope():
                    response = getattr(error, 'response', None)
                    code = ''
                    try:
                        code = response.json().get('error', '') if response is not None else ''
                    except (ValueError, AttributeError):
                        pass
                    self.query_one('#clubs-status', Static).update(self.t(ERRORS.get(code, 'Could not confirm this change. Refresh before retrying.')))
                    self.app.notify(self.t(ERRORS.get(code, 'Could not confirm this change. Refresh before retrying.')), severity='warning')
            finally:
                if scope == self.scope():
                    self.mutating = False
                    self.update_controls()
        self.run_worker(work(), group='clubs-mutation', exclusive=False)

    def toggle_dnd(self):
        self.mutate({'dnd': not self.dnd}, preference=True)

    @on(Button.Pressed)
    def pressed(self, event):
        key = event.button.id or ''
        if not key.startswith('clubs-'):
            return
        event.stop()
        c = self.current()
        if key == 'clubs-create-quick':
            key = 'clubs-create'
        elif key == 'clubs-refresh-quick':
            key = 'clubs-refresh'
        if key.startswith('clubs-nav-'):
            self.show_page(key[len('clubs-nav-'):])
        elif key == 'clubs-campus-news':
            campus = next((club for club in self.snapshot.get('clubs', []) if club['system']), None)
            if campus:
                self.select_club(campus['id'])
        elif key == 'clubs-history':
            self.show_history = not self.show_history
            self.query_one('#clubs-history', Button).set_source_label('Current activities' if self.show_history else 'Past activities')
            self.render_data()
        elif key == 'clubs-refresh':
            self.refresh_data()
        elif key == 'clubs-bell' and c:
            self.mutate({'club_id': c['id'], 'bell': not self.snapshot.get('bells', {}).get(c['id'], False)}, preference=True)
        elif key == 'clubs-create':
            campus = self.query_one('#clubs-campus', Select).value
            if type(campus) is int:
                self.open_form('New club', [('name', 'Club name', '', 'text'), ('description', 'Description', '', 'text')],
                    lambda v: self.mutate({**v, 'id': str(uuid4()), 'campus_id': campus}, create=True))
        elif key in ('clubs-activity', 'clubs-template-save') and c:
            save = key == 'clubs-template-save'
            self.open_form('Save template' if save else 'Start an activity', self.template_fields(),
                lambda v: self.mutate({'action': 'template', 'template': v} if save else {'action': 'activity', 'id': str(uuid4()), **v}),
                advanced=('capacity', 'minutes'), templates={'default': ('Club default', (c or {}).get('template', DEFAULT_TEMPLATE)),
                    **{k: (v['title'] or 'Custom', v) for k, v in TEMPLATES.items()}},
                submit_label='Save template' if save else 'Invite players')
        elif key == 'clubs-announce' and c and c.get('can_announce', False):
            from ft_tui.features.clubs.views.announcements import AnnouncementComposer
            self.app.push_screen(AnnouncementComposer(self, c['id'], self.club_label(c), getattr(self.app, 'account_login', None)))
        elif key in ('clubs-leave', 'clubs-archive') and c:
            action = 'leave' if key == 'clubs-leave' else 'archive'
            self.open_form('Leave club?' if action == 'leave' else 'Archive club and cancel its activities?', [], lambda _: self.mutate({'action': action}), confirm=True)
        elif key == 'clubs-activity-details' and c:
            activity = next((a for a in c['activities'] if a['id'] == self.selected_activity), None)
            if activity:
                self.app.push_screen(ClubActivityDetails(activity, c['members']))
        elif key.startswith('clubs-do-') and self.selected_activity:
            self.mutate({'action': key[9:], 'activity_id': self.selected_activity})
        elif key == 'clubs-member-add_member' and c:
            from types import SimpleNamespace
            from ft_tui.features.friends.views.search import FriendSearchScreen
            scope, club_id = self.scope(), c['id']
            adapter = SimpleNamespace(
                watches=[SimpleNamespace(user_id=m['account_id'], login=m['login']) for m in c['members']],
                adding=False, search_screen=None,
            )
            def add_member(login, selected_identity):
                if scope != self.scope() or self.selected_club != club_id or self.mutating:
                    return
                login = login.strip()
                if not login:
                    return
                adapter.search_screen.query_one('FriendSuggestions').reset()
                adapter.search_screen.dismiss()
                self.mutate({'action': 'add_member', 'login': login}, club_id=club_id)
            adapter.add_friend = add_member
            adapter.search_screen = FriendSearchScreen(adapter, purpose='member')
            self.app.push_screen(adapter.search_screen)
        elif key.startswith('clubs-member-') and self.selected_member:
            action = key[len('clubs-member-'):]
            member = self.selected_member
            title = {'remove_member': 'Remove {login} from this club?', 'delegate': 'Make {login} a delegate?',
                     'revoke_delegate': 'Remove delegate permissions from {login}?',
                     'transfer': 'Transfer club ownership to {login}?'}[action]
            self.open_form(self.t(title).format(login=next((m['login'] for m in c['members'] if m['account_id'] == member), member)), [],
                lambda _: self.mutate({'action': action, 'account_id': member}), confirm=True)


ERRORS = {
    'club_member_not_registered': 'This student must connect to 42TUI before being added.',
    'club_transfer_required': 'Transfer ownership before leaving the club.',
    'club_recruitment_cooldown': 'Please wait 30 seconds before posting again.',
    'clubs_forbidden': 'You do not have permission for this action.',
    'campus_denied': 'Club members must belong to the same campus.',
    'club_activity_closed': 'This activity is closed. Refresh to see its current status.',
    'club_activity_not_ready': 'More players are needed before starting.',
    'club_organizer_must_cancel': 'Organizers must cancel their activity instead of leaving it.',
    'invalid_clubs_request': 'Check required fields, player counts and duration.',
}
