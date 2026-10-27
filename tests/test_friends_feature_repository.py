"""Friend storage adapter preserves consent, origin isolation and stale presence."""
import unittest
from ft_tui.db.database import make_session_factory
from ft_tui.features.friends.adapters.sqlite import SqliteFriendsRepository, Membership
from ft_tui.features.friends.adapters.storage import cache_mutual_friends
from tests.friends_fixtures import snapshot

class FriendsFeatureRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.factory=make_session_factory('sqlite:///:memory:')
        self.repo=SqliteFriendsRepository(self.factory)
    def tearDown(self):self.factory.kw['bind'].dispose()

    def test_only_confirmed_mutual_relationships_are_portable_memberships(self):
        with self.factory() as session:
            cache_mutual_friends(session,'42',[{'account_id':'50','login':'alice'}],origin='https://one.test')
        members=self.repo.memberships('42',origin='https://one.test')
        self.assertEqual(members,[Membership('alice','50')])
        self.assertEqual(self.repo.memberships('42',origin='https://two.test'),[])
        self.assertEqual(self.repo.memberships('other',origin='https://one.test'),[])
        with self.assertRaises(Exception):members[0].login='changed'

    def test_saved_observation_discards_presence_and_is_scoped_by_origin_and_cursus(self):
        self.repo.save('42',snapshot(),origin='https://one.test/api')
        cached=self.repo.cached('42',21,origin='https://one.test/api')['alice']
        self.assertIsNone(cached['location'])
        self.assertEqual(cached['presence'],{'status':'unavailable','cached_at':None})
        self.assertTrue(cached['meta']['stale'])
        self.assertEqual(self.repo.cached('42',21,origin='https://two.test/api'),{})
        self.assertEqual(self.repo.cached('42',9,origin='https://one.test/api'),{})
        self.repo.forget('42',21,'alice',origin='https://two.test/api')
        self.assertIn('alice',self.repo.cached('42',21,origin='https://one.test/api'))
        self.repo.forget('42',21,'alice',origin='https://one.test/api')
        self.assertEqual(self.repo.cached('42',21,origin='https://one.test/api'),{})

    def test_custom_selection_capability_is_invoked_inside_repository_session(self):
        calls=[]
        def select(session):calls.append(session);return 21
        self.assertEqual(self.repo.configured_cursus(select),21)
        self.assertEqual(len(calls),1)
