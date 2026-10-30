import unittest
from datetime import timedelta
from types import SimpleNamespace
from textual.app import App
from textual.widgets import ListView, DataTable
from ft_tui.features.agenda.models import snapshot
from ft_tui.features.agenda.views import AgendaWorkspace

class Provider:
    def __init__(self): self.calls = []; self.fail = False
    def get_agenda(self, begin, end, kind, target, campus_id=None):
        self.calls.append(kind)
        if self.fail: raise RuntimeError('offline')
        return {'account_id': '42', 'items': [{'id': 1, 'kind': kind, 'begin_at': (begin + timedelta(hours=12)).isoformat(), 'end_at': None, 'title': '[red]Project', 'description': 'Details', 'counterpart': 'peer', 'url': None}]}

class Harness(App):
    account_id = '42'; account_generation = 0; language = 'en'
    def __init__(self): super().__init__(); self.provider = Provider()
    def _catalog_scope(self): return SimpleNamespace(campus_id=1)
    def compose(self): yield AgendaWorkspace()

class AgendaTests(unittest.IsolatedAsyncioTestCase):
    async def test_list_calendar_details_filters_and_account_switch(self):
        app = Harness()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            ws = app.query_one(AgendaWorkspace)
            self.assertEqual(len(ws.shown), 3)
            self.assertEqual(len(app.query_one(ListView).children), 3)
            await pilot.click('#agenda-view')
            self.assertTrue(app.query_one(DataTable).display)
            ws.select_row(ws.shown[0])
            self.assertEqual(ws.selected['description'], 'Details')
            app.account_id = None
            ws.check_context()
            await pilot.pause()
            self.assertEqual(ws.rows, [])
            self.assertIsNone(ws.selected)

    async def test_snapshot_rejects_foreign_account_and_links(self):
        provider = Provider()
        from datetime import datetime, timezone
        begin = datetime.now(timezone.utc)
        value = provider.get_agenda(begin, begin + timedelta(days=7), 'evaluated', None)
        with self.assertRaises(ValueError): snapshot(value, '99', 'evaluated')
        value['items'][0]['url'] = 'https://evil.example/'
        with self.assertRaises(ValueError): snapshot(value, '42', 'evaluated')

class AgendaSmallTerminalTests(unittest.IsolatedAsyncioTestCase):
    async def test_narrow_calendar_and_cached_sources(self):
        app = Harness()
        async with app.run_test(size=(40, 25)) as pilot:
            await pilot.pause()
            ws = app.query_one(AgendaWorkspace)
            count = len(app.provider.calls)
            await ws.reload()
            self.assertEqual(len(app.provider.calls), count)
            await pilot.pause()
            await pilot.click('#agenda-view')
            self.assertTrue(app.query_one(DataTable).display)
            self.assertEqual(len(app.query_one(DataTable).columns), 7)

class ProjectHandoffTests(unittest.IsolatedAsyncioTestCase):
    async def test_finish_only_opens_mine_page(self):
        from unittest.mock import patch
        from ft_tui.features.projects.views.details import ProjectDetailsMixin
        pending = []
        project = SimpleNamespace(slug='42cursus-ft_printf', official_project_id=5)
        owner = SimpleNamespace(projects={'p': project}, selected_project_key='p', language='en', run_worker=pending.append)
        with patch('webbrowser.open', return_value=True) as browser:
            ProjectDetailsMixin.action_project_slots(owner, finish=True)
            await pending[0]
            browser.assert_called_once_with('https://projects.intra.42.fr/42cursus-ft_printf/mine')

