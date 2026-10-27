"""Headless social operations with explicit publish fences and no write retries."""
import asyncio
from collections.abc import Callable
from .ports import ConfirmedFriendRepository, SocialActions, SocialReader

Current = Callable[[], bool]


class SocialService:
    def __init__(self, repository: ConfirmedFriendRepository):
        self.repository = repository

    async def snapshot(self, provider: SocialReader, account: str, current: Current, *, origin=''):
        if not current() or not callable(getattr(provider, 'get_social', None)):
            return None
        value = await asyncio.to_thread(provider.get_social)
        if not current() or value['account_id'] != account:
            return None
        # The provider owns response validation. Persist only its confirmed list,
        # never outgoing requests or client-local watches as inferred consent.
        self.repository.cache_confirmed(account, value['friends'], origin=origin)
        return value

    async def mutate(self, provider: SocialActions, draft: dict, current: Current):
        if not current():
            return None
        # Keep the caller's exact operation UUID and signed content. An uncertain
        # response propagates; this layer never creates another operation/retry.
        value = await asyncio.to_thread(provider.social_action, draft)
        return value if current() else None

    async def neighbours(self, provider: SocialReader, current: Current):
        if not current() or not callable(getattr(provider, 'get_poke_neighbours', None)):
            return None
        value = await asyncio.to_thread(provider.get_poke_neighbours)
        return value if current() else None

    async def sender_profile(self, provider, account: str, current: Current):
        if not current() or not callable(getattr(provider, 'get_student_profile', None)):
            return None
        value = await asyncio.to_thread(provider.get_student_profile, account)
        if not current() or value.get('user_id') != account:
            return None
        return value
