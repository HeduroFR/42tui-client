import unittest
import asyncio
import threading
from datetime import timedelta
from types import SimpleNamespace
from textual.app import App
from textual.widgets import ListView, DataTable
from ft_tui.features.agenda.models import snapshot
from ft_tui.features.agenda.views import AgendaWorkspace
from ft_tui.features.agenda.views.calendar import AgendaCalendar

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
    async def test_transient_initial_failures_are_retried(self):
        class WarmingUp(Provider):
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                if kind not in self.calls:
                    self.calls.append(kind)
                    raise OSError('temporarily unavailable')
                return super().get_agenda(begin, end, kind, target, campus_id)
        app = Harness()
        app.provider = WarmingUp()
        async with app.run_test(size=(100, 40)) as pilot:
            ws = app.query_one(AgendaWorkspace)
            for _ in range(100):
                await pilot.pause(.04)
                if len(ws.shown) == 4 and not ws.loading:
                    break
            self.assertEqual(len(ws.shown), 4)
            self.assertEqual(app.provider.calls.count('exam'), 2)
            self.assertIn('Up to date', str(ws.query_one('.agenda-status').render()))

    async def test_background_refresh_keeps_unchanged_selection(self):
        app = Harness()
        async with app.run_test(size=(100, 40)) as pilot:
            ws = app.query_one(AgendaWorkspace)
            for _ in range(50):
                await pilot.pause(.01)
                if len(ws.shown) == 4 and not ws.loading:
                    break
            ws.select_row(next(row for row in ws.shown if row['kind'] == 'event'))
            with unittest.mock.patch.object(ws, 'render_rows', wraps=ws.render_rows) as render:
                await ws.reload(refresh=True, background=True)
                self.assertEqual(ws.selected['kind'], 'event')
                self.assertFalse(ws.query_one('#agenda-intra').disabled)
                render.assert_not_called()

    async def test_event_opens_direct_intra_link_without_source_url(self):
        from unittest.mock import patch
        from ft_tui.ui.components import Button
        app = Harness()
        async with app.run_test(size=(100, 40)) as pilot:
            ws = app.query_one(AgendaWorkspace)
            for _ in range(50):
                await pilot.pause(.01)
                if len(ws.shown) == 4 and not ws.loading:
                    break
            ws.select_row(next(row for row in ws.shown if row['kind'] == 'event'))
            self.assertFalse(ws.query_one('#agenda-intra').disabled)
            with patch('ft_tui.features.agenda.views.webbrowser.open', return_value=True) as browser:
                await ws.on_button_pressed(Button.Pressed(ws.query_one('#agenda-intra', Button)))
                await pilot.pause()
            browser.assert_called_once_with('https://profile.intra.42.fr/events/1')

    async def test_week_navigation_remains_responsive_during_slow_exam(self):
        from ft_tui.ui.components import Button
        gate = threading.Event()
        started = threading.Event()
        class SlowExam(Provider):
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                if kind == 'exam':
                    started.set()
                    gate.wait(3)
                return super().get_agenda(begin, end, kind, target, campus_id)
        app = Harness()
        app.provider = SlowExam()
        try:
            async with app.run_test(size=(100, 40)) as pilot:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                ws = app.query_one(AgendaWorkspace)
                old_week = ws.week
                await ws.on_button_pressed(Button.Pressed(ws.query_one('#agenda-next', Button)))
                await pilot.pause(.1)
                self.assertEqual(ws.week, old_week + timedelta(days=7))
                self.assertIn('Loading', str(ws.query_one('.agenda-status').render()))
                await ws.on_button_pressed(Button.Pressed(ws.query_one('#agenda-next', Button)))
                await pilot.pause(.1)
                self.assertEqual(ws.week, old_week + timedelta(days=14))
                gate.set()
                for _ in range(80):
                    await pilot.pause(.01)
                    if not ws.loading and len(ws.shown) == 4:
                        break
                self.assertEqual({row['kind'] for row in ws.shown}, {'event', 'exam', 'evaluating', 'evaluated'})
                self.assertTrue(all(row['begin_at'].startswith(str(ws.week)) for row in ws.shown))
        finally:
            gate.set()

    async def test_fast_sources_display_while_another_source_is_loading(self):
        gate = threading.Event()
        started = threading.Event()
        class SlowEvents(Provider):
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                if kind == 'event':
                    started.set()
                    gate.wait(3)
                return super().get_agenda(begin, end, kind, target, campus_id)
        app = Harness()
        app.provider = SlowEvents()
        try:
            async with app.run_test(size=(100, 40)) as pilot:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                ws = app.query_one(AgendaWorkspace)
                for _ in range(50):
                    await pilot.pause(.01)
                    if len(ws.shown) >= 3:
                        break
                self.assertTrue(ws.loading)
                self.assertEqual({row['kind'] for row in ws.shown}, {'evaluating', 'evaluated', 'exam'})
                self.assertIn('Loading', str(ws.query_one('.agenda-status').render()))
                gate.set()
                for _ in range(50):
                    await pilot.pause(.01)
                    if not ws.loading:
                        break
                self.assertEqual(len(ws.shown), 4)
        finally:
            gate.set()

    async def test_failed_source_is_marked_stale_while_another_source_is_loading(self):
        gate = threading.Event()
        started = threading.Event()
        class PartialFailure(Provider):
            delayed = False
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                if self.delayed and kind == 'event':
                    started.set()
                    gate.wait(3)
                if self.delayed and kind == 'evaluated':
                    raise OSError('offline')
                return super().get_agenda(begin, end, kind, target, campus_id)
        app = Harness()
        app.provider = PartialFailure()
        try:
            async with app.run_test(size=(100, 40)) as pilot:
                ws = app.query_one(AgendaWorkspace)
                for _ in range(50):
                    await pilot.pause(.01)
                    if ws.shown and not ws.loading:
                        break
                self.assertEqual(len(ws.shown), 4)
                app.provider.delayed = True
                worker = ws.run_worker(ws.reload(refresh=True))
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                for _ in range(50):
                    await pilot.pause(.01)
                    if 'Unavailable' in str(ws.query_one('.agenda-status').render()):
                        break
                self.assertTrue(ws.loading)
                self.assertIn('Unavailable or stale', str(ws.query_one('.agenda-status').render()))
                self.assertTrue(any(row['kind'] == 'evaluated' for row in ws.shown))
                gate.set()
                await worker.wait()
        finally:
            gate.set()

    async def test_late_authorization_failure_clears_progressive_results(self):
        import httpx
        gate = threading.Event()
        started = threading.Event()
        class Expired(Provider):
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                if kind == 'event':
                    started.set()
                    gate.wait(3)
                    request = httpx.Request('GET', 'https://example.test/agenda')
                    raise httpx.HTTPStatusError('unauthorized', request=request, response=httpx.Response(401, request=request))
                return super().get_agenda(begin, end, kind, target, campus_id)
        app = Harness()
        app.provider = Expired()
        try:
            async with app.run_test(size=(100, 40)) as pilot:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                ws = app.query_one(AgendaWorkspace)
                for _ in range(50):
                    await pilot.pause(.01)
                    if ws.shown:
                        break
                self.assertTrue(ws.shown)
                gate.set()
                for _ in range(50):
                    await pilot.pause(.01)
                    if not ws.loading:
                        break
                self.assertFalse(ws.shown)
                self.assertFalse(ws.sources)
                self.assertIn('Unavailable', str(ws.query_one('.agenda-status').render()))
        finally:
            gate.set()

    async def test_unauthorized_source_clears_results_while_another_read_is_pending(self):
        import httpx
        denied = threading.Event()
        blocked = threading.Event()
        release = threading.Event()
        class Expired(Provider):
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                if kind == 'event':
                    denied.wait(3)
                    request = httpx.Request('GET', 'https://example.test/agenda')
                    raise httpx.HTTPStatusError('unauthorized', request=request, response=httpx.Response(401, request=request))
                if kind == 'exam':
                    blocked.set()
                    release.wait(3)
                return super().get_agenda(begin, end, kind, target, campus_id)
        app = Harness()
        app.provider = Expired()
        try:
            async with app.run_test(size=(100, 40)) as pilot:
                self.assertTrue(await asyncio.to_thread(blocked.wait, 1))
                ws = app.query_one(AgendaWorkspace)
                for _ in range(50):
                    await pilot.pause(.01)
                    if ws.shown:
                        break
                self.assertTrue(ws.shown)
                denied.set()
                for _ in range(50):
                    await pilot.pause(.01)
                    if not ws.loading:
                        break
                self.assertFalse(ws.loading)
                self.assertFalse(ws.shown)
                self.assertFalse(ws.sources)
        finally:
            denied.set()
            release.set()

    async def test_exit_while_sources_are_still_loading_is_safe(self):
        gate = threading.Event()
        started = threading.Event()
        class SlowEvents(Provider):
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                if kind == 'event':
                    started.set()
                    gate.wait(3)
                return super().get_agenda(begin, end, kind, target, campus_id)
        app = Harness()
        app.provider = SlowEvents()
        try:
            async with app.run_test(size=(100, 40)) as pilot:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                ws = app.query_one(AgendaWorkspace)
                for _ in range(50):
                    await pilot.pause(.01)
                    if ws.shown:
                        break
                self.assertTrue(ws.shown)
                self.assertTrue(ws.loading)
        finally:
            gate.set()

    async def test_old_week_results_cannot_replace_new_week_during_progressive_load(self):
        gate = threading.Event()
        started = threading.Event()
        class SlowOldWeek(Provider):
            old_begin = None
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                if self.old_begin is None:
                    self.old_begin = begin
                if kind == 'event' and begin == self.old_begin:
                    started.set()
                    gate.wait(3)
                return super().get_agenda(begin, end, kind, target, campus_id)
        app = Harness()
        app.provider = SlowOldWeek()
        try:
            async with app.run_test(size=(100, 40)) as pilot:
                self.assertTrue(await asyncio.to_thread(started.wait, 1))
                ws = app.query_one(AgendaWorkspace)
                old_week = ws.week
                from ft_tui.ui.components import Button
                await ws.on_button_pressed(Button.Pressed(ws.query_one('#agenda-next', Button)))
                for _ in range(50):
                    await pilot.pause(.01)
                    if not ws.loading:
                        break
                self.assertEqual(ws.week, old_week + timedelta(days=7))
                self.assertEqual(len(ws.shown), 4)
                gate.set()
                await pilot.pause(.1)
                self.assertTrue(all(row['begin_at'].startswith(str(ws.week)) for row in ws.shown))
        finally:
            gate.set()

    async def test_list_calendar_details_filters_and_account_switch(self):
        app = Harness()
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            ws = app.query_one(AgendaWorkspace)
            self.assertEqual(len(ws.shown), 4)
            self.assertEqual(len(app.query_one(ListView).children), 4)
            self.assertTrue(app.query_one(AgendaCalendar).display)
            ws.select_row(ws.shown[0])
            self.assertEqual(ws.selected['description'], 'Details')
            app.account_id = None
            ws.check_context()
            self.assertEqual(app.query_one(AgendaCalendar).blocks,[])
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
            self.assertTrue(app.query_one(AgendaCalendar).display)
            self.assertEqual(len(app.query_one(AgendaCalendar).columns), 1)

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
            self.assertFalse(workspace.query_one('.agenda-toolbar').display)
            self.assertFalse(workspace.query_one('.agenda-period').display)
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

