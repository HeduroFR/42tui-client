"""Capabilities needed by account bootstrap; profile reads remain optional."""
from typing import Protocol


class AccountReader(Protocol):
    def list_cursuses(self) -> list: ...


class ProfileReader(Protocol):
    def get_profile(self) -> dict: ...
