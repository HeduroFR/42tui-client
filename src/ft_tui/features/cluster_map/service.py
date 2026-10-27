"""Headless cluster reads and single-attempt reports, fenced by caller context."""
import asyncio
from collections.abc import Callable
from .ports import ClusterReader,ClusterReporter,ClusterRepository

Current=Callable[[],bool]


class ClusterService:
    def __init__(self,repository: ClusterRepository | None):
        self.repository=repository

    def memberships(self,account,*,origin=''):
        return self.repository.memberships(account,origin=origin) if self.repository else []

    def configured_cursus(self):
        return self.repository.configured_cursus() if self.repository else None

    def portrait_directory(self,account,origin):
        return self.repository.portrait_directory(account,origin) if self.repository else None

    async def _read(self,operation,current,*args,**kwargs):
        if not current():return None
        def dispatch():
            # The account may change while this work waits for the executor.
            if not current():return None
            return operation(*args,**kwargs)
        result=await asyncio.to_thread(dispatch)
        return result if current() else None

    async def map(self,provider: ClusterReader,current: Current):
        return await self._read(provider.get_cluster_map,current)

    async def portrait(self,provider: ClusterReader,hostname,current: Current):
        return await self._read(provider.get_cluster_portrait,current,hostname)

    async def issues(self,provider: ClusterReader,hostname,current: Current,*,include_resolved=False,cursor=None):
        return await self._read(provider.get_cluster_issues,current,hostname,include_resolved=include_resolved,cursor=cursor)

    async def options(self,provider: ClusterReader,current: Current):
        return await self._read(provider.get_cluster_issue_options,current)

    async def submit(self,provider: ClusterReporter,hostname,draft,idempotency_key,current: Current):
        # Preserve the reviewed payload and UUID; uncertain outcomes propagate.
        result=await self._read(provider.submit_cluster_issue,current,hostname,draft,idempotency_key)
        if result is not None and (result.get('hostname')!=hostname or result.get('status')!='submitted'):
            raise ValueError('Unknown outcome')
        return result

    async def person(self,provider: ClusterReader,login,cursus,user_id,current: Current):
        options={'user_id':user_id} if user_id else {}
        data=await self._read(provider.get_friend,current,login,cursus,**options)
        if data is None:return None
        if user_id and data.get('user_id')!=user_id:raise ValueError('Person identity changed')
        main=data.get('main_cursus_id')
        if main and main!=cursus:
            expected=options.get('user_id') or data.get('user_id')
            if not expected:raise ValueError('Missing person identity')
            options['user_id']=expected
            data=await self._read(provider.get_friend,current,login,main,**options)
            if data is None:return None
            if data.get('cursus_id')!=main:raise ValueError('Cursus identity changed')
            if data.get('main_cursus_id') not in (None,main):raise ValueError('Main cursus changed')
        if options.get('user_id') and data.get('user_id')!=options['user_id']:raise ValueError('Person identity changed')
        return data
