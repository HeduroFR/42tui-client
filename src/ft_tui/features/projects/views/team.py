"""Manage project teams and invitations using the shared fuzzy student picker."""
import asyncio
from functools import partial
from types import SimpleNamespace
from urllib.parse import quote
from uuid import uuid4
import webbrowser

from rich.text import Text
from textual import on
from textual.containers import Horizontal, Vertical, VerticalScroll
from ft_tui.ui.modal import AppModal
from textual.widgets import Input, Static

from ft_tui.features.projects.registration.team_types import team_state
from ..registration.service import RegistrationService, StaleRegistrationContext
from ft_tui.i18n import translate
from ft_tui.ui.button import Button
from ft_tui.ui.select import Select
from ft_tui.features.friends.views.suggestions import FriendSuggestions


class ProjectTeamScreen(AppModal):
    BINDINGS = [('escape', 'close', 'Close'), ('r', 'refresh', 'Refresh')]
    DEFAULT_CSS = """
    ProjectTeamScreen {  background: $background 65%; }
    #team-dialog {
        width: 88; max-width: 94%; height: 36; max-height: 92%;
        border: round $primary; background: $surface; padding: 1 2;
    }
    #team-dialog.creating { height: 23; }
    #team-invitations { height: auto; }
    #team-content { width: 1fr; height: 1fr; margin-bottom: 1; }
    #team-mode { height: auto; text-style: bold; color: $accent; margin-bottom: 1; }
    #team-name-label { height: auto; }
    #team-form-error { height: auto; color: $error; display: none; margin-bottom: 1; }
    #team-primary-actions, #team-footer { height: 3; min-height: 3; }
    #team-footer { margin-top: 1; }
    #team-heading { height: auto; text-style: bold; color: $accent; margin-bottom: 1; }
    #team-status, #team-roster, #team-pending, #team-help { height: auto; margin-bottom: 1; }
    #team-status, #team-help { color: $text-muted; }
    #team-choice, #team-name, #team-login { margin-bottom: 1; }
    .team-actions { height: auto; min-height: 3; layout: horizontal; }
    .team-actions Button { width: 1fr; min-width: 0; margin-right: 1; }
    #friend-suggestions { height: auto; display: none; }
    #friend-suggestions-status { height: auto; color: $text-muted; }
    #friend-suggestions-table { height: 6; }
    """

    def __init__(self, project_id, project_name, scope, account_id, provider, generation, slug):
        super().__init__()
        self.project_id, self.project_name, self.scope = project_id, project_name, scope
        self.account_id, self.provider, self.generation = account_id, provider, generation
        self.url = f'https://projects.intra.42.fr/{quote(slug, safe="")}/mine' if slug else None
        self.state = None
        self.busy = False
        self.uncertain = False
        self.alive = True
        self.pending = {}
        self.candidate = None
        self.selected = None

    def _registration_operations(self):
        service = getattr(self.app, 'registration_service', None)
        return service if service is not None else RegistrationService()

    def t(self, text):
        return translate(text, getattr(self.app, 'language', 'en'))

    def compose(self):
        with Vertical(id='team-dialog'):
            yield Static(f'{self.project_name} · {self.t("Manage team")}', id='team-heading', markup=False)
            with VerticalScroll(id='team-content'):
                yield Static(self.t('Loading team…'), id='team-status', markup=False)
                yield Select([], id='team-choice', prompt=self.t('Choose a team'))
                yield Static('', id='team-mode', markup=False)
                yield Static(self.t('Team name'), id='team-name-label', markup=False)
                yield Input(placeholder=self.t('Team name'), max_length=255, id='team-name')
                yield Static('', id='team-form-error', markup=False)
                yield Static('', id='team-roster', markup=False)
                with Vertical(id='team-invitations'):
                    yield Static(self.t('Search mates by name or login. Invitations are sent when you save the team.'), id='team-help', markup=False)
                    yield Input(placeholder=self.t('Name or 42 login'), max_length=128, id='team-login')
                    yield FriendSuggestions(purpose='team')
                    with Horizontal(classes='team-actions'):
                        yield Button(self.t('Invite'), id='team-invite')
                        yield Button(self.t('Remove last invite'), id='team-remove')
                    yield Static('', id='team-pending', markup=False)
            with Horizontal(id='team-primary-actions', classes='team-actions'):
                yield Button(self.t('Save team'), id='team-save', variant='primary')
                yield Button(self.t('Accept invitation'), id='team-accept')
                yield Button(self.t('Lock team'), id='team-lock')
            with Horizontal(id='team-footer', classes='team-actions'):
                yield Button(self.t('Refresh'), id='team-refresh')
                yield Button(self.t('Open on Intra'), id='team-intra', disabled=not self.url)
                yield Button(self.t('Close'), id='team-close', variant='danger')

    def on_mount(self):
        self.set_interval(.25, self._check_identity)
        self._controls()
        self.call_after_refresh(self.action_refresh)

    def _same_account(self):
        return (self.alive and self.is_mounted and self.provider is getattr(self.app, 'provider', None)
                and self.account_id == getattr(self.app, 'account_id', None)
                and self.generation == getattr(self.app, 'account_generation', None))

    def _check_identity(self, force=False):
        if self.alive and (force or not self._same_account()):
            self.alive = False
            self.state = None
            self.pending.clear()
            self.query_one(FriendSuggestions).reset()
            self.query_one('#team-choice', Select).set_options([])
            self.query_one('#team-roster', Static).update('')
            self.query_one('#team-mode', Static).update('')
            self.query_one('#team-pending', Static).update('')
            for selector in ('#team-name', '#team-login'):
                self.query_one(selector, Input).value = ''
            self.query_one('#team-status', Static).update(self.t('Account changed. Close this screen and reopen it.'))
            self._controls()

    def _team(self):
        return next((x for x in (self.state or {}).get('teams', []) if x['id'] == self.selected), None)

    def _controls(self):
        team = self._team()
        me = next((m for m in team['members'] if str(m['id']) == self.account_id), None) if team else None
        ready = self._same_account() and not self.busy and not self.uncertain and bool(self.state and self.state['can_write'])
        editable = ready and (not team or not team['locked'] and not team['closed'] and team['status'] == 'creating_group')
        leader = editable and (not team or me and me['leader'])
        self.query_one('#team-name', Input).disabled = not leader
        self.query_one('#team-login', Input).disabled = not leader or not team
        loaded = self.state is not None
        for selector in ('#team-name-label', '#team-name', '#team-mode', '#team-primary-actions'):
            self.query_one(selector).display = loaded
        self.query_one('#team-choice').display = loaded and bool(self.state['teams'])
        self.query_one('#team-invitations').display = bool(team)
        self.query_one('#team-dialog').set_class(not team, 'creating')
        for selector in ('#team-save', '#team-invite'):
            self.query_one(selector, Button).disabled = not leader
        capacity = ((self.state or {}).get('session') or {}).get('max_people') or 0
        count = len(team['members']) if team else 1
        self.query_one('#team-invite', Button).disabled = not (leader and team and self.candidate and count + len(self.pending) < capacity)
        self.query_one('#team-save', Button).display = not team or bool(me and me['leader'])
        self.query_one('#team-accept', Button).display = bool(team and me and not me['accepted'])
        self.query_one('#team-lock', Button).display = bool(team and me and me['leader'])
        self.query_one('#team-save', Button).label = self.t('Save team' if team else 'Create team')
        self.query_one('#team-remove', Button).disabled = not leader or not self.pending
        self.query_one('#team-accept', Button).disabled = not (editable and me and not me['accepted'])
        session = (self.state or {}).get('session') or {}
        self.query_one('#team-lock', Button).disabled = not (leader and team and len(team['members']) == session.get('max_people') and all(m['accepted'] for m in team['members']) and not self.pending)
        self.query_one('#team-refresh', Button).disabled = self.busy or not self._same_account()
        self.query_one('#team-choice', Select).disabled = self.busy or not self._same_account()

    def action_refresh(self):
        if self.busy or not self._same_account():
            return
        self.busy = True
        self._controls()
        self.run_worker(self._request(), group='project-team', exclusive=True)

    async def _request(self, action=None, key=None):
        if not self._same_account():
            self.busy = False
            return
        try:
            value = await self._registration_operations().team(
                self.provider, self.project_id, self.scope, self.account_id,
                current=self._same_account, action=action, key=key, state=self.state)
            if not self._same_account():
                return
            self.state = value
            self.uncertain = False
            if action:
                self.pending.clear()
                cache = getattr(self.app, '_activity_view_cache', {})
                cache.clear()
                refresh = getattr(self.app, '_request_catalog_refresh', None)
                if refresh:
                    refresh()
            teams = value['teams']
            if self.selected not in {x['id'] for x in teams}:
                self.selected = next((x['id'] for x in teams if not x['closed'] and x['status'] != 'finished'), teams[0]['id'] if teams else None)
            choice = self.query_one('#team-choice', Select)
            options = [(Text(x['name']), x['id']) for x in teams]
            if not any(not x['closed'] and x['status'] != 'finished' for x in teams):
                options.append((self.t('Create a new team'), 0))
                if self.selected is None or not action:
                    self.selected = None
            choice.display = bool(teams)
            choice.set_options(options)
            if self.selected is not None:
                choice.value = self.selected
            elif options and options[-1][1] == 0:
                choice.value = 0
            self._render_team()
        except StaleRegistrationContext:
            return
        except Exception as error:
            if self._same_account():
                import httpx
                code = ''
                status = None
                if isinstance(error, httpx.HTTPStatusError):
                    status = error.response.status_code
                    try:
                        payload = error.response.json()
                        code = payload.get('error', '') if isinstance(payload, dict) else ''
                    except ValueError:
                        pass
                    if error.response.status_code == 401:
                        self._check_identity(force=True)
                        self.query_one('#team-status', Static).update(self.t('Session expired. Close this screen and reconnect your account.'))
                        return
                self.uncertain = bool(action)
                message = {
                    'team_permission_denied': '42 denied this team action. Open the project on Intra.',
                    'team_rejected': '42 rejected this team change. Refresh the team or open Intra.',
                    'team_not_ready': 'All members must accept and the team must be complete before locking.',
                    'team_leader_required': 'Only the team leader can edit or lock the team.',
                    'team_size_invalid': 'Too many members or a duplicate invitation.',
                }.get(code, 'Team outcome unknown. Refresh before trying again.' if action else 'Could not load the team. Refresh to try again.')
                if not action:
                    if status == 404:
                        message = 'Team management endpoint not found. Update the backend to the same version as the app.'
                    elif status == 403:
                        message = '42 denied access to team information. Check your account permissions or open Intra.'
                    elif code == 'invalid_context':
                        message = 'The selected campus or cursus is not available for this account.'
                    elif status == 429:
                        message = '42 is limiting requests. Wait before refreshing the team.'
                    elif isinstance(error, httpx.TimeoutException):
                        message = 'Loading the team timed out. Refresh to try again.'
                    elif isinstance(error, ValueError):
                        message = 'The backend returned invalid team data. Check that the app and backend are up to date.'
                    # Only expose a bounded machine error identifier, never response bodies.
                    if status is not None:
                        diagnostic = f'HTTP {status}'
                        if isinstance(code, str) and 0 < len(code) <= 80 and all(c.isascii() and (c.isalnum() or c == '_') for c in code):
                            diagnostic += f' · {code}'
                        message = self.t(message) + '\n' + diagnostic
                self.query_one('#team-status', Static).update(self.t(message))
        finally:
            self.busy = False
            if self.is_mounted:
                self._controls()

    def _render_team(self):
        team = self._team()
        session = (self.state or {}).get('session') or {}
        size = session.get('max_people')
        status = self.t('All members must accept and the team must be complete before locking.' if team else 'Registered · No team yet')
        if not (self.state or {}).get('can_write'):
            messages = {
                'scope_missing': 'Your API connection is missing the projects permission. Reconnect your 42 account with the projects scope.',
                'scope_unknown': 'Your API connection has no recorded permissions. Reconnect your 42 account.',
                'catalog_outdated': 'Team details are restricted by 42 and the cached catalog is outdated. Refresh the backend catalog, then try again.',
                'session_missing': 'No matching project session was found for this campus and cursus. Refresh the backend catalog.',
                'session_ambiguous': 'Several project sessions match this campus and cursus. The backend cannot safely choose one.',
                'session_metadata_incomplete': 'The project session is missing its team size or group setting. Refresh the backend catalog or open Intra.',
                'solo_project': 'This project session is solo. Team creation is unavailable.',
            }
            status = self.t(messages.get((self.state or {}).get('reason_code'),
                'Team editing is unavailable for this session or account. Open the project on Intra.'))
        if team and not size and (self.state or {}).get('can_write'):
            status = self.t('Team created. Team capacity is unavailable; invitations and locking require a known capacity.')
        if size:
            status += '\n' + self.t('Team capacity: {size} members').format(size=size)
        self.query_one('#team-status', Static).update(status)
        self.query_one('#team-roster', Static).update('\n'.join(
            f"{m['login']} · {self.t('Leader') if m['leader'] else self.t('Member')} · {self.t('Accepted') if m['accepted'] else self.t('Invitation pending')}"
            for m in team['members']) if team else self.t('No team yet. Choose a name and invite your mates.'))
        self.query_one('#team-roster', Static).display = bool(team)
        self.query_one('#team-mode', Static).update(team['name'] if team else self.t('Create a new team'))
        login = getattr(self.app, 'account_login', None)
        default_name = f"{login}'s team"[:255] if login else ''
        self.query_one('#team-name', Input).value = team['name'] if team else default_name
        self.query_one('#team-form-error', Static).display = False
        if not team and self.state and self.state['can_write']:
            self.query_one('#team-name', Input).focus()
        if team and team['locked']:
            self.query_one('#team-status', Static).update(self.t('Team locked'))
        self._pending()

    def _pending(self):
        self.query_one('#team-pending', Static).update(self.t('Invites to send: {logins}').format(logins=', '.join(self.pending.values())) if self.pending else '')
        self._controls()

    @on(Select.Changed, '#team-choice')
    def select_team(self, event):
        if event.value is Select.NULL or (event.value or None) == self.selected:
            return
        self.selected = event.value or None
        self.pending.clear()
        self.candidate = None
        self.query_one('#team-login', Input).value = ''
        self.query_one(FriendSuggestions).reset()
        self._render_team()

    @on(Input.Changed, '#team-name')
    def name_changed(self, event):
        if event.value.strip():
            self.query_one('#team-form-error', Static).display = False

    @on(Input.Changed, '#team-login')
    def search(self, event):
        if not self._team():
            self.candidate = None
            self.query_one(FriendSuggestions).reset()
            return
        if self.candidate and event.value != self.candidate['login']:
            self.candidate = None
        members = (self._team() or {}).get('members', [])
        excluded = [SimpleNamespace(user_id=str(x['id']), login=x['login']) for x in members]
        excluded += [SimpleNamespace(user_id=str(uid), login=login) for uid, login in self.pending.items()]
        self.query_one(FriendSuggestions).set_query(event.value, excluded)
        self._controls()

    @on(FriendSuggestions.Chosen)
    def choose(self, event):
        event.stop()
        if not self._team():
            return
        self.candidate = event.candidate
        suggestions = self.query_one(FriendSuggestions)
        suggestions.pause()
        suggestions.suppressed_query = event.candidate['login']
        suggestions.display = False
        self.query_one('#team-login', Input).value = event.candidate['login']
        self._controls()
        self.query_one('#team-invite', Button).focus()

    def on_key(self, event):
        if event.key == 'down' and self.query_one('#team-login', Input).has_focus():
            if self.query_one(FriendSuggestions).focus_results():
                event.prevent_default()
                event.stop()

    @on(Button.Pressed)
    def button(self, event):
        event.stop()
        action = event.button.id
        if action == 'team-close':
            self.action_close()
        elif action == 'team-refresh':
            self.action_refresh()
        elif action == 'team-intra' and self.url:
            self.run_worker(partial(asyncio.to_thread, webbrowser.open, self.url))
        elif action == 'team-invite' and self._team() and self.candidate:
            team = self._team()
            size = ((self.state or {}).get('session') or {}).get('max_people')
            existing = {m['id'] for m in team['members']} if team else {int(self.account_id)}
            uid = int(self.candidate['user_id'])
            if uid not in existing and uid not in self.pending and size and len(existing) + len(self.pending) < size:
                self.pending[uid] = self.candidate['login']
                self.candidate = None
                self.query_one('#team-login', Input).value = ''
                self.query_one(FriendSuggestions).reset()
                self._pending()
        elif action == 'team-remove' and self.pending:
            self.pending.pop(next(reversed(self.pending)))
            self.search(SimpleNamespace(value=self.query_one('#team-login', Input).value))
            self._pending()
        elif action in {'team-save', 'team-accept', 'team-lock'} and not self.busy and not self.uncertain and self._same_account():
            request = {'action': {'team-save': 'save', 'team-accept': 'accept', 'team-lock': 'lock'}[action], 'team_id': self.selected}
            if action == 'team-save':
                name = self.query_one('#team-name', Input).value.strip()
                if not name:
                    error = self.query_one('#team-form-error', Static)
                    error.update(self.t('Enter a team name before creating the team.'))
                    error.display = True
                    self.query_one('#team-name', Input).focus()
                    return
                request.update(name=name, invite_ids=list(self.pending) if self._team() else [])
            self.busy = True
            self.query_one(FriendSuggestions).pause()
            self._controls()
            self.run_worker(partial(self._request, request, str(uuid4())), group='project-team', exclusive=True)

    def action_close(self):
        self.alive = False
        self.dismiss()

    def on_unmount(self):
        self.alive = False
