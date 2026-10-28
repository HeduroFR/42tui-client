# 42TUI

> [!NOTE]
> **About this project**
>
> 42TUI is a side project I build alongside my 42 cursus. It has two goals:
>
> 1. **Learn to integrate AI workflows** into the production of a real project.
>    The current version (Python) is written with AI assistance.
> 2. **Learn Rust** by rewriting 42TUI entirely in Rust, **by hand, without any
>    AI coding agent**.
>
> The Rust rewrite starts once 42TUI reaches **420 monthly active users** for
> two consecutive months. An active user is a distinct connected 42 account
> that used 42TUI at least once during the month.
>
> From then on, the Python version is frozen: no new features, only fixes for
> security issues and breakages (such as 42 API changes), until the Rust
> version reaches the same level of features.
>
> Using 42TUI, reporting bugs and sharing it with your peers is what moves
> the rewrite forward.

Your 42 projects, notes, and coding activity in the terminal. Connect your
42 account, track time with editor plugins, and jump to project folders with
`42goto`.

## Features

- Browse projects, read subjects, open your editor, and run supported testers.
- Keep project notes and coding activity locally, available offline.
- Track coding time with plugins for Vim, Neovim, VS Code, and Zed.
- Jump to local projects with `42goto`, with shell completion.
- Follow account progress, manage correction slots, and explore your campus's
  cluster map.
- Follow friends and join club conversations and events.

Account and campus features require a connected 42 account and available data.
Some project testers require Docker.

## Install and launch

For Linux (glibc) and macOS, on x86_64 or ARM64:

```sh
curl -fsSL https://tui.42wip.in/install.sh | sh
```

You can [inspect the installer](https://tui.42wip.in/install.sh) first. It needs
`curl`, internet access, and a writable home directory. It installs `uv` and
Python 3.12 if needed, without administrator rights.

The installer adds a managed block at the end of both `~/.bashrc` and
`${ZDOTDIR:-$HOME}/.zshrc`, configuring PATH and `42goto` navigation and
completion. Reinstalling updates that block without duplicating it.

Open a new terminal, or run the matching `source` command printed by the
installer, then launch:

```sh
42tui
```

## Connect your 42 account

1. Choose **Connect 42 account** during setup, or open **Settings → Profile**
   with `F5`.
2. Choose **Connect / reconnect**, then sign in and approve access in your browser.
   If no browser opens, use **Copy login link** to open it yourself.
3. Return to 42TUI and finish setup: projects folder, editor, theme, and language.

Your project list loads after connection. To change cursus, open
**Settings → Curriculum → Default cursus**. A connected 42 account is required
to finish first-run setup. Once setup is complete, saved projects and local notes
remain available offline.

Your password stays with 42; device credentials use your OS credential store.

## `42goto`

Configure your project's local folder in 42TUI. The Linux/macOS installer
enables shell navigation automatically for Bash and Zsh. For other installation
methods, add the matching line to your shell config:

```sh
# Zsh: ~/.zshrc, after compinit
eval "$(command 42goto --shell-init zsh)"

# Bash: ~/.bashrc
eval "$(command 42goto --shell-init bash)"
```

Restart your shell, then jump to a project:

```sh
42goto libft
42goto          # Use the active or most recently tracked project
```

Press `Tab` to complete project slugs. Local folders must exist. If `42goto`
cannot choose a project automatically, pass its name or slug.

## Editor plugins

Configure each project's local folder in 42TUI, then install your editor's plugin:

- [Vim](integrations/README.md#vim)
- [Neovim](integrations/README.md#neovim)
- [VS Code](integrations/vscode/README.md) — development extension setup
- [Zed](integrations/zed/README.md) — development extension setup

The plugins call `42tui heartbeat` locally as you work. Make sure your editor
can find `42tui` on its `PATH`, or set the executable path in the plugin.
Tracking needs no account connection; file contents are not read and file paths
are not retained.

## Everyday use

Press `?` or `F1` for shortcuts. `F2` opens Projects, `F3` opens Notes, and `F5`
opens Settings.

Automatic updates check for a new stable release before the TUI opens on supported
unpinned uv/pipx installations. When an update is available, 42TUI installs it and
starts the updated version. Offline checks or failed updates still allow the
installed version to launch. Disable this in **Settings → Automatic updates**.
Pinned and development installations are maintained manually. Updates discovered
while the TUI is open install on the next launch rather than on exit.

For installer-managed installations:

```sh
42tui update
42tui uninstall
```

Uninstalling preserves local data and credentials. To disconnect first, choose
**Settings → Profile → Manage 42 account → Disconnect this device**.
Other installations should be maintained with their original package manager.

If `42tui` is not found, restart your terminal and check the installer's printed
executable directory is on your `PATH`. If icons look wrong, select a Nerd Font
in your terminal settings.

For development setup, see [CONTRIBUTING.md](CONTRIBUTING.md).