class WeekTimelineTests(unittest.TestCase):
    def test_overlap_midnight_and_non_rounded_times_keep_every_item(self):
        from datetime import date, timezone
        from ft_tui.features.agenda.models import timeline_cells
        rows = [
            {'id':1,'begin_at':'2026-10-26T23:45:00Z','end_at':'2026-10-27T00:20:00Z'},
            {'id':2,'begin_at':'2026-10-27T00:05:00Z','end_at':None},
        ]
        cells = timeline_cells(rows,date(2026,10,26),timezone.utc)
        self.assertEqual([row['id'] for row in cells[47,0]],[1])
        self.assertEqual([row['id'] for row in cells[0,1]],[1,2])
        self.assertNotIn((1,1),cells)

    def test_repeated_dst_hour_keeps_both_evaluations(self):
        from datetime import date
        from zoneinfo import ZoneInfo
        from ft_tui.features.agenda.models import timeline_cells
        rows = [
            {'id':1,'begin_at':'2026-10-25T00:15:00Z','end_at':'2026-10-25T00:45:00Z'},
            {'id':2,'begin_at':'2026-10-25T01:15:00Z','end_at':'2026-10-25T01:45:00Z'},
        ]
        cells=timeline_cells(rows,date(2026,10,19),ZoneInfo('Europe/Paris'))
        self.assertEqual([row['id'] for row in cells[4,6]],[1,2])

