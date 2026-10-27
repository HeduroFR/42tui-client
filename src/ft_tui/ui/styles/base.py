"""Base screen styles."""

from ft_tui.ui.modal import APP_MODAL_CSS

BASE_CSS = r"""
    * { overflow-x: hidden; scrollbar-size-vertical: 1; scrollbar-size-horizontal: 0; }
    Screen { padding: 0 1; }
    Header { dock: top; height: 1; min-height: 1; max-height: 1; }
    Footer { dock: bottom; height: 1; min-height: 1; max-height: 1; }
    TabbedContent { height: 1fr; }
    /* Keep the command palette compact and centered over the current screen. */
    CommandPalette {
        align: center middle;
        background: $background 55%;
    }
    CommandPalette > #--container {
        width: 76;
        max-width: 84%;
        min-width: 0;
        height: auto;
        max-height: 76%;
        margin: 0;
        padding: 0 1 1 1;
        visibility: visible;
        border: round $primary;
        background: $surface;
    }
    CommandPalette #--input {
        width: 1fr;
        height: 3;
        padding: 0 1;
        border-bottom: hkey $primary;
        background: $surface;
    }
    CommandPalette SearchIcon {
        color: $accent;
        margin-left: 0;
        width: 2;
    }
    CommandPalette #--results {
        overlay: none;
        width: 1fr;
        height: auto;
        max-height: 60vh;
        padding-top: 1;
    }
    CommandPalette CommandList {
        width: 1fr;
        max-height: 56vh;
        border-top: none;
        border-bottom: none;
    }
    CommandPalette CommandList > .option-list--option {
        padding: 0 1;
    }
    CommandPalette CommandList > .option-list--option-highlighted {
        color: $text;
        background: $primary 35%;
        text-style: bold;
    }
    TabPane { padding: 0 1; }
    """ + APP_MODAL_CSS
