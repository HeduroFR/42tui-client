"""Catalog validation and Docker operations without an engine or administrator access."""

import json
import os
import shlex
import subprocess
import sys
import unittest
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from ft_tui.services.tester_catalog import load_catalog, user_catalog_path
from ft_tui.services.tester_docker import Host, TesterDocker, TesterError


class TesterCatalogTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "testers.toml"
        self.catalog = load_catalog(self.path)
        self.tester = self.catalog.testers[0]

    def write(self, text):
        self.path.write_text(text, encoding="utf-8")
        return load_catalog(self.path)

    def entry(self, identifier="custom"):
        return f'''[[testers]]
id = "{identifier}"
name = "Custom tester"
projects = ["42cursus-libft"]
platforms = ["linux"]
repository = "https://example.com/tester.git"
ref = "{'a' * 40}"
context = "."
command = ["runner", "--argument with spaces", "$(touch nope)"]
'''

    def test_explicit_slugs_platforms_and_no_born2beroot(self):
        for slug in ("libft", "ft_printf", "get_next_line"):
            for platform in ("linux", "darwin"):
                self.assertEqual(self.catalog.for_project(slug, platform), (self.tester,))
                self.assertEqual(self.catalog.for_project("42cursus-" + slug, platform), (self.tester,))
        self.assertFalse(self.catalog.for_project("born2beroot", "linux"))
        self.assertFalse(self.catalog.for_project("libft", "win32"))

    def test_add_replace_and_disable(self):
        catalog = self.write(self.entry())
        self.assertEqual(len(catalog.for_project("libft", "linux")), 2)
        self.assertEqual(len(catalog.for_project("libft", "darwin")), 1)
        catalog = self.write(self.entry("francinette"))
        self.assertEqual(len(catalog.testers), 1)
        self.assertEqual(catalog.testers[0].name, "Custom tester")
        self.assertFalse(catalog.for_project("ft_printf", "linux"))
        self.assertFalse(self.write('[[testers]]\nid="francinette"\nenabled=false').testers)

    def test_invalid_override_is_atomic(self):
        invalid = ["bad = [", "testers = 1", self.entry() + self.entry(),
                   self.entry().replace('context = "."', 'context = "../escape"'),
                   self.entry().replace('platforms = ["linux"]', 'platforms = ["windows"]'),
                   self.entry().replace('command = [', 'unknown = ['),
                   self.entry().replace('"runner", ', '1, '),
                   self.entry().replace('"https://example.com/tester.git"', '"file:///tmp/tester"'),
                   self.entry().replace('a' * 40, 'master'),
                   '[[testers]]\nid="francinette"\nenabled="false"']
        for content in invalid:
            with self.subTest(content=content):
                catalog = self.write('[[testers]]\nid="francinette"\nenabled=false\n' + content)
                self.assertTrue(catalog.error)
                self.assertEqual(catalog.testers, self.catalog.testers)
        self.assertTrue(self.write("").error)
        self.path.write_bytes(b"\xff")
        self.assertEqual(load_catalog(self.path).testers, self.catalog.testers)

    def test_xdg_and_fallback(self):
        with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(self.path.parent)}):
            self.assertEqual(user_catalog_path(), self.path.parent / "42tui/testers.toml")
        with patch.dict("os.environ", {"XDG_CONFIG_HOME": ""}):
            self.assertEqual(user_catalog_path(), Path.home() / ".config/42tui/testers.toml")

    def test_image_identity_tracks_source_and_is_shared_across_projects(self):
        self.assertEqual(self.catalog.for_project("libft")[0].image, self.catalog.for_project("ft_printf")[0].image)
        for changed in (replace(self.tester, ref="a" * 40), replace(self.tester, context="docker"),
                        replace(self.tester, repository="https://example.com/other.git")):
            self.assertNotEqual(self.tester.image, changed.image)

    def test_architectures_are_opt_in_and_use_separate_image_tags(self):
        self.assertEqual(self.tester.architectures, ("amd64", "arm64"))
        self.assertEqual(self.tester.image_for("amd64"), self.tester.image)
        self.assertNotEqual(self.tester.image_for("arm64"), self.tester.image)
        custom = self.write(self.entry()).testers[-1]
        self.assertEqual(custom.architectures, ("amd64",))
        for value in ('[]', '["riscv64"]', '["arm64", "arm64"]', '"arm64"', '[1]'):
            with self.subTest(value=value):
                self.assertTrue(self.write(self.entry() + f'architectures = {value}\n').error)


