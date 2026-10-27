"""Debounced, bounded searches against the backend's persistent student index."""
import asyncio
from collections import OrderedDict

from rich.text import Text
from textual import on
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import DataTable

from ft_tui.features.friends.models import student_search_result
from ft_tui.i18n import translate
from ft_tui.ui.components import Static


class FriendSuggestions(Vertical):
    class ResultsChanged(Message):
        """Candidates changed independently of the table cursor position."""

    class Chosen(Message):
        def __init__(self, candidate):
            super().__init__()
            self.candidate = dict(candidate)

    def __init__(self, *, purpose='friend'):
        self.purpose = purpose
        super().__init__(id='friend-suggestions')
        self.query = ''
        self.context = None
        self.candidates = {}
        self.index = None
        self.loading = False
        self.error = ''
        self.worker = self.timer = None
        self.retry_at = 0.0
        self.excluded_ids = set()
        self.excluded_logins = set()
        self.suppressed_query = None
        self.ready = False
        self.generation = 0
        self.cache = OrderedDict()

    def compose(self):
        yield Static('', id='friend-suggestions-status', markup=False, localize=False)
        yield DataTable(id='friend-suggestions-table', cursor_type='row', zebra_stripes=True)

    def t(self, source, **values):
        return translate(source, self.app.language).format(**values)

    def on_mount(self):
        self.ready = True
        self.apply_language()
        self.display = False

    def apply_language(self):
        if self.ready:
            table = self.query_one(DataTable)
            table.clear(columns=True)
            table.add_column(self.t('Login'), width=18)
            table.add_column(self.t('Name'), width=40)
            self._refresh_suggestions()

    def _scope(self):
        return (self.app.account_generation, self.app.account_id, id(self.app.provider))

    def _valid(self, context, generation):
        return self.is_mounted and self.is_attached and self.context == context == self._scope() and generation == self.generation and self.app.account_connected

    def pause(self):
        self.generation += 1
        if self.timer:
            self.timer.stop()
            self.timer = None
        if self.worker:
            self.worker.cancel()
            self.worker = None
        self.loading = False

    def on_unmount(self):
        self.pause()

    def reset(self):
        self.pause()
        self.context = None
        self.candidates = {}
        self.index = None
        self.error = ''
        self.retry_at = 0.0
        self.cache.clear()
        self.suppressed_query = None
        self.display = False

    def set_query(self, query, watches=()):
        context = self._scope()
        if context != self.context:
            self.reset()
            self.context = context
        excluded = {watch.user_id for watch in watches if watch.user_id}
        if self.app.account_id:
            excluded.add(self.app.account_id)
        logins = {watch.login for watch in watches}
        query = query.strip()
        changed = query != self.query or excluded != self.excluded_ids or logins != self.excluded_logins
        self.excluded_ids, self.excluded_logins = excluded, logins
        if changed:
            self.pause()
            self.candidates = {}
            self.index = None
            self.error = ''
        self.query = query
        if self.suppressed_query != query:
            self.suppressed_query = None
        self.display = sum(c.isalnum() for c in query) >= 2 and query != self.suppressed_query
        if not self.display:
            self.pause()
            return
        self._refresh_suggestions()
        if changed or not self.loading and not self.candidates:
            self.timer = self.set_timer(.25, self._start)

    def _start(self):
        self.timer = None
        if not self.display or self.loading or not self._valid(self.context, self.generation):
            return
        if not callable(getattr(self.app.provider, 'search_students', None)):
            self._refresh_suggestions()
            return
        now = asyncio.get_running_loop().time()
        key = (self.query, tuple(sorted(self.excluded_ids)), tuple(sorted(self.excluded_logins)))
        cached = self.cache.get(key)
        if cached and now - cached[0] < 30:
            self.cache.move_to_end(key)
            self._install(cached[1])
            return
        if now < self.retry_at:
            self.error = 'Suggestions unavailable; enter an exact login or try again later.'
            self._refresh_suggestions()
            return
        self.loading = True
        self.error = ''
        self.worker = self.run_worker(self._search(self.context, self.generation, key), group='friend-search', exclusive=True)
        self._refresh_suggestions()

    async def _search(self, context, generation, key):
        provider, query = self.app.provider, self.query
        try:
            from ft_tui.features.friends.views.workspace import friends_service_for
            result = await friends_service_for(self).search(
                provider,query,limit=20,exclude_ids=tuple(sorted(self.excluded_ids))[:200])
            if not self._valid(context, generation):
                return
            result = student_search_result(result)
            self.cache[key] = (asyncio.get_running_loop().time(), result)
            self.cache.move_to_end(key)
            while len(self.cache) > 32:
                self.cache.popitem(last=False)
            self._install(result)
        except Exception as error:
            if self._valid(context, generation):
                import httpx
                self.error = 'Suggestions unavailable; enter an exact login or try again later.'
                retry = error.response.headers.get('Retry-After', '') if isinstance(error, httpx.HTTPStatusError) else ''
                self.retry_at = asyncio.get_running_loop().time() + (max(30, int(retry)) if retry.isdigit() and len(retry) <= 10 else 30)
        finally:
            if self._valid(context, generation):
                self.loading = False
                self._refresh_suggestions()

    def _install(self, result):
        self.candidates = {row['user_id']: row for row in result['items']}
        self.index = result['index']
        self._refresh_suggestions()

    def result_candidates(self):
        return self.candidates

    def _refresh_suggestions(self):
        if not self.ready or not self.is_attached:
            return
        table = self.query_one(DataTable)
        selected = self.highlighted_candidate() if table.row_count else None
        table.clear()
        visible = []
        for row in self.result_candidates().values():
            if row['user_id'] in self.excluded_ids or row['login'] in self.excluded_logins:
                continue
            table.add_row(Text(row['login']), Text(row['display_name']), key=row['user_id'])
            visible.append(row['user_id'])
        if selected and selected['user_id'] in visible:
            table.move_cursor(row=visible.index(selected['user_id']), scroll=False)
        table.display = bool(table.row_count)
        if not self.app.account_connected:
            message = self.t('Connect your account for friend suggestions.')
        elif self.error:
            message = self.t('Student suggestions unavailable. Try again later or open Intra.' if self.purpose == 'team' else self.error)
        elif not callable(getattr(self.app.provider, 'search_students', None)):
            message = self.t('Student suggestions unavailable. Try again later or open Intra.' if self.purpose == 'team' else 'Suggestions unavailable; enter an exact login or try again later.')
        elif self.loading or self.index is None:
            message = self.t('Searching student directory…')
        else:
            message = ''
        hint = self.t('Select a friend to highlight them, or another student to send a request.' if self.purpose == 'navigate' else 'Choose a login with Enter, then Invite.' if self.purpose == 'team' else 'Choose a login with Enter, then Add member.' if self.purpose == 'member' else 'Choose a login with Enter, then Add friend.') if table.row_count else self.t('No suggestions yet. Try another name or login.' if self.purpose == 'team' else 'No suggestions yet; you can still add an exact login.')
        message = '\n'.join(part for part in (message, hint) if part)
        self.query_one(Static).update(message)
        self.post_message(self.ResultsChanged())

    def on_resize(self):
        if self.ready and self.is_attached:
            self.query_one(DataTable).styles.height = 3 if self.app.size.height < 32 else 6

    def focus_results(self):
        if self.display and self.query_one(DataTable).row_count:
            self.query_one(DataTable).focus()
            return True
        return False

    def highlighted_candidate(self):
        table = self.query_one(DataTable)
        if not self.display or not table.row_count or not table.is_valid_row_index(table.cursor_row):
            return None
        row_key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
        return self.result_candidates().get(str(row_key.value))

    def dismiss(self):
        self.pause()
        self.suppressed_query = self.query
        self.display = False

    @on(DataTable.RowSelected)
    def choose(self, event):
        event.stop()
        candidate = self.result_candidates().get(str(event.row_key.value))
        if candidate:
            self.pause()
            self.suppressed_query = candidate['login'].strip()
            self.display = False
            self.post_message(self.Chosen(candidate))
