"""Dedicated, account-fenced read-only project attempt history."""
import asyncio
from copy import deepcopy
from functools import partial
from datetime import datetime
from ..activity.adapters.transport import authorization_status,open_browser,webbrowser
from ..activity.adapters.factory import resolve_activity_service

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Collapsible, ListItem, ListView, Static

from ft_tui.ui.button import Button
from ft_tui.features.projects.activity.models import project_activity, team_evaluations
from ft_tui.i18n import translate
from ft_tui.features.projects.activity.presentation import correction_phase, format_date, format_mark, source_text, team_summary
from ft_tui.app.read_cache import account_scope, app_cache, ReadDeferred


def open_project_activity(app, project_id, project_name, scope, account_id, provider, generation, intra_url):
    """Retain at most the last activity DOM, fenced by the same read scope."""
    key = (account_scope(app), project_id, project_name, scope.cursus_id, scope.campus_id,
           intra_url, getattr(app, 'language', 'en'))
    previous = getattr(app, '_last_activity_screen', None)
    if previous is not None:
        previous_key, screen = previous
        if screen in app.screen_stack:
            return None
        eligible = (previous_key == key and not screen._invalidated
                    and screen._cache().peek(screen._cache_key()) is not None)
        if eligible:
            screen._alive = True
            screen._resume_cache = True
            return app.push_screen(screen)
        app.uninstall_screen(screen)
        screen.remove()
    screen = ProjectActivityScreen(project_id, project_name, scope, account_id, provider, generation, intra_url)
    app.install_screen(screen, 'last-project-activity')
    app._last_activity_screen = (key, screen)
    return app.push_screen(screen)


class TeamEntry(ListItem):
    def __init__(self, team, current, language):
        super().__init__()
        self.team_id = team['id']
        self.caption = team['name'] + (' · ' + translate('Current', language) if current else '')
        self.meta = f"{team['status'].replace('_', ' ')} · {format_mark(team['final_mark'])}"

    def compose(self):
        yield Static(self.caption, markup=False)
        yield Static(self.meta, markup=False, classes='activity-muted')


