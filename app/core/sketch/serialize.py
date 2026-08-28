"""Die Skizze als Parameterwert einer Operation (Bauplan §30.1, §15).

Eine gezeichnete Skizze reist als JSON-Text im ``sketch``-Parameter der Op,
die sie verbraucht — damit gilt §15 unverändert: kein verstecktes Attribut,
rücknehmbar, im Projekt gespeichert, und Bearbeiten heißt ``change_params``
auf dem Schritt im Verlauf.

Der Text kann aus einer Projektdatei kommen, also wird er geprüft wie jede
fremde Eingabe: nur bekannte Arten, nur Zahlen, nur ganzzahlige Ziele —
alles andere ist eine :class:`ValidationError` mit Vorschlag, nie ein
Traceback (§32, §33.1).
"""

from __future__ import annotations

import json
import math
from typing import Any

from app.core.errors import ValidationError
from app.core.expressions import references
from app.core.types import (
    Point2,
    Sketch,
    SketchConstraint,
    SketchConstraintKind,
    SketchElement,
    SketchElementKind,
)
from app.i18n import _

_ELEMENT_KINDS: frozenset[str] = frozenset(("point", "line", "arc", "circle", "spline"))
_CONSTRAINT_KINDS: frozenset[str] = frozenset(
    (
        "distance",
        "coincident",
        "horizontal",
        "vertical",
        "parallel",
        "perpendicular",
        "tangent",
        "symmetric",
        "fixed",
        "reference",
    )
)


def sketch_to_text(sketch: Sketch) -> str:
    """Die Skizze als JSON-Text, wie er im Op-Parameter steht."""
    payload = {
        "plane": sketch.plane,
        "elements": [
            {
                "kind": element.kind,
                "points": [list(point) for point in element.points],
                # Nur wenn gesetzt: eine Skizze ohne Hilfsgeometrie schreibt
                # denselben Text wie vor diesem Feld, und jede bestehende
                # Projektdatei liest sich unverändert.
                **({"construction": True} if element.construction else {}),
            }
            for element in sketch.elements
        ],
        "constraints": [
            {
                "kind": constraint.kind,
                "targets": list(constraint.targets),
                **({"value": constraint.value} if constraint.value else {}),
            }
            for constraint in sketch.constraints
        ],
    }
    return json.dumps(payload, ensure_ascii=False)


def sketch_from_text(text: str) -> Sketch:
    """Liest eine Skizze aus dem Parametertext — streng, mit Sätzen statt Tracebacks."""
    try:
        # RecursionError: json verschachtelt rekursiv — ein bösartig tiefer
        # Text wäre sonst ein Traceback statt einer Meldung (Regel 17).
        payload = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as problem:
        raise _damaged(_("Der Skizzentext ist kein gültiges JSON.")) from problem
    if not isinstance(payload, dict):
        raise _damaged(_("Die Skizze hat nicht den erwarteten Aufbau."), field="payload")

    plane = payload.get("plane", "plane:xy")
    if not isinstance(plane, str) or not _known_plane(plane):
        raise _damaged(_("Diese Ebene gibt es nicht."), plane=plane)

    elements: list[SketchElement] = []
    for index, entry in enumerate(_listed(payload.get("elements", []), "elements")):
        kind = _named(entry, "kind", index)
        if kind not in _ELEMENT_KINDS:
            raise _damaged(_("Diese Elementart gibt es nicht."), kind=kind)
        points = entry.get("points")
        if not isinstance(points, list) or not points:
            raise _damaged(_("Ein Element braucht Punkte."), index=index)
        parsed: list[Point2] = []
        for point in points:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or not all(_finite(value) for value in point)
            ):
                raise _damaged(_("Ein Punkt besteht aus zwei Zahlen."), index=index)
            parsed.append((float(point[0]), float(point[1])))
        construction = entry.get("construction", False)
        if not isinstance(construction, bool):
            raise _damaged(_("Ein Hilfsgeometrie-Kennzeichen ist wahr oder falsch."), index=index)
        element_kind: SketchElementKind = kind  # type: ignore[assignment]
        elements.append(
            SketchElement(kind=element_kind, points=tuple(parsed), construction=construction)
        )

    constraints: list[SketchConstraint] = []
    for index, entry in enumerate(_listed(payload.get("constraints", []), "constraints")):
        kind = _named(entry, "kind", index)
        if kind not in _CONSTRAINT_KINDS:
            raise _damaged(_("Diese Bedingungsart gibt es nicht."), kind=kind)
        targets = entry.get("targets")
        if not isinstance(targets, list) or not all(
            isinstance(value, int) and not isinstance(value, bool) for value in targets
        ):
            raise _damaged(_("Die Ziele einer Bedingung sind ganze Zahlen."), index=index)
        value = entry.get("value", "")
        if not isinstance(value, str):
            raise _damaged(_("Das Maß einer Bedingung ist ein Ausdruck als Text."), index=index)
        constraint_kind: SketchConstraintKind = kind  # type: ignore[assignment]
        constraints.append(
            SketchConstraint(kind=constraint_kind, targets=tuple(targets), value=value)
        )

    return Sketch(plane=plane, elements=tuple(elements), constraints=tuple(constraints))


def sketch_parameter_references(text: str) -> frozenset[str]:
    """Projektparameter, die die Maße der Skizze lesen (§13).

    Die Auswertung mischt ihre Werte in den Cache-Schlüssel der Op:
    Maßausdrücke stehen im Skizzentext und sind für ``resolve_params``
    unsichtbar — ohne die Werte bliebe nach einer Parameteränderung das alte
    Ergebnis im Cache stehen (§15). Ein unlesbarer Text hat keine
    Abhängigkeiten; er scheitert beim Lauf der Op mit seiner eigenen Meldung."""
    found: set[str] = set()
    try:
        sketch = sketch_from_text(text)
        for constraint in sketch.constraints:
            if constraint.value:
                found |= references(constraint.value)
    except ValidationError:
        return frozenset()
    return frozenset(found)


def _known_plane(plane: str) -> bool:
    """Eine Grundebene oder eine alte beziehungsweise eindeutige Flächenebene."""
    if plane in ("plane:xy", "plane:xz", "plane:yz"):
        return True
    prefix, separator, feature_id = plane.partition(":")
    return prefix == "feature" and bool(separator) and bool(feature_id)


def _finite(value: Any) -> bool:
    """Eine echte, endliche Zahl — ``True`` und ``NaN`` sind keine Koordinaten."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except OverflowError:
        # Eine Ganzzahl jenseits des double-Bereichs — JSON lässt sie durch,
        # ``float`` nicht mehr.
        return False


def _listed(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(entry, dict) for entry in value):
        raise _damaged(_("Die Skizze hat nicht den erwarteten Aufbau."), field=field)
    return value


def _named(entry: dict[str, Any], key: str, index: int) -> str:
    value = entry.get(key)
    if not isinstance(value, str):
        raise _damaged(_("Die Skizze hat nicht den erwarteten Aufbau."), index=index)
    return value


def _damaged(detail: Any, **values: Any) -> ValidationError:
    return ValidationError(
        "sketch",
        detail,
        constraint="damaged_sketch",
        values=dict(values),
    )
