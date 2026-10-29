"""The shell command resolves only its containing project and reviews writes."""

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.git import main


class GitCliTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.child = self.root / 'src'
        self.child.mkdir()
        self.factory = make_session_factory('sqlite:///:memory:')
        self.addCleanup(self.factory.kw['bind'].dispose)
        with self.factory() as session:
            session.add(Project(slug='libft', name='Libft', local_path=str(self.root),
                                dev_repo_url='https://example.com/dev.git'))
            session.commit()
        self.output = StringIO()
        self.enterContext(redirect_stdout(self.output))
        self.enterContext(redirect_stderr(self.output))
        self.enterContext(patch('ft_tui.git.initialize_database', return_value=self.factory))
        self.enterContext(patch('ft_tui.git.database_url', return_value='unused'))
        self.enterContext(patch('ft_tui.git.Path.cwd', return_value=self.child))

    def test_status_resolves_nested_directory_without_publishing(self):
        snapshot = SimpleNamespace(error=None, branch='dev', staged=1, changed=2, untracked=3)
        with patch('ft_tui.git.inspect_repository', return_value=snapshot) as inspect, \
                patch('ft_tui.git.push_project') as push:
            self.assertEqual(main(['status']), 0)
        inspect.assert_called_once_with(self.root)
        push.assert_not_called()
        self.assertIn('Branch: dev', self.output.getvalue())

    def test_outside_or_ambiguous_project_never_plans_push(self):
        with patch('ft_tui.git.Path.cwd', return_value=self.root.parent), \
                patch('ft_tui.git.plan_project_push') as plan:
            self.assertEqual(main(['push', 'all']), 1)
            plan.assert_not_called()
        with self.factory() as session:
            session.add(Project(slug='duplicate', name='Duplicate', local_path=str(self.root)))
            session.commit()
        with patch('ft_tui.git.plan_project_push') as plan:
            self.assertEqual(main(['push', 'dev']), 1)
            plan.assert_not_called()

    def test_push_reviews_destinations_and_reports_partial_failure(self):
        targets = [SimpleNamespace(destination=name, url=f'https://example.com/{name}.git',
                                   branch=branch, error=None)
                   for name, branch in (('dev', 'dev'), ('vog', 'master'))]
        plan = SimpleNamespace(commit='a' * 40, branch='dev', dirty_count=2, targets=targets)
        results = [SimpleNamespace(target=target, success=index == 0, message='result')
                   for index, target in enumerate(targets)]
        def approve(prompt):
            self.assertIn('https://example.com/vog.git -> master', self.output.getvalue())
            self.assertIn('Uncommitted changes left untouched: 2', self.output.getvalue())
            self.assertIn('Vogsphere requires the 42 campus network', self.output.getvalue())
            return 'y'
        with patch('ft_tui.git.plan_project_push', return_value=plan) as prepare, \
                patch('ft_tui.git.push_project', return_value=results) as push, \
                patch('builtins.input', side_effect=approve):
            self.assertEqual(main(['push', 'all']), 1)
        prepare.assert_called_once_with(self.root, 'all', dev_remote_url='https://example.com/dev.git',
                                        vogsphere_url=None)
        push.assert_called_once_with(plan)
        self.assertIn('dev: OK', self.output.getvalue())
        self.assertIn('vog: FAILED', self.output.getvalue())

    def test_cancel_or_closed_stdin_never_dispatches(self):
        plan = SimpleNamespace(commit='a' * 40, branch='dev', dirty_count=0,
                               targets=(SimpleNamespace(destination='dev', url='dev', branch='dev', error=None),))
        for response in ('', EOFError()):
            with self.subTest(response=response), patch('ft_tui.git.plan_project_push', return_value=plan), \
                    patch('ft_tui.git.push_project') as push, \
                    patch('builtins.input', **({'side_effect': response} if isinstance(response, Exception)
                                              else {'return_value': response})):
                self.assertEqual(main(['push', 'dev']), 2)
                push.assert_not_called()

    def test_pull_reviews_sources_and_requires_confirmation(self):
        plan = SimpleNamespace(commit='a'*40, branch='work', target_commit='b'*40,
                               targets=(SimpleNamespace(destination='vog', url='remote', branch='main', commit='b'*40),))
        with patch('ft_tui.git.plan_project_pull', return_value=plan) as prepare, \
                patch('ft_tui.git.pull_project', return_value='Fast-forwarded') as pull, \
                patch('builtins.input', return_value='y'):
            self.assertEqual(main(['pull', 'vog']), 0)
        prepare.assert_called_once_with(self.root, 'vog', dev_remote_url='https://example.com/dev.git', vogsphere_url=None)
        pull.assert_called_once_with(plan)
        self.assertIn('remote -> main', self.output.getvalue())
        self.assertIn('Fast-forwarded', self.output.getvalue())
        for reply in ('n', EOFError()):
            with patch('ft_tui.git.plan_project_pull', return_value=plan), \
                    patch('ft_tui.git.pull_project') as pull, \
                    patch('builtins.input', **({'side_effect': reply} if isinstance(reply, Exception) else {'return_value': reply})):
                self.assertEqual(main(['pull', 'all']), 2)
                pull.assert_not_called()

    def test_pull_failure_never_applies(self):
        from ft_tui.features.projects.adapters.git import ProjectGitError
        with patch('ft_tui.git.plan_project_pull', side_effect=ProjectGitError('Histories diverge')), \
                patch('ft_tui.git.pull_project') as pull:
            self.assertEqual(main(['pull', 'all']), 1)
            pull.assert_not_called()
