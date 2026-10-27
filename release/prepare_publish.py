"""Verify immutable existing PyPI artifacts and stage only missing uploads."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tomllib
from urllib.error import HTTPError
from urllib.request import urlopen


def prepare(dist: Path, pending: Path, existing: list[dict]) -> None:
    local = {p.name: p for p in dist.iterdir() if p.is_file()}
    published = {item['filename']: item['digests']['sha256'] for item in existing}
    for name, digest in published.items():
        if name not in local or hashlib.sha256(local[name].read_bytes()).hexdigest() != digest:
            raise ValueError(f'Published artifact differs: {name}. Reuse the original CI artifacts; never overwrite a release.')
    pending.mkdir(parents=True, exist_ok=False)
    for name, path in local.items():
        if name not in published:
            shutil.copy2(path, pending/name)


def main():
    version = tomllib.loads(Path('pyproject.toml').read_text())['project']['version']
    try:
        with urlopen(f'https://pypi.org/pypi/ft-tui/{version}/json', timeout=30) as response:
            existing = json.load(response)['urls']
    except HTTPError as error:
        if error.code != 404:
            raise
        existing = []
    prepare(Path('dist'), Path('pending-dist'), existing)
    pending = any(Path('pending-dist').iterdir())
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        print(f'pending={str(pending).lower()}', file=output)
    print('Missing artifacts staged' if pending else 'All existing artifacts verified against CI files')


if __name__ == '__main__':
    main()
