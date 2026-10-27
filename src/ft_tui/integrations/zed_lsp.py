"""Minimal stdio LSP for Zed that forwards local document activity to 42TUI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlparse


HEARTBEAT_INTERVAL_SECONDS = 30


def _read_message(stream: BinaryIO) -> dict[str, object] | None:
    """Read one Content-Length framed JSON-RPC message from a binary stream."""
    headers: dict[str, str] = {}
    while True:
        line = stream.readline()
        if not line:
            return None
        if line in (b"\r\n", b"\n"):
            break
        key, separator, value = line.decode("ascii", errors="replace").partition(":")
        if separator:
            headers[key.strip().casefold()] = value.strip()
    try:
        length = int(headers["content-length"])
    except (KeyError, ValueError):
        return None
    payload = stream.read(length)
    if len(payload) != length:
        return None
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _write_message(message: dict[str, object]) -> None:
    payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def _file_path(uri: object) -> Path | None:
    if not isinstance(uri, str):
        return None
    parsed = urlparse(uri)
    if parsed.scheme != "file":
        return None
    path = unquote(parsed.path)
    if os.name == "nt" and len(path) > 2 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return Path(path)


class ActivityForwarder:
    """Throttle editor notifications and forward them through the local CLI."""

    def __init__(self) -> None:
        self.last_file: Path | None = None
        self.last_sent_at = 0.0
        self.executable = os.environ.get("FT_TUI_EXECUTABLE", "42tui")

    def send(self, uri: object, *, is_write: bool = False) -> None:
        path = _file_path(uri)
        if path is None or not path.is_absolute():
            return
        now = time.time()
        if (
            not is_write
            and path == self.last_file
            and now - self.last_sent_at < HEARTBEAT_INTERVAL_SECONDS
        ):
            return

        self.last_file = path
        self.last_sent_at = now
        command = [
            self.executable,
            "heartbeat",
            "--file",
            str(path),
            "--editor",
            "zed",
            "--timestamp",
            str(now),
            "--quiet",
        ]
        if is_write:
            command.append("--write")
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            threading.Thread(target=self._finish_process, args=(process,), daemon=True).start()
        except OSError as error:
            # Keep stdout reserved for LSP framing; failure is non-fatal to editing.
            print(f"42TUI heartbeat could not start: {error}", file=sys.stderr, flush=True)
            return

    @staticmethod
    def _finish_process(process: subprocess.Popen[bytes]) -> None:
        _stdout, stderr = process.communicate()
        if process.returncode and stderr:
            message = stderr.decode("utf-8", errors="replace").strip()
            if message:
                print(f"42TUI heartbeat failed: {message}", file=sys.stderr, flush=True)


def _document_uri(params: object) -> object:
    if not isinstance(params, dict):
        return None
    document = params.get("textDocument")
    return document.get("uri") if isinstance(document, dict) else None


def serve() -> None:
    forwarder = ActivityForwarder()
    while message := _read_message(sys.stdin.buffer):
        method = message.get("method")
        params = message.get("params")
        request_id = message.get("id")

        if method == "initialize":
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "capabilities": {
                            "textDocumentSync": {
                                "openClose": True,
                                "change": 1,
                                "save": {"includeText": False},
                            }
                        },
                        "serverInfo": {"name": "42tui-activity", "version": "0.1.0"},
                    },
                }
            )
        elif method == "textDocument/didOpen":
            forwarder.send(_document_uri(params))
        elif method == "textDocument/didChange":
            forwarder.send(_document_uri(params))
        elif method == "textDocument/didSave":
            forwarder.send(_document_uri(params), is_write=True)
        elif method == "shutdown":
            _write_message({"jsonrpc": "2.0", "id": request_id, "result": None})
        elif method == "exit":
            return
        elif request_id is not None:
            _write_message(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": "Method not supported"},
                }
            )


def main() -> None:
    """Run the Zed LSP over stdio."""
    serve()
