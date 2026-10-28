"""Portable note, timer and heartbeat outcomes; ORM identities stay in adapters."""
from dataclasses import dataclass
from datetime import datetime

class NoteSaveError(RuntimeError):
    """Local storage could not persist the note; the editor must keep its draft."""


@dataclass(frozen=True)
class Note:
    id:int
    project_id:int
    title:str
    content:str
    updated_at:datetime

@dataclass(frozen=True)
class Timer:
    project_id:int
    start_time:datetime

@dataclass(frozen=True)
class TimerSummary:
    active:Timer|None
    total_seconds:float

@dataclass(frozen=True)
class TimerOutcome:
    action:str
    switched:bool=False

@dataclass(frozen=True)
class HeartbeatOutcome:
    project_name:str
    credited_seconds:float
