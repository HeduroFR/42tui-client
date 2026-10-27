"""Project tester controls, dependency consent and terminal handoff."""

from __future__ import annotations

import asyncio
import subprocess
import webbrowser
from functools import partial
from typing import ClassVar

from rich.markup import escape
from textual.containers import Horizontal, Vertical, VerticalScroll

from ft_tui.i18n import translate
from ft_tui.features.projects.adapters.tester_catalog import Tester
from ft_tui.features.projects.adapters.tester_docker import DockerInstallation, TesterError
from ft_tui.features.projects.adapters.tester_terminal import TerminalSession, wait_for_key
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
            yield Static("Install Docker", classes="panel-title")
            with VerticalScroll(id="docker-install-scroll"):
                yield Static("These commands install Docker on this computer. Commands using sudo require administrator approval.")
                yield Static("Existing conflicting Docker packages must be resolved manually using the official instructions.")
                yield Static(self.plan.preview(), markup=False, localize=False)
                yield Static("On macOS, finish Docker Desktop setup and start Docker, then check access again.")
            yield Button("Install Docker", id="confirm-docker-install")
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
        super().__init__("×", variant="error", classes="tester-remove", id=f"tester-remove-{tester.id}", tooltip=tooltip)
        self.tester = tester
        self.tooltip = translate(tooltip, language)


