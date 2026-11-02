"""Activity heatmap with per-day hover details and an hour-based gradient."""
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


class ActivityHeatmap(Static):
    """Keep the text grid and map hovered day cells to their exact time."""

    def __init__(self, *args, **kwargs):
        super().__init__("", *args, **kwargs)
        self._cells = {}

    def set_snapshot(self, text, cells):
        self._cells = cells
        self.update(text)

    def cell_tooltip(self, week, day):
        return self._cells.get((week, day))

    def on_mouse_move(self, event: MouseMove) -> None:
        # Week rows are offset by the title row; day cells start after the date label.
        column, week = event.x - 8, event.y - 1
        if week < 0 or column < 0 or column > 12 or column % 2:
            self.tooltip = None
            return
        self.tooltip = self._cells.get((week, column // 2))
