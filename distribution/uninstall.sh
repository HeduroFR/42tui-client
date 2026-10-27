#!/bin/sh
# 42TUI production uninstaller: curl -fsSL https://tui.42wip.in/uninstall.sh | sh
set -eu

fail() { printf '42TUI: %s\n' "$*" >&2; exit 1; }
case "${1:-}" in
    --help|-h)
        printf '%s\n' 'Usage: uninstall.sh' 'Remove the uv-managed 42TUI application; keep local data, fonts and Python tooling.'
        exit 0;;
esac
[ "$#" -eq 0 ] || fail "Unknown argument: $1"
case "$(uname -s)" in
    Linux|Darwin) :;;
    *) fail 'Supported targets: Linux and macOS. On Windows use uv tool uninstall ft-tui.';;
esac
: "${HOME:?A home directory is required}"
if [ -x "$HOME/.local/bin/uv" ]; then
    uv_bin="$HOME/.local/bin/uv"
else
    uv_bin=$(command -v uv || true)
fi
if [ -n "$uv_bin" ]; then
    tools_dir=$("$uv_bin" --no-config tool dir) || fail 'Could not locate the uv tool directory.'
    if [ -f "$tools_dir/ft-tui/uv-receipt.toml" ]; then
        "$uv_bin" --no-config tool uninstall ft-tui || fail 'Uninstall failed; local application data was preserved.'
        printf '%s\n' '42TUI uninstalled. Local data, account credentials, fonts, shell PATH and shared Python/uv installations were preserved.'
        exit 0
    fi
fi
if command -v 42tui >/dev/null 2>&1; then
    fail '42tui exists outside the uv tool installation. For pipx, use pipx uninstall ft-tui; other installations must be removed with their original manager.'
fi
printf '%s\n' 'No uv-managed 42TUI installation found. Nothing to remove; local data was preserved.'
