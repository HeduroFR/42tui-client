"""Pure stable-release selection, notes parsing and manager command models."""
from dataclasses import dataclass
from pathlib import Path
import re

PACKAGE = 'ft-tui'
PYPI_URL = 'https://pypi.org/pypi/ft-tui/json'
CHECK_INTERVAL = 12 * 60 * 60
STABLE = re.compile(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z')

def stable_version(value):
    if not isinstance(value, str) or not STABLE.fullmatch(value):
        return None
    return tuple(map(int, value.split('.')))

@dataclass(frozen=True)
class Installation:
    manager: str
    command: str
    prefix: Path
    executable: Path
    version: str

def upgrade_command(installation):
    if installation.manager == 'uv':
        return [installation.command, '--no-config', 'tool', 'upgrade', PACKAGE,
                '--default-index', 'https://pypi.org/simple', '--prerelease', 'disallow']
    if installation.manager == 'pipx':
        return [installation.command, 'upgrade', PACKAGE, '--pip-args=--index-url https://pypi.org/simple']
    raise ValueError('Unsupported installation')

def select_latest(value):
    if not isinstance(value, dict) or not isinstance(value.get('info'), dict):
        raise ValueError('Unexpected package metadata')
    if value['info'].get('name') != PACKAGE:
        raise ValueError('Unexpected package metadata')
    releases = value.get('releases')
    if not isinstance(releases, dict):
        raise ValueError('Missing release metadata')
    available = [version for version, files in releases.items() if stable_version(version)
                 and isinstance(files, list) and any(isinstance(file, dict) and file.get('yanked') is False
                                                    for file in files)]
    return max(available, key=stable_version) if available else None

def parse_release_notes(previous, current, text):
    if not stable_version(previous) or not stable_version(current):
        return ''
    sections = re.split(r'^## (\d+\.\d+\.\d+)\s*$', text, flags=re.MULTILINE)
    notes = []
    for version, body in zip(sections[1::2], sections[2::2]):
        if stable_version(previous) < stable_version(version) <= stable_version(current):
            notes.append((stable_version(version), f'## {version}\n\n{body.strip()}'))
    return '\n\n'.join(body for _, body in sorted(notes, reverse=True))
