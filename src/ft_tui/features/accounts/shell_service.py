"""Account lifecycle persistence and queued read fences without UI dependencies."""
import asyncio
from .shell_ports import AccountShellRepository

class AccountShellService:
    def __init__(self, repository: AccountShellRepository):
        self.repository = repository

    async def read(self, operation, current, *args, **kwargs):
        if not current():
            return None
        def dispatch():
            return operation(*args, **kwargs) if current() else None
        value = await asyncio.to_thread(dispatch)
        return value if current() else None

    def select_default(self, cursuses, today):
        return self.repository.select_default(cursuses, today)

    def configured_cursus(self, session=None):
        return self.repository.configured_cursus(session)

    def remember_account(self, account, campuses):
        self.repository.remember_account(account, campuses)

    def save_cursuses(self, values):
        self.repository.save_cursuses(values)

    def save_campuses(self, values):
        self.repository.save_campuses(values)
