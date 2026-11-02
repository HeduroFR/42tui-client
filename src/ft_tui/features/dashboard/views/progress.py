"""Accessible project lists for dashboard progress segments."""
from rich.text import Text
from textual import events
from textual.containers import Vertical, VerticalScroll
from ft_tui.i18n import translate
from ft_tui.ui.components import Button, Static
from ft_tui.ui.modal import AppModal


class ProgressProjects(AppModal):
    CSS = '''
    #progress-projects-dialog { width: 60; max-width: 90%; height: auto; max-height: 85%; border: round $primary; background: $surface; padding: 1 2; }
    #progress-projects-title { height: 1; text-style: bold; color: $accent; }
    #progress-projects-list { height: auto; max-height: 1fr; margin: 1 0; }
    #progress-projects-close { width: auto; }
    '''
    BINDINGS = [('escape', 'close', 'Close')]

    def __init__(self, title, names):
        super().__init__()
        self.title_text, self.names = title, names

    def compose(self):
        with Vertical(id='progress-projects-dialog'):
            yield Static(f'{self.title_text} · {len(self.names)}', id='progress-projects-title', markup=False)
            with VerticalScroll(id='progress-projects-list'):
                yield Static('\n'.join(f'• {name}' for name in self.names) if self.names else translate('No projects in this status.', self.app.language), markup=False)
            yield Button('Close', id='progress-projects-close')

    def on_mount(self):
        if self.names:
            self.query_one('#progress-projects-list', VerticalScroll).focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == 'progress-projects-close':
            self.dismiss()

    def action_close(self):
        self.dismiss()


class ProgressSegment(Static):
    def set_projects(self, title, names, color):
        self.project_title = title
        self.project_names = names
        empty = translate('No projects in this status.', self.app.language)
        preview = Text()
        preview.append(f'● {title} · {len(names)}', style=f'bold {color}')
        preview.append('\n' + ('\n'.join(names[:8]) if names else empty))
        if len(names) > 8:
            preview.append('\n' + translate('Open for all projects.', self.app.language), style='dim')
        self.tooltip = preview

    def on_click(self, event: events.Click):
        event.stop()
        self.app.push_screen(ProgressProjects(self.project_title, self.project_names))


class ProgressLegend(ProgressSegment):
    can_focus = True
    BINDINGS = [('enter', 'open_projects', 'Show projects'), ('space', 'open_projects', 'Show projects')]

    def action_open_projects(self):
        self.app.push_screen(ProgressProjects(self.project_title, self.project_names))
