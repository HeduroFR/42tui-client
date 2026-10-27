"""Portable dashboard input snapshots and immutable composed view models."""
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass(frozen=True)
class DashboardProject:
    id: int | None
    ui_key: str
    name: str
    status: str
    local_path: str | None = None
    official_project_id: int | None = None
    catalog_data: dict = field(default_factory=dict)
    progress_data: dict = field(default_factory=dict)

    @classmethod
    def from_project(cls, project):
        return cls(project.id, project.ui_key, project.name, project.status,
                   getattr(project, 'local_path', None), getattr(project, 'official_project_id', None),
                   dict(getattr(project, 'catalog_data', {})), dict(getattr(project, 'progress_data', {})))


@dataclass(frozen=True)
class ProfileStats:
    wallet: int | None
    correction_points: int | None
    location: str | None


@dataclass(frozen=True)
class Journey:
    total: int
    completed: int
    active: int
    available: int
    locked: int
    next_name: str


@dataclass(frozen=True)
class Deadline:
    milestone: str
    next_label: str


@dataclass(frozen=True)
class Activity:
    latest: dict[int, datetime]
    active_project_id: int | None


@dataclass(frozen=True)
class DashboardViewModel:
    stats: ProfileStats
    resume: DashboardProject | None
    resume_seconds: float
    resume_has_folder: bool
    activity_label: str
    active_now: bool
    recent_activity: bool
    setup_candidates: tuple[DashboardProject, ...]
    recent_notes: tuple[tuple, ...]
    week_starts: tuple[date, ...]
    day_seconds: dict[date, float]
    week_seconds: dict[date, float]
    journey: Journey
    deadline: Deadline
