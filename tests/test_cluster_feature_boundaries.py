"""Import compatibility, layering and resource paths survive extraction."""
import ast
import importlib
from pathlib import Path
from types import SimpleNamespace
import unittest


class ClusterBoundaryTests(unittest.TestCase):
    def test_legacy_imports_are_canonical_module_aliases(self):
        for legacy,canonical in [('api.cluster_map_types','models'),
                ('cluster_map.geometry','geometry'),('cluster_map.state','state'),('cluster_map.experience','experience'),
                *[('ui.'+name,'views.'+name) for name in ('cluster_map','cluster_issue','cluster_workstation','cluster_seat_preview','cluster_map_grid')]]:
            self.assertIs(importlib.import_module('ft_tui.'+legacy),importlib.import_module('ft_tui.features.cluster_map.'+canonical))

    def test_feature_core_has_no_framework_or_concrete_infrastructure_imports(self):
        from ft_tui.features.cluster_map import service
        root=Path(service.__file__).parent
        for name in ('service','ports','models','state','geometry','experience'):
            tree=ast.parse((root/(name+'.py')).read_text())
            for node in ast.walk(tree):
                modules=([node.module] if isinstance(node,ast.ImportFrom) and node.module else
                         [alias.name for alias in node.names] if isinstance(node,ast.Import) else [])
                for module in modules:
                    self.assertFalse(module.startswith(('textual','sqlalchemy','httpx','ft_tui.infrastructure','ft_tui.app')),module)

    def test_views_never_open_database_sessions(self):
        from ft_tui.features.cluster_map import service
        root=Path(service.__file__).parent/'views'
        for file in root.glob('*.py'):
            self.assertNotIn('with factory()',file.read_text())
            self.assertNotIn('with session_factory()',file.read_text())

    def test_local_repository_keeps_storage_account_scoped(self):
        from ft_tui.features.cluster_map.adapters.sqlite import SqliteClusterRepository
        factory=SimpleNamespace(kw={'bind':SimpleNamespace(url=SimpleNamespace(database='/tmp/example/user.db'))})
        repository=SqliteClusterRepository(factory)
        self.assertNotEqual(repository.portrait_directory('one','origin'),repository.portrait_directory('two','origin'))
        self.assertNotEqual(repository.portrait_directory('one','origin'),repository.portrait_directory('one','other'))
        self.assertIsNone(repository.portrait_directory(None,'origin'))
        empty=SqliteClusterRepository(None)
        self.assertEqual(empty.memberships('one'),[])
        self.assertIsNone(empty.configured_cursus())
        self.assertIsNone(empty.portrait_directory('one','origin'))
