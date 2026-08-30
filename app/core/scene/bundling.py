"""Aufeinanderfolgende gleichartige Züge werden ein Verlaufsschritt (§15.5).

Wer ein Teil an seinen Platz schiebt, zieht selten einmal. Er zieht, sieht
nach, zieht nach, sieht wieder nach — und hatte dafür bisher drei Einträge im
Verlauf, für eine einzige Absicht. Ein Strg+Z nahm dann ein Drittel zurück.

**Gebündelt wird eng.** Nur was dieselbe Operation auf denselben Eingängen mit
demselben Anker ist, und nur wo eine Kumulationsregel steht — das ist der
Punkt: Bündeln ist **opt-in je Operation**, nicht die Voreinstellung. Wer eine
neue Operation baut, bekommt kein Bündeln geschenkt, und das ist richtig, denn
die Regel dafür ist jedes Mal eine eigene Überlegung:

* Zwei Verschiebungen sind eine Vektorsumme.
* Zwei Drehungen sind eine Winkelsumme — **nur um dieselbe Achse.** Zwei
  Drehungen um verschiedene Achsen lassen sich nicht zu einer zusammenfassen;
  wer es doch tut, baut einen stillen Geometriefehler, den erst der Druck
  zeigt.
* Zwei Skalierungen wären ein Produkt. Sie bündeln trotzdem **nicht**: Der
  Kundenfall ist „dreimal nachgeschoben", die gefährliche Kante bleibt in
  Ruhe, und was hier fehlt, kann jederzeit dazukommen. Umgekehrt wäre es ein
  Rückbau (Entscheidung d5/Robert, 30.08.2026).

Das Bündel endet mit **jeder anderen Handlung** — einer anderen Operation,
einer anderen Auswahl, einem Werkzeugwechsel. Keine Zeitpause: Eine geratene
Zahl wäre die fragilste Bauart, und sie stünde in jeder Fehlersuche als
Verdächtige.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: Wie nah zwei Fließkommazahlen sein müssen, um als derselbe Anker zu gelten.
#: Der Anker kommt aus der Hüllquadermitte einer Auswahl und wird bei jedem Zug
#: neu gerechnet; identisch ist er deshalb nie, gleich schon.
_ANCHOR_TOLERANCE = 1e-9


def _same_anchor(older: Mapping[str, Any], newer: Mapping[str, Any]) -> bool:
    """Ob beide Züge um denselben Punkt gehen.

    Ein Zug ohne genannten Punkt dreht um den eigenen Schwerpunkt, und der
    wandert mit dem Körper: Zwei solche Drehungen **hintereinander** sind
    nicht dasselbe wie eine doppelte, sobald der Schwerpunkt sich verschiebt.
    Bei einer reinen Drehung tut er das nicht — deshalb ist „beide ohne
    Anker" gleichwertig und nicht etwa unbekannt.
    """
    for key in ("about", "pivot_x", "pivot_y", "pivot_z"):
        one, other = older.get(key), newer.get(key)
        if isinstance(one, (int, float)) and isinstance(other, (int, float)):
            if abs(float(one) - float(other)) > _ANCHOR_TOLERANCE:
                return False
        elif one != other:
            return False
    return True


def _translate(older: Mapping[str, Any], newer: Mapping[str, Any]) -> dict[str, Any] | None:
    """Zwei Verschiebungen sind ihre Summe."""
    merged = dict(older)
    for axis in ("dx", "dy", "dz"):
        merged[axis] = float(older.get(axis, 0.0)) + float(newer.get(axis, 0.0))
    return merged


def _rotate(older: Mapping[str, Any], newer: Mapping[str, Any]) -> dict[str, Any] | None:
    """Zwei Drehungen um **dieselbe** Achse sind ihre Winkelsumme.

    Um verschiedene Achsen gibt es keine gemeinsame Drehung, und der Versuch
    wäre schlimmer als zwei Einträge im Verlauf.
    """
    if older.get("axis") != newer.get("axis"):
        return None
    merged = dict(older)
    merged["angle"] = float(older.get("angle", 0.0)) + float(newer.get("angle", 0.0))
    return merged


#: Welche Operationen bündeln — und wie. Wer hier nicht steht, bündelt nicht.
_RULES = {
    "translate_object": _translate,
    "rotate_object": _rotate,
}


def bundles(op: str) -> bool:
    """Ob diese Operation überhaupt bündelt."""
    return op in _RULES


def merge_params(
    op: str, older: Mapping[str, Any], newer: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Die Werte zweier gleichartiger Züge zu einem — oder ``None``.

    ``None`` heißt: Diese beiden gehören nicht zusammen. Der Aufrufer legt
    dann einen eigenen Schritt an, und das ist der sichere Ausgang — ein
    Bündel zu viel verfälscht Geometrie, ein Bündel zu wenig kostet einen
    Eintrag im Verlauf.
    """
    rule = _RULES.get(op)
    if rule is None or not _same_anchor(older, newer):
        return None
    return rule(older, newer)
