"""Prepare primitive settings drafts and account-scoped curriculum choices."""
from pathlib import Path
from ft_tui.features.catalog.preferences import preference_key
from .ports import SettingsRepository

class SettingsService:
    def __init__(self, repository: SettingsRepository):
        self.repository = repository

    def get(self, key, default=''):
        return self.repository.get(key, default)

    def save_values(self, values):
        self.repository.save(values)

    def prepare(self, draft, *, account_id=None, campus_id=None):
        values = dict(draft)
        root_value = values.get('projects_root', '').strip()
        root = Path(root_value or Path.home() / '42').expanduser()
        if not root.is_absolute():
            raise ValueError('Enter an absolute projects folder path.')
        values['projects_root'] = str(root)
        selected = values.get('default_cursus_id')
        values['default_cursus_id'] = '' if selected is None else str(selected)
        values['default_cursus_source'] = 'manual' if values['default_cursus_id'] else ''
        cursus = int(selected) if selected not in (None, '') else None
        selected_campus = values.pop('campus_id', None)
        campus = int(selected_campus) if selected_campus is not None else campus_id
        track = values.pop('track', None)
        if account_id and cursus and campus:
            values.update({
                preference_key(account_id, cursus, None, 'campus'): str(campus),
                preference_key(account_id, cursus, campus, 'track'): track if track in ('old', 'new') else '',
            })
        return values

    def save(self, draft, *, account_id=None, campus_id=None):
        values = self.prepare(draft, account_id=account_id, campus_id=campus_id)
        self.save_values(values)
        return values

    def track(self, account, cursus, campus):
        return self.get(preference_key(account, cursus, campus, 'track'))

    def campus_choices(self, directory, account_campuses, *, campus_id=None, fallback_label='Saved campus (unavailable)'):
        options = []
        campus_ids = set()
        for campus in directory or account_campuses:
            identity = campus.get('id')
            if type(identity) is not int or identity < 1 or str(identity) in campus_ids:
                continue
            country = str(campus.get('country') or '').strip()
            city = str(campus.get('city') or '').strip()
            name = str(campus.get('name') or '').strip()
            label = ' - '.join(part for part in (country, city) if part) or name or fallback_label
            options.append((label, str(identity)))
            campus_ids.add(str(identity))
        options.sort(key=lambda option: option[0].casefold())
        selected = str(campus_id) if campus_id is not None else next(
            (str(campus['id']) for campus in account_campuses if campus.get('is_primary') and str(campus.get('id')) in campus_ids),
            options[0][1] if options else None,
        )
        if campus_id is not None and selected not in campus_ids:
            options.append((fallback_label, selected))
        return options, selected
