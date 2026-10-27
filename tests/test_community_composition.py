"""The shell wires feature services while tests can inject their own capabilities."""
import unittest
from types import SimpleNamespace
from ft_tui.db.database import make_session_factory
from ft_tui.ui.app import FortyTwoTuiApp

class CommunityCompositionTests(unittest.TestCase):
    def setUp(self):self.factory=make_session_factory('sqlite:///:memory:')
    def tearDown(self):self.factory.kw['bind'].dispose()
    def test_shell_constructs_feature_services_for_independent_community_owners(self):
        from ft_tui.features.friends.service import FriendsService
        from ft_tui.features.clubs.service import ClubsService
        from ft_tui.features.social.service import SocialService
        app=FortyTwoTuiApp(self.factory,None)
        self.assertIsInstance(app.friends_service,FriendsService)
        self.assertIsInstance(app.clubs_service,ClubsService)
        self.assertIsInstance(app.social_service,SocialService)
    def test_explicit_service_injection_is_not_replaced(self):
        friends,clubs,social=object(),object(),object()
        app=FortyTwoTuiApp(self.factory,None,friends_service=friends,clubs_service=clubs,social_service=social)
        self.assertIs(app.friends_service,friends)
        self.assertIs(app.clubs_service,clubs)
        self.assertIs(app.social_service,social)
