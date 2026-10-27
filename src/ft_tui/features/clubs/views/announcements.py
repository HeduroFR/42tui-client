"""An announcement stays editable until the server confirms publication."""
from datetime import datetime
from uuid import uuid4

from rich.text import Text
from textual import on
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, ContentSwitcher, TextArea
from ft_tui.i18n import translate
from ft_tui.ui.components import Button, Horizontal, Input, Static, Vertical
from ft_tui.ui.modal import AppModal


class AnnouncementComposer(AppModal[None]):
    DEFAULT_CSS = """
    AnnouncementComposer > Vertical { width: 72; max-width: 96%; height: auto; max-height: 94%;
        border: round $accent; padding: 1 2; background: $surface; }
    AnnouncementComposer #announcement-heading { text-style: bold; height: auto; }
    AnnouncementComposer #announcement-destination { color: $text-muted; height: auto; margin-bottom: 1; }
    AnnouncementComposer ContentSwitcher { height: auto; max-height: 32; }
    AnnouncementComposer VerticalScroll { height: auto; max-height: 32; }
    AnnouncementComposer Static { height: auto; }
    AnnouncementComposer Input { margin-bottom: 1; }
    AnnouncementComposer TextArea { height: 6; margin-bottom: 1; }
    AnnouncementComposer .announcement-actions { height: 3; margin-top: 1; }
    AnnouncementComposer Button { width: auto; min-width: 12; margin-right: 1; }
    AnnouncementComposer #announcement-error { height: auto; color: $error; }
    AnnouncementComposer #announcement-preview-title { text-style: bold; margin: 1 0; }
    AnnouncementComposer #announcement-preview-body { margin: 1 0; }
    """
    BINDINGS = [('escape', 'cancel', 'Cancel')]

    def __init__(self, workspace, club_id, destination, actor_login):
        super().__init__()
        self.workspace = workspace
        self.club_id = club_id
        self.destination = destination
        self.actor_login = actor_login
        self.context = workspace.scope()
        self.draft = None
        self.busy = False

    def t(self, text):
        return translate(text, getattr(self.app, 'language', 'en'))

    def compose(self):
        with Vertical():
            yield Static('New announcement', id='announcement-heading')
            yield Static(self.t('Destination: {name}').format(name=self.destination), id='announcement-destination', markup=False, localize=False)
            with ContentSwitcher(initial='announcement-editor', id='announcement-pages'):
                with VerticalScroll(id='announcement-editor'):
                    yield Static('Title')
                    yield Input(placeholder='What is happening?', max_length=100, id='announcement-title')
                    yield Static('Message')
                    yield TextArea(id='announcement-message')
                    with Collapsible(title=self.t('More options'), collapsed=True):
                        yield Static('Meeting point (optional)')
                        yield Input(max_length=200, id='announcement-location')
                        yield Static('Event date/time with timezone (optional)')
                        yield Input(placeholder='2026-12-01T18:00+01:00', id='announcement-event-at')
                        yield Static('Visible for (minutes)')
                        yield Input('120', type='integer', id='announcement-minutes')
                with VerticalScroll(id='announcement-preview-page'):
                    yield Static('', id='announcement-preview-destination', markup=False, localize=False)
                    yield Static('', id='announcement-preview-title', markup=False, localize=False)
                    yield Static('', id='announcement-preview-meta', markup=False, localize=False)
                    yield Static('', id='announcement-preview-body', markup=False, localize=False)
                    yield Static('', id='announcement-preview-author', markup=False, localize=False)
            yield Static('', id='announcement-error')
            with Horizontal(classes='announcement-actions'):
                yield Button('Cancel', id='announcement-cancel')
                yield Button('Edit', id='announcement-edit')
                yield Button('Preview', id='announcement-preview', variant='primary')
                yield Button('Publish', id='announcement-publish', variant='primary')

    def on_mount(self):
        self.set_preview(False)
        self.query_one('#announcement-title', Input).focus()

    def set_preview(self, preview):
        self.query_one('#announcement-pages', ContentSwitcher).current = 'announcement-preview-page' if preview else 'announcement-editor'
        self.query_one('#announcement-edit', Button).display = preview
        self.query_one('#announcement-publish', Button).display = preview
        self.query_one('#announcement-preview', Button).display = not preview

    def action_cancel(self):
        if not self.busy:
            self.dismiss(None)

    def preview(self):
        try:
            title = self.query_one('#announcement-title', Input).value.strip()
            message = self.query_one('#announcement-message', TextArea).text.strip()
            minutes = int(self.query_one('#announcement-minutes', Input).value)
            if (not 1 <= len(title) <= 100 or not 1 <= len(message) <= 2000 or not 1 <= minutes <= 10080
                    or any(ord(c) < 32 and c not in '\n\t' or ord(c) == 127 for c in title + message)):
                raise ValueError()
            candidate = {'action': 'announcement', 'title': title, 'message': message, 'minutes': minutes}
            location = self.query_one('#announcement-location', Input).value.strip()
            date = self.query_one('#announcement-event-at', Input).value.strip()
            if location:
                candidate['location'] = location
            if date:
                parsed = datetime.fromisoformat(date.replace('Z', '+00:00'))
                if parsed.tzinfo is None:
                    raise ValueError()
                candidate['event_at'] = parsed.isoformat()
        except (ValueError, OverflowError):
            self.query_one('#announcement-error', Static).update('Check the title, message, duration and timezone.')
            return
        # Retry an unchanged draft with the same UUID after an unknown outcome.
        old = {k: v for k, v in (self.draft or {}).items() if k != 'id'}
        self.draft = {**candidate, 'id': self.draft['id'] if old == candidate else str(uuid4())}
        self.query_one('#announcement-preview-destination', Static).update(self.t('Publish to {name}').format(name=self.destination))
        self.query_one('#announcement-preview-title', Static).update(title)
        self.query_one('#announcement-preview-meta', Static).update(' · '.join(v for v in (location, candidate.get('event_at')) if v))
        self.query_one('#announcement-preview-body', Static).update(message)
        self.query_one('#announcement-preview-author', Static).update(self.t('Published by {login}').format(login=self.actor_login or self.context[1]))
        self.query_one('#announcement-error', Static).update('')
        self.set_preview(True)
        self.query_one('#announcement-publish', Button).focus()

    async def publish(self):
        if self.busy or not self.draft:
            return
        if self.context != self.workspace.scope() or not self.workspace.connected():
            self.query_one('#announcement-error', Static).update('Account changed. Close this draft and reconnect.')
            return
        self.busy = True
        for button in self.query(Button):
            button.disabled = True
        try:
            result = await self.workspace.service.mutate(
                self.app.provider, dict(self.draft),
                lambda: self.context == self.workspace.scope() and self.workspace.connected(),
                club_id=self.club_id,
            )
            if result is None:
                if self.context != self.workspace.scope():
                    self.dismiss(None)
                return
            if self.context != self.workspace.scope():
                self.dismiss(None)
                return
            self.workspace.next_refresh = 0
            self.workspace.refresh_data()
            self.dismiss(None)
        except Exception as error:
            response = getattr(error, 'response', None)
            message = ('Your publishing permission is no longer available. Your draft has been kept.'
                       if getattr(response, 'status_code', None) == 403 else
                       'Publication not confirmed. Your draft has been kept; retry without editing to avoid duplicates.')
            self.query_one('#announcement-error', Static).update(message)
        finally:
            self.busy = False
            if self.is_mounted:
                for button in self.query(Button):
                    button.disabled = False

    @on(Button.Pressed)
    def pressed(self, event):
        event.stop()
        key = event.button.id
        if key == 'announcement-cancel':
            self.action_cancel()
        elif key == 'announcement-edit':
            self.set_preview(False)
        elif key == 'announcement-preview':
            self.preview()
        elif key == 'announcement-publish':
            self.run_worker(self.publish(), group='announcement-publish', exclusive=False)


class ClubEventDetails(AppModal[None]):
    DEFAULT_CSS = """
    ClubEventDetails > VerticalScroll { width: 72; max-width: 96%; height: auto; max-height: 90%;
        border: round $accent; padding: 1 2; background: $surface; }
    ClubEventDetails Static { height: auto; margin-bottom: 1; }
    ClubEventDetails Button { min-width: 12; height: 3; }
    """
    BINDINGS = [('escape', 'close', 'Close')]

    def __init__(self, event):
        super().__init__()
        self.event = event

    def compose(self):
        e = self.event
        with VerticalScroll():
            yield Static(Text(e['title'], style='bold'), localize=False)
            meta = ' · '.join(filter(None, (e.get('location'), e.get('event_at'), e.get('actor_login'))))
            if meta:
                yield Static(meta, markup=False, localize=False)
            yield Static(e['message'], markup=False, localize=False)
            yield Button('Close', id='club-event-close', variant='danger')

    def action_close(self):
        self.dismiss(None)

    @on(Button.Pressed, '#club-event-close')
    def close(self, event):
        event.stop()
        self.dismiss(None)
