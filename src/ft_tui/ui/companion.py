"""Small presentation-only WIP sprites and the app's permanent header perch."""
from time import monotonic

from PIL import Image, ImageOps
from rich.style import Style
from rich.text import Text
from textual.containers import Horizontal
from textual.widget import Widget
from textual.widgets import Header
from textual_image.widget import TGPImage

from ft_tui.features.cluster_map.views.portrait import PortraitSixelImage
from ft_tui.ui.companion_art import frame
from ft_tui.ui.terminal_capabilities import CAPABILITIES, image_mode


def companion_enabled(app) -> bool:
    return getattr(app, 'companion_visible', True) and image_mode(app) != 'off'


class WipSprite(Widget, can_focus=False):
    DEFAULT_CSS = '''
    WipSprite { width: 8; height: 3; padding: 0; margin: 0; overflow: hidden hidden; }
    WipSprite > .wip-pixels { width: 100%; height: 100%; }
    '''

    def __init__(self, pose='idle', **kwargs):
        super().__init__(**kwargs)
        self.pose = pose
        self.image = None
        self.failed = False
        self._frame_key = None
        self._pixel_key = None
        self._renderers = []

    def compose(self):
        # Mount both existing native renderers once; preferences can switch modes
        # without leaving a renderer from the previous protocol in the screen.
        self._renderers = [
            PortraitSixelImage(classes='wip-pixels wip-sixel', on_error=self._renderer_failed),
            TGPImage(classes='wip-pixels wip-tgp', on_error=self._renderer_failed),
        ]
        yield from self._renderers

    def clear_pixels(self):
        self._pixel_key = None
        for renderer in self._renderers:
            if renderer.image is not None:
                renderer.image = None

    def on_unmount(self):
        self.clear_pixels()

    def on_hide(self):
        self.clear_pixels()

    def _renderer_failed(self, error):
        self.failed = True
        self.display = False
        return Widget()

    def on_mount(self):
        self.set_pose(self.pose)
        self.refresh_preferences()

    def on_resize(self):
        self._sync_pixels()

    def refresh_preferences(self):
        enabled = companion_enabled(self.app) and not self.failed
        self.display = enabled
        self._pixel_key = None
        self._sync_pixels()
        self.refresh()

    def set_pose(self, pose: str, index: int = 0):
        key = (pose, index % 4)
        if key == self._frame_key:
            self._sync_pixels()
            return
        self.pose = pose
        try:
            self.image = frame(*key)
        except (OSError, ValueError):
            self.failed = True
            self.display = False
            return
        self._frame_key = key
        self._sync_pixels()
        self.refresh()

    def _prepared(self, width, height):
        _, background = self.background_colors
        result = Image.new('RGB', (width, height), (background.r, background.g, background.b))
        if self.image is not None:
            scaled = ImageOps.contain(self.image, (width, height), Image.Resampling.NEAREST)
            result.paste(scaled, ((width - scaled.width) // 2, (height - scaled.height) // 2), scaled)
        return result

    def _sync_pixels(self):
        if not self.is_mounted:
            return
        mode = image_mode(self.app)
        active = mode if self.display and self.visible and self.screen.is_active and not self.failed else 'off'
        for renderer in self.query('.wip-pixels'):
            selected = renderer.has_class('wip-' + active)
            renderer.display = selected
            if not selected and renderer.image is not None:
                renderer.image = None
        if active not in ('sixel', 'tgp') or self.image is None:
            return
        width, height = self.content_size
        if not width or not height:
            return
        cell_width, cell_height = getattr(self.app, 'terminal_capabilities', CAPABILITIES).cell_size
        key = (self._frame_key, width, height, self.background_colors, active, cell_width, cell_height)
        if key == self._pixel_key:
            return
        try:
            self.query_one('.wip-' + active).image = self._prepared(width * cell_width, height * cell_height)
        except (OSError, ValueError):
            self.failed = True
            self.display = False
        self._pixel_key = key

    def render(self):
        if self.image is None or not self.display or image_mode(self.app) in ('off', 'sixel', 'tgp'):
            return Text('')
        width, height = self.content_size
        if width < 1 or height < 1:
            return Text('')
        # Half cells deliberately use nearest-neighbor pixels, not photo filtering.
        pixels = self._prepared(width, height * 2).load()
        lines = []
        # Two terminal rows cannot retain the bitmap's six-pixel lettering.
        # Render the badge lettering as text in its own spot at this resolution.
        badge_x = min(width - 2, max(0, round(width * (17 if self.pose in ('hang', 'climb') else 24) / 48)))
        for y in range(height):
            line = Text()
            for x in range(width):
                if y == height - 1 and width >= 2 and x in (badge_x, badge_x + 1):
                    line.append('42'[x - badge_x], Style(color='#173e43', bgcolor='#e4e9d9', bold=True))
                    continue
                top, bottom = pixels[x, y * 2], pixels[x, y * 2 + 1]
                line.append('▀', Style(color='#%02x%02x%02x' % top, bgcolor='#%02x%02x%02x' % bottom))
            lines.append(line)
        return Text('\n').join(lines)


class WipPerch(WipSprite):
    """Read accepted UI state, without polling the backend or owning poke state."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._timer = None
        self._sleeping = False
        self._transition = None

    def on_mount(self):
        super().on_mount()
        self._timer = self.set_interval(0.2, self._tick)
        self._tick()

    def on_unmount(self):
        if self._timer:
            self._timer.stop()
            self._timer = None

    def refresh_preferences(self):
        super().refresh_preferences()
        enabled = companion_enabled(self.app) and not self.failed
        if self.parent:
            self.parent.set_class(not enabled, 'no-companion')
        if self.is_mounted:
            self._tick()

    def _tick(self):
        if not self.is_mounted:
            return
        from ft_tui.features.social.views.inbox import SocialInbox
        inbox = next(iter(self.screen.query(SocialInbox)), None)
        sleeping = bool(getattr(self.app, 'account_connected', False) and (inbox is None or inbox.dnd()))
        if sleeping != self._sleeping:
            self._sleeping = sleeping
            self._transition = monotonic()
        if not companion_enabled(self.app) or self.failed:
            self.display = False
            return
        self.display = True
        popup = getattr(inbox, 'poke_popup', None)
        away = bool(popup and popup in self.app.screen_stack and not popup.closing and popup._can_show_companion())
        if self.visible == away:
            self.visible = not away
            self._pixel_key = None
            self._sync_pixels()
        # Leave the covered header still; the active poke screen owns travel.
        if not self.screen.is_active:
            return
        motion = getattr(self.app, 'companion_motion', True)
        if self._transition is not None and motion:
            progress = int((monotonic() - self._transition) / 0.15)
            if progress < 4:
                self.set_pose('settle' if sleeping else 'wake', progress)
                return
        self._transition = None
        pose = 'sleep' if sleeping else 'blink' if motion and int(monotonic() * 5) % 31 == 0 else 'idle'
        self.set_pose(pose, int(monotonic() * 2) % 4 if sleeping and motion else 0)


class WipHeader(Horizontal):
    DEFAULT_CSS = '''
    WipHeader { dock: top; height: 2; }
    WipHeader.no-companion { height: 1; }
    WipHeader > Header { dock: none; width: 1fr; height: 1; }
    WipHeader > WipPerch { width: 8; height: 3; }
    '''

    def compose(self):
        yield Header(show_clock=True)
        yield WipPerch()
