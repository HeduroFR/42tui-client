"""Profile projections and polling decisions, independent of Textual and storage."""
import asyncio
import time
from collections.abc import Callable
from .ports import ProfileRepository, CursusSelection, GoalsReader
from .state import ProfileState


class ProfileService:
    def __init__(self, repository: ProfileRepository, selection: CursusSelection,
                 *, state: ProfileState | None = None, clock: Callable[[], float] | None = None):
        self.repository = repository
        self.selection = selection
        self.state = ProfileState() if state is None else state
        self._clock = clock

    def now(self):
        return time.monotonic() if self._clock is None else self._clock()

    def cursus_id(self):
        return self.selection.configured_cursus()

    def cached_profile(self, client):
        return self.repository.load_profile(client)

    def persist_profile(self, client, profile):
        self.repository.save_profile(client, profile)

    def cached_goals(self, account, cursus):
        return self.repository.load_goals(account, cursus)

    def current_goals(self, scope, *, connected):
        return self.state.goals if connected and self.state.goals_scope == scope else {}

    def should_refresh(self, provider, scope, *, connected):
        _, account, cursus = scope
        return bool(connected and account and cursus and callable(getattr(provider, 'get_goals', None))
                    and (scope != self.state.goals_scope or self.now() >= self.state.next_poll))

    async def refresh_goals(self, provider: GoalsReader, scope, current: Callable[[], bool], *, client):
        if not current():
            return False
        _, account, cursus = scope
        try:
            value = await asyncio.to_thread(provider.get_goals, cursus, account)
        except Exception:
            value = {'status': 'unavailable', 'stale': True}
        if not current():
            return False
        if value.get('status') in {'available', 'not_applicable'}:
            self.repository.save_goals(account, cursus, value)
            self.repository.save_profile(client, self.state.profile)
            self.state.goals = value
        elif self.state.goals_scope == scope and self.state.goals.get('status') in {'available', 'not_applicable'}:
            self.state.goals = {**self.state.goals, 'stale': True}
        else:
            self.state.goals = value
        self.state.goals_scope = scope
        self.state.next_poll = self.now() + (
            900 if value.get('status') in {'available', 'not_applicable'} and not value.get('stale') else 30
        )
        return True
