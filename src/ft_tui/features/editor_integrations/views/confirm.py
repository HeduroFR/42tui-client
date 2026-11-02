"""Confirmation for removing an editor integration."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical

from ft_tui.ui.components import Button, Static
from ft_tui.ui.modal import AppModal


class EditorIntegrationRemoveScreen(AppModal[bool]):
    CSS = """
    EditorIntegrationRemoveScreen { background: $background 70%; }
    #editor-remove-dialog {
        width: 72; max-width: 92%; height: auto;
        border: round $error; background: $surface; padding: 1 2;
    }
    #editor-remove-title { text-style: bold; color: $error; }
    #editor-remove-copy { color: $text-muted; margin-top: 1; }
    #editor-remove-actions { height: 3; align-horizontal: right; margin-top: 1; }
    #editor-remove-actions Button { margin-left: 1; }
    """

    def __init__(self, editor_label: str) -> None:
        super().__init__()
        self.editor_label = editor_label

    def compose(self) -> ComposeResult:
        with Vertical(id="editor-remove-dialog"):
            yield Static("Remove editor integration", id="editor-remove-title")
            yield Static(
                f"Remove the 42TUI integration for {self.editor_label}? "
                "Your editor configuration and recorded time are not changed.",
                id="editor-remove-copy",
            )
            with Horizontal(id="editor-remove-actions"):
                yield Button("Cancel", id="editor-remove-cancel")
                yield Button("Remove", variant="error", id="editor-remove-confirm")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "editor-remove-confirm")
