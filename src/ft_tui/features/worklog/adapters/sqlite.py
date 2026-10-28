"""Own worklog sessions and preserve existing note/timer/heartbeat transactions."""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from ft_tui.db.models import DevNote
from . import accounting
from ..models import Note,Timer,TimerSummary,TimerOutcome,HeartbeatOutcome,NoteSaveError

class SqliteWorklogRepository:
    def __init__(self,session_factory):self.session_factory=session_factory
    @staticmethod
    def _note(row):return Note(row.id,row.project_id,row.title,row.content,row.updated_at)
    def notes(self,project_id,limit=None):
        query=select(DevNote).where(DevNote.project_id==project_id).order_by(DevNote.updated_at.desc(),DevNote.id.desc())
        if limit is not None:query=query.limit(limit)
        with self.session_factory() as s:return [self._note(row) for row in s.scalars(query)]
    def note(self,note_id):
        with self.session_factory() as s:
            row=s.get(DevNote,note_id)
            return self._note(row) if row is not None else None
    def save_note(self,project_id,note_id,title,content):
        try:
            with self.session_factory() as s:
                if note_id is None:
                    row=DevNote(project_id=project_id,title=title,content=content);s.add(row)
                else:
                    row=s.get(DevNote,note_id)
                    if row is None or row.project_id!=project_id:return None
                    row.title=title;row.content=content;row.updated_at=datetime.now()
                s.commit();s.refresh(row);return self._note(row)
        except OperationalError as error:
            raise NoteSaveError("Could not persist the note") from error
    def delete_note(self,note_id):
        with self.session_factory() as s:
            row=s.get(DevNote,note_id)
            if row is not None:s.delete(row);s.commit()
    def timer(self,project_id):
        with self.session_factory() as s:
            row=accounting.active_manual_timer(s)
            active=Timer(row.project_id,row.start_time) if row is not None else None
            total=accounting.tracked_seconds(s,project_id) if project_id is not None else 0.0
            return TimerSummary(active,total)
    def toggle_timer(self,project_id):
        with self.session_factory() as s:
            accounting.lock_manual_timer(s)
            active=accounting.active_manual_timer(s)
            if active is not None and active.project_id==project_id:
                accounting.stop_manual_timer(s,project_id);return TimerOutcome('stopped')
            _,switched=accounting.start_manual_timer(s,project_id)
            return TimerOutcome('started',switched)
    def heartbeat(self,path,**kwargs):
        with self.session_factory() as s:
            project,credited=accounting.record_heartbeat(s,path,**kwargs)
            return HeartbeatOutcome(project.name,credited)
