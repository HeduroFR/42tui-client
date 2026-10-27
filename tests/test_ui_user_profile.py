import asyncio
import threading
import unittest
from copy import deepcopy
from textual.app import App
from textual.widgets import Static, DataTable
from ft_tui.ui.components import Button, Select
from ft_tui.features.profiles.views.user_profile import UserProfileScreen, open_user_profile
from tests.test_user_profile import profile, attendance
from tests.friends_fixtures import snapshot, attempt


class Provider:
    gate=None
    def get_student_profile(self,user_id,**options):
        if self.gate:self.gate.wait(3)
        value=profile();value['user_id']=user_id;return value
    def get_student_attendance(self,user_id,**options):
        return attendance()
    def get_student_goals(self,user_id,cursus_id):
        return {'user_id':user_id,'cursus_id':cursus_id,'status':'available','stale':False,'collected_at':'2026-10-23T12:00:00Z',
                'next_milestone':'2026-11-03','cc_eta':'2027-08-13','cc_validated':False,'probationary_period':False,'edtrax_weeks':[]}
    def get_friend(self,login,cursus_id,**options):
        value=snapshot(login,user_id=options.get('user_id','50'),cursus_id=cursus_id,
                       items=[attempt(id=1,mark=0,status='finished',validated=False),attempt(1002,id=2,name='Libft',mark=125,status='finished',validated=True)])
        return value


class Harness(App):
    language='en';account_id='42';account_generation=0;account_connected=True;provider=None
    def compose(self):
        yield Button('Caller',id='caller')


async def settle(screen,pilot):
    for _ in range(30):
        await pilot.pause(.02)
        if not screen.loading and not any(w.is_running for w in screen.workers):
            break