class ProjectActivityScreen(Screen):
    FEEDBACK_LABEL = 'Your feedback'
    BINDINGS = [('escape', 'close', 'Close'), ('r', 'refresh', 'Refresh'), ('i', 'intra', 'Open on Intra')]
    DEFAULT_CSS = """
    ProjectActivityScreen { background: $surface; padding: 1 2; }
    #activity-heading { height: auto; text-style: bold; color: $accent; margin-bottom: 1; }
    #activity-status { height: auto; color: $text-muted; margin-bottom: 1; }
    #activity-body { height: 1fr; }
    #activity-sidebar { width: 32; min-width: 24; border: round $primary; padding: 0 1; margin-right: 2; }
    #activity-sidebar-title { height: 2; text-style: bold; color: $accent; }
    #activity-team-list { height: 1fr; background: transparent; }
    #activity-team-list TeamEntry { height: auto; min-height: 3; padding: 0 1 1 1; }
    #activity-team-list Static { height: auto; }
    #activity-detail { width: 1fr; border: round $secondary; padding: 1 2; }
    #activity-team-summary { height: auto; margin-bottom: 1; }
    #activity-evaluation-status { height: auto; color: $text-muted; margin-bottom: 1; }
    #activity-evaluations { height: auto; }
    #activity-evaluations Static { height: auto; }
    #activity-evaluations Collapsible { margin-bottom: 1; }
    .activity-section { margin-top: 1; margin-bottom: 1; color: $accent; text-style: bold; }
    .activity-muted { color: $text-muted; }
    .activity-comment { margin-bottom: 1; }
    #activity-controls { height: 3; margin-top: 1; }
    #activity-controls Button { width: 1fr; min-width: 0; margin-right: 1; }
    #activity-body.compact { layout: vertical; }
    #activity-body.compact #activity-sidebar { width: 1fr; height: 10; min-height: 6; margin: 0 0 1 0; }
    #activity-body.compact #activity-detail { width: 1fr; height: 1fr; padding: 0 1; }
    """

    def __init__(self, project_id, project_name, scope, account_id, provider, account_generation, intra_url, *, service=None):
        super().__init__()
        self._service=service
        self.project_id = project_id
        self.project_name = project_name
        self.scope = scope
        self.account_id = account_id
        self.provider = provider
        self.account_generation = account_generation
        self.intra_url = intra_url
        self.selected_team_id = None
        self.history = None
        self.evaluations = None
        self._epoch = 0
        self._alive = True
        self._invalidated = False
        self._refreshing = False
        self._force_evaluations = False
        self._history_error = None
        self._restoring_cache = False
        self._rendered_items = None

    @property
    def service(self):
        return self._service if self._service is not None else resolve_activity_service(self.app)

    def t(self, message):
        return translate(message, getattr(self.app, 'language', 'en'))

    def compose(self) -> ComposeResult:
        yield Static(f"{self.project_name} · {self.t('Attempts & evaluations')}", markup=False, id='activity-heading')
        yield Static(self.t('Loading attempts…'), markup=False, id='activity-status')
        with Horizontal(id='activity-body'):
            with Vertical(id='activity-sidebar'):
                yield Static(self.t('Attempts'), id='activity-sidebar-title', markup=False)
                yield ListView(id='activity-team-list')
            with VerticalScroll(id='activity-detail'):
                yield Static('', id='activity-team-summary', markup=False)
                yield Static('', id='activity-evaluation-status', markup=False)
                yield Vertical(id='activity-evaluations')
        with Horizontal(id='activity-controls'):
            yield Button(self.t('Refresh'), id='activity-refresh')
            yield Button(self.t('Open on Intra'), id='activity-intra', disabled=not self.intra_url)
            yield Button(self.t('Close'), id='activity-close', variant='danger')

    async def on_mount(self):
        self._read_scope = account_scope(self.app)
        self.query_one('#activity-body').set_class(self.size.width < 90, 'compact')
        self.set_interval(.25, self._check_identity)
        await self._open_cached_activity()
        self.query_one('#activity-team-list').focus()

    async def on_screen_resume(self):
        if getattr(self, '_resume_cache', False):
            self._resume_cache = False
            if not self._same_account():
                self._invalidate('Account changed. Close this screen and reopen it.')
                return
            self._refreshing = False
            self.query_one('#activity-refresh', Button).disabled = False
            await self._open_cached_activity()

    def _cache_key(self, team_id=None):
        return self.service.key(self._read_scope,self.scope.cursus_id,self.scope.campus_id,self.project_id,team_id)

    def _cache(self):
        return app_cache(self.app)

    async def _open_cached_activity(self):
        if not self._same_account():
            return
        cached = self._cache().peek(self._cache_key())
        if cached:
            fresh_history = self._cache().fresh(self._cache_key())
            if not fresh_history:
                cached['source']['stale'] = True
            self._refreshing = True
            self._restoring_cache = True
            try:
                await self._display_history(cached, self._epoch, self.selected_team_id)
                if self.evaluations:
                    await self._display_evaluations(self.evaluations, self.selected_team_id, self._epoch)
            finally:
                self._restoring_cache = False
                self._refreshing = False
            self._show_source_status()
            if fresh_history:
                if self.selected_team_id is None or self._cache().fresh(self._cache_key(self.selected_team_id)):
                    return
                self.run_worker(partial(self._load_evaluations, self.selected_team_id, self._epoch, False),
                                group='activity-evaluations', exclusive=True)
                return
        self.action_refresh(initial=True)

    def on_resize(self, event: events.Resize):
        if self.is_mounted:
            self.query_one('#activity-body').set_class(event.size.width < 90, 'compact')

    def _same_account(self):
        # Textual hides pruning screens before detaching their children or sending Unmount.
        return (self._alive and self.display and self.is_attached and not self._invalidated
                and self._current_scope()
                and getattr(self.app, 'provider', None) is self.provider
                and getattr(self.app, 'account_id', None) == self.account_id
                and getattr(self.app, 'account_generation', None) == self.account_generation)

    def _current_scope(self):
        if account_scope(self.app) != self._read_scope:
            return False
        return self.service.cursus_matches(self.scope.cursus_id)

    def _invalidate(self, message, *, clear_scope=True):
        if clear_scope:
            self._cache().invalidate(lambda key: key[0] == self._read_scope)
        self._invalidated = True
        self._epoch += 1
        self.workers.cancel_node(self)
        self.selected_team_id = None
        self.history = self.evaluations = None
        self.query_one('#activity-team-list').clear()
        self.query_one('#activity-team-summary', Static).update('')
        self.query_one('#activity-evaluations').display = False
        self.query_one('#activity-evaluations').remove_children()
        self.query_one('#activity-evaluation-status', Static).update('')
        self.query_one('#activity-status', Static).update(self.t(message))
        self.query_one('#activity-refresh', Button).disabled = True

    def _authorization_failed(self, error):
        if authorization_status(error) == 401:
            self._invalidate('Session expired. Close this screen and reconnect your account.')
            return True
        if authorization_status(error) == 403:
            self._invalidate('Access denied by 42.', clear_scope=False)
            return True
        return False

    def _check_identity(self):
        if not self._alive or not self.is_mounted or not self.display:
            return
        if not self._same_account() and not self._invalidated:
            self._invalidate('Account changed. Close this screen and reopen it.')
        elif self._same_account() and self.history and not self._refreshing:
            self._show_source_status()

    def _show_source_status(self):
        if not self._same_account():
            return
        language = getattr(self.app, 'language', 'en')
        if self.history:
            status = source_text('Attempts', self.history['source'], language)
            if not self.history['teams'] and self.history['source']['status'] == 'available' and not self.history['source']['stale']:
                status = self.t('No attempts for this project.') + '\n' + status
            if self._history_error:
                status += '\n' + self._history_error
            if self._refreshing:
                status = self.t('Refreshing…') + '\n' + status
            self.query_one('#activity-status', Static).update(status)
        if self.evaluations:
            self.query_one('#activity-evaluation-status', Static).update('\n'.join(
                source_text(label, self.evaluations[key]['source'], language)
                for label, key in [('Peer evaluations', 'peer'), ('Automated evaluations', 'automated')]))

    def action_refresh(self, initial=False):
        if self._refreshing or not self._same_account():
            return
        self._refreshing = True
        self._epoch += 1
        self._force_evaluations = not initial
        self.query_one('#activity-refresh', Button).disabled = True
        if not self.history:
            self.query_one('#activity-status', Static).update(self.t('Loading attempts…'))
        else:
            self._show_source_status()
        self.run_worker(partial(self._load_history, self._epoch, not initial), group='activity-history', exclusive=True)

    async def _load_history(self, epoch, refresh):
        previous = self.selected_team_id
        try:
            value = await self.service.read(self._cache(),self._cache_key(),self._read_history,refresh,self._current_scope)
            if not self._same_account() or epoch != self._epoch:
                return
            await self._display_history(value, epoch, previous)
        except Exception as error:
            if self._same_account() and epoch == self._epoch:
                if self._authorization_failed(error):
                    return
                deferred = isinstance(error, ReadDeferred) or getattr(getattr(error, 'response', None), 'status_code', None) == 429
                self._history_error = self.t('Rate limited; retry later.' if deferred else 'Could not load attempts. Refresh to try again.')
                if self.history:
                    self.history['source'] = {**self.history['source'], 'status': 'unavailable', 'stale': True}
                self.query_one('#activity-status', Static).update(self._history_error)
        finally:
            self._refreshing = False
            if self._same_account():
                self.query_one('#activity-refresh', Button).disabled = False
                self._show_source_status()

    def _read_history(self, refresh):
        return self.service.history(self.provider,self.project_id,self.scope,self.account_id,refresh=refresh)

    def _read_evaluations(self, team_id, refresh):
        return self.service.evaluations(self.provider,self.project_id,team_id,self.scope,self.account_id,refresh=refresh)

    async def _display_history(self, value, epoch, previous=None):
        unchanged = (self.history is not None and self.history['teams'] == value['teams']
                     and self.history['current_team_id'] == value['current_team_id'])
        self.history = value
        self._history_error = None
        listing = self.query_one('#activity-team-list', ListView)
        if not unchanged:
            await listing.clear()
        if not self._same_account() or epoch != self._epoch:
            return
        teams = self._ordered_teams(value)
        if not unchanged:
            await listing.extend(TeamEntry(team, team['id'] == value['current_team_id'], getattr(self.app, 'language', 'en')) for team in teams)
        if not self._same_account() or epoch != self._epoch:
            return
        if not teams:
            self.selected_team_id = None
            self.evaluations = None
            if value['source']['status'] == 'available' and not value['source']['stale']:
                self.query_one('#activity-status', Static).update(self.t('No attempts for this project.'))
            else:
                self._show_source_status()
            self.query_one('#activity-team-summary', Static).update('')
            self.query_one('#activity-evaluations').display = False
            self.query_one('#activity-evaluation-status', Static).update('')
            return
        ids = [team['id'] for team in teams]
        target = previous if previous in ids else value['current_team_id'] if value['current_team_id'] in ids else ids[0]
        listing.index = ids.index(target)
        self._select_team(target, revalidate=True)
        self._show_source_status()

    @staticmethod
    def _ordered_teams(value):
        return sorted(value['teams'], key=lambda x: (datetime.fromisoformat(x['created_at'].replace('Z', '+00:00')).timestamp()
                      if x['created_at'] else float('-inf'), x['id']), reverse=True)

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        if event.list_view.id == 'activity-team-list':
            event.stop()
            if isinstance(event.item, TeamEntry) and not self._refreshing:
                self._select_team(event.item.team_id)

    def _select_team(self, team_id, *, revalidate=False):
        if not self._same_account() or not self.history or self.selected_team_id == team_id and not revalidate:
            return
        changed = self.selected_team_id != team_id
        team = next(t for t in self.history['teams'] if t['id'] == team_id)
        self.selected_team_id = team_id
        if changed:
            self.evaluations = None
        self._epoch += 1
        epoch = self._epoch
        self.query_one('#activity-team-summary', Static).update(team_summary(team, current=team_id == self.history['current_team_id'], language=getattr(self.app, 'language', 'en')))
        cached = self._cache().peek(self._cache_key(team_id))
        if cached:
            self.evaluations = cached
            if not self._cache().fresh(self._cache_key(team_id)):
                for kind in ('peer', 'automated'):
                    self.evaluations[kind]['source']['stale'] = True
        else:
            self.query_one('#activity-evaluations').display = False
            self.query_one('#activity-evaluation-status', Static).update(self.t('Loading evaluations…'))
        refresh = self._force_evaluations
        self._force_evaluations = False
        if not self._restoring_cache:
            self.run_worker(partial(self._load_evaluations, team_id, epoch, refresh), group='activity-evaluations', exclusive=True)

    async def _load_evaluations(self, team_id, epoch, refresh):
        def current():
            return self._same_account() and self.selected_team_id == team_id and self._epoch == epoch
        try:
            if self.evaluations:
                await self._display_evaluations(self.evaluations, team_id, epoch)
            value = await self.service.read(self._cache(),self._cache_key(team_id),partial(self._read_evaluations,team_id),refresh,self._current_scope)
            if not current():
                return
            await self._display_evaluations(value, team_id, epoch)
        except Exception as error:
            if current():
                if self._authorization_failed(error):
                    return
                deferred = isinstance(error, ReadDeferred) or getattr(getattr(error, 'response', None), 'status_code', None) == 429
                self.query_one('#activity-evaluation-status', Static).update(self.t(
                    'Rate limited; retry later.' if deferred else 'Could not load evaluations. Refresh to try again.'))

    async def _display_evaluations(self, value, team_id, epoch):
        def current():
            return self._same_account() and self.selected_team_id == team_id and self._epoch == epoch
        if not current():
            return
        container = self.query_one('#activity-evaluations', Vertical)
        fingerprint = self._evaluation_fingerprint(value, team_id)
        if self._rendered_items == fingerprint and container.children:
            self.evaluations = value
            container.display = True
            self._show_source_status()

            return
        expanded = {widget.id for widget in container.query(Collapsible) if not widget.collapsed}
        scroll = self.query_one('#activity-detail', VerticalScroll).scroll_y
        await container.remove_children()
        if not current():
            return
        self.evaluations = value
        widgets = list(self._evaluation_widgets(value))
        await container.mount(*widgets)
        if current():
            self._rendered_items = deepcopy(fingerprint)
            for widget in container.query(Collapsible):
                if widget.id in expanded:
                    widget.collapsed = False
            self.query_one('#activity-detail', VerticalScroll).scroll_to(y=scroll, animate=False)
            container.display = True
            self._show_source_status()

    @staticmethod
    def _evaluation_fingerprint(value, team_id):
        return (team_id, value['peer']['items'], value['automated']['items'],
                value['peer']['source']['status'], value['automated']['source']['status'])

    def _literal(self, text, **kwargs):
        return Static(text, markup=False, **kwargs)

    def _peer_sections(self, value):
        return [(False, 'Scheduled & pending evaluations'), (True, 'Completed evaluations')]

    def _show_automated(self, value):
        return True

    def _evaluation_widgets(self, value):
        peers = value['peer']['items']
        for completed, title in self._peer_sections(value):
            yield self._literal(self.t(title), classes='activity-section')
            group = [item for item in peers if bool(item['filled_at']) == completed]
            if not group and value['peer']['source']['status'] == 'available':
                yield self._literal(self.t('No evaluations in this section.'), classes='activity-muted')
            for item in group:
                corrector = item['corrector']['login'] if item['corrector'] else self.t('Hidden') if item['participants_hidden'] else '—'
                phase = self.t(correction_phase(item))
                caption = f"{corrector} · {format_mark(item['final_mark'])} · {phase} · {format_date(item['begin_at'])}"
                details = [self._literal(self.t('Correction comment'), classes='activity-muted'),
                           self._literal(item['comment'] or self.t('No comment available.'), id=f"peer-comment-{item['id']}", classes='activity-comment'),
                           self._literal(self.t(self.FEEDBACK_LABEL), classes='activity-muted'),
                           self._literal(item['feedback'] or self.t('No feedback available.'), classes='activity-comment')]
                if item.get('details_unavailable'):
                    details.append(self._literal(self.t('Additional correction details are restricted by 42.'), classes='activity-muted'))
                if item['filled_at']:
                    details.append(self._literal(f"{self.t('Completed')}: {format_date(item['filled_at'])}"))
                if item['flag']:
                    details.append(self._literal(item['flag']['name']))
                if item['feedback_rating'] is not None:
                    details.append(self._literal(f"{self.t('Feedback rating')}: {item['feedback_rating']:g}"))
                for feedback in item['feedbacks']:
                    details.append(self._literal(feedback['comment'] or self.t('No feedback available.')))
                    if feedback['rating'] is not None:
                        details.append(self._literal(f"{self.t('Feedback rating')}: {feedback['rating']:g}"))
                # Collapsible titles accept Rich markup; escape only this title.
                from rich.markup import escape
                yield Collapsible(*details, title=escape(caption), id=f"peer-evaluation-{item['id']}", collapsed=True)
        if not self._show_automated(value):
            return
        yield self._literal(self.t('Automated evaluations'), classes='activity-section')
        if not value['automated']['items'] and value['automated']['source']['status'] == 'available':
            yield self._literal(self.t('No automated evaluations.'), classes='activity-muted')
        for item in value['automated']['items']:
            from rich.markup import escape
            caption = f"{item['name']} · {format_mark(item['final_mark'])} · {format_date(item['created_at'])}"
            yield Collapsible(self._literal(item['comment'] or self.t('No output available.'), id=f"automated-output-{item['id']}"),
                              title=escape(caption), id=f"automated-evaluation-{item['id']}", collapsed=True)

    async def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == 'activity-close':
            self.action_close()
        elif event.button.id == 'activity-refresh':
            self.action_refresh()
        elif event.button.id == 'activity-intra':
            await self.action_intra()

    async def action_intra(self):
        if self.intra_url:
            try:
                if not await asyncio.to_thread(open_browser, self.intra_url):
                    raise OSError('Browser unavailable')
            except Exception:
                self.notify(self.t('Could not open the project page.'), severity='error')

    def action_close(self):
        self._alive = False
        self._epoch += 1
        self.workers.cancel_node(self)
        self.app.pop_screen()

    def on_unmount(self):
        self._alive = False
        self._epoch += 1
        self.workers.cancel_node(self)
