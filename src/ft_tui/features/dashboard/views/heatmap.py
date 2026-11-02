"""Activity heatmap with per-day hover details and an hour-based gradient."""
from rich.text import Text
from textual.events import MouseMove
from ft_tui.ui.components import Static


def activity_color(seconds):
    """Return a smooth cyan gradient for a non-zero daily duration."""
    if seconds is None or seconds <= 0:
        return None
    # Brighten the low end so short sessions remain distinguishable.
    ratio = min(1.0, (seconds / 3600) / 8) ** 0.6
    low, high = (31, 74, 70), (21, 211, 193)
    red, green, blue = (round(a + (b - a) * ratio) for a, b in zip(low, high))
    return f"#{red:02x}{green:02x}{blue:02x}"


def format_duration(seconds):
    hours, minutes = divmod(int(seconds // 60), 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"


def format_tooltip_time(seconds):
    hours, minutes = divmod(int(seconds // 60), 60)
    return f"{hours}h{minutes:02d}"


class ActivityHeatmap(Static):
    """Keep the text grid and map hovered day cells to their exact time."""

    def __init__(self, *args, **kwargs):
        super().__init__("", *args, **kwargs)
        self.styles.pointer = "default"
        self._cells = {}
        self._line_width = 0
        self._line_count = 0

    def set_snapshot(self, text, cells):
        self._cells = cells
        self.styles.pointer = "pointer" if cells else "default"
        lines = text.splitlines()
        self._line_width = max((Text.from_markup(line).cell_len for line in lines), default=0)
        self._line_count = len(lines)
        self.update(text)

    def cell_tooltip(self, week, day):
        return self._cells.get((week, day))

    def on_mouse_move(self, event: MouseMove) -> None:
        # Account for centered text and the date label before the seven day cells.
        left = self.content_region.x - self.region.x + max(
            0, (self.content_region.width - self._line_width) // 2)
        top = self.content_region.y - self.region.y + max(
            0, (self.content_region.height - self._line_count) // 2)
        column, week = event.x - left - 8, event.y - top - 1
        if week < 0 or column < 0 or column > 12 or column % 2:
            self.tooltip = None
            return
        self.tooltip = self._cells.get((week, column // 2))
