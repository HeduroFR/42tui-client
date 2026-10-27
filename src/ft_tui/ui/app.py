"""Application composition root and cross-screen event routing."""

import logging
from datetime import datetime
from dataclasses import replace
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker
from textual.app import App
from textual.binding import Binding
from textual.timer import Timer
from textual.widgets import Input, ListView, Static, TabbedContent, TabPane

from ft_tui.ui.select import Select
from ft_tui.ui.button import Button
from ft_tui.api.client_interface import CursusSnapshot, ProjectProvider
from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.api.oauth_client import OAuthClient
from ft_tui.db.models import Project
from ft_tui.i18n import detect_language, translate, translate_renderable
from ft_tui.features.projects.adapters.tester_catalog import load_catalog
from ft_tui.features.projects.adapters.tester_docker import TesterDocker
from ft_tui.ui.components import (
    DEFAULT_SUBJECT_CHECK_INTERVAL,
    SUPPORTED_LANGUAGES,
    SUBJECT_CHECK_INTERVALS,
    ConfirmDeleteNoteScreen,
    DashboardNoteEntry,
    ProjectEntry,
)
from ft_tui.ui.commands import FortyTwoTuiCommandProvider
from ft_tui.features.dashboard.views.home import DashboardMixin
from ft_tui.features.worklog.views.notes import DevLogMixin
from ft_tui.features.friends.views.workspace import FriendsMixin
from ft_tui.ui.layout import MainLayoutMixin
from ft_tui.ui.onboarding import OnboardingScreen
from ft_tui.features.catalog.views.browser import ProjectBrowserMixin
from ft_tui.features.catalog.views.controller import ProjectCatalogControllerMixin
from ft_tui.features.projects.views.details import ProjectDetailsMixin
from ft_tui.features.projects.views.registration import ProjectRegistrationMixin
from ft_tui.features.projects.views.navigation import ProjectNavigationMixin
from ft_tui.features.projects.views.setup import ProjectSetupMixin
from ft_tui.ui.shortcuts import ShortcutsPanel
from ft_tui.ui.styles import APP_CSS
from ft_tui.features.settings.views.workspace import SettingsMixin
from ft_tui.features.installation.views.updates import UpdateMixin
from ft_tui.ui.terminal_capabilities import CAPABILITIES, IMAGE_MODES, ICON_MODES, valid_mode


from ft_tui.app.bootstrap import (build_account_service, build_catalog_service,
                                    build_profile_service, build_dashboard_service,
                                    build_worklog_service, build_project_service,
                                    build_friends_service, build_clubs_service, build_social_service, build_cluster_service,
                                    build_corrections_service, build_settings_service, build_installation_service, build_registration_service, build_student_profile_service,
                                    build_subject_service, build_activity_service, build_account_shell_service, build_startup_service)
from ft_tui.features.dashboard.state import DashboardState
from ft_tui.features.worklog.state import WorklogState
from ft_tui.app.state import StateField
from ft_tui.features.projects.state import ProjectState
from ft_tui.features.settings.state import SettingsState
from ft_tui.features.accounts.state import AccountState
from ft_tui.features.catalog.state import CatalogState

logger = logging.getLogger(__name__)




from ft_tui.features.accounts.views.controller import AccountControllerMixin, SessionExpired


