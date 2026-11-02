"""Per-editor installation targets and commands."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

from ft_tui.features.editor_integrations.adapters.files import (
    MANIFEST,
    IntegrationFilesError,
    install_tree,
    read_manifest,
    remove_tree,
    tree_files,
)
from ft_tui.features.editor_integrations.adapters.vsix import build_vsix
from ft_tui.integrations import INTEGRATION_VERSION


VSCODE_ID = "42tui.42tui-activity"
REQUIRED_ASSETS = {
    "vim": ("plugin/ft_tui.vim",),
    "nvim": ("lua/ft_tui.lua", "plugin/ft_tui_auto.lua"),
    "vscode": ("extension.js", "package.json"),
    "zed": ("extension.toml", "extension.wasm"),
}


class EditorCommands:
    """Resolve editor directories and install the packaged integration."""

    def __init__(self, *, environ=None, home=None, which=shutil.which, run=subprocess.run):
        self.environ = dict(os.environ if environ is None else environ)
        self.home = Path(home or Path.home())
        self.which = which
        self.run = run

    def target(self, editor: str) -> Path:
        if editor == "vim":
            return self.home / ".vim" / "pack" / "42tui" / "start" / "ft_tui"
        if editor == "nvim":
            data = Path(self.environ.get("XDG_DATA_HOME") or self.home / ".local" / "share")
            return data / "nvim" / "site" / "pack" / "42tui" / "start" / "ft_tui"
        if editor == "zed":
            return self._zed_root() / "42tui-activity"
        if editor == "vscode":
            return self._vscode_roots()[0] / f"{VSCODE_ID}-{INTEGRATION_VERSION}"
        raise ValueError(f"Unknown editor: {editor}")

    def editor_found(self, editor: str) -> bool:
        from ft_tui.features.projects.adapters.editor import editor_launch

        if editor == "vscode" and self._vscode_commands():
            return True
        try:
            return editor_launch(editor, which=self.which, run=self.run)[0] is not None
        except (KeyError, OSError):
            return False

    def install(self, editor: str, cli_path: str, assets: Path) -> Path:
        assets = Path(assets)
        for relative in REQUIRED_ASSETS.get(editor, ()):
            if not (assets / relative).is_file():
                raise IntegrationFilesError("asset_missing", relative)
        manifest = {"editor": editor, "version": INTEGRATION_VERSION, "cli_path": cli_path}
        if editor == "vscode":
            return self._install_vscode(cli_path, assets, manifest)
        target = self.target(editor)
        extra = {}
        if editor == "vim":
            quoted = cli_path.replace("'", "''")
            extra["ft_tui_config.vim"] = f"let g:ft_tui_command = '{quoted}'\n"
        elif editor == "nvim":
            extra["lua/ft_tui_config.lua"] = f"return {{ command = {json.dumps(cli_path)} }}\n"
        install_tree(assets, target, manifest, base=target.parent, extra=extra)
        return target

    def uninstall(self, editor: str) -> bool:
        if editor == "vscode":
            for command in self._vscode_commands():
                self._run(command + ["--uninstall-extension", VSCODE_ID])
            removed = True
            for path in self._vscode_installed():
                if not remove_tree(path, path.parent):
                    removed = False
                elif path.exists():
                    removed = self._quarantine(path) and removed
            return removed and not any(self._vscode_installed())
        target = self.target(editor)
        removed = remove_tree(target, target.parent)
        if removed and target.exists():
            removed = self._quarantine(target)
        return removed

    def _quarantine(self, path: Path) -> bool:
        """Move unrelated leftovers aside so the target path is free again."""
        destination = path.with_name(f"{path.name}-unrelated")
        if destination.exists():
            destination = path.with_name(f"{path.name}-unrelated-{uuid.uuid4().hex[:8]}")
        try:
            path.rename(destination)
        except OSError:
            return False
        return True

    def manifest(self, editor: str) -> dict[str, object] | None:
        if editor == "vscode":
            for path in self._vscode_installed():
                manifest = read_manifest(path)
                if manifest is not None:
                    return manifest
            return None
        return read_manifest(self.target(editor))

    def installed_path(self, editor: str) -> Path | None:
        if editor == "vscode":
            return next(iter(self._vscode_installed()), None)
        target = self.target(editor)
        return target if target.is_dir() and not target.is_symlink() else None

    def _install_vscode(self, cli_path: str, assets: Path, manifest: dict[str, object]) -> Path:
        with tempfile.TemporaryDirectory() as directory:
            vsix = build_vsix(Path(directory) / "42tui-activity.vsix", assets, INTEGRATION_VERSION, cli_path)
            for command in self._vscode_commands():
                result = self._run(command + ["--install-extension", str(vsix), "--force"])
                if result is not None and result.returncode == 0:
                    installed = self._vscode_installed()
                    if installed:
                        payload = dict(manifest)
                        payload["files"] = tree_files(installed[0])
                        (installed[0] / MANIFEST).write_text(json.dumps(payload, indent=2) + "\n")
                        return installed[0]
        target = self.target("vscode")
        install_tree(assets, target, manifest, base=target.parent, extra={"42tui-path.txt": cli_path})
        return target

    def _run(self, command: list[str], *, timeout: int = 120):
        try:
            return self.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        except (OSError, subprocess.SubprocessError):
            return None

    def _vscode_roots(self) -> list[Path]:
        candidates = self._vscode_candidate_roots()
        existing = [path for path in candidates if path.is_dir()]
        return existing or [candidates[0]]

    def _vscode_candidate_roots(self) -> list[Path]:
        return [
            self.home / ".vscode" / "extensions",
            self.home / ".vscode-insiders" / "extensions",
            self.home / ".vscode-oss" / "extensions",
            self.home / ".var" / "app" / "com.visualstudio.code" / "data" / "vscode" / "extensions",
            self.home / ".var" / "app" / "com.vscodium.codium" / "data" / "codium" / "extensions",
        ]

    def _vscode_installed(self) -> list[Path]:
        found = []
        for root in self._vscode_candidate_roots():
            found.extend(sorted(root.glob(f"{VSCODE_ID}-*"), reverse=True))
        return [path for path in found if path.is_dir() and not path.is_symlink()]

    def _vscode_commands(self) -> list[list[str]]:
        commands = []
        for name in ("code", "codium"):
            executable = self.which(name)
            if executable:
                commands.append([executable])
        for bundle in (
            self.home / "Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
            Path("/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code"),
            self.home / "Applications/VSCodium.app/Contents/Resources/app/bin/codium",
            Path("/Applications/VSCodium.app/Contents/Resources/app/bin/codium"),
        ):
            if bundle.is_file():
                commands.append([str(bundle)])
        flatpak = self.which("flatpak")
        if flatpak and self._flatpak_vscode(flatpak):
            commands.append([flatpak, "run", "com.visualstudio.code"])
        return commands

    def _flatpak_vscode(self, flatpak: str) -> bool:
        result = self._run([flatpak, "info", "com.visualstudio.code"], timeout=5)
        return result is not None and result.returncode == 0

    def _zed_root(self) -> Path:
        if sys.platform == "darwin":
            base = self.home / "Library" / "Application Support" / "Zed" / "extensions"
        else:
            data = Path(self.environ.get("XDG_DATA_HOME") or self.home / ".local" / "share")
            base = data / "zed" / "extensions"
        return base / "installed"
