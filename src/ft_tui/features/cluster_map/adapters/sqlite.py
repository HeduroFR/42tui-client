"""Local memberships, selected cursus and account-scoped portrait storage."""
from hashlib import sha256
from pathlib import Path
from ft_tui.features.friends.adapters.storage import memberships


class SqliteClusterRepository:
    def __init__(self,session_factory,configured_cursus=None):
        self.session_factory=session_factory
        self.selector=configured_cursus

    def memberships(self,account,*,origin=''):
        if not self.session_factory or not account:return []
        with self.session_factory() as session:
            return list(memberships(session,account,origin=origin))

    def configured_cursus(self):
        if not self.session_factory or not self.selector:return None
        with self.session_factory() as session:return self.selector(session)

    def portrait_directory(self,account,origin):
        engine=getattr(self.session_factory,'kw',{}).get('bind')
        database=getattr(getattr(engine,'url',None),'database',None)
        scope=sha256(f'{origin}\0{account}'.encode()).hexdigest()
        return Path(database).parent/'portrait-cache'/scope if database and database!=':memory:' and account else None
