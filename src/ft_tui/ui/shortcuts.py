"""Inline keyboard shortcuts panel for the main application screen."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from ft_tui.ui.components import Static


class ShortcutRow(Horizontal):
    """One key and description pair in the shortcut list."""

    def __init__(self, key: str, description: str) -> None:
        super().__init__(classes="shortcuts-row")
        self.key = key
        self.description = description

    def compose(self) -> ComposeResult:
        yield Static(self.key, classes="shortcuts-key", markup=False)
        yield Static(
            self.description,
            classes="shortcuts-description",
            markup=False,
            localize=True,
        )


class ShortcutsPanel(Vertical):
    """Expandable, non-modal shortcuts area that pushes the app content down."""

    DEFAULT_CSS = """
    ShortcutsPanel {
        display: none;
        width: 1fr;
        height: auto;
        padding: 0 2;
        margin-bottom: 1;
        border: round $primary;
        background: $surface;
        overflow-y: hidden;
    }
    #shortcuts-title { color: $text; text-style: bold; margin-bottom: 1; }
    #shortcuts-columns { height: auto; }
    .shortcuts-column { width: 1fr; height: auto; padding: 0 1; }
    .shortcuts-section { color: $accent; text-style: bold; margin-bottom: 1; }
    .shortcuts-row { height: 1; }
    .shortcuts-key { width: 17; color: $secondary; text-style: bold; }
    .shortcuts-description { width: 1fr; color: $text; }
    #shortcuts-footer {
        height: auto;
        color: $text-muted;
        border-top: solid $secondary;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("KEYBOARD SHORTCUTS", id="shortcuts-title")
        with Horizontal(id="shortcuts-columns"):
            with Vertical(classes="shortcuts-column"):
                yield Static("Navigation", classes="shortcuts-section")
                yield ShortcutRow("j / k", "Next / previous list item")
                yield ShortcutRow("h / l", "Previous / next tab")
                yield ShortcutRow("Alt+← / Alt+→", "Previous / next tab")
                yield ShortcutRow("Home / End", "First / last list item")
                yield ShortcutRow("Ctrl+d / Ctrl+u", "Page through list")
                yield ShortcutRow("/", "Search projects")
            with Vertical(classes="shortcuts-column"):
                yield Static("Workspace", classes="shortcuts-section")
                yield ShortcutRow("o", "Open project in editor")
                yield ShortcutRow("e", "Configure project")
                yield ShortcutRow("d", "Project Details")
                yield ShortcutRow("t", "Project testers")
                yield ShortcutRow("F2", "Projects")
                yield ShortcutRow("F3–F5", "Notes, Git status, Settings")
            with Vertical(classes="shortcuts-column"):
                yield Static("General", classes="shortcuts-section")
                yield ShortcutRow("? / F1", "Show keyboard shortcuts")
                yield ShortcutRow("q", "Quit 42TUI")
        yield Static("Press ? or ESC to close", id="shortcuts-footer")
