import asyncio
import unittest
from unittest.mock import patch
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from textual.app import App, ComposeResult
from textual.widgets import Input, TabbedContent, TabPane, DataTable
from ft_tui.ui.button import Button
from ft_tui.ui.select import Select
from ft_tui.features.clubs.views.workspace import ClubsWorkspace, ClubsInvitations, ClubForm

CLUB = str(uuid4())
ACTIVITY = str(uuid4())


def fixture():
    now = datetime.now(timezone.utc)
    activity = {'id': ACTIVITY, 'title': 'Babyfoot [red]', 'location': 'Cafeteria', 'organizer_id': '1',
                'minimum': 2, 'capacity': 4, 'participants': ['1'], 'waitlist': [], 'status': 'recruiting',
                'created_at': now.isoformat(), 'expires_at': (now + timedelta(minutes=10)).isoformat()}
    event = {'sequence': 1, 'kind': 'activity', 'actor_id': '1', 'activity_id': ACTIVITY,
             'title': activity['title'], 'message': 'Cafeteria', 'created_at': activity['created_at'], 'expires_at': activity['expires_at']}
    return {'account_id': '2', 'dnd': False, 'bells': {CLUB: True}, 'clubs': [
        {'id': CLUB, 'campus_id': 31, 'name': 'Babyfoot', 'description': 'Play together', 'system': False,
         'archived': False, 'my_role': 'member', 'members': [{'account_id': '1', 'login': 'alice', 'role': 'creator'},
         {'account_id': '2', 'login': 'bob', 'role': 'member'}], 'activities': [activity], 'events': [event]}]}


class Provider:
    def __init__(self):
        self.data = fixture()
        self.notifications = []
        self.calls = []
        self.failure = False
        self.gate = None

    def get_clubs(self, campus):
        if self.gate:
            self.gate.wait(2)
        if self.failure:
            raise RuntimeError('private details')
        return deepcopy(self.data)

    def poll_clubs(self):
        result = {'dnd': self.data['dnd'], 'bells': self.data['bells'], 'notifications': self.notifications}
        self.notifications = []
        return deepcopy(result)

    def set_club_preferences(self, draft):
        self.calls.append(draft)
        if 'dnd' in draft:
            self.data['dnd'] = draft['dnd']
        else:
            self.data['bells'][draft['club_id']] = draft['bell']
        return {k: deepcopy(self.data[k]) for k in ('dnd', 'bells')}

    def club_action(self, club_id, draft):
        self.calls.append((club_id, draft))
        if draft['action'] == 'join':
            self.data['clubs'][0]['activities'][0]['participants'].append('2')
            self.data['clubs'][0]['activities'][0]['status'] = 'ready'
        return deepcopy(self.data['clubs'][0])


class Harness(App):
    BINDINGS = [('ctrl+shift+d', 'dnd', 'DND')]
    def __init__(self):
        super().__init__()
        self.provider = Provider()
        self.account_id = '2'
        self.account_connected = True
        self.account_generation = 0
        self.account_campuses = [{'id': 31, 'name': 'Campus', 'is_primary': True}]
        self.language = 'en'

    def compose(self) -> ComposeResult:
        with TabbedContent(initial='clubs'):
            with TabPane('Clubs', id='clubs'):
                yield ClubsWorkspace()
            with TabPane('Other', id='other'):
                yield Input(id='other-input')
        yield ClubsInvitations()

    def action_dnd(self):
        self.query_one(ClubsWorkspace).toggle_dnd()

    def _activate_main_tab(self, name):
        self.query_one(TabbedContent).active = name


class ClubsTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_wide_workspace_keeps_sidebar_fixed_and_pages_scrollable(self):
        app = Harness()
        async with app.run_test(size=(110, 24)) as pilot:
            await self.settle(app, pilot)
            workspace = app.query_one(ClubsWorkspace)
            sidebar = workspace.query_one('#clubs-sidebar')
            pages = workspace.query_one('#clubs-pages')
            self.assertEqual(sidebar.region.y, workspace.content_region.y)
            self.assertLessEqual(pages.region.bottom, workspace.content_region.bottom)
            self.assertEqual(workspace.max_scroll_y, 0)

    async def settle(self, app, pilot):
        await pilot.pause()
        await app.workers.wait_for_complete()
        await app.query_one(ClubsWorkspace).reload()
        await pilot.pause()

    async def test_join_bell_and_global_dnd_from_another_tab(self):
        app = Harness()
        async with app.run_test(size=(130, 55)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            await w.reload()
            await pilot.pause()
            self.assertEqual(app.query_one('#clubs-activities', DataTable).row_count, 1)
            self.assertFalse(app.query_one('#clubs-do-join', Button).disabled)
            w.mutate({'action': 'join', 'activity_id': ACTIVITY})
            await self.settle(app, pilot)
            self.assertTrue(app.query_one('#clubs-do-join', Button).disabled)
            w.mutate({'club_id': CLUB, 'bell': False}, preference=True)
            await self.settle(app, pilot)
            bell_button = app.query_one('#clubs-bell', Button)
            self.assertIn('off', str(bell_button.tooltip))
            app.query_one(TabbedContent).active = 'other'
            await pilot.pause()
            app.query_one('#other-input', Input).focus()
            await pilot.press('ctrl+shift+d')
            await self.settle(app, pilot)
            self.assertTrue(w.dnd)
            self.assertEqual(app.query_one(TabbedContent).active, 'other')

    async def test_notification_sound_batches_deduplicates_and_respects_local_mute(self):
        app = Harness()
        async with app.run_test(size=(110, 40)) as pilot:
            await self.settle(app, pilot)
            host = app.query_one(ClubsInvitations)
            def notification(sequence):
                event = dict(fixture()['clubs'][0]['events'][0], sequence=sequence)
                return {'club_id': CLUB, 'club_name': 'Babyfoot', 'event': event}
            with patch.object(app, 'bell') as bell, patch('ft_tui.features.clubs.views.workspace.monotonic', return_value=100) as now:
                host.enqueue([notification(1), notification(2)], 'account')
                bell.assert_called_once()
                host.enqueue([notification(1)], 'account')
                self.assertEqual(len(host.items), 2)
                bell.assert_called_once()
                now.return_value = 101
                host.enqueue([notification(3)], 'account')
                bell.assert_called_once()
                now.return_value = 106
                host.enqueue([notification(4)], 'account')
                self.assertEqual(bell.call_count, 2)
                app.club_notification_sound = False
                now.return_value = 112
                host.enqueue([notification(5)], 'account')
                self.assertEqual(bell.call_count, 2)
                self.assertEqual(len(host.items), 5)
                app.club_notification_sound = True
                expired = notification(6)
                expired['event']['expires_at'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
                host.enqueue([expired], 'account')
                self.assertEqual(bell.call_count, 2)

    async def test_muted_club_and_dnd_do_not_play_notification_sound(self):
        app = Harness()
        async with app.run_test(size=(110, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            item = {'club_id': CLUB, 'club_name': 'Babyfoot', 'event': fixture()['clubs'][0]['events'][0]}
            with patch.object(app, 'bell') as bell:
                app.provider.data['bells'][CLUB] = False
                app.provider.notifications = [item]
                await w.poll()
                app.provider.data['bells'][CLUB] = True
                app.provider.data['dnd'] = True
                app.provider.notifications = [item]
                await w.poll()
                bell.assert_not_called()
                self.assertFalse(app.query_one(ClubsInvitations).display)

    async def test_invitation_does_not_steal_focus_and_join_uses_its_club(self):
        app = Harness()
        async with app.run_test(size=(110, 40)) as pilot:
            await self.settle(app, pilot)
            app.query_one(TabbedContent).active = 'other'
            await pilot.pause()
            field = app.query_one('#other-input', Input)
            field.focus()
            item = {'club_id': CLUB, 'club_name': 'Babyfoot', 'event': fixture()['clubs'][0]['events'][0]}
            app.provider.notifications = [item]
            await app.query_one(ClubsWorkspace).poll()
            await pilot.pause()
            host = app.query_one(ClubsInvitations)
            self.assertTrue(host.display)
            self.assertIs(app.focused, field)
            self.assertGreaterEqual(host.region.x, 50)
            await pilot.click('#clubs-invitation-join')
            await self.settle(app, pilot)
            self.assertIn((CLUB, {'action': 'join', 'activity_id': ACTIVITY}), app.provider.calls)
            self.assertFalse(host.display)

    async def test_account_switch_clears_inbox_and_stale_result_is_ignored(self):
        import threading
        app = Harness()
        async with app.run_test(size=(100, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            gate = threading.Event()
            app.provider.gate = gate
            task = asyncio.create_task(w.reload())
            await asyncio.sleep(.05)
            app.account_id = '3'
            app.account_generation += 1
            app.account_connected = False
            w.tick()
            gate.set()
            await task
            self.assertEqual(w.snapshot, {})
            self.assertFalse(app.query_one(ClubsInvitations).display)

    async def test_narrow_layout_and_form_validation(self):
        app = Harness()
        async with app.run_test(size=(65, 30)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            self.assertTrue(w.has_class('narrow'))
            self.assertLessEqual(w.virtual_size.width, 65)
            self.assertLessEqual(w.query_one('#clubs-do-join', Button).region.bottom, 30)
            self.assertFalse(w.query_one('#clubs-list', DataTable).is_on_screen)
            self.assertTrue(w.query_one('#clubs-select', Select).is_on_screen)
            app.push_screen(ClubForm('Activity', [('minimum', 'Minimum', 0, 'number'), ('capacity', 'Maximum', 2, 'number')]))
            await pilot.pause()
            await pilot.click('#club-form-save')
            await pilot.pause()
            self.assertIsInstance(app.screen, ClubForm)
            await pilot.press('escape')
            self.assertEqual(len(app.screen_stack), 1)

    async def test_mutation_error_keeps_view_and_does_not_expose_error_body(self):
        app = Harness()
        async with app.run_test(size=(100, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            app.provider.failure = True
            await w.reload()
            self.assertEqual(w.current()['id'], CLUB)
            self.assertNotIn('private', str(app.query_one('#clubs-status').render()))

    async def test_main_view_hides_management_and_closed_activities(self):
        app = Harness()
        old = deepcopy(app.provider.data['clubs'][0]['activities'][0])
        old.update(id=str(uuid4()), status='finished')
        app.provider.data['clubs'][0]['activities'].append(old)
        async with app.run_test(size=(130, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            from textual.widgets import ContentSwitcher
            self.assertEqual(w.query_one('#clubs-pages', ContentSwitcher).current, 'clubs-page-activities')
            self.assertEqual(w.query_one('#clubs-activities', DataTable).row_count, 1)
            self.assertFalse(w.query_one('#clubs-do-start', Button).display)
            self.assertFalse(w.query_one('#clubs-do-cancel', Button).display)
            self.assertFalse(w.query_one('#clubs-member-add_member', Button).display)
            self.assertFalse(w.query_one('#clubs-members', DataTable).is_on_screen)
            self.assertFalse(w.query_one('#clubs-events', DataTable).is_on_screen)
            await pilot.click('#clubs-history')
            self.assertEqual(w.query_one('#clubs-activities', DataTable).row_count, 2)
            await pilot.click('#clubs-nav-inbox')
            self.assertEqual(w.query_one('#clubs-pages', ContentSwitcher).current, 'clubs-page-inbox')
            self.assertTrue(w.query_one('#clubs-events', DataTable).is_on_screen)

    async def test_activity_form_templates_and_advanced_options(self):
        from textual.widgets import Collapsible
        app = Harness()
        async with app.run_test(size=(100, 40)) as pilot:
            await self.settle(app, pilot)
            await pilot.click('#clubs-activity')
            await pilot.pause()
            form = app.screen
            self.assertIsInstance(form, ClubForm)
            self.assertTrue(form.query_one(Collapsible).collapsed)
            self.assertTrue(form.query_one('#club-field-minimum', Input).is_on_screen)
            self.assertFalse(form.query_one('#club-field-capacity', Input).is_on_screen)
            form.query_one('#club-form-template', Select).value = 'smash'
            await pilot.pause()
            self.assertEqual(form.query_one('#club-field-title', Input).value, 'Smash Bros')
            self.assertEqual(form.query_one('#club-field-capacity', Input).value, '8')
            form.query_one('#club-field-minimum', Input).value = '10'
            await pilot.pause()
            self.assertEqual(form.query_one('#club-field-capacity', Input).value, '10')
            await pilot.press('escape')

    async def test_campus_opens_inbox_and_refresh_keeps_club_selection(self):
        from textual.widgets import ContentSwitcher
        app = Harness()
        campus = deepcopy(app.provider.data['clubs'][0])
        campus.update(id='campus-31', name='Campus', system=True, members=[], activities=[])
        app.provider.data['clubs'].insert(0, campus)
        async with app.run_test(size=(110, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            self.assertEqual(w.selected_club, CLUB)
            listing = w.query_one('#clubs-list', DataTable)
            await pilot.click('#clubs-campus-news')
            await pilot.pause()
            self.assertEqual(w.selected_club, 'campus-31')
            self.assertEqual(w.query_one('#clubs-pages', ContentSwitcher).current, 'clubs-page-inbox')
            self.assertFalse(w.query_one('#clubs-nav-members', Button).display)
            await w.reload()
            await pilot.pause()
            self.assertEqual(w.selected_club, 'campus-31')
            self.assertEqual(listing.cursor_row, 0)
            self.assertTrue(w.has_class('campus-selected'))

    async def test_narrow_text_navigation_keeps_campus_and_clubs_accessible(self):
        app = Harness()
        app.icon_mode = 'text'
        app.language = 'fr'
        campus = deepcopy(app.provider.data['clubs'][0])
        campus.update(id='campus-31', system=True, members=[], activities=[])
        app.provider.data['clubs'].append(campus)
        async with app.run_test(size=(65, 30)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            for page in ('activities', 'inbox', 'members', 'manage'):
                button = w.query_one('#clubs-nav-' + page, Button)
                self.assertTrue(button.is_on_screen)
                self.assertLessEqual(button.region.right, w.content_region.right)
                await pilot.click(button)
                await pilot.pause()
                self.assertEqual(w.page, page)
            campus_button = w.query_one('#clubs-campus-news', Button)
            self.assertTrue(await pilot.click(campus_button), str(campus_button.region))
            await pilot.pause()
            self.assertEqual(w.selected_club, 'campus-31')
            selector = w.query_one('#clubs-select', Select)
            self.assertTrue(selector.is_on_screen)
            selector.value = CLUB
            await pilot.pause()
            self.assertEqual(w.selected_club, CLUB)
            self.assertEqual(w.page, 'activities')

    async def test_activity_card_prioritizes_action_and_keeps_people_in_details(self):
        from ft_tui.features.clubs.views.workspace import ClubActivityDetails
        app = Harness()
        async with app.run_test(size=(130, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            self.assertTrue(w.query_one('#club-activity-card').display)
            self.assertFalse(w.query_one('#clubs-activities', DataTable).display)
            self.assertEqual(str(w.query_one('#club-activity-title').render()), 'Babyfoot [red]')
            self.assertNotIn('alice', str(w.query_one('#club-activity-detail').render()))
            join = w.query_one('#clubs-do-join', Button)
            self.assertGreaterEqual(join.region.width, 20)
            self.assertEqual(join.region.height, 3)
            self.assertEqual(join.variant, 'primary')
            await pilot.click('#clubs-activity-details')
            await pilot.pause()
            self.assertIsInstance(app.screen, ClubActivityDetails)
            self.assertEqual(app.screen.activity['participants'], ['1'])
            self.assertIn('alice', ''.join(str(s.render()) for s in app.screen.query('Static')))
            await pilot.press('escape')
            self.assertEqual(len(app.screen_stack), 1)

    async def test_organizer_buttons_fit_small_terminal_in_french(self):
        app = Harness()
        app.language = 'fr'
        app.account_id = '1'
        app.provider.data['account_id'] = '1'
        app.provider.data['clubs'][0]['activities'][0].update(status='ready', participants=['1', '2'])
        async with app.run_test(size=(65, 30)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            for selector in ('#clubs-do-start', '#clubs-do-cancel', '#clubs-activity-details'):
                button = w.query_one(selector, Button)
                self.assertTrue(button.is_on_screen)
                self.assertEqual(button.region.height, 3)
                self.assertLessEqual(button.region.right, 65)
                self.assertLessEqual(button.region.bottom, 30)
            start, cancel = (w.query_one(q, Button) for q in ('#clubs-do-start', '#clubs-do-cancel'))
            self.assertLessEqual(start.region.right, cancel.region.x)
            self.assertEqual(w.query_one('#clubs-nav-activities', Button).region.height, 3)

    async def test_campus_has_separate_navigation_and_publisher_button_uses_capability(self):
        app = Harness()
        campus = deepcopy(app.provider.data['clubs'][0])
        campus.update(id='campus-31', name='Campus', system=True, members=[], activities=[], my_role='member', can_announce=True)
        app.provider.data['clubs'].append(campus)
        async with app.run_test(size=(110, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            listing = w.query_one('#clubs-list', DataTable)
            self.assertEqual([str(row.key.value) for row in listing.ordered_rows], [CLUB])
            campus_button = w.query_one('#clubs-campus-news', Button)
            self.assertTrue(campus_button.is_on_screen)
            await pilot.click('#clubs-campus-news')
            await pilot.pause()
            self.assertEqual(w.selected_club, 'campus-31')
            self.assertEqual(w.page, 'inbox')
            self.assertEqual(campus_button.variant, 'primary')
            self.assertTrue(w.query_one('#clubs-announce', Button).is_on_screen)
            self.assertIn('Campus', str(w.query_one('#club-summary').render()))
            await pilot.click('#clubs-announce')
            await pilot.pause()
            self.assertEqual(app.screen.__class__.__name__, 'AnnouncementComposer')
            await pilot.press('escape')
            await pilot.click('#clubs-list', offset=(2, 0))
            await pilot.pause()
            self.assertEqual(w.selected_club, CLUB)
            self.assertEqual(w.page, 'activities')
            self.assertEqual(campus_button.variant, 'default')

    async def test_announcement_preview_targets_campus_and_retains_draft_after_revocation(self):
        import httpx
        app = Harness()
        campus = deepcopy(app.provider.data['clubs'][0])
        campus.update(id='campus-31', name='Campus', system=True, members=[], activities=[], my_role='member', can_announce=True)
        app.provider.data['clubs'] = [campus]
        calls = []
        def denied(club, draft):
            calls.append((club, deepcopy(draft)))
            request = httpx.Request('POST', 'https://example.test/v1/clubs/campus-31/actions')
            raise httpx.HTTPStatusError('denied', request=request, response=httpx.Response(403, request=request, json={'error': 'clubs_forbidden'}))
        app.provider.club_action = denied
        async with app.run_test(size=(100, 45)) as pilot:
            await self.settle(app, pilot)
            await pilot.click('#clubs-announce')
            await pilot.pause()
            form = app.screen
            self.assertEqual(form.__class__.__name__, 'AnnouncementComposer')
            form.query_one('#announcement-title', Input).value = 'Crêpes'
            from textual.widgets import TextArea
            form.query_one('#announcement-message', TextArea).load_text('À la cafétéria')
            await pilot.click('#announcement-preview')
            await pilot.pause()
            self.assertEqual(calls, [])
            self.assertIn('Campus', str(form.query_one('#announcement-preview-destination').render()))
            await pilot.click('#announcement-publish')
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertIs(app.screen, form)
            self.assertEqual(form.query_one('#announcement-title', Input).value, 'Crêpes')
            self.assertEqual(form.query_one('#announcement-message', TextArea).text, 'À la cafétéria')
            self.assertEqual(calls[0][0], 'campus-31')
            self.assertNotIn('actor_id', calls[0][1])
            self.assertNotIn('campus_id', calls[0][1])
            self.assertIn('permission', str(form.query_one('#announcement-error').render()).lower())
            await pilot.press('escape')

    async def test_inbox_reader_displays_selected_message_without_details_dialog(self):
        app = Harness()
        campus = deepcopy(app.provider.data['clubs'][0])
        message = 'Bring your own plate. Full announcement details.'
        campus.update(id='campus-31', name='Campus', system=True, members=[], activities=[], my_role='member', can_announce=False)
        campus['events'][0].update(kind='announcement', activity_id=None, message=message, actor_login='alice')
        app.provider.data['clubs'] = [campus]
        async with app.run_test(size=(100, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            self.assertEqual(str(w.query_one('#club-event-body').render()), message)
            self.assertIn('alice', str(w.query_one('#club-event-detail').render()))
            self.assertEqual(len(app.screen_stack), 1)

    async def test_announcement_composer_keeps_actions_visible_on_small_terminal(self):
        app = Harness()
        campus = deepcopy(app.provider.data['clubs'][0])
        campus.update(id='campus-31', name='Campus', system=True, members=[], activities=[], my_role='member', can_announce=True)
        app.provider.data['clubs'] = [campus]
        async with app.run_test(size=(65, 30)) as pilot:
            await self.settle(app, pilot)
            await pilot.click('#clubs-announce')
            await pilot.pause()
            preview = app.screen.query_one('#announcement-preview', Button)
            self.assertLessEqual(preview.region.bottom, 30)
            self.assertGreater(preview.region.y, 0)
            self.assertTrue(preview.is_on_screen)

    async def test_inbox_filters_status_noise_and_keeps_selected_message_on_refresh(self):
        app = Harness()
        events = app.provider.data['clubs'][0]['events']
        events.append(dict(events[0], sequence=2, kind='cancelled', title='Cancelled match'))
        events.append(dict(events[0], sequence=3, kind='announcement', title='Crêpes [red]', message='Meet at noon'))
        async with app.run_test(size=(160, 45)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            w.show_page('inbox')
            await pilot.pause()
            table = w.query_one('#clubs-events', DataTable)
            self.assertEqual(table.row_count, 2)
            self.assertEqual(w.selected_event, '3')
            w.query_one('#clubs-inbox-filter', Select).value = 'all'
            await pilot.pause()
            self.assertEqual(table.row_count, 3)
            table.move_cursor(row=1)
            await pilot.pause()
            self.assertEqual(str(w.query_one('#club-event-title').render()), 'Cancelled match')
            await w.reload()
            await pilot.pause()
            self.assertEqual(w.selected_event, '2')
            w.query_one('#clubs-inbox-filter', Select).value = 'announcements'
            await pilot.pause()
            self.assertEqual(table.row_count, 1)
            self.assertEqual(str(w.query_one('#club-event-title').render()), 'Crêpes [red]')

    async def test_inbox_reader_stacks_on_small_terminal_and_subject_never_scrolls_sideways(self):
        for width in (160, 65):
            with self.subTest(width=width):
                app = Harness()
                app.provider.data['clubs'][0]['events'][0]['title'] = 'A very long announcement ' * 20
                async with app.run_test(size=(width, 45)) as pilot:
                    await self.settle(app, pilot)
                    w = app.query_one(ClubsWorkspace)
                    w.show_page('inbox')
                    await pilot.pause()
                    columns = w.query_one('#clubs-inbox-columns')
                    table = w.query_one('#clubs-events', DataTable)
                    reader = w.query_one('#club-event-reader')
                    self.assertLessEqual(table.virtual_size.width, table.size.width)
                    self.assertEqual(columns.has_class('stacked'), width == 65)
                    if width == 65:
                        self.assertGreaterEqual(reader.region.y, table.region.bottom)
                    else:
                        self.assertGreaterEqual(reader.region.x, table.region.right)
                    self.assertLessEqual(reader.region.right, width)

    async def test_cached_campus_without_name_uses_id_label_without_crashing(self):
        app = Harness()
        app.account_campuses = [{'id': 31, 'is_primary': True}]
        campus = deepcopy(app.provider.data['clubs'][0])
        campus.update(id='campus-31', name='Campus', system=True, members=[], activities=[], my_role='member', can_announce=False)
        app.provider.data['clubs'] = [campus]
        async with app.run_test(size=(100, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            self.assertIn('31', str(w.query_one('#club-summary').render()))

    async def test_add_member_reuses_fuzzy_dialog_and_centers_spaced_buttons(self):
        from ft_tui.features.friends.views.search import FriendSearchScreen
        from ft_tui.features.friends.views.suggestions import FriendSuggestions
        app = Harness()
        app.provider.data['clubs'][0]['my_role'] = 'creator'
        async with app.run_test(size=(100, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            w.show_page('members')
            await pilot.pause()
            await pilot.click('#clubs-member-add_member')
            await pilot.pause()
            modal = app.screen
            self.assertIsInstance(modal, FriendSearchScreen)
            modal.query_one('#friend-login-input', Input).value = 'charle'
            await pilot.pause()
            suggestions = modal.query_one(FriendSuggestions)
            self.assertEqual(suggestions.excluded_ids, {'1', '2'})
            suggestions._install({'items': [{'user_id': '3', 'login': 'charlie', 'display_name': 'Charlie Example'}], 'index': {}})
            await pilot.pause()
            cancel, add = modal.query_one('#friend-search-cancel', Button), modal.query_one('#friend-add', Button)
            self.assertGreater(add.region.x, cancel.region.right)
            actions = modal.query_one('#friend-search-actions')
            self.assertAlmostEqual((cancel.region.x + add.region.right) / 2, actions.region.center[0], delta=2)
            await pilot.click('#friend-add')
            await self.settle(app, pilot)
            self.assertIn((CLUB, {'action': 'add_member', 'login': 'charlie'}), app.provider.calls)
            self.assertEqual(len(app.screen_stack), 1)

    async def test_member_actions_share_row_and_wrap_without_overlap(self):
        app = Harness()
        app.provider.data['clubs'][0]['my_role'] = 'creator'
        app.provider.data['clubs'][0]['members'][1]['role'] = 'delegate'
        async with app.run_test(size=(165, 40)) as pilot:
            await self.settle(app, pilot)
            w = app.query_one(ClubsWorkspace)
            w.selected_member = '2'
            w.show_page('members')
            w.update_controls()
            await pilot.pause()
            buttons = [b for b in w.query('#clubs-member-actions Button') if b.display]
            self.assertEqual(len(buttons), 4)
            self.assertEqual(len({b.region.y for b in buttons}), 1)
            for left, right in zip(buttons, buttons[1:]):
                self.assertGreaterEqual(right.region.x - left.region.right, 2)
            await pilot.resize_terminal(65, 30)
            await pilot.pause()
            self.assertGreater(len({b.region.y for b in buttons}), 1)
            bounds = w.query_one('#clubs-member-actions').region
            for button in buttons:
                self.assertGreaterEqual(button.region.x, bounds.x)
                self.assertLessEqual(button.region.right, bounds.right)
                self.assertEqual(button.region.height, 3)
            for i, button in enumerate(buttons):
                for other in buttons[i+1:]:
                    self.assertFalse(button.region.overlaps(other.region))
