# Editor integrations

Each adapter sends local editor events to the shared `42tui heartbeat` CLI. Configure each
project's local path in 42TUI, then install the adapter for your editor. Adapters report active
file changes, edits, and saves with editor-appropriate throttling. Files in unnamed or special
buffers are ignored. Paths are passed as process arguments rather than interpolated into shell
commands.

## Vim

Copy `vim/plugin/ft_tui.vim` into `~/.vim/pack/plugins/start/ft_tui/plugin/`, or source it
from your `vimrc`. Vim 8.2+ is recommended for asynchronous jobs and timers. Configure an
alternate executable or heartbeat interval before loading the plugin:

```vim
let g:ft_tui_command = '/path/to/42tui'
let g:ft_tui_min_interval = 30
```

## Neovim

Copy `nvim/ft_tui.lua` to `~/.config/nvim/lua/ft_tui.lua`, then initialize it from
`init.lua`:

```lua
require("ft_tui").setup({
  command = "/path/to/42tui", -- optional; defaults to 42tui on PATH
  min_interval = 30, -- seconds; optional
})
```

If 42TUI was installed in a virtual environment, use the absolute path to that environment's
`42tui` executable. Both adapters are local-only and do not require API credentials or network
access.

## VS Code

See [the VS Code extension guide](vscode/README.md) for installing and running the extension in
an Extension Development Host.

## Zed

See [the standalone Zed integration guide](zed/README.md). It uses a small native Zed language
server extension and the local 42TUI heartbeat CLI.
