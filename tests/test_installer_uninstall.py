"""Maintenance delegates only to the owning manager and leaves app data alone."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zipfile
from unittest.mock import patch

from ft_tui.services.installation import manage_installation

ROOT = Path(__file__).resolve().parents[1]


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.prefix = self.home/'venvs/ft-tui'
        self.prefix.mkdir(parents=True)
        self.distribution = SimpleNamespace(read_text=lambda name: None, locate_file=lambda name: self.prefix/'lib')

    def uv(self):
        (self.prefix/'uv-receipt.toml').write_text('[tool]\nrequirements=[{name="ft-tui"}]\n')

    def run_action(self, action, directory=None, mutation_code=0):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, mutation_code if len(calls) > 1 else 0,
                                               str(directory or self.prefix.parent), '')
        with patch('ft_tui.services.installation.sys.prefix', str(self.prefix)), \
             patch('ft_tui.services.installation.metadata.distribution', return_value=self.distribution), \
             patch('ft_tui.services.installation._manager_command', side_effect=lambda name: '/fake/'+name), \
             patch('ft_tui.services.installation.subprocess.run', side_effect=run), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            result = manage_installation(action)
        return result, calls

    def test_uv_update_uninstall_and_remove_alias(self):
        self.uv()
        for action in ('update', 'uninstall', 'remove'):
            with self.subTest(action=action):
                result, calls = self.run_action(action)
                self.assertEqual(result, 0)
                self.assertEqual(calls[0], ['/fake/uv', '--no-config', 'tool', 'dir'])
                self.assertEqual(calls[1][:5], ['/fake/uv', '--no-config', 'tool',
                                               'upgrade' if action == 'update' else 'uninstall', 'ft-tui'])
                self.assertNotIn('--force', calls[1])

    def test_pipx_update_and_uninstall(self):
        (self.prefix/'pipx_metadata.json').write_text(json.dumps({
            'main_package': {'package': 'ft-tui', 'package_or_url': 'ft-tui'}}))
        for action in ('update', 'uninstall'):
            result, calls = self.run_action(action)
            self.assertEqual(result, 0)
            self.assertEqual(calls[1][:3], ['/fake/pipx', 'upgrade' if action == 'update' else 'uninstall', 'ft-tui'])

    def test_wrong_manager_target_and_editable_install_are_preserved(self):
        self.uv()
        result, calls = self.run_action('uninstall', directory=self.home/'other-tools')
        self.assertEqual(result, 1)
        self.assertEqual(len(calls), 1)
        self.distribution.read_text = lambda name: '{"dir_info":{"editable":true}}'
        result, calls = self.run_action('update')
        self.assertEqual(result, 1)
        self.assertEqual(calls, [])

    def test_missing_or_corrupt_receipt_never_invokes_manager(self):
        for text in (None, 'invalid toml', '[tool]\nrequirements=["bad"]\n'):
            if text is not None:
                (self.prefix/'uv-receipt.toml').write_text(text)
            result, calls = self.run_action('uninstall')
            self.assertEqual(result, 1)
            self.assertEqual(calls, [])

    def test_manager_failure_is_not_reported_as_success(self):
        self.uv()
        result, _ = self.run_action('uninstall', mutation_code=7)
        self.assertEqual(result, 7)

    def test_cli_maintenance_and_help_never_import_ui_or_database(self):
        script = '''
import importlib.abc, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('ft_tui.db', 'ft_tui.ui', 'ft_tui.api', 'ft_tui.config')):
            raise RuntimeError('application import: '+fullname)
sys.meta_path.insert(0, Guard())
from ft_tui.main import main
sys.argv = ['42tui', *sys.argv[1:]]
main()
'''
        for args, expected in ((['update'], 1), (['uninstall'], 1), (['remove'], 1),
                               (['--help'], 0), (['uninstall', '--help'], 0), (['update', '--unknown'], 2)):
            with self.subTest(args=args):
                env = dict(os.environ, HOME=str(self.home), XDG_DATA_HOME=str(self.home), PYTHONPATH=str(ROOT/'src'))
                result = subprocess.run([sys.executable, '-c', script, *args], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertNotIn('application import:', result.stderr)


@unittest.skipIf(os.name == 'nt', 'POSIX uninstaller')
class ShellUninstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='42tui uninstall ')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.bin = self.home/'.local/bin'
        self.bin.mkdir(parents=True)
        self.tools = self.home/'tools'
        self.receipt = self.tools/'ft-tui/uv-receipt.toml'
        self.receipt.parent.mkdir(parents=True)
        self.receipt.touch()
        self.data = self.home/'data/42tui.sqlite3'
        self.data.parent.mkdir()
        self.data.write_text('keep user data')
        uv = self.bin/'uv'
        uv.write_text('''#!/bin/sh
case "$*" in
 '--no-config tool dir') printf '%s\\n' "$FAKE_TOOLS";;
 '--no-config tool uninstall ft-tui')
  [ "${FAKE_FAIL:-0}" = 0 ] || exit 7
  rm "$FAKE_TOOLS/ft-tui/uv-receipt.toml";;
 *) exit 9;;
esac
''')
        uv.chmod(0o755)
        self.env = dict(os.environ, HOME=str(self.home), PATH='/usr/bin:/bin', FAKE_TOOLS=str(self.tools))

    def run_script(self, *args):
        return subprocess.run(['sh', str(ROOT/'distribution/uninstall.sh'), *args],
                              env=self.env, capture_output=True, text=True)

    def test_local_uv_outside_path_and_repeat_uninstall_preserve_data(self):
        self.assertEqual(self.run_script().returncode, 0)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(self.run_script().returncode, 0)
        self.assertEqual(self.data.read_text(), 'keep user data')
        self.assertTrue((self.bin/'uv').exists())

    def test_failed_uninstall_does_not_claim_success(self):
        self.env['FAKE_FAIL'] = '1'
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('42TUI uninstalled.', result.stdout)
        self.assertTrue(self.receipt.exists())

    def test_help_and_unknown_arguments_do_not_uninstall(self):
        self.assertEqual(self.run_script('--help').returncode, 0)
        self.assertNotEqual(self.run_script('--purge').returncode, 0)
        self.assertTrue(self.receipt.exists())


@unittest.skipIf(os.name == 'nt' or not shutil.which('uv'), 'Real POSIX uv lifecycle')
class RealMaintenanceTests(unittest.TestCase):
    def test_running_cli_can_uninstall_its_own_uv_environment(self):
        with tempfile.TemporaryDirectory(prefix='42tui self uninstall ') as directory:
            home = Path(directory)
            info = 'ft_tui-0.2.2.dist-info/'
            # Package the actual maintenance entry point without unrelated TUI
            # dependencies, and install by package name to produce a uv receipt.
            files = {
                'ft_tui/__init__.py': '', 'ft_tui/services/__init__.py': '',
                'ft_tui/main.py': (ROOT/'src/ft_tui/main.py').read_text(),
                'ft_tui/services/installation.py': (ROOT/'src/ft_tui/services/installation.py').read_text(),
                info+'METADATA': 'Metadata-Version: 2.1\nName: ft-tui\nVersion: 0.2.2\n',
                info+'WHEEL': 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
                info+'entry_points.txt': '[console_scripts]\n42tui = ft_tui.main:main\n',
            }
            for name in ('features/__init__.py', 'features/installation/__init__.py',
                         'features/installation/adapters/__init__.py',
                         'features/installation/adapters/maintenance.py'):
                files['ft_tui/'+name] = (ROOT/'src/ft_tui'/name).read_text()
            files[info+'RECORD'] = ''.join(f'{name},,\n' for name in files) + info+'RECORD,,\n'
            wheel = home/'ft_tui-0.2.2-py3-none-any.whl'
            with zipfile.ZipFile(wheel, 'w') as archive:
                for name, content in files.items():
                    archive.writestr(name, content)
            env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home/'data'),
                       UV_TOOL_DIR=str(home/'tools'), UV_TOOL_BIN_DIR=str(home/'bin'),
                       UV_CACHE_DIR=str(home/'cache'), UV_OFFLINE='1', UV_PYTHON_DOWNLOADS='never')
            env.pop('PYTHONPATH', None)
            installed = subprocess.run([shutil.which('uv'), '--no-config', 'tool', 'install', '--python', sys.executable,
                                        '--no-index', '--find-links', str(home), 'ft-tui==0.2.2'],
                                       env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(installed.returncode, 0, installed.stderr)
            updated = subprocess.run([str(home/'bin/42tui'), 'update'], env=env,
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
            sentinel = home/'data/preserve.txt'
            sentinel.parent.mkdir(parents=True, exist_ok=True)
            sentinel.write_text('local data')
            result = subprocess.run([str(home/'bin/42tui'), 'remove'], env=env,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((home/'bin/42tui').exists())
            self.assertEqual(sentinel.read_text(), 'local data')
