"""Das Laden der Sprachkataloge (Bauplan §4.1, §37.2).

Deutsch ist die Quellsprache: ihre Texte sind die Message-IDs, ``de`` braucht
also keinen Katalog. Jede andere Sprache ist eine JSON-Datei von Message-ID
auf Übersetzung.

Eine leere Übersetzung heißt „noch nicht übersetzt" —
``tests/test_translations.py`` schlägt darauf an, und genau diese Prüfung
verlangt §37.2.
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
    """Liest eine Katalogdatei; fehlende Dateien haben schlicht keine Einträge."""
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
    """Stellt eine Sprache für die Übersetzung bereit."""
    if language == SOURCE_LANGUAGE:
        return
    if language not in SUPPORTED_LANGUAGES:
        _log.warning("unknown language %s, staying on %s", language, SOURCE_LANGUAGE)
        return
    entries = {key: value for key, value in read_catalog(language).items() if value}
    install_catalog(language, entries)
    _log.info("installed %d translations for %s", len(entries), language)
