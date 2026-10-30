"""Application and editor-heartbeat command entry point."""

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys
import os

def _record_editor_heartbeat(args: argparse.Namespace) -> int:
    from ft_tui.config.settings import database_url
    from ft_tui.db import initialize_database
    from ft_tui.app.bootstrap import build_worklog_service

    session_factory = initialize_database(database_url())
    try:
        occurred_at = (
            datetime.fromtimestamp(args.timestamp, tz=timezone.utc) if args.timestamp is not None else None
        )
        result = build_worklog_service(session_factory).heartbeat(
            Path(args.file), editor=args.editor, is_write=args.write, occurred_at=occurred_at)
    except ValueError as error:
        print(f"42tui: {error}", file=sys.stderr)
        return 2
    if not args.quiet:
        print(f"42tui: activity recorded for {result.project_name} (+{result.credited_seconds:.0f}s)")
    return 0


def main() -> None:
    """Launch the TUI or ingest one editor event without opening the TUI."""
    if sys.argv[1:] == ["--version"]:
        from importlib.metadata import version

        print(f"42tui {version('ft-tui')}")
        return

    if len(sys.argv) > 1 and sys.argv[1] in ('update', 'uninstall', 'remove'):
        action = sys.argv[1]
        parser = argparse.ArgumentParser(prog=f'42tui {action}', description=(
            'Update the current managed installation.' if action == 'update' else
            'Uninstall 42TUI while preserving local data and shared tooling.'
        ))
        parser.parse_args(sys.argv[2:])
        from ft_tui.features.installation.adapters.maintenance import manage_installation
        raise SystemExit(manage_installation(action))

    if sys.argv[1:] in (["--help"], ["-h"]):
        print('Usage: 42tui [--version | update | uninstall | remove | heartbeat ...]')
        print('Run without arguments to open the TUI. Run a command with --help for details.')
        return

    if len(sys.argv) > 1 and sys.argv[1] == "heartbeat":
        parser = argparse.ArgumentParser(
            prog="42tui heartbeat",
            description="Record local editor activity for a configured project.",
        )
        parser.add_argument("--file", required=True, help="absolute path of the active editor file")
        parser.add_argument("--editor", default="unknown", help="editor identifier, for example vscode or nvim")
        parser.add_argument("--write", action="store_true", help="mark this event as a file save")
        parser.add_argument("--timestamp", type=float, help="event Unix timestamp (defaults to now)")
        parser.add_argument("--quiet", action="store_true", help="suppress the success message")
        raise SystemExit(_record_editor_heartbeat(parser.parse_args(sys.argv[2:])))

    from ft_tui.config.settings import database_url, oauth_api_url
    from ft_tui.db import initialize_database
    from ft_tui.db.database import DatabaseResetRequired
    try:
        session_factory = initialize_database(database_url())
    except DatabaseResetRequired as error:
        print(f"42tui: {error}", file=sys.stderr)
        raise SystemExit(2)
    from ft_tui.app.bootstrap import build_installation_service
    from ft_tui.config.settings import data_dir
    from ft_tui.features.installation.adapters.runtime import UpdateService

    updates = UpdateService.for_current_installation()
    policy = build_installation_service(session_factory)
    # Consume the guard so an upgrade failure cannot cause a restart/retry loop.
    checked = os.environ.pop('_42TUI_UPDATE_CHECKED', '') == '1'
    if not checked and updates.update_before_launch(policy, data_dir()):
        session_factory.kw['bind'].dispose()
        executable = str(updates.installation.executable)
        try:
            os.execve(executable, [executable, *sys.argv[1:]],
                      dict(os.environ, _42TUI_UPDATE_CHECKED='1'))
        except OSError:
            print('42tui: could not restart after updating. Please launch 42tui again.', file=sys.stderr)
            raise SystemExit(1)
        return

    from ft_tui.api.client_factory import provider_for_device
    from ft_tui.api.oauth_client import OAuthClient
    from ft_tui.ui.app import FortyTwoTuiApp

    from ft_tui.infrastructure.security.session_vault import LockedSessionStore, session_vault_path
    vault_path = session_vault_path()
    store = LockedSessionStore() if vault_path.exists() or vault_path.is_symlink() else None
    oauth_client = OAuthClient(oauth_api_url(), credential_store=store)
    provider = provider_for_device(oauth_client)
    app = FortyTwoTuiApp(session_factory, provider, oauth_client=oauth_client,
                        update_service=updates, installation_service=policy)
    app.run()


if __name__ == "__main__":
    main()