class WeekDetailPanelTests(unittest.IsolatedAsyncioTestCase):
    async def test_timeline_selection_and_filter_update_detail_panel(self):
        from ft_tui.ui.components import Static, Select
        app=Harness()
        async with app.run_test(size=(120,40)) as pilot:
            await pilot.pause()
            workspace=app.query_one(AgendaWorkspace)
            calendar=workspace.query_one(AgendaCalendar)
            self.assertEqual(len(calendar.blocks),4)
            self.assertFalse(workspace.query('#agenda-view'))
            calendar.focus();calendar.day=0;calendar.row=24
            await pilot.press('enter');await pilot.pause()
            self.assertIsNotNone(workspace.selected)
            self.assertTrue(workspace.query_one(ListView).display)
            workspace.query_one(Select).value='event';await pilot.pause()
            self.assertEqual(len(workspace.shown),1)
            calendar.focus();calendar.day=0;calendar.row=24
            await pilot.press('enter');await pilot.pause()
            self.assertEqual(workspace.selected['kind'],'event')
            self.assertFalse(workspace.query_one(ListView).display)
            calendar.row=0
            await pilot.press('enter');await pilot.pause()
            self.assertIsNone(workspace.selected)
            await pilot.resize_terminal(40,25);await pilot.pause()
            self.assertTrue(workspace.has_class('agenda-narrow'))
            self.assertGreaterEqual(workspace.query_one('.agenda-sidebar').region.y,workspace.query_one('.agenda-calendar-panel').region.bottom)

