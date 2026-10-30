import threading
import unittest

from textual.app import App
from textual.widgets import Digits,Static
from ft_tui.features.catalog.models import CatalogScope
from ft_tui.ui.button import Button
from ft_tui.features.friends.views.project import FriendProjectPreview
from tests.activity_fixtures import history,evaluations
from tests.friends_fixtures import snapshot,attempt


class Provider:
    gate=None
    def __init__(self):self.calls=[];self.finished=False;self.state=('in_progress',None,None)
    def get_friend_project_activity(self,project_id,attempt_id,user_id,scope,account_id,**options):
        self.calls.append(('history',project_id,attempt_id,user_id,account_id))
        if self.gate:self.gate.wait(3)
        value=history();value.update(subject_user_id=user_id,attempt_id=attempt_id)
        for team in value['teams']:
            team['members']=[{'id':int(user_id),'login':'alice','leader':True}]
            team.update(status=self.state[0],validated=self.state[1],final_mark=self.state[2])
        return value
    def get_friend_project_evaluations(self,project_id,attempt_id,user_id,team_id,scope,account_id,**options):
        self.calls.append(('evaluations',project_id,attempt_id,user_id,team_id,account_id))
        value=evaluations(team_id);value.update(subject_user_id=user_id,attempt_id=attempt_id)
        if self.finished:
            value['peer']['items'][0].update(filled_at='2026-10-23T10:00:00Z',final_mark=0)
        return value
    def get_catalog_project(self,project_id,scope,snapshot_id):
        return {'project_id':project_id,'name':'minishell','slug':'minishell','kind':'project','section':'common-core',
                'description':'Build a small shell. [red]literal text','xp':0,'rank':3,'project_mode':'group','team_size':2}
    def get_project_activity(self,*args,**kwargs):raise AssertionError('Must not load the viewer\'s attempts')
    def get_team_evaluations(self,*args,**kwargs):raise AssertionError('Must not load the viewer\'s evaluations')


class Harness(App):
    language='en';account_id='42';account_generation=0;account_connected=True
    def compose(self):yield Button('Caller',id='caller')


async def settle(screen,pilot):
    for _ in range(40):
        await pilot.pause(.02)
        if not any(worker.is_running for worker in screen.workers):break


