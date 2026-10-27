"""Headless student reads with identity validation and caller-context fencing."""
import asyncio
from collections.abc import Callable

from ft_tui.features.friends.models import friend_snapshot
from .models import student_id, student_profile, student_attendance, student_goals
from .student_ports import StudentProfileReader

Current = Callable[[], bool]


class StudentProfileService:
    def __init__(self, portrait_loader=None):
        self.portrait_loader = portrait_loader

    async def _read(self, operation, current, *args, **kwargs):
        if not current():
            return None
        def dispatch():
            # A context may expire while this operation waits for an executor.
            return operation(*args, **kwargs) if current() else None
        result = await asyncio.to_thread(dispatch)
        return result if current() else None

    async def search(self, provider: StudentProfileReader, login, current: Current):
        result = await self._read(provider.search_students, current, login, limit=20)
        if result is None:
            return None
        matches = [item for item in result['items'] if item['login'] == login]
        if len(matches) != 1:
            raise ValueError('Student identity unavailable')
        student_id(matches[0]['user_id'])
        return matches[0]

    async def profile(self, provider: StudentProfileReader, user_id, current: Current, *, refresh=False):
        result = await self._read(provider.get_student_profile, current, user_id, refresh=refresh)
        return student_profile(result, user_id) if result is not None else None

    async def attendance(self, provider: StudentProfileReader, user_id, current: Current, *, refresh=False):
        result = await self._read(provider.get_student_attendance, current, user_id, refresh=refresh)
        return student_attendance(result, user_id) if result is not None else None

    async def projects(self, provider: StudentProfileReader, login, user_id, cursus, current: Current, *, refresh=False):
        fetch = getattr(provider, 'get_friend_core', None) or provider.get_friend
        result = await self._read(fetch, current, login, cursus, refresh=refresh, user_id=user_id)
        return friend_snapshot(result, login, cursus, user_id=user_id) if result is not None else None

    async def goals(self, provider: StudentProfileReader, user_id, cursus, current: Current):
        result = await self._read(provider.get_student_goals, current, user_id, cursus)
        return student_goals(result, user_id, cursus) if result is not None else None

    async def portrait(self, url, current: Current, *, loader=None):
        operation = loader or self.portrait_loader
        if operation is None:
            raise ValueError('Portrait loader unavailable')
        return await self._read(operation, current, url)
