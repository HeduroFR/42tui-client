"""Projects UI composition and behavior."""

import asyncio
from functools import partial
from urllib.parse import quote

from ft_tui.features.projects.subjects.adapters.files import synchronize_subject_pdf
from ft_tui.api.http_client import SubjectPendingError

from ft_tui.ui.components import (
    Button,
    DevNote,
    Input,
    ListView,
    PDFCheckError,
    Path,
    Project,
    ProjectEntry,
    ProjectNoteEntry,
    Static,
    active_manual_timer,
    compare_subject_hashes,
    datetime,
    ensure_pdf_gitignore,
    escape,
    has_local_folder,
    inspect_repository,
    os,
    platform,
    select,
    shutil,
    subprocess,
    timezone,
    tracked_seconds,
    translate,
)


from .subjects import SubjectMixin


class ProjectDetailsMixin(SubjectMixin):

    def _show_project(self, project: Project, *, announce_git_refresh: bool = False) -> None:
        self.selected_project_key = project.ui_key
        self.query_one('#new-project-note', Button).disabled = project.id is None
        self._render_project_details(project)
        self._load_project_registration(project.ui_key)
        self.run_worker(partial(self._load_selected_catalog_detail, project), group="catalog-detail", exclusive=True)
        self._refresh_manual_timer_display()
        self._refresh_subject_status(project)
        self._update_editor_button()
        if (project.dev_repo_url or "").strip() and has_local_folder(project.local_path):
            self.run_worker(
                partial(
                    self._inspect_project_git_status, project.ui_key,
                    project.local_path,
                    announce=announce_git_refresh,
                ),
                group="project-git-status",
                exclusive=True,
            )
        elif announce_git_refresh:
            self.notify("Configure a development remote to inspect Git." if not (project.dev_repo_url or "").strip()
                        else "Configure an existing local folder to inspect Git.")
        if project.id is not None:
            self.run_worker(
                partial(self._load_project_notes, project.id, project.ui_key),
                group="project-notes",
                exclusive=True,
            )
        else:
            self.query_one("#project-notes-list", ListView).clear()
            self.query_one("#project-notes-empty", Static).update("Project metadata unavailable.")

    def _render_project_details(self, project: Project, git_snapshot=None) -> None:
        """Render project metadata, optionally with a completed Git inspection."""
        if not self.is_mounted or not self.query("#details-content"):
            return
        path = project.local_path or translate("Not configured", self.language)
        if not (project.dev_repo_url or "").strip():
            git_status = translate("Configure a development remote to inspect Git.", self.language)
        elif not project.local_path:
            git_status = translate("Configure a local path to inspect Git.", self.language)
        elif not has_local_folder(project.local_path):
            git_status = translate(
                "The project folder is missing. Press e to choose a new path.",
                self.language,
            )
        elif git_snapshot is None:
            git_status = translate("Checking Git status…", self.language)
        elif git_snapshot.error:
            git_status = (
                f"{translate('Unavailable', self.language)} · "
                f"{escape(translate(git_snapshot.error, self.language))}"
            )
        else:
            changes = []
            if git_snapshot.staged:
                changes.append(f"{git_snapshot.staged} {translate('staged', self.language)}")
            if git_snapshot.changed:
                changes.append(f"{git_snapshot.changed} {translate('modified', self.language)}")
            if git_snapshot.untracked:
                changes.append(f"{git_snapshot.untracked} {translate('untracked', self.language)}")
            git_status = f"{escape(git_snapshot.branch or translate('unknown', self.language))} · " + (
                ", ".join(changes) if changes else translate("clean", self.language)
            )
            if git_snapshot.sensitive_files:
                names = ", ".join(escape(name) for name in git_snapshot.sensitive_files)
                git_status += (
                    f"\n[bold red]{translate('Sensitive-looking files', self.language)}: "
                    f"{names}[/bold red]"
                )
        intra_url = f"https://projects.intra.42.fr/{quote(project.slug, safe='')}/mine"
        from ft_tui.features.catalog.views.presentation import catalog_details as format_catalog_details
        catalog_details = format_catalog_details(project, getattr(self,"project_curriculum",{}), self.language)
        if project.slug:
            catalog_details += f'[link="{intra_url}"]{intra_url}[/link]\n\n'
        self._project_technical_details = (
            catalog_details
            + f"{translate('Local path', self.language)}: {escape(path)}\n{translate('Git', self.language)}: {git_status}\n"
            + f"{translate('Dev remote', self.language)}: {escape(project.dev_repo_url or '—')}\n"
            + f"{translate('Vogsphere', self.language)}: {escape(project.vogsphere_url or '—')}"
        )
        data = project.catalog_data
        self.query_one("#project-heading", Static).update(
            f"[bold]{escape(project.name)}[/bold]"
        )
        self._render_project_summary(project)
        self.query_one("#show-project-activity", Button).disabled = not (
            project.official_project_id and getattr(self, 'account_id', None) and self._catalog_scope()
            and self.provider is not None and hasattr(self.provider, 'get_project_activity')
            and hasattr(self.provider, 'get_team_evaluations')
        )
        overview = escape(data.get("description") or translate("No description available.", self.language))
        self.query_one("#details-content", Static).update(overview)
        registration_state=getattr(self,"_registration_state",None)
        if registration_state and registration_state['project_id']==project.official_project_id:
            self._render_project_registration(registration_state)
        for selector in ("#configure-project", "#show-project-details"):
            self.query_one(selector, Button).disabled = False
        workspace = (f"Folder · {escape(Path(project.local_path).name)}\nGit · {git_status}"
                     if has_local_folder(project.local_path)
                     else "Configure a project folder to open the editor and subject.")
        self.query_one("#project-workspace-status", Static).update(workspace)
        self.query_one("#project-testers").set_project(project)

    def _render_project_summary(self, project, mode=None):
        data = project.catalog_data
        if mode in (None,"unknown"):
            mode = data.get("project_mode", "unknown")
        summary = [translate({"solo":"Solo", "group":"Group", "unknown":"Team size unavailable"}[mode], self.language)]
        if mode == "group" and data.get("team_size"):
            summary[0] = translate("Group · {size} members", self.language).format(size=data["team_size"])
        if data.get("rank") is not None:
            summary.append(f"Rank {data['rank']}")
        if data.get("xp") is not None:
            summary.append(f"{data['xp']} XP")
        if data.get("duration"):
            summary.append(str(data['duration']))
        self.query_one("#project-summary", Static).update(escape(" · ".join(summary)))

    def _clear_project_details(self) -> None:
        self.query_one("#project-testers").set_project(None)
        self._clear_project_registration()
        self._project_technical_details = ""
        self.query_one("#show-project-activity", Button).disabled = True
        for selector, text in (
            ("#project-heading", "Select a project"), ("#project-summary", ""),
            ("#project-workspace-status", "Select a project to see workspace actions."),
            ("#project-subject-status", ""), ("#project-time-spent", "TOTAL TIME · 0h 00m"),
            ("#project-timer-status", ""),
            ("#project-notes-empty", "No project selected."),
        ):
            self.query_one(selector, Static).update(text)
        self.query_one("#project-notes-list").display = False
        self.query_one("#project-notes-empty").display = True
        for selector in ("#configure-project", "#show-project-details",
                         "#open-project-folder", "#project-push-dev", "#project-push-vog", "#project-push-all"):
            self.query_one(selector, Button).disabled = True

    def action_project_team(self):
        from ft_tui.features.projects.views.team import ProjectTeamScreen
        project = self.projects.get(self.selected_project_key or '')
        scope = self._catalog_scope()
        if self._can_manage_project_team() and callable(getattr(self.provider, 'get_project_team', None)):
            self.push_screen(ProjectTeamScreen(project.official_project_id, project.name, scope, self.account_id,
                                             self.provider, self.account_generation, project.slug))

    def action_project_activity(self) -> None:
        from ft_tui.features.projects.views.activity import open_project_activity
        project = self.projects.get(self.selected_project_key or '')
        scope = self._catalog_scope()
        if (not project or not project.official_project_id or not scope or not self.account_id
                or self.provider is None or not hasattr(self.provider, 'get_project_activity')
                or not hasattr(self.provider, 'get_team_evaluations')):
            return
        url = f"https://projects.intra.42.fr/{quote(project.slug, safe='')}/mine" if project.slug else None
        open_project_activity(self, project.official_project_id, project.name, scope, self.account_id,
                              self.provider, self.account_generation, url)

    def action_project_testers(self) -> None:
        if len(self.screen_stack) != 1 or self.query_one("#main-tabs").active != "projects-tab":
            return
        if self.selected_project_key:
            self.query_one("#project-testers").focus_actions()

    def action_project_technical_details(self) -> None:
        from textual.widgets import TabbedContent
        if self.query_one(TabbedContent).active != "projects-tab":
            return
        if self.selected_project_key:
            from ft_tui.features.projects.views.technical_details import ProjectTechnicalDetailsScreen
            self.push_screen(ProjectTechnicalDetailsScreen(getattr(self, "_project_technical_details", "")))

    async def _inspect_project_git_status(
        self,
        project_key: str,
        project_path: str,
        *,
        announce: bool = False,
    ) -> None:
        """Inspect Git away from Textual's event loop and ignore stale results."""
        # Project rows emit a highlight event on every arrow key; wait briefly
        # so fast navigation starts a single Git inspection for the final row.
        await asyncio.sleep(0.12)
        if self.selected_project_key != project_key:
            return
        project = self.projects.get(project_key)
        if project is None or project.local_path != project_path or not (project.dev_repo_url or "").strip():
            return
        snapshot = await asyncio.to_thread(inspect_repository, project_path)
        if self.selected_project_key != project_key:
            return
        project = self.projects.get(project_key)
        if project is None or project.local_path != project_path or not (project.dev_repo_url or "").strip():
            return
        self._render_project_details(project, snapshot)
        if announce:
            self.notify(f"Git status refreshed for {project.name}.")

    def _refresh_manual_timer_display(self) -> None:
        """Update the selected project's live total and timer controls."""
        if not self.is_mounted or not self.query("#project-timer-toggle"):
            return
        project = self.projects.get(self.selected_project_key or "")
        toggle = self.query_one("#project-timer-toggle", Button)
        toggle.disabled = project is None or project.id is None
        timer = self.worklog_service.timer(project.id if project is not None else None)
        active, total_seconds = timer.active, timer.total_seconds

        hours, remainder = divmod(int(total_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.query_one("#project-time-spent", Static).update(
            f"TOTAL TIME · {hours}h {minutes:02d}m"
        )
        if project is not None and active is not None and project.id == active.project_id:
            elapsed = max(0, int((datetime.now(timezone.utc).replace(tzinfo=None) - active.start_time).total_seconds()))
            timer_hours, remainder = divmod(elapsed, 3600)
            timer_minutes, timer_seconds = divmod(remainder, 60)
            self.query_one("#project-timer-status", Static).update(
                f"MANUAL TIMER RUNNING · {timer_hours:02d}:{timer_minutes:02d}:{timer_seconds:02d}"
            )
            toggle.set_source_label("Stop timer")
        elif active is not None:
            active_project = next(
                (item for item in self.projects.values() if item.id == active.project_id),
                None,
            )
            active_name = active_project.name if active_project is not None else "another project"
            self.query_one("#project-timer-status", Static).update(
                f"Timer running for {active_name} · starting here switches projects"
            )
            toggle.set_source_label("Start timer")
        else:
            self.query_one("#project-timer-status", Static).update("No manual timer running")
            toggle.set_source_label("Start timer")


    async def _load_project_notes(self, project_id: int, project_key: str) -> None:
        """Refresh recent note links shown beside the selected project."""
        rows = [(note.id,note.title,note.updated_at) for note in self.worklog_service.notes(project_id,limit=5)]
        if self.selected_project_key != project_key:
            return
        note_list = self.query_one("#project-notes-list", ListView)
        await note_list.clear()
        empty = self.query_one("#project-notes-empty", Static)
        if rows:
            await note_list.extend(
                ProjectNoteEntry(note_id, project_key, title, updated_at)
                for note_id, title, updated_at in rows
            )
            note_list.styles.display = "block"
            empty.styles.display = "none"
        else:
            note_list.styles.display = "none"
            empty.update("No notes saved for this project.")
            empty.styles.display = "block"

    def _update_editor_button(self) -> None:
        """Match the project action button to the selected editor and project."""
        editor_names = {
            "nvim": "Neovim",
            "vim": "Vim",
            "vscode": "Visual Studio Code",
            "zed": "Zed",
        }
        editor_button = self.query_one("#open-project-editor", Button)
        editor_button.set_source_label("Open editor")
        editor_button.tooltip = f"Open in {editor_names.get(self.favorite_editor, 'editor')}"
        project = self.projects.get(self.selected_project_key or "")
        existing_folder = project is not None and has_local_folder(project.local_path)
        editor_button.disabled = not (existing_folder or (project is not None and project.local_path
                                     and (project.dev_repo_url or project.vogsphere_url)))
        self.query_one("#open-project-folder", Button).disabled = not existing_folder
        for destination in ("dev", "vog", "all"):
            self.query_one(f"#project-push-{destination}", Button).disabled = not existing_folder

    @staticmethod
    def _status_label(status: str) -> str:
        labels = {"in_progress": "DEV", "completed": "DONE", "locked": "LOCKED", "unknown": "INACTIVE"}
        return labels.get(status, status.upper())

    async def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "project-search":
            return
        preferred = self.pending_dashboard_project_key or self.selected_project_key
        if event.input.id == "project-search":
            timer = getattr(self, "_catalog_search_timer", None)
            if timer is not None: timer.stop()
            self._catalog_search_timer = self.set_timer(.3, self._request_catalog_refresh)
        await self._refresh_project_list(preferred)
        if self.pending_dashboard_project_key is not None:
            self.query_one("#project-list-view", ListView).focus()
        self.pending_dashboard_project_key = None
