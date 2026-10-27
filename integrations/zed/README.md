# 42TUI Activity for Zed

This is a standalone Zed extension. It starts a small local language server that listens for
document-open, edit, and save events, then calls `42tui heartbeat`.

## Install for development

1. Install 42TUI in an environment visible to Zed:

   ```sh
   pip install -e /absolute/path/to/ft_tui
   ```

2. In 42TUI, configure the local folder for the project you want to track.
3. In Zed, run `zed: install dev extension` and select this `integrations/zed` directory.
   Zed requires Rust via rustup and automatically installs its `wasm32-wasip2` target when
   available.
4. Reload the Zed window and edit or save a file in the configured project.

The extension attaches to C, C++, Python, JavaScript, TypeScript, Rust, and other languages listed
in `extension.toml`. It runs alongside the language's normal language server.

If Zed cannot find the Python entry point on its inherited `PATH`, set the absolute executable
path in Zed settings:

```json
{
  "lsp": {
    "42tui-activity": {
      "binary": {
        "path": "/absolute/path/to/venv/bin/42tui-zed-lsp"
      }
    }
  }
}
```

The extension forwards only the active file path, editor ID, event time, and save flag to the
local CLI. The CLI uses the path to find the configured project and does not store the path or read
the file contents. No project file is modified by installation.
