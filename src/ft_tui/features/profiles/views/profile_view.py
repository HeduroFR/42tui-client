"""Composition and rendering of the student profile, independent of workers."""
from datetime import datetime
from rich.text import Text
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import DataTable, ProgressBar, Static, TabbedContent, TabPane
from ft_tui.features.profiles.projections import latest_attempts
from ft_tui.ui.components import Button, Select
from ft_tui.features.profiles.views.profile_sections import ProfilePortrait, ProfileCalendar, attendance_chart, goals_text


class ProfileViewMixin:
    def compose(self):
        with Horizontal(id='profile-controls'):
            yield Button('Back', id='profile-back')
            yield Static('', id='profile-control-spacer')
            yield Button('Refresh', id='profile-refresh')
            yield Button('Open on Intra', id='profile-intra')
        yield Static(self.t('Loading profile…'), id='profile-status', markup=False)
        with VerticalScroll(id='profile-scroll'):
            with Horizontal(id='profile-identity'):
                portrait = ProfilePortrait()
                portrait.id = 'profile-portrait'
                yield portrait
                with Vertical(id='profile-heading'):
                    yield Static(self.login, id='profile-name', markup=False)
                    yield Static('', id='profile-login', markup=False)
                    yield Static('', id='profile-coalition', markup=False)
                    yield Static('', id='profile-contact', markup=False)
                    yield Static('', id='profile-titles', markup=False)
            with Horizontal(id='profile-cursus-row'):
                yield Static(self.t('Cursus'), id='profile-cursus-label')
                yield Select([], id='profile-cursus', prompt=self.t('No cursus'), disabled=True)
            with Horizontal(id='profile-stats'):
                for key, label in [('wallet','Wallet'), ('points','Evaluation points'), ('grade','Grade'), ('earned','Achievements')]:
                    with Vertical(classes='profile-stat'):
                        yield Static(self.t(label), classes='profile-caption')
                        yield Static('—', id='profile-' + key, classes='profile-value', markup=False)
            yield Static('', id='profile-level-caption', markup=False)
            yield ProgressBar(total=100, show_eta=False, show_percentage=False, id='profile-level')
            with Horizontal(id='profile-overview'):
                with Vertical(classes='profile-panel'):
                    yield Static(self.t('Weekly attendance'), classes='profile-section-title')
                    yield Static(self.t('Loading attendance…'), id='profile-weeks', markup=False)
                with Vertical(classes='profile-panel'):
                    yield Static(self.t('Location'), classes='profile-section-title')
                    yield Static('—', id='profile-presence', markup=False)
                    yield Static('', id='profile-piscine', markup=False)
                with Vertical(classes='profile-panel'):
                    yield Static(self.t('Deadlines'), classes='profile-section-title')
                    yield Static(self.t('Loading deadlines…'), id='profile-goals', markup=False)
            with Vertical(id='profile-calendar-panel'):
                yield Static(self.t('Activity calendar'), classes='profile-section-title')
                yield ProfileCalendar(id='profile-calendar')
            with TabbedContent(id='profile-tabs'):
                with TabPane(self.t('Project marks'), id='profile-marks-pane'):
                    with Horizontal(id='profile-project-tools'):
                        yield Button('Show all attempts', id='profile-attempts')
                    yield Static(self.t('Loading projects…'), id='profile-project-status', markup=False)
                    yield DataTable(id='profile-projects', cursor_type='row', zebra_stripes=True)
                with TabPane(self.t('Achievements'), id='profile-achievements-pane'):
                    yield Static('', id='profile-achievements', markup=False)

    def _render_seed(self):
        self.query_one('#profile-name', Static).update(self.seed.get('display_name') or self.login)
        self.query_one('#profile-login', Static).update(self.login)
        self.query_one('#profile-contact', Static).update(' · '.join(c['name'] for c in self.seed.get('campuses', [])))
        for key, field in [('wallet','wallet'), ('points','correction_point')]:
            value = self.seed.get(field)
            self.query_one('#profile-' + key, Static).update(str(value) if value is not None else '—')

    def _render_core(self):
        data = self.core
        self.query_one('#profile-name', Static).update(data['display_name'])
        portrait = self.query_one('#profile-portrait', ProfilePortrait)
        portrait.initials = ''.join(part[0].upper() for part in data['display_name'].split()[:2]) or data['login'][:2].upper()
        portrait.refresh()
        self.query_one('#profile-login', Static).update(data['login'])
        self.query_one('#profile-coalition', Static).update(' · '.join(c['name'] for c in (data.get('coalitions') or [])))
        contacts = [c['name'] for c in data.get('campuses', [])]
        if data.get('email'):
            contacts.append(data['email'])
        self.query_one('#profile-contact', Static).update(' · '.join(contacts))
        self.query_one('#profile-titles', Static).update(' · '.join(data.get('titles') or []))
        for ident in ('profile-coalition', 'profile-contact', 'profile-titles'):
            widget = self.query_one('#' + ident, Static)
            widget.display = bool(str(widget.render()))
        for key, field in [('wallet','wallet'), ('points','correction_point'), ('earned','achievements_count')]:
            value = data.get(field)
            if key == 'earned' and data.get('achievements') is not None:
                value = len(data['achievements'])
            self.query_one('#profile-' + key, Static).update(str(value) if value is not None else '—')
        memberships = data['cursus_users']
        selector = self.query_one('#profile-cursus', Select)
        options = [(item['name'], item['cursus_id']) for item in memberships]
        selected = self.cursus_id if self.cursus_id in {item['cursus_id'] for item in memberships} else data.get('main_cursus_id') or (memberships[0]['cursus_id'] if memberships else None)
        with self.prevent(Select.Changed):
            selector.set_options(options)
            selector.disabled = not bool(options)
            selector.value = selected if selected else Select.NULL
        self.cursus_id = selected
        self._render_level()
        pool = ' '.join(str(data.get(key) or '') for key in ('pool_month', 'pool_year')).strip()
        self.query_one('#profile-piscine', Static).update('\n' + self.t('Piscine') + '\n' + pool if pool else '')
        earned = data.get('achievements')
        text = self.t('Achievements unavailable') if earned is None else self.t('No achievements yet.') if not earned else '\n\n'.join(a['name'] + (' · ' + a['tier'] if a.get('tier') else '') + ('\n' + a['description'] if a.get('description') else '') for a in earned)
        self.query_one('#profile-achievements', Static).update(text)

    def _render_level(self):
        membership = next((m for m in (self.core or {}).get('cursus_users', []) if m['cursus_id'] == self.cursus_id), {})
        level = membership.get('level')
        self.query_one('#profile-grade', Static).update(membership.get('grade') or '—')
        self.query_one('#profile-level-caption', Static).update(self.t('Level {level}', level=f'{level:.2f}') if level is not None else self.t('Level unavailable'))
        self.query_one('#profile-level', ProgressBar).update(progress=round((level % 1) * 100) if level is not None else 0)
        self.query_one('#profile-level').display = level is not None

    def _render_attendance(self):
        if not self.is_mounted:
            return
        width = self.query_one('#profile-weeks').size.width
        chart = attendance_chart(self.attendance_data, self.t, width)
        if self.attendance_data and self.attendance_data.get('stale'):
            chart.append('\n' + self.t('Saved data · stale'))
        self.query_one('#profile-weeks', Static).update(chart)
        self.query_one('#profile-calendar', ProfileCalendar).set_data(self.attendance_data)

    def _render_presence(self):
        if not self._valid():
            return
        from ft_tui.features.friends.views.workspace import current_location
        value = current_location(self.project_data,app=self.app,login=self.login,user_id=self.user_id) if getattr(self.app, 'account_connected', False) else 'Unavailable'
        self.query_one('#profile-presence', Static).update(self.t(value))

    def _render_projects(self):
        table = self.query_one('#profile-projects', DataTable)
        table.clear()
        items = (self.project_data or {}).get('items', [])
        rows = sorted(items, key=lambda p:(p['name'].casefold(), -p['id'])) if self.all_attempts else latest_attempts(items)
        for item in rows:
            status = self.t('Validated') if item.get('validated') is True else self.t(item['status'].replace('_', ' ').capitalize())
            mark = item.get('final_mark')
            table.add_row(Text(item['name']), Text(status), Text(f'{mark:g}' if mark is not None else '—'), key=str(item['id']))
        state = self.errors.get('projects') or self.t('No project attempts in this cursus.') if not rows else self.t('{count} projects', count=len(rows))
        if self.project_data and self.project_data['meta']['stale']:
            state += ' · ' + self.t('Saved data · stale')
        if not self.cursus_id:
            state = self.t('No cursus')
        self.query_one('#profile-project-status', Static).update(state)

    def _render_sections(self):
        self._render_attendance()
        self._render_projects()
        self._render_presence()
        self.query_one('#profile-goals', Static).update(goals_text(self.goals_data, self.t) if self.cursus_id else self.t('No pace deadlines for this cursus'))

    def _render_status(self):
        if self.reconnect_required:
            text = self.t('Reconnect your 42 account.')
        elif self.errors.get('core'):
            text = self.errors['core']
        elif self.core:
            stamp = datetime.fromisoformat(self.core['meta']['cached_at'].replace('Z', '+00:00')).astimezone()
            text = self.t('Saved data · stale') if self.saved or self.core['meta']['stale'] else self.t('Updated {date}', date=stamp.strftime('%d %b %H:%M'))
        else:
            text = self.t('Loading profile…')
        if self.errors.get('throttle'):
            text += ' · ' + self.errors['throttle']
        failures = [self.t(section) for section in ('attendance', 'projects', 'goals') if section in self.errors]
        if failures:
            text += ' · ' + self.t('Some profile sections are unavailable')
        self.query_one('#profile-status', Static).update(text)
