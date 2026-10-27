"""Check/update the helper digest embedded in both public entry points."""
import hashlib
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parents[1]/'distribution'
digest = hashlib.sha256((root/'install.py').read_bytes()).hexdigest()
patterns = {'install.sh': r'(verify "\$work/install.py" )\x27[0-9a-f]{64}\x27',
            'install.ps1': r'(Assert-Hash \$helper )\x27[0-9a-f]{64}\x27'}
for name, pattern in patterns.items():
    path = root/name
    current = path.read_text()
    updated, count = re.subn(pattern, lambda match: match.group(1) + "'" + digest + "'", current)
    if count != 1:
        sys.exit(f'Expected one helper digest in {name}')
    if '--write' in sys.argv:
        path.write_text(updated)
    elif current != updated:
        sys.exit(f'{name} helper digest is stale; run python release/installer_hashes.py --write')
print('Both installer helper digests verified')
