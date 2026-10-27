"""Social capabilities; the backend remains the source of consent decisions."""
from typing import Protocol


class SocialReader(Protocol):
    def get_social(self) -> dict: ...
    def get_poke_neighbours(self) -> list[dict]: ...


class SocialActions(Protocol):
    def social_action(self, draft: dict) -> dict: ...


class ConfirmedFriendRepository(Protocol):
    def cache_confirmed(self, account: str, friends: list[dict], *, origin: str = '') -> None: ...
