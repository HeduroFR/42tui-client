"""Run with the installed package's Python, from outside the checkout."""
from importlib import metadata, resources
from pathlib import Path
import subprocess
import sys

import ft_tui

assert not (Path.cwd()/'src/ft_tui').exists(), 'Run outside source checkout'
version = metadata.version('ft-tui')
if len(sys.argv) > 1:
    assert version == sys.argv[1], (version, sys.argv[1])
assert 'site-packages' in str(ft_tui.__file__), ft_tui.__file__
entries = {e.name: e for e in metadata.distribution('ft-tui').entry_points if e.group == 'console_scripts'}
assert {'42tui', '42goto', '42tui-zed-lsp'} <= entries.keys()
for name in ('locales/fr.json', 'locales/es.json', 'testers.toml', 'features/cluster_map/layout.json'):
    assert resources.files('ft_tui').joinpath(name).read_bytes(), name
result = subprocess.run([sys.executable, '-c',
                         "import sys; sys.argv=['42tui', '--version']; from ft_tui.main import main; main()"],
                        capture_output=True, text=True, check=True)
assert result.stdout.strip() == f'42tui {version}', result
print(f'Installed package {version}: entry points and resources OK')
