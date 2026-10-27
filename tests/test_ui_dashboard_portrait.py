"""Dashboard portraits stay responsive and never cross account boundaries."""
import asyncio
import base64
from io import BytesIO
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image
from textual.app import App

from ft_tui.features.dashboard.views.home import DashboardMixin
from ft_tui.features.profiles.views.profile_sections import ProfilePortrait


class PortraitDashboard(DashboardMixin, App):
    account_connected = True
    account_generation = 0
    account_id = '42'
    account_login = 'alice'
    account_profile = {}
    image_mode = 'halfcell'
    language = 'en'

    def compose(self):
        portrait = ProfilePortrait()
        portrait.id = 'dashboard-portrait'
        yield portrait


class DashboardPortraitTests(unittest.IsolatedAsyncioTestCase):
    async def test_photo_loads_from_existing_profile_transport_and_images_off_skips_requests(self):
        url = 'https://cdn.intra.42.fr/users/alice.jpg'
        buffer = BytesIO()
        Image.new('RGB', (8, 8), 'red').save(buffer, format='PNG')
        response = {'user_id': '42', 'image_url': url, 'status': 'ready',
                    'image_base64': base64.b64encode(buffer.getvalue()).decode()}
        app = PortraitDashboard()
        calls = []

        def profile(user_id):
            calls.append(user_id)
            return response

        app.provider = SimpleNamespace(get_student_portrait=profile)
        with patch('ft_tui.features.profiles.adapters.portraits.download_portrait', side_effect=AssertionError('Direct CDN access')):
            async with app.run_test() as pilot:
                app.image_mode = 'off'
                app._refresh_dashboard_portrait()
                await pilot.pause()
                self.assertEqual(calls, [])
                app.image_mode = 'halfcell'
                app._refresh_dashboard_portrait()
                await asyncio.wait_for(app.workers.wait_for_complete(), 3)
                portrait = app.query_one(ProfilePortrait)
                self.assertIsNotNone(portrait.image)
                self.assertIn('▀', portrait.render().plain)
                self.assertEqual(calls, ['42'])
                app._refresh_dashboard_portrait()
                self.assertEqual(calls, ['42'])
                app.account_connected = False
                app._refresh_dashboard_portrait()
                self.assertIsNone(portrait.image)

    async def test_inflight_photo_is_discarded_after_account_changes(self):
        started, release = threading.Event(), threading.Event()
        app = PortraitDashboard()

        url = 'https://cdn.intra.42.fr/users/alice.jpg'
        buffer = BytesIO()
        Image.new('RGB', (8, 8), 'red').save(buffer, format='PNG')
        response = {'user_id': '42', 'image_url': url, 'status': 'ready',
                    'image_base64': base64.b64encode(buffer.getvalue()).decode()}

        def download(requested_url):
            started.set()
            release.wait(3)
            return response

        app.provider = SimpleNamespace(get_student_portrait=download)
        try:
            await self._switch_during_download(app, started, release)
        finally:
            release.set()

    async def _switch_during_download(self, app, started, release):
        async with app.run_test() as pilot:
            app._refresh_dashboard_portrait()
            self.assertTrue(await asyncio.to_thread(started.wait, 2))
            app.account_connected = False
            app.account_login = None
            app.account_id = None
            app.account_generation += 1
            app._refresh_dashboard_portrait()
            release.set()
            await asyncio.wait_for(app.workers.wait_for_complete(), 3)
            await pilot.pause()
            portrait = app.query_one(ProfilePortrait)
            self.assertIsNone(portrait.image)
            self.assertEqual(portrait.initials, '42')
            self.assertIsNone(portrait.status)

    async def test_pending_portrait_retries_without_dashboard_refresh(self):
        app = PortraitDashboard()
        url = 'https://cdn.intra.42.fr/users/alice.jpg'
        buffer = BytesIO()
        Image.new('RGB', (8, 8), 'red').save(buffer, format='PNG')
        calls = []

        def fetch(user_id):
            calls.append(user_id)
            return {'user_id': user_id, 'image_url': url,
                    'status': 'pending' if len(calls) == 1 else 'ready',
                    'image_base64': None if len(calls) == 1 else base64.b64encode(buffer.getvalue()).decode()}

        app.provider = SimpleNamespace(get_student_portrait=fetch)
        scheduled = []
        async with app.run_test():
            # Control only the scheduler boundary, retaining the production retry callback.
            with patch.object(app, 'set_timer', side_effect=lambda delay, callback: scheduled.append((delay, callback))):
                app._refresh_dashboard_portrait()
                await app.workers.wait_for_complete()
                self.assertEqual(app.query_one(ProfilePortrait).status, 'pending')
                self.assertEqual(calls, ['42'])
                self.assertEqual(scheduled[0][0], 5)
                app._refresh_dashboard_portrait()
                await app.workers.wait_for_complete()
                self.assertEqual(calls, ['42'])  # The retry deadline still suppresses requests.
                with patch('time.monotonic', return_value=app._dashboard_portrait_retry + .01):
                    scheduled[0][1]()
                await app.workers.wait_for_complete()
                self.assertIsNotNone(app.query_one(ProfilePortrait).image)
                self.assertEqual(calls, ['42', '42'])

    async def test_wrong_identity_never_publishes_portrait(self):
        app = PortraitDashboard()
        app.provider = SimpleNamespace(get_student_portrait=lambda _: {
            'user_id': '99', 'status': 'ready', 'image_url': 'https://cdn.intra.42.fr/users/other.jpg',
            'image_base64': 'ignored',
        })
        async with app.run_test():
            app._refresh_dashboard_portrait()
            await app.workers.wait_for_complete()
            self.assertIsNone(app.query_one(ProfilePortrait).image)
