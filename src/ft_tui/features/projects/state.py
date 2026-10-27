"""Mutable project workspace state, owned once and exposed through shell accessors."""
from dataclasses import dataclass,field

@dataclass
class ProjectState:
    projects: dict = field(default_factory=dict)
    project_curriculum: dict = field(default_factory=dict)
    _evidence_owner_unverified: bool = False
    _editing_project_key: str | None = None
    project_last_activity: dict = field(default_factory=dict)
    active_project_id: int | None = None
    selected_project_key: str | None = None
