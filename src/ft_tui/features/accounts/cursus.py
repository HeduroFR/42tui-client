"""Deterministic choices for a student's default cursus."""

from collections.abc import Sequence
from datetime import date, datetime, timezone

from ft_tui.api.client_interface import CursusSnapshot


def is_main_cursus(cursus: CursusSnapshot) -> bool:
    """Recognize the main curriculum independently of membership IDs."""
    return "".join(cursus.name.casefold().split()) in {"42", "42cursus"}


def select_default_cursus(
    cursuses: Sequence[CursusSnapshot], today: date
) -> CursusSnapshot | None:
    """Prefer the active main curriculum, then the latest active membership."""
    if not cursuses:
        return None

    active = [
        cursus
        for cursus in cursuses
        if cursus.end_at is None or cursus.end_at.date() > today
    ]
    candidates = active or list(cursuses)

    def order(cursus: CursusSnapshot) -> tuple[int, int, float, int]:
        begin_at = cursus.begin_at
        if begin_at is None:
            timestamp = float("-inf")
        else:
            normalized = (
                begin_at.replace(tzinfo=timezone.utc)
                if begin_at.tzinfo is None
                else begin_at.astimezone(timezone.utc)
            )
            timestamp = normalized.timestamp()
        return (int(is_main_cursus(cursus)), int(begin_at is not None), timestamp, -cursus.id)

    return max(candidates, key=order)
