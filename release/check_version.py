"""Validate a stable release tag against the sole package version source."""
from pathlib import Path
import re
import sys
import tomllib

STABLE = r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'


def check(tag: str) -> str:
    version = tomllib.loads((Path(__file__).resolve().parents[1]/'pyproject.toml').read_text())['project']['version']
    if not re.fullmatch('v' + STABLE, tag) or tag != 'v' + version:
        raise ValueError(f'Expected stable tag v{version}, got {tag!r}')
    notes = Path(__file__).resolve().parents[1]/'CHANGELOG.md'
    if f'## {version}\n' not in notes.read_text():
        raise ValueError(f'Missing release notes for {version}')
    return version


if __name__ == '__main__':
    try:
        print(check(sys.argv[1]))
    except (ValueError, IndexError, OSError) as error:
        sys.exit(str(error))
