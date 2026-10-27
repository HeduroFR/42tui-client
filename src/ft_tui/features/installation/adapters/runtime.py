"""Compatibility owner for PyPI, receipts, subprocesses and resource I/O.

The historical module aliases this adapter so monkeypatches of installation
inspection continue to guard apply_update and for_current_installation.
"""
from __future__ import annotations
from importlib import metadata, resources
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import httpx
import ft_tui
from ..ports import ReleaseCheck
from ..models import (PACKAGE, PYPI_URL, CHECK_INTERVAL, STABLE, Installation,
                      stable_version, select_latest, parse_release_notes, upgrade_command)

def latest_stable(client=None):
    """Read only public PyPI metadata; never use OAuth or release-supplied URLs."""
    if client is None:
        with httpx.Client(timeout=5, follow_redirects=False, trust_env=False) as owned:
            return latest_stable(owned)
    with client.stream('GET', PYPI_URL, headers={'Accept': 'application/json'}) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > 2 * 1024 * 1024:
                raise ValueError('Release metadata exceeds limit')
    value = json.loads(content)
    return select_latest(value)

def detect_installation(*, prefix=None, distribution=None, which=shutil.which):
    """Unknown, editable, direct-source and explicitly pinned installs stay local."""
    prefix = Path(prefix or sys.prefix).resolve()
    if sys.platform == 'win32' or prefix.name != PACKAGE:
        return None
    distribution = distribution or metadata.distribution(PACKAGE)
    if distribution.read_text('direct_url.json'):
        return None
    if not Path(distribution.locate_file('')).resolve().is_relative_to(prefix):
        return None
    executable = prefix / ('Scripts/42tui.exe' if sys.platform == 'win32' else 'bin/42tui')
    if not executable.is_file() or not stable_version(distribution.version):
        return None
    receipt = prefix / 'uv-receipt.toml'
    try:
        if receipt.is_file():
            tool = tomllib.loads(receipt.read_text())['tool']
            requirements = tool.get('requirements', [])
            own = [r for r in requirements if r.get('name') == PACKAGE]
            if not own or any(r.get(k) for r in requirements for k in ('editable', 'path', 'git', 'url')):
                return None
            if any(r.get('specifier') for r in own):
                return None
            entrypoints = tool.get('entrypoints', [])
            if not any(Path(e['install-path']).is_file()
                       and Path(e['install-path']).resolve() == executable.resolve() for e in entrypoints):
                return None
            command = which('uv')
            return Installation('uv', command, prefix, executable, distribution.version) if command else None
        receipt = prefix / 'pipx_metadata.json'
        if receipt.is_file():
            if prefix.parent.name != 'venvs':
                return None
            package = json.loads(receipt.read_text())['main_package']
            if package.get('package') != PACKAGE or package.get('package_or_url') != PACKAGE:
                return None
            if package.get('pip_args'):
                return None
            command = which('pipx')
            return Installation('pipx', command, prefix, executable, distribution.version) if command else None
    except (ValueError, TypeError, KeyError, AttributeError, OSError):
        return None
    return None

def installed_cli_version(installation, run=subprocess.run):
    result = run([str(installation.executable), '--version'], check=True, capture_output=True, text=True, timeout=15)
    found = re.fullmatch(r'42tui (\d+\.\d+\.\d+)\s*', result.stdout)
    if not found or not stable_version(found.group(1)):
        raise ValueError('Installed version could not be verified')
    return found.group(1)


def apply_update(installation, target, state_dir, *, run=subprocess.run):
    """Called only after the TUI exits. A lock prevents concurrent upgraders."""
    if not stable_version(target) or stable_version(target) <= stable_version(installation.version):
        raise ValueError('Expected a newer stable release')
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    # OS locks release automatically on a crash; the empty file can remain.
    import fcntl
    with (state_dir / 'update.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return None
        before = installed_cli_version(installation, run)
        if stable_version(before) >= stable_version(target):
            return before
        # An exact user pin added since the check must not be overwritten.
        current = detect_installation()
        if current is None or current.prefix != installation.prefix or current.manager != installation.manager:
            raise ValueError('Installation changed; update cancelled')
        directory_command = ([current.command, '--no-config', 'tool', 'dir'] if current.manager == 'uv'
                             else [current.command, 'environment', '--value', 'PIPX_LOCAL_VENVS'])
        directory = run(directory_command, check=True, capture_output=True, text=True, timeout=15)
        if Path(directory.stdout.strip()).resolve() != current.prefix.parent.resolve():
            raise ValueError('Package manager targets a different environment')
        run(upgrade_command(current), check=True, capture_output=True, text=True, timeout=600)
        after = installed_cli_version(current, run)
        if stable_version(after) <= stable_version(before) or stable_version(after) < stable_version(target):
            raise ValueError('Upgrade did not install the expected newer release')
        return after

def release_notes(previous, current, text=None):
    if not stable_version(previous) or not stable_version(current):
        return ''
    if text is None:
        try:
            text = resources.files('ft_tui').joinpath('CHANGELOG.md').read_text(encoding='utf-8')
        except (FileNotFoundError, OSError):
            source = Path(ft_tui.__file__).resolve().parents[2] / 'CHANGELOG.md'
            text = source.read_text(encoding='utf-8') if source.is_file() else ''
    return parse_release_notes(previous, current, text)

class UpdateService:
    def __init__(self, *, current=None, installation=None, check: ReleaseCheck=latest_stable):
        self.current = current or metadata.version(PACKAGE)
        self.installation = installation
        self.check = check

    @classmethod
    def for_current_installation(cls):
        try:
            return cls(installation=detect_installation())
        except (OSError, ValueError, metadata.PackageNotFoundError):
            return cls(installation=None)