class ProfileUITests(unittest.IsolatedAsyncioTestCase):
    async def test_project_row_opens_preview_and_returns_to_student_profile(self):
        from ft_tui.features.friends.views.project import FriendProjectPreview
        app=Harness();app.provider=Provider()
        async with app.run_test(size=(100,36)) as pilot:
            open_user_profile(app,'alice','50');profile_screen=app.screen
            await settle(profile_screen,pilot)
            table=profile_screen.query_one('#profile-projects',DataTable)
            table.focus();await pilot.press('enter');await pilot.pause()
            self.assertIsInstance(app.screen,FriendProjectPreview)
            self.assertEqual(app.screen.student['user_id'],'50')
            await pilot.press('escape');await pilot.pause()
            self.assertIs(app.screen,profile_screen)
            self.assertEqual(table.row_count,2)

    async def test_recent_map_seat_is_available_before_profile_data(self):
        from datetime import datetime,timezone,timedelta
        from test_ui_cluster_map import MapHarness
        from ft_tui.features.cluster_map.views.cluster_map import ClusterMapWorkspace
        from ft_tui.features.friends.views.workspace import current_location
        app=MapHarness();app.account_connected=False
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace)
            app.account_connected=True
            now=datetime.now(timezone.utc)
            ws.snapshot={'machines':[{'hostname':'1a1','status':'up','login':'alice',
                'person':{'user_id':'50'}}],'meta':{'cached_at':now.isoformat(),'stale':False}}
            ws.error=None;ws._update()
            self.assertEqual(current_location(None,app=app,login='alice',user_id='50'),'1A1')
            self.assertEqual(current_location(None,app=app,login='alice',user_id='51'),'Unavailable')
            newer={'location':'2A1','presence':{'status':'available','cached_at':now.isoformat()}}
            ws.snapshot['meta']['cached_at']=(now-timedelta(seconds=1)).isoformat()
            self.assertEqual(current_location(newer,app=app,login='alice'),'2A1')
            ws.snapshot['meta']['cached_at']=now.isoformat()
            ws.snapshot['machines'][0]['status']='down';ws._update()
            self.assertEqual(current_location(None,app=app,login='alice'),'No active session')
            ws.snapshot['machines'][0]['status']='up';ws._update()
            # A separate screen still sees the map underneath it, before projects load.
            screen=UserProfileScreen('alice',user_id='50')
            app.push_screen(screen);await pilot.pause()
            screen._render_presence()
            self.assertIn('1A1',str(screen.query_one('#profile-presence',Static).render()))
            ws.snapshot['meta']['stale']=True
            self.assertEqual(current_location(None,app=app,login='alice'),'Unavailable')
            ws.snapshot['meta']['stale']=False
            ws.snapshot['meta']['cached_at']=(now-timedelta(seconds=61)).isoformat()
            self.assertEqual(current_location(None,app=app,login='alice'),'Unavailable')
            ws.snapshot['meta']['cached_at']=now.isoformat()
            app.account_generation+=1
            self.assertEqual(current_location(None,app=app,login='alice'),'Unavailable')

    async def test_profile_shows_marks_deadlines_zero_stats_and_returns_at_both_sizes(self):
        for size in [(140,48),(80,30)]:
            app=Harness();app.provider=Provider()
            async with app.run_test(size=size) as pilot:
                caller=app.screen
                open_user_profile(app,'alice','50')
                screen=app.screen;await settle(screen,pilot)
                self.assertIsInstance(screen,UserProfileScreen)
                self.assertIn('Alice Example',str(screen.query_one('#profile-name',Static).render()))
                self.assertIn('AE',str(screen.query_one('#profile-portrait').render()))
                self.assertEqual(screen.query_one('#profile-projects',DataTable).row_count,2)
                self.assertIn('03/11/2026',str(screen.query_one('#profile-goals',Static).render()))
                self.assertIn('0',str(screen.query_one('#profile-wallet',Static).render()))
                self.assertLessEqual(screen.query_one('#profile-controls').region.right,size[0])
                self.assertIsInstance(screen.query_one('#profile-cursus'),Select)
                await pilot.press('escape');await pilot.pause()
                self.assertIs(app.screen,caller)

    async def test_optional_outage_and_no_cursus_keep_identity(self):
        class NoCursus(Provider):
            def get_student_profile(self,user_id,**options):
                value=super().get_student_profile(user_id);value['cursus_users']=[];value['main_cursus_id']=None;return value
            def get_student_attendance(self,*args,**kwargs):raise RuntimeError('private error')
        app=Harness();app.provider=NoCursus()
        async with app.run_test(size=(80,30)) as pilot:
            open_user_profile(app,'alice','50');screen=app.screen;await settle(screen,pilot)
            self.assertIn('Alice',str(screen.query_one('#profile-name',Static).render()))
            self.assertEqual(screen.query_one('#profile-projects',DataTable).row_count,0)
            self.assertTrue(screen.query_one('#profile-cursus').disabled)
            self.assertNotIn('private error',str(screen.query_one('#profile-status',Static).render()))

    async def test_late_core_after_close_or_account_change_does_not_publish(self):
        app=Harness();app.provider=Provider();gate=threading.Event();app.provider.gate=gate
        async with app.run_test(size=(100,35)) as pilot:
            open_user_profile(app,'alice','50');screen=app.screen;await pilot.pause(.03)
            await pilot.press('escape');gate.set();await pilot.pause(.1)
            self.assertFalse(screen.is_attached)
            self.assertFalse(getattr(app,'_student_profile_cache',{}))
        app=Harness();app.provider=Provider();gate=threading.Event();app.provider.gate=gate
        async with app.run_test(size=(100,35)) as pilot:
            open_user_profile(app,'alice','50');screen=app.screen;await pilot.pause(.03)
            app.account_generation+=1;app.account_id='43';gate.set();await pilot.pause(.3)
            self.assertFalse(screen.core)
            self.assertFalse(getattr(app,'_student_profile_cache',{}))

    async def test_cluster_profile_opens_in_tui_and_escape_restores_modal(self):
        from test_ui_cluster_map import MapHarness
        from ft_tui.features.cluster_map.views.cluster_map import ClusterMapWorkspace
        from ft_tui.features.cluster_map.views.cluster_map_grid import ClusterMapGrid
        from ft_tui.db.database import make_session_factory
        class ClusterProvider(Provider):
            def get_cluster_map(self):
                value=MapHarness.provider.get_cluster_map()
                value['machines'][0].update(login='alice',person={'user_id':'50','login':'alice','display_name':'Alice','image_url':None})
                return value
        app=MapHarness();app.provider=ClusterProvider();app.session_factory=make_session_factory('sqlite://')
        app._configured_cursus_id=lambda session:21
        try:
            async with app.run_test(size=(160,50)) as pilot:
                ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
                ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
                modal=app.screen
                await pilot.click('#cluster-profile');await pilot.pause()
                self.assertIsInstance(app.screen,UserProfileScreen)
                await settle(app.screen,pilot)
                await pilot.press('escape');await pilot.pause()
                self.assertIs(app.screen,modal)
        finally:app.session_factory.kw['bind'].dispose()

    async def test_friends_profile_action_uses_selected_stable_identity(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from ft_tui.db.database import make_session_factory
        from ft_tui.features.settings.adapters.storage import save_settings
        from ft_tui.ui.app import FortyTwoTuiApp
        from ft_tui.features.friends.views.workspace import FriendsWorkspace
        from textual.widgets import TabbedContent
        with TemporaryDirectory() as directory:
            factory=make_session_factory(f'sqlite:///{Path(directory)/"profile.sqlite"}')
            with factory() as session:save_settings(session,{'onboarding_completed':'true','default_cursus_id':'21'})
            app=FortyTwoTuiApp(factory,None)
            try:
                async with app.run_test(size=(160,50)) as pilot:
                    app.provider=Provider();app.account_id='42';app.account_login='you';app.account_connected=True
                    app.query_one(TabbedContent).active='friends'
                    ws=app.query_one(FriendsWorkspace);await ws.reload();await pilot.pause()
                    ws.selected_login='alice';ws.snapshots['alice']=snapshot();ws._refresh_view();await pilot.pause()
                    await pilot.click('#friend-view-profile');await pilot.pause()
                    self.assertIsInstance(app.screen,UserProfileScreen)
                    self.assertEqual(app.screen.user_id,'50')
                    await settle(app.screen,pilot)
                    await pilot.press('escape');await pilot.pause()
                    self.assertEqual(ws.selected_login,'alice')
            finally:factory.kw['bind'].dispose()

    async def test_cursus_switch_rejects_old_results_and_refresh_stays_enabled(self):
        class Switching(Provider):
            project_gate=threading.Event()
            started=threading.Event()
            def get_student_profile(self,user_id,**options):
                value=super().get_student_profile(user_id,**options)
                value['cursus_users'].append({'cursus_id':9,'name':'Piscine','slug':'c-piscine','grade':None,'level':0})
                return value
            def get_friend(self,login,cursus_id,**options):
                if cursus_id==21:
                    self.started.set();self.project_gate.wait(3)
                value=super().get_friend(login,cursus_id,**options)
                for item in value['items']:item['cursus_ids']=[cursus_id]
                return value
        app=Harness();app.provider=Switching()
        async with app.run_test(size=(100,35)) as pilot:
            open_user_profile(app,'alice','50');screen=app.screen
            for _ in range(20):
                await pilot.pause(.02)
                if app.provider.started.is_set():break
            screen.query_one('#profile-cursus',Select).value=9
            await pilot.pause(.1);app.provider.project_gate.set();await settle(screen,pilot)
            self.assertEqual(screen.cursus_id,9)
            self.assertEqual(screen.project_data['cursus_id'],9)
            self.assertEqual(screen.goals_data['cursus_id'],9)
            self.assertFalse(screen.query_one('#profile-refresh',Button).disabled)

    async def test_reopen_restores_saved_sections_and_expires_presence(self):
        app=Harness();app.provider=Provider()
        async with app.run_test(size=(100,35)) as pilot:
            open_user_profile(app,'alice','50');screen=app.screen;await settle(screen,pilot)
            screen.action_close();await pilot.pause()
            app.account_connected=False
            open_user_profile(app,'alice','50');screen=app.screen;await pilot.pause()
            self.assertTrue(screen.core)
            self.assertTrue(screen.project_data['meta']['stale'])
            self.assertIn('offline',str(screen.query_one('#profile-status').render()))
            self.assertEqual(str(screen.query_one('#profile-presence').render()),'Unavailable')
            self.assertEqual(screen.query_one('#profile-projects',DataTable).row_count,2)

    async def test_optional_auth_failure_prompts_reconnection(self):
        import httpx
        class Expired(Provider):
            def get_student_attendance(self,*args,**kwargs):
                response=httpx.Response(401,request=httpx.Request('GET','https://example.test'))
                response.raise_for_status()
        app=Harness();app.provider=Expired()
        async with app.run_test(size=(100,35)) as pilot:
            open_user_profile(app,'alice','50');screen=app.screen;await settle(screen,pilot)
            self.assertIn('Reconnect',str(screen.query_one('#profile-status').render()))
            self.assertTrue(screen.core)

    async def test_successful_stale_response_obeys_retry_after(self):
        from time import monotonic
        class Limited(Provider):
            def get_student_attendance(self,*args,**kwargs):
                value=attendance();value.update(status='unavailable',collected_at=None,stale=True,reason='upstream_rate_limited',retry_after=90)
                value.pop('days');return value
        app=Harness();app.provider=Limited()
        async with app.run_test(size=(100,35)) as pilot:
            open_user_profile(app,'alice','50');screen=app.screen;await settle(screen,pilot)
            self.assertGreater(screen.retry_at,monotonic()+60)
            self.assertTrue(screen.query_one('#profile-refresh',Button).disabled)

    async def test_core_membership_change_clears_old_cursus_sections_even_when_new_fetch_fails(self):
        class Changed(Provider):
            changed=False
            def get_student_profile(self,user_id,**options):
                value=super().get_student_profile(user_id,**options)
                if self.changed:value.update(main_cursus_id=9,cursus_users=[{'cursus_id':9,'name':'Piscine','slug':'c-piscine','grade':None,'level':0}])
                return value
            def get_friend(self,*args,**kwargs):
                if self.changed:raise RuntimeError('Unavailable new cursus')
                return super().get_friend(*args,**kwargs)
            def get_student_goals(self,*args,**kwargs):
                if self.changed:raise RuntimeError('Unavailable new cursus')
                return super().get_student_goals(*args,**kwargs)
        app=Harness();app.provider=Changed()
        async with app.run_test(size=(100,35)) as pilot:
            open_user_profile(app,'alice','50');screen=app.screen;await settle(screen,pilot)
            self.assertEqual(screen.goals_data['cursus_id'],21)
            app.provider.changed=True;screen.action_refresh();await settle(screen,pilot)
            self.assertEqual(screen.cursus_id,9)
            self.assertIsNone(screen.project_data)
            self.assertNotIn('03/11/2026',str(screen.query_one('#profile-goals').render()))
            self.assertEqual(screen.query_one('#profile-projects',DataTable).row_count,0)

    async def test_open_reopen_and_cursus_navigation_use_cache_but_refresh_is_explicit(self):
        class Recording(Provider):
            def __init__(self):
                self.calls = []
            def get_student_profile(self, user_id, **options):
                self.calls.append(('core', options['refresh']))
                value = super().get_student_profile(user_id, **options)
                value['cursus_users'].append({'cursus_id':9,'name':'Piscine','slug':'c-piscine','grade':None,'level':0})
                return value
            def get_student_attendance(self, user_id, **options):
                self.calls.append(('attendance', options['refresh']))
                return super().get_student_attendance(user_id, **options)
            def get_friend(self, login, cursus_id, **options):
                self.calls.append(('projects', options['refresh']))
                return super().get_friend(login, cursus_id, **options)
        app = Harness(); app.provider = Recording()
        async with app.run_test(size=(100,35)) as pilot:
            for _ in range(2):
                app.provider.calls.clear()
                open_user_profile(app, 'alice', '50'); screen = app.screen
                await settle(screen, pilot)
                self.assertCountEqual(app.provider.calls, [('core', False), ('attendance', False), ('projects', False)])
                screen.action_close(); await pilot.pause()
            open_user_profile(app, 'alice', '50'); screen = app.screen
            await settle(screen, pilot)
            app.provider.calls.clear()
            screen.action_refresh(); await settle(screen, pilot)
            self.assertCountEqual(app.provider.calls, [('core', True), ('attendance', True), ('projects', True)])
            app.provider.calls.clear()
            screen.query_one('#profile-cursus', Select).value = 9
            await settle(screen, pilot)
            self.assertEqual(app.provider.calls, [('projects', False)])
