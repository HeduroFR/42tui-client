"""A reader can find a friend, inspect reports, and survive a live seat change."""
import unittest
from tempfile import TemporaryDirectory
from textual.widgets import Input,TabbedContent
from test_ui_cluster_map import MapHarness,Provider
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import FriendWatch
from ft_tui.ui.cluster_map import ClusterMapWorkspace
from ft_tui.ui.cluster_map_grid import ClusterMapGrid


class JourneyTests(unittest.IsolatedAsyncioTestCase):
    async def test_find_friend_switch_cluster_read_report_and_preserve_focus_after_change(self):
        class P(Provider):
            login='friend42'
            def get_cluster_map(self):
                data=super().get_cluster_map()
                data['machines'].append({'hostname':'2a1.42angouleme.fr','status':'up','login':self.login,'is_locked':bool(self.login),
                    'person':{'login':self.login,'user_id':'99','display_name':'Campus Friend','image_url':None} if self.login else None,
                    'issues':{'availability':'available','open_count':1}})
                return data
            def get_friend(self,*args,**kwargs):return {'user_id':'99','level':4.2,'grade':'Cadet','items':[],'meta':{'stale':False}}
            def get_cluster_issues(self,host,**kwargs):return {'hostname':host,'include_resolved':False,'next_cursor':None,
                'items':[{'id':'1','hostname':host,'title':'Keyboard','category':'Hardware','component':'Keyboard','description':'Shift key sticks','status':'open','history':[]}],
                'meta':{'stale':False}}
        class A(MapHarness):
            def _configured_cursus_id(self,session):return 21
        with TemporaryDirectory() as directory:
            factory=make_session_factory('sqlite:///'+directory+'/journey.sqlite')
            try:
                with factory() as session:
                    from ft_tui.services.friends import cache_mutual_friends
                    cache_mutual_friends(session, '1', [{'account_id': '99', 'login': 'friend42'}])
                app=A();app.provider=P();app.session_factory=factory
                async with app.run_test(size=(120,40)) as pilot:
                    workspace=app.query_one(ClusterMapWorkspace);await workspace.reload();await pilot.pause()
                    grid=app.query_one(ClusterMapGrid);before=grid.seat_regions()
                    await pilot.click('#cluster-friends');await pilot.pause()
                    self.assertEqual(grid.highlighted,frozenset({'2A1'}))
                    search=app.query_one('#cluster-search',Input);search.focus()
                    await pilot.press(*'friend42','enter');await pilot.pause()
                    self.assertEqual(grid.selected_host,'2A1');self.assertEqual(grid.seat_regions(),before)
                    await pilot.click('#cluster-view-c2');await pilot.pause()
                    await pilot.resize_terminal(80,24);await pilot.pause()
                    self.assertEqual(len(grid.seat_regions()),49)
                    self.assertIsNone(grid.selected_host)
                    grid.focus();await pilot.press('right','enter');await pilot.pause()
                    modal=app.screen;modal.query_one('#cluster-modal-tabs',TabbedContent).active='cluster-workstation';await pilot.pause()
                    self.assertEqual(modal.items[0]['description'],'Shift key sticks')
                    app.provider.login=None;await workspace.reload();await pilot.pause()
                    self.assertEqual(modal.person_seat.login,'friend42')
                    self.assertTrue(modal.query_one('#cluster-occupant-notice').display)
                    await pilot.click('#cluster-latest');await pilot.pause()
                    self.assertIsNone(modal.person_seat.login)
                    self.assertEqual(modal.query_one('#cluster-modal-tabs',TabbedContent).active,'cluster-workstation')
                    await pilot.press('escape');await pilot.pause()
                    self.assertIs(app.focused,grid);self.assertIsNone(grid.selected_host)
            finally:factory.kw['bind'].dispose()
