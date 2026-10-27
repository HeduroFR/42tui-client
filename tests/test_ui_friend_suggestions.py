import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path
from tempfile import TemporaryDirectory
from textual.app import App
from textual.widgets import DataTable, Input, TabbedContent
from ft_tui.db.database import make_session_factory
from ft_tui.features.friends.adapters.storage import memberships, cache_mutual_friends
from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.features.friends.views.workspace import FriendsWorkspace, FriendsSearchSuggestions
from ft_tui.features.friends.views.suggestions import FriendSuggestions
from ft_tui.features.friends.views.search import FriendSearchScreen
from tests.friends_fixtures import snapshot


class DirectoryProvider:
    def __init__(self):
        self.queries = []
        self.canonical = None
        self.login = 'alice'
        self.index = dict(status="ready", count=1000, updated_at="2026-10-23T10:00:00Z", stale=False)
        self.profiles = []
        self.gate = None
        self.identity = '50'
        self.requests = []

    def social_action(self, draft):
        if draft.get('user_id') != self.identity:
            raise ValueError('Selected identity no longer registered')
        self.requests.append(draft)
        return {'status': 'pending'}

    def get_friend(self, login, cursus_id, *, refresh=False, user_id=None):
        self.profiles.append(login)
        return snapshot(self.canonical or login, user_id='42' if login == 'you' else self.identity)

    def search_students(self, query, *, limit=20, exclude_ids=()):
        self.queries.append((query, limit, exclude_ids))
        if self.gate:
            self.gate.wait(3)
        return dict(items=[{'user_id': '50', 'login': self.login, 'display_name': 'Élodie Example'}], index=self.index)


