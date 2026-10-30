"""Presentation selection without interrogating a real terminal in the tests."""
from types import SimpleNamespace
from unittest import TestCase

from textual_image.renderable import HalfcellImage, SixelImage, TGPImage
from ft_tui.ui.terminal_capabilities import (
    detect_capabilities, detect_nerd_font, icon_glyph, icon_mode, image_mode,
)


class TerminalCapabilitiesTests(TestCase):
    def test_selects_the_renderable_including_the_autoimage_tgp_case(self):
        for renderable, protocol in ((SixelImage, 'sixel'), (TGPImage, 'tgp'), (HalfcellImage, 'halfcell')):
            caps = detect_capabilities({}, renderable=renderable, cell_size=(9, 18))
            self.assertEqual(caps.image_protocol, protocol)
            self.assertEqual(caps.cell_size, (9, 18))

    def test_font_estimates_and_environment_override(self):
        self.assertFalse(detect_nerd_font({})[0])
        self.assertTrue(detect_nerd_font({'TERM_PROGRAM': 'ghostty'})[0])
        self.assertTrue(detect_nerd_font({'TERM_PROGRAM': 'WezTerm'})[0])
        self.assertTrue(detect_nerd_font({'TERM_PROGRAM': 'tmux', 'WEZTERM_PANE': '0'})[0])
        self.assertFalse(detect_nerd_font({'TERM_PROGRAM': 'WezTerm', 'NERDFONT': '0'})[0])
        self.assertFalse(detect_nerd_font({'TERM_PROGRAM': 'kitty'})[0])
        self.assertFalse(detect_nerd_font({'TERM_PROGRAM': 'kitty', 'TERM_PROGRAM_VERSION': '0.35.2'})[0])
        self.assertTrue(detect_nerd_font({'TERM_PROGRAM': 'kitty', 'TERM_PROGRAM_VERSION': '0.36.0'})[0])
        self.assertEqual(detect_nerd_font({'NERDFONT': '0', 'TERM_PROGRAM': 'ghostty'}), (False, 'NERDFONT'))
        self.assertEqual(detect_nerd_font({'NERDFONT': 'yes'}), (True, 'NERDFONT'))

    def test_explicit_preference_wins_over_estimation_and_invalid_values_fall_back(self):
        caps = detect_capabilities({}, renderable=HalfcellImage, cell_size=(10, 20))
        app = SimpleNamespace(terminal_capabilities=caps, icon_mode='nerd', image_mode='off')
        self.assertEqual(icon_mode(app), 'nerd')
        self.assertEqual(image_mode(app), 'off')
        app.icon_mode = 'invalid'
        self.assertEqual(icon_mode(app), 'unicode')
        app.image_mode = 'invalid'
        self.assertEqual(image_mode(app, native_default=False), 'halfcell')

    def test_unknown_private_glyphs_have_a_portable_fallback(self):
        self.assertEqual(icon_glyph('\uf067', 'unicode'), '+')
        self.assertEqual(icon_glyph('\uf1f8', 'unicode'), '🗑︎')
        self.assertEqual(icon_glyph('\uf067', 'nerd'), '\uf067')
        self.assertEqual(icon_glyph('\uf067', 'text'), '')
        self.assertEqual(icon_glyph('\ue123', 'unicode'), '·')
        self.assertEqual(icon_glyph('+', 'unicode'), '+')
