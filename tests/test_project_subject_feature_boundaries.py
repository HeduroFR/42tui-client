"""Subject atomic publication, metadata fencing and public aliases."""
import ast
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class SubjectBoundaryTests(unittest.TestCase):
    def test_stale_download_is_cleaned_without_replacing_existing_pdf(self):
        from ft_tui.features.projects.subjects.adapters.files import synchronize_subject_pdf
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'subject.pdf';path.write_bytes(b'%PDF-1.4 old');active=True
            def download(slug,temporary):
                nonlocal active
                temporary.write_bytes(b'%PDF-1.7 new');active=False;return True
            synchronize_subject_pdf('libft',path,download,None,current=lambda:active)
            self.assertEqual(path.read_bytes(),b'%PDF-1.4 old')
            self.assertEqual(list(Path(directory).iterdir()),[path])

    def test_repository_does_not_persist_metadata_for_a_changed_project_path(self):
        from ft_tui.db.database import make_session_factory
        from ft_tui.db.models import Project
        from ft_tui.features.projects.subjects.adapters.sqlite import SqliteSubjectRepository
        factory=make_session_factory('sqlite:///:memory:')
        try:
            with factory() as session:
                project=Project(slug='libft',name='Libft',local_path='/tmp/new')
                session.add(project);session.commit();identity=project.id
            repository=SqliteSubjectRepository(factory)
            self.assertFalse(repository.save(identity,'/tmp/old','/tmp/old/subject.pdf','a','b',None))
            with factory() as session:self.assertIsNone(session.get(Project,identity).subject_pdf_sha256)
        finally:factory.kw['bind'].dispose()

    def test_subject_error_and_view_have_one_owner(self):
        from ft_tui.api.http_client import SubjectPendingError
        from ft_tui.features.projects.subjects.models import SubjectPendingError as Canonical
        self.assertIs(SubjectPendingError,Canonical)
        from ft_tui.features.projects.views.details import ProjectDetailsMixin
        from ft_tui.features.projects.views.subjects import SubjectMixin
        self.assertTrue(issubclass(ProjectDetailsMixin,SubjectMixin))
        self.assertEqual(ProjectDetailsMixin.SUBJECT_PENDING_POLL_SECONDS,2)

    def test_subject_core_imports_no_framework_or_io_implementation(self):
        from ft_tui.features.projects.subjects import service
        root=Path(service.__file__).parent
        for name in ('service','models','ports'):
            for node in ast.walk(ast.parse((root/(name+'.py')).read_text())):
                names=([node.module] if isinstance(node,ast.ImportFrom) and node.module else
                       [alias.name for alias in node.names] if isinstance(node,ast.Import) else [])
                for name in names:self.assertFalse(name.startswith(('sqlalchemy','textual','httpx','subprocess','ft_tui.ui','ft_tui.api')),name)

    def test_missing_opener_is_distinct_from_a_failed_launch(self):
        from ft_tui.features.projects.subjects.adapters.files import SubjectFiles,SubjectViewerUnavailable
        files=SubjectFiles()
        with patch('ft_tui.features.projects.subjects.adapters.files.platform.system',return_value='Linux'), \
             patch('ft_tui.features.projects.subjects.adapters.files.shutil.which',return_value=None):
            with self.assertRaisesRegex(SubjectViewerUnavailable,'xdg-open was not found'):
                files.open_system(Path('/tmp/fake.pdf'))
        with patch('ft_tui.features.projects.subjects.adapters.files.platform.system',return_value='Linux'), \
             patch('ft_tui.features.projects.subjects.adapters.files.shutil.which',return_value='/fake/open'), \
             patch('ft_tui.features.projects.subjects.adapters.files.subprocess.Popen',side_effect=FileNotFoundError('missing')):
            with self.assertRaises(FileNotFoundError) as caught:files.open_system(Path('/tmp/fake.pdf'))
            self.assertNotIsInstance(caught.exception,SubjectViewerUnavailable)
