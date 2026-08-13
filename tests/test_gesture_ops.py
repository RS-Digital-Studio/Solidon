"""Operationen, die viele Gesten zu einem Schritt zusammenfassen (Regel 2).

Regel 2 verbietet Geometrieänderungen außerhalb einer Op — sie verlangt aber
nicht, dass jede Nutzergeste ein eigener Schritt wird. Ein Editor darf beliebig
viele Gesten in **einen** Parameterwert sammeln, solange das Ergebnis
vollständig aus den Parametern reproduzierbar ist.

Die Skizze macht das seit P13 (§30.1): hunderte Klicks, ein Op-Eintrag. Der
Modulkopf von :mod:`app.core.sketch.edit` nennt das „Regel 2 dem Geist nach" —
der Buchstabe passte damals nicht, der Geist schon. Seit dem Konzept zur
organischen Modellierung sagt die Regel es selbst, und diese Datei ist der
Test dazu.

Geprüft wird, was einen Sammelparameter von einer beliebigen Zeichenkette
unterscheidet. Ohne diese fünf Eigenschaften wäre die Erlaubnis ein Loch in
Regel 2 statt einer Präzisierung:

* er geht in den Hash der Operation ein — sonst bliebe eine Änderung im Editor
  ohne Wirkung, weil der Cache das alte Ergebnis zurückgäbe;
* er übersteht Speichern und Laden unverändert — sonst wäre „reproduzierbar"
  auf die laufende Sitzung beschränkt;
* er ist ein reiner Datenwert, kein Objekt — sonst reiste er nicht;
* der Agent bekommt ihn nicht zu sehen (Leitprinzip 5);
* er steht hinter „Weitere Einstellungen" — er wird bearbeitet, nicht getippt.
"""

from __future__ import annotations

from typing import Final

import pytest

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY, OperationSpec, json_schema
from app.core.scene.hashing import operation_hash
from app.core.scene.serialise import document_to_data, operation_from_data, operation_to_data
from app.core.types import Operation, Profile

#: Parameterarten, die eine unbegrenzte Zahl von Gesten tragen. Wächst mit:
#: ``strokes`` (Sculpting) und ``armature`` (Skelett) kommen aus P16 und
#: unterliegen denselben Prüfungen wie die Skizze.
GESTURE_KINDS: Final[frozenset[str]] = frozenset({"sketch", "strokes", "armature"})


def gesture_params() -> list[tuple[OperationSpec, str]]:
    """Jedes Paar aus Operation und Sammelparameter, das die Anwendung
    ausliefert."""
    load_operations()
    return [
        (spec, entry.name)
        for spec in REGISTRY.all()
        for entry in spec.params.spec()
        if entry.kind in GESTURE_KINDS
    ]


def ids(case: tuple[OperationSpec, str]) -> str:
    return f"{case[0].name}.{case[1]}"


CASES: Final = gesture_params()


def test_the_registry_has_gesture_operations_at_all() -> None:
    """Ein leerer Parametersatz ließe jede Prüfung unten grün laufen, ohne
    etwas geprüft zu haben."""
    assert CASES, "keine Operation mit Sammelparameter im Register"


@pytest.mark.parametrize("case", CASES, ids=ids)
def test_the_gathered_value_reaches_the_hash(
    case: tuple[OperationSpec, str], profile: Profile
) -> None:
    """Zwei verschiedene Sammelwerte sind zwei verschiedene Ergebnisse.

    Das ist die technische Zusage hinter „vollständig aus ihren Parametern
    reproduzierbar": Ändert der Editor den Wert, entwertet das den Cache-Eintrag
    und den Zweig darunter (§15). Fiele der Parameter aus dem Hash, zeigte das
    Fenster nach einer Bearbeitung das Ergebnis von vorher — und niemand
    verbände den Fehler mit seiner Ursache.
    """
    spec, name = case
    operation = Operation(id=1, op=spec.name, inputs=(), outputs=("obj_1",), params={})
    first = operation_hash(operation, {name: "eins"}, [], profile, "draft")
    second = operation_hash(operation, {name: "zwei"}, [], profile, "draft")
    assert first != second


@pytest.mark.parametrize("case", CASES, ids=ids)
def test_the_gathered_value_survives_the_round_trip(case: tuple[OperationSpec, str]) -> None:
    """Was der Editor gesammelt hat, steht nach dem Öffnen unverändert da."""
    spec, name = case
    value = '{"elements": [["line", [[0, 0], [10, 0]]]]}'
    operation = Operation(id=1, op=spec.name, inputs=(), outputs=("obj_1",), params={name: value})
    restored = operation_from_data(operation_to_data(operation))
    assert restored.params[name] == value


@pytest.mark.parametrize("case", CASES, ids=ids)
def test_the_gathered_value_is_plain_data(case: tuple[OperationSpec, str]) -> None:
    """Ein Sammelparameter ist Text, kein Objekt.

    Ein Objekt käme durch die Projektdatei nicht zurück, und der Hash oben
    hinge an einer Speicheradresse statt am Inhalt.
    """
    spec, name = case
    declared = next(entry for entry in spec.params.spec() if entry.name == name)
    assert isinstance(declared.default, str)


@pytest.mark.parametrize("case", CASES, ids=ids)
def test_the_agent_never_sees_the_gathered_value(case: tuple[OperationSpec, str]) -> None:
    """Leitprinzip 5: Die KI erzeugt keine Koordinaten.

    Eine Strichliste und eine Punktliste sind nichts anderes. Der Agent legt die
    Operation an und ändert ihre Zahlen; den Sammelwert füllt ein Mensch über
    den Editor.
    """
    spec, name = case
    assert name not in json_schema(spec.params).get("properties", {})


@pytest.mark.parametrize("case", CASES, ids=ids)
def test_the_gathered_value_sits_on_the_back_of_the_dialog(
    case: tuple[OperationSpec, str],
) -> None:
    """Vorne stehen die zwei bis drei Werte, die man tatsächlich ändert (§2.4).

    Ein Sammelwert gehört nicht dazu: Er wird bearbeitet, nicht getippt.
    """
    spec, name = case
    declared = next(entry for entry in spec.params.spec() if entry.name == name)
    assert declared.placement == "advanced"


@pytest.mark.parametrize("case", CASES, ids=ids)
def test_a_gesture_operation_is_reversible(case: tuple[OperationSpec, str]) -> None:
    """Viele Gesten in einem Schritt bleiben ein Schritt, den ein Undo
    zurücknimmt (Regel 16)."""
    spec, _name = case
    assert spec.reversible


def test_the_document_keeps_the_gathered_value(document: object) -> None:
    """Die runde Reise noch einmal über das ganze Dokument.

    Der Test darüber prüft eine einzelne Operation. Hier geht derselbe Wert
    durch dieselbe Tür wie beim Speichern eines Projekts — das ist die Stelle,
    an der ein vergessener Schlüssel im Dateiformat auffällt.
    """
    spec, name = CASES[0]
    value = '{"elements": []}'
    document.ops.append(  # type: ignore[attr-defined]
        Operation(id=1, op=spec.name, inputs=(), outputs=("obj_1",), params={name: value})
    )
    data = document_to_data(document)  # type: ignore[arg-type]
    assert data["ops"][0]["params"][name] == value
