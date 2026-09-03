"""Verschieben, Drehen und Skalieren (Bauplan §25, §18.11).

Jede Manipulation ist eine Operation — auch die, die als Ziehen im Viewport
begann (§18.11). Also sitzt die Rechnung hier, und der Gizmo entscheidet nur,
welche Zahlen er übergibt; das Undo nimmt ein Ziehen danach genauso zurück wie
einen Menüeintrag.

Das Einrasten gehört zur Interaktion, nicht zur Geometrie: die Oberfläche rundet
den Wert, die Operation speichert, was wirklich angewandt wurde.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.types import Vec3
from app.core.units import EPS_DISPLAY, EPS_GEOM

Axis = Literal["x", "y", "z"]
Anchor = Literal["centre", "origin", "bed"]
"""Worum eine Drehung oder Skalierung dreht: die Mitte des Körpers, der
Weltursprung, oder der Punkt, an dem der Körper auf der Platte aufsitzt."""

AXIS_VECTORS: dict[Axis, Vec3] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


def anchor_point(mesh: MeshData, anchor: Anchor) -> Vec3:
    """Der Fixpunkt einer Transformation."""
    bounds = mesh.bounds
    if anchor == "origin":
        return (0.0, 0.0, 0.0)
    if anchor == "bed":
        centre = bounds.centre
        return (centre[0], centre[1], bounds.minimum[2])
    return bounds.centre


def translation(offset: Vec3) -> np.ndarray:
    matrix = np.eye(4)
    matrix[:3, 3] = np.asarray(offset, dtype=float)
    return matrix


def rotation(axis: Axis, degrees: float, about: Vec3 = (0.0, 0.0, 0.0)) -> np.ndarray:
    return np.asarray(
        trimesh.transformations.rotation_matrix(
            math.radians(degrees), np.asarray(AXIS_VECTORS[axis], dtype=float), np.asarray(about)
        ),
        dtype=float,
    )


def scaling(factors: Vec3, about: Vec3 = (0.0, 0.0, 0.0)) -> np.ndarray:
    """Gleichmäßige oder achsweise Skalierung um einen Fixpunkt."""
    values = np.asarray(factors, dtype=float)
    if np.any(np.abs(values) <= EPS_GEOM):
        raise ValueError("a scale factor of zero would collapse the body")
    matrix = np.eye(4)
    matrix[0, 0], matrix[1, 1], matrix[2, 2] = values
    pivot = np.asarray(about, dtype=float)
    matrix[:3, 3] = pivot - values * pivot
    return matrix


def apply(mesh: MeshData, matrix: np.ndarray) -> MeshData:
    """Gibt eine transformierte Kopie zurück. Die Eingabe wird nie
    angefasst (AGENTS.md Regel 3)."""
    body = mesh.raw.copy()
    body.apply_transform(matrix)
    return mesh.replacing(body)


def place_on_bed(mesh: MeshData) -> MeshData:
    """Setzt den Körper auf Z = 0, ohne ihn seitlich zu verschieben
    (§17.1 Schritt 6)."""
    return apply(mesh, translation((0.0, 0.0, -mesh.bounds.minimum[2])))


@dataclass(frozen=True, slots=True)
class TransformSteps:
    """Ein Gizmo-Ziehen, zerlegt in Dinge, die eine Operation ausdrücken
    kann (§18.11).

    Eine gezogene Matrix ist danach nicht mehr änderbar; ``verschieben 12 mm``
    schon. Also wird die Matrix einmal zerlegt, hier, und was den Stapel
    erreicht, sind Operationen, deren Zahlen sich weiter ändern lassen (§2.1).
    """

    offset: Vec3 = (0.0, 0.0, 0.0)
    axis: Axis | None = None
    angle: float = 0.0
    scale: float = 1.0

    @property
    def moves(self) -> bool:
        return any(abs(value) > EPS_DISPLAY for value in self.offset)

    @property
    def turns(self) -> bool:
        return self.axis is not None and abs(self.angle) > EPS_DISPLAY

    @property
    def resizes(self) -> bool:
        return abs(self.scale - 1.0) > 1e-4


def decompose_transform(matrix: np.ndarray) -> TransformSteps:
    """Zerlegt eine Transformation in Versatz, Drehung um eine Hauptachse
    und Skalierung.

    Der Gizmo dreht um seine eigenen Achsen, eine Drehung landet also auf x, y
    oder z; ein kombiniertes Ziehen ergibt schlicht mehrere Schritte, die dann
    als eine Transaktion reisen (§15.5).
    """
    scales, _shear, angles, offset, _perspective = trimesh.transformations.decompose_matrix(
        np.asarray(matrix, dtype=float)
    )
    degrees = [math.degrees(value) for value in angles]
    largest = max(range(3), key=lambda index: abs(degrees[index]))
    axis: Axis | None = ("x", "y", "z")[largest]
    angle = degrees[largest]
    if abs(angle) <= EPS_DISPLAY:
        axis, angle = None, 0.0

    scale = float(np.mean(scales))
    return TransformSteps(
        offset=(float(offset[0]), float(offset[1]), float(offset[2])),
        axis=axis,
        angle=angle,
        scale=scale,
    )


def snap_to_step(value: float, step: float) -> float:
    """Raster- und Winkeleinrasten. Schrittweite null heißt: kein
    Einrasten (§18.11)."""
    if step <= EPS_GEOM:
        return value
    return round(value / step) * step


def snap_near(value: float, step: float, zone: float) -> float:
    """Rastet **nur in der Nähe** eines Vielfachen ein — sonst freie Fahrt.

    Der Unterschied zu :func:`snap_to_step` ist die Zone: Jenes zieht jeden
    Wert auf das nächste Vielfache, also **jeden**. Beim Drehen ist das
    falsch herum — man dreht frei, und ein Raster, das immer greift, macht
    aus einer Geste eine Auswahl aus acht Möglichkeiten. Vorher stand die
    Winkelvorgabe deshalb auf null, also gar kein Einrasten, und dann trifft
    niemand genau 45 Grad.

    Hier ist beides zu haben (Robert, 03.09.2026): „freies drehen, aber kurzes
    einrasten bei allen 45 grad winkeln außer man dreht weiter". Innerhalb der
    Zone um ein Vielfaches gilt das Vielfache — der Wert bleibt einen Moment
    stehen, obwohl die Maus weiterzieht. Außerhalb gilt der rohe Wert, und wer
    weiterdreht, kommt heraus.

    Zone null oder Schritt null heißt: kein Magnet, der Wert bleibt, wie er
    ist. Eine Zone von der halben Schrittweite ergäbe wieder
    :func:`snap_to_step`, also ist sie darauf begrenzt.
    """
    if step <= EPS_GEOM or zone <= EPS_GEOM:
        return value
    nearest = round(value / step) * step
    if abs(value - nearest) <= min(zone, step / 2.0):
        return nearest
    return value


def rotation_about(direction: Vec3, origin: Vec3, degrees: float) -> np.ndarray:
    """Die Matrix, die um eine Achse durch einen Punkt dreht.

    Hier und nicht in der Ansicht, weil die Ansicht keine Geometrie rechnet
    (§8) — sie braucht die Matrix, um einen laufenden Zug auf seine Raste zu
    ziehen, und das ist eine Drehung wie jede andere.
    """
    return np.asarray(
        trimesh.transformations.rotation_matrix(math.radians(degrees), direction, origin),
        dtype=float,
    )


def along_normal(offset: Vec3, normal: Vec3) -> float:
    """Wie weit ein Zug entlang einer Flächennormalen führt (§18.11).

    Die Maus zieht in drei Richtungen, eine Fläche wandert nur in einer — was
    quer dazu passiert, ist keine Bewegung dieser Fläche und wird verworfen.
    Ohne diese Projektion hätte ein Griff an die Fläche denselben Effekt wie
    ein Griff ans Objekt, und Press/Pull wäre nur ein Verschieben mit einem
    anderen Namen.

    Das Vorzeichen bleibt: nach außen ist positiv, nach innen negativ — genau
    die Zählung, die ``push_face`` erwartet.
    """
    length = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
    if length <= EPS_GEOM:
        return 0.0
    return (offset[0] * normal[0] + offset[1] * normal[1] + offset[2] * normal[2]) / length