class FrancinetteLauncherTests(unittest.TestCase):
    def test_private_compilers_preserve_arguments_and_cleanup_on_success_or_failure(self):
        with TemporaryDirectory(prefix="francinette 'quoted' ") as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            binaries = root / "bin"
            binaries.mkdir()
            compiler_script = (
                "#!/bin/sh\nexec " + shlex.quote(sys.executable)
                + " -c 'import json, sys; print(json.dumps(sys.argv[1:]))' \"$@\"\n"
            )
            for compiler in ("clang", "clang++"):
                executable = binaries / compiler
                executable.write_text(compiler_script)
                executable.chmod(0o755)
            (source / "helper.py").write_text("VALUE = 42\n")
            main = '''import json, os, subprocess, sys
from pathlib import Path
from helper import VALUE
arguments = ['-g3', 'source with spaces.c', '$(touch nope)', '-o', 'output file']
print(json.dumps({
    'root': str(Path(__file__).parent), 'cwd': os.getcwd(), 'value': VALUE,
    'calls': [json.loads(subprocess.check_output([name, *arguments], text=True))
              for name in ('clang', 'clang++')],
}))
sys.exit(int(os.environ['LAUNCHER_EXIT']))
'''
            (source / "main.py").write_text(main)
            tester = load_catalog(root / "absent.toml").testers[0]
            script = tester.command[2].replace('"/francinette"', repr(str(source)))
            for exit_code in (0, 7):
                with self.subTest(exit_code=exit_code):
                    result = subprocess.run(
                        [sys.executable, "-c", script], cwd=root,
                        env={**os.environ, "PATH": str(binaries), "LAUNCHER_EXIT": str(exit_code)},
                        capture_output=True, text=True, timeout=15, check=False,
                    )
                    self.assertEqual(result.returncode, exit_code, result.stderr)
                    output = json.loads(result.stdout)
                    self.assertEqual(output["calls"], [[
                        "-fdebug-default-version=4", "-g3", "source with spaces.c",
                        "$(touch nope)", "-o", "output file",
                    ]] * 2)
                    self.assertEqual(Path(output["cwd"]).resolve(), root.resolve())
                    self.assertEqual(output["value"], 42)
                    self.assertFalse(Path(output["root"]).parent.exists())
                    self.assertFalse((root / "nope").exists())
                    self.assertEqual((source / "main.py").read_text(), main)
                    for compiler in ("clang", "clang++"):
                        self.assertEqual((binaries / compiler).read_text(), compiler_script)


class TesterDockerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="testers space ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.service = TesterDocker(self.root, Host("linux", "amd64", "ubuntu", "noble"))
        self.tester = load_catalog(self.root / "absent").testers[0]
        connection = patch.object(self.service, "connection", side_effect=nullcontext)
        connection.start()
        self.addCleanup(connection.stop)
        architecture = patch.object(self.service, "architecture", return_value="amd64")
        architecture.start()
        self.addCleanup(architecture.stop)

    def test_missing_stopped_denied_ready_and_timeout(self):
        with patch.object(self.service, "docker", return_value=None):
            self.assertEqual(self.service.status().state, "missing")
        with patch.object(self.service, "docker", return_value="docker"), patch.object(self.service, "_capture") as capture:
            for error, state in (("Cannot connect to daemon", "stopped"), ("permission denied", "denied")):
                capture.return_value = subprocess.CompletedProcess([], 1, "", error)
                self.assertEqual(self.service.status().state, state)
            capture.return_value = subprocess.CompletedProcess([], 0, '{"OSType":"linux"}', "")
            self.assertEqual(self.service.status().state, "ready")
            capture.side_effect = subprocess.TimeoutExpired("docker", 15)
            self.assertEqual(self.service.status().state, "stopped")

    def test_real_image_presence_and_architecture_required(self):
        with patch.object(self.service, "docker", return_value="docker"), patch.object(self.service, "_capture") as capture:
            for code, output, expected in ((0, "linux/amd64\n", True), (0, "linux/arm64\n", False), (1, "", False)):
                capture.return_value = subprocess.CompletedProcess([], code, output, "")
                self.assertEqual(self.service.installed(self.tester), expected)

    def test_install_needs_no_project_and_commits_only_successful_builds(self):
        terminal = Mock()
        with patch.object(self.service, "_require_ready", return_value="docker"), \
                patch.object(self.service, "installed", side_effect=[False, True]), \
                patch.object(self.service, "_cleanup"):
            self.service.install(self.tester, terminal)
        calls = [call.args[0] for call in terminal.run.call_args_list]
        self.assertIn(self.tester.ref, calls[2])
        self.assertEqual(calls[4][:4], ["docker", "build", "--platform", "linux/amd64"])
        self.assertEqual(calls[5][:3], ["docker", "image", "tag"])
        self.assertFalse(any("install.sh" in " ".join(args) for args in calls))

    def test_network_build_failure_and_interrupt_never_publish_install(self):
        for failure_at in ("fetch", "build", "tag"):
            for failure in (OSError("network unavailable"), subprocess.CalledProcessError(1, "docker"), KeyboardInterrupt()):
                with self.subTest(step=failure_at, failure=type(failure)):
                    terminal = Mock()
                    def run(args, failure_at=failure_at, failure=failure, **kwargs):
                        if failure_at in args:
                            raise failure
                    terminal.run.side_effect = run
                    with patch.object(self.service, "_require_ready", return_value="docker"), \
                            patch.object(self.service, "installed", side_effect=[False, True]), \
                            patch.object(self.service, "_cleanup") as cleanup:
                        expected = TesterError if isinstance(failure, subprocess.CalledProcessError) and failure_at != "fetch" else type(failure)
                        with self.assertRaises(expected):
                            self.service.install(self.tester, terminal)
                        calls = [call.args[0] for call in terminal.run.call_args_list]
                        if failure_at in {"fetch", "build"}:
                            self.assertFalse(any("tag" in args for args in calls))
                        if failure_at != "fetch":
                            cleanup.assert_called_once()
                            self.assertNotEqual(cleanup.call_args.args[0][-1], self.tester.image)

    def test_run_keeps_spaces_quotes_and_shell_arguments_and_cleans_interruption(self):
        project = self.root / 'my project, "quoted" $(touch nope)'
        project.mkdir()
        terminal = Mock()
        tester = replace(self.tester, command=("runner", "--value with spaces", "$(touch nope)"))
        with patch.object(self.service, "_require_ready", return_value="docker"), \
                patch.object(self.service, "installed", return_value=True), \
                patch.object(self.service, "_user_arguments", return_value=[]), \
                patch.object(self.service, "_preflight"), \
                patch.object(self.service, "_cleanup") as cleanup:
            terminal.run.side_effect = KeyboardInterrupt
            with self.assertRaises(KeyboardInterrupt):
                self.service.run(tester, str(project), terminal)
            args = terminal.run.call_args.args[0]
            self.assertEqual(args[-3:], list(tester.command))
            self.assertIn('""quoted""', args[args.index("--mount") + 1])
            self.assertEqual(args[args.index("--workdir") + 1], "/project")
            self.assertEqual(args[args.index("--platform") + 1], "linux/amd64")
            self.assertIn("--rm", args)
            cleanup.assert_called_once()
            self.assertEqual(cleanup.call_args.args[0][:3], ["docker", "rm", "--force"])
        self.assertFalse((self.root / "nope").exists())

    def test_missing_folder_fails_before_docker(self):
        with patch.object(self.service, "_require_ready") as ready:
            for path in (None, "", str(self.root / "missing")):
                with self.assertRaises(TesterError):
                    self.service.run(self.tester, path, Mock())
            ready.assert_not_called()

    def test_global_operation_lock_is_released_after_interruption(self):
        with self.assertRaises(KeyboardInterrupt), self.service.operation():
            with self.assertRaises(TesterError), self.service.operation():
                pass
            raise KeyboardInterrupt
        with self.service.operation():
            self.assertTrue(self.service.busy)
        self.assertFalse(self.service.busy)

    def test_docker_installation_plans_are_platform_specific_and_not_executed(self):
        for host, supported in ((Host("linux", "amd64", "ubuntu", "noble"), True),
                                (Host("linux", "arm64", "debian", "trixie"), True),
                                (Host("linux", "amd64", "ubuntu", "old"), False),
                                (Host("linux", "amd64", "arch", ""), False),
                                (Host("win32", "amd64"), False)):
            service = TesterDocker(self.root, host)
            plan = service.installation()
            self.assertEqual(plan is not None, supported)
            if plan:
                self.assertIn(f"https://download.docker.com/linux/{host.distribution}", plan.source)
                self.assertTrue(all(command[0] == "sudo" for command in plan.commands))
        for architecture in ("amd64", "arm64"):
            service = TesterDocker(self.root, Host("darwin", architecture))
            with patch("ft_tui.services.tester_docker.shutil.which", return_value=None):
                plan = service.installation()
                self.assertIn(f"/mac/main/{architecture}/Docker.dmg", plan.commands[0][-1])
                self.assertEqual(plan.commands[-1][0], "open")
            with patch("ft_tui.services.tester_docker.shutil.which", return_value="/opt/homebrew/bin/brew"):
                self.assertEqual(service.installation().commands[0][1:], ("install", "--cask", "docker-desktop"))

    def test_mac_cli_discovery_without_path_changes(self):
        service = TesterDocker(self.root, Host("darwin", "arm64"))
        with patch("ft_tui.services.tester_docker.shutil.which", return_value=None), \
                patch("pathlib.Path.is_file", return_value=True):
            self.assertEqual(service.docker(), str(Path.home() / ".docker/bin/docker"))


class TesterRemovalTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.tester = load_catalog(self.root / "absent.toml").testers[0]
        self.service = TesterDocker(self.root, Host("linux", "amd64"))
        self.tags = [self.tester.image, self.tester.image_for("arm64"), "42tui/francinette:older"]
        self.containers = []
        for name, value in (("docker", "docker"), ("_require_ready", "docker")):
            mocked = patch.object(self.service, name, return_value=value)
            mocked.start()
            self.addCleanup(mocked.stop)
        capture = patch.object(self.service, "_capture", side_effect=self.capture)
        self.capture_mock = capture.start()
        self.addCleanup(capture.stop)
        environment = patch.dict(os.environ, {"DOCKER_CONTEXT": "selected"})
        environment.start()
        self.addCleanup(environment.stop)

    def capture(self, args):
        output = "\n".join(self.tags) if args[1:3] == ["image", "ls"] else "\n".join(
            json.dumps(container) for container in self.containers
        )
        return subprocess.CompletedProcess(args, 0, output, "")

    def test_removal_is_scoped_to_tester_tags_and_stopped_application_containers(self):
        self.tags += ["42tui/other:latest", "42tui/francinette-extra:latest", "42tui/francinette:<none>"]
        for number, (name, image, state) in enumerate((
            ("42tui-test-" + "a" * 32, self.tester.image, "exited"),
            ("42tui-probe-" + "b" * 32, self.tester.image_for("arm64"), "created"),
            ("42tui-test-" + "c" * 32, self.tester.image, "running"),
            ("personal-container", self.tester.image, "exited"),
            ("42tui-test-" + "d" * 32, "42tui/other:latest", "exited"),
        )):
            self.containers.append({"ID": f"{number + 1:012x}", "Names": name, "Image": image, "State": state})
        terminal = Mock()
        self.service.remove(self.tester, terminal)
        commands = [call.args[0] for call in terminal.run.call_args_list]
        self.assertEqual(commands[0], ["docker", "--context", "selected", "container", "rm",
                                       "000000000001", "000000000002"])
        self.assertEqual(commands[1][:5], ["docker", "--context", "selected", "image", "rm"])
        self.assertEqual(set(commands[1][5:]), set(self.tags[:3]))
        self.assertFalse(any("prune" in command or "--force" in command for command in commands))
        self.assertIsNone(self.service._connection.get())

    def test_inspection_errors_never_start_removal(self):
        for failed_call in (1, 2):
            terminal = Mock()
            calls = 0
            def capture(args, failed_call=failed_call):
                nonlocal calls
                calls += 1
                return subprocess.CompletedProcess(args, 1, "", "denied") if calls == failed_call else self.capture(args)
            with self.subTest(failed_call=failed_call), patch.object(self.service, "_capture", side_effect=capture):
                with self.assertRaises(TesterError):
                    self.service.remove(self.tester, terminal)
                terminal.run.assert_not_called()
        with patch.object(self.service, "_capture", side_effect=[self.capture(["docker", "image", "ls"]),
                          subprocess.CompletedProcess([], 0, "not json", "")]):
            with self.assertRaises(TesterError):
                self.service.remove(self.tester, terminal)
            terminal.run.assert_not_called()

    def test_absent_images_are_a_noop_and_in_use_errors_are_not_forced(self):
        terminal = Mock()
        self.tags = []
        self.assertFalse(self.service.has_images(self.tester))
        self.service.remove(self.tester, terminal)
        terminal.run.assert_not_called()
        self.tags = [self.tester.image_for("arm64")]
        self.assertTrue(self.service.has_images(self.tester))
        terminal.run.side_effect = subprocess.CalledProcessError(1, "docker", stderr="image in use")
        with self.assertRaises(subprocess.CalledProcessError):
            self.service.remove(self.tester, terminal)
        self.assertNotIn("--force", terminal.run.call_args.args[0])
        self.assertIsNone(self.service._connection.get())


class TesterArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.tester = load_catalog(self.root / "absent.toml").testers[0]
        self.service = TesterDocker(self.root, Host("darwin", "amd64"))
        self.engine = "aarch64"
        self.image_platform = "linux/arm64"
        docker = patch.object(self.service, "docker", return_value="docker")
        docker.start()
        self.addCleanup(docker.stop)
        capture = patch.object(self.service, "_capture", side_effect=self.capture)
        self.capture_mock = capture.start()
        self.addCleanup(capture.stop)
        environment = patch.dict(os.environ, {"DOCKER_CONTEXT": "selected"})
        environment.start()
        self.addCleanup(environment.stop)

    def capture(self, args):
        if "inspect" in args:
            output = self.image_platform
        elif "{{json .SecurityOptions}}" in args:
            output = "[]"
        else:
            output = json.dumps({"OSType": "linux", "Architecture": self.engine})
        return subprocess.CompletedProcess(args, 0, output, "")

    def test_selection_uses_the_engine_cpu_and_preserves_legacy_amd64_images(self):
        for engine, architecture in (("aarch64", "arm64"), ("arm64", "arm64"),
                                     ("x86_64", "amd64"), ("amd64", "amd64"), ("unknown", "amd64")):
            with self.subTest(engine=engine):
                self.engine = engine
                self.assertEqual(self.service.architecture(self.tester), architecture)
                self.assertEqual(self.service.image(self.tester), self.tester.image_for(architecture))
        self.engine = "aarch64"
        custom = replace(self.tester, architectures=("amd64",))
        self.assertEqual(self.service.architecture(custom), "amd64")
        self.assertEqual(self.service.image(custom), custom.image)

    def test_installation_rejects_an_image_for_the_other_cpu(self):
        with self.service.connection():
            self.assertTrue(self.service.installed(self.tester))
            self.assertEqual(self.capture_mock.call_args.args[0][-1], self.tester.image_for("arm64"))
            self.image_platform = "linux/amd64"
            self.assertFalse(self.service.installed(self.tester))

    def test_engine_cpu_is_frozen_per_connection_and_rechecked_next_time(self):
        with self.service.connection():
            self.service._require_ready()
            self.engine = "x86_64"
            with self.service.connection():
                self.assertEqual(self.service.architecture(self.tester), "arm64")
                self.assertTrue(self.service.installed(self.tester))
            info_calls = [call for call in self.capture_mock.call_args_list if "{{json .}}" in call.args[0]]
            self.assertEqual(len(info_calls), 1)
        self.assertIsNone(self.service._engine_architecture.get())
        with self.service.connection():
            self.assertEqual(self.service.architecture(self.tester), "amd64")

    def test_native_install_builds_and_publishes_only_the_native_tag(self):
        terminal = Mock()
        with patch.object(self.service, "installed", side_effect=[False, True]), \
                patch.object(self.service, "_cleanup"):
            self.service.install(self.tester, terminal)
        commands = [call.args[0] for call in terminal.run.call_args_list]
        build = next(command for command in commands if "build" in command)
        self.assertEqual(build[build.index("--platform") + 1], "linux/arm64")
        self.assertEqual(commands[-1][-1], self.tester.image_for("arm64"))
        self.assertNotEqual(commands[-1][-1], self.tester.image)

    def test_native_run_and_mount_probe_use_the_same_cpu_image_and_context(self):
        terminal = Mock()
        def simulate(args, **kwargs):
            if "--entrypoint" in args:
                folder = next(self.root.glob(".42tui-probe-*"))
                (folder / "output").write_text((folder / "input").read_text())
        terminal.run.side_effect = simulate
        with patch.object(self.service, "_cleanup") as cleanup:
            self.service.run(self.tester, str(self.root), terminal)
        commands = [call.args[0] for call in terminal.run.call_args_list]
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertEqual(command[:3], ["docker", "--context", "selected"])
            self.assertEqual(command[command.index("--platform") + 1], "linux/arm64")
            self.assertIn(self.tester.image_for("arm64"), command)
        self.assertIn('"$(uname -m)" = aarch64', commands[0][-1])
        self.assertEqual(cleanup.call_count, 2)
        self.assertFalse(list(self.root.iterdir()))


