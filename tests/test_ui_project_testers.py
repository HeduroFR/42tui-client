"""Project tester state transitions and guaranteed terminal restoration."""

import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.features.projects.adapters.tester_catalog import load_catalog
from ft_tui.features.projects.adapters.tester_docker import DockerStatus, Host, TesterDocker, TesterError
from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Button
from ft_tui.features.projects.views.testers import DockerInstallScreen, ProjectTesters, TesterAction, TesterRemoveButton


class ProjectTesterUITests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def workspace(self, invalid_catalog=False):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            factory = make_session_factory(f"sqlite:///{root / 'ui.sqlite'}")
            with factory() as session:
                save_settings(session, {"onboarding_completed": "true"})
                for slug in ("libft", "ft_printf", "get_next_line", "born2beroot"):
                    session.add(Project(slug=slug, name=slug))
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            catalog_path = root / "testers.toml"
            if invalid_catalog:
                catalog_path.write_text("testers = [", encoding="utf-8")
            app.tester_catalog = load_catalog(catalog_path)
            service = app.tester_docker = TesterDocker(root / "testers", Host("linux", "amd64", "ubuntu", "noble"))
            service.status = Mock(return_value=DockerStatus("ready"))
            service.installed = Mock(return_value=False)
            service.has_images = Mock(return_value=False)
            try:
                async with app.run_test(size=(140, 65)) as pilot:
                    await pilot.pause()
                    widget = app.query_one(ProjectTesters)
                    projects = {project.slug: project for project in app.projects.values()}
                    yield app, widget, service, projects, pilot, root
            finally:
                factory.kw["bind"].dispose()

    async def select(self, widget, project, pilot):
        widget.app._show_project(project)
        await pilot.pause()
        await widget._inspection_worker.wait()
        await pilot.pause()

    async def test_run_requires_folder_even_before_install_and_reuses_shared_image(self):
        async with self.workspace() as (_app, widget, service, projects, pilot, root):
            for installed in (False, True):
                service.installed.return_value = installed
                for slug in ("libft", "ft_printf"):
                    projects[slug].local_path = None
                    await self.select(widget, projects[slug], pilot)
                    button = widget.query_one(TesterAction)
                    self.assertEqual(str(button.label), "Run Supra libft tester" if slug == "libft" else "Run Supra printf tester")
                    self.assertTrue(button.disabled)
                    projects[slug].local_path = str(root)
                    await self.select(widget, projects[slug], pilot)
                    self.assertFalse(widget.query_one(TesterAction).disabled)
            await self.select(widget, projects["born2beroot"], pilot)
            self.assertFalse(widget.query(TesterAction))

    async def test_one_run_action_stays_available_for_setup_and_recovery(self):
        async with self.workspace() as (_app, widget, service, projects, pilot, root):
            projects["libft"].local_path = str(root)
            for state in ("missing", "denied", "stopped", "unsupported", "incompatible", "ready"):
                service.status.return_value = DockerStatus(state, "test detail")
                await self.select(widget, projects["libft"], pilot)
                buttons = list(widget.query(Button))
                self.assertEqual({b.tester.id for b in buttons if b.display}, {"supra-libft"})
                self.assertEqual(str(buttons[0].label), "Run Supra libft tester")
                self.assertFalse(buttons[0].disabled)

    async def test_workspace_keeps_output_and_run_when_closed_and_cancels(self):
        import asyncio
        import threading
        from ft_tui.features.projects.views.tester_workspace import TesterWorkspace
        async with self.workspace() as (app, widget, service, projects, pilot, root):
            projects["libft"].local_path = str(root)
            await self.select(widget, projects["libft"], pilot)
            entered = threading.Event()
            def run(tester, path, terminal, **kwargs):
                self.assertEqual(path, str(root))
                terminal.write("live tester output")
                entered.set()
                terminal.cancelled.wait(10)
                terminal.check_cancelled()
            service.prepare_and_run = Mock(side_effect=run)
            widget._start("run", app.tester_catalog.testers[0])
            widget._start("run", app.tester_catalog.testers[0])
            self.assertTrue(await asyncio.to_thread(entered.wait, 3))
            await pilot.pause()
            self.assertIsInstance(app.screen, TesterWorkspace)
            workspace = app.screen
            await pilot.resize_terminal(80, 24)
            await pilot.press("escape")
            await pilot.pause()
            self.assertTrue(service.busy)
            await self.select(widget, projects["ft_printf"], pilot)
            widget.query_one("#tester-workspace-open", Button).press()
            await pilot.pause()
            self.assertIs(app.screen, workspace)
            app.screen.query_one("#tester-cancel", Button).press()
            await pilot.pause(.3)
            await widget.workers.wait_for_complete()
            self.assertFalse(service.busy)
            self.assertFalse(widget._operating)
            self.assertIn("supra-libft", widget._retry)
            service.prepare_and_run.assert_called_once()
            transcript = workspace.log_path.read_text()
            self.assertIn("live tester output", transcript)
            self.assertIn("interrupted", transcript)
            await pilot.pause()
            service.prepare_and_run = Mock()
            workspace.query_one("#tester-rerun", Button).press()
            await pilot.pause(.4)
            await widget.workers.wait_for_complete()
            self.assertIsNot(widget._workspace, workspace)
            self.assertEqual(service.prepare_and_run.call_args.args[1], str(root))
            self.assertIn("Read the log", widget._workspace.log_path.read_text())

    async def test_workspace_distinguishes_structured_results_from_process_completion(self):
        from ft_tui.features.projects.tester_results import TestSummary, TesterRunResult
        from ft_tui.i18n import translate
        from textual.widgets import Static
        cases = (
            (TesterRunResult(0, TestSummary(3, 3, 0, 0, 0)), "Tests passed."),
            (TesterRunResult(0, TestSummary(3, 2, 1, 0, 0)), "Tests failed. Read the log for details."),
            (TesterRunResult(1, TestSummary(3, 2, 1, 0, 0)), "Tests failed. Read the log for details."),
            (TesterRunResult(2), "Tester process failed. Test results are not confirmed. Read the log."),
            (TesterRunResult(0, unreadable=True), "Tester results could not be read. Read the log."),
            (TesterRunResult(0), "Tester finished. Test results are unverified. Read the log."),
        )
        async with self.workspace() as (app, widget, service, projects, pilot, root):
            await self.select(widget, projects["libft"], pilot)
            for language in ("en", "fr", "es"):
                app.language = language
                for outcome, message in cases:
                    with self.subTest(language=language, status=outcome.status):
                        if widget._workspace and widget._workspace.is_current:
                            app.pop_screen()
                            await pilot.pause()
                        service.prepare_and_run = Mock(return_value=outcome)
                        await widget._perform("run", app.tester_catalog.testers[0], str(root), None)
                        workspace = widget._workspace
                        workspace.refresh_output()
                        rendered = str(workspace.query_one("#tester-result", Static).render())
                        self.assertIn(translate(message, language), rendered)
                        self.assertIn(translate("Process exit code: {code}", language).format(code=outcome.exit_code), rendered)
                        if language != "en":
                            self.assertNotEqual(translate(message, language), message)
                        transcript = workspace.log_path.read_text()
                        self.assertIn(translate(message, language), transcript)
                        if outcome.summary:
                            counts = translate("Tests: {total} · passed: {passed} · failed: {failed} · errors: {errors} · skipped: {skipped}", language).format(**vars(outcome.summary))
                            self.assertIn(counts, transcript)
                            self.assertIn(counts, rendered)
                        self.assertFalse(service.busy)
                        self.assertFalse(workspace.query_one("#tester-rerun", Button).disabled)
                        await pilot.press("escape")
                        await pilot.pause()

    async def test_workspace_refresh_waits_for_complete_controls_during_teardown(self):
        from ft_tui.features.projects.views.tester_workspace import TesterWorkspace
        async with self.workspace() as (app, _widget, _service, _projects, _pilot, root):
            workspace = TesterWorkspace("Synthetic", root / "log")
            await app.push_screen(workspace)
            await workspace.query_one("#tester-cancel", Button).remove()
            workspace.output.append(b"preserve pending output")
            workspace.refresh_output()
            self.assertEqual(list(workspace.output), [b"preserve pending output"])

    async def test_testers_below_registration_and_shortcut_reveals_actions_on_small_screens(self):
        async with self.workspace() as (app, widget, _service, projects, pilot, root):
            projects["libft"].local_path = str(root)
            from textual.containers import VerticalScroll

            await self.select(widget, projects["libft"], pilot)
            self.assertFalse(app.query("#show-project-testers"))
            self.assertEqual(widget.parent.id, "project-overview")
            for width, height in ((140, 65), (80, 24)):
                await pilot.resize_terminal(width, height)
                await pilot.pause()
                scroll = app.query_one("#project-details-scroll", VerticalScroll)
                scroll.scroll_end(animate=False)
                await pilot.pause()
                action = widget.query_one(TesterAction)
                self.assertGreaterEqual(widget.region.y, app.query_one("#project-registration").region.bottom)
                scroll.scroll_home(animate=False)
                await pilot.pause()
                app.set_focus(None)
                await pilot.press("t")
                await pilot.pause()
                self.assertIs(app.focused, action)
                self.assertTrue(scroll.content_region.contains_region(action.region),
                                (width, height, scroll.content_region, action.region))
            app.selected_project_key = None
            app._clear_project_details()
            await pilot.pause()
            self.assertIsNone(widget.project)

    async def test_long_docker_diagnostic_does_not_expand_the_status_message(self):
        async with self.workspace() as (_app, widget, service, projects, pilot, _root):
            detail = '\n'.join(f'Docker diagnostic line {index}' for index in range(20))
            service.status.return_value = DockerStatus('stopped', detail)
            await self.select(widget, projects['libft'], pilot)
            status = widget.query_one('#tester-status')
            text = str(status.render())
            self.assertNotIn(detail, text)
            self.assertEqual(status.tooltip, detail)
            self.assertIn('Configure an existing local project folder', text)
            scroll = widget.query_one('#tester-status-scroll')
            self.assertLessEqual(scroll.size.height, 5)
            self.assertEqual(scroll.max_scroll_y, 0)

    async def test_testers_shortcut_respects_text_input_and_other_tabs(self):
        async with self.workspace() as (app, widget, _service, projects, pilot, _root):
            from ft_tui.ui.components import Input

            await self.select(widget, projects["libft"], pilot)
            search = app.query_one("#project-search", Input)
            search.focus()
            await pilot.press("t")
            await pilot.pause()
            self.assertEqual(search.value, "t")
            self.assertIs(app.focused, search)
            app.query_one("#main-tabs").active = "settings"
            app.set_focus(None)
            await pilot.press("t")
            await pilot.pause()
            self.assertEqual(app.query_one("#main-tabs").active, "settings")
            self.assertNotIsInstance(app.focused, TesterAction)

    async def test_native_tester_needs_consent_and_never_probes_docker(self):
        from dataclasses import replace
        from ft_tui.features.projects.views.testers import NativeTesterConsent
        from ft_tui.features.projects.tester_results import TesterRunResult
        async with self.workspace() as (app, widget, service, projects, pilot, root):
            tester = replace(app.tester_catalog.testers[0], runtime='native')
            app.tester_catalog = replace(app.tester_catalog, testers=(tester,))
            service.status.reset_mock()
            projects['libft'].local_path = str(root)
            await self.select(widget, projects['libft'], pilot)
            service.status.assert_not_called()
            with patch('ft_tui.features.projects.views.testers.run_native', return_value=TesterRunResult(0)) as run:
                widget.query_one(TesterAction).press()
                await pilot.pause()
                self.assertIsInstance(app.screen, NativeTesterConsent)
                await pilot.press('escape')
                run.assert_not_called()
                widget.query_one(TesterAction).press()
                await pilot.pause()
                app.screen.query_one('#confirm-native-tester', Button).press()
                await pilot.pause(.3)
                await widget.workers.wait_for_complete()
                run.assert_called_once()
                self.assertEqual(run.call_args.args[1], str(root))
                self.assertIn('unverified', widget._messages['supra-libft'])

    async def test_result_card_counts_reflow_and_log_action(self):
        from ft_tui.features.projects.views.testers import TesterResultCard, TesterLogButton
        from ft_tui.features.projects.tester_results import TesterRunResult, TestSummary
        from ft_tui.ui.components import Static
        async with self.workspace() as (app, widget, service, projects, pilot, root):
            service.has_images.return_value = True
            outcome = TesterRunResult(0, TestSummary(503, 503, 0, 0, 0))
            log_path = root / "logs" / "run.log"
            widget._workspace = Mock(log_path=log_path, is_current=False)
            widget._messages["supra-libft"] = "Tests passed."
            widget._results["supra-libft"] = ("Tests passed.", outcome, log_path)
            await self.select(widget, projects["libft"], pilot)
            app.action_project_testers()
            await pilot.pause()
            card = widget.query_one(TesterResultCard)
            self.assertTrue(card.has_class("result-success"))
            self.assertEqual(str(card.query_one(".tester-result-total", Static).render()), "503 tests")
            self.assertNotIn(str(log_path), " ".join(str(w.render()) for w in card.query(Static)))
            with patch.object(app, "_open_file_in_editor") as opened:
                widget.query_one(TesterLogButton).press()
                await pilot.pause()
                await widget.workers.wait_for_complete()
                opened.assert_called_once_with(log_path)
            for width in (80, 200):
                await pilot.resize_terminal(width, 65)
                await pilot.pause()
                counts = list(card.query(".tester-count"))
                self.assertEqual(len(counts), 4)
                self.assertEqual(counts[0].region.y == counts[2].region.y, card.size.width >= 52)
                log_button = widget.query_one(TesterLogButton)
                output_button = widget.query_one("#tester-workspace-open", Button)
                self.assertEqual(log_button.region.y, output_button.region.y)
                self.assertGreaterEqual(output_button.region.x - log_button.region.right, 2, (width, log_button.region, output_button.region, log_button.display, widget.query_one("#tester-result-actions").region))
                self.assertTrue(widget.region.contains_region(output_button.region))
                for count in counts:
                    self.assertTrue(card.region.contains_region(count.region))
                for left, right in zip(counts, counts[1:]):
                    self.assertFalse(left.region.overlaps(right.region))
            # A failed run retains its nonzero exit code and uses the error palette.
            await card.remove()
            failed = TesterResultCard("Tests failed.", TesterRunResult(1, TestSummary(10, 8, 1, 0, 1)), log_path, "fr")
            await widget.query_one("#tester-rows").mount(failed)
            await pilot.pause()
            self.assertTrue(failed.has_class("result-error"))
            self.assertIn("Réussis", str(failed.query_one(".count-passed", Static).render()))
            self.assertTrue(failed.query(".tester-result-detail"))

    async def test_multiple_testers(self):
        from dataclasses import replace
        async with self.workspace() as (app, widget, _service, projects, pilot, _root):
            tester = app.tester_catalog.testers[0]
            app.tester_catalog = replace(app.tester_catalog, testers=(tester, replace(tester, id="other", name="Other")))
            await self.select(widget, projects["libft"], pilot)
            self.assertEqual(len(widget.query(TesterAction)), 2)

    async def test_remove_button_works_without_a_project_folder_and_refreshes_shared_installation(self):
        async with self.workspace() as (app, widget, service, projects, pilot, _root):
            service.has_images.return_value = True  # Old/other-CPU images can remain even without the current image.
            await self.select(widget, projects["libft"], pilot)
            await pilot.resize_terminal(80, 24)
            app.action_project_testers()
            await pilot.pause()
            remove = widget.query_one(TesterRemoveButton)
            self.assertFalse(remove.disabled)
            self.assertTrue(remove.square)
            app.icon_mode = "nerd"
            remove.apply_language()
            self.assertEqual(str(remove.label), "\uf1f8")
            app.icon_mode = "unicode"
            remove.apply_language()
            self.assertEqual(str(remove.label), "🗑︎")
            app.icon_mode = "text"
            remove.apply_language()
            self.assertEqual(str(remove.label), "Remove")
            self.assertFalse(remove.square)
            app.icon_mode = "nerd"
            remove.apply_language()
            await pilot.pause()
            self.assertEqual(remove.variant, "danger")
            run = widget.query_one(TesterAction)
            self.assertEqual(remove.region.y, run.region.y)
            self.assertEqual(remove.region.height, run.region.height)
            self.assertGreaterEqual(remove.region.x - run.region.right, 2)
            self.assertIn("all projects", str(remove.tooltip))
            self.assertTrue(app.screen.region.contains_region(remove.region))
            def removed(*args):
                service.has_images.return_value = False
                service.installed.return_value = False
            service.remove = Mock(side_effect=removed)
            with patch("ft_tui.features.projects.views.testers.WorkspaceSession") as terminal:
                terminal.return_value.phase = "Preparing the tester…"
                remove.press()
                remove.press()
                await pilot.pause(.4)
                await widget.workers.wait_for_complete()
                await widget._inspection_worker.wait()
            service.remove.assert_called_once()
            self.assertFalse(widget.query(TesterRemoveButton))
            self.assertFalse(service.busy)
            self.assertIn("removed", widget._messages["supra-libft"])
            await self.select(widget, projects["ft_printf"], pilot)
            self.assertFalse(widget.query(TesterRemoveButton))
            self.assertEqual(str(widget.query_one(TesterAction).label), "Run Supra printf tester")

    async def test_remove_failure_keeps_the_delete_action_available_without_changing_run_retry(self):
        async with self.workspace() as (app, widget, service, projects, pilot, _root):
            service.installed.return_value = True
            service.has_images.return_value = True
            service.remove = Mock(side_effect=TesterError("image in use"))
            await self.select(widget, projects["libft"], pilot)
            self.assertTrue(widget.query_one(TesterAction).disabled)
            self.assertFalse(widget.query_one(TesterRemoveButton).disabled)
            with patch("ft_tui.features.projects.views.testers.WorkspaceSession") as terminal:
                terminal.return_value.phase = "Preparing the tester…"
                widget._start("remove", app.tester_catalog.testers[0])
                await pilot.pause(.4)
                await widget.workers.wait_for_complete()
                await widget._inspection_worker.wait()
            self.assertIn("failed", widget._messages["supra-libft"])
            self.assertNotIn("supra-libft", widget._retry)
            self.assertEqual(str(widget.query_one(TesterAction).label), "Run Supra libft tester")
            self.assertFalse(widget.query_one(TesterRemoveButton).disabled)
            with service.operation():
                await self.select(widget, projects["libft"], pilot)
                self.assertTrue(widget.query_one(TesterRemoveButton).disabled)

    async def test_setup_failure_releases_operation_and_preserves_log(self):
        async with self.workspace() as (app, widget, service, projects, pilot, root):
            service.prepare_and_run = Mock(side_effect=TesterError("build failed"))
            await self.select(widget, projects["libft"], pilot)
            await widget._perform("run", app.tester_catalog.testers[0], str(root), None)
            self.assertFalse(service.busy)
            self.assertFalse(widget._operating)
            self.assertIn("supra-libft", widget._retry)
            self.assertIn("build failed", widget._workspace.log_path.read_text())

    async def test_invalid_catalog_warning_keeps_bundled_tester_usable(self):
        async with self.workspace(invalid_catalog=True) as (_app, widget, _service, projects, pilot, root):
            projects["libft"].local_path = str(root)
            await self.select(widget, projects["libft"], pilot)
            warning = widget.query_one("#tester-catalog-warning")
            self.assertTrue(warning.display)
            self.assertIn("Invalid tester configuration", str(warning.render()))
            self.assertEqual(str(widget.query_one(TesterAction).label), "Run Supra libft tester")
            self.assertFalse(widget.query_one(TesterAction).disabled)

    async def test_user_directory_installation_requires_explicit_confirmation(self):
        async with self.workspace() as (app, widget, service, projects, pilot, root):
            projects["libft"].local_path = str(root)
            service.host = Host("darwin", "arm64")
            service.status.return_value = DockerStatus("missing")
            service.install_docker = Mock()
            await self.select(widget, projects["libft"], pilot)
            button = widget.query_one(TesterAction)
            widget.on_button_pressed(Button.Pressed(button))
            await pilot.pause()
            self.assertIsInstance(app.screen, DockerInstallScreen)
            service.install_docker.assert_not_called()
            await pilot.press("escape")
            await pilot.pause()
            service.install_docker.assert_not_called()
            self.assertFalse(widget._operating)

    async def test_approved_setup_runs_original_project_after_selection_changes(self):
        async with self.workspace() as (app, widget, service, projects, pilot, root):
            projects["libft"].local_path = str(root)
            service.host = Host("darwin", "arm64")
            service.status.return_value = DockerStatus("missing")
            service.prepare_and_run = Mock()
            await self.select(widget, projects["libft"], pilot)
            plan = widget._setup_plan
            widget.on_button_pressed(Button.Pressed(widget.query_one(TesterAction)))
            await pilot.pause()
            widget.project = projects["ft_printf"]
            with patch("ft_tui.features.projects.views.testers.WorkspaceSession") as terminal:
                terminal.return_value.phase = "Preparing the tester…"
                app.screen.query_one("#confirm-docker-install", Button).press()
                await pilot.pause(.4)
                await widget.workers.wait_for_complete()
            service.prepare_and_run.assert_called_once_with(
                app.tester_catalog.testers[0], str(root), terminal.return_value, plan=plan,
            )



