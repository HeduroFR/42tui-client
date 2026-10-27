"""A shared, scrollable quarter-hour timeline for correction availability."""
from datetime import UTC, datetime, time, timedelta
from functools import lru_cache

from rich.color import Color
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual import events
from textual.geometry import Size
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip

from ft_tui.i18n import translate
from ft_tui.features.corrections.model import earliest_start, interval


@lru_cache(maxsize=32)
def calendar_styles(base, accent):
    """Resolve theme colors once rather than once per calendar cell."""
    background = base.bgcolor.get_truecolor()
    def blend(color, amount):
        foreground = Color.parse(color).get_truecolor()
        return Color.from_rgb(*(round(b * (1 - amount) + f * amount) for b, f in zip(background, foreground)))
    return (base + Style(color=blend(base.color.name, .2)),
            base + Style(color=blend(base.color.name, .35), bgcolor=blend('#000000', .12)),
            base + Style(bgcolor=blend(accent, .22)))


class SlotsCalendar(ScrollView, can_focus=True):
    DEFAULT_CSS = '''
    SlotsCalendar { height: 1fr; min-height: 1; width: 1fr; overflow-x: hidden; overflow-y: auto;
                    background: $surface; scrollbar-size-vertical: 1; }
    '''
    BINDINGS = [('up', 'cursor(0,-1)', 'Earlier'), ('down', 'cursor(0,1)', 'Later'),
                ('left', 'cursor(-1,0)', 'Previous day'), ('right', 'cursor(1,0)', 'Next day'),
                ('enter', 'edit', 'Edit'), ('escape', 'cancel', 'Cancel selection'),
                ('pageup', 'time(-1)', 'Earlier hours'), ('pagedown', 'time(1)', 'Later hours')]

    class EditRequested(Message):
        def __init__(self, begin, end, slot=None, *, form=True):
            super().__init__(); self.begin = begin; self.end = end; self.slot = slot; self.form = form

    class DeleteRequested(Message):
        def __init__(self, slot, *, slots=None, direct=False):
            super().__init__(); self.slot = slot
            self.slots = tuple(slots) if slots is not None else (slot,)
            self.direct = direct

    class SelectionChanged(Message):
        def __init__(self, slot):
            super().__init__(); self.slot = slot

    class ChooseRequested(Message):
        def __init__(self, slots):
            super().__init__(); self.slots = slots

    class PreviewChanged(Message):
        def __init__(self, preview, *, deleting=0):
            super().__init__(); self.preview = preview; self.deleting = deleting

    class ViewChanged(Message):
        pass

    def __init__(self, week, zone, **kwargs):
        super().__init__(**kwargs)
        self.week = week - timedelta(days=week.weekday())
        self.zone = zone
        self.slots = ()
        self.day = 0
        self.row = 32
        self.writable = False
        self.pending = None
        self.pending_label = 'Saving…'
        self.preview = None
        self.delete_preview = ()
        self.gesture = None
        self._keyboard_selection = False
        self._interval_scope = None
        self._intervals = {}
        self._slot_cells = {}
        self._day_slots = {}
        self._slot_revision = 0
        self._render_key = None
        self._lines = {}
        self.virtual_size = Size(0, 96)

    def t(self, message):
        return translate(message, getattr(self.app, 'language', 'en'))

    @property
    def day_count(self):
        return 7 if self.scrollable_content_region.width >= 98 else 1

    @property
    def columns(self):
        days = tuple(range(7)) if self.day_count == 7 else (self.day,)
        width, extra = divmod(max(1, self.scrollable_content_region.width - 7), len(days))
        x = 7
        columns = []
        for day in days:
            size = width + (1 if extra > 0 else 0)
            extra = max(0, extra - 1)
            columns.append((day, x, size)); x += size
        return tuple(columns)

    @property
    def guide_style(self):
        return calendar_styles(self.rich_style, self.app.theme_variables.get('accent', '#44aaff'))[0]

    @property
    def disabled_style(self):
        return calendar_styles(self.rich_style, self.app.theme_variables.get('accent', '#44aaff'))[1]

    @property
    def selection_style(self):
        return calendar_styles(self.rich_style, self.app.theme_variables.get('accent', '#44aaff'))[2]

    def on_mount(self):
        self.set_interval(30, self.refresh_time)
        self.call_after_refresh(self.show_time, 32)

    def on_resize(self):
        self.action_cancel()
        self.virtual_size = Size(self.size.width, 96)
        self.post_message(self.ViewChanged())

    def watch_scroll_y(self, old_value, new_value):
        super().watch_scroll_y(old_value, new_value)
        if self.is_mounted:
            self.action_cancel()
            self.post_message(self.ViewChanged())

    def show_time(self, row):
        self.action_cancel()
        first = max(0, min(round(self.max_scroll_y), row))
        if not first <= self.row < first + self.size.height:
            self.row = first
        self.scroll_to(y=first, animate=False, force=True)
        self.post_message(self.ViewChanged())

    def action_time(self, direction):
        self.show_time(round(self.scroll_offset.y) + direction * max(4, self.size.height - 1))

    def visible_hours(self):
        first = min(95, round(self.scroll_offset.y))
        end = min(96, first + self.scrollable_content_region.height)
        return f'{first // 4:02d}:{first % 4 * 15:02d} – {end // 4:02d}:{end % 4 * 15:02d}'

    def refresh_time(self):
        self.refresh()
        self.post_message(self.ViewChanged())

    def first_row(self, day, *, adding=True):
        now = datetime.now(self.zone)
        if adding:
            now = earliest_start(now).astimezone(self.zone)
        date = self.week + timedelta(days=day)
        return 96 if date < now.date() else now.hour * 4 + now.minute // 15 if date == now.date() else 0

    def set_slots(self, slots):
        self.action_cancel()
        self.slots = tuple(slots)
        self._slot_cells.clear()
        self._day_slots.clear()
        self._slot_revision += 1
        self.refresh()

    def set_week(self, week):
        self.action_cancel()
        self.week = week - timedelta(days=week.weekday())
        self.refresh_time()

    def set_day(self, day):
        self.action_cancel()
        self.day = max(0, min(6, day))
        self.refresh_time()

    def cell(self, x, y):
        day = next((d for d, start, width in self.columns if start <= x < start + width), None)
        row = int(y + self.scroll_offset.y)
        return (day, row) if day is not None and 0 <= row < 96 else None

    def wall_intervals(self, day, row):
        """Display both DST folds; input still rejects ambiguous local times."""
        scope = (self.week, self.zone)
        if scope != self._interval_scope:
            self._interval_scope = scope
            self._intervals.clear()
            self._slot_cells.clear()
            self._day_slots.clear()
        key = (day, row)
        if key in self._intervals:
            return self._intervals[key]
        wall = datetime.combine(self.week + timedelta(days=day), time()) + timedelta(minutes=row * 15)
        spans = set()
        for fold in (0, 1):
            begin = wall.replace(tzinfo=self.zone, fold=fold).astimezone(UTC)
            if begin.astimezone(self.zone).replace(tzinfo=None) == wall:
                spans.add((begin, begin + timedelta(minutes=15)))
        result = tuple(sorted(spans))
        self._intervals[key] = result
        return result

    def slots_at(self, day, row):
        spans = self.wall_intervals(day, row)
        key = (day, row)
        if key not in self._slot_cells:
            if day not in self._day_slots:
                date = self.week + timedelta(days=day)
                begin = datetime.combine(date, time(), self.zone).astimezone(UTC)
                end = datetime.combine(date + timedelta(days=1), time(), self.zone).astimezone(UTC)
                self._day_slots[day] = tuple(s for s in self.slots if s.begin < end and s.end > begin)
            self._slot_cells[key] = tuple(s for s in self._day_slots[day] if any(s.begin < b and s.end > a for a, b in spans))
        return self._slot_cells[key]

    def request_edit(self, day, row):
        candidates = self.slots_at(day, row)
        if len(candidates) > 1:
            self.post_message(self.ChooseRequested(candidates))
        elif candidates:
            slot = candidates[0]
            self.post_message(self.SelectionChanged(slot))
            if self.writable and not slot.booked and slot.end > datetime.now(self.zone):
                self.post_message(self.EditRequested(slot.begin, slot.end, slot))
        elif self.writable and row >= self.first_row(day):
            try:
                begin, end = interval(self.week + timedelta(days=day), row, min(95, row + 1), self.zone)
            except ValueError:
                return
            self.post_message(self.EditRequested(begin, end))

    def on_mouse_down(self, event: events.MouseDown):
        if event.button != 1 or self.disabled:
            return
        cell = self.cell(event.x, event.y)
        if cell is None:
            return
        event.stop(); self.focus()
        self._keyboard_selection = False
        self.day, self.row = cell
        candidates = self.slots_at(*cell)
        self.post_message(self.SelectionChanged(candidates[0] if len(candidates) == 1 else None))
        self.post_message(self.ViewChanged())
        if not self.writable or self.row < self.first_row(self.day, adding=not candidates):
            return
        self.gesture = (cell, (event.x, event.y), False)
        self.capture_mouse(); self.refresh()

    def on_mouse_move(self, event: events.MouseMove):
        if not self.gesture:
            return
        event.stop()
        origin, position, moved = self.gesture
        cell = self.cell(event.x, event.y)
        moved = moved or (event.x, event.y) != position
        self.gesture = (origin, position, moved)
        preview, deleting = None, ()
        if cell and cell[0] == origin[0] and cell[1] >= self.first_row(cell[0], adding=not self.slots_at(*origin)):
            try:
                begin, end = interval(self.week + timedelta(days=origin[0]), origin[1], cell[1], self.zone)
                existing = self.slots_at(*origin)
                if existing and cell[1] != origin[1] and any(not s.booked for s in existing):
                    deleting = tuple(s for s in self._day_slots[origin[0]]
                                     if not s.booked and s.begin < end and s.end > begin)
                elif not existing:
                    preview = (begin, end)
            except ValueError:
                pass
        if (preview, deleting) == (self.preview, self.delete_preview):
            return
        self.preview, self.delete_preview = preview, deleting
        self.post_message(self.PreviewChanged(preview, deleting=len(deleting)))
        self.refresh()

    def on_mouse_up(self, event: events.MouseUp):
        if event.button != 1 or not self.gesture:
            return
        event.stop()
        origin, position, moved = self.gesture
        moved = moved or (event.x, event.y) != position
        cell = self.cell(event.x, event.y)
        preview = self.preview
        deleting = self.delete_preview
        self.action_cancel()
        if not self.writable or cell is None or cell[0] != origin[0]:
            return
        if not moved:
            self.request_edit(*origin)
        elif deleting and cell[1] != origin[1]:
            self.post_message(self.DeleteRequested(deleting[0], slots=deleting, direct=True))
        elif preview:
            self.post_message(self.EditRequested(*preview, form=False))

    def on_mouse_release(self):
        if self.gesture:
            self.action_cancel()

    def action_cancel(self):
        changed = self.gesture is not None or self.preview is not None or bool(self.delete_preview) or self._keyboard_selection
        self.gesture = None
        self.preview = None
        self.delete_preview = ()
        self._keyboard_selection = False
        if self.is_mounted and changed:
            self.release_mouse()
            self.refresh()
            self.post_message(self.PreviewChanged(None))

    def action_cursor(self, dx, dy):
        self.set_day(self.day + dx)
        self.row = max(0, min(95, self.row + dy))
        if not self.scroll_offset.y <= self.row < self.scroll_offset.y + self.size.height:
            self.show_time(max(0, self.row - self.size.height // 2))
        candidates = self.slots_at(self.day, self.row)
        self._keyboard_selection = True
        self.post_message(self.SelectionChanged(candidates[0] if len(candidates) == 1 else None))
        self.refresh()

    def action_edit(self):
        self.request_edit(self.day, self.row)

    def apply_language(self):
        self.refresh_time()

    def headings(self):
        heading = Text(' ' * 7)
        today = datetime.now(self.zone).date()
        for day, _, width in self.columns:
            date = self.week + timedelta(days=day)
            label = self.t(date.strftime('%a')) + f' {date.day:02d}'
            style = self.disabled_style if date < today else self.rich_style + Style(bold=True, underline=date == today)
            if day == self.day:
                style += self.selection_style
            heading.append(label.center(width - 1)[:width - 1], style)
            heading.append('│', self.guide_style)
        return heading

    def render_line(self, y):
        row = int(y + self.scroll_offset.y)
        base = self.rich_style
        if row >= 96:
            return Strip.blank(self.size.width, base)
        now = datetime.now(self.zone)
        palette = self.app.theme_variables
        accent = palette.get('accent', '#44aaff')
        primary = palette.get('primary-darken-2', '#16435c')
        key = (self.week, self.zone, self._slot_revision, self.size.width,
               self.scrollable_content_region.width, base, accent, primary,
               getattr(self.app, 'language', 'en'), now.date(), now.hour, now.minute // 15,
               self.day, self.row, self.has_focus, self._keyboard_selection, self.preview, self.delete_preview,
               self.pending, self.pending_label, palette.get('error', '#ff6666'))
        if key != self._render_key:
            self._render_key = key
            self._lines.clear()
        line_key = (row, y == 0)
        if line_key in self._lines:
            return self._lines[line_key]
        guide, disabled, selection = calendar_styles(base, accent)
        hour = row % 4 == 0
        label = f'{row // 4:02d}:{row % 4 * 15:02d}'
        segments = [Segment(label + '  ', base + Style(bold=hour, dim=not hour))]
        for day, _, width in self.columns:
            spans = self.wall_intervals(day, row)
            candidates = self.slots_at(day, row)
            date = self.week + timedelta(days=day)
            past = date < now.date() or date == now.date() and row < now.hour * 4 + now.minute // 15
            style = disabled if row < self.first_row(day) else base
            text = ''
            if candidates:
                slot = candidates[0]
                previous = self.slots_at(day, row - 1) if row else ()
                first = candidates != previous or y == 0
                marker = '■' if slot.booked else '▎'
                if first:
                    text = (f'{len(candidates)} {self.t("slots")} ↵' if len(candidates) > 1 else
                            f'{marker}{slot.begin.astimezone(self.zone):%H:%M}–{slot.end.astimezone(self.zone):%H:%M}')
                else:
                    text = '▎'
                style = base + Style(bgcolor=primary, dim=past, bold=slot.booked)
            elif not spans:
                text = 'DST'
                style = disabled
            elif date == now.date() and row == now.hour * 4 + now.minute // 15:
                text = self.t('now')
                style += Style(color=accent, bold=True)
            overlay = self.preview or self.pending
            if overlay and any(a < overlay[1] and b > overlay[0] for a, b in spans):
                previous = self.wall_intervals(day, row - 1) if row else ()
                first = y == 0 or not any(a < overlay[1] and b > overlay[0] for a, b in previous)
                text = (f'{overlay[0].astimezone(self.zone):%H:%M}–{overlay[1].astimezone(self.zone):%H:%M}'
                        if self.preview else self.t(self.pending_label)) if first else '▎'
                style = selection
            if self.delete_preview and any(s in self.delete_preview for s in candidates):
                previous = self.slots_at(day, row - 1) if row else ()
                first = y == 0 or not any(s in self.delete_preview for s in previous)
                text = self.t('Delete slot') if first else '▎'
                style = calendar_styles(base, palette.get('error', '#ff6666'))[2]
            if self.has_focus and self._keyboard_selection and (day, row) == (self.day, self.row):
                style += Style(underline=True, bold=True)
            content = text[:max(0, width - 2)]
            segments.append(Segment(' ' + content, style))
            fill = max(0, width - 2 - len(content))
            segments.append(Segment(('─' if hour and not candidates and not overlay else ' ') * fill,
                                    (style + Style(color=guide.color)) if hour and not candidates and not overlay else style))
            segments.append(Segment('│', guide))
        result = Strip(segments).adjust_cell_length(self.size.width, base)
        self._lines[line_key] = result
        return result
