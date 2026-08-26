"""Der Filamentkatalog — benannte Filamente mit Farbe, als Vorwahl (§20).

Entstanden mit dem Filament-Konzept (26.08.2026): Farben kommen vom Kunden,
nicht aus einer Ersatzpalette. Ein Filament wird einmal angelegt — Name und
Farbe aus dem Farbwähler — und steht danach in jedem Projekt zur Wahl. Der
Katalog ist deshalb **projektübergreifend** und liegt im Einstellungsordner,
nicht in der Projektdatei; was ein Projekt wirklich benutzt, steht weiter in
seinen ``MaterialSlot``-Einträgen und reist mit der Datei.

Beliebig viele Einträge: Die Grenze je Objekt bleibt ``MAX_SLOTS`` (die
Druckerrealität des 3MF-Farbwechsels), der Katalog kennt keine — wer zwanzig
Spulen im Regal hat, legt zwanzig Filamente an und wählt je Projekt.

Die freundliche Richtung bei Fehlern wie beim Testlaufmarker: Eine kaputte
Datei kostet die Vorwahl, nie den Start; geschrieben wird atomar, damit ein
halber Katalog gar nicht erst entstehen kann.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.core.errors import ValidationError
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_config_dir
from app.i18n import _, sort_key

_log = get_logger(__name__)

#: Dateiname des Katalogs im Einstellungsordner.
CATALOGUE_FILE: Final = "filaments.json"

#: Der Farbvertrag: ``#RRGGBB``, wie ihn Ansicht und 3MF-Export lesen.
_COLOUR_PATTERN: Final = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True, slots=True)
class CatalogueFilament:
    """Ein Eintrag der Vorwahl: wie das Filament heißt und wie es aussieht."""

    name: str
    colour: str


def catalogue_path() -> Path:
    return user_config_dir() / CATALOGUE_FILE


def catalogue() -> tuple[CatalogueFilament, ...]:
    """Alle Filamente der Vorwahl, sortiert nach Name (DIN 5007-1).

    Sortiert, weil der Wähler die Liste zeigt und „ASA" nicht hinter „Über-"
    landen soll; die Anlage-Reihenfolge trägt keine Bedeutung.
    """
    try:
        data = json.loads(catalogue_path().read_text(encoding="utf-8"))
        entries = [
            CatalogueFilament(name=str(entry["name"]), colour=str(entry["colour"]))
            for entry in data
        ]
    except FileNotFoundError:
        return ()
    except (OSError, ValueError, KeyError, TypeError) as problem:
        # Die Vorwahl ist ein Komfort und kein Dokument: Eine kaputte Datei
        # kostet sie, nie den Start. Das nächste ``remember`` schreibt sie neu.
        _log.warning("filament catalogue unreadable, starting empty: %s", problem)
        return ()
    return tuple(sorted(entries, key=lambda entry: sort_key(entry.name)))


def remember(name: str, colour: str) -> CatalogueFilament:
    """Legt ein Filament an — oder gibt einem vorhandenen die neue Farbe.

    Ein Filament ist sein Name: Wer „PETG Rot" noch einmal anlegt, meint
    dasselbe Filament mit anderer Farbe, nicht ein zweites. Das ist dieselbe
    Entscheidung wie beim Slot, der seinen Namen behält.
    """
    cleaned = name.strip()
    if not cleaned:
        raise ValidationError(
            title=_("Ein Filament braucht einen Namen."),
            field="name",
            detail=_("Tragen Sie ein, wie die Spule heißt — etwa das Material und die Farbe."),
            value=name,
            constraint="empty",
        )
    if not _COLOUR_PATTERN.match(colour):
        raise ValidationError(
            title=_("Diese Farbe lässt sich nicht lesen."),
            field="colour",
            detail=_("Eine Filamentfarbe ist sechsstellig: #RRGGBB, etwa #d02020."),
            value=colour,
            constraint="colour",
        )
    entry = CatalogueFilament(name=cleaned, colour=colour.lower())
    kept = [existing for existing in catalogue() if existing.name != cleaned]
    _write([*kept, entry])
    return entry


def forget(name: str) -> bool:
    """Entfernt ein Filament aus der Vorwahl.

    ``False`` heißt: es stand keines unter diesem Namen — das Ziel ist
    erreicht, aber der Aufrufer soll es unterscheiden können (ein Knopf, der
    auf einen veralteten Eintrag zeigt, ist eine andere Lage als ein Erfolg).
    """
    kept = [entry for entry in catalogue() if entry.name != name]
    if len(kept) == len(catalogue()):
        return False
    _write(kept)
    return True


def _write(entries: list[CatalogueFilament]) -> None:
    """Atomar, wie der Testlaufmarker — ein halber Katalog sähe kaputt aus."""
    ensure_dir(user_config_dir())
    text = json.dumps(
        [{"name": entry.name, "colour": entry.colour} for entry in entries],
        ensure_ascii=False,
        indent=2,
    )
    target = catalogue_path()
    scratch = target.parent / (target.name + ".tmp")
    scratch.write_text(text, encoding="utf-8")
    scratch.replace(target)
