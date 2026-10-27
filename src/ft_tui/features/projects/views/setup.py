"""ProjectSetup actions for the Projects screen."""

from ft_tui.ui.components import (
    CheckoutResult,
    CheckoutSetupError,
    Input,
    ListView,
    Path,
    ProjectEntry,
    Select,
    ProjectSettingsScreen,
    TabbedContent,
    ensure_pdf_gitignore,
)


class ProjectSetupMixin:
    def action_git_sync(self) -> None:
        selected = self.query_one("#project-list-view", ListView).highlighted_child
        if isinstance(selected, ProjectEntry):
            self._show_project(selected.project, announce_git_refresh=True)
        else:
            self.notify("Select a project to inspect its Git status.", severity="warning")

    def action_configure_project(self) -> None:
        project_list = self.query_one("#project-list-view", ListView)
        selected = project_list.highlighted_child
        if not isinstance(selected, ProjectEntry):
            self.notify("There are no projects to configure.", severity="warning")
            return
        self._open_project_settings(selected)

    def _open_project_settings(self, selected: ProjectEntry) -> None:
        self._open_project_settings_for_key(selected.key)

    def _open_project_settings_for_key(self, slug: str) -> None:
        if slug not in self.projects:
            self.notify("Project is no longer available.", severity="warning")
            return
        self._editing_project_key = slug
        try:
            screen = ProjectSettingsScreen(self.projects[slug], self.projects_root)
        except ValueError:
            self._editing_project_key = None
            self.notify("Project slug cannot be used as a safe checkout folder.", severity="error")
            return
        self.push_screen(
            screen,
            self._save_project_settings,
        )

    async def _show_dashboard_project(self, slug: str) -> None:
        """Switch to Projects and reveal a project selected elsewhere in the app."""
        project = self.projects.get(slug)
        if project is None:
            return
        self._revealed_project_key = slug
        self.query_one(TabbedContent).active = "projects-tab"
        search = self.query_one("#project-search", Input)
        with self.prevent(Select.Changed, Input.Changed):
            if slug not in {p.ui_key for p in self._visible_projects()}:
                self.query_one("#project-view", Select).value = "all"
                self.query_one("#project-kind", Select).value = "all"
                self.query_one("#project-branch", Select).value = "all"
            search.value = ""
        expanded = getattr(self, '_expanded_project_ranks', set())
        expanded.add(self._rank_group_key(self._project_rank(project)))
        self._expanded_project_ranks = expanded
        # The explicit destination takes precedence over a highlighted rank header.
        self.query_one("#project-list-view", ListView).index = None
        await self._refresh_project_list(slug)
        self.query_one("#project-list-view", ListView).focus()

    def _save_project_settings(self, values: dict[str, str] | None) -> None:
        slug = self._editing_project_key
        self._editing_project_key = None
        if values is None or slug is None:
            return
        existing = self.projects.get(slug)
        if existing is None:
            self.notify("Project no longer exists in the local catalog.", severity="error")
            return
        updated = self.project_service.save_settings(existing.id,values,
                                                    catalog=existing.catalog_data,progress=existing.progress_data)
        if updated is None:
            self.notify("Project no longer exists in the local catalog.", severity="error")
            return

        self.projects[slug] = updated
        for entry in self.query(ProjectEntry):
            if entry.key == slug:
                entry.update_project(updated)
                break
        self._show_project(updated)
        if values.get("setup_checkout") != "true" and updated.local_path and Path(updated.local_path).expanduser().is_dir():
            try:
                ensure_pdf_gitignore(updated.local_path)
            except OSError as error:
                self.notify(f"Could not update project .gitignore: {error}", severity="warning")
            self._start_due_subject_checks()
        self.run_worker(self._refresh_dashboard(), group="dashboard-refresh", exclusive=True)
        self.notify(f"Saved settings for {updated.name}.")
        if values.get("setup_checkout") == "true":
            checkout_values = {
                "local_path": values["local_path"],
                "dev_repo_url": values["dev_repo_url"],
                "vogsphere_url": updated.vogsphere_url or "",
                "project_name": updated.name,
                "project_key": slug,
            }
            self.notify("Setting up the local Git checkout…")
            self.run_worker(
                lambda: self._setup_checkout_in_background(checkout_values),
                name=f"setup-checkout-{slug}",
                group="project-checkout",
                exclusive=True,
                thread=True,
            )

    def _setup_checkout_in_background(self, values: dict[str, str]) -> None:
        """Run Git/network work off the UI thread and report the result safely."""
        try:
            result = self.project_service.setup_checkout(
                values["local_path"],
                dev_remote_url=values["dev_repo_url"] or None,
                vogsphere_url=values["vogsphere_url"] or None,
            )
        except CheckoutSetupError as error:
            self.call_from_thread(
                self.notify,
                f"Checkout setup failed: {error}",
                severity="error",
                timeout=10,
            )
            return
        except OSError as error:
            self.call_from_thread(
                self.notify,
                f"Checkout setup failed: {error}",
                severity="error",
                timeout=10,
            )
            return

        self.call_from_thread(
            self._report_checkout_setup,
            values["project_name"],
            result,
            values["project_key"],
            values["local_path"],
        )

    def _report_checkout_setup(
        self, project_name: str, result: CheckoutResult, project_key: str, project_path: str
    ) -> None:
        self.notify(f"{project_name}: {result.message}", timeout=10)
        project = self.projects.get(project_key)
        if project is not None and project.local_path == project_path:
            for entry in self.query(ProjectEntry):
                if entry.key == project_key:
                    entry.update_project(project)
            if self.selected_project_key == project_key:
                self._show_project(project)
            self.run_worker(self._refresh_dashboard(), group="dashboard-refresh", exclusive=True)
        self._start_due_subject_checks()
