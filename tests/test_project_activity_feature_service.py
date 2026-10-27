"""Activity reads share scoped cache policy while fencing executor dispatch."""
import unittest
from unittest.mock import patch
from ft_tui.features.projects.activity.service import ActivityService,StaleActivityContext


class Cache:
    async def read(self,key,loader,*,refresh,current):
        self.key=key;self.refresh=refresh;self.current=current
        return await loader()


class ActivityFeatureTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_keys_preserve_cursus_campus_project_and_team(self):
        service=ActivityService()
        self.assertEqual(service.key(('account',),'21',31,1001),(('account',),'activity-history','21',31,1001,None))
        self.assertEqual(service.key(('account',),21,31,1001,8),(('account',),'activity-evaluations',21,31,1001,8))

    async def test_read_uses_original_loader_and_refresh_once(self):
        service=ActivityService();cache=Cache();calls=[]
        value=await service.read(cache,('scope',),lambda refresh:calls.append(refresh) or {'value':1},True,lambda:True)
        self.assertEqual(value,{'value':1});self.assertTrue(cache.refresh);self.assertEqual(calls,[True])

    async def test_stale_executor_never_dispatches_old_account_read(self):
        service=ActivityService();cache=Cache();active=True;calls=[]
        async def queue(operation,*args):
            nonlocal active
            active=False
            return operation(*args)
        with patch('ft_tui.features.projects.activity.service.asyncio.to_thread',side_effect=queue):
            with self.assertRaises(StaleActivityContext):
                await service.read(cache,('old',),lambda refresh:calls.append(refresh),False,lambda:active)
        self.assertEqual(calls,[])

    async def test_configured_cursus_matches_is_delegated_without_database(self):
        class Context:
            def cursus_matches(self,cursus):return cursus==21
        service=ActivityService(Context())
        self.assertTrue(service.cursus_matches(21));self.assertFalse(service.cursus_matches(9))
        self.assertTrue(ActivityService().cursus_matches(21))
