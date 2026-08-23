"""Was neu ist — der Verlauf, wie ihn der Nutzer liest (Bauplan §37.2).

Die Punkte je Version stehen in ``changelog/<sprache>.md``, eine Datei je
Sprache. Sie sind **keine** Liste der Änderungen: Von über zweihundert Commits
bleiben ein Dutzend Zeilen, und die Auswahl ist die Arbeit — ein Punkt gehört
hinein, wenn jemand ihn beim Benutzen merkt.

**Warum das im Kern steht und nicht im Bauwerkzeug.** Bis 0.1.3 las nur
``tools/make_download.py`` diese Dateien: Es schrieb den Abschnitt der neuen
Version in ``website/version.json``, und die Anwendung bekam ihn von dort — also
**nur beim Update und nur vom Server**. Wer wissen wollte, was die eigene
Fassung gebracht hat, fand es nirgends.

Seit dem reist der Ordner im Paket mit, und dieselbe Leseroutine bedient beide
Seiten: die Anwendung unter *Hilfe → Neuerungen* und das Bauwerkzeug beim
Veröffentlichen. Zwei Umsetzungen wären der Weg zu einem Verlauf, der sich
unterscheidet, je nachdem wer ihn liest.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

import app
from app.i18n import SOURCE_LANGUAGE, get_language

#: Eine Versionsüberschrift: ``## 0.1.4``.
SECTION: Final = re.compile(r"^##\s+(\S+)\s*$")

#: Ein Punkt darunter: ``- Solidon sieht beim Start nach …``. Das Sternchen
#: gilt mit, weil Markdown es zulässt und der Bestand beides kennt.
BULLET: Final = re.compile(r"^[-*]\s+(.*\S)\s*$")


@dataclass(frozen=True, slots=True)
class Entry:
    """Eine Version mit dem, was sie gebracht hat."""

    version: str
    points: tuple[str, ...]


def folder() -> Path:
    """Wo die Dateien liegen — im Paket wie in der Entwicklung.

    Im Paket liegen sie neben dem ``app``-Paket (die Spec legt sie dorthin),
    in der Entwicklung eine Ebene darüber im Repository. Geprüft wird der
    erste Ort zuerst: Ein ausgeliefertes Paket hat kein Repository um sich.
    """
    inside = Path(app.__file__).parent / "changelog"
    return inside if inside.is_dir() else Path(app.__file__).parent.parent / "changelog"


def file_for(language: str) -> Path:
    return folder() / f"{language}.md"


@lru_cache(maxsize=8)
def _read(language: str) -> tuple[Entry, ...]:
    """Alle Abschnitte einer Sprachdatei, in der Reihenfolge der Datei.

    Gehalten, weil der Dialog sie bei jedem Öffnen erfragt und eine Datei mit
    zweihundert Zeilen dafür nicht zweimal gelesen werden muss. Der Inhalt
    ändert sich zur Laufzeit nicht — er reist im Paket mit.
    """
    file = file_for(language)
    try:
        text = file.read_text(encoding="utf-8")
    except OSError:
        return ()
    found: list[Entry] = []
    version = ""
    points: list[str] = []
    for line in text.splitlines():
        heading = SECTION.match(line)
        if heading:
            if version:
                found.append(Entry(version=version, points=tuple(points)))
            version, points = heading.group(1), []
            continue
        if line.startswith("#"):
            # Eine andere Überschrift beendet den Abschnitt — der Kopf der
            # Datei erklärt, was hineingehört, und ist kein Punkt.
            if version:
                found.append(Entry(version=version, points=tuple(points)))
            version, points = "", []
            continue
        if not version:
            continue
        bullet = BULLET.match(line)
        if bullet:
            points.append(bullet.group(1))
    if version:
        found.append(Entry(version=version, points=tuple(points)))
    return tuple(entry for entry in found if entry.points)


def history(language: str = "") -> tuple[Entry, ...]:
    """Der ganze Verlauf in der Sprache des Fensters, sonst in der Quellsprache.

    Ein Rückfall und keine Lücke: Wer auf Italienisch arbeitet und für dessen
    Sprache noch nichts geschrieben wurde, liest lieber den deutschen Satz als
    eine Überschrift ohne Inhalt darunter — dieselbe Regel wie beim
    Update-Hinweis (``updates.Release.points``).
    """
    chosen = language or get_language()
    return _read(chosen) or _read(SOURCE_LANGUAGE)


def points_for(version: str, language: str = "") -> tuple[str, ...]:
    """Die Punkte genau einer Version, oder nichts."""
    for entry in history(language):
        if entry.version == version:
            return entry.points
    return ()


def forget_cache() -> None:
    """Vergisst die gehaltenen Dateien — für die Suite, die sie unterschiebt."""
    _read.cache_clear()
