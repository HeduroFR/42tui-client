"""Friend reads validate identity before eligible account-scoped persistence."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import httpx
from tests.friends_fixtures import snapshot
from ft_tui.features.friends.service import FriendsService
from ft_tui.features.friends.adapters.http import ProviderFriendsReader

class Repository:
    def __init__(self): self.saved=[]
    def save(self,account,value,*,origin=''):self.saved.append((account,value,origin))

class FriendsFeatureServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_summary_fallback_is_only_for_legacy_summary_endpoint_errors(self):
        calls=[]
        def summary(*args,**kwargs):
            calls.append('summary')
            raise httpx.HTTPStatusError('old endpoint',request=httpx.Request('GET','https://example.test'),response=httpx.Response(404))
        def core(*args,**kwargs):calls.append('core');return snapshot()
        provider=SimpleNamespace(get_friend_summary=summary,get_friend_core=core)
        service=FriendsService(Repository(),ProviderFriendsReader())
        self.assertEqual((await service.summary(provider,'alice',21))['user_id'],'50')
        self.assertEqual(calls,['summary','core'])
        def forbidden(*args,**kwargs):
            raise httpx.HTTPStatusError('forbidden',request=httpx.Request('GET','https://example.test'),response=httpx.Response(403))
        provider.get_friend_summary=forbidden
        calls.clear()
        with self.assertRaises(httpx.HTTPStatusError):await service.summary(provider,'alice',21)
        self.assertEqual(calls,[])

    async def test_expected_and_owner_identity_are_checked_before_snapshot_can_be_saved(self):
        repo=Repository();service=FriendsService(repo,ProviderFriendsReader())
        provider=SimpleNamespace(get_friend=lambda *args,**kwargs:snapshot())
        with self.assertRaises(ValueError):await service.summary(provider,'alice',21,expected_user_id='51')
        with self.assertRaisesRegex(ValueError,'Account identity mismatch'):
            await service.summary(provider,'alice',21,owner_login='alice',account_id='42')
        self.assertEqual(repo.saved,[])
        value=await service.summary(provider,'alice',21,expected_user_id='50')
        self.assertFalse(service.save('42',value,origin='https://one.test',current=lambda:False))
        self.assertEqual(repo.saved,[])
        self.assertTrue(service.save('42',value,origin='https://one.test'))
        self.assertEqual(repo.saved[0][0],'42')

    async def test_batch_and_search_keep_validation_without_ui_imports(self):
        service=FriendsService(Repository(),ProviderFriendsReader())
        provider=SimpleNamespace(get_friend_summaries=lambda *args:[snapshot('owner',user_id='99')])
        with self.assertRaisesRegex(ValueError,'Account identity mismatch'):
            await service.batch(provider,['owner'],21,owner_login='owner',account_id='42')
        provider.search_students=lambda *args,**kwargs:{'items':[],'index':{'updated_at':None,'status':'building','count':0,'stale':True}}
        self.assertEqual((await service.search(provider,'a',exclude_ids=('2',)))['items'],[])
