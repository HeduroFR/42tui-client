"""Run representative pinned Germinette integrations against empty copies.

Run from the repository root with a working Docker engine:
python tests/manual/germinette_tester_smoke.py
Uses a synthetic project only and checks that its original files stay unchanged.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
from ft_tui.features.projects.adapters.tester_catalog import load_catalog
from ft_tui.features.projects.adapters.tester_docker import TesterDocker
from ft_tui.features.projects.adapters.tester_terminal import WorkspaceSession

with TemporaryDirectory(prefix='42tui-python-smoke-') as folder:
    root = Path(folder)
    project = root / "project space"
    project.mkdir()
    (project / 'sentinel.txt').write_text('unchanged')
    service = TesterDocker(root / 'testers')
    catalog = load_catalog(root / 'absent')
    for slug in ('python-module-05-bis', 'python-module-06-bis', 'python-module-00', 'a-maze-ing'):
        tester = catalog.for_project(slug)[0]
        with (root / (slug + '.log')).open('wb') as log, service.operation():
            result = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
        assert (project / 'sentinel.txt').read_text() == 'unchanged'
        assert sorted(p.name for p in project.iterdir()) == ['sentinel.txt']
        if slug.endswith('-bis'):
            assert result.status == 'failed' and result.summary.failed == 5, result
        else:
            assert result.status == 'failed' and result.summary.failed > 0, result
            assert result.summary.incomplete, result
        print(slug, result.status, result.exit_code, flush=True)
