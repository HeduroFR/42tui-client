import unittest

from ft_tui.ui.username import username_text


class UsernameTests(unittest.TestCase):
    def test_literal_text_and_off_or_unknown_presets(self):
        for preset in ('off', 'unknown'):
            value = username_text('[red]alice', preset)
            self.assertEqual(value.plain, '[red]alice')
            self.assertFalse(any(span.style.color for span in value.spans))

    def test_gradient_endpoints_and_short_names(self):
        value = username_text('alice', 'ocean')
        self.assertEqual(value.plain, 'alice')
        self.assertEqual(value.spans[0].style.color.get_truecolor(), (88, 201, 192))
        self.assertEqual(value.spans[-1].style.color.get_truecolor(), (122, 162, 247))
        self.assertEqual(username_text('', 'ocean').plain, '')
        self.assertEqual(username_text('a', 'ocean').plain, 'a')
