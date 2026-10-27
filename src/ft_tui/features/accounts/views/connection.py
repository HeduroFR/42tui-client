"""Modal flow for pairing or disconnecting this device from a 42 account."""

import asyncio
import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from ft_tui.ui.modal import AppModal
from ft_tui.ui.components import Button, Static


logger = logging.getLogger(__name__)


class AccountConnectionScreen(AppModal[str | None]):
    """Run the shared browser pairing flow without blocking Textual's event loop."""

    CSS = """
    AccountConnectionScreen {  background: $background 70%; }
    #account-connection-dialog {
        width: 72; height: auto; max-height: 90%; padding: 1 2; overflow-y: auto;
        border: round $primary; background: $surface;
    }
    #account-connection-title { text-style: bold; }
    #account-connection-status { height: auto; min-height: 2; margin: 1 0; color: $text-muted; }
    #account-connection-actions { height: 3; align-vertical: middle; }
    #account-connect { margin-right: 1; }
    #account-manual-link { height: auto; margin-bottom: 1; }
    #account-authorization-url { height: auto; }
    """

    def __init__(
        self,
        oauth_client: Any,
        *,
        connected_login: str | None = None,
        connected: bool = False,
        start_pairing: bool = False,
    ) -> None:
        super().__init__()
        self.oauth_client = oauth_client
        self.connected_login = connected_login
        self.connected = connected
        self.start_pairing = start_pairing
        self.poll_timer = None
        self.polling = False
        self.poll_count = 0
        self._active_handle = ""
        self.poll_in_flight = False
        self._authorization_url = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="account-connection-dialog"):
            yield Static("Connect your 42 account", id="account-connection-title")
            initial = (
                f"Connected as {self.connected_login}. This device has its own session."
                if self.connected_login
                else "Connect securely in your browser. 42TUI will never ask for your password or OAuth code."
            )
            yield Static(initial, id="account-connection-status")
            with Vertical(id="account-manual-link"):
                yield Static("If no browser opens, copy this link into an available browser (another device works too).")
                yield Static("", id="account-authorization-url", markup=False)
                yield Button("Copy login link", id="account-copy-link")
            with Horizontal(id="account-connection-actions"):
                yield Button("Connect / reconnect", variant="primary", id="account-connect")
                yield Button("Disconnect this device", id="account-disconnect", disabled=not self.connected)
                yield Button("Cancel", id="account-connection-cancel")

    def on_mount(self) -> None:
        self.query_one("#account-manual-link").display = False
        # Widgets are composed after the app's language-change broadcast. Apply
        # the selected locale once this modal enters the screen tree.
        for widget in self.query("*"):
            apply_language = getattr(widget, "apply_language", None)
            if callable(apply_language):
                apply_language()
        if self.start_pairing:
            self.call_after_refresh(self._start_pairing)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "account-copy-link":
            if self._authorization_url:
                self.app.copy_to_clipboard(self._authorization_url)
        elif event.button.id == "account-connection-cancel":
            self._stop_polling()
            self.dismiss(None)
        elif event.button.id == "account-connect":
            await self._start_pairing()
        elif event.button.id == "account-disconnect":
            await self._disconnect()

    async def _start_pairing(self) -> None:
        self._stop_polling()
        self.query_one("#account-connect", Button).disabled = True
        self.query_one("#account-disconnect", Button).disabled = True
        self.query_one("#account-connection-cancel", Button).disabled = True
        self.query_one("#account-connection-status", Static).update("Opening the 42 authorization page…")
        try:
            pairing = await asyncio.to_thread(self.oauth_client.create_pairing)
        except Exception as error:
            logger.warning(
                "OAuth pairing start failed (%s): %s",
                type(error).__name__,
                error,
            )
            if not self.is_mounted:
                return
            self.query_one("#account-connection-status", Static).update(self._safe_error(error))
            self.query_one("#account-connect", Button).disabled = False
            self.query_one("#account-disconnect", Button).disabled = not self.connected
            self.query_one("#account-connection-cancel", Button).disabled = False
            return
        if not self.is_mounted:
            return
        self._active_handle = pairing.handle
        self._authorization_url = pairing.authorization_url
        self.query_one("#account-authorization-url", Static).update(self._authorization_url)
        self.query_one("#account-manual-link").display = True
        self.poll_count = 0
        self.polling = True
        self.query_one("#account-connection-cancel", Button).disabled = False
        self.query_one("#account-connection-status", Static).update(
            "Approve 42TUI in your browser. Waiting for authorization…"
            if getattr(pairing, "browser_opened", True)
            else "No browser opened. Open the login link below to continue."
        )
        self.poll_timer = self.set_interval(2, self._poll_pairing)

    async def _poll_pairing(self) -> None:
        if not self.polling or self.poll_in_flight:
            return
        self.poll_count += 1
        if self.poll_count > 300:
            self._stop_polling()
            self.query_one("#account-connection-status", Static).update("Pairing timed out. You can try again.")
            self.query_one("#account-connect", Button).disabled = False
            self.query_one("#account-disconnect", Button).disabled = not self.connected
            self.query_one("#account-connection-cancel", Button).disabled = False
            return
        try:
            # create_pairing stores only the opaque installation key in the OS
            # keychain; the one-time device credentials are stored there after approval.
            self.poll_in_flight = True
            self.query_one("#account-connection-cancel", Button).disabled = True
            result = await asyncio.to_thread(self.oauth_client.poll_pairing, self._pairing_handle())
        except Exception as error:
            logger.warning(
                "OAuth pairing poll failed (%s)",
                type(error).__name__,
            )
            if not self.is_mounted:
                return
            self._stop_polling()
            self.query_one("#account-connection-status", Static).update(self._safe_error(error))
            self.query_one("#account-connect", Button).disabled = False
            self.query_one("#account-disconnect", Button).disabled = not self.connected
            self.query_one("#account-connection-cancel", Button).disabled = False
            return
        finally:
            self.poll_in_flight = False
        if not self.is_mounted:
            return
        if result.status == "pending":
            self.query_one("#account-connection-cancel", Button).disabled = False
            return
        self._stop_polling()
        if result.status == "approved":
            self.query_one("#account-connection-status", Static).update(
                "Account connected. Updating your local project list…"
            )
            self.dismiss("connected")
        elif result.status in {"expired", "denied", "consumed"}:
            self.query_one("#account-connection-status", Static).update(
                "Pairing expired or was cancelled. You can start a new connection."
            )
            self.query_one("#account-connect", Button).disabled = False
            self.query_one("#account-disconnect", Button).disabled = not self.connected
            self.query_one("#account-connection-cancel", Button).disabled = False

    def _pairing_handle(self) -> str:
        return self._active_handle

    async def _disconnect(self) -> None:
        self.query_one("#account-disconnect", Button).disabled = True
        self.query_one("#account-connect", Button).disabled = True
        self.query_one("#account-connection-cancel", Button).disabled = True
        self.query_one("#account-connection-status", Static).update("Disconnecting this device…")
        try:
            await asyncio.to_thread(self.oauth_client.disconnect)
        except Exception as error:
            if not self.is_mounted:
                return
            self.query_one("#account-connection-status", Static).update(self._safe_error(error))
            self.query_one("#account-disconnect", Button).disabled = False
            self.query_one("#account-connect", Button).disabled = False
            self.query_one("#account-connection-cancel", Button).disabled = False
            return
        if self.is_mounted:
            self.dismiss("disconnected")

    def _stop_polling(self) -> None:
        self.polling = False
        self._authorization_url = ""
        self.query_one("#account-manual-link").display = False
        self.query_one("#account-authorization-url", Static).update("")
        if self.poll_timer is not None:
            self.poll_timer.stop()
            self.poll_timer = None

    @staticmethod
    def _safe_error(error: Exception) -> str:
        # OAuthClient errors intentionally contain generic descriptions. Never
        # display arbitrary response bodies which might contain sensitive data.
        from ft_tui.infrastructure.security.keychain import SecureStoreError

        if isinstance(error, SecureStoreError):
            return "The OS keychain is unavailable; credentials were not stored"
        from ft_tui.api.oauth_client import OAuthClientError

        if isinstance(error, OAuthClientError):
            return "Could not complete 42 account connection. Check your connection and try again."
        return "Could not reach the 42 account service. Your local projects are still available."


class SessionExpiredScreen(AppModal[bool]):
    """Let the user reconnect or continue working with saved projects."""

    CSS = """
    SessionExpiredScreen {  background: $background 70%; }
    #session-expired-dialog {
        width: 64; height: auto; padding: 2 3;
        border: round $warning; background: $surface;
    }
    #session-expired-message { height: auto; margin-bottom: 1; }
    #session-expired-actions { height: 3; }
    #session-reconnect { margin-right: 1; }
    """
    BINDINGS = [("escape", "later", "Later")]

    def compose(self) -> ComposeResult:
        with Vertical(id="session-expired-dialog"):
            yield Static("Your session has expired. Reconnect your 42 account?", id="session-expired-message")
            with Horizontal(id="session-expired-actions"):
                yield Button("Reconnect", variant="primary", id="session-reconnect")
                yield Button("Later", id="session-later")

    def on_mount(self) -> None:
        for widget in self.query("*"):
            apply_language = getattr(widget, "apply_language", None)
            if callable(apply_language):
                apply_language()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "session-reconnect")

    def action_later(self) -> None:
        self.dismiss(False)
