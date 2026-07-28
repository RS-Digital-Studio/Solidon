"""Hollowing out, with the vents that make it printable (Bauplan §25).

A solid part is material and hours nobody needs. Hollowing it is a good idea
with one condition attached: resin and unfused powder aside, an FDM print with a
sealed cavity traps air, and the first bridge over it sags. So the vent is not
an option here — it is the second half of the operation, and the default.

How the inner wall is found: the body is put on the same raster the analysis
maps use (§18.4), the raster is eroded by the wall thickness, and what is left
is meshed again. That is the voxel stage of §17.2 with its accuracy and its
honesty — the wall comes out within half a raster step, and the report says so.

An offset on the triangles themselves would be exact and would fold in on every
concave corner, which is where a hollow part needs the wall most.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import trimesh

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import Finding, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: How fine the raster is, relative to the wall being kept. A third of the wall
#: means the wall is right to within a sixth of itself.
PITCH_SHARE = 1.0 / 3.0

#: Never finer than this — a raster of a hundred million cells helps nobody.
MIN_PITCH = 0.3

#: Default vent diameter. Wide enough to let air out, narrow enough that the
#: hole does not have to be plugged afterwards.
VENT_DIAMETER = 4.0


@dataclass(slots=True)
class HollowResult:
    """The hollow body, and what had to be said about it."""

    mesh: MeshData
    removed: float = 0.0
    """Volume that came out, in mm³."""
    vents: tuple[Vec3, ...] = ()
    findings: list[Finding] = field(default_factory=list)


def hollow(
    mesh: MeshData,
    wall: float,
    *,
    vents: int = 1,
    vent_diameter: float = VENT_DIAMETER,
) -> HollowResult:
    """Leave a wall of ``wall`` millimetres and take out the rest."""
    if wall <= EPS_GEOM:
        raise ValueError("a wall thickness has to be positive")

    cavity = _cavity(mesh, wall)
    if cavity is None or cavity.triangle_count == 0:
        return HollowResult(
            mesh=mesh,
            findings=[
                Finding(
                    code="hollow.too_thin",
                    severity="warning",
                    message=_("Für diese Wandstärke bleibt kein Hohlraum übrig."),
                    values={"wall_mm": round(wall, 2)},
                )
            ],
        )

    before = mesh.volume
    outcome = boolean("difference", [mesh, cavity])
    body = outcome.mesh
    findings = list(outcome.findings)

    placed: tuple[Vec3, ...] = ()
    if vents > 0:
        body, placed = _vent(body, cavity, vent_diameter, vents)
        if not placed:
            findings.append(
                Finding(
                    code="hollow.no_vent",
                    severity="warning",
                    message=_(
                        "Es war keine Stelle für eine Entlüftung zu finden — "
                        "ein geschlossener Hohlraum drückt beim Drucken die Decke hoch."
                    ),
                )
            )

    removed = before - body.volume
    _log.info("hollowed out %.1f mm³ behind a %.2f mm wall", removed, wall)
    findings.append(
        Finding(
            code="hollow.done",
            severity="info",
            message=_("Ausgehöhlt. Die Wandstärke stimmt im Rahmen des Rasters."),
            values={
                "wall_mm": round(wall, 2),
                "removed_cm3": round(removed / 1000.0, 1),
                "vents": len(placed),
            },
        )
    )
    return HollowResult(mesh=body, removed=removed, vents=placed, findings=findings)


def _cavity(mesh: MeshData, wall: float) -> MeshData | None:
    """The inside of the body, pulled in by the wall thickness."""
    from scipy import ndimage

    from app.core.perceive.maps import solid_field

    pitch = max(wall * PITCH_SHARE, MIN_PITCH)
    field = solid_field(mesh, pitch)
    steps = max(1, round(wall / pitch))
    inner = ndimage.binary_erosion(field.filled, iterations=steps)
    if not inner.any():
        return None

    body = trimesh.voxel.ops.matrix_to_marching_cubes(matrix=inner, pitch=pitch)
    body.apply_translation(np.asarray(field.origin, dtype=float))
    return mesh.replacing(body) if len(body.faces) else None


def _vent(
    body: MeshData, cavity: MeshData, diameter: float, count: int
) -> tuple[MeshData, tuple[Vec3, ...]]:
    """Drill from the cavity out through the bottom.

    Downwards on purpose: a vent in the bottom face sits on the build plate,
    where it is neither seen nor in the way, and the air leaves the way the
    print grows.
    """
    from app.core.geom.transform import apply, translation

    inside = cavity.bounds
    outside = body.bounds
    if inside.size[2] <= EPS_GEOM:
        return body, ()

    spots: list[Vec3] = []
    for index in range(count):
        # Spread along X across the middle of the cavity, so several vents do
        # not end up in the same corner.
        share = (2 * index + 1) / (2 * count)
        x = inside.minimum[0] + inside.size[0] * share
        spots.append((float(x), float(inside.centre[1]), 0.0))

    drilled = body
    placed: list[Vec3] = []
    height = float(outside.size[2]) + 4.0
    for spot in spots:
        tool = trimesh.creation.cylinder(radius=diameter / 2.0, height=height)
        tool = apply(
            MeshData.of(tool),
            translation((spot[0], spot[1], float(outside.minimum[2]) + height / 2.0 - 2.0)),
        )
        try:
            drilled = boolean("difference", [drilled, tool]).mesh
        except Exception as problem:  # a vent that cannot be cut is not fatal
            _log.info("vent at %s failed: %s", spot, problem)
            continue
        placed.append(spot)
    return drilled, tuple(placed)
