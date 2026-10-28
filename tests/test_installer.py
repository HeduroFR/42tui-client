"""Installer behavior with disposable tool homes and an external uv double."""
from contextlib import redirect_stdout, redirect_stderr
import ast
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
        self.fail_install = False
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
            code = 1 if self.fail_install else 0
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
        self.fail_install = True
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
    def test_install_configures_both_shells_regardless_of_shell_environment(self):
        with patch.dict(os.environ, {'SHELL': '/bin/sh', 'ZDOTDIR': ''}):
            result, output = self.install()
        self.assertEqual(result, 0)
        for name in ('.bashrc', '.zshrc'):
            self.assertTrue((self.home/name).is_file(), name)
            self.assertIn(str(self.home/name), output)
        self.assertIn('source ', output)

    @unittest.skipIf(os.name == 'nt', 'POSIX shell startup files')
    def test_shell_blocks_update_in_place_and_preserve_surrounding_content(self):
        for shell in ('bash', 'zsh'):
            with self.subTest(shell=shell), patch.dict(os.environ, {'ZDOTDIR': ''}):
                rc = self.home/f'.{shell}rc'
                rc.write_text('# User settings without final newline')
                self.installer.configure_shell_path(self.bin, shell)
                first = rc.read_text()
                self.installer.configure_shell_path(self.bin, shell)
                self.assertEqual(rc.read_text(), first)
                rc.write_text(first + '# Later settings\n')
                new_bin = self.home/'new bin'
                self.installer.configure_shell_path(new_bin, shell)
                updated = rc.read_text()
                self.assertTrue(updated.startswith('# User settings without final newline\n'))
                self.assertTrue(updated.endswith('# <<< 42TUI shell setup <<<\n'))
                self.assertIn('# Later settings\n', updated)
                self.assertNotIn(str(self.bin), updated)
                self.assertEqual(updated.count('# >>> 42TUI shell setup >>>'), 1)

    @unittest.skipIf(os.name == 'nt', 'POSIX shell startup files')
    def test_zdotdir_symlink_and_permissions_are_preserved(self):
        directory = self.home/'zsh config'
        directory.mkdir()
        target = self.home/'actual rc'
        target.write_bytes(b'# Existing settings\r\n')
        target.chmod(0o640)
        rc = directory/'.zshrc'
        rc.symlink_to(target)
        with patch.dict(os.environ, {'ZDOTDIR': str(directory)}):
            self.assertEqual(self.installer.configure_shell_path(self.bin, 'zsh'), rc)
        self.assertTrue(rc.is_symlink())
        self.assertTrue(target.read_bytes().startswith(b'# Existing settings\r\n'))
        self.assertEqual(target.stat().st_mode & 0o777, 0o640)

    @unittest.skipIf(os.name == 'nt', 'POSIX shell startup files')
    def test_malformed_block_is_preserved_and_other_shell_still_configured(self):
        rc = self.home/'.bashrc'
        original = '# >>> 42TUI shell setup >>>\n# User content\n'
        rc.write_text(original)
        with patch.dict(os.environ, {'ZDOTDIR': ''}):
            result, _ = self.install()
        self.assertEqual(result, 0)
        self.assertEqual(rc.read_text(), original)
        self.assertTrue((self.home/'.zshrc').is_file())

    @unittest.skipIf(os.name == 'nt', 'POSIX shell startup files')
    def test_unwritable_bashrc_does_not_prevent_zsh_setup(self):
        # A directory at the rc path reliably fails even under privileged CI.
        (self.home/'.bashrc').mkdir()
        with patch.dict(os.environ, {'ZDOTDIR': ''}):
            self.assertEqual(self.install()[0], 0)
        self.assertTrue((self.home/'.zshrc').is_file())

    @unittest.skipIf(os.name == 'nt', 'POSIX shell execution')
    def test_real_shell_navigation_completion_and_uninstall_are_quiet(self):
        tree = ast.parse((ROOT/'src/ft_tui/goto.py').read_text())
        initializers = {node.targets[0].id: ast.literal_eval(node.value)
                        for node in tree.body if isinstance(node, ast.Assign)}
        project = self.home/'project directory'
        project.mkdir()
        command = self.bin/'42goto'
        for shell, key in (('bash', '_BASH_INIT'), ('zsh', '_ZSH_INIT')):
            executable = shutil.which(shell)
            if not executable:
                self.skipTest(f'{shell} unavailable')
            # Execute the production shell initializer with a disposable CLI/data source.
            command.write_text('#!/bin/sh\ncase "$1" in\n'
                               "--shell-init) cat <<'INIT'\n" + initializers[key] +
                               '\nINIT\n;;\n--path) printf "%s\\n" "$TEST_PROJECT";;\n'
                               '--complete) printf "%s\\n" "libft" "get_next_line";;\nesac\n')
            command.chmod(0o755)
            with patch.dict(os.environ, {'ZDOTDIR': ''}):
                rc = self.installer.configure_shell_path(self.bin, shell)
            completion = ('COMP_WORDS=(42goto ""); COMP_CWORD=1; _42goto_complete; '
                          'printf "%s\\n" "${COMPREPLY[@]}"' if shell == 'bash' else
                          '(( $+functions[compdef] )) && (( $+functions[_42goto] ))')
            script = 'set -e; . "$1"; . "$1"; 42goto libft; pwd; ' + completion + '; printf "%s\\n" "$PATH"'
            env = dict(os.environ, PATH='/usr/bin:/bin', TEST_PROJECT=str(project))
            result = subprocess.run([executable, '-f' if shell == 'zsh' else '--noprofile',
                                     '-c', script, 'test', str(rc)], env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            self.assertIn(str(project), result.stdout.splitlines())
            if shell == 'bash':
                self.assertIn('get_next_line', result.stdout.splitlines())
            paths = result.stdout.splitlines()[-1].split(':')
            self.assertEqual(paths.count(str(self.bin)), 1)
            self.assertEqual(paths.count(str(self.home/'.local/bin')), 1)
            command.unlink()
            result = subprocess.run([executable, '-c', '. "$1"', 'test', str(rc)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))

    @unittest.skipIf(os.name == 'nt', 'POSIX shell execution')
    def test_manual_function_is_preserved_and_shell_characters_remain_literal(self):
        bin_dir = self.home/'bin " $value `touch INJECTED`'
        bin_dir.mkdir()
        for shell in ('bash', 'zsh'):
            executable = shutil.which(shell)
            if not executable:
                self.skipTest(f'{shell} unavailable')
            rc = self.home/f'.{shell}rc'
            original = 'export PATH="$HOME/.local/bin:$PATH"\n42goto() { printf "manual\\n"; }\n'
            rc.write_text(original)
            with patch.dict(os.environ, {'ZDOTDIR': ''}):
                self.installer.configure_shell_path(bin_dir, shell)
            self.assertTrue(rc.read_text().startswith(original))
            result = subprocess.run([executable, '-c', '. "$1"; . "$1"; 42goto; printf "%s" "$PATH"',
                                     'test', str(rc)], cwd=self.home,
                                    env=dict(os.environ, PATH='/usr/bin:/bin'), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout.startswith('manual\n'))
            self.assertIn(str(bin_dir), result.stdout.splitlines()[-1].split(':'))
            self.assertFalse((self.home/'INJECTED').exists())

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
