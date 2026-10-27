"""Shared widgets, labels, and UI dependencies used across screens."""

from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import shutil
import subprocess
import os
import platform

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload
from rich.markup import escape
from rich.markdown import Markdown
from rich.style import Style
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from ft_tui.ui.modal import AppModal
from textual.widgets import (
    Footer,
    Header,
    Input,
    ListItem,
    ListView,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)
from textual.widgets.text_area import TextAreaTheme

from ft_tui.db.models import ActivityHeartbeat, DevNote, Project, TimeLog
from ft_tui.i18n import translate, translate_renderable
from ft_tui.i18n import LANGUAGE_LABELS, SUPPORTED_LANGUAGES
from ft_tui.features.projects.adapters.git import inspect_repository
from ft_tui.features.projects.adapters.checkout import (
    CheckoutResult,
    CheckoutSetupError,
    setup_project_checkout,
)


from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.features.worklog.adapters.accounting import (
    IDLE_TIMEOUT_SECONDS,
    active_manual_timer,
    tracked_seconds,
)
from ft_tui.features.projects.subjects.adapters.files import (
    PDFCheckError,
    compare_subject_hashes,
    ensure_pdf_gitignore,
    sha256_pdf,
)
from ft_tui.ui.select import Select
from ft_tui.ui.button import Button
from ft_tui.ui.terminal_capabilities import icon_glyph, icon_mode, icon_prefix
from ft_tui.features.projects.views.settings import ProjectSettingsScreen


def _widget_icon_mode(widget):
    from textual._context import NoActiveAppError
    try:
        return icon_mode(widget.app)
    except NoActiveAppError:
        return icon_mode(None)


def has_local_folder(local_path: str | None) -> bool:
    """Return whether a project's saved local path currently points to a directory."""
    return bool(local_path and Path(local_path).expanduser().is_dir())


class LocalizedStatic(Static):
    """A Static widget that retains its source text and follows the app locale."""

    def __init__(self, content="", *args, **kwargs) -> None:
        self._source_content = content
        self._localize = kwargs.pop("localize", kwargs.get("markup", True))
        super().__init__(translate_renderable(content, "en"), *args, **kwargs)

    def _language(self) -> str:
        try:
            return self.app.language
        except Exception:
            return "en"

    def update(self, *renderables) -> None:
        if len(renderables) == 1:
            self._source_content = renderables[0]
            localized = (
                translate_renderable(self._source_content, self._language())
                if self._localize
                else self._source_content
            )
            renderables = (localized,)
        super().update(*renderables)

    def apply_language(self) -> None:
        """Re-render the original message after the user changes language."""
        content = (
            translate_renderable(self._source_content, self._language())
            if self._localize
            else self._source_content
        )
        super().update(content)


Static = LocalizedStatic


class LocalizedButton(Button):
    """Button whose label can be refreshed when the selected locale changes."""

    def __init__(self, label, *args, **kwargs) -> None:
        self._source_label = label
        self.icon = kwargs.pop('icon', '')
        self.icon_only = kwargs.pop('icon_only', False)
        self._auto_square = 'square' not in kwargs
        kwargs.setdefault('square',self.icon_only and bool(icon_glyph(self.icon,_widget_icon_mode(self))))
        self._source_tooltip = kwargs.get('tooltip', label if self.icon_only else None)
        if self.icon_only:
            kwargs['tooltip'] = self._source_tooltip
            if icon_glyph(self.icon, _widget_icon_mode(self)):
                kwargs['classes'] = ((kwargs.get('classes') or '') + ' icon-button').strip()
        super().__init__(self._localized_label('en'), *args, **kwargs)

    def _localized_label(self, language):
        label = translate_renderable(self._source_label, language)
        mode = _widget_icon_mode(self)
        glyph = icon_glyph(self.icon, mode)
        if self.icon_only and glyph:
            return glyph
        return f'{icon_prefix(self.icon, mode)}{label}' if glyph else label

    def apply_language(self) -> None:
        try:
            language = self.app.language
        except Exception:
            language = "en"
        self.label = self._localized_label(language)
        self.set_class(self.icon_only and bool(icon_glyph(self.icon, _widget_icon_mode(self))), 'icon-button')
        if self._auto_square:
            self.square=self.icon_only and bool(icon_glyph(self.icon,_widget_icon_mode(self)))
        if self._source_tooltip is not None:
            self.tooltip = translate_renderable(self._source_tooltip, language)

    def set_source_label(self, label) -> None:
        """Set a dynamic English label while preserving future locale changes."""
        self._source_label = label
        self.apply_language()

    def set_source_tooltip(self, tooltip) -> None:
        """Refresh a dynamic tooltip through the same locale path as its label."""
        self._source_tooltip = tooltip
        self.apply_language()


