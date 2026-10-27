import asyncio
import threading
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from textual.app import App
from textual.containers import Vertical
from textual.widgets import Checkbox, DataTable
from ft_tui.db.database import make_session_factory
from ft_tui.features.friends.adapters.storage import memberships
from ft_tui.features.social.views.inbox import SocialInbox, PokeComposer
from ft_tui.features.social.views.events import PushEvents
from ft_tui.ui.components import Button, Input, Select


def fixture():
    now = datetime.now(timezone.utc)
    return {'account_id': '1', 'dnd': False, 'friends': [{'account_id': '2', 'login': 'bob'}],
            'incoming': [{'id': '1:3', 'members': [{'account_id': '1', 'login': 'alice'}, {'account_id': '3', 'login': 'charlie'}],
                          'requested_by': '3', 'status': 'pending', 'created_at': now.isoformat()}], 'outgoing': [],
            'pokes': [{'id': str(uuid4()), 'recipient': {'account_id': '1', 'login': 'alice'},
                       'senders': [{'account_id': '2', 'login': 'bob'}, {'account_id': '3', 'login': 'charlie'}],
                       'approved': ['2', '3'], 'status': 'sent', 'dismissed': False,
                       'message': '[red]Lunch?[/red]', 'created_at': now.isoformat(),
                       'expires_at': (now + timedelta(hours=1)).isoformat()}]}


class Provider:
    def __init__(self):
        self.data = fixture()
        self.calls = []
        self.gate = None
        self.fail = False
        self.reads = 0

    def get_social(self):
        value = deepcopy(self.data)
        self.reads += 1
        if self.gate:
            self.gate.wait(3)
        return value

    def social_action(self, draft):
        self.calls.append(deepcopy(draft))
        if self.fail:
            raise RuntimeError('lost response')
        if draft['action'] == 'accept':
            self.data['friends'].append({'account_id': '3', 'login': 'charlie'})
            self.data['incoming'] = []
        if draft['action'] == 'dismiss':
            self.data['pokes'] = [p for p in self.data['pokes'] if p['id'] != draft['id']]
        return {'status': 'sent'}

    def get_poke_neighbours(self):
        return []


class Parent(Vertical):
    def _stop(self):
        pass

    async def reload(self):
        pass


class Harness(App):
    account_generation = 1
    account_id = '1'
    account_connected = True
    account_login = 'alice'
    club_notification_sound = True
    language = 'en'

    def compose(self):
        with Parent():
            yield SocialInbox()
        yield PushEvents()


