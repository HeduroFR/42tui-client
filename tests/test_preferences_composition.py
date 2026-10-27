"""Settings and installation state have explicit production composition."""
import unittest
from ft_tui.db.database import make_session_factory
from ft_tui.ui.app import FortyTwoTuiApp


class PreferencesCompositionTests(unittest.TestCase):
    def setUp(self):
        self.factory = make_session_factory('sqlite:///:memory:')

    def tearDown(self):
        self.factory.kw['bind'].dispose()

    def test_services_have_production_defaults(self):
        app = FortyTwoTuiApp(self.factory, None)
        self.assertIsNotNone(app.settings_service)
        self.assertIsNotNone(app.installation_service)

    def test_supplied_services_are_not_replaced(self):
        settings, installation = object(), object()
        app = FortyTwoTuiApp(self.factory, None, settings_service=settings,
                            installation_service=installation)
        self.assertIs(app.settings_service, settings)
        self.assertIs(app.installation_service, installation)
