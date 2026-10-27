"""Cluster/corrections services have production defaults and explicit injection."""
import unittest
from ft_tui.db.database import make_session_factory
from ft_tui.ui.app import FortyTwoTuiApp

class CampusCompositionTests(unittest.TestCase):
    def setUp(self):self.factory=make_session_factory('sqlite:///:memory:')
    def tearDown(self):self.factory.kw['bind'].dispose()
    def test_cluster_and_corrections_services_are_constructed(self):
        app=FortyTwoTuiApp(self.factory,None)
        self.assertIsNotNone(app.cluster_service)
        self.assertIsNotNone(app.corrections_service)
    def test_explicit_services_are_preserved(self):
        cluster,corrections=object(),object()
        app=FortyTwoTuiApp(self.factory,None,cluster_service=cluster,corrections_service=corrections)
        self.assertIs(app.cluster_service,cluster)
        self.assertIs(app.corrections_service,corrections)
