"""The final shell delegates storage and exposes single-owner feature state."""
import ast
from pathlib import Path
import unittest
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.db.database import make_session_factory

ROOT = Path(__file__).resolve().parents[1]/'src/ft_tui'

class ShellArchitectureTests(unittest.TestCase):
    def test_app_shell_never_opens_database_sessions(self):
        tree=ast.parse((ROOT/'ui/app.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,(ast.With,ast.AsyncWith)):
                for item in node.items:
                    expr=item.context_expr
                    self.assertFalse(isinstance(expr,ast.Call) and isinstance(expr.func,ast.Attribute)
                                     and expr.func.attr in ('session_factory','factory'),node.lineno)

    def test_project_and_settings_state_are_single_owned(self):
        factory=make_session_factory('sqlite:///:memory:')
        try:
            first=FortyTwoTuiApp(factory,None);second=FortyTwoTuiApp(factory,None)
            first.projects['one']=object()
            self.assertIs(first.projects,first.project_state.projects)
            self.assertEqual(second.project_state.projects,{})
            first.favorite_editor='zed'
            self.assertEqual(first.settings_state.favorite_editor,'zed')
            self.assertEqual(second.settings_state.favorite_editor,'nvim')
        finally:factory.kw['bind'].dispose()

    def test_new_shell_services_support_explicit_injection(self):
        factory=make_session_factory('sqlite:///:memory:')
        try:
            startup,account=object(),object()
            # Startup is used by construction; inject a minimal explicit collaborator.
            class Startup:
                def initial_preferences(self,language):
                    return dict(campus_directory=[],language='en',club_notification_sound=True,
                                image_mode='auto',icon_mode='auto',username_gradient='off',
                                offline_account_id=None,offline_account_campuses=[])
            startup=Startup()
            app=FortyTwoTuiApp(factory,None,startup_service=startup,account_shell_service=account)
            self.assertIs(app.startup_service,startup)
            self.assertIs(app.account_shell_service,account)
        finally:factory.kw['bind'].dispose()

    def test_startup_core_imports_without_transport_dependencies(self):
        import os,subprocess,sys
        result=subprocess.run([sys.executable,'-S','-c',
            'from ft_tui.app.startup import StartupService; from ft_tui.features.accounts.shell_service import AccountShellService'],
            env=dict(os.environ,PYTHONPATH=str(ROOT.parent)),capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        from ft_tui.features.accounts import campuses as campus_types
        from ft_tui.features.accounts import campuses
        self.assertIs(campus_types,campuses)
