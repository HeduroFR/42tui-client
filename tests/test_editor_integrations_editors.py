"""Editor install targets, CLI discovery and heartbeat verification."""
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from ft_tui.db.database import make_session_factory
from ft_tui.db.models import ActivityHeartbeat, Project
from ft_tui.features.editor_integrations.adapters.editors import EditorCommands
from ft_tui.features.editor_integrations.adapters.files import read_manifest
from ft_tui.features.editor_integrations.adapters.heartbeat import HeartbeatProbe
from ft_tui.integrations import INTEGRATION_VERSION


def make_executable(path: Path, body: str) -> Path:
    path.write_text(body)
    path.chmod(0o755)
    return path


class EditorCommandTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name) / "home"
        self.home.mkdir()
        self.assets = Path(self.directory.name) / "assets"

    def commands(self, **overrides):
        return EditorCommands(
            home=self.home,
            environ={"XDG_DATA_HOME": str(self.home / "data"), **overrides},
            which=lambda _name: None,
            run=lambda *args, **kwargs: None,
        )

    def test_targets_follow_editor_conventions(self):
        commands = self.commands()
        self.assertEqual(commands.target("vim"), self.home / ".vim/pack/42tui/start/ft_tui")
        self.assertEqual(commands.target("nvim"), self.home / "data/nvim/site/pack/42tui/start/ft_tui")

    def test_vim_install_writes_generated_config_and_manifest(self):
        (self.assets / "plugin").mkdir(parents=True)
        (self.assets / "plugin" / "ft_tui.vim").write_text("plugin")
        commands = self.commands()
        target = commands.install("vim", "/opt/42tui's/bin/42tui", self.assets)
        self.assertEqual(target, commands.target("vim"))
        self.assertIn("42tui''s", (target / "ft_tui_config.vim").read_text())
        self.assertEqual(read_manifest(target)["cli_path"], "/opt/42tui's/bin/42tui")
        self.assertEqual(commands.install("vim", "/opt/42tui's/bin/42tui", self.assets), target)

    def test_missing_asset_is_reported(self):
        from ft_tui.features.editor_integrations.adapters.files import IntegrationFilesError

        with self.assertRaises(IntegrationFilesError) as error:
            self.commands().install("zed", "/bin/42tui", self.assets)
        self.assertEqual(error.exception.code, "asset_missing")

    def test_vscode_falls_back_to_a_marked_extension_folder(self):
        (self.assets).mkdir(parents=True)
        (self.assets / "package.json").write_text('{"main": "./extension.js"}')
        (self.assets / "extension.js").write_text("// extension")
        commands = self.commands()
        target = commands.install("vscode", "/bin/42tui", self.assets)
        self.assertEqual(target.parent, self.home / ".vscode" / "extensions")
        self.assertEqual(read_manifest(target)["editor"], "vscode")
        self.assertEqual((target / "42tui-path.txt").read_text(), "/bin/42tui")

    def test_vscode_uses_the_official_cli_when_available(self):
        (self.assets).mkdir(parents=True)
        (self.assets / "package.json").write_text('{"main": "./extension.js"}')
        (self.assets / "extension.js").write_text("// extension")
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        log = self.home / "cli.log"
        installed = self.home / ".vscode" / "extensions" / f"42tui.42tui-activity-{INTEGRATION_VERSION}"
        code = make_executable(
            bin_dir / "code",
            f"#!/bin/sh\nprintf '%s\\n' \"$@\" > '{log}'\nmkdir -p '{installed}'\n"
            f"printf '{{\"main\": \"./extension.js\"}}' > '{installed}/package.json'\n"
            f"printf '// extension' > '{installed}/extension.js'\n",
        )
        commands = EditorCommands(
            home=self.home,
            environ={"XDG_DATA_HOME": str(self.home / "data")},
            which=lambda name: str(code) if name == "code" else None,
            run=__import__("subprocess").run,
        )
        target = commands.install("vscode", "/bin/42tui", self.assets)
        self.assertEqual(target, installed)
        self.assertIn("--install-extension", log.read_text())
        self.assertIn("--force", log.read_text())
        self.assertEqual(read_manifest(target)["cli_path"], "/bin/42tui")

    def test_vscode_codium_cli_installs_into_the_oss_directory(self):
        (self.assets).mkdir(parents=True)
        (self.assets / "package.json").write_text('{"main": "./extension.js"}')
        (self.assets / "extension.js").write_text("// extension")
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        installed = self.home / ".vscode-oss" / "extensions" / f"42tui.42tui-activity-{INTEGRATION_VERSION}"
        codium = make_executable(
            bin_dir / "codium",
            f"#!/bin/sh\nmkdir -p '{installed}'\n"
            f"printf '{{\"main\": \"./extension.js\"}}' > '{installed}/package.json'\n"
            f"printf '// extension' > '{installed}/extension.js'\n",
        )
        commands = EditorCommands(
            home=self.home,
            environ={"XDG_DATA_HOME": str(self.home / "data")},
            which=lambda name: str(codium) if name == "codium" else None,
            run=__import__("subprocess").run,
        )
        self.assertEqual(commands.install("vscode", "/bin/42tui", self.assets), installed)

    def test_vscode_flatpak_cli_is_used_when_it_is_the_only_option(self):
        (self.assets).mkdir(parents=True)
        (self.assets / "package.json").write_text('{"main": "./extension.js"}')
        (self.assets / "extension.js").write_text("// extension")
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        installed = self.home / ".vscode" / "extensions" / f"42tui.42tui-activity-{INTEGRATION_VERSION}"
        package = f"'{installed}/package.json'"
        flatpak = make_executable(
            bin_dir / "flatpak",
            f"#!/bin/sh\nmkdir -p '{installed}'\nprintf '{{\"main\": \"./extension.js\"}}' > {package}\n"
            f"printf '// extension' > '{installed}/extension.js'\n",
        )
        commands = EditorCommands(
            home=self.home,
            environ={"XDG_DATA_HOME": str(self.home / "data")},
            which=lambda name: str(flatpak) if name == "flatpak" else None,
            run=__import__("subprocess").run,
        )
        target = commands.install("vscode", "/bin/42tui", self.assets)
        self.assertEqual(target, installed)

    def test_uninstall_removes_only_marked_tree(self):
        (self.assets / "plugin").mkdir(parents=True)
        (self.assets / "plugin" / "ft_tui.vim").write_text("plugin")
        commands = self.commands()
        commands.install("vim", "/bin/42tui", self.assets)
        self.assertTrue(commands.uninstall("vim"))
        self.assertFalse(commands.target("vim").exists())


class HeartbeatProbeTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.factory = make_session_factory("sqlite:///:memory:")
        self.addCleanup(lambda: self.factory.kw["bind"].dispose())

    def test_resolve_cli_validates_the_explicit_path(self):
        cli = make_executable(self.root / "42tui", "#!/bin/sh\nprintf '42tui 0.6.2\\n'\n")
        probe = HeartbeatProbe(self.factory)
        self.assertEqual(probe.resolve_cli(str(cli)), cli)
        self.assertIsNone(probe.resolve_cli(str(self.root / "missing")))

    def test_verify_reports_unavailable_without_a_project(self):
        cli = make_executable(self.root / "42tui", "#!/bin/sh\nexit 0\n")
        probe = HeartbeatProbe(self.factory)
        self.assertEqual(probe.verify(cli, "vim")[0], "unavailable")

    def test_verify_runs_the_dry_run_against_a_project(self):
        project_root = self.root / "project"
        project_root.mkdir()
        with self.factory() as session:
            session.add(Project(slug="p", name="P", local_path=str(project_root)))
            session.commit()
        arguments = self.root / "arguments"
        cli = make_executable(
            self.root / "42tui",
            f"#!/bin/sh\nprintf '%s\\n' \"$@\" > {arguments}\nexit 0\n",
        )
        probe = HeartbeatProbe(self.factory)
        self.assertEqual(probe.verify(cli, "nvim")[0], "verified")
        self.assertIn("--dry-run", arguments.read_text())
        self.assertIn(".42tui-heartbeat-check", arguments.read_text())

    def test_last_event_is_per_editor(self):
        with self.factory() as session:
            project = Project(slug="p", name="P")
            session.add(project)
            session.commit()
            now = datetime(2026, 11, 2, 12)
            session.add_all([
                ActivityHeartbeat(project_id=project.id, editor="vim", occurred_at=now),
                ActivityHeartbeat(project_id=project.id, editor="vim", occurred_at=now + timedelta(minutes=5)),
                ActivityHeartbeat(project_id=project.id, editor="zed", occurred_at=now + timedelta(minutes=9)),
            ])
            session.commit()
        self.assertEqual(HeartbeatProbe(self.factory).last_event_at("vim"), datetime(2026, 11, 2, 12, 5))
        self.assertEqual(HeartbeatProbe(self.factory).last_event_at("zed"), datetime(2026, 11, 2, 12, 9))


if __name__ == "__main__":
    unittest.main()
