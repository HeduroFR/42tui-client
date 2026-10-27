"""Dynamic commands exposed by the Textual command palette."""

from __future__ import annotations

from collections.abc import Callable

from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.widgets import TabbedContent

from ft_tui.ui.select import Select
from ft_tui.i18n import translate
from ft_tui.ui.components import has_local_folder


class FortyTwoTuiCommandProvider(Provider):
    """Offer navigation and project actions, including the local project catalog."""

    def _commands(self) -> list[tuple[str, str, Callable[[], object]]]:
        app = self.app
        language = app.language

        def label(message: str, **values: str) -> str:
            return translate(message, language).format(**values)

        commands: list[tuple[str, str, Callable[[], object]]] = [
            (label("Go to Dashboard"), label("Open the dashboard"), app.action_show_dashboard),
            (label("Go to Projects"), label("Browse the project catalog"), app.action_show_projects),
            (label("Go to Dev Log"), label("Open project notes"), app.action_show_notes),
            (label("Go to Settings"), label("Change local preferences"), app.action_show_settings),
        ]

        selected_key = app.selected_project_key
        if selected_key in app.projects:
            project = app.projects[selected_key]
            commands.extend(
                [
                    (
                        label("Open selected project in editor"),
                        label("Open {name} in the favorite editor", name=project.name),
                        app.action_open_project_editor,
                    ),
                    (
                        label("Configure selected project"),
                        label("Set the local folder and development remote for {name}", name=project.name),
                        lambda slug=selected_key: app._open_project_settings_for_key(slug),
                    ),
                    (
                        label("Create a note for selected project"),
                        label("Start a Dev Log note for {name}", name=project.name),
                        lambda slug=selected_key: self._create_note(slug),
                    ),
                ]
            )

        for project in app._sorted_projects(app.projects.values()):
            slug = project.ui_key
            commands.append(
                (
                    label("Go to project: {name}", name=project.name),
                    label("Show {name} in the Projects view", name=project.name),
                    lambda slug=slug: app.run_worker(
                        app._show_dashboard_project(slug),
                        group="palette-project-navigation",
                        exclusive=True,
                    ),
                )
            )
            if has_local_folder(project.local_path):
                commands.append(
                    (
                        label("Open project in editor: {name}", name=project.name),
                        label("Open {name} in the favorite editor", name=project.name),
                        lambda slug=slug: self._open_project(slug),
                    )
                )
            commands.append(
                (
                    label("Configure project: {name}", name=project.name),
                    label("Set the local folder and development remote for {name}", name=project.name),
                    lambda slug=slug: app._open_project_settings_for_key(slug),
                )
            )

        return commands

    async def discover(self) -> Hits:
        """Show common navigation and project-jump actions before search input."""
        language = self.app.language
        project_open_prefix = translate("Open project in editor: {name}", language).replace(
            "{name}", ""
        ).strip()
        project_config_prefix = translate("Configure project: {name}", language).replace(
            "{name}", ""
        ).strip()
        project_goto_prefix = translate("Go to project: {name}", language).replace(
            "{name}", ""
        ).strip()
        for name, help_text, callback in self._commands():
            # Keep the initial palette compact; every project action is still
            # discoverable by typing its name into the search field.
            if name.startswith((project_open_prefix, project_config_prefix, project_goto_prefix)):
                continue
            yield DiscoveryHit(name, callback, help=help_text)

    async def search(self, query: str) -> Hits:
        """Fuzzy-search translated action labels and project names."""
        matcher = self.matcher(query)
        for name, help_text, callback in self._commands():
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    callback,
                    text=name,
                    help=help_text,
                )

    def _open_project(self, slug: str) -> None:
        """Select a project as the editor target, then use the configured editor."""
        app = self.app
        app.selected_project_key = slug
        app._open_selected_project_in_editor()

    def _create_note(self, slug: str) -> None:
        """Open a blank Dev Log note attached to the requested project."""
        app = self.app
        app.query_one(TabbedContent).active = "dev-log"
        project_select = app.query_one("#dev-log-project", Select)
        if project_select.value == slug:
            async def load_then_create() -> None:
                await app._load_dev_log_notes(slug)
                app._begin_new_dev_note()

            app.run_worker(load_then_create(), group="palette-new-note", exclusive=True)
        else:
            app._new_note_after_project_load = slug
            project_select.value = slug
