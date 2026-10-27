"""Mutual friend inbox and explicit signatures for neighbour group pokes."""
import asyncio
from time import monotonic
from datetime import datetime, timezone
from uuid import uuid4

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Checkbox, DataTable

from ft_tui.app.read_cache import app_cache, backend_origin
from ft_tui.ui.components import Button, Input, Select, Static
from ft_tui.ui.modal import AppModal

ERRORS = {
    'student_not_registered': 'This student needs to connect to 42TUI before you can send a friend request.',
    'not_mutual_friends': 'Every sender must be an accepted friend of the recipient.',
    'poke_group_changed': 'The group must be a continuous row of friends. Seats or friendships have changed.',
    'poke_presence_unavailable': 'Current cluster presence is unavailable. Try a solo poke or refresh later.',
    'social_forbidden': 'This action is no longer available. Refresh your inbox.',
    'poke_closed': 'This poke has expired or has already been answered.',
    'identity_changed': 'The selected login now belongs to a different account. Search again.',
    'social_limit': 'Too many requests. Please try again later.',
}


def error_message(error):
    try:
        code = error.response.json().get('error')
    except (AttributeError, ValueError):
        code = None
    return ERRORS.get(code, 'Could not confirm this change. Refresh before retrying.')


class PokeComposer(AppModal):
    BINDINGS = [Binding('escape', 'cancel', show=False)]
    DEFAULT_CSS = '''
    PokeComposer { background: $background 65%; }
    #poke-dialog { width: 76; max-width: 96%; height: auto; max-height: 95%; padding: 1 2;
        border: round $primary; background: $surface; }
    #poke-dialog Static { height: auto; }
    #poke-neighbours { height: auto; max-height: 10; }
    #poke-dialog Horizontal { height: auto; }
    #poke-dialog Button { width: 1fr; }
    '''

    def __init__(self, inbox, recipient=None):
        super().__init__()
        self.inbox = inbox
        self.context = inbox.scope()
        self.recipient = recipient
        self.neighbours = []
        self.busy = False
        self.key = str(uuid4())
        self.submitted = None

    def compose(self):
        friends = self.inbox.snapshot.get('friends', [])
        with Vertical(id='poke-dialog'):
            yield Static('Poke', classes='panel-title')
            yield Select([(Text(f['login']), f['account_id']) for f in friends],
                         value=self.recipient or (friends[0]['account_id'] if friends else Select.NULL), id='poke-recipient')
            yield Input(placeholder='Poke message', max_length=500, id='poke-message')
            yield Static('Optional co-senders: select a continuous row of friends to your left or right. Each must approve this exact message.')
            yield Static('Loading neighbours…', id='poke-neighbour-status')
            yield VerticalScroll(id='poke-neighbours')
            yield Static('', id='poke-error', markup=False, localize=False)
            with Horizontal():
                yield Button('Cancel', id='poke-cancel')
                yield Button('Send poke', id='poke-send', variant='primary')

    def on_mount(self):
        self.run_worker(self.load_neighbours())

    async def load_neighbours(self):
        try:
            value = await self.inbox._service().neighbours(
                self.app.provider, lambda: self.context == self.inbox.scope() and self.is_mounted)
            if value is None:
                if self.context == self.inbox.scope() and self.is_mounted:
                    self.query_one('#poke-neighbour-status', Static).update('Neighbours unavailable. You can send a solo poke.')
                return
            self.neighbours = value
            await self.query_one('#poke-neighbours').mount(*[
                Checkbox(Text(item['login']), id=f'poke-author-{i}') for i, item in enumerate(value)])
            self.update_co_senders()
        except Exception:
            if self.is_mounted:
                self.query_one('#poke-neighbour-status', Static).update('Neighbours unavailable. You can send a solo poke.')

    def update_co_senders(self):
        recipient = self.query_one('#poke-recipient', Select).value
        eligible = False
        for i, neighbour in enumerate(self.neighbours):
            checkbox = self.query_one(f'#poke-author-{i}', Checkbox)
            is_recipient = neighbour['account_id'] == recipient
            if is_recipient:
                checkbox.value = False
            checkbox.disabled = is_recipient
            checkbox.display = not is_recipient
            eligible = eligible or not is_recipient
        self.query_one('#poke-neighbour-status', Static).update(
            'Choose co-senders below.' if eligible else 'No eligible neighbours. You can send a solo poke.')

    @on(Select.Changed, '#poke-recipient')
    def recipient_changed(self, event):
        event.stop()
        self.update_co_senders()

    def action_cancel(self):
        if not self.busy:
            self.dismiss()

    @on(Button.Pressed)
    async def pressed(self, event):
        event.stop()
        if event.button.id == 'poke-cancel':
            self.action_cancel()
            return
        if event.button.id != 'poke-send' or self.busy or self.context != self.inbox.scope():
            return
        recipient = self.query_one('#poke-recipient', Select).value
        message = self.query_one('#poke-message', Input).value.strip()
        if not isinstance(recipient, str) or not message:
            self.query_one('#poke-error', Static).update('Choose a friend and enter a message.')
            return
        draft = {'action': 'poke', 'recipient_id': recipient, 'message': message,
                 'sender_ids': [n['account_id'] for i, n in enumerate(self.neighbours)
                                if n['account_id'] != recipient and self.query_one(f'#poke-author-{i}', Checkbox).value]}
        if self.submitted is not None and draft != self.submitted:
            # Do not change content under a UUID that may already be accepted.
            self.query_one('#poke-error', Static).update('The previous send could not be confirmed. Restore the original message and recipients to retry; a new poke could send it twice.')
            return
        self.submitted = draft
        self.busy = True
        for button in self.query(Button):
            button.disabled = True
        try:
            result = await self.inbox._service().mutate(
                self.app.provider, {**draft, 'id': self.key}, lambda: self.context == self.inbox.scope())
            if result is None:
                return
            self.app.notify('Poke sent.' if result['status'] == 'sent' else 'Poke awaiting co-senders’ approval.')
            self.dismiss()
            await self.inbox.sync()
        except Exception as error:
            if self.is_mounted and self.context == self.inbox.scope():
                self.query_one('#poke-error', Static).update(error_message(error))
        finally:
            self.busy = False
            if self.is_mounted:
                for button in self.query(Button):
                    button.disabled = False


