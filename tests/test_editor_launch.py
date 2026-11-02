"""Resolve the configured editor to a launcher, including Flatpak installs."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ft_tui.features.projects.adapters import editor


class EditorLaunchTests(unittest.TestCase):
    def test_native_executable_wins_and_skips_flatpak(self):
        with patch.object(editor.shutil, 'which', side_effect=lambda name: '/bin/code' if name == 'code' else None), \
             patch.object(editor.subprocess, 'run') as run:
            argv, terminal, missing = editor.editor_launch('vscode')
        self.assertEqual(argv, ['/bin/code'])
        self.assertFalse(terminal)
        self.assertIsNone(missing)
        run.assert_not_called()

    def test_flatpak_install_is_used_when_the_executable_is_not_on_path(self):
        def which(name):
            return '/usr/bin/flatpak' if name == 'flatpak' else None
        with patch.object(editor.shutil, 'which', side_effect=which), \
             patch.object(editor.subprocess, 'run', return_value=Mock(returncode=0)) as run:
            argv, terminal, missing = editor.editor_launch('vscode')
        self.assertEqual(argv, ['/usr/bin/flatpak', 'run', 'com.visualstudio.code'])
        self.assertFalse(terminal)
        self.assertIsNone(missing)
        self.assertEqual(run.call_args.args[0], ['/usr/bin/flatpak', 'info', 'com.visualstudio.code'])

    def test_missing_flatpak_app_reports_both_locations(self):
        def which(name):
            return '/usr/bin/flatpak' if name == 'flatpak' else None
        with patch.object(editor.shutil, 'which', side_effect=which), \
             patch.object(editor.subprocess, 'run', return_value=Mock(returncode=1)):
            argv, terminal, missing = editor.editor_launch('zed')
        self.assertIsNone(argv)
        self.assertFalse(terminal)
        self.assertEqual(missing, ('zed', 'dev.zed.Zed'))

    def test_no_flatpak_keeps_the_path_only_message(self):
        with patch.object(editor.shutil, 'which', return_value=None):
            argv, terminal, missing = editor.editor_launch('nvim')
        self.assertIsNone(argv)
        self.assertTrue(terminal)
        self.assertEqual(missing, ('nvim', None))

    def test_flatpak_probe_failure_is_treated_as_not_installed(self):
        def which(name):
            return '/usr/bin/flatpak' if name == 'flatpak' else None
        with patch.object(editor.shutil, 'which', side_effect=which), \
             patch.object(editor.subprocess, 'run', side_effect=OSError('no flatpak')):
            argv, terminal, missing = editor.editor_launch('vim')
        self.assertIsNone(argv)
        self.assertEqual(missing, ('vim', 'org.vim.Vim'))


class NavigationFlatpakTests(unittest.TestCase):
    def test_flatpak_prefix_is_used_for_the_launch(self):
        from contextlib import nullcontext
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from ft_tui.features.projects.views import navigation

        with TemporaryDirectory() as directory:
            host = Mock()
            host.favorite_editor = 'vscode'
            host.suspend.return_value = nullcontext()
            with patch.object(navigation, 'editor_launch',
                              return_value=(['/usr/bin/flatpak', 'run', 'com.visualstudio.code'], False, None)), \
                 patch.object(navigation.subprocess, 'Popen') as opened:
                navigation.ProjectNavigationMixin._open_path_in_editor(host, 'Synthetic', Path(directory))
            args = opened.call_args.args[0]
            self.assertEqual(args[:3], ['/usr/bin/flatpak', 'run', 'com.visualstudio.code'])
            self.assertEqual(args[-2:], ['--reuse-window', directory])
            self.assertEqual(opened.call_args.kwargs['cwd'], Path(directory))
