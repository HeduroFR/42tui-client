import threading
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from textual.widgets import DataTable, Input, ProgressBar, TabbedContent
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import FriendWatch
from ft_tui.services.friends import memberships, cached_observations, save_observation, cache_mutual_friends
from ft_tui.services.user_settings import save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.friends import FriendsWorkspace
from tests.friends_fixtures import snapshot, attempt, curriculum_rank


class Provider:
    def __init__(self):
        self.calls = []
        self.social_calls = []
        self.failure = False
        self.gate = None

    def social_action(self, draft):
        self.social_calls.append(draft)
        return {'ok': True}

    def get_friend(self, login, cursus_id, *, refresh=False):
        self.calls.append((login, cursus_id, refresh))
        if self.gate:
            self.gate.wait(3)
        if self.failure:
            raise RuntimeError('private upstream details')
        if login == 'you':
            data = snapshot('you', user_id='42', level=8.42, items=[attempt()])
            data['curriculum_rank'] = curriculum_rank(3, 'new')
        else:
            data = snapshot(login, items=[attempt(status='finished', validated=True, mark=125),
                attempt(2, id=2, name='cub3d', status='in_progress', validated=None, mark=None)])
            data['curriculum_rank'] = curriculum_rank(3, 'old', (2,))
        return data



class FriendsUITests(unittest.IsolatedAsyncioTestCase):
    async def test_cached_summaries_render_before_history_and_rows_update_in_place(self):
        class SummaryProvider(Provider):
            def __init__(self):
                super().__init__()
                self.batch_calls = []
                self.summary_calls = []
                self.history_gate = threading.Event()

            def get_friend_summaries(self, logins, cursus_id):
                self.batch_calls.append(list(logins))
                return [{**snapshot(login, user_id='42' if login == 'you' else '50', items=[]),
                         'details_complete': False, 'projects_loaded': False} for login in logins]

            def get_friend_summary(self, login, cursus_id, *, refresh=False):
                self.summary_calls.append(login)
                return {**snapshot(login, user_id='42' if login == 'you' else '50', items=[]),
                        'details_complete': False, 'projects_loaded': False}

            def get_friend_core(self, login, cursus_id, *, refresh=False):
                self.history_gate.wait(5)
                return self.get_friend(login, cursus_id, refresh=refresh)

        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory)/"summary.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
                cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}])
            app = FortyTwoTuiApp(factory, None)
            provider = SummaryProvider()
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    app.provider = provider; app.account_connected = True
                    app.account_id = '42'; app.account_login = 'you'
                    app.query_one(TabbedContent).active = 'friends'
                    workspace = app.query_one(FriendsWorkspace)
                    await workspace.activate()
                    await self._settle(workspace, pilot)
                    table = workspace.query_one('#friends-table', DataTable)
                    self.assertEqual(table.row_count, 1)
                    self.assertEqual(provider.summary_calls, [])
                    self.assertEqual(len(provider.batch_calls), 1)
                    self.assertEqual(table.get_row('alice')[3].plain, '8.42')
                    self.assertEqual(table.get_row('alice')[4].plain, '—')
                    self.assertEqual(provider.calls, [])
                    row = table.rows[next(key for key in table.rows if key.value == 'alice')]
                    workspace.snapshots['alice']['level'] = 9.5
                    workspace._refresh_view()
                    self.assertIs(table.rows[next(key for key in table.rows if key.value == 'alice')], row)
                    self.assertEqual(table.get_row('alice')[3].plain, '9.50')
                    workspace.selected_login = 'alice'
                    self.assertEqual(workspace._sync_targets()[0], 'alice')
                    provider.history_gate.set()
                    for _ in range(60):
                        await pilot.pause(.025)
                        if not workspace.detail_busy:
                            break
                    self.assertFalse(workspace.detail_busy)
                    self.assertEqual(set(provider.calls[i][0] for i in range(len(provider.calls))), {'you', 'alice'})
                    self.assertNotEqual(table.get_row('alice')[4].plain, '—')
            finally:
                provider.history_gate.set()
                factory.kw['bind'].dispose()

    async def test_friends_columns_fit_browser_after_resize_rankings_and_translation(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "columns.sqlite"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
                    cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}])
                    save_observation(session, '42', snapshot(items=[attempt(name='A very long project name')]))
                app = FortyTwoTuiApp(factory, None)
                app.account_id = '42'
                async with app.run_test(size=(160, 46)) as pilot:
                    app.query_one(TabbedContent).active = 'friends'
                    await pilot.pause()
                    workspace = app.query_one(FriendsWorkspace)
                    table = app.query_one('#friends-table', DataTable)
                    for width, rankings, language in ((160, False, 'en'), (100, True, 'en'),
                                                       (80, False, 'fr'), (80, True, 'es'), (220, True, 'fr')):
                        await pilot.resize_terminal(width, 46)
                        app.language = language
                        app._apply_language()
                        workspace.rankings = rankings
                        workspace.apply_language()
                        await pilot.pause()
                        self.assertEqual(len(table.columns), 8)
                        self.assertEqual(str(list(table.columns.values())[-1].label), workspace.t('Freshness'))
                        self.assertEqual(table.get_row('alice')[5].plain, 'A very long project name')
                        self.assertEqual(table.get_row('alice')[6].plain, '×')
                        self.assertLessEqual(sum(column.get_render_width(table) for column in table.columns.values()),
                                             table.scrollable_content_region.width)
                        self.assertLessEqual(table.virtual_size.width, table.scrollable_content_region.width)
                        self.assertEqual(table.scroll_x, 0)
                        heading = app.query_one('#friends-heading')
                        self.assertLessEqual(heading.size.height, 7 if width >= 160 else 15)
                        self.assertFalse(app.query('#friends-title'))
                        self.assertFalse(app.query('#friends-view-list'))
                        controls = [control for control in heading.query('Input, Select, Button') if control.display]
                        from ft_tui.ui.button import AppButton
                        for control in controls:
                            if control.id in ('friends-view-rankings', 'social-toggle', 'friends-pokes', 'friends-refresh', 'friends-open-search'):
                                self.assertIsInstance(control, AppButton)
                                from textual.geometry import Region
                                size = control.outer_size
                                lines = control.render_lines(Region(0, 0, size.width, size.height))
                                self.assertIn(str(control.label), lines[1].text, control.id)
                            if control.id in ('friends-view-rankings', 'social-toggle', 'friends-open-search'):
                                label = control.label
                                self.assertGreaterEqual(control.content_region.width, (label.cell_length if hasattr(label, 'cell_length') else label.cell_len), control.id)
                        search_row = heading.query_one('#friends-search-row')
                        actions_row = heading.query_one('#friends-actions-row')
                        self.assertGreaterEqual(actions_row.region.y - search_row.region.bottom, 1)
                        search = heading.query_one('#friends-search')
                        ranking_toggle = heading.query_one('#friends-view-rankings')
                        self.assertEqual(search.region.x, ranking_toggle.region.x)
                        self.assertEqual(search.region.x, search_row.content_region.x)
                        add_friend = heading.query_one('#friends-open-search')
                        filter_control = heading.query_one('#friends-filter')
                        self.assertEqual(add_friend.region.y, search.region.y)
                        self.assertGreater(add_friend.region.x, search.region.right)
                        self.assertGreater(filter_control.region.x, add_friend.region.right)
                        # Keep a complete outline in both focus states.
                        from textual.geometry import Region
                        for focused in (True, False):
                            (search if focused else ranking_toggle).focus()
                            await pilot.pause()
                            middle = search.render_lines(Region(0, 0, search.region.width, search.region.height))[1]
                            self.assertEqual(middle.text[0], '│')
                            self.assertEqual(middle.text[-1], '│')
                        self.assertIsInstance(heading.query_one('#friends-view-rankings'), AppButton)
                        self.assertEqual(heading.query_one('#friends-view-rankings').variant,
                                         'primary' if rankings else 'default')
                        for control in controls:
                            self.assertTrue(heading.region.contains_region(control.region), control.id)
                        for index, control in enumerate(controls):
                            for other in controls[index + 1:]:
                                self.assertFalse(control.region.overlaps(other.region), (control.id, other.id))
            finally:
                factory.kw['bind'].dispose()

    async def test_project_enter_and_access_open_a_preview_without_changing_workspace(self):
        from ft_tui.db.models import Project
        from ft_tui.ui.components import Button, Select
        from ft_tui.ui.friend_project import FriendProjectPreview
        from textual.widgets import Static
        with TemporaryDirectory() as directory:
            factory=make_session_factory(f'sqlite:///{Path(directory)/"preview.sqlite"}')
            data=snapshot(items=[attempt(id=42),attempt(9999,id=44,name='Missing catalog',status='finished',validated=True,mark=125)])
            with factory() as session:
                save_settings(session,{'onboarding_completed':'true','default_cursus_id':'21'})
                cache_mutual_friends(session,'42',[{'account_id':'50','login':'alice'}])
                save_observation(session,'42',data)
            app=FortyTwoTuiApp(factory,None);app.account_id='42'
            try:
                async with app.run_test(size=(160,46)) as pilot:
                    tabs=app.query_one(TabbedContent);tabs.active='friends';await pilot.pause()
                    project=Project(official_project_id=1001,slug='catalog-name',name='Catalog name')
                    project._catalog_data={'kind':'project','rank':3,'description':'Project overview'}
                    app.projects={project.ui_key:project}
                    workspace=app.query_one(FriendsWorkspace)
                    for activation,target in [('enter','42'),('access','44')]:
                        workspace.snapshots={'alice':data};workspace.selected_login='alice'
                        workspace._render_details();workspace._responsive();await pilot.pause()
                        access = workspace.query_one('#friend-project-access')
                        caption = workspace.query_one('#friend-project-caption')
                        projects = workspace.query_one('#friend-projects')
                        self.assertEqual(access.region.y, caption.region.y)
                        self.assertLessEqual(access.region.bottom, projects.region.y)
                        actions = workspace.query_one('#friend-details-actions')
                        for control in actions.query(Button):
                            if control.display:
                                self.assertTrue(actions.region.contains_region(control.region), control.id)
                        app.query_one('#project-kind',Select).value='exam'
                        app.query_one('#project-search',Input).value='no match'
                        table=app.query_one('#friend-projects',DataTable);table.focus()
                        table.move_cursor(row=next(i for i,row in enumerate(table.ordered_rows) if row.key.value==target))
                        await pilot.pause();previous=app.selected_project_key
                        if activation=='enter':await pilot.press('enter')
                        else:self.assertTrue(await pilot.click('#friend-project-access'))
                        await pilot.pause()
                        preview=app.screen;self.assertIsInstance(preview,FriendProjectPreview)
                        dialog=preview.query_one('#friend-project-dialog').region
                        self.assertGreater(dialog.x,0);self.assertGreater(dialog.y,0)
                        self.assertLessEqual(abs(dialog.x-(160-dialog.right)),1)
                        self.assertLessEqual(abs(dialog.y-(46-dialog.bottom)),1)
                        self.assertEqual(preview.attempt['id'],int(target))
                        self.assertEqual(preview.student['user_id'],'50')
                        self.assertEqual(tabs.active,'friends')
                        self.assertEqual(app.selected_project_key,previous)
                        with patch.object(app,'action_open_project_editor') as editor:
                            await pilot.press('o')
                            editor.assert_not_called()
                        self.assertIn('alice',str(preview.query_one('#friend-project-attempt',Static).render()))
                        if target=='42':
                            self.assertIn('Project overview',str(preview.query_one('#friend-project-description',Static).render()))
                            await pilot.press('escape')
                        else:
                            self.assertIn('125%',str(preview.query_one('#friend-project-mark-caption',Static).render()))
                            self.assertTrue(await pilot.click('#activity-close'))
                        await pilot.pause()
                        self.assertEqual(workspace.selected_login,'alice')
                        self.assertEqual(table.ordered_rows[table.cursor_row].key.value,target)
                        self.assertEqual(tabs.active,'friends')
                        self.assertEqual(app.query_one('#project-search',Input).value,'no match')
                        self.assertEqual(app.query_one('#project-kind',Select).value,'exam')
            finally:factory.kw['bind'].dispose()

    def test_rank_labels_distinguish_pending_graph_failed_collection_and_unclassified_evidence(self):
        from types import SimpleNamespace
        workspace = SimpleNamespace(t=lambda value: value)
        for status, label in (
            ('pending', 'Loading campus graph…'),
            ('unavailable', 'Campus graph temporarily unavailable'),
            ('unknown', 'Rank could not be inferred'),
        ):
            self.assertEqual(FriendsWorkspace._curriculum_label(workspace, {'curriculum_rank': {'status': status}}), label)

    async def test_selected_friend_refresh_uses_core_snapshots_without_optional_xp(self):
        class CoreProvider(Provider):
            def __init__(self):
                super().__init__();self.phases=[]
            def get_friend_core(self,login,cursus_id,**options):
                self.phases.append(login)
                value=super().get_friend(login,cursus_id,**options)
                value['display_name']='Fresh '+login
                return value
            def get_friend(self,*args,**options):
                raise AssertionError('Friends must not request unused exact XP')
        with TemporaryDirectory() as directory:
            factory=make_session_factory(f'sqlite:///{Path(directory) / "core.sqlite"}')
            with factory() as session:
                save_settings(session,{'onboarding_completed':'true','default_cursus_id':'21'})
                cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}])
            app=FortyTwoTuiApp(factory,None);provider=CoreProvider()
            try:
                async with app.run_test(size=(140,40)) as pilot:
                    app.provider=provider;app.account_connected=True;app.account_id='42';app.account_login='you'
                    app.query_one(TabbedContent).active='friends'
                    workspace=app.query_one(FriendsWorkspace)
                    await workspace.activate()
                    await self._settle(workspace,pilot)
                    self.assertFalse(workspace.errors)
                    provider.phases.clear();workspace.selected_login='alice'
                    workspace.start_sync(refresh=True)
                    await self._settle(workspace,pilot)
                    self.assertEqual(provider.phases,['alice','you'])
                    self.assertFalse(workspace.errors)
                    self.assertEqual(workspace.snapshots['alice']['display_name'],'Fresh alice')
                    self.assertEqual(app.query_one('#friend-projects',DataTable).row_count,2)
                    with factory() as session:
                        self.assertEqual(cached_observations(session,'42',21)['alice']['display_name'],'Fresh alice')
            finally:
                factory.kw['bind'].dispose()

    async def test_switching_tabs_never_applies_a_zero_width_layout(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "layout.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    workspace = app.query_one(FriendsWorkspace)
                    tabs = app.query_one(TabbedContent)
                    await pilot.pause()
                    self.assertFalse(workspace.has_class('compact-toolbar'))
                    self.assertFalse(workspace.has_class('narrow'))
                    responsive = workspace._responsive
                    states = []

                    def record_layout():
                        responsive()
                        states.append((workspace.has_class('compact-toolbar'), workspace.has_class('narrow')))

                    with patch.object(workspace, '_responsive', side_effect=record_layout):
                        for _ in range(2):
                            tabs.active = 'friends'; await pilot.pause()
                            tabs.active = 'projects-tab'; await pilot.pause()
                        self.assertTrue(states)
                        self.assertEqual(set(states), {(False, False)})
                        # A hidden resize must also choose the new layout before showing.
                        await pilot.resize_terminal(80, 30)
                        await pilot.pause()
                        states.clear()
                        tabs.active = 'friends'; await pilot.pause()
                        self.assertEqual(set(states), {(True, True)})
            finally:
                factory.kw['bind'].dispose()

    async def _settle(self, workspace, pilot):
        for _ in range(40):
            await pilot.pause(.025)
            if not workspace.busy and not workspace.adding:
                return
        self.fail('Friend worker did not finish')

    async def test_add_compare_rank_search_and_narrow_navigation(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "friends.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    app.provider = Provider(); app.account_connected = True
                    app.account_id = '42'; app.account_login = 'you'
                    app.query_one(TabbedContent).active = 'friends'
                    workspace = app.query_one(FriendsWorkspace)
                    await self._settle(workspace, pilot)
                    await pilot.pause()
                    from ft_tui.ui.friend_search import FriendSearchScreen
                    workspace.search_screen = FriendSearchScreen(workspace)
                    await app.push_screen(workspace.search_screen)
                    await pilot.pause()
                    field = app.screen.query_one('#friend-login-input', Input)
                    field.value = 'alice'
                    await pilot.click('#friend-add')
                    await self._settle(workspace, pilot)
                    self.assertEqual(app.provider.social_calls[-1], {'action': 'request', 'login': 'alice'})
                    with factory() as session:
                        self.assertEqual(memberships(session, '42'), [])
                        # The recipient's acceptance arrives through the server push refresh.
                        cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}])
                    workspace.last_sync = 0
                    await workspace.reload()
                    await self._settle(workspace, pilot)
                    workspace.selected_login = 'alice'; workspace._refresh_view()
                    self.assertEqual(workspace.selected_login, 'alice')
                    self.assertEqual(app.query_one('#friend-projects', DataTable).row_count, 2)
                    self.assertEqual(str(app.query_one('#friends-table', DataTable).get_row('alice')[0]), '1')
                    with factory() as session:
                        self.assertEqual([w.login for w in memberships(session, '42')], ['alice'])
                        self.assertEqual(memberships(session, '43'), [])
                    await pilot.click('#friend-view-compare')
                    self.assertIn('Could help me', str(app.query_one('#friend-comparison').render()))
                    self.assertIn('minishell', str(app.query_one('#friend-comparison').render()))
                    await pilot.click('#friends-view-rankings')
                    table = app.query_one('#friends-table', DataTable)
                    self.assertEqual(table.row_count, 2)
                    self.assertEqual(str(table.get_row('alice')[0]), '1')
                    self.assertEqual(str(table.get_row('you')[0]), '1')
                    self.assertEqual(str(table.get_row('alice')[2]), 'Rank 03')
                    self.assertEqual(str(table.get_row('you')[2]), 'Rank 03')
                    self.assertIn('(you)', str(table.get_row('you')[1]))
                    original_style = table.get_row('you')[1].style
                    app.theme = 'gruvbox'; await pilot.pause()
                    themed_style = table.get_row('you')[1].style
                    self.assertNotEqual(themed_style.color, original_style.color)
                    self.assertEqual(themed_style, workspace.get_component_rich_style('friends--self', partial=True))
                    self.assertTrue(themed_style.bold)
                    self.assertEqual(table.get_row('alice')[1].style, '')
                    self.assertFalse(app.query_one('#friend-details').display)
                    self.assertGreater(app.query_one('#friends-browser').size.width, 140)
                    self.assertEqual([str(column.label) for column in list(table.columns.values())[:3]],
                                     ['#', 'Login', 'Rank'])
                    self.assertFalse(app.query('#friends-ranking-hint'))
                    metric = app.query_one('#friends-ranking-metric')
                    metric.value = 'projects'; await pilot.pause()
                    self.assertEqual(str(table.get_row('alice')[0]), '1')
                    self.assertEqual(str(table.get_row('you')[0]), '2')
                    self.assertEqual(str(table.get_row('alice')[4]), '1')
                    metric.value = 'level'; await pilot.pause()
                    self.assertEqual(str(table.get_row('alice')[0]), '1')
                    self.assertEqual(str(table.get_row('you')[0]), '1')
                    metric.value = 'curriculum'; await pilot.pause()
                    search = app.query_one('#friends-search', Input)
                    search.value = 'alice'; await pilot.pause()
                    self.assertEqual(table.row_count, 1)
                    await pilot.click('#friends-view-rankings')
                    self.assertEqual(str(table.get_row('alice')[0]), '1')
                    await pilot.click('#friends-view-rankings')
                    search.value = ''; await pilot.pause()
                    await pilot.resize_terminal(80, 30)
                    await pilot.pause()
                    self.assertLessEqual(app.query_one('#friends-heading').size.height, 15)
                    for control in app.query_one('#friends-heading').query('Input, Select, Button'):
                        self.assertLessEqual(control.region.right, 80)
                    table.focus(); table.move_cursor(row=0)
                    await pilot.press('enter'); await pilot.pause()
                    self.assertTrue(app.query_one('#friend-details').display)
                    self.assertFalse(app.query_one('#friends-browser').display)
                    for selector in ('#friend-back', '#friend-view-projects', '#friend-view-compare', '#friend-remove'):
                        self.assertLessEqual(app.query_one(selector).region.right, 80)
                    await pilot.press('escape')
                    self.assertTrue(app.query_one('#friends-browser').display)
                    self.assertFalse(app.query_one('#friend-details').display)
                    app.language = 'es'; app._apply_language()
                    await pilot.pause()
                    self.assertEqual(str(app.query_one('#friends-view-rankings').label), '✓  Mostrar clasificación')
                    table.move_cursor(row=0); table.focus(); await pilot.press('enter'); await pilot.pause()
                    for selector in ('#friend-back', '#friend-view-projects', '#friend-view-compare', '#friend-remove'):
                        self.assertLessEqual(app.query_one(selector).region.right, 80)
                    self.assertIn('Puede ayudarme', str(app.query_one('#friend-comparison').render()))

            finally:
                factory.kw['bind'].dispose()

    async def test_failed_refresh_keeps_history_and_account_switch_rejects_inflight_results(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "friends.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
                cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}])
            app = FortyTwoTuiApp(factory, None)
            provider = Provider()
            try:
                async with app.run_test(size=(140, 40)) as pilot:
                    app.provider = provider; app.account_connected = True
                    app.account_id = '42'; app.account_login = 'you'
                    app.query_one(TabbedContent).active = 'friends'
                    workspace = app.query_one(FriendsWorkspace)
                    await workspace.activate()
                    await self._settle(workspace, pilot)
                    original = deepcopy(workspace.snapshots['alice']['items'])
                    progress = app.query_one('#friends-sync-progress', ProgressBar)
                    self.assertEqual((progress.progress, progress.total), (2, 2))
                    self.assertFalse(progress.display)
                    self.assertFalse(app.query_one('#friends-sync-status').display)
                    self.assertIn('2 succeeded · 0 failed', str(progress.tooltip))
                    provider.failure = True
                    workspace.start_sync(refresh=True)
                    await self._settle(workspace, pilot)
                    self.assertEqual(workspace.snapshots['alice']['items'], original)
                    self.assertIn('alice', workspace.errors)
                    self.assertNotIn('private', str(workspace.errors))
                    self.assertEqual((progress.progress, progress.total), (2, 2))
                    self.assertIn('Refresh 2/2 profiles', str(progress.tooltip))
                    self.assertTrue(app.query_one('#friends-sync-status').display)
                    self.assertIn('2 refresh error(s)', str(app.query_one('#friends-sync-status').render()))
                    self.assertIn('0 succeeded · 2 failed', str(progress.tooltip))
                    provider.failure = False; provider.gate = threading.Event()
                    clock = app._read_cache.clock
                    app._read_cache.clock = lambda: clock() + 5
                    workspace.start_sync(refresh=True)
                    await pilot.pause(.05)
                    self.assertEqual((progress.progress, progress.total), (0, 2))
                    self.assertIn('Refreshing 0/2 profiles', str(progress.tooltip))
                    app.account_generation += 1; app.account_id = '43'; app.account_login = 'other'
                    await workspace.reload()
                    provider.gate.set()
                    await self._settle(workspace, pilot)
                    self.assertNotIn('alice', workspace.snapshots)
                    self.assertEqual(workspace.watches, [])
                    with factory() as session:
                        self.assertNotIn('alice', cached_observations(session, '43', 21))
            finally:
                if provider.gate:
                    provider.gate.set()
                factory.kw['bind'].dispose()

    async def test_fuzzy_search_fields_filters_and_original_ranks_work_offline(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "search.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21', 'catalog_last_account': '42'})
                cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'zoe'},
                                                   {'account_id': '51', 'login': 'albert'}])
                zoe = snapshot('zoe', level=4, items=[attempt(name='minishell')])
                zoe['display_name'] = 'José García'
                albert = snapshot('albert', user_id='51', level=8, items=[attempt(2, name='cub3d')])
                albert['display_name'] = 'Zoe Beta'
                albert['campuses'] = [{'id': 1, 'name': 'Tokyo', 'is_primary': True}]
                you = snapshot('you', user_id='42', level=6)
                zoe['curriculum_rank'] = curriculum_rank(1, 'old')
                albert['curriculum_rank'] = curriculum_rank(4, 'new', (2,))
                you['curriculum_rank'] = curriculum_rank(2, 'shared')
                for value in [zoe, albert, you]:
                    save_observation(session, '42', value)
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    app.query_one(TabbedContent).active = 'friends'
                    await pilot.pause()
                    table = app.query_one('#friends-table', DataTable)
                    self.assertEqual(list(row.key.value for row in table.ordered_rows), ['albert', 'zoe'])
                    search = app.query_one('#friends-search', Input)
                    for query in ['jgrc', 'garcia', 'jose paris', 'minsihell']:
                        search.value = query; await pilot.pause()
                        self.assertEqual(list(row.key.value for row in table.ordered_rows), ['zoe'], query)
                    search.value = 'zoe'; await pilot.pause()
                    self.assertEqual(list(row.key.value for row in table.ordered_rows), ['zoe', 'albert'])
                    await pilot.click('#friends-view-rankings')
                    self.assertEqual(list(row.key.value for row in table.ordered_rows), ['albert', 'zoe'])
                    self.assertEqual(str(table.get_row('zoe')[0]), '3')
                    search.value = 'zzzzz'; await pilot.pause()
                    self.assertEqual(table.row_count, 0)
                    search.value = ''; await pilot.pause()
                    self.assertEqual(table.row_count, 3)
                    app.query_one('#friends-filter').value = 'campus'; await pilot.pause()
                    search.value = 'zoe'; await pilot.pause()
                    self.assertEqual(list(row.key.value for row in table.ordered_rows), ['zoe'])
                    self.assertFalse(app.query_one(FriendsWorkspace).busy)
            finally:
                factory.kw['bind'].dispose()


class FreshnessTests(unittest.TestCase):
    def test_relative_age_units_and_future_clock_skew(self):
        from datetime import datetime, timedelta, timezone
        from ft_tui.ui.friends import freshness
        now = datetime(2026, 10, 25, tzinfo=timezone.utc)
        with patch('ft_tui.ui.friends.datetime') as clock:
            clock.now.return_value = now
            clock.fromisoformat.side_effect = datetime.fromisoformat
            for seconds, expected in [(0, '0s ago'), (59, '59s ago'), (60, '1m ago'),
                                      (3600, '1h ago'), (86400, '1d ago'), (-60, '0s ago')]:
                data = snapshot()
                data['meta']['cached_at'] = (now - timedelta(seconds=seconds)).isoformat()
                self.assertEqual(freshness(data), expected)
