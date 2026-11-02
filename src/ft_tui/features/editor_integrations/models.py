"""Editor integration status and results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

EDITORS = ("vim", "nvim", "vscode", "zed")


@dataclass(frozen=True)
class IntegrationStatus:
    editor: str
    state: str
    version: str | None
    installed_version: str | None
    path: Path | None
    cli_path: Path | None
    cli_ok: bool
    editor_found: bool
    last_event_at: datetime | None
    verification: str


@dataclass(frozen=True)
class IntegrationResult:
    installed: bool
    verified: bool
    code: str
    detail: str
    status: IntegrationStatus
