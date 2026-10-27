"""Session lifetimes around the unchanged credential-bound cache projections."""
from . import cache


class SqliteProfileRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def load_profile(self, client):
        with self.session_factory() as session:
            return cache.load_profile(session, client)

    def save_profile(self, client, profile):
        with self.session_factory() as session:
            cache.save_profile(session, client, profile)

    def load_goals(self, account, cursus):
        with self.session_factory() as session:
            return cache.load_goals(session, account, cursus)

    def save_goals(self, account, cursus, value):
        with self.session_factory() as session:
            cache.save_goals(session, account, cursus, value)
