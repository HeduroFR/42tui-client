"""Publish reviewed, committed project work with the same operations as the TUI."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from collections.abc import Sequence

from sqlalchemy.exc import SQLAlchemyError

from ft_tui.config.settings import database_url
from ft_tui.db import initialize_database
from ft_tui.features.projects.adapters.git import (
    ProjectGitError, inspect_repository, plan_project_push, push_project,
)
from ft_tui.features.projects.adapters.navigation import configured_projects


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="42git", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status", help="Inspect the configured project containing the current directory")
    push = commands.add_parser("push", help="Review and push committed work; local edits are not committed")
    push.add_argument("destination", choices=("dev", "vog", "all"))
    args = parser.parse_args(argv)
    try:
        cwd = Path.cwd().resolve()
        factory = initialize_database(database_url())
        with factory() as session:
            matches = [(Path(project.local_path).expanduser().resolve(), project)
                       for project in configured_projects(session)
                       if cwd.is_relative_to(Path(project.local_path).expanduser().resolve())]
            if not matches:
                raise ProjectGitError("Run 42git inside a configured local project folder.")
            depth = max(len(path.parts) for path, _ in matches)
            matches = [(path, project) for path, project in matches if len(path.parts) == depth]
            if len(matches) != 1:
                raise ProjectGitError("Multiple configured projects use this folder. Fix their local paths in Settings.")
            path, project = matches[0]
            dev_url, vog_url = project.dev_repo_url, project.vogsphere_url
            name = project.name
        print(f"{name}: {path}")
        if args.command == "status":
            snapshot = inspect_repository(path)
            if snapshot.error:
                raise ProjectGitError(snapshot.error)
            print(f"Branch: {snapshot.branch}")
            print(f"Staged: {snapshot.staged}; changed: {snapshot.changed}; untracked: {snapshot.untracked}")
            return 0
        plan = plan_project_push(path, args.destination, dev_remote_url=dev_url, vogsphere_url=vog_url)
        print(f"Committed work: {plan.commit} ({plan.branch})")
        print(f"Uncommitted changes left untouched: {plan.dirty_count}")
        for target in plan.targets:
            print(f"{target.destination}: {target.url} -> {target.branch}")
            if target.error:
                print(f"  Unavailable: {target.error}")
        if not any(not target.error for target in plan.targets):
            return 1
        try:
            approved = input("Push this committed work? [y/N] ").strip().casefold() == "y"
        except EOFError:
            approved = False
        if not approved:
            print("Push cancelled.")
            return 2
        results = push_project(plan)
        for result in results:
            print(f"{result.target.destination}: {'OK' if result.success else 'FAILED'}: {result.message}")
        return 0 if all(result.success for result in results) else 1
    except (ProjectGitError, OSError, SQLAlchemyError) as error:
        print(f"42git: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("42git: interrupted; check remote status before retrying.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
