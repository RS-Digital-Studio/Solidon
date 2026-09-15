"""Ein begrenztes Schnittfeld für Skizzenflächen und parametrische Organizer (§25)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final, cast

from shapely.affinity import translate
from shapely.geometry import Polygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.core.errors import ValidationError
from app.core.geom.sketch_solid import ARC_STEPS, outline_points
from app.core.registry import op_params, param, register_op
from app.core.sketch import shapes
from app.core.sketch.profile import Profile, arc_through, profile_of, shifted
from app.core.sketch.solver import solve_sketch
from app.core.types import (
    BaseParams,
    CancelToken,
    Feature,
    Finding,
    OpContext,
    OpResult,
    Point2,
    SceneObject,
)
from app.core.units import EPS_GEOM, MAX_FACET_SAG
from app.i18n import TranslatableText, _

MAX_FIELD_TOOLS: Final = 4096


def _invalid(detail: TranslatableText) -> ValidationError:
    return ValidationError(field="spacing", constraint="field_layout", detail=detail)


@dataclass(frozen=True, slots=True)
class FieldTools:
    """Vollständig passende Umrisse und ihre festen Rastermittelpunkte."""

    profiles: tuple[Profile, ...]
    centres: tuple[Point2, ...]
    candidates: int


def _sag(profile: Profile) -> float:
    """Die maximale Kreisabweichung der bestehenden Mesh-Umrissabtastung."""
    radius = profile.circle[1] if profile.circle is not None else 0.0
    for segment in profile.segments:
        if segment.kind == "arc" and segment.via is not None:
            arc = arc_through(segment.start, segment.via, segment.end)
            if arc is not None:
                radius = max(radius, arc[1])
    return radius * (1 - math.cos(math.pi / ARC_STEPS))


def _region(profile: Profile, *, exact: bool) -> tuple[BaseGeometry, float]:
    """Die bestehende Profilkurve mit konservativem Rand für die Flächenprüfung."""
    if exact and any(segment.kind == "spline" for segment in profile.segments):
        # Ein exakter interpolierender Spline ist nicht der Stützpunktzug des
        # Mesh-Rückwegs. Dieselbe B-Rep-Fläche liefert seine tolerierte Grenze.
        from app.core.brep import profiles

        body = profiles.extrude(profile, 1.0).mesh.raw
        faces = body.triangles[body.face_normals[:, 2] > 1 - EPS_GEOM]
        return unary_union([Polygon(face[:, :2]) for face in faces]), MAX_FACET_SAG
    outer: BaseGeometry = Polygon(outline_points(profile))
    error = _sag(profile)
    if not outer.is_valid or outer.area <= EPS_GEOM**2:
        raise _invalid(
            _("Die Feldgrenze umschließt keine gültige Fläche. Korrigieren Sie die Skizze.")
        )
    holes = []
    for hole in profile.holes:
        inner, uncertainty = _region(hole, exact=exact)
        holes.append(inner.buffer(uncertainty))
    if holes:
        outer = outer.difference(unary_union(holes))
    return outer, error


def _shape(shape: str, diameter: float, slot_length: float) -> Profile:
    if shape == "circle":
        return Profile(circle=((0.0, 0.0), diameter / 2))
    if shape == "slot":
        return profile_of(solve_sketch(shapes.slot(slot_length, diameter)))
    if shape == "hexagon":
        return profile_of(solve_sketch(shapes.polygon(diameter, 6)))
    raise _invalid(_("Wählen Sie runde Löcher, Langlöcher oder sechseckige Öffnungen."))


def field_tools(
    regions: Sequence[Profile],
    exclusions: Sequence[Profile],
    *,
    diameter: float,
    spacing: float,
    margin: float,
    web: float,
    shape: str = "circle",
    pattern: str = "grid",
    slot_length: float = 12.0,
    origin: Point2 = (0, 0),
    exact: bool = False,
    cancelled: CancelToken | None = None,
) -> FieldTools:
    """Nur ganze Öffnungen zulassen; Wände und Ausschlüsse bleiben vollständig erhalten."""
    if not all(
        math.isfinite(value) for value in (diameter, spacing, margin, web, slot_length, *origin)
    ):
        raise _invalid(_("Die Feldmaße müssen endliche Zahlen sein. Korrigieren Sie die Maße."))
    if min(diameter, spacing) <= EPS_GEOM or min(margin, web) < 0:
        raise _invalid(
            _("Lochmaß und Raster müssen positiv sein. Rand und Steg dürfen nicht negativ sein.")
        )
    if pattern not in ("grid", "staggered"):
        raise _invalid(_("Wählen Sie ein gerades oder versetztes Raster."))
    tool = _shape(shape, diameter, slot_length)
    outline = Polygon(outline_points(tool))
    guard = outline.buffer(_sag(tool))
    pitch_y = spacing * (math.sqrt(3) / 2 if pattern == "staggered" else 1)
    # Die Nachbarschaft des vollständigen regelmäßigen Musters genügt. Damit
    # kostet die Stegprüfung konstant Zeit statt quadratisch je Lochzahl.
    for row in range(-1, 2):
        for column in range(-1, 2):
            if row == column == 0:
                continue
            dx = spacing * (column + (0.5 if pattern == "staggered" and row else 0))
            dy = row * pitch_y
            other = translate(guard, dx, dy)
            if (
                guard.intersection(other).area > EPS_GEOM**2
                or guard.distance(other) < web - EPS_GEOM
            ):
                raise _invalid(
                    _(
                        "Zwischen den Öffnungen bleibt zu wenig Steg. "
                        "Vergrößern Sie das Raster oder verkleinern Sie die Öffnungen."
                    )
                )
    allowed_parts = []
    for profile in regions:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        polygon, error = _region(profile, exact=exact)
        allowed_parts.append(polygon.buffer(-margin - error))
    allowed = unary_union(allowed_parts)
    for profile in exclusions:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        polygon, error = _region(profile, exact=exact)
        allowed = allowed.difference(polygon.buffer(margin + error))
    if allowed.is_empty:
        raise _invalid(
            _(
                "Nach Rand und Ausschlüssen bleibt keine Fläche. Verkleinern "
                "Sie den Rand oder ändern Sie die Skizze."
            )
        )
    x0, y0, x1, y1 = allowed.bounds
    low_x, high_x = (
        math.floor((x0 - origin[0]) / spacing) - 1,
        math.ceil((x1 - origin[0]) / spacing) + 1,
    )
    low_y, high_y = math.floor((y0 - origin[1]) / pitch_y), math.ceil((y1 - origin[1]) / pitch_y)
    columns, rows = high_x - low_x + 1, high_y - low_y + 1
    if columns * rows > MAX_FIELD_TOOLS:
        raise _invalid(
            _(
                "Das Feld hat zu viele Öffnungen. Vergrößern Sie das Raster "
                "oder verkleinern Sie den Bereich."
            )
        )
    centre = (origin[0] + (low_x + high_x) / 2 * spacing, (low_y + high_y) / 2 * spacing)
    candidates = shapes.grid_centres(columns, rows, spacing, origin=centre)
    profiles_found: list[Profile] = []
    centres: list[Point2] = []
    for index, (x, _grid_y) in enumerate(candidates):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        row = low_y + index // columns
        y = origin[1] + row * pitch_y
        if pattern == "staggered" and row % 2:
            x += spacing / 2
        if allowed.covers(translate(guard, x, y)):
            profiles_found.append(shifted(tool, x, y))
            centres.append((x, y))
    if not profiles_found:
        raise _invalid(
            _(
                "In diesen Bereich passt keine ganze Öffnung. Verkleinern "
                "Sie die Öffnungen oder den Rand."
            )
        )
    return FieldTools(tuple(profiles_found), tuple(centres), len(candidates))


@op_params
class FieldCutParams(BaseParams):
    region_sketch: str = param(
        title=_("Feldbereich"),
        default="",
        kind="sketch",
        required=True,
        doc=_("Zeichnen Sie die Fläche für die Öffnungen. Innenringe bleiben ausgespart."),
    )
    shape: str = param(
        title=_("Öffnungsform"),
        default="circle",
        choices=("circle", "slot", "hexagon"),
        doc=_("Runde Löcher, Langlöcher oder sechseckige Öffnungen."),
    )
    diameter: float = param(
        title=_("Lochmaß"),
        default=6.0,
        minimum=0.1,
        maximum=1000.0,
        unit="mm",
        doc=_("Durchmesser runder Löcher, Breite von Langlöchern oder Eckmaß eines Sechsecks."),
    )
    spacing: float = param(
        title=_("Rasterabstand"),
        default=15.0,
        minimum=0.1,
        maximum=2000.0,
        unit="mm",
        doc=_("Abstand zwischen den Mittelpunkten benachbarter Öffnungen."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=4.0,
        minimum=0.1,
        maximum=1000.0,
        unit="mm",
        depends_on=("through", (False,)),
        doc=_("Schnitttiefe ab der Zeichenfläche, auf einer Grundebene ab der Körperoberkante."),
    )
    exclusion_sketch: str = param(
        title=_("Ausschlüsse"),
        default="",
        kind="sketch",
        placement="advanced",
        doc=_("Freizuhaltende Flächen auf derselben Zeichenebene, etwa für Füße oder Anschlüsse."),
    )
    pattern: str = param(
        title=_("Raster"),
        default="grid",
        choices=("grid", "staggered"),
        placement="advanced",
        doc=_("Gerade Reihen oder um eine halbe Teilung versetzte Reihen für ein Wabenmuster."),
    )
    margin: float = param(
        title=_("Randabstand"),
        default=2.0,
        minimum=0.0,
        maximum=1000.0,
        unit="mm",
        placement="advanced",
        doc=_("Mindestabstand jeder vollständigen Öffnung zum Bereichsrand und zu Ausschlüssen."),
    )
    web: float = param(
        title=_("Mindeststeg"),
        default=1.0,
        minimum=0.0,
        maximum=1000.0,
        unit="mm",
        placement="advanced",
        doc=_("Mindestens verbleibendes Material zwischen benachbarten Öffnungen."),
    )
    slot_length: float = param(
        title=_("Langlochlänge"),
        default=12.0,
        minimum=0.1,
        maximum=1000.0,
        unit="mm",
        placement="advanced",
        depends_on=("shape", ("slot",)),
        doc=_("Gesamtlänge des Langlochs einschließlich seiner runden Enden."),
    )
    through: bool = param(
        title=_("Durchgehend"),
        default=False,
        placement="advanced",
        doc=_("Schneidet durch die ganze Höhe des Körpers — die Tiefe zählt dann nicht."),
    )
    z: float = param(
        title=_("Schnittoberkante"),
        default=0.0,
        minimum=-2000.0,
        maximum=2000.0,
        unit="mm",
        placement="advanced",
        doc=_(
            "Auf einer Grundebene: Höhe entlang ihrer Normalen; null nimmt die Körperoberkante. "
            "Auf einer Körperfläche beginnt der Schnitt an dieser Fläche."
        ),
    )
    origin_x: float = param(
        title=_("Rasterursprung X"),
        default=0.0,
        minimum=-2000.0,
        maximum=2000.0,
        unit="mm",
        placement="advanced",
        doc=_("Ursprung des Rasters in der waagerechten Richtung der Zeichenebene."),
    )
    origin_y: float = param(
        title=_("Rasterursprung Y"),
        default=0.0,
        minimum=-2000.0,
        maximum=2000.0,
        unit="mm",
        placement="advanced",
        doc=_("Ursprung des Rasters in der senkrechten Richtung der Zeichenebene."),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=False,
        placement="advanced",
        depends_on=("shape", ("circle", "slot")),
        doc=_(
            "Vergrößert Lochmaß und Langlochlänge um dieselbe Materialzugabe wie beim Bohren. "
            "Sechseckige Öffnungen behalten ihr Eckmaß."
        ),
    )


@register_op(
    name="field_cut",
    title=_("Lochfeld schneiden"),
    category="sketch",
    params=FieldCutParams,
    consumes=1,
    produces=1,
    reads_other_bodies=True,
    doc=_(
        "Schneidet ein regelmäßiges Loch-, Langloch- oder Wabenfeld in die gezeichnete Fläche. "
        "Ränder, Innenringe und Ausschlüsse bleiben erhalten."
    ),
)
def field_cut(ctx: OpContext) -> OpResult:
    from app.core.errors import CHOOSE_PRINTER
    from app.core.geom.hollow import below_printable_wall
    from app.core.geom.prepare import bore_diameter, compensation_findings
    from app.core.knowledge.profiles import for_object
    from app.core.sketch.ops import _solved_drawing, cut_regions
    from app.core.sketch.profile import regions_of
    from app.core.sketch.serialize import sketch_from_text

    params = cast(FieldCutParams, ctx.params)
    if not params.region_sketch:
        raise ValidationError(
            "region_sketch",
            _("Zeichnen Sie zuerst den Bereich für die Öffnungen."),
            constraint="missing_region",
        )
    plane = sketch_from_text(params.region_sketch).plane
    findings: list[Finding] = []
    ctx.cancelled.raise_if_cancelled()
    ctx.progress(0.05, str(_("Feldgrenzen aufbereiten")))
    regions = regions_of(_solved_drawing(ctx, params.region_sketch, findings))
    exclusions: tuple[Profile, ...] = ()
    if params.exclusion_sketch:
        if sketch_from_text(params.exclusion_sketch).plane != plane:
            raise ValidationError(
                "exclusion_sketch",
                _("Zeichnen Sie Bereich und Ausschlüsse auf derselben Ebene."),
                constraint="different_planes",
            )
        exclusions = regions_of(_solved_drawing(ctx, params.exclusion_sketch, findings))
    profile = for_object(ctx.profile, ctx.inputs[0]) if ctx.profile is not None else None
    diameter = params.diameter
    compensate = params.compensate and params.shape in ("circle", "slot")
    if compensate:
        if profile is None:
            raise ValidationError(
                "compensate",
                _("Wählen Sie einen Drucker und ein Material für die Lochzugabe."),
                constraint="missing_profile",
                suggestions=[CHOOSE_PRINTER],
            )
        diameter = bore_diameter(diameter, profile, True)
    tools = field_tools(
        regions,
        exclusions,
        diameter=diameter,
        spacing=params.spacing,
        margin=params.margin,
        web=params.web,
        shape=params.shape,
        pattern=params.pattern,
        slot_length=params.slot_length + diameter - params.diameter,
        origin=(params.origin_x, params.origin_y),
        exact=ctx.inputs[0].kind == "brep",
        cancelled=ctx.cancelled,
    )
    ctx.progress(0.3, str(_("Lochfeld schneiden")))
    cut = cut_regions(
        ctx, list(tools.profiles), plane, depth=params.depth, through=params.through, z=params.z
    )
    findings.extend(compensation_findings(params.diameter, diameter, compensate))
    thin = below_printable_wall(min(params.margin, params.web), profile)
    if thin is not None:
        findings.append(thin)
    output = cut.outputs[0]
    if params.shape == "circle":
        output = _named_bores(ctx, output, cut, tools, plane, diameter, params)
    return replace(cut, outputs=[output], findings=[*findings, *cut.findings])


def _named_bores(
    ctx: OpContext,
    output: SceneObject,
    cut: OpResult,
    tools: FieldTools,
    plane: str,
    diameter: float,
    params: FieldCutParams,
) -> SceneObject:
    """Bekannte Maße nur an tatsächlich gefundenen und geometrisch bestätigten Löchern.

    Die Erkennung läuft einmal; ihr Netzcache bedient anschließend die normale
    Auswertung. Ein Werkzeug außerhalb des Körpers erzeugt keinen Merkmalseintrag.
    Tiefe und Durchgang stammen stets aus dem Ergebnis, nicht aus dem Werkzeug.
    """
    import numpy as np
    from scipy.spatial import cKDTree

    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.prepare_ops import _with_nominal_bore
    from app.core.perceive.features import detect
    from app.core.perceive.local import FEATURE_LIMIT_TRIANGLES
    from app.core.sketch.planes import frame_for_plane, to_plane, to_world
    from app.core.units import match_tolerance

    if cut.solver is not None and cut.solver.strategy in ("voxel", "jittered"):
        return output
    frame = frame_for_plane(plane, ctx.scene.objects.values())
    assert frame is not None
    mesh = as_mesh_data(output.mesh)
    if output.kind != "brep" and mesh.triangle_count > FEATURE_LIMIT_TRIANGLES:
        return output
    found = (
        dict(output.features)
        if output.kind == "brep"
        else detect(mesh, check_cancelled=ctx.cancelled.raise_if_cancelled)
    )
    points = cKDTree(tools.centres)
    tolerance = match_tolerance(mesh.bounds.diagonal)
    named: dict[str, Feature] = {}
    counts: dict[tuple[int, int], int] = {}
    ordinal = 1
    taken = (*ctx.inputs[0].features, *ctx.inputs[0].reserved_feature_ids)
    while any(name.startswith(f"field_{ordinal}_") for name in taken):
        ordinal += 1
    for key, feature in found.items():
        ctx.cancelled.raise_if_cancelled()
        if feature.kind != "hole":
            named[key] = feature
            continue
        centre = feature.params["centre"]
        distance, index = points.query(to_plane(frame, centre))
        if distance > tolerance:
            named[key] = feature
            continue
        point = tools.centres[int(index)]
        expected = replace(
            feature,
            params={
                **feature.params,
                "centre": to_world(frame, point),
                "axis": frame.normal,
            },
        )
        if output.kind == "brep":
            # Die exakte Zylinderfläche kennt ihren Radius. Die Lageprüfung
            # muss auch ihre Richtung belegen, nicht nur die Projektion.
            aligned = abs(float(np.dot(feature.params["axis"], frame.normal)))
            if aligned < 1 - EPS_GEOM or abs(feature.params["diameter"] - diameter) > EPS_GEOM:
                named[key] = feature
                continue
            checked = feature
        else:
            checked = _with_nominal_bore(mesh, feature, expected, diameter, sections=ARC_STEPS)
            if checked is feature:
                named[key] = feature
                continue
        row = round(
            (point[1] - params.origin_y)
            / (params.spacing * (math.sqrt(3) / 2 if params.pattern == "staggered" else 1))
        )
        offset = 0.5 if params.pattern == "staggered" and row % 2 else 0
        column = round((point[0] - params.origin_x) / params.spacing - offset)
        grid_key = (column, row)
        counts[grid_key] = counts.get(grid_key, 0) + 1
        name = f"field_{ordinal}_hole_{column}_{row}_{counts[grid_key]}"
        named[name] = replace(checked, id=name, provenance="generated")
    return replace(output, features=named)
