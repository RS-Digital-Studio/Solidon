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
import logging
from pathlib import Path

from app.i18n import SOURCE_LANGUAGE, install_catalog

#: Über die Standardbibliothek und nicht über ``app.core.log``: ``i18n`` hängt
#: an nichts, der Kern benutzt es — nicht umgekehrt (``app/CLAUDE.md``). Der
#: Name liegt unter der Anwendungswurzel ``app``, an der der Kern seinen
#: Dateihandler einhängt; das Protokoll landet also an derselben Stelle.
_log = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"


def catalog_path(language: str) -> Path:
    return LOCALES_DIR / f"{language}.json"


def available_languages() -> tuple[str, ...]:
    """Die Quellsprache und jede Sprache, für die ein Katalog daliegt.

    Eine feste Liste stand hier lange als ``SUPPORTED_LANGUAGES`` — und mit
    ihr die Aussicht, dass eine neue Sprache an fünf Stellen nachgetragen
    werden muss, von denen man vier vergisst: Auswahl im Erstlauf,
    Einstellungen, Einsammler, Handbuch, Bilder. Jetzt ist der Katalog selbst
    die Anmeldung. Wer eine Sprache hinzufügt, legt eine Datei ab; alles
    andere findet sie.

    Vollständig muss sie sein, bevor sie eingecheckt wird — dafür sorgt
    ``tests/test_translations.py``, das jede gefundene Datei prüft und nicht
    nur die englische.
    """
    found = sorted(path.stem for path in LOCALES_DIR.glob("*.json"))
    return tuple(dict.fromkeys((SOURCE_LANGUAGE, *found)))


def read_catalog(language: str) -> dict[str, str]:
    """Liest eine Katalogdatei; fehlende Dateien haben schlicht keine Einträge.

    Und beschädigte auch: Das war die einzige ungesicherte Dateilesung des
    Gebiets — ein halb geschriebenes ``fr.json`` hieß roher
    ``JSONDecodeError`` beim Start (Gesamtreview L-8). Die freundliche
    Richtung ist die Quellsprache; der Grund steht im Protokoll.
    """
    path = catalog_path(language)
    if not path.is_file():
        return {}
    try:
        data: dict[str, str] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        _log.warning("catalog %s unreadable, staying with the source language: %s", path, problem)
        return {}
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
    if language not in available_languages():
        _log.warning("unknown language %s, staying on %s", language, SOURCE_LANGUAGE)
        return
    entries = {key: value for key, value in read_catalog(language).items() if value}
    install_catalog(language, entries)
    _log.info("installed %d translations for %s", len(entries), language)
