"""Bounded unauthenticated check of the configured backend's liveness."""

import httpx


def backend_available(base_url: str) -> bool:
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/health", timeout=5.0, follow_redirects=False)
        return response.status_code == 200 and response.json() == {"status": "ok"}
    except (httpx.HTTPError, ValueError):
        return False
