"""The scoped runner must preserve complete, non-overlapping test coverage."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def runner_module():
    spec = importlib.util.spec_from_file_location('regression_scopes', ROOT/'release/regression_scopes.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(module):
    return type('Example', (unittest.TestCase,), {'__module__': module, 'runTest': lambda self: None})()


class RegressionScopeTests(unittest.TestCase):
    def test_matrix_cli_exports_every_validated_scope(self):
        result = subprocess.run(
            [sys.executable, str(ROOT/'release/regression_scopes.py'), '--matrix'],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {'scope': list(runner_module().SCOPES)})

    def test_matrix_refuses_unassigned_modules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'test_new.py').write_text(
                'import unittest\nclass New(unittest.TestCase):\n def test_new(self): pass\n'
            )
            script = '''
import functools, importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('runner', sys.argv[1])
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
runner.discover_plan = functools.partial(runner.discover_plan, Path(sys.argv[2]), {})
raise SystemExit(runner.main(['--matrix']))
'''
            result = subprocess.run(
                [sys.executable, '-c', script, str(ROOT/'release/regression_scopes.py'), str(root)],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, '')
            self.assertIn('Unassigned modules', result.stderr)

    def test_every_discovered_case_is_assigned_once_to_its_feature_scope(self):
        runner = runner_module()
        tests = [case('test_account'), case('test_projects'), case('test_widgets')]
        scopes = {'identity': ('test_account',), 'projects': ('test_projects',), 'shared': ('test_widgets',)}
        plan = runner.partition_tests(tests, set(scopes_module for modules in scopes.values() for scopes_module in modules), scopes)
        self.assertEqual({key: [test.id() for test in value] for key, value in plan.items()}, {
            'identity': ['test_account.Example.runTest'],
            'projects': ['test_projects.Example.runTest'],
            'shared': ['test_widgets.Example.runTest'],
        })

    def test_new_unassigned_module_fails_instead_of_silently_skipping(self):
        with self.assertRaisesRegex(ValueError, 'test_new'):
            runner_module().partition_tests([case('test_new')], {'test_old', 'test_new'}, {'shared': ('test_old',)})

    def test_module_in_two_scopes_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'multiple scopes'):
            runner_module().partition_tests([case('test_account')], {'test_account'},
                                            {'one': ('test_account',), 'two': ('test_account',)})

    def test_removed_module_is_reported(self):
        with self.assertRaisesRegex(ValueError, 'test_removed'):
            runner_module().partition_tests([case('test_account')], {'test_account'},
                                            {'one': ('test_account', 'test_removed')})

    def test_duplicate_test_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate test'):
            runner_module().partition_tests([case('test_account'), case('test_account')], {'test_account'},
                                            {'one': ('test_account',)})

    def test_runner_propagates_test_failures_and_discovery_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            test = root/'test_scope_failure.py'
            test.write_text('import unittest\nclass Failure(unittest.TestCase):\n def test_failure(self):\n  self.fail("scope failure fixture")\n')
            # Use the library entry point with a custom in-memory scope map; production CLI
            # keeps the checked-in manifest and discovers tests from the repository.
            script = '''
import importlib.util, sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('runner', sys.argv[1])
runner=importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
raise SystemExit(runner.run_scope('example', Path(sys.argv[2]), {'example': ('test_scope_failure',)}, durations=0))
'''
            args = [sys.executable, '-c', script, str(ROOT/'release/regression_scopes.py'), str(root)]
            failure = subprocess.run(args, capture_output=True, text=True)
            self.assertEqual(failure.returncode, 1)
            self.assertIn('scope failure fixture', failure.stderr)
            test.write_text('raise RuntimeError("broken discovery fixture")\n')
            broken = subprocess.run(args, capture_output=True, text=True)
            self.assertNotEqual(broken.returncode, 0)
            self.assertIn('broken discovery fixture', broken.stderr)
