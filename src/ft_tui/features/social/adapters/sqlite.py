"""Persist server-confirmed friendship lists through the friend cache contract."""
from ft_tui.features.friends.adapters import storage as friends


class SqliteSocialRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def cache_confirmed(self, account, accepted, *, origin=''):
        with self.session_factory() as session:
            friends.cache_mutual_friends(session, account, accepted, origin=origin)
