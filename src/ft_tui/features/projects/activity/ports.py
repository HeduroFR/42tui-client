"""Provider, scoped cache and configured-cursus capabilities."""
from typing import Protocol


class ActivityProvider(Protocol):
    def get_project_activity(self,project_id,scope,account_id,*,refresh=False): ...
    def get_team_evaluations(self,project_id,team_id,scope,account_id,*,refresh=False): ...


class ActivityContext(Protocol):
    def cursus_matches(self,cursus) -> bool: ...


class ActivityCache(Protocol):
    async def read(self,key,loader,*,refresh,current): ...
