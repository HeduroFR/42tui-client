"""Opt-in real container build/run on deliberately incomplete synthetic C projects.

Run from the repository root with a working Docker engine and installed package:
python tests/manual/supra_tester_smoke.py ft_printf  # or libft
No personal projects/accounts are used. A zero exit cannot establish passing tests.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from ft_tui.features.projects.adapters.tester_catalog import load_catalog
from ft_tui.features.projects.adapters.tester_docker import TesterDocker
from ft_tui.features.projects.adapters.tester_terminal import WorkspaceSession

slug = sys.argv[1]
identifier = {"ft_printf": "supra-printf", "libft": "supra-libft"}[slug]
fixture = {"ft_printf": "ft_printf space, 'quoted'", "libft": "libft space, 'quoted'"}[slug]
with TemporaryDirectory(prefix="42tui-supra-") as directory:
    root = Path(directory)
    project = root / fixture
    shutil.copytree(Path(__file__).parent / "fixtures" / fixture, project)
    before = {p.name: p.read_bytes() for p in project.iterdir()}
    tester = next(t for t in load_catalog(root / "absent").testers if t.id == identifier)
    service = TesterDocker(root / "testers")
    log_path = Path(f"{identifier}-smoke.log").resolve()
    with log_path.open("wb") as log, service.operation():
        result = service.prepare_and_run(tester, str(project), WorkspaceSession(log, lambda data: None))
    assert {p.name: p.read_bytes() for p in project.iterdir()} == before
    text = log_path.read_text(errors="replace")
    assert "Forbidden" in text, text[-3000:]
    if slug == "libft":
        assert "ft_isdigit not found" in text, text[-3000:]
    else:
        assert "vprintf" in text, text[-3000:]
    assert result.status == "unknown" and result.exit_code == 0, result
    image = service.image(tester)
    size = subprocess.check_output([service.docker(), "image", "inspect", image, "--format", "{{.Size}}"], text=True).strip()
    print(json.dumps({"tester": identifier, "exit_code": result.exit_code, "status": result.status,
                      "image": image, "bytes": int(size), "source_preserved": True}))
