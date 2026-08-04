"""Wo eine Skizze liegt (Bauplan §30.1).

Drei Ebenen sind fest — ``plane:xy``, ``plane:xz``, ``plane:yz``. Die vierte
Möglichkeit ist ``feature:<id>``: eine erkannte planare Fläche eines Körpers.
Sie ist die interessantere, denn sie ist der Weg, auf einem vorhandenen Teil
weiterzubauen, statt daneben.

**Der Rahmen wird berechnet, nicht gespeichert.** In der Projektdatei steht nur
die Feature-ID; Ursprung und Achsen entstehen bei jeder Auswertung neu aus dem
Körper. Wäre es umgekehrt, hinge die Skizze an Zahlen von gestern und würde
still danebenliegen, sobald sich der Körper unter ihr ändert — und genau das
wäre der Fall, für den §21 die stabilen IDs eingeführt hat.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from app.core.errors import Action, ValidationError
from app.core.types import PlaneFrame, SceneObject, Vec3
from app.i18n import _

#: Zwei Richtungen gelten als parallel, wenn ihr Kreuzprodukt darunter liegt.
#: Kein Toleranzwert im Sinne von Regel 7 — hier geht es nicht um Material,
#: sondern um die Frage, ob eine Rechnung numerisch trägt.
_PARALLEL = 1e-9

#: Ab wann eine Zielebene als parallel zur Extrusionsachse gilt. Deutlich
#: großzügiger als _PARALLEL: bei einem Kosinus von einem Tausendstel steht
#: die Ebene noch fast parallel, und der Schnittpunkt läge tausendmal weiter
#: weg als der Körper groß ist. Eine solche Höhe ist rechnerisch erklärbar und
#: als Antwort unbrauchbar.
_PARALLEL_ENOUGH = 1e-3


def _normalised(vector: Vec3) -> Vec3:
    length = math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)
    if length < _PARALLEL:
        raise ValidationError(
            "plane",
            _("Diese Fläche hat keine brauchbare Richtung."),
            value=str(vector),
            constraint="degenerate_normal",
            suggestions=[
                Action(
                    id="sketch.use_global_plane",
                    label=_("Auf einer der drei Grundebenen zeichnen"),
                )
            ],
        )
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def _cross(first: Vec3, second: Vec3) -> Vec3:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _dot(first: Vec3, second: Vec3) -> float:
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]


def _length(vector: Vec3) -> float:
    return math.sqrt(_dot(vector, vector))


def frame_of(normal: Vec3, origin: Vec3) -> PlaneFrame:
    """Ein rechtshändiger Rahmen zu einer Normalen.

    Die erste Achse ist das Kreuzprodukt aus Z und der Normalen, außer die
    Normale zeigt selbst nach Z — dann ist sie ``X``. Diese Wahl ist nicht die
    einzig mögliche, aber die einzig sinnvolle: sie macht die waagerechte
    Fläche zur globalen XY-Ebene, sodass dieselbe Skizze auf dem Tisch und auf
    dem Deckel gleich herum liegt. Jede andere Regel drehte die Zeichnung um
    einen Winkel, den niemand erklären kann.
    """
    unit = _normalised(normal)
    x_axis = _cross((0.0, 0.0, 1.0), unit)
    if _length(x_axis) < _PARALLEL:
        x_axis = _cross((0.0, 1.0, 0.0), unit)
    x_axis = _normalised(x_axis)
    y_axis = _normalised(_cross(unit, x_axis))
    return PlaneFrame(origin=origin, x_axis=x_axis, y_axis=y_axis, normal=unit)


def _outward(normal: Vec3, centre: Vec3, inside: Vec3) -> Vec3:
    """Die Normale so wenden, dass sie vom Körper wegzeigt.

    Ohne das ist die Richtung Glückssache. OpenCASCADE führt die Normale einer
    planaren Fläche als Achsenrichtung ihrer Ebene, und die hängt an der
    Orientierung der Fläche im Körper, nicht an der Anschauung: der Quader in
    der Suite meldet für die Wand bei x = -20 die Richtung +X. Wer darauf
    extrudiert, baut nach innen.

    ``inside`` ist die Mitte der Hüllbox — ein Punkt, der bei einem gedruckten
    Teil im Material liegt oder wenigstens in seiner Mitte. Für eine stark
    C-förmige Form kann er daneben liegen; dann zeigt die Richtung falsch
    herum, und man dreht sie mit einer negativen Höhe um. Die aufwendigere
    Prüfung (Strahl gegen den Körper) kostet mehr, als sie hier einbringt.
    """
    away = (centre[0] - inside[0], centre[1] - inside[1], centre[2] - inside[2])
    if _dot(normal, away) < 0.0:
        return (-normal[0], -normal[1], -normal[2])
    return normal


def is_feature_plane(plane: str) -> bool:
    """Ob diese Ebenenangabe an einer Fläche hängt statt an der Welt."""
    return plane.startswith("feature:")


def frame_for(plane: str, objects: Iterable[SceneObject]) -> PlaneFrame:
    """Der Rahmen zu ``feature:<id>``, gesucht über alle Objekte der Szene.

    Über alle und nicht nur über das Eingangsobjekt, weil ``sketch_extrude``
    nichts verbraucht: sie erzeugt einen Körper aus dem Nichts, und die Fläche,
    auf der sie aufsetzt, gehört einem anderen.
    """
    feature_id = plane.partition(":")[2]
    known: list[str] = []
    for entry in objects:
        for candidate, feature in entry.features.items():
            if feature.kind != "face":
                continue
            known.append(candidate)
            if candidate != feature_id:
                continue
            normal = tuple(float(value) for value in feature.params.get("normal", (0.0, 0.0, 1.0)))
            centre = tuple(float(value) for value in feature.params.get("centre", (0.0, 0.0, 0.0)))
            box = entry.mesh.bounds
            pairs = zip(box.minimum, box.maximum, strict=True)
            inside = tuple((low + high) / 2.0 for low, high in pairs)
            outward = _outward(
                (normal[0], normal[1], normal[2]),
                (centre[0], centre[1], centre[2]),
                (inside[0], inside[1], inside[2]),
            )
            return frame_of(outward, (centre[0], centre[1], centre[2]))
    raise ValidationError(
        "plane",
        _("Diese Fläche gibt es in der Szene nicht mehr."),
        value=feature_id,
        constraint="unknown_feature",
        values={"known_faces": known},
        suggestions=[
            Action(id="sketch.pick_face", label=_("Eine andere Fläche wählen"), primary=True),
            Action(
                id="sketch.use_global_plane", label=_("Auf einer der drei Grundebenen zeichnen")
            ),
        ],
    )


def height_to(start: PlaneFrame, target: PlaneFrame) -> float:
    """Wie hoch von der Skizzenebene bis zur Zielebene (D14).

    Die Extrusionsachse läuft vom Ursprung der Skizze entlang ihrer Normalen;
    gesucht ist der Parameter, bei dem sie die Zielebene trifft. Nur die Ebene
    der Zielfläche zählt, nicht ihr Umriss — „bis zu dieser Fläche" heißt im
    CAD seit jeher „bis auf ihre Höhe", und alles andere wäre ein Schnitt, für
    den es die Differenz gibt.

    Zwei Fälle enden hier statt in einer Zahl. Eine Zielebene parallel zur
    Achse wird nie erreicht; ohne diese Prüfung käme aus der Division durch
    beinahe null ein Körper von Kilometerhöhe. Und eine Fläche hinter der
    Skizze ergäbe eine negative Höhe — rückwärts durch die eigene Zeichnung.
    """
    direction = start.normal
    along = _dot(direction, target.normal)
    if abs(along) < _PARALLEL_ENOUGH:
        raise ValidationError(
            "up_to",
            _("Diese Fläche liegt parallel zur Richtung — sie wird nie erreicht."),
            value=str(target.origin),
            constraint="target_parallel",
            suggestions=[
                Action(id="sketch.pick_face", label=_("Eine andere Fläche wählen"), primary=True),
                Action(id="sketch.enter_height", label=_("Die Höhe von Hand eintragen")),
            ],
        )
    gap = (
        target.origin[0] - start.origin[0],
        target.origin[1] - start.origin[1],
        target.origin[2] - start.origin[2],
    )
    height = _dot(gap, target.normal) / along
    if height <= 0.0:
        raise ValidationError(
            "up_to",
            _("Diese Fläche liegt hinter der Skizze — von dort aus geht es nicht vorwärts."),
            value=f"{height:.3f}",
            constraint="target_behind",
            suggestions=[
                Action(
                    id="sketch.pick_face",
                    label=_("Eine Fläche in Richtung der Zeichnung wählen"),
                    primary=True,
                ),
                Action(id="sketch.flip_plane", label=_("Die Skizze auf die andere Fläche legen")),
            ],
        )
    return height
