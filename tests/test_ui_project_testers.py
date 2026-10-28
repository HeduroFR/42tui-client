"""Project tester state transitions and guaranteed terminal restoration."""

import unittest
from contextlib import asynccontextmanager, contextmanager, nullcontext
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
                for slug in ("libft", "ft_printf", "get_next_line"):
                    projects[slug].local_path = None
                    await self.select(widget, projects[slug], pilot)
                    button = widget.query_one(TesterAction)
                    self.assertEqual(str(button.label), "Run Francinette")
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
                self.assertEqual(len(buttons), 1)
                self.assertEqual(str(buttons[0].label), "Run Francinette")
                self.assertFalse(buttons[0].disabled)

    async def test_terminal_restored_after_success_failure_and_interrupt_and_double_click(self):
        async with self.workspace() as (app, widget, service, projects, pilot, root):
            projects["libft"].local_path = str(root)
            await self.select(widget, projects["libft"], pilot)
            restored = []
            @contextmanager
            def suspend():
                restored.append("enter")
                try:
                    yield
                finally:
                    restored.append("exit")
            for error in (None, TesterError("build failure"), KeyboardInterrupt()):
                service.prepare_and_run = Mock(side_effect=error)
                with patch.object(app, "suspend", side_effect=suspend), \
                        patch("ft_tui.features.projects.views.testers.wait_for_key") as key, \
                        patch("ft_tui.features.projects.views.testers.TerminalSession"):
                    widget._start("run", app.tester_catalog.testers[0])
                    widget._start("run", app.tester_catalog.testers[0])
                    self.assertTrue(widget._operating)
                    await pilot.pause(0.4)
                    await widget.workers.wait_for_complete()
                    await pilot.pause()
                    service.prepare_and_run.assert_called_once()
                    key.assert_called_once()
                    self.assertEqual(restored[-2:], ["enter", "exit"])
                    self.assertFalse(widget._operating)
                    self.assertFalse(service.busy)
                    self.assertFalse(widget.query_one(TesterAction).disabled)
                    self.assertEqual("francinette" in widget._retry, error is not None)
                    if isinstance(error, TesterError):
                        self.assertIn("build failure", widget._messages["francinette"])
            self.assertEqual(len(list((root / "testers/logs").glob("*.log"))), 3)

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

    async def test_long_docker_diagnostic_scrolls_without_hiding_folder_guidance(self):
        async with self.workspace() as (_app, widget, service, projects, pilot, _root):
            detail = '\n'.join(f'Docker diagnostic line {index}' for index in range(20))
            service.status.return_value = DockerStatus('stopped', detail)
            await self.select(widget, projects['libft'], pilot)
            status = widget.query_one('#tester-status')
            text = str(status.render())
            self.assertIn(detail, text)
            self.assertLess(text.index('Configure an existing local project folder'), text.index('Docker diagnostic'))
            scroll = widget.query_one('#tester-status-scroll')
            self.assertLessEqual(scroll.size.height, 5)
            self.assertGreater(scroll.max_scroll_y, 0)

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
            self.assertEqual(remove.region.width, 5)
            self.assertIn("all projects", str(remove.tooltip))
            self.assertTrue(app.screen.region.contains_region(remove.region))
            def removed(*args):
                service.has_images.return_value = False
                service.installed.return_value = False
            service.remove = Mock(side_effect=removed)
            with patch.object(app, "suspend", side_effect=nullcontext), \
                    patch("ft_tui.features.projects.views.testers.wait_for_key"), \
                    patch("ft_tui.features.projects.views.testers.TerminalSession"):
                remove.press()
                remove.press()
                await pilot.pause(.4)
                await widget.workers.wait_for_complete()
                await widget._inspection_worker.wait()
            service.remove.assert_called_once()
            self.assertFalse(widget.query(TesterRemoveButton))
            self.assertFalse(service.busy)
            self.assertIn("removed", widget._messages["francinette"])
            await self.select(widget, projects["ft_printf"], pilot)
            self.assertFalse(widget.query(TesterRemoveButton))
            self.assertEqual(str(widget.query_one(TesterAction).label), "Run Francinette")

    async def test_remove_failure_keeps_the_delete_action_available_without_changing_run_retry(self):
        async with self.workspace() as (app, widget, service, projects, pilot, _root):
            service.installed.return_value = True
            service.has_images.return_value = True
            service.remove = Mock(side_effect=TesterError("image in use"))
            await self.select(widget, projects["libft"], pilot)
            self.assertTrue(widget.query_one(TesterAction).disabled)
            self.assertFalse(widget.query_one(TesterRemoveButton).disabled)
            with patch.object(app, "suspend", side_effect=nullcontext), \
                    patch("ft_tui.features.projects.views.testers.wait_for_key"), \
                    patch("ft_tui.features.projects.views.testers.TerminalSession"):
                widget._start("remove", app.tester_catalog.testers[0])
                await pilot.pause(.4)
                await widget.workers.wait_for_complete()
                await widget._inspection_worker.wait()
            self.assertIn("failed", widget._messages["francinette"])
            self.assertNotIn("francinette", widget._retry)
            self.assertEqual(str(widget.query_one(TesterAction).label), "Run Francinette")
            self.assertFalse(widget.query_one(TesterRemoveButton).disabled)
            with service.operation():
                await self.select(widget, projects["libft"], pilot)
                self.assertTrue(widget.query_one(TesterRemoveButton).disabled)

    async def test_interrupt_during_terminal_handoff_releases_operation(self):
        async with self.workspace() as (app, widget, service, projects, pilot, _root):
            await self.select(widget, projects["libft"], pilot)
            with patch.object(app, "suspend", side_effect=KeyboardInterrupt):
                await widget._perform("run", app.tester_catalog.testers[0], None, None)
            self.assertFalse(service.busy)
            self.assertFalse(widget._operating)
            self.assertIn("francinette", widget._retry)
            self.assertIn("interrupted", widget._messages["francinette"])

    async def test_invalid_catalog_warning_keeps_bundled_tester_usable(self):
        async with self.workspace(invalid_catalog=True) as (_app, widget, _service, projects, pilot, root):
            projects["libft"].local_path = str(root)
            await self.select(widget, projects["libft"], pilot)
            warning = widget.query_one("#tester-catalog-warning")
            self.assertTrue(warning.display)
            self.assertIn("Invalid tester configuration", str(warning.render()))
            self.assertEqual(str(widget.query_one(TesterAction).label), "Run Francinette")
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
            with patch.object(app, "suspend", side_effect=nullcontext), \
                    patch("ft_tui.features.projects.views.testers.wait_for_key"), \
                    patch("ft_tui.features.projects.views.testers.TerminalSession") as terminal:
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
