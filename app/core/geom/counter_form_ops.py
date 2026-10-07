"""Gegenformeinsatz: Taschen für ausgewählte Teile in einen Einsatz (RM-184, Audit §8).

Die Werkzeugbox der Werkstatt (Audit Familie 10) hatte einen Einsatz 200 x 87
x 23 mit einer Tasche je Werkzeug, von Hand gezeichnet. Der Ablauf dahinter ist
immer derselbe: das Teil dorthin legen, wo es im Einsatz liegen soll, und eine
Tasche abziehen, in die es passt und aus der es gerade wieder herauskommt.
*Abziehen* allein tut das nicht — es schneidet die Form des Teils, mit seinen
Hinterschneidungen und ohne Luft.

Die Tasche ist hier der **Umriss des Teils in Entnahmerichtung** (der Schatten,
den es entlang der Achse wirft), um das halbe Spiel aus dem Materialprofil je
Seite geweitet (``clearance`` ist ein Durchmessermaß, `operationen.md`), vom
tiefsten Punkt des Teils, ebenfalls um das halbe Spiel tiefer, bis durch die
Oberseite des Einsatzes. Ein Teil, das so gesteckt ist, kommt geradeaus wieder
heraus; eine Hinterschneidung gibt es in einer solchen Tasche nicht. Wahlweise
öffnet eine Griffmulde die Tasche an einer Seite, damit man das Teil fassen
kann.

Beide Kerne: Am exakten Einsatz entstehen die Taschen als Prismen über den
Umrissen (``brep.lettering``) und werden exakt abgezogen; der Einsatz bleibt
exakt.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Final, cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import CANCEL, CORRECT_INPUT, ValidationError
from app.core.geom import transform
from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean, deepest, without_effect
from app.core.geom.mesh import MeshData, as_mesh_data, stable_normals
from app.core.knowledge.profiles import for_object
from app.core.registry import VARIABLE, op_params, param, play_param, register_op
from app.core.registry.params import ZERO_NONE
from app.core.types import BaseParams, BRepBody, Finding, OpContext, OpResult, SolverInfo
from app.core.units import EPS_GEOM, format_length
from app.i18n import _

#: Die drei rechtshändigen Rahmen der Entnahmerichtung: ``(u, v, w)`` als
#: Weltachsen, ``w`` zeigt dorthin, wohin das Teil herausgenommen wird.
_FRAMES: Final[dict[str, tuple[int, int, int]]] = {"x": (1, 2, 0), "y": (2, 0, 1), "z": (0, 1, 2)}


@op_params
class CounterFormParams(BaseParams):
    axis: str = param(
        title=_("Entnahmerichtung"),
        default="z",
        choices=("x", "y", "z"),
        doc=_(
            "Entlang welcher Achse die Teile aus dem Einsatz genommen werden — meist Z, von oben."
        ),
    )
    reverse: bool = param(
        title=_("Entgegengesetzt"),
        default=False,
        doc=_("Nimmt die Teile auf der anderen Seite heraus, etwa nach unten."),
    )
    grip: float = param(
        title=_("Griffmulde"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=60.0,
        doc=_(
            "Durchmesser einer runden Mulde an der Seite jeder Tasche, damit man das Teil "
            "greifen kann. Null lässt sie weg."
        ),
        zero_text=ZERO_NONE,
    )
    clearance: float = play_param(maximum=3.0)


def _frame(axis: str, reverse: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Die Einheitsvektoren ``u``, ``v``, ``w`` — ``w`` zeigt aus der Tasche heraus."""
    first, second, third = _FRAMES[axis]
    unit = np.eye(3)
    u, v, w = unit[first], unit[second], unit[third]
    if reverse:
        # Rechtshändig bleiben: ``w`` gedreht heißt auch ``v`` gedreht.
        v, w = -v, -w
    return u, v, w


def _silhouette(mesh: MeshData, u: np.ndarray, v: np.ndarray, w: np.ndarray) -> Any:
    """Der Schatten des Teils entlang ``w`` — die Vereinigung seiner zugewandten Dreiecke.

    Ein geschlossener Körper wirft genau den Schatten der Dreiecke, die in
    Entnahmerichtung schauen; die abgewandten liegen in derselben Fläche.
    """
    from shapely import Polygon, union_all

    raw = mesh.raw
    corners = np.asarray(raw.vertices, dtype=float)[np.asarray(raw.faces, dtype=np.int64)]
    normals, _areas = stable_normals(raw)
    facing = (normals[:, 0] * w[0] + normals[:, 1] * w[1] + normals[:, 2] * w[2]) > EPS_GEOM
    flat_u = corners[facing][:, :, 0] * u[0] + corners[facing][:, :, 1] * u[1]
    flat_u = flat_u + corners[facing][:, :, 2] * u[2]
    flat_v = corners[facing][:, :, 0] * v[0] + corners[facing][:, :, 1] * v[1]
    flat_v = flat_v + corners[facing][:, :, 2] * v[2]
    triangles = [
        Polygon(np.column_stack((flat_u[index], flat_v[index]))) for index in range(len(flat_u))
    ]
    shadow = union_all([triangle for triangle in triangles if triangle.area > EPS_GEOM**2])
    return shadow.simplify(EPS_GEOM)


