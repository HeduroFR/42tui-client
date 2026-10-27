"""Dashboard interaction state; composed view models are not persistent caches."""
from dataclasses import dataclass


@dataclass
class DashboardState:
    continue_key: str | None = None
    setup_key: str | None = None
    recent_notes_signature: tuple = ()
    portrait_scope: tuple | None = None
    portrait_retry: float = 0.0
    portrait_loading: tuple | None = None
    render_revision: int = 0
