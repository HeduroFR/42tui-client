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
        self.assertFalse(any(x.startswith('ft_tui.ui') for x in imports(ROOT/'services/user_profile.py')))

    def test_compatibility_imports_keep_canonical_catalog_class_and_patch_identity(self):
        from ft_tui.api import catalog_types
        from ft_tui.features.catalog import models
        from ft_tui.services import catalog_cache
        from ft_tui.features.catalog.adapters import cache
        self.assertIs(catalog_types, models)
        self.assertIs(catalog_cache, cache)
        self.assertIs(catalog_types.CatalogScope, models.CatalogScope)

    def test_dashboard_presentation_has_no_storage_or_direct_network_operations(self):
        path = ROOT/'features/dashboard/views/home.py'
        tree = ast.parse(path.read_text())
        self.assertFalse(any(isinstance(n, ast.Attribute) and n.attr=='session_factory' for n in ast.walk(tree)))
        self.assertFalse(any(x.startswith(('sqlalchemy','ft_tui.db','httpx','ft_tui.features.profiles.adapters')) for x in imports(path)))

    def test_dashboard_and_profile_legacy_modules_have_canonical_identity(self):
        from ft_tui.ui import dashboard
        from ft_tui.features.dashboard.views import home
        from ft_tui.services import dashboard_cache, project_curriculum
        from ft_tui.features.profiles.adapters import cache
        from ft_tui.features.catalog import read_models
        self.assertIs(dashboard, home)
        self.assertIs(dashboard_cache, cache)
        self.assertIs(project_curriculum, read_models)

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

    def test_community_views_and_dtos_preserve_legacy_module_identity(self):
        from ft_tui.ui import friends,clubs,social
        from ft_tui.features.friends.views import workspace as friend_view
        from ft_tui.features.clubs.views import workspace as club_view
        from ft_tui.features.social.views import inbox
        from ft_tui.api import friends_types,clubs_types,social_types
        from ft_tui.features.friends import models as friend_models
        from ft_tui.features.clubs import models as club_models
        from ft_tui.features.social import models as social_models
        self.assertIs(friends,friend_view);self.assertIs(clubs,club_view);self.assertIs(social,inbox)
        self.assertIs(friends_types,friend_models);self.assertIs(clubs_types,club_models);self.assertIs(social_types,social_models)

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

    def test_campus_feature_legacy_module_identities_remain_canonical(self):
        from ft_tui.ui import cluster_map,correction_slots
        from ft_tui.features.cluster_map.views import cluster_map as workspace
        from ft_tui.features.corrections import views as corrections_workspace
        self.assertIs(cluster_map,workspace)
        self.assertIs(correction_slots,corrections_workspace)

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

    def test_settings_and_installation_facades_keep_canonical_patch_identity(self):
        from ft_tui.ui import settings, updates
        from ft_tui.services import user_settings, updates as runtime, installation
        from ft_tui.features.settings.views import workspace
        from ft_tui.features.settings.adapters import storage
        from ft_tui.features.installation.views import updates as update_view
        from ft_tui.features.installation.adapters import runtime as update_runtime, maintenance
        self.assertIs(settings, workspace)
        self.assertIs(updates, update_view)
        self.assertIs(user_settings, storage)
        self.assertIs(runtime, update_runtime)
        self.assertIs(installation, maintenance)

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

    def test_goals_validator_keeps_canonical_identity(self):
        from ft_tui.api import goals_types
        from ft_tui.features.profiles import goals
        self.assertIs(goals_types, goals)
