"""Configured cursus selection with adapter-owned session lifetime."""
class SqliteActivityContext:
    def __init__(self,session_factory=None,configured_cursus=None):
        self.session_factory=session_factory;self.selector=configured_cursus

    def cursus_matches(self,cursus):
        if self.selector is None:return True
        with self.session_factory() as session:return self.selector(session)==cursus
