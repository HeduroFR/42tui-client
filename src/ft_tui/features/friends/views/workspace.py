"""API-backed Friends workspace with account-scoped offline observations."""
import asyncio
from datetime import datetime, timezone

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widget import Widget
from textual.widgets import DataTable, ProgressBar, TabbedContent

from ft_tui.features.friends.models import LOGIN, friend_snapshot
from ft_tui.services.fuzzy_search import fuzzy_score
from ft_tui.features.friends.adapters.storage import FriendIdentityChanged
from ft_tui.features.friends.projections import (
    comparison, curriculum_rankings, ongoing, level_rankings, project_rankings,
    validated_project_count,
)
from ft_tui.ui.components import Button, Input, Select, Static
from ft_tui.i18n import translate
from ft_tui.app.read_cache import account_scope, app_cache, backend_origin, ReadDeferred
from ft_tui.features.friends.views.suggestions import FriendSuggestions
from ft_tui.features.friends.views.search import FriendSearchScreen


def friends_service_for(host):
    """Use injected app service; standalone harnesses retain the production default."""
    service = getattr(host,'_friends_feature_service',None)
    if service is None:
        service = getattr(host.app,'friends_service',None)
    if service is None:
        from ft_tui.app.bootstrap import build_friends_service
        service = build_friends_service(host.app.session_factory)
    host._friends_feature_service = service
    return service


