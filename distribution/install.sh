#!/bin/sh
# 42TUI production installer: curl -fsSL https://tui.42wip.in/install.sh | sh
set -eu

fail() { printf '42TUI: %s\n' "$*" >&2; exit 1; }
fetch() { curl --proto '=https' --tlsv1.2 -fsSL --retry 2 --connect-timeout 15 --max-time 180 "$1" -o "$2"; }
verify() {
    if command -v sha256sum >/dev/null 2>&1; then
        actual=$(sha256sum "$1"); actual=${actual%% *}
    elif command -v shasum >/dev/null 2>&1; then
        actual=$(shasum -a 256 "$1"); actual=${actual%% *}
    else fail 'sha256sum or shasum is required to verify downloads.'; fi
    [ "$actual" = "$2" ] || fail "SHA-256 verification failed for $1"
}
compatible_uv() {
    [ -n "$1" ] && [ -x "$1" ] || return 1
    "$1" --version 2>/dev/null | LC_ALL=C awk '
        $1 == "uv" && $2 ~ /^[0-9]+\.[0-9]+\.[0-9]+$/ {
            split($2,v,".")
            ok=(v[1]>0 || v[2]>13 || (v[2]==13 && v[3]>=3))
        }
        END {exit !ok}'
}
validate_args() {
    font_seen=0
    while [ "$#" -gt 0 ]; do
        case "$1" in
            --version)
                [ "$#" -ge 2 ] || fail '--version requires X.Y.Z'
                printf '%s\n' "$2" | LC_ALL=C awk '/^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$/ {ok=1} END {exit !ok}' || fail 'Expected a stable version such as 0.2.0'
                shift;;
            --font|--no-font)
                [ "$font_seen" = 0 ] || fail 'Choose only one font option'
                font_seen=1;;
            --non-interactive) :;;
            --help|-h)
                printf '%s\n' 'Usage: install.sh [--version X.Y.Z] [--font|--no-font] [--non-interactive]'
                exit 0;;
            *) fail "Unknown argument: $1";;
        esac
        shift
    done
}
main() {
    validate_args "$@"
    case "$(uname -s):$(uname -m)" in
        Linux:x86_64|Linux:aarch64|Linux:arm64|Darwin:x86_64|Darwin:arm64) :;;
        *) fail 'Supported targets: Linux (glibc) and macOS, x86_64/ARM64. Use install.ps1 for Windows.';;
    esac
    command -v curl >/dev/null 2>&1 || fail 'curl is required.'
    : "${HOME:?A writable home directory is required}"
    work=$(mktemp -d "${TMPDIR:-/tmp}/42tui-install.XXXXXXXX")
    trap 'rm -rf "$work"' EXIT HUP INT TERM
    uv_bin=$(command -v uv || true)
    if ! compatible_uv "$uv_bin"; then
        uv_bin="$HOME/.local/bin/uv"
    fi
    if ! compatible_uv "$uv_bin"; then
        printf '%s\n' '42TUI: Installing uv 0.13.3 in ~/.local/bin (no administrator rights required).'
        fetch 'https://github.com/astral-sh/uv/releases/download/0.13.3/uv-installer.sh' "$work/uv.sh"
        verify "$work/uv.sh" '320a286374f5306c4f8c807bd6a7d504dc318841457cf8f2194bee37fe02a2bd'
        UV_INSTALL_DIR="$HOME/.local/bin" UV_NO_MODIFY_PATH=1 sh "$work/uv.sh"
        uv_bin="$HOME/.local/bin/uv"
    fi
    compatible_uv "$uv_bin" || fail 'Could not obtain uv >=0.13.3 in ~/.local/bin.'
    python_bin=$("$uv_bin" --no-config python find --no-project --no-python-downloads '>=3.12,<3.15' 2>/dev/null) || {
        "$uv_bin" --no-config python install --no-bin --no-registry 3.12
        python_bin=$("$uv_bin" --no-config python find --no-project 3.12)
    }
    fetch 'https://tui.42wip.in/install.py' "$work/install.py"
    verify "$work/install.py" '1c7fadfd2bd321a764b5d2f8b6367f349e11143474db3fbe8da6ed5d94a24261'
    "$python_bin" "$work/install.py" --uv "$uv_bin" "$@"
}
main "$@"