class LocalizedInput(Input):
    """Input that retains and translates its placeholder."""

    def __init__(self, *args, **kwargs) -> None:
        self._source_placeholder = kwargs.get("placeholder", "")
        super().__init__(*args, **kwargs)

    def apply_language(self) -> None:
        try:
            language = self.app.language
        except Exception:
            language = "en"
        self.placeholder = translate(self._source_placeholder, language)


class LocalizedSelect(Select):
    """Select that keeps source option labels for repeatable locale changes."""

    def __init__(self, options, *args, **kwargs) -> None:
        self._source_options = list(options)
        self._source_prompt = kwargs.get("prompt", "")
        self._localize_options = kwargs.pop("localize_options", True)
        super().__init__(self._localized_options("en"), *args, **kwargs)

    def _localized_options(self, language: str):
        return [
            (translate(label, language) if self._localize_options and isinstance(label, str) else label, value)
            for label, value in self._source_options
        ]

    def apply_language(self) -> None:
        try:
            language = self.app.language
        except Exception:
            language = "en"
        selected = self.value
        # Rebuilding labels briefly selects option zero. These are presentation
        # changes, so neither that intermediate value nor the restored selection
        # may trigger account/cursus/filter changes in the application.
        with self.prevent(self.Changed):
            super().set_options(self._localized_options(language))
            if selected in self._legal_values:
                self.value = selected
            self.prompt = translate(self._source_prompt, language)

    def set_options(self, options) -> None:
        self._source_options = list(options)
        try:
            language = self.app.language
        except Exception:
            language = "en"
        super().set_options(self._localized_options(language))


Static = LocalizedStatic
Button = LocalizedButton
Input = LocalizedInput
Select = LocalizedSelect


class LocalizedTabPane(TabPane):
    """Tab pane with a source title that can be translated in place."""

    def __init__(self, title, *args, **kwargs) -> None:
        self._source_title = title
        self.icon = kwargs.pop('icon', '')
        try:
            language = self.app.language
        except Exception:
            language = "en"
        super().__init__(self.localized_title(language), *args, **kwargs)

    def localized_title(self, language):
        title = translate(self._source_title, language)
        return icon_prefix(self.icon, _widget_icon_mode(self)) + title

    def apply_language(self) -> None:
        try:
            language = self.app.language
        except Exception:
            language = "en"
        self._title = self.render_str(self.localized_title(language))


TabPane = LocalizedTabPane


DEFAULT_SUBJECT_CHECK_INTERVAL = 6 * 60 * 60
SUBJECT_CHECK_INTERVALS = {
    "3600": "Every hour",
    "21600": "Every 6 hours",
    "43200": "Every 12 hours",
    "86400": "Once a day",
}


def _note_updated_label(updated_at: datetime | None) -> str:
    """Format a note's local database timestamp for compact list display."""
    return f"Updated {updated_at:%d-%m-%Y %H:%M}" if updated_at else "Update time unavailable"


PROJECT_STATE_CLASSES = ('state-active', 'state-done', 'state-available', 'state-failed', 'state-inactive', 'state-locked')


