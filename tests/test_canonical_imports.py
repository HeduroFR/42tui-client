"""Feature implementations have one owner and no legacy import facades."""
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / 'src/ft_tui'
SHARED_UI = {
    '__init__', 'app', 'button', 'commands', 'companion', 'companion_art', 'components', 'layout', 'modal',
    'navigation', 'onboarding', 'select', 'shortcuts', 'terminal_capabilities', 'username',
}
TRANSPORT = {'__init__', 'client_factory', 'client_interface', 'http_client', 'oauth_client'}


class CanonicalImportTests(unittest.TestCase):
    def test_top_level_packages_contain_only_shared_or_composition_code(self):
        for name in ('services', 'slots', 'cluster_map'):
            self.assertFalse((ROOT / name).exists(), name)
        self.assertEqual({p.stem for p in (ROOT / 'ui').glob('*.py')}, SHARED_UI)
        self.assertEqual({p.stem for p in (ROOT / 'api').glob('*.py')}, TRANSPORT)

    def test_source_imports_resolve_without_legacy_modules(self):
        for path in ROOT.rglob('*.py'):
            module = 'ft_tui.' + '.'.join(path.relative_to(ROOT).with_suffix('').parts)
            package = module.removesuffix('.__init__') if path.name == '__init__.py' else module.rpartition('.')[0]
            for node in ast.walk(ast.parse(path.read_text())):
                targets = []
                if isinstance(node, ast.ImportFrom):
                    targets = [importlib.util.resolve_name('.' * node.level + (node.module or ''), package)
                               if node.level else node.module or '']
                elif isinstance(node, ast.Import):
                    targets = [alias.name for alias in node.names]
                for target in targets:
                    if not target.startswith('ft_tui.'):
                        continue
                    relative = ROOT.joinpath(*target.split('.')[1:])
                    with self.subTest(source=path.relative_to(ROOT), target=target):
                        self.assertTrue(relative.with_suffix('.py').is_file() or (relative / '__init__.py').is_file())

    def test_feature_sources_are_not_module_aliases(self):
        for path in ROOT.rglob('*.py'):
            self.assertNotIn('_sys.modules[__name__]', path.read_text(), str(path))
