"""Project tester controls, dependency consent and terminal handoff."""

from __future__ import annotations

import asyncio
import subprocess
import time
from functools import partial
from typing import ClassVar

from rich.markup import escape
from textual.containers import Horizontal, Vertical, VerticalScroll

from ft_tui.i18n import translate
from ft_tui.features.projects.adapters.tester_catalog import Tester
from ft_tui.features.projects.adapters.tester_docker import DockerInstallation, TesterError
from ft_tui.features.projects.adapters.tester_terminal import WorkspaceSession
from ft_tui.features.projects.views.tester_workspace import TesterWorkspace
from ft_tui.ui.components import Button, Static, has_local_folder
from ft_tui.ui.modal import AppModal


class DockerInstallScreen(AppModal[bool]):
    BINDINGS: ClassVar = [("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    DockerInstallScreen { background: $background 70%; }
    #docker-install-dialog { width: 90%; height: 85%; border: round $primary; padding: 1 2; }
    #docker-install-scroll { height: 1fr; }
    #docker-install-scroll Static { height: auto; }
    """

    def __init__(self, plan: DockerInstallation):
        super().__init__()
        self.plan = plan

    def compose(self):
        with Vertical(id="docker-install-dialog"):
            yield Static("Set up tester dependencies", classes="panel-title")
            with VerticalScroll(id="docker-install-scroll"):
                user_service = all(command[0] == "systemctl" for command in self.plan.commands)
                if user_service:
                    yield Static("These commands start your Docker user service without administrator access.")
                else:
                    yield Static("These commands install Docker Desktop in your home directory without administrator access.")
                    yield Static("Keep Docker Desktop user-level settings. Do not enable system CLI links, the default socket or privileged port mapping.")
                yield Static(self.plan.preview(), markup=False, localize=False)
                if not user_service:
                    yield Static("On macOS, finish Docker Desktop installation and setup if prompted. Tests will continue automatically.")
            yield Button("Continue and run", id="confirm-docker-install")
            yield Button("Cancel", id="cancel-docker-install")

    def action_cancel(self):
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        self.dismiss(event.button.id == "confirm-docker-install")


class TesterAction(Button):
    def __init__(self, tester: Tester, action: str, retry: bool = False, **kwargs):
        source = {"install": "Install {name}", "run": "Run {name}"}[action]
        if retry:
            source = "Retry {name}"
        super().__init__(source.format(name=tester.name), **kwargs)
        self.tester = tester
        self.tester_action = action


class TesterRemoveButton(Button):
    def __init__(self, tester: Tester, language: str):
        tooltip = f"Remove {tester.name} images for all projects to free disk space. Reinstallation will be required."
        super().__init__("×", square=True, variant="danger", classes="tester-remove", id=f"tester-remove-{tester.id}", tooltip=tooltip)
        self.tester = tester
        self.tooltip = translate(tooltip, language)


class ProjectTesters(Vertical):
    DEFAULT_CSS = """
    ProjectTesters { height: auto; border-top: solid $secondary; margin-top: 1; padding-top: 1; }
    ProjectTesters Static, #tester-rows { height: auto; }
    ProjectTesters Button { width: 1fr; min-width: 0; margin-top: 1; }
    ProjectTesters .tester-action-row { height: 3; margin-top: 1; align-vertical: middle; }
    ProjectTesters .tester-action-row Button { height: 3; margin-top: 0; margin-bottom: 0; }
    ProjectTesters .tester-action-row TesterAction { margin-right: 2; }
    #tester-catalog-warning { color: $warning; }
    #tester-status-scroll { height: auto; max-height: 5; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.project = None
        self._operating = False
        self._messages: dict[str, str] = {}
        self._retry: set[str] = set()
        self._generation = 0
        self._setup_plan = None
        self._workspace = None

    def compose(self):
        yield Static("Testers", classes="panel-title")
        yield Static("", id="tester-catalog-warning")
        with VerticalScroll(id="tester-status-scroll"):
            yield Static("Select a project to see testers.", id="tester-status")
        yield Vertical(id="tester-rows")
        yield Button("Tester workspace", id="tester-workspace-open")

    def on_mount(self):
        for button in self.query(Button):
            button.display = False
        error = self.app.tester_catalog.error
        warning = self.query_one("#tester-catalog-warning", Static)
        warning.display = bool(error)
        if error:
            message = translate("Invalid tester configuration. Using the bundled catalog.", self.app.language)
            warning.update(f"{message}\n{escape(error)}")
        self.set_project(self.project)

    def set_project(self, project):
        self.project = project
        self._generation += 1
        if not self.is_mounted or not self.query("#tester-status"):
            return
        self._inspection_worker = self.run_worker(
            partial(self._refresh, self._generation), group="tester-inspection", exclusive=True,
        )

    def on_unmount(self):
        self._generation += 1
        worker = getattr(self, "_inspection_worker", None)
        if worker is not None:
            worker.cancel()

    def _inspection_current(self, generation):
        # Workers may start or resume while Textual is removing our children.
        return generation == self._generation and self.is_attached and all(
            self.query(selector) for selector in (
                "#tester-status", "#tester-rows",
            )
        )

    async def _refresh(self, generation):
        if not self._inspection_current(generation):
            return
        project = self.project
        service = self.app.tester_docker
        catalog = self.app.tester_catalog
        testers = catalog.for_project(project.slug, service.host.system) if project else ()
        for button in self.query(Button):
            button.disabled = True
        if self._workspace is not None:
            button = self.query_one("#tester-workspace-open", Button)
            button.display = True
            button.disabled = False
        self.query_one("#tester-status", Static).update("Checking Docker…" if testers else (
            "No tester is configured for this project on this platform." if project
            else "Select a project to see testers."
        ))
        await self.query_one("#tester-rows").remove_children()
        if not self._inspection_current(generation):
            return
        self._setup_plan = None
        if not testers:
            return
        # Avoid repeated daemon probes while moving through the project list.
        await asyncio.sleep(0.12)
        if not self._inspection_current(generation):
            return
        status = await asyncio.to_thread(service.status)
        if not self._inspection_current(generation):
            return
        setup_plan = await asyncio.to_thread(service.setup_plan, status)
        if not self._inspection_current(generation):
            return
        self._setup_plan = setup_plan
        removable = await asyncio.to_thread(lambda: {tester.id for tester in testers if service.has_images(tester)}) if (
            status.state == "ready"
        ) else set()
        if not self._inspection_current(generation):
            return
        self._docker_state = status.state
        messages = {
            "ready": "Docker is ready. Container execution and folder access are checked before each run.",
            "incompatible": "A Linux Docker engine is required.",
            "missing": "Docker is not installed. Run the tester to set it up.",
            "stopped": "Docker is not responding. Run the tester to start or retry setup.",
            "denied": "Docker access was denied. Select an accessible Docker context or ask school staff to enable access. 42TUI does not change permissions.",
            "unsupported": "Docker testers require Linux or macOS on amd64 or arm64.",
        }
        message = translate(messages[status.state], self.app.language)
        if status.state == "missing" and service.host.system == "linux":
            message = translate(
                "An accessible Docker engine is required on Linux. Ask school staff if Docker is missing. No system changes were made.",
                self.app.language,
            )
        if not has_local_folder(project.local_path):
            message += "\n" + translate("Configure an existing local project folder to run tests.", self.app.language)
        status_widget = self.query_one("#tester-status", Static)
        status_widget.update(message)
        status_widget.tooltip = escape(status.detail) if status.detail else None
        rows = self.query_one("#tester-rows")
        for tester in testers:
            button = TesterAction(tester, "run", tester.id in self._retry)
            button.disabled = self._operating or service.busy or not has_local_folder(project.local_path)
            controls = [button]
            if tester.id in removable:
                remove = TesterRemoveButton(tester, self.app.language)
                remove.disabled = self._operating or service.busy
                controls.append(remove)
            await rows.mount(Horizontal(*controls, classes="tester-action-row"))
            if not self._inspection_current(generation):
                return
            if tester.id in self._messages:
                await rows.mount(Static(self._messages[tester.id]))
                if not self._inspection_current(generation):
                    return

    def focus_actions(self) -> None:
        """Reveal tester controls using the project keyboard shortcut."""
        for button in self.query(Button):
            if button.display and not button.disabled:
                button.focus(scroll_visible=False)
                button.scroll_visible(animate=False, top=True, immediate=True)
                return
        self.scroll_visible(animate=False, top=True, immediate=True)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == "tester-workspace-open":
            if self._workspace and not self._workspace.is_current:
                self.app.push_screen("tester-workspace")
            return
        if event.button.disabled or self._operating or self.app.tester_docker.busy:
            return
        if isinstance(event.button, TesterAction):
            tester = event.button.tester
            project_path = self.project.local_path if self.project else None
            plan = self._setup_plan
            if plan:
                self.app.push_screen(
                    DockerInstallScreen(plan),
                    lambda approved: self._start("run", tester, plan=plan, project_path=project_path)
                    if approved else None,
                )
            else:
                self._start("run", tester, project_path=project_path)
        elif isinstance(event.button, TesterRemoveButton):
            self._start("remove", event.button.tester)

    def _start(self, action, tester=None, *, plan=None, project_path=None):
        if self._operating or self.app.tester_docker.busy:
            return
        self._operating = True
        for button in self.query(Button):
            button.disabled = True
        self.query_one("#tester-status", Static).update("Tester operation in progress…")
        if project_path is None:
            project_path = self.project.local_path if self.project else None
        self.app.run_worker(self._perform(action, tester, project_path, plan), group="tester-operation")

    async def _perform(self, action, tester, project_path, plan):
        service = self.app.tester_docker
        language = self.app.language
        key = tester.id if tester else "docker"
        message = "Tester finished. Read the log for test results."
        log_path = None
        error_detail = None
        try:
            log_path = service.log_path(action)
            if self.app.is_screen_installed("tester-workspace"):
                self.app.uninstall_screen("tester-workspace")
            workspace = self._workspace = TesterWorkspace(
                f"{tester.name if tester else 'Docker'} · {project_path or action}", log_path,
                rerun=partial(self._start, action, tester, plan=plan, project_path=project_path) if action == "run" else None)
            self.app.install_screen(workspace, "tester-workspace")
            await self.app.push_screen("tester-workspace")
            button = self.query_one("#tester-workspace-open", Button)
            button.display, button.disabled = True, False
            with log_path.open("wb") as log:
                terminal = workspace.session = WorkspaceSession(log, workspace.output.append, language=language)

                def operate():
                    try:
                        with service.operation():
                            if action == "run":
                                service.prepare_and_run(tester, project_path, terminal, plan=plan)
                            elif action == "remove":
                                service.remove(tester, terminal)
                            terminal.check_cancelled()
                    except (KeyboardInterrupt, EOFError):
                        return False
                    return True

                task = asyncio.create_task(asyncio.to_thread(operate))
                try:
                    completed = await asyncio.shield(task)
                except asyncio.CancelledError:
                    terminal.cancel()
                    # Keep the transcript open until child and container cleanup finish.
                    try:
                        await task
                    except (TesterError, OSError, subprocess.SubprocessError):
                        pass
                    raise
            if not completed:
                raise EOFError
            if action == "remove":
                message = "Tester removed. Run it again to reinstall and test."
            self._retry.discard(key)
        except (EOFError, asyncio.CancelledError):
            message = "Tester operation interrupted. You can retry."
            if action != "remove":
                self._retry.add(key)
        except (TesterError, OSError, subprocess.SubprocessError) as error:
            message = "Tester operation failed. You can retry."
            if action != "remove":
                self._retry.add(key)
            error_detail = str(error)
        finally:
            self._operating = False
            text = translate(message, language)
            if error_detail:
                text += "\n" + translate(error_detail, language)
            if log_path:
                text += "\n" + translate("Log: {path}", language).format(path=log_path)
                try:
                    with log_path.open("ab") as log:
                        log.write((text + "\n").encode())
                except OSError as error:
                    text += "\n" + str(error)
            if self._workspace is not None:
                self._workspace.result = message
                self._workspace.finished = time.monotonic()
                display_text = (text + "\n").replace("\r\n", "\n").replace("\n", "\r\n")
                self._workspace.output.append(display_text.encode())
            self._messages[key] = escape(text)
            if self.is_mounted:
                self.set_project(self.project)