class ProjectRankHeader(ListItem):
    """Selectable rank divider; Enter or click expands or collapses its projects."""

    def __init__(self, rank, projects, group_key, *, collapsed=False):
        super().__init__(classes="project-rank-header")
        self.rank, self.group_key = rank, group_key
        self.collapsed = collapsed
        self.styles.pointer = "pointer"
        self.update_projects(projects)

    def compose(self) -> ComposeResult:
        with Horizontal(classes='rank-header-content'):
            yield Static(self._label(), classes='rank-header-label', markup=False, localize=False)
            yield Static(f'{self.completed}/{self.count}', classes='rank-header-progress', markup=False)

    def update_projects(self, projects):
        statuses = [project.status for project in projects]
        self.count = len(statuses)
        self.completed = sum(status in ('completed', 'done') for status in statuses)
        self.state = ('state-done' if self.count and self.completed == self.count else
                      'state-active' if 'in_progress' in statuses else
                      'state-failed' if 'failed' in statuses else
                      'state-available' if self.completed or 'available' in statuses else 'state-inactive')
        for name in PROJECT_STATE_CLASSES:
            self.set_class(self.state == name, name)
        if self.is_mounted:
            try:
                self.query_one('.rank-header-progress', Static).update(f'{self.completed}/{self.count}')
            except NoMatches:
                pass  # The previous list can be clearing while activity refreshes.

    def _label(self):
        label = 'Unranked projects' if self.rank is None else f'Rank {self.rank}'
        return f"{'▶' if self.collapsed else '▼'} {translate(label, self.app.language)}"

    def apply_language(self):
        self.query_one('.rank-header-label', Static).update(self._label())


class ProjectEntry(ListItem):
    """Compact two-line project row with a clear state and setup hint."""

    def __init__(self, project: Project, *, active: bool = False) -> None:
        super().__init__(classes="project-entry")
        self.styles.pointer = "pointer"
        self.project = project
        self.key = project.ui_key
        self.active = active
        self.set_class(project.catalog_data.get('kind') == 'exam', 'exam-entry')

    def compose(self) -> ComposeResult:
        state = self.project.status
        with Vertical(classes="project-entry-content"):
            yield Static('★ EXAM', classes='project-exam-badge')
            yield Static(self._name_label(), classes=f"project-name {self._state_class(state)}", markup=False)
            with Horizontal(classes="project-entry-meta"):
                yield Static(self._status_label(state), classes=f"project-state {self._state_class(state)}")
                yield Static(self._local_state(), classes="project-local-state")
                score = self.project.last_defense_score if state in {"completed", "done", "failed"} else None
                yield Static(
                    f"{score:g}" if score is not None else "",
                    classes=f"project-score {self._state_class(state)}",
                    markup=False,
                )

    @staticmethod
    def _status_label(status: str) -> str:
        return {
            "in_progress": "ACTIVE",
            "completed": "DONE",
            "failed": "FAILED",
            "available": "AVAILABLE",
            "locked": "LOCKED",
            "unknown": "INACTIVE",
            "inactive": "INACTIVE",
        }.get(status, status.upper())

    @staticmethod
    def _state_class(status: str) -> str:
        return {
            "in_progress": "state-active",
            "completed": "state-done",
            "done": "state-done",
            "failed": "state-failed",
            "available": "state-available",
            "locked": "state-locked",
            "unknown": "state-inactive",
            "inactive": "state-inactive",
        }.get(status, "state-available")

    def _local_state(self) -> str:
        if has_local_folder(self.project.local_path):
            return "PATH SET"
        return "PATH MISSING" if self.project.local_path else "SETUP"

    def _name_label(self) -> str:
        try:
            language = self.app.language
        except Exception:
            language = "en"
        active_label = translate("  • ACTIVE", language) if self.active else ""
        return f"{self.project.name}{active_label}"

    def refresh_language(self) -> None:
        """Refresh translated metadata while keeping the project name intact."""
        try:
            name = self.query_one(".project-name", Static)
            status = self.query_one(".project-state", Static)
            local_state = self.query_one(".project-local-state", Static)
        except NoMatches:
            # List items can briefly remain in their parent's child list while
            # Textual is clearing/recomposing their contents.
            return
        name.update(self._name_label())
        status.update(self._status_label(self.project.status))
        local_state.update(self._local_state())

    def update_project(self, project: Project) -> None:
        """Refresh the visible row after project setup has been saved."""
        self.project = project
        self.key = project.ui_key
        self.set_class(project.catalog_data.get('kind') == 'exam', 'exam-entry')
        try:
            name = self.query_one(".project-name", Static)
            status = self.query_one(".project-state", Static)
            local_state = self.query_one(".project-local-state", Static)
            score_label = self.query_one(".project-score", Static)
        except NoMatches:
            # Preserve the new model; compose() will render it if this row is
            # mounted again after the current list rebuild.
            return
        name.update(self._name_label())
        status.update(self._status_label(project.status))
        for class_name in PROJECT_STATE_CLASSES:
            status.remove_class(class_name)
            name.remove_class(class_name)
            score_label.remove_class(class_name)
        status.add_class(self._state_class(project.status))
        name.add_class(self._state_class(project.status))
        score_label.add_class(self._state_class(project.status))
        local_state.update(self._local_state())
        score = project.last_defense_score if project.status in {"completed", "done", "failed"} else None
        score_label.update(f"{score:g}" if score is not None else "")


