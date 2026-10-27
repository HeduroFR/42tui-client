"""Installation core stays portable; historical patches keep one owner."""
import ast
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class InstallationBoundaryTests(unittest.TestCase):

    def test_core_imports_no_framework_or_external_io(self):
        from ft_tui.features.installation import service
        root=Path(service.__file__).parent
        for name in ('service','models','ports'):
            for node in ast.walk(ast.parse((root/(name+'.py')).read_text())):
                names=([node.module] if isinstance(node,ast.ImportFrom) and node.module else
                       [alias.name for alias in node.names] if isinstance(node,ast.Import) else [])
                for name in names:
                    self.assertFalse(name.startswith(('textual','sqlalchemy','httpx','subprocess','ft_tui.db','ft_tui.app','ft_tui.services')),name)

    def test_update_view_uses_injected_preferences_without_database(self):
        from ft_tui.features.installation.views.updates import UpdateMixin
        fake=SimpleNamespace(installation_service=SimpleNamespace(enabled=lambda:False))
        self.assertFalse(UpdateMixin.automatic_updates_enabled(fake))

    def test_source_notes_fallback_is_based_on_package_location(self):
        from ft_tui.features.installation.adapters import runtime
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);package=root/'src/ft_tui';package.mkdir(parents=True)
            (root/'CHANGELOG.md').write_text('## 0.4.0\nsource notes\n')
            with patch.object(runtime.resources,'files',side_effect=FileNotFoundError()), \
                 patch('ft_tui.__file__',str(package/'__init__.py')):
                self.assertIn('source notes',runtime.release_notes('0.3.0','0.4.0'))

    def test_runtime_factory_uses_detection_result(self):
        from ft_tui.features.installation.adapters.runtime import UpdateService
        installation=object()
        with patch('ft_tui.features.installation.adapters.runtime.detect_installation',return_value=installation), \
             patch('ft_tui.features.installation.adapters.runtime.metadata.version',return_value='0.3.0'):
            self.assertIs(UpdateService.for_current_installation().installation,installation)
