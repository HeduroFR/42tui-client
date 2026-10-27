"""The companion never owns messages or prevents ordinary terminal interaction."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from textual.app import App
from textual.widgets import Header


class CompanionArtTests(unittest.TestCase):
    def test_frames_are_transparent_distinct_and_keep_tiny_dimensions(self):
        from ft_tui.ui.companion_art import frame
        poses = [frame(pose, 0) for pose in ('idle', 'crawl', 'sleep', 'hang')]
        self.assertEqual({image.size for image in poses}, {(48, 32)})
        self.assertTrue(all(image.mode == 'RGBA' for image in poses))
        self.assertTrue(all(image.getpixel((0, 0))[3] == 0 for image in poses))
        self.assertEqual(len({image.tobytes() for image in poses}), 4)
        self.assertNotEqual(frame('crawl', 0).tobytes(), frame('crawl', 1).tobytes())

    def test_hiding_or_disabling_images_disables_art_without_affecting_motion_setting(self):
        from ft_tui.ui.companion import companion_enabled
        app = SimpleNamespace(image_mode='halfcell', companion_visible=True, companion_motion=False)
        self.assertTrue(companion_enabled(app))
        app.image_mode = 'off'
        self.assertFalse(companion_enabled(app))
        app.image_mode = 'halfcell'; app.companion_visible = False
        self.assertFalse(companion_enabled(app))


class CompanionUiTests(unittest.IsolatedAsyncioTestCase):
    def harness(self):
        from ft_tui.ui.companion import WipHeader
        class Harness(App):
            image_mode = 'halfcell'
            companion_visible = True
            companion_motion = True
            account_connected = False

            def compose(self):
                yield WipHeader()
        return Harness()

    async def test_perch_reserves_top_right_space_without_covering_header(self):
        from ft_tui.ui.companion import WipPerch
        app = self.harness()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            perch = app.query_one(WipPerch)
            header = app.query_one(Header)
            self.assertEqual(perch.region.width, 8)
            self.assertEqual(perch.region.height, 3)
            self.assertGreaterEqual(perch.region.x, header.region.right)
            self.assertEqual(perch.region.right, 80)
            self.assertEqual(perch.pose, 'idle')
            self.assertFalse(perch.can_focus)
            self.assertIn('42', perch.render().plain)

    async def test_missing_art_fails_quietly_and_off_mode_collapses_perch(self):
        from ft_tui.ui.companion import WipPerch
        app = self.harness()
        with patch('ft_tui.ui.companion.frame', side_effect=OSError('missing sprite')):
            async with app.run_test() as pilot:
                await pilot.pause()
                perch = app.query_one(WipPerch)
                self.assertFalse(perch.display)
                self.assertTrue(app.query_one(Header).display)
        app = self.harness()
        async with app.run_test() as pilot:
            app.image_mode = 'off'
            app.query_one(WipPerch).refresh_preferences()
            await pilot.pause()
            self.assertFalse(app.query_one(WipPerch).display)
            self.assertEqual(app.query_one(Header).parent.region.height, 1)

    async def test_reduced_motion_keeps_a_static_sprite_and_unmount_stops_timer(self):
        from ft_tui.ui.companion import WipPerch
        app = self.harness(); app.companion_motion = False
        async with app.run_test() as pilot:
            perch = app.query_one(WipPerch)
            await pilot.pause()
            before = perch.image.tobytes()
            perch._tick()
            self.assertEqual(perch.image.tobytes(), before)
            await perch.remove()
            self.assertIsNone(perch._timer)

    async def test_native_modes_receive_frames_and_clear_images_when_disabled(self):
        from ft_tui.ui.companion import WipPerch
        from textual.widget import Widget
        class NativePixels(Widget):
            image = None

            def __init__(self, *, on_error=None, **kwargs):
                super().__init__(**kwargs)
        app = self.harness(); app.image_mode = 'sixel'
        with patch('ft_tui.ui.companion.PortraitSixelImage', NativePixels), patch('ft_tui.ui.companion.TGPImage', NativePixels):
            async with app.run_test() as pilot:
                await pilot.pause()
                perch = app.query_one(WipPerch)
                sixel = perch.query_one('.wip-sixel')
                tgp = perch.query_one('.wip-tgp')
                self.assertIsNotNone(sixel.image)
                self.assertIsNone(tgp.image)
                app.image_mode = 'tgp'; perch.refresh_preferences()
                self.assertIsNone(sixel.image)
                self.assertIsNotNone(tgp.image)
                perch._timer.pause()
                perch.visible = False
                await pilot.pause()
                self.assertIsNone(tgp.image)
                perch.visible = True
                await pilot.pause()
                self.assertIsNotNone(tgp.image)
                from ft_tui.ui.modal import AppModal
                cover = AppModal()
                await app.push_screen(cover)
                await pilot.pause()
                perch.clear_pixels()
                perch.refresh_preferences()
                self.assertIsNone(tgp.image)
                cover.dismiss()
                await pilot.pause()
                perch._tick()
                self.assertIsNotNone(tgp.image)
                app.image_mode = 'off'; perch.refresh_preferences()
                self.assertIsNone(sixel.image)
                self.assertIsNone(tgp.image)
                app.image_mode = 'tgp'; perch.refresh_preferences()
                self.assertIsNotNone(tgp.image)
                await perch.remove()
                self.assertIsNone(tgp.image)


class PokeCompanionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from tempfile import TemporaryDirectory
        from tests.test_ui_social import Harness, Provider
        from ft_tui.db.database import make_session_factory
        from ft_tui.ui.companion import WipHeader
        from ft_tui.features.social.views.inbox import SocialInbox
        class CompanionHarness(Harness):
            image_mode = 'halfcell'
            companion_visible = True
            companion_motion = True

            def compose(self):
                yield WipHeader()
                yield from super().compose()
        self.directory = TemporaryDirectory()
        self.factory = make_session_factory('sqlite:///' + self.directory.name + '/companion.sqlite')
        self.app = CompanionHarness(); self.app.session_factory = self.factory; self.app.provider = Provider()
        self.context = self.app.run_test(size=(90, 32))
        self.pilot = await self.context.__aenter__()
        self.inbox = self.app.query_one(SocialInbox)
        await self.inbox.sync()
        await self.pilot.pause()

    async def asyncTearDown(self):
        await self.context.__aexit__(None, None, None)
        self.factory.kw['bind'].dispose()
        self.directory.cleanup()

    async def hang(self):
        popup = self.app.screen
        popup._tick_delivery(popup._phase_start + 2)
        await self.pilot.pause()
        return popup

    async def test_travel_hangs_on_top_left_without_covering_literal_message_or_close(self):
        from ft_tui.ui.companion import WipPerch
        popup = await self.hang()
        self.assertGreater(popup._origin[0], self.app.size.width // 2)
        self.assertEqual(popup._delivery_phase, 'hang')
        self.assertEqual(popup.companion.pose, 'hang')
        box = popup.query_one('#incoming-pokes')
        sprite = popup.companion
        self.assertEqual(sprite.region.x, box.region.x + 1)
        self.assertEqual(sprite.region.y, box.region.y)
        for text in popup.query('.poke-text'):
            self.assertGreaterEqual(text.region.x, sprite.region.right)
            self.assertIn('[red]Lunch?[/red]', str(text.render()))
        self.assertFalse(sprite.region.overlaps(popup.query_one('.poke-dismiss').region))
        self.assertEqual(self.app.provider.calls, [])
        perch = self.app.screen_stack[0].query_one(WipPerch)
        perch._tick()
        self.assertFalse(perch.visible)

    async def test_failed_dismiss_does_not_return_and_success_returns_without_extra_ack(self):
        popup = await self.hang()
        key = next(iter(popup.entries))
        self.app.provider.fail = True
        await popup.acknowledge([key])
        self.assertEqual(popup._delivery_phase, 'hang')
        self.app.provider.fail = False
        start = popup._position
        await popup.acknowledge([key])
        self.assertEqual(popup._delivery_phase, 'return')
        self.assertEqual(popup._position, start)
        popup._tick_delivery(popup._phase_start + 0.1)
        self.assertEqual(popup._position, start)
        home = popup._home_anchor()
        popup._tick_delivery(popup._phase_start + 2)
        await self.pilot.pause()
        self.assertNotIn(popup, self.app.screen_stack)
        self.assertEqual(self.app.provider.calls, [{'action': 'dismiss', 'id': key}] * 2)
        self.assertIsNone(popup._animation_timer)
        self.assertEqual(popup._position, home)

    async def test_new_poke_reconciles_during_return_without_losing_or_acknowledging_it(self):
        from test_ui_social import fixture
        popup = await self.hang()
        key = next(iter(popup.entries))
        await popup.acknowledge([key])
        extra = fixture()['pokes'][0]
        self.app.provider.data['pokes'] = [extra]
        await self.inbox.sync()
        await self.pilot.pause()
        self.assertIs(self.app.screen, popup)
        self.assertIn(extra['id'], popup.entries)
        self.assertNotEqual(popup._delivery_phase, 'return')
        self.assertEqual(self.app.provider.calls, [{'action': 'dismiss', 'id': key}])
        await popup.acknowledge([extra['id']])
        self.assertEqual(popup._origin, popup._home_anchor())
        self.assertGreater(popup._origin[0], self.app.size.width // 2)

    async def test_motion_off_and_images_off_preserve_immediate_poke_access(self):
        popup = self.app.screen
        self.app.companion_motion = False
        popup.companion.refresh_preferences()
        popup._tick_delivery()
        self.assertEqual(popup._delivery_phase, 'hang')
        self.assertEqual(popup.companion._frame_key, ('hang', 0))
        self.app.image_mode = 'off'
        popup.companion.refresh_preferences()
        popup._tick_delivery()
        self.assertFalse(popup.companion.display)
        self.assertTrue(popup.query_one('.poke-dismiss').display)
        self.assertTrue(popup.entries)
        await popup.action_close()
        self.assertNotIn(popup, self.app.screen_stack)

    async def test_tiny_terminal_and_sprite_failure_leave_poke_accessible(self):
        popup = self.app.screen
        await self.pilot.resize_terminal(30, 16)
        await self.pilot.pause()
        popup._tick_delivery()
        self.assertFalse(popup.companion.display)
        self.assertTrue(popup.query_one('.poke-dismiss').display)
        await self.pilot.resize_terminal(90, 32)
        await self.pilot.pause()
        popup.companion.failed = True
        popup._tick_delivery()
        self.assertFalse(popup.companion.display)
        self.assertTrue(popup.entries)
        await popup.action_close()
        self.assertNotIn(popup, self.app.screen_stack)

    async def test_resize_and_expiry_keep_anchor_correct_and_never_ack(self):
        from datetime import datetime, timedelta, timezone
        popup = await self.hang()
        await self.pilot.resize_terminal(50, 24)
        await self.pilot.pause()
        popup._tick_delivery()
        await self.pilot.pause()
        self.assertEqual(popup.companion.region.x, popup.query_one('#incoming-pokes').region.x + 1)
        self.app.provider.data['pokes'][0]['expires_at'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        await self.inbox.sync()
        await self.pilot.pause()
        self.assertNotIn(popup, self.app.screen_stack)
        self.assertEqual(self.app.provider.calls, [])

    async def test_context_change_during_travel_discards_sprite_without_ack(self):
        popup = self.app.screen
        self.app.account_id = '9'; self.app.account_generation += 1
        popup._tick_delivery()
        await self.pilot.pause()
        self.assertNotIn(popup, self.app.screen_stack)
        self.assertEqual(self.app.provider.calls, [])

    async def test_dnd_cancels_delivery_and_sleeps_on_perch(self):
        from ft_tui.ui.companion import WipPerch
        popup = self.app.screen
        self.app.provider.data['dnd'] = True
        await self.inbox.sync()
        await self.pilot.pause()
        perch = self.app.screen.query_one(WipPerch)
        self.app.companion_motion = False
        perch._tick()
        self.assertEqual(perch.pose, 'sleep')
        self.assertNotIn(popup, self.app.screen_stack)
        self.assertEqual(self.app.provider.calls, [])