class AgendaFilterTests(unittest.IsolatedAsyncioTestCase):
    async def test_filter_label_and_dropdown_have_room_in_each_language(self):
        from ft_tui.ui.components import Select
        from textual.widgets._select import SelectCurrent, SelectOverlay
        for size,language in [((40,30),'en'),((120,40),'en'),((120,40),'fr'),((120,40),'es')]:
            app=Harness();app.language=language
            async with app.run_test(size=size) as pilot:
                await pilot.pause()
                selector=app.query_one(Select)
                label=selector.query_one(SelectCurrent).query_one('#label')
                self.assertGreaterEqual(label.region.width,18)
                selector.focus()
                await pilot.press('enter');await pilot.pause()
                self.assertTrue(selector.expanded)
                self.assertGreaterEqual(selector.query_one(SelectOverlay).region.width,24)
                await pilot.press('down','enter');await pilot.pause()
                self.assertFalse(selector.expanded)
                self.assertEqual(selector.value,'event')
                self.assertTrue(all(row['kind']=='event' for row in app.query_one(AgendaWorkspace).shown))

class AgendaBlockTests(unittest.TestCase):
    def test_only_overlapping_events_share_width(self):
        from ft_tui.features.agenda.models import timeline_blocks
        a={'id':1,'kind':'event'};b={'id':2,'kind':'event'};c={'id':3,'kind':'event'}
        blocks=timeline_blocks({(20,0):[a],(21,0):[a,b],(22,0):[b],(25,0):[c]})
        self.assertEqual([(b['lane'],b['lanes']) for b in blocks],[(0,2),(1,2),(0,1)])

class AgendaCalendarInteractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_keyboard_leaves_event_and_unicode_blocks_fit_columns(self):
        app=Harness()
        async with app.run_test(size=(120,40)) as pilot:
            await pilot.pause()
            workspace=app.query_one(AgendaWorkspace)
            calendar=workspace.query_one(AgendaCalendar)
            item=dict(workspace.shown[0],title='测试 🎃 Valgrind',end_at=None)
            workspace.rows=[item]
            await workspace.render_rows();await pilot.pause()
            for y in range(calendar.size.height):
                self.assertLessEqual(calendar.render_line(y).cell_length,calendar.size.width)
            calendar.focus();calendar.day=0;calendar.row=24
            await pilot.press('enter','down');await pilot.pause()
            self.assertEqual(calendar.row,25)
            self.assertIsNone(workspace.selected)
            await pilot.press('up','enter');await pilot.pause()
            self.assertEqual(workspace.selected['title'],'测试 🎃 Valgrind')
            column=next(col for col in calendar.columns if col[0]==0)
            y=24-int(calendar.scroll_offset.y)
            await pilot.click('#agenda-calendar',offset=(column[1]+1,y))
            self.assertEqual(workspace.selected['id'],item['id'])

