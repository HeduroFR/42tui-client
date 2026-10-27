"""Profile polling owns data decisions without a UI, clock sleeps or database."""
import unittest
from types import SimpleNamespace
from ft_tui.features.profiles.service import ProfileService
from ft_tui.features.profiles.state import ProfileState


class Repository:
    def __init__(self): self.goals = []; self.profiles = []
    def load_profile(self, client): return {'account_id': '42', 'login': 'cached'}
    def load_goals(self, account, cursus): return {'status': 'available', 'stale': True}
    def save_profile(self, client, value): self.profiles.append(value)
    def save_goals(self, account, cursus, value): self.goals.append((account, cursus, value))


class ProfileServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = Repository(); self.now = [100.0]
        self.service = ProfileService(self.repo, SimpleNamespace(configured_cursus=lambda: 21), clock=lambda: self.now[0])
        self.scope = (0, '42', 21)
        self.provider = SimpleNamespace(get_goals=lambda *args: {'status': 'available', 'stale': False})

    def test_optional_capability_and_scope_control_refresh(self):
        self.assertFalse(self.service.should_refresh(None, self.scope, connected=True))
        self.assertFalse(self.service.should_refresh(self.provider, self.scope, connected=False))
        self.assertTrue(self.service.should_refresh(self.provider, self.scope, connected=True))
        self.service.state.goals_scope = self.scope; self.service.state.next_poll = 110
        self.assertFalse(self.service.should_refresh(self.provider, self.scope, connected=True))
        self.now[0] = 110
        self.assertTrue(self.service.should_refresh(self.provider, self.scope, connected=True))

    async def test_fresh_final_result_persists_and_uses_fifteen_minute_deadline(self):
        self.service.state.profile = {'account_id': '42', 'login': 'latest'}
        accepted = await self.service.refresh_goals(self.provider, self.scope, lambda: True, client='device')
        self.assertTrue(accepted)
        self.assertEqual(self.service.state.next_poll, 1000)
        self.assertEqual(len(self.repo.goals), 1)
        self.assertEqual(self.repo.profiles, [self.service.state.profile])
        self.assertEqual(self.service.current_goals(self.scope, connected=True)['status'], 'available')
        self.assertEqual(self.service.current_goals((1, 'other', 21), connected=True), {})
        self.assertEqual(self.service.current_goals(self.scope, connected=False), {})

    async def test_pending_and_outage_preserve_final_observation_and_poll_in_thirty_seconds(self):
        for status in ('pending', 'outage'):
            self.service.state.goals = {'status': 'available', 'cc_validated': True}
            self.service.state.goals_scope = self.scope
            def fetch(*args):
                if status == 'outage': raise RuntimeError('temporary')
                return {'status': 'pending', 'stale': True}
            await self.service.refresh_goals(SimpleNamespace(get_goals=fetch), self.scope, lambda: True, client=None)
            self.assertEqual(self.service.state.goals, {'status': 'available', 'cc_validated': True, 'stale': True})
            self.assertEqual(self.service.state.next_poll, 130)
        self.assertEqual(self.repo.goals, [])

    async def test_obsolete_response_never_persists_or_mutates_state(self):
        active = [True]
        def fetch(*args): active[0] = False; return {'status': 'available'}
        accepted = await self.service.refresh_goals(SimpleNamespace(get_goals=fetch), self.scope, lambda: active[0], client=None)
        self.assertFalse(accepted)
        self.assertEqual(self.service.state.goals, {})
        self.assertEqual(self.repo.goals, [])
        self.assertEqual(self.service.state.next_poll, 0)

    async def test_different_scope_cannot_reuse_old_final_goals_on_error(self):
        self.service.state.goals = {'status': 'available', 'cc_validated': True}
        self.service.state.goals_scope = (0, 'previous', 21)
        await self.service.refresh_goals(SimpleNamespace(get_goals=lambda *args: {'status': 'pending'}), self.scope, lambda: True, client=None)
        self.assertEqual(self.service.state.goals, {'status': 'pending'})

    def test_cached_reads_preserve_profile_and_stale_goals(self):
        self.assertEqual(self.service.cached_profile(None)['login'], 'cached')
        self.assertTrue(self.service.cached_goals('42', 21)['stale'])
