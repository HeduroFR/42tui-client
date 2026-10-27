# 42TUI

A terminal workspace for École 42 students. Browse your projects, keep notes,
track coding activity, and connect your 42 account to bring your campus into
your terminal.

Your notes and activity are stored locally. Account connection is optional;
saved projects remain available when you are offline.

## Install

### Linux and macOS

Run this in your terminal:

```sh
curl -fsSL https://tui.42wip.in/install.sh | sh
```

The installer supports Linux (glibc) and macOS on x86_64 and ARM64. It needs
internet access, `curl`, and a writable home directory. It installs `uv` and
Python 3.12 if needed, without administrator rights or replacing system Python.

To inspect the script before running it, download it instead:

```sh
curl -fsSL https://tui.42wip.in/install.sh -o install-42tui.sh
less install-42tui.sh
sh install-42tui.sh
```

### Windows (experimental)

In PowerShell, download and inspect the installer, then run it:

```powershell
Invoke-WebRequest https://tui.42wip.in/install.ps1 -OutFile install-42tui.ps1
Get-Content .\install-42tui.ps1
.\install-42tui.ps1
```

Use Windows Terminal. Native Windows support is experimental.

## Launch and connect

Restart your terminal after installation, then launch:

```sh
42tui
```

1. In first-time setup, choose **Connect 42 account**. You can also connect
   later from **Settings → Profile → Connect 42 account** (`F5` opens Settings).
2. Choose **Connect / reconnect** in the connection dialog. Sign in with 42
   in your browser and approve access. Keep 42TUI open while it waits for approval.
3. If no browser opens, use **Copy login link** and open the displayed link in
   an available browser. A browser on another device works too.
4. Return to 42TUI. Once connected, it refreshes your account and project list.
   Check **Settings → Curriculum → Default cursus** if you need another cursus.
5. Finish setup by choosing your projects folder, editor, theme, and language.
   These preferences can be changed later in Settings.

42TUI does not ask you to enter your 42 password or OAuth code in the terminal.
Device credentials are stored in the operating system's credential store.
Online features use the hosted service at `https://oauth.42wip.in`; you do not
need to run a backend yourself.

To work locally, skip account connection. Connecting is needed to load your
42 projects and use account-dependent features.

## Key features

| Feature | What you can do |
| --- | --- |
| Projects | Search and filter projects, view subjects and technical details, configure local checkouts, and open projects in your editor. |
| Project testers | Run supported project testers from the workspace. Some testers require Docker. |
| Dev Log / Notes | Write and revisit notes linked to your projects. |
| Time tracking | Record coding activity through local editor integrations for Vim, Neovim, VS Code, and Zed. |
| Dashboard | See your project activity and account progress in one place. |
| Correction Slots | View and manage correction availability with your connected account. |
| Friends and clubs | Follow friends' progress and take part in club conversations, announcements, and events. |
| Cluster Map | Explore campus workstations and their availability. |

Account and campus features depend on your connection and the data available
for your account. See [editor integrations](integrations/README.md) to set up
activity tracking; configure each project's local path in 42TUI first.

## Useful shortcuts

Press `?` or `F1` in the app for the shortcut guide. Some shortcuts depend on
the current view and focused control.

| Key | Action |
| --- | --- |
| `F2` | Open Projects |
| `F3` | Open Dev Log / Notes |
| `F5` | Open Settings |
| `/` | Focus project search |
| `j` / `k` | Move down / up the project list |
| `o` | Open the selected project in your editor |
| `q` | Quit |

## Update or uninstall

For installations made with the installer:

```sh
42tui update
42tui uninstall
```

Uninstalling preserves application data and account credentials. To disconnect
your account, open **Settings → Profile → Manage 42 account** and choose
**Disconnect this device** before uninstalling.

If you installed through another package manager or from a source checkout,
maintain that installation with its original manager.

## Troubleshooting

- **`42tui` is not found:** restart your terminal. If it still fails, add the
  executable directory printed by the installer to your `PATH`.
- **Icons appear as boxes:** select a Nerd Font in your terminal settings,
  such as JetBrainsMono Nerd Font Mono. For SSH or WSL, configure the font on
  the machine displaying the terminal.
- **Account connection fails:** check your internet connection and retry from
  Settings. If the app reports that the OS credential store is unavailable,
  make sure your system keychain or credential service is available and unlocked.
- **The project list is empty:** check that your account is connected and the
  correct **Default cursus** is selected in Settings.
- **Your session expired:** reconnect when prompted, or choose **Later** to
  continue with saved projects.

Local data lives in `~/.local/share/42tui` by default, or
`$XDG_DATA_HOME/42tui` when `XDG_DATA_HOME` is set. Back it up before removing
or moving it; uninstalling does not delete it.

## Contributing

The client is open source at [HeduroFR/42tui-client](https://github.com/HeduroFR/42tui-client).
For development setup and checks, see [CONTRIBUTING.md](CONTRIBUTING.md).
Further technical documentation covers [architecture](docs/architecture.md),
[distribution](docs/distribution.md), [API compatibility](docs/api-compatibility.md),
and [HTTP simulations](postman/README.md).
