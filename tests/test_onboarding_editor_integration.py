"""Onboarding can install the selected editor integration or skip it."""
import tempfile
import unittest
from pathlib import Path

from ft_tui.db.database import make_session_factory
from ft_tui.features.editor_integrations.models import IntegrationResult, IntegrationStatus
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Button, Static


def status(state="not_installed", verification="unverified"):
    return IntegrationStatus(
        editor="vim",
        state=state,
        version="0.1.0",
        installed_version=None,
        path=None,
        cli_path=Path("/bin/42tui"),
        cli_ok=True,
        editor_found=True,
        last_event_at=None,
        verification=verification,
    )


class FakeService:
    def __init__(self, result):
        self.result = result
        self.installed = 0

    def status(self, editor):
        return status()

    def install(self, editor, force=False):
        self.installed += 1
        return self.result


class OnboardingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def app_with_pending_onboarding(self, service):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        factory = make_session_factory(f"sqlite:///{directory.name}/ui.db")
        self.addCleanup(lambda: factory.kw["bind"].dispose())
        app = FortyTwoTuiApp(factory, None, editor_integration_service=service)
        return app

    async def test_onboarding_offers_install_and_skip_without_blocking_finish(self):
        service = FakeService(IntegrationResult(False, False, "cli_missing", "", status()))
        app = await self.app_with_pending_onboarding(service)
        async with app.run_test(size=(140, 50)) as pilot:
            app.account_connected = True
            await pilot.pause()
            for step in (1, 2):
                app.screen.query_one("#onboarding-next", Button).press()
                await pilot.pause()
                self.assertEqual(app.screen.step, step)
            self.assertTrue(app.screen.query_one("#onboarding-install-integration", Button).display)
            app.screen.query_one("#onboarding-install-integration", Button).press()
            await pilot.pause()
            await app.workers.wait_for_complete()
            self.assertEqual(service.installed, 1)
            text = str(app.screen.query_one("#onboarding-integration-status", Static).render())
            self.assertIn("42TUI", text)
            app.screen.query_one("#onboarding-skip-integration", Button).press()
            await pilot.pause()
            self.assertTrue(app.screen.query_one("#onboarding-finish", Button).display)
            self.assertFalse(app.screen.query_one("#onboarding-editor-integration").display)


if __name__ == "__main__":
    unittest.main()
