"""Small presentation helpers for the Clubs message list and reader."""
from datetime import datetime
from rich.text import Text
from textual.containers import Horizontal
from textual.widgets import DataTable


def event_time(value):
    """Show local dates as well as times so yesterday never looks like today."""
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone().strftime('%d/%m · %H:%M')
    except (TypeError, ValueError, AttributeError):
        return ''


def message_row(event, translate):
    title = ' '.join(event['title'].split())
    metadata = [translate(event['kind'].capitalize())]
    if event.get('actor_login'):
        metadata.append(event['actor_login'])
    metadata.append(event_time(event['created_at']))
    content = Text(title, style='bold', no_wrap=True, overflow='ellipsis')
    content.append('\n' + ' · '.join(filter(None, metadata)), style='not bold dim')
    return content


class InboxMessages(DataTable):
    """Keep long subjects inside the list, with an ellipsis rather than scrolling."""
    DEFAULT_CSS = 'InboxMessages { scrollbar-gutter: stable; }'

    def on_resize(self):
        if not self.columns:
            return
        column = self.ordered_columns[0]
        column.auto_width = False
        column.width = max(1, self.size.width - self.scrollbar_size_vertical - 2 * self.cell_padding)
        # DataTable has no public column-resize method. Recompute its viewport
        # and invalidate cached cells after changing the column metadata.
        self._update_dimensions(())
        self._clear_caches()


class InboxColumns(Horizontal):
    DEFAULT_CSS = """
    InboxColumns { height: 1fr; min-height: 15; }
    InboxColumns.stacked { layout: vertical; height: auto; }
    """

    def on_resize(self):
        self.set_class(self.size.width < 90, 'stacked')