class FriendSuggestionsUITests(unittest.IsolatedAsyncioTestCase):
    async def test_header_search_highlights_friends_and_confirms_requests(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory)/"header-search.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
                cache_mutual_friends(session, '42', [{'account_id': '51', 'login': 'bob'}])
            app = FortyTwoTuiApp(factory, None)
            provider = DirectoryProvider()
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    app.provider = provider; app.account_connected = True
                    app.account_id = '42'; app.account_login = 'you'
                    app.query_one(TabbedContent).active = 'friends'
                    workspace = app.query_one(FriendsWorkspace)
                    await workspace.activate()
                    await self.wait_for(pilot, lambda: not workspace.busy)
                    field = workspace.query_one('#friends-search', Input)
                    suggestions = workspace.query_one(FriendsSearchSuggestions)
                    table = suggestions.query_one(DataTable)
                    field.value = 'bbo'
                    field.focus()
                    await self.wait_for(pilot, lambda: table.row_count == 2 and not suggestions.loading)
                    self.assertEqual(str(table.ordered_rows[0].key.value), '51')
                    await pilot.press('down', 'enter')
                    await pilot.pause()
                    self.assertEqual(workspace.selected_login, 'bob')
                    friends = workspace.query_one('#friends-table', DataTable)
                    self.assertEqual(str(friends.ordered_rows[friends.cursor_row].key.value), 'bob')
                    self.assertEqual(field.value, '')
                    self.assertFalse(suggestions.display)
                    self.assertEqual(provider.requests, [])

                    field.value = 'ailce'; field.focus()
                    await self.wait_for(pilot, lambda: table.row_count == 1 and not suggestions.loading)
                    await pilot.press('down', 'enter'); await pilot.pause()
                    self.assertIsInstance(app.screen, FriendSearchScreen)
                    self.assertIn('alice', str(app.screen.query_one('#friend-search-help').render()))
                    self.assertEqual(provider.requests, [])
                    await pilot.press('escape'); await pilot.pause()
                    self.assertEqual(provider.requests, [])

                    # Result availability must update Add even when the cursor
                    # stays on the same row and emits no highlight notification.
                    with table.prevent(DataTable.RowHighlighted):
                        field.value = 'alice'; field.focus()
                        await self.wait_for(pilot, lambda: suggestions.query == 'alice'
                            and suggestions.display and suggestions.timer is None
                            and table.row_count == 1 and not suggestions.loading)
                        self.assertFalse(workspace.query_one('#friends-open-search').disabled)
                    await pilot.click('#friends-open-search')
                    self.assertNotIsInstance(app.screen, FriendSearchScreen)
                    await self.wait_for(pilot, lambda: not workspace.adding)
                    self.assertEqual(provider.requests, [{'action': 'request', 'login': 'alice', 'user_id': '50'}])

                    app.account_connected = False
                    field.value = 'bbo'; field.focus()
                    await pilot.pause(.3)
                    self.assertEqual(table.row_count, 1)
                    await pilot.press('down', 'enter'); await pilot.pause()
                    self.assertEqual(workspace.selected_login, 'bob')
            finally:
                factory.kw['bind'].dispose()

    async def test_add_uses_highlighted_result_and_discards_stale_results(self):
        class Harness(App):
            language = 'en'
            account_generation = 0
            account_id = '42'
            account_connected = True
            provider = None

        app = Harness()
        workspace = SimpleNamespace(watches=[], adding=False, add_friend=Mock(), search_screen=None)
        async with app.run_test(size=(100, 36)) as pilot:
            modal = FriendSearchScreen(workspace)
            await app.push_screen(modal)
            await pilot.pause()
            field = modal.query_one(Input)
            suggestions = modal.query_one(FriendSuggestions)
            field.value = 'touze'
            await pilot.pause()
            suggestions._install(dict(items=[
                dict(user_id='50', login='utouze-b', display_name='Ulysse Touzé Buord'),
                dict(user_id='51', login='vtouze', display_name='Valentin Touzé'),
            ], index={}))
            await pilot.pause()
            await pilot.click('#friend-add')
            workspace.add_friend.assert_called_once_with('utouze-b', ('utouze-b', '50'))

            workspace.add_friend.reset_mock()
            field.focus()
            await pilot.press('down', 'down')
            await pilot.click('#friend-add')
            workspace.add_friend.assert_called_once_with('vtouze', ('vtouze', '51'))
            self.assertEqual(field.value, 'touze')

            workspace.add_friend.reset_mock()
            field.value = 'exact-login'
            await pilot.pause(.3)
            await pilot.click('#friend-add')
            workspace.add_friend.assert_called_once_with('exact-login', None)

    async def wait_for(self, pilot, predicate):
        for _ in range(60):
            await pilot.pause(.025)
            if predicate():
                return
        self.fail('Directory worker did not reach the expected state')

    async def test_typo_and_name_suggestions_require_selection_then_add(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory)/"suggestions.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None); provider = DirectoryProvider()
            try:
                async with app.run_test(size=(100, 36)) as pilot:
                    app.provider = provider; app.account_connected = True
                    app.account_id = '42'; app.account_login = 'you'
                    app.account_campuses = [{'id': 31, 'is_primary': True}]
                    app.query_one(TabbedContent).active = 'friends'
                    workspace = app.query_one(FriendsWorkspace)
                    await self.wait_for(pilot, lambda: not workspace.busy and workspace.context and workspace.context[1] == '42')
                    await pilot.pause()
                    workspace.search_screen = FriendSearchScreen(workspace)
                    await app.push_screen(workspace.search_screen)
                    await pilot.pause()
                    field = app.screen.query_one('#friend-login-input', Input)
                    suggestions = app.screen.query_one(FriendSuggestions)
                    table = suggestions.query_one(DataTable)
                    self.assertIsInstance(app.screen, FriendSearchScreen)
                    self.assertTrue(field.has_focus)
                    await pilot.press('escape')
                    await pilot.pause()
                    self.assertNotIsInstance(app.screen, FriendSearchScreen)
                    workspace.search_screen = FriendSearchScreen(workspace)
                    await app.push_screen(workspace.search_screen)
                    await pilot.pause()
                    field = app.screen.query_one('#friend-login-input', Input)
                    suggestions = app.screen.query_one(FriendSuggestions)
                    table = suggestions.query_one(DataTable)
                    field.value = 'ailce'
                    await self.wait_for(pilot, lambda: table.row_count == 1 and not suggestions.loading)
                    self.assertEqual(str(table.get_row('50')[0]), 'alice')
                    field.value = 'elodi'
                    await self.wait_for(pilot, lambda: len(provider.queries) == 2 and table.row_count == 1)
                    self.assertEqual([q[0] for q in provider.queries], ['ailce', 'elodi'])
                    self.assertIn('42', provider.queries[0][2])
                    with factory() as session:
                        self.assertEqual(memberships(session, '42'), [])
                    await pilot.resize_terminal(80, 24)
                    dialog = app.screen.query_one('#friend-search-dialog')
                    self.assertLessEqual(dialog.region.right, 80)
                    self.assertLessEqual(dialog.region.bottom, 24)
                    field.focus(); await pilot.press('down', 'enter'); await pilot.pause()
                    self.assertEqual(field.value, 'alice')
                    self.assertFalse(suggestions.display)
                    self.assertNotIn('alice', provider.profiles)
                    await pilot.click('#friend-add')
                    await self.wait_for(pilot, lambda: not workspace.adding)
                    with factory() as session:
                        self.assertEqual(memberships(session, '42'), [])
                        self.assertEqual(provider.requests[-1], {'action': 'request', 'login': 'alice', 'user_id': '50'})
                        # After recipient acceptance the next server snapshot updates the cache.
                        cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}])
                    await workspace.reload()
                    await pilot.pause()
                    workspace.search_screen = FriendSearchScreen(workspace)
                    await app.push_screen(workspace.search_screen)
                    await pilot.pause()
                    field = app.screen.query_one('#friend-login-input', Input)
                    field.value = 'alice'; await pilot.pause(.4)
                    self.assertEqual(app.screen.query_one(FriendSuggestions).query_one(DataTable).row_count, 0)  # Already added users are excluded.
            finally:
                factory.kw['bind'].dispose()

    async def test_context_change_and_cancel_discard_inflight_results(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory)/"race.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None); provider = DirectoryProvider()
            try:
                async with app.run_test(size=(100, 36)) as pilot:
                    app.provider = provider; app.account_connected = True
                    app.account_id = '42'; app.account_login = 'you'
                    app.account_campuses = [{'id': 31, 'is_primary': True}]
                    app.query_one(TabbedContent).active = 'friends'
                    workspace = app.query_one(FriendsWorkspace)
                    await self.wait_for(pilot, lambda: not workspace.busy and workspace.context and workspace.context[1] == '42')
                    provider.gate = threading.Event()
                    await pilot.pause()
                    workspace.search_screen = FriendSearchScreen(workspace)
                    await app.push_screen(workspace.search_screen)
                    await pilot.pause()
                    field = app.screen.query_one('#friend-login-input', Input)
                    suggestions = app.screen.query_one(FriendSuggestions)
                    field.value = 'alice'
                    await self.wait_for(pilot, lambda: bool(provider.queries))
                    app.account_generation += 1; app.account_id = '43'; app.account_connected = False; app.provider = None
                    await workspace.reload()
                    provider.gate.set(); await pilot.pause(.1)
                    self.assertEqual(suggestions.candidates, {})
                    self.assertFalse(suggestions.loading)
                    field.focus(); await pilot.press('escape'); await pilot.pause()
                    self.assertFalse(suggestions.display)
                    with factory() as session:
                        self.assertEqual(memberships(session, '43'), [])
            finally:
                if provider.gate:
                    provider.gate.set()
                factory.kw['bind'].dispose()

    async def test_changed_suggested_identity_is_not_added(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory)/"identity.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None); provider = DirectoryProvider()
            try:
                async with app.run_test(size=(100, 36)) as pilot:
                    app.provider = provider; app.account_connected = True
                    app.account_id = '42'; app.account_login = 'you'
                    app.account_campuses = [{'id': 31, 'is_primary': True}]
                    app.query_one(TabbedContent).active = 'friends'
                    workspace = app.query_one(FriendsWorkspace)
                    await self.wait_for(pilot, lambda: not workspace.busy and workspace.context and workspace.context[1] == '42')
                    await pilot.pause()
                    workspace.search_screen = FriendSearchScreen(workspace)
                    await app.push_screen(workspace.search_screen)
                    await pilot.pause()
                    field = app.screen.query_one('#friend-login-input', Input)
                    field.value = 'ailce'
                    await self.wait_for(pilot, lambda: app.screen.query_one(FriendSuggestions).query_one(DataTable).row_count == 1)
                    field.focus(); await pilot.press('down', 'enter'); await pilot.pause()
                    provider.identity = '99'
                    await pilot.click('#friend-add')
                    await self.wait_for(pilot, lambda: not workspace.adding)
                    with factory() as session:
                        self.assertEqual(memberships(session, '42'), [])
            finally:
                factory.kw['bind'].dispose()

    async def test_renamed_suggestion_requests_verified_id_without_campus(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory)/"rename.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None); provider = DirectoryProvider()
            provider.login = '_Alice-É'
            provider.index = dict(status='building', count=250, updated_at=None, stale=True)
            try:
                async with app.run_test(size=(100, 36)) as pilot:
                    app.provider = provider; app.account_connected = True
                    app.account_id = '42'; app.account_login = 'you'
                    app.query_one(TabbedContent).active = 'friends'
                    workspace = app.query_one(FriendsWorkspace)
                    await self.wait_for(pilot, lambda: not workspace.busy and workspace.context and workspace.context[1] == '42')
                    await pilot.pause()
                    workspace.search_screen = FriendSearchScreen(workspace)
                    await app.push_screen(workspace.search_screen)
                    await pilot.pause()
                    field = app.screen.query_one('#friend-login-input', Input)
                    suggestions = app.screen.query_one(FriendSuggestions)
                    field.value = 'al'; field.value = 'alic'; field.value = 'alice'
                    await self.wait_for(pilot, lambda: suggestions.query_one(DataTable).row_count == 1)
                    self.assertEqual(len(provider.queries), 1)
                    self.assertEqual(suggestions.index['status'], 'building')
                    self.assertTrue(suggestions.index['stale'])
                    field.value = 'elodi'
                    await self.wait_for(pilot, lambda: len(provider.queries) == 2 and not suggestions.loading)
                    field.value = 'alice'
                    await self.wait_for(pilot, lambda: suggestions.query_one(DataTable).row_count == 1)
                    self.assertEqual(len(provider.queries), 2)
                    field.focus(); await pilot.press('down', 'enter'); await pilot.pause()
                    self.assertEqual(field.value, '_Alice-É')
                    provider.canonical = '_Alice-É-new'
                    await pilot.click('#friend-add')
                    await self.wait_for(pilot, lambda: not workspace.adding)
                    with factory() as session:
                        self.assertEqual(memberships(session, '42'), [])
                        self.assertEqual(provider.requests[-1], {'action': 'request', 'login': '_Alice-É', 'user_id': '50'})
            finally:
                factory.kw['bind'].dispose()
