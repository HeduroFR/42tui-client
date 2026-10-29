"""Project details prioritize overview and workspace over diagnostics."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from textual.widgets import Static, TabbedContent
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.ui.app import FortyTwoTuiApp


class ProjectDetailsLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_checkout_completion_refreshes_editor_without_changing_view(self):
        from ft_tui.features.projects.adapters.checkout import CheckoutResult

        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "checkout.sqlite"}')
            folder = Path(directory) / 'libft'
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
                session.add(Project(slug='libft', name='Libft', local_path=str(folder)))
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 50)) as pilot:
                    app.query_one(TabbedContent).active = 'projects-tab'
                    await pilot.pause()
                    project = next(iter(app.projects.values()))
                    app._show_project(project)
                    self.assertTrue(app.query_one('#open-project-editor').disabled)
                    folder.mkdir()
                    result = CheckoutResult(folder, True, False, (), (), 'Ready')
                    app._report_checkout_setup(project.name, result,
                                               project.ui_key, str(folder))
                    await pilot.pause()
                    self.assertEqual(app.selected_project_key, project.ui_key)
                    self.assertFalse(app.query_one('#open-project-editor').disabled)
                    self.assertFalse(app.query_one('#open-project-folder').disabled)
                    for destination in ('dev', 'vog', 'all'):
                        self.assertFalse(app.query_one(f'#project-push-{destination}').disabled)
                    app._clear_project_details()
                    self.assertTrue(app.query_one('#open-project-folder').disabled)
                    for destination in ('dev', 'vog', 'all'):
                        self.assertTrue(app.query_one(f'#project-push-{destination}').disabled)
            finally:
                factory.kw['bind'].dispose()

    async def test_editor_recovery_mounts_review_in_full_app_with_catppuccin_theme(self):
        from unittest.mock import Mock, patch
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.adapters.git import CheckoutReview
        from ft_tui.features.projects.views.git_review import ProjectGitReviewScreen
        with TemporaryDirectory() as directory:
            folder = Path(directory) / 'project'
            folder.mkdir()
            factory = make_session_factory(f'sqlite:///{Path(directory) / "review.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
                session.add(Project(slug='ft_printf', name='ft_printf', local_path=str(folder),
                                    dev_repo_url='/synthetic/origin.git'))
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            app.project_service.setup_checkout = Mock(side_effect=CheckoutReviewRequired(
                'Remote ahead', folder, 'origin', 'main', 'a' * 40))
            app._open_project_in_editor = Mock()
            try:
                with patch('ft_tui.features.projects.views.git_review.review_project_checkout',
                           return_value=CheckoutReview('main', 'b' * 40, '', '', 'behind', 0, 1,
                                                       '/synthetic/origin.git')):
                    async with app.run_test(size=(160, 50)) as pilot:
                        app.theme = 'catppuccin-macchiato'
                        app.query_one(TabbedContent).active = 'projects-tab'
                        await pilot.pause()
                        app._show_project(next(iter(app.projects.values())))
                        await pilot.pause()
                        await pilot.click('#open-project-editor')
                        await pilot.pause()
                        self.assertIsInstance(app.screen, ProjectGitReviewScreen)
                        await app.screen.workers.wait_for_complete()
                        buttons = list(app.screen.query('#git-review-actions AppButton'))
                        self.assertEqual(len(buttons), 4)
                        self.assertEqual(len({button.region.y for button in buttons}), 1)
                        await pilot.click('#git-review-cancel')
                        await pilot.pause()
                        self.assertFalse(app._project_git_operation_busy())
                        app._open_project_in_editor.assert_not_called()
            finally:
                factory.kw['bind'].dispose()

    async def test_git_inspection_requires_development_remote(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from ft_tui.features.projects.views.details import ProjectDetailsMixin

        project = Project(id=1, slug='libft', name='Libft', local_path='/workspace/libft')
        app = SimpleNamespace(selected_project_key=project.ui_key,
                              projects={project.ui_key: project},
                              _render_project_details=Mock(), notify=Mock())
        with patch('ft_tui.features.projects.views.details.inspect_repository') as inspect:
            for remote in (None, '', '   '):
                project.dev_repo_url = remote
                await ProjectDetailsMixin._inspect_project_git_status(app, project.ui_key, project.local_path)
            inspect.assert_not_called()
            app._render_project_details.assert_not_called()
            project.dev_repo_url = 'git@example.com:student/libft.git'
            await ProjectDetailsMixin._inspect_project_git_status(app, project.ui_key, project.local_path)
            inspect.assert_called_once_with(project.local_path)
            app._render_project_details.assert_called_once_with(project, inspect.return_value)

    async def test_overview_hides_diagnostics_and_details_remain_accessible(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "details.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
                session.add(Project(slug='libft', name='Libft', setup_status='unknown'))
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 50)) as pilot:
                    app.query_one(TabbedContent).active = 'projects-tab'
                    await pilot.pause()
                    project = next(iter(app.projects.values()))
                    project._catalog_data = {'rank': 0, 'xp': 462, 'duration': '70 hours',
                                             'description': 'Build your C library.', 'snapshot_id': 'secret-snapshot',
                                             'clauses': [{'status': 'recognized', 'modality': 'required',
                                                          'expression': {'op': 'predicate', 'ref': '42cursus-libft',
                                                                         'action': 'validated', 'target': 'project'}}]}
                    app.selected_project_key = project.ui_key
                    app._render_project_details(project)
                    app._update_editor_button()
                    self.assertEqual(str(app.query_one("#open-project-editor").label), "Open editor")
                    overview = str(app.query_one('#details-content', Static).render())
                    self.assertIn('Build your C library.', overview)
                    self.assertNotIn('Libft completed', overview)
                    self.assertNotIn('Snapshot', overview)
                    self.assertNotIn('Classification', overview)
                    self.assertNotIn('Local path', overview)
                    await pilot.pause()
                    self.assertGreater(app.query_one('#project-workspace').region.x,
                                       app.query_one('#project-overview').region.x)
                    self.assertGreaterEqual(app.query_one('#project-notes-empty').region.y,
                                            app.query_one('#notes-title').region.bottom)
                    await pilot.press('d')
                    await pilot.pause()
                    technical = '\n'.join(str(widget.render()) for widget in app.screen.query('#technical-content Static'))
                    self.assertIn('secret-snapshot', technical)
                    self.assertIn('Build your C library.', technical)
                    self.assertEqual(len(app.screen.query('.technical-section')), 3)
                    self.assertEqual(str(app.screen.query_one('#technical-project-name').render()), project.name)
                    self.assertLessEqual(app.screen.query_one('#technical-dialog').region.width, 96)
                    actions = app.screen.query_one('#technical-actions').content_region
                    close = app.screen.query_one('#close-technical-details').region
                    self.assertLessEqual(abs((close.x - actions.x) - (actions.right - close.right)), 1)
                    await pilot.resize_terminal(80, 24)
                    await pilot.pause()
                    self.assertTrue(app.screen.region.contains_region(app.screen.query_one('#close-technical-details').region))
                    self.assertGreater(app.screen.query_one('#technical-scroll').max_scroll_y, 0)
                    await pilot.press('escape')
                    await pilot.resize_terminal(80, 40)
                    await pilot.pause()
                    self.assertGreaterEqual(app.query_one('#project-workspace').region.y,
                                            app.query_one('#project-overview').region.bottom)
            finally:
                factory.kw['bind'].dispose()


class ProjectGitControlsTests(unittest.IsolatedAsyncioTestCase):
    async def test_review_partial_results_and_retry_only_failed_destination(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.git import PushPlan, PushResult, PushTarget
        from ft_tui.features.projects.views.git_push import ProjectGitPushScreen

        dev = PushTarget('dev', 'origin', '/disposable/dev.git', 'work')
        vog = PushTarget('vog', 'vogsphere', '/disposable/vog.git', 'master')
        initial = PushPlan(Path('/disposable/project'), 'work', 'a' * 40, 2, (dev, vog))
        retry = PushPlan(initial.path, 'work', 'a' * 40, 2, (vog,))
        screen = ProjectGitPushScreen('Original project', str(initial.path), 'all',
                                      dev_remote_url=dev.url, vogsphere_url=vog.url)
        app = App()
        app.language = 'en'
        with patch('ft_tui.features.projects.views.git_push.plan_project_push',
                   side_effect=[initial, retry]) as prepare, patch(
                       'ft_tui.features.projects.views.git_push.push_project',
                       side_effect=[(PushResult(dev, True, 'Published'), PushResult(vog, False, 'Rejected')),
                                    (PushResult(vog, True, 'Published'),)]) as push:
            async with app.run_test(size=(110, 35)) as pilot:
                app.push_screen(screen)
                await pilot.pause()
                await screen.workers.wait_for_complete()
                review = str(screen.query_one('#git-push-review', Static).render())
                for text in ('Original project', str(initial.path), initial.commit, dev.url, vog.url,
                             'Source branch: work', 'Uncommitted changes excluded: 2', 'master'):
                    self.assertIn(text, review)
                push.assert_not_called()
                await pilot.click('#git-push-confirm')
                await pilot.pause()
                self.assertTrue(screen.query_one('#git-push-retry-dev').disabled)
                self.assertFalse(screen.query_one('#git-push-retry-vog').disabled)
                results = str(screen.query_one('#git-push-results', Static).render())
                self.assertIn('origin → work: Succeeded', results)
                self.assertIn('vogsphere → master: Failed', results)
                await pilot.click('#git-push-retry-vog')
                await pilot.pause()
                self.assertEqual(push.call_count, 1)
                self.assertEqual(prepare.call_args.args, (str(initial.path), 'vog'))
                await pilot.click('#git-push-confirm')
                await pilot.pause()
                self.assertEqual(push.call_args.args, (retry,))
                self.assertTrue(screen.query_one('#git-push-retry-vog').disabled)
                await pilot.press('escape')
                self.assertIsNot(app.screen, screen)

    async def test_preparation_is_threaded_and_cannot_close_or_dispatch_while_busy(self):
        import asyncio
        from threading import Event, get_ident
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.git import ProjectGitError
        from ft_tui.features.projects.views.git_push import ProjectGitPushScreen

        started, release = Event(), Event()
        thread_ids = []
        def prepare(*args, **kwargs):
            thread_ids.append(get_ident())
            started.set()
            release.wait(5)
            raise ProjectGitError('No committed HEAD')
        app = App()
        app.language = 'en'
        screen = ProjectGitPushScreen('Project', '/disposable/project', 'all')
        with patch('ft_tui.features.projects.views.git_push.plan_project_push', side_effect=prepare), patch(
                'ft_tui.features.projects.views.git_push.push_project') as push:
            try:
                async with app.run_test() as pilot:
                    app.push_screen(screen)
                    for _ in range(100):
                        if started.is_set():
                            break
                        await asyncio.sleep(.01)
                    self.assertTrue(started.is_set())
                    self.assertNotEqual(thread_ids, [get_ident()])
                    self.assertTrue(screen.query_one('#git-push-confirm').disabled)
                    screen.action_close()
                    await screen._push()
                    self.assertIs(app.screen, screen)
                    push.assert_not_called()
                    release.set()
                    await screen.workers.wait_for_complete()
                    self.assertIn('No committed HEAD', str(screen.query_one('#git-push-review', Static).render()))
                    screen.action_close()
            finally:
                release.set()

    async def test_editor_recovery_captures_path_and_blocks_overlap(self):
        import asyncio
        from threading import Event
        from types import SimpleNamespace
        from unittest.mock import ANY, Mock
        from ft_tui.features.projects.views.navigation import ProjectNavigationMixin
        from ft_tui.features.projects.adapters.checkout import CheckoutSetupError

        class NavigationHarness(ProjectNavigationMixin):
            is_mounted = True
        harness = NavigationHarness()
        original = SimpleNamespace(name='Original', local_path='/disposable/original',
                                   dev_repo_url='/disposable/dev.git', vogsphere_url='/disposable/vog.git')
        harness.projects = {'one': original}
        harness.selected_project_key = 'one'
        harness.notify = Mock()
        harness.push_screen = Mock(return_value=asyncio.get_running_loop().create_future())
        harness.push_screen.return_value.set_result(None)
        harness._open_project_in_editor = Mock()
        tasks = []
        harness.run_worker = lambda coro: tasks.append(asyncio.create_task(coro))
        started, release = Event(), Event()
        def setup(*args, **kwargs):
            started.set()
            release.wait(5)
        harness.project_service = SimpleNamespace(setup_checkout=Mock(side_effect=setup))
        harness._open_selected_project_in_editor()
        try:
            for _ in range(100):
                if started.is_set():
                    break
                await asyncio.sleep(.01)
            self.assertTrue(started.is_set())
            harness._open_selected_project_in_editor()
            self.assertEqual(len(tasks), 1)
            harness.selected_project_key = 'other'
            original.local_path = '/disposable/changed'
            release.set()
            await tasks[0]
            harness.project_service.setup_checkout.assert_called_once_with(
                '/disposable/original', dev_remote_url='/disposable/dev.git', vogsphere_url='/disposable/vog.git', ssh_prompt=ANY)
            harness._open_project_in_editor.assert_called_once_with('Original', Path('/disposable/original'))
            self.assertFalse(harness._project_checkout_busy)
            original.local_path = '/disposable/original'
            harness.selected_project_key = 'one'
            harness._open_selected_project_in_editor()
            await tasks[-1]
            self.assertEqual(len(tasks), 2)  # Local state is checked before reusing remote results.
            original.local_path = '/disposable/failure'
            harness.project_service.setup_checkout.side_effect = CheckoutSetupError('Divergent history')
            harness._open_project_in_editor.reset_mock()
            harness._open_selected_project_in_editor()
            await tasks[-1]
            harness._open_project_in_editor.assert_not_called()
            self.assertIn('Divergent history', harness.notify.call_args.args[0])
            self.assertFalse(harness._project_checkout_busy)
            harness.project_service.setup_checkout.side_effect = None
            warning = 'Vogsphere could not be checked. Connect to the 42 campus network to recover remote work. Opening the existing local checkout.'
            harness.project_service.setup_checkout.return_value = SimpleNamespace(warnings=(warning,))
            original.local_path = '/disposable/off-campus'
            harness._open_selected_project_in_editor()
            await tasks[-1]
            harness._open_project_in_editor.assert_called_once_with('Original', Path(original.local_path))
            harness.notify.assert_called_with(warning, severity='warning', timeout=10)
            self.assertFalse(any(key[0] == original.local_path for key in harness._editor_recovered_checkouts))
            # An unverified remote is checked again on the next editor launch.
            previous_count = len(tasks)
            harness._open_selected_project_in_editor()
            await tasks[-1]
            self.assertEqual(len(tasks), previous_count + 1)
            harness._open_project_in_editor.reset_mock()
            harness.is_mounted = False
            await harness._recover_project_for_editor('Original', Path(original.local_path),
                                                      (original.local_path, original.dev_repo_url, original.vogsphere_url))
            harness._open_project_in_editor.assert_not_called()
        finally:
            release.set()
            await asyncio.gather(*tasks)


    async def test_late_git_results_ignore_unmounted_screen(self):
        import asyncio
        from threading import Event
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.git import PushPlan, PushResult, PushTarget
        from ft_tui.features.projects.views.git_push import ProjectGitPushScreen

        target = PushTarget('dev', 'origin', '/disposable/dev.git', 'work')
        plan = PushPlan(Path('/disposable/project'), 'work', 'a' * 40, 0, (target,))
        started, release = Event(), Event()
        def push(_plan):
            started.set()
            release.wait(5)
            return (PushResult(target, True, 'Published'),)
        app = App()
        app.language = 'fr'
        screen = ProjectGitPushScreen('Project', str(plan.path), 'dev')
        with patch('ft_tui.features.projects.views.git_push.plan_project_push', return_value=plan), patch(
                'ft_tui.features.projects.views.git_push.push_project', side_effect=push) as dispatch:
            async with app.run_test() as pilot:
                app.push_screen(screen)
                await pilot.pause()
                await screen.workers.wait_for_complete()
                task = asyncio.create_task(screen._push())
                try:
                    for _ in range(100):
                        if started.is_set():
                            break
                        await asyncio.sleep(.01)
                    self.assertTrue(started.is_set())
                    await screen._push()  # A second dispatch while pending is ignored.
                    dispatch.assert_called_once_with(plan)
                    await app.pop_screen()
                    release.set()
                    await task
                    self.assertFalse(screen.is_current)
                    self.assertFalse(screen.busy)
                finally:
                    release.set()
                    await task


class ProjectExplorerTests(unittest.TestCase):
    def test_platform_launches_and_clear_missing_folder_or_tool_errors(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from ft_tui.features.projects.adapters.explorer import open_project_folder

        with TemporaryDirectory(prefix='project folder ') as directory:
            for platform, command in (('darwin', 'open'), ('linux', 'xdg-open')):
                with self.subTest(platform=platform), patch(
                    'ft_tui.features.projects.adapters.explorer.sys.platform', platform
                ), patch('ft_tui.features.projects.adapters.explorer.shutil.which', return_value=f'/bin/{command}'), patch(
                    'ft_tui.features.projects.adapters.explorer.subprocess.run',
                    return_value=SimpleNamespace(returncode=0, stderr='')
                ) as run:
                    open_project_folder(directory)
                    self.assertEqual(run.call_args.args[0], [f'/bin/{command}', str(Path(directory).resolve())])
            with patch('ft_tui.features.projects.adapters.explorer.sys.platform', 'win32'), patch(
                    'ft_tui.features.projects.adapters.explorer.os.startfile', create=True) as startfile:
                open_project_folder(directory)
                startfile.assert_called_once_with(str(Path(directory).resolve()))
            with patch('ft_tui.features.projects.adapters.explorer.sys.platform', 'linux'), patch(
                    'ft_tui.features.projects.adapters.explorer.shutil.which', return_value=None):
                with self.assertRaisesRegex(OSError, 'xdg-open was not found'):
                    open_project_folder(directory)
            with patch('ft_tui.features.projects.adapters.explorer.sys.platform', 'linux'), patch(
                    'ft_tui.features.projects.adapters.explorer.shutil.which', return_value='/bin/xdg-open'), patch(
                    'ft_tui.features.projects.adapters.explorer.subprocess.run',
                    return_value=SimpleNamespace(returncode=1, stderr='No file manager available')):
                with self.assertRaisesRegex(OSError, 'No file manager available'):
                    open_project_folder(directory)
        with self.assertRaisesRegex(OSError, 'does not exist'):
            open_project_folder(directory)


class ProjectGitReviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_review_dialog_open_and_cancel(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.adapters.git import CheckoutReview
        from ft_tui.features.projects.views.git_review import ProjectGitReviewScreen
        error = CheckoutReviewRequired('Different history', Path('/synthetic'), 'origin', 'main', 'a' * 40)
        for key, expected in [('escape', False), ('open', True)]:
            app = App()
            app.language = 'en'
            answers = []
            with patch('ft_tui.features.projects.views.git_review.review_project_checkout',
                       return_value=CheckoutReview('work', 'b' * 40, '?? notes',
                                                  'diff --git a/file b/file\n--- a/file\n+++ b/file\n'
                                                  '@@ -1 +1 @@\n-old\n+[bold]literal')):
                async with app.run_test(size=(80, 24)) as pilot:
                    screen = ProjectGitReviewScreen(error, project_name='Libft')
                    app.push_screen(screen, answers.append)
                    await pilot.pause()
                    await screen.workers.wait_for_complete()
                    rendered = screen.query_one('#git-review-content', Static).render()
                    self.assertIn('[bold]literal', str(rendered))
                    added = rendered.get_style_at_offset(rendered.plain.index('+[bold]literal'))
                    removed = rendered.get_style_at_offset(rendered.plain.index('-old'))
                    header = rendered.get_style_at_offset(rendered.plain.index('+++ b/file'))
                    hunk = rendered.get_style_at_offset(rendered.plain.index('@@ -1'))
                    self.assertIsNotNone(added.foreground)
                    self.assertIsNotNone(removed.foreground)
                    self.assertNotEqual(added.foreground, removed.foreground)
                    self.assertTrue(header.bold)
                    self.assertNotEqual(header.foreground, added.foreground)
                    self.assertTrue(hunk.bold)
                    button = screen.query_one('#git-review-open')
                    self.assertFalse(button.disabled)
                    self.assertLess(button.region.bottom, 25)
                    if key == 'open':
                        await pilot.click('#git-review-open')
                    else:
                        await pilot.press(key)
                    await pilot.pause()
                    self.assertEqual(answers, [expected])

    async def test_recovery_requires_explicit_open_and_captures_path(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import Mock
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.views.navigation import ProjectNavigationMixin
        class Harness(ProjectNavigationMixin):
            is_mounted = True
        for approved in (False, True):
            host = Harness()
            path = Path('/synthetic')
            host.project_service = SimpleNamespace(setup_checkout=Mock(side_effect=
                CheckoutReviewRequired('Different history', path, 'origin', 'main', 'a' * 40)))
            host.push_screen = Mock(return_value=asyncio.get_running_loop().create_future())
            host.push_screen.return_value.set_result(None)
            host._open_project_in_editor = Mock()
            await host._recover_project_for_editor('Original', path, (str(path), 'dev', None))
            host._open_project_in_editor.assert_not_called()
            self.assertTrue(host._project_git_operation_busy())
            host.push_screen.call_args.args[1](approved)
            self.assertFalse(host._project_git_operation_busy())
            self.assertFalse(getattr(host, '_editor_recovered_checkouts', set()))
            if approved:
                host._open_project_in_editor.assert_called_once_with('Original', path)
            else:
                host._open_project_in_editor.assert_not_called()

    async def test_cancel_during_inspection_ignores_late_result(self):
        import asyncio
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.adapters.git import CheckoutReview
        from ft_tui.features.projects.views.git_review import ProjectGitReviewScreen
        app = App()
        app.language = 'fr'
        answers = []
        started, finish = asyncio.Event(), asyncio.Event()
        async def inspect(*args, **kwargs):
            started.set()
            await finish.wait()
            return CheckoutReview('work', 'a' * 40, '', '')
        with patch('ft_tui.features.projects.views.git_review.asyncio.to_thread', side_effect=inspect):
            async with app.run_test(size=(80, 24)) as pilot:
                error = CheckoutReviewRequired('Different history', Path('/synthetic'), 'origin', 'main', 'a' * 40)
                screen = ProjectGitReviewScreen(error, project_name='Libft')
                app.push_screen(screen, answers.append)
                await asyncio.wait_for(started.wait(), timeout=3)
                self.assertTrue(screen.query_one('#git-review-open').disabled)
                await pilot.press('escape')
                finish.set()
                await pilot.pause()
                self.assertEqual(answers, [False])

    def test_review_copy_has_supported_translations(self):
        import ast
        from ft_tui.i18n import translate
        from ft_tui.features.projects.views import checkout_progress, git_action, git_review, ssh_prompt
        tree = ast.parse('\n'.join(Path(module.__file__).read_text() for module in
                                   (checkout_progress, git_action, git_review, ssh_prompt)))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and ((isinstance(node.func, ast.Name) and node.func.id == 'tr')
                         or (isinstance(node.func, ast.Attribute) and node.func.attr == '_t'))
                    and isinstance(node.args[0], ast.Constant)):
                source = node.args[0].value
                for language in ('fr', 'es'):
                    self.assertNotEqual(translate(source, language), source, (language, source))
        for source in git_review._HISTORY_ADVICE.values():
            for language in ('fr', 'es'):
                self.assertNotEqual(translate(source, language), source, (language, source))

    async def test_ssh_passphrase_is_masked_and_cancel_never_opens_editor(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from textual.app import App
        from textual.widgets import Input
        from ft_tui.features.projects.adapters.checkout import CheckoutResult
        from ft_tui.features.projects.views.navigation import ProjectNavigationMixin
        from ft_tui.features.projects.views.ssh_prompt import ProjectSshPromptScreen
        class Harness(ProjectNavigationMixin, App):
            language = 'en'
        for submit in (True, False):
            app = Harness()
            app._open_project_in_editor = Mock()
            supplied = []
            def setup(path, *, ssh_prompt, **kwargs):
                supplied.append(ssh_prompt('Enter passphrase for key [literal]:', False))
                return CheckoutResult(Path(path), False, False, (), (), 'Ready',
                                      warnings=('Vogsphere unavailable',) if supplied[-1] is None else ())
            app.project_service = SimpleNamespace(setup_checkout=setup)
            async with app.run_test(size=(80, 24)) as pilot:
                app._project_checkout_busy = True
                worker = app.run_worker(app._recover_project_for_editor('Libft', Path('/synthetic'),
                                                                        ('/synthetic', 'dev', None)))
                await pilot.pause()
                self.assertIsInstance(app.screen, ProjectSshPromptScreen)
                field = app.screen.query_one(Input)
                self.assertTrue(field.password)
                field.value = 'synthetic-passphrase'
                if submit:
                    await pilot.click('#ssh-prompt-submit')
                else:
                    await pilot.press('escape')
                await worker.wait()
                await pilot.pause()
                self.assertEqual(field.value, '')
                self.assertFalse(app._project_checkout_busy)
                if submit:
                    self.assertEqual(supplied, ['synthetic-passphrase'])
                    app._open_project_in_editor.assert_called_once_with('Libft', Path('/synthetic'))
                else:
                    self.assertEqual(supplied, [None])
                    app._open_project_in_editor.assert_not_called()

    async def test_slow_remote_shows_loading_and_cancel_ignores_late_success(self):
        from threading import Event
        from types import SimpleNamespace
        from unittest.mock import Mock
        from textual.app import App
        from ft_tui.features.projects.adapters.checkout import CheckoutResult
        from ft_tui.features.projects.views.navigation import ProjectNavigationMixin
        from ft_tui.features.projects.views.checkout_progress import ProjectCheckoutProgressScreen
        class Harness(ProjectNavigationMixin, App):
            language = 'en'
        app = Harness()
        release = Event()
        def setup(path, **kwargs):
            release.wait(5)
            return CheckoutResult(Path(path), False, False, (), (), 'Ready')
        app.project_service = SimpleNamespace(setup_checkout=setup)
        app._open_project_in_editor = Mock()
        async with app.run_test(size=(80, 24)) as pilot:
            app._project_checkout_busy = True
            worker = app.run_worker(app._recover_project_for_editor('Libft', Path('/synthetic'),
                                                                    ('/synthetic', 'dev', None)))
            try:
                await pilot.pause()
                self.assertIsInstance(app.screen, ProjectCheckoutProgressScreen)
                await pilot.click('#checkout-progress-cancel')
                await pilot.pause()
                self.assertNotIsInstance(app.screen, ProjectCheckoutProgressScreen)
                self.assertTrue(app._project_checkout_busy)
            finally:
                release.set()
            await worker.wait()
            app._open_project_in_editor.assert_not_called()
            self.assertFalse(app._project_checkout_busy)

    async def test_review_names_dev_vog_and_suggests_only_compatible_pull(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.adapters.git import CheckoutReview
        from ft_tui.features.projects.views.git_review import ProjectGitReviewScreen
        for remote, destination, relation in (('origin', 'dev', 'behind'), ('vogsphere', 'vog', 'behind'),
                                              ('origin', 'dev', 'diverged'), ('vogsphere', 'vog', 'unrelated')):
            app = App()
            app.language = 'en'
            review = CheckoutReview('main', 'b' * 40, '', '', relation, 0, 2, 'git@example.invalid:project.git')
            with patch('ft_tui.features.projects.views.git_review.review_project_checkout', return_value=review):
                async with app.run_test(size=(80, 24)) as pilot:
                    screen = ProjectGitReviewScreen(CheckoutReviewRequired('Different', Path('/synthetic project'),
                                                    remote, 'master', 'a' * 40), project_name='Libft')
                    app.push_screen(screen)
                    await pilot.pause()
                    await screen.workers.wait_for_complete()
                    header = str(screen.query_one('#git-review-remote', Static).render())
                    content = str(screen.query_one('#git-review-content', Static).render())
                    self.assertIn(f'{destination} ({remote})', header)
                    self.assertIn('master', header)
                    self.assertIn(review.remote_url, content)
                    self.assertIn("cd '/synthetic project'", content)
                    self.assertIn(f'only on {destination}: 2', content)
                    if relation == 'behind':
                        self.assertIn(f'42git pull {destination}', content)
                    else:
                        self.assertNotIn('42git pull', content)
                        self.assertIn('git -C', content)
                        self.assertIn('a' * 40, content)
                    self.assertTrue(screen.region.contains_region(screen.query_one('#git-review-open').region))
                    open_button = screen.query_one('#git-review-open')
                    cancel_button = screen.query_one('#git-review-cancel')
                    self.assertGreaterEqual(cancel_button.region.x - open_button.region.right, 2)
                    command = screen.query_one('#git-review-command')
                    self.assertFalse(command.disabled)
                    self.assertEqual(str(command.label), f'Pull {destination}' if relation == 'behind' else 'Inspect commits')
                    buttons = [screen.query_one(selector) for selector in
                               ('#git-review-command', '#git-review-status', '#git-review-open', '#git-review-cancel')]
                    self.assertEqual(len({button.region.y for button in buttons}), 1)
                    for button in buttons:
                        button.focus()
                        await pilot.pause()
                        self.assertTrue(screen.region.contains_region(button.region))

    async def test_git_action_pull_requires_confirmation_and_displays_output(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.adapters.git import CheckoutReview, PullPlan, PullTarget
        from ft_tui.features.projects.views.git_action import ProjectGitActionScreen
        path = Path('/synthetic')
        review = CheckoutReviewRequired('Different', path, 'origin', 'main', 'a' * 40)
        snapshot = CheckoutReview('main', 'b' * 40, '', '', 'behind', 0, 1, 'git@example.invalid:project.git')
        target = PullTarget('dev', 'origin', snapshot.remote_url, 'main', review.commit, 'fingerprint')
        plan = PullPlan(path, 'main', snapshot.head, review.commit, (target,))
        app = App()
        app.language = 'en'
        answers = []
        with patch('ft_tui.features.projects.views.git_action.plan_project_pull', return_value=plan) as prepare, \
             patch('ft_tui.features.projects.views.git_action.pull_project', return_value='Fast-forward complete') as apply:
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ProjectGitActionScreen(review, snapshot, 'pull', project_name='Libft')
                app.push_screen(screen, answers.append)
                await pilot.pause()
                await screen.workers.wait_for_complete()
                prepare.assert_called_once_with(path, 'dev')
                apply.assert_not_called()
                confirm = screen.query_one('#git-action-confirm')
                close = screen.query_one('#git-action-close')
                self.assertFalse(confirm.disabled)
                self.assertGreaterEqual(close.region.x - confirm.region.right, 2)
                await pilot.click('#git-action-confirm')
                await pilot.pause()
                apply.assert_called_once_with(plan)
                self.assertIn('Fast-forward complete', str(screen.query_one('#git-action-output', Static).render()))
                self.assertTrue(confirm.disabled)
                await pilot.click('#git-action-close')
                await pilot.pause()
                self.assertEqual(answers, [review.commit])

    async def test_git_action_stale_target_blocks_confirmation(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.adapters.git import CheckoutReview, PullPlan, PullTarget
        from ft_tui.features.projects.views.git_action import ProjectGitActionScreen
        path = Path('/synthetic')
        review = CheckoutReviewRequired('Different', path, 'vogsphere', 'master', 'a' * 40)
        snapshot = CheckoutReview('main', 'b' * 40, '', '', 'behind', 0, 1, 'git@example.invalid:project.git')
        target = PullTarget('vog', 'vogsphere', snapshot.remote_url, 'main', 'c' * 40, 'fingerprint')
        plan = PullPlan(path, 'main', snapshot.head, target.commit, (target,))
        app = App()
        app.language = 'en'
        with patch('ft_tui.features.projects.views.git_action.plan_project_pull', return_value=plan), \
             patch('ft_tui.features.projects.views.git_action.pull_project') as apply:
            async with app.run_test(size=(80, 24)) as pilot:
                screen = ProjectGitActionScreen(review, snapshot, 'pull', project_name='Libft')
                app.push_screen(screen)
                await pilot.pause()
                await screen.workers.wait_for_complete()
                self.assertTrue(screen.query_one('#git-action-confirm').disabled)
                self.assertIn('changed', str(screen.query_one('#git-action-output', Static).render()))
                apply.assert_not_called()

    async def test_review_status_button_opens_output_modal(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.adapters.git import CheckoutReview
        from ft_tui.features.projects.views.git_review import ProjectGitReviewScreen
        from ft_tui.features.projects.views.git_action import ProjectGitActionScreen
        app = App()
        app.language = 'en'
        review = CheckoutReviewRequired('Different', Path('/synthetic'), 'origin', 'main', 'a' * 40)
        with patch('ft_tui.features.projects.views.git_review.review_project_checkout',
                   return_value=CheckoutReview('main', 'b' * 40, '', '', 'unrelated')), \
             patch('ft_tui.features.projects.views.git_action.project_git_output', return_value='## main\n?? [literal]') as output:
            async with app.run_test(size=(80, 24)) as pilot:
                parent = ProjectGitReviewScreen(review, project_name='Libft')
                app.push_screen(parent)
                await pilot.pause()
                await parent.workers.wait_for_complete()
                await pilot.click('#git-review-status')
                await pilot.pause()
                child = app.screen
                self.assertIsInstance(child, ProjectGitActionScreen)
                await child.workers.wait_for_complete()
                self.assertIn('?? [literal]', str(child.query_one('#git-action-output', Static).render()))
                output.assert_called_once_with(review.path, history_commit=None)
                await pilot.click('#git-action-close')
                await pilot.pause()
                self.assertIs(app.screen, parent)

    async def test_push_action_reports_success_or_failure_after_confirmation(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.adapters.git import CheckoutReview, PushPlan, PushTarget, PushResult
        from ft_tui.features.projects.views.git_action import ProjectGitActionScreen
        for success in (False, True):
            path = Path('/synthetic')
            review = CheckoutReviewRequired('Different', path, 'origin', 'main', 'a' * 40)
            snapshot = CheckoutReview('main', 'b' * 40, ' M file', '', 'ahead', 1, 0, 'git@example.invalid:project.git')
            target = PushTarget('dev', 'origin', snapshot.remote_url, 'main')
            plan = PushPlan(path, 'main', snapshot.head, 1, (target,))
            app = App()
            app.language = 'en'
            with patch('ft_tui.features.projects.views.git_action.plan_project_push', return_value=plan), \
                 patch('ft_tui.features.projects.views.git_action.push_project',
                       return_value=(PushResult(target, success, 'Synthetic outcome [literal]'),)) as apply:
                async with app.run_test(size=(80, 24)) as pilot:
                    screen = ProjectGitActionScreen(review, snapshot, 'push', project_name='Libft')
                    app.push_screen(screen)
                    await pilot.pause()
                    await screen.workers.wait_for_complete()
                    apply.assert_not_called()
                    self.assertIn('Uncommitted changes excluded: 1', str(screen.query_one('#git-action-output', Static).render()))
                    await pilot.click('#git-action-confirm')
                    await pilot.pause()
                    apply.assert_called_once_with(plan)
                    output = screen.query_one('#git-action-output', Static)
                    self.assertIn('Synthetic outcome [literal]', str(output.render()))
                    self.assertTrue(output.has_class('success' if success else 'error'))
                    self.assertEqual(screen.updated_commit, plan.commit if success else None)

    async def test_review_pull_button_refreshes_after_result_modal_closes(self):
        from unittest.mock import patch
        from textual.app import App
        from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
        from ft_tui.features.projects.adapters.git import CheckoutReview, PullPlan, PullTarget
        from ft_tui.features.projects.views.git_review import ProjectGitReviewScreen
        from ft_tui.features.projects.views.git_action import ProjectGitActionScreen
        path = Path('/synthetic')
        review = CheckoutReviewRequired('Different', path, 'vogsphere', 'master', 'a' * 40)
        snapshot = CheckoutReview('main', 'b' * 40, '', '', 'behind', 0, 1, 'git@example.invalid:project.git')
        target = PullTarget('vog', 'vogsphere', snapshot.remote_url, 'master', review.commit, 'fingerprint')
        plan = PullPlan(path, 'main', snapshot.head, review.commit, (target,))
        after = CheckoutReview('main', review.commit, '', '', 'equal', 0, 0, snapshot.remote_url)
        app = App()
        app.language = 'en'
        with patch('ft_tui.features.projects.views.git_review.review_project_checkout', side_effect=[snapshot, after]), \
             patch('ft_tui.features.projects.views.git_action.plan_project_pull', return_value=plan), \
             patch('ft_tui.features.projects.views.git_action.pull_project', return_value='Fast-forward complete'):
            async with app.run_test(size=(80, 24)) as pilot:
                parent = ProjectGitReviewScreen(review, project_name='Libft')
                app.push_screen(parent)
                await pilot.pause()
                await parent.workers.wait_for_complete()
                self.assertEqual(str(parent.query_one('#git-review-command').label), 'Pull vog')
                await pilot.click('#git-review-command')
                await pilot.pause()
                child = app.screen
                self.assertIsInstance(child, ProjectGitActionScreen)
                await child.workers.wait_for_complete()
                await pilot.click('#git-action-confirm')
                await pilot.pause()
                await pilot.click('#git-action-close')
                await pilot.pause()
                await parent.workers.wait_for_complete()
                self.assertIs(app.screen, parent)
                self.assertEqual(parent.snapshot.relationship, 'equal')
                self.assertTrue(parent.query_one('#git-review-command').disabled)
