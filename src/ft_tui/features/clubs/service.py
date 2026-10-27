"""Headless clubs operations; UI scheduling and notifications stay in views."""
import asyncio
from collections.abc import Callable

from .ports import ClubsReader, ClubsPoller, ClubsWriter

Current = Callable[[], bool]


class ClubsService:
    async def read(self, provider: ClubsReader, campus_id: int, account_id: str, current: Current) -> dict | None:
        if not current() or not callable(getattr(provider, 'get_clubs', None)):
            return None
        value = await asyncio.to_thread(provider.get_clubs, campus_id)
        if not current():
            return None
        if value.get('account_id') != account_id:
            raise ValueError('Clubs account mismatch')
        return value

    async def poll(self, provider: ClubsPoller, current: Current) -> dict | None:
        if not current() or not callable(getattr(provider, 'poll_clubs', None)):
            return None
        value = await asyncio.to_thread(provider.poll_clubs)
        return value if current() else None

    async def mutate(self, provider: ClubsWriter, draft: dict, current: Current, *,
                     club_id: str | None = None, create: bool = False,
                     preference: bool = False) -> dict | None:
        if not current():
            return None
        # Keep one dispatch with the caller's exact idempotency draft. An
        # uncertain outcome propagates; retries belong to the explicit UI action.
        if preference:
            result = await asyncio.to_thread(provider.set_club_preferences, draft)
        elif create:
            result = await asyncio.to_thread(provider.create_club, draft)
        else:
            result = await asyncio.to_thread(provider.club_action, club_id, draft)
        return result if current() else None
