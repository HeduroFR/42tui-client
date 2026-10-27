"""Enforce boundaries for migrated feature code while legacy UI remains explicit."""
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]/'src/ft_tui'


def imports(path):
    module = 'ft_tui.' + '.'.join(path.relative_to(ROOT).with_suffix('').parts)
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield importlib.util.resolve_name('.'*node.level+(node.module or ''), module.rpartition('.')[0]) if node.level else node.module or ''


class ArchitectureBoundaryTests(unittest.TestCase):
    def test_feature_cores_do_not_import_presentation_storage_or_http_implementations(self):
        forbidden = ('textual','sqlalchemy','httpx','ft_tui.ui','ft_tui.db','ft_tui.infrastructure','ft_tui.app')
        for path in (ROOT/'features').rglob('*.py'):
            if any(part in ('views', 'adapters') for part in path.relative_to(ROOT/'features').parts) or path.relative_to(ROOT).as_posix() in {'features/corrections/views.py','features/corrections/calendar.py'}:
                continue
            for target in imports(path):
                with self.subTest(module=path.relative_to(ROOT), dependency=target):
                    self.assertFalse(any(target==prefix or target.startswith(prefix+'.') for prefix in forbidden))

    def test_catalog_presentation_never_opens_a_database_session(self):
        path = ROOT/'features/catalog/views/controller.py'
        tree = ast.parse(path.read_text())
        self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr=='session_factory' for n in ast.walk(tree)))
        self.assertFalse(any(x.startswith(('sqlalchemy','ft_tui.db')) for x in imports(path)))

    def test_profile_download_does_not_import_a_widget(self):
        self.assertFalse(any(x.startswith('ft_tui.ui') for x in imports(ROOT/'features/profiles/adapters/portraits.py')))

    def test_dashboard_presentation_has_no_storage_or_direct_network_operations(self):
        path = ROOT/'features/dashboard/views/home.py'
        tree = ast.parse(path.read_text())
        self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr=='session_factory' for n in ast.walk(tree)))
        self.assertFalse(any(x.startswith(('sqlalchemy','ft_tui.db','httpx','ft_tui.features.profiles.adapters')) for x in imports(path)))

    def test_note_and_project_setup_views_do_not_open_database_sessions(self):
        for rel in ('features/worklog/views/notes.py','features/projects/views/setup.py'):
            path=ROOT/rel
            tree=ast.parse(path.read_text())
            self.assertFalse(any(isinstance(n,ast.Attribute) and n.attr=='session_factory' for n in ast.walk(tree)),rel)
            self.assertFalse(any(x.startswith(('sqlalchemy','ft_tui.db')) for x in imports(path)),rel)

    def test_community_views_do_not_open_sql_sessions(self):
        for directory in ('friends','clubs','social'):
            for path in (ROOT/f'features/{directory}/views').glob('*.py'):
                tree=ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node,(ast.With,ast.AsyncWith)):
                        for item in node.items:
                            call=item.context_expr
                            self.assertFalse(isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute)
                                             and call.func.attr=='session_factory',str(path))
                self.assertFalse(any(x.startswith(('sqlalchemy','ft_tui.db')) for x in imports(path)),str(path))

    def test_cluster_and_corrections_views_do_not_open_database_sessions(self):
        for feature in ('cluster_map','corrections'):
            for path in list((ROOT/f'features/{feature}/views').glob('*.py')) + ([ROOT/'features/corrections/views.py',ROOT/'features/corrections/calendar.py'] if feature == 'corrections' else []):
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node,(ast.With,ast.AsyncWith)):
                        for item in node.items:
                            call=item.context_expr
                            self.assertFalse(isinstance(call,ast.Call) and isinstance(call.func,ast.Attribute)
                                             and call.func.attr in ('session_factory','factory'),str(path))
                self.assertFalse(any(x.startswith(('sqlalchemy','ft_tui.db')) for x in imports(path)),str(path))

    def test_settings_and_update_views_do_not_own_database_sessions(self):
        for feature in ('settings', 'installation'):
            paths = list((ROOT/f'features/{feature}/views').glob('*.py'))
            self.assertTrue(paths, feature)
            for path in paths:
                tree = ast.parse(path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, (ast.With, ast.AsyncWith)):
                        for item in node.items:
                            call = item.context_expr
                            self.assertFalse(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                                             and call.func.attr in ('session_factory', 'factory'), str(path))
                self.assertFalse(any(x.startswith(('sqlalchemy', 'ft_tui.db')) for x in imports(path)), str(path))

    def test_remaining_workflow_views_do_not_open_database_sessions(self):
        for rel in ('projects/views/registration.py', 'projects/views/team.py',
                    'projects/views/activity.py', 'projects/views/subjects.py',
                    'profiles/views/user_profile.py', 'profiles/views/profile_view.py',
                    'profiles/views/profile_sections.py'):
            path = ROOT/'features'/rel
            self.assertTrue(path.exists(), rel)
            tree = ast.parse(path.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.With, ast.AsyncWith)):
                    for item in node.items:
                        call = item.context_expr
                        self.assertFalse(isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                                         and call.func.attr in ('session_factory', 'factory'), rel)
            self.assertFalse(any(x.startswith(('sqlalchemy', 'ft_tui.db')) for x in imports(path)), rel)
