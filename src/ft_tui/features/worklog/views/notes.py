"""DevLog UI composition and behavior."""

from inspect import isawaitable

from ft_tui.features.worklog.models import NoteSaveError
from ft_tui.ui.modal import AppModal
from ft_tui.ui.components import (
    ComposeResult,
    Horizontal,
    Vertical,
    Button,
    DashboardNoteEntry,
    DevNoteEntry,
    Input,
    ListView,
    Markdown,
    ProjectEntry,
    ProjectRankHeader,
    ProjectNoteEntry,
    Select,
    Static,
    Style,
    TabbedContent,
    TextArea,
    TextAreaTheme,
    translate,
)


class UnsavedNoteScreen(AppModal[str]):
    BINDINGS = [("escape", "cancel", "Cancel")]
    DEFAULT_CSS = """
    #unsaved-note-dialog {
        width: 64; max-width: 95%; height: auto; padding: 1 2;
        border: round $warning; background: $surface;
    }
    #unsaved-note-actions { height: 3; align-horizontal: right; margin-top: 1; }
    #unsaved-note-actions Button { margin-left: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="unsaved-note-dialog"):
            yield Static("Save changes to this note before continuing?")
            with Horizontal(id="unsaved-note-actions"):
                yield Button("Cancel", id="cancel-note-changes")
                yield Button("Discard", id="discard-note-changes", variant="error")
                yield Button("Save note", id="save-note-changes", variant="primary")

    def action_cancel(self) -> None:
        self.dismiss("cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss({"save-note-changes": "save", "discard-note-changes": "discard"}.get(event.button.id, "cancel"))


class DevLogMixin:
    def _dev_note_contents(self) -> tuple[str, str]:
        return (self.query_one("#dev-log-title", Input).value,
                self.query_one("#dev-log-editor", TextArea).text)

    def _remember_dev_note(self) -> None:
        self.worklog_state.saved_contents = self._dev_note_contents()

    def _protect_dev_note(self, continuation) -> bool:
        if self.worklog_state.prompt_pending:
            return False
        if self._dev_note_contents() == self.worklog_state.saved_contents:
            return True
        project_select = self.query_one("#dev-log-project", Select)
        with self.prevent(Select.Changed, ListView.Highlighted):
            project_select.value = self.worklog_state.project_key or Select.NULL
            listing = self.query_one("#dev-log-note-list", ListView)
            listing.index = next((i for i, entry in enumerate(listing.children)
                                  if entry.note_id == self.selected_note_id), None)
        self.worklog_state.prompt_pending = True

        async def finish(choice):
            self.worklog_state.prompt_pending = False
            if choice == "save":
                if not await self._save_dev_note():
                    return
            elif choice == "discard":
                self._remember_dev_note()
            else:
                return
            result = continuation()
            if isawaitable(result):
                await result

        self.push_screen(UnsavedNoteScreen(), lambda choice: self.run_worker(finish(choice), group="note-navigation"))
        return False

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if isinstance(event.item, DevNoteEntry):
            if event.item is not event.list_view.highlighted_child:
                return
            self._show_dev_note(event.item.note_id)
            return
        if event.list_view.id == "project-list-view" and event.item is not event.list_view.highlighted_child:
            return
        project = self.projects.get(event.item.key) if isinstance(event.item, ProjectEntry) else None
        if project is not None and project.ui_key != self.selected_project_key:
            self._show_project(project)

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "project-list-view" and isinstance(event.item, ProjectRankHeader):
            await self._toggle_project_rank(event.item)
        elif event.list_view.id == "dev-log-note-list" and isinstance(event.item, DevNoteEntry):
            self._show_dev_note(event.item.note_id)
        elif isinstance(event.item, (ProjectNoteEntry, DashboardNoteEntry)):
            await self._open_note_target(event.item.project_key, event.item.note_id)
            if isinstance(event.item, DashboardNoteEntry):
                event.list_view.index = None

    async def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "project-view":
            scope = self.query_one("#project-view", Select).value
            if scope == getattr(self, "_project_filter_value", None):
                return
            await self._refresh_project_list(self.selected_project_key)
            self._request_catalog_refresh()
            return
        if event.select.id in {"project-kind", "project-branch"}:
            await self._refresh_project_list(self.selected_project_key)
            self._request_catalog_refresh()
            return
        if event.select.id == "default-cursus":
            if event.value != event.select.value:
                return  # Discard queued events for a selection already replaced.
            await self._handle_default_cursus_changed(event.value)
            return
        if event.select.id == "dev-log-project" and isinstance(event.value, str):
            if event.value != event.select.value:
                return
            await self._load_dev_log_notes(event.value)

    async def _open_project_note(self, entry: ProjectNoteEntry) -> None:
        """Open a note from the project detail panel in the Dev Log editor."""
        await self._open_note_target(entry.project_key, entry.note_id)

    async def _open_note_target(self, project_key: str, note_id: int) -> None:
        """Open a note in Dev Log and select the project it belongs to."""
        if not self._protect_dev_note(lambda: self._open_note_target(project_key, note_id)):
            return
        self.query_one(TabbedContent).active = "dev-log"
        await self._load_dev_log_notes(project_key)
        self._show_dev_note(note_id)

    async def _load_dev_log_notes(self, project_key: str) -> None:
        """Load a project's notes into the Dev Log sidebar."""
        if not self._protect_dev_note(lambda: self._load_dev_log_notes(project_key)):
            return
        self.worklog_state.notes_revision += 1
        revision = self.worklog_state.notes_revision
        project = self.projects.get(project_key)
        note_list = self.query_one("#dev-log-note-list", ListView)
        await note_list.clear()
        if revision != self.worklog_state.notes_revision:
            return
        if not self._protect_dev_note(lambda: self._load_dev_log_notes(project_key)):
            return
        self.worklog_state.project_key = project_key
        with self.prevent(Select.Changed):
            self.query_one("#dev-log-project", Select).value = project_key if project else Select.NULL
        self.selected_note_id = None
        self.query_one("#dev-log-title", Input).value = ""
        self.query_one("#dev-log-editor", TextArea).text = ""
        self._remember_dev_note()
        self.query_one("#dev-log-preview", Static).update("")
        if self.dev_log_previewing:
            self._set_dev_log_preview(False)
        self.query_one("#dev-log-delete", Button).disabled = True
        self.query_one("#dev-log-save", Button).disabled = project is None
        self.query_one("#dev-log-status", Static).update(
            f"Notes for {project.name}. Choose a note or create one." if project else "No project selected."
        )
        if project is None or project.id is None:
            return
        notes = self.worklog_service.notes(project.id)
        note_data = [(note.id,note.title,note.updated_at) for note in notes]
        await note_list.extend(
            DevNoteEntry(note_id, title, updated_at)
            for note_id, title, updated_at in note_data
        )

    def _show_dev_note(self, note_id: int) -> None:
        """Load one note into the editor and preview pane."""
        if note_id == self.selected_note_id:
            return
        note = self.worklog_service.note(note_id)
        project = self.projects.get(self.worklog_state.project_key)
        if note is None or project is None or note.project_id != project.id:
            return
        if not self._protect_dev_note(lambda: self._show_dev_note(note_id)):
            return
        title, content = note.title, note.content
        self.selected_note_id = note_id
        listing = self.query_one("#dev-log-note-list", ListView)
        with self.prevent(ListView.Highlighted):
            listing.index = next((i for i, entry in enumerate(listing.children) if entry.note_id == note_id), None)
        self.query_one("#dev-log-title", Input).value = title
        self.query_one("#dev-log-editor", TextArea).text = content
        self._remember_dev_note()
        self.query_one("#dev-log-delete", Button).disabled = False
        self.query_one("#dev-log-save", Button).disabled = False
        self.query_one("#dev-log-status", Static).update("Saved note · preview mode.")
        self._set_dev_log_preview(True)

    def _set_dev_log_preview(self, visible: bool) -> None:
        editor = self.query_one("#dev-log-editor", TextArea)
        preview = self.query_one("#dev-log-preview", Static)
        empty_preview = translate("Nothing to preview yet.", self.language)
        preview.update(Markdown(editor.text or f"*{empty_preview}*"))
        editor.styles.display = "none" if visible else "block"
        preview.styles.display = "block" if visible else "none"
        self.query_one("#dev-log-preview-toggle", Button).set_source_label(
            "Edit" if visible else "Preview"
        )
        self.dev_log_previewing = visible

    def _configure_markdown_editor(self) -> None:
        """Apply live Markdown syntax styles in the editable note area."""
        editor = self.query_one("#dev-log-editor", TextArea)
        editor.register_theme(
            TextAreaTheme(
                name="42tui-markdown",
                syntax_styles={
                    "markdown.emphasis": Style(italic=True),
                    "markdown.strong": Style(bold=True),
                    "markdown.strikethrough": Style(strike=True),
                    "markdown.code": Style(color="bright_cyan"),
                    "markdown.delimiter": Style(dim=True),
                },
            )
        )
        editor.theme = "42tui-markdown"
        # The Markdown package exposes a separate inline grammar; the default
        # Textual Markdown grammar only covers block-level elements.
        inline_query = """
            (emphasis) @markdown.emphasis
            (strong_emphasis) @markdown.strong
            (strikethrough) @markdown.strikethrough
            (code_span) @markdown.code
            [(emphasis_delimiter) (code_span_delimiter)] @markdown.delimiter
            """
        try:
            import tree_sitter_markdown
            from tree_sitter import Language

            editor.register_language(
                "markdown-inline",
                Language(tree_sitter_markdown.inline_language()),
                inline_query,
            )
            editor.language = "markdown-inline"
        except Exception:
            # Keep note editing available if the optional parser cannot load.
            editor.language = None
            self.notify("Markdown live styling is unavailable; install the syntax extra.", severity="warning")

    def _begin_new_dev_note(self) -> None:
        """Clear the editor and focus the title for a new note."""
        if not self._protect_dev_note(self._begin_new_dev_note):
            return
        self.selected_note_id = None
        self.query_one("#dev-log-title", Input).value = ""
        self.query_one("#dev-log-editor", TextArea).text = ""
        self._remember_dev_note()
        self.query_one("#dev-log-delete", Button).disabled = True
        self.query_one("#dev-log-save", Button).disabled = False
        self.query_one("#dev-log-status", Static).update("New note · enter a title and Markdown content.")
        if self.dev_log_previewing:
            self._set_dev_log_preview(False)
        self.query_one("#dev-log-title", Input).focus()

    async def _new_dev_note_for_project(self, project_key: str) -> None:
        if not self._protect_dev_note(lambda: self._new_dev_note_for_project(project_key)):
            return
        self.query_one(TabbedContent).active = "dev-log"
        await self._load_dev_log_notes(project_key)
        self._begin_new_dev_note()

    async def _save_dev_note(self) -> bool:
        """Create or update the current project's Markdown note."""
        project_key = self.worklog_state.project_key
        project = self.projects.get(project_key) if isinstance(project_key, str) else None
        title = self.query_one("#dev-log-title", Input).value.strip()
        content = self.query_one("#dev-log-editor", TextArea).text
        status = self.query_one("#dev-log-status", Static)
        if project is None or project.id is None:
            status.update("Select a project before saving a note.")
            return False
        if not title:
            status.update("A note title is required.")
            self.query_one("#dev-log-title", Input).focus()
            return False
        try:
            note = self.worklog_service.save_note(project.id,self.selected_note_id,title,content)
        except NoteSaveError:
            status.update("Note not saved. Check disk space and database access, then try again.")
            return False
        if note is None:
            self.selected_note_id = None
            status.update("This note no longer exists. Save again to create it.")
            return False
        self._remember_dev_note()
        await self._load_dev_log_notes(project.ui_key)
        self._show_dev_note(note.id)
        status.update("Note saved.")
        await self._refresh_dashboard()
        if self.dev_log_previewing:
            self._set_dev_log_preview(True)
        if self.selected_project_key == project.ui_key and project.id is not None:
            self.run_worker(
                self._load_project_notes(project.id, project.ui_key),
                group="project-notes",
                exclusive=True,
            )

        return True

    def _finish_delete_dev_note(self, confirmed: bool | None) -> None:
        if not confirmed or self.selected_note_id is None:
            return
        self.worklog_service.delete_note(self.selected_note_id)
        self._remember_dev_note()
        project_key = self.query_one("#dev-log-project", Select).value
        self.selected_note_id = None
        if isinstance(project_key, str):
            self.run_worker(self._load_dev_log_notes(project_key), exclusive=True)
            project = self.projects.get(project_key)
            if project and project.id is not None and self.selected_project_key == project_key:
                self.run_worker(
                    self._load_project_notes(project.id, project_key),
                    group="project-notes",
                    exclusive=True,
                )
        self.query_one("#dev-log-status", Static).update("Note deleted.")
        self.run_worker(self._refresh_dashboard(), group="dashboard-refresh", exclusive=True)