class ProjectSlotViewTests(unittest.IsolatedAsyncioTestCase):
    async def test_unfinished_project_hides_times_and_explains_intra_action(self):
        import httpx
        from ft_tui.features.corrections.calendar import SlotsCalendar
        class NotReady(Provider):
            def get_agenda(self, *args):
                response = httpx.Response(409, json={'error': 'project_not_ready'}, request=httpx.Request('GET', 'https://example.test/v1/me/agenda'))
                raise httpx.HTTPStatusError('not ready', request=response.request, response=response)
        class ProjectHarness(Harness):
            def compose(self): yield AgendaWorkspace(project_id=5, project_url='https://projects.intra.42.fr/ft_printf/mine')
        app = ProjectHarness(); app.provider = NotReady()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            workspace = app.query_one(AgendaWorkspace)
            self.assertTrue(workspace.project_not_ready)
            self.assertFalse(app.query_one(SlotsCalendar).display)
            self.assertEqual(workspace.shown, [])
            from ft_tui.ui.components import Static, Button
            self.assertIn('Set the project as finished', str(app.query_one('.agenda-status', Static).render()))
            self.assertFalse(app.query_one('#agenda-intra', Button).disabled)

    async def test_project_timeline_is_read_only_and_list_shows_ranges(self):
        from ft_tui.features.corrections.calendar import SlotsCalendar
        from ft_tui.ui.components import Select, Static
        class Ready(Provider):
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                self.calls.append(campus_id)
                start = begin + timedelta(days=6, hours=12)
                return {'account_id':'42','items':[{'id':1,'kind':'available','begin_at':start.isoformat(),'end_at':(start+timedelta(minutes=30)).isoformat(),'title':'Available','description':'','counterpart':'','url':None}]}
        class ProjectHarness(Harness):
            def compose(self): yield AgendaWorkspace(project_id=5, project_url='https://projects.intra.42.fr/ft_printf/mine')
        app = ProjectHarness(); app.provider = Ready()
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            calendar = app.query_one(SlotsCalendar)
            self.assertTrue(calendar.display)
            self.assertFalse(calendar.writable)
            self.assertFalse(app.query_one(Select).display)
            self.assertEqual(app.provider.calls, [1])
            await pilot.click('#agenda-view')
            listing = app.query_one(ListView)
            self.assertTrue(listing.display)
            listing.focus(); listing.index = 0
            await pilot.press('enter')
            await pilot.pause()
            self.assertEqual(app.query_one(AgendaWorkspace).selected['id'], 1)
            label = str(listing.children[0].query_one(Static).render())
            self.assertIn('12:00–12:30', label)
            self.assertNotIn('Available', label)

class ProjectSlotsModalTests(unittest.IsolatedAsyncioTestCase):
    async def test_unfinished_project_modal_is_bounded_at_small_and_large_sizes(self):
        import httpx
        from ft_tui.features.agenda.views import ProjectSlotsScreen
        class NotReady(Provider):
            def get_agenda(self, *args):
                response = httpx.Response(409, json={'error':'project_not_ready'}, request=httpx.Request('GET','https://example.test/v1/me/agenda'))
                raise httpx.HTTPStatusError('not ready',request=response.request,response=response)
        for size, language in (((40,25),'en'),((40,25),'fr'),((40,25),'es'),((120,45),'en')):
            app=Harness();app.provider=NotReady();app.language=language
            async with app.run_test(size=size) as pilot:
                app.push_screen(ProjectSlotsScreen(5,'https://projects.intra.42.fr/ft_printf/mine','ft_printf'))
                await pilot.pause()
                dialog=app.screen.query_one('#project-slots-dialog')
                button=app.screen.query_one('#agenda-intra')
                self.assertLess(dialog.region.width,size[0])
                self.assertGreater(button.region.width,0)
                self.assertLessEqual(button.region.bottom,dialog.region.bottom)
                self.assertEqual(str(button.label), {'en':'Open Intra','fr':'Ouvrir Intra','es':'Abrir Intra'}[language])
                self.assertEqual(button.get_content_height(button.container_size, app.size, button.content_region.width),1)
                close=app.screen.query_one('#project-slots-close')
                self.assertEqual(button.region.y,close.region.y)
                self.assertLessEqual(abs(button.region.width-close.region.width),1)
                self.assertGreaterEqual(close.region.x-button.region.right,2)
                self.assertLessEqual(abs((button.region.x+close.region.right)-(dialog.content_region.x*2+dialog.content_region.width)),1)
                await pilot.click('#project-slots-close')
                self.assertNotIsInstance(app.screen,ProjectSlotsScreen)
