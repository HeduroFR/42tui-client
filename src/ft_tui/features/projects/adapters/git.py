"""Git hygiene inspection and conservative publishing for configured projects."""

from __future__ import annotations

import subprocess
import os
import re
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from .ssh_askpass import ssh_environment


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
            text=True, stdin=subprocess.DEVNULL if ssh_environment.get() else None, timeout=timeout,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **ssh_environment.get()},
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
        raise ProjectGitError("Detached HEAD: switch to a branch before continuing.")
    commit = _run_git(root, "rev-parse", "--verify", "HEAD^{commit}", timeout=timeout)
    if commit.returncode:
        raise ProjectGitError("No committed HEAD: create a commit before continuing.")
    if _checked_git(root, "ls-files", "--unmerged", timeout=timeout):
        raise ProjectGitError("Resolve the repository's merge conflicts before continuing.")
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


def _remote_heads(output: str) -> tuple[dict[str, str], str | None]:
    heads = {}
    default = None
    for line in output.splitlines():
        value, ref = line.split("\t", 1)
        if value.startswith("ref: refs/heads/") and ref == "HEAD":
            default = value.removeprefix("ref: refs/heads/")
        elif ref.startswith("refs/heads/"):
            heads[ref.removeprefix("refs/heads/")] = value
    return heads, default


def _remote_branch(remote: str, heads: dict[str, str], default: str | None,
                   *, preferred: str | None = None, empty: str | None = None) -> str:
    if preferred in heads:
        return preferred
    if default in heads:
        return default
    if len(heads) == 1:
        return next(iter(heads))
    if not heads and empty:
        return empty
    raise ProjectGitError(f"Remote '{remote}' has no unambiguous branch; inspect it manually.")


def _discover_remote(root: Path, remote: str, timeout: float) -> tuple[dict[str, str], str | None]:
    return _remote_heads(_checked_git(root, "ls-remote", "--symref", "--", remote,
                                      "HEAD", "refs/heads/*", timeout=timeout))


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
        ("dev", "origin", branch, dev_remote_url), ("vog", "vogsphere", branch, vogsphere_url),
    ):
        if destination not in {name, "all"}:
            continue
        try:
            url = _remote_url(root, remote, expected, timeout)
            if name == "vog":
                heads, default = _discover_remote(root, remote, timeout)
                remote_branch = _remote_branch(remote, heads, default, empty=branch)
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
            if target.destination == "vog":
                heads, default = _discover_remote(root, target.remote, timeout)
                if _remote_branch(target.remote, heads, default, empty=plan.branch) != target.branch:
                    raise ProjectGitError("Remote branch changed since review; review the push again.")
            _checked_git(root, "-c", "push.followTags=false", "-c", "push.recurseSubmodules=no",
                         "-c", f"remote.{target.remote}.mirror=false", "push", "--porcelain",
                         "--", target.remote, f"{plan.commit}:refs/heads/{target.branch}", timeout=timeout)
            outcomes.append(PushResult(target, True, f"Published committed HEAD {plan.commit[:12]} to {target.remote}/{target.branch}."))
        except ProjectGitError as error:
            outcomes.append(PushResult(target, False, str(error)))
    return tuple(outcomes)


@dataclass(frozen=True)
class PullTarget:
    destination: str
    remote: str
    url: str
    branch: str
    commit: str
    url_fingerprint: str = field(repr=False)


@dataclass(frozen=True)
class PullPlan:
    path: Path
    branch: str
    commit: str
    target_commit: str
    targets: tuple[PullTarget, ...]


def _clean_pull_head(root: Path, timeout: float) -> tuple[str, str]:
    head = _committed_head(root, timeout)
    for marker in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply", "sequencer"):
        location = Path(_checked_git(root, "rev-parse", "--git-path", marker, timeout=timeout))
        if (root / location).exists():
            raise ProjectGitError("Finish the current merge, rebase or cherry-pick before pulling.")
    if _checked_git(root, "status", "--porcelain=v1", "--untracked-files=all",
                    "--ignore-submodules=none", timeout=timeout):
        raise ProjectGitError("Commit or move local changes and untracked files before pulling. Nothing was stashed.")
    return head


