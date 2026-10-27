import asyncio
import unittest

import httpx

from ft_tui.app.read_cache import ReadCache, ReadDeferred, ReadInvalidated, normalize_origin


class ReadCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_reads_share_work_and_return_defensive_copies(self):
        cache = ReadCache()
        key = (('backend', 'account', 1), 'activity-history', 21)
        gate = asyncio.Event()
        calls = []

        async def load():
            calls.append(1)
            await gate.wait()
            return {'source': {'stale': True}, 'items': [1]}

        first = asyncio.create_task(cache.read(key, load))
        second = asyncio.create_task(cache.read(key, load, refresh=True))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertEqual(len(calls), 1)
        first.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await first
        gate.set()
        value = await second
        value['items'].append(2)
        self.assertEqual((await cache.read(key, load))['items'], [1])
        self.assertTrue(cache.peek(key)['source']['stale'])
        self.assertEqual(len(calls), 1)

    async def test_invalidation_and_scope_change_fence_commits(self):
        cache = ReadCache()
        key = (('backend', 'account', 1), 'friend', 'alice')
        commits = []
        gate = asyncio.Event()

        async def late():
            try:
                await gate.wait()
            except asyncio.CancelledError:
                # Model an uncancellable operation that still completes.
                await gate.wait()
            return 'old'

        old = asyncio.create_task(cache.read(key, late, commit=commits.append))
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        cache.invalidate()

        async def newer():
            return 'new'

        self.assertEqual(await cache.read(key, newer, commit=commits.append), 'new')
        gate.set()
        with self.assertRaises(asyncio.CancelledError):
            await old
        self.assertEqual(commits, ['new'])
        current = False
        with self.assertRaises(ReadInvalidated):
            await cache.read(key, newer, current=lambda: current)

    async def test_failures_retain_data_and_respect_retry_after_even_for_manual_refresh(self):
        now = [0]
        cache = ReadCache(clock=lambda: now[0])
        key = (('backend', 'account', 1), 'activity-history')

        async def good():
            return {'peer': {'source': {'stale': True}}, 'automated': {'source': {'status': 'unavailable'}}}

        value = await cache.read(key, good)
        calls = []

        async def limited():
            calls.append(1)
            request = httpx.Request('GET', 'https://example.test')
            response = httpx.Response(429, headers={'Retry-After': '10'}, request=request)
            raise httpx.HTTPStatusError('limited', request=request, response=response)

        with self.assertRaises(httpx.HTTPStatusError):
            await cache.read(key, limited, refresh=True)
        self.assertEqual(cache.peek(key), value)
        with self.assertRaises(ReadDeferred):
            await cache.read(key, limited, refresh=True)
        now[0] = 10
        with self.assertRaises(httpx.HTTPStatusError):
            await cache.read(key, limited)
        self.assertEqual(len(calls), 2)

    async def test_authorization_failure_clears_all_scoped_entries(self):
        cache = ReadCache()
        key = (('backend', 'account', 1), 'friend', 'alice')

        async def good():
            return [1]

        await cache.read(key, good)
        await cache.read((key[0], 'activity-history'), good)

        async def forbidden():
            request = httpx.Request('GET', 'https://example.test')
            raise httpx.HTTPStatusError('forbidden', request=request,
                response=httpx.Response(401, request=request))

        with self.assertRaises(httpx.HTTPStatusError):
            await cache.read(key, forbidden, refresh=True)
        self.assertFalse(cache.entries)

    async def test_resource_forbidden_keeps_other_reads_and_does_not_revoke_account(self):
        cache = ReadCache()
        scope = ('backend', 'account', 1)
        allowed = (scope, 'friend-summary', 'alice')
        restricted = (scope, 'activity-evaluations', 8)
        revoked = []
        cache.on_authorization_lost = revoked.append

        async def good():
            return {'name': 'Alice'}

        await cache.read(allowed, good)
        await cache.read(restricted, good)

        async def forbidden():
            request = httpx.Request('GET', 'https://example.test/evaluations')
            raise httpx.HTTPStatusError('restricted', request=request,
                response=httpx.Response(403, request=request))

        with self.assertRaises(httpx.HTTPStatusError):
            await cache.read(restricted, forbidden, refresh=True)
        self.assertIsNone(cache.peek(restricted))
        self.assertEqual(cache.peek(allowed), {'name': 'Alice'})
        self.assertEqual(await cache.read((scope, 'another-allowed-read'), good), {'name': 'Alice'})
        self.assertEqual(revoked, [])

    async def test_eviction_retention_and_normalized_origin(self):
        now = [0]
        cache = ReadCache(limit=2, retention=100, clock=lambda: now[0])

        async def load():
            return [1]

        for index in range(3):
            await cache.read(('scope', 'resource', index), load)
        self.assertEqual(len(cache.entries), 2)
        self.assertIsNone(cache.peek(('scope', 'resource', 0)))
        now[0] = 100
        self.assertIsNone(cache.peek(('scope', 'resource', 2)))
        self.assertEqual(normalize_origin('HTTPS://user:secret@EXAMPLE.test:443/api/?secret=x#f'),
                         'https://example.test/api')
