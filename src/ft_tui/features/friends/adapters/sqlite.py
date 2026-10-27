"""Own friend session lifetimes and return portable confirmed memberships."""
from dataclasses import dataclass
from ft_tui.features.settings.adapters.storage import get_setting
from . import storage

@dataclass(frozen=True)
class Membership:
    login: str
    user_id: str | None

class SqliteFriendsRepository:
    def __init__(self,session_factory):
        self.session_factory = session_factory
    def configured_cursus(self, selector=None):
        with self.session_factory() as session:
            if selector is not None:
                return selector(session)
            value = get_setting(session,'default_cursus_id')
            try:
                parsed = int(value) if value else None
            except ValueError:
                return None
            return parsed if parsed and parsed > 0 else None
    def memberships(self,account,*,origin=''):
        with self.session_factory() as session:
            return [Membership(row.login,row.user_id) for row in storage.memberships(session,account,origin=origin)]
    def cached(self,account,cursus,*,origin=''):
        with self.session_factory() as session:
            return storage.cached_observations(session,account,cursus,origin=origin)
    def save(self,account,value,*,origin=''):
        with self.session_factory() as session:
            storage.save_observation(session,account,value,origin=origin)
    def forget(self,account,cursus,login,*,origin=''):
        with self.session_factory() as session:
            storage.forget_observation(session,account,cursus,login,origin=origin)