class DevNoteEntry(ListItem):
    """A selectable note row in the Dev Log sidebar."""

    def __init__(self, note_id: int, title: str, updated_at: datetime | None) -> None:
        super().__init__(classes="dev-log-note")
        self.styles.pointer = "pointer"
        self.note_id = note_id
        self.title = title
        self.updated_at = updated_at

    def compose(self) -> ComposeResult:
        yield Static(self.title, classes="dev-log-note-title", markup=False)
        yield Static(
            _note_updated_label(self.updated_at),
            classes="dev-log-note-date",
            markup=False,
            localize=True,
        )


class ProjectNoteEntry(ListItem):
    """A recent project note that opens the matching Dev Log entry."""

    def __init__(self, note_id: int, project_key: str, title: str, updated_at: datetime | None) -> None:
        super().__init__(classes="project-note-entry")
        self.styles.pointer = "pointer"
        self.note_id = note_id
        self.project_key = project_key
        self.title = title
        self.updated_at = updated_at

    def compose(self) -> ComposeResult:
        yield Static(self.title, markup=False)
        yield Static(
            _note_updated_label(self.updated_at),
            classes="dev-log-note-date",
            markup=False,
            localize=True,
        )


class DashboardNoteEntry(ListItem):
    """A recent note shortcut showing its owning project and edit time."""

    def __init__(
        self,
        note_id: int,
        project_key: str,
        project_name: str,
        title: str,
        updated_at: datetime | None,
    ) -> None:
        super().__init__(classes="dashboard-note-entry")
        self.styles.pointer = "pointer"
        self.note_id = note_id
        self.project_key = project_key
        self.project_name = project_name
        self.title = title
        self.updated_at = updated_at

    def compose(self) -> ComposeResult:
        yield Static(self.title, classes="dashboard-note-title", markup=False)
        yield Static(self._meta_label(), classes="dashboard-note-meta", markup=False)

    def _meta_label(self) -> str:
        try:
            language = self.app.language
        except Exception:
            language = "en"
        date = self.updated_at.strftime("%d-%m-%Y %H:%M") if self.updated_at else None
        updated = (
            translate("Updated {date}", language).format(date=date)
            if date
            else translate("Time unavailable", language)
        )
        return f"{self.project_name} · {updated}"

    def refresh_language(self) -> None:
        self.query_one(".dashboard-note-meta", Static).update(self._meta_label())


