"""Bohrungen, die der Schritt durch den ganzen Träger führt — gebaut und gezeigt (RM-631, RM-632).

Ein Baustein baut eine solche Bohrung nur über seine eigene Strecke
(``PartSpec.reaches_through``); wie weit der Träger entlang ihrer Achse noch
Material hat, misst die Operation (``ops._reaching_through``). Ohne Träger —
im Katalogbild, im Platzierungsgeist, im SCAD-Export — gibt es nichts zu
messen, und ohne Fortsetzung sah die Mutternfalle dort aus, als hätte sie
kein Schraubenloch: Es lag ganz in ihrer Tasche. Gezeigt wird es deshalb mit
einer Anzeigelänge (:data:`SHOWN_REACH`), und nur dorthin, wohin der Schritt
es bohren kann: nie aus der Mündung heraus.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.knowledge.parts.registry import PartSpec
from app.core.types import PartResult, Vec3
from app.core.units import EPS_GEOM

#: Wie lang eine durchgehende Bohrung ohne Träger gezeigt wird, in ihren
#: Durchmessern. Ein Zahlenwert in Millimetern wäre bei M1,6 ein Stab und bei
#: M64 ein Stummel; drei Durchmesser lesen sich in jeder Größe als Loch, das
#: weitergeht, ohne den Baustein zu überragen (bei M3 10,2 mm, so lang wie der
#: feste Stummel, den die Mutternfalle bis RM-631 schnitt). Es ist eine
#: Anzeige, kein Maß: Gebohrt wird, so weit der Träger reicht.
SHOWN_REACH: Final = 3.0


@dataclass(frozen=True, slots=True)
class ShownBore:
    """Ein gezeigtes Stück Bohrung: ab ``start`` entlang ``direction``, ``length`` lang."""

    name: str
    diameter: float
    start: Vec3
    direction: Vec3
    length: float


def shown_bores(spec: PartSpec, produced: PartResult, *, upward: bool) -> list[ShownBore]:
    """Die Fortsetzungen der Bohrungen aus ``spec.reaches_through``, im eigenen Rahmen.

    Je Ende eine, außer dem, das aus der Mündung zeigt: Ein Baustein, der nach
    oben baut (``upward``, die Mutternfalle), öffnet nach -Z, die übrigen nach
    +Z. Dort liegt beim Setzen die Fläche, und dahinter bohrt der Schritt nie.
    """
    shown: list[ShownBore] = []
    for name in spec.reaches_through:
        feature = produced.features.get(name)
        if feature is None or feature.kind != "hole":
            continue
        axis = unit(feature.params.get("axis") or (0.0, 0.0, 1.0))
        centre = triple(feature.params["centre"])
        half = float(feature.params.get("depth") or 0.0) / 2.0
        diameter = float(feature.params["diameter"])
        for sign in (-1.0, 1.0):
            direction = (sign * axis[0], sign * axis[1], sign * axis[2])
            if (direction[2] < -0.5) if upward else (direction[2] > 0.5):
                continue
            reach = half - BOOLEAN_OVERLAP
            shown.append(
                ShownBore(
                    name=name,
                    diameter=diameter,
                    start=(
                        centre[0] + direction[0] * reach,
                        centre[1] + direction[1] * reach,
                        centre[2] + direction[2] * reach,
                    ),
                    direction=direction,
                    length=SHOWN_REACH * diameter + BOOLEAN_OVERLAP,
                )
            )
    return shown


def with_shown_bores(spec: PartSpec, produced: PartResult, form: Any) -> Any:
    """``form`` mit den gezeigten Fortsetzungen — im Kern, den ``building`` gewählt hat."""
    from app.core.knowledge.parts.build import union

    if not spec.reaches_through:
        return form
    upward = builds_upward(form)
    pieces = [
        cylinder_along(entry.diameter, entry.start, entry.direction, 0.0, entry.length)
        for entry in shown_bores(spec, produced, upward=upward)
    ]
    return union(form, *pieces) if pieces else form


def builds_upward(form: Any) -> bool:
    """Ob ein Baustein über seine Mündung hinaus nach +Z baut — die Mutternfalle.

    **Die eine Spiegelungsentscheidung** (``ops._extends_above_mouth``): Ein
    abtragender Baustein, der so baut, wird an einer Fläche gespiegelt, und
    seine Mündung liegt dann bei -Z. Operation, Anzeige und SCAD fragen hier,
    statt den Ausdruck je für sich herzuleiten (Nachprüfung G, N-8).
    """
    from app.core.geom.mesh import as_mesh_data

    return float(as_mesh_data(form).bounds.maximum[2]) > BOOLEAN_OVERLAP + EPS_GEOM


def cylinder_along(diameter: float, centre: Vec3, axis: Vec3, start: float, length: float) -> Any:
    """Ein Zylinder entlang ``axis`` durch ``centre``, ab ``start`` ``length`` lang.

    Gebaut aus ``shapes.cylinder`` (steht auf z = 0) im Kern, den ``building``
    gewählt hat: von +Z auf die Achse gedreht, dann verschoben.
    """
    from app.core.knowledge.parts import shapes

    piece = shapes.cylinder(diameter, length)
    turn = turn_onto(axis)
    if turn is not None:
        degrees, about = turn
        piece = shapes.turned(piece, degrees, about)
    return shapes.moved(
        piece,
        (
            centre[0] + axis[0] * start,
            centre[1] + axis[1] * start,
            centre[2] + axis[2] * start,
        ),
    )


def turn_onto(axis: Vec3) -> tuple[float, Vec3] | None:
    """Die Drehung von +Z auf ``axis`` als Winkel und Drehachse — ``None``, wo keine nötig ist.

    Um das Kreuzprodukt beider, so weit, wie sie auseinanderliegen; genau
    entgegen um X. Der Winkel über ``exact_atan2_degrees`` (RM-187).
    """
    from app.core.units import exact_atan2_degrees

    if axis[2] >= 1.0 - EPS_GEOM:
        return None
    sideways = math.hypot(axis[0], axis[1])
    if sideways <= EPS_GEOM:
        return 180.0, (1.0, 0.0, 0.0)
    return (
        exact_atan2_degrees(sideways, axis[2]),
        (-axis[1] / sideways, axis[0] / sideways, 0.0),
    )


def unit(vector: Any) -> Vec3:
    """``vector`` auf Länge eins, als Tripel aus ``float`` (Länge über ``math.hypot``)."""
    values = triple(vector)
    length = math.hypot(*values)
    return (values[0] / length, values[1] / length, values[2] / length)


def triple(vector: Any) -> Vec3:
    """``vector`` als Tripel aus ``float``."""
    return (float(vector[0]), float(vector[1]), float(vector[2]))
