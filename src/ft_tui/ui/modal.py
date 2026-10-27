"""Shared modal overlay layout, independent of the underlying screen spacing."""
from typing import TypeVar

from textual.screen import ModalScreen as TextualModalScreen

ModalResult = TypeVar('ModalResult')

def modal_css(selector):
    """Use the same root rules in app CSS and Textual's scoped widget CSS."""
    return selector + """ {
        layout: vertical;
        align: center middle;
        background: $background 55%;
        padding: 0;
    }
"""

APP_MODAL_CSS = modal_css('.app-modal')


class AppModal(TextualModalScreen[ModalResult]):
    """Cover the viewport without inheriting the main screen's outer padding.

    Dialog containers own their padding, dimensions and scrolling. Subclasses
    retain Textual's focus isolation, result typing and dismissal behavior.
    """

    DEFAULT_CSS = modal_css('AppModal')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Class selectors also work when AppModal is a secondary UI base:
        # Textual's CSS type ancestry follows only the first DOM base class.
        self.add_class('app-modal')


ModalScreen = AppModal
