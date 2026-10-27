import unittest

from ft_tui.db.database import make_session_factory
from ft_tui.db.models import FriendObservation
from ft_tui.services.friends import cache_mutual_friends, memberships, save_observation, cached_observations, forget_authorization
from ft_tui.services.user_settings import get_setting, save_settings
from tests.friends_fixtures import snapshot


class OriginStorageTests(unittest.TestCase):
    def test_membership_removal_and_revocation_remove_only_eligible_history(self):
        factory = make_session_factory('sqlite://')
        try:
            with factory() as session:
                save_settings(session, {'personal-note': 'keep'})
                cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}], origin='https://a.test')
                save_observation(session, '42', snapshot(), origin='https://a.test')
                save_observation(session, '42', snapshot('you', user_id='42'), origin='https://a.test')
                cache_mutual_friends(session, '42', [], origin='https://a.test')
                self.assertEqual(set(cached_observations(session, '42', 21, origin='https://a.test')), {'you'})
                forget_authorization(session, '42', origin='https://b.test')
                self.assertIn('you', cached_observations(session, '42', 21, origin='https://a.test'))
                forget_authorization(session, '42', origin='https://a.test')
                self.assertEqual(cached_observations(session, '42', 21, origin='https://a.test'), {})
                self.assertEqual(get_setting(session, 'personal-note'), 'keep')
        finally:
            factory.kw['bind'].dispose()

    def test_origin_membership_identity_and_corrupt_legacy_entries(self):
        factory = make_session_factory('sqlite://')
        try:
            with factory() as session:
                save_settings(session, {'personal-note': 'keep', 'mutual_friends:42': '["50"]'})
                self.assertEqual(memberships(session, '42', origin='https://a.test'), [])
                cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}], origin='https://a.test')
                save_observation(session, '42', snapshot(), origin='https://a.test')
                self.assertEqual(len(memberships(session, '42', origin='https://a.test/')), 1)
                self.assertEqual(memberships(session, '42', origin='https://b.test'), [])
                self.assertEqual(cached_observations(session, '42', 21, origin='https://b.test'), {})
                saved = cached_observations(session, '42', 21, origin='https://a.test')['alice']
                self.assertEqual(saved['presence']['status'], 'unavailable')
                self.assertIsNone(saved['location'])
                row = session.query(FriendObservation).one()
                row.data = snapshot()  # Legacy payload has no verifiable origin.
                session.commit()
                self.assertEqual(cached_observations(session, '42', 21, origin='https://a.test'), {})
                row.data = {'version': 1, 'origin': 'https://a.test', 'snapshot': None}
                session.commit()
                self.assertEqual(cached_observations(session, '42', 21, origin='https://a.test'), {})
                self.assertEqual(get_setting(session, 'personal-note'), 'keep')
        finally:
            factory.kw['bind'].dispose()
