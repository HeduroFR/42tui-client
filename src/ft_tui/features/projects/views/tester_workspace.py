"""Persistent tester output and controls while the rest of the app stays usable."""
import asyncio
import codecs
from collections import deque
import time

from ft_tui.features.projects.adapters.tester_console import TesterConsole
from ft_tui.features.projects.adapters.explorer import open_project_folder
from textual.containers import Horizontal, Vertical
from textual.widgets import Input, RichLog

from ft_tui.i18n import translate
from ft_tui.ui.components import Button, Static
from ft_tui.ui.modal import AppModal


class TesterWorkspace(AppModal):
    BINDINGS = [('escape', 'close', 'Close')]
    DEFAULT_CSS = """
    #tester-workspace { width: 96%; height: 92%; border: round $primary; padding: 0 1; }
    #tester-workspace Static { height: auto; }
    #tester-output { height: 1fr; padding-left: 1; }
    #tester-workspace-actions { height: auto; margin-top: 1; }
    #tester-workspace-actions Button { min-width: 0; width: 1fr; margin: 0 1; }
    #tester-input { height: 3; }
    """

    def __init__(self, title, log_path, *, rerun=None):
        super().__init__()
        self.title_text, self.log_path = title, log_path
        self.output = deque(maxlen=128)
        self.decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        self.rerun = rerun
        self.session = None
        self.started = time.monotonic()
        self.finished = None
        self.result = 'Tester operation in progress…'
        self.result_details = ''
        self.follow = True
        self.console = TesterConsole()

    def compose(self):
        with Vertical(id='tester-workspace'):
            yield Static(self.title_text, markup=False, localize=False)
            yield Static('', id='tester-result', markup=False, localize=False)
            yield RichLog(id='tester-output', max_lines=1024, min_width=100, wrap=False)
            yield Input(id='tester-input', placeholder=translate('Send input to tester', self.app.language))
            with Horizontal(id='tester-workspace-actions'):
                yield Button('Cancel', id='tester-cancel')
                yield Button('Pause output', id='tester-follow')
                yield Button('Open log folder', id='tester-log')
                yield Button('Run again', id='tester-rerun', disabled=True)
                yield Button('Close', id='tester-close')

    def on_mount(self):
        self.set_interval(.1, self.refresh_output)
        self.refresh_output()

    def refresh_output(self):
        # Timers can fire while a replaced workspace's children are unmounting.
        if not self.is_attached or not all(self.query(selector) for selector in (
                '#tester-output', '#tester-result', '#tester-rerun', '#tester-cancel', '#tester-input')):
            return
        log = self.query_one('#tester-output', RichLog)
        chunks = []
        try:
            while True:
                chunks.append(self.output.popleft())
        except IndexError:
            pass
        if chunks:
            self.console.feed(self.decoder.decode(b''.join(chunks)))
            position = log.scroll_offset
            log.clear()
            log.write(self.console.render(), scroll_end=self.follow)
            if not self.follow:
                log.scroll_to(position.x, position.y, animate=False, immediate=True)
        elapsed = (self.finished or time.monotonic()) - self.started
        self.query_one('#tester-result', Static).update(
            translate(self.session.phase if self.finished is None and self.session else self.result, self.app.language)
            + f' · {elapsed:.1f}s'
            + ('\n' + self.result_details if self.result_details else ''))
        self.query_one('#tester-rerun', Button).disabled = self.finished is None or self.rerun is None
        self.query_one('#tester-cancel', Button).disabled = self.finished is not None or bool(
            self.session and self.session.cancel_requested)
        self.query_one('#tester-input', Input).disabled = self.finished is not None

    def action_close(self):
        self.app.pop_screen()

    def on_input_submitted(self, event: Input.Submitted):
        event.stop()
        if self.session and self.finished is None:
            self.session.input.put((event.value + '\n').encode())
            event.input.value = ''

    def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == 'tester-close':
            self.action_close()
        elif event.button.id == 'tester-cancel' and self.session:
            self.session.cancel()
        elif event.button.id == 'tester-follow':
            self.follow = not self.follow
            self.query_one('#tester-output', RichLog).auto_scroll = self.follow
            event.button.label = translate('Pause output' if self.follow else 'Follow output', self.app.language)
        elif event.button.id == 'tester-rerun' and self.finished is not None and self.rerun:
            self.action_close()
            self.app.call_after_refresh(self.rerun)
        elif event.button.id == 'tester-log':
            self.run_worker(self._open_log_folder())

    async def _open_log_folder(self):
        try:
            await asyncio.to_thread(open_project_folder, str(self.log_path.parent))
        except (OSError, RuntimeError) as error:
            self.app.notify(translate('Could not open log folder: {error}', self.app.language).format(error=error),
                            severity='error', markup=False)