class FriendEntry(ListItem):
    """Clickable friend row in the local friends list."""

    def __init__(self, friend_id: int, login: str, project_count: int) -> None:
        super().__init__(classes="friend-entry")
        self.styles.pointer = "pointer"
        self.friend_id = friend_id
        self.login = login
        self.project_count = project_count

    def compose(self) -> ComposeResult:
        yield Static(self.login, classes="friend-login", markup=False)
        yield Static(
            translate("{count} tracked projects", "en").format(count=self.project_count),
            classes="friend-meta", markup=False,
        )


class FriendProgressEntry(ListItem):
    """Clickable manual progress row for a friend."""

    def __init__(
        self,
        progress_id: int,
        project_id: int,
        project_name: str,
        status: str,
        updated_at: datetime | None,
    ) -> None:
        super().__init__(classes="friend-progress-entry")
        self.styles.pointer = "pointer"
        self.progress_id = progress_id
        self.project_id = project_id
        self.project_name = project_name
        self.status = status
        self.updated_at = updated_at

    def compose(self) -> ComposeResult:
        yield Static(self._project_name, classes="friend-progress-name", markup=False)
        date = self.updated_at.strftime("%d-%m-%Y %H:%M") if self.updated_at else ""
        yield Static(f"{self._status_label()} · {date}", classes="friend-progress-meta", markup=False)

    def _status_label(self) -> str:
        labels = {"in_progress": "In progress", "blocked": "Blocked", "completed": "Completed"}
        return labels.get(self.status, self.status)


class ConfirmDeleteNoteScreen(AppModal[bool]):
    """Confirm deletion of a single local dev note."""

    CSS = """
    #confirm-note-dialog {
        width: 54; max-width: 90%; height: auto; padding: 1 2;
        border: round $error; background: $surface;
    }
    #confirm-note-actions { height: 3; align-horizontal: right; margin-top: 1; }
    #confirm-note-actions Button { margin-left: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-note-dialog"):
            yield Static("Delete this note? This cannot be undone.")
            with Horizontal(id="confirm-note-actions"):
                yield Button("Cancel", id="cancel-delete-note")
                yield Button("Delete note", variant="error", id="confirm-delete-note")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-delete-note")


__all__ = [
    "ActivityHeartbeat",
    "Button",
    "CheckoutResult",
    "CheckoutSetupError",
    "ComposeResult",
    "ConfirmDeleteNoteScreen",
    "DEFAULT_SUBJECT_CHECK_INTERVAL",
    "DashboardNoteEntry",
    "DevNote",
    "DevNoteEntry",
    "Footer",
    "FriendEntry",
    "FriendProgressEntry",
    "Header",
    "Horizontal",
    "IDLE_TIMEOUT_SECONDS",
    "Input",
    "Iterable",
    "LANGUAGE_LABELS",
    "ListView",
    "Markdown",
    "PDFCheckError",
    "Path",
    "Project",
    "ProjectEntry",
    "ProjectRankHeader",
    "ProjectNoteEntry",
    "ProjectSettingsScreen",
    "SUBJECT_CHECK_INTERVALS",
    "SUPPORTED_LANGUAGES",
    "Select",
    "Session",
    "Static",
    "Style",
    "TabPane",
    "TabbedContent",
    "TextArea",
    "TextAreaTheme",
    "TimeLog",
    "Vertical",
    "active_manual_timer",
    "compare_subject_hashes",
    "date",
    "datetime",
    "ensure_pdf_gitignore",
    "escape",
    "func",
    "has_local_folder",
    "inspect_repository",
    "os",
    "platform",
    "save_settings",
    "select",
    "selectinload",
    "setup_project_checkout",
    "sha256_pdf",
    "shutil",
    "subprocess",
    "timedelta",
    "timezone",
    "tracked_seconds",
    "translate",
]
