"""Welche Auswahl eine Absage meint — am Schritt, der sie auslöst (RB-1, RB-2).

*Andere Kanten wählen*, *Andere Flächen wählen* und *Anderes Merkmal wählen*
öffnen den Schritt (``change_step``) mit dem Cursor im Feld, das sie nennen.
**Wer die Absage wirft, kennt den Schritt oft nicht:** ``edges.round_edges``
sagt „Radius zu groß für diese Kanten“ aus *Verrunden* (Feld *Kanten*) und
aus *Merkmal ändern* (Feld *Merkmal*, kein Kantenfeld); ``faces.push_face``
sagt „Fläche gewölbt“ aus *Fläche versetzen* (Feld *Fläche*) und aus *Kammer
ändern* (Feld *Merkmal*). Die Auswertung kennt den Schritt
(``evaluate._finding_from`` und die Befunde einer Ausgabe), und dort passt
:func:`fitted_to_step` die Handlung an sein Schema an: Hat der Schritt kein
Feld der genannten Art, meint die Absage sein Merkmal, sonst den Schritt
selbst (*Diesen Schritt ändern*).

**Das Feld steht in ``values["choice_field"]``**, und in ``values["field"]``,
wo die Absage keins nennt und keinen Wert korrigieren lässt
(``errors.FIELD_WAYS``). Zwei Schlüssel, weil eine Absage beides anbieten
kann: *Eingabe korrigieren* mit dem Cursor im Radius (``field``) und *Andere
Kanten wählen* mit dem Cursor in den Kanten (``choice_field``). Mit einem
Schlüssel taten beide Knöpfe dasselbe (Review 1 Restpaket B, RB-2).
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Mapping, Sequence
from typing import Final, Literal

from app.core.errors import (
    CHANGE_EDGES,
    CHANGE_FACES,
    CHANGE_FEATURE,
    CHANGE_THIS_STEP,
    FIELD_WAYS,
    AppError,
)
from app.core.types import Action, Finding, ParamSpec

Choice = Literal["edges", "faces", "feature"]

#: Die drei Auswahlhandlungen und die Art Feld, die sie öffnen.
CHOICE_ACTIONS: Final[dict[Action, Choice]] = {
    CHANGE_EDGES: "edges",
    CHANGE_FACES: "faces",
    CHANGE_FEATURE: "feature",
}

#: Merkmalsfelder, die Flächen wählen. Ihr Schema nennt keine Merkmalsarten
#: (``feature_kinds``), weil der Dialog dort jede Fläche annimmt und die
#: Operation selbst absagt — darum hier beim Namen: *Formschräge anstellen*,
#: *Fläche versetzen*, *Textur aufbringen*, *Aushöhlen*, *Dichtnut*.
FACE_FIELDS: Final = frozenset({"face", "faces", "openings", "support_feature"})

#: Die Kantengruppe: *Kanten* (``edges``) ist ein Auswahlwert, kein
#: Kantenfeld, und wählt trotzdem Kanten; *Einzelne Kanten* (``edge_keys``)
#: wirkt nur bei „Einzeln gewählt“ (:func:`choice_fields`).
EDGE_GROUP: Final = "edges"

_FACE_KINDS: Final = frozenset({"face", "curved_face"})


def _choice_of(entry: ParamSpec) -> Choice | None:
    """Welche Auswahl ein Feld trägt, oder keine."""
    if entry.kind == "edges" or entry.name == EDGE_GROUP:
        return "edges"
    if entry.name in FACE_FIELDS:
        return "faces"
    if entry.kind not in ("feature", "features"):
        # Ein Ziel (``targets_feature``) ist der Ort einer Platzierung, nicht
        # das Merkmal, an dem der Schritt arbeitet.
        return None
    if entry.feature_kinds and set(entry.feature_kinds) <= _FACE_KINDS:
        return "faces"
    return "feature"


def choice_fields(
    params: Sequence[ParamSpec], values: Mapping[str, object] | None = None
) -> dict[Choice, list[str]]:
    """Je Auswahl die Felder eines Schritts, das gemeinte zuerst.

    Gemeint ist ein Feld, das bei den Werten des Schritts wirkt
    (``ParamSpec.depends_on``), und von zweien das, welches erst durch das
    andere wirkt: Bei *Kanten* „Einzeln gewählt“ stehen die gewählten Kanten
    in *Einzelne Kanten*, die Gruppe davor sagt nur „Einzeln gewählt“
    (RB2-3). Ein Feld, das nicht wirkt, kommt zuletzt. Sonst gilt die
    Reihenfolge des Schemas; ohne Werte die Vorgaben.
    """
    given: dict[str, object] = {entry.name: entry.default for entry in params}
    given.update(values or {})
    found: dict[Choice, list[str]] = {"edges": [], "faces": [], "feature": []}
    depends = {entry.name: entry.depends_on for entry in params}
    for entry in params:
        choice = _choice_of(entry)
        if choice is not None:
            found[choice].append(entry.name)

    def rank(name: str, siblings: list[str]) -> int:
        condition = depends[name]
        if condition is None:
            return 1
        (source, wanted) = condition
        if given.get(source) not in wanted:
            return 2
        return 0 if source in siblings else 1

    for names in found.values():
        ranks = {name: rank(name, names) for name in names}
        names.sort(key=ranks.__getitem__)
    return found


def fitted_to_step(
    finding: Finding, op: str, params: Mapping[str, object] | None = None
) -> Finding:
    """Die Auswahlhandlungen eines Befunds auf die Felder seines Schritts.

    ``params`` sind die Werte des Schritts: Welches Feld eine Handlung meint,
    hängt an ihnen (:func:`choice_fields`). Ohne bekannte Operation (eine
    Datei aus einer späteren Fassung) bleibt der Befund, wie er ist.
    """
    if not any(action in CHOICE_ACTIONS for action in finding.suggestions):
        return finding
    from app.core.registry import REGISTRY

    if not REGISTRY.has(op):
        return finding
    fields = choice_fields(REGISTRY.get(op).params.spec(), params)
    values = dict(finding.values)
    stated = str(values.get("choice_field", ""))
    # ``field`` gehört dem Wert, wo die Absage ihn korrigieren lässt: Ohne
    # eigenes Feld öffnet *Eingabe korrigieren* das erste Feld, den Radius.
    reads_field = any(action.id in FIELD_WAYS for action in finding.suggestions)
    ways: list[Action] = []
    for action in finding.suggestions:
        wanted = CHOICE_ACTIONS.get(action)
        if wanted is None:
            way = action
        else:
            target: Choice | None = (
                wanted if fields[wanted] else ("feature" if fields["feature"] else None)
            )
            if target is None:
                way = CHANGE_THIS_STEP
            else:
                way = next(key for key, choice in CHOICE_ACTIONS.items() if choice == target)
                chosen = stated if stated in fields[target] else fields[target][0]
                values["choice_field"] = chosen
                if not reads_field:
                    values.setdefault("field", chosen)
        if way not in ways:
            ways.append(way)
    return dataclasses.replace(finding, suggestions=tuple(ways), values=values)


def for_the_choice(error: AppError) -> AppError:
    """Derselbe Fehler mit dem Feld der Auswahl als ``field`` — für ``change_step``.

    *Eingabe korrigieren* liest ``field`` (den Wert, der nicht ging), die
    Auswahlhandlung ``choice_field``. Der Handler des Fensters ist für beide
    derselbe (``MainWindow._correct_after_error``); er bekommt hier den Fehler
    so, dass er das richtige Feld öffnet. Ohne Auswahlfeld bleibt er, wie er ist
    (*Größe ändern*, *Splitter behalten*).
    """
    chosen = error.values.get("choice_field")
    if not chosen:
        return error
    moved = copy.copy(error)
    moved.values = {**error.values, "field": str(chosen)}
    return moved
