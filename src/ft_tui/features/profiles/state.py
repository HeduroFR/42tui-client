"""Single owner of cached profile/goals presentation state and polling deadline."""
from dataclasses import dataclass, field


@dataclass
class ProfileState:
    profile: dict = field(default_factory=dict)
    goals: dict = field(default_factory=dict)
    goals_scope: tuple | None = None
    next_poll: float = 0.0
