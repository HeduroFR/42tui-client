"""Terminal presentation policy; image probing happens before Textual owns stdin."""
from dataclasses import dataclass
import os
from collections.abc import Mapping
from rich.cells import set_cell_size

from textual_image._terminal import get_cell_size
from textual_image.renderable import Image as AutoRenderable, SixelImage, TGPImage


IMAGE_MODES = ('auto', 'sixel', 'tgp', 'halfcell', 'off')
ICON_MODES = ('auto', 'nerd', 'unicode', 'text')


@dataclass(frozen=True)
class TerminalCapabilities:
    image_protocol: str
    cell_size: tuple[int, int]
    nerd_font: bool
    icon_source: str


def detect_nerd_font(environ: Mapping[str, str]) -> tuple[bool, str]:
    """Estimate glyph support, never equate installed fonts with active fonts."""
    override = environ.get('NERDFONT', '').strip().lower()
    if override in ('1', 'true', 'yes', 'on'):
        return True, 'NERDFONT'
    if override in ('0', 'false', 'no', 'off'):
        return False, 'NERDFONT'
    program = environ.get('TERM_PROGRAM', '').lower()
    if (program in ('ghostty', 'wezterm') or environ.get('TERM') == 'xterm-ghostty'
            or environ.get('WEZTERM_PANE')):
        return True, 'Bundled symbols (estimated)'
    # Kitty only bundles symbols since 0.36; its name alone is insufficient.
    if program == 'kitty':
        version = environ.get('TERM_PROGRAM_VERSION', '').split('.')
        if len(version) >= 2 and all(part.isdigit() for part in version[:2]):
            if tuple(map(int, version[:2])) >= (0, 36):
                return True, 'Bundled symbols (estimated)'
    return False, 'Font support unknown'


def detect_capabilities(environ=None, *, renderable=AutoRenderable, cell_size=None):
    nerd, source = detect_nerd_font(os.environ if environ is None else environ)
    protocol = 'sixel' if renderable is SixelImage else 'tgp' if renderable is TGPImage else 'halfcell'
    return TerminalCapabilities(protocol, tuple(cell_size or get_cell_size()), nerd, source)


# textual-image caches its bounded terminal probe on import. Reuse the selected
# renderable instead of comparing widget classes (TGP uses an AutoImage wrapper).
CAPABILITIES = detect_capabilities()


def valid_mode(value, modes):
    return value if value in modes else 'auto'


def image_mode(app, *, native_default=None):
    mode = valid_mode(getattr(app, 'image_mode', 'auto'), IMAGE_MODES)
    if mode != 'auto':
        return mode
    if native_default is not None:
        return 'native' if native_default else 'halfcell'
    return CAPABILITIES.image_protocol


def icon_mode(app):
    mode = valid_mode(getattr(app, 'icon_mode', 'auto'), ICON_MODES)
    capabilities = getattr(app, 'terminal_capabilities', CAPABILITIES)
    return ('nerd' if capabilities.nerd_font else 'unicode') if mode == 'auto' else mode


# Keep the existing glyph API, including dynamic bell/DND buttons, in one place.
ICON_FALLBACKS = {
    '\uf015': '⌂', '\uf07b': '▤', '\uf067': '+', '\uf0c0': '○',
    '\uf0f4': '♧', '\uf044': '✎', '\uf1f8': '×', '\uf0c7': '↓',
    '\uf108': '▣', '\uf013': '⚙', '\uf204': '○', '\uf205': '●',
    '\uf058': '✓', '\uf555': '₳',
    '\uf021': '↻', '\uf1f6': '◇', '\uf0f3': '◆',
}


def icon_glyph(glyph, mode):
    if mode == 'text':
        return ''
    if mode == 'nerd':
        return glyph
    if any(0xE000 <= ord(char) <= 0xF8FF or 0xF0000 <= ord(char) <= 0x10FFFD for char in glyph):
        return ICON_FALLBACKS.get(glyph, '·')
    return glyph


def icon_prefix(glyph, mode):
    """Reserve two terminal cells for icons, including wide Unicode glyphs."""
    selected = icon_glyph(glyph, mode)
    return set_cell_size(selected, 2) + ' ' if selected else ''
