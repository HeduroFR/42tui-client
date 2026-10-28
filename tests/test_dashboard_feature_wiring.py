"""Composition and stale UI frames preserve single state ownership."""
import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project, DevNote
from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import ListView


class DashboardFeatureWiringTests(unittest.IsolatedAsyncioTestCase):
    def test_shell_aliases_forward_to_profile_and_dashboard_owned_state(self):
        factory = make_session_factory('sqlite:///:memory:')
        try:
            app = FortyTwoTuiApp(factory, None)
            self.assertIs(app.profile_state, app.profile_service.state)
            app.account_profile = {'wallet': 0}
            self.assertIs(app.account_profile, app.profile_state.profile)
            app.account_goals = {'status': 'pending'}
            self.assertIs(app.account_goals, app.profile_state.goals)
            app.dashboard_continue_key = 'selected'
            self.assertEqual(app.dashboard_state.continue_key, 'selected')
        finally:
            factory.kw['bind'].dispose()

    async def test_older_dashboard_refresh_cannot_append_stale_notes_after_newer_frame(self):
        factory = make_session_factory('sqlite:///:memory:')
        at = datetime(2026, 10, 26, 12)
        try:
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
                project = Project(slug='one', name='One'); session.add(project); session.flush()
                note = DevNote(project_id=project.id, title='Initial', updated_at=at)
                session.add(note); session.commit(); note_id = note.id
            app = FortyTwoTuiApp(factory, None)
            async with app.run_test(size=(160, 46)) as pilot:
                await pilot.pause()
                notes = app.query_one('#dashboard-recent-notes', ListView)
                original_clear = notes.clear
                started, release = asyncio.Event(), asyncio.Event()
                first = [True]
                async def delayed_clear():
                    await original_clear()
                    if first[0]:
                        first[0] = False; started.set(); await release.wait()
                def rename(title, tick):
                    with factory() as session:
                        row = session.get(DevNote, note_id); row.title = title
                        row.updated_at = at+timedelta(seconds=tick); session.commit()
                rename('Older frame', 1)
                with patch.object(notes, 'clear', side_effect=delayed_clear):
                    old = asyncio.create_task(app._refresh_dashboard())
                    try:
                        await asyncio.wait_for(started.wait(), 3)
                        rename('Latest frame', 2)
                        new = asyncio.create_task(app._refresh_dashboard())
                        await asyncio.sleep(.02)
                    finally:
                        release.set()
                    await asyncio.gather(old, new)
                self.assertEqual(app.dashboard_recent_notes_signature[0][3], 'Latest frame')
                self.assertEqual(len(notes.children), 1)
        finally:
            factory.kw['bind'].dispose()

    async def test_activity_callback_after_project_list_removal_is_safe(self):
        factory = make_session_factory('sqlite:///:memory:')
        try:
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
            app = FortyTwoTuiApp(factory, None)
            async with app.run_test() as pilot:
                await pilot.pause()
                await app.query_one('#project-list-view', ListView).remove()
                await app._refresh_activity_order()
        finally:
            factory.kw['bind'].dispose()

    async def test_activity_callback_rechecks_view_after_await_and_stops_on_shutdown(self):
        factory = make_session_factory('sqlite:///:memory:')
        try:
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
            app = FortyTwoTuiApp(factory, None)
            async with app.run_test() as pilot:
                await pilot.pause()
                started, release = asyncio.Event(), asyncio.Event()
                async def refresh():
                    started.set()
                    await release.wait()
                with patch.object(app, '_refresh_dashboard', side_effect=refresh):
                    callback = asyncio.create_task(app._refresh_activity_order())
                    await asyncio.wait_for(started.wait(), 3)
                    await app.query_one('#project-list-view', ListView).remove()
                    release.set()
                    await callback
                stop_patch = patch.object(app.activity_refresh_timer, 'stop', wraps=app.activity_refresh_timer.stop)
                stop = stop_patch.start()
                app.exit()
            try:
                stop.assert_called_once()
                await app._refresh_activity_order()
            finally:
                stop_patch.stop()
        finally:
            factory.kw['bind'].dispose()
