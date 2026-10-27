"""Headless correction operations, guarded at dispatch and never retried."""
import asyncio
from collections.abc import Callable
from .model import Slot, group_slots
from .ports import CorrectionsProvider

Current = Callable[[], bool]

class StaleCorrectionsContext(Exception):
    """The captured account/provider/view context no longer owns this request."""

class MutationFailure(Exception):
    """A single attempt failed, possibly after earlier deletions succeeded."""
    def __init__(self, error, completed=0):
        super().__init__(str(error))
        self.error = error
        self.completed = completed

class CorrectionsService:
    def __init__(self, provider: CorrectionsProvider | None = None):
        self.provider = provider

    async def _dispatch(self, method, *args, current):
        def dispatch():
            # Check in the executor too: the account can change while queued.
            if not current():
                raise StaleCorrectionsContext()
            return method(*args)
        if not current():
            raise StaleCorrectionsContext()
        value = await asyncio.to_thread(dispatch)
        if not current():
            raise StaleCorrectionsContext()
        return value

    async def snapshot(self, begin, end, *, account_id, current, provider=None):
        provider = provider if provider is not None else self.provider
        value = await self._dispatch(provider.get_correction_slots, begin, end, current=current)
        if (not isinstance(value, dict) or value.get('account_id') != str(account_id)
                or not isinstance(value.get('account_id'), str)
                or not value['account_id'].isascii() or not value['account_id'].isdigit()
                or int(value['account_id']) < 1 or type(value.get('can_write')) is not bool
                or not isinstance(value.get('slots'), (tuple, list)) or len(value['slots']) > 3000
                or any(not isinstance(slot, Slot) for slot in value['slots'])):
            raise ValueError('Invalid correction slots snapshot or account changed')
        # Revalidate duplicate identities at the service boundary as well as HTTP.
        group_slots(value['slots'])
        return value

    async def save(self, slot, begin, end, *, current, provider=None):
        if slot is not None and (not isinstance(slot, Slot) or slot.booked):
            raise ValueError('Booked slots cannot be changed')
        Slot(('1',), begin, end)
        provider = provider if provider is not None else self.provider
        try:
            return await self._dispatch(provider.save_correction_slot, slot, begin, end, current=current)
        except StaleCorrectionsContext:
            raise
        except Exception as error:
            raise MutationFailure(error) from error

    async def delete(self, slots, *, current, provider=None):
        targets = tuple(slots)
        if not targets or any(not isinstance(slot, Slot) or slot.booked for slot in targets):
            raise ValueError('Only available slots can be deleted')
        group_slots(targets)
        provider = provider if provider is not None else self.provider
        completed = 0
        try:
            for target in targets:
                await self._dispatch(provider.delete_correction_slot, target, current=current)
                completed += 1
        except StaleCorrectionsContext:
            raise
        except Exception as error:
            raise MutationFailure(error, completed) from error
        return completed
