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

## Project Git and `42git`

Configure your folder and remotes in project settings. Use the project's push
buttons, or run these commands inside its folder:

```sh
42git status     # Branch and local changes
42git pull dev   # Review a fast-forward from development
42git pull vog   # Review a fast-forward from Vogsphere
42git pull all   # Fetch both; advance only if histories are compatible
42git push dev   # Current branch → development
42git push vog   # Committed work → Vogsphere default branch
42git push all   # Both destinations, separate results
```

Each push asks for confirmation and leaves uncommitted edits untouched.
Vogsphere operations require the 42 campus network. Pull requires a clean checkout
and never stashes, resets or creates a merge commit.
**Open in file explorer** opens the project folder.
See [recovery, branch rules and failed pushes](docs/project-git.md) for details.

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

Configure an existing local project folder, find **Testers** below Registration
(or press `t` in Projects), then choose **Run Francinette**. The same button handles setup and retries.

Tester builds and cleanup run against a temporary copy of the project, excluding
Git metadata. Your original files stay in place; generated files in the copy are
discarded after the run, including after failure or cancellation. Keep the tester
log when you need its diagnostics. Allow enough temporary disk space for the copy.

Runs open an in-app tester workspace with live, scrollable output, line input,
cancellation, elapsed time and **Run again**. Close it to keep using the app,
then choose **Tester workspace** from any project's tester section to return.
**Pause output** stops automatic scrolling. Full logs are saved automatically;
**Open log folder** opens its directory in your file explorer. The output view retains recent output only.
The console interprets cursor redraws and colors on a 100-column terminal with
scrollback; narrow windows can scroll horizontally. Process completion alone does
not mean all tests passed. The workspace and saved log distinguish reported test
failures, process failures, unreadable reports and unverified results, with the
process exit code and available test counts. The bundled Francinette integration
does not yet provide a structured summary: its results remain **unverified** and
must be checked in the log. Full-screen terminal applications are not supported.

Custom definitions in `~/.config/42tui/testers.toml` (or
`$XDG_CONFIG_HOME/42tui/testers.toml`) can opt into structured results by adding
`result_file = "reports/result.json"` to their `[[testers]]` entry. The tester must
write a UTF-8 JSON report at that path under `/project` during each run:

```json
{"version": 1, "total": 4, "passed": 2, "failed": 1, "errors": 0, "skipped": 1}
```

All counts are required nonnegative integers, must add up to `total`, and must
include at least one executed test. Only a valid report with no failures/errors
and process exit code zero yields **Tests passed**. An absent, invalid, empty or
all-skipped report cannot confirm passing tests. Reports are limited to 64 KiB;
symbolic links and nonregular files are rejected. Use a dedicated report path,
not a source file: an inherited report is removed from the disposable copy before execution
to prevent stale results. The original project is unchanged. Reported success
describes that tester's checks, not official project validation.

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
