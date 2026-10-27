"""Preserve project settings transactions and invalidate only path-bound subjects."""
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from ft_tui.db.models import Project

class SqliteProjectRepository:
    def __init__(self,session_factory):self.session_factory=session_factory
    def save_settings(self,project_id,values,*,catalog,progress):
        with self.session_factory() as s:
            project=s.scalar(select(Project).options(selectinload(Project.time_logs),selectinload(Project.notes)).where(Project.id==project_id))
            if project is None:return None
            path=values['local_path'] or None
            if project.local_path!=path:
                project.subject_pdf_path=None
                project.subject_pdf_sha256=None
                project.subject_reference_sha256=None
                project.subject_checked_at=None
            project.local_path=path
            project.dev_repo_url=values['dev_repo_url'] or None
            if project.local_path and project.status=='available':project.status='in_progress'
            s.commit()
            project._progress_data=progress
            project._catalog_data=catalog
            return project
