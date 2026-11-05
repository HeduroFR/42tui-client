"""Opt-in Docker integration check using a disposable get_next_line fixture."""
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from ft_tui.features.projects.adapters.tester_catalog import load_catalog
from ft_tui.features.projects.adapters.tester_docker import TesterDocker
from ft_tui.features.projects.adapters.tester_terminal import WorkspaceSession


def snapshot(project):
    return {str(path.relative_to(project)): path.read_bytes() for path in project.rglob('*') if path.is_file()}


with TemporaryDirectory(prefix="42tui-gnl-smoke-") as directory:
    root = Path(directory)
    project = root / "project with spaces"
    shutil.copytree(Path(__file__).parent / "fixtures/get_next_line space", project)
    before = snapshot(project)
    tester = next(t for t in load_catalog(root / "absent").testers if t.id == "tripouille-gnl")
    service = TesterDocker(root / "testers")
    with (root / "transcript.log").open("wb") as log, service.operation():
        result = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
    assert result.status == "passed" and result.summary.total == 222, result
    assert result.summary.failed == result.summary.errors == 0, result
    assert snapshot(project) == before
    print(json.dumps({"status": result.status, "counts": vars(result.summary), "source_preserved": True}))
    for layout in ('root', 'bonus'):
        bonus = project if layout == 'root' else project / 'bonus'
        bonus.mkdir(exist_ok=True)
        for name in ('get_next_line.c', 'get_next_line_utils.c', 'get_next_line.h'):
            target = name.replace('.c', '_bonus.c').replace('.h', '_bonus.h')
            (bonus / target).write_text((project / name).read_text().replace('get_next_line.h', 'get_next_line_bonus.h'))
        before = snapshot(project)
        with (root / f'{layout}.log').open('wb') as log, service.operation():
            combined = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
        assert combined.status == 'passed' and combined.summary.total == 501, combined
        assert combined.summary.failed == combined.summary.errors == 0, combined
        assert snapshot(project) == before
        assert 'Detected bonus sources' in (root / f'{layout}.log').read_text(errors='replace')
        print(json.dumps({'layout': layout, 'status': combined.status, 'counts': vars(combined.summary), 'source_preserved': True}))
        if layout == 'root':
            for path in project.glob('*_bonus.*'):
                path.unlink()
    bonus_source = project / 'bonus/get_next_line_bonus.c'
    for name, body in (('bonus-failure', 'char *p=malloc(2); if(p){p[0]=120;p[1]=0;} return p;'), ('bonus-early', '_exit(0);'),
                       ('bonus-timeout', 'while (1) {}'), ('bonus-crash', 'abort();')):
        bonus_source.write_text('#include "get_next_line_bonus.h"\nchar *get_next_line(int fd) { (void)fd; ' + body + ' }\n')
        before = snapshot(project)
        with (root / f'{name}.log').open('wb') as log, service.operation():
            failed_bonus = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
        assert failed_bonus.status == 'failed', failed_bonus
        count = failed_bonus.summary.failed if name == 'bonus-failure' else failed_bonus.summary.errors
        assert count > 0, failed_bonus
        assert snapshot(project) == before
        print(json.dumps({'case': name, 'status': failed_bonus.status, 'counts': vars(failed_bonus.summary), 'source_preserved': True}))
    (project / 'bonus/get_next_line_utils_bonus.c').unlink()
    before = snapshot(project)
    with (root / 'bonus-missing.log').open('wb') as log, service.operation():
        missing = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
    assert missing.status == 'unreadable' and missing.summary is None and missing.exit_code != 0, missing
    assert snapshot(project) == before
    print(json.dumps({'case': 'bonus-missing', 'status': missing.status, 'source_preserved': True}))
    shutil.rmtree(project / 'bonus')
    (project / "get_next_line.c").write_text(
        '#include "get_next_line.h"\nchar *get_next_line(int fd) { char *p; (void)fd; '
        'p=malloc(2); if(p){p[0]=120;p[1]=0;} return p; }\n')
    before = snapshot(project)
    with (root / "failure.log").open("wb") as log, service.operation():
        failed = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
    assert failed.status == "failed" and failed.summary.failed > 0, failed
    assert snapshot(project) == before
    print(json.dumps({"status": failed.status, "counts": vars(failed.summary), "source_preserved": True}))
    (project / "get_next_line.c").write_text(
        '#include "get_next_line.h"\nchar *get_next_line(int fd) { (void)fd; _exit(0); }\n')
    before = snapshot(project)
    with (root / "early.log").open("wb") as log, service.operation():
        early = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
    assert early.status == "failed" and early.summary.errors > 0, early
    assert snapshot(project) == before
    print(json.dumps({"status": early.status, "counts": vars(early.summary), "source_preserved": True}))
