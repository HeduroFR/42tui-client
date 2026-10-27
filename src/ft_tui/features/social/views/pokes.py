"""Persistent, minimal incoming pokes, acknowledged only on explicit dismissal."""
import asyncio

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.await_complete import AwaitComplete

from ft_tui.features.profiles.adapters.portraits import download_portrait
from ft_tui.ui.cluster_portrait import ClusterPortrait, PortraitCache
from ft_tui.ui.components import Button, Static
from ft_tui.ui.modal import AppModal
from ft_tui.ui.terminal_capabilities import image_mode


class PokePortrait(ClusterPortrait):
    """Keep unavailable pictures quiet; identity remains available as a tooltip."""

    def render(self):
        if self.image is None or image_mode(self.app) == 'off':
            return Text('●', style='dim', justify='center')
        return super().render()


class PokeEntry(Vertical):
    def __init__(self, poke, popup):
        super().__init__(classes='poke-entry')
        self.poke = poke
        self.popup = popup

    def compose(self):
        yield Button('×', classes='poke-dismiss', tooltip='Dismiss', square=True, variant='danger')
        with Horizontal(classes='poke-faces'):
            for sender in self.poke['senders']:
                portrait = PokePortrait(cover=True)
                portrait.tooltip = sender['login']
                yield portrait
        yield Static(self.poke['message'], classes='poke-text', markup=False, localize=False)

    def on_mount(self):
        for sender, portrait in zip(self.poke['senders'], self.query(PokePortrait)):
            self.run_worker(self.load_portrait(sender, portrait))

    async def load_portrait(self, sender, portrait):
        try:
            provider = self.app.provider
            if not callable(getattr(provider, 'get_student_profile', None)):
                return
            profile = await self.popup.inbox._service().sender_profile(
                provider, sender['account_id'], lambda: self.popup.valid() and self.is_mounted)
            if profile is None:
                return
            url = profile.get('image_url')
            image = await self.popup.cache.load(url, lambda: asyncio.to_thread(download_portrait, url))
            if self.popup.valid() and self.is_mounted:
                portrait.image = image
        except Exception:
            # A missing picture must never prevent reading or dismissing a poke.
            pass

    @on(Button.Pressed, '.poke-dismiss')
    async def close(self, event):
        event.stop()
        await self.popup.acknowledge([self.poke['id']])


class PokeNotification(AppModal):
    BINDINGS = [Binding('escape', 'close', show=False)]
    DEFAULT_CSS = '''
    #incoming-pokes { width: 64; max-width: 95%; height: auto; max-height: 85%;
        border: round $primary; background: $surface; padding: 0 1; }
    .poke-entry { height: auto; padding: 0 1 1 1; }
    .poke-dismiss { dock: right; height: 3; }
    .poke-faces { height: 7; width: 1fr; margin: 1 3 1 0; }
    .poke-faces PokePortrait { width: 1fr; max-width: 16; height: 7; margin-right: 1; }
    .poke-text { height: auto; width: 1fr; }
    '''

    def __init__(self, inbox):
        super().__init__()
        self.inbox = inbox
        self.context = inbox.scope()
        self.entries = {}
        self.cache = PortraitCache()
        self.busy = False
        self.closing = False

    def compose(self):
        yield VerticalScroll(id='incoming-pokes')

    def valid(self):
        return not self.closing and self.context == self.inbox.scope() and self.is_mounted

    async def reconcile(self, pokes):
        if not self.valid():
            return
        current = {p['id']: p for p in pokes}
        for key in list(self.entries):
            if key not in current:
                await self.entries.pop(key).remove()
        for key, poke in current.items():
            if key not in self.entries:
                entry = self.entries[key] = PokeEntry(poke, self)
                await self.query_one('#incoming-pokes').mount(entry)
                entry.scroll_visible(animate=False)
        for button in self.query(Button):
            button.disabled = self.busy
        if not self.entries:
            self.dismiss()
        elif self.focused is None:
            self.query_one('.poke-dismiss', Button).focus()

    async def acknowledge(self, keys):
        if self.busy or not self.valid() or self.inbox.mutating:
            return
        self.busy = True
        for button in self.query(Button):
            button.disabled = True
        try:
            for key in keys:
                if not self.valid():
                    return
                if key not in self.entries:
                    continue
                if not await self.inbox.mutate({'action': 'dismiss', 'id': key}):
                    break
                if not self.valid():
                    return
                self.inbox.snapshot['pokes'] = [p for p in self.inbox.snapshot.get('pokes', []) if p['id'] != key]
                entry = self.entries.pop(key, None)
                if entry is not None:
                    await entry.remove()
                self.inbox.render_data()
        finally:
            self.busy = False
            if self.valid():
                for button in self.query(Button):
                    button.disabled = False
                if not self.entries:
                    self.dismiss()

    async def action_close(self):
        # Capture only currently displayed pokes: an arrival during the request
        # must remain visible and must not be silently acknowledged.
        await self.acknowledge(list(self.entries))

    def dismiss(self, result=None):
        self.closing = True
        if self.is_mounted:
            self.query_one('#incoming-pokes').display = False
        if not self.is_mounted or not self.is_active:
            return AwaitComplete.nothing()
        return super().dismiss(result)

    def on_screen_resume(self):
        if self.closing:
            self.dismiss()
