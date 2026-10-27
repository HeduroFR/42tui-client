"""Inspect built distributions before publication; never extract untrusted paths."""
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
import sys
import tarfile
import zipfile

RESOURCES = ('locales/es.json', 'locales/fr.json', 'testers.toml', 'features/cluster_map/layout.json', 'assets/wip.png')


def check_archive(path: Path) -> str:
    if path.suffix == '.whl':
        with zipfile.ZipFile(path) as archive:
            files = {n: archive.read(n) for n in archive.namelist() if not n.endswith('/')}
        prefix = 'ft_tui/'
        metadata_name = next((n for n in files if n.endswith('.dist-info/METADATA')), '')
    else:
        with tarfile.open(path) as archive:
            files = {m.name: archive.extractfile(m).read() for m in archive.getmembers() if m.isfile()}
            if any(m.issym() or m.islnk() for m in archive.getmembers()):
                raise ValueError('forbidden archive link')
        root = next(iter(files)).split('/')[0] + '/'
        prefix = root + 'src/ft_tui/'
        metadata_name = root + 'PKG-INFO'
    for name in files:
        parts = PurePosixPath(name).parts
        if (PurePosixPath(name).is_absolute() or '..' in parts or
                any(p.startswith('.env') or p in ('.local', 'node_modules', 'backend', '__pycache__')
                    or '.sqlite' in p or p.endswith(('.pyc', '.pem', '.key')) for p in parts)):
            raise ValueError(f'forbidden archive member: {name}')
        if path.suffix == '.whl' and not (name.startswith('ft_tui/') or '.dist-info/' in name):
            raise ValueError(f'unexpected wheel member: {name}')
    for resource in ('main.py', *RESOURCES):
        if prefix + resource not in files:
            raise ValueError(f'Missing package resource {resource} in {path.name}')
    metadata = BytesParser().parsebytes(files.get(metadata_name, b''))
    if metadata['Name'] != 'ft-tui' or metadata['Requires-Python'] != '>=3.12' or not metadata['Version']:
        raise ValueError(f'Invalid distribution metadata in {path.name}')
    return metadata['Version']


def main(directory: Path) -> None:
    archives = sorted(directory.glob('*.whl')) + sorted(directory.glob('*.tar.gz'))
    versions = {check_archive(path) for path in archives}
    if len(archives) != 2 or len(versions) != 1 or not any(p.suffix == '.whl' for p in archives):
        raise ValueError('Expected exactly one wheel and one matching sdist')
    print(f'Checked wheel and sdist: {versions.pop()}')


if __name__ == '__main__':
    try:
        main(Path(sys.argv[1]))
    except (ValueError, OSError, IndexError, KeyError) as error:
        sys.exit(str(error))
