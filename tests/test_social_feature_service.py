"""Social reads and single-shot mutations preserve context and confirmed consent."""
import unittest
from types import SimpleNamespace
from ft_tui.features.social.service import SocialService


def snapshot(account='1'):
    return {'account_id':account,'dnd':False,'friends':[{'account_id':'2','login':'bob'}],
            'incoming':[],'outgoing':[],'pokes':[]}


class Repository:
    def __init__(self):self.confirmed=[]
    def cache_confirmed(self,account,friends,*,origin=''):
        self.confirmed.append((account,friends,origin))


class SocialFeatureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo=Repository();self.service=SocialService(self.repo)

    async def test_snapshot_persists_only_server_confirmed_relationships(self):
        data=snapshot();provider=SimpleNamespace(get_social=lambda:data)
        value=await self.service.snapshot(provider,'1',lambda:True,origin='https://one.test')
        self.assertIs(value,data)
        self.assertEqual(self.repo.confirmed,[('1',data['friends'],'https://one.test')])

    async def test_wrong_account_or_obsolete_result_cannot_persist(self):
        self.assertIsNone(await self.service.snapshot(SimpleNamespace(get_social=lambda:snapshot('3')),'1',lambda:True))
        active=[True]
        def fetch():active[0]=False;return snapshot()
        self.assertIsNone(await self.service.snapshot(SimpleNamespace(get_social=fetch),'1',lambda:active[0]))
        self.assertEqual(self.repo.confirmed,[])

    async def test_initially_obsolete_context_never_dispatches(self):
        def unexpected(*args):raise AssertionError('dispatched after invalidation')
        provider=SimpleNamespace(get_social=unexpected,social_action=unexpected,get_poke_neighbours=unexpected)
        self.assertIsNone(await self.service.snapshot(provider,'1',lambda:False))
        self.assertIsNone(await self.service.mutate(provider,{'action':'accept'},lambda:False))
        self.assertIsNone(await self.service.neighbours(provider,lambda:False))

    async def test_pending_request_does_not_infer_a_mutual_friend(self):
        data=snapshot();data['friends']=[]
        data['outgoing']=[{'id':'1:2','members':[{'account_id':'1','login':'alice'},{'account_id':'2','login':'bob'}],
                           'requested_by':'1','status':'pending','created_at':'2026-10-27T12:00:00Z'}]
        await self.service.snapshot(SimpleNamespace(get_social=lambda:data),'1',lambda:True)
        self.assertEqual(self.repo.confirmed,[('1',[],'')])

    async def test_poke_dispatch_preserves_exact_id_and_explicit_authors_once(self):
        calls=[];draft={'action':'poke','id':'stable-id','recipient_id':'2','sender_ids':['3'],'message':'Lunch?'}
        def send(value):calls.append(value);return {'status':'pending'}
        self.assertEqual(await self.service.mutate(SimpleNamespace(social_action=send),draft,lambda:True),{'status':'pending'})
        self.assertEqual(calls,[draft]);self.assertIs(calls[0],draft)

    async def test_uncertain_mutation_is_not_retried_and_context_change_discards_outcome(self):
        calls=[]
        def fail(value):calls.append(value);raise RuntimeError('response lost')
        with self.assertRaises(RuntimeError):
            await self.service.mutate(SimpleNamespace(social_action=fail),{'action':'approve','id':'same'},lambda:True)
        self.assertEqual(len(calls),1)
        active=[True]
        def send(value):active[0]=False;return {'status':'sent'}
        self.assertIsNone(await self.service.mutate(SimpleNamespace(social_action=send),{'action':'dismiss','id':'same'},lambda:active[0]))

    async def test_neighbours_and_portrait_reads_preserve_identity_and_optional_capabilities(self):
        self.assertIsNone(await self.service.neighbours(None,lambda:True))
        self.assertIsNone(await self.service.sender_profile(None,'2',lambda:True))
        data={'user_id':'2','image_url':None}
        provider=SimpleNamespace(get_poke_neighbours=lambda:[{'account_id':'2','login':'bob'}],get_student_profile=lambda user:data)
        self.assertEqual(await self.service.neighbours(provider,lambda:True),[{'account_id':'2','login':'bob'}])
        self.assertIs(await self.service.sender_profile(provider,'2',lambda:True),data)
        self.assertIsNone(await self.service.sender_profile(provider,'3',lambda:True))

    def test_legacy_modules_keep_canonical_identity(self):
        from ft_tui.api import social_types
        from ft_tui.features.social import models
        from ft_tui.ui import social,poke_notification,push_events
        from ft_tui.features.social.views import inbox,pokes,events
        self.assertIs(social_types,models)
        self.assertIs(social,inbox);self.assertIs(poke_notification,pokes);self.assertIs(push_events,events)