def plan_project_pull(
    path: str | Path, destination: str = "all", *, dev_remote_url: str | None = None,
    vogsphere_url: str | None = None, timeout: float = 60,
) -> PullPlan:
    """Fetch selected branches and review one fast-forward, without changing local files."""
    if destination not in {"dev", "vog", "all"}:
        raise ProjectGitError("Choose a pull source: dev, vog or all.")
    root = _repository_path(path, timeout)
    branch, commit = _clean_pull_head(root, timeout)
    targets = []
    for name, remote, expected in (("dev", "origin", dev_remote_url), ("vog", "vogsphere", vogsphere_url)):
        if destination not in {name, "all"}:
            continue
        url = _remote_url(root, remote, expected, timeout)
        heads, default = _discover_remote(root, remote, timeout)
        remote_branch = _remote_branch(remote, heads, default, preferred=branch if name == "dev" else None)
        _checked_git(root, "fetch", "--no-tags", "--no-recurse-submodules", "--refmap=", "--", remote,
                     f"refs/heads/{remote_branch}", timeout=timeout)
        fetched = _checked_git(root, "rev-parse", "--verify", "FETCH_HEAD^{commit}", timeout=timeout)
        targets.append(PullTarget(name, remote, _display_url(url), remote_branch, fetched,
                                  sha256(url.encode()).hexdigest()))
    target_commit = commit
    for target in targets:
        if not _run_git(root, "merge-base", "--is-ancestor", target.commit, target_commit, timeout=timeout).returncode:
            continue
        if _run_git(root, "merge-base", "--is-ancestor", target_commit, target.commit, timeout=timeout).returncode:
            raise ProjectGitError("Pull histories diverge or are unrelated. Reconcile manually; local HEAD was not changed.")
        target_commit = target.commit
    if _clean_pull_head(root, timeout) != (branch, commit):
        raise ProjectGitError("Branch or HEAD changed while fetching; review the pull again.")
    return PullPlan(root, branch, commit, target_commit, tuple(targets))


def pull_project(plan: PullPlan, *, timeout: float = 60) -> str:
    """Apply only the reviewed fast-forward; never stash, reset or create a merge commit."""
    root = _repository_path(plan.path, timeout)
    for target in plan.targets:
        url = _remote_url(root, target.remote, None, timeout)
        if sha256(url.encode()).hexdigest() != target.url_fingerprint:
            raise ProjectGitError("Remote changed since review; review the pull again.")
        heads, default = _discover_remote(root, target.remote, timeout)
        branch = _remote_branch(target.remote, heads, default,
                                preferred=plan.branch if target.destination == "dev" else None)
        if branch != target.branch or heads.get(branch) != target.commit:
            raise ProjectGitError("Remote branch or commit changed since review; review the pull again.")
    if _clean_pull_head(root, timeout) != (plan.branch, plan.commit):
        raise ProjectGitError("Branch or HEAD changed since review; review the pull again.")
    if plan.target_commit == plan.commit:
        return "Already up to date; local commits were preserved."
    _checked_git(root, "-c", "submodule.recurse=false", "merge", "--ff-only", "--no-autostash",
                 "--no-overwrite-ignore", "--", plan.target_commit, timeout=timeout)
    return f"Fast-forwarded {plan.branch} to {plan.target_commit[:12]}."


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


@dataclass(frozen=True)
class CheckoutReview:
    branch: str
    head: str
    status: str
    diff: str


def review_project_checkout(path: str | Path, commit: str) -> CheckoutReview:
    """Compare the fetched snapshot with tracked local files without changing Git."""
    root = _repository_path(path, 10.0)
    # Resolve to an object ID before passing it to diff, never an option or path.
    fetched = _checked_git(root, "rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}")
    branch = _run_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    head = _run_git(root, "rev-parse", "--verify", "HEAD^{commit}")
    status = _run_git(root, "--no-optional-locks", "status", "--short", "--untracked-files=all")
    if status.returncode:
        raise ProjectGitError(_safe_detail(status.stderr) or "Git could not read repository status.")
    diff = _checked_git(root, "--no-optional-locks", "diff", "--no-ext-diff", "--no-textconv",
                        "--no-color", fetched, "--")
    return CheckoutReview(branch.stdout.strip() if not branch.returncode else "(detached HEAD)",
                          head.stdout.strip() if not head.returncode else "—", status.stdout.rstrip(), diff)


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
