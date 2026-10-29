"""MainLayout UI composition and behavior."""

from ft_tui.ui.components import (
    Button,
    ComposeResult,
    Footer,
    Header,
    Horizontal,
    Input,
    ListView,
    Select,
    Static,
    TabPane,
    TextArea,
    Vertical,
)
from textual.containers import VerticalScroll
from ft_tui.features.corrections.views import CorrectionSlotsWorkspace
from ft_tui.features.friends.views.workspace import FriendsWorkspace
from ft_tui.features.cluster_map.views.cluster_map import ClusterMapWorkspace
from ft_tui.features.clubs.views.workspace import ClubsWorkspace, ClubsInvitations

from ft_tui.features.profiles.views.profile_sections import ProfilePortrait
from ft_tui.ui.shortcuts import ShortcutsPanel
from ft_tui.ui.navigation import MainTabbedContent
from ft_tui.features.projects.views.testers import ProjectTesters


class DashboardProfileCard(Vertical):
    """Keep the identity readable when dashboard columns become narrow."""

    def on_resize(self) -> None:
        self.set_class(self.size.width < 28, 'compact-profile')


class ProjectDetailsColumns(Horizontal):
    """Stack the workspace when the details pane becomes narrow."""

    def on_resize(self) -> None:
        self.set_class(self.size.width < 74, "stacked")


