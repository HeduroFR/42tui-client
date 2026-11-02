# Editor integrations

42TUI records local coding activity through a small editor integration. The
integration sends the active file path, editor name, event time and save flag to
`42tui heartbeat`, which maps the path to a configured project and credits the
time. File paths are not stored and file contents are never read.

## Install from 42TUI

1. Open **Settings → Workspace → Editor**.
2. Set **42TUI executable** if the automatic path is wrong. Leave it empty to
   auto-detect `42tui`.
3. Choose your editor and select **Install**.
4. Select **Check heartbeat** to confirm the executable and project resolution.
   A project folder must exist for verification.

The same card shows the installed version, update and repair state, the last
editor event and the installed editor executable. **Uninstall** removes only the
files 42TUI installed.

During first-run onboarding, the **Editor & style** step offers the same install
for the selected editor. **Skip** leaves the rest of setup untouched.

## Supported editors

| Editor | Installed location | Notes |
| --- | --- | --- |
| Vim | `~/.vim/pack/42tui/start/ft_tui/` | Loaded by Vim's native package support; no `vimrc` change. |
| Neovim | `$XDG_DATA_HOME/nvim/site/pack/42tui/start/ft_tui/` (or `~/.local/share/...`) | Native `pack/*/start`, also active under LazyVim and SupraVIM. A manual `require("ft_tui").setup()` is respected. |
| VS Code | `~/.vscode/extensions/42tui.42tui-activity-0.1.0/` or the CLI's profile directory | Installed from a generated VSIX when `code`/`codium` is available, otherwise copied into the extension directory. |
| Zed | Zed's `extensions/installed/42tui-activity/` | Uses the prebuilt extension wasm. Zed must be restarted after install. |

The installer never edits `vimrc`, `init.lua`, `settings.json` or project files.
Reinstalling is idempotent. An unmarked directory at the target is left alone and
reported as a foreign installation.

## Executable path

GUI-launched editors often do not inherit `~/.local/bin`. 42TUI injects the
absolute executable path into the files it owns:

- Vim: generated `ft_tui_config.vim` next to the plugin.
- Neovim: generated `lua/ft_tui_config.lua`.
- VS Code: `42tui-path.txt` inside the extension package.
- Zed: found on the editor's `PATH`; Settings shows the required
  `42tui-zed-lsp` path.

If the path moves, the card reports **Needs repair**. Set the new path, save, and
select **Repair**.

## Heartbeat checks and privacy

**Check heartbeat** runs `42tui heartbeat --dry-run` against a configured project.
It resolves the project exactly like a real event but writes no heartbeat and
credits no time. Without a project folder the check reports that verification is
unavailable instead of claiming success.

Only the project ID, editor name, event timestamp, save flag and credited
duration are stored. File paths are not retained.

## Development

Packaged assets live in `src/ft_tui/integrations/assets/`. The VS Code extension
is plain JavaScript and the VSIX is generated at install time. Zed's wasm is
built from `integrations/zed/`:

```sh
python release/build_zed_extension.py
```

See `integrations/zed/README.md` for the dev-extension fallback.
