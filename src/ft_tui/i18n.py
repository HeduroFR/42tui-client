"""Small, extensible JSON based translations for the terminal interface.

Add a ``<language>.json`` file under ``locales/`` and register its code and
display name below to add a language. Missing translations deliberately fall
back to English, so catalogs can be translated incrementally without changing
application code.
"""

from __future__ import annotations

import json
import locale
import os
import re
from functools import lru_cache
from pathlib import Path
from string import Formatter
from typing import Any

LOCALES_DIR = Path(__file__).with_name("locales")
SUPPORTED_LANGUAGES = ("en", "fr", "es")
LANGUAGE_LABELS = {"en": "English", "fr": "Français", "es": "Español"}


def detect_language() -> str:
    """Resolve the primary system locale without changing process-wide settings."""
    preferred = next(
        (os.environ[key] for key in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG") if os.environ.get(key)),
        "",
    )
    if not preferred:
        try:
            preferred = locale.getlocale()[0] or ""
        except (ValueError, TypeError):
            return "en"
    language = re.split(r"[-_.:@]", preferred.strip().lower(), maxsplit=1)[0]
    return language if language in SUPPORTED_LANGUAGES else "en"


@lru_cache(maxsize=None)
def _catalog(language: str) -> dict[str, str]:
    if language == "en":
        return {}
    path = LOCALES_DIR / f"{language}.json"
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def translate(message: str, language: str = "en") -> str:
    """Translate a UI message, falling back to its English source text."""
    if language not in SUPPORTED_LANGUAGES:
        language = "en"
    catalog = _catalog(language)
    translated = catalog.get(message)
    if translated is not None:
        return translated
    # Dynamic labels can be catalogued as templates, e.g. ``Updated {date}``.
    templates = [(key, value) for key, value in catalog.items() if "{" in key and "}" in key]
    templates = sorted(
        templates,
        key=lambda item: sum(len(literal) for literal, _, _, _ in Formatter().parse(item[0])),
        reverse=True,
    )
    for template, candidate in templates:
        if "{" not in template or "}" not in template:
            continue
        pattern_parts: list[str] = []
        fields: list[str] = []
        for literal, field, format_spec, conversion in Formatter().parse(template):
            pattern_parts.append(re.escape(literal))
            if field is not None:
                if format_spec or conversion or not field.isidentifier() or field in fields:
                    pattern_parts = []
                    break
                fields.append(field)
                pattern_parts.append(f"(?P<{field}>.+?)")
        if not pattern_parts:
            continue
        match = re.fullmatch("".join(pattern_parts), message)
        if match:
            try:
                return candidate.format(**match.groupdict())
            except (KeyError, ValueError):
                continue
    return message


def translate_renderable(content: Any, language: str) -> Any:
    """Translate plain strings while leaving Rich renderables and markup intact."""
    if isinstance(content, str):
        return translate(content, language)
    return content
