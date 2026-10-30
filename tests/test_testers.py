"""Catalog validation and Docker operations without an engine or administrator access."""

import csv
import json
import os
import shutil
from importlib.resources import files
import subprocess
import sys
import unittest
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from ft_tui.features.projects.adapters.tester_catalog import Tester, load_catalog, user_catalog_path
from ft_tui.features.projects.adapters.tester_docker import Host, TesterDocker, TesterError


def docker_fixture():
    return Tester("docker-fixture", "Docker fixture", ("libft", "ft_printf"), ("linux", "darwin"),
                  "https://example.com/tester.git", "b" * 40, ".", ("runner",), ("amd64", "arm64"))


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
        for slug in ("libft", "ft_printf", "push_swap"):
            for platform in ("linux", "darwin"):
                entries = self.catalog.for_project(slug, platform)
                self.assertEqual(len(entries), 1)
                self.assertEqual(self.catalog.for_project("42cursus-" + slug, platform), entries)
        gnl = self.catalog.for_project("get_next_line", "linux")
        self.assertEqual([t.id for t in gnl], ["tripouille-gnl"])
        self.assertEqual(gnl[0].architectures, ("amd64", "arm64"))
        self.assertEqual(gnl[0].result_file, ".42tui-gnl-result.json")
        self.assertFalse(gnl[0].interactive_input)
        self.assertNotIn("francinette", {t.id for t in self.catalog.testers})
        self.assertFalse(self.catalog.for_project("born2beroot", "linux"))
        self.assertFalse(self.catalog.for_project("libft", "win32"))

    def test_add_replace_and_disable(self):
        catalog = self.write(self.entry())
        self.assertEqual(len(catalog.for_project("libft", "linux")), 2)
        self.assertEqual(len(catalog.for_project("libft", "darwin")), 1)
        catalog = self.write(self.entry("supra-libft"))
        self.assertEqual(len(catalog.testers), len(self.catalog.testers))
        self.assertEqual(catalog.testers[0].name, "Custom tester")
        self.assertEqual([t.id for t in catalog.for_project("ft_printf", "linux")], ["supra-printf"])
        disabled = self.write('[[testers]]\nid="supra-libft"\nenabled=false')
        self.assertFalse(disabled.for_project("libft", "linux"))

    def test_invalid_override_is_atomic(self):
        invalid = ["bad = [", "testers = 1", self.entry() + self.entry(),
                   self.entry().replace('context = "."', 'context = "../escape"'),
                   self.entry().replace('platforms = ["linux"]', 'platforms = ["windows"]'),
                   self.entry().replace('command = [', 'unknown = ['),
                   self.entry().replace('"runner", ', '1, '),
                   self.entry().replace('"https://example.com/tester.git"', '"file:///tmp/tester"'),
                   self.entry().replace('a' * 40, 'master'),
                   '[[testers]]\nid="docker-fixture"\nenabled="false"']
        for content in invalid:
            with self.subTest(content=content):
                catalog = self.write('[[testers]]\nid="docker-fixture"\nenabled=false\n' + content)
                self.assertTrue(catalog.error)
                self.assertEqual(catalog.testers, self.catalog.testers)
        self.assertTrue(self.write("").error)
        self.path.write_bytes(b"\xff")
        self.assertEqual(load_catalog(self.path).testers, self.catalog.testers)

    def test_optional_result_file_is_a_project_relative_json_report(self):
        catalog = self.write(self.entry() + 'result_file = "reports/result.json"\n')
        self.assertFalse(catalog.error)
        self.assertEqual(catalog.testers[-1].result_file, "reports/result.json")
        self.assertEqual(self.tester.result_file, ".42tui-libft-result.json")
        for value in ('"/outside.json"', '"../outside.json"', '"."', '""', 'false', '".git/result.json"'):
            with self.subTest(value=value):
                catalog = self.write(self.entry() + f'result_file = {value}\n')
                self.assertTrue(catalog.error)
                self.assertEqual(catalog.testers, self.catalog.testers)

    def test_native_commands_and_invalid_runtime_fields(self):
        entry = self.entry() + 'runtime = "native"\nprepare = [["{python}", "-V"]]\n'
        catalog = self.write(entry)
        self.assertFalse(catalog.error)
        self.assertEqual(catalog.testers[-1].runtime, 'native')
        self.assertEqual(catalog.testers[-1].prepare, (('{python}', '-V'),))
        for extra in ('runtime="shell"', 'prepare=[[]]', 'runtime="native"\nprepare=["make"]', 'prepare=[["make"]]'):
            self.assertTrue(self.write(self.entry() + extra).error)
        push_swap = self.catalog.for_project('push_swap', 'darwin')[0]
        self.assertEqual(push_swap.runtime, 'native')
        self.assertEqual(push_swap.result_file, '.42tui-push-swap-result.json')
        self.assertEqual(push_swap.command[-2:], ('--report', '{project}/.42tui-push-swap-result.json'))

    def test_bundled_recipe_is_explicit_and_image_identity_tracks_its_bytes(self):
        catalog = self.write(self.entry() + 'recipe="supra"\n')
        self.assertFalse(catalog.error)
        tester = catalog.testers[-1]
        self.assertEqual(tester.recipe, "supra")
        self.assertNotEqual(tester.image, replace(tester, recipe=None).image)
        with patch("ft_tui.features.projects.adapters.tester_catalog.files") as resources:
            resources.return_value.joinpath.return_value.read_bytes.return_value = b"changed recipe"
            changed = tester.image
        self.assertNotEqual(tester.image, changed)
        for value in ('"../outside"', '"/tmp/file"', '"unknown"', 'false', '"supra"\nruntime="native"'):
            with self.subTest(value=value):
                self.assertTrue(self.write(self.entry() + f'recipe={value}\n').error)
        self.assertFalse(self.write(self.entry() + 'recipe="supra"\narchitectures=["arm64"]\n').error)
        self.assertTrue(self.write(self.entry().replace('context = "."', 'context = "nested"') + 'recipe="supra"\n').error)
        for identifier in ("supra-printf", "supra-libft"):
            bundled = next(t for t in self.catalog.testers if t.id == identifier)
            self.assertEqual(bundled.architectures, ("amd64", "arm64") if identifier == "supra-printf" else ("amd64",))
            self.assertEqual(bundled.runtime, "docker")
            if identifier == "supra-printf":
                self.assertEqual(bundled.repository, "https://github.com/HeduroFR/42tui-tester-printf.git")
                self.assertEqual(bundled.result_file, ".42tui-printf-result.json")
                self.assertIn("--report", bundled.command)
            else:
                self.assertEqual(bundled.repository, "https://github.com/HeduroFR/42tui-tester-libft.git")
                self.assertEqual(bundled.result_file, ".42tui-libft-result.json")
                self.assertIn("--report", bundled.command)

    def test_germinette_projects_share_image_and_select_explicit_checks(self):
        projects = [(f"python-module-{number:02}", f"python_module_{number:02}")
                    for number in range(11)]
        projects += [("python-module-05-bis", "python_module_05_bis"),
                     ("python-module-06-bis", "python_module_06_bis"),
                     ("a-maze-ing", "a_maze_ing")]
        testers = []
        for slug, module in projects:
            with self.subTest(slug=slug):
                entries = self.catalog.for_project(slug, "linux")
                self.assertEqual(len(entries), 1)
                tester = entries[0]
                testers.append(tester)
                self.assertEqual(tester.command[0], module)
                self.assertEqual(tester.recipe, "germinette")
                self.assertEqual(tester.architectures, ("amd64", "arm64"))
                self.assertEqual(tester.result_file, ".42tui-germinette-result.json")
                self.assertIn("--report", tester.command)
                self.assertFalse(tester.interactive_input)
        self.assertEqual(len({tester.image for tester in testers}), 1)
        self.assertEqual(len({tester.image_for("arm64") for tester in testers}), 1)
        self.assertEqual({tester.image_repository for tester in testers}, {"germinette"})
        self.assertFalse(self.catalog.for_project("python-module-05-bis-extra", "linux"))

    def test_interactive_input_catalog_option(self):
        printf = next(t for t in self.catalog.testers if t.id == "supra-printf")
        self.assertFalse(printf.interactive_input)
        self.assertTrue(self.write(self.entry()).testers[-1].interactive_input)
        self.assertFalse(self.write(self.entry() + 'interactive_input=false\n').testers[-1].interactive_input)
        self.assertTrue(self.write(self.entry() + 'interactive_input="false"\n').error)

    def test_xdg_and_fallback(self):
        with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(self.path.parent)}):
            self.assertEqual(user_catalog_path(), self.path.parent / "42tui/testers.toml")
        with patch.dict("os.environ", {"XDG_CONFIG_HOME": ""}):
            self.assertEqual(user_catalog_path(), Path.home() / ".config/42tui/testers.toml")

    def test_image_identity_tracks_source_and_distinguishes_project_testers(self):
        self.assertNotEqual(self.catalog.for_project("libft")[0].image, self.catalog.for_project("ft_printf")[0].image)
        for changed in (replace(self.tester, ref="a" * 40), replace(self.tester, context="docker"),
                        replace(self.tester, repository="https://example.com/other.git")):
            self.assertNotEqual(self.tester.image, changed.image)

    def test_architectures_are_opt_in_and_use_separate_image_tags(self):
        self.assertEqual(self.tester.architectures, ("amd64",))
        self.assertEqual(self.tester.image_for("amd64"), self.tester.image)
        self.assertNotEqual(self.tester.image_for("arm64"), self.tester.image)
        custom = self.write(self.entry()).testers[-1]
        self.assertEqual(custom.architectures, ("amd64",))
        for value in ('[]', '["riscv64"]', '["arm64", "arm64"]', '"arm64"', '[1]'):
            with self.subTest(value=value):
                self.assertTrue(self.write(self.entry() + f'architectures = {value}\n').error)


