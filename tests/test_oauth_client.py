import base64
import hashlib
import json
import subprocess
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier, Event
from time import sleep
from tempfile import TemporaryDirectory
from unittest.mock import patch
import httpx
from ft_tui.api.oauth_client import DeviceCredentials, OAuthClient, OAuthClientError, open_authorization_browser


class MemoryStore:
    def __init__(self): self.value = None
    def load(self): return self.value
    def save(self, value): self.value = value
    def delete(self): self.value = None


class FakeResponse:
    def __init__(self, payload, status_code=200): self._payload, self.status_code = payload, status_code
    def json(self): return self._payload
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError("HTTP failure")


class FakeHTTP:
    def __init__(self, responses): self.responses = list(responses); self.calls = []
    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)
    def close(self): pass


class OAuthClientTests(unittest.TestCase):
    def test_pairing_adds_validated_theme_to_browser_and_manual_url(self):
        from urllib.parse import parse_qs, urlsplit
        url = "https://api.example/oauth/42/start?pairing=" + "h" * 43
        http = FakeHTTP([FakeResponse({"pairing_handle": "h" * 43, "authorization_url": url, "expires_at": "later"})])
        opened = []
        client = self.make_client("https://api.example", MemoryStore(), http_client=http, browser_open=opened.append)
        theme = dict(background="#101820", surface="#182830", foreground="#EEF4FF", primary="#55CCFF", success="#77DDAA")
        start = client.create_pairing(theme=theme)
        self.assertEqual(opened, [start.authorization_url])
        self.assertEqual(parse_qs(urlsplit(start.authorization_url).query)["theme"], ["101820,182830,eef4ff,55ccff,77ddaa"])
        self.assertEqual(http.calls[0][2]["json"].keys(), {"installation_public_key"})

    def test_pairing_ignores_invalid_or_incomplete_palettes(self):
        url = "https://api.example/oauth/42/start?pairing=" + "h" * 43
        for theme in ({}, {"background": "</style>"}, dict.fromkeys(("background", "surface", "foreground", "primary", "success"), "#abc")):
            with self.subTest(theme=theme):
                http = FakeHTTP([FakeResponse({"pairing_handle": "h" * 43, "authorization_url": url, "expires_at": "later"})])
                client = self.make_client("https://api.example", MemoryStore(), http_client=http, browser_open=lambda _: False)
                self.assertEqual(client.create_pairing(theme=theme).authorization_url, url)

    @patch("ft_tui.api.oauth_client.webbrowser.Chrome")
    @patch("ft_tui.api.oauth_client.subprocess.run")
    @patch("ft_tui.api.oauth_client.shutil.which")
    @patch("ft_tui.api.oauth_client.sys.platform", "linux")
    @patch.dict("os.environ", {"DISPLAY": ":0", "BROWSER": ""})
    def test_default_desktop_browser_is_opened_before_browser_fallbacks(self, which, run, chrome):
        which.side_effect = lambda name: "/usr/bin/" + name if name in ('xdg-open', 'gio') else None
        run.return_value.returncode = 0
        url = "https://api.example/oauth/42/start?pairing=" + "h" * 43
        self.assertTrue(open_authorization_browser(url))
        self.assertEqual(run.call_args.args[0], ["/usr/bin/xdg-open", url])
        chrome.assert_not_called()

    @patch("ft_tui.api.oauth_client.subprocess.run")
    @patch("ft_tui.api.oauth_client.shutil.which")
    @patch("ft_tui.api.oauth_client.sys.platform", "linux")
    @patch.dict("os.environ", {"DISPLAY": ":0", "BROWSER": ""})
    def test_failed_or_timed_out_xdg_open_falls_back_to_gio(self, which, run):
        which.side_effect = lambda name: "/usr/bin/" + name if name in ('xdg-open', 'gio') else None
        for failure in (subprocess.CompletedProcess([], 3), subprocess.TimeoutExpired('xdg-open', 5)):
            with self.subTest(failure=failure):
                run.side_effect = [failure, subprocess.CompletedProcess([], 0)]
                self.assertTrue(open_authorization_browser("https://api.example/login"))
                self.assertEqual(run.call_args.args[0], ["/usr/bin/gio", "open", "https://api.example/login"])

    @patch("ft_tui.api.oauth_client.subprocess.run")
    @patch("ft_tui.api.oauth_client.shutil.which")
    @patch("ft_tui.api.oauth_client.sys.platform", "linux")
    @patch.dict("os.environ", {"DISPLAY": ":0", "BROWSER": ""})
    def test_configured_browser_desktop_id_is_launched_before_broken_xdg_open(self, which, run):
        which.side_effect = lambda name: "/usr/bin/" + name
        for desktop in ('app.zen_browser.zen.desktop', 'firefox.desktop', 'com.example.Browser.desktop'):
            with self.subTest(desktop=desktop):
                run.reset_mock()
                run.side_effect = [subprocess.CompletedProcess([], 0, desktop + '\n'),
                                   subprocess.CompletedProcess([], 0)]
                self.assertTrue(open_authorization_browser('https://api.example/login'))
                self.assertEqual(run.call_args_list[0].args[0], ['/usr/bin/xdg-settings', 'get', 'default-web-browser'])
                self.assertEqual(run.call_args_list[1].args[0], ['/usr/bin/gtk-launch', desktop, 'https://api.example/login'])
                self.assertEqual(run.call_count, 2)

    @patch("ft_tui.api.oauth_client.subprocess.run")
    @patch("ft_tui.api.oauth_client.shutil.which")
    @patch("ft_tui.api.oauth_client.sys.platform", "linux")
    def test_flatpak_default_browser_desktop_file_can_be_launched_with_gio(self, which, run):
        with TemporaryDirectory() as directory, patch.dict('os.environ', {
            'HOME': directory, 'XDG_DATA_HOME': directory + '/data',
            'XDG_DATA_DIRS': directory + '/system', 'DISPLAY': ':0', 'BROWSER': '',
        }):
            desktop = Path(directory)/'.local/share/flatpak/exports/share/applications/app.zen_browser.zen.desktop'
            desktop.parent.mkdir(parents=True)
            desktop.write_text('[Desktop Entry]\nType=Application\nExec=flatpak run app.zen_browser.zen %u\n')
            which.side_effect = lambda name: '/usr/bin/' + name if name in ('xdg-settings', 'gio', 'xdg-open') else None
            run.side_effect = [subprocess.CompletedProcess([], 0, desktop.name + '\n'),
                               subprocess.CompletedProcess([], 0)]
            self.assertTrue(open_authorization_browser('https://api.example/login'))
            self.assertEqual(run.call_args.args[0], ['/usr/bin/gio', 'launch', str(desktop), 'https://api.example/login'])

    def test_browser_launch_failure_keeps_manual_pairing_available(self):
        import webbrowser
        for error in (OSError("launcher missing"), webbrowser.Error("no browser")):
            with self.subTest(error=type(error).__name__):
                url = "https://api.example/oauth/42/start?pairing=" + "h" * 43
                http = FakeHTTP([FakeResponse({"pairing_handle": "h" * 43,
                                              "authorization_url": url, "expires_at": "later"})])
                def unavailable(_):
                    raise error
                client = self.make_client("https://api.example", MemoryStore(), http_client=http,
                                          browser_open=unavailable)
                self.assertEqual(client.create_pairing().authorization_url, url)

    @patch("ft_tui.api.oauth_client.webbrowser.open")
    @patch("ft_tui.api.oauth_client.webbrowser.Chrome")
    @patch("ft_tui.api.oauth_client.shutil.which")
    @patch("ft_tui.api.oauth_client.sys.platform", "linux")
    @patch.dict("os.environ", {"DISPLAY": ":0", "BROWSER": ""})
    def test_installed_chrome_is_used_before_broken_default_firefox(self, which, get, default_open):
        which.side_effect = lambda name: "/usr/bin/google-chrome" if name == "google-chrome" else None
        get.return_value.open.return_value = True
        self.assertTrue(open_authorization_browser("https://api.example/login"))
        get.assert_called_once_with("/usr/bin/google-chrome")
        get.return_value.open.assert_called_once_with("https://api.example/login", new=2)
        default_open.assert_not_called()

    @patch("ft_tui.api.oauth_client.webbrowser.open", return_value=True)
    @patch("ft_tui.api.oauth_client.shutil.which")
    @patch("ft_tui.api.oauth_client.sys.platform", "linux")
    @patch.dict("os.environ", {"BROWSER": "my-browser"})
    def test_explicit_browser_override_is_preserved(self, which, default_open):
        self.assertTrue(open_authorization_browser("https://api.example/login"))
        which.assert_not_called()
        default_open.assert_called_once_with("https://api.example/login", new=2)

    def setUp(self):
        self._lock_temp = TemporaryDirectory()
        self.lock_directory = self._lock_temp.name

    def tearDown(self):
        self._lock_temp.cleanup()

    def make_client(self, *args, **kwargs):
        kwargs.setdefault("lock_directory", self.lock_directory)
        return OAuthClient(*args, **kwargs)

    def set_credentials(self, client, credentials):
        client._credentials = credentials
        client.store.save(
            {
                "access_token": credentials.access_token,
                "refresh_token": credentials.refresh_token,
                "expires_at": credentials.expires_at,
                "private_key_pem": credentials.private_key_pem,
            }
        )

    def test_authentication_failure_notifies_once_but_service_errors_do_not(self):
        for status, code, expires_at, expected in (
            (401, "invalid_device_credentials", "2000-01-01T00:00:00Z", 1),
            (401, "invalid_device_credentials", "2030-01-01T00:00:00Z", 1),
            (401, "reauthorization_required", "2030-01-01T00:00:00Z", 1),
            (503, "session_service_unavailable", "2000-01-01T00:00:00Z", 0),
            (403, "forbidden", "2030-01-01T00:00:00Z", 0),
        ):
            with self.subTest(status=status, code=code):
                response = httpx.Response(status, json={"error": code}, request=httpx.Request("GET", "https://api.example/v1/me"))
                client = self.make_client("https://api.example", MemoryStore(), http_client=FakeHTTP([response] * 4))
                self.set_credentials(client, DeviceCredentials("access", "refresh", expires_at, client._new_private_key_pem()))
                notifications = []
                client.on_session_expired = lambda: notifications.append(True)
                for _ in range(2):
                    with self.assertRaises(httpx.HTTPStatusError):
                        client.request("GET", "/v1/me")
                self.assertEqual(len(notifications), expected)

    def test_replayed_proof_recovery_does_not_prompt_for_reconnection(self):
        url = "https://api.example/v1/me"
        responses = [httpx.Response(status, json=body, request=httpx.Request("GET", url)) for status, body in (
            (401, {"error": "invalid_device_credentials"}), (200, {"login": "student42"}))]
        client = self.make_client("https://api.example", MemoryStore(), http_client=FakeHTTP(responses))
        self.set_credentials(client, DeviceCredentials("access", "refresh", "2030-01-01T00:00:00Z", client._new_private_key_pem()))
        notifications = []
        client.on_session_expired = lambda: notifications.append(True)
        self.assertEqual(client.request("GET", "/v1/me"), {"login": "student42"})
        self.assertEqual(notifications, [])

    def test_inflight_old_request_cannot_expire_newly_paired_credentials(self):
        client = self.make_client("https://api.example", MemoryStore())
        old = DeviceCredentials("old", "refresh", "2030-01-01T00:00:00Z", client._new_private_key_pem())
        new = DeviceCredentials("new", "new-refresh", "2030-01-01T00:00:00Z", old.private_key_pem)
        self.set_credentials(client, old)
        notifications = []
        client.on_session_expired = lambda: notifications.append(True)
        def reject_old_request(request):
            client._save_credentials(new)
            return httpx.Response(401, json={"error": "invalid_device_credentials"})
        client.close()
        client.http = httpx.Client(transport=httpx.MockTransport(reject_old_request))
        try:
            with self.assertRaises(httpx.HTTPStatusError):
                client.request("POST", "/v1/projects/graph/advance")
            self.assertEqual(notifications, [])
            self.assertEqual(client.credentials.access_token, "new")
        finally:
            client.close()

    def test_unreachable_service_does_not_expire_session(self):
        def unavailable(request):
            raise httpx.ConnectError("offline", request=request)
        client = self.make_client("https://api.example", MemoryStore(), http_client=httpx.Client(transport=httpx.MockTransport(unavailable)))
        self.set_credentials(client, DeviceCredentials("access", "refresh", "2000-01-01T00:00:00Z", client._new_private_key_pem()))
        notifications = []
        client.on_session_expired = lambda: notifications.append(True)
        try:
            with self.assertRaises(httpx.ConnectError):
                client.request("GET", "/v1/me")
            self.assertFalse(client.session_expired)
            self.assertEqual(notifications, [])
        finally:
            client.close()

    def test_loopback_http_authorization_url_requires_matching_backend_origin(self):
        client = self.make_client(
            "http://127.0.0.1:8765",
            MemoryStore(),
            http_client=FakeHTTP([]),
            browser_open=lambda _: None,
        )
        handle = "h" * 43
        client._validate_authorization_url(
            f"http://127.0.0.1:8765/oauth/42/start?pairing={handle}", handle
        )
        with self.assertRaises(OAuthClientError):
            client._validate_authorization_url(
                f"http://127.0.0.1:8765/oauth/42/start?pairing={'x' * 43}", handle
            )
        client._validate_authorization_url(
            f"http://127.0.0.1:8765/oauth/42/start?pairing={handle}", handle
        )
        with self.assertRaises(OAuthClientError):
            client._validate_authorization_url(
                f"http://localhost:8765/oauth/42/start?pairing={handle}", handle
            )
        with self.assertRaises(OAuthClientError):
            client._validate_authorization_url(
                f"http://127.0.0.1:8766/oauth/42/start?pairing={handle}", handle
            )
        with self.assertRaises(OAuthClientError):
            client._validate_authorization_url(
                f"http://127.0.0.1:8765/not-oauth?pairing={handle}", handle
            )
        with self.assertRaises(OAuthClientError):
            client._validate_authorization_url(
                f"http://127.0.0.1:8765/oauth/42/start?pairing={handle}&pairing={handle}", handle
            )
        with self.assertRaises(OAuthClientError):
            client._validate_authorization_url("http://127.0.0.1:8765/oauth/42/start?pairing=", handle)

    def test_authorization_url_must_match_api_origin_and_pairing_route(self):
        client = self.make_client("https://api.example:8443", MemoryStore(), http_client=FakeHTTP([]))
        handle = "h" * 43
        client._validate_authorization_url(
            f"https://api.example:8443/oauth/42/start?pairing={handle}", handle
        )
        for url in (
            f"https://other.example:8443/oauth/42/start?pairing={handle}",
            f"https://api.example/oauth/42/start?pairing={handle}",
            f"https://api.example:8443/other?pairing={handle}",
            f"https://api.example:8443/oauth/42/start?pairing={handle}&pairing={handle}",
            "https://api.example:8443/oauth/42/start?pairing=",
            "http://localhost/oauth/42/start?pairing=" + handle,
        ):
            with self.subTest(url=url), self.assertRaises(OAuthClientError):
                client._validate_authorization_url(url, handle)

    def test_pairing_posts_installation_public_key_opens_browser_and_polls(self):
        http = FakeHTTP([
            FakeResponse(
                {
                    "pairing_handle": "h" * 43,
                    "authorization_url": f"https://api.example/oauth/42/start?pairing={'h' * 43}",
                    "expires_at": "2030-01-01T00:00:00Z",
                },
                201,
            ),
            FakeResponse(
                {
                    "status": "approved",
                    "credentials": {
                        "access_token": "a" * 43,
                        "refresh_token": "r" * 43,
                        "expires_at": "2030-01-01T00:15:00Z",
                    },
                }
            ),
        ])
        store = MemoryStore()
        opened = []
        client = self.make_client("https://api.example", store, http_client=http, browser_open=opened.append)
        start = client.create_pairing()
        self.assertEqual(start.handle, "h" * 43)
        self.assertEqual(opened, [f"https://api.example/oauth/42/start?pairing={'h' * 43}"])
        body = http.calls[0][2]["json"]
        self.assertEqual(set(body["installation_public_key"]), {"kty", "crv", "x", "y"})
        result = client.poll_pairing(start.handle)
        self.assertEqual(result.credentials.access_token, "a" * 43)
        self.assertTrue(store.value["private_key_pem"])
        self.assertEqual(http.calls[1][1], "https://api.example/v1/pairings/" + "h" * 43)

    def test_protected_request_proof_binds_uri_method_and_access_token(self):
        http = FakeHTTP(
            [
                FakeResponse(
                    {"projects": [], "pagination": {"page": 1, "per_page": 100, "has_more": False}, "meta": {}}
                )
            ]
        )
        store = MemoryStore()
        client = self.make_client("https://api.example", store, http_client=http, browser_open=lambda _: None)
        self.set_credentials(
            client,
            DeviceCredentials("access", "refresh", "2030-01-01T00:00:00Z", client._new_private_key_pem()),
        )
        client.request("GET", "/v1/projects", params={"page": 2, "per_page": 100})
        proof = http.calls[0][2]["headers"]["DPoP"]
        header, claims, signature = proof.split(".")
        decode = lambda part: json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        self.assertEqual(decode(header)["typ"], "dpop+jwt")
        self.assertEqual(decode(header)["alg"], "ES256")
        payload = decode(claims)
        self.assertEqual(payload["htm"], "GET")
        self.assertEqual(payload["htu"], "https://api.example/v1/projects?page=2&per_page=100")
        expected_ath = base64.urlsafe_b64encode(hashlib.sha256(b"access").digest()).decode().rstrip("=")
        self.assertEqual(payload["ath"], expected_ath)
        self.assertTrue(payload["jti"])
        self.assertEqual(len(base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))), 64)

    def test_graph_advance_post_proof_and_no_blind_retry(self):
        url = "https://api.example/v1/projects/graph/advance?cursus_id=21"
        for response_status in (200, 401):
            http = FakeHTTP([httpx.Response(response_status,
                json={"error": "invalid_device_credentials"} if response_status == 401 else {"status": "scanning"},
                request=httpx.Request("POST", url))])
            client = self.make_client("https://api.example", MemoryStore(), http_client=http, browser_open=lambda _: None)
            self.set_credentials(client, DeviceCredentials("access", "refresh", "2030-01-01T00:00:00Z", client._new_private_key_pem()))
            if response_status == 401:
                with self.assertRaises(httpx.HTTPStatusError):
                    client.request("POST", "/v1/projects/graph/advance", params={"cursus_id": 21})
            else:
                self.assertEqual(client.request("POST", "/v1/projects/graph/advance", params={"cursus_id": 21}), {"status": "scanning"})
            self.assertEqual(len(http.calls), 1)
            proof = http.calls[0][2]["headers"]["DPoP"]
            claims = proof.split(".")[1]
            payload = json.loads(base64.urlsafe_b64decode(claims + "=" * (-len(claims) % 4)))
            self.assertEqual(payload["htm"], "POST")
            self.assertEqual(payload["htu"], url)
            expected_ath = base64.urlsafe_b64encode(hashlib.sha256(b"access").digest()).decode().rstrip("=")
            self.assertEqual(payload["ath"], expected_ath)

    def test_get_retries_once_with_a_fresh_proof_after_device_auth_replay(self):
        url = "https://api.example/v1/projects"
        http = FakeHTTP([
            httpx.Response(401, json={"error": "invalid_device_credentials"}, request=httpx.Request("GET", url)),
            httpx.Response(200, json={"projects": [], "pagination": {"page": 1, "per_page": 100, "has_more": False}}, request=httpx.Request("GET", url)),
        ])
        ids = iter(("proof-one", "proof-two"))
        client = self.make_client(
            "https://api.example", MemoryStore(), http_client=http,
            browser_open=lambda _: None, id_factory=lambda: next(ids),
        )
        self.set_credentials(
            client,
            DeviceCredentials("access", "refresh", "2030-01-01T00:15:00Z", client._new_private_key_pem()),
        )

        with self.assertLogs("ft_tui.api.oauth_client", level="WARNING") as captured:
            try:
                result = client.request("GET", "/v1/projects")
            except httpx.HTTPStatusError as error:
                self.fail(f"safe GET did not recover from a replayed proof: {error}")

        self.assertEqual(result["projects"], [])
        self.assertEqual(len(http.calls), 2)
        proofs = [call[2]["headers"]["DPoP"] for call in http.calls]
        decode = lambda part: json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        jtids = [decode(proof.split(".")[1])["jti"] for proof in proofs]
        self.assertEqual(jtids, ["proof-one", "proof-two"])
        self.assertIn("retrying with fresh DPoP proof", captured.output[0])
        self.assertIn(hashlib.sha256(b"proof-one").hexdigest()[:12], captured.output[0])
        self.assertIn(hashlib.sha256(b"proof-two").hexdigest()[:12], captured.output[0])

    def test_cursus_and_project_page_methods_use_authenticated_request(self):
        http = FakeHTTP([
            FakeResponse({"cursuses": [], "meta": {}}),
            FakeResponse({"projects": [], "pagination": {"page": 3, "per_page": 100, "has_more": False}}),
        ])
        client = self.make_client("https://api.example", MemoryStore(), http_client=http)
        self.set_credentials(
            client,
            DeviceCredentials("access", "refresh", "2030-01-01T00:00:00Z", client._new_private_key_pem()),
        )
        client._proof = lambda method, uri, token: "test-proof"
        client.list_cursuses()
        client.request("GET", "/v1/catalog/projects", params={"cursus_id":21,"campus_id":31,"track":"new","limit":100})
        self.assertEqual(http.calls[0][1], "https://api.example/v1/cursuses")
        self.assertEqual(
            http.calls[1][1],
            "https://api.example/v1/catalog/projects?cursus_id=21&campus_id=31&track=new&limit=100",
        )
        self.assertEqual(http.calls[1][2]["headers"]["Authorization"], "DPoP access")
        self.assertGreater(http.calls[1][2]["timeout"], 0.0)

    def test_request_refreshes_near_expiry_without_recursing(self):
        now = 1_800_000_000
        near_expiry = datetime.fromtimestamp(now + 30, timezone.utc).isoformat().replace("+00:00", "Z")
        renewed_expiry = datetime.fromtimestamp(now + 900, timezone.utc).isoformat().replace("+00:00", "Z")
        http = FakeHTTP(
            [
                FakeResponse({"access_token": "b" * 43, "refresh_token": "s" * 43, "expires_at": renewed_expiry}),
                FakeResponse({"login": "student", "meta": {}}),
            ]
        )
        store = MemoryStore()
        client = self.make_client(
            "https://api.example",
            store,
            http_client=http,
            browser_open=lambda _: None,
            clock=lambda: now,
        )
        self.set_credentials(client, DeviceCredentials("a" * 43, "r" * 43, near_expiry, "test-private-key"))
        client._proof = lambda method, uri, token: "test-proof"

        client.request("GET", "/v1/me")

        self.assertEqual(http.calls[0][1], "https://api.example/v1/sessions/refresh")
        self.assertEqual(http.calls[0][2]["json"], {"refresh_token": "r" * 43})
        self.assertEqual(http.calls[1][1], "https://api.example/v1/me")
        self.assertEqual(http.calls[1][2]["headers"]["Authorization"], f"DPoP {'b' * 43}")

    def test_disconnect_refreshes_near_expiry_before_delete(self):
        now = 1_800_000_000
        near_expiry = datetime.fromtimestamp(now + 30, timezone.utc).isoformat().replace("+00:00", "Z")
        renewed_expiry = datetime.fromtimestamp(now + 900, timezone.utc).isoformat().replace("+00:00", "Z")
        http = FakeHTTP(
            [
                FakeResponse({"access_token": "b" * 43, "refresh_token": "s" * 43, "expires_at": renewed_expiry}),
                FakeResponse({}, 204),
            ]
        )
        client = self.make_client(
            "https://api.example",
            MemoryStore(),
            http_client=http,
            browser_open=lambda _: None,
            clock=lambda: now,
        )
        self.set_credentials(client, DeviceCredentials("a" * 43, "r" * 43, near_expiry, "test-private-key"))
        client._proof = lambda method, uri, token: "test-proof"

        client.disconnect()

        self.assertEqual(http.calls[0][1], "https://api.example/v1/sessions/refresh")
        self.assertEqual(http.calls[1][1], "https://api.example/v1/sessions/current")
        self.assertEqual(http.calls[1][2]["headers"]["Authorization"], f"DPoP {'b' * 43}")

    def test_concurrent_near_expiry_requests_rotate_refresh_token_once(self):
        now = 1_800_000_000
        near_expiry = datetime.fromtimestamp(now + 30, timezone.utc).isoformat().replace("+00:00", "Z")
        renewed_expiry = datetime.fromtimestamp(now + 900, timezone.utc).isoformat().replace("+00:00", "Z")
        http = FakeHTTP(
            [
                FakeResponse({"access_token": "b" * 43, "refresh_token": "s" * 43, "expires_at": renewed_expiry}),
                FakeResponse({"login": "student", "meta": {}}),
                FakeResponse({"login": "student", "meta": {}}),
            ]
        )
        client = self.make_client(
            "https://api.example",
            MemoryStore(),
            http_client=http,
            browser_open=lambda _: None,
            clock=lambda: now,
        )
        self.set_credentials(client, DeviceCredentials("a" * 43, "r" * 43, near_expiry, "test-private-key"))
        client._proof = lambda method, uri, token: "test-proof"
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(client.request, "GET", "/v1/me") for _ in range(2)]
            for future in futures:
                future.result(timeout=3)

        refresh_calls = [call for call in http.calls if call[1].endswith("/v1/sessions/refresh")]
        self.assertEqual(len(refresh_calls), 1)
        self.assertEqual(refresh_calls[0][2]["json"], {"refresh_token": "r" * 43})

    def test_separate_clients_reload_keychain_before_cross_instance_refresh(self):
        now = 1_800_000_000
        near_expiry = datetime.fromtimestamp(now + 30, timezone.utc).isoformat().replace("+00:00", "Z")
        renewed_expiry = datetime.fromtimestamp(now + 900, timezone.utc).isoformat().replace("+00:00", "Z")
        shared_store = MemoryStore()
        old = DeviceCredentials("a" * 43, "r" * 43, near_expiry, "test-private-key")
        shared_store.save({
            "access_token": old.access_token,
            "refresh_token": old.refresh_token,
            "expires_at": old.expires_at,
            "private_key_pem": old.private_key_pem,
        })
        http = FakeHTTP(
            [
                FakeResponse({"access_token": "b" * 43, "refresh_token": "s" * 43, "expires_at": renewed_expiry}),
                FakeResponse({"login": "student", "meta": {}}),
                FakeResponse({"login": "student", "meta": {}}),
            ]
        )
        lock_dir = self.lock_directory
        clients = [
            self.make_client(
                "https://api.example",
                shared_store,
                http_client=http,
                browser_open=lambda _: None,
                clock=lambda: now,
                lock_directory=lock_dir,
            )
            for _ in range(2)
        ]
        for client in clients:
            self.set_credentials(client, old)
            client._proof = lambda method, uri, token: "test-proof"
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(client.request, "GET", "/v1/me") for client in clients]
            for future in futures:
                future.result(timeout=3)

        refresh_calls = [call for call in http.calls if call[1].endswith("/v1/sessions/refresh")]
        self.assertEqual(len(refresh_calls), 1)
        self.assertEqual(refresh_calls[0][2]["json"], {"refresh_token": "r" * 43})
        protected_authorizations = [
            call[2]["headers"]["Authorization"]
            for call in http.calls
            if call[1].endswith("/v1/me")
        ]
        self.assertEqual(protected_authorizations, [f"DPoP {'b' * 43}"] * 2)
        lock_files = list(Path(lock_dir).glob("*.lock"))
        self.assertEqual(len(lock_files), 1)
        lock_content = lock_files[0].read_bytes()
        for credential in (b"r" * 43, b"s" * 43, b"a" * 43, b"b" * 43):
            self.assertNotIn(credential, lock_content)

    def test_request_reloads_credentials_after_another_client_refreshes(self):
        now = 1_800_000_000
        expiry = datetime.fromtimestamp(now + 600, timezone.utc).isoformat().replace("+00:00", "Z")
        renewed_expiry = datetime.fromtimestamp(now + 900, timezone.utc).isoformat().replace("+00:00", "Z")
        store = MemoryStore()
        old = DeviceCredentials("a" * 43, "r" * 43, expiry, "test-private-key")
        http = FakeHTTP([
            FakeResponse({"access_token": "b" * 43, "refresh_token": "s" * 43, "expires_at": renewed_expiry}),
            FakeResponse({"login": "student", "meta": {}}),
        ])
        client_a = self.make_client("https://api.example", store, http_client=http, clock=lambda: now)
        client_b = self.make_client("https://api.example", store, http_client=http, clock=lambda: now)
        self.set_credentials(client_a, old)
        client_a._proof = client_b._proof = lambda method, uri, token: "test-proof"
        self.assertEqual(client_a.credentials.access_token, "a" * 43)

        client_b.refresh()
        client_a.request("GET", "/v1/me")

        self.assertEqual(http.calls[1][2]["headers"]["Authorization"], f"DPoP {'b' * 43}")

    def test_disconnect_holds_shared_lock_through_delete_and_keychain_cleanup(self):
        now = 1_800_000_000
        expiry = datetime.fromtimestamp(now + 600, timezone.utc).isoformat().replace("+00:00", "Z")
        delete_entered = Event()
        release_delete = Event()

        class BlockingDeleteHTTP(FakeHTTP):
            def request(self, method, url, **kwargs):
                if method == "DELETE":
                    delete_entered.set()
                    if not release_delete.wait(timeout=2):
                        raise TimeoutError("test did not release delete")
                return super().request(method, url, **kwargs)

        store = MemoryStore()
        http = BlockingDeleteHTTP([FakeResponse({}, 204)])
        client_a = self.make_client("https://api.example", store, http_client=http, clock=lambda: now)
        client_b = self.make_client("https://api.example", store, http_client=http, clock=lambda: now)
        self.set_credentials(client_a, DeviceCredentials("a" * 43, "r" * 43, expiry, "test-private-key"))
        client_a._proof = client_b._proof = lambda method, uri, token: "test-proof"
        refresh_started = Event()

        def refresh_from_second_client():
            refresh_started.set()
            return client_b.refresh()

        with ThreadPoolExecutor(max_workers=2) as pool:
            disconnect_future = pool.submit(client_a.disconnect)
            self.assertTrue(delete_entered.wait(timeout=2))
            refresh_future = pool.submit(refresh_from_second_client)
            self.assertTrue(refresh_started.wait(timeout=2))
            sleep(0.05)
            self.assertFalse(refresh_future.done())
            release_delete.set()
            disconnect_future.result(timeout=2)
            with self.assertRaises(OAuthClientError):
                refresh_future.result(timeout=2)

        self.assertIsNone(store.value)
        self.assertEqual([call[0] for call in http.calls], ["DELETE"])

    def test_public_refresh_serializes_concurrent_rotations(self):
        now = 1_800_000_000
        renewed_expiry = datetime.fromtimestamp(now + 900, timezone.utc).isoformat().replace("+00:00", "Z")

        class DelayedHTTP(FakeHTTP):
            def request(self, method, url, **kwargs):
                if url.endswith("/v1/sessions/refresh"):
                    sleep(0.02)
                return super().request(method, url, **kwargs)

        http = DelayedHTTP(
            [
                FakeResponse({"access_token": "b" * 43, "refresh_token": "s" * 43, "expires_at": renewed_expiry}),
                FakeResponse({"access_token": "c" * 43, "refresh_token": "t" * 43, "expires_at": renewed_expiry}),
            ]
        )
        client = self.make_client(
            "https://api.example",
            MemoryStore(),
            http_client=http,
            browser_open=lambda _: None,
            clock=lambda: now,
        )
        self.set_credentials(client, DeviceCredentials("a" * 43, "r" * 43, renewed_expiry, "test-private-key"))
        client._proof = lambda method, uri, token: "test-proof"
        calls_ready = Barrier(2)

        def refresh_at_once():
            calls_ready.wait(timeout=2)
            return client.refresh()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(refresh_at_once) for _ in range(2)]
            for future in futures:
                future.result(timeout=3)

        presented_refresh_tokens = [call[2]["json"]["refresh_token"] for call in http.calls]
        self.assertEqual(presented_refresh_tokens, ["r" * 43, "s" * 43])

    def test_request_does_not_refresh_after_upstream_reauthorization_required(self):
        expiry = datetime.fromtimestamp(1_800_000_600, timezone.utc).isoformat().replace("+00:00", "Z")
        response = FakeResponse({"error": "reauthorization_required", "reauthorization_required": True}, 401)
        http = FakeHTTP([response])
        client = self.make_client(
            "https://api.example",
            MemoryStore(),
            http_client=http,
            browser_open=lambda _: None,
            clock=lambda: 1_800_000_000,
        )
        self.set_credentials(client, DeviceCredentials("a" * 43, "r" * 43, expiry, "test-private-key"))
        client._proof = lambda method, uri, token: "test-proof"
        with patch.object(client, "refresh") as refresh:
            with self.assertRaises(RuntimeError):
                client.request("GET", "/v1/me")
        refresh.assert_not_called()

    def test_refresh_rotates_tokens_and_disconnect_deletes_keychain_entry(self):
        http = FakeHTTP([
            FakeResponse({"access_token": "b" * 43, "refresh_token": "s" * 43, "expires_at": "2030-01-01T00:15:00Z"}),
            FakeResponse({}, 204),
        ])
        store = MemoryStore()
        client = self.make_client("https://api.example", store, http_client=http, browser_open=lambda _: None)
        pem = client._new_private_key_pem()
        store.save(
            {
                "access_token": "a" * 43,
                "refresh_token": "r" * 43,
                "expires_at": "2030-01-01T00:15:00Z",
                "private_key_pem": pem,
            }
        )
        refreshed = client.refresh()
        self.assertEqual(refreshed.access_token, "b" * 43)
        self.assertEqual(http.calls[0][2]["json"], {"refresh_token": "r" * 43})
        client.disconnect()
        self.assertIsNone(store.value)
        self.assertEqual(http.calls[1][0], "DELETE")