class SocialUiTests(unittest.IsolatedAsyncioTestCase):
    async def test_inbox_accepts_requests_displays_all_senders_and_deduplicates_sound(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory('sqlite:///' + directory + '/social.sqlite')
            app = Harness(); app.session_factory = factory; app.provider = Provider()
            try:
                async with app.run_test(size=(80, 35)) as pilot:
                    inbox = app.query_one(SocialInbox)
                    await pilot.pause()
                    await inbox.sync()
                    with factory() as session:
                        self.assertEqual([w.login for w in memberships(session, '1')], ['bob'])
                    await inbox.toggle()
                    await pilot.pause()
                    self.assertEqual(app.query_one('#social-table', DataTable).row_count, 2)
                    await inbox.toggle(kind='requests')
                    self.assertTrue(inbox.open)
                    self.assertEqual([kind for kind, _ in inbox.rows.values()], ['incoming'])
                    await inbox.toggle(kind='pokes')
                    self.assertTrue(inbox.open)
                    self.assertEqual([kind for kind, _ in inbox.rows.values()], ['poke'])
                    await inbox.toggle(kind='pokes')
                    self.assertFalse(inbox.open)
                    await inbox.toggle()

                    inbox.selected = inbox.snapshot['pokes'][0]['id']; inbox.update_controls()
                    detail = str(app.query_one('#social-detail').render())
                    self.assertIn('bob, charlie', detail)
                    self.assertIn('[red]Lunch?[/red]', detail)
                    with patch.object(app, 'bell') as bell:
                        inbox.seen.clear(); inbox.last_sound = float('-inf')
                        await inbox.sync(); await inbox.sync()
                        self.assertEqual(bell.call_count, 1)
                        inbox.seen.clear(); app.club_notification_sound = False
                        await inbox.sync(); self.assertEqual(bell.call_count, 1)
                    await app.screen.action_close()
                    await pilot.pause()
                    app.query_one('#social-table', DataTable).move_cursor(row=0)
                    await pilot.pause()
                    inbox.selected = 'incoming:3'; inbox.update_controls()
                    await pilot.pause()
                    await pilot.click('#social-accept'); await pilot.pause()
                    await inbox.sync()
                    with factory() as session:
                        self.assertEqual([w.login for w in memberships(session, '1')], ['bob', 'charlie'])
                    self.assertEqual(app.provider.calls[-1], {'action': 'accept', 'account_id': '3'})
            finally:
                factory.kw['bind'].dispose()

    async def test_account_switch_discards_late_inbox_and_no_network_poll_timer_runs(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory('sqlite:///' + directory + '/social.sqlite')
            app = Harness(); app.session_factory = factory; app.provider = Provider()
            try:
                async with app.run_test() as pilot:
                    inbox = app.query_one(SocialInbox); await pilot.pause()
                    app.provider.gate = threading.Event()
                    worker = inbox.run_worker(inbox.sync())
                    await pilot.pause(.05)
                    app.account_id = '4'; app.account_generation += 1
                    app.provider.gate.set()
                    await worker.wait(); await inbox.check_context(); await pilot.pause()
                    self.assertFalse(inbox.snapshot)
                    with factory() as session:
                        self.assertEqual(memberships(session, '4'), [])
                    reads = app.provider.reads
                    await pilot.pause(1.1)
                    self.assertEqual(reads, app.provider.reads)
            finally:
                factory.kw['bind'].dispose()

    async def test_server_change_refreshes_inbox_and_old_account_events_are_ignored(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory('sqlite:///' + directory + '/push.sqlite')
            app = Harness(); app.session_factory = factory; app.provider = Provider()
            try:
                async with app.run_test() as pilot:
                    await pilot.pause()
                    push = app.query_one(PushEvents)
                    context = push.scope()
                    reads = app.provider.reads
                    push.post_message(PushEvents.Changed(context, 'social'))
                    await pilot.pause(.1)
                    await push.workers.wait_for_complete()
                    self.assertEqual(app.provider.reads, reads + 1)
                    app.account_generation += 1
                    push.post_message(PushEvents.Changed(context, 'social'))
                    await pilot.pause(.1)
                    self.assertEqual(app.provider.reads, reads + 1)
            finally:
                factory.kw['bind'].dispose()

    async def test_recipient_is_excluded_and_changing_recipient_clears_co_sender_selection(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory('sqlite:///' + directory + '/recipients.sqlite')
            app = Harness(); app.session_factory = factory; app.provider = Provider()
            friends = [{'account_id': '2', 'login': 'bob'}, {'account_id': '3', 'login': 'charlie'}]
            app.provider.data['friends'] = friends
            app.provider.get_poke_neighbours = lambda: deepcopy(friends)
            try:
                async with app.run_test(size=(80, 35)) as pilot:
                    inbox = app.query_one(SocialInbox); await pilot.pause(); await inbox.sync()
                    inbox.compose_poke('2'); await pilot.pause()
                    composer = app.screen
                    await composer.workers.wait_for_complete()
                    bob = composer.query_one('#poke-author-0', Checkbox)
                    charlie = composer.query_one('#poke-author-1', Checkbox)
                    self.assertFalse(bob.display)
                    self.assertTrue(bob.disabled)
                    charlie.value = True
                    composer.query_one('#poke-recipient', Select).value = '3'
                    await pilot.pause()
                    self.assertFalse(charlie.display)
                    self.assertTrue(charlie.disabled)
                    self.assertFalse(charlie.value)
                    self.assertTrue(bob.display)
                    bob.value = True
                    composer.query_one('#poke-message', Input).value = 'Lunch?'
                    await pilot.click('#poke-send'); await pilot.pause()
                    self.assertEqual(app.provider.calls[-1]['recipient_id'], '3')
                    self.assertEqual(app.provider.calls[-1]['sender_ids'], ['2'])
            finally:
                factory.kw['bind'].dispose()

    async def test_uncertain_poke_retry_reuses_uuid_and_preserves_immutable_message(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory('sqlite:///' + directory + '/social.sqlite')
            app = Harness(); app.session_factory = factory; app.provider = Provider()
            try:
                async with app.run_test(size=(80, 35)) as pilot:
                    inbox = app.query_one(SocialInbox); await pilot.pause(); await inbox.sync()
                    inbox.compose_poke('2'); await pilot.pause()
                    composer = app.screen
                    self.assertIsInstance(composer, PokeComposer)
                    composer.query_one('#poke-message', Input).value = 'Lunch?'
                    app.provider.fail = True
                    await pilot.click('#poke-send'); await pilot.pause(.35)
                    app.provider.fail = False
                    await pilot.click('#poke-send'); await pilot.pause(.35)
                    self.assertEqual(app.provider.calls[-1]['id'], app.provider.calls[-2]['id'])
                    self.assertEqual(app.provider.calls[-1]['message'], 'Lunch?')
            finally:
                factory.kw['bind'].dispose()


class PokeNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory()
        self.factory = make_session_factory('sqlite:///' + self.directory.name + '/poke.sqlite')
        self.app = Harness()
        self.app.session_factory = self.factory
        self.app.provider = Provider()
        self.app.provider.data['incoming'] = []
        self.context = self.app.run_test(size=(80, 35))
        self.pilot = await self.context.__aenter__()
        await self.pilot.pause()
        self.inbox = self.app.query_one(SocialInbox)
        await self.inbox.sync()

    async def asyncTearDown(self):
        await self.context.__aexit__(None, None, None)
        self.factory.kw['bind'].dispose()
        self.directory.cleanup()

    async def test_minimal_popup_has_all_portraits_literal_message_and_persistent_dismiss(self):
        from ft_tui.features.social.views.pokes import PokeNotification, PokePortrait
        popup = self.app.screen
        self.assertIsInstance(popup, PokeNotification)
        self.assertEqual(len(popup.query(PokePortrait)), 2)
        self.assertEqual([p.tooltip for p in popup.query(PokePortrait)], ['bob', 'charlie'])
        self.assertEqual([str(w.render()) for w in popup.query('.poke-text')], ['[red]Lunch?[/red]'])
        self.assertEqual(len(popup.query('Static')), 1)
        from ft_tui.ui.button import AppButton
        close = popup.query_one('.poke-dismiss', AppButton)
        self.assertTrue(close.square)
        self.assertEqual(close.variant, 'danger')
        self.assertEqual(close.region.height, 3)
        self.assertEqual(close.region.width, 6)
        key = next(iter(popup.entries))
        await self.pilot.click('.poke-dismiss')
        await self.pilot.pause()
        self.assertEqual(self.app.provider.calls[-1], {'action': 'dismiss', 'id': key})
        self.assertIsNot(self.app.screen, popup)
        await self.inbox.sync()
        self.assertIsNot(self.app.screen, popup)
        self.assertEqual(self.inbox.snapshot['pokes'], [])

    async def test_failed_dismiss_stays_visible_and_retries_same_id(self):
        popup = self.app.screen
        key = next(iter(popup.entries))
        self.app.provider.fail = True
        await self.pilot.press('escape')
        await self.pilot.pause()
        self.assertIs(self.app.screen, popup)
        self.assertIn(key, popup.entries)
        self.assertFalse(popup.query_one('.poke-dismiss', Button).disabled)
        self.app.provider.fail = False
        await self.pilot.press('escape')
        await self.pilot.pause()
        self.assertEqual(self.app.provider.calls, [{'action': 'dismiss', 'id': key}] * 2)
        self.assertIsNot(self.app.screen, popup)

    async def test_dnd_hides_open_poke_without_acknowledging_and_restores_it(self):
        popup = self.app.screen
        keys = list(popup.entries)
        self.app.provider.data['dnd'] = True
        await self.inbox.sync()
        await self.pilot.pause()
        self.assertNotIn(popup, self.app.screen_stack)
        self.assertEqual(self.app.provider.calls, [])
        self.assertEqual([p['id'] for p in self.app.provider.data['pokes']], keys)
        self.app.provider.data['dnd'] = False
        await self.inbox.sync()
        self.assertEqual(list(self.app.screen.entries), keys)

    async def test_dnd_under_cover_never_pops_cover_or_acknowledges_poke(self):
        from ft_tui.ui.modal import AppModal
        popup = self.app.screen
        cover = AppModal()
        await self.app.push_screen(cover)
        self.app.provider.data['dnd'] = True
        await self.inbox.sync()
        self.assertIs(self.app.screen, cover)
        self.assertTrue(popup.closing)
        self.assertEqual(self.app.provider.calls, [])
        cover.dismiss()
        await self.pilot.pause()
        self.assertNotIn(popup, self.app.screen_stack)

    async def test_new_arrival_appends_in_same_window_and_sounds_without_request_throttle(self):
        popup = self.app.screen
        extra = deepcopy(self.app.provider.data['pokes'][0])
        extra['id'] = str(uuid4()); extra['message'] = 'Another poke'
        self.app.provider.data['pokes'].append(extra)
        with patch.object(self.app, 'bell') as bell, patch.object(self.app, 'notify') as notify:
            await self.inbox.sync()
            await self.inbox.sync()
            self.assertEqual(bell.call_count, 1)
            notify.assert_not_called()
        self.assertIs(self.app.screen, popup)
        self.assertEqual(len(popup.entries), 2)
        # Dismiss just one entry, leaving the other in the same window.
        first = next(iter(popup.entries))
        await popup.acknowledge([first])
        self.assertEqual(list(popup.entries), [extra['id']])

    async def test_arrival_during_escape_is_not_acknowledged(self):
        popup = self.app.screen
        first = next(iter(popup.entries))
        started, release = threading.Event(), threading.Event()
        extra = deepcopy(self.app.provider.data['pokes'][0])
        extra['id'] = str(uuid4()); extra['message'] = 'Arrived during dismiss'
        def dismiss(draft):
            self.app.provider.calls.append(draft)
            started.set(); release.wait()
            self.app.provider.data['pokes'] = [p for p in self.app.provider.data['pokes'] if p['id'] != draft['id']]
            return {'status': 'sent'}
        self.app.provider.social_action = dismiss
        worker = popup.run_worker(popup.action_close())
        try:
            self.assertTrue(await asyncio.to_thread(started.wait, 5))
            self.app.provider.data['pokes'].append(extra)
            self.inbox.snapshot['pokes'].append(deepcopy(extra))
            await self.inbox.show_pokes()
        finally:
            release.set()
            await worker.wait()
        self.assertEqual(list(popup.entries), [extra['id']])
        await self.inbox.sync()
        self.assertIs(self.app.screen, popup)
        self.assertEqual(list(popup.entries), [extra['id']])
        self.assertEqual(self.app.provider.calls, [{'action': 'dismiss', 'id': first}])

    async def test_account_change_under_another_modal_does_not_pop_that_modal(self):
        from ft_tui.ui.modal import AppModal
        popup = self.app.screen
        cover = AppModal()
        await self.app.push_screen(cover)
        self.app.account_id = '4'; self.app.account_generation += 1
        await self.inbox.check_context()
        self.assertIs(self.app.screen, cover)
        self.assertTrue(popup.closing)
        cover.dismiss()
        await self.pilot.pause()
        self.assertNotIn(popup, self.app.screen_stack)
        self.assertEqual(self.app.provider.calls, [])

    async def test_dnd_defers_new_popup_and_muting_only_suppresses_sound(self):
        await self.app.screen.action_close()
        await self.pilot.pause()
        extra = fixture()['pokes'][0]
        self.app.provider.data['pokes'] = [extra]
        self.app.provider.data['dnd'] = True
        with patch.object(self.app, 'bell') as bell:
            await self.inbox.sync()
            self.assertNotEqual(self.app.screen, self.inbox.poke_popup)
            bell.assert_not_called()
            self.app.provider.data['dnd'] = False
            self.app.club_notification_sound = False
            await self.inbox.sync()
            self.assertIs(self.app.screen, self.inbox.poke_popup)
            bell.assert_not_called()

    async def test_unavailable_profile_does_not_block_message_or_dismiss(self):
        popup = self.app.screen
        def unavailable(_):
            raise RuntimeError('Profile unavailable')
        self.app.provider.get_student_profile = unavailable
        entry = next(iter(popup.entries.values()))
        portrait = entry.query_one('PokePortrait')
        await entry.load_portrait(entry.poke['senders'][0], portrait)
        self.assertIsNone(portrait.image)
        self.assertIn('Lunch?', str(entry.query_one('.poke-text').render()))
        await popup.action_close()
        self.assertIsNot(self.app.screen, popup)

    async def test_sender_picture_uses_existing_profile_and_bounded_portrait_loader(self):
        import base64
        from io import BytesIO
        from PIL import Image
        from ft_tui.features.social.views.pokes import PokePortrait
        entry = next(iter(self.app.screen.entries.values()))
        portrait = entry.query_one(PokePortrait)
        sender = entry.poke['senders'][0]
        url = 'https://cdn.intra.42.fr/users/bob.jpg'
        image = BytesIO(); Image.new('RGB', (8, 8), '#123456').save(image, format='PNG')
        self.app.provider.get_student_profile = lambda user_id: {'user_id': user_id, 'image_url': url}
        with patch('ft_tui.features.social.views.pokes.download_portrait', return_value={
                'image_url': url, 'status': 'ready', 'image_base64': base64.b64encode(image.getvalue()).decode()}) as download:
            await entry.load_portrait(sender, portrait)
            download.assert_called_once_with(url)
        self.assertEqual(portrait.image.getpixel((0, 0)), (18, 52, 86))

    async def test_expired_poke_closes_without_acknowledging_it(self):
        popup = self.app.screen
        self.app.provider.data['pokes'][0]['expires_at'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        await self.inbox.sync()
        await self.pilot.pause()
        self.assertIsNot(self.app.screen, popup)
        self.assertEqual(self.app.provider.calls, [])
