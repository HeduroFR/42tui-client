"""Clubs orchestration is headless and never retries an uncertain mutation."""
import unittest
from types import SimpleNamespace

from ft_tui.features.clubs.service import ClubsService


class ClubsFeatureTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = ClubsService()

    async def test_overview_checks_identity_and_obsolete_context_before_return(self):
        calls = []
        provider = SimpleNamespace(get_clubs=lambda campus: calls.append(campus) or {'account_id': '42'})
        self.assertEqual(await self.service.read(provider, 31, '42', lambda: True), {'account_id': '42'})
        self.assertEqual(calls, [31])
        with self.assertRaisesRegex(ValueError, 'account mismatch'):
            await self.service.read(provider, 31, '43', lambda: True)
        active = [True]
        def fetch(campus):
            active[0] = False
            return {'account_id': '42'}
        self.assertIsNone(await self.service.read(SimpleNamespace(get_clubs=fetch), 31, '42', lambda: active[0]))

    async def test_obsolete_or_missing_capability_does_not_dispatch(self):
        calls = []
        provider = SimpleNamespace(get_clubs=lambda campus: calls.append(campus))
        self.assertIsNone(await self.service.read(provider, 31, '42', lambda: False))
        self.assertEqual(calls, [])
        self.assertIsNone(await self.service.read(SimpleNamespace(), 31, '42', lambda: True))
        self.assertIsNone(await self.service.poll(SimpleNamespace(), lambda: True))

    async def test_poll_discards_a_response_after_scope_or_revision_changes(self):
        active = [True]
        def poll():
            active[0] = False
            return {'dnd': False, 'bells': {}, 'notifications': []}
        self.assertIsNone(await self.service.poll(SimpleNamespace(poll_clubs=poll), lambda: active[0]))

    async def test_mutation_dispatch_keeps_exact_draft_id_and_no_retries(self):
        calls = []
        def action(club, draft):
            calls.append((club, draft))
            raise RuntimeError('outcome unknown')
        draft = {'action': 'announce', 'id': 'stable-original-id', 'message': 'text'}
        with self.assertRaisesRegex(RuntimeError, 'outcome unknown'):
            await self.service.mutate(SimpleNamespace(club_action=action), draft, lambda: True, club_id='campus-31')
        self.assertEqual(calls, [('campus-31', draft)])
        self.assertIs(calls[0][1], draft)

    async def test_preference_and_creation_use_their_distinct_capabilities(self):
        calls = []
        provider = SimpleNamespace(set_club_preferences=lambda d: calls.append(('preference', d)) or {'dnd': True},
                                   create_club=lambda d: calls.append(('create', d)) or {'id': 'new'})
        self.assertEqual(await self.service.mutate(provider, {'dnd': True}, lambda: True, preference=True), {'dnd': True})
        self.assertEqual(await self.service.mutate(provider, {'name': 'Club'}, lambda: True, create=True), {'id': 'new'})
        self.assertEqual([kind for kind, _ in calls], ['preference', 'create'])

    async def test_mutation_result_after_context_change_is_not_publishable(self):
        active = [True]
        def action(club, draft):
            active[0] = False
            return {'id': club}
        self.assertIsNone(await self.service.mutate(SimpleNamespace(club_action=action), {'action': 'join'},
                                                   lambda: active[0], club_id='campus-31'))

    def test_contract_and_view_legacy_imports_keep_canonical_identity(self):
        from ft_tui.api import clubs_types
        from ft_tui.features.clubs import models
        from ft_tui.ui import clubs, club_announcements, club_inbox
        from ft_tui.features.clubs.views import workspace, announcements, inbox
        self.assertIs(clubs_types, models)
        self.assertIs(clubs, workspace)
        self.assertIs(club_announcements, announcements)
        self.assertIs(club_inbox, inbox)
