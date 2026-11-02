"""Resolve the configured editor to a launcher, including Flatpak installs."""

import shutil
import subprocess

# command, terminal editor, Flatpak application id
EDITORS = {
    "nvim": ("nvim", True, "io.neovim.nvim"),
    "vim": ("vim", True, "org.vim.Vim"),
    "vscode": ("code", False, "com.visualstudio.code"),
    "zed": ("zed", False, "dev.zed.Zed"),
}


def editor_launch(name, *, which=None, run=None):
    """Return (argv prefix, terminal, missing) for the configured editor.

    A native executable wins. A Flatpak install is used only when the
    executable is not on PATH, so existing native installs keep their behavior.
    ``missing`` is ``(command, flatpak_id)`` when nothing usable was found.
    """
    which = which or shutil.which
    run = run or subprocess.run
    command, terminal, app_id = EDITORS[name]
    executable = which(command)
    if executable:
        return [executable], terminal, None
    flatpak = which("flatpak")
    if flatpak and app_id:
        try:
            installed = run(
                [flatpak, "info", app_id],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            ).returncode == 0
        except OSError:
            installed = False
        if installed:
            return [flatpak, "run", app_id], terminal, None
        return None, terminal, (command, app_id)
    return None, terminal, (command, None)
