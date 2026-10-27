"""Portable subject rows and path-checked metadata transactions."""
from sqlalchemy import select
from ft_tui.db.models import Project


class SqliteSubjectRepository:
    def __init__(self,session_factory):self.session_factory=session_factory

    def subjects(self):
        with self.session_factory() as session:
            return [tuple(row) for row in session.execute(select(Project.id,Project.slug,Project.local_path,
                Project.subject_pdf_sha256,Project.subject_reference_sha256,Project.subject_checked_at)).all()]

    def save(self,project_id,local_path,path,digest,reference,checked):
        with self.session_factory() as session:
            project=session.get(Project,project_id)
            if project is None or project.local_path!=local_path:return False
            project.subject_pdf_path=path
            project.subject_pdf_sha256=digest
            project.subject_reference_sha256=reference
            project.subject_checked_at=checked
            session.commit()
            return True
