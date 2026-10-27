"""Secondary, scrollable project metadata."""
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from ft_tui.ui.modal import AppModal
from textual.widgets import Static
from ft_tui.ui.button import Button
from ft_tui.i18n import translate


class ProjectTechnicalDetailsScreen(AppModal):
    BINDINGS = [('escape', 'close', 'Close')]
    DEFAULT_CSS = """
    ProjectTechnicalDetailsScreen {  background: $background 70%; }
    #technical-dialog { width: 85%; height: 80%; border: round $primary; padding: 1 2; }
    #technical-scroll { height: 1fr; }
    #technical-content { height: auto; }
    #close-technical-details { margin-top: 1; }
    """

    def __init__(self, content: str) -> None:
        super().__init__()
        self.content = content

    def compose(self) -> ComposeResult:
        with Vertical(id='technical-dialog'):
            yield Static(translate('Project Details', self.app.language), classes='panel-title')
            with VerticalScroll(id='technical-scroll'):
                yield Static(self.content, id='technical-content')
            yield Button(translate('Close', self.app.language), id='close-technical-details', variant='danger')

    def action_close(self) -> None:
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss()
