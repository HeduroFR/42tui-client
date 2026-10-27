"""Only current server-confirmed social lists authorize historical friend reads."""
import unittest
from ft_tui.db.database import make_session_factory
from ft_tui.features.social.adapters.sqlite import SqliteSocialRepository
from ft_tui.services.friends import memberships


class SocialRepositoryTests(unittest.TestCase):
    def test_confirmed_friend_cache_is_origin_and_account_scoped(self):
        factory=make_session_factory('sqlite:///:memory:')
        try:
            repo=SqliteSocialRepository(factory)
            repo.cache_confirmed('1',[{'account_id':'2','login':'bob'}],origin='https://one.test')
            with factory() as session:
                self.assertEqual([watch.login for watch in memberships(session,'1',origin='https://one.test')],['bob'])
                self.assertEqual(memberships(session,'1',origin='https://two.test'),[])
                self.assertEqual(memberships(session,'3',origin='https://one.test'),[])
            repo.cache_confirmed('1',[],origin='https://one.test')
            with factory() as session:self.assertEqual(memberships(session,'1',origin='https://one.test'),[])
        finally:factory.kw['bind'].dispose()
