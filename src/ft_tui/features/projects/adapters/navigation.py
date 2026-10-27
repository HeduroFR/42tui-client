"""Resolve local project directories for the ``42goto`` shell command."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ft_tui.db.models import ActivityHeartbeat, DevNote, Project, TimeLog
from ft_tui.features.worklog.adapters.accounting import IDLE_TIMEOUT_SECONDS


class ProjectNavigationError(ValueError):
    """Raised when a project cannot be mapped to an existing local directory."""


def configured_projects(session: Session) -> list[Project]:
    """Return projects whose configured local path currently exists."""
    projects = session.scalars(
        select(Project).where(Project.local_path.is_not(None)).order_by(Project.name)
    )
    return [project for project in projects if _existing_directory(project.local_path)]


def resolve_project_path(session: Session, query: str | None = None) -> Path:
    """Resolve a project by name/slug or select the current/recent local project.

    With no query, a live editor heartbeat wins. When no editor is active, the
    most recently tracked project is used. A sole configured in-progress project
    is the final fallback; ambiguous or missing state is reported explicitly.
    """
    if query:
        projects = list(session.scalars(select(Project).order_by(Project.name)))
        return _resolve_named_project(projects, query)
    return _resolve_active_project(session, configured_projects(session))


def _resolve_named_project(projects: list[Project], query: str) -> Path:
    normalized = query.strip().casefold()
    if not normalized:
        raise ProjectNavigationError("Enter a project name or slug.")

    exact_slug = [project for project in projects if project.slug.casefold() == normalized]
    exact_name = [project for project in projects if project.name.casefold() == normalized]
    matches = exact_slug or exact_name
    if not matches:
        matches = [
            project
            for project in projects
            if normalized in project.slug.casefold() or normalized in project.name.casefold()
        ]
    if len(matches) > 1:
        names = ", ".join(f"{project.name} ({project.slug})" for project in matches)
        raise ProjectNavigationError(f"'{query}' matches multiple projects: {names}. Use a project slug.")
    if not matches:
        raise ProjectNavigationError(f"No configured project matches '{query}'.")
    return _project_directory(matches[0])


def _resolve_active_project(session: Session, projects: list[Project]) -> Path:
    by_id = {project.id: project for project in projects}
    if not by_id:
        raise ProjectNavigationError("No projects have an existing local folder configured.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    latest_heartbeat = session.scalar(
        select(ActivityHeartbeat)
        .where(
            ActivityHeartbeat.occurred_at >= now - timedelta(seconds=IDLE_TIMEOUT_SECONDS),
            ActivityHeartbeat.occurred_at <= now,
            ActivityHeartbeat.project_id.in_(by_id),
        )
        .order_by(ActivityHeartbeat.occurred_at.desc(), ActivityHeartbeat.id.desc())
        .limit(1)
    )
    if latest_heartbeat is not None:
        return _project_directory(by_id[latest_heartbeat.project_id])

    last_activity: dict[int, datetime] = {}
    activity_sources = (
        (ActivityHeartbeat.project_id, ActivityHeartbeat.occurred_at),
        (TimeLog.project_id, func.coalesce(TimeLog.end_time, TimeLog.start_time)),
        (DevNote.project_id, DevNote.updated_at),
    )
    for project_id_column, timestamp_column in activity_sources:
        rows = session.execute(
            select(project_id_column, func.max(timestamp_column))
            .where(project_id_column.in_(by_id))
            .group_by(project_id_column)
        )
        for project_id, timestamp in rows:
            if timestamp is not None and (
                project_id not in last_activity or timestamp > last_activity[project_id]
            ):
                last_activity[project_id] = timestamp
    if last_activity:
        project_id = max(last_activity, key=last_activity.__getitem__)
        return _project_directory(by_id[project_id])

    in_progress = [
        project for project in projects if project.status.casefold() == "in_progress"
    ]
    if len(in_progress) == 1:
        return _project_directory(in_progress[0])
    if len(in_progress) > 1:
        names = ", ".join(f"{project.name} ({project.slug})" for project in in_progress)
        raise ProjectNavigationError(
            "No recent project activity identifies the active project. Choose one: "
            f"{names}."
        )
    raise ProjectNavigationError(
        "No active project has been tracked yet. Pass a project name or slug, "
        "for example: 42goto libft."
    )


def _existing_directory(value: str | None) -> bool:
    if not value:
        return False
    try:
        return Path(value).expanduser().is_dir()
    except (OSError, RuntimeError):
        return False


def _project_directory(project: Project) -> Path:
    if not project.local_path:
        raise ProjectNavigationError(
            f"No local folder is configured for {project.name} ({project.slug})."
        )
    path = Path(project.local_path).expanduser()
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ProjectNavigationError(
            f"The local folder for {project.name} is unavailable: {path}"
        ) from error
    if not resolved.is_dir():
        raise ProjectNavigationError(
            f"The local path for {project.name} is not a directory: {resolved}"
        )
    return resolved
