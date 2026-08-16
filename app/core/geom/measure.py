"""Messen (Bauplan §18.3).

Der Viewport ist kein Anzeigefenster, sondern das Prüfwerkzeug, und Messen ist
der Teil davon, der exakt sein muss. Also lebt die Rechnung hier, wo sie gegen
bekannte Körper geprüft werden kann, und die Oberfläche sammelt nur Klicks.

Einrasten ist, was eine Messung reproduzierbar macht: ein Klick landet nie
genau auf einer Ecke, also wird er auf den nächsten Eckpunkt oder die nächste
Kante gezogen, bevor irgendetwas gerechnet wird. Gerundet wird nur in der
Anzeige (§11.2).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.types import BoundingBox, Vec3
from app.core.units import EPS_GEOM, round_display

#: Wie weit ein Klick von einem Eckpunkt oder einer Kante entfernt sein darf,
#: um darauf gezogen zu werden — relativ zur Modelldiagonale. Auf dem
#: Bildschirm etwa eine Fingerbreite.
SNAP_RADIUS_RELATIVE = 0.02


@dataclass(frozen=True, slots=True)
class SnapResult:
    """Wo ein Klick gelandet ist, und worauf er gezogen wurde."""

    point: Vec3
    kind: str
    """``vertex``, ``edge`` or ``free``."""
    distance: float = 0.0
    """Wie weit der Klick gewandert ist."""


@dataclass(frozen=True, slots=True)
class Measurement:
    """Ein Maß, das bleibt, bis es gelöscht wird (§18.3)."""

    kind: str
    """``distance``, ``diameter``, ``thickness`` or ``angle``."""
    value: float
    points: tuple[Vec3, ...] = ()
    object_id: str | None = None
    label: str = ""

    @property
    def shown(self) -> float:
        """Der Wert, wie er erscheint — auf Anzeigegenauigkeit gerundet."""
        return round_display(self.value)


@dataclass(slots=True)
class MeasurementList:
    """Die Maße einer Sitzung. Sie bleiben bis zum Löschen und verfallen
    nie von selbst.
    """

    entries: list[Measurement] = field(default_factory=list)

    def add(self, measurement: Measurement) -> Measurement:
        self.entries.append(measurement)
        return measurement

    def remove(self, index: int) -> None:
        if 0 <= index < len(self.entries):
            del self.entries[index]

    def clear(self) -> None:
        self.entries.clear()

    def __len__(self) -> int:
        return len(self.entries)


# --- Grundgrößen -----------------------------------------------------------------


def distance(a: Vec3, b: Vec3) -> float:
    """Von Punkt zu Punkt, in Millimetern."""
    return float(np.linalg.norm(np.asarray(b, dtype=float) - np.asarray(a, dtype=float)))


def angle_between(first: Vec3, second: Vec3) -> float:
    """Winkel zwischen zwei Richtungen in Grad, immer der kleinere."""
    one = np.asarray(first, dtype=float)
    two = np.asarray(second, dtype=float)
    lengths = float(np.linalg.norm(one)) * float(np.linalg.norm(two))
    if lengths <= EPS_GEOM:
        return 0.0
    cosine = float(np.clip(float(np.dot(one, two)) / lengths, -1.0, 1.0))
    return math.degrees(math.acos(abs(cosine))) if cosine < 0 else math.degrees(math.acos(cosine))


def bounding_box_of(meshes: list[MeshData]) -> BoundingBox:
    """Grenzen einer Auswahl — eine leere Auswahl gibt einen leeren Quader."""
    if not meshes:
        return BoundingBox((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
    lows = np.array([mesh.bounds.minimum for mesh in meshes], dtype=float)
    highs = np.array([mesh.bounds.maximum for mesh in meshes], dtype=float)
    low = lows.min(axis=0)
    high = highs.max(axis=0)
    return BoundingBox(
        (float(low[0]), float(low[1]), float(low[2])),
        (float(high[0]), float(high[1]), float(high[2])),
    )


def volume_of(meshes: list[MeshData]) -> float:
    """Volumen einer Auswahl in mm³. Nur bei geschlossenen Körpern sinnvoll."""
    return float(sum(mesh.volume for mesh in meshes))


# --- Einrasten ------------------------------------------------------------------


def snap(mesh: MeshData, point: Vec3, radius: float | None = None) -> SnapResult:
    """Zieht einen Klick auf den nächsten Eckpunkt, sonst auf die nächste
    Kante, sonst lässt ihn stehen.
    """
    limit = radius if radius is not None else mesh.bounds.diagonal * SNAP_RADIUS_RELATIVE
    target = np.asarray(point, dtype=float)

    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    if len(vertices):
        offsets = np.linalg.norm(vertices - target, axis=1)
        closest = int(np.argmin(offsets))
        if float(offsets[closest]) <= limit:
            found = vertices[closest]
            return SnapResult(
                point=(float(found[0]), float(found[1]), float(found[2])),
                kind="vertex",
                distance=float(offsets[closest]),
            )

    edge_point, edge_offset = _closest_point_on_edges(mesh, target)
    if edge_point is not None and edge_offset <= limit:
        return SnapResult(point=edge_point, kind="edge", distance=edge_offset)

    return SnapResult(point=(float(target[0]), float(target[1]), float(target[2])), kind="free")


def _closest_point_on_edges(mesh: MeshData, target: np.ndarray) -> tuple[Vec3 | None, float]:
    edges = np.asarray(mesh.raw.edges_unique, dtype=np.int64)
    if not len(edges):
        return None, math.inf
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    starts = vertices[edges[:, 0]]
    ends = vertices[edges[:, 1]]

    directions = ends - starts
    lengths = np.einsum("ij,ij->i", directions, directions)
    lengths[lengths < EPS_GEOM] = EPS_GEOM
    travel = np.clip(np.einsum("ij,ij->i", target - starts, directions) / lengths, 0.0, 1.0)
    projected = starts + directions * travel[:, None]
    offsets = np.linalg.norm(projected - target, axis=1)

    closest = int(np.argmin(offsets))
    found = projected[closest]
    return (float(found[0]), float(found[1]), float(found[2])), float(offsets[closest])


# --- Wandstärke ------------------------------------------------------------------


def wall_thickness(mesh: MeshData, point: Vec3, direction: Vec3 | None = None) -> float | None:
    """Dicke an einem Punkt: nach innen schießen und bis zum ersten Treffer
    messen (§18.3).

    Gibt None zurück, wo der Strahl den Körper verlässt, ohne etwas zu treffen —
    ein ehrliches „kann ich nicht sagen" schlägt eine erfundene Zahl.
    """
    origin = np.asarray(point, dtype=float)
    ray = _inward_direction(mesh, origin, direction)
    if ray is None:
        return None

    hits = ray_distances(mesh, origin, ray)
    return float(hits.min()) if len(hits) else None


def ray_distances(mesh: MeshData, origin: np.ndarray, direction: np.ndarray) -> np.ndarray:
    """Abstände von ``origin`` zu jedem Dreieck, das der Strahl trifft,
    nächstes zuerst.

    Möller-Trumbore über alle Dreiecke auf einmal. Vektorisiert ist das schnell
    genug für einzelne Strahlen und braucht keinen Raumindex — eine
    Abhängigkeit weniger für eine Handvoll Zeilen (AGENTS.md Regel 22).
    """
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    faces = np.asarray(mesh.raw.faces, dtype=np.int64)
    if not len(faces):
        return np.array([])

    first = vertices[faces[:, 0]]
    edge_one = vertices[faces[:, 1]] - first
    edge_two = vertices[faces[:, 2]] - first

    side = np.cross(direction, edge_two)
    determinant = np.einsum("ij,ij->i", edge_one, side)
    hits = np.abs(determinant) > EPS_GEOM
    if not hits.any():
        return np.array([])

    inverse = np.zeros_like(determinant)
    inverse[hits] = 1.0 / determinant[hits]

    offset = origin - first
    along = inverse * np.einsum("ij,ij->i", offset, side)
    across = np.cross(offset, edge_one)
    sideways = inverse * (across @ direction)
    travel = inverse * np.einsum("ij,ij->i", edge_two, across)

    inside = (
        hits
        & (along >= -EPS_GEOM)
        & (sideways >= -EPS_GEOM)
        & (along + sideways <= 1.0 + EPS_GEOM)
        & (travel > EPS_GEOM * 100.0)
    )
    return np.sort(travel[inside])


def _inward_direction(
    mesh: MeshData, origin: np.ndarray, direction: Vec3 | None
) -> np.ndarray | None:
    """Die Richtung zum Schießen: die gegebene, oder die invertierte
    Flächennormale.
    """
    if direction is not None:
        ray = np.asarray(direction, dtype=float)
        length = float(np.linalg.norm(ray))
        return ray / length if length > EPS_GEOM else None

    triangles = np.asarray(mesh.raw.triangles_center, dtype=float)
    if not len(triangles):
        return None
    nearest = int(np.argmin(np.linalg.norm(triangles - origin, axis=1)))
    normal = np.asarray(mesh.raw.face_normals[nearest], dtype=float)
    length = float(np.linalg.norm(normal))
    return -normal / length if length > EPS_GEOM else None
