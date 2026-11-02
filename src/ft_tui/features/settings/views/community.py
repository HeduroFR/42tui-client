"""Small, non-modal invitations to the project community."""
import asyncio
import webbrowser

from textual.containers import Horizontal, Vertical
from ft_tui.ui.components import Button, Static

COMMUNITY_LINKS = {
    'github': 'https://tui.42wip.in/github',
    'discord': 'https://tui.42wip.in/discord',
}


class CommunityReminder(Vertical):
    DEFAULT_CSS = '''
    CommunityReminder { overlay: screen; layer: _toastrack; dock: bottom; width: 100%; height: auto;
        align: right bottom; margin-bottom: 1; }
    CommunityReminder #community-reminder-card { width: 52; max-width: 95%; height: auto;
        padding: 1 2; border: round $primary; background: $surface; }
    CommunityReminder #community-reminder-heading { height: 1; color: $accent; text-style: bold; }
    CommunityReminder #community-reminder-message { height: auto; margin: 1 0; }
    CommunityReminder #community-reminder-status { height: auto; color: $text-muted; }
    CommunityReminder #community-reminder-actions { height: 3; }
    CommunityReminder #community-reminder-open { width: auto; min-width: 0; margin-right: 2; }
    CommunityReminder #community-reminder-close { width: auto; min-width: 0; }
    '''

    def __init__(self, name):
        super().__init__(id='community-reminder')
        self.community_kind = name

    def compose(self):
        github = self.community_kind == 'github'
        with Vertical(id='community-reminder-card'):
            yield Static('★  GitHub' if github else '✦  Discord', id='community-reminder-heading', localize=False)
            yield Static('Enjoy 42TUI? Consider starring the project on GitHub.' if github else
                         'Join the 42TUI community on Discord.', id='community-reminder-message')
            yield Static('', id='community-reminder-status')
            with Horizontal(id='community-reminder-actions'):
                yield Button('Open GitHub' if github else 'Open Discord', variant='primary', id='community-reminder-open')
                yield Button('Not now', id='community-reminder-close')

    def on_mount(self):
        self.set_timer(25, self.remove)

    async def on_button_pressed(self, event: Button.Pressed):
        event.stop()
        if event.button.id == 'community-reminder-close':
            self.remove()
        elif event.button.id == 'community-reminder-open':
            try:
                opened = await asyncio.to_thread(webbrowser.open, COMMUNITY_LINKS[self.community_kind])
            except Exception:
                opened = False
            if not self.is_mounted:
                return
            if opened:
                self.remove()
            else:
                self.query_one('#community-reminder-status', Static).update('Could not open a browser. Use the link in Settings → Community.')