class SocialInbox(Vertical):
    DEFAULT_CSS = '''
    SocialInbox { height: auto; }
    #social-content { height: auto; max-height: 19; border: round $primary; padding: 0 1; }
    #social-table { height: 6; }
    #social-detail { height: auto; max-height: 5; overflow-y: auto; }
    #social-actions { height: auto; }
    #social-actions Button { width: 1fr; min-width: 8; }
    #social-status { height: auto; }
    '''

    def __init__(self, *, external_toggle=False, service=None):
        super().__init__(id='social-inbox')
        self.external_toggle = external_toggle
        self.service = service
        self.snapshot = {}
        self.context = None
        self.rows = {}
        self.selected = None
        self.seen = set()
        self.polling = self.mutating = False
        self.resync_pending = False
        self.last_sound = float('-inf')
        self.open = False
        self.composer = None
        self.poke_popup = None
        self._poke_lock = asyncio.Lock()
        self.revision = 0

    def compose(self):
        if not self.external_toggle:
            yield Button('Requests & pokes', id='social-toggle')
        with Vertical(id='social-content'):
            yield Static('', id='social-status', markup=False, localize=False)
            yield DataTable(id='social-table', cursor_type='row')
            yield Static('', id='social-detail', markup=False, localize=False)
            with Horizontal(id='social-actions'):
                yield Button('Accept', id='social-accept')
                yield Button('Decline', id='social-decline')
                yield Button('Cancel request', id='social-cancel')
                yield Button('Approve poke', id='social-approve')
                yield Button('Reject poke', id='social-reject')
                yield Button('Dismiss', id='social-dismiss')
                yield Button('New poke', id='social-compose')
                yield Button('Refresh', id='social-refresh')

    def _service(self):
        if self.service is not None:
            return self.service
        service = getattr(self.app, 'social_service', None)
        if service is None:
            from ft_tui.app.bootstrap import build_social_service
            service = build_social_service(self.app.session_factory)
        self.service = service
        return service

    def scope(self):
        return (getattr(self.app, 'account_generation', None), getattr(self.app, 'account_id', None),
                id(getattr(self.app, 'provider', None)), getattr(self.app, 'account_connected', False))

    def on_mount(self):
        self.query_one('#social-table', DataTable).add_columns('Type', 'Student(s)', 'Message')
        self.query_one('#social-content').display = False
        self.set_interval(1, self.check_context)
        self.run_worker(self.sync())

    async def check_context(self):
        context = self.scope()
        if context == self.context:
            await self.show_pokes()
            now = datetime.now(timezone.utc)
            pokes = self.snapshot.get('pokes', [])
            active = [p for p in pokes if datetime.fromisoformat(p['expires_at'].replace('Z', '+00:00')) > now]
            if active != pokes:
                self.snapshot['pokes'] = active
                self.render_data()
                await self.show_pokes()

        if context != self.context:
            if self.poke_popup:
                self.poke_popup.dismiss()
                self.poke_popup = None
            self.context = context
            self.snapshot = {}
            self.rows = {}
            self.seen.clear()
            self.selected = None
            self.revision += 1
            if self.composer and self.composer.is_mounted:
                self.app.pop_screen() if self.app.screen is self.composer else None
            self.render_data()
            await self.sync()

    def dnd(self):
        if self.snapshot.get('dnd', True):
            return True
        from ft_tui.features.clubs.views.workspace import ClubsWorkspace
        return any(w.dnd for w in self.app.query(ClubsWorkspace))

    async def sync(self):
        context = self.scope()
        if context != self.context:
            if self.poke_popup:
                self.poke_popup.dismiss()
                self.poke_popup = None
            self.context = context
            self.snapshot = {}
            self.rows = {}
            self.seen.clear()
            self.selected = None
        if self.polling or self.mutating:
            self.resync_pending = True
            return
        if not context[1] or not context[3] or not callable(getattr(self.app.provider, 'get_social', None)):
            return
        self.polling = True
        self.resync_pending = False
        revision = self.revision
        try:
            value = await self._service().snapshot(
                self.app.provider, context[1],
                lambda: context == self.scope() and revision == self.revision,
                origin=backend_origin(self.app),
            )
            if value is None:
                return
            changed = value.get('friends') != self.snapshot.get('friends')
            self.snapshot = value
            fresh = []
            fresh_pokes = False
            for pair in value['incoming']:
                key = ('request', pair['id'], pair['created_at'])
                if key not in self.seen:
                    fresh.append('Friend request from ' + next(m['login'] for m in pair['members'] if m['account_id'] != context[1]))
                    self.seen.add(key)
            for p in value['pokes']:
                if p['status'] == 'pending' and context[1] in p['approved']:
                    continue
                key = (p['id'], p['status'])
                if key not in self.seen:
                    names = ', '.join(s['login'] for s in p['senders'])
                    if p['status'] == 'sent':
                        fresh_pokes = True
                    else:
                        fresh.append('Poke approval requested by ' + names + ': ' + p['message'])
                    self.seen.add(key)
            self.render_data()
            self.query_one('#social-status', Static).update('Friendships and inbox are up to date.')
            if (fresh or fresh_pokes) and not self.dnd():
                for message in fresh[-3:]:
                    self.app.notify(message, timeout=15, markup=False)
                if (getattr(self.app, 'club_notification_sound', True)
                        and (fresh_pokes or monotonic() - self.last_sound >= 5)):
                    self.app.bell()
                    self.last_sound = monotonic()
            await self.show_pokes()
            if changed:
                app_cache(self.app).invalidate(lambda key: str(key[1]).startswith('friend-'))
                self.parent._stop()
                self.parent.last_sync = 0
                await self.parent.reload()
                from ft_tui.features.cluster_map.views.cluster_map import ClusterMapWorkspace
                for workspace in self.app.query(ClusterMapWorkspace):
                    await workspace.reload()
        except Exception:
            if context == self.scope():
                self.query_one('#social-status', Static).update('Friends inbox unavailable. Saved friendships may be out of date; refresh to retry.')
        finally:
            self.polling = False
            if self.resync_pending and self.is_mounted:
                self.run_worker(self.sync())

    async def show_pokes(self):
        async with self._poke_lock:
            await self._show_pokes()

    async def _show_pokes(self):
        from ft_tui.features.social.views.pokes import PokeNotification
        if self.context != self.scope():
            return
        now = datetime.now(timezone.utc)
        pokes = [p for p in self.snapshot.get('pokes', [])
                 if p['status'] == 'sent' and not p.get('dismissed')
                 and p['recipient']['account_id'] == self.scope()[1]
                 and datetime.fromisoformat(p['expires_at'].replace('Z', '+00:00')) > now]
        popup = self.poke_popup
        if popup and popup in self.app.screen_stack and not popup.closing:
            await popup.reconcile(pokes)
        elif pokes and not self.dnd():
            # A covered closing window must resume and leave the stack first.
            if popup and popup in self.app.screen_stack:
                return
            self.poke_popup = popup = PokeNotification(self)
            await self.app.push_screen(popup)
            await popup.reconcile(pokes)

    def render_data(self):
        if not self.is_mounted:
            return
        self.rows = {}
        owner = self.snapshot.get('account_id')
        table = self.query_one('#social-table', DataTable)
        table.clear()
        for kind in (() if getattr(self, 'inbox_kind', None) == 'pokes' else ('incoming', 'outgoing')):
            for p in self.snapshot.get(kind, []):
                other = next(m for m in p['members'] if m['account_id'] != owner)
                key = kind + ':' + other['account_id']
                self.rows[key] = (kind, other)
                table.add_row('Friend request' if kind == 'incoming' else 'Sent request', Text(other['login']), '', key=key)
        for p in ([] if getattr(self, 'inbox_kind', None) == 'requests' else self.snapshot.get('pokes', [])):
            key = p['id']
            self.rows[key] = ('poke', p)
            table.add_row('Poke' if p['status'] == 'sent' else 'Awaiting approval', Text(', '.join(s['login'] for s in p['senders'])), Text(p['message']), key=key)
        if self.selected not in self.rows:
            self.selected = next(iter(self.rows), None)
        if self.selected:
            table.move_cursor(row=list(self.rows).index(self.selected))
        host = self.parent if self.external_toggle else self
        toggle = host.query_one('#social-toggle', Button)
        if self.external_toggle:
            count = sum(len(self.snapshot.get(kind, [])) for kind in ('incoming', 'outgoing'))
            toggle.set_source_label('Requests')
            toggle.set_source_tooltip(f'Requests ({count})')
            poke = host.query_one('#friends-pokes', Button)
            poke.set_class(bool(self.snapshot.get('pokes')), 'has-pending')
        else:
            toggle.set_source_label(f'Requests & pokes ({len(self.rows)})')
        toggle.set_class(bool(count) if self.external_toggle else bool(self.rows), 'has-pending')
        self.update_controls()

    def update_controls(self):
        kind, item = self.rows.get(self.selected, (None, {}))
        owner = self.snapshot.get('account_id')
        pending = kind == 'poke' and item.get('status') == 'pending'
        for action, visible in {
            'accept': kind == 'incoming', 'decline': kind == 'incoming', 'cancel': kind == 'outgoing',
            'approve': pending and owner not in item.get('approved', []), 'reject': pending,
            'dismiss': kind == 'poke' and item.get('status') == 'sent',
        }.items():
            self.query_one('#social-' + action, Button).display = bool(visible)
        if kind == 'poke':
            detail = 'From: ' + ', '.join(s['login'] for s in item['senders']) + ' → ' + item['recipient']['login'] + '\n' + item['message']
            if pending:
                detail += '\nApproved: ' + ', '.join(s['login'] for s in item['senders'] if s['account_id'] in item['approved']) + ' · Expires: ' + item['expires_at']
        else:
            detail = ('Friend request: ' + item['login']) if kind else 'No pending requests or pokes.'
        self.query_one('#social-detail', Static).update(detail)
        for button in self.query('#social-actions Button'):
            button.disabled = self.mutating or not self.scope()[3]
        self.query_one('#social-compose', Button).disabled = self.mutating or not self.scope()[3] or not self.snapshot.get('friends')

    @on(DataTable.RowHighlighted, '#social-table')
    @on(DataTable.RowSelected, '#social-table')
    def selected_row(self, event):
        event.stop()
        self.selected = str(event.row_key.value)
        self.update_controls()

    async def mutate(self, draft):
        if (self.mutating or not self.scope()[3] or self.context != self.scope()
                or self.snapshot.get('account_id') != self.scope()[1]):
            return False
        context = self.scope()
        self.mutating = True
        self.revision += 1
        self.update_controls()
        try:
            result = await self._service().mutate(self.app.provider, draft, lambda: context == self.scope())
            return result is not None
        except Exception as error:
            if context == self.scope():
                self.app.notify(error_message(error), severity='warning')
            return False
        finally:
            self.mutating = False
            if context == self.scope():
                if draft.get('action') in ('remove', 'accept', 'decline', 'cancel', 'request'):
                    app_cache(self.app).invalidate(lambda key: str(key[1]).startswith('friend-'))
                    if self.external_toggle:
                        self.parent._stop()
                        self.parent.snapshots.clear()
                        self.parent.last_sync = 0
                self.update_controls()
                self.run_worker(self.sync())

    def compose_poke(self, recipient=None):
        if (self.snapshot.get('friends') and self.scope()[3] and self.context == self.scope()
                and self.snapshot.get('account_id') == self.scope()[1]):
            self.composer = PokeComposer(self, recipient)
            self.app.push_screen(self.composer)

    async def toggle(self, *, kind=None):
        self.open = not self.open or kind != getattr(self, 'inbox_kind', None)
        self.inbox_kind = kind
        self.render_data()
        self.query_one('#social-content').display = self.open
        host = self.parent if self.external_toggle else self
        host.query_one('#social-toggle', Button).variant = 'primary' if self.open and kind != 'pokes' else 'default'
        if self.external_toggle:
            host.query_one('#friends-pokes', Button).variant = 'primary' if self.open and kind == 'pokes' else 'default'
        await self.sync()

    @on(Button.Pressed)
    async def pressed(self, event):
        key = event.button.id or ''
        if not key.startswith('social-'):
            return
        event.stop()
        action = key[7:]
        if action == 'toggle':
            await self.toggle()
        elif action == 'refresh':
            await self.sync()
        elif action == 'compose':
            self.compose_poke()
        elif self.selected in self.rows:
            kind, item = self.rows[self.selected]
            await self.mutate({'action': action, **({'id': item['id']} if kind == 'poke' else {'account_id': item['account_id']})})
