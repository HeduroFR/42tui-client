import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ft_tui.features.profiles.student_service import StudentProfileService
from tests.test_user_profile import profile, attendance
from tests.friends_fixtures import snapshot


class StudentProfileServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_validate_stable_identity_and_preserve_arguments(self):
        service = StudentProfileService()
        provider = SimpleNamespace(get_student_profile=Mock(return_value=profile()),
                                   get_student_attendance=Mock(return_value=attendance()),
                                   get_friend=Mock(return_value=snapshot()))
        self.assertEqual((await service.profile(provider, '50', lambda: True, refresh=True))['user_id'], '50')
        provider.get_student_profile.assert_called_once_with('50', refresh=True)
        self.assertEqual((await service.attendance(provider, '50', lambda: True))['user_id'], '50')
        await service.projects(provider, 'alice', '50', 21, lambda: True, refresh=True)
        provider.get_friend.assert_called_once_with('alice', 21, refresh=True, user_id='50')
        provider.get_student_profile.return_value = {**profile(), 'user_id': '51'}
        with self.assertRaises(ValueError):
            await service.profile(provider, '50', lambda: True)
        with self.assertRaises(ValueError):
            await service.projects(provider, 'alice', '51', 21, lambda: True)

    async def test_projects_prefers_core_endpoint_and_discards_switched_cursus(self):
        active = True
        def fetch(*args, **kwargs):
            nonlocal active
            active = False
            return snapshot()
        provider = SimpleNamespace(get_friend_core=Mock(side_effect=fetch), get_friend=Mock())
        result = await StudentProfileService().projects(provider, 'alice', '50', 21, lambda: active)
        self.assertIsNone(result)
        provider.get_friend_core.assert_called_once_with('alice', 21, refresh=False, user_id='50')
        provider.get_friend.assert_not_called()

    async def test_search_requires_one_exact_login_and_valid_identity(self):
        provider = SimpleNamespace(search_students=Mock(return_value={'items': [{'login': 'alice', 'user_id': '50'}]}))
        service = StudentProfileService()
        self.assertEqual((await service.search(provider, 'alice', lambda: True))['user_id'], '50')
        provider.search_students.assert_called_once_with('alice', limit=20)
        for items in ([], [{'login': 'other', 'user_id': '50'}],
                      [{'login': 'alice', 'user_id': '50'}] * 2,
                      [{'login': 'alice', 'user_id': '0'}]):
            provider.search_students.return_value = {'items': items}
            with self.assertRaises(ValueError):
                await service.search(provider, 'alice', lambda: True)

    async def test_stale_read_is_not_dispatched_or_published(self):
        service = StudentProfileService()
        provider = SimpleNamespace(get_student_profile=Mock(return_value=profile()))
        self.assertIsNone(await service.profile(provider, '50', lambda: False))
        provider.get_student_profile.assert_not_called()
        active = True
        def fetch(*args, **kwargs):
            nonlocal active
            active = False
            return profile()
        provider.get_student_profile.side_effect = fetch
        self.assertIsNone(await service.profile(provider, '50', lambda: active))
        provider.get_student_profile.assert_called_once()

    async def test_queued_executor_rechecks_context_before_dispatch(self):
        service = StudentProfileService()
        provider = SimpleNamespace(get_student_profile=Mock(return_value=profile()))
        active = True
        async def delayed_dispatch(operation):
            nonlocal active
            active = False
            return operation()
        from unittest.mock import patch
        with patch('ft_tui.features.profiles.student_service.asyncio.to_thread', delayed_dispatch):
            self.assertIsNone(await service.profile(provider, '50', lambda: active))
        provider.get_student_profile.assert_not_called()

    async def test_goals_reject_wrong_cursus_and_do_not_retry_failure(self):
        value = {'user_id':'50','cursus_id':21,'status':'pending','stale':False,
                 'collected_at':None,'next_milestone':None,'cc_eta':None,
                 'cc_validated':False,'probationary_period':False,'edtrax_weeks':[]}
        provider = SimpleNamespace(get_student_goals=Mock(return_value=value))
        service = StudentProfileService()
        self.assertIs(await service.goals(provider, '50', 21, lambda: True), value)
        with self.assertRaises(ValueError):
            await service.goals(provider, '50', 9, lambda: True)
        provider.get_student_goals.reset_mock(side_effect=True)
        provider.get_student_goals.side_effect = RuntimeError('offline')
        with self.assertRaises(RuntimeError):
            await service.goals(provider, '50', 21, lambda: True)
        provider.get_student_goals.assert_called_once_with('50', 21)

    async def test_portrait_transport_uses_injected_loader_once_and_fences_result(self):
        loader = Mock(return_value={'image_url': 'https://cdn.intra.42.fr/a', 'status':'ready'})
        service = StudentProfileService()
        self.assertIsNone(await service.portrait('https://cdn.intra.42.fr/a', lambda: False, loader=loader))
        loader.assert_not_called()
        self.assertEqual((await service.portrait('https://cdn.intra.42.fr/a', lambda: True, loader=loader))['status'], 'ready')
        loader.assert_called_once_with('https://cdn.intra.42.fr/a')

    async def test_portrait_adapter_reuses_profile_projection(self):
        from ft_tui.features.profiles.adapters.portraits import latest_attempts
        from ft_tui.features.profiles.projections import latest_attempts as canonical
        self.assertIs(latest_attempts, canonical)


class StudentPortraitTransportTests(unittest.TestCase):
    def test_public_transport_keeps_redirect_timeout_and_byte_bounds(self):
        from unittest.mock import patch
        from ft_tui.features.profiles.adapters import portraits
        response = Mock()
        response.iter_bytes.return_value = [b'abc', b'def']
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        with patch.object(portraits.httpx, 'stream', return_value=context) as stream:
            result = portraits.download_portrait('https://cdn.intra.42.fr/a')
            self.assertEqual(result['image_base64'], 'YWJjZGVm')
            stream.assert_called_once_with('GET', 'https://cdn.intra.42.fr/a', timeout=10, follow_redirects=False)
            response.raise_for_status.assert_called_once()
        with patch.object(portraits.httpx, 'stream') as stream:
            with self.assertRaises(ValueError):
                portraits.download_portrait('https://example.test/a')
            stream.assert_not_called()
        response.iter_bytes.return_value = [b'a' * (portraits.MAX_PORTRAIT_BYTES + 1)]
        with patch.object(portraits.httpx, 'stream', return_value=context):
            with self.assertRaises(ValueError):
                portraits.download_portrait('https://cdn.intra.42.fr/a')
