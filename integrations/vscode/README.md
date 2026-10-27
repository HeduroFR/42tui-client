# 42TUI Activity for VS Code

This extension forwards local VS Code activity to the shared `42tui heartbeat` command. It does
not send activity over the network. VS Code reports active-file changes, edits to the active file,
and saves; repeated events for the same file are throttled to at most one per two minutes except
for saves.

## Configure

1. Install 42TUI and make sure `42tui` is on VS Code's `PATH`.
2. In 42TUI, configure the local path for the project you want to track.
3. Open this folder in VS Code, run `npm install`, then run `npm run compile`.
4. Press `F5` in VS Code to launch the Extension Development Host with the integration enabled.

If the executable is not on VS Code's `PATH`, set `42tui.cliPath` in VS Code settings to the
absolute path of the executable. The extension passes file paths as separate process arguments;
it does not interpolate them into a shell command.

The CLI identifies the project from the configured local project folders. Only the project ID,
editor name, event timestamp, save flag, and credited duration are stored by 42TUI; file paths are
not retained.
