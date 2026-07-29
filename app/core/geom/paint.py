"""Painting slots onto a surface (Bauplan §20, "Bemalen").

A brush with a radius, and edge detection — which is the part that makes it
usable. Painting a radius into a mesh without it means the colour goes round
the corner onto the back of the part, and cleaning that up by hand costs more
than the painting saved.

So the brush spreads over the surface rather than through space: it starts at
the triangle that was clicked and walks to neighbours, and it stops at an edge
sharper than a given angle. The top of a lid gets painted, the side does not,
without anybody drawing a boundary.

The other half of §20 — texture to slots — is in :mod:`app.core.geom.texture`.
This one is the manual counterpart: for the lettering that has no texture, and
for correcting what the quantisation got wrong.
"""

from __future__ import annotations

import dataclasses
from collections import deque
from typing import cast

import numpy as np

from app.core.geom.attributes import counts
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, MaterialSlot, OpContext, OpResult, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Above this angle between two triangles the brush stops. Thirty degrees keeps
#: it on a rounded face and holds it back at anything that reads as an edge.
EDGE_ANGLE = 30.0

#: How many filaments a slot number may name (§20, same as the colour ops).
MAX_SLOTS = 8


def brush(
    mesh: MeshData,
    point: Vec3,
    radius: float,
    slot: int,
    *,
    edge_angle: float = EDGE_ANGLE,
) -> MeshData:
    """Paint every triangle around ``point`` that belongs to the same surface.

    Reached over the surface, not through the air: a walk from neighbour to
    neighbour that stops at sharp edges and at the radius. Both limits matter —
    the radius alone would paint through a wall, the edge alone would paint a
    whole side.
    """
    body = mesh.raw
    faces = len(body.faces)
    if not faces or radius <= EPS_GEOM:
        return mesh

    centres = np.asarray(body.triangles_center, dtype=float)
    away = np.linalg.norm(centres - np.asarray(point, dtype=float), axis=1)
    start = int(np.argmin(away))
    if away[start] > radius:
        # The stroke did not land on the body. There is always a nearest
        # triangle, and painting it because it was the nearest would put colour
        # on the other side of the part from where somebody clicked.
        return mesh

    within = np.linalg.norm(centres - centres[start], axis=1) <= radius
    reached = _walk(mesh, start, within, edge_angle)

    slots = list(mesh.slots) if mesh.slots else [0] * faces
    for index in reached:
        slots[index] = int(slot)
    _log.info("painted %d of %d faces into slot %d", len(reached), faces, slot)
    return MeshData(raw=body, slots=tuple(slots))


def _walk(mesh: MeshData, start: int, within: np.ndarray, edge_angle: float) -> set[int]:
    """Faces reachable from ``start`` without crossing an edge or the radius."""
    adjacency = np.asarray(mesh.raw.face_adjacency)
    if not len(adjacency):
        return {start} if within[start] else set()

    angles = np.degrees(np.asarray(mesh.raw.face_adjacency_angles, dtype=float))
    passable = angles <= edge_angle

    neighbours: dict[int, list[int]] = {}
    for (first, second), open_edge in zip(adjacency, passable, strict=True):
        if not open_edge:
            continue
        neighbours.setdefault(int(first), []).append(int(second))
        neighbours.setdefault(int(second), []).append(int(first))

    seen = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for other in neighbours.get(current, ()):
            if other in seen or not within[other]:
                continue
            seen.add(other)
            queue.append(other)
    return seen


@op_params
class PaintParams(BaseParams):
    slot: int = param(
        title=_("Slot"),
        default=1,
        minimum=0,
        maximum=MAX_SLOTS - 1,
        doc=_("In welchen Materialslot der Pinsel malt."),
    )
    radius: float = param(title=_("Radius"), default=10.0, unit="mm", minimum=0.1, maximum=500.0)
    x: float = param(title=_("Position X"), default=0.0, unit="mm")
    y: float = param(title=_("Position Y"), default=0.0, unit="mm")
    z: float = param(title=_("Position Z"), default=0.0, unit="mm")
    edge_angle: float = param(
        title=_("Kantenwinkel"),
        default=EDGE_ANGLE,
        unit="grad",
        minimum=1.0,
        maximum=180.0,
        placement="advanced",
        doc=_("Ab diesem Winkel hält der Pinsel an. 180 Grad heißt: über alles hinweg."),
    )
    name: str = param(title=_("Bezeichnung"), default="", placement="advanced")


@register_op(
    name="paint_slot",
    title=_("Bemalen"),
    category="colour",
    params=PaintParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    doc=_(
        "Malt einen Materialslot auf die Fläche um einen Punkt. Der Pinsel läuft "
        "über die Oberfläche und hält an Kanten an, statt um die Ecke zu malen."
    ),
)
def paint_slot(ctx: OpContext) -> OpResult:
    params = cast(PaintParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    painted = brush(
        mesh,
        (params.x, params.y, params.z),
        params.radius,
        params.slot,
        edge_angle=params.edge_angle,
    )
    covered = counts(painted).get(params.slot, 0)
    if not covered:
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="colour.nothing_painted",
                    severity="warning",
                    message=_("An dieser Stelle war keine Fläche zu treffen."),
                    object_id=source.id,
                    values={"radius_mm": round(params.radius, 2)},
                )
            ],
        )

    known = {entry.index: entry for entry in source.material_slots}
    known.setdefault(
        params.slot,
        MaterialSlot(
            index=params.slot, name=params.name or f"{_('Slot').translate()} {params.slot}"
        ),
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=painted,
                material_slots=[known[index] for index in sorted(known)],
            )
        ],
        findings=[
            Finding(
                code="colour.painted",
                severity="info",
                message=_("Die Fläche wurde bemalt."),
                object_id=source.id,
                values={"faces": covered, "slot": params.slot},
            )
        ],
    )
