"""Real uv must accept a second install of the candidate package."""
from email.message import EmailMessage
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('uv'), 'uv is needed for the real tool lifecycle')
class InstallerLifecycleTests(unittest.TestCase):
    def test_candidate_wheel_can_be_installed_twice_then_removed(self):
        with tempfile.TemporaryDirectory(prefix='42tui lifecycle ') as directory:
            root = Path(directory)
            wheel = root/'ft_tui-0.2.0-py3-none-any.whl'
            # Minimal real wheel: tests actual uv receipt/ownership semantics without network deps.
            files = {
                'ft_tui/__init__.py': '',
                'ft_tui/main.py': 'def main():\n    print("42tui 0.2.0")\n',
                'ft_tui-0.2.0.dist-info/METADATA': 'Metadata-Version: 2.1\nName: ft-tui\nVersion: 0.2.0\n',
                'ft_tui-0.2.0.dist-info/WHEEL': 'Wheel-Version: 1.0\nGenerator: fixture\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
                'ft_tui-0.2.0.dist-info/entry_points.txt': '[console_scripts]\n42tui = ft_tui.main:main\n42goto = ft_tui.main:main\n42tui-zed-lsp = ft_tui.main:main\n',
            }
            files['ft_tui-0.2.0.dist-info/RECORD'] = ''.join(f'{name},,\n' for name in files) + 'ft_tui-0.2.0.dist-info/RECORD,,\n'
            with zipfile.ZipFile(wheel, 'w') as archive:
                for name, data in files.items():
                    archive.writestr(name, data)
            env = dict(os.environ, UV_CACHE_DIR=str(root/'cache'), UV_PYTHON_DOWNLOADS='never',
                       UV_PYTHON=sys.executable, UV_OFFLINE='1')
            uv = shutil.which('uv')
            if os.name != 'nt':
                # CI installs uv and the candidate package into the same bin
                # directory. That unrelated 42tui must stay outside the smoke PATH.
                manager_bin = root/'manager bin'
                manager_bin.mkdir()
                (manager_bin/'uv').symlink_to(uv)
                unrelated = manager_bin/'42tui'
                unrelated.write_text('#!/bin/sh\nexit 99\n')
                unrelated.chmod(0o755)
                uv = str(manager_bin/'uv')
                env['PATH'] = str(manager_bin) + os.pathsep + env['PATH']
            result = subprocess.run([sys.executable, str(ROOT/'release/smoke_install.py'), str(wheel), uv],
                                    env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Fresh/repeat/exact-version', result.stdout)
            if os.name != 'nt':
                self.assertEqual(unrelated.read_text(), '#!/bin/sh\nexit 99\n')
