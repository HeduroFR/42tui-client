"""Cluster operations remain headless and fence every independent request."""
import unittest
from types import SimpleNamespace
from ft_tui.features.cluster_map.service import ClusterService


class ClusterServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_read_or_write_when_context_is_obsolete(self):
        service=ClusterService(None)
        provider=SimpleNamespace(get_cluster_map=lambda: self.fail('obsolete read'),
                                 submit_cluster_issue=lambda *args:self.fail('obsolete write'))
        self.assertIsNone(await service.map(provider,lambda:False))
        self.assertIsNone(await service.submit(provider,'C1R1P1',{},'same-uuid',lambda:False))

    async def test_reject_result_when_context_changes_during_request(self):
        active=True
        def fetch():
            nonlocal active
            active=False
            return {'machines':[]}
        self.assertIsNone(await ClusterService(None).map(SimpleNamespace(get_cluster_map=fetch),lambda:active))

    async def test_main_cursus_read_pins_person_identity(self):
        calls=[]
        def get_friend(login,cursus,**options):
            calls.append((login,cursus,options))
            return {'user_id':'42','cursus_id':cursus,'main_cursus_id':21}
        data=await ClusterService(None).person(SimpleNamespace(get_friend=get_friend),'alice',9,'42',lambda:True)
        self.assertEqual(data['cursus_id'],21)
        self.assertEqual(calls,[('alice',9,{'user_id':'42'}),('alice',21,{'user_id':'42'})])

    async def test_identity_change_never_requests_second_profile(self):
        calls=[]
        def get_friend(*args,**kwargs):
            calls.append(args)
            return {'user_id':'other','main_cursus_id':21}
        with self.assertRaises(ValueError):
            await ClusterService(None).person(SimpleNamespace(get_friend=get_friend),'alice',9,'42',lambda:True)
        self.assertEqual(len(calls),1)

    async def test_uncertain_write_is_attempted_once_with_original_uuid(self):
        calls=[];draft={'description':'test'}
        def submit(host,payload,key):
            calls.append((host,payload,key))
            raise TimeoutError()
        with self.assertRaises(TimeoutError):
            await ClusterService(None).submit(SimpleNamespace(submit_cluster_issue=submit),'host',draft,'original',lambda:True)
        self.assertEqual(calls,[('host',draft,'original')])

    async def test_no_fallback_read_after_account_switch(self):
        active=True;calls=[]
        def get_friend(*args,**kwargs):
            nonlocal active
            calls.append(args);active=False
            return {'user_id':'42','main_cursus_id':21}
        result=await ClusterService(None).person(SimpleNamespace(get_friend=get_friend),'alice',9,'42',lambda:active)
        self.assertIsNone(result);self.assertEqual(len(calls),1)

    async def test_all_read_ports_delegate_without_changing_arguments(self):
        calls=[]
        def read(*args,**kwargs):calls.append((args,kwargs));return {'value':True}
        provider=SimpleNamespace(get_cluster_portrait=read,get_cluster_issue_options=read,get_cluster_issues=read)
        service=ClusterService(None)
        self.assertEqual(await service.portrait(provider,'host',lambda:True),{'value':True})
        await service.options(provider,lambda:True)
        await service.issues(provider,'host',lambda:True,include_resolved=True,cursor='next')
        self.assertEqual(calls,[(('host',),{}),((),{}),(('host',),{'include_resolved':True,'cursor':'next'})])

    async def test_unknown_submission_outcome_is_rejected(self):
        with self.assertRaises(ValueError):
            await ClusterService(None).submit(SimpleNamespace(submit_cluster_issue=lambda *args:{'hostname':'other','status':'submitted'}),'host',{},'uuid',lambda:True)

    async def test_executor_rechecks_context_before_queued_write(self):
        from unittest.mock import patch
        active=True;calls=[]
        async def queued(operation,*args,**kwargs):
            nonlocal active
            active=False
            return operation(*args,**kwargs)
        provider=SimpleNamespace(submit_cluster_issue=lambda *args:calls.append(args))
        with patch('ft_tui.features.cluster_map.service.asyncio.to_thread',side_effect=queued):
            self.assertIsNone(await ClusterService(None).submit(provider,'host',{},'original',lambda:active))
        self.assertEqual(calls,[])
