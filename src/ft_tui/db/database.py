"""SQLite schema for the current development release; explicit resets only."""
from sqlalchemy import create_engine,event,inspect,text
from sqlalchemy.orm import Session,sessionmaker
from .models import Base
SCHEMA_VERSION=2
class DatabaseResetRequired(RuntimeError):
    pass

def make_session_factory(url: str) -> sessionmaker[Session]:
    from sqlalchemy.pool import StaticPool
    memory = url in ("sqlite:///:memory:", "sqlite://")
    engine=create_engine(url, **({"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if memory else {}))
    if url.startswith('sqlite'):
        @event.listens_for(engine,'connect')
        def configure(connection,_record):
            connection.execute('PRAGMA foreign_keys=ON')
        with engine.connect() as connection:
            version=connection.execute(text('PRAGMA user_version')).scalar()
            if inspect(engine).has_table('projects') and version != SCHEMA_VERSION:
                engine.dispose()
                raise DatabaseResetRequired('SQLite schema changed. Stop 42TUI and reset its development database before restarting; no data was deleted.')
    Base.metadata.create_all(engine)
    if url.startswith('sqlite'):
        with engine.begin() as connection:
            connection.execute(text(f'PRAGMA user_version={SCHEMA_VERSION}'))
    return sessionmaker(bind=engine,expire_on_commit=False)

def initialize_database(url:str)->sessionmaker[Session]:
    return make_session_factory(url)
