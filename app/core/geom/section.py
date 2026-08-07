"""Einen Körper mit einer Ebene schneiden (Bauplan §18.2).

**Die Schnittfläche ist geschlossen.** Ohne Deckel sieht jeder Vollkörper hohl
aus, und die Wandstärke lässt sich nicht beurteilen — genau daran scheitern
naive Umsetzungen, und darum lebt das hier im Kern statt im Viewport: ein
gedeckelter Schnitt ist Geometrie, lässt sich also am Ergebnis nachmessen
statt an Pixeln vergleichen.

Eine zweite Ebene macht aus dem Schnitt eine Scheibe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import Vec3
from app.core.units import EPS_GEOM

_log = get_logger(__name__)

Axis = Literal["x", "y", "z"]

AXIS_NORMALS: dict[Axis, Vec3] = {
    "x": (1.0, 0.0, 0.0),
    "y": (0.0, 1.0, 0.0),
    "z": (0.0, 0.0, 1.0),
}


@dataclass(frozen=True, slots=True)
class SectionPlane:
    """Eine Schnittebene. Alles auf der positiven Seite der Normalen fällt weg."""

    normal: Vec3 = (0.0, 0.0, 1.0)
    position: float = 0.0
    """Abstand der Ebene vom Ursprung entlang ihrer Normalen, in Millimetern."""

    @classmethod
    def along(cls, axis: Axis, position: float = 0.0) -> SectionPlane:
        return cls(normal=AXIS_NORMALS[axis], position=position)

    @property
    def origin(self) -> Vec3:
        length = float(np.linalg.norm(self.normal)) or 1.0
        return (
            self.normal[0] / length * self.position,
            self.normal[1] / length * self.position,
            self.normal[2] / length * self.position,
        )

    def flipped(self) -> SectionPlane:
        return SectionPlane(
            normal=(-self.normal[0], -self.normal[1], -self.normal[2]),
            position=-self.position,
        )


@dataclass(frozen=True, slots=True)
class SectionResult:
    """Was vom Körper bleibt, und ob die Schnittfläche geschlossen werden
    konnte.
    """

    mesh: MeshData
    capped: bool
    """Falsch, wenn der Körper von vornherein offen war — dann gibt es keinen Deckel."""


def cut(mesh: MeshData, plane: SectionPlane, second: SectionPlane | None = None) -> SectionResult:
    """Schneidet einen Körper und schließt die Schnittfläche. Eine zweite
    Ebene lässt eine Scheibe übrig.

    Ein offenes Modell lässt sich nicht ehrlich deckeln — der Schnitt wird
    trotzdem gezeigt, aber als ungedeckelt gemeldet statt vorgetäuscht.
    """
    body: trimesh.Trimesh = mesh.raw
    capped = True

    for entry in (plane, second) if second is not None else (plane,):
        body, closed = _apply(body, entry)
        capped = capped and closed
        if not len(body.faces):
            return SectionResult(mesh=mesh.replacing(trimesh.Trimesh()), capped=capped)

    return SectionResult(mesh=_keeping_slots(mesh, body), capped=capped)


def _keeping_slots(mesh: MeshData, body: trimesh.Trimesh) -> MeshData:
    """§20: ein Schnitt ist eine Boolesche Op gegen einen Halbraum, und er
    behält die Slots.

    Die Schnittfläche selbst gehört zu keiner alten Oberfläche und bekommt den
    Vorgabe-Slot — dieselbe Regel wie eine Bohrungswand, aus demselben Grund:
    sie ist neues, sichtbares Material, kein Stück von etwas, das vorher da
    war.
    """
    from app.core.geom.attributes import transfer

    result = mesh.replacing(body)
    if not mesh.slots or result.slots:
        return result
    return transfer(result, [mesh])


def _apply(body: trimesh.Trimesh, plane: SectionPlane) -> tuple[trimesh.Trimesh, bool]:
    """Eine Ebene. ``slice_plane`` deckelt, wenn die Eingabe wasserdicht ist."""
    normal = np.asarray(plane.normal, dtype=float)
    length = float(np.linalg.norm(normal))
    if length <= EPS_GEOM:
        return body, True
    normal = normal / length
    # trimesh behält, was auf der positiven Seite liegt — die Normale zeigt
    # also andersherum: die sichtbare Hälfte ist die, von der die Ebene
    # wegschaut.
    watertight = bool(body.is_watertight)

    # Eine Ebene, die den Körper verfehlt, braucht keinen Schnitt — und ein
    # Schnitt ohne etwas zu deckeln ist der eine Fall, aus dem der
    # Polygon-Code nicht schlau wird.
    distances = _corner_distances(body, normal, np.asarray(plane.origin, dtype=float))
    if distances.max() <= EPS_GEOM:
        return body, watertight
    if distances.min() >= -EPS_GEOM:
        return trimesh.Trimesh(), watertight
    result = body.slice_plane(
        plane_origin=np.asarray(plane.origin, dtype=float),
        plane_normal=-normal,
        cap=watertight,
    )
    return result, watertight


def _corner_distances(body: trimesh.Trimesh, normal: np.ndarray, origin: np.ndarray) -> np.ndarray:
    """Vorzeichenbehafteter Abstand der Hüllquader-Ecken; positiv heißt
    „fällt weg".
    """
    low, high = body.bounds
    corners = np.array(
        [(x, y, z) for x in (low[0], high[0]) for y in (low[1], high[1]) for z in (low[2], high[2])]
    )
    return np.asarray((corners - origin) @ normal, dtype=float)


def section_volume(mesh: MeshData, plane: SectionPlane) -> float:
    """Das Volumen nach dem Schnitt — der ehrliche Test für eine geschlossene
    Schnittfläche.
    """
    return float(cut(mesh, plane).mesh.volume)
