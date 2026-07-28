"""Working on the net itself (Bauplan §25, category "Netz").

Three operations that change how a body is described without meaning to change
what it is: fewer triangles, smoother triangles, more even triangles. They earn
their place with pillar B — a generated mesh arrives with half a million
triangles and the stair steps of the grid it came off, and both are in the way
of everything that follows.

All three are lossy, and each says how much it lost. A decimation that quietly
moves a bore by a tenth of a millimetre is worse than one that says so.
"""

from __future__ import annotations

import dataclasses
from typing import cast

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, OpContext, OpResult, Severity
from app.i18n import _

_log = get_logger(__name__)

#: Below this many triangles nothing is decimated. A body that small is not
#: where the time goes, and every removal costs shape.
DECIMATE_FLOOR = 500

#: How far a decimation may move the surface before it is worth a warning, as a
#: share of the model diagonal. Half a percent on a 100 mm part is 0.5 mm — more
#: than a fit tolerates.
DEVIATION_WARN = 0.005


def deviation(before: MeshData, after: MeshData) -> float:
    """How far the new surface sits from the old one, at worst, in mm.

    Measured, not estimated: every vertex of the result is asked for its
    distance to the original surface. That is the number a fit lives or dies by.
    """
    if not after.triangle_count or not before.triangle_count:
        return 0.0
    query = trimesh.proximity.ProximityQuery(before.raw)
    _closest, distance, _triangle = query.on_surface(np.asarray(after.raw.vertices, dtype=float))
    return float(np.max(distance)) if len(distance) else 0.0


def decimate(mesh: MeshData, target: int) -> MeshData:
    """Fewer triangles for the same shape, as far as that is possible."""
    if mesh.triangle_count <= max(target, DECIMATE_FLOOR):
        return mesh
    reduced = mesh.raw.simplify_quadric_decimation(face_count=target)
    _log.info("decimated %d to %d triangles", mesh.triangle_count, len(reduced.faces))
    return mesh.replacing(reduced)


def smooth(mesh: MeshData, iterations: int) -> MeshData:
    """Take the noise off a surface without pulling it in.

    Taubin rather than Laplace: plain smoothing shrinks a body a little with
    every pass, and after ten passes a 20 mm pin no longer fits a 20 mm hole.
    """
    body = mesh.raw.copy()
    trimesh.smoothing.filter_taubin(body, iterations=iterations)
    return mesh.replacing(body)


def remesh(mesh: MeshData, edge: float) -> MeshData:
    """Split every edge longer than ``edge`` until none is.

    Not a full remesher — it only subdivides. That is what an analysis needs
    (an even sampling of the surface) and it never moves a point, so nothing is
    lost. Making triangles *coarser* where they are dense is decimation's job.
    """
    vertices, faces = trimesh.remesh.subdivide_to_size(
        np.asarray(mesh.raw.vertices, dtype=float),
        np.asarray(mesh.raw.faces, dtype=np.int64),
        max_edge=edge,
    )
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    _log.info("remeshed %d to %d triangles", mesh.triangle_count, len(body.faces))
    return mesh.replacing(body)


# --- operations -------------------------------------------------------------------


@op_params
class DecimateParams(BaseParams):
    triangles: int = param(
        title=_("Dreiecke"),
        default=50_000,
        minimum=DECIMATE_FLOOR,
        maximum=5_000_000,
        doc=_("Zielzahl. Weniger heißt schneller und ungenauer — wie viel, sagt der Bericht."),
    )


@register_op(
    name="decimate_mesh",
    title=_("Dezimieren"),
    category="mesh",
    params=DecimateParams,
    consumes=1,
    produces=1,
    doc=_(
        "Verringert die Dreieckszahl. Die größte Abweichung zur Ausgangsfläche "
        "wird gemessen und gemeldet."
    ),
)
def decimate_mesh(ctx: OpContext) -> OpResult:
    params = cast(DecimateParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = decimate(before, params.triangles)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=after)],
        findings=_deviation_findings(before, after, source.id),
    )


@op_params
class SmoothParams(BaseParams):
    iterations: int = param(
        title=_("Durchgänge"),
        default=5,
        minimum=1,
        maximum=50,
        doc=_("Mehr Durchgänge heißt glatter. Kanten verschwinden dabei mit."),
    )


@register_op(
    name="smooth_mesh",
    title=_("Glätten"),
    category="mesh",
    params=SmoothParams,
    consumes=1,
    produces=1,
    doc=_(
        "Nimmt die Rauheit aus einer Oberfläche, ohne den Körper zu schrumpfen. "
        "Für erzeugte Netze mit Treppenstufen (§27)."
    ),
)
def smooth_mesh(ctx: OpContext) -> OpResult:
    params = cast(SmoothParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = smooth(before, params.iterations)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=after)],
        findings=_deviation_findings(before, after, source.id),
    )


@op_params
class RemeshParams(BaseParams):
    edge: float = param(
        title=_("Kantenlänge"),
        default=1.0,
        unit="mm",
        minimum=0.05,
        maximum=50.0,
        doc=_("Jede längere Kante wird geteilt. Kürzer heißt gleichmäßiger und größer."),
    )


@register_op(
    name="remesh_mesh",
    title=_("Neu vernetzen"),
    category="mesh",
    params=RemeshParams,
    consumes=1,
    produces=1,
    doc=_("Teilt lange Kanten, bis das Netz gleichmäßig ist. Die Form bleibt exakt."),
)
def remesh_mesh(ctx: OpContext) -> OpResult:
    params = cast(RemeshParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    after = remesh(before, params.edge)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=after)],
        findings=[
            Finding(
                code="mesh.remeshed",
                severity="info",
                message=_("Das Netz wurde feiner unterteilt; die Form ist unverändert."),
                object_id=source.id,
                values={"before": before.triangle_count, "after": after.triangle_count},
            )
        ],
    )


def _deviation_findings(before: MeshData, after: MeshData, object_id: str) -> list[Finding]:
    """Say what it cost — measured against the surface, not guessed from counts."""
    moved = deviation(before, after)
    limit = max(before.bounds.diagonal, 1.0) * DEVIATION_WARN
    severity: Severity = "warning" if moved > limit else "info"
    return [
        Finding(
            code="mesh.deviation",
            severity=severity,
            message=(
                _("Die Fläche hat sich dabei spürbar verschoben — Passungen neu prüfen.")
                if severity == "warning"
                else _("Die Fläche hat sich dabei kaum verschoben.")
            ),
            object_id=object_id,
            values={
                "deviation_mm": round(moved, 4),
                "before": before.triangle_count,
                "after": after.triangle_count,
            },
        )
    ]
