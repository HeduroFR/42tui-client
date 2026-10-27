"""Unix terminal handoff with a PTY, live output and persistent transcripts."""

from __future__ import annotations

import errno
import fcntl
import os
import pty
import select
import shlex
import signal
import struct
import subprocess
import sys
import termios
import tty
from pathlib import Path
from typing import BinaryIO

from ft_tui.i18n import translate


class TerminalSession:
    def __init__(self, log: BinaryIO, language: str = "en") -> None:
        self.log = log
        self.language = language

    def write(self, message: str) -> None:
        message = translate(message, self.language)
        data = (message + "\n").encode()
        self.log.write(data)
        self.log.flush()
        sys.stdout.write(message + "\n")
        sys.stdout.flush()

    def run(self, args: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
        self.write("$ " + shlex.join(args))
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            # Also useful for headless diagnostics; no shell or hidden input.
            result = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
            self.log.write(result.stdout)
            self.log.flush()
            sys.stdout.buffer.write(result.stdout)
            sys.stdout.flush()
            if result.returncode:
                raise subprocess.CalledProcessError(result.returncode, args)
            return
        input_fd = sys.stdin.fileno()
        original = termios.tcgetattr(input_fd)
        size = fcntl.ioctl(input_fd, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        pid, master = pty.fork()
        if pid == 0:
            try:
                if cwd is not None:
                    os.chdir(cwd)
                os.execvpe(args[0], args, env if env is not None else os.environ)
            except (OSError, ValueError) as error:
                os.write(2, (str(error) + "\n").encode())
                os._exit(127)
        previous_resize = signal.getsignal(signal.SIGWINCH)

        def resize(*_args):
            dimensions = fcntl.ioctl(input_fd, termios.TIOCGWINSZ, size)
            fcntl.ioctl(master, termios.TIOCSWINSZ, dimensions)
            os.killpg(pid, signal.SIGWINCH)

        completed = False
        try:
            fcntl.ioctl(master, termios.TIOCSWINSZ, size)
            signal.signal(signal.SIGWINCH, resize)
            tty.setraw(input_fd)
            while True:
                ready, _, _ = select.select([master, input_fd], [], [])
                if master in ready:
                    try:
                        data = os.read(master, 65536)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        break
                    if not data:
                        break
                    self.log.write(data)
                    self.log.flush()
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                if input_fd in ready:
                    data = os.read(input_fd, 4096)
                    if not data:
                        raise KeyboardInterrupt
                    # Ctrl+C stops the client and lets the caller remove its container.
                    if b"\x03" in data:
                        raise KeyboardInterrupt
                    os.write(master, data)
            _, status = os.waitpid(pid, 0)
            completed = True
        finally:
            termios.tcsetattr(input_fd, termios.TCSADRAIN, original)
            signal.signal(signal.SIGWINCH, previous_resize)
            if not completed:
                # Ensure an interrupted subprocess never outlives the handoff.
                # A single signal avoids signalling a group that disappeared
                # between SIGTERM and SIGKILL (EPERM on macOS).
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                os.waitpid(pid, 0)
            os.close(master)
        code = os.waitstatus_to_exitcode(status)
        if code:
            raise subprocess.CalledProcessError(code, args)


def wait_for_key(message: str) -> None:
    print(message, flush=True)
    if not sys.stdin.isatty():
        return
    descriptor = sys.stdin.fileno()
    original = termios.tcgetattr(descriptor)
    try:
        tty.setraw(descriptor)
        os.read(descriptor, 1)
    finally:
        termios.tcsetattr(descriptor, termios.TCSADRAIN, original)
