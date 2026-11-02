"""Install, verify, repair and remove editor integrations."""

from __future__ import annotations

from pathlib import Path

from ft_tui.features.editor_integrations.adapters.files import IntegrationFilesError, tree_files
from ft_tui.features.editor_integrations.models import (
    EDITORS,
    IntegrationResult,
    IntegrationStatus,
)


class EditorIntegrationService:
    def __init__(self, assets, editors, heartbeat, settings):
        self.assets = assets
        self.editors = editors
        self.heartbeat = heartbeat
        self.settings = settings
        self._verification: dict[str, tuple[str, str]] = {}

    def status(self, editor: str) -> IntegrationStatus:
        configured = str(self.settings.get("editor_cli_path", "") or "")
        cli_path = self.heartbeat.resolve_cli(configured)
        path = self.editors.installed_path(editor)
        manifest = self.editors.manifest(editor)
        installed_version = str(manifest["version"]) if manifest and manifest.get("version") else None
        version = self.assets.version(editor)
        state = self._state(editor, path, manifest, cli_path, version, installed_version)
        manifest_cli = str(manifest.get("cli_path") or "") if manifest else ""
        cached = self._verification.get(editor)
        verification = cached[1] if cached and cached[0] == manifest_cli else "unverified"
        return IntegrationStatus(
            editor=editor,
            state=state,
            version=version,
            installed_version=installed_version,
            path=path,
            cli_path=cli_path,
            cli_ok=cli_path is not None,
            editor_found=self.editors.editor_found(editor),
            last_event_at=self.heartbeat.last_event_at(editor),
            verification=verification,
        )

    def _state(self, editor, path, manifest, cli_path, version, installed_version) -> str:
        if path is None or not path.is_dir():
            return "not_installed"
        if manifest is None:
            return "foreign"
        if sorted(str(item) for item in manifest.get("files", [])) != tree_files(path):
            return "needs_repair"
        if cli_path is None or str(cli_path) != manifest.get("cli_path"):
            return "needs_repair"
        if installed_version != version:
            return "update_available"
        return "installed"

    def install(self, editor: str, *, force: bool = False) -> IntegrationResult:
        if editor not in EDITORS:
            raise ValueError(f"Unknown editor: {editor}")
        configured = str(self.settings.get("editor_cli_path", "") or "")
        cli_path = self.heartbeat.resolve_cli(configured)
        if cli_path is None:
            code = "cli_invalid" if configured.strip() else "cli_missing"
            detail = configured.strip() if configured.strip() else ""
            return self._result(editor, False, False, code, detail)
        try:
            self.editors.install(editor, str(cli_path), self.assets.path(editor))
        except IntegrationFilesError as error:
            detail = "" if str(error) == error.code else str(error)
            return self._result(editor, False, False, error.code, detail)
        except OSError as error:
            return self._result(editor, False, False, "install_failed", str(error))

        verification, detail = self.heartbeat.verify(cli_path, editor)
        self._verification[editor] = (str(cli_path), verification)
        if verification == "verified":
            return self._result(editor, True, True, "installed_verified", "")
        if verification == "unavailable":
            return self._result(editor, True, False, "installed_verification_unavailable", detail)
        return self._result(editor, True, False, "installed_verification_failed", detail)

    def uninstall(self, editor: str) -> IntegrationResult:
        if self.status(editor).state == "not_installed":
            return self._result(editor, False, False, "not_installed", "")
        try:
            removed = self.editors.uninstall(editor)
        except OSError as error:
            return self._result(editor, False, False, "uninstall_failed", str(error))
        if removed and self.editors.manifest(editor) is None:
            self._verification.pop(editor, None)
            return self._result(editor, False, False, "removed", "")
        return self._result(editor, True, False, "uninstall_failed", "integration files remain")

    def verify(self, editor: str) -> IntegrationResult:
        status = self.status(editor)
        if status.state == "not_installed":
            return self._result(editor, False, False, "not_installed", "")
        manifest = self.editors.manifest(editor)
        installed_cli = str(manifest.get("cli_path") or "") if manifest else ""
        configured = str(self.settings.get("editor_cli_path", "") or "")
        cli_path = self.heartbeat.resolve_cli(installed_cli or configured)
        if cli_path is None:
            self._verification[editor] = (installed_cli or configured, "failed")
            return self._result(editor, True, False, "verification_failed",
                                "The installed 42TUI path is not available")
        verification, detail = self.heartbeat.verify(cli_path, editor)
        self._verification[editor] = (str(cli_path), verification)
        if verification == "verified":
            return self._result(editor, True, True, "verified", "")
        if verification == "unavailable":
            return self._result(editor, True, False, "verification_unavailable", detail)
        return self._result(editor, True, False, "verification_failed", detail)

    def detect_cli_path(self) -> str | None:
        path = self.heartbeat.resolve_cli("")
        return str(path) if path is not None else None

    def cli_version(self, path: str) -> str | None:
        candidate = Path(path).expanduser()
        if not candidate.is_absolute() or not candidate.is_file():
            return None
        return self.heartbeat.version(candidate)

    def _result(self, editor, installed, verified, code, detail) -> IntegrationResult:
        return IntegrationResult(
            installed=installed,
            verified=verified,
            code=code,
            detail=detail,
            status=self.status(editor),
        )
