"""Confined, atomic installation of editor integration files."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path, PurePosixPath


MANIFEST = "42tui-integration.json"


class IntegrationFilesError(Exception):
    """A refused or failed integration filesystem operation."""

    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(detail or code)
        self.code = code


def read_manifest(target: Path) -> dict[str, object] | None:
    try:
        value = json.loads((target / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or not isinstance(value.get("editor"), str) or not isinstance(
        value.get("files"), list
    ):
        return None
    return value


def _confined(path: Path, base: Path) -> bool:
    try:
        return path.resolve(strict=False).is_relative_to(base.resolve(strict=False))
    except OSError:
        return False


def tree_files(root: Path) -> list[str]:
    """Relative paths of regular files and symlinks, excluding the manifest."""
    return sorted(
        path.relative_to(root).as_posix()
        for path in Path(root).rglob("*")
        if path.is_file() or path.is_symlink()
        if path.name != MANIFEST
    )


def _files(root: Path) -> list[str]:
    return tree_files(root)


def install_tree(
    source: Path,
    target: Path,
    manifest: dict[str, object],
    *,
    base: Path,
    extra: dict[str, str] | None = None,
) -> None:
    """Copy an asset tree into a marked target, never overwriting foreign files."""
    target = Path(target)
    base = Path(base)
    if target.is_symlink():
        raise IntegrationFilesError("target_symlink")
    if not _confined(target, base) or target.resolve(strict=False) == base.resolve(strict=False):
        raise IntegrationFilesError("outside_base")

    for relative in extra or {}:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise IntegrationFilesError("outside_base")

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = target.parent / f".{target.name}.tmp-{uuid.uuid4().hex}"
    backup = target.parent / f".{target.name}.old-{uuid.uuid4().hex}"
    moved = False
    try:
        shutil.copytree(source, stage)
        for relative, content in (extra or {}).items():
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8")
        payload = dict(manifest)
        payload["files"] = _files(stage)
        (stage / MANIFEST).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        if target.exists():
            current = read_manifest(target)
            if current is None:
                raise IntegrationFilesError("target_foreign")
            expected = {str(item) for item in current["files"]}
            if not set(_files(target)).issubset(expected):
                raise IntegrationFilesError("target_modified")
            os.replace(target, backup)
            moved = True
        os.replace(stage, target)
    except IntegrationFilesError:
        if moved and not target.exists():
            os.replace(backup, target)
        raise
    except OSError as error:
        if moved and not target.exists():
            os.replace(backup, target)
        raise IntegrationFilesError("write_failed", str(error)) from error
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        if target.exists():
            shutil.rmtree(backup, ignore_errors=True)


def remove_tree(target: Path, base: Path) -> bool:
    """Remove manifest-owned files only, leaving unrelated files untouched."""
    target = Path(target)
    base = Path(base)
    if target.is_symlink() or not target.is_dir():
        return False
    if not _confined(target, base) or target.resolve(strict=False) == base.resolve(strict=False):
        return False
    manifest = read_manifest(target)
    if manifest is None:
        return False
    expected = {str(item) for item in manifest.get("files", [])}
    actual = set(_files(target))
    if not expected:
        return False
    try:
        for relative in sorted(expected & actual):
            (target / relative).unlink(missing_ok=True)
        (target / MANIFEST).unlink(missing_ok=True)
    except OSError:
        return False
    for directory in sorted(
        (path for path in target.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass
    try:
        target.rmdir()
    except OSError:
        pass
    return True
