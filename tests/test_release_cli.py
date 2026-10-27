"""Release verification must never initialize application state."""
import importlib.metadata
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ReleaseCliTests(unittest.TestCase):
    def test_version_does_not_import_application_or_create_data(self):
        script = '''
import importlib.abc, sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('ft_tui.db', 'ft_tui.ui', 'ft_tui.api', 'ft_tui.services', 'ft_tui.config')):
            raise RuntimeError('application import: ' + fullname)
sys.meta_path.insert(0, Guard())
sys.argv = ['42tui', '--version']
from ft_tui.main import main
main()
'''
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home, XDG_DATA_HOME=home, PYTHONPATH=str(ROOT / 'src'))
            result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), '42tui ' + importlib.metadata.version('ft-tui'))
            self.assertEqual(list(Path(home).iterdir()), [])
