"""Headless validated activity reads and account-scoped cache loading."""
import asyncio
from .models import project_activity,team_evaluations
from .ports import ActivityProvider,ActivityContext,ActivityCache


class StaleActivityContext(Exception):
    """A queued read no longer belongs to the captured account/cursus."""


class ActivityService:
    def __init__(self,context: ActivityContext | None=None):self.context=context

    def cursus_matches(self,cursus):return self.context.cursus_matches(cursus) if self.context else True

    @staticmethod
    def key(read_scope,cursus,campus,project,team=None):
        return (read_scope,'activity-history' if team is None else 'activity-evaluations',cursus,campus,project,team)

    def history(self,provider: ActivityProvider,project,scope,account,*,refresh=False):
        return project_activity(provider.get_project_activity(project,scope,account,refresh=refresh),project,scope,account)

    def evaluations(self,provider: ActivityProvider,project,team,scope,account,*,refresh=False):
        return team_evaluations(provider.get_team_evaluations(project,team,scope,account,refresh=refresh),project,team,scope,account)

    async def read(self,cache: ActivityCache,key,loader,refresh,current):
        async def load():
            def dispatch():
                if not current():raise StaleActivityContext()
                return loader(refresh)
            if not current():raise StaleActivityContext()
            value=await asyncio.to_thread(dispatch)
            if not current():raise StaleActivityContext()
            return value
        return await cache.read(key,load,refresh=refresh,current=current)
