import threading
import unittest
from unittest.mock import patch

from textual.widgets import TextArea
from ft_tui.features.cluster_map.views.cluster_issue import ClusterIssueModal, IssueChoiceButton
from ft_tui.ui.components import Button,Static
from ft_tui.features.cluster_map.views.cluster_map import ClusterMapWorkspace
from ft_tui.features.cluster_map.views.cluster_map_grid import ClusterMapGrid
from test_ui_cluster_map import MapHarness


class Provider:
    can_submit=True
    failure=False
    gate=None
    def __init__(self):self.calls=[]
    def get_cluster_map(self):return MapHarness.provider.get_cluster_map()
    def get_cluster_issues(self,host,**options):
        return {'items':[{'id':'known','hostname':host,'title':'Known keyboard report','description':'A sticking key',
            'status':'open','category':'Hardware','component':'Keyboard'}],'next_cursor':None,'meta':{'stale':False}}
    def get_cluster_issue_options(self):
        return {'options':{'General':{'General':['No power','System frozen']},'Hardware':{'Mouse':['Missing','Other'],'Keyboard':['Missing','Broken keys']},'Other':{'Other':['Other']}},
            'max_description_length':2000,'reporter_login':'student','can_submit':self.can_submit}
    def submit_cluster_issue(self,host,draft,key):
        self.calls.append((host,draft,key))
        if self.gate:self.gate.wait(5)
        if self.failure:raise RuntimeError('lost response')
        return {'hostname':host,'status':'submitted'}


