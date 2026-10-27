"""Local preference and external release-check capabilities."""
from typing import Protocol
from collections.abc import Mapping


class InstallationPreferences(Protocol):
    def get(self,key: str,default=''): ...
    def save(self,values: Mapping[str,str]): ...


class ReleaseCheck(Protocol):
    def __call__(self) -> str | None: ...
