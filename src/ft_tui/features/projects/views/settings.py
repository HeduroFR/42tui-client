"""Modal form for configuring a project's local checkout and Git remotes."""

from pathlib import Path
import re

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from ft_tui.ui.modal import AppModal
from textual.widgets import Input, Label, Static

from ft_tui.ui.button import Button
from ft_tui.db.models import Project
from ft_tui.i18n import translate


def suggested_checkout_path(project: Project, projects_root: str) -> str:
    """Return the saved path or a safe project slug without its cursus prefix."""
    if project.local_path:
        return project.local_path

    slug = project.slug
    if (
        not slug
        or "\x00" in slug
        or slug in {".", ".."}
        or "/" in slug
        or "\\" in slug
        or Path(slug).is_absolute()
    ):
        raise ValueError("Project slug must be a safe path component")

    # Identify the project suffix from its name, rather than guessing where a
    # cursus prefix ends: both cursus and project names can contain hyphens.
    def normalized(value: str) -> str:
        return re.sub(r"[\W_]+", "-", value.casefold()).strip("-")

    name = normalized(project.name or "")
    if name and normalized(slug) != name:
        for index, character in enumerate(slug):
            if character == "-" and normalized(slug[index + 1:]) == name:
                slug = slug[index + 1:]
                break

    try:
        root = (
            Path(projects_root).expanduser() if projects_root else Path.home() / "42"
        ).resolve(strict=False)
        checkout = (root / slug).resolve(strict=False)
    except (OSError, RuntimeError, ValueError) as error:
        raise ValueError("Suggested checkout path must stay inside the projects root") from error
    if checkout == root or root not in checkout.parents:
        raise ValueError("Suggested checkout path must stay inside the projects root")
    return str(checkout)


class ProjectSettingsScreen(AppModal[dict[str, str] | None]):
    """Collect per-project local path and the two repository remotes."""

    CSS = """
    #project-settings-dialog {
        width: 82;
        max-width: 90%;
        height: auto;
        max-height: 90%;
        padding: 1 3;
        border: round $accent;
        background: $surface;
    }
    #project-settings-kicker { color: $accent; text-style: bold; }
    #project-settings-title { text-style: bold; margin-top: 1; }
    #project-settings-intro { color: $text-muted; margin-bottom: 1; }
    .section-kicker { color: $accent; text-style: bold; }
    .form-section { border: round $secondary; padding: 0 1; margin-top: 1; height: auto; }
    .field-label { text-style: bold; margin-top: 1; }
    .field-help { color: $text-muted; margin-bottom: 1; }
    #project-settings-error { color: $error; height: auto; margin-top: 1; }
    #project-settings-actions { height: 3; margin-top: 1; align-horizontal: right; }
    #project-settings-actions Button { margin-left: 1; }
    """

    def __init__(self, project: Project, projects_root: str) -> None:
        super().__init__()
        self.project = project
        self.suggested_path = suggested_checkout_path(project, projects_root)

    def _t(self, message: str) -> str:
        """Translate modal copy using the currently selected app language."""
        return translate(message, getattr(self.app, "language", "en"))

    def compose(self) -> ComposeResult:
        with Vertical(id="project-settings-dialog"):
            yield Static(self._t("PROJECT SETUP"), id="project-settings-kicker")
            yield Static(self.project.name, id="project-settings-title")
            yield Static(
                self._t("Choose a folder and development remote. You can also create the local Git checkout now."),
                id="project-settings-intro",
            )
            with Vertical(classes="form-section"):
                yield Static(self._t("LOCAL WORKSPACE"), classes="section-kicker")
                yield Label(self._t("Project folder"), classes="field-label")
                yield Static(
                    self._t("Use an absolute path. The suggested location comes from Settings."),
                    classes="field-help",
                )
                yield Input(value=self.suggested_path, placeholder="/home/user/42/project", id="local-path")
            with Vertical(classes="form-section"):
                yield Static(self._t("DEVELOPMENT REMOTE"), classes="section-kicker")
                yield Label(self._t("GitHub or GitLab SSH / HTTPS URL"), classes="field-label")
                yield Input(
                    value=self.project.dev_repo_url or "",
                    placeholder="git@github.com:user/project.git",
                    id="dev-remote",
                )
            yield Static("", id="project-settings-error")
            with Horizontal(id="project-settings-actions"):
                yield Button(self._t("Cancel"), id="cancel-project-settings")
                yield Button(self._t("Save settings"), id="save-project-settings")
                yield Button(self._t("Save + Set Up Checkout"), variant="primary", id="setup-project-checkout")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-project-settings":
            self.dismiss(None)
            return
        if event.button.id not in {"save-project-settings", "setup-project-checkout"}:
            return

        values = {
            "local_path": self.query_one("#local-path", Input).value.strip(),
            "dev_repo_url": self.query_one("#dev-remote", Input).value.strip(),
        }
        is_setup = event.button.id == "setup-project-checkout"
        path = Path(values["local_path"]).expanduser() if values["local_path"] else None
        if is_setup and path is None:
            self.query_one("#project-settings-error", Static).update(
                self._t("Enter a project folder before setting up its checkout.")
            )
            return
        if path is not None and not path.is_absolute():
            self.query_one("#project-settings-error", Static).update(
                self._t("Enter an absolute path, such as /home/user/42/project.")
            )
            return
        if path is not None:
            values["local_path"] = str(path)
        values["setup_checkout"] = "true" if is_setup else "false"
        self.dismiss(values)
