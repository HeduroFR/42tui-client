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


class WorkspaceSession:
    """Run children on a private PTY without taking over the application's terminal."""

    def __init__(self, log: BinaryIO, output, language: str = "en"):
        import threading
        import queue
        self.log, self.output, self.language = log, output, language
        self.cancelled = threading.Event()
        self.cancel_requested = False
        self.phase = "Preparing the tester…"
        self.input = queue.SimpleQueue()

    def cancel(self):
        self.cancel_requested = True
        self.cancelled.set()

    def check_cancelled(self):
        if self.cancelled.is_set():
            # Consume the interruption so finally blocks can run cleanup commands.
            self.cancelled.clear()
            raise KeyboardInterrupt

    def write(self, message):
        self.check_cancelled()
        if message in {"Preparing a disposable project copy…", "Preparing the native tester…",
                       "Building the tester image…", "Running the tester…",
                       "Checking container execution and local folder access…"}:
            self.phase = message
        # App messages bypass the PTY, so supply its usual LF-to-CRLF conversion.
        text = translate(message, self.language).replace("\r\n", "\n")
        self._output((text.replace("\n", "\r\n") + "\r\n").encode())

    def _output(self, data):
        self.log.write(data)
        self.log.flush()
        self.output(data)

    def run(self, args, *, cwd=None, env=None):
        import queue
        self.write("$ " + shlex.join(args))
        master, slave = pty.openpty()
        process = None
        completed = False
        try:
            # Match the console emulator dimensions; input remains line-oriented.
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
            process = subprocess.Popen(args, cwd=cwd, env={**(env if env is not None else os.environ), "TERM": "dumb"},
                                       stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
            os.close(slave)
            slave = None
            while True:
                self.check_cancelled()
                try:
                    while True:
                        os.write(master, self.input.get_nowait())
                except queue.Empty:
                    pass
                ready, _, _ = select.select([master], [], [], .1)
                if not ready:
                    if process.poll() is not None:
                        # A background child must not keep the tester's PTY open forever.
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        completed = True
                        break
                    continue
                try:
                    data = os.read(master, 65536)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    break
                if not data:
                    break
                self._output(data)
            while True:
                self.check_cancelled()
                try:
                    code = process.wait(timeout=.1)
                    completed = True
                    break
                except subprocess.TimeoutExpired:
                    pass
            if code:
                raise subprocess.CalledProcessError(code, args)
        finally:
            if process is not None:
                if not completed:
                    # The unreaped leader keeps its process-group identity reserved.
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                process.wait()
            os.close(master)
            if slave is not None:
                os.close(slave)
