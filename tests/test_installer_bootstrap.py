"""Execute the shell entry point with fake external commands."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(os.name == 'nt', 'POSIX bootstrap; PowerShell is checked in Windows CI')
class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='42tui bootstrap ')
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.bin = self.home/'bin'
        self.bin.mkdir()
        self.env = dict(os.environ, HOME=str(self.home), TMPDIR=str(self.home),
                        PATH=str(self.bin)+os.pathsep+os.environ['PATH'], FAKE_HELPER=str(ROOT/'distribution/install.py'))
        self.log = self.home/'calls'
        self.env['FAKE_LOG'] = str(self.log)
        self.command('uv', '''#!/bin/sh
case "$*" in
 --version) echo 'uv 0.13.3';;
 *'python find'*) printf '%s\\n' "$FAKE_PYTHON";;
 *) exit 9;;
esac
''')
        self.command('fake-python', '#!/bin/sh\nprintf "%s\\n" "$@" > "$FAKE_LOG"\n')
        self.env['FAKE_PYTHON'] = str(self.bin/'fake-python')
        self.command('curl', '''#!/bin/sh
[ "${FAKE_DOWNLOAD_FAIL:-0}" = 0 ] || exit 22
while [ "$#" -gt 0 ]; do
 if [ "$1" = -o ]; then shift; target=$1; fi
 shift
done
cp "$FAKE_HELPER" "$target"
''')

    def command(self, name, content):
        p = self.bin/name
        p.write_text(content)
        p.chmod(0o755)

    def run_bootstrap(self, *args):
        return subprocess.run(['sh', str(ROOT/'distribution/install.sh'), *args],
                              env=self.env, stdin=subprocess.DEVNULL, capture_output=True, text=True)

    def test_arguments_are_forwarded_literally_and_temporary_files_removed(self):
        result = self.run_bootstrap('--version', '0.2.0', '--no-font', '--non-interactive')
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.log.read_text().splitlines()
        self.assertEqual(lines[1:], ['--uv', str(self.bin/'uv'), '--version', '0.2.0', '--no-font', '--non-interactive'])
        self.assertFalse(Path(lines[0]).exists())

    def test_failed_download_never_invokes_helper(self):
        self.env['FAKE_DOWNLOAD_FAIL'] = '1'
        result = self.run_bootstrap('--no-font')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_old_system_uv_reuses_compatible_user_copy(self):
        local = self.home/'.local/bin'
        local.mkdir(parents=True)
        shutil.copy2(self.bin/'uv', local/'uv')
        self.command('uv', '#!/bin/sh\necho "uv 0.11.7"\n')
        result = self.run_bootstrap('--no-font')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines()[2], str(local/'uv'))

    def test_incompatible_uv_bootstraps_user_copy(self):
        working_uv = self.home/'working-uv'
        shutil.copy2(self.bin/'uv', working_uv)
        installer = self.home/'uv-installer.sh'
        installer.write_text('#!/bin/sh\nmkdir -p "$UV_INSTALL_DIR"\ncp "$FAKE_WORKING_UV" "$UV_INSTALL_DIR/uv"\n')
        self.env['FAKE_WORKING_UV'] = str(working_uv)
        self.env['FAKE_UV_INSTALLER'] = str(installer)
        self.command('curl', '''#!/bin/sh
while [ "$#" -gt 0 ]; do
 if [ "$1" = -o ]; then shift; target=$1; fi
 shift
done
case "$target" in
 */uv.sh) cp "$FAKE_UV_INSTALLER" "$target";;
 *) cp "$FAKE_HELPER" "$target";;
esac
''')
        # Substitute only the synthetic upstream installer hash; continue to
        # verify the actual helper using the host's checksum executable.
        self.env['REAL_SHASUM'] = shutil.which('shasum') or ''
        self.env['REAL_SHA256SUM'] = shutil.which('sha256sum') or ''
        self.command('sha256sum', '''#!/bin/sh
case "$1" in
 */uv.sh) echo '320a286374f5306c4f8c807bd6a7d504dc318841457cf8f2194bee37fe02a2bd  uv.sh';;
 *) if [ -n "$REAL_SHA256SUM" ]; then exec "$REAL_SHA256SUM" "$@"; else exec "$REAL_SHASUM" -a 256 "$@"; fi;;
esac
''')
        for version in ('0.11.7', '0.13.2', '0.13.3-preview', 'invalid'):
            with self.subTest(version=version):
                self.command('uv', f'#!/bin/sh\necho "uv {version}"\n')
                local_uv = self.home/'.local/bin/uv'
                local_uv.unlink(missing_ok=True)
                result = self.run_bootstrap('--no-font')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.log.read_text().splitlines()[2], str(local_uv))
                self.assertIn(version, (self.bin/'uv').read_text())

    def test_corrupt_helper_is_rejected(self):
        bad = self.home/'bad.py'
        bad.write_text('raise Exception("must not run")')
        self.env['FAKE_HELPER'] = str(bad)
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_invalid_arguments_do_not_download(self):
        result = self.run_bootstrap('--version', '0.2.0; echo bad')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())

    def test_unsupported_platform_stops_before_download(self):
        self.command('uname', '#!/bin/sh\necho Unsupported\n')
        result = self.run_bootstrap()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.log.exists())
