"""Build the Zed extension wasm and copy it into the packaged assets."""

from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "integrations" / "zed"
TARGET = ROOT / "src" / "ft_tui" / "integrations" / "assets" / "zed"


def main() -> int:
    result = subprocess.run(
        ["cargo", "build", "--release", "--locked", "--target", "wasm32-wasip2"],
        cwd=SOURCE,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr.strip() or "cargo build failed", file=sys.stderr)
        return result.returncode
    wasm = SOURCE / "target" / "wasm32-wasip2" / "release" / "zed_42tui_activity.wasm"
    if not wasm.is_file():
        print(f"missing build output: {wasm}", file=sys.stderr)
        return 1
    TARGET.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(wasm, TARGET / "extension.wasm")
    shutil.copyfile(SOURCE / "extension.toml", TARGET / "extension.toml")
    print(f"Wrote {TARGET / 'extension.wasm'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
