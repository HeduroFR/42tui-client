"""Create/resume a draft release; compare existing assets before upload."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


def gh(*args, check=True):
    return subprocess.run(['gh', *args], capture_output=True, text=True, check=check)


def find_release(repo, tag):
    view = gh('api', f'repos/{repo}/releases/tags/{tag}', check=False)
    if view.returncode == 0:
        return json.loads(view.stdout)
    if '404' not in view.stderr:
        raise RuntimeError(view.stderr)
    # The tag endpoint only returns published releases. Authenticated listings
    # include drafts, which may be on a later page when resuming an old release.
    pages = json.loads(gh('api', f'repos/{repo}/releases', '--paginate', '--slurp').stdout)
    return next((release for page in pages for release in page if release['tag_name'] == tag), None)


def main():
    tag = os.environ['RELEASE_TAG']
    repo = os.environ['GITHUB_REPOSITORY']
    output = Path('release-assets')
    output.mkdir(exist_ok=True)
    for path in [*Path('dist').iterdir(), *[Path('distribution')/n for n in ('install.sh', 'install.ps1', 'install.py', 'uninstall.sh')]]:
        (output/path.name).write_bytes(path.read_bytes())
    sums = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n'
                   for p in sorted(output.iterdir()) if p.name != 'SHA256SUMS')
    (output/'SHA256SUMS').write_text(sums)
    release = find_release(repo, tag)
    if release is None:
        notes = Path('CHANGELOG.md').read_text().split(f'## {tag[1:]}\n', 1)[1].split('\n## ', 1)[0]
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.md') as body:
            body.write(notes)
            body.flush()
            gh('release', 'create', tag, '--verify-tag', '--draft', '--title', tag, '--notes-file', body.name)
        release = find_release(repo, tag)
        if release is None:
            raise RuntimeError(f'Created draft release {tag} is not visible; retry with the original artifacts')
    remote_names = {a['name'] for a in release['assets']}
    local_names = {p.name for p in output.iterdir()}
    if remote_names - local_names:
        raise RuntimeError('Existing release contains unexpected assets; inspect manually')
    with tempfile.TemporaryDirectory() as temporary:
        for path in sorted(output.iterdir()):
            if path.name in remote_names:
                gh('release', 'download', tag, '--pattern', path.name, '--dir', temporary)
                if (Path(temporary)/path.name).read_bytes() != path.read_bytes():
                    raise RuntimeError(f'Existing GitHub release asset differs: {path.name}')
            else:
                if not release['draft']:
                    raise RuntimeError('Published GitHub release is incomplete; inspect manually')
                gh('release', 'upload', tag, str(path))
    if release['draft']:
        gh('release', 'edit', tag, '--draft=false')


if __name__ == '__main__':
    main()
