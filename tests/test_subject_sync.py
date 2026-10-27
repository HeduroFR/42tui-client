import base64
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.features.projects.subjects.adapters.files import PDFCheckError, synchronize_subject_pdf, ensure_pdf_gitignore


class SubjectSyncTests(unittest.TestCase):
    def test_download_replace_and_leave_identical_pdf_untouched(self):
        pdf = b'%PDF-1.7\ncurrent subject'
        digest = hashlib.sha256(pdf).hexdigest()
        api = Mock()
        api.request.return_value = {'sha256': digest, 'pdf_base64': base64.b64encode(pdf).decode()}
        provider = HttpProjectProvider(api)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'subject.pdf'
            for old in (None, b'%PDF-1.4\nold subject', b'corrupt'):
                if old is not None:
                    path.write_bytes(old)
                reference = provider.get_subject_reference_sha256('libft')
                self.assertEqual(synchronize_subject_pdf('libft', path, provider.download_subject_pdf, reference), digest)
                self.assertEqual(path.read_bytes(), pdf)
            downloader = Mock()
            before = path.stat().st_mtime_ns
            synchronize_subject_pdf('libft', path, downloader, digest)
            downloader.assert_not_called()
            self.assertEqual(path.stat().st_mtime_ns, before)

    def test_failed_or_invalid_download_preserves_local_pdf_and_cleans_staging(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'subject.pdf'
            old = b'%PDF-1.4\nold'
            for response in (b'login html', b'%PDF-1.7\nwrong revision', None):
                path.write_bytes(old)
                def download(slug, destination):
                    if response is None:
                        raise OSError('network failure')
                    destination.write_bytes(response)
                    return True
                with self.assertRaises((PDFCheckError, OSError)):
                    synchronize_subject_pdf('libft', path, download, 'a' * 64)
                self.assertEqual(path.read_bytes(), old)
                self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_symlinks_are_rejected_and_ignore_rules_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.git').mkdir()
            ignore = root / '.gitignore'
            ignore.write_text('build/')
            self.assertTrue(ensure_pdf_gitignore(root))
            self.assertFalse(ensure_pdf_gitignore(root))
            self.assertTrue(ignore.read_text().startswith('build/\n'))
            target = root / 'outside'
            target.write_bytes(b'%PDF-1.7')
            path = root / 'subject.pdf'
            path.symlink_to(target)
            with self.assertRaises(PDFCheckError):
                synchronize_subject_pdf('libft', path, Mock(), None)
            ignore.unlink()
            ignore.symlink_to(target)
            with self.assertRaises(OSError):
                ensure_pdf_gitignore(root)
            self.assertEqual(target.read_bytes(), b'%PDF-1.7')

    def test_bad_provider_fingerprint_is_rejected(self):
        api = Mock()
        api.request.return_value = {'sha256': '0' * 64, 'pdf_base64': base64.b64encode(b'%PDF-1.7').decode()}
        with self.assertRaises(ValueError):
            HttpProjectProvider(api).get_subject_reference_sha256('libft')

    def test_periodic_worker_updates_file_and_persisted_reference(self):
        from types import SimpleNamespace
        from ft_tui.db.database import make_session_factory
        from ft_tui.db.models import Project
        from ft_tui.features.projects.views.details import ProjectDetailsMixin
        pdf = b'%PDF-1.7\nupdated subject'
        digest = hashlib.sha256(pdf).hexdigest()
        api = Mock()
        api.request.return_value = {'sha256': digest, 'pdf_base64': base64.b64encode(pdf).decode()}
        factory = make_session_factory('sqlite:///:memory:')
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'subject.pdf').write_bytes(b'%PDF-1.4\nold subject')
                with factory() as session:
                    project = Project(slug='libft', name='Libft', local_path=directory)
                    session.add(project)
                    session.commit()
                    project_id = project.id
                report = Mock()
                worker = SimpleNamespace(session_factory=factory, provider=HttpProjectProvider(api),
                                         subject_check_interval_seconds=21600,
                                         call_from_thread=lambda callback, *args: callback(*args),
                                         _report_automatic_subject_checks=report,
                                         _report_subject_worker_state=Mock())
                ready = api.request.return_value
                api.request.return_value = {'status': 'pending', 'sha256': None, 'pdf_base64': None}
                ProjectDetailsMixin._check_due_subjects_in_background(worker)
                worker._report_subject_worker_state.assert_called_once_with('libft', 'pending')
                self.assertEqual((root / 'subject.pdf').read_bytes(), b'%PDF-1.4\nold subject')
                with factory() as session:
                    self.assertIsNone(session.get(Project, project_id).subject_checked_at)
                api.request.return_value = ready
                api.request.reset_mock()
                ProjectDetailsMixin._check_due_subjects_in_background(worker)
                self.assertEqual((root / 'subject.pdf').read_bytes(), pdf)
                self.assertIn('*.pdf', (root / '.gitignore').read_text())
                self.assertEqual(report.call_args.args[1], [])
                with factory() as session:
                    saved = session.get(Project, project_id)
                    self.assertEqual(saved.subject_pdf_sha256, digest)
                    self.assertEqual(saved.subject_reference_sha256, digest)
                    self.assertIsNotNone(saved.subject_checked_at)
                ProjectDetailsMixin._check_due_subjects_in_background(worker)
                api.request.assert_called_once()
                # A recent database hash must not suppress recovery of a deleted PDF.
                (root / 'subject.pdf').unlink()
                ProjectDetailsMixin._check_due_subjects_in_background(worker)
                self.assertEqual((root / 'subject.pdf').read_bytes(), pdf)
                self.assertEqual(api.request.call_count, 2)
        finally:
            factory.kw['bind'].dispose()

    def test_subject_slug_accepts_underscores_and_rejects_path_characters(self):
        api = Mock()
        api.request.return_value = {'sha256': None, 'pdf_base64': None}
        provider = HttpProjectProvider(api)
        self.assertIsNone(provider.get_subject_reference_sha256('ft_printf'))
        api.request.assert_called_once_with('GET', '/v1/me/subjects/ft_printf')
        for slug in ('../ft_printf', 'ft/printf', 'ft_printf?x=1', 'ft_printf#x'):
            with self.assertRaises(ValueError):
                provider.get_subject_reference_sha256(slug)

    def test_subject_http_errors_include_safe_backend_rejection_code(self):
        import httpx
        from ft_tui.api.oauth_client import _decode_response
        for code in ('invalid_project_slug', 'invalid_upstream_resource'):
            response = httpx.Response(400, json={'error': code}, request=httpx.Request(
                'GET', 'https://api.example/v1/me/subjects/42cursus-ft_printf'))
            with self.assertRaisesRegex(httpx.HTTPStatusError, code):
                _decode_response(response)

    def test_attachment_permission_denial_explains_why_download_is_blocked(self):
        import httpx
        api = Mock()
        request = httpx.Request('GET', 'https://api.example/v1/me/subjects/42cursus-ft_printf')
        response = httpx.Response(403, json={'error': 'subject_permission_denied'}, request=request)
        api.request.side_effect = httpx.HTTPStatusError('forbidden', request=request, response=response)
        with self.assertRaisesRegex(ValueError, '42 denied access to subject attachments'):
            HttpProjectProvider(api).get_subject_reference_sha256('42cursus-ft_printf')

    def test_queued_subject_does_not_clear_local_file_or_record_a_successful_check(self):
        from ft_tui.api.http_client import SubjectPendingError
        api = Mock()
        provider = HttpProjectProvider(api)
        for value in ({'status': 'pending', 'sha256': None, 'pdf_base64': None},
                      {'status': 'unavailable', 'sha256': None, 'pdf_base64': None,
                       'reason': 'subject_link_not_found'}):
            api.request.return_value = value
            with self.assertRaises(SubjectPendingError):
                provider.get_subject_reference_sha256('42cursus-ft_printf')
