"""Terminal renderers for profile attendance and school details."""
import calendar
from datetime import date

from rich.text import Text
from rich.style import Style
from textual.widgets import Static

from ft_tui.features.profiles.projections import weekly_attendance
from ft_tui.features.cluster_map.views.portrait import ClusterPortrait
from ft_tui.ui.terminal_capabilities import image_mode


def attendance_chart(data, t, width=24):
    if not data or data.get('status') != 'available':
        return Text(t('Attendance unavailable'))
    weeks = weekly_attendance(data)
    maximum = max(1, *(week['seconds'] for week in weeks))
    bar_width = max(4, min(24, width - 20))
    lines = []
    for week in weeks:
        label = week['begin'].strftime('%d/%m')
        if not week['known_days']:
            lines.append(f"{label}  {'·' * bar_width}  —")
        else:
            hours = week['seconds'] / 3600
            bars = round(week['seconds'] / maximum * bar_width)
            lines.append(f"{label}  {'━' * bars}{' ' * (bar_width - bars)}  {hours:.1f} h")
    lines += ['', t('Campus session time · UTC'), t('— No reported sessions')]
    return Text('\n'.join(lines))


class ProfileCalendar(Static):
    """Four bounded calendar months; missing observations stay visibly unknown."""
    COMPONENT_CLASSES = {'profile-calendar--active', 'profile-calendar--muted'}
    DEFAULT_CSS = """
    ProfileCalendar .profile-calendar--active { color: $accent; }
    ProfileCalendar .profile-calendar--muted { color: $text-muted; }
    """

    def __init__(self, **kwargs):
        super().__init__('', markup=False, **kwargs)
        self.data = None

    def set_data(self, data):
        self.data = data
        self.refresh(layout=True)

    def render(self):
        from ft_tui.i18n import translate
        t = lambda text: translate(text, getattr(self.app, 'language', 'en'))
        if not self.data or self.data.get('status') != 'available':
            return Text(t('Activity calendar unavailable'))
        start = date.fromisoformat(self.data['begin'])
        end = date.fromisoformat(self.data['end'])
        days = self.data['days']
        accent = self.get_component_rich_style('profile-calendar--active', partial=True)
        muted = self.get_component_rich_style('profile-calendar--muted', partial=True)
        columns = 4 if self.content_size.width >= 96 else 2 if self.content_size.width >= 48 else 1
        months = []
        current = start.replace(day=1)
        while current <= end and len(months) < 4:
            lines = [Text(t(calendar.month_name[current.month]) + f' {current.year}', style='bold'),
                     Text(' '.join(t(day)[:2] for day in ('Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su')), style=muted)]
            for week in calendar.Calendar(firstweekday=0).monthdayscalendar(current.year, current.month):
                row = Text()
                for day in week:
                    key = current.replace(day=day).isoformat() if day else None
                    value = days.get(key)
                    # The dot marks unknown days; zero is a known empty session day.
                    label = '   ' if not day or key > end.isoformat() else f'{day:2d}' + ('·' if value is None else '+' if value > 0 else ' ')
                    style = muted if value is None else accent if value > 0 else ''
                    if value is not None and value >= 4 * 3600:
                        style = Style.combine([style if isinstance(style, Style) else Style(), Style(bold=True)])
                    row.append(label, style=style)
                lines.append(row)
            months.append(lines)
            current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
        output = Text()
        for offset in range(0, len(months), columns):
            group = months[offset:offset + columns]
            for line in range(max(map(len, group))):
                for month in group:
                    part = month[line].copy() if line < len(month) else Text()
                    part.pad_right(max(0, 24 - part.cell_len))
                    output.append_text(part)
                output.append('\n')
            output.append('\n')
        output.append(t('· Unknown / unreported · + Session · bold: 4+ hours'), style=muted)
        return output

    def on_resize(self):
        self.refresh(layout=True)


def goals_text(data, t):
    if not data:
        return t('Loading deadlines…')
    status = data.get('status')
    if status != 'available':
        return t({'pending':'Deadlines pending · waiting for Intra', 'not_applicable':'No pace deadlines for this cursus'}.get(status, 'Deadlines unavailable'))
    def fmt(value):
        return date.fromisoformat(value).strftime('%d/%m/%Y') if value else '—'
    lines = [t('Milestone deadline') + '\n' + fmt(data.get('next_milestone')),
             t('Common Core ETA') + '\n' + fmt(data.get('cc_eta'))]
    if data.get('cc_validated'):
        lines.append(t('Common Core completed'))
    if data.get('probationary_period'):
        lines.append(t('Probationary period'))
    if data.get('stale'):
        lines.append(t('Saved data · stale'))
    return '\n'.join(lines)


class ProfilePortrait(ClusterPortrait):
    """Reuse native terminal images, with initials while no image is available."""
    DEFAULT_CSS = "ProfilePortrait { content-align: center middle; }"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.initials = '…'

    def render(self):
        return super().render() if self.image is not None and image_mode(self.app) != 'off' else Text(self.initials, style='bold', justify='center')
