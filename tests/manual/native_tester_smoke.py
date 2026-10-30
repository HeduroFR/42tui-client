"""Opt-in pinned upstream default suite; network/Git/make/C compiler required.

Uses an intentionally incorrect C fixture. A rejected run proves failure handling,
not correctness of the fixture or upstream memory checks. No real project is used.
Run from the repository root: python tests/manual/native_tester_smoke.py
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import re

from ft_tui.features.projects.adapters.tester_catalog import load_catalog
from ft_tui.features.projects.adapters.tester_native import run_native
from ft_tui.features.projects.adapters.tester_terminal import WorkspaceSession

with TemporaryDirectory(prefix="42tui native 'quoted' ") as directory:
    root = Path(directory)
    project = root / "push_swap"
    shutil.copytree(Path(__file__).parent / "fixtures/push_swap", project)
    before = {p.name: p.read_bytes() for p in project.iterdir()}
    tester = load_catalog(root / "absent").for_project("push_swap")[0]
    log_path = Path("native-tester-smoke.log").resolve()
    with log_path.open("wb") as log:
        result = run_native(tester, str(project), WorkspaceSession(log, lambda data: None))
    # Upstream's default main returns zero even when its printed suites fail.
    assert result.status == "unknown" and result.exit_code == 0, result
    transcript = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", log_path.read_text())
    assert "BASIC FAILURE(S)" in transcript
    rows = re.findall(r"(?m)^(?:100|500)\s*\|[^\n]+\|\s*100\s*\|\s*0\s*$", transcript)
    assert len(rows) == 8, "Expected all eight performance groups to reject the fixture"
    assert {p.name: p.read_bytes() for p in project.iterdir()} == before
    print(f"Default suite failures remain unverified despite exit zero; original preserved: {result}")
    print(f"Review the transcript, including memory tooling: {log_path}")
