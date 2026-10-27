"""Select the online provider from secure device-session state."""

from .http_client import HttpProjectProvider
from .oauth_client import OAuthClient
from .client_interface import ProjectProvider


def provider_for_device(oauth_client: OAuthClient) -> ProjectProvider | None:
    """Return no provider until this device has a usable 42TUI session."""
    try:
        credentials = oauth_client.credentials
    except Exception:
        # Missing/unavailable OS keychain support must not prevent local startup.
        return None
    if credentials is not None and credentials.access_token and credentials.refresh_token:
        return HttpProjectProvider(oauth_client=oauth_client)
    return None
