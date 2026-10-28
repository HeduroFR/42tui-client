"""Shared per-user installer. Uses only Python's standard library."""
import argparse
import ctypes
import hashlib
import io
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from urllib.request import urlopen

COMMANDS = ('42tui', '42goto', '42git', '42tui-zed-lsp')
PYTHON = '>=3.12,<3.15'
STABLE = r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)'
# Upstream release asset digest, v3.5.1 (2026-08-21).
# https://github.com/ryanoasis/nerd-fonts/releases/expanded_assets/v3.5.1
FONT_URL = 'https://github.com/ryanoasis/nerd-fonts/releases/download/v3.5.1/JetBrainsMono.tar.xz'
FONT_SHA256 = '04d5e8f903693f9dd13e16f867e994834e681eb3c72c0d337a770dcda09010cf'
FONT_FACES = {f'JetBrainsMonoNerdFontMono-{style}.ttf' for style in ('Regular', 'Bold', 'Italic', 'BoldItalic')}


def download(url: str) -> bytes:
    with urlopen(url, timeout=120) as response:
        if not response.url.startswith('https://'):
            raise ValueError('Refusing a non-HTTPS download redirect')
        data = response.read(20 * 1024 * 1024 + 1)
    if len(data) > 20 * 1024 * 1024:
        raise ValueError('Font archive exceeds download limit')
    return data


def font_directory() -> Path:
    if sys.platform == 'win32':
        return Path(os.environ['LOCALAPPDATA'])/'Microsoft/Windows/Fonts'
    if sys.platform == 'darwin':
        return Path.home()/'Library/Fonts'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home()/'.local/share'))/'fonts/42tui'


def register_windows_fonts(paths: list[Path]) -> None:
    import winreg
    key_name = r'Software\Microsoft\Windows NT\CurrentVersion\Fonts'
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_name) as key:
        for path in paths:
            name = path.stem.replace('JetBrainsMonoNerdFontMono-', 'JetBrainsMono Nerd Font Mono ') + ' (TrueType)'
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(path))
            if not ctypes.windll.gdi32.AddFontResourceExW(str(path), 0, 0):
                raise OSError(f'Windows could not load {path.name}; sign out and try again')
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 2, 5000, ctypes.byref(result))


def install_font(target: Path, *, system: str | None = None) -> None:
    system = system or platform.system()
    if all((target/name).is_file() for name in FONT_FACES):
        if system == 'Windows':
            register_windows_fonts([target/name for name in sorted(FONT_FACES)])
        print(f'Nerd Font already present in {target}')
        return
    content = download(FONT_URL)
    if hashlib.sha256(content).hexdigest() != FONT_SHA256:
        raise ValueError('Font SHA-256 verification failed')
    selected = {}
    with tarfile.open(fileobj=io.BytesIO(content), mode='r:xz') as archive:
        for member in archive.getmembers():
            # Select known basenames, never extract paths or links from an archive.
            name = member.name
            if not member.isfile() or '/' in name.removeprefix('./') or member.size > 10 * 1024 * 1024:
                continue
            name = Path(name).name
            if name in FONT_FACES or name.lower() in ('ofl.txt', 'license', 'license.txt'):
                selected[name] = archive.extractfile(member).read()
    if 'JetBrainsMonoNerdFontMono-Regular.ttf' not in selected or not any(n not in FONT_FACES for n in selected):
        raise ValueError('Font archive is missing its regular face or license')
    target.mkdir(parents=True, exist_ok=True)
    for name, data in selected.items():
        destination = target/name
        if destination.exists():
            continue
        with tempfile.NamedTemporaryFile(dir=target, delete=False) as temporary:
            staged = Path(temporary.name)
            temporary.write(data)
        try:
            staged.chmod(0o644)
            staged.replace(destination)
        finally:
            staged.unlink(missing_ok=True)
    if system == 'Windows':
        register_windows_fonts([target/n for n in selected if n in FONT_FACES])
    elif system == 'Linux' and shutil.which('fc-cache'):
        subprocess.run(['fc-cache', '-f', str(target)], check=True)
    print(f'Nerd Font installed in {target}')


