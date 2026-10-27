"""Each navigation key visits exactly the adjacent visible tab."""
import unittest
from textual.app import App
from textual.widgets import TabbedContent, TabPane, Tabs, Input, DataTable
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.features.projects.views.navigation import ProjectNavigationMixin
from ft_tui.ui.select import AppSelect

PANES = ['dashboard', 'projects-tab', 'friends', 'dev-log', 'settings']

class NavigationHarness(ProjectNavigationMixin, App):
    BINDINGS = [binding for binding in FortyTwoTuiApp.BINDINGS if binding.action in {'tab_left', 'tab_right', 'move_project_down', 'move_project_up', 'first_project', 'last_project', 'move_project_page_down', 'move_project_page_up'}]
    def compose(self):
        with TabbedContent(initial='dashboard'):
            for pane_id in PANES:
                with TabPane(pane_id, id=pane_id):
                    yield Input(id=f'{pane_id}-input')
                    if pane_id == 'friends':
                        yield AppSelect([('Alpha', 'a'), ('Beta', 'b')], value='a', id='friends-filter')
                        yield DataTable(id='friends-table', cursor_type='row')

    def on_mount(self):
        table = self.query_one('#friends-table', DataTable)
        table.add_column('Friend')
        table.add_rows([('alice',), ('bob',), ('charlie',)])

class TabNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_key_visits_each_adjacent_tab_in_both_directions(self):
        app = NavigationHarness()
        async with app.run_test() as pilot:
            tabs = app.query_one(TabbedContent)
            for key in ('l', 'L', 'shift+l'):
                tabs.active = PANES[0]; await pilot.pause()
                for expected in PANES[1:] + PANES[:1]:
                    app.set_focus(None); await pilot.press(key); await pilot.pause()
                    self.assertEqual(tabs.active, expected, (key, expected))
            for key in ('h', 'H', 'shift+h'):
                tabs.active = PANES[0]; await pilot.pause()
                for expected in list(reversed(PANES[1:])) + PANES[:1]:
                    app.set_focus(None); await pilot.press(key); await pilot.pause()
                    self.assertEqual(tabs.active, expected, (key, expected))
    async def test_j_k_enter_and_navigate_the_active_friends_list(self):
        app = NavigationHarness()
        async with app.run_test() as pilot:
            content = app.query_one(TabbedContent)
            content.active = 'friends'; await pilot.pause()
            content.query_one(Tabs).focus()
            table = app.query_one('#friends-table', DataTable)
            await pilot.press('j'); await pilot.pause()
            self.assertIs(app.focused, table)
            self.assertEqual(table.cursor_row, 0)
            await pilot.press('j'); await pilot.pause()
            self.assertEqual(table.cursor_row, 1)
            await pilot.press('k'); await pilot.pause()
            self.assertEqual(table.cursor_row, 0)
            await pilot.press('end'); await pilot.pause()
            self.assertEqual(table.cursor_row, 2)
            await pilot.press('home'); await pilot.pause()
            self.assertEqual(table.cursor_row, 0)
            await pilot.press('ctrl+d'); await pilot.pause()
            self.assertEqual(table.cursor_row, 2)
            await pilot.press('ctrl+u'); await pilot.pause()
            self.assertEqual(table.cursor_row, 0)
            field = app.query_one('#friends-input', Input); field.focus()
            await pilot.press('j', 'k'); await pilot.pause()
            self.assertEqual(field.value, 'jk')
            self.assertIs(app.focused, field)
            self.assertEqual(table.cursor_row, 0)
            await pilot.press('home', 'x', 'end', 'y'); await pilot.pause()
            self.assertEqual(field.value, 'xjky')
            app.query_one('#friends-filter', AppSelect).focus()
            await pilot.press('enter', 'end'); await pilot.pause()
            self.assertIsNot(app.focused, table)
            await pilot.press('escape'); await pilot.pause()

    async def test_navigation_skips_disabled_tabs_and_typing_keeps_focus(self):
        app = NavigationHarness()
        async with app.run_test() as pilot:
            tabs = app.query_one(TabbedContent)
            tabs.disable_tab('friends'); tabs.active = 'projects-tab'; await pilot.pause()
            app.set_focus(None); await pilot.press('l'); await pilot.pause()
            self.assertEqual(tabs.active, 'dev-log')
            field = app.query_one('#dev-log-input', Input); field.focus()
            await pilot.press('h', 'l'); await pilot.pause()
            self.assertEqual(tabs.active, 'dev-log'); self.assertEqual(field.value, 'hl')
            await pilot.press('alt+left'); await pilot.pause()
            self.assertEqual(tabs.active, 'projects-tab')
            self.assertEqual(field.value, 'hl')
            await pilot.press('alt+right'); await pilot.pause()
            self.assertEqual(tabs.active, 'dev-log')

