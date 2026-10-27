"""Local application and database paths."""

import os
from pathlib import Path


APP_NAME = "42tui"
DEFAULT_OAUTH_API_URL = "https://oauth.42wip.in"


def oauth_api_url() -> str:
    """Return the configured OAuth backend origin."""
    return os.environ.get("FT_TUI_API_URL") or DEFAULT_OAUTH_API_URL


def data_dir() -> Path:
    """Return the XDG data directory, with a home-directory fallback."""
    base = os.environ.get("XDG_DATA_HOME")
    return Path(base).expanduser() / APP_NAME if base else Path.home() / ".local/share" / APP_NAME


def database_url() -> str:
    """Return a SQLite URL, allowing an explicit path override for development."""
    override = os.environ.get("FT_TUI_DATABASE")
    path = Path(override).expanduser() if override else data_dir() / "42tui.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{path}"
