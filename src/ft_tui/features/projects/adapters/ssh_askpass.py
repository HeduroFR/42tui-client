"""Per-operation OpenSSH askpass bridge; credentials stay in memory."""
from concurrent.futures import CancelledError
from contextlib import contextmanager
from contextvars import ContextVar
import hmac
import json
import os
from pathlib import Path
import secrets
import shlex
import socket
import sys
from tempfile import TemporaryDirectory
from threading import Event, Thread


ssh_environment: ContextVar[dict[str, str]] = ContextVar('ssh_environment', default={})


@contextmanager
def ssh_askpass(prompt):
    if prompt is None:
        yield
        return
    with TemporaryDirectory(prefix='42tui-askpass-') as directory, socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(0.2)
        secret = secrets.token_hex(32)
        stopped = Event()

        def serve():
            while not stopped.is_set():
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    continue
                except OSError:
                    return
                with connection:
                    connection.settimeout(60)
                    try:
                        with connection.makefile('rwb') as stream:
                            request = json.loads(stream.readline(65536))
                            if not isinstance(request, dict) or not hmac.compare_digest(request.get('token', ''), secret):
                                continue
                            answer = prompt(str(request.get('prompt', '')), bool(request.get('confirm')))
                            stream.write(json.dumps(answer).encode() + b'\n')
                            stream.flush()
                    except (OSError, ValueError, TypeError, RuntimeError, CancelledError):
                        continue

        helper = Path(directory) / ('askpass.cmd' if os.name == 'nt' else 'askpass')
        module = str(Path(__file__).resolve())
        if os.name == 'nt':
            helper.write_text(f'@echo off\n"{sys.executable}" "{module}" %*\n')
        else:
            helper.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(module)} "$@"\n')
            helper.chmod(0o700)
        thread = Thread(target=serve, daemon=True)
        thread.start()
        token = ssh_environment.set({
            'SSH_ASKPASS': str(helper), 'SSH_ASKPASS_REQUIRE': 'force',
            'DISPLAY': os.environ.get('DISPLAY') or '42tui',
            'FT_TUI_ASKPASS_PORT': str(listener.getsockname()[1]),
            'FT_TUI_ASKPASS_TOKEN': secret,
        })
        try:
            yield
        finally:
            ssh_environment.reset(token)
            stopped.set()
            listener.close()
            thread.join(timeout=0.3)


def main():
    """Executed by OpenSSH, outside the TUI process."""
    try:
        with socket.create_connection(('127.0.0.1', int(os.environ['FT_TUI_ASKPASS_PORT'])), timeout=60) as connection:
            with connection.makefile('rwb') as stream:
                request = {'token': os.environ['FT_TUI_ASKPASS_TOKEN'],
                           'prompt': sys.argv[1] if len(sys.argv) > 1 else 'SSH authentication',
                           'confirm': os.environ.get('SSH_ASKPASS_PROMPT') == 'confirm'}
                stream.write(json.dumps(request).encode() + b'\n')
                stream.flush()
                answer = json.loads(stream.readline(65536))
        if not isinstance(answer, str):
            return 1
        sys.stdout.write(answer + '\n')
        return 0
    except (KeyError, OSError, ValueError):
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
