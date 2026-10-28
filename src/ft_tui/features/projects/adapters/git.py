"""Git hygiene inspection and conservative publishing for configured projects."""

from __future__ import annotations

import subprocess
import os
import re
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path


class ProjectGitError(RuntimeError):
    """A Git operation cannot safely proceed."""


def _safe_detail(value: str) -> str:
    # Credentials and query tokens must not reach notifications or CLI output.
    return re.sub(r"([a-zA-Z][\w+.-]*://)[^\s]+", lambda match: _display_url(match[0]), value)


def _display_url(value: str) -> str:
    if "://" not in value:
        return value
    scheme, address = value.split("://", 1)
    address = address.split("?", 1)[0].split("#", 1)[0]
    authority, separator, path = address.partition("/")
    return scheme + "://" + authority.rsplit("@", 1)[-1] + separator + path


def _run_git(root: Path, *args: str, timeout: float = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ("git", "-C", str(root), *args), check=False, capture_output=True,
            text=True, timeout=timeout, env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except FileNotFoundError as error:
        raise ProjectGitError("Git is not installed or is not on PATH.") from error
    except subprocess.TimeoutExpired as error:
        raise ProjectGitError("Git operation timed out; check the remote before retrying.") from error
    except OSError as error:
        raise ProjectGitError("Could not access the project repository.") from error


def _checked_git(root: Path, *args: str, timeout: float = 60) -> str:
    result = _run_git(root, *args, timeout=timeout)
    if result.returncode:
        raise ProjectGitError(_safe_detail(result.stderr.strip() or "Git operation failed."))
    return result.stdout.strip()


def _repository_path(path: str | Path, timeout: float) -> Path:
    root = Path(path).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ProjectGitError("Project folder must be an existing absolute directory.")
    root = root.resolve()
    actual = _run_git(root, "rev-parse", "--show-toplevel", timeout=timeout)
    if actual.returncode or Path(actual.stdout.strip()).resolve() != root:
        raise ProjectGitError("Project folder must be the root of a Git checkout.")
    return root


def _committed_head(root: Path, timeout: float) -> tuple[str, str]:
    branch = _run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD", timeout=timeout)
    if branch.returncode:
        raise ProjectGitError("Detached HEAD: switch to a branch before publishing.")
    commit = _run_git(root, "rev-parse", "--verify", "HEAD^{commit}", timeout=timeout)
    if commit.returncode:
        raise ProjectGitError("No committed HEAD: create a commit before publishing.")
    if _checked_git(root, "ls-files", "--unmerged", timeout=timeout):
        raise ProjectGitError("Resolve the repository's merge conflicts before publishing.")
    return branch.stdout.strip(), commit.stdout.strip()


@dataclass(frozen=True)
class PushTarget:
    destination: str
    remote: str
    url: str
    branch: str
    error: str | None = None
    url_fingerprint: str = field(default="", repr=False)


@dataclass(frozen=True)
class PushPlan:
    path: Path
    branch: str
    commit: str
    dirty_count: int
    targets: tuple[PushTarget, ...]


@dataclass(frozen=True)
class PushResult:
    target: PushTarget
    success: bool
    message: str


def _remote_url(root: Path, remote: str, expected: str | None, timeout: float) -> str:
    fetch = _run_git(root, "remote", "get-url", "--all", remote, timeout=timeout)
    push = _run_git(root, "remote", "get-url", "--push", "--all", remote, timeout=timeout)
    urls = fetch.stdout.strip().splitlines()
    if fetch.returncode or push.returncode or not urls:
        raise ProjectGitError(f"Remote '{remote}' is not configured; run project checkout setup first.")
    if len(urls) != 1 or push.stdout.strip().splitlines() != urls:
        raise ProjectGitError(f"Remote '{remote}' has ambiguous fetch/push URLs; resolve them manually.")
    if expected and urls[0] != expected:
        raise ProjectGitError(f"Remote '{remote}' points to a different URL; resolve it manually.")
    return urls[0]


def plan_project_push(
    path: str | Path, destination: str = "all", *, dev_remote_url: str | None = None,
    vogsphere_url: str | None = None, timeout: float = 60,
) -> PushPlan:
    """Review the committed HEAD and explicit destinations without changing files."""
    if destination not in {"dev", "vog", "all"}:
        raise ProjectGitError("Choose a push destination: dev, vog or all.")
    root = _repository_path(path, timeout)
    branch, commit = _committed_head(root, timeout)
    status = _checked_git(root, "status", "--porcelain=v1", "--untracked-files=all", "-z", timeout=timeout)
    targets = []
    for name, remote, remote_branch, expected in (
        ("dev", "origin", branch, dev_remote_url), ("vog", "vogsphere", "master", vogsphere_url),
    ):
        if destination not in {name, "all"}:
            continue
        try:
            url = _remote_url(root, remote, expected, timeout)
            target = PushTarget(name, remote, _display_url(url), remote_branch,
                                url_fingerprint=sha256(url.encode()).hexdigest())
        except ProjectGitError as error:
            target = PushTarget(name, remote, "", remote_branch, str(error))
        targets.append(target)
    # Rename records include a second NUL-delimited filename.
    records = status.split("\0") if status else []
    count = index = 0
    while index < len(records):
        if records[index]:
            count += 1
            index += int("R" in records[index][:2] or "C" in records[index][:2])
        index += 1
    return PushPlan(root, branch, commit, count, tuple(targets))


def push_project(plan: PushPlan, *, timeout: float = 60) -> tuple[PushResult, ...]:
    """Publish only the reviewed commit, independently per destination, without force."""
    outcomes = []
    for target in plan.targets:
        try:
            if target.error:
                raise ProjectGitError(target.error)
            root = _repository_path(plan.path, timeout)
            if _committed_head(root, timeout) != (plan.branch, plan.commit):
                raise ProjectGitError("Branch or HEAD changed since review; review the push again.")
            url = _remote_url(root, target.remote, None, timeout)
            if sha256(url.encode()).hexdigest() != target.url_fingerprint:
                raise ProjectGitError("Remote changed since review; review the push again.")
            _checked_git(root, "-c", "push.followTags=false", "-c", "push.recurseSubmodules=no",
                         "-c", f"remote.{target.remote}.mirror=false", "push", "--porcelain",
                         "--", target.remote, f"{plan.commit}:refs/heads/{target.branch}", timeout=timeout)
            outcomes.append(PushResult(target, True, f"Published committed HEAD {plan.commit[:12]} to {target.remote}/{target.branch}."))
        except ProjectGitError as error:
            outcomes.append(PushResult(target, False, str(error)))
    return tuple(outcomes)


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
