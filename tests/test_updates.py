"""Public metadata, installation boundaries and pre-launch update verification."""
import json
import os
import sys
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from ft_tui.features.installation.adapters.runtime import Installation, apply_update, detect_installation, latest_stable, release_notes, stable_version


class ReleaseCheckTests(unittest.TestCase):
    def check(self, payload, status=200):
        def response(request):
            self.assertEqual(str(request.url), 'https://pypi.org/pypi/ft-tui/json')
            self.assertNotIn('authorization', request.headers)
            return httpx.Response(status, json=payload)
        with httpx.Client(transport=httpx.MockTransport(response)) as client:
            return latest_stable(client)

    def test_stable_non_yanked_releases_only(self):
        self.assertEqual(self.check({'info': {'name': 'ft-tui'}, 'releases': {
            '0.3.0': [{'yanked': False}], '0.10.0': [{'yanked': False}],
            '1.0.0rc1': [{'yanked': False}], '2.0.0': [{'yanked': True}],
            '3.0.0': [], '0.11.0': [{}],
        }}), '0.10.0')
        for version in ('v1.0.0', '01.2.3', '1.2', '1.2.3.dev1', None):
            self.assertIsNone(stable_version(version))

    def test_invalid_metadata_and_http_error(self):
        for payload in ([], {}, {'info': []}, {'info': {'name': 'other'}},
                        {'info': {'name': 'ft-tui'}, 'releases': []}):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.check(payload)
        with self.assertRaises(httpx.HTTPStatusError):
            self.check({}, 503)

    def test_oversized_response(self):
        transport = httpx.MockTransport(lambda r: httpx.Response(200, content=b' ' * (2*1024*1024+1)))
        with httpx.Client(transport=transport) as client, self.assertRaises(ValueError):
            latest_stable(client)

    def test_notes_only_include_crossed_releases(self):
        text = '# Changelog\n## 0.4.0\nfuture\n## 0.3.0\nnew\n## 0.2.2\nfix\n## 0.2.0\nold\n'
        notes = release_notes('0.2.0', '0.3.0', text)
        self.assertIn('fix', notes)
        self.assertIn('new', notes)
        self.assertNotIn('future', notes)
        self.assertNotIn('old', notes)
        self.assertTrue(notes.startswith('## 0.3.0'))
        self.assertEqual(release_notes('0.3.0', '0.3.0', text), '')


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prefix = Path(self.tmp.name) / 'venvs' / 'ft-tui'
        self.cli = self.prefix / 'bin' / '42tui'
        self.cli.parent.mkdir(parents=True)
        self.cli.touch()
        self.dist = SimpleNamespace(version='0.2.2', read_text=lambda key: None,
                                    locate_file=lambda key: self.prefix / 'lib')
        self.installation = Installation('uv', '/fake/uv', self.prefix, self.cli, '0.2.2')

    def detect(self):
        return detect_installation(prefix=self.prefix, distribution=self.dist, which=lambda name: '/fake/'+name)

    def uv_receipt(self, specifier=''):
        (self.prefix / 'uv-receipt.toml').write_text(
            '[tool]\nrequirements = [{name="ft-tui", specifier="'+specifier+'"}]\n'
            'entrypoints = [{install-path="'+str(self.cli)+'"}]\n')

    def test_uv_managed_and_pinned(self):
        self.assertIsNone(self.detect())
        self.uv_receipt()
        self.assertEqual(self.detect().manager, 'uv')
        self.uv_receipt('==0.2.2')
        self.assertIsNone(self.detect())
        self.uv_receipt()
        self.dist.read_text = lambda key: '{"dir_info":{"editable":true}}'
        self.assertIsNone(self.detect())

    def test_pipx_and_malformed_receipt(self):
        receipt = self.prefix / 'pipx_metadata.json'
        receipt.write_text(json.dumps({'main_package': {'package': 'ft-tui', 'package_or_url': 'ft-tui'}}))
        self.assertEqual(self.detect().manager, 'pipx')
        receipt.write_text(json.dumps({'main_package': {'package': 'ft-tui', 'package_or_url': 'ft-tui',
                                                       'pip_args': ['--pre']}}))
        self.assertIsNone(self.detect())
        receipt.write_text(json.dumps({'main_package': {'package': 'ft-tui', 'package_or_url': 'ft-tui==0.2.2'}}))
        self.assertIsNone(self.detect())
        receipt.write_text('invalid')
        self.assertIsNone(self.detect())
        self.uv_receipt()
        (self.prefix / 'uv-receipt.toml').write_text('[tool]\nrequirements=["bad"]')
        self.assertIsNone(self.detect())

    def fake_run(self, *, after='0.3.0', directory=None, failure=False):
        self.calls = []
        versions = iter(['0.2.2', after])
        def run(command, **kwargs):
            self.calls.append(command)
            self.assertNotIn('shell', kwargs)
            if '--version' in command:
                return SimpleNamespace(stdout='42tui '+next(versions)+'\n')
            if command[-1] == 'dir' or command[-1] == 'PIPX_LOCAL_VENVS':
                return SimpleNamespace(stdout=str(directory or self.prefix.parent)+'\n')
            if failure:
                raise subprocess.CalledProcessError(1, command)
            return SimpleNamespace(stdout='')
        return run

    def apply(self, run):
        with patch('ft_tui.features.installation.adapters.runtime.detect_installation', return_value=self.installation):
            return apply_update(self.installation, '0.3.0', self.tmp.name, run=run)

    def test_upgrade_and_verify(self):
        self.assertEqual(self.apply(self.fake_run()), '0.3.0')
        self.assertIn('upgrade', self.calls[2])
        self.assertIn('https://pypi.org/simple', self.calls[2])

    def test_wrong_manager_environment_never_installs(self):
        with self.assertRaises(ValueError):
            self.apply(self.fake_run(directory=Path('/different')))
        self.assertEqual(len(self.calls), 2)

    def test_pipx_upgrade_and_verify(self):
        self.installation = Installation('pipx', '/fake/pipx', self.prefix, self.cli, '0.2.2')
        self.assertEqual(self.apply(self.fake_run()), '0.3.0')
        self.assertEqual(self.calls[1][-1], 'PIPX_LOCAL_VENVS')
        self.assertEqual(self.calls[2][1:3], ['upgrade', 'ft-tui'])

    def test_installation_changed_after_check(self):
        with patch('ft_tui.features.installation.adapters.runtime.detect_installation', return_value=None):
            with self.assertRaises(ValueError):
                apply_update(self.installation, '0.3.0', self.tmp.name, run=self.fake_run())
        self.assertEqual(len(self.calls), 1)

    def test_failed_or_unchanged_upgrade_and_lock_recovery(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.apply(self.fake_run(failure=True))
        with self.assertRaises(ValueError):
            self.apply(self.fake_run(after='0.2.2'))
        self.assertEqual(self.apply(self.fake_run()), '0.3.0')

    def test_concurrent_update_is_skipped(self):
        import fcntl
        with (Path(self.tmp.name)/'update.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertIsNone(self.apply(self.fake_run()))
            self.assertEqual(self.calls, [])


class PrelaunchUpdateTests(unittest.TestCase):
    def setUp(self):
        from ft_tui.features.installation.service import InstallationService
        self.values = {}
        prefs = SimpleNamespace(get=lambda key, default='': self.values.get(key, default),
                                save=self.values.update)
        self.policy = InstallationService(prefs)
        self.installation = Installation('uv', '/fake/uv', Path('/fake/ft-tui'),
                                         Path('/fake/ft-tui/bin/42tui'), '0.3.0')

    def prepare(self, check, *, installation=True, installed='0.4.0', error=None):
        from ft_tui.features.installation.adapters.runtime import UpdateService
        service = UpdateService(current='0.3.0', installation=self.installation if installation else None,
                                check=check)
        with patch('ft_tui.features.installation.adapters.runtime.apply_update',
                   return_value=installed, side_effect=error) as upgrade, patch('builtins.print'):
            restart = service.update_before_launch(self.policy, Path('/unused'))
        return restart, upgrade.call_count

    def test_new_release_updates_before_launch_and_preserves_previous_version_for_notes(self):
        self.assertEqual(self.prepare(lambda: '0.4.0'), (True, 1))
        self.assertEqual(self.values['updates:last_seen_version'], '0.3.0')
        self.assertIn('updates:last_check', self.values)

    def test_recent_check_does_not_hide_a_new_release_on_launch(self):
        self.values['updates:last_check'] = '9999999999'
        self.assertEqual(self.prepare(lambda: '0.4.0'), (True, 1))

    def test_optout_and_unmanaged_installations_do_not_contact_pypi(self):
        contacted = []
        def unexpected():
            contacted.append(True)
            return '0.4.0'
        self.assertEqual(self.prepare(unexpected, installation=False), (False, 0))
        self.values['automatic_updates'] = 'false'
        self.assertEqual(self.prepare(unexpected), (False, 0))
        self.assertEqual(contacted, [])

    def test_offline_and_non_newer_releases_launch_without_installing(self):
        def offline():
            raise OSError('offline')
        for check in (offline, lambda: None, lambda: '0.3.0', lambda: '0.2.2', lambda: '0.5.0rc1'):
            with self.subTest(check=check):
                self.assertEqual(self.prepare(check), (False, 0))

    def test_optout_during_metadata_check_prevents_installation(self):
        def check():
            self.values['automatic_updates'] = 'false'
            return '0.4.0'
        self.assertEqual(self.prepare(check), (False, 0))

    def test_failed_upgrade_restarts_cleanly_without_retrying_in_the_same_launch(self):
        self.assertEqual(self.prepare(lambda: '0.4.0', error=OSError('failed')), (True, 1))

    def test_concurrent_upgrade_never_opens_the_ui_during_package_changes(self):
        with self.assertRaises(SystemExit):
            self.prepare(lambda: '0.4.0', installed=None)


class MainUpdateTests(unittest.TestCase):
    def run_main(self, *, restart=False, skip=False, exec_error=None):
        from contextlib import ExitStack
        from ft_tui.main import main
        from ft_tui.db.database import make_session_factory
        events = []
        factory = make_session_factory('sqlite://')
        self.addCleanup(factory.kw['bind'].dispose)
        with ExitStack() as stack:
            stack.enter_context(patch('sys.argv', ['42tui']))
            stack.enter_context(patch.dict('os.environ', {'_42TUI_UPDATE_CHECKED': '1' if skip else ''}))
            stack.enter_context(patch('ft_tui.db.initialize_database', return_value=factory))
            stack.enter_context(patch('ft_tui.config.settings.database_url', return_value='sqlite://'))
            stack.enter_context(patch('ft_tui.api.client_factory.provider_for_device'))
            stack.enter_context(patch('ft_tui.api.oauth_client.OAuthClient'))
            stack.enter_context(patch('ft_tui.config.settings.data_dir', return_value=Path('/unused')))
            def prepare(*args):
                events.append('check/update')
                return restart
            service = SimpleNamespace(installation=SimpleNamespace(executable=Path('/fake/42tui')),
                                      update_before_launch=prepare)
            stack.enter_context(patch('ft_tui.features.installation.adapters.runtime.UpdateService.for_current_installation',
                                      return_value=service))
            def construct(*args, **kwargs):
                events.append('construct UI')
                def run():
                    events.append('run UI')
                return SimpleNamespace(run=run)
            stack.enter_context(patch('ft_tui.ui.app.FortyTwoTuiApp', side_effect=construct))
            def execute(path, args, environment):
                events.append(('restart', path, args, environment['_42TUI_UPDATE_CHECKED']))
                if exec_error:
                    raise exec_error
            stack.enter_context(patch('os.execve', side_effect=execute))
            stack.enter_context(patch('builtins.print'))
            if exec_error:
                with self.assertRaises(SystemExit):
                    main()
            else:
                main()
            import os
            self.assertNotIn('_42TUI_UPDATE_CHECKED', os.environ)
        return events

    def test_check_precedes_ui_and_no_install_runs_after_exit(self):
        self.assertEqual(self.run_main(), ['check/update', 'construct UI', 'run UI'])

    def test_successful_update_restarts_installed_entrypoint_before_any_ui_is_constructed(self):
        self.assertEqual(self.run_main(restart=True),
                         ['check/update', ('restart', '/fake/42tui', ['/fake/42tui'], '1')])

    def test_restarted_process_consumes_guard_and_does_not_check_or_install_twice(self):
        self.assertEqual(self.run_main(skip=True), ['construct UI', 'run UI'])

    def test_failed_restart_does_not_run_a_mix_of_old_and_new_code(self):
        self.assertEqual(self.run_main(restart=True, exec_error=OSError('cannot execute')),
                         ['check/update', ('restart', '/fake/42tui', ['/fake/42tui'], '1')])


@unittest.skipIf(os.name == 'nt', 'POSIX automatic updates')
class PrelaunchProcessTests(unittest.TestCase):
    def test_upgrade_or_failure_hands_off_once_before_the_ui_imports(self):
        from textwrap import dedent
        for failed in (False, True):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory(prefix='42tui launch ') as directory:
                root = Path(directory)
                executable = root/'42tui'
                events = root/'events'
                new_code = f"#!{sys.executable}\nfrom pathlib import Path\np=Path({str(events)!r}); p.write_text(p.read_text()+'new UI\\n')\n"
                script = dedent("""
                    import importlib.abc, os, sys
                    from pathlib import Path
                    from types import ModuleType, SimpleNamespace
                    from ft_tui.features.installation.adapters import runtime
                    root = Path(ROOT)
                    events = root/'events'
                    def record(value):
                        with events.open('a') as stream:
                            stream.write(value+'\\n')
                    class Guard(importlib.abc.MetaPathFinder):
                        def find_spec(self, fullname, path=None, target=None):
                            if fullname.startswith(('ft_tui.ui', 'ft_tui.api')):
                                raise RuntimeError('UI or account import before update: '+fullname)
                    if os.environ.get('_42TUI_UPDATE_CHECKED'):
                        for name in ('ft_tui.api.client_factory','ft_tui.api.oauth_client','ft_tui.ui.app'):
                            sys.modules[name] = ModuleType(name)
                        sys.modules['ft_tui.api.client_factory'].provider_for_device = lambda client: None
                        sys.modules['ft_tui.api.oauth_client'].OAuthClient = lambda url, **kwargs: None
                        sys.modules['ft_tui.ui.app'].FortyTwoTuiApp = lambda *a, **kw: SimpleNamespace(run=lambda: record('old UI'))
                    else:
                        sys.meta_path.insert(0, Guard())
                    def check():
                        record('check')
                        return '0.4.0'
                    def apply(*args):
                        record('install')
                        if FAILED:
                            raise OSError('simulated package manager failure')
                        (root/'42tui').write_text(NEW_CODE)
                        return '0.4.0'
                    runtime.apply_update = apply
                    runtime.UpdateService.for_current_installation = classmethod(lambda cls: cls(
                        current='0.3.0', installation=runtime.Installation('uv','unused',root,root/'42tui','0.3.0'), check=check))
                    sys.argv = [str(root/'42tui')]
                    from ft_tui.main import main
                    main()
                """).replace('ROOT',repr(str(root))).replace('FAILED',repr(failed)).replace('NEW_CODE',repr(new_code))
                executable.write_text(f'#!{sys.executable}\n'+script)
                executable.chmod(0o755)
                env = dict(os.environ, HOME=str(root), XDG_DATA_HOME=str(root/'data'),
                           FT_TUI_DATABASE=str(root/'test.sqlite3'))
                env.pop('_42TUI_UPDATE_CHECKED', None)
                result = subprocess.run([str(executable)], env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(events.read_text().splitlines(), ['check','install','old UI' if failed else 'new UI'])
