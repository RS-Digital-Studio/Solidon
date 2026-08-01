"""Arbeit am Netz selbst (Bauplan §25, Kategorie „Netz").

Drei Operationen, die ändern, wie ein Körper beschrieben ist, ohne ändern zu
wollen, was er ist: weniger Dreiecke, glattere Dreiecke, gleichmäßigere
Dreiecke. Ihren Platz verdienen sie mit Säule B — ein erzeugtes Netz kommt mit
einer halben Million Dreiecken und den Treppenstufen des Rasters an, von dem
es stammt, und beides steht allem Folgenden im Weg.

Alle drei sind verlustbehaftet, und jede sagt, wie viel sie verloren hat. Eine
Dezimierung, die eine Bohrung still um einen Zehntelmillimeter verschiebt, ist
schlimmer als eine, die es sagt.
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

#: Unter so vielen Dreiecken wird nichts dezimiert. Bei einem so kleinen
#: Körper geht die Zeit nicht verloren, und jede Entfernung kostet Form.
DECIMATE_FLOOR = 500

#: Wie weit eine Dezimierung die Oberfläche verschieben darf, bevor es eine
#: Warnung wert ist — als Anteil der Modelldiagonale. Ein halbes Prozent auf
#: einem 100-mm-Teil sind 0,5 mm, mehr als eine Passung verträgt.
DEVIATION_WARN = 0.005


def deviation(before: MeshData, after: MeshData) -> float:
    """Wie weit die neue Oberfläche schlimmstenfalls von der alten sitzt, in mm.

    Gemessen, nicht geschätzt: jeder Eckpunkt des Ergebnisses wird nach seinem
    Abstand zur ursprünglichen Oberfläche gefragt. Das ist die Zahl, an der
    eine Passung lebt oder stirbt.
    """
    if not after.triangle_count or not before.triangle_count:
        return 0.0
    query = trimesh.proximity.ProximityQuery(before.raw)
    _closest, distance, _triangle = query.on_surface(np.asarray(after.raw.vertices, dtype=float))
    return float(np.max(distance)) if len(distance) else 0.0


def decimate(mesh: MeshData, target: int) -> MeshData:
    """Weniger Dreiecke für dieselbe Form, soweit das möglich ist."""
    if mesh.triangle_count <= max(target, DECIMATE_FLOOR):
        return mesh
    reduced = mesh.raw.simplify_quadric_decimation(face_count=target)
    _log.info("decimated %d to %d triangles", mesh.triangle_count, len(reduced.faces))
    return mesh.replacing(reduced)


def smooth(mesh: MeshData, iterations: int) -> MeshData:
    """Nimmt das Rauschen von einer Oberfläche, ohne sie einzuziehen.

    Taubin statt Laplace: schlichtes Glätten schrumpft einen Körper mit jedem
    Durchgang ein wenig, und nach zehn Durchgängen passt ein 20-mm-Stift nicht
    mehr in ein 20-mm-Loch.
    """
    body = mesh.raw.copy()
    trimesh.smoothing.filter_taubin(body, iterations=iterations)
    return mesh.replacing(body)


def remesh(mesh: MeshData, edge: float) -> MeshData:
    """Teilt jede Kante, die länger als ``edge`` ist, bis keine mehr übrig ist.

    Kein vollwertiger Remesher — er unterteilt nur. Das ist, was eine Analyse
    braucht (eine gleichmäßige Abtastung der Oberfläche), und er verschiebt nie
    einen Punkt, es geht also nichts verloren. Dreiecke dort *gröber* zu
    machen, wo sie dicht sind, ist die Aufgabe der Dezimierung.
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
    """Sagt, was es gekostet hat — gemessen an der Oberfläche, nicht aus
    Zahlen geraten.
    """
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