def _along(mesh: Any, w: np.ndarray) -> tuple[float, float]:
    """Wie weit ein Körper entlang ``w`` reicht — kleinster und größter Wert."""
    bounds = mesh.bounds
    low = np.asarray(bounds.minimum, dtype=float)
    high = np.asarray(bounds.maximum, dtype=float)
    index = int(np.argmax(np.abs(w)))
    if w[index] > 0.0:
        return float(low[index]), float(high[index])
    return -float(high[index]), -float(low[index])


def _pieces(shape: Any) -> list[Any]:
    return [piece for piece in getattr(shape, "geoms", [shape]) if piece.area > EPS_GEOM]


def _notch(outline: Any, diameter: float) -> Any:
    """Eine runde Griffmulde, mittig auf der Kante der Tasche in ``+v``.

    Die Mitte liegt auf dem Umriss, an der Stelle seiner größten Ausdehnung in
    ``v`` über der Mitte in ``u`` — dort, wohin ein Finger von der Seite greift.
    """
    from shapely import LineString, Point

    left, low, right, high = outline.bounds
    middle = (left + right) / 2.0
    crossing = outline.intersection(LineString([(middle, low - 1.0), (middle, high + 1.0)]))
    top = float(crossing.bounds[3]) if not crossing.is_empty else float(high)
    return Point(middle, top).buffer(diameter / 2.0, quad_segs=32)


def _matrix(u: np.ndarray, v: np.ndarray, w: np.ndarray, start: float) -> np.ndarray:
    """Vom Rahmen der Tasche (Prisma ab ``z = 0``) in die Welt, beginnend bei ``start``."""
    matrix = np.eye(4)
    matrix[:3, 0], matrix[:3, 1], matrix[:3, 2] = u, v, w
    matrix[:3, 3] = w * start
    return matrix


