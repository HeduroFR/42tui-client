"""Project details prioritize overview and workspace over diagnostics."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from textual.widgets import Static, TabbedContent
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.services.user_settings import save_settings
from ft_tui.ui.app import FortyTwoTuiApp


class ProjectDetailsLayoutTests(unittest.IsolatedAsyncioTestCase):
    async def test_checkout_completion_refreshes_editor_without_changing_view(self):
        from ft_tui.services.project_checkout import CheckoutResult

        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "checkout.sqlite"}')
            folder = Path(directory) / 'libft'
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
                session.add(Project(slug='libft', name='Libft', local_path=str(folder)))
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 50)) as pilot:
                    app.query_one(TabbedContent).active = 'projects-tab'
                    await pilot.pause()
                    project = next(iter(app.projects.values()))
                    app._show_project(project)
                    self.assertTrue(app.query_one('#open-project-editor').disabled)
                    folder.mkdir()
                    result = CheckoutResult(folder, True, False, (), (), 'Ready')
                    app._report_checkout_setup(project.name, result,
                                               project.ui_key, str(folder))
                    await pilot.pause()
                    self.assertEqual(app.selected_project_key, project.ui_key)
                    self.assertFalse(app.query_one('#open-project-editor').disabled)
            finally:
                factory.kw['bind'].dispose()

    async def test_git_inspection_requires_development_remote(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from ft_tui.ui.project_details import ProjectDetailsMixin

        project = Project(id=1, slug='libft', name='Libft', local_path='/workspace/libft')
        app = SimpleNamespace(selected_project_key=project.ui_key,
                              projects={project.ui_key: project},
                              _render_project_details=Mock(), notify=Mock())
        with patch('ft_tui.ui.project_details.inspect_repository') as inspect:
            for remote in (None, '', '   '):
                project.dev_repo_url = remote
                await ProjectDetailsMixin._inspect_project_git_status(app, project.ui_key, project.local_path)
            inspect.assert_not_called()
            app._render_project_details.assert_not_called()
            project.dev_repo_url = 'git@example.com:student/libft.git'
            await ProjectDetailsMixin._inspect_project_git_status(app, project.ui_key, project.local_path)
            inspect.assert_called_once_with(project.local_path)
            app._render_project_details.assert_called_once_with(project, inspect.return_value)

    async def test_overview_hides_diagnostics_and_details_remain_accessible(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "details.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
                session.add(Project(slug='libft', name='Libft', setup_status='unknown'))
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(160, 50)) as pilot:
                    app.query_one(TabbedContent).active = 'projects-tab'
                    await pilot.pause()
                    project = next(iter(app.projects.values()))
                    project._catalog_data = {'rank': 0, 'xp': 462, 'duration': '70 hours',
                                             'description': 'Build your C library.', 'snapshot_id': 'secret-snapshot',
                                             'clauses': [{'status': 'recognized', 'modality': 'required',
                                                          'expression': {'op': 'predicate', 'ref': '42cursus-libft',
                                                                         'action': 'validated', 'target': 'project'}}]}
                    app.selected_project_key = project.ui_key
                    app._render_project_details(project)
                    app._update_editor_button()
                    self.assertEqual(str(app.query_one("#open-project-editor").label), "Open editor")
                    overview = str(app.query_one('#details-content', Static).render())
                    self.assertIn('Build your C library.', overview)
                    self.assertNotIn('Libft completed', overview)
                    self.assertNotIn('Snapshot', overview)
                    self.assertNotIn('Classification', overview)
                    self.assertNotIn('Local path', overview)
                    await pilot.pause()
                    self.assertGreater(app.query_one('#project-workspace').region.x,
                                       app.query_one('#project-overview').region.x)
                    self.assertGreaterEqual(app.query_one('#project-notes-empty').region.y,
                                            app.query_one('#notes-title').region.bottom)
                    await pilot.press('d')
                    await pilot.pause()
                    self.assertIn('secret-snapshot', str(app.screen.query_one('#technical-content', Static).render()))
                    await pilot.press('escape')
                    await pilot.resize_terminal(80, 40)
                    await pilot.pause()
                    self.assertGreaterEqual(app.query_one('#project-workspace').region.y,
                                            app.query_one('#project-overview').region.bottom)
            finally:
                factory.kw['bind'].dispose()
