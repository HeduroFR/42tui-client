"""Safe recovery and publishing against disposable local Git remotes."""
import os
from pathlib import Path
import subprocess
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ft_tui.features.projects.adapters.checkout import CheckoutSetupError, CheckoutReviewRequired, setup_project_checkout
from ft_tui.features.projects.adapters.git import (
    ProjectGitError, review_project_checkout, _safe_detail, plan_project_push, push_project, plan_project_pull, pull_project,
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

    def test_editor_review_preserves_index_files_and_history(self):
        other = self.repo('unrelated')
        self.git(other, 'push', str(self.dev), 'HEAD:refs/heads/main')
        self.git(self.dev, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        (self.local / 'main.c').write_text('staged')
        self.git(self.local, 'add', 'main.c')
        (self.local / 'main.c').write_text('working [bold]')
        (self.local / 'notes.txt').write_text('untracked private contents')
        original = self.git(self.local, 'rev-parse', 'HEAD')
        index = (self.local / '.git/index').read_bytes()
        with self.assertRaises(CheckoutReviewRequired) as caught:
            setup_project_checkout(self.local, dev_remote_url=str(self.dev))
        error = caught.exception
        self.assertEqual((error.path, error.remote, error.branch), (self.local, 'origin', 'main'))
        review = review_project_checkout(error.path, error.commit)
        self.assertEqual(review.head, original)
        self.assertEqual(review.relationship, 'unrelated')
        self.assertEqual(review.branch, 'work')
        self.assertIn('MM main.c', review.status)
        self.assertIn('?? notes.txt', review.status)
        self.assertIn('+working [bold]', review.diff)
        self.assertNotIn('untracked private contents', review.diff)
        self.assertEqual((self.local / '.git/index').read_bytes(), index)
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), original)
        self.assertEqual((self.local / 'main.c').read_text(), 'working [bold]')

    def test_editor_review_supports_unborn_checkout_with_files(self):
        self.git(self.local, 'push', str(self.dev), 'HEAD:refs/heads/main')
        self.git(self.dev, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        target = self.root / 'unborn'
        target.mkdir()
        self.git(target, 'init', '--initial-branch=main')
        (target / 'main.c').write_text('existing local work')
        with self.assertRaises(CheckoutReviewRequired) as caught:
            setup_project_checkout(target, dev_remote_url=str(self.dev))
        review = review_project_checkout(target, caught.exception.commit)
        self.assertEqual(review.head, '—')
        self.assertEqual(review.relationship, 'unborn')
        self.assertEqual(review.remote_only, 1)
        self.assertIn('?? main.c', review.status)
        self.assertEqual((target / 'main.c').read_text(), 'existing local work')

    @unittest.skipUnless(shutil.which('ssh-keygen'), 'OpenSSH keygen is unavailable')
    def test_ssh_askpass_unlocks_real_encrypted_key_without_terminal(self):
        from ft_tui.features.projects.adapters.ssh_askpass import ssh_askpass, ssh_environment
        key = self.root / 'synthetic_key'
        password = 'synthetic-test-passphrase'
        subprocess.run(('ssh-keygen', '-q', '-t', 'ed25519', '-N', password, '-f', str(key)), check=True)
        prompts = []
        def answer(prompt, confirm):
            prompts.append((prompt, confirm))
            return password
        with patch('ft_tui.features.projects.adapters.ssh_askpass.__file__', str(self.root / 'removed-checkout.py')), ssh_askpass(answer):
            environment = {**os.environ, **ssh_environment.get()}
            helper = Path(environment['SSH_ASKPASS'])
            # The child must not depend on a checkout that can switch branches.
            self.assertTrue((helper.parent / 'askpass.py').is_file())
            self.assertNotIn(str(Path(__file__).resolve().parent.parent / 'src'), helper.read_text())
            self.assertNotIn(password, helper.read_text())
            self.assertNotIn(password, environment.values())
            result = subprocess.run(('ssh-keygen', '-y', '-f', str(key)),
                                    stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                    env=environment, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith('ssh-ed25519 '))
        self.assertEqual(len(prompts), 1)
        self.assertIn('passphrase', prompts[0][0])
        self.assertFalse(prompts[0][1])
        self.assertNotIn(password, result.stdout + result.stderr)
        self.assertFalse(helper.exists())
        self.assertFalse(ssh_environment.get())

    def test_ssh_askpass_rejects_bad_token_and_cancellation(self):
        from unittest.mock import Mock
        from ft_tui.features.projects.adapters.ssh_askpass import ssh_askpass, ssh_environment
        answer = Mock(return_value=None)
        with ssh_askpass(answer):
            environment = {**os.environ, **ssh_environment.get()}
            for token in ('invalid', environment['FT_TUI_ASKPASS_TOKEN']):
                result = subprocess.run((environment['SSH_ASKPASS'], 'Enter passphrase:'),
                                        stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                        env={**environment, 'FT_TUI_ASKPASS_TOKEN': token}, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, '')
        answer.assert_called_once_with('Enter passphrase:', False)

    def test_review_distinguishes_fast_forward_dirty_and_divergent_histories(self):
        self.publish_seed()
        newer = self.advance_remote(self.dev, 'work', 'remote work')
        with self.assertRaises(CheckoutReviewRequired):
            setup_project_checkout(self.local, dev_remote_url=str(self.dev))
        review = review_project_checkout(self.local, newer, remote='origin')
        self.assertEqual((review.relationship, review.local_only, review.remote_only), ('behind', 0, 1))
        self.assertEqual(review.remote_url, str(self.dev))
        self.assertIsNone(review.pull_blocker)
        (self.local / 'main.c').write_text('local work')
        index = (self.local / '.git/index').read_bytes()
        review = review_project_checkout(self.local, newer, remote='origin')
        self.assertEqual(review.relationship, 'behind')
        self.assertIn('Commit or move', review.pull_blocker)
        self.assertEqual((self.local / '.git/index').read_bytes(), index)
        self.commit(self.local, 'local work')
        review = review_project_checkout(self.local, newer, remote='origin')
        self.assertEqual((review.relationship, review.local_only, review.remote_only), ('diverged', 1, 1))
        local = self.git(self.local, 'rev-parse', 'HEAD')
        review = review_project_checkout(self.local, local, remote='origin')
        self.assertEqual(review.relationship, 'equal')

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

    def test_development_ahead_requires_explicit_fast_forward_and_keeps_dirty_files(self):
        self.publish_seed()
        original = self.git(self.local, 'rev-parse', 'HEAD')
        upstream = self.repo('development-upstream')
        self.git(upstream, 'fetch', str(self.dev), 'work')
        self.git(upstream, 'reset', '--hard', 'FETCH_HEAD')
        newer = self.commit(upstream, 'home development work')
        self.git(upstream, 'push', str(self.dev), 'HEAD:refs/heads/work')
        (self.local / 'main.c').write_text('staged campus work')
        self.git(self.local, 'add', 'main.c')
        (self.local / 'main.c').write_text('dirty campus work')
        with self.assertRaisesRegex(CheckoutSetupError, 'Development remote .*newer commits.*--ff-only'):
            setup_project_checkout(self.local)
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), original)
        self.assertEqual(self.git(self.local, 'rev-parse', 'FETCH_HEAD'), newer)
        self.assertEqual(self.git(self.local, 'show', ':main.c'), 'staged campus work')
        self.assertEqual((self.local / 'main.c').read_text(), 'dirty campus work')

    def test_existing_remote_configuration_conflict_is_not_rewritten(self):
        before = (self.local / '.git/config').read_bytes()
        with self.assertRaisesRegex(CheckoutSetupError, 'different or ambiguous URL'):
            setup_project_checkout(self.local, dev_remote_url='https://example.invalid/other')
        self.assertEqual((self.local / '.git/config').read_bytes(), before)

    def test_recovery_network_failure_preserves_existing_files(self):
        self.git(self.local, 'remote', 'set-url', 'vogsphere', str(self.root / 'missing.git'))
        (self.local / 'main.c').write_text('staged')
        self.git(self.local, 'add', 'main.c')
        (self.local / 'main.c').write_text('dirty')
        before = self.git(self.local, 'status', '--porcelain=v1')
        refs = self.git(self.local, 'show-ref')
        config = (self.local / '.git/config').read_bytes()
        result = setup_project_checkout(self.local)
        self.assertEqual(result.warnings, (
            'Vogsphere could not be checked. Connect to the 42 campus network to recover remote work. '
            'Opening the existing local checkout.',
        ))
        self.assertEqual((self.local / 'main.c').read_text(), 'dirty')
        self.assertEqual(self.git(self.local, 'show', ':main.c'), 'staged')
        self.assertEqual(self.git(self.local, 'status', '--porcelain=v1'), before)
        self.assertEqual(self.git(self.local, 'show-ref'), refs)
        self.assertEqual((self.local / '.git/config').read_bytes(), config)

    def test_vogsphere_probe_and_fetch_timeouts_warn_for_existing_committed_checkout(self):
        self.publish_seed()
        original = subprocess.run
        for operation in ('ls-remote', 'fetch'):
            with self.subTest(operation=operation):
                def run(args, **kwargs):
                    if operation in args and (str(self.vog) in args or 'vogsphere' in args):
                        raise subprocess.TimeoutExpired(args, 1)
                    return original(args, **kwargs)
                with patch('ft_tui.features.projects.adapters.git.subprocess.run', side_effect=run):
                    result = setup_project_checkout(self.local)
                self.assertEqual(len(result.warnings), 1)
                self.assertIn('42 campus network', result.warnings[0])
                self.assertEqual((self.local / 'main.c').read_text(), 'initial')

    def test_new_empty_and_unborn_checkouts_still_require_vogsphere_recovery(self):
        for state in ('new', 'empty', 'unborn'):
            with self.subTest(state=state):
                target = self.root / state
                if state != 'new':
                    target.mkdir()
                if state == 'unborn':
                    self.git(target, 'init', '--initial-branch=work')
                with self.assertRaises(CheckoutSetupError):
                    setup_project_checkout(target, vogsphere_url=str(self.root / 'missing.git'))
                self.assertFalse((target / 'main.c').exists())

    def test_development_access_failure_still_blocks_existing_checkout(self):
        self.git(self.local, 'remote', 'set-url', 'origin', str(self.root / 'missing.git'))
        with self.assertRaises(CheckoutSetupError):
            setup_project_checkout(self.local)

    def test_local_fetch_failure_is_not_reported_as_campus_network_warning(self):
        self.publish_seed()
        original = subprocess.run
        def run(args, **kwargs):
            if 'fetch' in args and 'vogsphere' in args:
                return subprocess.CompletedProcess(args, 128, '', "error: cannot open '.git/FETCH_HEAD': Permission denied")
            return original(args, **kwargs)
        with patch('ft_tui.features.projects.adapters.git.subprocess.run', side_effect=run):
            with self.assertRaisesRegex(CheckoutSetupError, 'FETCH_HEAD'):
                setup_project_checkout(self.local)

    def test_vogsphere_recovery_uses_advertised_default_or_only_branch(self):
        for branch in ('main', 'master', 'submission'):
            with self.subTest(branch=branch):
                remote = self.repo(f'{branch}.git', bare=True)
                self.git(self.local, 'push', str(remote), f'HEAD:refs/heads/{branch}')
                self.git(remote, 'symbolic-ref', 'HEAD', f'refs/heads/{branch}')
                self.git(self.local, 'push', str(remote), 'HEAD:refs/heads/other')
                result = setup_project_checkout(self.root / f'clone-{branch}', vogsphere_url=str(remote))
                self.assertEqual(self.git(result.path, 'branch', '--show-current'), branch)
        self.git(self.local, 'push', 'vogsphere', 'HEAD:refs/heads/submission')
        result = setup_project_checkout(self.root / 'sole', vogsphere_url=str(self.vog))
        self.assertEqual(self.git(result.path, 'branch', '--show-current'), 'submission')

    def test_vogsphere_without_default_and_multiple_branches_is_ambiguous(self):
        for branch in ('main', 'master'):
            self.git(self.local, 'push', 'vogsphere', f'HEAD:refs/heads/{branch}')
        target = self.root / 'recovery'
        with self.assertRaisesRegex(CheckoutSetupError, 'unambiguous'):
            setup_project_checkout(target, vogsphere_url=str(self.vog))
        self.assertFalse(target.exists())

    def test_push_uses_vogsphere_default_instead_of_creating_master(self):
        self.git(self.local, 'push', 'vogsphere', 'HEAD:refs/heads/main')
        self.git(self.vog, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        self.git(self.local, 'push', 'vogsphere', 'HEAD:refs/heads/master')
        old_master = self.git(self.vog, 'rev-parse', 'master')
        newer = self.commit(self.local, 'new work')
        plan = plan_project_push(self.local, 'vog')
        self.assertEqual(plan.targets[0].branch, 'main')
        self.assertTrue(push_project(plan)[0].success)
        self.assertEqual(self.git(self.vog, 'rev-parse', 'main'), newer)
        self.assertEqual(self.git(self.vog, 'rev-parse', 'master'), old_master)

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
        self.assertEqual([(t.remote, t.branch) for t in plan.targets], [('origin', 'work'), ('vogsphere', 'work')])
        self.assertTrue(all(result.success for result in push_project(plan)))
        self.assertEqual(self.git(self.dev, 'rev-parse', 'refs/heads/work'), head)
        self.assertEqual(self.git(self.vog, 'rev-parse', 'refs/heads/work'), head)
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

    def advance_remote(self, remote, branch, content):
        other = self.repo(content.replace(' ', '-'))
        self.git(other, 'fetch', str(remote), branch)
        self.git(other, 'reset', '--hard', 'FETCH_HEAD')
        newer = self.commit(other, content)
        self.git(other, 'push', str(remote), f'HEAD:refs/heads/{branch}')
        return newer

    def test_pull_vogsphere_main_reviews_before_fast_forwarding_current_branch(self):
        self.git(self.local, 'push', 'vogsphere', 'HEAD:refs/heads/main')
        newer = self.advance_remote(self.vog, 'main', 'remote work')
        original = self.git(self.local, 'rev-parse', 'HEAD')
        plan = plan_project_pull(self.local, 'vog')
        self.assertEqual(plan.targets[0].branch, 'main')
        self.assertEqual(plan.target_commit, newer)
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), original)
        pull_project(plan)
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), newer)
        self.assertEqual(self.git(self.local, 'branch', '--show-current'), 'work')
        self.assertEqual((self.local / 'main.c').read_text(), 'remote work')

    def test_pull_all_fetches_before_advancing_once_to_newest_compatible_commit(self):
        self.publish_seed()
        newer = self.advance_remote(self.dev, 'work', 'development work')
        plan = plan_project_pull(self.local)
        self.assertEqual(len(plan.targets), 2)
        self.assertEqual(plan.target_commit, newer)
        pull_project(plan)
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), newer)
        self.assertEqual(self.git(self.local, 'rev-list', '--count', 'HEAD'), '2')

    def test_pull_all_divergent_remotes_never_partially_advances_local_branch(self):
        self.publish_seed()
        original = self.git(self.local, 'rev-parse', 'HEAD')
        self.advance_remote(self.dev, 'work', 'development work')
        self.advance_remote(self.vog, 'master', 'campus work')
        with self.assertRaisesRegex(ProjectGitError, 'diverge'):
            plan_project_pull(self.local)
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), original)
        self.assertEqual((self.local / 'main.c').read_text(), 'initial')

    def test_pull_refuses_dirty_and_untracked_work_without_stashing(self):
        self.publish_seed()
        for staged in (False, True):
            with self.subTest(staged=staged):
                (self.local / 'main.c').write_text('my work')
                if staged:
                    self.git(self.local, 'add', 'main.c')
                with self.assertRaisesRegex(ProjectGitError, 'local changes'):
                    plan_project_pull(self.local)
                self.assertEqual((self.local / 'main.c').read_text(), 'my work')
        self.git(self.local, 'reset', '--hard', 'HEAD')
        (self.local / 'notes').write_text('private notes')
        with self.assertRaisesRegex(ProjectGitError, 'untracked'):
            plan_project_pull(self.local)
        self.assertEqual((self.local / 'notes').read_text(), 'private notes')
        self.assertEqual(self.git(self.local, 'stash', 'list'), '')

    def test_pull_review_invalidated_by_local_or_remote_changes(self):
        self.publish_seed()
        plan = plan_project_pull(self.local, 'dev')
        self.advance_remote(self.dev, 'work', 'remote changed')
        with self.assertRaisesRegex(ProjectGitError, 'changed since review'):
            pull_project(plan)
        plan = plan_project_pull(self.local, 'dev')
        self.commit(self.local, 'local changed')
        with self.assertRaisesRegex(ProjectGitError, 'changed since review'):
            pull_project(plan)
        self.assertEqual((self.local / 'main.c').read_text(), 'local changed')

    def test_pull_remote_url_change_and_local_edits_require_another_review(self):
        self.publish_seed()
        plan = plan_project_pull(self.local, 'dev')
        self.git(self.local, 'remote', 'set-url', 'origin', str(self.vog))
        with self.assertRaisesRegex(ProjectGitError, 'Remote changed'):
            pull_project(plan)
        self.git(self.local, 'remote', 'set-url', 'origin', str(self.dev))
        (self.local / 'notes').write_text('untracked')
        with self.assertRaisesRegex(ProjectGitError, 'local changes'):
            pull_project(plan)

    def test_pull_all_missing_remote_and_empty_remote_keep_head(self):
        original = self.git(self.local, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex(ProjectGitError, 'unambiguous'):
            plan_project_pull(self.local)
        self.publish_seed()
        self.git(self.local, 'remote', 'remove', 'vogsphere')
        with self.assertRaisesRegex(ProjectGitError, 'not configured'):
            plan_project_pull(self.local)
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), original)

    def test_pull_blocks_clean_in_progress_operations_and_preserves_ahead_commits(self):
        self.publish_seed()
        self.commit(self.local, 'local ahead')
        plan = plan_project_pull(self.local)
        self.assertIn('up to date', pull_project(plan))
        (self.local / '.git/rebase-merge').mkdir()
        with self.assertRaisesRegex(ProjectGitError, 'Finish the current'):
            plan_project_pull(self.local)

    def test_pull_preserves_ignored_files_and_does_not_enable_autostash(self):
        self.publish_seed()
        upstream = self.repo('ignored-upstream')
        self.git(upstream, 'fetch', str(self.dev), 'work')
        self.git(upstream, 'reset', '--hard', 'FETCH_HEAD')
        (upstream / 'notes').write_text('remote notes')
        self.git(upstream, 'add', 'notes')
        self.git(upstream, 'commit', '-m', 'notes')
        self.git(upstream, 'push', str(self.dev), 'HEAD:refs/heads/work')
        (self.local / '.git/info/exclude').write_text('notes\n')
        (self.local / 'notes').write_text('private ignored notes')
        self.git(self.local, 'config', 'merge.autoStash', 'true')
        plan = plan_project_pull(self.local, 'dev')
        with self.assertRaises(ProjectGitError):
            pull_project(plan)
        self.assertEqual((self.local / 'notes').read_text(), 'private ignored notes')
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), plan.commit)

    def test_push_default_branch_change_requires_another_review(self):
        self.publish_seed()
        self.git(self.local, 'push', 'vogsphere', 'HEAD:refs/heads/main')
        self.git(self.vog, 'symbolic-ref', 'HEAD', 'refs/heads/master')
        plan = plan_project_push(self.local, 'vog')
        self.git(self.vog, 'symbolic-ref', 'HEAD', 'refs/heads/main')
        self.assertIn('branch changed', push_project(plan)[0].message)

    def test_pull_rejects_ambiguous_vogsphere_and_keeps_local_head(self):
        for branch in ('main', 'master'):
            self.git(self.local, 'push', 'vogsphere', f'HEAD:refs/heads/{branch}')
        original = self.git(self.local, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex(ProjectGitError, 'unambiguous'):
            plan_project_pull(self.local, 'vog')
        self.assertEqual(self.git(self.local, 'rev-parse', 'HEAD'), original)

    def test_existing_recovery_inspects_vogsphere_main_and_preserves_local_work(self):
        self.git(self.local, 'push', 'vogsphere', 'HEAD:refs/heads/main')
        self.advance_remote(self.vog, 'main', 'campus main work')
        (self.local / 'main.c').write_text('local work')
        with self.assertRaisesRegex(CheckoutSetupError, 'vogsphere/main.*commits missing'):
            setup_project_checkout(self.local)
        self.assertEqual((self.local / 'main.c').read_text(), 'local work')