@register_op(
    name="cut_counter_form",
    title=_("Gegenform einlassen"),
    category="boolean",
    params=CounterFormParams,
    consumes=VARIABLE,
    minimum_inputs=2,
    produces=VARIABLE,
    # Jedes Teil steht danach als Tasche im Einsatz, auch wenn es selbst
    # entfernt wird (``history.discarded``).
    shapes_with_other_inputs=True,
    doc=_(
        "Lässt in den zuerst gewählten Einsatz eine Tasche für jedes weitere Teil ein. "
        "Sie folgt dem Umriss des Teils mit Spiel, vom tiefsten Punkt bis durch die Oberseite, "
        "so dass es gerade herauskommt. Die Teile bleiben, wo sie sind."
    ),
    caveat=_(
        "Für eine Tasche in der Form des Teils, mit Hinterschneidungen und ohne Luft, "
        "nehmen Sie *Abziehen*."
    ),
)
def cut_counter_form(ctx: OpContext) -> OpResult:
    """Die Taschen eines Werkzeugeinsatzes aus den Teilen selbst (RM-184)."""
    params = cast(CounterFormParams, ctx.params)
    insert, tools = ctx.inputs[0], ctx.inputs[1:]
    clearance = params.clearance
    if not clearance:
        if ctx.profile is None:
            raise ValidationError(
                field="clearance",
                detail=_("Ohne Profil muss das Spiel angegeben werden."),
                constraint="no_profile",
                suggestions=(CORRECT_INPUT,),
            )
        clearance = for_object(ctx.profile, insert).material.clearance
    u, v, w = _frame(params.axis, params.reverse)
    exact = isinstance(insert.mesh, BRepBody)
    insert_low, insert_high = _along(insert.mesh, w)
    top = insert_high + BOOLEAN_OVERLAP
    findings: list[Finding] = []
    pockets: list[tuple[Any, float]] = []
    for tool in tools:
        ctx.cancelled.raise_if_cancelled()
        shape = as_mesh_data(tool.mesh)
        low, _high = _along(tool.mesh, w)
        outline = _silhouette(shape, u, v, w).buffer(clearance / 2.0, join_style=2)
        if params.grip > EPS_GEOM:
            outline = outline.union(_notch(outline, params.grip))
        start = low - clearance / 2.0
        if start >= insert_high - EPS_GEOM or not _overlaps(insert.mesh, outline, u, v):
            raise ValidationError(
                field="axis",
                detail=_(
                    "„{object}“ liegt nicht im Einsatz, es gibt keine Tasche zu schneiden. "
                    "Legen Sie das Teil dorthin, wo es im Einsatz liegen soll.",
                    object=tool.name,
                ),
                constraint="outside",
                values={"object": tool.name},
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        if start <= insert_low + EPS_GEOM:
            findings.append(
                Finding(
                    code="counter_form.through_floor",
                    severity="warning",
                    message=_(
                        "Die Tasche für „{object}“ reicht durch den Boden des Einsatzes.",
                        object=tool.name,
                    ),
                    object_id=insert.id,
                    values={"object": tool.name, "floor_mm": round(insert_low, 3)},
                    suggestions=(CORRECT_INPUT,),
                )
            )
        pockets.append((outline, start))

    solver: SolverInfo | None = None
    if exact:
        from app.core.brep import edit

        body: Any = cast(Any, insert.mesh)
        tools_exact = [
            _exact_pocket(outline, start, top, u, v, w, ctx) for outline, start in pockets
        ]
        ctx.cancelled.raise_if_cancelled()
        result: Any = edit.unified(edit.boolean("difference", [body, *tools_exact]))
    else:
        mesh = as_mesh_data(insert.mesh)
        tool_meshes = [_mesh_pocket(outline, start, top, u, v, w) for outline, start in pockets]
        outcome = boolean(
            "difference",
            [mesh, *tool_meshes],
            quality=ctx.quality,
            seed=ctx.seed,
            cancelled=ctx.cancelled,
        )
        result = outcome.mesh
        findings.extend(outcome.findings)
        solver = deepest([outcome.solver])
    nothing = without_effect(insert.mesh, result, "difference", ctx.profile)
    if nothing is not None:
        findings.append(nothing)
    findings.append(
        Finding(
            code="counter_form.cut",
            severity="info",
            message=_(
                "Eingelassene Taschen: {count}, je mit {play} Spiel um das Teil.",
                count=len(pockets),
                play=format_length(clearance),
            ),
            object_id=insert.id,
            values={"count": len(pockets), "clearance_mm": round(clearance, 3)},
        )
    )
    return OpResult(
        outputs=[dataclasses.replace(insert, mesh=result, features={}), *tools],
        solver=solver,
        findings=findings,
    )


def _overlaps(body: Any, outline: Any, u: np.ndarray, v: np.ndarray) -> bool:
    """Ob der Umriss den Einsatz quer zur Entnahmerichtung überhaupt trifft."""
    from shapely import box

    bounds = body.bounds
    low = np.asarray(bounds.minimum, dtype=float)
    high = np.asarray(bounds.maximum, dtype=float)
    first = int(np.argmax(np.abs(u)))
    second = int(np.argmax(np.abs(v)))
    span_u = sorted((float(low[first] * u[first]), float(high[first] * u[first])))
    span_v = sorted((float(low[second] * v[second]), float(high[second] * v[second])))
    return bool(outline.intersects(box(span_u[0], span_v[0], span_u[1], span_v[1])))


def _mesh_pocket(
    outline: Any, start: float, top: float, u: np.ndarray, v: np.ndarray, w: np.ndarray
) -> MeshData:
    """Das Taschenwerkzeug als Netz: Prismen über dem Umriss von ``start`` bis ``top``."""
    from app.core.geom.mesh import concatenated

    height = top - start
    prisms = [trimesh.creation.extrude_polygon(piece, height=height) for piece in _pieces(outline)]
    joined = concatenated(prisms) if len(prisms) > 1 else prisms[0]
    transform.moved(joined, _matrix(u, v, w, start))
    return MeshData.of(joined)


def _exact_pocket(
    outline: Any,
    start: float,
    top: float,
    u: np.ndarray,
    v: np.ndarray,
    w: np.ndarray,
    ctx: OpContext,
) -> Any:
    """Dasselbe Werkzeug exakt — Prismen mit ebenen Wänden (``brep.lettering``)."""
    from itertools import pairwise

    from app.core.brep import edit, lettering
    from app.core.geom.ops import as_transform

    found = []
    for piece in _pieces(outline):
        for ring in (piece.exterior, *piece.interiors):
            points = [(float(x), float(y)) for x, y in ring.coords]
            found.append(tuple(pairwise(points)))
    prisms = lettering.letters(found, top - start, cancelled=ctx.cancelled)
    return edit.transformed(prisms, as_transform(_matrix(u, v, w, start)), cancelled=ctx.cancelled)
