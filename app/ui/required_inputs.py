"""Pflichtangaben eines Operationsdialogs, ohne die nichts gerechnet wird.

Ohne Pflichtwahl keine Vorschau (``oberflaeche.md``): Die Auswertung hielte
sicher an, und das Band nennte eine Absage, bevor jemand etwas gewählt hat.
Das galt für Bild und Datei (RM-775); ein leerer Pflichttext lief dagegen in
die Vorschau, und *Schriftzug als Körper* zeigte beim Öffnen „Ohne Text gibt
es nichts anzulegen.“ als Absage (FD-134). Hier steht die eine Frage für alle
drei: welche Angabe fehlt, und der Satz, der sie nennt.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Final

from app.core.registry import OperationSpec, inactive_dependency
from app.core.types import ParamSpec
from app.i18n import tr

#: Feldarten, deren Wert eine Projektquelle nennt, die erst gewählt werden muss.
CHOSEN_SOURCES: Final = ("image", "source")


def is_required_text(entry: ParamSpec) -> bool:
    """Ein Pflichtfeld aus freiem Text — der Name beim Umbenennen, der Schriftzug."""
    return (
        entry.kind == "str"
        and bool(entry.required)
        and not entry.internal
        and not entry.choices
        and not entry.targets_feature
    )


def missing_input(spec: OperationSpec, values_of: Callable[[], Mapping[str, Any]]) -> str:
    """Die erste Pflichtangabe ohne Wert als Satz für den gesperrten Knopf, sonst leer.

    Ein Bild oder eine Datei nennt den Knopf, der sie holt; ein Text nennt
    sein Feld. Eine Angabe, deren Bedingung gerade nicht gilt
    (``depends_on``), fehlt nicht. Ein Text aus Leerzeichen ist kein Text.
    Die Werte werden nur gelesen, wo es eine solche Angabe gibt.
    """
    schema = spec.params.spec()
    wanted = [
        entry
        for entry in schema
        if not entry.internal
        and entry.required
        and (entry.kind in CHOSEN_SOURCES or is_required_text(entry))
    ]
    if not wanted:
        return ""
    values = values_of()
    for entry in wanted:
        if inactive_dependency(entry, schema, values) is not None:
            continue
        if entry.kind in CHOSEN_SOURCES:
            if values.get(entry.name):
                continue
            choose = tr("Bild wählen …") if entry.kind == "image" else tr("Datei wählen …")
            return tr("{name}: {value}", name=entry.title, value=choose)
        if is_required_text(entry) and not str(values.get(entry.name) or "").strip():
            return tr("Erst „{field}“ ausfüllen, dann übernehmen.", field=entry.title)
    return ""
