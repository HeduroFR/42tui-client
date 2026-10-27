"""Opt-in, isolated Textual cache profiling; no network or user database access.

Run from the checkout: PYTHONPATH=src:tests python tests/manual/cache_profile.py
    --output docs/cache-baseline.json --revisits 20
"""
from __future__ import annotations

import argparse
import asyncio
import gc
from copy import deepcopy
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import threading
from time import perf_counter

from textual.app import App
from textual.widgets import DataTable, Static, TabbedContent, TabPane

from ft_tui.features.catalog.models import CatalogScope
from ft_tui.db.database import make_session_factory
from ft_tui.features.friends.adapters.storage import cache_mutual_friends, save_observation
from ft_tui.features.friends.views.workspace import FriendsWorkspace
from ft_tui.features.projects.views.activity import ProjectActivityScreen, open_project_activity
from activity_fixtures import history, evaluations
from friends_fixtures import snapshot


class MeasuredProvider:
    """Synchronous provider with a bounded gate and per-operation timings."""

    def __init__(self):
        self.mode = 'normal'
        self.calls = []
        self.gate = threading.Event()
        self.gate.set()
        self._lock = threading.Lock()

    def read(self, resource, value, refresh=False):
        start = perf_counter()
        try:
            if self.mode == 'delayed' and not self.gate.wait(5):
                raise TimeoutError('Profiling gate was not released')
            if self.mode == 'unavailable':
                raise OSError('Synthetic offline provider')
            return deepcopy(value)
        finally:
            with self._lock:
                self.calls.append({'resource': resource, 'refresh': refresh,
                                   'wait_ms': (perf_counter() - start) * 1000})

    def get_friend(self, login, cursus_id, *, refresh=False, **kwargs):
        return self.read('friend:' + login, snapshot(login, user_id='42' if login == 'you' else '50'), refresh)

    def get_project_activity(self, *args, refresh=False):
        return self.read('history', history(), refresh)

    def get_team_evaluations(self, project, team, *args, refresh=False):
        return self.read('evaluations', evaluations(team), refresh)


class FriendsHarness(App):
    language = 'en'
    account_id = '42'
    account_login = 'you'
    account_generation = 0
    account_connected = False

    def __init__(self, factory, provider):
        super().__init__()
        self.session_factory = factory
        self.provider = provider

    def _configured_cursus_id(self, session):
        return 21

    def compose(self):
        with TabbedContent(initial='friends'):
            with TabPane('Friends', id='friends'):
                yield FriendsWorkspace()
            with TabPane('Other', id='other'):
                yield Static('Other screen')


class ActivityHarness(App):
    language = 'en'
    account_id = '42'
    account_generation = 0

    def __init__(self, provider):
        super().__init__()
        self.provider = provider

    def compose(self):
        yield Static('Project browser')


async def frame(widget):
    """Wait for the next actual Textual refresh, excluding Pilot.pause defaults."""
    done = asyncio.Event()
    app = widget if isinstance(widget, App) else widget.app
    app.screen.refresh()
    app.screen.call_after_refresh(done.set)
    await asyncio.wait_for(done.wait(), 5)


async def wait_until(predicate):
    deadline = perf_counter() + 8
    while not predicate():
        if perf_counter() > deadline:
            raise TimeoutError('Profiling operation did not settle')
        await asyncio.sleep(.002)


async def measure(provider, widget, action, usable, settled, *, cold=False):
    offset = len(provider.calls)
    provider.gate.clear() if provider.mode == 'delayed' else provider.gate.set()
    # Bound synthetic latency independently of rendering and release on all paths.
    release = asyncio.get_running_loop().call_later(.25, provider.gate.set)
    started = perf_counter()
    collections = []
    collection_starts = {}

    def observe_collection(phase, info):
        identity = (threading.get_ident(), info['generation'])
        if phase == 'start':
            collection_starts[identity] = perf_counter()
        elif identity in collection_starts:
            collections.append({'generation': info['generation'],
                'duration_ms': (perf_counter() - collection_starts.pop(identity)) * 1000})

    gc.callbacks.append(observe_collection)
    try:
        await action()
        action_ms = (perf_counter() - started) * 1000
        frame_started = perf_counter()
        await frame(widget)
        initial_frame_ms = (perf_counter() - frame_started) * 1000
        first = None
        if usable():
            first = (perf_counter() - started) * 1000
        while not settled():
            if first is None and usable():
                await frame(widget)
                first = (perf_counter() - started) * 1000
            if perf_counter() - started > 8:
                raise TimeoutError('Profiling refresh did not settle')
            await asyncio.sleep(.002)
        await frame(widget)
        if first is None and usable():
            first = (perf_counter() - started) * 1000
        calls = provider.calls[offset:]
        return {'usable_ms': first, 'complete_ms': (perf_counter() - started) * 1000,
                'action_ms': action_ms, 'initial_frame_ms': initial_frame_ms,
                'provider_operations': len(calls),
                'provider_wait_ms': sum(call['wait_ms'] for call in calls),
                'gc_collections': collections,
                'calls': calls, 'cold': cold}
    finally:
        gc.callbacks.remove(observe_collection)
        release.cancel()
        provider.gate.set()


