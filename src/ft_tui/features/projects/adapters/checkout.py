"""Recover project history without replacing existing files or local branches."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256
import subprocess
import time

from ft_tui.features.projects.subjects.adapters.files import ensure_pdf_gitignore
from .ssh_askpass import ssh_askpass
from .git import ProjectGitError, _checked_git, _run_git, _repository_path, _remote_heads, _remote_branch


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


class CheckoutReviewRequired(CheckoutSetupError):
    """Fetched history differs; opening local files needs an explicit choice."""

    def __init__(self, message: str, path: Path, remote: str, branch: str, commit: str):
        super().__init__(message)
        self.path, self.remote, self.branch, self.commit = path, remote, branch, commit


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
    vogsphere_url: str | None = None, timeout: float = 60.0, ssh_prompt=None,
) -> CheckoutResult:
    """Clone Vogsphere work first; fetch and inspect existing checkouts only.

    Remote commits missing locally require explicit reconciliation. Setup never
    stages, commits, merges, resets, or changes an existing checkout's branch.
    """
    try:
        with ssh_askpass(ssh_prompt):
            return _setup(path, dev_remote_url, vogsphere_url, timeout)
    except CheckoutSetupError:
        raise
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
        heads[remote], defaults[remote] = _remote_heads(output)

    source = None
    if not existing:
        source = next((remote for remote in ("vogsphere", "origin") if heads.get(remote)), None)
        if source:
            branch = _remote_branch(source, heads[source], defaults.get(source))
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
        branch = _remote_branch(remote, branches, defaults.get(remote),
                                preferred=current if remote == "origin" else None)
        fetched = inspect_remote(remote, "fetch", "--no-tags", "--no-recurse-submodules", "--refmap=",
                                 "--", remote, f"refs/heads/{branch}")
        if fetched is None:
            continue
        remote_commit = git("rev-parse", "--verify", "FETCH_HEAD^{commit}")
        if local.returncode or _run_git(target, "merge-base", "--is-ancestor", remote_commit, "HEAD", timeout=timeout).returncode:
            if remote == "origin" and not local.returncode and not _run_git(
                target, "merge-base", "--is-ancestor", "HEAD", remote_commit, timeout=timeout,
            ).returncode:
                raise CheckoutReviewRequired(
                    f"Development remote 'origin/{branch}' has newer commits. Preserve or commit local edits, "
                    "then fetch/pull development with --ff-only and retry. Local files and branches were preserved.",
                    target, remote, branch, remote_commit,
                )
            raise CheckoutReviewRequired(
                f"Remote '{remote}/{branch}' has commits missing from local HEAD (ahead, divergent or unrelated history). "
                "Fetched for inspection; review before synchronizing. Local files and branches were preserved.",
                target, remote, branch, remote_commit,
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


def _editor_checkout_signature(path):
    """Fingerprint local Git state without remote access or index refresh."""
    try:
        root = _repository_path(path, 2.0)
        outputs = tuple(_checked_git(root, *args, timeout=2) for args in (
            ("rev-parse", "HEAD^{commit}"), ("symbolic-ref", "HEAD"),
            ("config", "--list", "--show-origin"), ("show-ref",),
            ("--no-optional-locks", "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"),
            ("diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD", "--"),
            ("diff", "--cached", "--no-ext-diff", "--no-textconv", "--binary", "--"),
        ))
        names = _run_git(root, "ls-files", "--others", "--exclude-standard", "-z", timeout=2)
        if names.returncode:
            return None
        files = []
        for name in names.stdout.split('\0'):
            if name:
                info = (root / name).lstat()
                files.append((name, info.st_mtime_ns, info.st_ctime_ns, info.st_size))
        markers = []
        for marker in ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'sequencer'):
            location = Path(_checked_git(root, "rev-parse", "--git-path", marker, timeout=2))
            markers.append((root / location).exists())
        return sha256(repr((outputs, files, markers)).encode()).hexdigest()
    except (ProjectGitError, OSError):
        return None


class EditorCheckoutCache:
    """Five-minute, app-session cache of checks, never of authentication secrets."""

    def __init__(self):
        self.entries = {}

    def run(self, setup, path, **kwargs):
        key = (str(path), kwargs.get('dev_remote_url'), kwargs.get('vogsphere_url'))
        signature = _editor_checkout_signature(path)
        cached = self.entries.pop(key, None)
        now = time.monotonic()
        if signature is not None and cached and now - cached[0] < 300 and signature == cached[1]:
            self.entries[key] = cached
            outcome = cached[2]
            if isinstance(outcome, CheckoutReviewRequired):
                # The UI may update its copy after a confirmed pull/push.
                raise CheckoutReviewRequired(str(outcome), outcome.path, outcome.remote, outcome.branch, outcome.commit)
            return outcome
        try:
            result = setup(path, **kwargs)
        except CheckoutReviewRequired as error:
            if signature is not None and _editor_checkout_signature(path) == signature:
                self.entries[key] = (time.monotonic(), signature, CheckoutReviewRequired(
                    str(error), error.path, error.remote, error.branch, error.commit))
            raise
        if signature is not None and not getattr(result, 'warnings', ()) and _editor_checkout_signature(path) == signature:
            self.entries[key] = (time.monotonic(), signature, result)
        # Keep this bounded even when many projects are opened in one session.
        self.entries = {key: value for key, value in self.entries.items() if time.monotonic() - value[0] < 300}
        return result
