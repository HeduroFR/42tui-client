"""Checked-in manual fixtures must be checkable out on Windows."""
from pathlib import Path
import re
import unittest

FIXTURES = Path(__file__).resolve().parent/'manual/fixtures'


class FixturePortabilityTests(unittest.TestCase):
    def test_fixture_paths_use_windows_compatible_names(self):
        forbidden = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
        reserved = {'CON', 'PRN', 'AUX', 'NUL',
                    *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
        for path in FIXTURES.rglob('*'):
            with self.subTest(path=path.relative_to(FIXTURES)):
                self.assertIsNone(forbidden.search(path.name), 'Windows forbids this filename')
                self.assertFalse(path.name.endswith((' ', '.')), 'Windows strips trailing dots/spaces')
                self.assertNotIn(path.name.split('.')[0].upper(), reserved, 'Windows device name')
