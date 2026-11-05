"""Compatible revision updates for bundled testers; custom definitions stay pinned."""
from dataclasses import replace
import json
from pathlib import Path
import re
import tempfile
import time

import httpx

from ft_tui.config.settings import data_dir
from .tester_catalog import bundled_catalog

CATALOG_URL = "https://raw.githubusercontent.com/HeduroFR/42tui-client/main/tester-updates/v1.json"
CHECK_INTERVAL = 3600
MAX_BYTES = 65536


def validate_manifest(value):
    if (not isinstance(value, dict) or set(value) != {"version", "testers"}
            or type(value["version"]) is not int or value["version"] != 1
            or not isinstance(value["testers"], list) or len(value["testers"]) > 256):
        raise ValueError("Invalid tester update catalog")
    seen = set()
    for entry in value["testers"]:
        if (not isinstance(entry, dict) or set(entry) != {"id", "base", "ref"}
                or not isinstance(entry["id"], str)
                or len(entry["id"]) > 63
                or not re.fullmatch(r"[a-z][a-z0-9]*(?:[-_][a-z0-9]+)*", entry["id"])
                or any(not isinstance(entry[key], str) or not re.fullmatch(pattern, entry[key])
                       for key, pattern in (("base", r"[0-9a-f]{64}"), ("ref", r"[0-9a-f]{40}")))):
            raise ValueError("Invalid tester update entry")
        key = entry["id"], entry["base"]
        if key in seen:
            raise ValueError("Duplicate tester update entry")
        seen.add(key)


def fetch_manifest(client=None):
    if client is None:
        with httpx.Client(timeout=3, follow_redirects=False, trust_env=False) as owned:
            return fetch_manifest(owned)
    deadline = time.monotonic() + 5
    with client.stream("GET", CATALOG_URL, headers={"Accept": "application/json"}) as response:
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_bytes():
            content.extend(chunk)
            if len(content) > MAX_BYTES or time.monotonic() > deadline:
                raise ValueError("Tester update catalog exceeds size or time limit")
    value = json.loads(content)
    validate_manifest(value)
    return value


def apply_manifest(catalog, manifest):
    validate_manifest(manifest)
    revisions = {(entry["id"], entry["base"]): entry["ref"] for entry in manifest["testers"]}
    return replace(catalog, testers=tuple(
        replace(tester, ref=revisions.get((tester.id, tester.update_key), tester.ref))
        if tester.update_key else tester for tester in catalog.testers))


def refresh_catalog(catalog, terminal):
    if not any(tester.update_key for tester in catalog.testers):
        return catalog
    terminal.write("Checking for compatible tester updates…")
    cache = data_dir() / "tester-updates.json"
    manifest, checked = None, 0
    try:
        with cache.open("rb") as stored:
            content = stored.read(MAX_BYTES * 2 + 1)
        if len(content) > MAX_BYTES * 2:
            raise ValueError("Tester update cache exceeds size limit")
        value = json.loads(content)
        validate_manifest(value["manifest"])
        if type(value["checked"]) not in (int, float):
            raise ValueError("Invalid tester update timestamp")
        manifest, checked = value["manifest"], value["checked"]
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        pass
    now = time.time()
    if manifest is None or not 0 <= now - checked < CHECK_INTERVAL:
        try:
            fresh = fetch_manifest()
        except (httpx.HTTPError, OSError, ValueError, RecursionError):
            terminal.write("Tester updates are unavailable. Using the available revision.")
        else:
            manifest = fresh
            temporary = None
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=cache.parent, delete=False) as output:
                    temporary = output.name
                    json.dump({"checked": now, "manifest": manifest}, output)
                Path(temporary).replace(cache)
            except OSError:
                terminal.write("Tester update cache could not be saved. Updates still apply to this run.")
            finally:
                if temporary is not None:
                    try:
                        Path(temporary).unlink(missing_ok=True)
                    except OSError:
                        pass
    return apply_manifest(catalog, manifest) if manifest is not None else catalog


if __name__ == "__main__":
    print(json.dumps({"version": 1, "testers": [
        {"id": tester.id, "base": tester.update_key, "ref": tester.ref}
        for tester in bundled_catalog().testers]}, indent=2))
