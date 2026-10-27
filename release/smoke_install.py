"""Disposable installer integration using the candidate wheel, before PyPI publication.

Resolve the candidate wheel through a local find-links directory; run actual uv and
all installation, ownership, verification and shell-update logic. Never run in a
real user's HOME: caller supplies a throwaway account/container/home.
"""
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from unittest.mock import patch

root = Path(__file__).resolve().parents[1]
wheel = Path(sys.argv[1]).resolve()
uv = sys.argv[2]
module = runpy.run_path(str(root/'distribution/install.py'))
real_run = subprocess.run


def run(args, **kwargs):
    if 'tool' in args and 'install' in args:
        args = [*args, '--find-links', str(wheel.parent), '--override', str(constraints)]
    return real_run(args, **kwargs)


with tempfile.TemporaryDirectory(prefix='42tui-smoke-') as temporary:
    home = Path(temporary)
    constraints = home/'candidate-constraints.txt'
    constraints.write_text('ft-tui==' + wheel.name.split('-')[1] + '\n')
    env = {'HOME': str(home), 'USERPROFILE': str(home), 'XDG_DATA_HOME': str(home/'data'),
           'XDG_CONFIG_HOME': str(home/'config'), 'UV_TOOL_DIR': str(home/'tools'),
           'UV_TOOL_BIN_DIR': str(home/'bin'),
           'PATH': os.pathsep.join(p for p in os.environ.get('PATH', '').split(os.pathsep)
                                  if not any((Path(p)/name).exists() for name in
                                             ('42tui', '42tui.exe', '42goto', '42goto.exe', '42tui-zed-lsp', '42tui-zed-lsp.exe')))}
    with patch.dict(os.environ, env), patch('subprocess.run', run):
        assert module['main'](['--uv', uv, '--non-interactive', '--no-font']) == 0
        assert module['main'](['--uv', uv, '--non-interactive', '--no-font', '--version', wheel.name.split('-')[1]]) == 0
        sentinel = home/'data/42tui/preserved.txt'
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text('local application data')
        if os.name == 'nt':
            real_run([uv, '--no-config', 'tool', 'uninstall', 'ft-tui'], check=True)
        else:
            # Expose only uv, not siblings from its original bin directory:
            # CI may have installed another 42tui next to the uv executable.
            manager_bin = home/'manager-bin'
            manager_bin.mkdir()
            (manager_bin/'uv').symlink_to(Path(uv).resolve())
            uninstall_env = dict(os.environ, PATH=str(manager_bin) + os.pathsep + os.environ['PATH'])
            for _ in range(2):
                real_run(['sh', str(root/'distribution/uninstall.sh')], env=uninstall_env, check=True)
        assert sentinel.read_text() == 'local application data'
        assert not (home/'bin/42tui').exists()
print('Fresh/repeat/exact-version installer and uninstall passed using candidate wheel')
