import unittest
from datetime import timedelta
from types import SimpleNamespace
from textual.app import App
from textual.widgets import ListView, DataTable
from ft_tui.features.agenda.models import snapshot
from ft_tui.features.agenda.views import AgendaWorkspace

class Provider:
    def __init__(self): self.calls = []; self.fail = False
    def get_agenda(self, begin, end, kind, target):
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
