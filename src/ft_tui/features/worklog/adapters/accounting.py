"""Editor-neutral local coding activity ingestion and aggregation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ft_tui.db.models import ActivityHeartbeat, Project, TimeLog


from ft_tui.shared.activity import IDLE_TIMEOUT_SECONDS


def record_heartbeat(
    session: Session,
    file_path: str | Path,
    *,
    editor: str = "unknown",
    is_write: bool = False,
    occurred_at: datetime | None = None,
) -> tuple[Project, float]:
    """Record an editor event, crediting only the gap since recent activity.

    The incoming absolute file path is used only to find a configured project. It is not
    written to the database. Activity from multiple editors shares one global idle window,
    so simultaneous use does not double count time.
    """
    if session.get_bind().dialect.name == "sqlite" and not session.in_transaction():
        # Serialize CLI processes around the read-previous / insert-current sequence.
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    target = Path(file_path).expanduser().resolve(strict=False)
    candidates = list(session.scalars(select(Project).where(Project.local_path.is_not(None))))
    matches: list[tuple[int, Project]] = []
    for project in candidates:
        project_root = Path(project.local_path or "").expanduser().resolve(strict=False)
        try:
            target.relative_to(project_root)
        except ValueError:
            continue
        matches.append((len(str(project_root)), project))
    if not matches:
        raise ValueError("File is outside every configured project folder")
    project = max(matches, key=lambda match: match[0])[1]

    timestamp = occurred_at or datetime.now(timezone.utc).replace(tzinfo=None)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
    previous = session.scalar(
        select(ActivityHeartbeat)
        .order_by(ActivityHeartbeat.occurred_at.desc(), ActivityHeartbeat.id.desc())
        .limit(1)
    )
    credited_project_id: int | None = None
    credited_seconds = 0.0
    if previous is not None:
        delta = (timestamp - previous.occurred_at).total_seconds()
        if 0 < delta <= IDLE_TIMEOUT_SECONDS:
            credited_project_id = previous.project_id
            credited_seconds = delta

    heartbeat = ActivityHeartbeat(
        project_id=project.id,
        editor=editor[:100] or "unknown",
        occurred_at=timestamp,
        is_write=is_write,
        credited_project_id=credited_project_id,
        credited_seconds=credited_seconds,
    )
    session.add(heartbeat)
    session.commit()
    return project, credited_seconds


def tracked_seconds(session: Session, project_id: int) -> float:
    """Sum editor-credited time and manual sessions, including a running session."""
    editor_seconds = session.scalar(
        select(func.coalesce(func.sum(ActivityHeartbeat.credited_seconds), 0.0)).where(
            ActivityHeartbeat.credited_project_id == project_id
        )
    ) or 0.0
    manual_seconds = session.scalar(
        select(func.coalesce(func.sum(TimeLog.duration), 0.0)).where(
            TimeLog.project_id == project_id,
            TimeLog.end_time.is_not(None),
        )
    ) or 0.0
    running = session.scalar(
        select(TimeLog).where(
            TimeLog.project_id == project_id,
            TimeLog.end_time.is_(None),
        ).order_by(TimeLog.start_time.desc()).limit(1)
    )
    if running is not None:
        manual_seconds += max(0.0, (_utc_naive_now() - running.start_time).total_seconds())
    return float(editor_seconds + manual_seconds)


def active_manual_timer(session: Session) -> TimeLog | None:
    """Return the currently running manual timer, if one exists."""
    return session.scalar(
        select(TimeLog)
        .where(TimeLog.end_time.is_(None))
        .order_by(TimeLog.start_time.desc(), TimeLog.id.desc())
        .limit(1)
    )


def start_manual_timer(session: Session, project_id: int) -> tuple[TimeLog, bool]:
    """Start a project timer, stopping any other active manual session first.

    Returns the active log and whether a timer for another project was switched.
    """
    now = _utc_naive_now()
    current = active_manual_timer(session)
    if current is not None and current.project_id == project_id:
        return current, False
    switched = current is not None
    if current is not None:
        _finish_manual_log(current, now)
    log = TimeLog(project_id=project_id, start_time=now)
    session.add(log)
    session.commit()
    session.refresh(log)
    return log, switched


def stop_manual_timer(session: Session, project_id: int | None = None) -> TimeLog | None:
    """Stop the running manual timer, optionally only if it belongs to a project."""
    current = active_manual_timer(session)
    if current is None or (project_id is not None and current.project_id != project_id):
        return None
    _finish_manual_log(current, _utc_naive_now())
    session.commit()
    session.refresh(current)
    return current


def _finish_manual_log(log: TimeLog, end_time: datetime) -> None:
    log.end_time = end_time
    log.duration = max(0.0, (end_time - log.start_time).total_seconds())


def _utc_naive_now() -> datetime:
    """Use the naive UTC convention of the existing SQLite DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
