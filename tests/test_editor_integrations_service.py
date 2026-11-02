"""Editor integration status and lifecycle at the service boundary."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ft_tui.db.database import make_session_factory
from ft_tui.features.editor_integrations.adapters.assets import PackagedAssets
from ft_tui.features.editor_integrations.adapters.editors import EditorCommands
from ft_tui.features.editor_integrations.adapters.files import MANIFEST
from ft_tui.features.editor_integrations.adapters.heartbeat import HeartbeatProbe
from ft_tui.features.editor_integrations.service import EditorIntegrationService
from ft_tui.integrations import INTEGRATION_VERSION


class Settings:
    def __init__(self, cli_path=""):
        self.values = {"editor_cli_path": cli_path}

    def get(self, key, default=""):
        return self.values.get(key, default)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name) / "home"
        self.home.mkdir()
        self.factory = make_session_factory("sqlite:///:memory:")
        self.addCleanup(lambda: self.factory.kw["bind"].dispose())
        self.cli = self.home / "bin" / "42tui"
        self.cli.parent.mkdir()
        self.cli.write_text("#!/bin/sh\nprintf '42tui 0.6.2\\n'\n")
        self.cli.chmod(0o755)
        self.assets = PackagedAssets()
        self.settings = Settings()

    def service(self, *, which=None, assets=None):
        commands = EditorCommands(
            home=self.home,
            environ={"XDG_DATA_HOME": str(self.home / "data")},
            which=which or (lambda name: str(self.cli) if name == "42tui" else None),
            run=__import__("subprocess").run,
        )
        probe = HeartbeatProbe(
            self.factory,
            which=which or (lambda name: str(self.cli) if name == "42tui" else None),
            detection=lambda: None,
        )
        return EditorIntegrationService(assets or self.assets, commands, probe, self.settings)

    def test_install_reports_installed_and_unverified_without_project(self):
        result = self.service().install("vim")
        self.assertTrue(result.installed)
        self.assertFalse(result.verified)
        self.assertEqual(result.code, "installed_verification_unavailable")
        self.assertEqual(result.status.state, "installed")

    def test_install_fails_when_cli_missing(self):
        with patch("ft_tui.features.editor_integrations.adapters.heartbeat.sys.executable", "/missing/python"):
            result = self.service(which=lambda _name: None).install("vim")
        self.assertFalse(result.installed)
        self.assertEqual(result.code, "cli_missing")

    def test_missing_zed_asset_is_reported_not_installed(self):
        class Assets:
            def __init__(self, root):
                self.root = root

            def version(self, editor):
                return INTEGRATION_VERSION

            def path(self, editor):
                return self.root

        empty = Path(self.directory.name) / "empty-assets"
        empty.mkdir()
        result = self.service(assets=Assets(empty)).install("zed")
        self.assertFalse(result.installed)
        self.assertEqual(result.code, "asset_missing")

    def test_status_detects_stale_cli_path(self):
        service = self.service()
        service.install("nvim")
        self.assertEqual(service.status("nvim").state, "installed")
        target = service.editors.target("nvim")
        manifest = json.loads((target / MANIFEST).read_text())
        manifest["cli_path"] = "/missing/42tui"
        (target / MANIFEST).write_text(json.dumps(manifest))
        self.assertEqual(service.status("nvim").state, "needs_repair")

    def test_verify_checks_the_installed_cli_not_a_newer_setting(self):
        other = self.home / "bin" / "other-42tui"
        other.write_text("#!/bin/sh\nprintf '42tui 0.6.2\\n'\n")
        other.chmod(0o755)
        checked = []

        class Probe:
            def resolve_cli(self, configured):
                path = Path(configured) if configured else self.cli
                return path if path.is_file() else None

            def verify(self, path, editor):
                checked.append(Path(path))
                return "verified", ""

            def last_event_at(self, editor):
                return None

        probe = Probe()
        probe.cli = self.cli
        service = EditorIntegrationService(
            self.assets,
            EditorCommands(
                home=self.home,
                environ={"XDG_DATA_HOME": str(self.home / "data")},
                which=lambda _name: None,
                run=__import__("subprocess").run,
            ),
            probe,
            Settings(str(self.cli)),
        )
        service.install("vim")
        service.settings.values["editor_cli_path"] = str(other)
        service.verify("vim")
        self.assertEqual(checked[-1], self.cli)

    def test_repair_restores_a_missing_generated_file(self):
        service = self.service()
        service.install("vim")
        target = service.editors.target("vim")
        (target / "ft_tui_config.vim").unlink()
        self.assertEqual(service.status("vim").state, "needs_repair")
        self.assertEqual(service.install("vim").code, "installed_verification_unavailable")
        self.assertTrue((target / "ft_tui_config.vim").is_file())
        self.assertEqual(service.status("vim").state, "installed")

    def test_uninstall_leaves_user_files_and_still_counts_as_removed(self):
        service = self.service()
        service.install("vim")
        target = service.editors.target("vim")
        (target / "user.txt").write_text("keep")
        result = service.uninstall("vim")
        self.assertEqual(result.code, "removed")
        self.assertEqual(service.status("vim").state, "not_installed")
        self.assertEqual((target.with_name("ft_tui-unrelated") / "user.txt").read_text(), "keep")
        self.assertFalse((target / "plugin" / "ft_tui.vim").exists())

    def test_uninstall_preserves_config_and_reports_missing(self):
        service = self.service()
        service.install("vim")
        config = service.editors.target("vim") / "ft_tui_config.vim"
        saved = Path(self.directory.name) / "saved-config"
        saved.write_text(config.read_text())
        self.assertEqual(service.uninstall("vim").code, "removed")
        self.assertTrue(saved.exists())
        self.assertEqual(service.uninstall("vim").code, "not_installed")


if __name__ == "__main__":
    unittest.main()