def choose_font() -> bool:
    if os.environ.get('SSH_CONNECTION') or os.environ.get('WSL_DISTRO_NAME'):
        return False
    try:
        source = 'CONIN$' if os.name == 'nt' else '/dev/tty'
        destination = 'CONOUT$' if os.name == 'nt' else '/dev/tty'
        with open(source, 'r') as reader, open(destination, 'w') as writer:
            writer.write('Install JetBrainsMono Nerd Font for this user? [y/N] ')
            writer.flush()
            return reader.readline().strip().lower() in ('y', 'yes')
    except OSError:
        return False


def stable(value: str) -> str:
    if not re.fullmatch(STABLE, value):
        raise argparse.ArgumentTypeError('Expected a stable version such as 0.2.0')
    return value


def configure_shell_path(bin_dir: Path, shell: str) -> Path:
    """Maintain a shell block without executing or replacing user configuration."""
    home = Path.home()
    directory = Path(os.environ.get('ZDOTDIR') or home).expanduser() if shell == 'zsh' else home
    rc = directory / f'.{shell}rc'
    target = rc.resolve()
    with target.open(newline='') if target.exists() else io.StringIO() as stream:
        content = stream.read()
    begin, end = '# >>> 42TUI shell setup >>>', '# <<< 42TUI shell setup <<<'
    lines = content.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == begin]
    ends = [i for i, line in enumerate(lines) if line.rstrip('\r\n') == end]
    if starts or ends:
        if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
            raise ValueError(f'{rc} has an incomplete or duplicate 42TUI block; leaving it unchanged')
        content = ''.join(lines[:starts[0]] + lines[ends[0] + 1:])
    block = [begin + '\n']
    for path in dict.fromkeys((home/'.local/bin', bin_dir)):
        value = shlex.quote(str(path))
        block.append(f'case ":$PATH:" in\n    *:{value}:*) ;;\n    *) export PATH={value}:"$PATH" ;;\nesac\n')
    # Keep manual shell functions and remain quiet after the application is removed.
    block.append('if ! typeset -f 42goto >/dev/null 2>&1 && command -v 42goto >/dev/null 2>&1; then\n')
    if shell == 'zsh':
        block.append('    if ! typeset -f compdef >/dev/null 2>&1; then\n'
                     '        autoload -Uz compinit\n        compinit -i\n    fi\n')
    block.append(f'    eval "$(command 42goto --shell-init {shell})"\nfi\n{end}\n')
    updated = content + ('\n' if content and not content.endswith('\n') else '') + ''.join(block)
    directory.mkdir(parents=True, exist_ok=True)
    # Replace the symlink's target atomically, retaining existing permissions.
    staged = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=target.parent, newline='', delete=False) as stream:
            staged = Path(stream.name)
            stream.write(updated)
        if target.exists():
            staged.chmod(target.stat().st_mode & 0o777)
        staged.replace(target)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)
    return rc


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Install or upgrade 42TUI using uv, without administrator rights.')
    parser.add_argument('--uv', default='uv', help=argparse.SUPPRESS)
    parser.add_argument('--version', type=stable, help='install an exact stable package version')
    fonts = parser.add_mutually_exclusive_group()
    fonts.add_argument('--font', dest='font', action='store_true', help='install the optional Nerd Font')
    fonts.add_argument('--no-font', dest='font', action='store_false', help='skip font installation')
    parser.set_defaults(font=None)
    parser.add_argument('--non-interactive', action='store_true', help='skip optional prompts')
    args = parser.parse_args(argv)
    uv = [args.uv, '--no-config']

    def run(*command):
        result = subprocess.run([*uv, *command], capture_output=True, text=True)
        if result.returncode:
            raise ValueError(result.stderr.strip() or f'uv {command[0]} failed')
        return result.stdout.strip()

    try:
        bin_dir = Path(run('tool', 'dir', '--bin'))
        tools = Path(run('tool', 'dir'))
        receipt_file = tools/'ft-tui/uv-receipt.toml'
        receipt = tomllib.loads(receipt_file.read_text()) if receipt_file.exists() else {}
        tool = receipt.get('tool', {})
        if any(r.get('editable') or r.get('path') or r.get('git') or r.get('url')
               for r in tool.get('requirements', [])):
            raise ValueError('Existing uv tool uses a development source; uninstall it explicitly before migrating.')
        owned = {Path(e['install-path']).absolute() for e in tool.get('entrypoints', [])}
        for command in COMMANDS:
            filename = command + ('.exe' if os.name == 'nt' else '')
            candidates = [bin_dir/filename]
            on_path = shutil.which(command)
            if on_path:
                candidates.append(Path(on_path))
            for candidate in candidates:
                expected = tools/'ft-tui'/('Scripts' if os.name == 'nt' else 'bin')/filename
                managed = candidate.absolute() in owned and expected.is_file()
                if managed and os.name == 'nt':
                    managed = candidate.is_file() and candidate.read_bytes() == expected.read_bytes()
                elif managed:
                    managed = candidate.is_symlink() and candidate.resolve() == expected.resolve()
                if os.path.lexists(candidate) and not managed:
                    raise ValueError(f'{candidate} belongs to another installation. For pipx, run '
                                     '`pipx uninstall ft-tui` first; preserve any editable development checkout.')
        package = 'ft-tui' + (f'=={args.version}' if args.version else '')
        # No --force: uv must also reject executable conflicts found during installation.
        subprocess.run([*uv, 'tool', 'install', '--python', PYTHON,
                                 '--default-index', 'https://pypi.org/simple', '--prerelease', 'disallow',
                                 '--upgrade', '--reinstall', package], check=True)
        executable = bin_dir/('42tui.exe' if os.name == 'nt' else '42tui')
        verification = subprocess.run([str(executable), '--version'], check=True, capture_output=True, text=True)
        found = re.fullmatch(r'42tui (' + STABLE + ')', verification.stdout.strip())
        if not found or (args.version and found.group(1) != args.version):
            raise ValueError('Installed CLI version verification failed')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f'42TUI installation failed: {error}', file=sys.stderr)
        return 1
    if os.name == 'nt':
        try:
            run('tool', 'update-shell')
        except (OSError, ValueError) as error:
            print(f'Warning: PATH setup needs attention: {error}', file=sys.stderr)
    else:
        for shell in ('bash', 'zsh'):
            try:
                rc = configure_shell_path(bin_dir, shell)
                print(f'PATH and 42goto configured in {rc}.')
                print(f'Activate in {shell}: source {shlex.quote(str(rc))}')
            except (OSError, ValueError) as error:
                print(f'Warning: {shell} setup needs attention: {error}. '
                      f'Add {bin_dir} to PATH and add '
                      f'`eval "$(command 42goto --shell-init {shell})"` to your rc file.', file=sys.stderr)
    print(f'Installed {verification.stdout.strip()} at {executable}')
    print(f'Executable directory: {bin_dir}. Restart your terminal if it is not on PATH.')
    if os.name == 'nt':
        print('Windows support is experimental. Use Windows Terminal; WSL follows the Linux instructions.')
    requested_font = args.font if args.font is not None else (False if args.non_interactive else choose_font())
    if requested_font:
        try:
            install_font(font_directory())
        except (OSError, ValueError, tarfile.TarError, subprocess.CalledProcessError) as error:
            print(f'Warning: optional font setup failed: {error}', file=sys.stderr)
    print('Select JetBrainsMono Nerd Font Mono in your terminal settings after font installation.')
    print('With SSH/WSL, install and select the font on the machine running your terminal.')
    print('Upgrade: uv tool upgrade ft-tui | Uninstall (preserves app data): uv tool uninstall ft-tui')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