class DockerConnectionTests(unittest.TestCase):
    def setUp(self):
        self.service = TesterDocker(host=Host('linux', 'arm64'))
        self.docker = patch.object(self.service, 'docker', return_value='docker')
        self.docker.start()
        self.addCleanup(self.docker.stop)
        architecture = patch.object(self.service, "architecture", return_value="amd64")
        architecture.start()
        self.addCleanup(architecture.stop)

    def test_current_context_is_kept_through_commands_and_cleanup(self):
        terminal = Mock()
        def capture(args, **kwargs):
            if args[1:3] == ['context', 'show']:
                return subprocess.CompletedProcess(args, 0, 'selected\n', '')
            return subprocess.CompletedProcess(args, 0, '', '')
        with patch.dict(os.environ, {}, clear=True), patch('subprocess.run', side_effect=capture) as run:
            with self.service.connection():
                os.environ['DOCKER_HOST'] = 'tcp://changed:2375'
                self.service._run(terminal, ['docker', 'run', 'image'])
                with self.service.connection():
                    self.service._cleanup(['docker', 'rm', '--force', 'container'])
            self.assertEqual(terminal.run.call_args.args[0], ['docker', '--context', 'selected', 'run', 'image'])
            self.assertNotIn('DOCKER_HOST', terminal.run.call_args.kwargs['env'])
            self.assertEqual(run.call_args.args[0][:3], ['docker', '--context', 'selected'])
            self.assertNotIn('DOCKER_HOST', run.call_args.kwargs['env'])
            self.assertIsNone(self.service._connection.get())

    def test_host_tls_config_and_context_precedence_are_preserved(self):
        for extra, prefix in (({}, []), ({'DOCKER_CONTEXT': 'rootless'}, ['--context', 'rootless'])):
            with self.subTest(extra=extra), patch.dict(os.environ, {
                'DOCKER_HOST': 'tcp://engine:2376', 'DOCKER_TLS_VERIFY': '1',
                'DOCKER_CERT_PATH': '/certs', 'DOCKER_CONFIG': '/config', **extra,
            }, clear=True), patch('subprocess.run') as run:
                terminal = Mock()
                with self.service.connection():
                    self.service._run(terminal, ['docker', 'build', '.'])
                    self.service._cleanup(['docker', 'image', 'rm', 'staging'])
                self.assertEqual(terminal.run.call_args.args[0], ['docker', *prefix, 'build', '.'])
                self.assertEqual(run.call_count, 1)
                environment = terminal.run.call_args.kwargs['env']
                self.assertEqual(environment['DOCKER_HOST'], 'tcp://engine:2376')
                self.assertEqual(environment['DOCKER_TLS_VERIFY'], '1')
                self.assertEqual(environment['DOCKER_CERT_PATH'], '/certs')
                self.assertEqual(environment['DOCKER_CONFIG'], '/config')

    def test_windows_engine_and_32_bit_hosts_are_rejected(self):
        with patch.object(self.service, '_capture', return_value=subprocess.CompletedProcess(
            [], 0, '{"OSType":"windows"}', ''
        )):
            self.assertEqual(self.service.status().state, 'incompatible')
        self.service.host = Host('linux', 'i686')
        self.assertEqual(self.service.status().state, 'unsupported')

    def test_rootful_linux_uses_host_uid_and_rootless_retains_container_root(self):
        for system, options, user in (
            ('linux', ['name=seccomp'], True), ('linux', ['name=rootless'], False),
            ('darwin', ['name=seccomp'], False),
        ):
            self.service.host = Host(system, 'arm64')
            with patch.object(self.service, '_capture', return_value=subprocess.CompletedProcess(
                [], 0, json.dumps(options), ''
            )):
                arguments = self.service._user_arguments('docker')
                self.assertEqual(bool(arguments), user)
                if user:
                    self.assertIn(f'{os.getuid()}:{os.getgid()}', arguments)

    def test_mount_probe_verifies_roundtrip_and_cleans_failed_emulation(self):
        with TemporaryDirectory(prefix='probe, "quoted" ') as directory:
            path = Path(directory)
            tester = load_catalog(path / 'absent').testers[0]
            terminal = Mock()
            def simulate(args, **kwargs):
                folder = next(path.glob('.42tui-probe-*'))
                (folder / 'output').write_text((folder / 'input').read_text())
            terminal.run.side_effect = simulate
            with patch.object(self.service, '_cleanup') as cleanup:
                self.service._preflight('docker', tester, path, [], terminal)
                self.assertIn('""quoted""', terminal.run.call_args.args[0][
                    terminal.run.call_args.args[0].index('--mount') + 1])
                cleanup.assert_called_once()
            self.assertFalse(list(path.iterdir()))
            with (
                patch.object(self.service, '_cleanup'),
                patch('os.getuid', return_value=os.getuid() + 1),
                self.assertRaisesRegex(TesterError, 'owned by another user'),
            ):
                self.service._preflight('docker', tester, path, [], terminal)
            self.assertFalse(list(path.iterdir()))
            terminal.run.side_effect = subprocess.CalledProcessError(126, 'docker', stderr='exec format error')
            with patch.object(self.service, '_cleanup') as cleanup, self.assertRaisesRegex(TesterError, 'emulation'):
                self.service._preflight('docker', tester, path, [], terminal)
            cleanup.assert_called_once()
            self.assertFalse(list(path.iterdir()))

    def test_missing_mount_is_reported_separately_from_emulation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory)
            tester = load_catalog(path / 'absent').testers[0]
            terminal = Mock()
            terminal.run.side_effect = subprocess.CalledProcessError(81, 'docker')
            with patch.object(self.service, '_cleanup'), self.assertRaisesRegex(TesterError, 'file sharing'):
                self.service._preflight('docker', tester, path, [], terminal)
            self.assertFalse(list(path.iterdir()))

    def test_docker_that_appears_after_installation_prompt_is_reused(self):
        terminal = Mock()
        plan = self.service.installation()
        self.service.install_docker(plan, terminal)
        terminal.run.assert_not_called()
