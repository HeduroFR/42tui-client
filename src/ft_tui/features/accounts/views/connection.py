"""Modal flow for pairing or disconnecting this device from a 42 account."""

import asyncio
import logging
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.color import Color
from textual.widgets import Input
from ft_tui.ui.modal import AppModal
from ft_tui.ui.components import Button, Static
from ft_tui.ui.select import Select
from ft_tui.i18n import translate


logger = logging.getLogger(__name__)


class AccountConnectionScreen(AppModal[str | None]):
    """Run the shared browser pairing flow without blocking Textual's event loop."""

    CSS = """
    AccountConnectionScreen {  background: $background 70%; }
    #account-connection-dialog {
        width: 54; max-width: 94%; height: auto; max-height: 90%; padding: 1 2; overflow-y: auto;
        border: round $primary; background: $surface;
    }
    #account-connection-title { text-style: bold; }
    #account-connection-status { height: auto; min-height: 2; margin: 1 0; color: $text-muted; }
    #account-storage-label { color: $text-muted; margin-top: 1; }
    #account-storage { width: 100%; margin: 0 0 1 0; }
    #account-storage-help { height: auto; color: $text-muted; margin-bottom: 1; }
    #account-connection-actions { height: auto; }
    #account-connection-actions Button { width: 100%; margin-bottom: 1; }
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
        start_vault: bool = False,
        required: bool = False,
    ) -> None:
        super().__init__()
        self.oauth_client = oauth_client
        self.connected_login = connected_login
        self.connected = connected
        self.start_pairing = start_pairing
        self.start_vault = start_vault
        self.required = required
        self.poll_timer = None
        self.polling = False
        self.poll_count = 0
        self._active_handle = ""
        self.poll_in_flight = False
        self._authorization_url = ""
        self._previous_store = None
        self._previous_credentials = None
        self._session_paired = False
        self._starting_pairing = False
        self._vault_busy = False
        self._vault_existed = False

    def compose(self) -> ComposeResult:
        with Vertical(id="account-connection-dialog"):
            yield Static("Connect your 42 account", id="account-connection-title")
            initial = (
                f"Connected as {self.connected_login}. This device has its own session."
                if self.connected_login
                else "Connect securely in your browser. 42TUI will never ask for your password or OAuth code."
            )
            yield Static(initial, id="account-connection-status")
            if not self.connected and hasattr(self.oauth_client, "store"):
                from ft_tui.infrastructure.security.session_vault import LockedSessionStore
                language = getattr(self.app, "language", "en")
                locked = isinstance(self.oauth_client.store, LockedSessionStore)
                options = [] if locked else [("OS keyring", "keyring")]
                options += [("This session only", "session"), ("Remember with a passphrase", "vault")]
                yield Static("Session storage", id="account-storage-label")
                yield Select(
                    [(translate(label, language), value) for label, value in options],
                    value="vault" if locked else "keyring",
                    allow_blank=False, id="account-storage",
                )
                yield Static("", id="account-storage-help")
            with Vertical(id="account-manual-link"):
                yield Static("If no browser opens, copy this link into an available browser (another device works too).")
                yield Static("", id="account-authorization-url", markup=False)
                yield Button("Copy login link", id="account-copy-link")
            with Vertical(id="account-connection-actions"):
                yield Button("Connect 42 account" if not self.connected and hasattr(self.oauth_client, "store") else "Connect / reconnect", variant="primary", id="account-connect")
                yield Button("Disconnect this device", id="account-disconnect", disabled=not self.connected)
                if not self.connected and hasattr(self.oauth_client, "store"):
                    if isinstance(self.oauth_client.store, LockedSessionStore):
                        yield Button("Discard saved session", variant="danger", id="account-vault-reset")
                elif self.connected:
                    from ft_tui.infrastructure.security.keychain import CredentialStore
                    if isinstance(getattr(self.oauth_client, "store", None), CredentialStore):
                        yield Button("Move keyring session to passphrase", id="account-vault-migrate")
                yield Button("Quit TUI" if self.required else "Cancel", id="account-connection-cancel")

    def on_mount(self) -> None:
        self.query_one("#account-manual-link").display = False
        self.query_one("#account-disconnect").display = self.connected
        if self.query("#account-storage"):
            storage = self.query_one("#account-storage", Select)
            self._update_storage_help(storage.value)
            self.watch(storage, "expanded", self._storage_expanded)
        # Widgets are composed after the app's language-change broadcast. Apply
        # the selected locale once this modal enters the screen tree.
        for widget in self.query("*"):
            apply_language = getattr(widget, "apply_language", None)
            if callable(apply_language):
                apply_language()
        if self.start_pairing:
            from ft_tui.infrastructure.security.session_vault import LockedSessionStore
            if isinstance(getattr(self.oauth_client, "store", None), LockedSessionStore):
                self.call_after_refresh(self._prompt_vault)
            else:
                self.call_after_refresh(self._start_pairing)
        elif self.start_vault:
            self.call_after_refresh(self._prompt_vault)

    async def on_unmount(self) -> None:
        await self._restore_previous_store()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "account-storage":
            self._update_storage_help(event.value)

    def _storage_expanded(self, expanded: bool) -> None:
        for button in self.query("#account-connection-actions Button"):
            if button.id != "account-connection-cancel":
                button.styles.visibility = "hidden" if expanded else "visible"

    def _update_storage_help(self, value: object) -> None:
        messages = {
            "keyring": "Save your session in the system keyring.",
            "session": "Connect again when you restart 42TUI.",
            "vault": "Unlock your saved session with a passphrase.",
        }
        self.query_one("#account-storage-help", Static).update(messages.get(value, ""))

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "account-copy-link":
            if self._authorization_url:
                self.app.copy_to_clipboard(self._authorization_url)
        elif event.button.id == "account-connection-cancel":
            self._stop_polling()
            await self._restore_previous_store()
            if self.required:
                self.app.exit()
            else:
                self.dismiss(None)
        elif event.button.id == "account-connect":
            selection = self.query_one("#account-storage", Select).value if self.query("#account-storage") else "keyring"
            if selection == "vault":
                self._prompt_vault()
            elif selection == "session":
                if self.polling or self.poll_in_flight or self._starting_pairing or self._vault_busy:
                    return
                from ft_tui.infrastructure.security.keychain import SessionCredentialStore
                await self._select_store(SessionCredentialStore())
                await self._start_pairing()
            else:
                await self._start_pairing()
        elif event.button.id == "account-disconnect":
            await self._disconnect()
        elif event.button.id == "account-vault-reset":
            if not self.polling and not self._vault_busy and not self._starting_pairing:
                self._vault_busy = True
                self.app.push_screen(VaultResetScreen(), self._confirm_vault_reset)
        elif event.button.id == "account-vault-migrate":
            if not self._vault_busy:
                from ft_tui.infrastructure.security.session_vault import session_vault_path
                path = session_vault_path()
                if path.exists() or path.is_symlink():
                    self.query_one("#account-connection-status", Static).update("A saved session already exists; it will not be overwritten.")
                else:
                    self._vault_busy = True
                    self.app.push_screen(VaultPassphraseScreen(False), self._confirm_vault_migration)

    def _confirm_vault_reset(self, confirm: bool | None) -> None:
        if confirm and self.is_mounted:
            self.query_one("#account-connection-cancel", Button).disabled = True
            self.run_worker(self._discard_vault(), group="discard-session-vault", exclusive=True)
        else:
            self._vault_busy = False

    def _confirm_vault_migration(self, passphrase: str | None) -> None:
        if passphrase is None or not self.is_mounted:
            self._vault_busy = False
            return
        self.query_one("#account-connection-cancel", Button).disabled = True
        self.run_worker(self._migrate_vault(passphrase), group="migrate-session-vault", exclusive=True)

    async def _migrate_vault(self, passphrase: str) -> None:
        from ft_tui.infrastructure.security.session_vault import SessionVault, session_vault_path

        try:
            def migrate():
                with self.oauth_client._credential_lock():
                    original = self.oauth_client.store
                    credentials = original.load()
                    if not credentials:
                        raise ValueError('No stored credentials')
                    vault = SessionVault.create(session_vault_path(), passphrase)
                    vault.save(credentials)
                    if vault.load() != credentials:
                        raise ValueError('Vault verification failed')
                    original.delete()
                    self.oauth_client.store = vault
                    self.oauth_client._credentials = None
            await asyncio.to_thread(migrate)
        except Exception:
            if self.is_mounted:
                self.query_one("#account-connection-status", Static).update("Migration could not be completed. Check both the keyring and saved session before retrying.")
        else:
            if self.is_mounted:
                self.query_one("#account-connection-status", Static).update("Your session is now protected by your passphrase.")
        finally:
            self._vault_busy = False
            if self.is_mounted:
                self.query_one("#account-connection-cancel", Button).disabled = False

    async def _discard_vault(self) -> None:
        from ft_tui.infrastructure.security.keychain import CredentialStore
        from ft_tui.infrastructure.security.session_vault import discard_locked_vault, session_vault_path

        try:
            def discard():
                with self.oauth_client._credential_lock():
                    discard_locked_vault(session_vault_path())
                    self.oauth_client.store = CredentialStore()
                    self.oauth_client._credentials = None
            await asyncio.to_thread(discard)
        except Exception:
            self._vault_busy = False
            if self.is_mounted:
                self.query_one("#account-connection-cancel", Button).disabled = False
                self.query_one("#account-connection-status", Static).update("Could not discard the saved session.")
            return
        self._vault_busy = False
        if self.is_mounted:
            self.query_one("#account-connection-cancel", Button).disabled = False
            self.query_one("#account-vault-reset").display = False
            self.query_one("#account-connection-status", Static).update("The local saved session was discarded. The old server session was not revoked.")

    def _prompt_vault(self) -> None:
        if self.polling or self.poll_in_flight or self._starting_pairing or self._vault_busy:
            return
        from ft_tui.infrastructure.security.session_vault import session_vault_path

        path = session_vault_path()
        self._vault_busy = True
        self._vault_existed = path.exists() or path.is_symlink()
        self.app.push_screen(VaultPassphraseScreen(self._vault_existed), self._vault_passphrase)

    def _vault_passphrase(self, value: str | None) -> None:
        if value is None or not self.is_mounted:
            self._vault_busy = False
            return
        self.run_worker(self._open_vault(value, existing=self._vault_existed), group="open-session-vault", exclusive=True)

    async def _open_vault(self, passphrase: str, *, existing: bool | None = None) -> None:
        from ft_tui.infrastructure.security.session_vault import SessionVault, session_vault_path

        path = session_vault_path()
        if existing is None:
            existing = path.exists() or path.is_symlink()
        self.query_one("#account-connection-cancel", Button).disabled = True
        try:
            def open_vault():
                with self.oauth_client._credential_lock():
                    vault = SessionVault.unlock(path, passphrase) if existing else SessionVault.create(path, passphrase)
                    return vault, vault.load() if existing else None
            if hasattr(self.oauth_client, '_credential_lock'):
                vault, credentials = await asyncio.to_thread(open_vault)
            else:
                vault = await asyncio.to_thread(SessionVault.unlock if existing else SessionVault.create, path, passphrase)
                credentials = await asyncio.to_thread(vault.load) if existing else None
        except Exception:
            self._vault_busy = False
            if self.is_mounted:
                self.query_one("#account-connection-cancel", Button).disabled = False
                self.query_one("#account-connection-status", Static).update("Could not open the saved session. Check your passphrase and try again.")
            return
        self._vault_busy = False
        if not self.is_mounted:
            return
        self.query_one("#account-connection-cancel", Button).disabled = False
        await self._select_store(vault)
        if credentials and all(isinstance(credentials.get(key), str) and credentials[key] for key in ("access_token", "refresh_token", "expires_at", "private_key_pem")):
            self._session_paired = True
            self.dismiss("connected")
        elif credentials is None or (not credentials.get("access_token") and not credentials.get("refresh_token")):
            await self._start_pairing()
        else:
            await self._restore_previous_store()
            self.query_one("#account-connection-status", Static).update("The saved session is incomplete. It has not been changed.")

    async def _start_pairing(self) -> None:
        if self._starting_pairing or self.poll_in_flight or self._vault_busy:
            return
        from ft_tui.infrastructure.security.session_vault import LockedSessionStore
        if isinstance(getattr(self.oauth_client, "store", None), LockedSessionStore):
            self._prompt_vault()
            return
        self._starting_pairing = True
        self._stop_polling()
        self.query_one("#account-connect", Button).disabled = True
        self.query_one("#account-disconnect", Button).disabled = True
        self.query_one("#account-connection-cancel", Button).disabled = True
        self.query_one("#account-connection-status", Static).update("Opening the 42 authorization page…")
        try:
            # Resolve generated/overridden colors on the UI thread before I/O.
            variables = self.app.get_css_variables()
            theme = {key: Color.parse(variables[key]).hex6 for key in ("background", "surface", "foreground", "primary", "success")}
            pairing = await asyncio.to_thread(self.oauth_client.create_pairing, theme=theme)
        except Exception as error:
            self._starting_pairing = False
            logger.warning("OAuth pairing start failed (%s)", type(error).__name__)
            if not self.is_mounted:
                return
            self.query_one("#account-connection-status", Static).update(self._safe_error(error))
            self.query_one("#account-connect", Button).disabled = False
            self.query_one("#account-disconnect", Button).disabled = not self.connected
            self.query_one("#account-connection-cancel", Button).disabled = False
            return
        self._starting_pairing = False
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
            self._session_paired = True
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

    async def _select_store(self, store) -> None:
        replace = getattr(self.oauth_client, "replace_credential_store", None)
        if callable(replace):
            previous = await asyncio.to_thread(replace, store)
        else:
            previous = self.oauth_client.store, self.oauth_client._credentials
            self.oauth_client.store, self.oauth_client._credentials = store, None
        if self._previous_store is None:
            self._previous_store, self._previous_credentials = previous

    async def _restore_previous_store(self) -> None:
        if self._previous_store is not None and not self._session_paired:
            replace = getattr(self.oauth_client, "replace_credential_store", None)
            if callable(replace):
                await asyncio.to_thread(replace, self._previous_store)
            else:
                self.oauth_client.store = self._previous_store
                self.oauth_client._credentials = self._previous_credentials
            self._previous_store = None

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
            return "Could not securely access session credentials. Your saved data remains unchanged."
        from ft_tui.api.oauth_client import OAuthClientError

        if isinstance(error, OAuthClientError):
            return "Could not complete 42 account connection. Check your connection and try again."
        return "Could not reach the 42 account service. Your local projects are still available."


class VaultResetScreen(AppModal[bool]):
    CSS = """
    #vault-reset-dialog { width: 68; height: auto; max-height: 90%; overflow-y: auto;
        padding: 1 2; border: round $warning; background: $surface; }
    #vault-reset-dialog Static { height: auto; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="vault-reset-dialog"):
            yield Static("Discard the saved session on this device? This does not revoke the server session or delete projects.")
            yield Button("Discard saved session", variant="danger", id="vault-reset-confirm")
            yield Button("Cancel", id="vault-reset-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id in {"vault-reset-confirm", "vault-reset-cancel"}:
            self.dismiss(event.button.id == "vault-reset-confirm")

    def on_mount(self) -> None:
        for widget in self.query("*"):
            apply_language = getattr(widget, "apply_language", None)
            if callable(apply_language):
                apply_language()


class VaultPassphraseScreen(AppModal[str | None]):
    """Ask for a separate passphrase without storing it in preferences."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    CSS = """
    #vault-dialog { width: 70; height: auto; max-height: 90%; overflow-y: auto;
        padding: 1 2; border: round $primary; background: $surface; }
    #vault-dialog Static { height: auto; }
    """

    def __init__(self, existing: bool) -> None:
        super().__init__()
        self.existing = existing

    def compose(self) -> ComposeResult:
        with Vertical(id="vault-dialog"):
            yield Static("Unlock your saved session" if self.existing else "Choose a separate 42TUI passphrase")
            yield Static("A copied vault can be attacked offline. A forgotten passphrase cannot be recovered.")
            yield Input(password=True, placeholder="Passphrase", id="vault-passphrase")
            if not self.existing:
                yield Input(password=True, placeholder="Confirm passphrase", id="vault-confirm")
            yield Static("", id="vault-error")
            yield Button("Continue", variant="primary", id="vault-continue")
            yield Button("Cancel", id="vault-cancel")

    def on_mount(self) -> None:
        for widget in self.query("*"):
            apply_language = getattr(widget, "apply_language", None)
            if callable(apply_language):
                apply_language()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "vault-cancel":
            self.dismiss(None)
            return
        if event.button.id != "vault-continue":
            return
        field = self.query_one("#vault-passphrase", Input)
        value = field.value
        if not value or (not self.existing and (len(value) < 12 or value != self.query_one("#vault-confirm", Input).value)):
            self.query_one("#vault-error", Static).update("Use matching passphrases of at least 12 characters.")
            return
        field.value = ""
        if not self.existing:
            self.query_one("#vault-confirm", Input).value = ""
        self.dismiss(value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not self.existing and event.input.id == "vault-passphrase":
            self.query_one("#vault-confirm", Input).focus()
        else:
            self.query_one("#vault-continue", Button).press()

    def action_cancel(self) -> None:
        self.dismiss(None)


class SessionExpiredScreen(AppModal[bool]):
    """Let the user reconnect or quit after session expiry."""

    CSS = """
    SessionExpiredScreen {  background: $background 70%; }
    #session-expired-dialog {
        width: 64; max-width: 94%; height: auto; max-height: 90%; padding: 1 2; overflow-y: auto;
        border: round $warning; background: $surface;
    }
    #session-expired-message { height: auto; margin-bottom: 1; }
    #session-expired-actions { height: auto; align-horizontal: center; }
    #session-expired-actions Button { width: 100%; max-width: 42; margin-bottom: 1; }
    """
    BINDINGS = [("escape", "quit_tui", "Quit TUI")]

    def compose(self) -> ComposeResult:
        with Vertical(id="session-expired-dialog"):
            yield Static("Your session has expired. Reconnect your 42 account.", id="session-expired-message")
            with Vertical(id="session-expired-actions"):
                yield Button("Reconnect", variant="primary", id="session-reconnect")
                yield Button("Quit TUI", id="session-quit")

    def on_mount(self) -> None:
        for widget in self.query("*"):
            apply_language = getattr(widget, "apply_language", None)
            if callable(apply_language):
                apply_language()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "session-reconnect")

    def action_quit_tui(self) -> None:
        self.dismiss(False)