def freshness(data, *, offline=False, language='en'):
    if not data:
        return translate('Not synced', language)
    meta = data['meta']
    stamp = datetime.fromisoformat(meta['cached_at'].replace('Z', '+00:00'))
    seconds = max(0, int((datetime.now(timezone.utc) - stamp).total_seconds()))
    value, unit = next((seconds // size, unit) for size, unit in
                       ((86400, 'd'), (3600, 'h'), (60, 'm'), (1, 's')) if seconds >= size or size == 1)
    age = translate('{age} ago', language).format(age=f'{value}{unit}')
    if offline:
        return age + ' · ' + translate('Saved data · offline', language)
    if meta.get('stale'):
        return age + ' · ' + translate('Saved data · stale', language)
    return age


def current_location(data, *, app=None, login=None, user_id=None):
    presence = (data or {}).get('presence') or {}
    cached_at = presence.get('cached_at')
    stamp = None
    if isinstance(cached_at, str):
        try:
            stamp = datetime.fromisoformat(cached_at.replace('Z', '+00:00'))
        except ValueError:
            pass
    if stamp is not None and stamp.tzinfo is None:
        stamp = None
    available = presence.get('status') == 'available'
    if app is not None:
        from ft_tui.features.cluster_map.views.cluster_map import observed_seat
        observed = observed_seat(app, login or (data or {}).get('login'), user_id or (data or {}).get('user_id'))
        if observed:
            if not available or stamp is None or observed[1] >= stamp:
                return observed[0]
    if not available or stamp is None:
        return 'Unavailable'
    if not 0 <= (datetime.now(timezone.utc) - stamp).total_seconds() < 60:
        return 'Unavailable'
    return data.get('location') or 'No active session'


def project_attempt_sort_key(item):
    priority = {
        'in_progress': 0, 'waiting_for_correction': 1, 'waiting_to_start': 2,
        'creating_group': 3, 'searching_a_group': 4,
    }
    group = 6 if item.get('validated') is True else priority.get(item['status'], 5)
    return group, item['name'].casefold(), -item['id']


class FriendsTable(DataTable):
    """Keep every friends column inside the current browser viewport."""

    def on_resize(self):
        self.call_after_refresh(self.fit_columns)

    def fit_columns(self):
        if not self.columns or not self.scrollable_content_region.width:
            return
        columns = self.ordered_columns
        preferred = [max(width, column.label.cell_len) for column, width in zip(
            columns, (3, 12, 7, 5, 18, 16, 12, 12))]
        budget = max(len(columns), self.scrollable_content_region.width - 2*self.cell_padding*len(columns))
        widths = preferred.copy()
        minimum = (1, 8, 4, 5, 5, 10, 1, 7)
        while sum(widths) > budget:
            candidates = [i for i, width in enumerate(widths) if width > minimum[i]]
            if not candidates:
                candidates = [i for i, width in enumerate(widths) if width > 1]
            if not candidates:
                break
            index = max(candidates, key=lambda i: widths[i])
            widths[index] -= 1
        if widths == [column.width for column in columns]:
            return
        rows = [(row.key.value, self.get_row(row.key)) for row in self.ordered_rows]
        cursor = self.cursor_coordinate
        scroll_y = self.scroll_y
        labels = [column.label for column in columns]
        keys = [column.key.value for column in columns]
        with self.app.batch_update(), self.prevent(self.RowHighlighted):
            self.clear(columns=True)
            for label, key, width in zip(labels, keys, widths):
                self.add_column(label, key=key, width=width)
            for key, values in rows:
                self.add_row(*values, key=key)
            self.move_cursor(row=cursor.row, column=cursor.column, scroll=False)
            self.scroll_to(x=0, y=scroll_y, animate=False, force=True)


class FriendsSearchSuggestions(FriendSuggestions):
    """Merge local fuzzy friend matches with the shared directory dropdown."""

    def __init__(self, workspace):
        super().__init__(purpose='navigate')
        self.workspace = workspace

    def result_candidates(self):
        matches = []
        for watch in self.workspace.watches:
            data = self.workspace.snapshots.get(watch.login, {})
            name = data.get('display_name') or watch.login
            score = fuzzy_score(self.query, watch.login, name)
            if score is not None:
                matches.append((score, watch.login, {
                    'user_id': watch.user_id or 'friend:' + watch.login,
                    'login': watch.login, 'display_name': name + ' · ' + self.t('Friend'),
                }))
        local = {row['user_id']: row for _, _, row in sorted(matches)[:20]}
        logins = {row['login'].casefold() for row in local.values()}
        return {**local, **{key: row for key, row in self.candidates.items()
                             if row['login'].casefold() not in logins and key not in local}}


class FriendsWorkspace(Vertical):
    """Owns friend workers so navigation and account changes cannot publish old results."""

    COMPONENT_CLASSES = {'friends--self'}

    BINDINGS = [Binding('escape', 'back_to_friends', show=False)]

    def check_action(self, action, parameters):
        if action == 'back_to_friends':
            return bool(self.selected_login)
        return True

    def action_back_to_friends(self):
        self.selected_login = None
        self._refresh_view()
        self.query_one('#friends-table', DataTable).focus()

    def __init__(self, *, service=None):
        super().__init__(id='friends-workspace')
        self._friends_feature_service = service
        self.context = None
        self.epoch = 0
        self.snapshots = {}
        self.watches = []
        self.errors = {}
        self.selected_login = None
        self.expanded_friend = False
        self._highlighted_login = None
        self.rankings = False
        self.comparing = False
        self.busy = False
        self.worker = None
        self.add_worker = None
        self.adding = False
        self.pending_logins = set()
        self.sync_total = self.sync_done = self.sync_successes = self.sync_errors = 0
        self.last_sync = 0.0
        self.tables_ready = False
        self.search_screen = None
        self.detail_snapshots = {}
        self.detail_worker = None
        self.detail_busy = False
        self.detail_attempted = set()
        self._project_rows = None
        self._force_details = False

    def compose(self):
        from ft_tui.features.social.views.inbox import SocialInbox
        with Vertical(id='friends-toolbar'):
            with Vertical(id='friends-heading'):
                with Horizontal(id='friends-search-row'):
                    yield Input(placeholder='Search friends or students', id='friends-search')
                    yield Button('Add friend', icon='➕', id='friends-open-search', variant='primary')
                    yield Select([('All friends', 'all'), ('On my projects', 'shared'),
                                  ('Same campus', 'campus'), ('In a cluster', 'online')],
                                 value='all', id='friends-filter')
                with Horizontal(id='friends-actions-row'):
                    yield Button('Show ranking', icon='🏆', id='friends-view-rankings')
                    yield Select([('Curriculum ↓', 'curriculum'), ('Level ↓', 'level'),
                                  ('Validated projects ↓', 'projects')], value='curriculum', id='friends-ranking-metric')
                    yield Button('Requests', icon='📩', id='social-toggle')
                    yield Button('Pokes', icon='👋', icon_only=True, square=False, id='friends-pokes')
                    yield Button('Refresh', icon='↻', icon_only=True, square=False, id='friends-refresh')
            yield FriendsSearchSuggestions(self)
        yield SocialInbox(external_toggle=True)
        yield ProgressBar(total=1, show_eta=False, show_percentage=False, id='friends-sync-progress')
        yield Static('', id='friends-sync-status', markup=False, localize=False)
        with Horizontal(id='friends-columns'):
            with Vertical(id='friends-browser'):
                yield FriendsTable(id='friends-table', cursor_type='row', zebra_stripes=True)
                yield Static('', id='friends-empty', markup=False, localize=False)
            with Vertical(id='friend-details'):
                with Horizontal(id='friend-details-actions'):
                    yield Button('Back', icon='←', icon_only=True, square=False, id='friend-back')
                    yield Button('View profile', icon='👤', id='friend-view-profile')
                    yield Button('Projects', icon='📚', id='friend-view-projects', variant='primary')
                    yield Button('Compare with me', icon='⇄', icon_only=True, square=False, id='friend-view-compare')
                    yield Button('Poke', icon='👋', icon_only=True, square=False, id='friend-poke', disabled=True)
                    yield Button('Remove', icon='🗑', icon_only=True, square=False, id='friend-remove', disabled=True)
                with VerticalScroll(id='friend-profile-scroll'):
                    yield Static('Select a friend', id='friend-profile', markup=False, localize=False)
                    yield Static('', id='friend-comparison', markup=False, localize=False)
                with Horizontal(id='friend-project-heading'):
                    yield Static('Project attempts', id='friend-project-caption')
                    yield Button('View project', icon='↗', id='friend-project-access', disabled=True, variant='primary')
                yield DataTable(id='friend-projects', cursor_type='row', zebra_stripes=True)

    def t(self, source, **values):
        return translate(source, self.app.language).format(**values) if values else translate(source, self.app.language)

    def _freshness(self, data):
        return freshness(data, offline=not self.app.account_connected, language=self.app.language)

    def apply_language(self):
        if not self.tables_ready:
            return
        table = self.query_one('#friends-table', DataTable)
        table.clear(columns=True)
        for name, width in [('#', 3), ('Login', 12), ('Rank', 7), ('Level', 5),
                            ('Validated projects', 18), ('Working on', 16), ('Cluster', 12), ('Freshness', 12)]:
            table.add_column(self.t(name), width=max(width, len(self.t(name))))
        projects = self.query_one('#friend-projects', DataTable)
        projects.clear(columns=True)
        projects.add_columns(*(self.t(name) for name in ('Project', 'Status', 'Mark', 'Attempt ID')))
        self._refresh_view()
        self.query_one(FriendsTable).call_after_refresh(self.query_one(FriendsTable).fit_columns)

    async def on_mount(self):
        self.tables_ready = True
        self.apply_language()
        self.app.theme_changed_signal.subscribe(self, lambda theme: self._refresh_view())
        self.set_interval(60, self._poll)
        self._responsive()

    def _scope(self):
        app = self.app
        cursus = friends_service_for(self).configured_cursus(getattr(app,'_configured_cursus_id',None))
        return (app.account_generation, app.account_id, cursus, id(app.provider), backend_origin(app))

    def _read_key(self, resource, *parts):
        return (account_scope(self.app), resource, self.context[2], *parts)

    async def _read(self, resource, parts, fetch, *, refresh=False, commit=None):
        context = self.context
        return await app_cache(self.app).read(self._read_key(resource, *parts), fetch,
            refresh=refresh, current=lambda: context == self._scope(), commit=commit)

    def _valid(self, epoch, context):
        return self.is_mounted and self.is_attached and epoch == self.epoch and context == self.context == self._scope()

    def _authorization_lost(self):
        self.snapshots.clear()
        self.detail_snapshots.clear()
        self.watches = []
        self.selected_login = None

    def _profile_forbidden(self, login, context):
        self.snapshots.pop(login, None)
        self.detail_snapshots.pop(login, None)
        app_cache(self.app).invalidate(lambda key: len(key) > 3 and key[2] == context[2] and (
            key[1] in ('friend-summary', 'friend-detail') and key[3] == login
            or key[1] == 'friend-batch' and login in key[3]))
        friends_service_for(self).forget(context[1],context[2],login,origin=context[4])

    def _stop(self):
        self.query_one(FriendsSearchSuggestions).reset()
        if self.search_screen and self.search_screen.is_mounted:
            self.search_screen.query_one(FriendSuggestions).reset()
            self.search_screen.dismiss()
        self.search_screen = None
        if self.detail_worker:
            self.detail_worker.cancel()
        self.detail_busy = False
        self.detail_attempted.clear()
        self.detail_snapshots.clear()
        self.epoch += 1
        if self.worker:
            self.worker.cancel()
        if self.add_worker:
            self.add_worker.cancel()
        self.busy = self.adding = False
        self.pending_logins.clear()
        self.sync_total = self.sync_done = self.sync_successes = self.sync_errors = 0

    async def reload(self):
        context = self._scope()
        if context != self.context:
            self._stop()
            self.context = context
            self.selected_login = None
            self.errors = {}
            self.last_sync = 0
            self.snapshots = friends_service_for(self).cached(context[1],context[2],origin=context[4])
            self.detail_snapshots = {login: data for login, data in self.snapshots.items() if data.get('details_complete') is not False}
        self.watches = friends_service_for(self).memberships(context[1],origin=context[4])
        allowed = {w.login for w in self.watches} | {self.app.account_login}
        self.snapshots = {k: v for k, v in self.snapshots.items() if k in allowed or v['user_id'] == context[1]}
        if self.selected_login not in allowed:
            self.selected_login = None
        self._refresh_view()
        if self.app.query_one(TabbedContent).active == 'friends':
            self.start_sync()

    async def activate(self):
        await self.reload()

    def start_sync(self, *, refresh=False):
        if self.busy or self.adding or not self.app.account_connected or not self.app.provider or not self.context or not all(self.context[1:3]):
            return
        now = asyncio.get_running_loop().time()
        if not refresh and now - self.last_sync < 60:
            return
        self.last_sync = now
        self._force_details = refresh
        self.sync_total = len(self._sync_targets())
        self.sync_done = self.sync_successes = self.sync_errors = 0
        self.busy = True
        self.worker = self.run_worker(self._sync(self.epoch, self.context, refresh), group='friends-sync', exclusive=True)
        self._render_status()

    async def _poll(self):
        if self.app.query_one(TabbedContent).active == 'friends':
            await self.reload()

    async def _fetch(self, login, epoch, context, refresh, expected_user_id=None):
        provider = self.app.provider
        async def load():
            return await friends_service_for(self).summary(
                provider,login,context[2],refresh=refresh,expected_user_id=expected_user_id,
                owner_login=self.app.account_login,account_id=context[1])

        def persist(value):
            friends_service_for(self).save(context[1],value,origin=context[4])

        value = await self._read('friend-summary', (login, expected_user_id), load, refresh=refresh, commit=persist)
        if not self._valid(epoch, context):
            return
        value = friend_snapshot(value, login, context[2], user_id=expected_user_id)
        if login == self.app.account_login and value['user_id'] != context[1]:
            raise ValueError('Account identity mismatch')
        self.snapshots[value['login']] = value
        self.errors.pop(login, None)
        if value.get('details_complete') is not False:
            self.detail_snapshots[value['login']] = value
        return value

    def _sync_targets(self):
        targets = list(dict.fromkeys(login for login in [self.app.account_login] + [w.login for w in self.watches] if login))
        table = self.query_one('#friends-table', DataTable)
        top = max(0, int(table.scroll_y))
        visible = [str(row.key.value) for row in table.ordered_rows[top:top + max(1, table.size.height)]]
        targets = [login for login in visible if login in targets] + [login for login in targets if login not in visible]
        if self.selected_login in targets:
            targets.remove(self.selected_login)
            targets.insert(0,self.selected_login)
        return targets

    async def _sync(self, epoch, context, refresh):
        targets = self._sync_targets()
        batch = getattr(getattr(getattr(self, 'app', None), 'provider', None), 'get_friend_summaries', None)
        if callable(batch) and not refresh:
            import httpx
            try:
                cached = []
                for offset in range(0, len(targets), 50):
                    logins = targets[offset:offset+50]
                    async def load_batch():
                        return await friends_service_for(self).batch(
                            self.app.provider,logins,context[2],owner_login=self.app.account_login,account_id=context[1])
                    cached.extend(await self._read('friend-batch', (tuple(logins),), load_batch))
                if not self._valid(epoch, context):
                    return
                for data in cached:
                    friend_snapshot(data, data['login'], context[2])
                    if data['login'] == self.app.account_login and data['user_id'] != context[1]:
                        raise ValueError('Account identity mismatch')
                    friends_service_for(self).save(context[1],data,origin=context[4])
                    self.snapshots[data['login']] = data
                    self.errors.pop(data['login'], None)
                self._refresh_view()
                fresh = {data['login'] for data in cached if not data['meta']['stale'] and current_location(data) != 'Unavailable'}
                self.sync_done += len(fresh)
                self.sync_successes += len(fresh)
                targets = [login for login in self._sync_targets() if login not in fresh]
            except httpx.HTTPStatusError as error:
                if error.response.status_code == 401:
                    if not self._valid(epoch, context):
                        return
                    self.busy = False
                    self._authorization_lost()
                    if targets:
                        self.errors[targets[0]] = self._error(error)
                    self._refresh_view()
                    return
                # Older backends and temporarily unavailable caches retain per-profile fallback.
            except Exception:
                pass
        self.pending_logins = set(targets)
        queue = iter(targets)
        authorization_failed = False

        async def consume():
            nonlocal authorization_failed
            for login in queue:
                if authorization_failed or not self._valid(epoch, context):
                    return
                try:
                    await self._fetch(login, epoch, context, refresh)
                    if self._valid(epoch, context):
                        self.sync_successes += 1
                except Exception as error:
                    if self._valid(epoch, context):
                        self.errors[login] = self._error(error)
                        self.sync_errors += 1
                    import httpx
                    if isinstance(error, httpx.HTTPStatusError):
                        if error.response.status_code == 401:
                            authorization_failed = True
                            self._authorization_lost()
                        elif error.response.status_code == 403 and self._valid(epoch, context):
                            self._profile_forbidden(login, context)
                if not self._valid(epoch, context):
                    return
                self.sync_done += 1
                self.pending_logins.discard(login)
                self._refresh_view()

        try:
            # Two profiles overlap without a large burst against the shared API budget.
            # Keep selected-first dispatch without waiting for slow profiles.
            # TaskGroup also cancels every consumer on navigation/account changes.
            async with asyncio.TaskGroup() as group:
                for _ in range(min(2, len(targets))):
                    group.create_task(consume())
        finally:
            if self._valid(epoch, context):
                self.busy = False
                self.pending_logins.clear()
                self._refresh_view()
                self.detail_attempted.clear()
                if not authorization_failed:
                    self._ensure_details()

    def _ensure_details(self):
        if self.busy or self.detail_busy or not self.app.account_connected or not callable(getattr(self.app.provider, 'get_friend_summary', None)):
            return
        self.detail_busy = True
        self.detail_worker = self.run_worker(self._enrich_details(self.epoch, self.context), group='friends-details', exclusive=True)

    async def _enrich_details(self, epoch, context):
        try:
            while self._valid(epoch, context):
                targets = [login for login in self._sync_targets() if login not in self.detail_attempted and (
                    self.snapshots.get(login, {}).get('projects_loaded') is False
                    or self.snapshots.get(login, {}).get('details_complete') is False and self.snapshots.get(login, {}).get('meta', {}).get('stale')
                    or login == self.selected_login and self.snapshots.get(login, {}).get('details_complete') is False
                    or self.comparing and login == self.app.account_login and self.snapshots.get(login, {}).get('details_complete') is False)]
                if not targets:
                    return
                login = targets[0]
                self.detail_attempted.add(login)
                try:
                    provider = self.app.provider
                    refresh = self._force_details
                    async def load_detail():
                        return await friends_service_for(self).detail(
                            provider,login,context[2],refresh=refresh,
                            owner_login=self.app.account_login,account_id=context[1])
                    def persist_detail(data):
                        friends_service_for(self).save(context[1],data,origin=context[4])
                    data = await self._read('friend-detail', (login,), load_detail, refresh=refresh, commit=persist_detail)
                    if not self._valid(epoch, context):
                        return
                    friend_snapshot(data, login, context[2])
                    if login == self.app.account_login and data['user_id'] != context[1]:
                        raise ValueError('Account identity mismatch')
                    self.detail_snapshots[login] = self.snapshots[login] = data
                    self.errors.pop(login, None)
                except Exception as error:
                    if not self._valid(epoch, context):
                        return
                    self.errors[login] = self._error(error)
                    import httpx
                    if isinstance(error, httpx.HTTPStatusError):
                        if error.response.status_code == 403:
                            self._profile_forbidden(login, context)
                        elif error.response.status_code in (401, 429):
                            if error.response.status_code == 401:
                                self._authorization_lost()
                            self._refresh_view()
                            return
                self._refresh_view()
        finally:
            if self._valid(epoch, context):
                self.detail_busy = False
                self._force_details = False

    @staticmethod
    def _error(error):
        import httpx
        if isinstance(error, httpx.HTTPStatusError):
            return {401: 'Reconnect your 42 account.', 403: 'Access denied by 42.',
                    404: 'Login not found.', 429: 'Rate limited; retry later.'}.get(error.response.status_code, 'Refresh failed; saved data retained.')
        if isinstance(error, FriendIdentityChanged):
            return 'Friend identity changed; remove and re-add this login to confirm it.'
        if isinstance(error, ValueError):
            return 'Response or friend identity could not be verified.'
        if isinstance(error, ReadDeferred):
            return 'Rate limited; retry later.'
        return 'Refresh failed; saved data retained.'

    def _render_status(self):
        account, cursus = self.context[1:3] if self.context else (None, None)
        ready = bool(account and cursus and self.app.account_connected and self.app.provider)
        candidate = self.query_one(FriendsSearchSuggestions).highlighted_candidate()
        included = candidate and (candidate['login'] == self.app.account_login or any(w.login == candidate['login'] for w in self.watches))
        self.query_one('#friends-open-search', Button).disabled = not (account and self.app.account_connected and self.app.provider and candidate) or bool(included) or self.adding
        if self.search_screen and self.search_screen.is_mounted:
            self.search_screen.set_busy(self.adding or self.busy)
        self.query_one('#friends-refresh', Button).disabled = not ready or self.busy or self.adding
        if not account:
            message = self.t('Connect your 42 account to use Friends.')
        elif not cursus:
            message = self.t('Choose a cursus in Settings to see progress and rankings.')
        else:
            mode = 'Refreshing…' if self.busy else 'Checking login…' if self.adding else 'Saved data · offline' if not ready else 'Automatic refresh · every minute while open'
            errors = ' · ' + self.t('{count} refresh error(s)', count=len(self.errors)) if self.errors else ''
            message = self.t('Cursus {cursus} · {count} friends · {mode}', cursus=cursus, count=len(self.watches), mode=self.t(mode)) + errors
            if self.sync_total:
                message += ' · ' + self.t('Refreshing {done}/{total} profiles' if self.busy else 'Refresh {done}/{total} profiles',
                                          done=self.sync_done, total=self.sync_total)
                message += ' · ' + self.t('{successes} succeeded · {errors} failed',
                                          successes=self.sync_successes, errors=self.sync_errors)
            if self.rankings:
                expected = len({w.login for w in self.watches}
                    | {data['login'] for _, data in self._ranking_rows()}
                    | ({self.app.account_login} if self.app.account_login else set()))
                known = sum(place is not None for place, _ in self._ranking_rows())
                message += ' · ' + self.t('{known}/{expected} profiles ranked', known=known, expected=expected)
        progress = self.query_one('#friends-sync-progress', ProgressBar)
        progress.display = ready and self.busy
        progress.update(total=max(1, self.sync_total), progress=self.sync_done)
        progress.tooltip = message
        status = self.query_one('#friends-sync-status', Static)
        status.display = not ready or bool(self.errors)
        status.update(message if not ready else self.t('{count} refresh error(s)', count=len(self.errors)))

    def _ranking_rows(self):
        logins = {w.login for w in self.watches}
        if self.app.account_login:
            logins.add(self.app.account_login)
        else:
            # The requesting account's own snapshot can still be shown offline.
            logins.update(login for login, data in self.snapshots.items() if data['user_id'] == self.context[1])
        metric = self.query_one('#friends-ranking-metric', Select).value if self.rankings else 'curriculum'
        ranker = {'curriculum': curriculum_rankings, 'level': level_rankings, 'projects': project_rankings}[metric]
        return ranker(self.snapshots[login] for login in logins if login in self.snapshots)

    def _refresh_view(self):
        if not self.is_mounted or not self.is_attached:
            return
        self._render_status()
        table = self.query_one('#friends-table', DataTable)
        scroll_y = table.scroll_y
        previous = self.selected_login
        rendered_rows = []
        search = self.query_one('#friends-search', Input).value.strip().lower()
        choice = self.query_one('#friends-filter', Select).value
        mine = next((d for d in self.snapshots.values() if d['user_id'] == self.context[1]), None) if self.context else None
        my_projects = ongoing(mine['items']) if mine else {}
        my_campuses = {c['id'] for c in (mine or {}).get('campuses', [])}
        ranking_rows = self._ranking_rows()
        places = {data['user_id']: place for place, data in ranking_rows}
        if self.rankings:
            rows = [(rank, data['login'], data) for rank, data in ranking_rows]
            known = {login for _, login, _ in rows}
            rows += [(None, w.login, None) for w in self.watches if w.login not in known]
        else:
            rows = [(places.get(self.snapshots.get(w.login, {}).get('user_id')), w.login, self.snapshots.get(w.login))
                    for w in self.watches]
            rows.sort(key=lambda row: (row[0] is None, row[0] or 0, -(row[2].get('level') or 0) if row[2] else 0, row[1]))
        matches = []
        for rank, login, data in rows:
            fields = [login]
            if data:
                fields += [data['display_name']]
                fields += [campus['name'] for campus in data['campuses']]
                fields += [project['name'] for project in ongoing(data['items']).values()]
            score = fuzzy_score(search, *fields)
            if score is not None:
                matches.append((score, rank, login, data))
        if search and not self.rankings:
            matches.sort(key=lambda row: (row[0], row[2] != search, row[2]))
        shown = []
        for _, rank, login, data in matches:
            working = ongoing(data['items']) if data else {}
            if choice == 'shared' and not my_projects.keys() & working.keys():
                continue
            if choice == 'campus' and not my_campuses & {c['id'] for c in (data or {}).get('campuses', [])}:
                continue
            location = current_location(data,app=self.app,login=login) if self.app.account_connected else 'Unavailable'
            if choice == 'online' and location in ('Unavailable', 'No active session'):
                continue
            names = [p['name'] for p in working.values()]
            project = names[0] + (f' +{len(names)-1}' if len(names) > 1 else '') if names else '—'
            level = f"{data['level']:.2f}" if data and data.get('level') is not None else '—'
            own = data and data['user_id'] == self.context[1]
            style = self.get_component_rich_style('friends--self', partial=True) if own else ''
            cluster = '×' if location in ('Unavailable', 'No active session') else self.t(location)
            state = 'Refreshing…' if login in self.pending_logins else self.errors.get(login) or self._freshness(data)
            validated = validated_project_count(data) if data else None
            rendered_rows.append((login, [Text(str(v), style=style) for v in (rank if rank is not None else '—', login + (' (' + self.t('you') + ')' if own else ''), self._curriculum_label(data), level, validated if validated is not None else '—', project, cluster, self.t(state))]))
            shown.append(login)
        existing = [str(row.key.value) for row in table.ordered_rows]
        with self.app.batch_update(), table.prevent(DataTable.RowHighlighted):
            for login in set(existing) - set(shown):
                table.remove_row(login)
            for login, cells in rendered_rows:
                if login not in existing:
                    table.add_row(*cells, key=login)
                else:
                    for column, old, new in zip(table.columns, table.get_row(login), cells):
                        if old != new or old.style != new.style:
                            table.update_cell(login, column, new)
            if existing != shown and shown:
                order = {cells[1].plain: index for index, (_, cells) in enumerate(rendered_rows)}
                table.sort(list(table.columns)[1], key=lambda cell: order[cell.plain])
        self.query_one('#friends-empty', Static).update('' if shown else self.t('No matching friends.' if self.watches else 'Add a friend by their 42 login.'))
        if previous in shown:
            table.move_cursor(row=shown.index(previous), scroll=False)
        table.scroll_to(y=scroll_y, animate=False)
        self._highlighted_login = str(table.ordered_rows[table.cursor_row].key.value) if 0 <= table.cursor_row < table.row_count else None
        self._render_details()
        self._responsive()

    def _curriculum_label(self, data):
        value = (data or {}).get('curriculum_rank') or {}
        if value.get('status') != 'inferred':
            labels = {
                'ambiguous': 'Conflicting cursus evidence',
                'no_active_projects': 'No ongoing project',
                'pending': 'Loading campus graph…',
                'unknown': 'Rank could not be inferred',
                'unavailable': 'Campus graph temporarily unavailable',
            }
            return self.t(labels.get(value.get('status'), 'Rank unavailable'))
        return self.t('Rank {rank}', rank=f"{value['rank']:02d}") if value['section'] == 'common-core' else self.t('Specialization')

    def _render_details(self):
        data = self.snapshots.get(self.selected_login)
        if self.comparing:
            self._ensure_details()
        if data and data.get('details_complete') is False:
            self._ensure_details()
            data = self.detail_snapshots.get(self.selected_login, data)
        watch = next((w for w in self.watches if w.login == self.selected_login), None)
        self.query_one('#friend-view-profile', Button).disabled = data is None
        self.query_one('#friend-remove', Button).disabled = watch is None or self.adding or not self.app.account_connected
        self.query_one('#friend-poke', Button).disabled = watch is None or not self.app.account_connected
        self.query_one('#friend-view-compare', Button).disabled = not data or data['user_id'] == self.context[1]
        table = self.query_one('#friend-projects', DataTable)
        rows_key = (self.app.language, self.selected_login, (data or {}).get('items'))
        rebuild = self._project_rows != rows_key
        if rebuild:
            from copy import deepcopy
            self._project_rows = deepcopy(rows_key)
            table.clear()
        access = self.query_one('#friend-project-access', Button)
        access.disabled = not data or not data['items']
        access.display = not self.comparing
        profile = self.query_one('#friend-profile', Static)
        if not data:
            profile.update(self.selected_login + '\n' + self.t(self.errors.get(self.selected_login, 'Waiting for API progress.')) if self.selected_login else self.t('Select a friend'))
            self.query_one('#friend-comparison', Static).update('')
            return
        if data['user_id'] == self.context[1]:
            self.comparing = False
            self.query_one('#friend-view-projects', Button).variant = 'primary'
            self.query_one('#friend-view-compare', Button).variant = 'default'
        if data.get('details_complete') is False:
            profile.update(data['login'] + '\n' + data['display_name'] + '\n' + self._freshness(data))
            message = self.t(self.errors.get(self.selected_login) or ('Loading project history…' if self.app.account_connected else 'Project history is not cached.'))
            self.query_one('#friend-project-caption', Static).update(message)
            self.query_one('#friend-comparison', Static).update(message)
            access.disabled = True
            return
        self.query_one('#friend-project-caption', Static).update(
            self.t('Project attempts · {count}', count=len(data['items'])) if data['items']
            else self.t('No project attempts in this cursus.'))
        lines = [data['login'] + ' · ' + data['display_name'], ' · '.join(c['name'] for c in data['campuses']) or self.t('Campus unavailable')]
        lines.append(self._curriculum_label(data))
        if (data.get('curriculum_rank') or {}).get('source') == 'failed_attempt':
            lines.append(self.t('Rank estimated from failed attempts · no ongoing project'))
        level = data.get('level')
        if level is not None:
            fraction = level % 1
            filled = int(fraction * 20)
            lines += [self.t('Level {level} · {grade}', level=f'{level:.2f}', grade=data.get('grade') or self.t('Grade unavailable')), '█' * filled + '░' * (20 - filled) + '  ' + self.t('{percent} to next level', percent=f'{fraction:.0%}')]
        else:
            lines.append(self.t('No level available in this cursus.'))
        location = current_location(data,app=self.app,login=self.selected_login) if self.app.account_connected else 'Unavailable'
        lines += [self.t('Cluster') + ' · ' + self.t(location), self._freshness(data)]
        if self.selected_login in self.errors:
            lines.append(self.t(self.errors[self.selected_login]))
        profile.update('\n'.join(lines))
        for item in sorted(data['items'], key=project_attempt_sort_key):
            state = 'Validated' if item.get('validated') is True else 'Failed' if item['status'] == 'finished' and item.get('validated') is False else item['status'].replace('_', ' ').capitalize()
            if rebuild:
                table.add_row(Text(item['name']), Text(self.t(state)), '—' if item.get('final_mark') is None else str(item['final_mark']), str(item['id']), key=str(item['id']))
        mine = next((d for d in self.snapshots.values() if d['user_id'] == self.context[1]), None)
        if mine and mine.get('projects_loaded') is not False:
            parts = [self.t('Comparison') + ' · ' + self._freshness(mine) + ' (' + self.t('you') + ')']
            for title, items in comparison(mine['items'], data['items']).items():
                parts += ['', self.t(title), '\n'.join('• ' + p['name'] for p in items) or self.t('No matching projects.')]
            self.query_one('#friend-comparison', Static).update('\n'.join(parts))
        else:
            self.query_one('#friend-comparison', Static).update(self.t('Your project history has not synced yet. Refresh to compare.'))
        self.query_one('#friend-comparison').display = self.comparing
        access.display = not self.comparing
        table.display = not self.comparing
        self.query_one('#friend-project-heading').display = not self.comparing
        self.query_one('#friend-profile-scroll').set_class(self.comparing, 'expanded')

    def on_resize(self):
        self._responsive()

    def _responsive(self):
        if not self.is_mounted or not self.is_attached:
            return
        width = self.size.width
        if not width:
            # Hidden tab panes have no region. Use their available container
            # width so the first visible frame already has the right layout.
            gutter = self.styles.gutter.width
            for ancestor in self.ancestors:
                if not isinstance(ancestor, Widget):
                    break
                if ancestor.content_size.width:
                    width = max(0, ancestor.content_size.width - gutter)
                    break
                gutter += ancestor.styles.gutter.width
        if not width:
            return
        self.set_class(width < 145, 'compact-toolbar')
        actions = self.query_one('#friends-actions-row')
        toggle = self.query_one('#friends-view-rankings', Button)
        toggle.icon = '✓' if self.rankings else '🏆'
        toggle.apply_language()
        toggle.variant = 'primary' if self.rankings else 'default'
        ranking_width = Text(str(toggle.label)).cell_len + 6
        requests_width = Text(str(self.query_one('#social-toggle', Button).label)).cell_len + 6
        add_width = Text(str(self.query_one('#friends-open-search', Button).label)).cell_len + 6
        metric_width = max(Text(self.t(label)).cell_len for label in
                           ('Curriculum ↓', 'Level ↓', 'Validated projects ↓')) + 8
        self.query_one('#friends-search-row').styles.grid_columns = f'1fr {add_width} 22'
        control_widths = [ranking_width, *([metric_width] if self.rankings else []), requests_width, 6, 6]
        control_count = len(control_widths)
        columns = control_widths
        for count in range(control_count - 1, 0, -1):
            if sum(columns) + 2 * (len(columns) - 1) <= width:
                break
            columns = [max(control_widths[index::count]) for index in range(count)]
        actions.styles.grid_size_columns = len(columns)
        actions.styles.grid_columns = ' '.join(map(str, columns))
        rows = (control_count + len(columns) - 1) // len(columns)
        actions.styles.height = rows * 3 + (rows - 1)
        narrow = width < 150
        if not self.selected_login:
            self.expanded_friend = False
        self.set_class(narrow, 'narrow')
        self.set_class(not self.selected_login, 'ranking-overview')
        self.query_one('#friends-ranking-metric').display = self.rankings
        self.set_class(narrow and bool(self.selected_login) and not self.expanded_friend, 'previewing')
        self.query_one('#friends-browser').display = not narrow or not self.expanded_friend
        self.query_one('#friend-details').display = bool(self.selected_login)
        self.query_one('#friend-back').display = narrow
        detail_actions = self.query_one('#friend-details-actions')
        buttons = [button for button in detail_actions.query(Button) if button.display]
        sizes = [max(6, Text(str(button.label)).cell_len + (4 if button.icon_only else 6)) for button in buttons]
        budget = max(1, (width if narrow else int(width * .45)) - 4)
        columns = sizes
        for count in range(len(sizes) - 1, 0, -1):
            if sum(columns) + len(columns) - 1 <= budget:
                break
            columns = [max(sizes[index::count]) for index in range(count)]
        detail_actions.styles.grid_size_columns = len(columns)
        detail_actions.styles.grid_columns = ' '.join(map(str, columns))
        rows = (len(sizes) + len(columns) - 1) // len(columns)
        detail_actions.styles.height = rows * 3 + rows - 1

    @on(DataTable.RowHighlighted, '#friends-table')
    def highlight_friend(self, event):
        event.stop()
        table = event.data_table
        login = str(event.row_key.value)
        # Rebuilds post intermediate highlights; only preview the current row
        # while the user is browsing, without stealing keyboard focus.
        if not table.has_focus or event.cursor_row != table.cursor_row or not 0 <= table.cursor_row < table.row_count:
            return
        if str(table.ordered_rows[table.cursor_row].key.value) != login or login == self._highlighted_login:
            return
        self._highlighted_login = login
        if login == self.selected_login:
            return
        self.selected_login = login
        self.expanded_friend = False
        self._render_details()
        self._responsive()

    @on(DataTable.RowSelected, '#friend-projects')
    async def select_project(self, event):
        event.stop()
        await self._open_project_attempt(str(event.row_key.value))

    async def _open_project_attempt(self, attempt_id):
        data = self.detail_snapshots.get(self.selected_login) or self.snapshots.get(self.selected_login)
        item = next((item for item in (data or {}).get('items', [])
                     if str(item['id']) == attempt_id), None)
        if item is None:
            return
        from ft_tui.features.friends.views.project import open_friend_project
        open_friend_project(self.app,data,item)

    @on(DataTable.RowSelected, '#friends-table')
    def select_friend(self, event):
        event.stop()
        self.expanded_friend = True
        self.selected_login = str(event.row_key.value)
        self._render_details()
        self._responsive()
        if self.has_class('narrow'):
            self.query_one('#friend-back', Button).focus()

    @on(Input.Changed, '#friends-search')
    def search(self, event):
        event.stop()
        self._refresh_view()
        self.query_one(FriendsSearchSuggestions).set_query(event.value)
        self._render_status()

    @on(DataTable.RowHighlighted, '#friend-suggestions-table')
    def highlight_suggestion(self, event):
        event.stop()
        self._render_status()

    def on_key(self, event):
        suggestions = self.query_one(FriendsSearchSuggestions)
        if event.key == 'down' and self.query_one('#friends-search', Input).has_focus:
            if suggestions.focus_results():
                event.prevent_default()
                event.stop()
        elif event.key == 'escape' and suggestions.display:
            suggestions.dismiss()
            self.query_one('#friends-search', Input).focus()
            event.prevent_default()
            event.stop()

    @on(Input.Submitted, '#friends-search')
    def submit_search(self, event):
        event.stop()
        suggestions = self.query_one(FriendsSearchSuggestions)
        candidate = suggestions.highlighted_candidate()
        if candidate:
            self._choose_search(candidate)
        elif event.value.strip():
            self._choose_search({'login': event.value.strip(), 'user_id': None})

    @on(FriendSuggestions.Chosen)
    def choose_search(self, event):
        event.stop()
        self._choose_search(event.candidate)

    def _choose_search(self, candidate):
        login = candidate['login']
        watch = next((w for w in self.watches if w.login.casefold() == login.casefold()), None)
        self.query_one(FriendsSearchSuggestions).dismiss()
        if watch or login.casefold() == (self.app.account_login or '').casefold():
            self.query_one('#friends-search', Input).value = ''
            self.query_one('#friends-filter', Select).value = 'all'
            self.selected_login = watch.login if watch else self.app.account_login
            self.expanded_friend = False
            self._refresh_view()
            self.query_one('#friends-table', DataTable).focus()
        elif self.app.account_connected and not self.adding:
            self.search_screen = FriendSearchScreen(self, candidate=candidate)
            self.app.push_screen(self.search_screen)

    @on(Select.Changed, '#friends-filter')
    @on(Select.Changed, '#friends-ranking-metric')
    def filter(self, event):
        event.stop()
        self._refresh_view()

    @on(Button.Pressed, '#friends-view-rankings')
    def toggle_ranking(self, event):
        event.stop()
        self.rankings = not self.rankings
        self.selected_login = None
        self._refresh_view()

    @on(Button.Pressed)
    async def button(self, event):
        event.stop()
        name = event.button.id
        if name == 'friend-project-access':
            table = self.query_one('#friend-projects', DataTable)
            if 0 <= table.cursor_row < table.row_count:
                await self._open_project_attempt(str(table.ordered_rows[table.cursor_row].key.value))
            return
        if name == 'social-toggle':
            from ft_tui.features.social.views.inbox import SocialInbox
            await self.query_one(SocialInbox).toggle(kind='requests')
        elif name == 'friends-pokes':
            from ft_tui.features.social.views.inbox import SocialInbox
            inbox = self.query_one(SocialInbox)
            await inbox.toggle(kind='pokes')
        elif name == 'friends-open-search':
            suggestions = self.query_one(FriendsSearchSuggestions)
            candidate = suggestions.highlighted_candidate()
            if candidate:
                self.add_friend(candidate['login'], (candidate['login'], candidate['user_id']))
        elif name == 'friends-refresh':
            self.start_sync(refresh=True)
        elif name == 'friend-back':
            self.selected_login = None
            self._responsive()
            self.query_one('#friends-table', DataTable).focus()
        elif name in ('friend-view-projects', 'friend-view-compare'):
            self.comparing = name == 'friend-view-compare'
            self.query_one('#friend-view-projects', Button).variant = 'default' if self.comparing else 'primary'
            self.query_one('#friend-view-compare', Button).variant = 'primary' if self.comparing else 'default'
            self._render_details()
        elif name == 'friend-view-profile' and self.selected_login:
            from ft_tui.features.profiles.views.user_profile import open_user_profile
            data = self.detail_snapshots.get(self.selected_login) or self.snapshots.get(self.selected_login)
            if data:
                open_user_profile(self.app, self.selected_login, data['user_id'], seed=data)
        elif name in ('friend-remove', 'friend-poke') and self.selected_login:
            from ft_tui.features.social.views.inbox import SocialInbox
            inbox = self.query_one(SocialInbox)
            watch = next((w for w in self.watches if w.login == self.selected_login), None)
            if not watch or not watch.user_id:
                return
            if name == 'friend-poke':
                inbox.compose_poke(watch.user_id)
            elif await inbox.mutate({'action': 'remove', 'account_id': watch.user_id}):
                self._stop()
                self.selected_login = None
                await inbox.sync()
                await self.reload()

    def add_friend(self, entered, suggested_friend=None):
        if self.adding or not self.app.account_connected or not self.context or self.context != self._scope() or not self.context[1]:
            return
        login = entered if suggested_friend and suggested_friend[0] == entered else entered.strip()
        if not LOGIN.fullmatch(login):
            if self.search_screen and self.search_screen.query_one(FriendSuggestions).focus_results():
                return
            self.app.notify('Enter a valid 42 login.', severity='warning')
            return
        if login == self.app.account_login or any(w.login == login for w in self.watches):
            self.app.notify('This login is already included.', severity='warning')
            return
        if self.search_screen:
            self.search_screen.query_one(FriendSuggestions).pause()
        expected_id = suggested_friend[1] if suggested_friend and suggested_friend[0] == login else None
        self.adding = True
        self._render_status()
        self.add_worker = self.run_worker(self._add_checked(login, self.epoch, self.context, expected_id), group='friend-add', exclusive=True)

    async def _add_checked(self, login, epoch, context, expected_id=None):
        from ft_tui.features.social.views.inbox import SocialInbox, error_message
        try:
            draft = {'action': 'request', 'login': login}
            if expected_id is not None:
                draft['user_id'] = expected_id
            await asyncio.to_thread(self.app.provider.social_action, draft)
            if not self._valid(epoch, context):
                return
            self.app.notify('Friend request sent. Waiting for acceptance.')
            self.query_one(FriendsSearchSuggestions).dismiss()
            if self.search_screen and self.search_screen.is_mounted:
                self.search_screen.dismiss()
        except Exception as error:
            if self._valid(epoch, context):
                self.app.notify(error_message(error), severity='warning')
        finally:
            if self._valid(epoch, context):
                self.adding = False
                app_cache(self.app).invalidate(lambda key: str(key[1]).startswith('friend-'))
                await self.query_one(SocialInbox).sync()
                if self._valid(epoch, context):
                    self._refresh_view()


class FriendsMixin:
    async def _load_friends(self):
        await self.query_one(FriendsWorkspace).reload()
        from ft_tui.features.cluster_map.views.cluster_map import ClusterMapWorkspace
        for workspace in self.query(ClusterMapWorkspace):
            await workspace.reload()

    async def _handle_friend_button(self, button_id):
        # FriendsWorkspace handles and stops its own button messages.
        return False

    async def on_tabbed_content_tab_activated(self, event):
        if event.pane.id == 'friends':
            await self.query_one(FriendsWorkspace).activate()
        elif event.pane.id == 'cluster-map':
            from ft_tui.features.cluster_map.views.cluster_map import ClusterMapWorkspace
            await self.query_one(ClusterMapWorkspace).reload()
