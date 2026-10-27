"""Read-only Git hygiene inspection for a configured local project."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitSnapshot:
    """Small, presentation-ready summary of a local Git working tree."""

    branch: str | None = None
    staged: int = 0
    changed: int = 0
    untracked: int = 0
    sensitive_files: tuple[str, ...] = ()
    error: str | None = None

    @property
    def dirty_count(self) -> int:
        return self.staged + self.changed + self.untracked


_SENSITIVE_NAMES = {".npmrc", ".pypirc", "id_rsa", "id_ed25519"}


def _is_sensitive(path: str) -> bool:
    name = Path(path).name.casefold()
    return (
        name in _SENSITIVE_NAMES
        or name == ".env"
        or name.startswith(".env.")
        or name.endswith((".pem", ".p12", ".pfx", ".key"))
    )


def inspect_repository(path: str | Path, *, timeout: float = 2.0) -> GitSnapshot:
    """Inspect branch, working-tree counts and sensitive-looking filenames.

    This function only invokes read-only Git commands and never reads file contents.
    """
    root = Path(path).expanduser()
    if not root.is_dir():
        return GitSnapshot(error="Project folder does not exist")

    def git(*args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ("git", "-C", str(root), *args),
            check=False,
            capture_output=True,
            timeout=timeout,
        )

    try:
        status_result = git("status", "--porcelain=v1", "--branch", "--untracked-files=all")
        files_result = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
        if status_result.returncode:
            return GitSnapshot(error="Not a Git repository")
        if files_result.returncode:
            return GitSnapshot(error="Git could not read repository files")

        staged = changed = untracked = 0
        status_lines = status_result.stdout.decode("utf-8", errors="replace").splitlines()
        branch_line = next((line for line in status_lines if line.startswith("## ")), "")
        branch = branch_line[3:].split("...", maxsplit=1)[0] or "(detached HEAD)"
        for line in status_lines:
            if line.startswith("## "):
                continue
            if line.startswith("??"):
                untracked += 1
                continue
            index_status, worktree_status = line[:2]
            if index_status != " " and index_status != "?":
                staged += 1
            if worktree_status != " " and worktree_status != "?":
                changed += 1

        filenames = set(files_result.stdout.decode("utf-8", errors="replace").split("\0"))
        # Include root-level secrets even when excluded by .gitignore.
        for child in root.iterdir():
            if child.is_file() and _is_sensitive(child.name):
                filenames.add(child.name)
        sensitive = tuple(sorted(name for name in filenames if name and _is_sensitive(name)))
        return GitSnapshot(branch, staged, changed, untracked, sensitive)
    except FileNotFoundError:
        return GitSnapshot(error="Git is not installed or is not on PATH")
    except subprocess.TimeoutExpired:
        return GitSnapshot(error="Git inspection timed out")
    except OSError:
        return GitSnapshot(error="Could not access the project repository")
