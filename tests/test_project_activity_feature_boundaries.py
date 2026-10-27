"""Activity compatibility and provider validation survive feature extraction."""
import ast
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
import unittest
from activity_fixtures import history,evaluations


class ActivityBoundaryTests(unittest.TestCase):
    def test_legacy_validator_display_and_view_modules_are_aliases(self):
        for old,new in [('api.activity_types','activity.models'),('services.project_activity','activity.presentation'),('ui.project_activity','views.activity')]:
            self.assertIs(import_module('ft_tui.'+old),import_module('ft_tui.features.projects.'+new))

    def test_service_validates_history_identity_and_discards_unknown_fields(self):
        from ft_tui.features.projects.activity.service import ActivityService
        from ft_tui.api.catalog_types import CatalogScope
        payload=history();payload['private_upstream']='discard'
        provider=SimpleNamespace(get_project_activity=lambda *args,**kwargs:payload)
        clean=ActivityService().history(provider,1001,CatalogScope(21,31),'42')
        self.assertNotIn('private_upstream',clean)
        payload['account_id']='other'
        with self.assertRaises(ValueError):ActivityService().history(provider,1001,CatalogScope(21,31),'42')

    def test_service_rejects_evaluations_for_another_team(self):
        from ft_tui.features.projects.activity.service import ActivityService
        from ft_tui.api.catalog_types import CatalogScope
        provider=SimpleNamespace(get_team_evaluations=lambda *args,**kwargs:evaluations(99))
        with self.assertRaises(ValueError):ActivityService().evaluations(provider,1001,8,CatalogScope(21,31),'42')

    def test_core_has_no_io_and_activity_view_opens_no_sessions(self):
        from ft_tui.features.projects.activity import service
        root=Path(service.__file__).parent
        for name in ('service','models','ports'):
            for node in ast.walk(ast.parse((root/(name+'.py')).read_text())):
                names=([node.module] if isinstance(node,ast.ImportFrom) and node.module else
                       [alias.name for alias in node.names] if isinstance(node,ast.Import) else [])
                for name in names:self.assertFalse(name.startswith(('sqlalchemy','textual','httpx','subprocess','ft_tui.ui')),name)
        view=import_module('ft_tui.features.projects.views.activity')
        self.assertNotIn('session_factory()',Path(view.__file__).read_text())
