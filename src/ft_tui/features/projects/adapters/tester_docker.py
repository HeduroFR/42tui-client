"""Docker diagnosis, explicit dependency installation and shared tester operations."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ft_tui.config.settings import data_dir
from ft_tui.features.projects.adapters.tester_catalog import Tester

ENGINE_DOCS = "https://docs.docker.com/engine/install/"
MAC_DOCS = "https://docs.docker.com/desktop/setup/install/mac-install/"


def _normalize_architecture(machine: str) -> str:
    machine = machine.lower()
    return {"x86_64": "amd64", "aarch64": "arm64"}.get(machine, machine)


@dataclass(frozen=True)
class Host:
    system: str
    architecture: str
    distribution: str = ""
    codename: str = ""

    @classmethod
    def detect(cls) -> Host:
        release = {}
        if sys.platform == "linux":
            try:
                release = platform.freedesktop_os_release()
            except OSError:
                pass
        architecture = _normalize_architecture(platform.machine())
        return cls(sys.platform, architecture, release.get("ID", ""), release.get("VERSION_CODENAME", ""))

    @property
    def docs(self) -> str:
        if self.system == "darwin":
            return MAC_DOCS
        if self.distribution in {"ubuntu", "debian", "fedora", "centos", "rhel"}:
            return ENGINE_DOCS + self.distribution + "/"
        return ENGINE_DOCS


@dataclass(frozen=True)
class DockerStatus:
    state: str
    detail: str = ""
    architecture: str = ""


@dataclass(frozen=True)
class DockerInstallation:
    commands: tuple[tuple[str, ...], ...]
    source: str = ""

    def preview(self) -> str:
        import shlex
        return "\n".join(shlex.join(command) for command in self.commands) + (
            "\n\n" + self.source if self.source else ""
        )


class TesterError(RuntimeError):
    pass


class TesterDocker:
    def __init__(self, root: Path | None = None, host: Host | None = None) -> None:
        self.root = root if root is not None else data_dir() / "testers"
        self.host = host or Host.detect()
        self._lock = threading.Lock()
        self._connection: ContextVar[tuple[str, list[str], dict[str, str]] | None] = ContextVar(
            "tester_docker_connection", default=None,
        )
        self._engine_architecture: ContextVar[str | None] = ContextVar("tester_engine_architecture", default=None)

    @property
    def busy(self) -> bool:
        return self._lock.locked()

    @contextmanager
    def operation(self):
        if not self._lock.acquire(blocking=False):
            raise TesterError("Another tester operation is running.")
        try:
            yield
        finally:
            self._lock.release()

    def docker(self) -> str | None:
        if self._connection.get() is not None:
            return self._connection.get()[0]
        executable = shutil.which("docker")
        if executable:
            return executable
        if self.host.system == "darwin":
            for path in (Path.home() / ".docker/bin/docker",
                         Path("/Applications/Docker.app/Contents/Resources/bin/docker")):
                if path.is_file():
                    return str(path)
        return None

    @contextmanager
    def connection(self):
        """Snapshot CLI selection and environment without changing user configuration."""
        if self._connection.get() is not None:
            yield
            return
        docker = self.docker()
        if not docker:
            raise TesterError("Docker is not installed.")
        environment = dict(os.environ)
        token = self._connection.set((docker, [], environment))
        architecture_token = self._engine_architecture.set(None)
        try:
            # DOCKER_CONTEXT overrides DOCKER_HOST. Otherwise keep a supplied host
            # (and its TLS variables), or freeze the currently selected context.
            context = environment.get("DOCKER_CONTEXT")
            if not context and not environment.get("DOCKER_HOST"):
                result = self._capture([docker, "context", "show"])
                if result.returncode or not result.stdout.strip():
                    raise TesterError("The active Docker context could not be resolved.")
                context = result.stdout.strip()
            self._connection.set((docker, ["--context", context] if context else [], environment))
            yield
        finally:
            self._engine_architecture.reset(architecture_token)
            self._connection.reset(token)

    def _arguments(self, args):
        connection = self._connection.get()
        if connection and args[0] == connection[0]:
            return [args[0], *connection[1], *args[1:]]
        return args

    def _run(self, terminal, args):
        connection = self._connection.get()
        terminal.run(self._arguments(args), env=connection[2] if connection else None)

    def _capture(self, args: list[str]) -> subprocess.CompletedProcess:
        connection = self._connection.get()
        return subprocess.run(self._arguments(args), env=connection[2] if connection else None,
                              capture_output=True, text=True, timeout=15, check=False)

    def status(self) -> DockerStatus:
        if self.host.system not in {"linux", "darwin"} or self.host.architecture not in {"amd64", "arm64"}:
            return DockerStatus("unsupported")
        docker = self.docker()
        if not docker:
            return DockerStatus("missing")
        try:
            result = self._capture([docker, "info", "--format", "{{json .}}"])
        except (OSError, subprocess.TimeoutExpired) as error:
            return DockerStatus("stopped", str(error))
        if result.returncode == 0:
            try:
                info = json.loads(result.stdout)
                if info.get("OSType") != "linux":
                    return DockerStatus("incompatible", "A Linux Docker engine is required.")
                architecture = _normalize_architecture(str(info.get("Architecture", "")))
            except (ValueError, AttributeError):
                return DockerStatus("stopped", "Docker engine information could not be read.")
            if self._connection.get() is not None:
                self._engine_architecture.set(architecture)
            return DockerStatus("ready", architecture=architecture)
        detail = (result.stderr or result.stdout).strip()
        state = "denied" if any(word in detail.lower() for word in ("permission denied", "access denied")) else "stopped"
        return DockerStatus(state, detail)

    def architecture(self, tester: Tester) -> str:
        """Prefer the engine's CPU, including remote engines, when the tester supports it."""
        if len(tester.architectures) == 1:
            return tester.architectures[0]
        architecture = self._engine_architecture.get() if self._connection.get() is not None else None
        if architecture is None:
            architecture = self.status().architecture
        return architecture if architecture in tester.architectures else tester.architectures[0]

    def image(self, tester: Tester) -> str:
        return tester.image_for(self.architecture(tester))

    def installed(self, tester: Tester, *, image: str | None = None) -> bool:
        docker = self.docker()
        if not docker:
            return False
        architecture = self.architecture(tester)
        try:
            result = self._capture([docker, "image", "inspect", "--format", "{{.Os}}/{{.Architecture}}",
                                    image or tester.image_for(architecture)])
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0 and result.stdout.strip() == f"linux/{architecture}"

    def _image_tags(self, docker: str, tester: Tester) -> tuple[str, ...]:
        repository = f"42tui/{tester.id}:"
        result = self._capture([docker, "image", "ls", "--filter", f"reference={repository}*",
                                "--format", "{{.Repository}}:{{.Tag}}"])
        if result.returncode:
            raise TesterError("Docker tester resources could not be inspected.")
        return tuple(sorted({tag for tag in result.stdout.splitlines()
                             if tag.startswith(repository)
                             and re.fullmatch(r"[\w][\w.-]{0,127}", tag[len(repository):], flags=re.ASCII)}))

    def has_images(self, tester: Tester) -> bool:
        """Include older versions and other CPUs so they can also be removed."""
        docker = self.docker()
        if not docker:
            return False
        try:
            return bool(self._image_tags(docker, tester))
        except (TesterError, OSError, subprocess.TimeoutExpired):
            return False

    def remove(self, tester: Tester, terminal) -> None:
        """Remove this tester's tags and stopped 42TUI containers, without a global prune."""
        with self.connection():
            docker = self._require_ready()
            tags = self._image_tags(docker, tester)
            result = self._capture([docker, "container", "ls", "--all", "--filter", "name=42tui-",
                                    "--format", "{{json .}}"])
            if result.returncode:
                raise TesterError("Docker tester resources could not be inspected.")
            containers = []
            try:
                for line in result.stdout.splitlines():
                    container = json.loads(line)
                    if (re.fullmatch(r"42tui-(?:test|probe)-[0-9a-f]{32}", container["Names"])
                            and container["Image"].startswith(f"42tui/{tester.id}:")
                            and container["State"] in {"created", "exited", "dead"}
                            and re.fullmatch(r"[0-9a-f]{12,64}", container["ID"])):
                        containers.append(container["ID"])
            except (ValueError, KeyError, TypeError, AttributeError) as error:
                raise TesterError("Docker tester resources could not be inspected.") from error
            terminal.write("Removing tester images and stopped containers…")
            if containers:
                self._run(terminal, [docker, "container", "rm", *containers])
            if tags:
                self._run(terminal, [docker, "image", "rm", *tags])
            terminal.write("Docker may retain shared image layers and build cache.")

    def _require_ready(self) -> str:
        status = self.status()
        docker = self.docker()
        if status.state != "ready" or docker is None:
            raise TesterError(status.detail or "Docker is not ready. Check Docker access and retry.")
        return docker

    def log_path(self, action: str) -> Path:
        folder = self.root / "logs"
        folder.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
        return folder / f"{stamp}-{action}-{uuid.uuid4().hex[:8]}.log"

    def install(self, tester: Tester, terminal) -> None:
        with self.connection():
            self._install(tester, terminal)

    def _install(self, tester: Tester, terminal) -> None:
        docker = self._require_ready()
        if self.host.system not in tester.platforms:
            raise TesterError("This tester is unavailable on this platform.")
        if self.installed(tester):
            return
        architecture = self.architecture(tester)
        with tempfile.TemporaryDirectory(prefix="42tui-tester-") as directory:
            checkout = Path(directory)
            terminal.write("Fetching the pinned tester source…")
            terminal.run(["git", "init", str(checkout)])
            terminal.run(["git", "-C", str(checkout), "remote", "add", "origin", tester.repository])
            terminal.run(["git", "-C", str(checkout), "fetch", "--depth=1", "origin", tester.ref])
            terminal.run(["git", "-C", str(checkout), "checkout", "--detach", "FETCH_HEAD"])
            context = (checkout / tester.context).resolve()
            if not context.is_relative_to(checkout.resolve()) or not context.is_dir():
                raise TesterError("Docker build context must be inside the tester repository.")
            # Build under a temporary tag. Only publish the final tag after success,
            # so cancelling a build never makes it appear installed.
            staging = f"42tui/build:{uuid.uuid4().hex}"
            try:
                terminal.write("Building the tester image…")
                self._run(terminal, [docker, "build", "--platform", f"linux/{architecture}",
                                    "--tag", staging, str(context)])
                if not self.installed(tester, image=staging):
                    raise TesterError("The tester image could not be verified. Retry installation.")
                self._run(terminal, [docker, "image", "tag", staging, tester.image_for(architecture)])
            except subprocess.CalledProcessError as error:
                raise TesterError("Docker could not build or publish the tester image. "
                                  "Check build support, CPU emulation and the build log.") from error
            finally:
                self._cleanup([docker, "image", "rm", staging])

    def run(self, tester: Tester, project_path: str | None, terminal) -> None:
        if not project_path or not Path(project_path).expanduser().is_dir():
            raise TesterError("Configure an existing local project folder to run tests.")
        with self.connection():
            self._run_tester(tester, project_path, terminal)

    def _run_tester(self, tester: Tester, project_path: str, terminal) -> None:
        if not project_path or not Path(project_path).expanduser().is_dir():
            raise TesterError("Configure an existing local project folder to run tests.")
        path = Path(project_path).expanduser().resolve()
        docker = self._require_ready()
        if self.host.system not in tester.platforms:
            raise TesterError("This tester is unavailable on this platform.")
        if not self.installed(tester):
            raise TesterError("The tester image is missing. Install it and retry.")
        architecture = self.architecture(tester)
        user = self._user_arguments(docker)
        self._preflight(docker, tester, path, user, terminal)
        container = "42tui-test-" + uuid.uuid4().hex
        # --mount parses CSV; quoting the source also preserves commas and quotes.
        source = '"source=' + str(path).replace('"', '""') + '"'
        args = [docker, "run", "--rm", "--interactive", "--tty", "--name", container,
                "--platform", f"linux/{architecture}", "--mount", f"type=bind,{source},target=/project",
                "--workdir", "/project", *user, tester.image_for(architecture), *tester.command]
        try:
            terminal.write("Running the tester…")
            self._run(terminal, args)
        finally:
            self._cleanup([docker, "rm", "--force", container])

    def _user_arguments(self, docker):
        result = self._capture([docker, "info", "--format", "{{json .SecurityOptions}}"])
        if result.returncode:
            raise TesterError("Docker security options could not be read.")
        try:
            options = json.loads(result.stdout)
        except ValueError as error:
            raise TesterError("Docker security options could not be read.") from error
        # Root in a rootless container maps to the invoking host user. With a
        # regular Linux daemon, use that user's IDs to avoid root-owned output.
        if self.host.system == "linux" and not any("rootless" in option for option in options or []):
            return ["--user", f"{os.getuid()}:{os.getgid()}", "--env", "HOME=/tmp"]
        return []

    def _preflight(self, docker, tester, path, user, terminal):
        """Check the selected CPU and a writable, correctly shared local mount."""
        architecture = self.architecture(tester)
        machine = {"amd64": "x86_64", "arm64": "aarch64"}[architecture]
        container = "42tui-probe-" + uuid.uuid4().hex
        source = '"source=' + str(path).replace('"', '""') + '"'
        with tempfile.TemporaryDirectory(prefix=".42tui-probe-", dir=path) as directory:
            folder = Path(directory)
            value = uuid.uuid4().hex
            (folder / "input").write_text(value)
            target = "/project/" + folder.name
            script = (f'test "$(uname -m)" = {machine} || exit 80; '
                      f'test "$(cat {target}/input)" = {value} || exit 81; '
                      f'printf %s {value} > {target}/output || exit 81')
            try:
                terminal.write("Checking container execution and local folder access…")
                self._run(terminal, [docker, "run", "--rm", "--name", container,
                                    "--platform", f"linux/{architecture}", "--mount", f"type=bind,{source},target=/project",
                                    *user, "--entrypoint", "/bin/sh", tester.image_for(architecture), "-c", script])
                output = folder / "output"
                if output.read_text() != value:
                    raise TesterError("Docker did not mount the local project folder correctly.")
                if output.stat().st_uid != os.getuid():
                    raise TesterError("Docker produced a file owned by another user. "
                                      "Check Docker user mapping and local folder permissions.")
            except subprocess.CalledProcessError as error:
                if error.returncode in {80, 126, 127}:
                    raise TesterError("Docker cannot execute the tester image. Check CPU emulation. " + str(error)) from error
                if error.returncode == 81:
                    raise TesterError("Docker cannot read or write the local project folder. "
                                      "Check file sharing and folder permissions. " + str(error)) from error
                raise TesterError("Docker could not validate container execution and the local mount. "
                                  "Check emulation, file sharing and folder permissions. " + str(error)) from error
            except (OSError, subprocess.SubprocessError) as error:
                raise TesterError("Docker could not read the local folder probe. "
                                  "Check file sharing and folder permissions. " + str(error)) from error
            finally:
                self._cleanup([docker, "rm", "--force", container])

    def _cleanup(self, args: list[str]) -> None:
        try:
            self._capture(args)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def installation(self) -> DockerInstallation | None:
        host = self.host
        if host.architecture not in {"amd64", "arm64"}:
            return None
        if host.system == "darwin":
            brew = shutil.which("brew")
            if brew:
                return DockerInstallation(((brew, "install", "--cask", "docker-desktop"), ("open", "-a", "Docker")))
            image = str(self.root / f"Docker-{host.architecture}.dmg")
            url = f"https://desktop.docker.com/mac/main/{host.architecture}/Docker.dmg"
            return DockerInstallation((("curl", "--fail", "--location", "--output", image, url), ("open", image)))
        supported = {"ubuntu": {"jammy", "noble", "resolute", "stonking"}, "debian": {"bookworm", "trixie"}}
        if host.system != "linux" or host.codename not in supported.get(host.distribution, set()):
            return None
        url = f"https://download.docker.com/linux/{host.distribution}"
        source = (f"Types: deb\nURIs: {url}\nSuites: {host.codename}\nComponents: stable\n"
                  f"Architectures: {host.architecture}\nSigned-By: /etc/apt/keyrings/docker.asc\n")
        commands = (
            ("sudo", "apt-get", "update"),
            ("sudo", "apt-get", "install", "-y", "ca-certificates", "curl"),
            ("sudo", "install", "-m", "0755", "-d", "/etc/apt/keyrings"),
            ("sudo", "curl", "-fsSL", url + "/gpg", "-o", "/etc/apt/keyrings/docker.asc"),
            ("sudo", "chmod", "a+r", "/etc/apt/keyrings/docker.asc"),
            ("sudo", "install", "-m", "0644", str(self.root / "docker.sources"),
             "/etc/apt/sources.list.d/docker.sources"),
            ("sudo", "apt-get", "update"),
            ("sudo", "apt-get", "install", "-y", "docker-ce", "docker-ce-cli", "containerd.io",
             "docker-buildx-plugin", "docker-compose-plugin"),
            ("sudo", "systemctl", "start", "docker"),
        )
        return DockerInstallation(commands, source)

    def install_docker(self, plan: DockerInstallation, terminal) -> None:
        """Called only after the user has approved the displayed command plan."""
        if self.docker():
            terminal.write("Docker is already installed. Check Docker access again.")
            return
        self.root.mkdir(parents=True, exist_ok=True)
        if plan.source:
            (self.root / "docker.sources").write_text(plan.source, encoding="utf-8")
        for command in plan.commands:
            terminal.run(list(command))
