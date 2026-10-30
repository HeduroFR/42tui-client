"""Packaged tester definitions and atomic, user-owned TOML overrides."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


RECIPE_FILES = {"supra": ("supra.Dockerfile", "supra.sh")}


def project_slug(slug: str) -> str:
    return slug.lower().removeprefix("42cursus-")


@dataclass(frozen=True)
class Tester:
    id: str
    name: str
    projects: tuple[str, ...]
    platforms: tuple[str, ...]
    repository: str
    ref: str
    context: str
    command: tuple[str, ...]
    architectures: tuple[str, ...] = ("amd64",)
    result_file: str | None = None
    runtime: str = "docker"
    prepare: tuple[tuple[str, ...], ...] = ()
    recipe: str | None = None
    interactive_input: bool = True

    @property
    def image(self) -> str:
        identity = json.dumps((self.repository, self.ref, self.context)).encode()
        if self.recipe:
            for name in RECIPE_FILES[self.recipe]:
                identity += files("ft_tui").joinpath("tester_images", name).read_bytes()
        digest = hashlib.sha256(identity).hexdigest()[:16]
        return f"42tui/{self.id}:{self.ref[:12]}-{digest}"

    def image_for(self, architecture: str) -> str:
        # Keep existing amd64 installations; native images need separate tags.
        return self.image if architecture == "amd64" else f"{self.image}-{architecture}"


@dataclass(frozen=True)
class TesterCatalog:
    testers: tuple[Tester, ...]
    error: str = ""

    def for_project(self, slug: str, platform: str | None = None) -> tuple[Tester, ...]:
        platform = platform or sys.platform
        return tuple(tester for tester in self.testers
                     if project_slug(slug) in tester.projects and platform in tester.platforms)


def user_catalog_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base).expanduser() if base else Path.home() / ".config") / "42tui/testers.toml"


def _entries(content: str) -> dict[str, Tester | None]:
    document = tomllib.loads(content)
    if set(document) - {"testers"} or not isinstance(document.get("testers"), list):
        raise ValueError("Expected [[testers]] entries")
    result: dict[str, Tester | None] = {}
    fields = {"id", "name", "projects", "platforms", "repository", "ref", "context", "command", "enabled",
              "architectures", "result_file", "runtime", "prepare", "recipe", "interactive_input"}
    for entry in document["testers"]:
        if not isinstance(entry, dict) or set(entry) - fields:
            raise ValueError("Unknown tester field")
        identifier = entry.get("id", "")
        if (not isinstance(identifier, str) or len(identifier) > 63
                or not re.fullmatch(r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*", identifier)):
            raise ValueError("Invalid tester id")
        if identifier in result:
            raise ValueError(f"Duplicate tester id: {identifier}")
        if not isinstance(entry.get("enabled", True), bool):
            raise TypeError(f"{identifier}: enabled must be a boolean")
        if not entry.get("enabled", True):
            result[identifier] = None
            continue
        for key in ("name", "repository", "ref", "context"):
            if not isinstance(entry.get(key), str) or not entry[key].strip() or "\x00" in entry[key]:
                raise ValueError(f"{identifier}: missing or invalid {key}")
        for key in ("projects", "platforms", "command"):
            value = entry.get(key)
            if (not isinstance(value, list) or not value
                    or any(not isinstance(item, str) or not item.strip() or "\x00" in item for item in value)):
                raise ValueError(f"{identifier}: {key} must be a nonempty list of strings")
        if set(entry["platforms"]) - {"linux", "darwin"}:
            raise ValueError(f"{identifier}: supported platforms are linux and darwin")
        runtime = entry.get("runtime", "docker")
        if runtime not in {"docker", "native"}:
            raise ValueError(f"{identifier}: runtime must be docker or native")
        recipe = entry.get("recipe")
        if "recipe" in entry and (recipe != "supra" or runtime != "docker"):
            raise ValueError(f"{identifier}: recipe must name a bundled Docker recipe")
        prepare = entry.get("prepare", [])
        if (not isinstance(prepare, list) or any(not isinstance(command, list) or not command
                or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in command) for command in prepare)):
            raise ValueError(f"{identifier}: prepare must contain nonempty command lists")
        if runtime == "docker" and prepare:
            raise ValueError(f"{identifier}: prepare is only supported for native testers")
        architectures = entry.get("architectures", ["amd64"])
        if (not isinstance(architectures, list) or not architectures
                or any(not isinstance(item, str) or item not in {"amd64", "arm64"} for item in architectures)
                or len(set(architectures)) != len(architectures)):
            raise ValueError(f"{identifier}: architectures must list amd64 and/or arm64 without duplicates")
        if recipe and entry["context"] != ".":
            raise ValueError(f"{identifier}: Supra recipes require the repository root")
        if not re.fullmatch(r"[0-9a-fA-F]{40}", entry["ref"]):
            raise ValueError(f"{identifier}: ref must be a full Git commit SHA")
        url = urlparse(entry["repository"])
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment or url.query:
            raise ValueError(f"{identifier}: repository must be an HTTPS Git URL")
        context = PurePosixPath(entry["context"])
        if context.is_absolute() or ".." in context.parts or entry["context"].startswith("-"):
            raise ValueError(f"{identifier}: context must stay inside the repository")
        if any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", slug) for slug in entry["projects"]):
            raise ValueError(f"{identifier}: invalid project slug")
        interactive_input = entry.get("interactive_input", True)
        if not isinstance(interactive_input, bool):
            raise ValueError(f"{identifier}: interactive_input must be a boolean")
        result_file = entry.get("result_file")
        if "result_file" in entry and (
                not isinstance(result_file, str) or not result_file.strip() or "\x00" in result_file
                or PurePosixPath(result_file).is_absolute() or not PurePosixPath(result_file).parts
                or any(part in {"..", ".git"} for part in PurePosixPath(result_file).parts)):
            raise ValueError(f"{identifier}: result_file must be a file inside the project copy")
        result[identifier] = Tester(
            identifier, entry["name"], tuple(project_slug(slug) for slug in entry["projects"]),
            tuple(entry["platforms"]), entry["repository"], entry["ref"].lower(),
            entry["context"], tuple(entry["command"]), tuple(architectures), result_file, runtime, tuple(tuple(command) for command in prepare), recipe, interactive_input,
        )
    return result


def load_catalog(path: Path | None = None) -> TesterCatalog:
    bundled = _entries(files("ft_tui").joinpath("testers.toml").read_text(encoding="utf-8"))
    path = path if path is not None else user_catalog_path()
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return TesterCatalog(tuple(item for item in bundled.values() if item is not None))
    except (OSError, UnicodeError) as error:
        return TesterCatalog(tuple(item for item in bundled.values() if item is not None), f"{path}: {error}")
    try:
        bundled.update(_entries(content))
    except (ValueError, TypeError) as error:
        return TesterCatalog(tuple(item for item in bundled.values() if item is not None), f"{path}: {error}")
    return TesterCatalog(tuple(item for item in bundled.values() if item is not None))
