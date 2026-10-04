"""Schrift auf einer Bahn und um eine Rundung (RM-184, Audit §9 „Text auf Fläche/Bahn“).

*Text aufbringen* setzte eine gerade Zeile auf eine ebene Fläche. Zwei Dinge,
die an echten Teilen ständig vorkommen, gingen damit nicht: ein Schriftzug, der
einem Kreisbogen folgt — der Rand eines Deckels, eine Münze —, und eine
Beschriftung auf einer runden Wand, einem Becher, einem Griff. Beides ist
hier eine **Abbildung der fertigen Buchstaben**, keine zweite Schriftmaschine:

* **Bahn** (:func:`bent_outlines`): Die ebenen Umrisse, mittig um den
  Ursprung, werden auf einen Kreisbogen gelegt. Die Mittellinie der Zeile
  wird der Bogen vom Radius ``radius``; positiv wölbt sie sich nach oben (der
  Mittelpunkt liegt unter der Schrift), negativ nach unten. Vorher wird jede
  Kante so fein geteilt, dass die Sehne höchstens ``units.MAX_FACET_SAG`` vom
  Bogen abweicht — dieselbe Grenze, mit der der exakte Kern tesselliert.
* **Rundung** (:func:`wrapped`): Die fertigen Buchstaben (Prismen, im Rahmen
  der Fläche: X Leserichtung, Y oben, Z nach außen) werden um eine Achse
  gebogen, die parallel zur Zeile (``along``) oder quer dazu (``around``) im
  Abstand ``radius`` hinter der Fläche liegt. Ein negativer Radius biegt nach
  vorn — Schrift innen in einem Ring. Das Netz wird vorher so fein geteilt,
  dass jede gebogene Kante dieselbe Sehnengrenze hält.

Winkelfunktionen über :func:`app.core.geom.mesh.stable_sin_cos` — aus
Grundrechenarten, damit dieselbe Datei auf jeder Maschine dieselben Buchstaben
ergibt (`kern.md`).
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal, cast

import numpy as np

from app.core.errors import CANCEL, CORRECT_INPUT, ValidationError
from app.core.geom.mesh import MeshData, stable_sin_cos
from app.core.types import Feature, Vec3, vec3_or_none
from app.core.units import EPS_GEOM, MAX_FACET_SAG, format_length
from app.i18n import _

Wrap = Literal["flat", "around", "along"]

#: Die drei Lagen einer Beschriftung zur Rundung ihres Trägers.
WRAPS: Final[tuple[str, ...]] = ("flat", "around", "along")

#: Wie viel eines vollen Umlaufs eine Zeile höchstens belegt. Darüber träfen
#: Anfang und Ende des Schriftzugs aufeinander; ein Rest hält sie getrennt.
MOST_OF_A_TURN: Final = 0.95

#: Wie weit eine Rundung neben dem angeklickten Punkt liegen darf, um als die
#: Fläche dort zu gelten — als Anteil ihres Radius. Gemessen wird nur, welches
#: erkannte Merkmal den Punkt trägt, nicht das Maß selbst.
ON_THE_ROUND_SHARE: Final = 0.05

#: Wie weit die Achse einer Rundung von der verlangten Richtung abweichen darf
#: (Kosinus): rund zehn Grad. Ein Becher auf schräger Fläche bleibt ein Becher.
AXIS_AGREEMENT: Final = 0.985


def chord_for(radius: float) -> float:
    """Die längste Sehne, die auf einem Bogen dieses Radius ``MAX_FACET_SAG`` hält.

    Pfeilhöhe einer Sehne ``L`` auf dem Radius ``r``: ``L² / (8 r)``.
    """
    return math.sqrt(8.0 * max(radius, EPS_GEOM) * MAX_FACET_SAG)


def _arc_refusal(detail: Any, field: str = "arc_radius") -> ValidationError:
    return ValidationError(
        field=field,
        detail=detail,
        constraint="bend",
        suggestions=(CORRECT_INPUT, CANCEL),
    )


def bend_room(extent: tuple[float, float], length: float, radius: float, field: str) -> float:
    """Prüft, ob eine Zeile auf diesen Bogen passt — und gibt den kleinsten Radius zurück.

    ``extent`` ist die Spanne quer zur Biegung (unten, oben), ``length`` die
    Länge entlang. Der kleinste Radius, auf dem ein Punkt der Schrift liegt,
    muss positiv bleiben, sonst kehrte sich die Schrift um; und die Zeile darf
    den Umfang nicht ganz belegen.
    """
    low, high = extent
    smallest = radius + low if radius > 0.0 else -radius - high
    if smallest <= EPS_GEOM:
        raise _arc_refusal(
            _(
                "Der Radius ist kleiner als die Schrift hoch ist ({height}). "
                "Wählen Sie einen größeren Radius oder eine kleinere Schrift.",
                height=format_length(high - low),
            ),
            field,
        )
    if length / abs(radius) > 2.0 * math.pi * MOST_OF_A_TURN:
        raise _arc_refusal(
            _(
                "Der Schriftzug ist länger als der Umfang des Bogens. Wählen Sie einen "
                "größeren Radius oder einen kürzeren Text."
            ),
            field,
        )
    return smallest


def bent_outlines(shapes: Sequence[Any], radius: float) -> list[Any]:
    """Die ebenen Umrisse einer Zeile, mittig um den Ursprung, auf einen Kreisbogen gelegt.

    ``(x, y)`` geht nach ``(0, -R) + (R + y)·(sin(x/R), cos(x/R))``: Die
    Mittellinie ``y = 0`` wird der Bogen vom Radius ``R`` durch den Ursprung,
    die Oberkante der Buchstaben liegt außen, wenn ``R`` positiv ist. Ein
    Radius null lässt die Zeile gerade.
    """
    if not radius or not shapes:
        return list(shapes)
    from shapely import segmentize, transform

    low = min(float(shape.bounds[1]) for shape in shapes)
    high = max(float(shape.bounds[3]) for shape in shapes)
    left = min(float(shape.bounds[0]) for shape in shapes)
    right = max(float(shape.bounds[2]) for shape in shapes)
    smallest = bend_room((low, high), right - left, radius, "arc_radius")
    chord = chord_for(smallest)

    def bent(points: np.ndarray) -> np.ndarray:
        x = np.asarray(points[:, 0], dtype=float)
        y = np.asarray(points[:, 1], dtype=float)
        sine, cosine = stable_sin_cos(x / radius)
        reach = radius + y
        return np.column_stack((reach * sine, reach * cosine - radius))

    return [transform(segmentize(shape, chord), bent) for shape in shapes]


def wrapped(body: MeshData, radius: float, wrap: Wrap) -> MeshData:
    """Buchstaben im Rahmen der Fläche um eine Rundung gebogen.

    ``around``: die Achse liegt parallel zu Y (oben der Schrift), die Zeile
    läuft um sie herum; ``along``: die Achse liegt parallel zu X, die Zeile
    läuft an ihr entlang und die Buchstaben biegen sich über ihre Höhe. Die
    Achse liegt bei ``z = -radius``; ein Punkt ``(u, ·, w)`` geht nach
    ``((R + w)·sin(u/R), ·, (R + w)·cos(u/R) - R)``. Die Fläche ``w = 0`` wird
    damit genau der Zylinder vom Radius ``R`` durch den Ursprung.
    """
    if wrap == "flat" or not radius:
        return body
    from trimesh.remesh import subdivide_to_size

    vertices = np.asarray(body.raw.vertices, dtype=float)
    across = 0 if wrap == "around" else 1
    outward = vertices[:, 2]
    low, high = float(outward.min()), float(outward.max())
    span = float(vertices[:, across].max() - vertices[:, across].min())
    smallest = bend_room((low, high), span, radius, "wrap_radius")
    fine, faces = cast(Any, subdivide_to_size)(
        vertices, np.asarray(body.raw.faces, dtype=np.int64), max_edge=chord_for(smallest)
    )
    fine = np.asarray(fine, dtype=float)
    sine, cosine = stable_sin_cos(fine[:, across] / radius)
    reach = radius + fine[:, 2]
    moved = fine.copy()
    moved[:, across] = reach * sine
    moved[:, 2] = reach * cosine - radius
    from app.core.deferred import trimesh

    return MeshData.of(trimesh.Trimesh(vertices=moved, faces=faces, process=False))


def wrap_axis(wrap: Wrap, frame_x: np.ndarray, frame_y: np.ndarray) -> np.ndarray:
    """Die Richtung der Rundungsachse in der Welt — quer zur Zeile oder an ihr entlang."""
    return frame_y if wrap == "around" else frame_x


def measured_radius(
    features: Mapping[str, Feature], position: Vec3, normal: Vec3, axis: np.ndarray
) -> float | None:
    """Der Radius der Rundung, auf der dieser Punkt liegt — aus einem erkannten Merkmal.

    Gesucht wird ein Zapfen, eine Bohrung oder eine gerundete Seite mit Achse
    und Durchmesser, deren Achse die verlangte Richtung hat und deren Mantel
    durch den Punkt geht. Liegt die Achse hinter der Fläche, ist die Rundung
    gewölbt (Radius positiv); liegt sie davor, hohl (negativ). ``None``, wenn
    kein Merkmal den Punkt trägt — dann nennt der Kunde den Radius, geraten
    wird nicht (Regel 21).
    """
    point = np.asarray(position, dtype=float)
    facing = np.asarray(normal, dtype=float)
    want = np.asarray(axis, dtype=float)
    want = want / max(math.hypot(*(float(value) for value in want)), EPS_GEOM)
    best: tuple[float, float] | None = None
    for feature in features.values():
        if feature.kind not in ("pin", "hole", "curved_face"):
            continue
        centre = vec3_or_none(feature.params.get("centre"))
        direction = vec3_or_none(feature.params.get("axis"))
        diameter = feature.params.get("diameter")
        if centre is None or direction is None or not isinstance(diameter, int | float):
            continue
        line = np.asarray(direction, dtype=float)
        length = math.hypot(*(float(value) for value in line))
        if length <= EPS_GEOM:
            continue
        line = line / length
        agreement = abs(
            float(line[0] * want[0]) + float(line[1] * want[1]) + float(line[2] * want[2])
        )
        if agreement < AXIS_AGREEMENT:
            continue
        offset = point - np.asarray(centre, dtype=float)
        along = float(offset[0] * line[0]) + float(offset[1] * line[1]) + float(offset[2] * line[2])
        radial = offset - line * along
        distance = math.hypot(*(float(value) for value in radial))
        expected = float(diameter) / 2.0
        miss = abs(distance - expected)
        if miss > ON_THE_ROUND_SHARE * expected + EPS_GEOM:
            continue
        behind = (
            float(radial[0] * facing[0])
            + float(radial[1] * facing[1])
            + float(radial[2] * facing[2])
        ) > 0.0
        signed = distance if behind else -distance
        if best is None or miss < best[0]:
            best = (miss, signed)
    return None if best is None else best[1]
