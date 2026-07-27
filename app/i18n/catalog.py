"""Loading language catalogs (Bauplan §4.1, §37.2).

German is the source language: its texts are the message ids, so ``de`` needs no
catalog. Every other language is a JSON file mapping message id to translation.

An empty translation means "not translated yet" — ``tests/test_translations.py``
fails on those, which is the check §37.2 asks for.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.log import get_logger
from app.i18n import SOURCE_LANGUAGE, SUPPORTED_LANGUAGES, install_catalog

_log = get_logger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"


def catalog_path(language: str) -> Path:
    return LOCALES_DIR / f"{language}.json"


def read_catalog(language: str) -> dict[str, str]:
    """Read one catalog file; missing files simply have no entries."""
    path = catalog_path(language)
    if not path.is_file():
        return {}
    data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    return data


def write_catalog(language: str, entries: dict[str, str]) -> Path:
    path = catalog_path(language)
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = {key: entries[key] for key in sorted(entries)}
    path.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def install_language(language: str) -> None:
    """Make one language available for translation."""
    if language == SOURCE_LANGUAGE:
        return
    if language not in SUPPORTED_LANGUAGES:
        _log.warning("unknown language %s, staying on %s", language, SOURCE_LANGUAGE)
        return
    entries = {key: value for key, value in read_catalog(language).items() if value}
    install_catalog(language, entries)
    _log.info("installed %d translations for %s", len(entries), language)
