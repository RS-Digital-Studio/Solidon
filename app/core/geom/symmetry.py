"""Spiegelsymmetrie eines Körpers messen (Bauplan §22.3, RM-080 T6).

Ein symmetrisches Teil wird am liebsten in seiner Symmetrieebene geteilt:
zwei gleiche Hälften, eine Druckeinstellung für beide, und die Naht liegt dort,
wo ein Mensch sie auch hinlegen würde. Dafür muss die Suche wissen, **ob** ein
Körper spiegelgleich ist — und das wird gemessen, nicht aus dem Hüllquader
oder dem Dateinamen geschlossen.

Gemessen wird so: Die Ebene quer zu einer Richtung liegt, wenn es sie gibt,
genau in der Mitte der Ausdehnung — eine Spiegelung vertauscht die beiden
äußersten Punkte. Die Ecken und die Dreiecksmitten des Netzes werden an ihr
gespiegelt, und der **größte** Abstand eines gespiegelten Punkts zur
Oberfläche entscheidet (:func:`app.core.geom.mesh.max_distance_to_surface`,
exakt und ohne ``rtree``). Liegt er unter der Vergleichstoleranz aus
:func:`app.core.units.match_tolerance`, ist der Körper in dieser Ebene
spiegelgleich.

Die Toleranz ist die der Merkmalsvergleiche (§11.2) und keine eigene Zahl: Ein
fremdes Netz ist selten spiegelgleich trianguliert — eine Rundung aus Sehnen
liegt auf der einen Seite anders als auf der anderen, und eine gespiegelte Ecke
landet dann bis zur Sehnenhöhe neben der Fläche. Was darüber hinausgeht, ist
eine Form und kein Rauschen.

Deterministisch ist die Antwort, weil nichts gezogen wird: dieselben Punkte,
dieselbe Reihenfolge, dieselbe exakte Abstandsrechnung.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

from app.core import units
from app.core.geom.mesh import MeshData, max_distance_to_surface
from app.core.types import CancelToken, Vec3
from app.core.units import EPS_GEOM

#: Wie viele gespiegelte Punkte die Vorprobe höchstens misst, bevor alle
#: gemessen werden. Die Vorprobe ist eine **exakte** Absage: Das Maximum über
#: eine Teilmenge ist höchstens das Maximum über alle, liegt es schon über der
#: Toleranz, ist der Körper nicht spiegelgleich. Sie spart die volle Messung an
#: den unsymmetrischen Körpern, und das ist die Mehrheit.
PROBE_POINTS: Final = 2048


@dataclass(frozen=True, slots=True)
class MirrorPlane:
    """Eine gemessene Spiegelebene: ``normal · x = position``."""

    normal: Vec3
    position: float
    deviation: float
    """Der größte Abstand eines gespiegelten Punkts zur Oberfläche, in mm."""
    tolerance: float
    """Die Grenze, unter der das als spiegelgleich galt, in mm."""


def mirror_plane(
    mesh: MeshData,
    normal: Vec3,
    *,
    cancelled: CancelToken | None = None,
) -> MirrorPlane | None:
    """Die Spiegelebene quer zu ``normal`` — oder ``None``, wenn der Körper dort keine hat.

    Zwei billige Bedingungen stehen vor der teuren Messung, beide notwendig
    für eine Spiegelebene: Sie liegt in der Mitte der Ausdehnung, und der
    **Flächenschwerpunkt** der Oberfläche liegt auf ihr. Die zweite gilt auch
    bei ungleich triangulierten Seiten, bis auf die Sehnenhöhe, und scheidet
    die meisten unsymmetrischen Körper ohne Abstandsrechnung aus.
    """
    raw = mesh.raw
    vertices = np.asarray(raw.vertices, dtype=float)
    faces = np.asarray(raw.faces, dtype=np.int64)
    if not len(vertices) or not len(faces):
        return None
    direction = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(direction))
    if length <= EPS_GEOM:
        return None
    direction = direction / length

    heights = vertices @ direction
    low, high = float(heights.min()), float(heights.max())
    if high - low <= EPS_GEOM:
        return None
    position = (low + high) / 2.0
    tolerance = units.match_tolerance(float(np.linalg.norm(mesh.bounds.size)))

    triangles = vertices[faces]
    centroids = triangles.mean(axis=1)
    areas = 0.5 * np.linalg.norm(
        np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1
    )
    total = float(areas.sum())
    if total <= EPS_GEOM:
        return None
    if abs(float(areas @ (centroids @ direction)) / total - position) > tolerance:
        return None

    points = np.concatenate([vertices, centroids])
    reflected = points - 2.0 * (points @ direction - position)[:, None] * direction
    stride = max(1, len(reflected) // PROBE_POINTS)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if stride > 1 and max_distance_to_surface(raw, reflected[::stride]) > tolerance:
        return None
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    deviation = max_distance_to_surface(raw, reflected)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if deviation > tolerance:
        return None
    return MirrorPlane(
        normal=(float(direction[0]), float(direction[1]), float(direction[2])),
        position=position,
        deviation=deviation,
        tolerance=tolerance,
    )
