"""First-run setup wizard for a personal 42TUI workspace."""

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from ft_tui.ui.modal import AppModal
from textual.widgets import Input, Static

from ft_tui.ui.select import Select
from ft_tui.i18n import LANGUAGE_LABELS, SUPPORTED_LANGUAGES, translate
from ft_tui.ui.components import Button


class OnboardingScreen(AppModal[dict[str, str]]):
    """A short, three-step welcome wizard for first launch."""

    CSS = """
    OnboardingScreen {   background: $background 70%; }
    #onboarding-shell {
        width: 96; max-width: 96%; height: 29; max-height: 92%;
        border: round $primary; background: $surface;
    }
    #onboarding-rail { width: 30; height: 1fr; padding: 2; background: #142332; border-right: solid $primary; }
    #onboarding-brand { color: $text; text-style: bold; }
    #onboarding-brand-mark { color: $accent; text-style: bold; margin-top: 1; }
    #onboarding-rail-copy { color: $text-muted; margin-top: 1; height: auto; }
    #onboarding-motif { color: $accent; margin-top: 2; text-style: bold; }
    #onboarding-steps { height: 1fr; margin-top: 2; }
    .onboarding-stage { height: 3; padding: 0 1; color: $text-muted; }
    .onboarding-stage.-current { color: $text; background: $primary 25%; text-style: bold; }
    .onboarding-stage-number { width: 5; color: $accent; }
    .onboarding-stage-label { width: 1fr; }
    #onboarding-rail-foot { color: $text-muted; }
    #onboarding-main { width: 1fr; height: 1fr; padding: 2 3 1 3; }
    #onboarding-eyebrow { color: $accent; text-style: bold; }
    #onboarding-title { margin-top: 1; text-style: bold; }
    #onboarding-description { color: $text-muted; margin-top: 1; height: 2; }
    .onboarding-form { height: 1fr; padding-top: 1; }
    .onboarding-field-label { text-style: bold; margin-top: 1; }
    .onboarding-help { color: $text-muted; margin-top: 1; }
    #onboarding-preferences-row { height: auto; margin-top: 1; }
    #onboarding-editor-wrap { width: 1fr; margin-right: 1; }
    #onboarding-theme-wrap { width: 1fr; }
    #onboarding-language-wrap { height: auto; margin-top: 1; }
    #onboarding-error { color: $error; height: 1; }
    #onboarding-actions { height: 3; align-vertical: middle; }
    #onboarding-actions-spacer { width: 1fr; }
    #onboarding-back { width: 14; margin-right: 1; }
    #onboarding-next, #onboarding-finish { width: 18; }
    """

    def __init__(
        self,
        *,
        projects_root: str,
        favorite_editor: str,
        favorite_theme: str,
        language: str,
        themes: list[str],
        account_connected: bool = False,
        account_login: str | None = None,
    ) -> None:
        super().__init__()
        self.step = 0
        self.projects_root = projects_root
        self.favorite_editor = favorite_editor
        self.favorite_theme = favorite_theme if favorite_theme in themes else (themes[0] if themes else "textual-dark")
        self.language = language
        self.themes = themes
        self.account_connected = account_connected
        self.account_login = account_login

    def _t(self, message: str) -> str:
        return translate(message, getattr(self.app, "language", "en"))

    def _account_state(self) -> str:
        if self.account_connected and self.account_login:
            return self._t("Connected as {login}").format(login=self.account_login)
        if self.account_connected:
            return self._t("Connected · profile unavailable")
        return self._t("Not connected")

    def compose(self) -> ComposeResult:
        with Horizontal(id="onboarding-shell"):
            with Vertical(id="onboarding-rail"):
                yield Static("42TUI", id="onboarding-brand")
                yield Static(self._t("YOUR 42 WORKSPACE"), id="onboarding-brand-mark")
                yield Static(
                    self._t("A calmer home for your projects, notes and coding rhythm."),
                    id="onboarding-rail-copy",
                )
                yield Static("▂  ▄  ▆  █  ▆  ▄  ▂", id="onboarding-motif")
                with Vertical(id="onboarding-steps"):
                    for index, label in enumerate(("Your profile", "Workspace folder", "Editor & style")):
                        with Horizontal(classes="onboarding-stage", id=f"onboarding-stage-{index}"):
                            yield Static(f"0{index + 1}", classes="onboarding-stage-number")
                            yield Static(self._t(label), classes="onboarding-stage-label")
                yield Static(self._t("LOCAL FIRST · YOUR DATA STAYS HERE"), id="onboarding-rail-foot")
            with Vertical(id="onboarding-main"):
                yield Static(self._t("WELCOME  /  SETUP"), id="onboarding-eyebrow")
                yield Static(self._t("Make this space yours"), id="onboarding-title")
                yield Static(
                    self._t("A few choices now. You can change everything later in Settings."),
                    id="onboarding-description",
                )
                with Vertical(id="onboarding-form-profile", classes="onboarding-form"):
                    yield Static(self._t("42 ACCOUNT"), classes="onboarding-field-label")
                    yield Static(self._account_state(), id="onboarding-account-state")
                    yield Button(
                        self._t("Manage 42 account" if self.account_connected else "Connect 42 account"),
                        id="onboarding-connect-account",
                    )
                    yield Static(
                        self._t("Required · connect in your browser. Your password and OAuth code stay with 42."),
                        classes="onboarding-help",
                    )
                with Vertical(id="onboarding-form-workspace", classes="onboarding-form"):
                    yield Static(self._t("PROJECTS FOLDER"), classes="onboarding-field-label")
                    yield Input(value=self.projects_root, placeholder=str(Path.home() / "42"), id="onboarding-root")
                    yield Static(
                        self._t("New project checkouts will be suggested inside this folder."),
                        classes="onboarding-help",
                    )
                with Vertical(id="onboarding-form-preferences", classes="onboarding-form"):
                    with Horizontal(id="onboarding-preferences-row"):
                        with Vertical(id="onboarding-editor-wrap"):
                            yield Static(self._t("FAVORITE EDITOR"), classes="onboarding-field-label")
                            yield Select(
                                [
                                    (self._t("Neovim"), "nvim"),
                                    (self._t("Vim"), "vim"),
                                    (self._t("Visual Studio Code"), "vscode"),
                                    ("Zed", "zed"),
                                ],
                                value=self.favorite_editor,
                                id="onboarding-editor",
                            )
                        with Vertical(id="onboarding-theme-wrap"):
                            yield Static(self._t("FAVORITE THEME"), classes="onboarding-field-label")
                            yield Select(
                                [(name.replace("-", " ").title(), name) for name in self.themes],
                                value=self.favorite_theme,
                                id="onboarding-theme",
                            )
                    with Vertical(id="onboarding-language-wrap"):
                        yield Static(self._t("LANGUAGE"), classes="onboarding-field-label")
                        yield Select(
                            [(LANGUAGE_LABELS[code], code) for code in SUPPORTED_LANGUAGES],
                            value=self.language,
                            allow_blank=False,
                            id="onboarding-language",
                        )
                    yield Static(self._t("Your choices are saved on this device."), classes="onboarding-help")
                yield Static("", id="onboarding-error")
                with Horizontal(id="onboarding-actions"):
                    yield Static("", id="onboarding-actions-spacer")
                    yield Button(self._t("Back"), id="onboarding-back")
                    yield Button(self._t("Continue"), variant="primary", id="onboarding-next")
                    yield Button(self._t("Finish setup"), variant="primary", id="onboarding-finish")

    def on_mount(self) -> None:
        self._show_step()
        self.query_one("#onboarding-connect-account", Button).focus()

    def _show_step(self) -> None:
        selectors = (
            "#onboarding-form-profile",
            "#onboarding-form-workspace",
            "#onboarding-form-preferences",
        )
        for index, selector in enumerate(selectors):
            self.query_one(selector).styles.display = "block" if index == self.step else "none"
            stage = self.query_one(f"#onboarding-stage-{index}")
            if index == self.step:
                stage.add_class("-current")
            else:
                stage.remove_class("-current")
        self.query_one("#onboarding-back", Button).styles.display = "block" if self.step > 0 else "none"
        self.query_one("#onboarding-next", Button).styles.display = "block" if self.step < 2 else "none"
        self.query_one("#onboarding-finish", Button).styles.display = "block" if self.step == 2 else "none"
        titles = ("Connect your 42 account", "Choose your workspace folder", "Pick your tools")
        descriptions = (
            "Connect in your browser. 42TUI never sees your 42 password.",
            "42TUI will use this as the default home for your project checkouts.",
            "Choose the editor and look you want when you open 42TUI.",
        )
        self.query_one("#onboarding-title", Static).update(self._t(titles[self.step]))
        self.query_one("#onboarding-description", Static).update(self._t(descriptions[self.step]))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "onboarding-connect-account":
            self.app.open_account_connection("onboarding")
        elif event.button.id == "onboarding-back":
            self.step = max(0, self.step - 1)
            self._show_step()
            self._focus_current_step()
        elif event.button.id == "onboarding-next":
            self._continue()
        elif event.button.id == "onboarding-finish":
            self._finish()

    def _continue(self) -> None:
        if not self._valid_account():
            return
        if self.step == 1 and not self._valid_root():
            return
        self.step = min(2, self.step + 1)
        self._show_step()
        self._focus_current_step()

    def _focus_current_step(self) -> None:
        selector = ("#onboarding-connect-account", "#onboarding-root", "#onboarding-editor")[self.step]
        widget_type = Button if self.step == 0 else Input if self.step == 1 else Select
        self.query_one(selector, widget_type).focus()

    def _valid_root(self) -> bool:
        root = Path(self.query_one("#onboarding-root", Input).value.strip() or Path.home() / "42").expanduser()
        if not root.is_absolute():
            self.query_one("#onboarding-error", Static).update(self._t("Enter an absolute projects folder path."))
            self.query_one("#onboarding-root", Input).focus()
            return False
        self.query_one("#onboarding-error", Static).update("")
        return True

    def _valid_account(self) -> bool:
        if not self.app.account_connected:
            self.step = 0
            self._show_step()
            self._focus_current_step()
            self.query_one("#onboarding-error", Static).update(self._t("Connect your 42 account"))
            return False
        self.query_one("#onboarding-error", Static).update("")
        return True

    def _finish(self) -> None:
        if not self._valid_account():
            return
        if not self._valid_root():
            self.step = 1
            self._show_step()
            self._focus_current_step()
            return
        self.dismiss({
            "projects_root": str(
                Path(
                    self.query_one("#onboarding-root", Input).value.strip()
                    or Path.home() / "42"
                ).expanduser()
            ),
            "favorite_editor": str(self.query_one("#onboarding-editor", Select).value),
            "favorite_theme": str(self.query_one("#onboarding-theme", Select).value),
            "language": str(self.query_one("#onboarding-language", Select).value),
        })