@unittest.skipUnless(all(shutil.which(tool) for tool in ("sh", "make", "cc", "ar")), "C build tools required")
class SupraRebuildTests(unittest.TestCase):
    def test_foreign_up_to_date_outputs_rebuild_only_in_the_project_copy(self):
        import time
        with TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original"
            original.mkdir()
            (original / "stub.c").write_text("int answer(void) { return 42; }\n")
            (original / "Makefile").write_text("all: lib.a\nlib.a: stub.o\n\tar rcs lib.a stub.o\nstub.o: stub.c\n\tcc -c stub.c -o stub.o\nfclean:\n\trm -f lib.a stub.o\n")
            for name in ("stub.o", "lib.a"):
                (original / name).write_bytes(b"foreign build output")
                os.utime(original / name, (time.time() + 3600,) * 2)
            before = {p.name: p.read_bytes() for p in original.iterdir()}
            copy = root / "copy with spaces"
            shutil.copytree(original, copy)
            wrapper = str(files("ft_tui").joinpath("tester_images", "supra.sh"))
            process = subprocess.run(["sh", wrapper, sys.executable, "-c", "import sys; print(repr(sys.argv[1:]))",
                                      "argument with spaces", "$(touch nope)"], cwd=copy, capture_output=True, text=True, timeout=20)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            self.assertIn("argument with spaces", process.stdout)
            self.assertFalse((copy / "nope").exists())
            self.assertNotEqual((copy / "stub.o").read_bytes(), b"foreign build output")
            self.assertIn("stub.o", subprocess.check_output(["ar", "t", "lib.a"], cwd=copy, text=True).splitlines())
            self.assertEqual({p.name: p.read_bytes() for p in original.iterdir()}, before)

    def test_failed_cleanup_stops_before_the_tester_starts(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Makefile").write_text("fclean:\n\tfalse\n")
            wrapper = str(files("ft_tui").joinpath("tester_images", "supra.sh"))
            process = subprocess.run(["sh", wrapper, sys.executable, "-c", "from pathlib import Path; Path('started').touch()"],
                                     cwd=root, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse((root / "started").exists())


class TesterDockerTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="testers space ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.service = TesterDocker(self.root, Host("linux", "amd64", "ubuntu", "noble"))
        self.tester = replace(docker_fixture(), result_file=None)
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
        self.assertEqual(calls[0][-1], f"{self.tester.repository}#{self.tester.ref}")
        self.assertEqual(calls[0][:6], ["docker", "build", "--progress", "plain", "--platform", "linux/amd64"])
        self.assertEqual(calls[1][:3], ["docker", "image", "tag"])
        self.assertFalse(any("install.sh" in " ".join(args) for args in calls))

    def test_bundled_recipe_build_uses_an_isolated_packaged_context_and_pinned_source(self):
        tester = next(t for t in load_catalog(self.root / "absent").testers if t.id == "supra-printf")
        terminal = Mock()
        observed = []
        def run(args, **kwargs):
            if "build" in args:
                context = Path(args[-1])
                observed.append(context)
                self.assertEqual(sorted(p.name for p in context.iterdir()), ["Dockerfile", "supra.sh"])
                self.assertIn("AS builder", (context / "Dockerfile").read_text())
                self.assertIn("TESTER_REPOSITORY=" + tester.repository, args)
                self.assertIn("TESTER_REF=" + tester.ref, args)
        terminal.run.side_effect = run
        with patch.object(self.service, "_require_ready", return_value="docker"), \
                patch.object(self.service, "installed", side_effect=[False, True]), \
                patch.object(self.service, "_cleanup"):
            self.service.install(tester, terminal)
        self.assertEqual(len(observed), 1)
        self.assertFalse(observed[0].exists())
        runtime = self.service._runtime_arguments(tester)
        self.assertIn("/tmp:rw,exec,nosuid,nodev,size=256m", runtime)
        self.assertIn("--read-only", runtime)
        self.assertIn("none", runtime)
        self.assertIn("no-new-privileges=true", runtime)
        self.assertEqual(self.service._runtime_arguments(self.tester), [])

    def test_network_build_failure_and_interrupt_never_publish_install(self):
        for failure_at in ("build", "tag"):
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
                        expected = TesterError if isinstance(failure, subprocess.CalledProcessError) else type(failure)
                        with self.assertRaises(expected):
                            self.service.install(self.tester, terminal)
                        calls = [call.args[0] for call in terminal.run.call_args_list]
                        if failure_at == "build":
                            self.assertFalse(any("tag" in args for args in calls))
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

    def test_tester_writes_and_cleanup_never_change_the_checkout(self):
        project = self.root / "project"
        project.mkdir()
        (project / "source.c").write_text("original")
        (project / ".git").mkdir()
        (project / ".git/config").write_text("private remote configuration")
        (project / "source-link").symlink_to("source.c")
        for failure in (None, KeyboardInterrupt(), subprocess.CalledProcessError(1, "tester")):
            mounted = []

            def run(args, **kwargs):
                fields = next(csv.reader([args[args.index("--mount") + 1]]))
                copy = Path(next(field.removeprefix("source=") for field in fields if field.startswith("source=")))
                mounted.append(copy)
                self.assertNotEqual(copy, project)
                self.assertFalse((copy / ".git").exists())
                self.assertTrue((copy / "source-link").is_symlink())
                (copy / "source.c").write_text("tester changed this")
                (copy / "artifact").write_text("build output")
                if failure:
                    raise failure

            terminal = Mock()
            terminal.run.side_effect = run
            with patch.object(self.service, "_require_ready", return_value="docker"), \
                    patch.object(self.service, "installed", return_value=True), \
                    patch.object(self.service, "_user_arguments", return_value=[]), \
                    patch.object(self.service, "_preflight"), \
                    patch.object(self.service, "_cleanup"):
                if isinstance(failure, KeyboardInterrupt):
                    with self.assertRaises(KeyboardInterrupt):
                        self.service.run(self.tester, str(project), terminal)
                else:
                    result = self.service.run(self.tester, str(project), terminal)
                    self.assertEqual(result.status, "process_failed" if failure else "unknown")
            self.assertEqual((project / "source.c").read_text(), "original")
            self.assertEqual((project / ".git/config").read_text(), "private remote configuration")
            self.assertFalse((project / "artifact").exists())
            self.assertEqual(len(mounted), 1)
            self.assertFalse(mounted[0].exists())

    def synthetic_result(self, report=None, *, exit_code=0, configured=True, inherited=None, script=None):
        from io import BytesIO
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        from ft_tui.features.projects.adapters.tester_terminal import WorkspaceSession
        project = self.root / "project"
        project.mkdir(exist_ok=True)
        if inherited is not None:
            (project / "result.json").write_text(inherited)
        tester = replace(self.tester, result_file="result.json" if configured else None)
        log = BytesIO()
        terminal = WorkspaceSession(log, lambda data: None)
        mounted = []

        def run(terminal, args, **kwargs):
            fields = next(csv.reader([args[args.index("--mount") + 1]]))
            copy = Path(next(field.removeprefix("source=") for field in fields if field.startswith("source=")))
            mounted.append(copy)
            program = "from pathlib import Path; import sys, os; "
            if report is not None:
                program += f"Path('result.json').write_text({report!r}); "
            if script is not None:
                program += script + "; "
            program += f"print('synthetic tester finished'); sys.exit({exit_code})"
            terminal.run([sys.executable, "-c", program], cwd=copy)

        with (patch.object(self.service, "_require_ready", return_value="docker"),
              patch.object(self.service, "status", return_value=DockerStatus("ready")),
              patch.object(self.service, "_install"),
              patch.object(self.service, "installed", return_value=True),
              patch.object(self.service, "_user_arguments", return_value=[]),
              patch.object(self.service, "_preflight"),
              patch.object(self.service, "_run", side_effect=run),
              patch.object(self.service, "_cleanup")):
            result = self.service.prepare_and_run(tester, str(project), terminal)
        self.assertIn(b"synthetic tester finished", log.getvalue())
        self.assertFalse(mounted[0].exists())
        return result

    def test_zero_exit_does_not_hide_structured_test_failures(self):
        result = self.synthetic_result(json.dumps(dict(version=1, total=3, passed=2, failed=1, skipped=0, errors=0)))
        self.assertIsNotNone(result, "the runner must return a structured outcome")
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.summary.failed, 1)
        self.assertEqual(result.summary.total, 3)
        self.assertFalse((self.root / "project/result.json").exists())

    def test_process_exit_without_a_reader_is_not_a_passing_test_result(self):
        self.assertEqual(self.synthetic_result(configured=False).status, "unknown")
        result = self.synthetic_result(configured=False, exit_code=1)
        self.assertEqual(result.status, "process_failed")
        self.assertEqual(result.exit_code, 1)

    def test_nonzero_exit_with_reported_failures_is_a_test_failure(self):
        report = json.dumps(dict(version=1, total=3, passed=2, failed=1, skipped=0, errors=0))
        result = self.synthetic_result(report, exit_code=1)
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.exit_code, 1)

    def test_nonzero_exit_cannot_be_overridden_by_a_passing_report(self):
        report = json.dumps(dict(version=1, total=3, passed=3, failed=0, skipped=0, errors=0))
        self.assertEqual(self.synthetic_result(report).status, "passed")
        self.assertEqual(self.synthetic_result(report, exit_code=2).status, "process_failed")

    def test_invalid_or_empty_summaries_are_unreadable_not_passing(self):
        valid = dict(version=1, total=3, passed=3, failed=0, skipped=0, errors=0)
        invalid = [None, "not JSON", "[]", "{}", "{" + "[" * 2000,
                   json.dumps({**valid, "version": 2}), json.dumps({**valid, "version": True}),
                   json.dumps({**valid, "failed": -1}), json.dumps({**valid, "passed": True}),
                   json.dumps({**valid, "passed": "3"}), json.dumps({**valid, "passed": 2}),
                   json.dumps(dict(version=1, total=0, passed=0, failed=0, skipped=0, errors=0)),
                   json.dumps(dict(version=1, total=3, passed=0, failed=0, skipped=3, errors=0))]
        for report in invalid:
            with self.subTest(report=report):
                try:
                    result = self.synthetic_result(report)
                except (ValueError, TypeError, KeyError, OSError, RecursionError) as error:
                    self.fail(f"unreadable summaries must be outcomes, not crashes: {type(error).__name__}")
                self.assertEqual(result.status, "unreadable")
                self.assertIsNone(result.summary)

    def test_incomplete_reports_never_confirm_a_pass(self):
        report = dict(version=1, total=1, passed=0, failed=0, skipped=1, errors=0, incomplete=True)
        result = self.synthetic_result(json.dumps(report))
        self.assertEqual(result.status, "unknown")
        self.assertTrue(result.summary.incomplete)
        report.update(total=2, failed=1)
        self.assertEqual(self.synthetic_result(json.dumps(report)).status, "failed")
        report.update(incomplete="yes")
        self.assertEqual(self.synthetic_result(json.dumps(report)).status, "unreadable")
        report = dict(version=1, total=2, passed=1, failed=0, skipped=1, errors=0)
        self.assertEqual(self.synthetic_result(json.dumps(report)).status, "unknown")

    def test_results_must_be_fresh_regular_bounded_files_inside_the_copy(self):
        report = json.dumps(dict(version=1, total=1, passed=1, failed=0, skipped=0, errors=0))
        self.assertEqual(self.synthetic_result(inherited=report).status, "unreadable")
        self.assertEqual((self.root / "project/result.json").read_text(), report)
        outside = self.root / "outside.json"
        outside.write_text(report)
        for script in (f"Path('result.json').symlink_to({str(outside)!r})",
                       "Path('result.json').mkdir()",
                       "os.mkfifo('result.json')",
                       "Path('result.json').write_bytes(b' ' * 65537)",
                       "Path('result.json').write_bytes(b'\\xff')"):
            with self.subTest(script=script):
                self.assertEqual(self.synthetic_result(script=script).status, "unreadable")
        self.assertEqual(outside.read_text(), report)

    def test_docker_launch_failures_cannot_be_reported_as_test_failures(self):
        report = json.dumps(dict(version=1, total=1, passed=0, failed=1, skipped=0, errors=0))
        for code in (125, 126, 127):
            with self.subTest(code=code), self.assertRaises(subprocess.CalledProcessError):
                self.synthetic_result(report, exit_code=code)

    def test_nested_report_paths_reject_symlink_parents_without_deleting_the_target(self):
        from ft_tui.features.projects.adapters.tester_reports import clear_report, read_report
        report = json.dumps(dict(version=1, total=1, passed=1, failed=0, skipped=0, errors=0))
        project, outside = self.root / "copy", self.root / "outside"
        project.mkdir()
        outside.mkdir()
        target = outside / "result.json"
        target.write_text(report)
        (project / "reports").symlink_to(outside, target_is_directory=True)
        for operation in (clear_report, read_report):
            with self.subTest(operation=operation.__name__), self.assertRaises(OSError):
                operation(project, "reports/result.json")
        self.assertEqual(target.read_text(), report)
        (project / "reports").unlink()
        (project / "reports").mkdir()
        (project / "reports/result.json").write_text(report)
        self.assertEqual(read_report(project, "reports/result.json").passed, 1)
        clear_report(project, "reports/result.json")
        self.assertFalse((project / "reports/result.json").exists())

    def test_global_operation_lock_is_released_after_interruption(self):
        with self.assertRaises(KeyboardInterrupt), self.service.operation():
            with self.assertRaises(TesterError), self.service.operation():
                pass
            raise KeyboardInterrupt
        with self.service.operation():
            self.assertTrue(self.service.busy)
        self.assertFalse(self.service.busy)

    def test_docker_installation_plans_are_user_only_and_not_executed(self):
        for host in (Host("linux", "amd64", "ubuntu", "noble"), Host("linux", "arm64", "debian", "trixie"),
                     Host("win32", "amd64"), Host("darwin", "riscv64")):
            self.assertIsNone(TesterDocker(self.root, host).installation())
        for architecture in ("amd64", "arm64"):
            service = TesterDocker(self.root, Host("darwin", architecture))
            plan = service.installation()
            self.assertIn(f"/mac/main/{architecture}/Docker.dmg", plan.commands[0][-1])
            self.assertEqual(plan.commands[-1], ("open", str(Path.home() / "Applications/Docker.app")))
            self.assertTrue(all(command[0] != "sudo" for command in (*plan.commands, *plan.cleanup)))

    def test_mac_cli_discovery_without_path_changes(self):
        service = TesterDocker(self.root, Host("darwin", "arm64"))
        with patch("ft_tui.features.projects.adapters.tester_docker.shutil.which", return_value=None), \
                patch("pathlib.Path.is_file", return_value=True):
            self.assertEqual(service.docker(), str(Path.home() / ".docker/bin/docker"))


class TesterRemovalTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.tester = docker_fixture()
        self.service = TesterDocker(self.root, Host("linux", "amd64"))
        self.tags = [self.tester.image, self.tester.image_for("arm64"), "42tui/docker-fixture:older"]
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
        self.tags += ["42tui/other:latest", "42tui/docker-fixture-extra:latest", "42tui/docker-fixture:<none>"]
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

    def test_germinette_removal_uses_shared_repository_not_project_id(self):
        catalog = load_catalog(self.root / "absent")
        first = catalog.for_project("python-module-00", "linux")[0]
        other = catalog.for_project("python-module-05-bis", "linux")[0]
        self.assertEqual(first.image, other.image)
        self.tags = [first.image, "42tui/unrelated:latest"]
        self.containers = [{"ID": "000000000001", "Names": "42tui-test-" + "a" * 32,
                            "Image": first.image, "State": "exited"}]
        terminal = Mock()
        self.service.remove(other, terminal)
        commands = [call.args[0] for call in terminal.run.call_args_list]
        self.assertIn("000000000001", commands[0])
        self.assertEqual(commands[1][-1], first.image)
        self.assertNotIn("42tui/unrelated:latest", commands[1])

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
        self.tester = docker_fixture()
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
                fields = next(csv.reader([args[args.index("--mount") + 1]]))
                source = next(field.removeprefix("source=") for field in fields if field.startswith("source="))
                folder = next(Path(source).glob(".42tui-probe-*"))
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
            tester = docker_fixture()
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
            tester = docker_fixture()
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


class TesterAutomaticSetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.service = TesterDocker(self.root / 'testers', Host('linux', 'amd64', 'ubuntu', 'noble'))
        self.tester = docker_fixture()
        self.terminal = Mock()
        desktop = patch.object(self.service, '_desktop_installed', return_value=True)
        desktop.start()
        self.addCleanup(desktop.stop)

    def test_run_installs_missing_image_and_uses_one_connection(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        with (patch.object(self.service, 'status', return_value=DockerStatus('ready')),
              patch.object(self.service, 'connection', side_effect=nullcontext) as connection,
              patch.object(self.service, '_install') as install,
              patch.object(self.service, '_run_tester') as run):
            self.service.prepare_and_run(self.tester, str(self.root), self.terminal)
        connection.assert_called_once()
        install.assert_called_once_with(self.tester, self.terminal)
        run.assert_called_once_with(self.tester, str(self.root), self.terminal)

    def test_missing_folder_prevents_all_setup(self):
        with patch.object(self.service, 'status') as status, self.assertRaisesRegex(TesterError, 'local project folder'):
            self.service.prepare_and_run(self.tester, str(self.root / 'absent'), self.terminal)
        status.assert_not_called()
        self.terminal.run.assert_not_called()

    def test_mac_missing_docker_requires_approved_plan(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        self.service.host = Host('darwin', 'arm64')
        with patch.object(self.service, 'status', return_value=DockerStatus('missing')):
            with self.assertRaisesRegex(TesterError, 'approval'):
                self.service.prepare_and_run(self.tester, str(self.root), self.terminal)
        self.terminal.run.assert_not_called()

    def test_approved_mac_install_continues_to_run(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        self.service.host = Host('darwin', 'arm64')
        plan = self.service.installation()
        with (patch.object(self.service, 'status', side_effect=[DockerStatus('missing'), DockerStatus('ready')]),
              patch.object(self.service, 'install_docker') as install_docker,
              patch.object(self.service, 'connection', side_effect=nullcontext),
              patch.object(self.service, '_install'), patch.object(self.service, '_run_tester') as run):
            self.service.prepare_and_run(self.tester, str(self.root), self.terminal, plan=plan)
        install_docker.assert_called_once_with(plan, self.terminal)
        run.assert_called_once()

    def test_desktop_starts_and_waits_before_running(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        self.service.host = Host('darwin', 'arm64')
        with (patch.object(self.service, 'status', side_effect=[DockerStatus('stopped'), DockerStatus('ready')]),
              patch.object(self.service, '_desktop_path', return_value=None),
              patch.object(self.service, '_docker_endpoint', return_value='unix:///Users/test/.docker/run/docker.sock'),
              patch.object(self.service, 'connection', side_effect=nullcontext),
              patch.object(self.service, '_install'), patch.object(self.service, '_run_tester') as run,
              patch('ft_tui.features.projects.adapters.tester_docker.time.sleep')):
            self.service.prepare_and_run(self.tester, str(self.root), self.terminal)
        self.terminal.run.assert_called_once_with(['open', '-a', 'Docker'])
        run.assert_called_once()

    def test_timeout_and_denied_access_never_build_or_run(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        self.service.host = Host('darwin', 'arm64')
        for state in ('stopped', 'denied', 'incompatible'):
            with (self.subTest(state=state),
                  patch.object(self.service, 'status', return_value=DockerStatus(state)),
                  patch.object(self.service, '_docker_endpoint', return_value='unix:///Users/test/.docker/run/docker.sock'),
                  patch.object(self.service, '_install') as install,
                  patch.object(self.service, '_run_tester') as run,
                  patch('ft_tui.features.projects.adapters.tester_docker.time.monotonic', side_effect=[0, 181]),
                  self.assertRaises(TesterError)):
                self.service.prepare_and_run(self.tester, str(self.root), self.terminal)
            install.assert_not_called()
            run.assert_not_called()

    def test_linux_startup_plan_respects_remote_and_rootless_contexts(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        for endpoint, expected in [
            ('ssh://remote', None), ('tcp://localhost:2376', None), ('unix:///var/run/docker.sock', None),
            (f'unix:///run/user/{os.getuid()}/docker.sock', ('systemctl', '--user', 'start', 'docker')),
        ]:
            with (self.subTest(endpoint=endpoint),
                  patch.dict(os.environ, {'DOCKER_HOST': endpoint, 'DOCKER_CONTEXT': ''})):
                plan = self.service.setup_plan(DockerStatus('stopped'))
                self.assertEqual(plan.commands[0] if plan else None, expected)

    def test_setup_interruption_never_runs_tester(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        self.service.host = Host('darwin', 'arm64')
        plan = self.service.installation()
        with (patch.object(self.service, 'status', return_value=DockerStatus('missing')),
              patch.object(self.service, 'install_docker', side_effect=KeyboardInterrupt),
              patch.object(self.service, '_run_tester') as run, self.assertRaises(KeyboardInterrupt)):
            self.service.prepare_and_run(self.tester, str(self.root), self.terminal, plan=plan)
        run.assert_not_called()

    def test_mac_dmg_detaches_even_after_copy_failure(self):
        self.service.host = Host('darwin', 'arm64')
        plan = self.service.installation()
        def run(command):
            if command[0] == 'ditto':
                raise subprocess.CalledProcessError(1, command)
        self.terminal.run.side_effect = run
        with (patch.object(self.service, '_desktop_installed', return_value=False),
              self.assertRaises(subprocess.CalledProcessError)):
            self.service.install_docker(plan, self.terminal)
        self.assertTrue(any('detach' in call.args[0] for call in self.terminal.run.call_args_list))

    def test_remote_mac_context_never_starts_local_desktop(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        self.service.host = Host('darwin', 'arm64')
        with (patch.object(self.service, 'status', return_value=DockerStatus('stopped')),
              patch.dict(os.environ, {'DOCKER_HOST': 'ssh://remote', 'DOCKER_CONTEXT': ''}),
              self.assertRaisesRegex(TesterError, 'selected context')):
            self.service.prepare_and_run(self.tester, str(self.root), self.terminal)
        self.terminal.run.assert_not_called()

    def test_standalone_mac_cli_still_offers_desktop_installation(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        self.service.host = Host('darwin', 'arm64')
        with (patch.object(self.service, '_desktop_installed', return_value=False),
              patch.object(self.service, '_docker_endpoint', return_value='unix:///var/run/docker.sock'),
              patch.object(self.service, 'installation') as installation):
            self.assertIs(self.service.setup_plan(DockerStatus('stopped')), installation.return_value)
            self.service.status = Mock(side_effect=[DockerStatus('stopped'), DockerStatus('ready')])
            with (patch.object(self.service, 'install_docker') as install,
                  patch.object(self.service, 'connection', side_effect=nullcontext),
                  patch.object(self.service, '_install'), patch.object(self.service, '_run_tester') as run):
                self.service.prepare_and_run(self.tester, str(self.root), self.terminal, plan=installation.return_value)
            install.assert_called_once()
            run.assert_called_once()


class TesterUnprivilegedTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.tester = docker_fixture()
        self.service = TesterDocker(self.root / 'testers', Host('linux', 'amd64', 'ubuntu', 'noble'))

    def test_linux_never_offers_system_installation_or_system_service_start(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        self.assertIsNone(self.service.installation())
        with patch.object(self.service, '_docker_endpoint', return_value='unix:///var/run/docker.sock'):
            self.assertIsNone(self.service.setup_plan(DockerStatus('stopped')))

    def test_mac_installation_stays_under_home_without_privileged_helpers(self):
        self.service.host = Host('darwin', 'arm64')
        with patch('pathlib.Path.home', return_value=self.root):
            plan = self.service.installation()
        commands = (*plan.commands, *plan.cleanup)
        self.assertTrue(any(command[0] == 'mv' and command[-1] == str(self.root / 'Applications/Docker.app')
                            for command in commands))
        self.assertFalse(any(Path(command[0]).name in {'sudo', 'su', 'doas', 'pkexec', 'brew', 'apt-get'}
                             for command in commands))
        self.assertFalse(any('/Contents/MacOS/install' in part for command in commands for part in command))

    def test_build_fetches_pinned_source_in_builder_without_host_git(self):
        terminal = Mock()
        with (patch.object(self.service, 'connection', side_effect=nullcontext),
              patch.object(self.service, '_require_ready', return_value='docker'),
              patch.object(self.service, 'installed', side_effect=[False, True]),
              patch.object(self.service, 'architecture', return_value='amd64'),
              patch.object(self.service, '_cleanup'),
              patch('ft_tui.features.projects.adapters.tester_docker.shutil.which', return_value=None),
              patch.dict(os.environ, {'DOCKER_BUILDKIT': '0'})):
            self.service.install(self.tester, terminal)
        commands = [call.args[0] for call in terminal.run.call_args_list]
        self.assertEqual(commands[0][-1], f'{self.tester.repository}#{self.tester.ref}')
        self.assertEqual(terminal.run.call_args_list[0].kwargs['env']['DOCKER_BUILDKIT'], '1')
        self.assertTrue(all(command[0] == 'docker' for command in commands))

    def test_linux_missing_or_denied_docker_never_changes_machine(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        terminal = Mock()
        for state in ('missing', 'denied', 'stopped'):
            with (self.subTest(state=state),
                  patch.object(self.service, 'status', return_value=DockerStatus(state)),
                  patch.object(self.service, '_docker_endpoint', return_value='unix:///var/run/docker.sock'),
                  self.assertRaisesRegex(TesterError, 'school|accessible|staff')):
                self.service.prepare_and_run(self.tester, str(self.root), terminal)
        terminal.run.assert_not_called()


    def test_existing_rootless_service_starts_without_system_access(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerStatus
        terminal = Mock()
        with (patch.object(self.service, '_docker_endpoint', return_value=f'unix:///run/user/{os.getuid()}/docker.sock'),
              patch.object(self.service, 'status', side_effect=[DockerStatus('stopped'), DockerStatus('ready')]),
              patch.object(self.service, 'connection', side_effect=nullcontext),
              patch.object(self.service, '_install'), patch.object(self.service, '_run_tester') as run):
            plan = self.service.setup_plan(DockerStatus('stopped'))
            self.service.prepare_and_run(self.tester, str(self.root), terminal, plan=plan)
        terminal.run.assert_called_once_with(['systemctl', '--user', 'start', 'docker'])
        run.assert_called_once()

    def test_user_app_cli_and_launch_are_discovered_without_path_changes(self):
        self.service.host = Host('darwin', 'arm64')
        app = self.root / 'Applications/Docker.app'
        binary = app / 'Contents/Resources/bin/docker'
        binary.parent.mkdir(parents=True)
        binary.write_text('fixture')
        with (patch('pathlib.Path.home', return_value=self.root),
              patch('ft_tui.features.projects.adapters.tester_docker.shutil.which', return_value=None)):
            self.assertEqual(self.service.docker(), str(binary))
            self.assertEqual(self.service._desktop_command(), ['open', str(app)])

    def test_privileged_commands_and_shell_wrappers_are_rejected_before_execution(self):
        from ft_tui.features.projects.adapters.tester_docker import DockerInstallation
        for command in [('sudo', 'true'), ('/usr/bin/sudo', 'true'), ('pkexec', 'true'),
                        ('systemctl', 'start', 'docker'), ('sh', '-c', 'sudo true'), ('apt-get', 'update')]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                DockerInstallation((command,))

    def test_remote_build_context_keeps_subdirectory_and_rejects_escape(self):
        for context in ('../outside', '/outside', 'docker files'):
            terminal = Mock()
            tester = replace(self.tester, context=context)
            with (patch.object(self.service, 'connection', side_effect=nullcontext),
                  patch.object(self.service, '_require_ready', return_value='docker'),
                  patch.object(self.service, 'architecture', return_value='amd64'),
                  patch.object(self.service, 'installed', side_effect=[False, True]),
                  patch.object(self.service, '_cleanup')):
                if context == 'docker files':
                    self.service.install(tester, terminal)
                    self.assertEqual(terminal.run.call_args_list[0].args[0][-1],
                                     f'{tester.repository}#{tester.ref}:docker%20files')
                else:
                    with self.assertRaises(TesterError):
                        self.service.install(tester, terminal)
                    terminal.run.assert_not_called()

    def test_failed_mac_copy_leaves_no_installed_bundle_and_can_retry(self):
        import shutil
        self.service.host = Host('darwin', 'arm64')
        terminal = Mock()
        copied = []
        def run(command):
            if command[0] == 'ditto':
                partial = Path(command[-1])
                partial.mkdir(parents=True)
                copied.append(partial)
                raise subprocess.CalledProcessError(1, command)
            if command[0] == 'rm':
                shutil.rmtree(command[-1], ignore_errors=True)
        terminal.run.side_effect = run
        with patch('pathlib.Path.home', return_value=self.root):
            plan = self.service.installation()
            with self.assertRaises(subprocess.CalledProcessError):
                self.service.install_docker(plan, terminal)
            self.assertFalse(self.service._desktop_installed())
            self.assertFalse(copied[0].exists())
            terminal.run = Mock()
            self.service.install_docker(self.service.installation(), terminal)
            self.assertTrue(terminal.run.called)

    def test_non_git_suffix_never_falls_back_to_an_unpinned_http_build(self):
        terminal = Mock()
        tester = replace(self.tester, repository='https://example.com/tester')
        with (patch.object(self.service, 'connection', side_effect=nullcontext),
              patch.object(self.service, '_require_ready', return_value='docker'),
              patch.object(self.service, 'architecture', return_value='amd64'),
              patch.object(self.service, 'installed', return_value=False),
              patch('ft_tui.features.projects.adapters.tester_docker.shutil.which', return_value=None),
              self.assertRaisesRegex(TesterError, 'clone URL')):
            self.service.install(tester, terminal)
        terminal.run.assert_not_called()

    def test_custom_clone_without_git_suffix_keeps_existing_git_checkout_support(self):
        terminal = Mock()
        tester = replace(self.tester, repository='https://example.com/tester')
        with (patch.object(self.service, 'connection', side_effect=nullcontext),
              patch.object(self.service, '_require_ready', return_value='docker'),
              patch.object(self.service, 'architecture', return_value='amd64'),
              patch.object(self.service, 'installed', side_effect=[False, True]),
              patch.object(self.service, '_cleanup'),
              patch('ft_tui.features.projects.adapters.tester_docker.shutil.which', return_value='/usr/bin/git')):
            self.service.install(tester, terminal)
        commands = [call.args[0] for call in terminal.run.call_args_list]
        self.assertTrue(any('fetch' in command and tester.ref in command for command in commands))
        build = next(command for command in commands if 'build' in command)
        self.assertFalse(build[-1].startswith('https://'))

    def test_remote_build_preserves_git_metadata_for_custom_dockerfiles(self):
        terminal = Mock()
        with (patch.object(self.service, 'connection', side_effect=nullcontext),
              patch.object(self.service, '_require_ready', return_value='docker'),
              patch.object(self.service, 'architecture', return_value='amd64'),
              patch.object(self.service, 'installed', side_effect=[False, True]),
              patch.object(self.service, '_cleanup')):
            self.service.install(self.tester, terminal)
        build = terminal.run.call_args_list[0].args[0]
        self.assertIn('BUILDKIT_CONTEXT_KEEP_GIT_DIR=1', build)


class NativeTesterTests(unittest.TestCase):
    def test_real_native_setup_results_and_project_preservation(self):
        import io
        from ft_tui.features.projects.adapters.tester_native import run_native
        from ft_tui.features.projects.adapters.tester_terminal import WorkspaceSession
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            source, project = root / 'source', root / 'project'
            source.mkdir()
            project.mkdir()
            (source / 'README').write_text('synthetic tester')
            def git(*args):
                return subprocess.check_output(['git', '-C', str(source), *args], stderr=subprocess.DEVNULL, text=True).strip()
            git('init')
            git('add', 'README')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-m', 'fixture')
            revision = git('rev-parse', 'HEAD')
            (project / 'main.c').write_text('original')
            tester = replace(docker_fixture(), runtime='native', repository=str(source), ref=revision,
                             prepare=(("{python}", '-c', 'from pathlib import Path; Path("prepared").touch()'),),
                             command=("{python}", '-c', 'import json; from pathlib import Path; assert Path("prepared").exists(); '
                                      'Path("main.c").write_text("changed"); '
                                      'Path("result.json").write_text(json.dumps(dict(version=1,total=1,passed=1,failed=0,errors=0,skipped=0)))'),
                             result_file='result.json')
            result = run_native(tester, str(project), WorkspaceSession(io.BytesIO(), lambda data: None))
            self.assertEqual(result.status, 'passed')
            self.assertEqual((project / 'main.c').read_text(), 'original')
            self.assertFalse((project / 'result.json').exists())
            failing = replace(tester, command=('{python}', '-c', 'raise SystemExit(3)'), result_file=None)
            self.assertEqual(run_native(failing, str(project), WorkspaceSession(io.BytesIO(), lambda data: None)).status,
                             'process_failed')
            unreadable = replace(tester, command=('{python}', '-c', 'print("no report")'))
            self.assertEqual(run_native(unreadable, str(project), WorkspaceSession(io.BytesIO(), lambda data: None)).status,
                             'unreadable')
            cancelled = replace(tester, command=('{python}', '-c', 'import time; print("NATIVE_READY",flush=True); time.sleep(30)'))
            terminal = WorkspaceSession(io.BytesIO(), lambda data: terminal.cancel() if data.startswith(b'NATIVE_READY') else None)
            with self.assertRaises(KeyboardInterrupt):
                run_native(cancelled, str(project), terminal)
            self.assertEqual((project / 'main.c').read_text(), 'original')
            broken = replace(tester, prepare=(('{python}', '-c', 'raise SystemExit(4)'),))
            with self.assertRaises(subprocess.CalledProcessError):
                run_native(broken, str(project), WorkspaceSession(io.BytesIO(), lambda data: None))


    def test_native_rejects_external_links_before_executing(self):
        from ft_tui.features.projects.adapters.tester_native import run_native
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / 'project'
            project.mkdir()
            (root / 'private').write_text('private')
            (project / 'linked').symlink_to(root / 'private')
            tester = replace(docker_fixture(), runtime='native')
            terminal = Mock()
            with self.assertRaisesRegex(TesterError, 'links outside'):
                run_native(tester, str(project), terminal)
            terminal.run.assert_not_called()
