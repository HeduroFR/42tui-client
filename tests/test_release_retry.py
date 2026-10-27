"""A retry may upload missing files, never replace an immutable package."""
import importlib.util
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ReleaseRetryTests(unittest.TestCase):
    def test_github_release_creates_or_resumes_draft_hidden_from_tag_lookup(self):
        spec = importlib.util.spec_from_file_location('github_release', ROOT/'release/github_release.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root/'dist').mkdir()
                (root/'dist/package.whl').write_bytes(b'original wheel')
                (root/'distribution').mkdir()
                for name in ('install.sh', 'install.ps1', 'install.py', 'uninstall.sh'):
                    (root/'distribution'/name).write_bytes(name.encode())
                (root/'CHANGELOG.md').write_text('## 0.3.0\n\nRelease notes.\n')
                remote = {'package.whl': b'original wheel'} if existing else {}
                release = {'tag_name': 'v0.3.0', 'draft': True,
                           'assets': [{'name': name} for name in remote]}
                state = {'exists': existing, 'created': 0, 'published': False, 'uploads': {}}

                def gh(*args, check=True):
                    if args[:2] == ('api', 'repos/example/project/releases/tags/v0.3.0'):
                        if check:
                            raise subprocess.CalledProcessError(1, args, stderr='HTTP 404')
                        return subprocess.CompletedProcess(args, 1, '', 'HTTP 404')
                    if args == ('api', 'repos/example/project/releases', '--paginate', '--slurp'):
                        # Place our draft on a later page among unrelated releases.
                        pages = [[{'tag_name': 'v0.2.2', 'draft': False, 'assets': []}],
                                 [release] if state['exists'] else []]
                        return subprocess.CompletedProcess(args, 0, json.dumps(pages), '')
                    if args[:2] == ('release', 'create'):
                        self.assertFalse(state['exists'], 'retry must reuse the existing draft')
                        state['exists'] = True
                        state['created'] += 1
                    elif args[:2] == ('release', 'upload'):
                        path = Path(args[3])
                        self.assertNotIn(path.name, remote, 'existing assets must be compared, never overwritten')
                        self.assertNotIn(path.name, state['uploads'])
                        state['uploads'][path.name] = path.read_bytes()
                    elif args[:2] == ('release', 'download'):
                        name = args[args.index('--pattern') + 1]
                        target = Path(args[args.index('--dir') + 1])
                        (target/name).write_bytes(remote[name])
                    elif args[:2] == ('release', 'edit'):
                        self.assertEqual(set(state['uploads']) | remote.keys(), {
                            'package.whl', 'install.sh', 'install.ps1', 'install.py', 'uninstall.sh', 'SHA256SUMS',
                        })
                        state['published'] = True
                    else:
                        self.fail(f'Unexpected GitHub command: {args}')
                    return subprocess.CompletedProcess(args, 0, '', '')

                previous = Path.cwd()
                try:
                    os.chdir(root)
                    with patch.dict(os.environ, RELEASE_TAG='v0.3.0', GITHUB_REPOSITORY='example/project'), patch.object(module, 'gh', gh):
                        module.main()
                finally:
                    os.chdir(previous)
                self.assertEqual(state['created'], 0 if existing else 1)
                self.assertTrue(state['published'])
                self.assertEqual((state['uploads'] | remote)['package.whl'], b'original wheel')

    def test_github_lookup_does_not_hide_permissions_or_server_errors(self):
        spec = importlib.util.spec_from_file_location('github_release', ROOT/'release/github_release.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for message in ('HTTP 403: Forbidden', 'HTTP 500: Internal Server Error'):
            with self.subTest(message=message), patch.object(module, 'gh', return_value=
                    subprocess.CompletedProcess([], 1, '', message)):
                with self.assertRaisesRegex(RuntimeError, message):
                    module.find_release('example/project', 'v0.3.0')

    def test_retry_keeps_only_missing_files_and_rejects_mismatch(self):
        spec = importlib.util.spec_from_file_location('prepare_publish', ROOT/'release/prepare_publish.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dist = root/'dist'
            dist.mkdir()
            (dist/'a.whl').write_bytes(b'wheel')
            (dist/'a.tar.gz').write_bytes(b'source')
            existing = [{'filename': 'a.whl', 'digests': {'sha256': hashlib.sha256(b'wheel').hexdigest()}}]
            module.prepare(dist, root/'pending', existing)
            self.assertEqual([p.name for p in (root/'pending').iterdir()], ['a.tar.gz'])
            existing[0]['digests']['sha256'] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'differs'):
                module.prepare(dist, root/'other', existing)