class MainLayoutMixin:
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with MainTabbedContent(initial="projects-tab", id="main-tabs"):
            with TabPane("Dashboard", icon="\uf015", id="dashboard"):
                with Vertical(id="dashboard-page"):
                    with Horizontal(id="dashboard-heading"):
                        yield Static("STUDENT OVERVIEW", id="dashboard-title")
                        yield Static("LOCAL WORKSPACE · OFFLINE MODE", id="dashboard-subtitle")
                    with Horizontal(id="dashboard-cards"):
                        with DashboardProfileCard(classes="dashboard-card", id="dashboard-profile-card"):
                            yield Static("STUDENT PROFILE", classes="dashboard-kicker")
                            with Vertical(id="dashboard-profile-data"):
                                with Horizontal(id="dashboard-identity"):
                                    portrait = ProfilePortrait(cover=True)
                                    portrait.id = 'dashboard-portrait'
                                    yield portrait
                                    with Vertical(id="dashboard-identity-text"):
                                        yield Static("Local profile", id="dashboard-login", markup=False, localize=False)
                                        yield Static("Unavailable", id="dashboard-workstation", markup=False, localize=False)
                                with Horizontal(id="dashboard-balances"):
                                    with Vertical(classes="dashboard-stat", id="dashboard-wallet-stat") as wallet:
                                        wallet.tooltip = 'Wallet'
                                        yield Static("Unavailable", id="dashboard-wallet", classes="dashboard-stat-value")
                                    with Vertical(classes="dashboard-stat", id="dashboard-correction-stat") as points:
                                        points.tooltip = 'Correction points'
                                        yield Static("Unavailable", id="dashboard-correction-points", classes="dashboard-stat-value")
                        with Vertical(classes="dashboard-card", id="dashboard-activity-card"):
                            yield Static(
                                "WEEKLY CODING",
                                id="dashboard-activity-title",
                                classes="dashboard-kicker",
                                localize=False,
                            )
                            yield Static("", id="dashboard-activity-heatmap")
                        with Vertical(classes="dashboard-card", id="dashboard-cluster-card"):
                            yield Static("CLUSTER RADAR", classes="dashboard-kicker")
                            yield Static("Unavailable", id="dashboard-cluster-status")
                            yield Button("Cluster Map", id="dashboard-cluster-map")
                        with Vertical(classes="dashboard-card", id="dashboard-blackhole-card"):
                            yield Static("CURSUS DEADLINES", classes="dashboard-kicker")
                            with Horizontal(id="dashboard-deadlines"):
                                yield Static("Milestone deadline\nUnavailable", id="dashboard-blackhole-days")
                                yield Static("Common Core ETA\nUnavailable", id="dashboard-blackhole-date")
                            yield Static("", id="dashboard-goals-status")
                            yield Static("", id="dashboard-deadline-summary")
                    with Horizontal(id="dashboard-action-cards"):
                        with Vertical(classes="dashboard-card", id="dashboard-continue-card"):
                            yield Static("CONTINUE WORKING", classes="dashboard-kicker")
                            yield Static("No project yet", id="dashboard-continue-name")
                            yield Static("", id="dashboard-continue-activity")
                            with Horizontal(id="dashboard-continue-time-row"):
                                yield Static("", id="dashboard-continue-meta")
                                yield Static("TIME TRACKED", id="dashboard-continue-time-label")
                            yield Static("", id="dashboard-continue-spacer")
                            with Horizontal(id="dashboard-continue-actions"):
                                yield Button(
                                    "Open in editor",
                                    id="dashboard-open-editor",
                                    variant="primary",
                                    disabled=True,
                                )
                                yield Button("View project", id="dashboard-view-project", disabled=True)
                        with Vertical(classes="dashboard-card", id="dashboard-notes-card"):
                            yield Static("RECENT NOTES", classes="dashboard-kicker")
                            yield ListView(id="dashboard-recent-notes", initial_index=None)
                            yield Static("No notes saved yet.", id="dashboard-notes-empty")
                        with Vertical(classes="dashboard-card", id="dashboard-needs-card"):
                            yield Static("NEEDS ATTENTION", classes="dashboard-kicker")
                            yield Static("All projects are set up", id="dashboard-needs-summary")
                            yield Static("", id="dashboard-needs-list")
                            yield Static("", id="dashboard-needs-spacer")
                            yield Button(
                                "Set up next project",
                                id="dashboard-setup-next",
                                variant="primary",
                                disabled=True,
                            )
                    with Vertical(id="dashboard-progress-card"):
                        with Horizontal(id="dashboard-progress-topline"):
                            yield Static("YOUR 42 JOURNEY", classes="dashboard-kicker")
                            yield Static("LOCAL CURSUS SNAPSHOT", id="dashboard-progress-context")
                        with Horizontal(id="dashboard-progress-heading"):
                            yield Static("0 / 0", id="dashboard-progress-value")
                            yield Static("projects completed · 0%", id="dashboard-progress-caption")
                        yield Static("", id="dashboard-progress-bar")
                        with Horizontal(id="dashboard-progress-legend"):
                            yield Static("● DONE 0", id="dashboard-progress-done", classes="dashboard-progress-stat")
                            yield Static(
                                "● ACTIVE 0",
                                id="dashboard-progress-active",
                                classes="dashboard-progress-stat",
                            )
                            yield Static(
                                "● AVAILABLE 0",
                                id="dashboard-progress-available",
                                classes="dashboard-progress-stat",
                            )
                            yield Static(
                                "● LOCKED 0",
                                id="dashboard-progress-locked",
                                classes="dashboard-progress-stat",
                            )
                        with Horizontal(id="dashboard-progress-next"):
                            yield Static("NEXT UP", id="dashboard-progress-next-label")
                            yield Static("No project in catalog", id="dashboard-progress-next-name")
            with TabPane("Projects", icon="\uf07b", id="projects-tab"):
                with Horizontal(id="workspace"):
                    with Vertical(id="project-list"):
                        with Horizontal(id="project-list-header"):
                            yield Static("PROJECTS", classes="panel-title")
                            yield Static("0", id="project-count")
                        with Horizontal(id="project-filters"):
                            yield Select(
                                [("My 42 projects", "relevant"), ("All projects", "all"),
                                 ("Registerable projects", "eligible"),
                                 ("Specializations", "specialization"), ("Active and local projects", "active")], value="relevant", allow_blank=False,
                                id="project-view",
                            )
                            yield Select([("All types", "all"), ("Exams", "exam"), ("Projects", "project"), ("Piscines", "piscine"), ("Rushes", "rush"), ("Big projects", "big_project")], value="all", allow_blank=False, id="project-kind")
                        yield Select([("All branches", "all")], value="all", allow_blank=False, id="project-branch")
                        yield Input(placeholder="Search projects…", id="project-search")
                        yield ListView(id="project-list-view", initial_index=None)
                        yield Static("No matching projects.", id="project-empty")
                        yield Button("Load more projects", id="catalog-more", disabled=True)
                        yield Button("Load more branches", id="catalog-more-branches", disabled=True)
                    with Vertical(id="project-details"):
                        yield Static("Select a project", id="project-heading", classes="panel-title")
                        yield Static("", id="project-summary")
                        with VerticalScroll(id="project-details-scroll"):
                            with ProjectDetailsColumns(id="project-details-columns"):
                                with Vertical(id="project-overview"):
                                    yield Static("Overview", classes="panel-title")
                                    yield Static("Select a project from the list.", id="details-content")
                                    with Vertical(id="project-registration"):
                                        yield Static("Registration", classes="panel-title")
                                        yield Static("Registration status unavailable", id="registration-relationship")
                                        yield Static("", id="registration-feedback")
                                        with Horizontal(id="registration-actions"):
                                            yield Button("Register", id="registration-action", disabled=True)
                                            yield Button("Refresh status", id="registration-refresh", disabled=True)
                                        yield Button("Open project on Intra", id="registration-intra-link")
                                    yield Button("Attempts & evaluations", id="show-project-activity", disabled=True)
                                    yield ProjectTesters(id="project-testers")
                                with Vertical(id="project-workspace"):
                                    yield Static("Workspace", classes="panel-title")
                                    with Horizontal(id="project-actions"):
                                        yield Button("Open editor", id="open-project-editor", variant="primary", disabled=True)
                                        yield Button("Open subject", id="open-subject", disabled=True)
                                    yield Button("Open folder", id="open-project-folder", tooltip="Open in file explorer", disabled=True)
                                    yield Static("", id="project-subject-status")
                                    yield Static("", id="project-workspace-status")
                                    with Horizontal(id="project-workspace-actions"):
                                        yield Button("Configure", id="configure-project")
                                        yield Button("Details", id="show-project-details")
                                    with Vertical(id="project-git-actions"):
                                        yield Button("Push dev", id="project-push-dev", disabled=True)
                                        yield Button("Push vog", id="project-push-vog", tooltip="Vogsphere → remote branch", disabled=True)
                                        yield Button("Push all", id="project-push-all", disabled=True)
                                    with Horizontal(id="project-timer-row"):
                                        with Vertical(id="project-timer-info"):
                                            yield Static("TOTAL TIME · 0h 00m", id="project-time-spent")
                                            yield Static("No manual timer running", id="project-timer-status")
                                        yield Button("Start timer", id="project-timer-toggle", disabled=True)
                            with Horizontal(id="project-notes-header"):
                                yield Static("Notes · Enter to open", id="notes-title")
                                yield Button("New note", icon="\uf067", icon_only=True, id="new-project-note")
                            yield ListView(id="project-notes-list", initial_index=None)
                            yield Static("No notes saved for this project.", id="project-notes-empty")
                        yield Static("o Editor · e Configure · d Details · t Testers · F4 Refresh Git", id="project-details-help")
            with TabPane("Correction Slots", icon="\uf073", id="correction-slots"):
                yield CorrectionSlotsWorkspace()
            with TabPane("Friends", icon="\uf0c0", id="friends"):
                yield FriendsWorkspace()
            with TabPane("Clubs", icon="\uf0f4", id="clubs"):
                yield ClubsWorkspace()
            with TabPane("Dev Log / Notes", icon="\uf044", id="dev-log"):
                with Horizontal(id="dev-log-workspace"):
                    with Vertical(id="dev-log-sidebar"):
                        yield Static("DEV LOG", classes="panel-title")
                        yield Select(
                            [], prompt="Select project", id="dev-log-project", localize_options=False
                        )
                        yield ListView(id="dev-log-note-list", initial_index=None)
                        yield Button("New note", id="dev-log-new")
                    with Vertical(id="dev-log-main"):
                        yield Input(placeholder="Note title", id="dev-log-title")
                        with Vertical(id="dev-log-content"):
                            yield TextArea("", language="markdown", id="dev-log-editor")
                            yield Static("", id="dev-log-preview")
                        with Horizontal(id="dev-log-actions"):
                            yield Static("Select a project to view its notes.", id="dev-log-status")
                            yield Button("Preview", id="dev-log-preview-toggle")
                            yield Button("Delete", icon="\uf1f8", icon_only=True, id="dev-log-delete", disabled=True)
                            yield Button("Save note", icon="\uf0c7", id="dev-log-save", variant="primary", disabled=True)
            with TabPane("Cluster Map", icon="\uf108", id="cluster-map"):
                yield ClusterMapWorkspace()
            with TabPane("Settings", icon="\uf013", id="settings"):
                yield from self.compose_settings()
        from ft_tui.features.social.views.events import PushEvents
        yield PushEvents()
        yield ClubsInvitations()
        yield ShortcutsPanel(id="shortcuts-panel")
        yield Footer()