class TesterInspectionLifecycleTests(unittest.IsolatedAsyncioTestCase):
    @asynccontextmanager
    async def inspection(self):
        from textual.app import App

        class Harness(App):
            language = 'en'

            def compose(self):
                yield ProjectTesters()

        with TemporaryDirectory() as directory:
            root = Path(directory)
            app = Harness()
            app.tester_catalog = load_catalog(root/'absent.toml')
            app.tester_docker = TesterDocker(root/'testers', Host('linux', 'amd64', 'ubuntu', 'noble'))
            app.tester_docker.status = Mock(return_value=DockerStatus('ready'))
            app.tester_docker.installed = Mock(return_value=False)
            app.tester_docker.has_images = Mock(return_value=False)
            async with app.run_test() as pilot:
                await pilot.pause()
                widget = app.query_one(ProjectTesters)
                widget.set_project(None)
                await widget._inspection_worker.wait()
                yield app, widget, app.tester_docker

    async def test_queued_inspection_ignores_controls_removed_before_start(self):
        async with self.inspection() as (_app, widget, service):
            generation = widget._generation
            await widget.remove_children()
            await widget._refresh(generation)
            service.status.assert_not_called()

    async def test_inflight_inspection_ignores_controls_removed_during_probe(self):
        import asyncio
        import threading

        entered, release = threading.Event(), threading.Event()

        def status():
            entered.set()
            if not release.wait(3):
                raise AssertionError('Test did not release Docker status probe')
            return DockerStatus('ready')

        try:
            async with self.inspection() as (_app, widget, service):
                service.status.side_effect = status
                widget.set_project(Project(slug='libft', name='Libft'))
                worker = widget._inspection_worker
                self.assertTrue(await asyncio.to_thread(entered.wait, 2))
                await widget.remove_children()
                release.set()
                await worker.wait()
                self.assertFalse(widget.query('#tester-status'))
        finally:
            release.set()


