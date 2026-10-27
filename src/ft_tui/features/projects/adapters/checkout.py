"""Safe creation and configuration of a project's local Git checkout."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ft_tui.features.projects.subjects.adapters.files import ensure_pdf_gitignore


@dataclass(frozen=True)
class CheckoutResult:
    """Summary of a checkout setup operation."""

    path: Path
    created_repository: bool
    cloned_development_remote: bool
    created_branches: tuple[str, ...]
    configured_remotes: tuple[str, ...]
    message: str


class CheckoutSetupError(RuntimeError):
    """Raised when setup would be unsafe or Git cannot complete an operation."""


def setup_project_checkout(
    path: str | Path,
    *,
    dev_remote_url: str | None = None,
    vogsphere_url: str | None = None,
    timeout: float = 60.0,
) -> CheckoutResult:
    """Create or safely configure a checkout without overwriting existing files.

    A development remote is cloned into a missing or empty directory. Existing Git
    repositories are preserved; conflicting remote URLs cause a clear error. The
    local ``dev`` and ``master`` branches are created from the checkout HEAD when a
    commit exists. For a newly initialized empty repository, ``master`` is deferred
    until the first commit because Git does not store unborn branch refs.
    """
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise CheckoutSetupError("Project path must be absolute.")
    target = target.resolve(strict=False)
    if target.exists() and not target.is_dir():
        raise CheckoutSetupError("The project path exists and is not a directory.")

    cloned = False
    created_repository = False
    created_branches: list[str] = []
    configured_remotes: list[str] = []

    def git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                ("git", *args),
                cwd=cwd or target,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as error:
            raise CheckoutSetupError("Git is not installed or is not on PATH.") from error
        except subprocess.TimeoutExpired as error:
            raise CheckoutSetupError("Git checkout setup timed out.") from error

    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)

    repository_root = git("rev-parse", "--show-toplevel") if target.exists() else None
    is_repository = (
        repository_root is not None
        and repository_root.returncode == 0
        and Path(repository_root.stdout.strip()).resolve(strict=False) == target
    )
    if not is_repository and target.exists() and any(target.iterdir()):
        raise CheckoutSetupError(
            "The selected folder is not empty and is not a Git repository. Choose an empty folder."
        )

    if not is_repository and dev_remote_url:
        result = git("clone", "--origin", "origin", dev_remote_url, str(target), cwd=target.parent)
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
            raise CheckoutSetupError(f"Could not clone the development remote: {detail}")
        cloned = True
        is_repository = True

    if not is_repository:
        target.mkdir(parents=True, exist_ok=True)
        result = git("init", "--initial-branch=dev")
        if result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
            raise CheckoutSetupError(f"Could not initialize the Git repository: {detail}")
        created_repository = True
        created_branches.append("dev")

    def configure_remote(name: str, url: str | None) -> None:
        if not url:
            return
        existing = git("remote", "get-url", name)
        if existing.returncode == 0:
            if existing.stdout.strip() != url:
                raise CheckoutSetupError(
                    f"Remote '{name}' already points to a different URL; update it manually first."
                )
            return
        added = git("remote", "add", name, url)
        if added.returncode:
            detail = added.stderr.strip() or "unknown Git error"
            raise CheckoutSetupError(f"Could not configure remote '{name}': {detail}")
        configured_remotes.append(name)

    def configure_branch_upstream(branch: str, remote: str, remote_branch: str) -> None:
        expected = {"remote": remote, "merge": f"refs/heads/{remote_branch}"}
        for setting, value in expected.items():
            key = f"branch.{branch}.{setting}"
            existing = git("config", "--get", key)
            if existing.returncode == 0 and existing.stdout.strip() != value:
                raise CheckoutSetupError(
                    f"Branch '{branch}' already tracks a different upstream; update it manually first."
                )
            configured = git("config", key, value)
            if configured.returncode:
                detail = configured.stderr.strip() or "unknown Git error"
                raise CheckoutSetupError(f"Could not configure upstream for '{branch}': {detail}")

    configure_remote("origin", dev_remote_url)
    configure_remote("vogsphere", vogsphere_url)

    has_commit = git("rev-parse", "--verify", "HEAD").returncode == 0
    if has_commit:
        current_branch_result = git("branch", "--show-current")
        current_branch = current_branch_result.stdout.strip()
        for branch in ("dev", "master"):
            exists = git("show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
            if exists.returncode == 0:
                continue
            base = current_branch or "HEAD"
            created = git("branch", branch, base)
            if created.returncode:
                detail = created.stderr.strip() or "unknown Git error"
                raise CheckoutSetupError(f"Could not create branch '{branch}': {detail}")
            created_branches.append(branch)
        # Make dev the working branch for a fresh clone/new branch setup. Existing
        # repositories stay on their current branch to avoid disrupting the user.
        if cloned and current_branch != "dev":
            switched = git("switch", "dev")
            if switched.returncode:
                detail = switched.stderr.strip() or "unknown Git error"
                raise CheckoutSetupError(f"Could not switch to branch 'dev': {detail}")

    if dev_remote_url:
        configure_branch_upstream("dev", "origin", "dev")
    if vogsphere_url:
        # Vogsphere accepts submissions only on master; configure its upstream
        # without fetching or pushing the official remote during setup.
        configure_branch_upstream("master", "vogsphere", "master")

    try:
        gitignore_changed = ensure_pdf_gitignore(target)
    except OSError as error:
        raise CheckoutSetupError(f"Could not protect project subject PDFs in .gitignore: {error}") from error

    notes: list[str] = []
    if cloned:
        notes.append("cloned the development remote")
    elif created_repository:
        notes.append("initialized an empty local repository")
    else:
        notes.append("kept the existing repository intact")
    if has_commit:
        notes.append("ensured local dev and master branches")
    else:
        notes.append("run setup again after the first commit to create master")
    if configured_remotes:
        notes.append("configured " + ", ".join(configured_remotes))
    if gitignore_changed:
        notes.append("added *.pdf to .gitignore")

    return CheckoutResult(
        path=target,
        created_repository=created_repository,
        cloned_development_remote=cloned,
        created_branches=tuple(created_branches),
        configured_remotes=tuple(configured_remotes),
        message="; ".join(notes) + ".",
    )
