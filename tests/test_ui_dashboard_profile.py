import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from textual.widgets import Static, TabbedContent
from rich.console import Console
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.ui.app import FortyTwoTuiApp


class DashboardProfileTests(unittest.IsolatedAsyncioTestCase):
    async def test_profile_remains_inside_card_at_narrow_and_normal_sizes(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "layout.db"}')
            try:
                with factory() as session:
                    save_settings(session, {'onboarding_completed': 'true', 'language': 'en'})
                app = FortyTwoTuiApp(factory, None)
                async with app.run_test(size=(80, 46)) as pilot:
                    app.query_one(TabbedContent).active = 'dashboard'
                    app.account_login = 'mabarrer'
                    app.account_connected = True
                    app.account_profile = {'location': 'e1r2p3', 'wallet': 40, 'correction_point': 5, 'coalition': {'score': 7758, 'rank': 5}}
                    app.icon_mode = 'text'
                    await app._refresh_dashboard()
                    self.assertFalse(app.query("#dashboard-subtitle"))
                    self.assertTrue(app.query("Header"))
                    # Exercise both growing and shrinking without restarting the full app.
                    for width in (80, 120, 160, 80):
                        with self.subTest(width=width):
                            await pilot.resize_terminal(width, 46)
                            await pilot.pause()
                            card = app.query_one('#dashboard-profile-card')
                            for name in ('login', 'level', 'grade', 'wallet', 'correction-points', 'portrait'):
                                widget = app.query_one(f'#dashboard-{name}')
                                self.assertGreater(widget.region.width, 0)
                                self.assertLessEqual(widget.region.right, card.content_region.right)
                                self.assertLessEqual(widget.region.bottom, card.content_region.bottom)
                            self.assertGreaterEqual(app.query_one('#dashboard-login').region.width, len('mabarrer'))
                            if not card.has_class('compact-profile'):
                                self.assertEqual(app.query_one('#dashboard-login').region.y, app.query_one('#dashboard-portrait').region.y)
                            for name in ('wallet', 'correction-points', 'coalition-score', 'coalition-rank'):
                                widget = app.query_one(f'#dashboard-{name}')
                                self.assertTrue(app.query_one('#dashboard-balances').content_region.contains_region(widget.region))
                            self.assertEqual(app.query_one('#dashboard-level').region.y - app.query_one('#dashboard-login').region.bottom, 1)
                            self.assertLess(app.query_one('#dashboard-level').region.y, app.query_one('#dashboard-grade').region.y)
                            last_detail = '#dashboard-grade' if card.has_class('compact-profile') else '#dashboard-campus'
                            self.assertLessEqual(app.query_one(last_detail).region.bottom, app.query_one('#dashboard-balances').region.y)
                            self.assertFalse(app.query('#dashboard-wallet-label, #dashboard-correction-label'))
            finally:
                factory.kw['bind'].dispose()

    async def test_progress_list_scrolls_and_closes_on_small_terminal(self):
        from textual.app import App
        from textual.containers import VerticalScroll
        from ft_tui.features.dashboard.views.progress import ProgressProjects

        class Harness(App):
            language = 'en'

        app = Harness()
        async with app.run_test(size=(40, 20)) as pilot:
            app.push_screen(ProgressProjects('Completed', tuple(f'Project {i}' for i in range(50))))
            await pilot.pause()
            listing = app.screen.query_one('#progress-projects-list', VerticalScroll)
            self.assertGreater(listing.max_scroll_y, 0)
            self.assertLessEqual(app.screen.query_one('#progress-projects-close').region.bottom, 20)
            listing.focus()
            await pilot.press('end')
            await pilot.pause()
            self.assertGreater(listing.scroll_y, 0)
            await pilot.press('escape')
            await pilot.pause()
            self.assertEqual(len(app.screen_stack), 1)

    def test_deadline_summary_uses_current_rank_and_track(self):
        from types import SimpleNamespace
        from ft_tui.features.dashboard.views.home import DashboardMixin

        summary = Static()
        def project(name, rank, track, status):
            return SimpleNamespace(name=name, catalog_data={'rank': rank, 'track': track}, status=status)

        app = SimpleNamespace(
            project_curriculum={'selected_rank': {'rank': 2, 'source': 'quest'},
                                'selected_track': {'track': 'new'}},
            projects=dict(enumerate([
                project('Wrong rank', 1, 'new', 'in_progress'),
                project('Wrong track', 2, 'old', 'in_progress'),
                project('Available project', 2, 'new', 'available'),
                project('Current project', 2, 'shared', 'in_progress'),
                project('Completed project', 2, 'new', 'completed'),
            ])),
            _sorted_projects=list,
            query_one=lambda *args: summary,
        )
        DashboardMixin._update_deadline_summary(app)
        self.assertIn('Rank 02', str(summary.render()))
        self.assertIn('Current project · In progress', str(summary.render()))
        self.assertNotIn('Wrong', str(summary.render()))
        app.project_curriculum = {}
        DashboardMixin._update_deadline_summary(app)
        self.assertNotIn('Current project', str(summary.render()))
        self.assertIn('Unavailable', str(summary.render()))

    async def test_identity_grade_and_balances_fit_dashboard(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "dashboard.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
                session.add(Project(slug='libft', name='Libft', setup_status='unknown'))
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    app.query_one(TabbedContent).active = "dashboard"
                    await pilot.pause()
                    app.account_connected = True
                    app.account_profile = {'last_name': 'Doe', 'first_name': 'Jane', 'location': 'e1r2p3', 'wallet': 0, 'correction_point': 7, 'coalition': {'score': 7758, 'rank': 5}, 'campuses': [{'name': 'Paris', 'is_primary': True}], 'cursus_users': [
                        {'cursus_id': 9, 'name': 'Other', 'grade': 'Wrong'},
                        {'cursus_id': 21, 'name': '42cursus', 'grade': 'Cadet', 'level': 12.34}]}
                    await app._refresh_dashboard()
                    await pilot.pause()
                    console = Console(width=40, color_system=None)
                    with console.capture() as captured:
                        console.print(app.query_one('#dashboard-cluster-status', Static).render()._renderable)
                    self.assertIn('e1r2p3', captured.get())
                    self.assertFalse(app.query('#dashboard-first-name, #dashboard-last-name, #dashboard-workstation'))
                    self.assertEqual(str(app.query_one('#dashboard-grade', Static).render()), 'Grade: Cadet')
                    self.assertEqual(str(app.query_one('#dashboard-level', Static).render()), 'Level: 12.34')
                    self.assertGreater(app.query_one('#dashboard-level').region.y, app.query_one('#dashboard-login').region.y)
                    self.assertGreater(app.query_one('#dashboard-grade').region.y, app.query_one('#dashboard-level').region.y)
                    self.assertEqual(str(app.query_one('#dashboard-campus', Static).render()), 'Campus: Paris')
                    self.assertGreater(app.query_one('#dashboard-campus').region.y, app.query_one('#dashboard-grade').region.y)
                    with factory() as session:
                        save_settings(session, {'default_cursus_id': '9'})
                    await app._refresh_dashboard()
                    self.assertEqual(str(app.query_one('#dashboard-grade', Static).render()), 'Grade: Wrong')
                    self.assertEqual(str(app.query_one('#dashboard-level', Static).render()), 'Level: Unavailable')
                    for language, expected in (('fr', 'Grade: Wrong'), ('es', 'Grado: Wrong')):
                        app.language = language
                        await app._refresh_dashboard()
                        self.assertEqual(str(app.query_one('#dashboard-grade', Static).render()), expected)
                    app.language = 'en'
                    await app._refresh_dashboard()
                    self.assertEqual(str(app.query_one('#dashboard-wallet', Static).render()), '0 ₳')
                    self.assertEqual(str(app.query_one('#dashboard-correction-points', Static).render()), '7 🪙')
                    self.assertEqual(str(app.query_one('#dashboard-coalition-score', Static).render()), 'Score: 7758')
                    self.assertEqual(str(app.query_one('#dashboard-coalition-rank', Static).render()), 'Rank: 5')
                    self.assertEqual(app.query_one('#dashboard-wallet').region.y, app.query_one('#dashboard-coalition-score').region.y)
                    self.assertEqual(app.query_one('#dashboard-correction-points').region.y, app.query_one('#dashboard-coalition-rank').region.y)
                    self.assertEqual(app.query_one('#dashboard-correction-stat').tooltip, 'Correction points')
                    self.assertTrue(app.query('#dashboard-portrait'))
                    page = app.query_one('#dashboard-page')
                    self.assertLessEqual(page.virtual_size.width, page.size.width)
                    page.scroll_end(animate=False)
                    await pilot.pause()
                    self.assertLessEqual(app.query_one('#dashboard-progress-card').region.bottom, page.region.bottom)
                    for card_id in ('continue', 'notes', 'needs'):
                        card = app.query_one(f'#dashboard-{card_id}-card')
                        self.assertEqual(card.region.height, 14)
                    for button_id in ('dashboard-open-editor', 'dashboard-view-project'):
                        button = app.query_one(f'#{button_id}')
                        card = app.query_one('#dashboard-continue-card')
                        self.assertEqual(button.region.height, 3)
                        self.assertLessEqual(button.region.bottom, card.region.bottom - 2)
                    setup = app.query_one('#dashboard-setup-next')
                    needs = app.query_one('#dashboard-needs-card')
                    self.assertEqual(setup.region.height, 3)
                    self.assertLessEqual(setup.region.bottom, needs.region.bottom - 2)
                    self.assertIn('Unavailable', str(app.query_one('#dashboard-blackhole-date', Static).render()))
                    app.account_profile = {}
                    await app._refresh_dashboard()
                    self.assertEqual(str(app.query_one('#dashboard-grade', Static).render()), 'Grade: Unavailable')
                    self.assertEqual(str(app.query_one('#dashboard-coalition-score', Static).render()), '')
                    self.assertEqual(str(app.query_one('#dashboard-wallet', Static).render()), 'Unavailable')
                    self.assertEqual(str(app.query_one('#dashboard-cluster-status', Static).render()), 'Unavailable')
                    cluster_button = app.query_one('#dashboard-cluster-map')
                    self.assertEqual(cluster_button.region.height, 3)
                    self.assertLessEqual(cluster_button.region.bottom, app.query_one('#dashboard-cluster-card').region.bottom - 1)
                    await pilot.click('#dashboard-cluster-map')
                    self.assertEqual(app.query_one(TabbedContent).active, 'cluster-map')
                    app.query_one(TabbedContent).active = 'dashboard'
                    app.account_profile = {'location': 'old-host'}
                    app.account_connected = False
                    await app._refresh_dashboard()
                    self.assertEqual(str(app.query_one('#dashboard-cluster-status', Static).render()), 'Unavailable')
                    self.assertEqual(str(app.query_one('#dashboard-grade', Static).render()), 'Grade: Unavailable')
            finally:
                factory.kw['bind'].dispose()

    async def test_journey_uses_selected_track_and_switches_to_specializations_after_common_core(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "journey.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    await pilot.pause()
                    rows = []
                    for official, name, track, section, status in (
                        (1, 'Core completed', 'new', 'common-core', 'completed'),
                        (2, 'Core next', 'shared', 'common-core', 'in_progress'),
                        (3, 'A wrong track', 'old', 'common-core', 'in_progress'),
                        (4, 'Spec next', 'new', 'specialization', 'in_progress'),
                        (5, 'Spec completed', 'shared', 'specialization', 'completed'),
                        (6, 'A wrong spec', 'old', 'specialization', 'in_progress'),
                        (7, 'Unclassified', None, 'other', 'completed'),
                        (8, 'Local project', None, None, 'completed'),
                    ):
                        project = Project(official_project_id=official, slug=str(official), name=name,
                                          setup_status=status)
                        project._catalog_data = {'track': track, 'section': section}
                        rows.append(project)
                    app.projects = {p.ui_key: p for p in rows}
                    app.project_curriculum = {'selected_track': {'track': 'new'},
                                              'selected_rank': {'source': 'quest', 'completed': False}}
                    async def check(next_name):
                        await app._refresh_dashboard()
                        self.assertEqual(str(app.query_one('#dashboard-progress-value', Static).render()), '01 / 02')
                        self.assertIn('50%', str(app.query_one('#dashboard-progress-caption', Static).render()))
                        self.assertEqual(str(app.query_one('#dashboard-progress-next-name', Static).render()), next_name)
                        self.assertIn('ACTIVE 1', str(app.query_one('#dashboard-progress-active', Static).render()))
                    await check('Core next')
                    app.query_one(TabbedContent).active = 'dashboard'
                    await pilot.pause()
                    self.assertIn('Core completed', str(app.query_one('#dashboard-progress-segment-done').tooltip))
                    self.assertIn('green', str(app.query_one('#dashboard-progress-segment-done').tooltip.spans[0].style))
                    self.assertIn('#15d3c1', str(app.query_one('#dashboard-progress-active').tooltip.spans[0].style))
                    self.assertIn('Core next', str(app.query_one('#dashboard-progress-active').tooltip))
                    for width in (80, 160):
                        await pilot.resize_terminal(width, 46)
                        await pilot.pause()
                        bar = app.query_one('#dashboard-progress-bar')
                        done = app.query_one('#dashboard-progress-segment-done')
                        active = app.query_one('#dashboard-progress-segment-active')
                        self.assertEqual(bar.region.height, 2)
                        self.assertEqual(done.region.height, bar.content_region.height)
                        self.assertLessEqual(abs(done.region.width - active.region.width), 1)
                        self.assertEqual(done.region.width + active.region.width, bar.content_region.width)
                    app.query_one('#dashboard-progress-active').focus()
                    await pilot.press('enter')
                    await pilot.pause()
                    self.assertIn('Core next', str(app.screen.query_one('#progress-projects-list Static').render()))
                    await pilot.press('escape')
                    await pilot.pause()
                    app.query_one('#dashboard-progress-locked').focus()
                    await pilot.press('enter')
                    await pilot.pause()
                    self.assertIn('No projects', str(app.screen.query_one('#progress-projects-list Static').render()))
                    await pilot.press('escape')
                    await pilot.pause()
                    # Authoritative quest completion changes the stage.
                    app.project_curriculum['selected_rank']['completed'] = True
                    await check('Spec next')
                    self.assertIn('Spec next', str(app.query_one('#dashboard-progress-active').tooltip))
                    # The scoped CC completion checkbox also changes the stage.
                    app.project_curriculum['selected_rank']['completed'] = False
                    app.account_connected = True
                    app.account_id = '42'
                    app.goals_scope = (app.account_generation, '42', 21)
                    app.account_goals = {'status': 'available', 'cc_validated': True}
                    await check('Spec next')
                    app.goals_scope = (app.account_generation, 'other-account', 21)
                    await check('Core next')
                    app.project_curriculum = {}
                    await app._refresh_dashboard()
                    self.assertEqual(str(app.query_one('#dashboard-progress-value', Static).render()), '00 / 00')
            finally:
                factory.kw['bind'].dispose()

    async def test_completed_projects_are_never_suggested_for_continuation(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "continue.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
                session.add_all([Project(slug='done', name='Done', setup_status='completed'),
                                 Project(slug='next', name='Next', setup_status='in_progress')])
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 46)):
                    done = next(p for p in app.projects.values() if p.slug == 'done')
                    pending = next(p for p in app.projects.values() if p.slug == 'next')
                    app.selected_project_key = done.ui_key
                    app.active_project_id = done.id
                    await app._refresh_dashboard()
                    self.assertEqual(app.dashboard_continue_key, pending.ui_key)
                    app.active_project_id = None
                    await app._refresh_dashboard()
                    self.assertEqual(app.dashboard_continue_key, pending.ui_key)
                    pending.status = 'done'
                    await app._refresh_dashboard()
                    self.assertIsNone(app.dashboard_continue_key)
                    self.assertTrue(app.query_one('#dashboard-view-project').disabled)
            finally:
                factory.kw['bind'].dispose()

    async def test_deadline_countdown_follows_date_and_uses_theme_urgency(self):
        from datetime import datetime, timedelta, timezone
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "deadlines.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    app.query_one(TabbedContent).active = 'dashboard'
                    app.account_connected = True
                    app.account_id = '42'
                    app.goals_scope = (app.account_generation, '42', 21)
                    today = datetime.now(timezone.utc).date()
                    for days, urgency in ((28, 'approaching'), (3, 'urgent'), (-2, 'urgent'), (90, 'comfortable')):
                        target = today + timedelta(days=days)
                        app.account_goals = dict(status='available', next_milestone=target.isoformat(), cc_eta=(today + timedelta(days=240)).isoformat())
                        app._update_black_hole()
                        await pilot.pause()
                        milestone = app.query_one('#dashboard-blackhole-days', Static)
                        text = str(milestone.render())
                        countdown = f'{days} days left' if days >= 0 else '2 days overdue'
                        self.assertGreater(text.index(countdown), text.index(target.strftime('%d/%m/%Y')))
                        self.assertIn(target.strftime('%d/%m/%Y'), text)
                        self.assertEqual(milestone.tooltip, countdown)
                        common_core = app.query_one('#dashboard-blackhole-date', Static)
                        self.assertEqual(common_core.tooltip, '240 days left')
                        self.assertIn('240 days left', str(common_core.render()))
                        self.assertEqual(milestone.region.y, common_core.region.y)
                        self.assertLessEqual(milestone.region.right, common_core.region.x)
                        self.assertTrue(milestone.has_class(urgency))
                        self.assertEqual(milestone.region.intersection(app.query_one('#dashboard-blackhole-card').content_region), milestone.region)
                        summary = app.query_one('#dashboard-deadline-summary', Static)
                        card = app.query_one('#dashboard-blackhole-card')
                        self.assertEqual(summary.region.intersection(card.content_region), summary.region)
                        self.assertGreaterEqual(milestone.content_region.height, 4)
                    app.account_goals = dict(status='unavailable')
                    app._update_black_hole()
                    self.assertFalse(milestone.has_class('urgent'))
                    self.assertIsNone(milestone.tooltip)
                    self.assertIsNone(common_core.tooltip)
                    self.assertFalse(app.query_one('#dashboard-goals-status').display)
            finally:
                factory.kw['bind'].dispose()

    async def test_pace_deadlines_activity_and_cursus_isolation(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "goals.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 46)) as pilot:
                    app.query_one(TabbedContent).active = 'dashboard'
                    app.account_connected = True
                    app.account_id = '42'
                    app.goals_scope = (app.account_generation, '42', 21)
                    app.account_goals = dict(status='available', stale=False, cc_validated=False,
                                             probationary_period=True, next_milestone='2026-10-31',
                                             cc_eta='2027-10-18', edtrax_weeks=[
                                                 dict(name='Last Week', hours=0, text='Extremely low'),
                                                 dict(name='W-2', hours=32, text='Medium')])
                    await app._refresh_dashboard()
                    await pilot.pause()
                    self.assertIn('31/10/2026', str(app.query_one('#dashboard-blackhole-days', Static).render()))
                    self.assertIn('18/10/2027', str(app.query_one('#dashboard-blackhole-date', Static).render()))
                    self.assertIn('Probationary', str(app.query_one('#dashboard-goals-status', Static).render()))
                    self.assertNotIn('Medium', str(app.query_one('#dashboard-activity-heatmap', Static).render()))
                    self.assertIn('M T W T F S S', str(app.query_one('#dashboard-activity-heatmap', Static).render()))
                    self.assertIn('WEEKLY CODING', str(app.query_one('#dashboard-activity-title', Static).render()))
                    page = app.query_one('#dashboard-page')
                    self.assertLessEqual(page.virtual_size.width, page.size.width)
                    page.scroll_end(animate=False)
                    await pilot.pause()
                    self.assertLessEqual(app.query_one('#dashboard-progress-card').region.bottom, page.region.bottom)
                    app.account_goals['cc_validated'] = True
                    app._update_black_hole()
                    self.assertIn('Completed', str(app.query_one('#dashboard-blackhole-days', Static).render()))
                    app.account_goals = dict(status='not_applicable')
                    app._update_black_hole()
                    self.assertIn('Not applicable', str(app.query_one('#dashboard-blackhole-date', Static).render()))
                    app.goals_scope = (app.account_generation, 'other-account', 21)
                    app._update_black_hole()
                    self.assertIn('Unavailable', str(app.query_one('#dashboard-blackhole-days', Static).render()))
            finally:
                factory.kw['bind'].dispose()
