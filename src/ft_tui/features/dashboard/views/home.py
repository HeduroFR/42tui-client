"""Dashboard UI composition and behavior."""

import asyncio
import math
import re

from textual.css.query import NoMatches

from rich.markup import escape
from rich.panel import Panel
from rich.align import Align
from rich.text import Text
from ft_tui.ui.username import username_text

from ft_tui.features.dashboard.service import DashboardService
from ft_tui.features.dashboard.views.heatmap import (
    ActivityHeatmap,
    activity_color,
    format_duration,
    format_tooltip_time,
)

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


def attendance_pending_retry(error):
    """Return the retry delay for the worker's pending response, else None."""
    response = getattr(error, "response", None)
    if getattr(response, "status_code", None) != 503:
        return None
    try:
        payload = response.json()
    except Exception:
        return None
    if not isinstance(payload, dict) or payload.get("error") != "attendance_pending":
        return None
    try:
        retry = int(response.headers.get("retry-after", "5"))
    except (TypeError, ValueError):
        retry = 5
    return min(max(retry, 1), 60)


def coalition_values(profile, snapshot, *, account_id=None, cursus_id=None):
    """Prefer a valid backend coalition snapshot, else the live profile value."""
    profile = profile.get('coalition') if isinstance(profile, dict) else None
    profile = profile if isinstance(profile, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    value = snapshot.get('coalition')
    if (snapshot.get('status') == 'available'
            and (account_id is None or snapshot.get('account_id') == account_id)
            and (cursus_id is None or snapshot.get('cursus_id') == cursus_id)
            and isinstance(value, dict)
            and type(value.get('score')) is int and value['score'] >= 0
            and type(value.get('rank')) is int and value['rank'] >= 1):
        return value
    return profile


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

    def _render_coalition(self, profile):
        cursus_id = self.profile_service.cursus_id()
        snapshot = getattr(self, 'account_coalition', None) if getattr(self, 'account_connected', False) else None
        coalition = coalition_values(profile, snapshot,
                                     account_id=self.account_id, cursus_id=cursus_id)
        name = coalition.get('name')
        rank = coalition.get('rank')
        label = name.strip() if isinstance(name, str) else ''
        if label and type(rank) is int and rank >= 1:
            label = f"{label} - #{rank}"
        elif type(rank) is int and rank >= 1:
            label = f"#{rank}"
        name_widget = self.query_one('#dashboard-coalition-name', Static)
        name_widget.update(label)
        color = coalition.get('color')
        name_widget.styles.color = (color if isinstance(color, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', color)
                                    else self.app.theme_variables.get('accent', '#ffffff'))
        rank_widget = self.query_one('#dashboard-coalition-rank', Static)
        rank_widget.update('')
        rank_widget.display = False
        for field, label in (('score', 'Score'), ('rank', 'Rank')):
            value = coalition.get(field)
            text = f"{translate(label, self.language)}: {value}" if type(value) is int and value >= (1 if field == 'rank' else 0) else ''
            widget = self.query_one(f'#dashboard-coalition-{field}', Static)
            widget.update(text)
            widget.tooltip = text or None

    def _start_coalition_refresh(self):
        provider = getattr(self, 'provider', None)
        if (not getattr(self, 'account_connected', False) or not getattr(self, 'account_id', None)
                or not callable(getattr(provider, 'get_coalition', None))
                or getattr(self, '_coalition_busy', False)):
            return
        now = asyncio.get_running_loop().time()
        if getattr(self, '_coalition_account', None) != self.account_id:
            self._coalition_account = self.account_id
            self._coalition_checked = 0.0
        if now - getattr(self, '_coalition_checked', 0.0) < 60:
            return
        self._coalition_busy = True
        self.run_worker(self._fetch_coalition(provider, self.account_id, self.account_generation),
                        group='dashboard-coalition', exclusive=True)

    async def _fetch_coalition(self, provider, account, generation):
        try:
            value = await asyncio.to_thread(provider.get_coalition)
            if account == self.account_id and generation == self.account_generation:
                self.account_coalition = value if isinstance(value, dict) else {}
                self._coalition_checked = asyncio.get_running_loop().time()
                self._render_coalition(self.account_profile if self.account_connected else {})
        except Exception:
            pass
        finally:
            self._coalition_busy = False

    def _start_event_subscriptions_refresh(self):
        provider = getattr(self, 'provider', None)
        if (not getattr(self, 'account_connected', False) or not getattr(self, 'account_id', None)
                or not callable(getattr(provider, 'get_event_subscriptions', None))
                or getattr(self, '_subscriptions_busy', False)):
            return
        now = asyncio.get_running_loop().time()
        if getattr(self, '_subscriptions_account', None) != self.account_id:
            self._subscriptions_account = self.account_id
            self._subscriptions_checked = 0.0
        if now - getattr(self, '_subscriptions_checked', 0.0) < 60:
            return
        self._subscriptions_busy = True
        self.run_worker(self._fetch_event_subscriptions(provider, self.account_id, self.account_generation),
                        group='dashboard-subscriptions', exclusive=True)

    async def _fetch_event_subscriptions(self, provider, account, generation):
        try:
            value = await asyncio.to_thread(provider.get_event_subscriptions)
            if account == self.account_id and generation == self.account_generation:
                ids = value.get('event_ids') if isinstance(value, dict) else None
                self.event_subscriptions = {item for item in ids if type(item) is int and item > 0} if isinstance(ids, list) else set()
                self._subscriptions_checked = asyncio.get_running_loop().time()
                try:
                    self.query_one('#dashboard-evaluations').run_worker(
                        self.query_one('#dashboard-evaluations').render_rows(),
                        group='dashboard-evaluations-render', exclusive=True)
                except NoMatches:
                    pass
        except Exception:
            pass
        finally:
            self._subscriptions_busy = False

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
        memberships = profile.get('cursus_users', [])
        cursus_id = self.profile_service.cursus_id()
        membership = next((item for item in memberships if isinstance(item, dict)
                           and item.get('cursus_id') == cursus_id), {}) if isinstance(memberships, list) else {}
        grade = membership.get('grade')
        grade = grade.strip() if isinstance(grade, str) and grade.strip() else translate('Unavailable', self.language)
        details = f"{translate('Grade', self.language)}: {grade}"
        level = membership.get('level')
        level_value = (f'{level:.2f}' if type(level) in (int, float) and math.isfinite(level) and level >= 0
                       else translate('Unavailable', self.language))
        level_text = f"{translate('Level', self.language)}: {level_value}"
        campuses = profile.get('campuses', [])
        campus = next((item for item in campuses if isinstance(item, dict) and item.get('is_primary') is True
                       and isinstance(item.get('name'), str) and item['name'].strip()), {}) if isinstance(campuses, list) else {}
        campus_name = campus.get('name', '').strip() or translate('Unavailable', self.language)
        campus_text = f"{translate('Campus', self.language)}: {campus_name}"
        for selector, value in (('#dashboard-level', level_text), ('#dashboard-grade', details),
                                ('#dashboard-campus', campus_text)):
            widget = self.query_one(selector, Static)
            widget.update(value)
            widget.tooltip = value
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
        self._render_coalition(profile)
        self._start_coalition_refresh()
        self._start_event_subscriptions_refresh()
        self._start_attendance_refresh()
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

        self._render_activity_card(model, self.language)

        self._update_black_hole()

        journey = model.journey
        total, completed = journey.total, journey.completed
        percent = round(completed / total * 100) if total else 0
        self.query_one("#dashboard-progress-value", Static).update(f"{completed:02d} / {total:02d}")
        self.query_one("#dashboard-progress-caption", Static).update(
            f"projects completed · {percent}%"
        )
        self.query_one("#dashboard-progress-done", Static).update(f"[green]●[/] {translate('Done', self.language).upper()} {completed}")
        self.query_one("#dashboard-progress-active", Static).update(f"[#15d3c1]●[/] {translate('Active', self.language).upper()} {journey.active}")
        self.query_one("#dashboard-progress-available", Static).update(
            f"[#e6b450]●[/] {translate('Available', self.language).upper()} {journey.available}"
        )
        self.query_one("#dashboard-progress-locked", Static).update(f"[#59636e]●[/] {translate('Locked', self.language).upper()} {journey.locked}")
        segments = [
            (journey.completed, "green"),
            (journey.active, "#15d3c1"),
            (journey.available, "#e6b450"),
            (journey.locked, "#59636e"),
        ]
        labels = (('done', 'Completed'), ('active', 'In progress'), ('available', 'Available'), ('locked', 'Locked'))
        for (count, color), (status, label), names in zip(segments, labels, journey.groups):
            segment = self.query_one(f'#dashboard-progress-segment-{status}')
            segment.display = count > 0
            if count:
                segment.styles.width = f'{count}fr'
                segment.styles.background = color
            title = translate(label, self.language)
            tooltip_color = '#98a6b5' if status == 'locked' else color
            segment.set_projects(title, names, tooltip_color)
            self.query_one(f'#dashboard-progress-{status}').set_projects(title, names, tooltip_color)
        unknown = max(0, total - sum(count for count, _ in segments))
        unclassified = self.query_one('#dashboard-progress-unknown')
        unclassified.display = unknown > 0
        if unknown:
            unclassified.styles.width = f'{unknown}fr'
        self.query_one("#dashboard-progress-next-name", Static).update(journey.next_name)

    def _render_activity_card(self, model, language) -> None:
        workstation = getattr(self, "attendance_mode", "coding") == "workstation"
        toggle = self.query_one("#dashboard-activity-toggle", Button)
        toggle.set_source_label("Coding time" if workstation else "Log time")
        data = getattr(self, "account_attendance", None) if workstation else None
        if isinstance(data, dict) and data.get("user_id") != getattr(self, "account_id", None):
            data = None
        status = data.get("status") if isinstance(data, dict) else None
        title_widget = self.query_one("#dashboard-activity-title", Static)
        heatmap = self.query_one("#dashboard-activity-heatmap", ActivityHeatmap)
        if workstation and status != "available":
            pending = status in (None, "pending")
            state = "Loading…" if pending else "Unavailable"
            title_widget.update(f"{translate('LOG TIME', language)} · {translate(state, language)}")
            title_widget.tooltip = None
            heatmap.set_snapshot(translate("Loading workstation time…" if pending
                                           else "Workstation time unavailable.", language), {})
            heatmap.tooltip = None
            return
        if workstation:
            week_starts, day_seconds, week_seconds, known = DashboardService.attendance_weeks(
                data.get("days") or {}, datetime.now(timezone.utc)
            )
            stale = data.get("stale") is True
            heading = translate("LOG TIME", language)
        else:
            week_starts, day_seconds, week_seconds = model.week_starts, model.day_seconds, model.week_seconds
            known = {week: 7 for week in week_starts}
            stale = False
            heading = translate("WEEKLY CODING", language)
        current_seconds = week_seconds[week_starts[-1]]
        if known[week_starts[-1]]:
            hours, minutes = divmod(int(current_seconds // 60), 60)
            current = translate("{time} [dim]this week[/]", language).format(
                time=f"{hours}h {minutes:02d}m"
            )
        else:
            current = translate("Unavailable", language)
        title_widget.update(f"{heading} · {current}{' · ' + translate('stale', language) if stale else ''}")
        title_widget.tooltip = None

        day_labels = {
            "en": "M T W T F S S",
            "fr": "L M M J V S D",
            "es": "L M X J V S D",
        }.get(language, "M T W T F S S")
        month_labels = {
            "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
            "fr": ("jan", "fév", "mar", "avr", "mai", "jun", "jui", "aoû", "sep", "oct", "nov", "déc"),
            "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
        }.get(language, ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"))
        # Keep every row the same width so the weekday legend stays aligned.
        heatmap_lines = [f"        {day_labels}         "]
        tooltips = {}
        for week_index, week in enumerate(week_starts):
            cumulative = 0.0
            reported = 0
            cells = []
            for day in range(7):
                date = week + timedelta(days=day)
                seconds = day_seconds[date]
                if seconds is not None:
                    cumulative += seconds
                    reported += 1
                color = activity_color(seconds)
                cells.append(f"[{color}]█[/]" if color
                             else "[#2f3740]·[/]" if seconds is None
                             else "[#46505b]·[/]")
                day_time = "—" if seconds is None else format_tooltip_time(seconds)
                week_time = format_tooltip_time(cumulative) if reported else "—"
                tooltips[(week_index, day)] = f"{day_time} ({week_time})"
            seconds = week_seconds[week]
            duration = format_duration(seconds) if known[week] else "—"
            label = f"{week.day:02d} {month_labels[week.month - 1]}"
            heatmap_lines.append(f"{label:>6}  {' '.join(cells)} {duration:>8}")
        heatmap.set_snapshot("\n".join(heatmap_lines), tooltips)
        heatmap.tooltip = None

    def _start_attendance_refresh(self, *, force=False) -> None:
        provider = getattr(self, "provider", None)
        if (not getattr(self, "account_connected", False) or not getattr(self, "account_id", None)
                or getattr(self, "attendance_mode", "coding") != "workstation"
                or not callable(getattr(provider, "get_my_attendance", None))
                or getattr(self, "_attendance_busy", False)):
            return
        if force and getattr(self, "_attendance_timer", None) is not None:
            self._attendance_timer.stop()
            self._attendance_timer = None
        now = asyncio.get_running_loop().time()
        if getattr(self, "_attendance_account", None) != self.account_id:
            self._attendance_account = self.account_id
            self._attendance_checked = 0.0
            self._attendance_attempts = 0
        if not force and now - getattr(self, "_attendance_checked", 0.0) < 60:
            return
        self._attendance_busy = True
        self.run_worker(self._fetch_attendance(provider, self.account_id, self.account_generation),
                        group="dashboard-attendance", exclusive=True)

    def _schedule_attendance_retry(self, delay) -> None:
        attempts = getattr(self, "_attendance_attempts", 0) + 1
        self._attendance_attempts = attempts
        if attempts > 6 or getattr(self, "_attendance_timer", None) is not None:
            return

        def retry():
            self._attendance_timer = None
            if self.is_mounted and self.attendance_mode == "workstation":
                self._start_attendance_refresh(force=True)

        self._attendance_timer = self.set_timer(delay, retry)

    async def _fetch_attendance(self, provider, account, generation):
        try:
            value = await asyncio.to_thread(provider.get_my_attendance, account)
            if account != self.account_id or generation != self.account_generation:
                return
            current = getattr(self, "account_attendance", None)
            if isinstance(value, dict) and (value.get("status") == "available" or not current):
                self.account_attendance = value
            elif isinstance(current, dict):
                self.account_attendance = {**current, "stale": True}
            self._attendance_attempts = 0
            self._attendance_checked = asyncio.get_running_loop().time()
            await self._refresh_dashboard()
        except Exception as error:
            if account == self.account_id and generation == self.account_generation:
                current = getattr(self, "account_attendance", None)
                delay = attendance_pending_retry(error)
                if delay is not None and not (isinstance(current, dict)
                                              and current.get("status") == "available"):
                    self.account_attendance = {"user_id": account, "status": "pending", "stale": False}
                    self._schedule_attendance_retry(delay)
                elif isinstance(current, dict) and current.get("status") == "available":
                    self.account_attendance = {**current, "stale": True}
                    self._attendance_attempts = 0
                else:
                    self.account_attendance = {"user_id": account, "status": "unavailable",
                                               "stale": True, "reason": "attendance_unavailable"}
                    self._attendance_attempts = 0
                self._attendance_checked = asyncio.get_running_loop().time()
                await self._refresh_dashboard()
        finally:
            self._attendance_busy = False

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
