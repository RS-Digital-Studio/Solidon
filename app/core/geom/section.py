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

from app.core.deferred import trimesh
from app.core.geom import enclosure
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import Vec3
from app.core.units import EPS_GEOM, is_zero

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


def plane_through(first: Vec3, second: Vec3, view: Vec3) -> SectionPlane | None:
    """Die Ebene, die eine im Bild gezeichnete Linie meint.

    Zwei angeklickte Punkte auf dem Körper geben eine Linie — und eine Linie
    allein legt keine Ebene fest, sie lässt sich um sich selbst drehen. Was
    die Drehung festhält, ist die Richtung, in die geschaut wurde: Gemeint ist
    immer der Schnitt *in den Bildschirm hinein*, denn das ist die Ebene, die
    der Nutzer als Strich sieht. Beides zusammen ist eindeutig, und deshalb
    steht die Blickrichtung hier im Argument statt in der Operation — die Op
    bekommt die fertige Ebene und hängt damit an keiner Kamerastellung (§11.2).

    ``None``, wenn die Linie zu kurz ist oder genau in die Blickrichtung
    zeigt: dann spannt sich keine Ebene auf, und eine geratene wäre schlimmer
    als keine (Regel 21).
    """
    along = np.asarray(second, dtype=float) - np.asarray(first, dtype=float)
    normal = np.cross(along, np.asarray(view, dtype=float))
    length = float(np.linalg.norm(normal))
    if length <= EPS_GEOM:
        return None
    normal = normal / length
    return SectionPlane(
        normal=(float(normal[0]), float(normal[1]), float(normal[2])),
        position=float(np.dot(normal, np.asarray(first, dtype=float))),
    )


def plane_patch(minimum: Vec3, maximum: Vec3, plane: SectionPlane) -> tuple[Vec3, ...]:
    """Der Teil einer Ebene, der im Hüllquader eines Körpers liegt.

    Das Polygon ist für die Vorschau des Trennwerkzeugs: Eine gezeichnete
    Linie zeigt nur die Kante der Ebene. Erst die Fläche bis an den Körperrand
    beantwortet sichtbar, was beim Anwenden wirklich getrennt wird. Sie ist
    reine Anzeigegeometrie und ändert weder Netz noch Dokument.

    Die Ecken kommen umlaufend sortiert zurück, damit der Viewport daraus eine
    Fläche zeichnen kann. Verfehlt die Ebene den Quader, ist das Ergebnis leer.
    """
    normal = np.asarray(plane.normal, dtype=float)
    length = float(np.linalg.norm(normal))
    if length <= EPS_GEOM:
        return ()
    normal /= length
    origin = np.asarray(plane.origin, dtype=float)
    low, high = np.asarray(minimum, dtype=float), np.asarray(maximum, dtype=float)
    corners = np.array(
        [
            (x, y, z)
            for x in (low[0], high[0])
            for y in (low[1], high[1])
            for z in (low[2], high[2])
        ],
        dtype=float,
    )
    bits = tuple((x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1))
    points: list[np.ndarray] = []

    def remember(point: np.ndarray) -> None:
        if not any(float(np.linalg.norm(point - known)) <= EPS_GEOM for known in points):
            points.append(point)

    for first in range(len(corners)):
        for second in range(first + 1, len(corners)):
            if sum(a != b for a, b in zip(bits[first], bits[second], strict=True)) != 1:
                continue
            start, end = corners[first], corners[second]
            start_distance = float(np.dot(start - origin, normal))
            end_distance = float(np.dot(end - origin, normal))
            if is_zero(start_distance):
                remember(start)
            if is_zero(end_distance):
                remember(end)
            crosses = (start_distance < -EPS_GEOM and end_distance > EPS_GEOM) or (
                end_distance < -EPS_GEOM and start_distance > EPS_GEOM
            )
            if crosses:
                share = start_distance / (start_distance - end_distance)
                remember(start + share * (end - start))

    if len(points) < 3:
        return ()

    centre = np.mean(points, axis=0)
    # Die am wenigsten parallele Weltachse gibt eine stabile erste Achse in
    # der Ebene — auch dann, wenn die Ebene fast genau waagerecht steht.
    seed = np.eye(3)[int(np.argmin(np.abs(normal)))]
    across = np.cross(normal, seed)
    across /= float(np.linalg.norm(across))
    upward = np.cross(normal, across)
    points.sort(
        key=lambda point: float(
            np.arctan2(np.dot(point - centre, upward), np.dot(point - centre, across))
        )
    )
    return tuple((float(point[0]), float(point[1]), float(point[2])) for point in points)


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
    """Eine Ebene. ``slice_plane`` deckelt, wenn die Eingabe wasserdicht ist.

    Das Deckeln braucht die Konturverschachtelung, und die kommt seit dem
    24.08.2026 aus :mod:`app.core.geom.enclosure` statt aus ``rtree`` — der
    Aufruf unten installiert sie, bevor hier geschnitten wird.
    """
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
    enclosure.install()
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
