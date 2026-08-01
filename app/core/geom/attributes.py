"""Die Materialslots durch eine Operation hindurch behalten (Bauplan §20).

„Boolesche Operationen dürfen die Slot-Zuweisung nicht verlieren." Sie
verlieren sie aber — eine Boolesche Op baut die Dreiecke neu, und die, die
herauskommen, sind nicht die, die hineingingen. Also wird die Zuweisung
übertragen: jedes neue Dreieck fragt, auf welchem der alten es sitzt, und nimmt
dessen Slot.

Nächste Fläche, nicht nächster Eckpunkt: ein Dreieck sitzt auf einer
Oberfläche, und die Oberfläche ist es, die die Farbe trägt. Neue Schnittflächen
gehören zu keiner der alten Oberflächen — sie bekommen den Slot, den die
Operation ihnen zuweisen soll, und per Vorgabe ist das der des Körpers, der
geschnitten wird.

Welche Oberflächen als „alt" zählen, entscheidet der Aufrufer, und das zählt:
ein Körper, den die Operation entfernt hat, ist keine Farbquelle — wie nah
seine ehemalige Haut auch an der neuen liegt.

**Nach der Voxelstufe läuft die Übertragung immer** (§20). Diese Stufe ersetzt
die Vernetzung vollständig — alles von vorher Behaltene wäre Unsinn, der
zufällig die richtige Länge hat.
"""

from __future__ import annotations

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.log import get_logger

_log = get_logger(__name__)

#: Wie weit ein neues Dreieck von einer alten Oberfläche sitzen darf und noch
#: als auf ihr liegend zählt, relativ zur Modelldiagonale. Darüber hinaus ist
#: es eine Schnittfläche.
NEAR_LIMIT = 0.002

#: Slot, den eine Fläche bekommt, die zu keiner Oberfläche der Eingaben
#: gehört.
DEFAULT_CUT_SLOT = 0


def transfer(
    result: MeshData,
    sources: list[MeshData],
    *,
    cut_slot: int = DEFAULT_CUT_SLOT,
    tolerance: float | None = None,
) -> MeshData:
    """Gibt jedem Dreieck von ``result`` den Slot der Oberfläche, auf der es liegt.

    Ohne Slots irgendwo in den Eingaben wird nichts übertragen und nichts
    erfunden: ein Körper mit einem Material bleibt ein Körper mit einem
    Material.

    ``tolerance`` ist, wie weit ein Dreieck von einer alten Oberfläche sitzen
    darf und noch als auf ihr liegend zählt. Sie muss der Stufe folgen, die das
    Netz erzeugt hat: ein Voxel-Ergebnis ist überall um einen halben Voxel
    getreppt, und mit der Toleranz einer exakten Booleschen Op gemessen verlöre
    es seine Farbe an die eigene Treppe.
    """
    if not any(mesh.slots for mesh in sources):
        return result
    body = result.raw
    if not len(body.faces):
        return result

    centres = np.asarray(body.triangles_center, dtype=float)
    slots = np.full(len(centres), cut_slot, dtype=np.int32)
    distance = np.full(len(centres), np.inf)

    for mesh in sources:
        if not mesh.slots:
            continue
        found, offset = _nearest(mesh, centres)
        closer = offset < distance
        slots[closer] = found[closer]
        distance[closer] = offset[closer]

    limit = tolerance if tolerance is not None else max(result.bounds.diagonal, 1.0) * NEAR_LIMIT
    slots[distance > limit] = cut_slot

    carried = int(np.count_nonzero(distance <= limit))
    _log.info("carried %d of %d face slots", carried, len(slots))
    return MeshData(raw=body, slots=tuple(int(entry) for entry in slots))


def _nearest(mesh: MeshData, points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Für jeden Punkt: der Slot des nächsten Dreiecks, und wie weit es weg war.

    Abstand zur *Oberfläche*, nicht zum nächsten Dreiecksmittelpunkt. Eine
    Boolesche Op teilt eine große Fläche in viele kleine, und deren Mittelpunkte
    landen weit von dem der Fläche entfernt, aus der sie kamen — so gemessen
    verlöre ein Körper seine Farbe an die eigene Neuvernetzung.
    """
    import trimesh

    slots = np.asarray(mesh.slots, dtype=np.int32)
    query = trimesh.proximity.ProximityQuery(mesh.raw)
    _closest, distance, triangle = query.on_surface(points)
    return slots[np.asarray(triangle, dtype=np.int64)], np.asarray(distance, dtype=float)


def with_slot(mesh: MeshData, slot: int) -> MeshData:
    """Ein Slot für den ganzen Körper — wo eine Farbe von Hand zugewiesen wird."""
    return MeshData(raw=mesh.raw, slots=tuple([int(slot)] * len(mesh.raw.faces)))


def counts(mesh: MeshData) -> dict[int, int]:
    """Wie viele Dreiecke in welchem Slot sitzen. Liest der Prüfbericht und
    der Export."""
    if not mesh.slots:
        return {0: len(mesh.raw.faces)}
    values, amounts = np.unique(np.asarray(mesh.slots), return_counts=True)
    return {int(value): int(amount) for value, amount in zip(values, amounts, strict=True)}


def used_slots(mesh: MeshData) -> tuple[int, ...]:
    return tuple(sorted(counts(mesh)))