class FortyTwoTuiApp(
    AccountControllerMixin,
    ProjectCatalogControllerMixin,
    MainLayoutMixin,
    DashboardMixin,
    ProjectBrowserMixin,
    ProjectDetailsMixin,
    ProjectRegistrationMixin,
    ProjectSetupMixin,
    ProjectNavigationMixin,
    DevLogMixin,
    FriendsMixin,
    SettingsMixin,
    UpdateMixin,
    App[None],
):
    """Offline-first 42TUI application shell."""

    projects = StateField('project_state', 'projects')
    project_curriculum = StateField('project_state', 'project_curriculum')
    _evidence_owner_unverified = StateField('project_state', '_evidence_owner_unverified')
    _editing_project_key = StateField('project_state', '_editing_project_key')
    project_last_activity = StateField('project_state', 'project_last_activity')
    active_project_id = StateField('project_state', 'active_project_id')
    selected_project_key = StateField('project_state', 'selected_project_key')
    projects_root = StateField('settings_state', 'projects_root')
    favorite_editor = StateField('settings_state', 'favorite_editor')
    favorite_subject_viewer = StateField('settings_state', 'favorite_subject_viewer')
    language = StateField('settings_state', 'language')
    club_notification_sound = StateField('settings_state', 'club_notification_sound')
    image_mode = StateField('settings_state', 'image_mode')
    icon_mode = StateField('settings_state', 'icon_mode')
    username_gradient = StateField('settings_state', 'username_gradient')
    subject_check_interval_seconds = StateField('settings_state', 'subject_check_interval_seconds')

    selected_note_id = StateField('worklog_state','selected_note_id')
    dev_log_previewing = StateField('worklog_state','previewing')
    account_id = StateField('account_state', 'account_id')
    account_login = StateField('account_state', 'login')
    account_profile = StateField('profile_state', 'profile')
    account_goals = StateField('profile_state', 'goals')
    goals_scope = StateField('profile_state', 'goals_scope')
    _goals_next_poll = StateField('profile_state', 'next_poll')
    dashboard_continue_key = StateField('dashboard_state', 'continue_key')
    dashboard_setup_key = StateField('dashboard_state', 'setup_key')
    dashboard_recent_notes_signature = StateField('dashboard_state', 'recent_notes_signature')
    account_campuses = StateField('account_state', 'campuses')
    account_connected = StateField('account_state', 'connected')
    account_generation = StateField('account_state', 'generation')
    catalog_status = StateField('catalog_state', 'status')
    _catalog_next = StateField('catalog_state', 'next_pages')
    _branch_cursor = StateField('catalog_state', 'branch_cursor')
    _branch_items = StateField('catalog_state', 'branch_items')
    _catalog_generation = StateField('catalog_state', 'generation')
    _catalog_snapshot = StateField('catalog_state', 'snapshot')
    _branch_snapshot = StateField('catalog_state', 'branch_snapshot')
    _catalog_request = StateField('catalog_state', 'request')

    ALLOW_SELECT = False  # Prevent container double-clicks from highlighting the UI.
    CSS = APP_CSS
    TITLE = "42 TUI"
    SUB_TITLE = "Local projects"
    COMMANDS = App.COMMANDS | {FortyTwoTuiCommandProvider}

    BINDINGS = [
        Binding("q,Q,shift+q", "quit", "Quit"),
        Binding("question_mark", "help", "Shortcuts"),
        Binding("escape", "close_shortcuts", show=False),
        Binding("ctrl+shift+d", "toggle_clubs_dnd", "DND", priority=True),
        Binding("ctrl+shift+n", "focus_clubs_invitation", "Invitation", priority=True),
        Binding("f1", "help", show=False),
        Binding("f2", "show_projects", show=False),
        Binding("f3", "show_notes", show=False),
        Binding("f4", "git_sync", show=False),
        Binding("f5", "show_settings", show=False),
        Binding("/", "focus_project_search", show=False),
        Binding("e,E,shift+e", "configure_project", show=False),
        Binding("d", "project_technical_details", show=False),
        Binding("t", "project_testers", show=False),
        Binding("o,O,shift+o", "open_project_editor", show=False),
        Binding("j,J,shift+j", "move_project_down", show=False),
        Binding("k,K,shift+k", "move_project_up", show=False),
        Binding("h,H,shift+h", "tab_left", show=False),
        Binding("l,L,shift+l", "tab_right", show=False),
        Binding("alt+left", "tab_left", show=False, priority=True),
        Binding("alt+right", "tab_right", show=False, priority=True),
        Binding("home", "first_project", show=False, priority=True),
        Binding("end", "last_project", show=False, priority=True),
        Binding("ctrl+d", "move_project_page_down", show=False, priority=True),
        Binding("ctrl+u", "move_project_page_up", show=False, priority=True),
    ]

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        provider: ProjectProvider | None,
        oauth_client: OAuthClient | None = None,
        update_service=None,
        account_service=None,
        catalog_service=None,
        profile_service=None,
        dashboard_service=None,
        worklog_service=None,
        project_service=None,
        friends_service=None,
        clubs_service=None,
        social_service=None,
        cluster_service=None,
        corrections_service=None,
        settings_service=None,
        installation_service=None,
        registration_service=None,
        subject_service=None,
        activity_service=None,
        student_profile_service=None,
        account_shell_service=None,
        startup_service=None,
    ) -> None:
        super().__init__()
        self.project_state = ProjectState()
        self.settings_state = SettingsState()
        self.account_state = AccountState()
        self.catalog_state = CatalogState()
        self.account_service = build_account_service() if account_service is None else account_service
        self.catalog_service = build_catalog_service(session_factory) if catalog_service is None else catalog_service
        self.profile_service = build_profile_service(session_factory, self.catalog_service) if profile_service is None else profile_service
        self.profile_state = self.profile_service.state
        self.dashboard_service = build_dashboard_service(session_factory) if dashboard_service is None else dashboard_service
        self.dashboard_state = DashboardState()
        self.worklog_state = WorklogState()
        self.worklog_service = build_worklog_service(session_factory) if worklog_service is None else worklog_service
        self.project_service = build_project_service(session_factory) if project_service is None else project_service
        self.friends_service = build_friends_service(session_factory) if friends_service is None else friends_service
        self.clubs_service = build_clubs_service() if clubs_service is None else clubs_service
        self.social_service = build_social_service(session_factory) if social_service is None else social_service
        self.cluster_service = build_cluster_service(session_factory,self._configured_cursus_id) if cluster_service is None else cluster_service
        self.corrections_service = build_corrections_service() if corrections_service is None else corrections_service
        self.settings_service = build_settings_service(session_factory) if settings_service is None else settings_service
        self.installation_service = build_installation_service(session_factory) if installation_service is None else installation_service
        self.registration_service = build_registration_service() if registration_service is None else registration_service
        self.subject_service = build_subject_service(session_factory) if subject_service is None else subject_service
        self.activity_service = build_activity_service(session_factory,self._configured_cursus_id) if activity_service is None else activity_service
        self.student_profile_service = build_student_profile_service() if student_profile_service is None else student_profile_service
        self.account_shell_service = build_account_shell_service(session_factory) if account_shell_service is None else account_shell_service
        self.startup_service = build_startup_service(session_factory) if startup_service is None else startup_service
        self.session_factory = session_factory
        self.update_service = update_service
        self.pending_update = None
        self.provider = provider
        self.tester_catalog = load_catalog()
        self.tester_docker = TesterDocker()
        self.oauth_client = oauth_client or getattr(provider, "api", None)
        self._session_expiry_prompted = False
        self._session_expiry_prompt_pending = False
        if isinstance(self.oauth_client, OAuthClient):
            self.oauth_client.on_session_expired = lambda: self.post_message(SessionExpired())
        self.account_goals: dict = {}
        self.goals_scope = None
        self._goals_next_poll = 0.0
        self.account_profile: dict = {}
        self.account_login: str | None = None
        self.account_id: str | None = None
        self.account_campuses = []
        self.campus_directory = []
        self.catalog_status = "Saved catalog"
        self._catalog_next = []
        self._branch_cursor = None
        self._branch_items = []
        self._catalog_generation = 0
        self.account_connected = isinstance(provider, HttpProjectProvider)
        self.account_generation = 0
        initial = self.startup_service.initial_preferences(detect_language())
        self.campus_directory = initial['campus_directory']
        self.language = initial['language']
        self.club_notification_sound = initial['club_notification_sound']
        self.image_mode = valid_mode(initial['image_mode'], IMAGE_MODES)
        self.icon_mode = valid_mode(initial['icon_mode'], ICON_MODES)
        from ft_tui.ui.username import USERNAME_GRADIENTS
        gradient = initial['username_gradient']
        self.username_gradient = gradient if gradient in USERNAME_GRADIENTS else 'off'
        self.terminal_capabilities = CAPABILITIES
        if self.account_connected:
            self.account_profile = self.profile_service.cached_profile(self.oauth_client)
            self.account_id = self.account_profile.get('account_id')
            self.account_login = self.account_profile.get('login')
            self.account_campuses = self.account_profile.get('campuses', [])
        else:
            self.account_id = initial['offline_account_id']
            self.account_campuses = initial['offline_account_campuses']
        if self.language not in SUPPORTED_LANGUAGES:
            self.language = "en"
        self.projects: dict[str, Project] = {}
        self.project_curriculum: dict = {}
        self._evidence_owner_unverified = False
        self.projects_root = str(Path.home() / "42")
        self._editing_project_key: str | None = None
        self.project_last_activity: dict[int, datetime] = {}
        self.active_project_id: int | None = None
        self.selected_project_key: str | None = None
        self.favorite_editor = "nvim"
        self.favorite_subject_viewer = "system"
        self.activity_refresh_timer: Timer | None = None
        self.manual_timer_refresh_timer: Timer | None = None
        self.subject_check_timer: Timer | None = None
        self.subject_check_interval_seconds = DEFAULT_SUBJECT_CHECK_INTERVAL
        self.settings_status_timer: Timer | None = None
        self.selected_note_id: int | None = None
        self.dev_log_previewing = False
        self._new_note_after_project_load: str | None = None
        self._open_note_after_project_load: tuple[str, int] | None = None
        self.dashboard_continue_key: str | None = None
        self.dashboard_setup_key: str | None = None
        self.dashboard_recent_notes_signature: tuple[tuple[object, ...], ...] = ()
        self.pending_dashboard_project_key: str | None = None
        self.shortcuts_visible = False

    async def on_mount(self) -> None:
        project_list = self.query_one("#project-list-view", ListView)
        preferences = self.startup_service.mount_preferences(
            self.language, self.projects_root, self.favorite_editor, self.theme,
            DEFAULT_SUBJECT_CHECK_INTERVAL)
        onboarding_pending = preferences['onboarding_pending']
        self.language = preferences['language']
        self.projects_root = preferences['projects_root']
        self.favorite_editor = preferences['favorite_editor']
        self.favorite_subject_viewer = preferences['favorite_subject_viewer']
        subject_interval = preferences['subject_interval']
        favorite_theme = preferences['favorite_theme']
        cached_cursuses = self.startup_service.cached_cursuses()
        if cached_cursuses:
            self._select_default_cursus_if_unset(cached_cursuses)
        configured_cursus_id = self._configured_cursus_id()
        self.account_goals = self.profile_service.cached_goals(self.account_id, configured_cursus_id)
        if self.account_goals:
            self.goals_scope = (self.account_generation, self.account_id, configured_cursus_id)
        catalog_scope = self._catalog_scope()
        projects, self.project_curriculum = self.startup_service.catalog(
            configured_cursus_id, self.account_id, catalog_scope.campus_id if catalog_scope else None,
            allow_cached_owner=not self.account_connected)
        if self.account_connected and not self.account_id:
            projects = []
        self.project_curriculum = self._resolved_curriculum(self.project_curriculum)
        self.projects.update((project.ui_key, project) for project in projects)
        self._load_project_activity()
        self._load_curriculum_setting_widgets()
        if self.language not in SUPPORTED_LANGUAGES:
            self.language = "en"
        if subject_interval not in SUBJECT_CHECK_INTERVALS:
            subject_interval = str(DEFAULT_SUBJECT_CHECK_INTERVAL)
        if self.favorite_subject_viewer not in {"system", "tdf"}:
            self.favorite_subject_viewer = "system"
        self.subject_check_interval_seconds = int(subject_interval)
        self.set_cursus_choices(
            [
                CursusSnapshot(id=cursus.id, name=cursus.name, begin_at=cursus.begin_at, end_at=cursus.end_at)
                for cursus in cached_cursuses
            ],
            available=bool(cached_cursuses),
        )
        track=self.project_curriculum.get('selected_track',{}).get('track')
        if catalog_scope and track:
            self._set_branch_options(self.startup_service.branches(
                catalog_scope.cursus_id,catalog_scope.campus_id,track))
        ordered_projects = self._sorted_projects(self.projects.values())
        self._load_project_browser_preferences()
        visible_projects = await self._refresh_project_list()

        self._update_account_connection_widgets()
        self.query_one("#projects-root", Input).value = self.projects_root
        if self.favorite_editor not in {"nvim", "vim", "vscode", "zed"}:
            self.favorite_editor = "nvim"
        self.query_one("#favorite-editor", Select).value = self.favorite_editor
        self.query_one("#subject-viewer", Select).value = self.favorite_subject_viewer
        self.query_one("#subject-check-interval", Select).value = subject_interval
        if favorite_theme in self.available_themes:
            self.theme = favorite_theme
        else:
            favorite_theme = self.theme
        self.query_one("#favorite-theme", Select).value = favorite_theme
        self.query_one("#interface-language", Select).value = self.language
        self._apply_language()
        self._refresh_terminal_preview()
        self._configure_markdown_editor()

        project_select = self.query_one("#dev-log-project", Select)
        with self.prevent(Select.Changed):
            project_select.set_options((project.name, project.ui_key) for project in ordered_projects)
            if ordered_projects:
                initial_note_project = self.selected_project_key or ordered_projects[0].ui_key
                project_select.value = initial_note_project
        if ordered_projects:
            await self._load_dev_log_notes(initial_note_project)
        await self._load_friends()

        if visible_projects:
            project_list.focus()
        self._update_black_hole()
        await self._refresh_dashboard()
        self._update_empty_cursus_state()
        self.goals_refresh_timer = self.set_interval(30, self._start_goals_refresh)
        self._start_goals_refresh()
        self.activity_refresh_timer = self.set_interval(15, self._refresh_activity_order)
        self.manual_timer_refresh_timer = self.set_interval(1, self._refresh_manual_timer_display)
        self.subject_check_timer = self.set_interval(
            min(30, self.subject_check_interval_seconds),
            self._start_due_subject_checks,
        )
        self._start_due_subject_checks()
        if onboarding_pending:
            self.push_screen(
                OnboardingScreen(
                    projects_root=self.projects_root,
                    favorite_editor=self.favorite_editor,
                    favorite_theme=favorite_theme,
                    language=self.language,
                    themes=sorted(self.available_themes),
                    account_connected=self.account_connected,
                    account_login=self.account_login,
                ),
                self._finish_onboarding,
            )
        self.set_interval(60, self._start_session_check)
        self.call_after_refresh(self._start_updates)
        if self.account_connected:
            self.run_worker(
                self._sync_online_provider(self.provider, self.account_generation),
                group="oauth-startup-sync",
                exclusive=True,
            )

    async def _finish_onboarding(self, values: dict[str, str] | None) -> None:
        """Persist first-run choices, or remember that the user skipped setup."""
        self.startup_service.finish_onboarding(self.language, values)
        if values is None:
            return
        self.projects_root = values["projects_root"]
        self.favorite_editor = values["favorite_editor"]
        self.language = values["language"]
        self.theme = values["favorite_theme"]
        self.query_one("#projects-root", Input).value = self.projects_root
        self.query_one("#favorite-editor", Select).value = self.favorite_editor
        self.query_one("#favorite-theme", Select).value = values["favorite_theme"]
        self.query_one("#interface-language", Select).value = self.language
        self._apply_language()
        self._update_editor_button()
        await self._refresh_dashboard()














    async def _reload_project_catalog(self) -> None:
        scope = self._catalog_scope()
        projects, self.project_curriculum = self.startup_service.catalog(
            self._configured_cursus_id(), self.account_id, scope.campus_id if scope else None,
            allow_cached_owner=not self.account_connected and not self._evidence_owner_unverified)
        self._load_project_activity()
        self.project_curriculum = self._resolved_curriculum(self.project_curriculum)
        if self.account_connected:
            registration_ids = self.project_curriculum.get('registration', {}).get('project_ids', [])
            projects = [project for project in projects if (
                project.official_project_id is None or scope and (
                    project.catalog_data or project.progress_data
                    or project.official_project_id in registration_ids
                )
            )]
        track=self.project_curriculum.get('selected_track',{}).get('track')
        if scope and track:
            self._set_branch_options(self.startup_service.branches(scope.cursus_id,scope.campus_id,track))
        else:
            self._set_branch_options([])
        self.projects = {project.ui_key: project for project in projects}
        ordered = self._sorted_projects(projects)
        self._load_project_browser_preferences()
        project_select = self.query_one("#dev-log-project", Select)
        with self.prevent(Select.Changed):
            project_select.set_options((project.name, project.ui_key) for project in ordered)
        await self._refresh_project_list(self.selected_project_key)
        await self._load_dev_log_notes(self.selected_project_key or "")
        await self._refresh_dashboard()
        self._update_empty_cursus_state()
        await self._load_friends()

    def _update_empty_cursus_state(self) -> None:
        if self.projects:
            self.query_one("#new-project-note", Button).disabled = not bool(
                self.selected_project_key in self.projects
            )
            return
        self._clear_project_details()
        needs_connection = not self.account_connected and self._has_saved_cursus_selection()
        if needs_connection:
            message = "Connect your 42 account to load projects for this cursus."
            self.query_one("#dashboard-continue-activity", Static).update(
                message
            )
            self.query_one("#project-empty", Static).update(message)
        else:
            self.query_one("#project-empty", Static).update("No matching projects.")
        self.query_one("#project-empty", Static).styles.display = "block"
        self.query_one("#details-content", Static).update("Select a project from the list.")
        self.query_one("#project-subject-status", Static).update("SUBJECT · no project selected")
        for selector in ("#open-project-editor", "#project-timer-toggle", "#open-subject", "#new-project-note"):
            self.query_one(selector, Button).disabled = True

    def _has_saved_cursus_selection(self) -> bool:
        return self.startup_service.has_saved_cursus_selection()

    def _apply_language(self) -> None:
        """Refresh every locale-aware widget after loading or saving preferences."""
        for widget in self.query("*"):
            apply_language = getattr(widget, "apply_language", None)
            if apply_language is not None:
                apply_language()
        for project_entry in self.query(ProjectEntry):
            project_entry.refresh_language()
        for note_entry in self.query(DashboardNoteEntry):
            note_entry.refresh_language()
        for key, bindings in self._bindings.key_to_bindings.items():
            self._bindings.key_to_bindings[key] = [
                replace(
                    binding,
                    description=translate(
                        {"quit": "Quit", "help": "Shortcuts"}[binding.action],
                        self.language,
                    ),
                )
                if binding.action in {"quit", "help"}
                else binding
                for binding in bindings
            ]
        self.screen.refresh_bindings()
        labels = {
            "dashboard": "Dashboard",
            "projects-tab": "Projects",
            "friends": "Friends",
            "correction-slots": "Correction Slots",
            "clubs": "Clubs",
            "dev-log": "Dev Log / Notes",
            "cluster-map": "Cluster Map",
            "settings": "Settings",
        }
        source_subtitle = "Connected 42 account" if self.account_connected else "Local projects"
        self.sub_title = translate(source_subtitle, self.language)
        tabs = self.query_one(TabbedContent).query_one("Tabs")
        for pane in self.query(TabPane):
            if pane.id in labels:
                title = (pane.localized_title(self.language) if hasattr(pane, 'localized_title')
                         else translate(labels[pane.id], self.language))
                pane._title = pane.render_str(title)
                tabs.get_content_tab(pane.id).label = title
        from ft_tui.ui.navigation import MainTabbedContent
        self.call_after_refresh(self.query_one(MainTabbedContent).align_settings)
        selected_project = self.projects.get(self.selected_project_key or "")
        if selected_project is not None:
            # The project details are a composed Rich block, so refresh it as a
            # whole when the locale changes instead of translating project data.
            self._show_project(selected_project)
        self._update_account_connection_widgets()

    def notify(self, message, *args, **kwargs):
        """Localize app notifications using the same catalogs as screen labels."""
        return super().notify(translate_renderable(message, self.language), *args, **kwargs)

    def action_toggle_clubs_dnd(self) -> None:
        from ft_tui.features.clubs.views.workspace import ClubsWorkspace
        self.query_one(ClubsWorkspace).toggle_dnd()

    def action_focus_clubs_invitation(self) -> None:
        from ft_tui.features.clubs.views.workspace import ClubsInvitations
        if len(self.screen_stack) == 1:
            host = self.query_one(ClubsInvitations)
            if host.display:
                next((b for b in host.query(Button) if b.display and not b.disabled), host).focus()

    def action_help(self) -> None:
        self.shortcuts_visible = not self.shortcuts_visible
        self.query_one("#shortcuts-panel", ShortcutsPanel).styles.display = (
            "block" if self.shortcuts_visible else "none"
        )

    def action_close_shortcuts(self) -> None:
        if not self.shortcuts_visible:
            return
        self.shortcuts_visible = False
        self.query_one("#shortcuts-panel", ShortcutsPanel).styles.display = "none"

    def action_show_projects(self) -> None:
        self._activate_main_tab("projects-tab")

    def action_show_dashboard(self) -> None:
        self._activate_main_tab("dashboard")

    def action_show_notes(self) -> None:
        self._activate_main_tab("dev-log")

    def action_show_settings(self) -> None:
        self._activate_main_tab("settings")
        if len(self.screen_stack) == 1:
            self._refresh_username_preview()
            self.query_one("#settings-categories", ListView).focus()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-refresh-catalog":
            self.run_worker(self._refresh_settings_catalog(), group="catalog", exclusive=True)
            return
        if event.button.id == "catalog-more":
            self.run_worker(self._refresh_catalog_context(self.provider, self.account_generation, more=True), group="catalog", exclusive=True)
            return
        if event.button.id == "catalog-more-branches":
            self.run_worker(self._load_more_branches(), group="branches", exclusive=True)
            return
        # Textual keeps mouse-activated buttons focused after the click. Clear
        # that focus for every action so the button label does not stay highlighted.
        if not any(node.id == "settings-workspace" for node in event.button.ancestors):
            self.set_focus(None)
        if await self._handle_registration_button(event.button.id):
            return
        if await self._handle_friend_button(event.button.id):
            return
        if event.button.id == "show-project-activity":
            self.action_project_activity()
            return
        if event.button.id == "show-project-testers":
            self.action_project_testers()
            return
        if event.button.id == "show-project-details":
            self.action_project_technical_details()
            return
        if event.button.id == "configure-project":
            self.action_configure_project()
            return
        if event.button.id == "open-subject":
            self._open_selected_subject_pdf()
            return
        if event.button.id == "project-timer-toggle":
            project = self.projects.get(self.selected_project_key or "")
            if project is None or project.id is None:
                self.notify("Select a project first.", severity="warning")
                return
            outcome = self.worklog_service.toggle_timer(project.id)
            if outcome.action == 'stopped':
                message = f"Stopped timer for {project.name}."
            else:
                message = (f"Started timer for {project.name}; previous project timer stopped."
                           if outcome.switched else f"Started timer for {project.name}.")
            self._load_project_activity()
            self._refresh_manual_timer_display()
            await self._refresh_dashboard()
            self.notify(message)
            return
        if event.button.id == "dashboard-open-editor":
            slug = self.dashboard_continue_key
            if slug is None:
                return
            self.selected_project_key = slug
            pointer = event.button.styles.pointer
            event.button.styles.pointer = "default"
            self.screen.update_pointer_shape()
            try:
                self._open_selected_project_in_editor()
            finally:
                event.button.styles.pointer = pointer
                self.screen.update_pointer_shape()
            return
        if event.button.id == "dashboard-cluster-map":
            self.query_one(TabbedContent).active = "cluster-map"
            return
        if event.button.id == "dashboard-view-project":
            if self.dashboard_continue_key:
                await self._show_dashboard_project(self.dashboard_continue_key)
            return
        if event.button.id == "dashboard-setup-next":
            if self.dashboard_setup_key:
                self._open_project_settings_for_key(self.dashboard_setup_key)
            return
        if event.button.id == "dev-log-new":
            self._begin_new_dev_note()
            return
        if event.button.id == "new-project-note":
            project_key = self.selected_project_key
            if project_key is None:
                self.notify("Select a project first.", severity="warning")
                return
            self.query_one(TabbedContent).active = "dev-log"
            project_select = self.query_one("#dev-log-project", Select)
            if project_select.value == project_key:
                await self._load_dev_log_notes(project_key)
                self._begin_new_dev_note()
            else:
                self._new_note_after_project_load = project_key
                project_select.value = project_key
            return
        if event.button.id == "dev-log-preview-toggle":
            self._set_dev_log_preview(not self.dev_log_previewing)
            return
        if event.button.id == "dev-log-save":
            await self._save_dev_note()
            return
        if event.button.id == "dev-log-delete":
            if self.selected_note_id is not None:
                self.push_screen(ConfirmDeleteNoteScreen(), self._finish_delete_dev_note)
            return
        if event.button.id == "settings-connect-account":
            self.open_account_connection("settings")
            return
        if event.button.id == "open-project-editor":
            self._open_selected_project_in_editor()
            return
        if event.button.id != "save-settings":
            return
        await self._save_settings_and_refresh_projects()

    async def _save_settings_and_refresh_projects(self) -> None:
        """Persist settings and refresh the selected cursus when it changes."""
        await self._save_settings()
        self._cancel_catalog_requests()
        self._load_curriculum_setting_widgets()
        if self.account_connected and self.provider is not None:
            await self._refresh_catalog_context(self.provider,self.account_generation)
        else:
            await self._reload_project_catalog()

    async def _handle_default_cursus_changed(self, value: object) -> None:
        """Persist a deliberate cursus selection and refresh only its project view."""
        if value in (None, Select.NULL):
            return
        selected_cursus_id = str(value)
        if not selected_cursus_id.isdecimal() or int(selected_cursus_id) <= 0:
            return
        previous_cursus_id = self.settings_service.get("default_cursus_id")
        if selected_cursus_id == previous_cursus_id:
            return
        self.settings_service.save_values({"default_cursus_id": selected_cursus_id, "default_cursus_source": "manual"})
        self._cancel_catalog_requests()
        self._load_curriculum_setting_widgets()
        if self.account_connected and self.provider is not None:
            await self._sync_online_provider(self.provider, self.account_generation)
        else:
            await self._reload_project_catalog()
