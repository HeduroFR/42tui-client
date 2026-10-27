"""Transport error classification and external browser integration."""
import webbrowser
import httpx


def authorization_status(error):
    return error.response.status_code if isinstance(error,httpx.HTTPStatusError) else None


def open_browser(url):return webbrowser.open(url)
