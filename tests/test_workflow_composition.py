"""Remaining project/profile workflows support explicit app composition."""
import unittest
from ft_tui.db.database import make_session_factory
from ft_tui.ui.app import FortyTwoTuiApp


class WorkflowCompositionTests(unittest.TestCase):
    def setUp(self):
        self.factory = make_session_factory('sqlite:///:memory:')

    def tearDown(self):
        self.factory.kw['bind'].dispose()

    def test_default_workflow_services_exist(self):
        app = FortyTwoTuiApp(self.factory, None)
        for name in ('registration_service', 'subject_service', 'activity_service', 'student_profile_service'):
            with self.subTest(service=name):
                self.assertIsNotNone(getattr(app, name))

    def test_explicit_workflow_services_are_retained(self):
        services = {name: object() for name in (
            'registration_service', 'subject_service', 'activity_service', 'student_profile_service')}
        app = FortyTwoTuiApp(self.factory, None, **services)
        for name, service in services.items():
            with self.subTest(service=name):
                self.assertIs(getattr(app, name), service)
