"""Focused friend discovery dialog using the shared directory suggestions."""
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from ft_tui.ui.modal import AppModal

from ft_tui.ui.components import Button, Input, Static
from ft_tui.features.friends.views.suggestions import FriendSuggestions


class FriendSearchScreen(AppModal):
    BINDINGS = [Binding('escape', 'cancel', show=False)]

    CSS = """
    FriendSearchScreen {  background: $background 65%; }
    #friend-search-dialog {
        width: 76; max-width: 96%; height: 24; max-height: 95%;
        padding: 1 2; border: round $primary; background: $surface;
    }
    #friend-search-title { height: 1; text-style: bold; color: $accent; }
    #friend-search-help { height: auto; color: $text-muted; margin-bottom: 1; }
    #friend-login-input { width: 1fr; }
    #friend-search-results { height: 1fr; overflow-y: auto; }
    #friend-search-actions { height: 3; align-horizontal: center; margin-top: 1; }
    #friend-search-actions Button { width: auto; min-width: 12; margin: 0 1; }
    #friend-suggestions { height: auto; max-height: 10; display: none; }
    #friend-suggestions-status { height: auto; max-height: 3; color: $text-muted; }
    #friend-suggestions-table { height: 6; scrollbar-size-horizontal: 1; }
    FriendSearchScreen.confirm-request #friend-search-dialog { height: auto; }
    """

    def __init__(self, workspace, *, purpose='friend', candidate=None):
        super().__init__()
        self.workspace = workspace
        self.purpose = purpose
        self.suggested_friend = None
        self.candidate = candidate
        self.set_class(bool(candidate), 'confirm-request')

    def compose(self):
        with Vertical(id='friend-search-dialog'):
            yield Static('Add member' if self.purpose == 'member' else 'Send friend request', id='friend-search-title')
            yield Static('Search by name or 42 login, then choose a club member to add.' if self.purpose == 'member' else 'Search by name or 42 login, then send a friend request. Friendship starts after acceptance.', id='friend-search-help')
            yield Input(placeholder='Name or 42 login', id='friend-login-input', max_length=128)
            with Vertical(id='friend-search-results'):
                yield FriendSuggestions(purpose=self.purpose)
            with Horizontal(id='friend-search-actions'):
                yield Button('Cancel', id='friend-search-cancel')
                yield Button('Add member' if self.purpose == 'member' else 'Send friend request', id='friend-add', variant='primary')

    def on_mount(self):
        for widget in self.query('*'):
            apply = getattr(widget, 'apply_language', None)
            if apply:
                apply()
        if self.candidate:
            login = self.candidate['login']
            self.suggested_friend = (login, self.candidate['user_id']) if self.candidate.get('user_id') else None
            field = self.query_one('#friend-login-input', Input)
            field.value = login
            field.display = False
            self.query_one('#friend-search-results').display = False
            from ft_tui.i18n import translate
            self.query_one('#friend-search-help', Static).update(
                translate('Send a friend request to {login}?', self.app.language).format(login=login))
            self.query_one('#friend-add', Button).focus()
            self.set_busy(self.workspace.busy or self.workspace.adding)
        else:
            self.query_one('#friend-login-input', Input).focus()

    def set_busy(self, busy):
        self.query_one('#friend-login-input', Input).disabled = busy
        add = self.query_one('#friend-add', Button)
        add.disabled = busy
        add.set_source_label('Checking login…' if self.workspace.adding else 'Add member' if self.purpose == 'member' else 'Send friend request')
        self.query_one('#friend-search-cancel', Button).disabled = busy

    def action_cancel(self):
        if not self.workspace.adding:
            self.query_one(FriendSuggestions).reset()
            self.dismiss()

    def on_unmount(self):
        if self.workspace.search_screen is self:
            self.workspace.search_screen = None

    @on(Input.Changed, '#friend-login-input')
    def search(self, event):
        event.stop()
        if self.candidate:
            return
        if self.suggested_friend and event.value != self.suggested_friend[0]:
            self.suggested_friend = None
        self.query_one(FriendSuggestions).set_query(event.value, self.workspace.watches)

    @on(FriendSuggestions.Chosen)
    def choose(self, event):
        event.stop()
        self.suggested_friend = (event.candidate['login'], event.candidate['user_id'])
        self.query_one('#friend-login-input', Input).value = event.candidate['login']
        self.query_one('#friend-add', Button).focus()

    def on_key(self, event):
        if event.key == 'down' and self.query_one('#friend-login-input', Input).has_focus:
            if self.query_one(FriendSuggestions).focus_results():
                event.prevent_default()
                event.stop()

    @on(Input.Submitted, '#friend-login-input')
    def submit(self, event):
        event.stop()
        self._add()

    @on(Button.Pressed)
    def button(self, event):
        event.stop()
        if event.button.id == 'friend-search-cancel':
            self.action_cancel()
        elif event.button.id == 'friend-add':
            self._add()

    def _add(self):
        login = self.query_one('#friend-login-input', Input).value
        suggestions = self.query_one(FriendSuggestions)
        candidate = suggestions.highlighted_candidate() if suggestions.query == login.strip() else None
        if candidate:
            self.workspace.add_friend(candidate['login'], (candidate['login'], candidate['user_id']))
        else:
            self.workspace.add_friend(login, self.suggested_friend)