class FriendProjectTests(unittest.IsolatedAsyncioTestCase):
    async def test_restricted_evaluations_keep_unrelated_account_cache(self):
        import httpx
        from ft_tui.app.read_cache import app_cache, account_scope

        class Restricted(Provider):
            restricted = False

            def get_friend_project_evaluations(self, *args, **kwargs):
                if self.restricted:
                    request = httpx.Request('GET', 'https://example.test/evaluations')
                    raise httpx.HTTPStatusError('restricted', request=request,
                        response=httpx.Response(403, request=request))
                return super().get_friend_project_evaluations(*args, **kwargs)

        app = Harness()
        app.provider = Restricted()
        async with app.run_test(size=(100, 36)) as pilot:
            cache = app_cache(app)
            key = (account_scope(app), 'unrelated-friend-summary')
            async def allowed():
                return {'login': 'other-friend'}
            await cache.read(key, allowed)
            screen = FriendProjectPreview(snapshot(), attempt(), None, CatalogScope(21, 31),
                                          '42', app.provider, 0)
            await app.push_screen(screen)
            await settle(screen, pilot)
            self.assertIsNotNone(screen.evaluations)
            app.provider.restricted = True
            screen.action_refresh()
            await settle(screen, pilot)
            self.assertEqual(cache.peek(key), {'login': 'other-friend'})
            self.assertEqual(await cache.read((key[0], 'another-allowed-read'), allowed), {'login': 'other-friend'})
            self.assertFalse(screen.query_one('#activity-evaluations').display)
            self.assertIn('restricted', str(screen.query_one('#activity-status', Static).render()))
            self.assertTrue(app.account_connected)

    async def test_preview_adapts_to_pending_passed_and_failed_attempts_and_renders_evaluations(self):
        for status,validated,mark,expected,style in [('in_progress',None,None,'In progress','ongoing'),
                ('finished',True,125,'Validated','passed'),('finished',False,0,'Failed','failed')]:
            app=Harness();app.provider=Provider();app.provider.finished=status=='finished';app.provider.state=(status,validated,mark)
            async with app.run_test(size=(100,36)) as pilot:
                caller=app.screen
                item=attempt(id=72,status=status,validated=validated,mark=mark)
                screen=FriendProjectPreview(snapshot(items=[item]),item,None,CatalogScope(21,31),'42',app.provider,0)
                app.push_screen(screen);await settle(screen,pilot)
                summary=screen.query_one('#friend-project-attempt',Static)
                self.assertIn(expected,str(summary.render()));self.assertTrue(summary.has_class(style))
                caption=str(screen.query_one('#friend-project-mark-caption',Static).render())
                self.assertIn('0%' if mark==0 else '125%' if mark==125 else 'Result pending',caption)
                self.assertEqual(screen.query_one('#friend-project-mark',Digits).value,'-' if mark is None else str(mark))
                self.assertTrue(screen.query_one('#friend-project-score').has_class(style))
                self.assertEqual(screen.query_one('#friend-project-mark-scale').display,mark is not None)
                description = str(screen.query_one('#friend-project-description',Static).render())
                facts = str(screen.query_one('#friend-project-facts',Static).render())
                self.assertIn('Build a small shell. [red]literal text', description)
                self.assertIn('Rank: 3', facts)
                self.assertIn('Members: 2', facts)
                self.assertNotIn('Rank: 3', description)
                self.assertNotIn('Members: 2', description)
                self.assertTrue(screen.evaluations)
                self.assertIn('[red]literal',str(screen.query_one('#peer-comment-1',Static).render()))
                self.assertIn('test: KO',str(screen.query_one('#automated-output-2',Static).render()))
                labels=[str(widget.render()) for widget in screen.query('#activity-evaluations Static')]
                self.assertNotIn('Your feedback',labels)
                self.assertIn('Feedback',labels)
                self.assertEqual('Scheduled & pending evaluations' in labels,status!='finished')
                self.assertIn(('history',1001,72,'50','42'),app.provider.calls)
                self.assertTrue(any(call[0]=='evaluations' and call[3]=='50' for call in app.provider.calls))
                self.assertLessEqual(screen.query_one('#activity-close').region.bottom,36)
                await pilot.press('escape');await pilot.pause();self.assertIs(app.screen,caller)

    async def test_preview_is_centered_with_visible_background_at_each_size(self):
        app=Harness();app.provider=Provider()
        async with app.run_test(size=(180,60)) as pilot:
            item=attempt(id=72)
            screen=FriendProjectPreview(snapshot(),item,None,CatalogScope(21,31),'42',app.provider,0)
            app.push_screen(screen);await settle(screen,pilot)
            for width,height in ((180,60),(100,36),(80,30)):
                await pilot.resize_terminal(width,height);await pilot.pause()
                dialog=screen.query_one('#friend-project-dialog').region
                self.assertGreaterEqual(dialog.x,2);self.assertGreaterEqual(dialog.y,1)
                self.assertGreaterEqual(width-dialog.right,2);self.assertGreaterEqual(height-dialog.bottom,1)
                self.assertLessEqual(abs(dialog.x-(width-dialog.right)),1)
                self.assertLessEqual(abs(dialog.y-(height-dialog.bottom)),1)
                self.assertLessEqual(dialog.width,132)
                self.assertGreater(screen.query_one('#activity-detail').region.height,0)
                self.assertLessEqual(screen.query_one('#activity-close').region.bottom,dialog.bottom)

    async def test_close_and_account_change_prevent_late_evaluations_from_publishing(self):
        app=Harness();app.provider=Provider();app.provider.gate=threading.Event()
        async with app.run_test(size=(80,30)) as pilot:
            item=attempt(id=72)
            screen=FriendProjectPreview(snapshot(),item,None,CatalogScope(21,31),'42',app.provider,0)
            app.push_screen(screen);await pilot.pause(.03)
            app.account_generation+=1;screen._check_identity()
            app.provider.gate.set();await pilot.pause()
            self.assertFalse(screen.history)
            self.assertEqual(str(screen.query_one('#friend-project-attempt',Static).render()),'')
            self.assertTrue(screen.query_one('#activity-refresh',Button).disabled)
            screen.action_close();await pilot.pause()

