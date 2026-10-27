"""Session ownership for settings reads and atomic writes."""
from .storage import get_setting, save_settings

class SqliteSettingsRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def get(self, key, default=''):
        with self.session_factory() as session:
            return get_setting(session, key, default)

    def save(self, values):
        with self.session_factory() as session:
            save_settings(session, values)