class AgendaExamDetailsTests(unittest.IsolatedAsyncioTestCase):
    async def test_exam_details_metadata_markdown_and_intra_handoff(self):
        from unittest.mock import patch
        from ft_tui.ui.components import Static, Select, Button
        from textual.widgets import Markdown
        class Exams(Provider):
            def get_agenda(self, begin, end, kind, target, campus_id=None):
                self.calls.append(kind)
                start=begin+timedelta(days=3,hours=13,minutes=15)
                rows=[] if kind!='exam' else [dict(id=5,kind='exam',begin_at=start.isoformat(),end_at=(start+timedelta(hours=3)).isoformat(),title='EXAM RANK X',description='# Exam session\n\n- Bring your ID\n- Check registration',counterpart='',url='https://profile-v3.intra.42.fr/',location='C1',subscribers=0,capacity=45,projects=['Exam Rank 02','Exam Rank 03'])]
                return dict(account_id='42',items=rows)
        app=Harness();app.provider=Exams()
        async with app.run_test(size=(150,44)) as pilot:
            await pilot.pause();await pilot.pause()
            workspace=app.query_one(AgendaWorkspace)
            self.assertIn('exam',app.provider.calls)
            self.assertEqual(workspace.selected['kind'],'exam')
            text=str(workspace.query_one('#agenda-detail',Static).render())
            for expected in ('3h','C1','0/45','Exam Rank 02','Exam Rank 03'):
                self.assertIn(expected,text)
            self.assertIn('EXAM RANK X',str(workspace.query_one('#agenda-item-title',Static).render()))
            markdown=workspace.query_one('#agenda-description',Markdown)
            self.assertTrue(markdown.query('MarkdownH1'))
            self.assertTrue(markdown.query('MarkdownBulletList'))
            self.assertIn('both the exam session',str(workspace.query_one('#agenda-exam-note',Static).render()))
            button=workspace.query_one('#agenda-intra',Button)
            self.assertEqual(str(button.label),'Open on Intra')
            with patch('ft_tui.features.agenda.views.webbrowser.open',return_value=True) as browser:
                await pilot.click('#agenda-intra');await pilot.pause()
                browser.assert_called_once_with('https://profile.intra.42.fr/exams/5')
            workspace.query_one(Select).value='event';await pilot.pause()
            self.assertEqual(workspace.shown,[])
            self.assertFalse(markdown.query('MarkdownH1'))

    async def test_exam_unavailability_does_not_hide_other_sources(self):
        class OlderBackend(Provider):
            def get_agenda(self,begin,end,kind,target,campus_id=None):
                if kind=='exam':raise RuntimeError('source not deployed')
                return super().get_agenda(begin,end,kind,target,campus_id)
        app=Harness();app.provider=OlderBackend()
        async with app.run_test(size=(120,40)) as pilot:
            await pilot.pause()
            workspace=app.query_one(AgendaWorkspace)
            self.assertEqual(len(workspace.shown),3)
            from ft_tui.ui.components import Static
            self.assertIn('Exam',str(workspace.query_one('.agenda-status',Static).render()))

    def test_optional_metadata_rejects_malformed_values(self):
        from datetime import datetime,timezone
        begin=datetime.now(timezone.utc)
        value=Provider().get_agenda(begin,begin+timedelta(days=7),'event',1)
        for field,invalid in [('location',3),('subscribers',True),('capacity',-1),('projects',[123])]:
            row=dict(value['items'][0]);row[field]=invalid
            with self.assertRaises(ValueError):snapshot({'account_id':'42','items':[row]},'42','event')

class AgendaPermissionFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_denied_exam_is_explained_and_other_sources_remain_visible(self):
        import httpx
        from ft_tui.ui.components import Static
        class DeniedExams(Provider):
            def get_agenda(self,begin,end,kind,target,campus_id=None):
                if kind=='exam':
                    response=httpx.Response(403,json={'error':'upstream_permission_denied'},request=httpx.Request('GET','https://example.test/v1/me/agenda'))
                    raise httpx.HTTPStatusError('denied',request=response.request,response=response)
                return super().get_agenda(begin,end,kind,target,campus_id)
        app=Harness();app.provider=DeniedExams()
        async with app.run_test(size=(120,40)) as pilot:
            await pilot.pause();await pilot.pause()
            workspace=app.query_one(AgendaWorkspace)
            self.assertIn('Exam · Access denied by 42',str(workspace.query_one('.agenda-status',Static).render()))
            self.assertEqual(len(workspace.shown),3)
            self.assertFalse(any(row['kind']=='exam' for row in workspace.shown))
