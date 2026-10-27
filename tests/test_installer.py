"""Installer behavior with disposable tool homes and an external uv double."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_installer():
    spec = importlib.util.spec_from_file_location('installer', ROOT/'distribution/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.installer = load_installer()
        self.temp = tempfile.TemporaryDirectory(prefix='42tui installer ')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.bin = self.home/'bin'
        self.bin.mkdir()
        self.tools = self.home/'tools'
        self.calls = []
        self.fail = False
        self.bad_version = False
        self.env = patch.dict(os.environ, {'HOME': str(self.home), 'XDG_DATA_HOME': str(self.home/'data')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def run_command(self, args, **kwargs):
        self.calls.append(args)
        command = args[2:] if args[1:2] == ['--no-config'] else args[1:]
        output = ''
        code = 0
        if command == ['tool', 'dir', '--bin']:
            output = str(self.bin)
        elif command == ['tool', 'dir']:
            output = str(self.tools)
        elif command[:2] == ['tool', 'install']:
            code = 1 if self.fail else 0
            if not code:
                for name in self.installer.COMMANDS:
                    (self.bin / name).write_text('executable')
        elif args[-1:] == ['--version'] and Path(args[0]).name.startswith('42tui'):
            output = 'unexpected' if self.bad_version else '42tui 0.2.0'
        elif command[:2] == ['tool', 'update-shell']:
            output = ''
        else:
            raise AssertionError(args)
        if code and kwargs.get('check'):
            raise subprocess.CalledProcessError(code, args)
        return subprocess.CompletedProcess(args, code, output, '')

    def install(self, *args):
        with patch.object(self.installer.subprocess, 'run', side_effect=self.run_command), \
             patch.object(self.installer.shutil, 'which', return_value=None), \
             redirect_stdout(io.StringIO()) as output, redirect_stderr(io.StringIO()):
            result = self.installer.main(['--uv', '/fake uv', '--non-interactive', '--no-font', *args])
        return result, output.getvalue()

    def test_fresh_install_requests_compatible_python_without_force(self):
        result, output = self.install()
        self.assertEqual(result, 0)
        call = next(c for c in self.calls if 'install' in c)
        self.assertIn('>=3.12,<3.15', call)
        self.assertNotIn('--force', call)
        self.assertIn('ft-tui', call)
        self.assertIn('0.2.0', output)
        self.assertIn(str(self.bin), output)

    def test_exact_version_is_literal_and_allows_downgrade(self):
        result, _ = self.install('--version', '0.2.0')
        self.assertEqual(result, 0)
        call = next(c for c in self.calls if 'install' in c)
        self.assertIn('ft-tui==0.2.0', call)
        self.assertIn('--reinstall', call)

    def test_invalid_version_fails_before_invoking_uv(self):
        with self.assertRaises(SystemExit):
            self.install('--version', '0.2.0; echo bad')
        self.assertEqual(self.calls, [])

    def test_failed_install_never_reports_success(self):
        self.fail = True
        result, output = self.install()
        self.assertNotEqual(result, 0)
        self.assertNotIn('Installed 42tui', output)

    def test_failed_verification_never_reports_success(self):
        self.bad_version = True
        result, output = self.install()
        self.assertNotEqual(result, 0)
        self.assertNotIn('Installed 42tui', output)

    def test_existing_unmanaged_executable_is_preserved(self):
        existing = self.bin/'42tui'
        existing.write_text('editable checkout')
        result, _ = self.install()
        self.assertNotEqual(result, 0)
        self.assertEqual(existing.read_text(), 'editable checkout')
        self.assertFalse(any('install' in c for c in self.calls))

    def test_font_hash_mismatch_writes_nothing(self):
        with patch.object(self.installer, 'download', return_value=b'bad archive'):
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                self.installer.install_font(self.home/'fonts', system='Linux')
        self.assertFalse((self.home/'fonts').exists())

    def test_font_archive_installs_only_mono_faces_and_license(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:xz') as archive:
            for name in ['JetBrainsMonoNerdFontMono-Regular.ttf', 'OFL.txt', '../../bad.ttf']:
                payload = b'fixture'
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
        content = data.getvalue()
        target = self.home/'fonts'
        with patch.object(self.installer, 'FONT_SHA256', hashlib.sha256(content).hexdigest()), \
             patch.object(self.installer, 'download', return_value=content), \
             patch.object(self.installer.shutil, 'which', return_value=None):
            self.installer.install_font(target, system='Linux')
        self.assertEqual((target/'JetBrainsMonoNerdFontMono-Regular.ttf').read_bytes(), b'fixture')
        self.assertTrue((target/'OFL.txt').exists())
        self.assertFalse((self.home/'bad.ttf').exists())

    def test_noninteractive_skips_prompt_and_font(self):
        with patch.object(self.installer, 'choose_font', side_effect=AssertionError('prompt')), \
             patch.object(self.installer, 'install_font', side_effect=AssertionError('font')):
            self.assertEqual(self.install()[0], 0)

    def test_repeat_install_accepts_only_receipt_owned_commands(self):
        tool = self.tools/'ft-tui'
        tool.mkdir(parents=True)
        entries = []
        for name in self.installer.COMMANDS:
            environment_bin = tool/('Scripts' if os.name == 'nt' else 'bin')
            environment_bin.mkdir(exist_ok=True)
            (environment_bin/name).write_text('managed')
            if os.name == 'nt':
                (self.bin/name).write_text('managed')
            else:
                (self.bin/name).symlink_to(environment_bin/name)
            entries.append('[[tool.entrypoints]]\nname = "' + name + '"\ninstall-path = "' + str(self.bin/name) + '"\n')
        (tool/'uv-receipt.toml').write_text('[tool]\nrequirements = [{name = "ft-tui"}]\n' + ''.join(entries))
        self.assertEqual(self.install()[0], 0)

    def test_uv_editable_install_requires_explicit_migration(self):
        tool = self.tools/'ft-tui'
        tool.mkdir(parents=True)
        (tool/'uv-receipt.toml').write_text('[tool]\nrequirements = [{name = "ft-tui", editable = "/dev/checkout"}]\n')
        self.assertNotEqual(self.install()[0], 0)
        self.assertFalse(any('install' in c for c in self.calls))

    def test_existing_font_is_preserved_without_download(self):
        target = self.home/'fonts'
        target.mkdir()
        for name in self.installer.FONT_FACES:
            (target/name).write_bytes(b'existing')
        with patch.object(self.installer, 'download', side_effect=AssertionError('download')):
            self.installer.install_font(target, system='Linux')
        self.assertTrue(all(p.read_bytes() == b'existing' for p in target.iterdir()))

    def test_no_controlling_terminal_skips_font(self):
        with patch('builtins.open', side_effect=OSError('no tty')):
            self.assertFalse(self.installer.choose_font())

    def test_pending_shell_path_update_does_not_fail_verified_install(self):
        real = self.run_command
        def shell_pending(args, **kwargs):
            if args[-2:] == ['tool', 'update-shell']:
                return subprocess.CompletedProcess(args, 2, '', 'Configuration already updated; restart shell')
            return real(args, **kwargs)
        self.run_command = shell_pending
        result, output = self.install()
        self.assertEqual(result, 0)
        self.assertIn('Installed 42tui', output)

    @unittest.skipIf(os.name == 'nt', 'POSIX shell startup files')
    def test_bash_and_zsh_path_setup_is_persistent_and_idempotent(self):
        for shell, filename in (('/bin/bash', '.bashrc'), ('/bin/zsh', '.zshrc')):
            with self.subTest(shell=shell), patch.dict(os.environ, {'SHELL': shell, 'ZDOTDIR': ''}):
                rc = self.home/filename
                rc.write_text('# Existing user settings\n')
                self.assertEqual(self.installer.configure_shell_path(self.bin), rc)
                first = rc.read_text()
                self.installer.configure_shell_path(self.bin)
                self.assertEqual(rc.read_text(), first)
                self.assertTrue(first.startswith('# Existing user settings\n'))
                # Source the generated config twice in a real shell. Each path
                # must occur only once, including a HOME containing spaces.
                for executable in filter(None, (shutil.which('bash'), shutil.which('zsh'))):
                    result = subprocess.run([executable, '-c', '. "$1"; . "$1"; printf "%s" "$PATH"',
                                             'check', str(rc)], env=dict(os.environ, PATH='/usr/bin:/bin'),
                                            capture_output=True, text=True, check=True)
                    paths = result.stdout.split(':')
                    self.assertEqual(paths.count(str(self.home/'.local/bin')), 1)
                    self.assertEqual(paths.count(str(self.bin)), 1)

    @unittest.skipIf(os.name == 'nt', 'POSIX shell startup files')
    def test_existing_local_bin_exports_are_preserved(self):
        for value in ('export PATH="$HOME/.local/bin:$PATH"',
                      'export PATH="${PATH}:${HOME}/.local/bin"',
                      f'export PATH="{self.home}/.local/bin:$PATH"'):
            with self.subTest(value=value), patch.dict(os.environ, {'SHELL': '/bin/bash'}):
                rc = self.home/'.bashrc'
                rc.write_text(value + '\n')
                self.installer.configure_shell_path(self.home/'.local/bin')
                self.assertEqual(rc.read_text(), value + '\n')

    @unittest.skipIf(os.name == 'nt', 'POSIX shell startup files')
    def test_commented_export_is_not_treated_as_configured(self):
        with patch.dict(os.environ, {'SHELL': '/bin/bash'}):
            rc = self.home/'.bashrc'
            rc.write_text('# export PATH="$HOME/.local/bin:$PATH"\n')
            self.installer.configure_shell_path(self.home/'.local/bin')
            self.assertIn('# 42TUI: user executables', rc.read_text())

    @unittest.skipIf(os.name == 'nt', 'POSIX shell startup files')
    def test_zsh_uses_zdotdir_and_leaves_bashrc_untouched(self):
        directory = self.home/'zsh config'
        with patch.dict(os.environ, {'SHELL': '/bin/zsh', 'ZDOTDIR': str(directory)}):
            rc = self.installer.configure_shell_path(self.home/'.local/bin')
            self.assertEqual(rc, directory/'.zshrc')
            self.assertTrue(rc.is_file())
            self.assertFalse((self.home/'.bashrc').exists())

    @unittest.skipIf(os.name == 'nt', 'POSIX shell startup files')
    def test_supported_shell_is_configured_after_verified_install(self):
        with patch.dict(os.environ, {'SHELL': '/bin/bash'}):
            result, output = self.install()
        self.assertEqual(result, 0)
        self.assertTrue((self.home/'.bashrc').is_file())
        self.assertIn('PATH configured', output)
        self.assertFalse(any(c[-2:] == ['tool', 'update-shell'] for c in self.calls))

    @unittest.skipIf(os.name == 'nt', 'POSIX terminal contract')
    def test_font_prompt_works_with_a_nonseekable_terminal(self):
        import builtins
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        self.addCleanup(os.close, slave)
        original_open = builtins.open
        def terminal_open(name, mode):
            self.assertEqual(name, '/dev/tty')
            return original_open(os.dup(slave), mode)
        os.write(master, b'y\n')
        with patch.dict(os.environ, {'SSH_CONNECTION': '', 'WSL_DISTRO_NAME': ''}), \
             patch('builtins.open', side_effect=terminal_open):
            self.assertTrue(self.installer.choose_font())

    def test_stale_receipt_never_overwrites_replaced_launcher(self):
        tool = self.tools/'ft-tui'
        tool.mkdir(parents=True)
        existing = self.bin/'42tui'
        existing.write_text('another installation')
        (tool/'uv-receipt.toml').write_text('[tool]\nrequirements = [{name = "ft-tui"}]\n'
            + '[[tool.entrypoints]]\nname = "42tui"\ninstall-path = "' + str(existing) + '"\n')
        result, _ = self.install()
        self.assertNotEqual(result, 0)
        self.assertFalse(any('install' in c for c in self.calls))
        self.assertEqual(existing.read_text(), 'another installation')
