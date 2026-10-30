"""Account/session lifecycle orchestration without persistence ownership."""
import logging
from datetime import date
from textual.message import Message
from ft_tui.i18n import translate
from ft_tui.ui.select import Select
from ft_tui.api.client_interface import CursusSnapshot, ProjectProvider
from ft_tui.features.accounts.views.connection import AccountConnectionScreen, SessionExpiredScreen
from ft_tui.features.accounts.adapters.shell import connected_provider, supports_session_check

logger = logging.getLogger(__name__)

class SessionExpired(Message):
    """Authentication failed in an OAuth worker thread."""

class AccountControllerMixin:
    def _account_shell(self):
        service = getattr(self, 'account_shell_service', None)
        if service is None:
            from ft_tui.app.bootstrap import build_account_shell_service
            service = build_account_shell_service(self.session_factory)
        return service

    def _start_session_check(self) -> None:
        if self.account_connected and supports_session_check(self.oauth_client):
            self.run_worker(self._check_session(), group="oauth-session-check", exclusive=True)

    async def _check_session(self) -> None:
        try:
            client, generation, account = self.oauth_client, self.account_generation, self.account_id
            def current():
                return client is self.oauth_client and generation == self.account_generation and account == self.account_id
            profile = await self._account_shell().read(client.request, current, "GET", "/v1/me", timeout=10.0)
            if current() and isinstance(profile, dict) and profile.get('account_id') == account:
                self.profile_service.persist_profile(client, profile)
        except Exception:
            # Authentication failures post SessionExpired; temporary outages do
            # not invalidate credentials or interrupt local work.
            pass

    def on_session_expired(self, message: SessionExpired) -> None:
        if self._session_expiry_prompted or not getattr(self.oauth_client, "session_expired", False):
            return
        self._session_expiry_prompted = True
        self._cancel_catalog_requests()
        self.account_generation += 1
        self.account_connected = False
        self.provider = None
        self.call_later(self._load_friends)
        self._update_account_connection_widgets()
        if any(isinstance(screen, AccountConnectionScreen) for screen in self.screen_stack):
            self._session_expiry_prompt_pending = True
        else:
            self.push_screen(SessionExpiredScreen(), self._finish_session_expiry_prompt)

    def _read_authorization_lost(self, scope):
        from ft_tui.features.friends.views.workspace import FriendsWorkspace
        from ft_tui.features.projects.views.activity import ProjectActivityScreen
        for screen in self.screen_stack:
            for workspace in screen.query(FriendsWorkspace):
                workspace._authorization_lost()
                workspace._refresh_view()
            if isinstance(screen, ProjectActivityScreen) and screen._read_scope == scope:
                screen._invalidate('Session expired. Close this screen and reconnect your account.')

    def _finish_session_expiry_prompt(self, reconnect: bool) -> None:
        if reconnect:
            self.open_account_connection(start_pairing=True)
        else:
            self.exit()

    def open_account_connection(self, source: str = "settings", *, start_pairing: bool = False, start_vault: bool = False) -> None:
        """Open the shared pairing/disconnect flow from onboarding or Settings."""
        if self.oauth_client is None:
            self.notify("42 account connection is not configured.", severity="warning")
            return
        self.push_screen(
            AccountConnectionScreen(
                self.oauth_client,
                connected_login=self.account_login,
                connected=self.account_connected,
                start_pairing=start_pairing,
                start_vault=start_vault,
            ),
            lambda result: self._finish_account_connection(result, source),
        )

    def _finish_account_connection(self, result: str | None, source: str) -> None:
        if result in {"connected", "disconnected"}:
            self._cancel_catalog_requests()
        if result == "connected":
            self._session_expiry_prompt_pending = False
            self._session_expiry_prompted = False
            self.account_generation += 1
            self.provider = connected_provider(self.oauth_client)
            self.account_connected = True
            self.account_goals = {}
            self.goals_scope = None
            self._goals_next_poll = 0.0
            self.account_profile = {}
            self.account_login = None
            self.account_id = None
            self.account_campuses = []
            self.notify("42 account connected. Refreshing projects…")
            self.run_worker(
                self._sync_online_provider(self.provider, self.account_generation),
                group="oauth-startup-sync",
                exclusive=True,
            )
        elif result == "disconnected":
            self.account_generation += 1
            self.provider = None
            self.account_connected = False
            self.account_goals = {}
            self.goals_scope = None
            self._goals_next_poll = 0.0
            self.account_profile = {}
            self.account_login = None
            self.account_id = None
            self.account_campuses = []
            self.run_worker(self._refresh_dashboard(), group="dashboard-refresh", exclusive=True)
            self.notify("This device is disconnected. Your local projects remain available.")
        if result in {"connected", "disconnected"}:
            self.project_curriculum = {}
            self._evidence_owner_unverified = True
            for project in self.projects.values(): project._progress_data = {}
            self.call_later(self._reload_project_catalog)
            self.call_later(self._load_friends)
        self._update_account_connection_widgets()

        if self._session_expiry_prompt_pending:
            self._session_expiry_prompt_pending = False
            self.push_screen(SessionExpiredScreen(), self._finish_session_expiry_prompt)

    def _select_default_cursus_if_unset(
        self, cursuses: list[CursusSnapshot], today: date | None = None
    ) -> int | None:
        """Choose a default and repair legacy automatic Piscine selections."""
        if self.is_mounted:
            self.set_cursus_choices(cursuses, available=True)
        selected_id, changed = AccountControllerMixin._account_shell(self).select_default(cursuses, today or date.today())
        if not changed:
            return selected_id
        if self.is_mounted:
            selector = self.query_one("#default-cursus", Select)
            with self.prevent(Select.Changed):
                selector.value = str(selected_id)
        return selected_id

    def _update_account_connection_widgets(self) -> None:
        if not self.is_mounted:
            return
        if self.account_connected and self.account_login:
            state = translate("Connected as {login}", self.language).format(login=self.account_login)
        elif self.account_connected:
            state = translate("Connected · profile unavailable", self.language)
        else:
            state = translate("Not connected · saved projects only", self.language)
        for selector in ("#account-connection-state", "#onboarding-account-state"):
            for widget in [widget for screen in self.screen_stack for widget in screen.query(selector)]:
                widget.update(state)
        connect_label = "Manage 42 account" if self.account_connected else "Connect 42 account"
        for selector in ("#settings-connect-account", "#onboarding-connect-account"):
            for button in [widget for screen in self.screen_stack for widget in screen.query(selector)]:
                button.set_source_label(connect_label)
        dashboard_state = (
            "CONNECTED ACCOUNT · LOCAL PROJECTS"
            if self.account_connected
            else "LOCAL WORKSPACE · OFFLINE MODE"
        )
        for widget in self.query("#dashboard-subtitle"):
            widget.update(translate(dashboard_state, self.language))
        provider_title = (
            "Connected 42 account"
            if self.account_connected
            else "42 account not connected"
        )
        for widget in self.query("#provider-title"):
            widget.update(translate(provider_title, self.language))
        provider_description = (
            "Your projects sync from the centralized 42 API. The local catalog stays available offline."
            if self.account_connected
            else "Your saved projects and activity stay on this device. Connect your 42 account to sync your real projects."
        )
        for widget in self.query("#provider-description"):
            widget.update(translate(provider_description, self.language))

    def _configured_cursus_id(self, session=None) -> int | None:
        return AccountControllerMixin._account_shell(self).configured_cursus(session)

    def _sync_online_data(self, provider: ProjectProvider):
        """Fetch source data without touching persistence before the account fence."""
        return self.account_service.read(provider)

    async def _sync_online_provider(self, provider: ProjectProvider, generation: int | None = None) -> None:
        if generation is None:
            generation = self.account_generation
        def current():
            return provider is self.provider and generation == self.account_generation
        result = await self._account_shell().read(self._sync_online_data, current, provider)
        if result is None:
            return
        profile, cursus_snapshots = result
        if provider is not self.provider or generation != self.account_generation:
            return
        if profile and isinstance(profile.get("login"), str):
            if self.account_id and self.account_id != profile.get('account_id'):
                self.account_goals = {}
                self.goals_scope = None
                self.project_curriculum = {}
            self.account_profile = profile
            self.account_login = profile["login"]
            self.account_id = profile.get("account_id")
            self.account_campuses = profile.get("campuses", [])
            self._start_goals_refresh()
            if self.account_id:
                self._account_shell().remember_account(self.account_id, self.account_campuses)
                self.profile_service.persist_profile(self.oauth_client, profile)
            self._load_curriculum_setting_widgets()
        if not await self._refresh_campus_directory(provider, generation):
            return
        self._update_account_connection_widgets()
        await self._load_friends()
        if cursus_snapshots is None:
            self.notify("Could not refresh 42 projects. Showing your saved local catalog.", severity="warning")
            await self._reload_project_catalog()
            return
        if provider is not self.provider or generation != self.account_generation:
            return
        selected_cursus_id = self._select_default_cursus_if_unset(cursus_snapshots)
        self._start_goals_refresh()
        self._account_shell().save_cursuses(cursus_snapshots)
        if selected_cursus_id is None:
            await self._reload_project_catalog()
            return
        self._load_curriculum_setting_widgets()
        # Resolve the cursus as well as the identity before displaying saved rows.
        await self._reload_project_catalog()
        await self._refresh_catalog_context(provider, generation)

    async def _refresh_campus_directory(self, provider: ProjectProvider, generation: int) -> bool:
        """Refresh public choices without mixing directory data into memberships."""
        list_campuses = getattr(provider, "list_campuses", None)
        if not callable(list_campuses):
            return provider is self.provider and generation == self.account_generation
        try:
            from ft_tui.features.accounts.campuses import campus_directory
            values = await self._account_shell().read(list_campuses,
                lambda: provider is self.provider and generation == self.account_generation)
            if values is None:
                return False
            campuses = campus_directory({"campuses": values})
        except Exception as error:
            logger.warning("Campus directory request failed (%s): %s", type(error).__name__, error)
            return provider is self.provider and generation == self.account_generation
        if provider is not self.provider or generation != self.account_generation:
            return False
        self._account_shell().save_campuses(campuses)
        self.campus_directory = campuses
        self._load_curriculum_setting_widgets()
        return True