class IssueUiTests(unittest.IsolatedAsyncioTestCase):
    async def open_composer(self,app,pilot):
        ws=app.query_one(ClusterMapWorkspace);await ws.reload();await pilot.pause()
        ws.open_seat(ClusterMapGrid.SeatSelected('1A1'));await pilot.pause()
        await ws.modal._compose_issue();await pilot.pause()
        modal=app.screen
        self.assertIsInstance(modal,ClusterIssueModal)
        await modal.workers.wait_for_complete();await pilot.pause()
        return ws,modal

    async def choose(self,modal,pilot,group,value):
        button=next(b for b in modal.query(IssueChoiceButton) if b.group==group and b.value==value)
        # Focus the current choice before scrolling: focus left in a replaced
        # grid can otherwise scroll the form again between layout and the click.
        button.focus()
        await pilot.pause()
        button.scroll_visible(immediate=True,animate=False)
        await pilot.pause()
        self.assertTrue(await pilot.click(button))
        await pilot.pause()
        self.assertTrue(button.has_class('selected'))

    async def fill(self,modal,pilot):
        await self.choose(modal,pilot,'category','Hardware')
        await self.choose(modal,pilot,'component','Mouse')
        await self.choose(modal,pilot,'problem','Missing')
        modal.query_one(TextArea).text='No mouse at the seat. Checked the desk and USB ports.'
        await pilot.pause()

    async def test_review_dependent_options_description_limits_and_single_submission(self):
        app=MapHarness();app.provider=Provider()
        async with app.run_test(size=(100,40)) as pilot:
            ws,modal=await self.open_composer(app,pilot)
            self.assertIn('Known keyboard report',str(modal.query_one('#issue-existing',Static).render()))
            self.assertTrue(modal.query_one('#issue-review',Button).disabled)
            await self.fill(modal,pilot)
            self.assertFalse(modal.query_one('#issue-review',Button).disabled)
            await self.choose(modal,pilot,'component','Keyboard')
            self.assertIsNone(modal.selection['problem'])
            self.assertIn('No mouse',modal.query_one(TextArea).text)
            await self.choose(modal,pilot,'category','Other')
            self.assertEqual(modal._draft()['problem'],'Other')
            modal.query_one(TextArea).text='😀'*1001;await pilot.pause()
            self.assertTrue(modal.query_one('#issue-review',Button).disabled)
            self.assertIn('2002 / 2000',str(modal.query_one('#issue-length',Static).render()))
            await self.fill(modal,pilot)
            modal.query_one('#issue-review').scroll_visible(immediate=True);await pilot.pause();await pilot.click('#issue-review');await pilot.pause()
            self.assertIn('1A1 - Hardware - Mouse - Missing',str(modal.query_one('#issue-preview',Static).render()))
            self.assertTrue(modal.reviewed)
            modal.query_one(TextArea).text+=' Extra detail';await pilot.pause()
            self.assertFalse(modal.reviewed)
            modal.query_one('#issue-review').scroll_visible(immediate=True);await pilot.pause();await pilot.click('#issue-review');await pilot.pause()
            app.provider.gate=threading.Event()
            await pilot.click('#issue-submit');await pilot.pause()
            self.assertTrue(modal.busy)
            await modal.pressed(Button.Pressed(modal.query_one('#issue-submit',Button)))
            self.assertEqual(len(app.provider.calls),1)
            app.provider.gate.set();await modal.workers.wait_for_complete();await pilot.pause()
            self.assertIs(app.screen,ws.modal)
            self.assertEqual(app.provider.calls[0][0],'1A1')

    async def test_unknown_outcome_locks_draft_and_account_change_closes_overlay(self):
        app=MapHarness();app.provider=Provider();app.provider.failure=True
        async with app.run_test(size=(70,28)) as pilot:
            ws,modal=await self.open_composer(app,pilot);await self.fill(modal,pilot)
            modal.query_one('#issue-review').scroll_visible(immediate=True);await pilot.pause();await pilot.click('#issue-review');await pilot.pause()
            await pilot.click('#issue-submit');await modal.workers.wait_for_complete();await pilot.pause()
            self.assertIn('outcome unknown',str(modal.query_one('#issue-status',Static).render()))
            self.assertTrue(modal.query_one('#issue-submit',Button).disabled)
            self.assertTrue(modal.query_one(TextArea).read_only)
            self.assertEqual(len(app.provider.calls),1)
            app.account_generation+=1;modal._check_context();await pilot.pause()
            self.assertNotIsInstance(app.screen,ClusterIssueModal)

    async def test_mismatched_account_keeps_browser_fallback_and_never_writes(self):
        app=MapHarness();app.provider=Provider();app.provider.can_submit=False
        async with app.run_test(size=(60,24)) as pilot:
            _,modal=await self.open_composer(app,pilot);await self.fill(modal,pilot)
            self.assertTrue(modal.query_one('#issue-review',Button).disabled)
            self.assertIn('unavailable for this account',str(modal.query_one('#issue-status',Static).render()))
            with patch('ft_tui.features.cluster_map.views.cluster_issue.webbrowser.open') as browser:
                await pilot.click('#issue-browser');browser.assert_called_once_with('https://cluster-map.42angouleme.fr/')
            self.assertFalse(app.provider.calls)

    async def test_choice_buttons_support_keyboard_and_wrap_long_labels_on_narrow_screens(self):
        app=MapHarness();app.provider=Provider()
        async with app.run_test(size=(60,24)) as pilot:
            _,modal=await self.open_composer(app,pilot)
            modal.options['Network']={'Access & Permissions':['Auth works, access blocked','Other']}
            await modal._render_choices('category')
            category=next(b for b in modal.query(IssueChoiceButton) if b.value=='Network')
            category.focus();category.scroll_visible(immediate=True);await pilot.pause()
            await pilot.press('enter');await pilot.pause()
            self.assertEqual(modal.selection['category'],'Network')
            await self.choose(modal,pilot,'problem','Auth works, access blocked')
            selected=[b for b in modal.query(IssueChoiceButton) if b.has_class('selected')]
            self.assertEqual(len(selected),3)
            self.assertEqual({b.group for b in selected},{'category','component','problem'})
            for button in selected:
                self.assertTrue(all(edge[0] == 'solid' for edge in button.styles.border))
            for button in modal.query(IssueChoiceButton):
                self.assertGreater(button.size.width,0)
                self.assertGreaterEqual(button.region.x,button.parent.region.x)
                self.assertLessEqual(button.region.right,button.parent.region.right)
