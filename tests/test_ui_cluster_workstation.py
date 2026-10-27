import unittest
from textual.widgets import TabbedContent, Collapsible
from textual.containers import VerticalScroll
from test_ui_cluster_map import MapHarness
from ft_tui.features.cluster_map.views.cluster_map import ClusterMapWorkspace
from ft_tui.features.cluster_map.views.cluster_workstation import ClusterWorkstationModal
from ft_tui.features.cluster_map.views.cluster_map_grid import ClusterMapGrid
from ft_tui.features.cluster_map.state import SeatState


class ModalTests(unittest.IsolatedAsyncioTestCase):
    async def test_person_cache_reopens_immediately_refreshes_and_isolates_identity(self):
        import threading
        from dataclasses import replace
        from ft_tui.db.database import make_session_factory
        from ft_tui.ui.components import Static
        from tests.friends_fixtures import snapshot
        class Provider:
            calls=0;name='Cached profile';gate=None;fail=False;malformed=False
            def get_cluster_map(self):return MapHarness.provider.get_cluster_map()
            def get_friend(self,login,cursus,**options):
                self.calls+=1
                if self.gate:self.gate.wait(5)
                if self.fail:raise RuntimeError('offline')
                data=snapshot(login,user_id=options['user_id'],cursus_id=cursus)
                data.update(display_name=self.name,wallet=42)
                if self.malformed:data.pop('login')
                return data
        app=MapHarness();app.provider=Provider();app.session_factory=make_session_factory('sqlite://')
        app._configured_cursus_id=lambda session:21
        try:
            async with app.run_test(size=(160,50)) as pilot:
                ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
                ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
                await ws.modal.workers.wait_for_complete()
                self.assertEqual(app.provider.calls,1)
                ws.modal.dismiss();await pilot.pause()
                # The same user at another workstation shares the cached profile.
                ws.states['1A2']=replace(ws.states['1A1'],hostname='1A2')
                ws.open_seat(ClusterMapGrid.SeatSelected('1A2'));await pilot.pause()
                self.assertEqual(app.provider.calls,1)
                self.assertIn('Cached profile',str(ws.modal.query_one('#cluster-person-info',Static).render()))
                self.assertIn('1A2',str(ws.modal.query_one('#cluster-person-host',Static).render()))
                ws.modal.dismiss();await pilot.pause()
                key=ws.person_cache_key(ws.states['1A1'],21)
                stamp,data=ws.person_cache[key];ws.person_cache[key]=(stamp-301,data)
                app.provider.gate=threading.Event();app.provider.name='Refreshed profile'
                ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
                self.assertIn('Cached profile',str(ws.modal.query_one('#cluster-person-info',Static).render()))
                self.assertIn('42',str(ws.modal.query_one('#cluster-person-school',Static).render()))
                self.assertNotIn('Loading',str(ws.modal.query_one('#cluster-person-projects',Static).render()))
                app.provider.gate.set();await ws.modal.workers.wait_for_complete();await pilot.pause()
                self.assertIn('Refreshed profile',str(ws.modal.query_one('#cluster-person-info',Static).render()))
                ws.modal.dismiss();await pilot.pause()
                stamp,data=ws.person_cache[key];ws.person_cache[key]=(stamp-301,data)
                app.provider.fail=True
                ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
                await ws.modal.workers.wait_for_complete()
                self.assertIn('Refreshed profile',str(ws.modal.query_one('#cluster-person-info',Static).render()))
                self.assertIn('stale',str(ws.modal.query_one('#cluster-person-projects',Static).render()))
                ws.modal.dismiss();await pilot.pause()
                app.provider.fail=False;app.provider.name='Other user'
                ws.states['1A1']=replace(ws.states['1A1'],login='other',person={'user_id':'99'})
                calls=app.provider.calls
                ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
                await ws.modal.workers.wait_for_complete()
                self.assertEqual(app.provider.calls,calls+1)
                self.assertEqual(ws.modal.person_data['user_id'],'99')
                other=ws.states['1A1']
                ws.modal.dismiss();await pilot.pause()
                # An old refresh must not overwrite a cached newly selected occupant.
                ws.states['1A1']=replace(ws.states['1A2'],hostname='1A1')
                app.provider.gate=threading.Event()
                ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
                ws.modal.update_seat(other)
                await pilot.pause()
                self.assertTrue(await pilot.click('#cluster-latest'));await pilot.pause()
                self.assertEqual(ws.modal.person_data['user_id'],'99')
                app.provider.gate.set();await ws.modal.workers.wait_for_complete();await pilot.pause()
                self.assertEqual(ws.modal.person_data['user_id'],'99')
                app.account_generation+=1
                await ws.reload();await pilot.pause()
                self.assertFalse(ws.person_cache)
                app.provider.malformed=True
                ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
                await ws.modal.workers.wait_for_complete()
                self.assertFalse(ws.person_cache)
                self.assertFalse(ws.modal.person_data)
        finally:
            if app.provider.gate:app.provider.gate.set()
            app.session_factory.kw['bind'].dispose()

    async def test_workstation_loads_and_refreshes_its_embedded_reports(self):
        from ft_tui.ui.components import Static
        class Provider:
            calls=0
            def get_cluster_map(self):return MapHarness.provider.get_cluster_map()
            def get_cluster_issues(self,host,**options):
                self.calls+=1
                return {'items':[],'next_cursor':None,'meta':{'stale':False}}
        app=MapHarness();app.provider=Provider()
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
            modal=app.screen;tabs=modal.query_one('#cluster-modal-tabs',TabbedContent)
            self.assertEqual(app.provider.calls,0)
            tabs.active='cluster-workstation';await pilot.pause()
            await modal.workers.wait_for_complete();await pilot.pause()
            self.assertTrue(modal.reports_loaded)
            scroll=modal.query_one('#cluster-workstation-scroll')
            for ident in ('cluster-machine-info','cluster-machine-session','cluster-storage-root','cluster-report-status','cluster-reports'):
                self.assertTrue(scroll.query('#'+ident))
            self.assertIn('No known open reports',str(modal.query_one('#cluster-report-status',Static).render()))
            before=app.provider.calls
            modal._refresh_reports();await modal.workers.wait_for_complete();await pilot.pause()
            self.assertEqual(app.provider.calls,before+1)
            tabs.active='cluster-person';await pilot.pause()
            modal._refresh_reports();await pilot.pause()
            self.assertEqual(app.provider.calls,before+1)

    async def test_workstation_cards_preserve_zero_storage_and_fit_narrow_screens(self):
        from ft_tui.ui.components import Static
        app=MapHarness()
        async with app.run_test(size=(160,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            seat=SeatState('1A1',login='abcdefgh',machine='online',session='signed in',open_count=0,
                storage={'root':'0%','goinfre':'41%'})
            modal=ClusterWorkstationModal(ws,'1A1',seat,'workstation',ws._scope())
            app.push_screen(modal);await pilot.pause()
            self.assertIn('0 open reports',str(modal.query_one('#cluster-machine-reports',Static).render()))
            self.assertTrue(modal.query_one('#cluster-storage-root-progress').display)
            self.assertEqual(modal.query_one('#cluster-storage-root-progress').progress,0)
            self.assertEqual(modal.query_one('#cluster-storage-goinfre-progress').progress,41)
            for width in (160,80,60):
                await pilot.resize_terminal(width,30);await pilot.pause()
                from ft_tui.ui.button import AppButton
                close=modal.query_one('#cluster-close',AppButton)
                self.assertTrue(close.square)
                self.assertEqual(close.variant,'danger')
                self.assertEqual(close.region.height,3)
                self.assertEqual(close.region.width,6)
                self.assertTrue(modal.query_one('#cluster-modal-header').region.contains_region(close.region))
                scroll=modal.query_one('#cluster-workstation-scroll')
                for card in scroll.query('#cluster-workstation-layout .cluster-detail-card'):
                    self.assertGreater(card.region.width,0)
                    self.assertLessEqual(card.region.right,scroll.content_region.right)
            modal.update_seat(SeatState('1A1',storage={'root':0}))
            self.assertEqual(str(modal.query_one('#cluster-storage-root',Static).render()),'0')
            self.assertFalse(modal.query_one('#cluster-storage-root-progress').display)
            self.assertIn('Unavailable',str(modal.query_one('#cluster-storage-goinfre',Static).render()))
            self.assertIn('Reports unavailable',str(modal.query_one('#cluster-machine-reports',Static).render()))
            self.assertEqual(len(modal.query('#cluster-modal-tabs TabPane')),2)
            self.assertFalse(modal.query('#cluster-issues'))
            self.assertTrue(modal.query_one('#cluster-reports').is_mounted)
            self.assertEqual(modal.query_one('#cluster-modal-tabs',TabbedContent).active,'cluster-workstation')

    async def test_progress_uses_target_main_cursus_and_marks_estimated_xp(self):
        from ft_tui.db.database import make_session_factory
        from ft_tui.ui.components import Static
        from tests.friends_fixtures import snapshot
        class Provider:
            exact=False
            zero=False
            calls=[]
            def get_cluster_map(self):return MapHarness.provider.get_cluster_map()
            def get_friend(self,login,cursus,**options):
                self.calls.append((cursus,options.get('user_id')))
                data=snapshot(login,user_id='42',cursus_id=cursus,items=[],level=0 if cursus==9 or self.zero else 2.25)
                data.update(main_cursus_id=21,cursus_name='Piscine' if cursus==9 else '42cursus')
                data['xp_progress']={'total_xp':1500,'level_start_xp':1000,'next_level_xp':3000} if self.exact and cursus==21 else None
                if self.exact and self.zero and cursus==21:data['xp_progress']={'total_xp':0,'level_start_xp':0,'next_level_xp':1000}
                return data
        app=MapHarness();app.provider=Provider();app.session_factory=make_session_factory('sqlite://')
        app._configured_cursus_id=lambda session:9
        try:
            async with app.run_test(size=(160,50)) as pilot:
                ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
                ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
                modal=app.screen
                await modal.workers.wait_for_complete();await pilot.pause()
                text=str(modal.query_one('#cluster-person-cursus',Static).render())
                self.assertIn('Cursus: 42cursus',text);self.assertIn('Level: 2.25',text)
                self.assertNotIn('0.00',text)
                self.assertIn((21,'42'),app.provider.calls)
                self.assertTrue(modal.query_one('#cluster-level-progress').display)
                self.assertIn('Estimated XP',str(modal.query_one('#cluster-person-xp',Static).render()))
                self.assertIn('799 / 3,197 XP',str(modal.query_one('#cluster-person-xp',Static).render()))
                app.provider.zero=True
                await modal._load_person();await pilot.pause()
                self.assertIn('0 / 462 XP',str(modal.query_one('#cluster-person-xp',Static).render()))
                self.assertEqual(modal.query_one('#cluster-level-progress').progress,0)
                app.provider.zero=False
                app.provider.exact=True
                await modal._load_person();await pilot.pause()
                bar=modal.query_one('#cluster-level-progress')
                self.assertTrue(bar.display);self.assertEqual(bar.progress,500);self.assertEqual(bar.total,2000)
                self.assertIn('500 / 2,000 XP',str(modal.query_one('#cluster-person-xp',Static).render()))
                self.assertNotIn('Estimated XP',str(modal.query_one('#cluster-person-xp',Static).render()))
                app.provider.zero=True
                await modal._load_person();await pilot.pause()
                self.assertIn('Level: 0.00',str(modal.query_one('#cluster-person-cursus',Static).render()))
                self.assertIn('0 / 1,000 XP',str(modal.query_one('#cluster-person-xp',Static).render()))
                self.assertTrue(bar.display);self.assertEqual(bar.progress,0)
        finally:app.session_factory.kw['bind'].dispose()

    async def test_sixel_partial_repaint_uses_the_fragment_position(self):
        from PIL import Image
        from rich.control import Control
        from textual.app import App
        from textual.geometry import Region
        from unittest.mock import patch
        from ft_tui.features.cluster_map.views.portrait import PortraitSixelImage, _PortraitSixelImpl
        class PortraitApp(App):
            def compose(self):
                image=PortraitSixelImage(Image.new('RGB',(32,32),'red'))
                image.styles.width=20;image.styles.height=10
                yield image
        app=PortraitApp()
        async with app.run_test(size=(80,24)) as pilot:
            await pilot.pause()
            renderer=app.query_one(_PortraitSixelImpl)
            with patch.object(renderer,'_image_to_sixels',return_value='pixels'):
                for crop in (Region(0,0,10,8),Region(2,3,5,2)):
                    strips=renderer.render_lines(crop)
                    segments=list(strips[-1])
                    self.assertEqual(segments[-3].text,Control.move_to(renderer.region.x+crop.x,renderer.region.y+crop.y).segment.text)
                    self.assertEqual(segments[-2].text,'pixels')

    async def test_school_life_and_add_friend_use_the_displayed_identity(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from ft_tui.db.database import make_session_factory
        from ft_tui.features.settings.adapters.storage import save_settings
        from ft_tui.features.friends.adapters.storage import memberships
        from ft_tui.ui.app import FortyTwoTuiApp
        from ft_tui.ui.components import Static,Button
        from tests.friends_fixtures import snapshot
        class Provider:
            calls=[]
            social_calls=[]
            def social_action(self,draft):
                self.social_calls.append(draft)
                return {"ok":True}
            def get_cluster_map(self):return MapHarness.provider.get_cluster_map()
            def get_friend(self,login,cursus,*,refresh=False,user_id=None):
                self.calls.append((login,user_id))
                data=snapshot(login,user_id=user_id or '42')
                data.update(display_name='Alex Example',wallet=0,correction_point=0,pool_month='september',pool_year='2026',achievements_count=9,coalitions=[{'id':7,'name':'Analysts'}],titles=['Mastermind %login',"%login, Writer's soul"],xp_progress={'total_xp':12000,'level_start_xp':10000,'next_level_xp':20000})
                return data
        with TemporaryDirectory() as directory:
            factory=make_session_factory(f'sqlite:///{Path(directory)/"seat.sqlite"}')
            with factory() as session:save_settings(session,{'onboarding_completed':'true','default_cursus_id':'21'})
            app=FortyTwoTuiApp(factory,None)
            try:
                async with app.run_test(size=(160,50)) as pilot:
                    app.provider=Provider();app.account_connected=True;app.account_id='99';app.account_login='you'
                    app.query_one(TabbedContent).active='cluster-map'
                    ws=app.query_one(ClusterMapWorkspace)
                    await ws.reload();await pilot.pause()
                    ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
                    modal=app.screen
                    await modal._load_person();await pilot.pause()
                    self.assertFalse(modal.query('#cluster-modal-summary'))
                    self.assertIn('Alex Example',str(modal.query_one('#cluster-person-info',Static).render()))
                    user=str(modal.query_one('#cluster-person-user',Static).render())
                    for text in ('abcdefgh','September 2026','Analysts'):self.assertIn(text,user)
                    school=str(modal.query_one('#cluster-person-school',Static).render())
                    for text in ('Balance: 0','Evaluation points: 0','Achievements: 9'):self.assertIn(text,school)
                    self.assertIn('Mastermind abcdefgh',str(modal.query_one('#cluster-person-titles',Static).render()))
                    self.assertIn("abcdefgh, Writer's soul",str(modal.query_one('#cluster-person-titles',Static).render()))
                    self.assertIn('2,000 / 10,000 XP',str(modal.query_one('#cluster-person-xp',Static).render()))
                    self.assertIn('Level: 8.42',str(modal.query_one('#cluster-person-cursus',Static).render()))
                    self.assertAlmostEqual(modal.query_one('#cluster-level-progress').progress,2000)
                    self.assertEqual(modal.query_one('#cluster-level-progress').total,10000)
                    cards=list(modal.query('#cluster-person-cards > .cluster-detail-card'))
                    self.assertEqual(len({card.region.height for card in cards}),1)
                    self.assertGreater(cards[0].region.height,3)
                    self.assertLessEqual(modal.query_one('#cluster-titles-card').region.y-max(card.region.bottom for card in cards),1)
                    for width in (160,80,60):
                        await pilot.resize_terminal(width,50);await pilot.pause()
                        details=modal.query_one('#cluster-person-details')
                        for card in modal.query('#cluster-person-cards > .cluster-detail-card'):
                            self.assertLessEqual(card.region.right,details.content_region.right)
                    await pilot.resize_terminal(160,50);await pilot.pause()
                    # A later occupant must never become the target of this person's button.
                    modal.update_seat(SeatState('1A1',login='someone-else'))
                    modal.query_one('#cluster-add-friend',Button).scroll_visible(animate=False)
                    await pilot.pause()
                    self.assertTrue(await pilot.click('#cluster-add-friend'))
                    await pilot.pause()
                    await modal.workers.wait_for_complete();await pilot.pause()
                    with factory() as session:
                        watches=memberships(session,'99')
                        self.assertEqual(watches,[])
                        self.assertEqual(memberships(session,'100'),[])
                    self.assertEqual(app.provider.social_calls[-1],{'action':'request','login':'abcdefgh','user_id':'42'})
                    self.assertFalse(modal.query_one('#cluster-friend-details',Button).display)
                    self.assertTrue(modal.query_one('#cluster-add-friend',Button).display)
                    self.assertIs(app.screen,modal)
            finally:factory.kw['bind'].dispose()

    async def test_repeated_close_only_dismisses_the_workstation_once(self):
        app=MapHarness()
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            grid=ws.query_one(ClusterMapGrid);grid.select_host('1A1')
            ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
            modal=app.screen
            modal.action_close();modal.action_close()
            await pilot.pause()
            self.assertIsNone(ws.modal)
            self.assertIs(app.focused,ws.query_one(ClusterMapGrid))
            self.assertIsNone(grid.selected_host)
            modal.action_close()

    async def test_account_change_closes_covered_workstation_without_popping_the_overlay(self):
        from ft_tui.ui.modal import AppModal
        app=MapHarness()
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
            modal=app.screen;overlay=AppModal()
            await app.push_screen(overlay);await pilot.pause()
            app.account_generation+=1
            await ws.reload();await pilot.pause()
            self.assertIs(app.screen,overlay)
            self.assertFalse(modal._valid())
            overlay.dismiss();await pilot.pause();await pilot.pause()
            self.assertNotIn(modal,app.screen_stack)
            self.assertIsNone(ws.modal)
            modal.action_close()

    async def test_person_reference_layout_has_large_portrait_beside_grouped_details(self):
        from ft_tui.features.cluster_map.views.portrait import ClusterPortrait
        from ft_tui.ui.components import Static
        app=MapHarness()
        async with app.run_test(size=(160,50)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
            modal=app.screen;portrait=modal.query_one(ClusterPortrait)
            details=modal.query_one('#cluster-person-details')
            self.assertGreater(portrait.size.width,30)
            self.assertGreater(portrait.size.height,15)
            self.assertLessEqual(portrait.region.right,details.region.x)
            self.assertIn('1A1',str(modal.query_one('#cluster-person-host',Static).render()))
            for width,height in ((80,24),(60,24)):
                await pilot.resize_terminal(width,height);await pilot.pause()
                dialog=modal.query_one('#cluster-dialog')
                self.assertLessEqual(dialog.region.right,width)
                self.assertLessEqual(dialog.region.bottom,height)

    async def test_host_details_and_cached_portrait_render_without_waiting_for_refresh(self):
        from PIL import Image
        from ft_tui.features.cluster_map.views.portrait import ClusterPortrait
        from ft_tui.ui.components import Static
        app=MapHarness()
        async with app.run_test(size=(80,24)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            seat=SeatState('1A1',login='abcdefgh',person={'login':'abcdefgh','image_url':'https://cdn.intra.42.fr/cached.jpg'})
            image=Image.new('RGB',(8,12),'red');ws.cache.images[seat.person['image_url']]=image
            modal=ClusterWorkstationModal(ws,'1A1',seat,'person',ws._scope())
            app.push_screen(modal);await pilot.pause()
            self.assertIn('1A1',str(modal.query_one('#cluster-person-host',Static).render()))
            self.assertIs(modal.query_one(ClusterPortrait).image,image)

    async def test_refresh_preserves_loaded_later_pages_and_expanded_reports(self):
        class P:
            def get_cluster_map(self):return MapHarness.provider.get_cluster_map()
            def get_cluster_issues(self,host,*,include_resolved=False,cursor=None):
                number=2 if cursor else 1
                return {'hostname':host,'include_resolved':include_resolved,'next_cursor':'2' if number==1 else None,
                    'items':[{'id':str(number),'title':f'Report {number}','category':'Hardware','component':'Keyboard','status':'open','description':'\n'.join(['Key sticks']*40),'history':[]}],
                    'meta':{'stale':False}}
        app=MapHarness();app.provider=P()
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            ws.open_seat(ClusterMapGrid.SeatSelected('1A1',True));await pilot.pause()
            modal=app.screen
            await modal._load_issues('2');await pilot.pause()
            later=list(modal.query(Collapsible))[-1];later.collapsed=False;later_id=later.id
            await pilot.pause()
            scroll=modal.query_one('#cluster-workstation-scroll',VerticalScroll)
            scroll.scroll_to(y=20,animate=False);await pilot.pause()
            self.assertEqual(scroll.scroll_y,20)
            await modal._load_issues();await pilot.pause()
            self.assertEqual(len(modal.query(Collapsible)),2)
            self.assertFalse(modal.query_one('#'+later_id,Collapsible).collapsed)
            self.assertIn('Keyboard',str(modal.query_one('#'+later_id,Collapsible).title))
            self.assertEqual(scroll.scroll_y,20)

    async def test_occupant_change_preserves_person_and_active_tab_until_explicit_action(self):
        app=MapHarness()
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            ws.query_one(ClusterMapGrid).select_host('1A1')
            ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
            modal=app.screen
            self.assertIsInstance(modal,ClusterWorkstationModal)
            tabs=modal.query_one('#cluster-modal-tabs',TabbedContent)
            self.assertEqual(tabs.active,'cluster-person')
            tabs.active='cluster-workstation';await pilot.pause()
            modal.update_seat(SeatState('1A1',machine='online',session='no active session'))
            self.assertEqual(modal.person_seat.login,'abcdefgh')
            self.assertTrue(modal.query_one('#cluster-occupant-notice').display)
            self.assertEqual(tabs.active,'cluster-workstation')
            await pilot.pause()
            await pilot.click('#cluster-latest');await pilot.pause()
            self.assertIsNone(modal.person_seat.login)
            self.assertEqual(tabs.active,'cluster-workstation')

    async def test_issues_disclosure_resolved_toggle_and_unavailable_are_distinct(self):
        from ft_tui.ui.components import Static
        class P:
            fail=False
            def get_cluster_map(self):return MapHarness.provider.get_cluster_map()
            def get_cluster_issues(self,host,*,include_resolved=False,cursor=None):
                if self.fail:raise RuntimeError('offline')
                return {'hostname':host,'include_resolved':include_resolved,'next_cursor':None,'items':[
                    {'id':'a','title':'Keyboard','status':'open','description':'Shift key sticks','updated_at':'Today','history':[]}
                ]+([{'id':'b','title':'Mouse','status':'resolved','description':'Replaced','history':[]}] if include_resolved else []),'meta':{'stale':False}}
        app=MapHarness();app.provider=P()
        async with app.run_test(size=(120,40)) as pilot:
            ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
            ws.open_seat(ClusterMapGrid.SeatSelected('1A1',True));await pilot.pause()
            modal=app.screen
            self.assertEqual(modal.query_one('#cluster-modal-tabs',TabbedContent).active,'cluster-workstation')
            await pilot.pause()
            self.assertEqual(len(modal.query(Collapsible)),1)
            await pilot.click('#cluster-resolved');await pilot.pause();await pilot.pause()
            self.assertEqual(len(modal.query(Collapsible)),2)
            self.assertEqual(str(modal.query_one('#cluster-count-open',Static).render()),'1')
            self.assertEqual(str(modal.query_one('#cluster-count-resolved',Static).render()),'1')
            for width in (80,60):
                await pilot.resize_terminal(width,30);await pilot.pause()
                scroll=modal.query_one('#cluster-workstation-scroll')
                for card in modal.query('.cluster-report-card'):
                    self.assertLessEqual(card.region.right,scroll.content_region.right)
                button=modal.query_one('#cluster-resolved')
                button.scroll_visible(animate=False);await pilot.pause()
                self.assertTrue(button.visible)
            app.provider.fail=True
            await pilot.click('#cluster-resolved');await pilot.pause();await pilot.pause()
            self.assertEqual(len(modal.query(Collapsible)),0)
            self.assertFalse(modal.query_one('#cluster-issue-counts').display)

    async def test_lock_duration_ticks_in_hover_and_person_and_clears_on_unlock(self):
        from datetime import datetime, timezone
        from dataclasses import replace
        from unittest.mock import patch
        from ft_tui.ui.components import Static
        from ft_tui.features.cluster_map.state import session_label
        now=datetime(2026,10,23,10,2,3,tzinfo=timezone.utc)
        def label(seat,t):return session_label(seat,t,now)
        app=MapHarness()
        with patch('ft_tui.features.cluster_map.views.cluster_seat_preview.session_label',side_effect=label),patch('ft_tui.features.cluster_map.views.cluster_workstation.session_label',side_effect=label):
            async with app.run_test(size=(160,50)) as pilot:
                ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
                grid=ws.query_one(ClusterMapGrid)
                seat=replace(grid.states['1A1'],lock_time='00:02:03',lock_observed_at='2026-10-23T10:02:03Z')
                grid.states['1A1']=seat
                grid._hover_host='1A1';grid._show_preview();await pilot.pause()
                preview=grid._preview.query_one('.cluster-preview-details',Static)
                self.assertIn('Locked for 2m 03s',str(preview.render()))
                self.assertIn('Online · Locked',str(preview.render()))
                modal=ClusterWorkstationModal(ws,'1A1',seat,'person',ws._scope())
                app.push_screen(modal);await pilot.pause()
                info=modal.query_one('#cluster-person-info',Static)
                self.assertIn('Locked for 2m 03s',str(info.render()))
                for second in (4,5,6):
                    now=datetime(2026,10,23,10,2,second,tzinfo=timezone.utc)
                    await pilot.pause(1.1)
                    self.assertIn(f'Locked for 2m {second:02d}s',str(info.render()))
                    self.assertIn(f'Locked for 2m {second:02d}s',str(preview.render()))
                unlocked=replace(seat,session='signed in',lock_time=None)
                modal.update_seat(unlocked)
                app.pop_screen();await pilot.pause()
                grid.set_state(grid.view,{**grid.states,'1A1':unlocked},grid.highlighted)
                self.assertTrue(grid._preview.display)
                self.assertNotIn('Locked for',str(info.render()))
                self.assertNotIn('Locked for',str(preview.render()))
                self.assertIn('Signed in',str(info.render()))
                self.assertIn('Online · Signed in',str(preview.render()))
