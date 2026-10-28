"""Recover project history without replacing existing files or local branches."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess

from ft_tui.features.projects.subjects.adapters.files import ensure_pdf_gitignore
from .git import ProjectGitError, _checked_git, _run_git, _repository_path


@dataclass(frozen=True)
class CheckoutResult:
    path: Path
    created_repository: bool
    cloned_development_remote: bool
    created_branches: tuple[str, ...]
    configured_remotes: tuple[str, ...]
    message: str
    cloned_vogsphere_remote: bool = False
    warnings: tuple[str, ...] = ()


class CheckoutSetupError(ProjectGitError):
    """Recovery needs manual attention or Git could not finish."""


_VOGSPHERE_WARNING = (
    "Vogsphere could not be checked. Connect to the 42 campus network to recover remote work. "
    "Opening the existing local checkout."
)


def _remote_access_failure(error: ProjectGitError) -> bool:
    detail = str(error).casefold()
    return isinstance(error.__cause__, subprocess.TimeoutExpired) or (
        "unable to access" in detail and "://" in detail
    ) or any(
        text in detail for text in (
            "could not resolve", "couldn't resolve", "could not read from remote repository",
            "connection refused", "connection timed out", "connection reset", "network is unreachable",
            "no route to host", "permission denied (publickey", "authentication failed", "could not read username",
            "does not appear to be a git repository", "repository not found",
        )
    )


def setup_project_checkout(
    path: str | Path, *, dev_remote_url: str | None = None,
    vogsphere_url: str | None = None, timeout: float = 60.0,
) -> CheckoutResult:
    """Clone Vogsphere work first; fetch and inspect existing checkouts only.

    Remote commits missing locally require explicit reconciliation. Setup never
    stages, commits, merges, resets, or changes an existing checkout's branch.
    """
    try:
        return _setup(path, dev_remote_url, vogsphere_url, timeout)
    except ProjectGitError as error:
        raise CheckoutSetupError(str(error)) from error
    except OSError as error:
        raise CheckoutSetupError("Could not access the project folder.") from error


def _setup(path: str | Path, dev_url: str | None, vog_url: str | None, timeout: float) -> CheckoutResult:
    target = Path(path).expanduser()
    if not target.is_absolute():
        raise CheckoutSetupError("Project path must be absolute.")
    target = target.resolve(strict=False)
    if target.exists() and not target.is_dir():
        raise CheckoutSetupError("The project path exists and is not a directory.")
    existing = False
    if target.is_dir():
        try:
            _repository_path(target, timeout)
            existing = True
        except ProjectGitError:
            if any(target.iterdir()):
                raise CheckoutSetupError("The selected folder is not empty and is not a Git repository. Choose an empty folder.")
    target.parent.mkdir(parents=True, exist_ok=True)

    def git(*args):
        return _checked_git(target if target.exists() else target.parent, *args, timeout=timeout)

    committed_existing = existing and _run_git(
        target, "rev-parse", "--verify", "HEAD^{commit}", timeout=timeout,
    ).returncode == 0
    warnings = []

    def inspect_remote(remote, *args):
        try:
            return git(*args)
        except ProjectGitError as error:
            if remote != "vogsphere" or not committed_existing or not _remote_access_failure(error):
                raise
            warnings.append(_VOGSPHERE_WARNING)
            return None

    configured = []
    remotes = []
    # Validate all existing URL settings before adding or fetching any remote.
    for remote, expected in (("origin", dev_url), ("vogsphere", vog_url)):
        result = _run_git(target, "remote", "get-url", "--all", remote, timeout=timeout) if existing else None
        urls = result.stdout.strip().splitlines() if result and result.returncode == 0 else []
        if urls and (len(urls) != 1 or expected and urls != [expected]):
            raise CheckoutSetupError(f"Remote '{remote}' already points to a different or ambiguous URL; update it manually first.")
        url = expected or (urls[0] if urls else None)
        if url:
            remotes.append((remote, url))

    heads = {}
    defaults = {}
    for remote, url in remotes:
        output = inspect_remote(remote, "ls-remote", "--symref", "--", url, "HEAD", "refs/heads/*")
        heads[remote] = {}
        if output is None:
            continue
        for line in output.splitlines():
            value, ref = line.split("\t", 1)
            if value.startswith("ref: ") and ref == "HEAD":
                defaults[remote] = value[5:].removeprefix("refs/heads/")
            elif ref.startswith("refs/heads/"):
                heads[remote][ref.removeprefix("refs/heads/")] = value
        if remote == "vogsphere" and heads[remote] and "master" not in heads[remote]:
            raise CheckoutSetupError("Vogsphere contains branches but no master; choose the history to recover manually.")

    source = None
    if not existing:
        source = next((remote for remote in ("vogsphere", "origin") if heads.get(remote)), None)
        if source:
            branches = heads[source]
            branch = "master" if source == "vogsphere" else defaults.get(source)
            if not branch and len(branches) == 1:
                branch = next(iter(branches))
            if branch not in branches:
                raise CheckoutSetupError("The development remote has no unambiguous default branch; select it manually.")
            url = dict(remotes)[source]
            git("clone", "--origin", source, "--branch", branch, "--", url, str(target))
        else:
            target.mkdir(parents=True, exist_ok=True)
            git("init", "--initial-branch=dev")

    for remote, url in remotes:
        result = _run_git(target, "remote", "get-url", remote, timeout=timeout)
        if result.returncode:
            git("remote", "add", remote, url)
            configured.append(remote)

    current_result = _run_git(target, "symbolic-ref", "--quiet", "--short", "HEAD", timeout=timeout)
    if current_result.returncode:
        raise CheckoutSetupError("Detached HEAD: select a branch before recovering remote work.")
    current = current_result.stdout.strip()
    local = _run_git(target, "rev-parse", "--verify", "HEAD^{commit}", timeout=timeout)
    for remote, url in remotes:
        branches = heads[remote]
        if not branches:
            continue
        branch = "master" if remote == "vogsphere" else current if current in branches else defaults.get(remote)
        if branch not in branches:
            if len(branches) == 1:
                branch = next(iter(branches))
            else:
                raise CheckoutSetupError(f"Remote '{remote}' has no unambiguous recovery branch; inspect it manually.")
        fetched = inspect_remote(remote, "fetch", "--no-tags", "--no-recurse-submodules", "--refmap=",
                                 "--", remote, f"refs/heads/{branch}")
        if fetched is None:
            continue
        remote_commit = git("rev-parse", "--verify", "FETCH_HEAD^{commit}")
        if local.returncode or _run_git(target, "merge-base", "--is-ancestor", remote_commit, "HEAD", timeout=timeout).returncode:
            if remote == "origin" and not local.returncode and not _run_git(
                target, "merge-base", "--is-ancestor", "HEAD", remote_commit, timeout=timeout,
            ).returncode:
                raise CheckoutSetupError(
                    f"Development remote 'origin/{branch}' has newer commits. Preserve or commit local edits, "
                    "then fetch/pull development with --ff-only and retry. Local files and branches were preserved."
                )
            raise CheckoutSetupError(
                f"Remote '{remote}/{branch}' has commits missing from local HEAD (ahead, divergent or unrelated history). "
                "Fetched for inspection; reconcile the histories manually before opening the editor. Local files and branches were preserved."
            )

    initialized = not existing and source is None
    if initialized:
        try:
            ensure_pdf_gitignore(target)
        except OSError as error:
            raise CheckoutSetupError("Could not protect project subject PDFs in .gitignore.") from error
    message = (f"Recovered {source} committed work" if source else "Initialized an empty local repository" if initialized else "Kept the existing checkout intact")
    if remotes and not warnings:
        message += "; fetched and inspected configured remote histories"
    return CheckoutResult(target, initialized, source == "origin", ("dev",) if initialized else (),
                          tuple(configured), message + ".", source == "vogsphere", tuple(warnings))
