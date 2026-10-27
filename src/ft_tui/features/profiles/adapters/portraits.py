"""Bounded public CDN portrait transport and legacy helper exports."""
import base64
import httpx
from ft_tui.features.profiles.models import portrait_url
from ft_tui.features.profiles.projections import latest_attempts, weekly_attendance
from ft_tui.shared.portraits import MAX_PORTRAIT_BYTES


def download_portrait(url):
    """Public images only; no redirects, cookies or OAuth credentials."""
    if not portrait_url(url):
        raise ValueError('Invalid portrait URL')
    with httpx.stream('GET', url, timeout=10, follow_redirects=False) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > MAX_PORTRAIT_BYTES:
                raise ValueError('Portrait exceeds limit')
    return {'image_url': url, 'status': 'ready', 'image_base64': base64.b64encode(data).decode('ascii')}
