"""CLI backend and shell integration for changing directory with ``42goto``."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ft_tui.config.settings import database_url
from ft_tui.db import initialize_database
from ft_tui.features.projects.adapters.navigation import (
    ProjectNavigationError,
    configured_projects,
    resolve_project_path,
)


_BASH_INIT = r'''42goto() {
    local target
    target="$(command 42goto --path "$@")" || return $?
    builtin cd -- "$target"
}

_42goto_complete() {
    local prefix="${COMP_WORDS[COMP_CWORD]}" candidate
    COMPREPLY=()
    while IFS= read -r candidate; do
        COMPREPLY+=("$candidate")
    done < <(command 42goto --complete --prefix "$prefix")
}
complete -o nospace -F _42goto_complete 42goto'''

_ZSH_INIT = r'''42goto() {
    local target
    target="$(command 42goto --path "$@")" || return $?
    builtin cd -- "$target"
}

_42goto() {
    local -a projects
    projects=("${(@f)$(command 42goto --complete --prefix "${words[2]}")}")
    _describe '42 project' projects
}
compdef _42goto 42goto'''


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="42goto",
        description="Change to a configured 42 project directory from your shell.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--path", action="store_true", help=argparse.SUPPRESS)
    mode.add_argument("--complete", action="store_true", help=argparse.SUPPRESS)
    mode.add_argument("--shell-init", choices=("bash", "zsh"), metavar="SHELL")
    parser.add_argument("--prefix", default="", help=argparse.SUPPRESS)
    parser.add_argument("project", nargs="*", help="project name or slug; omit to use the active project")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Print a target path for the shell wrapper, or emit completion candidates."""
    args = _parser().parse_args(argv)
    if args.shell_init:
        print(_BASH_INIT if args.shell_init == "bash" else _ZSH_INIT)
        return 0

    if not args.path and not args.complete:
        print(
            "42goto must be loaded as a shell function to change your current directory. "
            "Add `eval \"$(command 42goto --shell-init zsh)\"` to ~/.zshrc "
            "or use `42goto --shell-init bash` for Bash.",
            file=sys.stderr,
        )
        return 2

    try:
        session_factory = initialize_database(database_url())
        with session_factory() as session:
            if args.complete:
                prefix = args.prefix.casefold()
                for project in configured_projects(session):
                    if project.slug.casefold().startswith(prefix):
                        print(project.slug)
                return 0

            query = " ".join(args.project).strip() or None
            print(resolve_project_path(session, query))
            return 0
    except ProjectNavigationError as error:
        if not args.complete:
            print(f"42goto: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"42goto: local project database error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