class ProjectTesters(Vertical):
    DEFAULT_CSS = """
    ProjectTesters { height: auto; border-top: solid $secondary; margin-top: 1; padding-top: 1; }
    ProjectTesters Static, #tester-rows { height: auto; }
    ProjectTesters Button { width: 1fr; min-width: 0; margin-top: 1; }
    ProjectTesters .tester-action-row { height: auto; }
    ProjectTesters .tester-remove { width: 5; min-width: 5; padding: 0; margin-left: 1; }
    #tester-catalog-warning { color: $warning; }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.project = None
        self._operating = False
        self._messages: dict[str, str] = {}
        self._retry: set[str] = set()
        self._generation = 0

    def compose(self):
        yield Static("Testers", classes="panel-title")
        yield Static("", id="tester-catalog-warning")
        yield Static("Select a project to see testers.", id="tester-status")
        yield Vertical(id="tester-rows")
        yield Button("Install Docker", id="tester-install-docker")
        yield Button("Start Docker Desktop", id="tester-start-docker")
        yield Button("Docker instructions", id="tester-docker-docs")
        yield Button("Check Docker access again", id="tester-recheck")

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
                "#tester-status", "#tester-rows", "#tester-install-docker",
                "#tester-start-docker", "#tester-docker-docs", "#tester-recheck",
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
        self.query_one("#tester-status", Static).update("Checking Docker…" if testers else (
            "No tester is configured for this project on this platform." if project
            else "Select a project to see testers."
        ))
        await self.query_one("#tester-rows").remove_children()
        if not self._inspection_current(generation):
            return
        for selector in ("#tester-install-docker", "#tester-start-docker", "#tester-docker-docs", "#tester-recheck"):
            self.query_one(selector).display = False
        if not testers:
            return
        # Avoid repeated daemon probes while moving through the project list.
        await asyncio.sleep(0.12)
        if not self._inspection_current(generation):
            return
        status = await asyncio.to_thread(service.status)
        if not self._inspection_current(generation):
            return
        installed = await asyncio.to_thread(lambda: {tester.id for tester in testers if service.installed(tester)}) if (
            status.state == "ready"
        ) else set()
        if not self._inspection_current(generation):
            return
        removable = await asyncio.to_thread(lambda: {tester.id for tester in testers if service.has_images(tester)}) if (
            status.state == "ready"
        ) else set()
        if not self._inspection_current(generation):
            return
        self._docker_state = status.state
        messages = {
            "ready": "Docker is ready. Container execution and folder access are checked before each run.",
            "incompatible": "A Linux Docker engine is required.",
            "missing": "Docker is not installed.",
            "stopped": "Docker is not responding. Start the engine and check access again.",
            "denied": "Docker access was denied. Check your Docker context, DOCKER_HOST and socket permissions. For rootless Docker, start your user daemon. Do not run 42TUI with sudo.",
            "unsupported": "Docker testers require Linux or macOS on amd64 or arm64.",
        }
        message = translate(messages[status.state], self.app.language)
        if status.detail:
            message += "\n" + escape(status.detail)
        if status.state == "denied" and service.host.system == "linux":
            message += "\n" + translate(
                "For a system Docker Engine, an administrator can grant Docker group access: sudo usermod -aG docker <login>. Then sign out and back in.",
                self.app.language,
            )
        if status.state == "ready" and not has_local_folder(project.local_path):
            message += "\n" + translate("Configure an existing local project folder to run tests.", self.app.language)
        self.query_one("#tester-status", Static).update(message)
        rows = self.query_one("#tester-rows")
        for tester in testers:
            action = "run" if tester.id in installed else "install"
            button = TesterAction(tester, action, tester.id in self._retry)
            button.disabled = (self._operating or service.busy or status.state != "ready"
                               or (action == "run" and not has_local_folder(project.local_path)))
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
        for selector, visible in (
            ("#tester-install-docker", status.state == "missing" and service.installation() is not None),
            ("#tester-start-docker", status.state == "stopped" and service.host.system == "darwin"),
            ("#tester-docker-docs", status.state != "ready"),
            ("#tester-recheck", True),
        ):
            button = self.query_one(selector, Button)
            button.display = visible
            button.disabled = self._operating or service.busy

    def focus_actions(self) -> None:
        """Reveal tester controls from the Projects heading or its keyboard shortcut."""
        for button in self.query(Button):
            if button.display and not button.disabled:
                button.focus(scroll_visible=False)
                button.scroll_visible(animate=False, top=True, immediate=True)
                return
        self.scroll_visible(animate=False, top=True, immediate=True)

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.disabled or self._operating or self.app.tester_docker.busy:
            return
        if isinstance(event.button, TesterAction):
            self._start(event.button.tester_action, event.button.tester)
        elif isinstance(event.button, TesterRemoveButton):
            self._start("remove", event.button.tester)
        elif event.button.id == "tester-recheck":
            self.set_project(self.project)
        elif event.button.id == "tester-docker-docs":
            host = self.app.tester_docker.host
            url = "https://docs.docker.com/engine/install/linux-postinstall/" if (
                getattr(self, "_docker_state", "") == "denied" and host.system == "linux"
            ) else host.docs
            webbrowser.open(url)
        elif event.button.id == "tester-start-docker":
            self._start("start-docker")
        elif event.button.id == "tester-install-docker":
            plan = self.app.tester_docker.installation()
            if plan:
                self.app.push_screen(DockerInstallScreen(plan), lambda approved: self._start("docker", plan=plan)
                                     if approved else None)

    def _start(self, action, tester=None, *, plan=None):
        if self._operating or self.app.tester_docker.busy:
            return
        self._operating = True
        for button in self.query(Button):
            button.disabled = True
        self.query_one("#tester-status", Static).update("Tester operation in progress…")
        project_path = self.project.local_path if self.project else None
        self.run_worker(partial(self._perform, action, tester, project_path, plan), group="tester-operation")

    async def _perform(self, action, tester, project_path, plan):
        service = self.app.tester_docker
        language = self.app.language
        key = tester.id if tester else "docker"
        message = "Tester operation completed."
        log_path = None
        try:
            with service.operation():
                log_path = service.log_path(action)
                # Keep child output and the return-key prompt inside the terminal handoff.
                with log_path.open("wb") as log, self.app.suspend():
                    terminal = TerminalSession(log, language=language)
                    try:
                        if action == "install":
                            service.install(tester, terminal)
                        elif action == "run":
                            service.run(tester, project_path, terminal)
                        elif action == "remove":
                            service.remove(tester, terminal)
                            message = "Tester removed. Install it again to run tests."
                        elif action == "docker":
                            service.install_docker(plan, terminal)
                            terminal.write("Finish Docker setup, then check Docker access again.")
                        elif action == "start-docker":
                            terminal.run(["open", "-a", "Docker"])
                        self._retry.discard(key)
                    except (KeyboardInterrupt, EOFError):
                        message = "Tester operation interrupted. You can retry."
                        if action != "remove":
                            self._retry.add(key)
                    except (TesterError, OSError, subprocess.SubprocessError) as error:
                        message = "Tester operation failed. You can retry."
                        if action != "remove":
                            self._retry.add(key)
                        terminal.write(str(error))
                    finally:
                        terminal.write(message)
                        terminal.write(translate("Log: {path}", language).format(path=log_path))
                        try:
                            wait_for_key(translate("Press any key to return to 42TUI.", language))
                        except (KeyboardInterrupt, EOFError):
                            pass
        except (KeyboardInterrupt, EOFError):
            message = "Tester operation interrupted. You can retry."
            if action != "remove":
                self._retry.add(key)
        except (TesterError, OSError, subprocess.SubprocessError) as error:
            message = "Tester operation failed. You can retry."
            if action != "remove":
                self._retry.add(key)
            self.app.notify(f"{translate(message, language)} {error}", severity="error")
        finally:
            self._operating = False
            text = translate(message, language)
            if log_path:
                text += "\n" + translate("Log: {path}", language).format(path=escape(str(log_path)))
            self._messages[key] = text
            self.app.refresh(layout=True)
            self.set_project(self.project)
            if tester is None:
                self.app.notify(text, timeout=10)
