"""Backend availability and the offline warning shown by the app shell."""

import asyncio

from textual.containers import Vertical
from textual.widgets import Static, TabbedContent

from ft_tui.api.health import backend_available
from ft_tui.config.settings import oauth_api_url
from ft_tui.i18n import translate
from ft_tui.ui.button import Button
from ft_tui.ui.modal import AppModal

OFFLINE_TABS = ('cluster-map',)


class OfflineScreen(AppModal):
    BINDINGS = [("escape", "close", "Close")]
    DEFAULT_CSS = """
    OfflineScreen > Vertical { width: 72; max-width: 95%; height: auto;
        border: round $accent; background: $surface; padding: 1 2; }
    OfflineScreen Button { margin-top: 1; }
    """

    def __init__(self, language):
        super().__init__()
        self.language = language

    def compose(self):
        def tr(message):
            return translate(message, self.language)
        with Vertical():
            yield Static(tr("Backend unavailable"))
            yield Static(tr("The server cannot be reached. Check your connection or try again later."))
            yield Static(tr("Cluster Map, subscriptions, correction slots, registration "
                            "and social actions require the server."))
            yield Static(tr("Online features may be unavailable. Saved data and local tools remain available."))
            yield Button(tr("Close"), id="close-offline")

    def on_button_pressed(self, event):
        if event.button.id == "close-offline":
            self.action_close()

    def action_close(self):
        self.dismiss()


class OfflineMixin:
    def _start_backend_check(self):
        if self.oauth_client is None:
            return
        self.run_worker(self._check_backend(), group="backend-health", exclusive=True)

    async def _check_backend(self):
        client = self.oauth_client
        origin = getattr(client, "base_url", None) or oauth_api_url()
        available = await asyncio.to_thread(backend_available, origin)
        if client is not self.oauth_client:
            return
        self._set_backend_available(available)

    def _set_backend_available(self, available):
        previous = getattr(self, "backend_available", None)
        if previous is available:
            return
        self.backend_available = available
        main = self.screen_stack[0]
        tabs = main.query_one("#main-tabs", TabbedContent)
        if not available and tabs.active == "cluster-map":
            tabs.active = "projects-tab"
        for pane in OFFLINE_TABS:
            (tabs.enable_tab if available else tabs.disable_tab)(pane)
        button = main.query_one("#dashboard-cluster-map", Button)
        button.disabled = not available
        button.tooltip = None if available else translate("Backend unavailable", self.language)
        for selector, cursor in (('#catalog-more', '_catalog_next'),
                                 ('#catalog-more-branches', '_branch_cursor')):
            for control in main.query(selector):
                control.disabled = not available or not getattr(self, cursor, None)
        for control in main.query('#settings-refresh-catalog'):
            control.disabled = not available
        self.sub_title = self._normal_sub_title if available else translate("Backend unavailable", self.language)
        from ft_tui.features.corrections.views import CorrectionSlotsWorkspace
        from ft_tui.features.clubs.views.workspace import ClubsWorkspace
        from ft_tui.features.agenda.views import AgendaWorkspace
        from ft_tui.features.friends.views.workspace import FriendsWorkspace
        from ft_tui.features.social.views.inbox import SocialInbox
        for workspace in main.query(CorrectionSlotsWorkspace):
            workspace.controls()
        for workspace in main.query(ClubsWorkspace):
            workspace.update_controls()
        for workspace in main.query(FriendsWorkspace):
            workspace._render_status()
            workspace._render_details()
        for inbox in main.query(SocialInbox):
            inbox.update_controls()
        for invitation in main.query('#clubs-invitation-join'):
            invitation.disabled = not available
        for workspace in main.query(AgendaWorkspace):
            if not workspace.timeline:
                continue
            if not available:
                workspace.query_one('#agenda-subscribe', Button).disabled = True
            elif workspace.selected and workspace.selected['kind'] == 'event':
                workspace.run_worker(workspace.read_subscription(
                    workspace.selected['id'], workspace.subscription_epoch, workspace.identity()),
                    group='agenda-subscription-read', exclusive=True)
        registration = getattr(self, '_registration_state', None)
        if registration is not None:
            self._render_project_registration(registration)
        from ft_tui.features.accounts.views.connection import AccountConnectionScreen
        from ft_tui.features.projects.views.team import ProjectTeamScreen
        from ft_tui.ui.onboarding import OnboardingScreen
        for screen in self.screen_stack[1:]:
            if isinstance(screen, ProjectTeamScreen):
                screen._controls()
            for button in screen.query('#poke-send, #club-form-save, #slot-editor-publish, #slot-editor-delete'):
                button.disabled = not available or bool(getattr(screen, 'busy', False))
            if isinstance(screen, AccountConnectionScreen) and screen.required:
                screen.query_one('#account-connection-cancel', Button).set_source_label(
                    'Continue offline' if not available else 'Quit TUI')
                if not available:
                    screen.query_one('#account-connection-status', Static).update(
                        translate('The server cannot be reached. Check your connection or try again later.',
                                  self.language))
            elif isinstance(screen, OnboardingScreen):
                screen.query_one('#onboarding-account-state', Static).update(
                    screen._account_state() if available else translate(
                        'The server cannot be reached. Check your connection or try again later.', self.language))
                screen.query_one('#onboarding-account-help', Static).update(translate(
                    ('Required · connect in your browser. Your password and OAuth code stay with 42.' if available
                     else 'You can continue offline and connect your 42 account later in Settings.'), self.language))
        if not available and previous is None:
            self._show_offline_when_ready()
        elif available and previous is False and getattr(self, "account_connected", False):
            self._start_due_subject_checks()
            self.run_worker(
                self._sync_online_provider(self.provider, self.account_generation),
                group="oauth-startup-sync", exclusive=True,
            )

    def _show_offline_when_ready(self):
        if self.backend_available is not False:
            return
        if len(self.screen_stack) > 1:
            self.set_timer(0.5, self._show_offline_when_ready)
            return
        self.push_screen(OfflineScreen(self.language))
