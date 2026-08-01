"""Keeping the material slots through an operation (Bauplan §20).

"Boolean operations must not lose the slot assignment." They do lose it,
though — a boolean rebuilds the triangles, and the ones that come out are not
the ones that went in. So the assignment is carried over: every new triangle
asks which of the old ones it sits on, and takes its slot.

Nearest face, not nearest vertex: a triangle sits on a surface, and the surface
is what carries the colour. New cut faces belong to none of the old surfaces —
they get the slot the operation was told to give them, and by default that is
the one of the body being cut.

Which surfaces count as "old" is the caller's decision, and it matters: a body
that the operation removed is not a source of colour, however close its former
skin lies to the new one.

**After the voxel stage the transfer always runs** (§20). That stage replaces
the meshing entirely, so anything kept from before would be nonsense that
happens to have the right length.
"""

from __future__ import annotations

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.log import get_logger

_log = get_logger(__name__)

#: How far a new triangle may sit from an old surface and still count as being
#: on it, relative to the model diagonal. Beyond that it is a cut face.
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

    Without slots anywhere in the inputs nothing is carried and nothing is
    invented: a body with one material stays a body with one material.

    ``tolerance`` is how far a triangle may sit from an old surface and still
    count as being on it. It has to follow the stage that produced the mesh: a
    voxel result is stair-stepped by half a voxel everywhere, and measured with
    the tolerance of an exact boolean it would lose its colour to its own
    staircase.
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

    Distance to the *surface*, not to the nearest triangle centre. A boolean
    splits one big face into many small ones, and their centres end up far from
    the centre of the face they came from — measured that way, a body would lose
    its colour to its own re-triangulation.
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
