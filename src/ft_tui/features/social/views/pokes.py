"""Persistent, minimal incoming pokes, acknowledged only on explicit dismissal."""
import asyncio
from time import monotonic

from rich.text import Text
from textual import on
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.await_complete import AwaitComplete

from ft_tui.features.profiles.adapters.portraits import download_portrait
from ft_tui.features.cluster_map.views.portrait import ClusterPortrait, PortraitCache
from ft_tui.ui.components import Button, Static
from ft_tui.ui.modal import AppModal
from ft_tui.ui.terminal_capabilities import image_mode
from ft_tui.ui.companion import WipPerch, WipSprite, companion_enabled


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
            if self.popup.preview or not callable(getattr(provider, 'get_student_profile', None)):
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
    #incoming-pokes.with-wip { padding-left: 7; }
    #poke-wip { position: absolute; layer: wip; display: none; }
    '''

    def __init__(self, inbox, *, preview=False):
        super().__init__()
        self.inbox = inbox
        self.preview = preview
        self.preview_pokes = []
        self.context = inbox.scope()
        self.entries = {}
        self.cache = PortraitCache()
        self.busy = False
        self.closing = False
        self.companion = WipSprite('crawl', id='poke-wip')
        self._animation_timer = None
        self._delivery_phase = 'travel'
        self._phase_start = monotonic()
        self._origin = (0, 0)
        self._position = (0, 0)
        self._return_start = (0, 0)

    def compose(self):
        yield VerticalScroll(id='incoming-pokes')
        yield self.companion

    def on_mount(self):
        perch = self._perch()
        self._origin = self._home_anchor()
        self._position = self._origin
        self._phase_start = monotonic()
        self._animation_timer = self.set_interval(0.125, self._tick_delivery)
        if perch:
            perch._tick()
        self.call_after_refresh(self._tick_delivery)
        if self.preview_pokes:
            self.run_worker(self.reconcile(self.preview_pokes))

    def _perch(self):
        for screen in self.app.screen_stack:
            if screen is self:
                continue
            for perch in screen.query(WipPerch):
                return perch
        return None

    def _can_show_companion(self):
        return (companion_enabled(self.app) and not self.companion.failed
                and self._perch() is not None and self.size.width >= 36 and self.size.height >= 12)

    def _home_anchor(self):
        perch = self._perch()
        if perch is not None:
            region = perch.region
            padding = perch.screen.styles.padding
            if region.width and region.height and region.right == self.app.size.width - padding.right:
                return (region.x, region.y)
            # Textual can discard a covered screen's compositor geometry. An
            # initial social update can also arrive before that screen lays out.
            return (max(0, self.app.size.width - padding.right - 8), padding.top)
        return (max(0, self.app.size.width - 8), 0)

    def _tick_delivery(self, now=None):
        if not self.is_mounted or self.closing or not self.is_active:
            return
        if self.context != self.inbox.scope() or (self.inbox.dnd() and not self.preview):
            self.dismiss()
            return
        now = monotonic() if now is None else now
        box = self.query_one('#incoming-pokes')
        enabled = self._can_show_companion()
        box.set_class(enabled, 'with-wip')
        self.companion.display = enabled
        if not enabled:
            self.companion.clear_pixels()
            if self._delivery_phase == 'return':
                self.dismiss()
            return
        target = (box.region.x + 1, box.region.y)
        motion = getattr(self.app, 'companion_motion', True)
        elapsed = max(0, now - self._phase_start)
        index = int(elapsed * 8) % 4 if motion else 0
        if self._delivery_phase == 'travel':
            progress = min(1, elapsed / 0.9) if motion else 1
            ease = progress * progress * (3 - 2 * progress)
            self._position = tuple(round(a + (b - a) * ease) for a, b in zip(self._origin, target))
            self.companion.set_pose('crawl', index)
            if progress == 1:
                self._delivery_phase = 'hang'
        if self._delivery_phase == 'hang':
            self._position = target
            self.companion.set_pose('hang', index)
        elif self._delivery_phase == 'return':
            if not motion:
                self.dismiss()
                return
            # First pull up from the border, then crawl toward the permanent perch.
            progress = min(1, max(0, elapsed - 0.2) / 0.6)
            self._origin = self._home_anchor()
            self._position = tuple(round(a + (b - a) * progress) for a, b in zip(self._return_start, self._origin))
            self.companion.set_pose('climb' if elapsed < 0.2 else 'crawl', index)
            if progress == 1:
                self.dismiss()
                return
        x, y = self._position
        self.companion.styles.offset = (max(0, min(x, self.size.width - 8)), max(0, min(y, self.size.height - 3)))
        self.companion._sync_pixels()

    def _finish_delivery(self):
        if self._can_show_companion() and getattr(self.app, 'companion_motion', True):
            self._origin = self._home_anchor()
            self._delivery_phase = 'return'
            self._phase_start = monotonic()
            self.query_one('#incoming-pokes').visibility = 'hidden'
            self._tick_delivery()
        else:
            self.dismiss()

    def on_unmount(self):
        self._stop_animation()

    def _stop_animation(self):
        if self._animation_timer is not None:
            self._animation_timer.stop()
            self._animation_timer = None

    def valid(self):
        return not self.closing and self.context == self.inbox.scope() and self.is_mounted

    async def reconcile(self, pokes):
        if not self.valid():
            return
        current = {p['id']: p for p in pokes}
        if current and self._delivery_phase == 'return':
            self._delivery_phase = 'travel'
            self._origin = self._position
            self._phase_start = monotonic()
            self.query_one('#incoming-pokes').visibility = 'visible'
        for key in list(self.entries):
            if key not in current and not self.busy:
                await self.entries.pop(key).remove()
        for key, poke in current.items():
            if key not in self.entries:
                entry = self.entries[key] = PokeEntry(poke, self)
                await self.query_one('#incoming-pokes').mount(entry)
                entry.scroll_visible(animate=False)
        for button in self.query(Button):
            button.disabled = self.busy
        if not self.entries:
            # A refresh can complete during entry.remove() in acknowledge().
            # Let that explicit operation finish before starting the return.
            if not self.busy and self._delivery_phase != 'return':
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
                if not self.preview and not await self.inbox.mutate({'action': 'dismiss', 'id': key}):
                    break
                if not self.valid():
                    return
                self.inbox.snapshot['pokes'] = [p for p in self.inbox.snapshot.get('pokes', []) if p['id'] != key]
                if len(self.entries) == 1:
                    # Removing the last entry changes the centered box geometry.
                    # Keep the grip location before it collapses for the climb.
                    self._return_start = self._position
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
                    self._finish_delivery()

    async def action_close(self):
        # Capture only currently displayed pokes: an arrival during the request
        # must remain visible and must not be silently acknowledged.
        await self.acknowledge(list(self.entries))

    def dismiss(self, result=None):
        self.closing = True
        self._stop_animation()
        self.companion.display = False
        self.companion.clear_pixels()
        perch = self._perch()
        if perch:
            perch._tick()
        if self.is_mounted:
            self.query_one('#incoming-pokes').display = False
        if not self.is_mounted or not self.is_active:
            return AwaitComplete.nothing()
        return super().dismiss(result)

    def on_screen_resume(self):
        if self.closing:
            self.dismiss()
        else:
            self.call_after_refresh(self._tick_delivery)

    def on_screen_suspend(self):
        self.companion.clear_pixels()
