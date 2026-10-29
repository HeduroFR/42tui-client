"""Keep remote checkout inspection visible and cancellable."""
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import LoadingIndicator, Static

from ft_tui.i18n import translate
from ft_tui.ui.button import AppButton
from ft_tui.ui.modal import AppModal


class ProjectCheckoutProgressScreen(AppModal):
    BINDINGS = [('escape', 'cancel', 'Cancel')]
    DEFAULT_CSS = """
    #checkout-progress-dialog { width: 72; max-width: 94%; height: auto; border: round $primary; padding: 1 2; }
    #checkout-progress-dialog Static { height: auto; }
    #checkout-progress-dialog LoadingIndicator { height: 3; }
    #checkout-progress-cancel { margin-top: 1; align-horizontal: center; }
    """

    def __init__(self, project_name: str):
        super().__init__()
        self.project_name = project_name
        self.cancelled = False

    def compose(self) -> ComposeResult:
        with Vertical(id='checkout-progress-dialog'):
            yield Static(translate('Checking project Git history…', self.app.language), classes='panel-title')
            yield Static(self.project_name, markup=False)
            yield LoadingIndicator()
            yield Static(translate('Waiting for remote Git access. Cancel prevents the editor from opening; the current Git check may finish in the background.', self.app.language))
            yield AppButton(translate('Cancel', self.app.language), id='checkout-progress-cancel')

    def action_cancel(self) -> None:
        self.cancelled = True
        self.dismiss()

    def on_button_pressed(self, event: AppButton.Pressed) -> None:
        event.stop()
        self.action_cancel()
