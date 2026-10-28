"""Background update checks and offline release notes on the next startup."""
import asyncio
import time

from textual.containers import Vertical, VerticalScroll
from textual.widgets import Markdown, Static

from ft_tui.i18n import translate
from ft_tui.features.installation.adapters.runtime import CHECK_INTERVAL, release_notes, stable_version
from ..adapters.factory import resolve_installation_service
from ft_tui.ui.button import Button
from ft_tui.ui.modal import AppModal


class ChangelogScreen(AppModal):
    BINDINGS = [("escape", "close", "Close")]
    DEFAULT_CSS = """
    ChangelogScreen > Vertical { width: 80; max-width: 95%; height: 85%;
        border: round $accent; background: $surface; padding: 1 2; }
    ChangelogScreen VerticalScroll { height: 1fr; }
    ChangelogScreen Button { margin-top: 1; }
    """

    def __init__(self, previous, current, language="en"):
        super().__init__()
        self.previous, self.current, self.language = previous, current, language

    def compose(self):
        tr = lambda text: translate(text, self.language)
        with Vertical():
            yield Static(tr("What's new in 42TUI {version}").format(version=self.current))
            with VerticalScroll():
                yield Markdown(release_notes(self.previous, self.current) or
                               tr("Release notes are not available for this version."))
            yield Button(tr("Close"), id="close-changelog")

    def on_button_pressed(self, event):
        if event.button.id == "close-changelog":
            self.action_close()

    def action_close(self):
        self.dismiss(True)


class UpdateMixin:
    def automatic_updates_enabled(self):
        return resolve_installation_service(self).enabled()

    def _start_updates(self):
        service = self.update_service
        if service is None or not stable_version(service.current):
            return
        previous = resolve_installation_service(self).startup(service.current)
        if previous:
            self._show_changelog_when_ready(previous)
        self.set_interval(CHECK_INTERVAL, self._start_update_check)
        self._start_update_check()

    def _start_update_check(self, *, force=False):
        if (self.update_service is not None and stable_version(self.update_service.current)
                and self.automatic_updates_enabled()):
            self.run_worker(self._check_updates(force=force), group="release-check", exclusive=True)

    def _show_changelog_when_ready(self, previous):
        # Onboarding and account dialogs keep priority over release notes.
        if len(self.screen_stack) > 1:
            self.set_timer(0.5, lambda: self._show_changelog_when_ready(previous))
            return
        current = self.update_service.current

        def acknowledged(result):
            if result:
                resolve_installation_service(self).acknowledge(current)

        self.push_screen(ChangelogScreen(previous, current, self.language), acknowledged)

    async def _check_updates(self, *, force=False):
        now = time.time()
        policy = resolve_installation_service(self)
        if not self.automatic_updates_enabled() or not policy.begin_check(now, force=force):
            return
        try:
            available = await asyncio.to_thread(self.update_service.check)
        except Exception:
            # Update infrastructure must never prevent normal offline use.
            return
        if not self.automatic_updates_enabled() or not policy.newer(available, self.update_service.current):
            return
        if self.update_service.installation is not None:
            self.pending_update = available
            message = "42TUI {version} will install before your next launch."
        else:
            message = "42TUI {version} is available. Update your installation manually."
        self.notify(translate(message, self.language).format(version=available), timeout=10)
