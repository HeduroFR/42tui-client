"""Public metadata, installation boundaries and post-exit update verification."""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from ft_tui.services.updates import (
    Installation, apply_update, detect_installation, latest_stable, release_notes, stable_version,
)


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
        with patch('ft_tui.services.updates.detect_installation', return_value=self.installation):
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
        with patch('ft_tui.services.updates.detect_installation', return_value=None):
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


class MainUpdateTests(unittest.TestCase):
    def test_install_only_after_normal_exit_and_with_optin_still_enabled(self):
        from contextlib import ExitStack
        from ft_tui.main import main
        for enabled, crashes in ((True, False), (False, False), (True, True)):
            with self.subTest(enabled=enabled, crashes=crashes), ExitStack() as stack:
                events = []
                stack.enter_context(patch('sys.argv', ['42tui']))
                stack.enter_context(patch('ft_tui.db.initialize_database'))
                stack.enter_context(patch('ft_tui.api.client_factory.provider_for_device'))
                stack.enter_context(patch('ft_tui.api.oauth_client.OAuthClient'))
                stack.enter_context(patch('ft_tui.config.settings.data_dir', return_value=Path('/unused')))
                stack.enter_context(patch('ft_tui.config.settings.database_url', return_value='sqlite://'))
                service = SimpleNamespace(installation=object())
                stack.enter_context(patch('ft_tui.services.updates.UpdateService.for_current_installation',
                                          return_value=service))
                app = stack.enter_context(patch('ft_tui.ui.app.FortyTwoTuiApp')).return_value
                app.pending_update = '0.3.0'
                app.automatic_updates_enabled.return_value = enabled
                def run():
                    events.append('exit')
                    if crashes:
                        raise RuntimeError('UI failed')
                app.run.side_effect = run
                installer = stack.enter_context(patch('ft_tui.services.updates.apply_update',
                                                      side_effect=lambda *args: events.append('install')))
                stack.enter_context(patch('builtins.print'))
                if crashes:
                    with self.assertRaises(RuntimeError):
                        main()
                else:
                    main()
                self.assertEqual(events, ['exit', 'install'] if enabled and not crashes else ['exit'])
                self.assertEqual(installer.call_count, int(enabled and not crashes))
