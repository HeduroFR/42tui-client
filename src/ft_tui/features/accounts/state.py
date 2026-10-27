"""Account presentation state, independent of the app and credential storage."""
from dataclasses import dataclass, field


@dataclass
class AccountState:
    account_id: str | None = None
    login: str | None = None
    profile: dict = field(default_factory=dict)
    campuses: list = field(default_factory=list)
    connected: bool = False
    generation: int = 0
