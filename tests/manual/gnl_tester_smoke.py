"""Opt-in Docker integration check using a disposable get_next_line fixture."""
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from ft_tui.features.projects.adapters.tester_catalog import load_catalog
from ft_tui.features.projects.adapters.tester_docker import TesterDocker
from ft_tui.features.projects.adapters.tester_terminal import WorkspaceSession

with TemporaryDirectory(prefix="42tui-gnl-smoke-") as directory:
    root = Path(directory)
    project = root / "project with spaces"
    shutil.copytree(Path(__file__).parent / "fixtures/get_next_line space", project)
    before = {path.name: path.read_bytes() for path in project.iterdir()}
    tester = next(t for t in load_catalog(root / "absent").testers if t.id == "tripouille-gnl")
    service = TesterDocker(root / "testers")
    with (root / "transcript.log").open("wb") as log, service.operation():
        result = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
    assert result.status == "passed" and result.summary.total == 222, result
    assert result.summary.failed == result.summary.errors == 0, result
    assert {path.name: path.read_bytes() for path in project.iterdir()} == before
    print(json.dumps({"status": result.status, "counts": vars(result.summary), "source_preserved": True}))
    (project / "get_next_line.c").write_text(
        '#include "get_next_line.h"\nchar *get_next_line(int fd) { char *p; (void)fd; '
        'p=malloc(2); if(p){p[0]=120;p[1]=0;} return p; }\n')
    before = {path.name: path.read_bytes() for path in project.iterdir()}
    with (root / "failure.log").open("wb") as log, service.operation():
        failed = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
    assert failed.status == "failed" and failed.summary.failed > 0, failed
    assert {path.name: path.read_bytes() for path in project.iterdir()} == before
    print(json.dumps({"status": failed.status, "counts": vars(failed.summary), "source_preserved": True}))
    (project / "get_next_line.c").write_text(
        '#include "get_next_line.h"\nchar *get_next_line(int fd) { (void)fd; _exit(0); }\n')
    before = {path.name: path.read_bytes() for path in project.iterdir()}
    with (root / "early.log").open("wb") as log, service.operation():
        early = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
    assert early.status == "failed" and early.summary.errors > 0, early
    assert {path.name: path.read_bytes() for path in project.iterdir()} == before
    print(json.dumps({"status": early.status, "counts": vars(early.summary), "source_preserved": True}))
