"""Verschluss ändern — Spiel und Drehweg eines Bajonetts oder einer Rastung (RM-184).

Der Dateiaudit (§7) verlangt für Bajonett und Rastverschluss „Spiel und
Drehweg ändern“. Die Gruppe kommt aus :mod:`app.core.perceive.groups`; diese
Operation ändert **alle Stellungen zugleich**:

* **Spiel** — jede Flanke einer Stellung, eine ebene Fläche quer zur
  Umfangsrichtung, wandert um die halbe Änderung. Mehr Spiel macht Nocken
  schmaler und Mulden, Schlitze und Wege breiter, weniger Spiel umgekehrt.
* **Drehweg** — der Anschlag jedes Wegs (``groups.closure_stops``) schwenkt um
  die Achse weiter: Der Verschluss dreht weiter, bis er sitzt. Das geht nur am
  Teil mit den Wegen; Nocken tragen keinen Anschlag.

**Wie.** Je Flanke ein Werkzeug aus ihrem eigenen Umriss: für das Spiel ein
Prisma längs ihrer Normalen, für den Drehweg der Umriss um die Achse
geschwenkt. Wird der Weg weiter, wird es abgezogen, sonst angesetzt. Wo
Material an eine Kante grenzt — Boden, Dach, der Rundkörper unter einer
Nocke —, gleitet ihre Ecke an dessen Fläche entlang (:func:`_slides`); wo Luft
dahinter liegt, reicht ein abziehendes Werkzeug um :data:`REACH_INTO_AIR`
hinaus, sonst bliebe an einer Rundung eine Haut stehen. Zwei Wege davor gingen
nicht: *Fläche versetzen* traf am Kartuschendeckel aus dem Audit drei von
sechs Flanken schief, und wandernde Ecken klappten am Filterkäfig schon bei
einem halben Grad Drehweg Dreiecke um; die Werkzeuge aus dem Umriss treffen
dort das erwartete Volumen auf Hundertstel Prozent.

**Was nicht geht, sagt es** (Regel 17): runde Mulden ohne ebene Flanken, ein
Drehweg an einem Teil ohne Anschlag, eine Flanke mit Loch, eine Nocke, die
schmaler als null würde, ein Weg, der zuginge, und ein Werkzeug, das in eine
Nachbarstellung oder durch eine Wand liefe — dann trifft die Wirkung die
Rechnung nicht mehr (:data:`VOLUME_SHARE`).
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable
from typing import TYPE_CHECKING, Final, cast

import numpy as np

from app.core.errors import CANCEL, CHANGE_SELECTION, CORRECT_INPUT, GeometryError
from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean, without_effect
from app.core.geom.chamber_ops import flat_cap, rims_of
from app.core.geom.mesh import (
    MeshData,
    as_mesh_data,
    face_components,
    signed_volume,
    stable_normals,
)
from app.core.geom.prepare import inside_material
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Feature, Finding, OpContext, OpResult, SolverInfo
from app.core.units import EPS_GEOM, exact_cos_degrees, exact_sin_degrees, plane_axes
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    # Träge, wie jede Kante von ``geom`` nach ``perceive``
    # (``tests/test_core_package_direction.py``).
    from collections.abc import Mapping, Sequence

    from app.core.perceive.groups import ClosureStop, FlankPair
    from app.core.types import FeatureId

#: Wie weit ein abziehendes Werkzeug über einen Flankenrand mit Luft dahinter
#: hinausreicht. Bündig bliebe dort, wo die Flanke an eine Rundung stößt, eine
#: Haut stehen: Der Mantel weicht zwischen seinen Ecken um seine Sehne vom
#: geraden Rand ab. Ob dahinter Luft ist, fragen zwei Proben — eine am Rand,
#: eine am Ende der Zugabe.
REACH_INTO_AIR: Final = 1.0

#: Ein Schritt des geschwenkten Werkzeugs in Grad: Die Sehne bleibt bis
#: 1000 mm Radius unter ``units.MAX_FACET_SAG``, der Boden des Wegs bleibt rund.
TURN_STEP_DEGREES: Final = 1.0

#: Wie weit die Wirkung von der Rechnung abweichen darf. Ein Werkzeug aus dem
#: Umriss trifft das Volumen auf Hundertstel Prozent; was mehr verfehlt, lief in
#: Luft oder Material, das nicht zu seiner Stellung gehört.
VOLUME_SHARE: Final = 0.02

#: Rauschen einer gemessenen Achsrichtung, das auf null fällt: Eine Weltachse
#: bleibt so genau, und Boden und Dach eines Wegs bleiben in ihrer Ebene.
AXIS_NOISE: Final = 1e-12


@op_params
class ResizeClosureParams(BaseParams):
    at_feature: str = param(
        title=_("Verschluss", context="Merkmalsgruppe"),
        default="",
        kind="feature",
        doc=_("Achse, Nocke oder Weg des Verschlusses. Geändert werden immer alle Stellungen."),
    )
    play: float = param(
        title=_("Mehr Spiel"),
        default=0.0,
        unit="mm",
        minimum=-5.0,
        maximum=5.0,
        doc=_(
            "Um so viel wird jede Stellung lockerer: Nocken schmaler, Mulden und Wege "
            "breiter, je Seite um die Hälfte. Ein negativer Wert macht den Verschluss strammer."
        ),
    )
    turn: float = param(
        title=_("Längerer Drehweg"),
        default=0.0,
        unit="°",
        minimum=-45.0,
        maximum=45.0,
        doc=_(
            "Um so viel Grad schwenkt der Anschlag jedes Wegs weiter: Der Verschluss dreht "
            "weiter, bis er sitzt. Ein negativer Wert verkürzt den Weg. Nur am Teil mit den "
            "Wegen."
        ),
    )


@register_op(
    name="resize_closure",
    cache_version="1",
    title=_("Verschluss ändern"),
    category="shaping",
    params=ResizeClosureParams,
    consumes=1,
    produces=1,
    applies_to=("face", "hole", "pin"),
    # Die Werkzeuge entstehen am Netz: Ein exakter Körper kommt als
    # Dreiecksmodell zurück, und das Fenster sagt es vor der Rechnung.
    result_kind="mesh",
    doc=_(
        "Ändert Spiel und Drehweg eines erkannten Bajonetts oder einer Rastung an allen "
        "Stellungen zugleich: Nocken schmaler, Mulden und Wege breiter, der Anschlag weiter — "
        "oder umgekehrt."
    ),
    caveat=_(
        "Nur an einem erkannten Verschluss mit ebenen Seiten, den Drehweg nur am Teil mit den "
        "Wegen. Runde Rastmulden ändern Sie über ihren Radius mit „Merkmal ändern“."
    ),
)
def resize_closure(ctx: OpContext) -> OpResult:
    from app.core.perceive.groups import (
        NOT_A_CLOSURE,
        closure_axis,
        closure_flanks,
        closure_pairs,
        closure_stops,
        functional_groups,
        group_of,
        reason_against_closure,
        reason_against_play,
        reason_against_turn,
    )

    params = cast(ResizeClosureParams, ctx.params)
    source = ctx.inputs[0]
    body = as_mesh_data(source.mesh)
    features = source.features
    group = group_of(params.at_feature, functional_groups(features, body, cancelled=ctx.cancelled))
    axis = closure_axis(group, features) if group is not None else None
    if group is None or axis is None:
        raise GeometryError(detail=NOT_A_CLOSURE, suggestions=(CHANGE_SELECTION, CANCEL))
    play, turn = float(params.play), float(params.turn)
    if abs(play) <= EPS_GEOM and abs(turn) <= EPS_GEOM:
        raise GeometryError(
            detail=_(
                "Spiel und Drehweg stehen auf null — geändert wird nichts. Tragen Sie ein, um "
                "wie viel der Verschluss lockerer oder strammer werden oder wie viel Grad weiter "
                "er drehen soll."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    refusal = reason_against_closure(group, features)
    if refusal is None and abs(play) > EPS_GEOM:
        refusal = reason_against_play(group, features, body)
    if refusal is None and abs(turn) > EPS_GEOM:
        refusal = reason_against_turn(group, features, body)
    if refusal is not None:
        raise GeometryError(detail=refusal, suggestions=(CHANGE_SELECTION, CANCEL))
    point = np.asarray(axis[0], dtype=np.float64)
    direction = _snapped(axis[1])
    stops = closure_stops(group, features, body) if abs(turn) > EPS_GEOM else ()
    # Nur die Umrisse, die bewegt werden: Eine Flanke mit Loch hält das Spiel
    # an, nicht den Drehweg eines Anschlags daneben.
    moving = closure_flanks(group, features) if abs(play) > EPS_GEOM else ()
    outlines = {
        name: _outline(body, features[name])
        for name in dict.fromkeys([*moving, *(stop.flank for stop in stops)])
    }
    mesh, solver = body, SolverInfo(strategy="direct")
    findings: list[Finding] = []
    moved: dict[FeatureId, np.ndarray] = {}
    if abs(play) > EPS_GEOM:
        _check_widths(closure_pairs(group, features, body), play)
        mesh, solver, found, moved = _played(ctx, mesh, features, outlines, play)
        findings.extend(found)
    if abs(turn) > EPS_GEOM:
        mesh, solver, found = _turned(
            ctx, mesh, features, outlines, moved, stops, turn, point, direction
        )
        findings.extend(found)
    shrank = signed_volume(mesh.raw) < signed_volume(body.raw)
    effect = without_effect(body, mesh, "difference" if shrank else "union", ctx.profile)
    if effect is not None:
        findings.append(effect)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh, kind="mesh", features={})],
        solver=solver,
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in findings],
    )


def _played(
    ctx: OpContext,
    mesh: MeshData,
    features: Mapping[FeatureId, Feature],
    outlines: Mapping[FeatureId, _Outline],
    play: float,
) -> tuple[MeshData, SolverInfo, list[Finding], dict[FeatureId, np.ndarray]]:
    """Jede Flanke um die halbe Änderung längs ihrer Normalen — ins Material oder hinaus.

    Zurück kommt auch, wo jede Flanke danach steht: Der Drehweg schwenkt den
    Anschlag von dort aus weiter.

    **Ein Werkzeugende in einer Fläche bekommt** :data:`BOOLEAN_OVERLAP`
    (``operationen.md``): Das abziehende beginnt so weit in der Luft vor der
    Flanke, das ansetzende so weit im Material hinter ihr. Bündig blieb an
    einer STL eine Haut von einem Zehntelmikrometer stehen — als eigenes Stück.
    Die Überdeckung ist ein eigener Abschnitt: Ab der Flanke selbst läuft das
    Werkzeug durch ihre eigenen Ecken, wie das genaue.
    """
    depth = play / 2.0
    exact: list[MeshData] = []
    tools: list[MeshData] = []
    moved: dict[FeatureId, np.ndarray] = {}
    for name, outline in outlines.items():
        normal = _normal(features[name])
        air = _air(mesh, outline.corners, normal, _moving(-normal * depth / 2.0))
        moved[name] = outline.corners + _slides(normal, outline.neighbours, air, depth)
        exact.append(_swept([outline.corners, moved[name]], normal))
        if play > 0.0:
            grown = _grown(outline.corners, normal, air)
            start = grown + _slides(normal, outline.neighbours, air, -BOOLEAN_OVERLAP)
            end = grown + _slides(normal, outline.neighbours, air, depth)
            tools.append(_swept([start, grown, end], normal))
        else:
            start = outline.corners + _slides(normal, outline.neighbours, air, BOOLEAN_OVERLAP)
            tools.append(_swept([start, outline.corners, moved[name]], normal))
    result, solver, findings = _applied(
        ctx,
        mesh,
        tools,
        exact,
        "difference" if play > 0.0 else "union",
        _(
            "Mit diesem Spiel liefe eine Seite in Material oder Luft, die nicht zu ihrer "
            "Stellung gehört — etwa durch eine dünne Wand. Wählen Sie einen Wert näher an null."
        ),
        {"play_mm": round(play, 3)},
    )
    return result, solver, findings, moved


def _turned(
    ctx: OpContext,
    mesh: MeshData,
    features: Mapping[FeatureId, Feature],
    outlines: Mapping[FeatureId, _Outline],
    moved: Mapping[FeatureId, np.ndarray],
    stops: Sequence[ClosureStop],
    turn: float,
    point: np.ndarray,
    direction: np.ndarray,
) -> tuple[MeshData, SolverInfo, list[Finding]]:
    """Jeder Anschlag um ``turn`` Grad weiter, dort, wo ihn das Spiel hingesetzt hat.

    Boden und Dach eines Wegs stehen quer zur Achse und die Mäntel um sie
    herum: Gedreht bleibt jede Ecke auf ihnen, ohne zu gleiten. Das Werkzeug
    beginnt wie beim Spiel um :data:`BOOLEAN_OVERLAP` vor der Flanke, hier um
    die Achse zurückgedreht — so bleiben auch die Ecken der Überdeckung auf
    ihren Mänteln.
    """
    steps = max(1, math.ceil(abs(turn) / TURN_STEP_DEGREES))
    exact: list[MeshData] = []
    tools: list[MeshData] = []
    for stop in stops:
        normal = _normal(features[stop.flank])
        outline = outlines[stop.flank]
        corners = moved.get(stop.flank, outline.corners)
        degrees = stop.sense * turn
        copies = [
            _rotated(corners, point, direction, degrees * k / steps) for k in range(steps + 1)
        ]
        exact.append(_swept(copies, normal))
        air = _air(mesh, corners, normal, _turning(point, direction, degrees / 2.0))
        back = -math.copysign(_overlap_degrees(corners, point, direction), degrees)
        if turn > 0.0:
            grown = _grown(corners, normal, air)
            tools.append(
                _swept(
                    [
                        _rotated(grown, point, direction, back),
                        *(
                            _rotated(grown, point, direction, degrees * k / steps)
                            for k in range(steps + 1)
                        ),
                    ],
                    normal,
                )
            )
        else:
            tools.append(_swept([_rotated(corners, point, direction, back), *copies], normal))
    return _applied(
        ctx,
        mesh,
        tools,
        exact,
        "difference" if turn > 0.0 else "union",
        _(
            "Mit diesem Drehweg liefe ein Anschlag in eine Nachbarstellung oder über den "
            "Einführweg hinaus. Wählen Sie einen Wert näher an null."
        ),
        {"angle_deg": round(turn, 3)},
    )


def _applied(
    ctx: OpContext,
    mesh: MeshData,
    tools: Sequence[MeshData],
    exact: Sequence[MeshData],
    kind: str,
    missed: TranslatableText,
    values: dict[str, float],
) -> tuple[MeshData, SolverInfo, list[Finding]]:
    """Die Werkzeuge abziehen oder ansetzen — und die Wirkung gegen die Rechnung halten.

    Die Rechnung ist das Volumen der genauen Werkzeuge: Was eine Flanke
    überstreicht, ist ihr Umriss mal ihr Weg. Zerfällt der Körper, sagt es das.
    """
    ctx.cancelled.raise_if_cancelled()
    outcome = boolean(
        "difference" if kind == "difference" else "union",
        [mesh, *tools],
        quality=ctx.quality,
        cancelled=ctx.cancelled,
    )
    result = outcome.mesh
    before = signed_volume(mesh.raw)
    expected = sum(abs(signed_volume(tool.raw)) for tool in exact)
    changed = abs(signed_volume(result.raw) - before)
    if abs(changed - expected) > VOLUME_SHARE * expected + 1e-6 * abs(before):
        raise GeometryError(
            detail=missed,
            values={**values, "expected_mm3": round(expected, 3), "volume_mm3": round(changed, 3)},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if len(face_components(result.raw)) != len(face_components(mesh.raw)):
        raise GeometryError(
            detail=_(
                "Mit diesem Wert zerfiele der Körper in Stücke. Wählen Sie einen Wert näher an "
                "null."
            ),
            values=dict(values),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return result, outcome.solver, list(outcome.findings)


def _check_widths(pairs: Sequence[FlankPair], play: float) -> None:
    """Keine Nocke wird schmaler als null, kein Weg und keine Mulde geht zu.

    Je Paar gegenüberliegender Flanken (``groups.closure_pairs``): Liegt
    Material dazwischen, schrumpft es um das Spiel, liegt Luft dazwischen,
    wächst sie um das Spiel.
    """
    for pair in pairs:
        if pair.gap < 0.0 and -pair.gap - play <= EPS_GEOM:
            raise GeometryError(
                detail=_(
                    "Mit so viel Spiel würde eine Nocke schmaler als null. Wählen Sie weniger "
                    "Spiel."
                ),
                values={"play_mm": round(play, 3), "width_mm": round(-pair.gap, 3)},
                suggestions=(CORRECT_INPUT, CANCEL),
            )
        if pair.gap > 0.0 and pair.gap + play <= EPS_GEOM:
            raise GeometryError(
                detail=_(
                    "Mit so wenig Spiel ginge ein Weg oder eine Mulde ganz zu. Wählen Sie einen "
                    "Wert näher an null."
                ),
                values={"play_mm": round(play, 3), "width_mm": round(pair.gap, 3)},
                suggestions=(CORRECT_INPUT, CANCEL),
            )


# --- Umriss und Werkzeug ----------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class _Outline:
    """Der Rand einer Flanke: Ecken gegen den Uhrzeigersinn um ihre Normale."""

    corners: np.ndarray
    neighbours: tuple[np.ndarray | None, ...]
    """Je Kante von Ecke ``i`` zu ``i + 1`` die Normale des Dreiecks jenseits von
    ihr — die Fläche, an der eine Ecke entlanggleitet, wo Material anliegt."""


def _outline(body: MeshData, feature: Feature) -> _Outline:
    """Der Umriss einer ebenen Fläche, ohne Zwischenpunkte auf geraden Rändern.

    Eine Fläche mit Loch oder aus mehreren Stücken hat mehr als einen Rand und
    keinen Umriss, der sich als Ganzes verschieben ließe.
    """
    all_faces = np.asarray(body.raw.faces, dtype=np.int64)
    own = np.asarray(feature.face_indices, dtype=np.int64)
    loops = rims_of(all_faces[own])
    if len(loops) != 1:
        raise _no_outline()
    loop = loops[0]
    points = np.asarray(body.raw.vertices, dtype=np.float64)[loop]
    count = len(points)
    kept: list[int] = []
    for index in range(count):
        before, here, after = points[index - 1], points[index], points[(index + 1) % count]
        one, two = here - before, after - here
        if _length(np.cross(one, two)) > 1e-9 * _length(one) * _length(two):
            kept.append(index)
    if len(kept) < 3:
        raise _no_outline()
    normals, _areas = stable_normals(body.raw)
    mine = np.zeros(len(all_faces), dtype=bool)
    mine[own] = True
    neighbours: list[np.ndarray | None] = []
    for index in kept:
        start, end = loop[index], loop[(index + 1) % count]
        beside = np.flatnonzero(
            (all_faces == start).any(axis=1) & (all_faces == end).any(axis=1) & ~mine
        )
        neighbours.append(np.asarray(normals[beside[0]], dtype=np.float64) if len(beside) else None)
    return _Outline(points[kept], tuple(neighbours))


def _no_outline() -> GeometryError:
    return GeometryError(
        detail=_(
            "Eine Seite dieses Verschlusses hat ein Loch oder liegt in mehreren Stücken — ihr "
            "Umriss lässt sich nicht als Ganzes verschieben. Ändern Sie sie über „Fläche "
            "versetzen“."
        ),
        suggestions=(CHANGE_SELECTION, CANCEL),
    )


def _air(
    body: MeshData,
    corners: np.ndarray,
    normal: np.ndarray,
    motion: Callable[[np.ndarray], np.ndarray],
) -> tuple[bool, ...]:
    """Je Kante des Umrisses: liegt jenseits von ihr Luft?

    Gefragt wird mitten im Weg des Werkzeugs (``motion``): Liegen eine Probe
    knapp hinter der Kante und eine im Abstand :data:`REACH_INTO_AIR` außerhalb
    des Materials, ist dort Luft. Sonst endet dort Material — ein Boden, ein
    Dach, der Körper unter einer Nocke.
    """
    count = len(corners)
    found: list[bool] = []
    for index in range(count):
        start, end = corners[index], corners[(index + 1) % count]
        out = _outward(start, end, normal)
        middle = (start + end) / 2.0
        probes = motion(
            np.stack([middle + out * (REACH_INTO_AIR / 20.0), middle + out * REACH_INTO_AIR])
        )
        inside, _normals = inside_material(body, probes)
        found.append(not bool(np.any(inside)))
    return tuple(found)


def _outward(start: np.ndarray, end: np.ndarray, normal: np.ndarray) -> np.ndarray:
    """Die Richtung aus dem Umriss hinaus, in seiner Ebene, quer zur Kante."""
    out = np.cross(end - start, normal)
    return np.asarray(out / _length(out))


def _grown(corners: np.ndarray, normal: np.ndarray, air: Sequence[bool]) -> np.ndarray:
    """Der Umriss, an Kanten mit Luft dahinter um :data:`REACH_INTO_AIR` größer.

    Die Ecke wandert so, dass beide anliegenden Kanten ihren Abstand halten:
    v · aus₁ = r₁ und v · aus₂ = r₂, v in der Ebene der Flanke. Kanten an
    Material bleiben, wo sie sind.
    """
    count = len(corners)
    outward = [
        _outward(corners[index], corners[(index + 1) % count], normal) for index in range(count)
    ]
    reach = [REACH_INTO_AIR if open_ else 0.0 for open_ in air]
    grown = []
    for index in range(count):
        out_one, out_two = outward[index - 1], outward[index]
        reach_one, reach_two = reach[index - 1], reach[index]
        cosine = _dot(out_one, out_two)
        determinant = 1.0 - cosine * cosine
        if determinant <= EPS_GEOM:
            grown.append(corners[index] + out_two * max(reach_one, reach_two))
            continue
        alpha = (reach_one - cosine * reach_two) / determinant
        beta = (reach_two - cosine * reach_one) / determinant
        grown.append(corners[index] + out_one * alpha + out_two * beta)
    return np.asarray(grown, dtype=np.float64)


def _slides(
    normal: np.ndarray,
    neighbours: Sequence[np.ndarray | None],
    air: Sequence[bool],
    depth: float,
) -> np.ndarray:
    """Wohin jede Ecke wandert, wenn die Flanke um ``depth`` ins Material rückt.

    Eine Ecke zwischen zwei Kanten mit Luft geht geradeaus, gegen die Normale.
    Liegt an einer Kante Material, gleitet die Ecke an dessen Fläche entlang:
    Sie bleibt auf ihr (v · m = 0) und rückt die Flanke trotzdem um die Tiefe
    (v · n = -Tiefe). So folgt eine Nocke auf einem Rundkörper seiner Wand,
    statt eine Kerbe hineinzuschneiden — am Kartuschendeckel aus dem Audit
    stehen die Nocken auf der Rundung der Platte. Zwei Materialkanten an einer
    Ecke legen sie auf die Schnittlinie beider Flächen.
    """
    count = len(neighbours)
    moves = []
    for index in range(count):
        held = [
            np.asarray(neighbours[edge], dtype=np.float64)
            for edge in (index - 1, index)
            if not air[edge] and neighbours[edge] is not None
        ]
        move = -normal * depth
        if len(held) == 2:
            crossed = np.cross(held[0], held[1])
            determinant = _dot(normal, crossed)
            if abs(determinant) > 1e-9:
                move = -crossed * (depth / determinant)
                moves.append(move)
                continue
            held = held[:1]
        if len(held) == 1:
            cosine = _dot(normal, held[0])
            rest = 1.0 - cosine * cosine
            if rest > 1e-9:
                move = normal * (-depth / rest) + held[0] * (depth * cosine / rest)
        moves.append(move)
    return np.asarray(moves, dtype=np.float64)


def _swept(copies: Sequence[np.ndarray], normal: np.ndarray) -> MeshData:
    """Ein geschlossener Körper aus Kopien desselben ebenen Umrisses: Mantel und zwei Deckel.

    Die Kopien entstehen durch Verschieben oder Drehen, Ecke für Ecke
    dieselbe Folge — deshalb gilt die Dreiecksteilung des ersten Deckels auch
    für den letzten.
    """
    import trimesh

    count = len(copies[0])
    points = np.vstack(copies)
    sides: list[tuple[int, int, int]] = []
    for step in range(len(copies) - 1):
        low, high = step * count, (step + 1) * count
        for index in range(count):
            after = (index + 1) % count
            sides.append((low + index, low + after, high + after))
            sides.append((low + index, high + after, high + index))
    axes = plane_axes([float(value) for value in normal])
    if axes is None:
        raise _no_outline()
    first, second = (np.asarray(axis, dtype=np.float64) for axis in axes)
    cap = flat_cap([list(range(count))], copies[0], copies[0][0], first, second)
    if cap is None:
        raise _no_outline()
    last = (len(copies) - 1) * count
    triangles = np.vstack([np.asarray(sides, dtype=np.int64), cap, (cap + last)[:, ::-1]])
    tool = trimesh.Trimesh(vertices=points, faces=triangles, process=False)
    tool.fix_normals()
    if not tool.is_watertight:
        raise _no_outline()
    if signed_volume(tool) < 0.0:
        tool.invert()
    return MeshData(raw=tool)


def _moving(shift: np.ndarray) -> Callable[[np.ndarray], np.ndarray]:
    """Die Bewegung, die Punkte um ``shift`` verschiebt — für die Proben einer Kante."""

    def moved(points: np.ndarray) -> np.ndarray:
        return np.asarray(points + shift)

    return moved


def _turning(
    point: np.ndarray, direction: np.ndarray, degrees: float
) -> Callable[[np.ndarray], np.ndarray]:
    """Die Bewegung, die Punkte um die Achse dreht — für die Proben einer Kante."""

    def turned(points: np.ndarray) -> np.ndarray:
        return _rotated(points, point, direction, degrees)

    return turned


def _rotated(
    points: np.ndarray, point: np.ndarray, direction: np.ndarray, degrees: float
) -> np.ndarray:
    """Punkte um die Achse gedreht, rechtsherum um ``direction`` — plattformgleich.

    Nur der Anteil quer zur Achse ändert sich, und er wird zur alten Lage
    addiert: Eine Ecke auf dem Boden eines Wegs bleibt in dessen Ebene.
    """
    cosine, sine = exact_cos_degrees(degrees), exact_sin_degrees(degrees)
    relative = points - point
    along = (
        relative[:, 0] * direction[0]
        + relative[:, 1] * direction[1]
        + relative[:, 2] * direction[2]
    )
    across = relative - along[:, None] * direction
    turned = across * cosine + np.cross(direction, across) * sine
    return np.asarray(points + (turned - across))


def _overlap_degrees(corners: np.ndarray, point: np.ndarray, direction: np.ndarray) -> float:
    """Um wie viel Grad eine Flanke zurückgedreht :data:`BOOLEAN_OVERLAP` überdeckt.

    Gemessen an ihrer achsnächsten Ecke: Dort ist der Bogen zum Winkel am
    kürzesten, weiter außen überdeckt sie mehr.
    """
    relative = corners - point
    along = (
        relative[:, 0] * direction[0]
        + relative[:, 1] * direction[1]
        + relative[:, 2] * direction[2]
    )
    across = relative - along[:, None] * direction
    nearest = min(_length(row) for row in across)
    return BOOLEAN_OVERLAP / max(nearest, EPS_GEOM) * (180.0 / math.pi)


def _snapped(direction: Sequence[float]) -> np.ndarray:
    """Die Achsrichtung ohne Rauschen unter :data:`AXIS_NOISE`, wieder auf Länge eins."""
    values = np.asarray(
        [0.0 if abs(value) <= AXIS_NOISE else float(value) for value in direction],
        dtype=np.float64,
    )
    return values / _length(values)


def _normal(feature: Feature) -> np.ndarray:
    normal = np.asarray(feature.params["normal"], dtype=np.float64)
    return normal / _length(normal)


def _dot(one: np.ndarray, two: np.ndarray) -> float:
    return float(one[0] * two[0] + one[1] * two[1] + one[2] * two[2])


def _length(vector: np.ndarray) -> float:
    return math.sqrt(_dot(vector, vector))


__all__ = ["ResizeClosureParams", "resize_closure"]
