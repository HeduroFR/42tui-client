"""Settings exposes editor integration state, paths and actions."""
import gc
import tempfile
import unittest
import warnings
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

from textual.widgets import Input

from ft_tui.db.database import make_session_factory
from ft_tui.features.editor_integrations.models import IntegrationResult, IntegrationStatus
from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.features.settings.views.workspace import SettingsWorkspace
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Static


def status(state="installed", verification="verified"):
    return IntegrationStatus(
        editor="vim",
        state=state,
        version="0.1.0",
        installed_version="0.1.0" if state != "not_installed" else None,
        path=Path("/tmp/ft_tui"),
        cli_path=Path("/bin/42tui"),
        cli_ok=True,
        editor_found=True,
        last_event_at=None,
        verification=verification,
    )


class FakeService:
    def __init__(self):
        self.installed = 0
        self.uninstalled = 0

    def status(self, editor):
        return status()

    def detect_cli_path(self):
        return "/bin/42tui"

    def cli_version(self, path):
        return "0.6.2"

    def install(self, editor, force=False):
        self.installed += 1
        return IntegrationResult(True, False, "installed_verification_failed", "boom", status())

    def uninstall(self, editor):
        self.uninstalled += 1
        return IntegrationResult(False, False, "removed", "", status("not_installed"))

    def verify(self, editor):
        return IntegrationResult(True, True, "verified", "", status())


class EditorSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancelled_editor_refresh_does_not_leak_coroutine(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            self.addCleanup(lambda: factory.kw["bind"].dispose())
            with factory() as session:
                save_settings(session, {"onboarding_completed": "true"})
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", RuntimeWarning)
                app = FortyTwoTuiApp(factory, None, editor_integration_service=FakeService())
                async with app.run_test(size=(140, 50)) as pilot:
                    workspace = app.query_one(SettingsWorkspace)
                    workspace.editor_selection_changed(Mock())
                    workspace.editor_selection_changed(Mock())
                    await app._save_settings()
                    await pilot.pause()
                del workspace, app
                gc.collect()
            self.assertEqual(
                [str(item.message) for item in caught if "_load_editor_integration" in str(item.message)],
                [],
            )

    async def test_editor_card_shows_status_and_blocks_invalid_cli_path(self):
        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f"sqlite:///{directory}/settings.db")
            with factory() as session:
                save_settings(session, {"onboarding_completed": "true"})
            service = FakeService()
            app = FortyTwoTuiApp(factory, None, editor_integration_service=service)
            try:
                async with app.run_test(size=(140, 50)) as pilot:
                    await pilot.press("f5")
                    app.query_one(SettingsWorkspace).show_category(2)
                    await pilot.pause()
                    self.assertIn(
                        "Installed",
                        str(app.query_one("#editor-integration-status", Static).render()),
                    )
                    self.assertIn(
                        "verified",
                        str(app.query_one("#editor-integration-heartbeat", Static).render()).lower(),
                    )
                    app.query_one(SettingsWorkspace)._render_editor_status(replace(status(), editor="nvim"))
                    self.assertIn(
                        "dry run",
                        str(app.query_one("#editor-integration-heartbeat", Static).render()),
                    )
                    self.assertIn(
                        "unknown",
                        str(app.query_one("#editor-integration-last-event", Static).render()),
                    )

                    app.query_one("#editor-cli-path", Input).value = "relative/path"
                    await pilot.click("#save-settings")
                    self.assertIn(
                        "absolute",
                        str(app.query_one("#settings-status", Static).render()).lower(),
                    )

                    app.query_one("#editor-integration-install").press()
                    await pilot.pause()
                    self.assertEqual(service.installed, 1)
                    self.assertIn(
                        "failed",
                        str(app.query_one("#editor-integration-detail", Static).render()).lower(),
                    )
            finally:
                factory.kw["bind"].dispose()


if __name__ == "__main__":
    unittest.main()
