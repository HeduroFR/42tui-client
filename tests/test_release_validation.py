"""Reject wrong release versions and unintended archive contents."""
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class ReleaseValidationTests(unittest.TestCase):
    def test_version_tag_requires_exact_stable_project_version(self):
        version = tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
        for tag, good in [('v' + version, True), ('v9999.0.0', False), (version, False),
                          ('v' + version + 'rc1', False), ('v0' + version, False), ('v' + version + ';echo no', False)]:
            with self.subTest(tag=tag):
                result = subprocess.run([sys.executable, str(ROOT/'release/check_version.py'), tag],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode == 0, good, result.stderr)

    def test_archive_rejects_private_files(self):
        with tempfile.TemporaryDirectory() as directory:
            wheel = Path(directory)/'ft_tui-0.2.0-py3-none-any.whl'
            with zipfile.ZipFile(wheel, 'w') as archive:
                archive.writestr('ft_tui/.env', 'not a real secret')
            result = subprocess.run([sys.executable, str(ROOT/'release/check_package.py'), directory],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('forbidden', result.stderr.lower())
