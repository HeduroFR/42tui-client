"""Locate the 42TUI CLI and verify editor heartbeats without recording time."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select

from ft_tui.db.models import ActivityHeartbeat, Project


VERSION_PATTERN = re.compile(r"42tui (\d+\.\d+\.\d+)\s*")


class HeartbeatProbe:
    """Resolve the installed CLI and run a non-writing heartbeat check."""

    def __init__(self, session_factory, *, which=shutil.which, run=subprocess.run, detection=None):
        self.session_factory = session_factory
        self.which = which
        self.run = run
        self.detection = detection

    def resolve_cli(self, configured: str) -> Path | None:
        if configured.strip():
            explicit = Path(configured).expanduser()
            if explicit.is_absolute() and explicit.is_file() and self.version(explicit):
                return explicit
            return None
        candidates: list[Path] = []
        detection = self.detection
        if detection is None:
            from ft_tui.features.installation.adapters.runtime import detect_installation

            detection = detect_installation
        try:
            installation = detection()
        except (OSError, ValueError):
            installation = None
        if installation is not None:
            candidates.append(Path(installation.executable))
        candidates.append(Path(sys.executable).parent / "42tui")
        found = self.which("42tui")
        if found:
            candidates.append(Path(found))
        for candidate in candidates:
            if candidate.is_absolute() and candidate.is_file() and self.version(candidate):
                return candidate
        return None

    def version(self, path: Path) -> str | None:
        try:
            result = self.run(
                [str(path), "--version"], capture_output=True, text=True, timeout=5, check=False
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        match = VERSION_PATTERN.fullmatch(result.stdout or "")
        return match.group(1) if match else None

    def verify(self, path: Path, editor: str) -> tuple[str, str]:
        try:
            with self.session_factory() as session:
                roots = list(
                    session.scalars(
                        select(Project.local_path)
                        .where(Project.local_path.is_not(None))
                        .order_by(Project.id)
                    )
                )
        except Exception:
            return "unavailable", "configured projects could not be read"
        root = next((Path(value).expanduser() for value in roots if Path(value).expanduser().is_dir()), None)
        if root is None:
            return "unavailable", "no configured project folder exists"
        try:
            result = self.run(
                [str(path), "heartbeat", "--file", str(root / ".42tui-heartbeat-check"),
                 "--editor", editor, "--dry-run", "--quiet"],
                capture_output=True, text=True, timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return "failed", str(error)
        if result.returncode == 0:
            return "verified", ""
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        return "failed", detail[0] if detail else f"exit code {result.returncode}"

    def last_event_at(self, editor: str) -> datetime | None:
        with self.session_factory() as session:
            return session.scalar(
                select(func.max(ActivityHeartbeat.occurred_at)).where(ActivityHeartbeat.editor == editor)
            )
