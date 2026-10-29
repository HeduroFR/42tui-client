"""Masked SSH authentication without handing the terminal to OpenSSH."""
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, Static

from ft_tui.i18n import translate
from ft_tui.ui.button import AppButton
from ft_tui.ui.modal import AppModal


class ProjectSshPromptScreen(AppModal[str | None]):
    BINDINGS = [('escape', 'cancel', 'Cancel')]
    DEFAULT_CSS = """
    #ssh-prompt-dialog { width: 80; max-width: 94%; height: auto; border: round $primary; padding: 1 2; }
    #ssh-prompt-dialog Static { height: auto; margin-bottom: 1; }
    #ssh-prompt-actions { height: 3; margin-top: 1; align-horizontal: center; }
    """

    def __init__(self, prompt: str, confirm: bool = False):
        super().__init__()
        self.prompt = prompt
        self.confirm = confirm

    def compose(self) -> ComposeResult:
        tr = lambda text: translate(text, self.app.language)
        with Vertical(id='ssh-prompt-dialog'):
            yield Static(tr('SSH authentication'), classes='panel-title')
            yield Static(self.prompt, markup=False)
            yield Input(password=not self.confirm, id='ssh-prompt-value')
            with Horizontal(id='ssh-prompt-actions'):
                yield AppButton(tr('Continue'), id='ssh-prompt-submit', variant='primary')
                yield AppButton(tr('Cancel'), id='ssh-prompt-cancel')

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def action_cancel(self) -> None:
        self.query_one(Input).value = ''
        self.dismiss(None)

    def _submit(self) -> None:
        field = self.query_one(Input)
        value = field.value
        field.value = ''
        self.dismiss(value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        self._submit()

    def on_button_pressed(self, event: AppButton.Pressed) -> None:
        event.stop()
        if event.button.id == 'ssh-prompt-submit':
            self._submit()
        else:
            self.action_cancel()
