"""HTTP failure warnings must include safe backend codes, never raw bodies."""
import unittest
import httpx
from ft_tui.api.oauth_client import _decode_response


class ApiErrorDiagnosticsTests(unittest.TestCase):
    def test_known_backend_error_is_visible_and_preserves_http_response(self):
        for status, code in [(502, "invalid_upstream_response"), (401, "invalid_device_credentials")]:
            with self.subTest(status=status):
                response = httpx.Response(status, json={"error": code, "detail": "private"}, request=httpx.Request("GET", "https://api.example/v1/projects"))
                with self.assertRaises(httpx.HTTPStatusError) as caught:
                    _decode_response(response)
                self.assertIn(code, str(caught.exception))
                self.assertNotIn("private", str(caught.exception))
                self.assertIs(caught.exception.response, response)

    def test_unknown_error_values_and_proxy_html_do_not_enter_warning(self):
        for response in [
            httpx.Response(502, json={"error": "private"}, request=httpx.Request("GET", "https://api.example/v1/projects")),
            httpx.Response(502, text="<html>private</html>", request=httpx.Request("GET", "https://api.example/v1/projects")),
        ]:
            with self.subTest(response=response), self.assertRaises(httpx.HTTPStatusError) as caught:
                _decode_response(response)
            self.assertNotIn("private", str(caught.exception))
