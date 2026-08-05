"""Formatversionen und die Migrationskette (Bauplan §16.2).

Gleiche Version: laden. Älter: die Kette läuft. Neuer: freundlich ablehnen,
statt die Hälfte zu laden — eine Datei aus einem neueren Release kann
Operationen enthalten, die dieses nicht kennt.

Migrationsschritte werden nie zusammengefasst (AGENTS.md, Checkliste
„Dateiformat ändern"): jeder behält seine eigene Funktion, seinen eigenen
Test und seine eigene eingecheckte Beispieldatei — so funktioniert die Kette
von der allerersten Version an weiter.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Final

from app.core.errors import ValidationError
from app.core.log import get_logger
from app.i18n import _

_log = get_logger(__name__)

#: Aktuelle Version von ``project.json``.
FORMAT_VERSION: Final = 7


@dataclass(frozen=True, slots=True)
class Step:
    """Ein Schritt der Kette, von einer Version zur nächsten."""

    from_version: int
    to_version: int
    apply: Callable[[dict[str, Any]], dict[str, Any]]


def _add_chat(data: dict[str, Any]) -> dict[str, Any]:
    """1 → 2: das Gespräch zog ins Projekt (§26.3).

    Eine Datei aus der Zeit vor dem Agenten hat schlicht kein Gespräch, und
    eine leere Liste sagt genau das. Sonst ändert sich nichts — darum ist
    dieser Schritt eine eigene Funktion und bleibt für immer eine.
    """
    data.setdefault("chat", [])
    return data


def _mark_generated_sources(data: dict[str, Any]) -> dict[str, Any]:
    """2 → 3: eine Quelle trägt, wie sie erzeugt wurde (§27, Säule B).

    Quellen aus der Zeit vor Säule B waren alle importiert oder aus Bausteinen
    gebaut, die zwei neuen Felder sind für jede von ihnen leer. Was der
    Schritt wirklich tut: das beim Hereinkommen festhalten — statt eine Datei
    zu hinterlassen, die aussieht, als hätte sie irgendwo ihren Prompt
    verloren.
    """
    for source in data.get("sources", {}).values():
        if source.get("type") == "generated":
            source.setdefault("origin", {}).setdefault("prompt", "")
    return data


def _add_print_settings(data: dict[str, Any]) -> dict[str, Any]:
    """3 → 4: womit gedruckt wird, steht im Projekt (§29).

    Eine ältere Datei hat keine eigenen Druckeinstellungen, und ``None`` sagt
    genau das: es gilt weiter, was sich aus Qualitätsstufe, Material und
    Drucker ergibt. Erst wer sie einmal ändert, hat welche — vorher wäre ein
    voller Satz Zahlen in der Datei eine Behauptung über eine Entscheidung,
    die niemand getroffen hat.
    """
    data.setdefault("print_settings", None)
    return data


def _add_transaction_changes(data: dict[str, Any]) -> dict[str, Any]:
    """4 → 5: eine Transaktion trägt auch, was keine Operation war (§15.5).

    Bis hierher konnte eine Transaktion nur Operationen enthalten; Parameter,
    Passungen, Drucker und Material standen außerhalb des Undo. Eine ältere
    Datei hat für ihre Transaktionen also nichts einzutragen — ``None`` sagt
    genau das, und ein Undo darauf verhält sich wie bisher.

    Was der Schritt *nicht* tut: die Änderungen nachträglich erfinden. Welche
    Zahl vor einer alten Transaktion galt, steht nirgends; sie zu raten hieße,
    ein Undo anzubieten, das etwas Falsches zurücklegt.
    """
    for transaction in data.get("transactions", ()):
        transaction.setdefault("changes", None)
    return data


def _keep_transaction_titles_literal(data: dict[str, Any]) -> dict[str, Any]:
    """5 → 6: ein Transaktionstitel darf eine Message-ID sein (§4.1).

    Ab Version 6 vermerkt ``title_translatable``, dass ein Titel aus dem Code
    stammt und erst bei der Anzeige in die aktive Sprache aufgelöst wird.
    Eine ältere Datei trägt den aufgelösten Text, und dabei bleibt es: ob er
    aus dem Code kam oder vom Nutzer getippt wurde, steht nirgends, und ein
    Abgleich mit dem Katalog wäre geraten — ein selbst vergebener Titel, der
    zufällig einem Katalogeintrag gleicht, würde plötzlich übersetzt. Alte
    Titel bleiben also wörtlich; strukturell ändert dieser Schritt nichts.

    Die Versionserhöhung selbst ist der Schutz: eine ältere Fassung des
    Programms kennt die Markierung nicht und würde sie beim Speichern
    stillschweigend verwerfen — sie lehnt eine Version-6-Datei stattdessen
    freundlich ab.
    """
    return data


def _keep_bores_centred(data: dict[str, Any]) -> dict[str, Any]:
    """6 → 7: die Position einer Bohrung ist ihre Mündung (§25).

    Bis Version 6 lag die *Mitte* der Bohrung auf der Position. Wer eine Fläche
    anklickte, bekam ihre Höhe eingetragen — und damit eine Bohrung, die zur
    Hälfte über dem Teil in der Luft stand und nur halb so tief ging wie
    verlangt. Ab Version 7 fängt sie an der Position an und geht von dort ins
    Material.

    Für eine alte Datei ändert das die Maße, also wird sie nicht umgedeutet:
    ihre Bohrungen bekommen ``anchor="centre"`` und rechnen weiter, wie sie
    gerechnet haben. Umzurechnen wäre nichts — die Richtung ins Material
    steckt in der Geometrie, und die liegt hier nicht vor.

    Durchgehende Bohrungen (``depth`` null) trifft es ohnehin nicht: durch ist
    durch, egal von wo aus gemessen.
    """
    for operation in data.get("ops", ()):
        if operation.get("op") == "drill_hole":
            operation.setdefault("params", {})["anchor"] = "centre"
    return data


#: Alle bekannten Schritte, älteste zuerst.
MIGRATIONS: Final[tuple[Step, ...]] = (
    Step(from_version=1, to_version=2, apply=_add_chat),
    Step(from_version=2, to_version=3, apply=_mark_generated_sources),
    Step(from_version=3, to_version=4, apply=_add_print_settings),
    Step(from_version=4, to_version=5, apply=_add_transaction_changes),
    Step(from_version=5, to_version=6, apply=_keep_transaction_titles_literal),
    Step(from_version=6, to_version=7, apply=_keep_bores_centred),
)


def migrate(
    data: dict[str, Any],
    target: int = FORMAT_VERSION,
    steps: Sequence[Step] = MIGRATIONS,
) -> dict[str, Any]:
    """Hebt ein Dokument auf ``target`` — oder sagt, warum das nicht geht."""
    version = int(data.get("format_version", 0))
    if version == target:
        return data
    if version > target:
        raise ValidationError(
            field="format_version",
            detail=_(
                "Diese Datei stammt aus einer neueren Fassung des Programms. Ein Update öffnet sie."
            ),
            constraint="too_new",
            values={"file_version": version, "supported": target},
        )

    by_source = {step.from_version: step for step in steps}
    current = data
    while version < target:
        step = by_source.get(version)
        if step is None:
            raise ValidationError(
                field="format_version",
                detail=_("Für diese Dateiversion fehlt der Umstellungsschritt."),
                constraint="no_migration",
                values={"file_version": version, "supported": target},
            )
        _log.info("migrating project from %d to %d", step.from_version, step.to_version)
        current = step.apply(dict(current))
        current["format_version"] = step.to_version
        version = step.to_version
    return current