async def friends_profile(mode, revisits):
    provider = MeasuredProvider()
    rows = []
    with tempfile.TemporaryDirectory(prefix='42tui-cache-profile-') as directory:
        factory = make_session_factory(f'sqlite:///{directory}/profile.sqlite')
        with factory() as session:
            cache_mutual_friends(session, '42', [{'account_id': '50', 'login': 'alice'}])
        app = FriendsHarness(factory, provider)
        try:
            async with app.run_test(size=(120, 40)):
                workspace = app.query_one(FriendsWorkspace)
                await workspace.reload()
                app.account_connected = True
                provider.mode = mode
                usable = lambda: 'alice' in workspace.snapshots
                settled = lambda: not workspace.busy and not workspace.detail_busy

                async def activate():
                    await workspace.activate()

                rows.append({'scenario': 'cold', **await measure(provider, workspace, activate, usable, settled, cold=True)})
                # Use isolated historical observations even when the cold provider was unavailable.
                if not usable():
                    with factory() as session:
                        save_observation(session, '42', snapshot())
                    workspace.context = None
                    await workspace.reload()
                    await wait_until(settled)
                for index in range(revisits):
                    rows.append({'scenario': 'warm', **await measure(provider, workspace, activate, usable, settled)})

                async def switch_tabs():
                    app.query_one(TabbedContent).active = 'other'
                    await frame(app.screen)
                    app.query_one(TabbedContent).active = 'friends'
                    await workspace.activate()

                rows.append({'scenario': 'tabs', **await measure(provider, workspace, switch_tabs, usable, settled)})

                async def refresh():
                    workspace.start_sync(refresh=True)

                rows.append({'scenario': 'refresh', **await measure(provider, workspace, refresh, usable, settled)})

                async def remove_membership():
                    # Model an authoritative confirmed membership write, without an API mutation.
                    with factory() as session:
                        cache_mutual_friends(session, '42', [])
                    await workspace.reload()

                rows.append({'scenario': 'post-membership-write', **await measure(provider, workspace, remove_membership,
                    lambda: workspace.query_one('#friends-table', DataTable).row_count == 0, settled)})
        finally:
            provider.gate.set()
            factory.kw['bind'].dispose()
    return rows


async def activity_profile(mode, revisits):
    provider = MeasuredProvider()
    app = ActivityHarness(provider)
    rows = []
    try:
        async with app.run_test(size=(120, 40)):
            screen = None

            async def open_screen():
                nonlocal screen
                mounting = open_project_activity(app, 1001, 'Libft', CatalogScope(21, 31), '42', provider, 0, None)
                if mounting is not None:
                    await mounting
                screen = app.screen

            async def opening():
                # The measure widget is the underlying browser so it exists before the push.
                await open_screen()

            usable = lambda: bool(screen and screen.history)
            settled = lambda: bool(screen and not screen._refreshing and all(w.is_finished for w in screen.workers) and (
                screen.evaluations is not None or screen._history_error or not screen.history))
            provider.mode = mode
            rows.append({'scenario': 'cold', **await measure(provider, app.screen, opening, usable, settled, cold=True)})
            if not usable():
                # Fixture setup for the separate warm/offline scenario: discard
                # cold-failure backoff before seeding historical data.
                cache = getattr(app, '_read_cache', None)
                if cache is not None:
                    cache.clear()
                provider.mode = 'normal'
                screen.action_refresh()
                await wait_until(lambda: screen.evaluations is not None and settled())
                provider.mode = mode
            for index in range(revisits):
                closing = screen
                closing.action_close()
                await wait_until(lambda: app.screen is not closing)
                await frame(app.screen)
                rows.append({'scenario': 'warm', **await measure(provider, app.screen, opening, usable, settled)})

            async def refresh():
                screen.action_refresh()

            rows.append({'scenario': 'refresh', **await measure(provider, screen, refresh, usable, settled)})
    finally:
        provider.gate.set()
    return rows


def summary(rows):
    result = {}
    for scenario in dict.fromkeys(row['scenario'] for row in rows):
        selected = [row for row in rows if row['scenario'] == scenario]
        values = sorted(row['usable_ms'] for row in selected if row['usable_ms'] is not None)
        result[scenario] = {'samples': len(selected), 'usable_samples': len(values),
            'usable_p50_ms': statistics.median(values) if values else None,
            'usable_p95_ms': values[math.ceil(len(values) * .95) - 1] if values else None,
            'provider_operations': sum(row['provider_operations'] for row in selected)}
    return result


async def main(args):
    from hashlib import sha256
    report = {'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              'source_sha256': {str(path): sha256(path.read_bytes()).hexdigest() for path in [
                  Path('src/ft_tui/features/friends/views/workspace.py'), Path('src/ft_tui/features/projects/views/activity.py'),
                  Path('src/ft_tui/app/read_cache.py'), Path(__file__).relative_to(Path.cwd())] if path.exists()},
              'environment': {'python': platform.python_version(), 'textual': version('textual'),
                  'platform': platform.platform(), 'machine': platform.machine(), 'terminal': [120, 40]},
              'dataset': {'friends': 1, 'account_profiles': 1, 'teams': 2, 'evaluations_per_team': 2},
              'limitations': ['Synthetic synchronous providers; no HTTP requests or authenticated deployment.',
                  'Provider wait is cumulative across concurrent operations, not elapsed navigation time.',
                  'Headless refresh timings include layout/scheduling; they are not an interactive terminal SLA.',
                  'Post-membership-write measures confirmed local reconciliation, not a network mutation.'],
              'results': {}}
    for pilot, run in [('friends', friends_profile), ('activity', activity_profile)]:
        for mode in ['normal', 'delayed', 'unavailable']:
            rows = await run(mode, args.revisits)
            report['results'][pilot + ':' + mode] = {'summary': summary(rows), 'samples': rows}
            print(pilot, mode, json.dumps(summary(rows)), flush=True)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--revisits', type=int, default=20)
    args = parser.parse_args()
    if args.revisits < 1:
        parser.error('--revisits must be positive')
    asyncio.run(main(args))
