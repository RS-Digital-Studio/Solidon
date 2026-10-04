"""Kammer ändern — Innenmaß und Tiefe einer Kammer, einer Nut oder eines Kanals (RM-184).

Der Dateiaudit (§7) verlangt für die Kammer „Innenmaß oder Tiefe ändern,
gewählte Außenmaße erhalten“ und für Dichtweg und Kanal „Querschnitt
gekoppelt ändern“. Die Gruppe dazu kommt aus :mod:`app.core.perceive.groups`;
diese Operation ändert sie **als Ganzes**: Boden, Wände, Rundungen und Ecken
wandern gemeinsam, die Außenhaut des Körpers bleibt, wo sie ist — die Wand und
der Boden nehmen den Unterschied auf.

**Wie.** Der Luftraum der Kammer wird ein geschlossener Körper: ihre eigenen
Dreiecke, die Löcher im Boden verschlossen, oben ein Deckel über dem Rand
(:func:`chamber_air`). Er wird **gestreckt**, nicht skaliert: Was rechts der
Mitte liegt, wandert um die halbe Änderung nach rechts, was links liegt, nach
links — Eckenradien, Bodenrundungen und Wandneigung bleiben, wie sie sind.
Eine Nut mit runden Wänden weitet sich radial. Dann wird die Differenz
gebildet: Wächst die Kammer, wird der gestreckte Luftraum abgezogen; wird sie
kleiner, erst der alte Luftraum gefüllt und dann der neue abgezogen.

**Was nicht geht, sagt es** (Regel 17): eine Kammer mit unterbrochenem Rand
oder geteilten Wänden, eine Verkleinerung über die Mitte hinaus, eine Wand,
die durchbrechen würde. Ein offener Kanal mit genau zwei ebenen Wänden ändert
seine Breite über diese beiden Wände (:func:`geom.faces.push_face`), seine
Tiefe über den Boden.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, cast

import numpy as np

from app.core.errors import CANCEL, CHANGE_SELECTION, CORRECT_INPUT, GeometryError
from app.core.geom.boolean import boolean, without_effect
from app.core.geom.mesh import MeshData, as_mesh_data, signed_volume, stable_normals
from app.core.geom.prepare import FEATURE_OVERLAP
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Feature, Finding, OpContext, OpResult, SolverInfo
from app.core.units import EPS_GEOM
from app.i18n import _

if TYPE_CHECKING:
    # Träge, wie jede Kante von ``geom`` nach ``perceive``
    # (``tests/test_core_package_direction.py``).
    from app.core.perceive.groups import ChamberRegion, FunctionalGroup


@op_params
class ResizeChamberParams(BaseParams):
    at_feature: str = param(
        # Mit Kontext: „Kammer“ allein ist im Katalog die Druckkammer.
        title=_("Kammer", context="Merkmalsgruppe"),
        default="",
        kind="feature",
        doc=_("Boden oder Wand der Kammer. Geändert wird immer die ganze Kammer."),
    )
    width: float = param(
        title=_("Breite innen"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        doc=_(
            "Das neue Innenmaß quer. Die Wände rücken um die Hälfte der Änderung je "
            "Seite, die Außenmaße bleiben. Null behält das gemessene Maß."
        ),
    )
    length: float = param(
        title=_("Länge innen"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        doc=_(
            "Das neue Innenmaß längs, wie die Breite. Bei einer Nut gibt es nur die "
            "Breite. Null behält das gemessene Maß."
        ),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        doc=_(
            "Die neue Tiefe vom Rand bis zum Boden. Der Boden wandert, der Rand bleibt. "
            "Null behält das gemessene Maß."
        ),
    )


@register_op(
    name="resize_chamber",
    cache_version="1",
    title=_("Kammer ändern"),
    category="shaping",
    params=ResizeChamberParams,
    consumes=1,
    produces=1,
    applies_to=("face",),
    # Der Luftraum wird am Netz gestreckt: Ein exakter Körper kommt als
    # Dreiecksmodell zurück, und das Fenster sagt es vor der Rechnung.
    result_kind="mesh",
    doc=_(
        "Ändert Innenmaß und Tiefe einer erkannten Kammer, einer Nut oder eines Kanals als Ganzes: "
        "Boden, Wände und Rundungen wandern gemeinsam, die Außenmaße bleiben."
    ),
    caveat=_(
        "Nur an einer erkannten Kammer mit ebenem Rand, einer Nut oder einem Kanal "
        "mit zwei ebenen Wänden. Eine einzelne Wand verschiebt „Fläche versetzen“."
    ),
)
def resize_chamber(ctx: OpContext) -> OpResult:
    from app.core.perceive.groups import chamber_region, reason_against_group

    params = cast(ResizeChamberParams, ctx.params)
    source = ctx.inputs[0]
    body = as_mesh_data(source.mesh)
    region = chamber_region(source.features, body, params.at_feature, cancelled=ctx.cancelled)
    if region is None:
        raise not_a_chamber()
    group = region.group
    refusal = reason_against_group(group, source.features)
    if refusal is not None:
        raise GeometryError(detail=refusal, suggestions=(CHANGE_SELECTION, CANCEL))
    changes = _changes(group, params)
    if not any(abs(value) > EPS_GEOM for value in changes.values()):
        raise GeometryError(
            detail=_(
                "Alle drei Maße stehen auf dem gemessenen Wert — geändert wird nichts. "
                "Tragen Sie ein neues Innenmaß oder eine neue Tiefe ein."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    if group.kind == "channel" and group.variant == "trough":
        mesh, solver, findings = _trough(ctx, source, body, group, changes)
    else:
        mesh, solver, findings = _stretched_chamber(ctx, body, region, changes)
    effect = without_effect(body, mesh, "difference", ctx.profile)
    if effect is not None:
        findings.append(effect)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=mesh, kind="mesh", features={})],
        solver=solver,
        findings=[dataclasses.replace(entry, object_id=source.id) for entry in findings],
    )


def not_a_chamber() -> GeometryError:
    """Der Satz, wenn das Merkmal zu keiner Kammer gehört (Regel 17)."""
    from app.core.perceive.groups import NOT_A_CHAMBER

    return GeometryError(detail=NOT_A_CHAMBER, suggestions=(CHANGE_SELECTION, CANCEL))


def _changes(group: FunctionalGroup, params: ResizeChamberParams) -> dict[str, float]:
    """Die Änderung je Maß gegen das gemessene — null, wo das Feld leer ist."""
    found: dict[str, float] = {}
    for name in ("width", "length", "depth"):
        wanted = float(getattr(params, name))
        measured = group.measure(name)
        if measured is None or wanted <= EPS_GEOM:
            found[name] = 0.0
            continue
        found[name] = wanted - measured
    if group.variant in ("groove", "ring"):
        found["length"] = 0.0
    return found


# --- Kammer und Nut: der gestreckte Luftraum ---------------------------------


def _stretched_chamber(
    ctx: OpContext, body: MeshData, region: ChamberRegion, changes: dict[str, float]
) -> tuple[MeshData, SolverInfo, list[Finding]]:
    depth = float(region.group.measure("depth") or 0.0)
    # Über den Rand hinaus um die Werkzeugzugabe, damit die Differenz die
    # Randfläche durchschneidet und nicht genau auf ihr endet.
    tool = chamber_air(body, region, depth, FEATURE_OVERLAP)
    fill = chamber_air(body, region, depth, 0.0)
    if tool is None or fill is None:
        raise GeometryError(
            detail=_(
                "Der Raum dieser Kammer lässt sich nicht als Ganzes greifen — ihr Rand ist "
                "nicht geschlossen. Ändern Sie eine Wand über „Fläche versetzen“."
            ),
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    moved_tool = _moved(tool, region, changes, depth)
    moved_fill = _moved(fill, region, changes, depth)
    grows = all(value >= -EPS_GEOM for value in changes.values())
    ctx.cancelled.raise_if_cancelled()
    if grows:
        outcome = boolean(
            "difference", [body, moved_tool], quality=ctx.quality, cancelled=ctx.cancelled
        )
        findings = list(outcome.findings)
    else:
        filled = boolean("union", [body, fill], quality=ctx.quality, cancelled=ctx.cancelled)
        outcome = boolean(
            "difference", [filled.mesh, moved_tool], quality=ctx.quality, cancelled=ctx.cancelled
        )
        findings = [*filled.findings, *outcome.findings]
    expected = signed_volume(fill.raw) - signed_volume(moved_fill.raw)
    actual = signed_volume(outcome.mesh.raw) - signed_volume(body.raw)
    tolerance = max(1e-2, 1e-5 * abs(signed_volume(body.raw)))
    if actual - expected > tolerance:
        # Weniger abgetragen, als der gestreckte Raum verlangt: Ein Teil lag
        # außerhalb des Körpers — die Wand ist durchgebrochen.
        raise GeometryError(
            detail=_(
                "Mit diesem Maß würde eine Wand oder der Boden durchbrechen. Wählen Sie ein "
                "kleineres Innenmaß oder eine geringere Tiefe."
            ),
            values={"missing_mm3": round(actual - expected, 3)},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return outcome.mesh, outcome.solver, findings


def chamber_air(
    body: MeshData, region: ChamberRegion, depth: float, lift: float
) -> MeshData | None:
    """Der Luftraum der Kammer als geschlossener Körper — oder ``None``.

    Boden und Wände sind die Dreiecke der Kammer selbst, umgedreht; Löcher im
    Boden (Ablauflöcher am Besteckkorb) bekommen einen ebenen Deckel auf
    Bodenhöhe; der Rand bekommt einen Deckel ``lift`` über sich, verbunden über
    senkrechte Streifen. ``None``, wenn der Rand nicht aus ebenen Ringen auf
    Rand- oder Bodenhöhe besteht oder das Ergebnis nicht dicht ist.
    """
    import trimesh

    raw = body.raw
    vertices = np.asarray(raw.vertices, dtype=np.float64)
    faces = np.asarray(raw.faces, dtype=np.int64)[region.triangles]
    loops = rims_of(faces)
    if not loops:
        return None
    normal = np.asarray(region.normal, dtype=np.float64)
    origin = np.asarray(region.origin, dtype=np.float64)
    level = max(1e-3, 1e-6 * float(np.abs(vertices).max()))
    rims: list[list[int]] = []
    floors: list[list[int]] = []
    for loop in loops:
        heights = _heights(vertices[loop], origin, normal)
        if float(np.abs(heights - depth).max()) <= level:
            rims.append(loop)
        elif float(np.abs(heights).max()) <= level:
            floors.append(loop)
        else:
            return None
    if not rims:
        return None
    used = np.unique(np.concatenate([faces.reshape(-1), *[np.asarray(loop) for loop in rims]]))
    index = {int(old): new for new, old in enumerate(used.tolist())}
    points = [vertices[used]]
    count = len(used)
    triangles: list[np.ndarray] = [np.vectorize(index.__getitem__)(faces[:, ::-1])]
    first, second = (np.asarray(axis, dtype=np.float64) for axis in region.axes)
    for loop in floors:
        cap = flat_cap(
            [[index[int(vertex)] for vertex in loop]], np.vstack(points), origin, first, second
        )
        if cap is None:
            return None
        triangles.append(cap[:, ::-1])
    top_loops: list[list[int]] = []
    for loop in rims:
        local = [index[int(vertex)] for vertex in loop]
        if lift > 0.0:
            lifted = vertices[loop] + normal * lift
            points.append(lifted)
            copies = list(range(count, count + len(loop)))
            count += len(loop)
            for position, (low, high) in enumerate(zip(local, copies, strict=True)):
                after = (position + 1) % len(loop)
                triangles.append(
                    np.asarray([[low, local[after], copies[after]], [low, copies[after], high]])
                )
            top_loops.append(copies)
        else:
            top_loops.append(local)
    cap = flat_cap(top_loops, np.vstack(points), origin, first, second)
    if cap is None:
        return None
    triangles.append(cap)
    air = trimesh.Trimesh(vertices=np.vstack(points), faces=np.vstack(triangles), process=False)
    air.fix_normals()
    if not air.is_watertight:
        return None
    if signed_volume(air) < 0.0:
        air.invert()
    return MeshData(raw=air)


def _heights(points: np.ndarray, origin: np.ndarray, normal: np.ndarray) -> np.ndarray:
    relative = points - origin
    return np.asarray(
        relative[:, 0] * normal[0] + relative[:, 1] * normal[1] + relative[:, 2] * normal[2]
    )


def rims_of(faces: np.ndarray) -> list[list[int]]:
    """Die Randringe einer Dreiecksmenge als Eckenfolgen, in Umlaufrichtung."""
    directed = np.concatenate((faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]))
    forward = {(int(a), int(b)) for a, b in directed.tolist()}
    following: dict[int, int] = {}
    for a, b in sorted(forward):
        if (b, a) not in forward:
            if a in following:
                return []
            following[a] = b
    loops: list[list[int]] = []
    seen: set[int] = set()
    for start in sorted(following):
        if start in seen:
            continue
        loop = [start]
        seen.add(start)
        current = following[start]
        while current != start:
            if current in seen or current not in following:
                return []
            loop.append(current)
            seen.add(current)
            current = following[current]
        loops.append(loop)
    return loops


def flat_cap(
    loops: list[list[int]],
    points: np.ndarray,
    origin: np.ndarray,
    first: np.ndarray,
    second: np.ndarray,
) -> np.ndarray | None:
    """Ein ebener Deckel über Ringen derselben Ebene, Dreiecke über deren Ecken.

    Der größte Ring ist der Umriss, die übrigen sind Löcher darin (die
    Innenwand einer Nut). Trianguliert wie die Schnittdeckel in
    :mod:`app.core.geom.section`; jeder Punkt des Ergebnisses ist eine Ecke
    eines Rings, sonst gibt es keinen Deckel.
    """
    from scipy.spatial import cKDTree
    from shapely.geometry import Polygon
    from trimesh.creation import triangulate_polygon

    planar = []
    for loop in loops:
        relative = points[loop] - origin
        planar.append(
            np.column_stack(
                (
                    relative[:, 0] * first[0]
                    + relative[:, 1] * first[1]
                    + relative[:, 2] * first[2],
                    relative[:, 0] * second[0]
                    + relative[:, 1] * second[1]
                    + relative[:, 2] * second[2],
                )
            )
        )
    shapes = [Polygon(ring) for ring in planar]
    if any(not shape.is_valid or shape.area <= EPS_GEOM for shape in shapes):
        return None
    order = sorted(range(len(shapes)), key=lambda position: -shapes[position].area)
    outline = order[0]
    holes = [position for position in order[1:] if shapes[outline].contains(shapes[position])]
    if len(holes) != len(order) - 1:
        return None
    polygon = Polygon(planar[outline], [planar[position] for position in holes])
    found, triangles = triangulate_polygon(polygon, force_vertices=True)
    if not len(triangles):
        return None
    corners = np.concatenate([np.asarray(loops[position]) for position in [outline, *holes]])
    flat = np.vstack([planar[position] for position in [outline, *holes]])
    distance, nearest = cKDTree(flat).query(np.asarray(found, dtype=np.float64))
    if float(np.max(distance)) > 1e-6:
        return None
    return np.asarray(corners[np.asarray(nearest, dtype=np.int64)][np.asarray(triangles)])


def _moved(
    air: MeshData, region: ChamberRegion, changes: dict[str, float], depth: float
) -> MeshData:
    """Der Luftraum, gestreckt: je Achse jede Hälfte um die halbe Änderung."""
    import trimesh

    points = np.asarray(air.raw.vertices, dtype=np.float64)
    origin = np.asarray(region.origin, dtype=np.float64)
    normal = np.asarray(region.normal, dtype=np.float64)
    shift = np.zeros_like(points)
    group = region.group
    if group.variant in ("groove", "ring"):
        if abs(changes["width"]) > EPS_GEOM:
            shift += _radial(points, region, changes["width"])
    else:
        for name, axis in (("width", region.axes[0]), ("length", region.axes[1])):
            change = changes[name]
            if abs(change) > EPS_GEOM:
                direction = np.asarray(axis, dtype=np.float64)
                shift += (
                    _halves(_heights(points, origin, direction), change, name)[:, None] * direction
                )
    change = changes["depth"]
    if abs(change) > EPS_GEOM:
        heights = _heights(points, origin, normal)
        below = heights < _split(heights, change, "depth", within=(0.0, depth))
        shift -= np.where(below, change, 0.0)[:, None] * normal
    moved = trimesh.Trimesh(vertices=points + shift, faces=np.asarray(air.raw.faces), process=False)
    return MeshData(raw=moved)


def _halves(along: np.ndarray, change: float, name: str) -> np.ndarray:
    """Je Ecke die halbe Änderung mit dem Vorzeichen ihrer Seite der Mitte."""
    split = _split(along, change, name)
    return np.where(along > split, change / 2.0, -change / 2.0)


def _split(
    values: np.ndarray, change: float, name: str, within: tuple[float, float] | None = None
) -> float:
    """Die Mitte der größten Lücke zwischen den Ecken — dort wird gestreckt.

    Keine Ecke liegt in der Lücke, also verbiegt sich kein Dreieck, es wird
    nur länger. Verkleinert wird höchstens um diese Lücke: Weiter kämen die
    Hälften einander in die Quere.
    """
    ordered = np.unique(np.round(values, 9))
    if within is not None:
        ordered = ordered[(ordered >= within[0] - 1e-6) & (ordered <= within[1] + 1e-6)]
    if len(ordered) < 2:
        raise _too_small(name)
    gaps = np.diff(ordered)
    widest = int(np.argmax(gaps))
    if change < 0.0 and -change >= float(gaps[widest]) - EPS_GEOM:
        raise _too_small(name)
    return float(ordered[widest] + gaps[widest] / 2.0)


def _radial(points: np.ndarray, region: ChamberRegion, change: float) -> np.ndarray:
    """Eine runde Nut weitet sich radial: außen nach außen, innen nach innen."""
    origin = np.asarray(region.origin, dtype=np.float64)
    normal = np.asarray(region.normal, dtype=np.float64)
    centre = origin
    relative = points - centre
    along = _heights(points, centre, normal)
    across = relative - along[:, None] * normal
    radius = np.sqrt(
        across[:, 0] * across[:, 0] + across[:, 1] * across[:, 1] + across[:, 2] * across[:, 2]
    )
    split = _split(radius, change, "width")
    outward = np.where(radius > split, 1.0, -1.0)
    safe = np.where(radius > EPS_GEOM, radius, 1.0)
    return np.asarray((outward * change / 2.0 / safe)[:, None] * across)


def _too_small(name: str) -> GeometryError:
    titles = {"width": _("Breite innen"), "length": _("Länge innen"), "depth": _("Tiefe")}
    return GeometryError(
        detail=_(
            "So weit lässt sich „{field}“ nicht verkleinern — die Kammer fiele in sich "
            "zusammen. Wählen Sie ein größeres Maß.",
            field=titles.get(name, name),
        ),
        values={"field": name},
        suggestions=(CORRECT_INPUT, CANCEL),
    )


# --- Kanal: zwei ebene Wände ------------------------------------------------


def _trough(
    ctx: OpContext,
    source: object,
    body: MeshData,
    group: FunctionalGroup,
    changes: dict[str, float],
) -> tuple[MeshData, SolverInfo, list[Finding]]:
    """Ein offener Kanal mit genau zwei ebenen Wänden: Wände und Boden versetzen."""
    from app.core.geom.faces import push_face
    from app.core.perceive.groups import TROUGH_WALLS, trough_walls

    features = getattr(source, "features", {})
    walls = trough_walls(group, features)
    if not walls:
        raise GeometryError(detail=TROUGH_WALLS, suggestions=(CHANGE_SELECTION, CANCEL))
    if abs(changes["length"]) > EPS_GEOM:
        raise GeometryError(
            detail=_(
                "Ein offener Kanal hat keine Länge innen — er läuft bis an seine Enden. "
                "Ändern Sie Breite oder Tiefe."
            ),
            values={"field": "length"},
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    mesh = body
    solver = SolverInfo(strategy="direct")
    findings: list[Finding] = []
    # **Erst beide Wände, dann der Boden — und jede Fläche an ihrem Netz.**
    # Nach dem ersten Versetzen zeigen die Dreiecksnummern der übrigen Flächen
    # ins neue Netz und treffen dort anderes; deshalb wird jede Fläche vor
    # ihrem Schritt an ihrer Ebene wiedergefunden (:func:`_plane_again`). Und
    # der Boden kommt nach den Wänden: Sein Werkzeug steht dann unter der
    # neuen Breite, sonst bliebe in der Ecke ein Streifen stehen.
    steps = [(features[wall], -changes["width"] / 2.0) for wall in walls]
    steps.append((features[group.anchor], -changes["depth"]))
    for feature, distance in steps:
        if abs(distance) <= EPS_GEOM:
            continue
        ctx.cancelled.raise_if_cancelled()
        current = feature if mesh is body else _plane_again(body, mesh, feature)
        outcome = push_face(mesh, current, distance, quality=ctx.quality, cancelled=ctx.cancelled)
        mesh, solver = outcome.mesh, outcome.solver
        findings.extend(outcome.findings)
    return mesh, solver, findings


def _plane_again(before: MeshData, after: MeshData, feature: Feature) -> Feature:
    """Dieselbe ebene Fläche im neuen Netz: ihre Ebene, ihr Bereich, ihre Richtung.

    Gesucht werden Dreiecke mit derselben Normalen auf derselben Ebene, deren
    Mitten im um den Weg der Wände vergrößerten Umriss der alten Fläche liegen.
    """
    old_vertices = np.asarray(before.raw.vertices, dtype=np.float64)
    old_faces = np.asarray(before.raw.faces, dtype=np.int64)[list(feature.face_indices)]
    corners = old_vertices[old_faces.reshape(-1)]
    normal = np.asarray(feature.params["normal"], dtype=np.float64)
    origin = corners.mean(axis=0)
    low = corners.min(axis=0)
    high = corners.max(axis=0)
    reach = float(np.max(high - low))
    vertices = np.asarray(after.raw.vertices, dtype=np.float64)
    faces = np.asarray(after.raw.faces, dtype=np.int64)
    centres = vertices[faces].mean(axis=1)
    normals, _areas = stable_normals(after.raw)
    facing = normals[:, 0] * normal[0] + normals[:, 1] * normal[1] + normals[:, 2] * normal[2]
    level = np.abs(_heights(centres, origin, normal))
    inside = np.all((centres >= low - reach) & (centres <= high + reach), axis=1)
    found = np.flatnonzero((facing >= 1.0 - 1e-9) & (level <= 1e-6) & inside)
    if not len(found):
        raise GeometryError(
            detail=_(
                "Nach dem Versetzen der Wände ist der Boden nicht wiederzufinden. Ändern Sie "
                "Breite und Tiefe in zwei Schritten."
            ),
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return dataclasses.replace(feature, face_indices=tuple(int(index) for index in found))


__all__ = [
    "ResizeChamberParams",
    "chamber_air",
    "flat_cap",
    "not_a_chamber",
    "resize_chamber",
    "rims_of",
]
