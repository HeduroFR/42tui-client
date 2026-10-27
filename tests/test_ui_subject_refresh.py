"""Queued subjects become usable without navigating away from the project."""
import asyncio
import hashlib
import tempfile
import unittest
from pathlib import Path

from textual.app import App
from ft_tui.ui.components import Static, Button

from ft_tui.api.http_client import SubjectPendingError
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.ui.button import AppButton
from ft_tui.ui.project_details import ProjectDetailsMixin


class SubjectRefreshTests(unittest.IsolatedAsyncioTestCase):
    async def test_queued_download_refreshes_selected_project_before_periodic_check(self):
        pdf = b'%PDF-1.7\nsubject'
        digest = hashlib.sha256(pdf).hexdigest()

        class Provider:
            ready = False

            def get_subject_reference_sha256(self, slug):
                if not self.ready:
                    raise SubjectPendingError('pending')
                return digest

            def download_subject_pdf(self, slug, destination):
                destination.write_bytes(pdf)
                return True

        class Harness(ProjectDetailsMixin, App):
            SUBJECT_PENDING_POLL_SECONDS = 0.05
            subject_check_interval_seconds = 21600
            language = 'en'

            def compose(self):
                yield Static(id='project-subject-status')
                yield Button('Open Subject', id='open-subject', disabled=True)

            def on_mount(self):
                self.set_interval(30, self._start_due_subject_checks)
                self._start_due_subject_checks()

        with tempfile.TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{directory}/test.db')
            try:
                with factory() as session:
                    project = Project(slug='libft', name='Libft', local_path=directory)
                    session.add(project)
                    session.commit()
                    project_id = project.id
                app = Harness()
                app.session_factory = factory
                app.provider = Provider()
                app.projects = {project.ui_key: project}
                app.selected_project_key = project.ui_key
                async with app.run_test() as pilot:
                    async def wait_for(predicate):
                        for _ in range(100):
                            if predicate():
                                return
                            await asyncio.sleep(0.02)
                        self.fail('Subject state did not update automatically')

                    status = app.query_one('#project-subject-status', Static)
                    await wait_for(lambda: 'QUEUED' in str(status.render()))
                    self.assertTrue(app.query_one('#open-subject', AppButton).disabled)
                    app.provider.ready = True
                    await wait_for(lambda: project.subject_pdf_sha256 == digest)
                    self.assertNotIn('QUEUED', str(status.render()))
                    self.assertFalse(app.query_one('#open-subject', AppButton).disabled)
                    self.assertEqual((Path(directory) / 'subject.pdf').read_bytes(), pdf)
                    with factory() as session:
                        self.assertEqual(session.get(Project, project_id).subject_pdf_sha256, digest)
            finally:
                factory.kw['bind'].dispose()
