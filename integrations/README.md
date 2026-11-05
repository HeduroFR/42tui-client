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
files 42TUI installed. If you added unrelated files inside the integration
folder, they are moved to a sibling `<folder>-unrelated` directory instead of
being deleted.

During first-run onboarding, the **Editor & style** step offers the same install
for the selected editor. **Skip** leaves the rest of setup untouched.

## Supported editors

| Editor | Installed location | Notes |
| --- | --- | --- |
| Vim | `~/.vim/pack/42tui/start/ft_tui/` | Loaded by Vim's native package support; no `vimrc` change. |
| Neovim | Config: `after/plugin/42tui/`; data: `site/pack/42tui/start/ft_tui/` | A managed loader supports standard Neovim and Lazy.nvim startup; see below. |
| VS Code | `~/.vscode/extensions/42tui.42tui-activity-0.1.0/` or the CLI's profile directory | Installed from a generated VSIX when `code`/`codium` is available, otherwise copied into the extension directory. |
| Zed | Zed's `extensions/installed/42tui-activity/` | Uses the prebuilt extension wasm. Zed must be restarted after install. |

The installer never edits `vimrc`, `init.lua`, `settings.json` or project files.
Reinstalling is idempotent. An unmarked directory at the target is left alone and
reported as a foreign installation.

## Neovim startup and migration

After you explicitly select **Install**, 42TUI installs a small loader at
`$XDG_CONFIG_HOME/$NVIM_APPNAME/after/plugin/42tui/ft_tui_loader.lua` and keeps
the existing module at
`$XDG_DATA_HOME/$NVIM_APPNAME/site/pack/42tui/start/ft_tui/`. Defaults are
`~/.config`, `~/.local/share` and `nvim`, respectively. Launch 42TUI with the
same environment as your target Neovim configuration; `NVIM_APPNAME` can also
select a nested relative name. The installer does not start Neovim or run your
configuration.

[Neovim's startup sequence](https://neovim.io/doc/user/starting/#load-plugins)
loads `after/plugin` scripts. [Lazy.nvim's startup sequence](https://lazy.folke.io/usage)
disables native package loading but explicitly sources `after/plugin`. The loader
adds the managed module directory to `runtimepath` and uses the existing setup
guard. The native entry point and repeated loader sourcing therefore share one
set of heartbeat autocommands and one pending heartbeat timer. Existing manual
`require("ft_tui").setup({...})` options are preserved when setup runs before
the automatic entry point. With Lazy.nvim, configure overrides after
`require("lazy").setup(...)` has made the module available.

Existing native-only installs show **Needs repair**. Select **Repair** (or
**Update**) to add the loader using the existing ownership manifest; the module
is upgraded in place. Both directories use 42TUI manifests, updates are atomic
per directory, and unmarked or unrelated files are never overwritten. If an
operation fails, retry **Repair** or **Uninstall**. Uninstall removes the owned
loader before the module and preserves unrelated files using the convention
above. Restart Neovim after installation, repair or removal; already running
instances retain their loaded code. Remove any manually added `require` calls
yourself when uninstalling.

**Installed** describes files on disk. A verified heartbeat CLI check is a dry
run, not proof that Neovim loaded the integration. **Runtime activity: unknown**
means no editor event has been observed. A last-event timestamp is historical
evidence for the editor, not confirmation of the current process or selected
configuration.

The module still targets Neovim 0.8+; `NVIM_APPNAME` requires a Neovim version
that supports it (0.9+). Automatic loading relies on the config's `after` directory
remaining on `runtimepath` and on plugin startup running. Configurations using
`--clean`, `--noplugin`, `-u NONE`, disabling plugins without a replacement
startup sequence, or removing that runtime directory are outside this guarantee.
Other custom plugin-manager configurations have not all been validated.

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

Neovim startup tests use temporary config/data directories and stub `jobstart`
and deferred heartbeat callbacks, so no activity is recorded or transmitted.
To include a real Lazy.nvim startup, point at a disposable checkout:

```sh
FT_TUI_TEST_LAZY_NVIM=/tmp/lazy.nvim .venv/bin/python release/regression_scopes.py --scope editor-integrations
```

Without Neovim or that checkout, the corresponding startup tests report a skip.
