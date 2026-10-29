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


_ASKPASS_HELPER = r'''import json
import os
import socket
import sys


def main():
    try:
        with socket.create_connection(('127.0.0.1', int(os.environ['FT_TUI_ASKPASS_PORT'])), timeout=60) as connection:
            with connection.makefile('rwb') as stream:
                request = {'token': os.environ['FT_TUI_ASKPASS_TOKEN'],
                           'prompt': sys.argv[1] if len(sys.argv) > 1 else 'SSH authentication',
                           'confirm': os.environ.get('SSH_ASKPASS_PROMPT') == 'confirm',
                           'process': os.getppid()}
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
'''


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
        cancelled = Event()
        answers = {}
        attempted = set()

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
                            message, confirm = str(request.get('prompt', '')), bool(request.get('confirm'))
                            process = request.get('process')
                            attempt = (message, process)
                            reusable = (not confirm and message.startswith('Enter passphrase for key ')
                                        and isinstance(process, int) and process > 0)
                            cached = answers.get(message)
                            if cancelled.is_set():
                                answer = None
                            elif reusable and cached is not None and attempt not in attempted:
                                answer = cached
                            else:
                                answer = prompt(message, confirm)
                            if stopped.is_set():
                                return
                            if answer is None:
                                cancelled.set()
                                answers.clear()
                            if reusable:
                                attempted.add(attempt)
                                if answer is None:
                                    answers.pop(message, None)
                                else:
                                    answers[message] = answer
                            stream.write(json.dumps(answer).encode() + b'\n')
                            stream.flush()
                    except (OSError, ValueError, TypeError, RuntimeError, CancelledError):
                        continue

        helper = Path(directory) / ('askpass.cmd' if os.name == 'nt' else 'askpass')
        module = Path(directory) / "askpass.py"
        module.write_text(_ASKPASS_HELPER, encoding="utf-8")
        if os.name == 'nt':
            helper.write_text(f'@echo off\n"{sys.executable}" "{module}" %*\n')
        else:
            helper.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(module))} "$@"\n')
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
            answers.clear()
            attempted.clear()


def run_with_ssh_askpass(operation, prompt, *args, **kwargs):
    """Keep one in-memory authentication scope around a background Git operation."""
    with ssh_askpass(prompt):
        return operation(*args, **kwargs)