class TesterConsoleRenderingTests(unittest.TestCase):
    def test_cursor_redraw_does_not_duplicate_compilation_status(self):
        from ft_tui.features.projects.adapters.tester_console import TesterConsole
        console = TesterConsole()
        console.feed("Compiling tests: fsoares\r\n")
        for _ in range(15):
            console.feed("\x1b[1")
            console.feed("A\r\x1b[2KCompiling tests: fsoares\r\n")
        output = console.render().plain
        self.assertEqual(output.count("Compiling tests: fsoares"), 1)

    def test_partial_lines_colors_and_scrollback(self):
        from ft_tui.features.projects.adapters.tester_console import TesterConsole
        console = TesterConsole()
        console.feed("\x1b[31mhel")
        console.feed("lo\x1b[0m\rbye\x1b[K")
        self.assertEqual(console.render().plain, "bye")
        console.feed("\r\n" + "line\r\n" * 35)
        self.assertTrue(console.screen.history.top)
        self.assertIn("bye", console.render().plain)


class TesterLogFolderTests(unittest.IsolatedAsyncioTestCase):
    async def test_folder_action_and_failure_feedback(self):
        from textual.app import App
        from ft_tui.features.projects.views.tester_workspace import TesterWorkspace
        class Harness(App):
            language = 'en'
        app = Harness()
        async with app.run_test() as pilot:
            screen = TesterWorkspace('Test', Path('/tmp/tester/logs/run.log'))
            await app.push_screen(screen)
            await pilot.pause()
            self.assertEqual(screen.query_one("#tester-output").styles.padding.left, 1)
            with patch('ft_tui.features.projects.views.tester_workspace.open_project_folder') as open_folder:
                await screen._open_log_folder()
                open_folder.assert_called_once_with('/tmp/tester/logs')
            with patch('ft_tui.features.projects.views.tester_workspace.open_project_folder', side_effect=OSError('denied')), \
                    patch.object(app, 'notify') as notify:
                await screen._open_log_folder()
                self.assertIn('denied', notify.call_args.args[0])


class TesterInputVisibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_interactive_input_visibility_tracks_run(self):
        from textual.app import App
        from ft_tui.features.projects.views.tester_workspace import TesterWorkspace
        class Harness(App):
            language = "en"
        app = Harness()
        async with app.run_test() as pilot:
            for interactive in (False, True):
                screen = TesterWorkspace("Test", Path("/tmp/test.log"), interactive_input=interactive)
                await app.push_screen(screen)
                await pilot.pause()
                self.assertEqual(screen.query_one("#tester-input").display, interactive)
                screen.finished = screen.started
                screen.refresh_output()
                self.assertFalse(screen.query_one("#tester-input").display)
                await app.pop_screen()


class TesterLogEditorTests(unittest.TestCase):
    def test_file_uses_preferred_editor_and_preserves_path_arguments(self):
        from contextlib import nullcontext
        from ft_tui.features.projects.views.navigation import ProjectNavigationMixin
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "run 'with spaces'.log"
            log_path.write_text("synthetic test output")
            host = Mock()
            host._open_path_in_editor = lambda name, path: ProjectNavigationMixin._open_path_in_editor(host, name, path)
            host.suspend.return_value = nullcontext()
            for editor, command in (("vscode", "code"), ("zed", "zed"), ("vim", "vim"), ("nvim", "nvim")):
                host.favorite_editor = editor
                with patch("ft_tui.features.projects.views.navigation.shutil.which", return_value=f"/bin/{command}"), \
                     patch("ft_tui.features.projects.views.navigation.subprocess.Popen") as opened, \
                     patch("ft_tui.features.projects.views.navigation.subprocess.run", return_value=Mock(returncode=0)) as ran:
                    ProjectNavigationMixin._open_file_in_editor(host, log_path)
                    launch = ran if editor in ("vim", "nvim") else opened
                    launch.assert_called_once()
                    args = launch.call_args.args[0]
                    self.assertEqual(args[-1], str(log_path))
                    self.assertEqual(launch.call_args.kwargs["cwd"], log_path.parent)
                    self.assertEqual("--reuse-window" in args, editor == "vscode")
                    launch.reset_mock()
                    ProjectNavigationMixin._open_project_in_editor(host, "Synthetic", log_path.parent)
                    self.assertEqual(launch.call_args.args[0][-1], "." if editor in ("vim", "nvim") else str(log_path.parent))
                    self.assertEqual(launch.call_args.kwargs["cwd"], log_path.parent)
            with patch("ft_tui.features.projects.views.navigation.shutil.which", return_value=None):
                ProjectNavigationMixin._open_file_in_editor(host, log_path)
                host.notify.assert_called_with("nvim was not found on PATH.", severity="error")
            log_path.unlink()
            ProjectNavigationMixin._open_file_in_editor(host, log_path)
            host.notify.assert_called_with("The log file no longer exists.", severity="error")
