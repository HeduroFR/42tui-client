"""Preview highlighted themes while the selector is open."""
from textual.widgets._select import SelectOverlay


def watch_theme_preview(owner, selector):
    overlay = selector.query_one(SelectOverlay)

    def highlighted(index):
        if selector.expanded and index is not None and 0 <= index < len(selector._options):
            theme = selector._options[index][1]
            if theme in owner.app.available_themes:
                owner.app.theme = theme

    def expanded(value):
        if not value:
            def restore():
                if owner.is_mounted and selector.value in owner.app.available_themes:
                    owner.app.theme = selector.value
            owner.call_after_refresh(restore)

    owner.watch(overlay, 'highlighted', highlighted, init=False)
    owner.watch(selector, 'expanded', expanded, init=False)
