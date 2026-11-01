"""Read-only event blocks on a local-time week, sharing agenda selection."""
from datetime import datetime, timedelta
import textwrap
from rich.color import Color
from rich.style import Style
from rich.text import Text
from textual import events
from textual.geometry import Size, Region
from textual.message import Message
from textual.scroll_view import ScrollView
from textual.strip import Strip
from ft_tui.i18n import translate
from ..models import timeline_cells, timeline_blocks


class AgendaCalendar(ScrollView, can_focus=True):
    DEFAULT_CSS = '''
    AgendaCalendar { width: 1fr; height: 1fr; min-height: 3; overflow-x: hidden; overflow-y: auto; scrollbar-size-vertical: 1; background: $surface; }
    '''
    BINDINGS = [('up', 'move(0,-1)', 'Earlier'), ('down', 'move(0,1)', 'Later'),
                ('left', 'move(-1,0)', 'Previous day'), ('right', 'move(1,0)', 'Next day'),
                ('enter', 'choose', 'Details'), ('pageup', 'move(0,-8)', 'Earlier hours'),
                ('pagedown', 'move(0,8)', 'Later hours')]

    class Selected(Message):
        def __init__(self, items):
            super().__init__()
            self.items = items

    class ViewChanged(Message):
        pass

    def __init__(self, week, zone, **kwargs):
        super().__init__(**kwargs)
        self.week, self.zone = week, zone
        self.day, self.row = 0, 16
        self.cells, self.blocks = {}, []
        self.skeleton = False
        self.skeleton_bright = False
        self.skeleton_timer = None
        self.selected = None
        self.virtual_size = Size(0, 48)

    @property
    def days(self):
        return tuple(range(7)) if self.scrollable_content_region.width >= 84 else (self.day,)

    @property
    def columns(self):
        width = max(1, self.scrollable_content_region.width - 6)
        return [(day, 6 + i * width // len(self.days), (i + 1) * width // len(self.days) - i * width // len(self.days)) for i, day in enumerate(self.days)]

    def headings(self):
        result = Text(' ' * 6)
        today = datetime.now(self.zone).date()
        for day, _, width in self.columns:
            date = self.week + timedelta(days=day)
            label = translate(date.strftime('%a'), getattr(self.app, 'language', 'en')) + (f' {date:%d %b %Y}' if len(self.days) == 1 else f' {date.day:02d}')
            result.append(label.center(max(1, width - 1)), style='dim' if date < today else 'bold underline' if date == today else 'bold')
            result.append('│', style='dim')
        return result

    def on_mount(self):
        self.set_interval(60, self.refresh_time)
        self.skeleton_timer = self.set_interval(.65, self.blink_skeleton, pause=not self.skeleton)

    def refresh_time(self):
        self.refresh()
        self.post_message(self.ViewChanged())

    def set_skeleton(self, visible):
        if self.skeleton == visible:
            return
        self.skeleton = visible
        self.skeleton_bright = False
        if self.skeleton_timer:
            self.skeleton_timer.resume() if visible else self.skeleton_timer.pause()
        self.refresh()

    def blink_skeleton(self):
        self.skeleton_bright = not self.skeleton_bright
        self.refresh()

    def set_items(self, items, week):
        changed = week != self.week
        self.week = week
        self.cells = timeline_cells(items, week, self.zone)
        self.blocks = timeline_blocks(self.cells)
        keys = {(item['kind'], item['id']) for item in items}
        if changed or self.selected not in keys:
            first = min(self.blocks, key=lambda b: (b['day'], b['start']), default=None)
            self.selected = None
            if first:
                self.day, self.row = first['day'], first['start']
                self.select_item(first['item'])
            else:
                self.row = 16
                self.selected = None
                self.call_after_refresh(self.show_cursor)
        self.refresh()
        self.post_message(self.ViewChanged())

    def select_item(self, item):
        key = (item['kind'], item['id']) if item else None
        changed = key != self.selected
        self.selected = key
        block = next((b for b in self.blocks if (b['item']['kind'], b['item']['id']) == self.selected), None)
        if block and changed:
            self.day, self.row = block['day'], block['start']
            self.call_after_refresh(self.show_cursor)
        self.refresh()
        self.post_message(self.ViewChanged())

    def show_cursor(self):
        self.scroll_to(y=max(0, self.row - 2), animate=False)

    def on_resize(self):
        self.call_after_refresh(self.show_cursor)
        self.virtual_size = Size(self.size.width, 48)
        self.post_message(self.ViewChanged())
        self.refresh()

    def action_move(self, day, half):
        self.day = max(0, min(6, self.day + day))
        self.row = max(0, min(47, self.row + half))
        self.scroll_to_region(Region(0, self.row, 1, 1), animate=False)
        self.refresh()
        self.post_message(self.ViewChanged())
        self.action_choose()

    def action_choose(self):
        self.post_message(self.Selected(self.cells.get((self.row, self.day), [])))

    def on_click(self, event: events.Click):
        x, y = event.x, event.y + int(self.scroll_offset.y)
        for day, start, width in self.columns:
            if start <= x < start + width:
                self.day, self.row = day, max(0, min(47, y))
                candidates = [b for b in self.blocks if b['day'] == day and b['start'] <= self.row < b['end']]
                lane_x = x - start
                hit = [b['item'] for b in candidates if b['lane'] * max(1, width - 1) // b['lanes'] <= lane_x < (b['lane'] + 1) * max(1, width - 1) // b['lanes']]
                self.post_message(self.Selected(hit or self.cells.get((self.row, day), [])))
                self.refresh()
                self.post_message(self.ViewChanged())
                break

    def render_line(self, y):
        half = y + int(self.scroll_offset.y)
        if not 0 <= half < 48:
            return Strip.blank(self.size.width, self.rich_style)
        result = Text(f'{half // 2:02d}:{half % 2 * 30:02d} ' if half % 2 == 0 else '      ', style=self.rich_style)
        now = datetime.now(self.zone)
        palette = {'exam': 'error', 'event': 'accent', 'evaluating': 'success', 'evaluated': 'warning'}
        variables = self.app.theme_variables
        for day, _, width in self.columns:
            date = self.week + timedelta(days=day)
            past = date < now.date() or date == now.date() and half < now.hour * 2 + now.minute // 30
            current = date == now.date() and half == now.hour * 2 + now.minute // 30
            blocks = [b for b in self.blocks if b['day'] == day and b['start'] <= half < b['end']]
            base = self.rich_style.bgcolor or Color.parse(variables.get('surface', '#202030'))
            background = Color.parse(variables.get('surface-darken-1', variables.get('background', '#101020'))) if past else base
            column = Text(style=self.rich_style + Style(bgcolor=background, dim=past))
            position = 0
            for block in sorted(blocks, key=lambda b: b['lane']):
                item = block['item']
                start = block['lane'] * max(1, width - 1) // block['lanes']
                end = (block['lane'] + 1) * max(1, width - 1) // block['lanes']
                size = end - start
                accent = variables.get(palette[item['kind']], '#88aaff')
                foreground = Color.parse(accent).get_truecolor()
                surface = background.get_truecolor()
                selected = self.selected == (item['kind'], item['id'])
                amount = .3 if selected else .12
                fill = Color.from_rgb(*(round(b * (1 - amount) + f * amount) for b, f in zip(surface, foreground)))
                style = Style(color=accent, bgcolor=fill, bold=selected, dim=past)
                offset = half - block['start']
                begin = datetime.fromisoformat(item['begin_at']).astimezone(self.zone)
                finish = datetime.fromisoformat(item['end_at']).astimezone(self.zone) if item['end_at'] else None
                label = f'{begin:%H:%M}' + (f'–{finish:%H:%M}' if finish else '')
                height = block['end'] - block['start']
                if height == 1:
                    label = f'{begin:%H:%M} {item["title"]}'
                elif offset:
                    lines = textwrap.wrap(item['title'], max(1, size - 2), max_lines=max(1, height - 1), placeholder='…')
                    label = lines[offset - 1] if offset <= len(lines) else ''
                rendered = Text('▎' + label, style=style)
                rendered.truncate(size, overflow='ellipsis', pad=True)
                column.append(' ' * max(0, start - position))
                column.append_text(rendered)
                position = end
            remaining = max(0, width - 1 - position)
            if self.skeleton and not blocks and not current and (half - 16 - day * 2) in (0, 1):
                size = remaining
                if size >= 4:
                    label = '▎ ' + '━' * min(size - 2, 3 if (half - 16 - day * 2) == 0 else 6)
                    shade = 'surface-lighten-2' if self.skeleton_bright else 'surface-lighten-1'
                    style = Style(color=self.rich_style.color, bgcolor=variables.get(shade, '#404050'), dim=True)
                    column.append(label.ljust(size), style=style)
                    remaining -= size
            if not blocks and current:
                label = translate('now', getattr(self.app, 'language', 'en'))[:remaining]
                column.append(label, style=Style(color=variables.get('accent', '#44aaff'), bold=True))
                remaining -= len(label)
            column.append(' ' * remaining)
            if not blocks and day == self.day and half == self.row and self.has_focus:
                column.stylize('reverse')
            result.append_text(column)
            result.append('│', style='dim')
        segments = result.render(self.app.console, end='')
        return Strip(segments).crop(0, self.size.width)
