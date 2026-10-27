"""Bounded read coordination, independent of app, UI and storage implementations."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from math import isfinite
from time import monotonic
from .context import normalize_origin










class ReadInvalidated(asyncio.CancelledError):
    """A result belongs to a discarded scope or revision."""


class ReadDeferred(RuntimeError):
    """A retry deadline is active; callers retain eligible snapshots."""


@dataclass
class Entry:
    token: object = field(default_factory=object)
    value: object = None
    validated_at: float = float('-inf')
    retry_at: float = 0
    failures: int = 0
    error: Exception | None = None


class ReadCache:
    def __init__(self, *, limit=256, retention=3600, clock=monotonic):
        self.limit = limit
        self.retention = retention
        self.clock = clock
        self.entries = OrderedDict()
        self.inflight = {}
        self.on_authorization_lost = lambda scope: None
        self.revoked = {}

    def _entry(self, key):
        entry = self.entries.get(key)
        if entry is None:
            entry = self.entries[key] = Entry()
        self.entries.move_to_end(key)
        while len(self.entries) > self.limit:
            self.entries.popitem(last=False)
        if len(key) > 1 and str(key[1]).startswith('activity-'):
            activity = [candidate for candidate in self.entries if str(candidate[1]).startswith('activity-')]
            for candidate in activity[:-64]:
                self.entries.pop(candidate, None)
        return entry

    def peek(self, key):
        entry = self.entries.get(key)
        if entry is None or entry.value is None:
            return None
        if self.clock() - entry.validated_at >= self.retention:
            self.entries.pop(key, None)
            return None
        self.entries.move_to_end(key)
        return deepcopy(entry.value)

    def fresh(self, key, ttl=60):
        entry = self.entries.get(key)
        return bool(entry and entry.value is not None and entry.error is None
                    and self.clock() - entry.validated_at < ttl)

    def invalidate(self, predicate=lambda key: True):
        for key in list(self.entries):
            if predicate(key):
                self.entries.pop(key, None)
        # A cancelled consumer does not cancel shared work. An invalidation does.
        for (key, token), task in list(self.inflight.items()):
            if predicate(key) and task is not asyncio.current_task():
                task.cancel()

    def clear(self):
        self.invalidate()

    def _retry_delay(self, error, failures):
        response = getattr(error, 'response', None)
        header = response.headers.get('Retry-After') if response is not None else None
        if header:
            try:
                delay = float(header)
                if isfinite(delay):
                    return max(0, delay)
            except ValueError:
                try:
                    return max(0, (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds())
                except (ValueError, TypeError):
                    pass
        return min(60, 2 ** min(failures, 6))

    async def read(self, key, loader, *, refresh=False, ttl=60, current=lambda: True, commit=None):
        """Read with shared work; loader validates, commit persists on the loop.

        UI consumers use peek before awaiting this method to keep stale content
        visible. The supplied current predicate checks app scope, not widget life.
        """
        if not current():
            raise ReadInvalidated()
        if key[0] in self.revoked:
            raise self.revoked[key[0]]
        entry = self._entry(key)
        if not refresh and self.fresh(key, ttl):
            return deepcopy(entry.value)
        identity = (key, entry.token)
        task = self.inflight.get(identity)
        if task is None:
            if self.clock() < entry.retry_at:
                raise ReadDeferred('Rate limited; retry later.')
            if len(self.inflight) >= self.limit:
                raise ReadDeferred('Too many reads; retry later.')

            async def fetch():
                try:
                    value = await loader()
                    if not current() or self.entries.get(key) is not entry:
                        raise ReadInvalidated()
                    if commit is not None:
                        commit(value)
                    entry.value = deepcopy(value)
                    entry.validated_at = self.clock()
                    entry.retry_at = entry.failures = 0
                    entry.error = None
                    return value
                except Exception as error:
                    if current() and self.entries.get(key) is entry:
                        status = getattr(getattr(error, 'response', None), 'status_code', None)
                        if status == 401:
                            # Invalidate all reads sharing this authorization scope.
                            scope = key[0]
                            self.invalidate(lambda candidate: candidate[0] == scope)
                            self.revoked[scope] = error
                            self.on_authorization_lost(scope)
                        elif status == 403:
                            # A restricted resource does not invalidate the session.
                            self.invalidate(lambda candidate: candidate == key)
                        else:
                            entry.error = error
                            entry.failures += 1
                            entry.retry_at = self.clock() + self._retry_delay(error, entry.failures)
                    raise
                finally:
                    self.inflight.pop(identity, None)

            task = asyncio.create_task(fetch())
            self.inflight[identity] = task
            # Retrieve exceptions even if every widget has detached.
            task.add_done_callback(lambda task: None if task.cancelled() else task.exception())
        return deepcopy(await asyncio.shield(task))
