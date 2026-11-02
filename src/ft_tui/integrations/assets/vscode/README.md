# 42TUI Activity for VS Code

This extension forwards local VS Code activity to the shared `42tui heartbeat`
command. It does not send activity over the network. Repeated events for the same
file are throttled to at most one per 30 seconds except for saves.

## Install

Use **Settings → Workspace → Editor → Install** in 42TUI. 42TUI builds a VSIX
with the absolute 42TUI path embedded, installs it with `code` or `codium` when
available, and otherwise copies the extension into the VS Code extensions
directory.

Restart or reload VS Code after installation.

## Configure

The extension resolves the executable in this order:

1. `42tui.cliPath` in VS Code settings (leave empty unless auto-detection fails).
2. `FT_TUI_EXECUTABLE`.
3. The `42tui-path.txt` file written by 42TUI into the installed extension.
4. Common install locations such as `~/.local/bin/42tui`.
5. `42tui` on `PATH`.

Open the **42TUI Activity** output channel to see executable failures. If the
extension reports a missing command, set `42tui.cliPath` to the absolute path of
the `42tui` executable.

The CLI identifies the project from the configured local project folders. Only
the project ID, editor name, event timestamp, save flag and credited duration are
stored by 42TUI; file paths are not retained.

## Development

The source is `extension.js` next to this README. Install or uninstall it through
42TUI; there is no compile step.
