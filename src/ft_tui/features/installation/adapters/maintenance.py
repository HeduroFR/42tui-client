"""Explicit maintenance of the running uv/pipx installation, without TUI state."""
from importlib import metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib


def _manager_command(name: str) -> str:
    local = Path.home()/'.local/bin'/name
    command = str(local) if local.is_file() and local.stat().st_mode & 0o111 else shutil.which(name)
    if not command:
        raise ValueError(f'{name} is unavailable. Use the original installation manager to maintain 42TUI.')
    return command


def manage_installation(action: str) -> int:
    """Only change a manager-owned environment matching this running package."""
    if action not in ('update', 'uninstall', 'remove'):
        raise ValueError('Unknown installation action')
    uninstall = action in ('uninstall', 'remove')
    try:
        prefix = Path(sys.prefix).resolve()
        distribution = metadata.distribution('ft-tui')
        if (prefix.name != 'ft-tui' or distribution.read_text('direct_url.json')
                or not Path(distribution.locate_file('')).resolve().is_relative_to(prefix)):
            raise ValueError('Source, editable and unmanaged installations must be maintained with their original manager.')
        if (prefix/'uv-receipt.toml').is_file():
            tool = tomllib.loads((prefix/'uv-receipt.toml').read_text())['tool']
            requirements = tool.get('requirements', [])
            if (not any(r.get('name') == 'ft-tui' for r in requirements)
                    or any(r.get(key) for r in requirements for key in ('editable', 'path', 'git', 'url'))):
                raise ValueError('The uv receipt does not describe a registry installation of ft-tui.')
            command = [_manager_command('uv'), '--no-config', 'tool']
            directory_command = [*command, 'dir']
            mutation = [*command, 'uninstall' if uninstall else 'upgrade', 'ft-tui']
            if not uninstall:
                mutation += ['--default-index', 'https://pypi.org/simple', '--prerelease', 'disallow']
        elif (prefix/'pipx_metadata.json').is_file() and prefix.parent.name == 'venvs':
            package = json.loads((prefix/'pipx_metadata.json').read_text())['main_package']
            if package.get('package') != 'ft-tui' or package.get('package_or_url') != 'ft-tui':
                raise ValueError('The pipx receipt does not describe a registry installation of ft-tui.')
            command = _manager_command('pipx')
            directory_command = [command, 'environment', '--value', 'PIPX_LOCAL_VENVS']
            mutation = [command, 'uninstall' if uninstall else 'upgrade', 'ft-tui']
            if not uninstall:
                mutation += ['--pip-args=--index-url https://pypi.org/simple']
        else:
            raise ValueError('No supported uv/pipx installation receipt was found.')
        directory = subprocess.run(directory_command, check=True, capture_output=True, text=True, timeout=15)
        if Path(directory.stdout.strip()).resolve() != prefix.parent:
            raise ValueError('The package manager targets a different installation; no changes were made.')
        # Import every module needed above before self-uninstall removes this package.
        result = subprocess.run(mutation)
        if result.returncode:
            return result.returncode
        if uninstall:
            print('42TUI uninstalled. Local data, account credentials, fonts and shared Python tooling were preserved.')
        else:
            print('42TUI update completed using your package manager; existing version constraints are respected.')
        return 0
    except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError,
            metadata.PackageNotFoundError) as error:
        print(f'42tui: {error}', file=sys.stderr)
        return 1
