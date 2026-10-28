"""Safe recovery and publishing against disposable local Git remotes."""
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ft_tui.features.projects.adapters.checkout import CheckoutSetupError, setup_project_checkout
from ft_tui.features.projects.adapters.git import (
    ProjectGitError, _safe_detail, plan_project_push, push_project,
)


class ProjectGitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.env = patch.dict(os.environ, {
            'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1',
            'GIT_AUTHOR_NAME': 'Test', 'GIT_AUTHOR_EMAIL': 'test@example.invalid',
            'GIT_COMMITTER_NAME': 'Test', 'GIT_COMMITTER_EMAIL': 'test@example.invalid',
            'GIT_TERMINAL_PROMPT': '0',
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.local = self.repo('local')
        self.dev = self.repo('development.git', bare=True)
        self.vog = self.repo('vogsphere.git', bare=True)
        self.git(self.local, 'remote', 'add', 'origin', str(self.dev))
        self.git(self.local, 'remote', 'add', 'vogsphere', str(self.vog))

    def git(self, root, *args, check=True):
        result = subprocess.run(('git', '-C', str(root), *args), capture_output=True, text=True)
        if check and result.returncode:
            self.fail(result.stderr)
        return result.stdout.strip()

    def repo(self, name, bare=False):
        root = self.root / name
        root.mkdir()
        self.git(root, 'init', '--initial-branch=work', *(['--bare'] if bare else []))
        if not bare:
            self.commit(root, 'initial' if name == 'local' else name)
        return root

    def commit(self, root, content):
        (root / 'main.c').write_text(content)
        self.git(root, 'add', 'main.c')
        self.git(root, 'commit', '-m', content)
        return self.git(root, 'rev-parse', 'HEAD')

    def publish_seed(self):
        self.git(self.local, 'push', 'origin', 'HEAD:refs/heads/work')
        self.git(self.local, 'push', 'vogsphere', 'HEAD:refs/heads/master')

    def test_vogsphere_work_is_recovered_instead_of_empty_development(self):
        self.git(self.local, 'push', 'vogsphere', 'HEAD:refs/heads/master')
        target = self.root / 'recovered'
        result = setup_project_checkout(target, dev_remote_url=str(self.dev), vogsphere_url=str(self.vog))
        self.assertTrue(result.cloned_vogsphere_remote)
        self.assertFalse(result.cloned_development_remote)
        self.assertEqual((target / 'main.c').read_text(), 'initial')
        self.assertEqual(self.git(target, 'branch', '--show-current'), 'master')
        self.assertEqual(self.git(target, 'remote', 'get-url', 'origin'), str(self.dev))

    def test_development_only_is_recovered_and_empty_remotes_initialize(self):
        self.git(self.local, 'push', 'origin', 'HEAD:refs/heads/work')
        result = setup_project_checkout(self.root / 'dev-clone', dev_remote_url=str(self.dev), vogsphere_url=str(self.vog))
        self.assertTrue(result.cloned_development_remote)
        empty = self.repo('empty.git', bare=True)
        result = setup_project_checkout(self.root / 'empty', dev_remote_url=str(empty), vogsphere_url=str(self.vog))
        self.assertTrue(result.created_repository)
        self.assertEqual(self.git(result.path, 'branch', '--show-current'), 'dev')

    def test_existing_dirty_checkout_keeps_files_index_branches_and_config(self):
        self.publish_seed()
        (self.local / 'main.c').write_text('staged')
        self.git(self.local, 'add', 'main.c')
        (self.local / 'main.c').write_text('unstaged')
        (self.local / '.gitignore').write_text('personal ignore\n')
        (self.local / 'notes').write_text('untracked')
        before = self.git(self.local, 'status', '--porcelain=v1')
        refs = self.git(self.local, 'show-ref')
        config = (self.local / '.git/config').read_bytes()
        setup_project_checkout(self.local, dev_remote_url=str(self.dev), vogsphere_url=str(self.vog))
        self.assertEqual(self.git(self.local, 'status', '--porcelain=v1'), before)
        self.assertEqual(self.git(self.local, 'show-ref'), refs)
        self.assertEqual((self.local / '.git/config').read_bytes(), config)
        self.assertEqual((self.local / '.gitignore').read_text(), 'personal ignore\n')
        self.assertEqual(self.git(self.local, 'show', ':main.c'), 'staged')
        self.assertEqual((self.local / 'main.c').read_text(), 'unstaged')

    def test_existing_remote_ahead_is_fetched_without_checkout_or_merge(self):
        self.publish_seed()
        original = self.git(self.local, 'rev-parse', 'HEAD')
        upstream = self.repo('upstream')
        self.git(upstream, 'fetch', str(self.vog), 'master')
        self.git(upstream, 'reset', '--hard', 'FETCH_HEAD')
        newer = self.commit(upstream, 'remote work')
        self.git(upstream, 'push', str(self.vog), 'HEAD:refs/heads/master')
        (self.local / 'main.c').write_text('my dirty work')
        with self.assertRaisesRegex(CheckoutSetupError, 'commits missing'):
            setup_project_checkout(self.local)
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), original)
        self.assertEqual(self.git(self.local, 'rev-parse', 'FETCH_HEAD'), newer)
        self.assertEqual((self.local / 'main.c').read_text(), 'my dirty work')

    def test_divergent_recovery_is_explicit_and_preserves_local_commit(self):
        self.git(self.local, 'push', 'origin', 'HEAD:refs/heads/work')
        other = self.repo('unrelated')
        self.git(other, 'push', str(self.vog), 'HEAD:refs/heads/master')
        original = self.git(self.local, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex(CheckoutSetupError, 'divergent or unrelated'):
            setup_project_checkout(self.local)
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), original)

    def test_existing_remote_configuration_conflict_is_not_rewritten(self):
        before = (self.local / '.git/config').read_bytes()
        with self.assertRaisesRegex(CheckoutSetupError, 'different or ambiguous URL'):
            setup_project_checkout(self.local, dev_remote_url='https://example.invalid/other')
        self.assertEqual((self.local / '.git/config').read_bytes(), before)

    def test_recovery_network_failure_preserves_existing_files(self):
        self.git(self.local, 'remote', 'set-url', 'vogsphere', str(self.root / 'missing.git'))
        (self.local / 'main.c').write_text('dirty')
        with self.assertRaises(CheckoutSetupError):
            setup_project_checkout(self.local)
        self.assertEqual((self.local / 'main.c').read_text(), 'dirty')

    def test_new_vogsphere_with_no_master_requires_explicit_selection(self):
        self.git(self.local, 'push', 'vogsphere', 'HEAD:refs/heads/other')
        target = self.root / 'recovery'
        with self.assertRaisesRegex(CheckoutSetupError, 'no master'):
            setup_project_checkout(target, vogsphere_url=str(self.vog))
        self.assertFalse(target.exists())

    def test_dirty_push_publishes_committed_head_to_explicit_branches_only(self):
        head = self.git(self.local, 'rev-parse', 'HEAD')
        (self.local / 'main.c').write_text('staged')
        self.git(self.local, 'add', 'main.c')
        (self.local / 'main.c').write_text('unstaged')
        (self.local / 'notes').write_text('untracked')
        status = self.git(self.local, 'status', '--porcelain=v1')
        plan = plan_project_push(self.local)
        self.assertEqual(plan.dirty_count, 2)
        self.assertEqual(plan.branch, 'work')
        self.assertEqual(plan.commit, head)
        self.assertEqual([(t.remote, t.branch) for t in plan.targets], [('origin', 'work'), ('vogsphere', 'master')])
        self.assertTrue(all(result.success for result in push_project(plan)))
        self.assertEqual(self.git(self.dev, 'rev-parse', 'refs/heads/work'), head)
        self.assertEqual(self.git(self.vog, 'rev-parse', 'refs/heads/master'), head)
        self.assertEqual(self.git(self.local, 'status', '--porcelain=v1'), status)
        self.assertEqual(self.git(self.local, 'show', ':main.c'), 'staged')
        self.assertEqual((self.local / 'main.c').read_text(), 'unstaged')

    def test_divergent_push_reports_partial_success_without_overwriting(self):
        other = self.repo('other')
        remote_head = self.git(other, 'rev-parse', 'HEAD')
        self.git(other, 'push', str(self.vog), 'HEAD:refs/heads/master')
        results = push_project(plan_project_push(self.local))
        self.assertEqual([result.success for result in results], [True, False])
        self.assertEqual(self.git(self.vog, 'rev-parse', 'refs/heads/master'), remote_head)
        self.assertEqual(self.git(self.dev, 'rev-parse', 'refs/heads/work'), self.git(self.local, 'rev-parse', 'HEAD'))

    def test_rejected_remote_hook_reports_partial_success_and_retry_is_independent(self):
        hook = self.vog / 'hooks/pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        results = push_project(plan_project_push(self.local))
        self.assertEqual([result.success for result in results], [True, False])
        hook.unlink()
        retry = push_project(plan_project_push(self.local, 'vog'))
        self.assertEqual(len(retry), 1)
        self.assertTrue(retry[0].success)

    def test_local_pre_push_hook_is_honored(self):
        hook = self.local / '.git/hooks/pre-push'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o755)
        result = push_project(plan_project_push(self.local, 'dev'))
        self.assertFalse(result[0].success)
        self.assertEqual(self.git(self.dev, 'show-ref', check=False), '')

    def test_missing_remote_is_independent_failure_and_nested_path_rejected(self):
        self.git(self.local, 'remote', 'remove', 'vogsphere')
        results = push_project(plan_project_push(self.local))
        self.assertEqual([result.success for result in results], [True, False])
        nested = self.local / 'nested'
        nested.mkdir()
        with self.assertRaisesRegex(ProjectGitError, 'root of a Git checkout'):
            plan_project_push(nested)

    def test_detached_and_unborn_head_are_rejected_before_push(self):
        self.git(self.local, 'switch', '--detach')
        with self.assertRaisesRegex(ProjectGitError, 'Detached HEAD'):
            plan_project_push(self.local)
        empty = self.root / 'unborn'
        empty.mkdir()
        self.git(empty, 'init', '--initial-branch=work')
        with self.assertRaisesRegex(ProjectGitError, 'No committed HEAD'):
            plan_project_push(empty)

    def test_changed_head_or_destination_requires_review_again(self):
        plan = plan_project_push(self.local, 'dev')
        self.commit(self.local, 'new commit')
        self.assertIn('changed since review', push_project(plan)[0].message)
        plan = plan_project_push(self.local, 'dev')
        self.git(self.local, 'remote', 'set-url', 'origin', str(self.vog))
        self.assertIn('Remote changed since review', push_project(plan)[0].message)

    def test_push_url_ambiguity_and_saved_configuration_mismatch_are_rejected(self):
        self.git(self.local, 'remote', 'set-url', '--push', 'origin', str(self.vog))
        plan = plan_project_push(self.local, 'dev')
        self.assertIn('ambiguous', plan.targets[0].error)
        self.assertFalse(push_project(plan)[0].success)
        plan = plan_project_push(self.local, 'vog', vogsphere_url='https://example.invalid/wrong')
        self.assertIn('different URL', plan.targets[0].error)

    def test_multiple_urls_and_push_rewrites_require_manual_resolution(self):
        self.git(self.local, 'config', '--add', 'remote.origin.url', str(self.vog))
        self.assertIn('ambiguous', plan_project_push(self.local, 'dev').targets[0].error)
        self.git(self.local, 'config', '--unset-all', 'remote.origin.url')
        self.git(self.local, 'config', 'remote.origin.url', str(self.dev))
        self.git(self.local, 'config', f'url.{self.vog}.pushInsteadOf', str(self.dev))
        self.assertIn('ambiguous', plan_project_push(self.local, 'dev').targets[0].error)

    def test_mirror_and_follow_tags_settings_do_not_expand_published_refs(self):
        self.git(self.local, 'config', 'remote.origin.mirror', 'true')
        self.git(self.local, 'config', 'push.followTags', 'true')
        self.git(self.local, 'tag', '-a', '-m', 'private tag', 'private')
        self.git(self.local, 'branch', 'private-branch')
        self.assertTrue(push_project(plan_project_push(self.local, 'dev'))[0].success)
        self.assertEqual(self.git(self.dev, 'for-each-ref', '--format=%(refname)'), 'refs/heads/work')

    def test_rename_counts_one_dirty_file(self):
        self.git(self.local, 'mv', 'main.c', 'renamed.c')
        self.assertEqual(plan_project_push(self.local).dirty_count, 1)

    def test_uri_credentials_and_query_tokens_are_redacted(self):
        url = 'https://name:password@example.invalid/repo@project.git?token=private'
        self.git(self.local, 'remote', 'set-url', 'origin', url)
        plan = plan_project_push(self.local, 'dev', dev_remote_url=url)
        self.assertEqual(plan.targets[0].url, 'https://example.invalid/repo@project.git')
        detail = _safe_detail(f'fatal: cannot access {url}')
        self.assertNotIn('password', detail)
        self.assertNotIn('private', detail)

    def test_timeout_is_explicit_and_does_not_stop_other_destination(self):
        plan = plan_project_push(self.local)
        original = subprocess.run
        def run(args, **kwargs):
            if 'push' in args and 'origin' in args:
                raise subprocess.TimeoutExpired(args, 1)
            return original(args, **kwargs)
        with patch('ft_tui.features.projects.adapters.git.subprocess.run', side_effect=run):
            results = push_project(plan)
        self.assertEqual([result.success for result in results], [False, True])
        self.assertIn('timed out', results[0].message)

    def test_hidden_remote_url_change_requires_another_review(self):
        url = 'https://name:first@example.invalid/repo?token=first'
        self.git(self.local, 'remote', 'set-url', 'origin', url)
        plan = plan_project_push(self.local, 'dev')
        changed = url.replace('first', 'second')
        self.git(self.local, 'remote', 'set-url', 'origin', changed)
        result = push_project(plan)[0]
        self.assertFalse(result.success)
        self.assertIn('Remote changed since review', result.message)
        self.assertNotIn('first', repr(plan))
        self.assertNotIn('second', result.message)
