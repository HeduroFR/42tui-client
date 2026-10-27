# 42TUI

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

Restart your terminal, then run:

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

Configure your project's local folder in 42TUI, then enable shell navigation.
Add the matching line to your shell config:

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

## Project testers

Configure an existing local project folder, open **Testers** (or press `t` in
Projects), then choose **Run Francinette**. The same button handles setup and retries.

On Linux, an accessible Docker engine with BuildKit support must already be
available. Check with `docker info` from your normal account. 42TUI can start an
existing rootless user service; it does not install system packages, start system
services, change socket permissions or use `sudo`. If Docker is missing or access
is denied at school, ask school staff to make an engine available.

On macOS, the setup button can install Docker Desktop in `~/Applications` without
using Homebrew or a privileged installer. Keep Docker's user-level defaults:
user CLI tools, no default system socket and no privileged port mapping. Accept
Docker's terms if prompted, then testing continues automatically. Existing local
or remote Docker contexts remain supported. See Docker's
[Mac permission requirements](https://docs.docker.com/desktop/setup/install/mac-permission-requirements/).

The bundled tester builds its pinned source inside Docker, so host Git and C
compiler installation are unnecessary. Custom tester clone URLs without a `.git`
suffix retain support through an existing Git installation; use an HTTPS `.git`
clone URL to build those without host Git.

## Everyday use

Press `?` or `F1` for shortcuts. `F2` opens Projects, `F3` opens Notes, and `F5`
opens Settings.

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
