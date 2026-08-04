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

from app.core.errors import CANCEL, ValidationError
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


# --- Aufdicken (Konzept P15 §7 Etappe 6, D15) -----------------------------------


@op_params
class ThickenParams(BaseParams):
    thickness: float = param(
        title=_("Wandstärke"),
        default=2.0,
        unit="mm",
        minimum=0.1,
        doc=_(
            "Wie dick die Wand wird. Unter zwei Extrusionsbahnen ist sie fragil — "
            "was das für dieses Material heißt, sagt der Prüfbericht."
        ),
    )


@register_op(
    name="thicken",
    title=_("Fläche aufdicken"),
    category="mesh",
    params=ThickenParams,
    consumes=1,
    produces=1,
    doc=_(
        "Gibt einer offenen Fläche eine Wand und macht sie damit zu einem Körper. "
        "Der Weg für ein Netz, das als Fläche ankommt statt als Volumen."
    ),
)
def thicken(ctx: OpContext) -> OpResult:
    """Aus einer Fläche einen Körper machen.

    Sechs von 68 echten Modellen sind nicht geschlossen; das ist bei
    Community-Modellen normal, und bis hierher war es eine Sackgasse. Der
    Prüfbericht meldete es korrekt, und danach ging nichts mehr: eine
    Boolesche Operation braucht ein Volumen, und eine Fläche hat keines.

    Ein Körper, der schon einer ist, bekommt **keine** zweite Haut, sondern
    eine Meldung. Ihn stillschweigend zu verdoppeln wäre ein Ergebnis, das
    aussieht wie das Original und beim Schneiden auffällt.
    """
    params = cast(ThickenParams, ctx.params)
    source = ctx.inputs[0]
    before = as_mesh_data(source.mesh)
    if before.raw.is_watertight:
        raise ValidationError(
            "thickness",
            _(
                "Dieser Körper ist schon geschlossen — eine zweite Haut darüber wäre "
                "keine Wand, sondern eine Verdopplung."
            ),
            value=params.thickness,
            constraint="already_solid",
            suggestions=[CANCEL],
        )

    thickened = _thickened(before, params.thickness)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=thickened, features={})],
        findings=[
            Finding(
                code="mesh.thickened",
                severity="info",
                message=_("Aus einer offenen Fläche wurde ein Körper mit Wandstärke."),
            )
        ],
    )


def _thickened(mesh: MeshData, thickness: float) -> MeshData:
    """Die Fläche nach innen auftragen und die Ränder schließen.

    Drei Teile, und kein einziger boolescher Schnitt: die Fläche selbst bleibt
    die Außenseite, eine um die Wandstärke entlang der Punktnormalen versetzte
    Kopie mit umgedrehten Dreiecken wird die Innenseite, und für jede offene
    Kante schließt ein Viereck den Spalt dazwischen.

    Der naheliegende Weg — jedes Dreieck zu einem Prisma und alle vereinigen —
    war der erste Versuch und ist zweimal falsch: er kostet eine Boolesche
    Operation je Dreieck, und ohne sie bleiben die Innenflächen stehen. Das
    Ergebnis war ein Netz mit achtzig Flächen, das aussah wie ein Körper und
    keiner war.

    **Punktnormalen, nicht Flächennormalen.** Mit Flächennormalen bekommt jedes
    Dreieck seinen eigenen Versatz, und an jeder Kante klafft die Innenseite
    auseinander.
    """
    import numpy as np

    body = mesh.raw
    outer = np.asarray(body.vertices, dtype=float)
    inner = outer - np.asarray(body.vertex_normals, dtype=float) * thickness
    count = len(outer)

    faces = np.asarray(body.faces, dtype=np.int64)
    # Innen läuft die Umlaufrichtung andersherum, sonst zeigen dort alle
    # Normalen in den Körper hinein.
    flipped = faces[:, ::-1] + count

    edges = np.sort(np.asarray(body.edges, dtype=np.int64), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    border = unique[counts == 1]
    walls = [[first, second, second + count, first + count] for first, second in border.tolist()]
    quads = np.asarray(
        [[wall[0], wall[1], wall[2]] for wall in walls]
        + [[wall[0], wall[2], wall[3]] for wall in walls],
        dtype=np.int64,
    ).reshape(-1, 3)

    built = trimesh.Trimesh(
        vertices=np.vstack([outer, inner]),
        faces=np.vstack([faces, flipped, quads]) if len(quads) else np.vstack([faces, flipped]),
        process=True,
    )
    built.fix_normals()
    return mesh.replacing(built)
