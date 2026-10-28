"""Dashboard UI composition and behavior."""

from textual.css.query import NoMatches

from rich.markup import escape
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from ft_tui.ui.username import username_text

from ft_tui.features.dashboard.service import DashboardService

from ft_tui.ui.components import (
    Button,
    DashboardNoteEntry,
    ListView,
    ProjectEntry,
    ProjectRankHeader,
    Static,
    date,
    datetime,
    timedelta,
    timezone,
    translate,
)


class DashboardMixin:
    def _refresh_dashboard_portrait(self):
        """Load the current account photo without blocking dashboard rendering."""
        import time
        from ft_tui.features.profiles.views.profile_sections import ProfilePortrait
        from ft_tui.ui.terminal_capabilities import image_mode
        portrait = self.query_one('#dashboard-portrait', ProfilePortrait)
        profile = self.account_profile if self.account_connected else {}
        login = self.account_login or profile.get('login') or ''
        account_id = self.account_id or profile.get('account_id')
        scope = (self.account_connected, self.account_generation, account_id, login, id(self.provider))
        if getattr(self, '_dashboard_portrait_scope', None) != scope:
            self._dashboard_portrait_scope = scope
            self._dashboard_portrait_retry = 0
            self._dashboard_portrait_loading = None
            portrait.image = None
            portrait.status = None
        portrait.initials = login[:2].upper() or '42'
        portrait.refresh()
        if (not self.account_connected or not account_id or not self.provider
                or image_mode(self) == 'off' or portrait.image is not None
                or self._dashboard_portrait_loading == scope
                or time.monotonic() < self._dashboard_portrait_retry):
            return
        if not callable(getattr(self.provider, 'get_student_portrait', None)):
            return
        self._dashboard_portrait_loading = scope
        self.run_worker(self._load_dashboard_portrait(scope, self.provider),
                        group='dashboard-portrait', exclusive=True)

    async def _load_dashboard_portrait(self, scope, provider):
        import asyncio
        import time
        from ft_tui.features.cluster_map.views.portrait import PortraitCache
        from ft_tui.features.profiles.views.profile_sections import ProfilePortrait

        def current():
            profile = self.account_profile if self.account_connected else {}
            return scope == (self.account_connected, self.account_generation,
                             self.account_id or profile.get('account_id'),
                             self.account_login or profile.get('login') or '', id(self.provider))

        retry = 60
        try:
            result = await asyncio.to_thread(provider.get_student_portrait, scope[2])
            if not current() or result.get('user_id') != scope[2]:
                return
            portrait = self.query_one('#dashboard-portrait', ProfilePortrait)
            portrait.status = result.get('status')
            if portrait.status == 'pending':
                retry = 5
                return
            url = result.get('image_url')
            if not url:
                return
            if not hasattr(self, '_dashboard_portrait_cache'):
                self._dashboard_portrait_cache = PortraitCache()

            async def loaded():
                return result

            image = await self._dashboard_portrait_cache.load(url, loaded)
            if current():
                portrait.image = image
                portrait.status = 'ready' if image is not None else 'unavailable'
        except Exception:
            # Portrait availability must never interrupt the local dashboard.
            if current():
                self.query_one('#dashboard-portrait', ProfilePortrait).status = 'unavailable'
        finally:
            if current():
                self._dashboard_portrait_loading = None
                self._dashboard_portrait_retry = time.monotonic() + retry

                def refresh():
                    if self.is_mounted and current():
                        self._refresh_dashboard_portrait()
                self.set_timer(retry, refresh)

    async def _refresh_dashboard(self) -> None:
        """Refresh project shortcuts, recent notes, local activity, and cursus progress."""
        if not self.is_running or not self.query("#dashboard-login"):
            return
        self.query_one("#dashboard-login", Static).update(
            username_text(self.account_login or ("Account connected" if self.account_connected else "Local profile"),
                          self.username_gradient)
        )
        profile = self.account_profile if self.account_connected else {}
        self._refresh_dashboard_portrait()
        model = self.dashboard_service.compose(
            projects=self.projects.values(), profile=profile, goals=self._current_goals(),
            curriculum=self.project_curriculum, activity=self.project_last_activity,
            active_project_id=self.active_project_id, selected_project_key=self.selected_project_key,
            now=datetime.now(timezone.utc),
        )
        self.dashboard_state.render_revision += 1
        revision = self.dashboard_state.render_revision

        self.query_one('#dashboard-wallet-stat').tooltip = translate('Wallet', self.language)
        self.query_one('#dashboard-correction-stat').tooltip = translate('Correction points', self.language)
        location = model.stats.location
        self.query_one('#dashboard-workstation', Static).update(Text(
            location.strip() if isinstance(location, str) and location.strip()
            else translate('Unavailable', self.language),
        ))
        self.query_one("#dashboard-cluster-status", Static).update(
            Panel(Align.center(Text(location, style="bold"), vertical="middle"),
                  height=5, border_style="bold cyan", padding=(1, 2))
            if isinstance(location, str) and location.strip() else "Unavailable"
        )
        for field, selector, suffix in (
            ("wallet", "#dashboard-wallet", " ₳"),
            ("correction_point", "#dashboard-correction-points", " 🪙"),
        ):
            value = model.stats.wallet if field == 'wallet' else model.stats.correction_points
            label = f"{value}{suffix}" if type(value) is int and value >= 0 else "Unavailable"
            self.query_one(selector, Static).update(label)
        continue_project = model.resume
        active_project = continue_project if model.active_now else None
        recent_project = continue_project if model.recent_activity else None
        activity_label = translate(model.activity_label, self.language)

        open_button = self.query_one("#dashboard-open-editor", Button)
        view_button = self.query_one("#dashboard-view-project", Button)
        editor_names = {
            "nvim": "Neovim",
            "vim": "Vim",
            "vscode": "VS Code",
            "zed": "Zed",
        }
        open_button.set_source_label(
            f"Open in {editor_names.get(self.favorite_editor, 'editor')}"
        )
        if continue_project is None:
            self.dashboard_continue_key = None
            self.query_one("#dashboard-continue-name", Static).update("No project yet")
            self.query_one("#dashboard-continue-activity", Static).update(
                translate("Set up a project to get started.", self.language)
            )
            self.query_one("#dashboard-continue-time-row").styles.display = "none"
            open_button.disabled = True
            view_button.disabled = True
        else:
            self.dashboard_continue_key = continue_project.ui_key
            self.query_one("#dashboard-continue-name", Static).update(continue_project.name)
            activity_color = "#72d6b0" if active_project is not None else (
                "#58c9c0" if recent_project is not None else "#e6b450"
            )
            self.query_one("#dashboard-continue-activity", Static).update(
                f"[{activity_color}]●[/] {activity_label}"
            )
            elapsed = model.resume_seconds
            hours, minutes = divmod(int(elapsed // 60), 60)
            self.query_one("#dashboard-continue-meta", Static).update(f"{hours}h {minutes:02d}m")
            self.query_one("#dashboard-continue-time-label", Static).update(
                translate("TIME TRACKED", self.language)
            )
            self.query_one("#dashboard-continue-time-row").styles.display = "block"
            open_button.disabled = not model.resume_has_folder
            view_button.disabled = False

        setup_candidates = model.setup_candidates
        setup_project = setup_candidates[0] if setup_candidates else None
        self.dashboard_setup_key = setup_project.ui_key if setup_project else None
        self.query_one("#dashboard-needs-summary", Static).update(
            f"{len(setup_candidates)} projects need a local folder"
            if setup_candidates
            else "All available projects are set up"
        )
        self.query_one("#dashboard-needs-list", Static).update(
            ", ".join(project.name for project in setup_candidates[:3])
            + (
                " " + translate(f"+{len(setup_candidates) - 3} more", self.language)
                if len(setup_candidates) > 3
                else ""
            )
        )
        setup_button = self.query_one("#dashboard-setup-next", Button)
        setup_button.disabled = setup_project is None
        setup_button.set_source_label(
            f"Set up {setup_project.name}" if setup_project else "Nothing to set up"
        )

        recent_notes = model.recent_notes
        note_signature = tuple(tuple(row) for row in recent_notes)
        notes_list = self.query_one("#dashboard-recent-notes", ListView)
        if note_signature != self.dashboard_recent_notes_signature:
            await notes_list.clear()
            if revision != self.dashboard_state.render_revision or not notes_list.is_mounted or not self.is_running:
                return
            if recent_notes:
                await notes_list.extend(
                    DashboardNoteEntry(note_id, slug, project_name, title, updated_at)
                    for note_id, slug, project_name, title, updated_at in recent_notes
                )
                if revision != self.dashboard_state.render_revision or not notes_list.is_mounted or not self.is_running:
                    return
                notes_list.styles.display = "block"
                self.query_one("#dashboard-notes-empty", Static).styles.display = "none"
            else:
                notes_list.styles.display = "none"
                self.query_one("#dashboard-notes-empty", Static).styles.display = "block"
            self.dashboard_recent_notes_signature = note_signature

        week_starts = model.week_starts
        day_seconds = model.day_seconds
        week_seconds = model.week_seconds
        current_seconds = week_seconds[week_starts[-1]]
        current_hours, current_minutes = divmod(int(current_seconds // 60), 60)
        language = self.language
        weekly_coding = translate("WEEKLY CODING", language)
        weekly_time = translate("{time} [dim]this week[/]", language).format(
            time=f"{current_hours}h {current_minutes:02d}m"
        )
        self.query_one("#dashboard-activity-title", Static).update(
            f"{weekly_coding} · {weekly_time}"
        )

        def activity_cell(seconds: float) -> str:
            if seconds <= 0:
                return "[#46505b]·[/]"
            if seconds < 15 * 60:
                return "[#65bfa8]░[/]"
            if seconds < 60 * 60:
                return "[#49c7ae]▒[/]"
            if seconds < 3 * 60 * 60:
                return "[#22cbb7]▓[/]"
            return "[bold #15d3c1]█[/]"

        day_labels = {
            "en": "M T W T F S S",
            "fr": "L M M J V S D",
            "es": "L M X J V S D",
        }.get(self.language, "M T W T F S S")
        month_labels = {
            "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
            "fr": ("jan", "fév", "mar", "avr", "mai", "jun", "jui", "aoû", "sep", "oct", "nov", "déc"),
            "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
        }.get(self.language, ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))
        # Keep every row the same width so centering the widget doesn't shift
        # the weekday legend away from its activity columns.
        heatmap_lines = [f"        {day_labels}         "]
        for week in week_starts:
            cells = " ".join(
                activity_cell(day_seconds[week + timedelta(days=day)])
                for day in range(7)
            )
            seconds = week_seconds[week]
            hours, minutes = divmod(int(seconds // 60), 60)
            duration = f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
            label = f"{week.day:02d} {month_labels[week.month - 1]}"
            heatmap_lines.append(f"{label:>6}  {cells} {duration:>8}")
        self.query_one("#dashboard-activity-heatmap", Static).update("\n".join(heatmap_lines))

        self._update_black_hole()

        journey = model.journey
        total, completed = journey.total, journey.completed
        percent = round(completed / total * 100) if total else 0
        self.query_one("#dashboard-progress-value", Static).update(f"{completed:02d} / {total:02d}")
        self.query_one("#dashboard-progress-caption", Static).update(
            f"projects completed · {percent}%"
        )
        self.query_one("#dashboard-progress-done", Static).update(f"[green]●[/] DONE {completed}")
        self.query_one("#dashboard-progress-active", Static).update(f"[#15d3c1]●[/] ACTIVE {journey.active}")
        self.query_one("#dashboard-progress-available", Static).update(
            f"[#e6b450]●[/] AVAILABLE {journey.available}"
        )
        self.query_one("#dashboard-progress-locked", Static).update(f"[#59636e]●[/] LOCKED {journey.locked}")
        bar_width = max(1, self.size.width - 16)
        segments = [
            (journey.completed, "green"),
            (journey.active, "#15d3c1"),
            (journey.available, "#e6b450"),
            (journey.locked, "#59636e"),
        ]
        remaining_width = bar_width
        bar_parts: list[str] = []
        for index, (count, color) in enumerate(segments):
            width = remaining_width if index == len(segments) - 1 else round(bar_width * count / total) if total else 0
            width = min(remaining_width, width)
            bar_parts.append(f"[{color}]{'█' * width}[/]")
            remaining_width -= width
        bar_line = "".join(bar_parts)
        self.query_one("#dashboard-progress-bar", Static).update(f"{bar_line}\n{bar_line}")
        self.query_one("#dashboard-progress-next-name", Static).update(journey.next_name)

    def _load_project_activity(self, session=None) -> None:
        activity = self.dashboard_service.activity(datetime.now(timezone.utc))
        self.project_last_activity = activity.latest
        self.active_project_id = activity.active_project_id

    def _sorted_projects(self, projects):
        return DashboardService.sorted_projects(projects, self.project_last_activity, self.active_project_id)

    async def _refresh_activity_order(self) -> None:
        """Refresh recency/active state without disturbing the current selection."""
        if not self.is_running:
            return
        try:
            project_list = self.query_one("#project-list-view", ListView)
        except NoMatches:
            return  # The root view may already have been removed during shutdown.
        highlighted = project_list.highlighted_child
        selected_key = highlighted.key if isinstance(highlighted, ProjectEntry) else None
        previous_active = self.active_project_id
        self._load_project_activity()
        await self._refresh_dashboard()
        if not self.is_running or not project_list.is_mounted:
            return

        # A project folder may be removed while 42TUI is running. Keep its
        # visible path status in sync with the filesystem as the dashboard refreshes.
        for entry in project_list.children:
            if (
                isinstance(entry, ProjectEntry)
                and entry.is_mounted
                and entry.key in self.projects
            ):
                entry.update_project(self.projects[entry.key])

        visible = self._visible_projects()
        groups = {}
        for project in visible:
            groups.setdefault(self._project_rank(project), []).append(project)
        for header in project_list.query(ProjectRankHeader):
            header.update_projects(groups.get(header.rank, []))
        current_order = [
            child.key for child in project_list.children if isinstance(child, ProjectEntry)
        ]
        next_order = [project.ui_key for project in self._expanded_projects(visible)]
        if current_order == next_order and previous_active == self.active_project_id:
            return

        await self._refresh_project_list(selected_key)

    def _current_goals(self) -> dict:
        scope = (self.account_generation, self.account_id, self.profile_service.cursus_id())
        return self.profile_service.current_goals(scope, connected=self.account_connected)

    def _start_goals_refresh(self) -> None:
        scope = (self.account_generation, self.account_id, self.profile_service.cursus_id())
        if self.profile_service.should_refresh(self.provider, scope, connected=self.account_connected):
            self.run_worker(self._refresh_goals(scope), group="dashboard-goals", exclusive=True)

    async def _refresh_goals(self, scope) -> None:
        provider = self.provider
        def current():
            return (provider is self.provider and
                    scope == (self.account_generation, self.account_id, self.profile_service.cursus_id()))
        if await self.profile_service.refresh_goals(provider, scope, current, client=self.oauth_client):
            await self._refresh_dashboard()

    def _update_black_hole(self) -> None:
        goals = self._current_goals()
        self._update_deadline_summary()
        milestone = self.query_one("#dashboard-blackhole-days", Static)
        common_core = self.query_one("#dashboard-blackhole-date", Static)
        status = self.query_one("#dashboard-goals-status", Static)
        milestone.remove_class("urgent", "approaching", "comfortable")
        milestone.tooltip = None
        common_core.tooltip = None
        common_core.display = True
        if goals.get("status") != "available":
            label = {"pending": "Loading…", "not_applicable": "Not applicable"}.get(goals.get("status"), "Unavailable")
            milestone.update(f"[dim]Milestone deadline[/]\n[bold]{label}[/]")
            common_core.update(f"[bold]Common Core ETA[/]\n{label}")
            renewal = goals.get("reason") in {"web_login_required", "web_login_incomplete", "web_login_form_unavailable"}
            status.update("Session renewal required" if renewal else "")
            status.display = renewal
            return
        if goals.get("cc_validated"):
            milestone.update("[dim]Common Core[/]\n[bold]Completed[/]")
            common_core.display = False
            common_core.update("")
        else:
            today = datetime.now(timezone.utc).date()

            def deadline(title, field, *, primary=False):
                raw = goals.get(field)
                if not raw:
                    return f"[dim]{title}[/]\nUnavailable"
                target = date.fromisoformat(raw)
                remaining = (target - today).days
                countdown = f"{remaining} days left" if remaining >= 0 else f"{abs(remaining)} days overdue"
                widget = milestone if primary else common_core
                widget.tooltip = countdown
                if primary:
                    milestone.add_class("urgent" if remaining < 7 else "approaching" if remaining <= 30 else "comfortable")
                return f"[dim]{title}[/]\n\n[bold]{target:%d/%m/%Y}[/]\n[dim]{countdown}[/]"

            milestone.update(deadline("Milestone deadline", "next_milestone", primary=True))
            common_core.update(deadline("Common Core ETA", "cc_eta"))
        flags = []
        if goals.get("probationary_period"):
            flags.append("Probationary period")
        status.update(" · ".join(flags))
        status.display = bool(flags)

    def _update_deadline_summary(self) -> None:
        """Show the resolved milestone and a project from that rank and track."""
        deadline = DashboardService.deadline_summary(
            self.project_curriculum, self._sorted_projects(self.projects.values()))
        milestone, next_label = deadline.milestone, deadline.next_label
        summary = self.query_one("#dashboard-deadline-summary", Static)
        summary.update(f"[dim]MILESTONE[/]  [bold]{escape(milestone)}[/]\n[dim]NEXT UP[/]  {escape(next_label)}")
        summary.tooltip = f"Milestone: {milestone}\nNext up: {next_label}"
