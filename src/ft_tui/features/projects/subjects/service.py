"""Headless due-subject orchestration without filesystem or ORM ownership."""
from datetime import datetime,timezone
from .models import PDFCheckError,SubjectPendingError
from .ports import SubjectProvider,SubjectRepository,SubjectStorage


class SubjectService:
    def __init__(self,repository: SubjectRepository,files: SubjectStorage):
        self.repository=repository;self.files=files

    def inspect(self,local_path,subject_path):return self.files.inspect(local_path,subject_path)
    def viewer(self,name):return self.files.viewer(name)
    def run_tdf(self,executable,path):return self.files.run_tdf(executable,path)
    def open_system(self,path):return self.files.open_system(path)

    def sync_due(self,provider: SubjectProvider,interval,pending,*,current=lambda:True):
        now=datetime.now(timezone.utc).replace(tzinfo=None)
        results=[];errors=[]
        downloader=getattr(provider,'download_subject_pdf',None)
        reference_getter=getattr(provider,'get_subject_reference_sha256',None)
        for project_id,slug,local_path,previous_digest,previous_reference,checked_at in self.repository.subjects():
            if not current():break
            root=self.files.root(local_path)
            if root is None:continue
            path=self.files.subject(root)
            if (self.files.regular(path) and not self.files.symlink(path) and previous_digest is not None
                    and checked_at is not None and (now-checked_at).total_seconds()<interval):continue
            try:
                self.files.ensure_ignore(root)
                if self.files.symlink(path):raise PDFCheckError('Refusing to read or replace a symlinked subject.pdf.')
                if not current():break
                reference=reference_getter(slug) if callable(reference_getter) else None
                if not current():break
                digest=self.files.synchronize(slug,path,downloader,reference,current=current)
            except SubjectPendingError as error:
                if current():pending(slug,str(error))
                continue
            except (PDFCheckError,OSError) as error:
                if current():errors.append((slug,str(error)))
                continue
            except Exception as error:
                if current():errors.append((slug,f'Provider check failed: {error}'))
                continue
            if not current():break
            checked=datetime.now(timezone.utc).replace(tzinfo=None)
            try:
                if not self.repository.save(project_id,local_path,str(path),digest,reference,checked):continue
            except Exception as error:
                if current():errors.append((slug,f'Could not save subject check: {error}'))
                continue
            changed=((previous_digest is not None and digest is not None and previous_digest!=digest)
                or (previous_reference is not None and reference is not None and previous_reference!=reference))
            if current():results.append((project_id,slug,str(path),digest,reference,checked,changed))
        return results,errors
