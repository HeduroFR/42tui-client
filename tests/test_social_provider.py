import threading
import unittest
from copy import deepcopy
from tempfile import TemporaryDirectory
from uuid import uuid4

import httpx
from ft_tui.api.social_types import overview, poke
from ft_tui.api.oauth_client import OAuthClient, DeviceCredentials
from tests.test_oauth_client import MemoryStore
from tests.test_ui_social import fixture


class SocialProviderTests(unittest.TestCase):
    def test_response_validation_rejects_wrong_consent_recipient_and_preference(self):
        data = fixture()
        self.assertEqual(overview(data)['pokes'][0]['message'], '[red]Lunch?[/red]')
        for mutate in (lambda d: d.update(dnd='false'),
                       lambda d: d['pokes'][0].update(approved=['2']),
                       lambda d: d['pokes'][0]['recipient'].update(account_id='9'),
                       lambda d: d['friends'].append(deepcopy(d['friends'][0]))):
            value = deepcopy(data); mutate(value)
            with self.assertRaises(ValueError):
                overview(value)

    def test_sse_parser_signs_get_and_releases_credential_lock_before_reading(self):
        seen = []
        client = None
        class Chunks(httpx.SyncByteStream):
            def __iter__(self):
                # A protected JSON operation can proceed while the stream is open.
                worker = threading.Thread(target=lambda: seen.append(client.request('GET', '/v1/check')), daemon=True)
                worker.start(); worker.join(1)
                if worker.is_alive():
                    raise AssertionError('The event stream held the credential lock while reading')
                yield b': keep alive\n\nevent: ready\ndata: resync\n\nevent: changed\ndata: social\n\n'
        def transport(request):
            seen.append(request)
            if request.url.path == '/v1/check':
                return httpx.Response(200, json={'ok': True})
            return httpx.Response(200, headers={'Content-Type': 'text/event-stream'}, stream=Chunks())
        with TemporaryDirectory() as directory:
            http = httpx.Client(transport=httpx.MockTransport(transport))
            client = OAuthClient('https://example.test', MemoryStore(), http_client=http, lock_directory=directory)
            client._save_credentials(DeviceCredentials('a'*43, 'r'*43, '2099-01-01T00:00:00Z', client._new_private_key_pem()))
            try:
                self.assertEqual(list(client.event_stream(threading.Event())), ['resync', 'social'])
                self.assertEqual(seen[0].headers['Accept'], 'text/event-stream')
                self.assertTrue(seen[0].headers['DPoP'])
                self.assertEqual(seen[-1], {'ok': True})
            finally:
                client.close()

    def test_rejected_stream_marks_current_device_session_expired(self):
        with TemporaryDirectory() as directory:
            http = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(401, json={'error': 'invalid_device_credentials'})))
            client = OAuthClient('https://example.test', MemoryStore(), http_client=http, lock_directory=directory)
            client._save_credentials(DeviceCredentials('a'*43, 'r'*43, '2099-01-01T00:00:00Z', client._new_private_key_pem()))
            try:
                with self.assertRaises(httpx.HTTPStatusError):
                    list(client.event_stream(threading.Event()))
                self.assertTrue(client.session_expired)
            finally:
                client.close()