class FullAppNavigationTests(unittest.IsolatedAsyncioTestCase):
    async def test_h_l_leave_projects_with_list_focus_and_keep_cycling(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from ft_tui.db.database import make_session_factory
        from ft_tui.db.models import Project
        from ft_tui.features.settings.adapters.storage import save_settings
        from textual.widgets import ListView
        with TemporaryDirectory() as directory:
            factory=make_session_factory(f'sqlite:///{Path(directory)/"navigation.sqlite"}')
            try:
                with factory() as session:
                    save_settings(session,{'onboarding_completed':'true', 'icon_mode':'nerd'})
                    session.add(Project(slug='local',name='Local',local_path=directory));session.commit()
                app=FortyTwoTuiApp(factory,None)
                async with app.run_test(size=(140,50)) as pilot:
                    content=app.query_one(TabbedContent)
                    settings_tab = content.query_one(Tabs).get_content_tab('settings')
                    self.assertEqual(settings_tab.region.right, content.region.right)
                    self.assertIn('\uf013', str(settings_tab.label))
                    for key,expected in [('l','correction-slots'),('h','dashboard')]:
                        content.active='projects-tab';await pilot.pause()
                        app.query_one('#project-list-view',ListView).focus();await pilot.pause()
                        await pilot.press(key);await pilot.pause()
                        self.assertEqual(content.active,expected)
                    await pilot.press('l','l','l','l');await pilot.pause()
                    self.assertEqual(content.active,'clubs')
                    await pilot.press('l');await pilot.pause()
                    self.assertEqual(content.active,'dev-log')
                    for key,expected in [('f3','dev-log'),('f5','settings'),('f2','projects-tab')]:
                        content.active='projects-tab';await pilot.pause()
                        app.query_one('#project-list-view',ListView).focus();await pilot.pause()
                        await pilot.press(key);await pilot.pause()
                        self.assertEqual(content.active,expected)
                    app.action_show_dashboard();await pilot.pause()
                    index=app.query_one('#project-list-view',ListView).index
                    await pilot.press('j','k');await pilot.pause()
                    self.assertEqual(content.active,'dashboard')
                    self.assertEqual(app.query_one('#project-list-view',ListView).index,index)
                    from textual.screen import ModalScreen
                    class EditingModal(ModalScreen):
                        def compose(self):
                            yield Input(id='modal-input')
                    app.push_screen(EditingModal());await pilot.pause()
                    await pilot.press('h','l','alt+left','alt+right','f2');await pilot.pause()
                    self.assertEqual(content.active,'dashboard')
                    self.assertEqual(app.screen.query_one('#modal-input',Input).value,'hl')
                    app.pop_screen()
                    app.language = 'fr'
                    app._apply_language()
                    await pilot.pause()
                    self.assertIn('Paramètres', str(settings_tab.label))
                    for width in (64, 180, 80, 140):
                        await pilot.resize_terminal(width, 40)
                        content.active = 'settings'
                        await pilot.pause()
                        self.assertTrue(settings_tab.is_on_screen)
                        if width >= 140:
                            self.assertEqual(settings_tab.region.right, content.region.right)
            finally:
                factory.kw['bind'].dispose()
