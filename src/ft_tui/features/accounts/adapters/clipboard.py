"""Copy a login link to a local desktop clipboard when available."""
import os
import shutil
import subprocess
import sys


def copy_login_link(value):
    if sys.platform == 'darwin':
        commands = [('pbcopy',)]
    elif os.environ.get('WAYLAND_DISPLAY'):
        commands = [('wl-copy',), ('xclip', '-selection', 'clipboard'), ('xsel', '--clipboard', '--input')]
    else:
        commands = [('xclip', '-selection', 'clipboard'), ('xsel', '--clipboard', '--input')]
    for command in commands:
        executable = shutil.which(command[0])
        if not executable:
            continue
        try:
            result = subprocess.run([executable, *command[1:]], input=value.encode(), stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=3, check=False)
            if result.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            continue
    return False
