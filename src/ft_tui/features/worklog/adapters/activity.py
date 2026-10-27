"""Read-only bridge to local worklog data until that feature is migrated."""
from sqlalchemy import select, func
from ft_tui.db.models import Project, DevNote, ActivityHeartbeat, TimeLog
from ft_tui.features.worklog.adapters.accounting import tracked_seconds


class SqliteActivityReader:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def tracked(self, project_id):
        with self.session_factory() as session:
            return tracked_seconds(session, project_id)

    def recent_notes(self):
        with self.session_factory() as session:
            rows = session.execute(
                select(DevNote.id, Project.id, Project.name, DevNote.title, DevNote.updated_at)
                .join(Project, DevNote.project_id == Project.id)
                .order_by(DevNote.updated_at.desc(), DevNote.id.desc()).limit(3)
            ).all()
            return [tuple(row) for row in rows]

    def heartbeats_since(self, start):
        with self.session_factory() as session:
            rows = session.execute(select(ActivityHeartbeat.occurred_at, ActivityHeartbeat.credited_seconds)
                                   .where(ActivityHeartbeat.occurred_at >= start)).all()
            return [tuple(row) for row in rows]

    def activity(self):
        with self.session_factory() as session:
            latest = {}
            for project_column, time_column in (
                (ActivityHeartbeat.project_id, ActivityHeartbeat.occurred_at),
                (TimeLog.project_id, func.coalesce(TimeLog.end_time, TimeLog.start_time)),
                (DevNote.project_id, DevNote.updated_at),
            ):
                for project_id, at in session.execute(select(project_column, func.max(time_column)).group_by(project_column)):
                    if at is not None and (project_id not in latest or at > latest[project_id]):
                        latest[project_id] = at
            heartbeat = session.execute(select(ActivityHeartbeat.project_id, ActivityHeartbeat.occurred_at)
                                        .order_by(ActivityHeartbeat.occurred_at.desc(), ActivityHeartbeat.id.desc())
                                        .limit(1)).first()
            return latest, tuple(heartbeat) if heartbeat is not None else None
