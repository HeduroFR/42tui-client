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
                    self.assertIn('secret-snapshot', str(app.screen.query_one('#technical-content', Static).render()))
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
        from unittest.mock import Mock
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
                '/disposable/original', dev_remote_url='/disposable/dev.git', vogsphere_url='/disposable/vog.git')
            harness._open_project_in_editor.assert_called_once_with('Original', Path('/disposable/original'))
            self.assertFalse(harness._project_checkout_busy)
            original.local_path = '/disposable/original'
            harness.selected_project_key = 'one'
            harness._open_selected_project_in_editor()
            self.assertEqual(len(tasks), 1)  # Successful first-launch recovery is reused.
            original.local_path = '/disposable/failure'
            harness.project_service.setup_checkout.side_effect = CheckoutSetupError('Divergent history')
            harness._open_project_in_editor.reset_mock()
            harness._open_selected_project_in_editor()
            await tasks[-1]
            harness._open_project_in_editor.assert_not_called()
            self.assertIn('Divergent history', harness.notify.call_args.args[0])
            self.assertFalse(harness._project_checkout_busy)
            harness.project_service.setup_checkout.side_effect = None
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
