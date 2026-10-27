"""Reusable, read-only student profile with account-fenced section workers."""
import asyncio
from copy import deepcopy
from time import monotonic
from urllib.parse import quote
import webbrowser

import httpx
from textual import on
from textual.screen import Screen
from textual.widgets import DataTable, Static

from ft_tui.i18n import translate
from ft_tui.features.profiles.adapters.portraits import download_portrait
from ft_tui.ui.cluster_portrait import ClusterPortrait, PortraitCache
from ft_tui.ui.components import Button, Select
from ft_tui.features.profiles.views.profile_sections import goals_text
from ft_tui.features.profiles.views.profile_view import ProfileViewMixin
from ft_tui.ui.styles.user_profile import PROFILE_CSS


def open_user_profile(app, login, user_id=None, seed=None):
    app.push_screen(UserProfileScreen(login, user_id=user_id, seed=seed))


class UserProfileScreen(ProfileViewMixin, Screen):
    BINDINGS = [('escape', 'close', 'Back'), ('r', 'refresh', 'Refresh')]
    DEFAULT_CSS = PROFILE_CSS

    def __init__(self, login, user_id=None, seed=None, *, service=None):
        super().__init__()
        self.service = service
        self.login, self.user_id = login, user_id
        self.seed = deepcopy(seed)
        self.core = None
        self.project_data = None
        self.attendance_data = None
        self.goals_data = None
        self.cursus_id = None
        self.context = None
        self.epoch = 0
        self.alive = True
        self.loading = False
        self.all_attempts = False
        self.saved = False
        self.retry_at = 0
        self.errors = {}
        self.reconnect_required = False
        self._goals_polls = 0
        self._portrait_cache = PortraitCache()

    def _service(self):
        if self.service is None:
            self.service = getattr(self.app, 'student_profile_service', None)
            if self.service is None:
                from ft_tui.app.bootstrap import build_student_profile_service
                self.service = build_student_profile_service()
        return self.service

    def t(self, message, **values):
        text = translate(message, getattr(self.app, 'language', 'en'))
        return text.format(**values) if values else text

    @on(DataTable.RowSelected,'#profile-projects')
    def preview_project(self,event):
        event.stop()
        if not self._valid() or not self.project_data:return
        item=next((item for item in self.project_data['items'] if str(item['id'])==str(event.row_key.value)),None)
        if item:
            from ft_tui.features.friends.views.project import open_friend_project
            open_friend_project(self.app,self.project_data,item)

    def on_mount(self):
        self.context = (getattr(self.app, 'account_generation', 0), getattr(self.app, 'account_id', None), id(getattr(self.app, 'provider', None)))
        self.provider = getattr(self.app, 'provider', None)
        self._responsive()
        table = self.query_one('#profile-projects', DataTable)
        table.add_columns(*(self.t(label) for label in ('Project', 'Status', 'Mark')))
        self._restore()
        # Navigation revalidates through the backend cache; only Refresh bypasses it.
        self.call_after_refresh(lambda: self.action_refresh(refresh=False))
        self.call_after_refresh(self._render_presence)
        self.set_interval(.25, self._check_context)
        self.set_interval(15, self._poll_goals)
        self.set_interval(10, self._render_presence)
        self.query_one('#profile-back', Button).focus()

    def _valid(self, epoch=None, cursus=None):
        return (self.alive and self.is_mounted and self.context ==
                (getattr(self.app, 'account_generation', 0), getattr(self.app, 'account_id', None), id(getattr(self.app, 'provider', None)))) and (epoch is None or epoch == self.epoch) and (cursus is None or cursus == self.cursus_id)

    def _check_context(self):
        if self.alive and not self._valid():
            self.alive = False
            self.epoch += 1
            self.workers.cancel_all()
            self.core = self.project_data = self.attendance_data = self.goals_data = None
            self.query_one('#profile-scroll').display = False
            self.query_one('#profile-status', Static).update(self.t('Account changed · close this profile and reopen it.'))
            self.query_one('#profile-refresh', Button).disabled = True

    def on_unmount(self):
        self.alive = False
        self.epoch += 1
        self.workers.cancel_all()

    def action_close(self):
        self.alive = False
        self.epoch += 1
        self.workers.cancel_all()
        self.app.pop_screen()

    def on_resize(self):
        if self.is_mounted:
            self._responsive()
            self._render_attendance()

    def _responsive(self):
        self.set_class(self.size.width < 110, 'compact')
        self.set_class(self.size.width < 65, 'tiny')

    def _cache(self):
        if not hasattr(self.app, '_student_profile_cache'):
            self.app._student_profile_cache = {}
        return self.app._student_profile_cache

    def _key(self):
        return (*self.context, self.user_id)

    def _remember(self):
        if not self._valid() or not self.core:
            return
        cache = self._cache()
        old = cache.get(self._key(), {})
        sections = old.get('sections', {})
        if self.cursus_id:
            sections[self.cursus_id] = deepcopy({'projects': self.project_data, 'goals': self.goals_data})
        cache.pop(self._key(), None)
        cache[self._key()] = deepcopy({'core': self.core, 'attendance': self.attendance_data, 'sections': sections})
        while len(cache) > 32:
            cache.pop(next(iter(cache)))

    def _restore(self):
        cached = self._cache().get(self._key()) if self.user_id else None
        if cached:
            self.core = deepcopy(cached['core'])
            self.core['meta'] = {**self.core['meta'], 'cache': 'stale', 'stale': True}
            self.attendance_data = deepcopy(cached.get('attendance'))
            if self.attendance_data:
                self.attendance_data['stale'] = True
            self.saved = True
            self._render_core()
            self._restore_sections()
        elif self.seed and self.seed.get('user_id') == self.user_id:
            self._render_seed()

    def _restore_sections(self):
        cached = self._cache().get(self._key(), {}).get('sections', {}).get(self.cursus_id, {})
        projects = cached.get('projects')
        goals = cached.get('goals')
        self.project_data = deepcopy(projects) if projects and projects.get('cursus_id') == self.cursus_id and projects.get('user_id') == self.user_id else None
        self.goals_data = deepcopy(goals) if goals and goals.get('cursus_id') == self.cursus_id and goals.get('user_id') == self.user_id else None
        if self.project_data:
            self.project_data['presence'] = {'status': 'unavailable', 'cached_at': None}
            self.project_data['location'] = None
            self.project_data['meta'] = {**self.project_data['meta'], 'cache': 'stale', 'stale': True}
        if self.goals_data:
            self.goals_data['stale'] = True
        self._render_sections()

    def action_refresh(self, *, refresh=True):
        if not self._valid() or self.loading or monotonic() < self.retry_at:
            return
        if not getattr(self.app, 'account_connected', False) or not self.provider:
            self.query_one('#profile-status', Static).update(self.t('Saved data · offline') if self.core else self.t('Connect your 42 account to view this profile.'))
            return
        self.loading = True
        self.epoch += 1
        self.errors = {}
        self._goals_polls = 0
        self.query_one('#profile-refresh', Button).disabled = True
        self.query_one('#profile-status', Static).update(self.t('Refreshing profile…'))
        self.run_worker(self._load(self.epoch, refresh=refresh), group='student-profile', exclusive=True)

    async def _load(self, epoch, *, refresh=False):
        try:
            if not self.user_id:
                match = await self._service().search(self.provider, self.login, lambda: self._valid(epoch))
                if match is None or not self._valid(epoch):
                    return
                self.user_id = match['user_id']
            user_id = self.user_id
            data = await self._service().profile(self.provider, user_id, lambda: self._valid(epoch) and self.user_id == user_id, refresh=refresh)
            if data is None or not self._valid(epoch):
                return
            previous_cursus = self.cursus_id
            self.core = data
            self.login = data['login']
            self.saved = False
            self._honor_retry(data['meta'])
            self._render_core()
            if previous_cursus != self.cursus_id:
                self._restore_sections()
            self._remember()
            await asyncio.gather(self._load_attendance(epoch, refresh=refresh), self._load_cursus(epoch, self.cursus_id, refresh=refresh), self._load_portrait(epoch))
        except Exception as error:
            if self._valid(epoch):
                self.errors['core'] = self._error(error)
        finally:
            if self._valid(epoch):
                self.loading = False
                self.query_one('#profile-refresh', Button).disabled = monotonic() < self.retry_at
                self._render_status()

    def _error(self, error):
        if isinstance(error, httpx.HTTPStatusError):
            if error.response.status_code == 401:
                self.reconnect_required = True
                return self.t('Reconnect your 42 account.')
            if error.response.status_code == 429:
                delay = error.response.headers.get('Retry-After', '30')
                self._honor_retry({'retry_after': int(delay) if delay.isdigit() else 30, 'reason': 'upstream_rate_limited'})
                return self.t('Rate limited; retry later.')
            if error.response.status_code == 404:
                return self.t('Login not found.')
        return self.t('Refresh failed; saved data retained.')

    def _honor_retry(self, metadata):
        delay = metadata.get('retry_after')
        if type(delay) is int and delay > 0:
            self.retry_at = max(self.retry_at, monotonic() + min(86400, delay))
            self.query_one('#profile-refresh', Button).disabled = True
            self.set_timer(max(1, self.retry_at - monotonic()), self._enable_refresh)
            if metadata.get('reason') == 'upstream_rate_limited':
                self.errors['throttle'] = self.t('Rate limited; retry later.')

    def _enable_refresh(self):
        if self._valid():
            self.query_one('#profile-refresh', Button).disabled = self.loading or monotonic() < self.retry_at
            if monotonic() >= self.retry_at:
                self.errors.pop('throttle', None)
                self._render_status()

    async def _load_attendance(self, epoch, *, refresh=False):
        try:
            user_id = self.user_id
            data = await self._service().attendance(self.provider, user_id, lambda: self._valid(epoch) and self.user_id == user_id, refresh=refresh)
            if data is None or not self._valid(epoch):
                return
            self._honor_retry(data)
            if data['status'] == 'available' or not self.attendance_data:
                self.attendance_data = data
            else:
                self.attendance_data['stale'] = True
            self._render_attendance()
            self._remember()
        except Exception as error:
            if self._valid(epoch):
                self.errors['attendance'] = self._error(error)
                if self.attendance_data:
                    self.attendance_data['stale'] = True
                self._render_attendance()

    async def _load_cursus(self, epoch, cursus, *, refresh=False):
        if not cursus:
            self._render_sections()
            return
        await asyncio.gather(self._load_projects(epoch, cursus, refresh=refresh), self._load_goals(epoch, cursus))

    async def _load_projects(self, epoch, cursus, *, refresh=False):
        try:
            user_id, login = self.user_id, self.login
            data = await self._service().projects(self.provider, login, user_id, cursus, lambda: self._valid(epoch, cursus) and self.user_id == user_id, refresh=refresh)
            if data is None or not self._valid(epoch, cursus):
                return
            self.errors.pop('projects', None)
            self.project_data = data
            self._render_projects()
            self._render_presence()
            self._remember()
        except Exception as error:
            if self._valid(epoch, cursus):
                self.errors['projects'] = self._error(error)
                if self.project_data:
                    self.project_data['meta'].update(cache='stale', stale=True)
                    self.project_data['presence'] = {'status':'unavailable','cached_at':None}
                    self.project_data['location'] = None
                self._render_projects()
                self._render_presence()

    async def _load_goals(self, epoch, cursus):
        try:
            user_id = self.user_id
            data = await self._service().goals(self.provider, user_id, cursus, lambda: self._valid(epoch, cursus) and self.user_id == user_id)
            if data is None or not self._valid(epoch, cursus):
                return
            self.errors.pop('goals', None)
            if data['status'] in ('available', 'not_applicable') or not self.goals_data:
                self.goals_data = data
            else:
                self.goals_data['stale'] = True
            self.query_one('#profile-goals', Static).update(goals_text(self.goals_data, self.t))
            self._remember()
            self._render_status()
        except Exception as error:
            if self._valid(epoch, cursus):
                self.errors['goals'] = self._error(error)
                if self.goals_data:
                    self.goals_data['stale'] = True
                else:
                    self.goals_data = {'status':'unavailable'}
                self.query_one('#profile-goals', Static).update(goals_text(self.goals_data, self.t))

    async def _load_portrait(self, epoch):
        url = self.core.get('image_url')
        if not url:
            return
        image = await self._portrait_cache.load(url, lambda: self._service().portrait(url, lambda: self._valid(epoch), loader=download_portrait))
        if self._valid(epoch):
            portrait = self.query_one('#profile-portrait', ClusterPortrait)
            portrait.image = image
            portrait.status = 'ready' if image else 'unavailable'
            portrait.refresh()

    def _poll_goals(self):
        if (self._valid() and not self.loading and self.cursus_id and self._goals_polls < 8
                and (self.goals_data or {}).get('status') == 'pending' and monotonic() >= self.retry_at):
            self._goals_polls += 1
            self.run_worker(self._load_goals(self.epoch, self.cursus_id), group='student-goals', exclusive=True)

    async def _load_selection(self, epoch, cursus):
        tasks = [self._load_cursus(epoch, cursus)]
        if not self.attendance_data:
            tasks.append(self._load_attendance(epoch))
        if self.core and self.core.get('image_url'):
            tasks.append(self._load_portrait(epoch))
        await asyncio.gather(*tasks)
        if self._valid(epoch, cursus):
            self._render_status()

    @on(Select.Changed, '#profile-cursus')
    def select_cursus(self, event):
        event.stop()
        if event.value is Select.NULL or event.value == self.cursus_id or not self._valid():
            return
        self.cursus_id = event.value
        self.epoch += 1
        self._goals_polls = 0
        self.loading = False
        self.query_one('#profile-refresh', Button).disabled = monotonic() < self.retry_at
        self.errors = {}
        self._restore_sections()
        self._render_level()
        self.run_worker(self._load_selection(self.epoch, self.cursus_id), group='student-cursus', exclusive=True)

    @on(Button.Pressed)
    def button_pressed(self, event):
        event.stop()
        if event.button.id == 'profile-back':
            self.action_close()
        elif event.button.id == 'profile-refresh':
            self.action_refresh()
        elif event.button.id == 'profile-intra':
            webbrowser.open('https://profile.intra.42.fr/users/' + quote(self.login, safe=''))
        elif event.button.id == 'profile-attempts':
            self.all_attempts = not self.all_attempts
            event.button.label = self.t('Show latest attempts' if self.all_attempts else 'Show all attempts')
            self._render_projects()
