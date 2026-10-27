import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Input, Select


class ProjectFuzzySearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_project_search_handles_abbreviations_typos_and_separators(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "search.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true'})
                session.add_all([Project(slug=slug, name=name, local_path=directory, setup_status='unknown')
                    for slug, name in [('libft', 'Libft'), ('push-swap', 'push_swap'), ('pipex', 'Pipex')]])
                session.commit()
            app = FortyTwoTuiApp(factory, None)
            try:
                async with app.run_test(size=(120, 40)) as pilot:
                    app.query_one('#project-view', Select).value = 'active'
                    await pilot.pause()
                    search = app.query_one('#project-search', Input)
                    for query in ['pswp', 'puhs swap', 'SWAP PUSH']:
                        search.value = query; await pilot.pause()
                        self.assertEqual([p.slug for p in app._visible_projects()], ['push-swap'])
                    search.value = 'zzzzz'; await pilot.pause()
                    self.assertEqual(app._visible_projects(), [])
                    search.value = ''; await pilot.pause()
                    self.assertEqual(len(app._visible_projects()), 3)
            finally:
                factory.kw['bind'].dispose()
