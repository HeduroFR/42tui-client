"""Secondary, scrollable project metadata."""
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from ft_tui.ui.modal import AppModal
from textual.widgets import Static
from ft_tui.ui.button import Button
from ft_tui.i18n import translate


class ProjectTechnicalDetailsScreen(AppModal):
    BINDINGS = [('escape', 'close', 'Close')]
    DEFAULT_CSS = """
    ProjectTechnicalDetailsScreen {  background: $background 70%; }
    #technical-dialog { width: 96; max-width: 94%; height: 80%; max-height: 42; border: round $primary; padding: 1 2; }
    #technical-project-name { height: auto; text-style: bold; margin-bottom: 1; }
    #technical-scroll { height: 1fr; }
    #technical-content, .technical-section { height: auto; }
    .technical-section { padding: 0 1; margin-bottom: 1; border-left: solid $secondary; }
    .technical-section Static { height: auto; }
    #technical-actions { height: 3; margin-top: 1; align-horizontal: center; }
    """

    def __init__(self, sections: tuple[tuple[str, str], ...], *, project_name: str) -> None:
        super().__init__()
        self.sections = sections
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        with Vertical(id='technical-dialog'):
            yield Static(translate('Project Details', self.app.language), classes='panel-title')
            yield Static(self.project_name, id='technical-project-name', markup=False)
            with VerticalScroll(id='technical-scroll'):
                with Vertical(id='technical-content'):
                    for title, content in self.sections:
                        with Vertical(classes='technical-section'):
                            yield Static(translate(title, self.app.language), classes='panel-title')
                            yield Static(content)
            with Horizontal(id='technical-actions'):
                yield Button(translate('Close', self.app.language), id='close-technical-details')

    def action_close(self) -> None:
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss()
