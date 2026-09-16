"""Geteilte Profilklemmen und separat austauschbare Einlagen (§24)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Final, cast

import numpy as np
from shapely.geometry import LineString, Polygon

from app.core.deferred import trimesh
from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean
from app.core.geom.contours import offset_section as normal_offset
from app.core.geom.contours import polygons_of
from app.core.geom.contours import section_of as profile_section
from app.core.geom.mesh import MeshData
from app.core.knowledge import standards
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.registry import PartChange, WallRequirement, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, CancelToken, Feature, PartResult, Quality, SolverInfo
from app.core.units import DEGREE_UNIT, EPS_GEOM, MAX_FACET_SAG
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.sketch.profile import Profile as SketchProfile

#: Die Kontur und ihre aufeinander folgenden Versätze teilen sich das
#: Auflösungsbudget des Kerns. Das ist Sehnenauflösung, kein Fertigungsspiel.
CONTOUR_SAG: Final = MAX_FACET_SAG / 8.0
_ADDED = PartChange("1", "2026-09-15", "Geteilte Profilklemme mit separat wechselbaren Einlagen.")
_SHELL_SEATED = PartChange(
    version="19",
    date="2026-09-16",
    reason="Die Schale allein begann bei der Bundhöhe der Einlage und schwebte als "
    "aufgesetzter Baustein um genau dieses Maß über ihrer Fläche.",
    effect="Die Schale beginnt bei null; den Bundfreiraum setzt das Klemmenpaar, das "
    "beide Hälften in einem Rahmen ablegt. Das Feld Bundhöhe gibt es an der Schale "
    "nicht mehr.",
)


def _invalid(detail: TranslatableText, field: str = "sketch") -> ValidationError:
    """Die Korrektur gehört zu demselben gezeichneten Profil und seinen Maßen."""
    return ValidationError(field=field, constraint="profile_clamp", detail=detail)


def section_of(profile: SketchProfile) -> Any:
    """Den vorhandenen Skizzenumriss als einen gefüllten Profilquerschnitt lesen."""
    if profile.holes:
        raise _invalid(_("Wählen Sie genau einen äußeren Profilumriss ohne weitere Ausschnitte."))
    return profile_section(profile, max_sag=CONTOUR_SAG)


def drawn_section(text: str) -> Any:
    """Ein Baustein erhält eine bereits numerisch aufgelöste Zeichnung."""
    from app.core.sketch.profile import profile_of
    from app.core.sketch.serialize import sketch_from_text
    from app.core.sketch.solver import solve_sketch

    if not text:
        raise _invalid(_("Zeichnen oder wählen Sie zuerst die Gegenkontur."))
    return section_of(profile_of(solve_sketch(sketch_from_text(text))))


def _circle_text(diameter: float) -> str:
    """Die Vorgabe nutzt dieselbe reguläre Zeichnung wie der gezeichnete Sitz."""
    from app.core.sketch import shapes as sketch_shapes
    from app.core.sketch.serialize import sketch_to_text

    return sketch_to_text(sketch_shapes.circle(diameter))


def polygon_of(section: Any) -> Polygon:
    """Ein gefüllter zusammenhängender Querschnitt, ohne versteckte weitere Konturen."""
    polygons = polygons_of(section)
    if len(polygons) != 1:
        raise _invalid(
            _("Der Konturversatz zerfällt in mehrere Teile. Ändern Sie Kontur oder Einlagenstärke.")
        )
    polygon = polygons[0]
    if polygon.interiors:
        raise _invalid(
            _("Der Konturversatz lässt keinen gültigen Sitz. Ändern Sie die Kontur oder das Spiel.")
        )
    return polygon


def offset_section(section: Any, distance: float) -> Any:
    """Echter Normalversatz; numerische Clipper-Restkanten werden an EPS_GEOM entfernt."""
    if abs(distance) <= EPS_GEOM:
        return section
    moved = normal_offset(section, distance, max_sag=CONTOUR_SAG)
    polygon_of(moved)
    return moved


def _rectangle(x0: float, x1: float, y0: float, y1: float) -> Any:
    import manifold3d

    return manifold3d.CrossSection.square((x1 - x0, y1 - y0)).translate((x0, y0))


def _mesh(solid: Any) -> MeshData:
    """Eine eigene Manifold-Konstruktion ohne Genauigkeitsverlust übernehmen."""
    raw = solid.to_mesh64()
    mesh = MeshData.of(
        trimesh.Trimesh(
            vertices=np.array(raw.vert_properties[:, :3], copy=True),
            faces=np.array(raw.tri_verts, copy=True),
            process=False,
        )
    )
    if (
        not mesh.is_watertight
        or mesh.component_count != 1
        or not mesh.raw.nondegenerate_faces().all()
    ):
        raise _invalid(
            _("Die Teilung erzeugt keine geschlossene einzelne Hälfte. Ändern Sie die Trennebene.")
        )
    return mesh


def _half(section: Any, half: str, gap: float, split_offset: float) -> Any:
    """Die Halbebene aus dem wirklichen Außenumfang ableiten, nicht aus einer Weltgröße."""
    if half not in {"lower", "upper"}:
        raise _invalid(_("Wählen Sie die untere oder obere Hälfte."), "half")
    left, low, right, high = section.bounds()
    reach = max(right - left, high - low, abs(split_offset), gap) + BOOLEAN_OVERLAP
    cut = split_offset + (-gap / 2.0 if half == "lower" else gap / 2.0)
    box = _rectangle(
        left - reach,
        right + reach,
        low - reach if half == "lower" else cut,
        cut if half == "lower" else high + reach,
    )
    clipped = section ^ box
    if len(clipped.decompose()) != 1 or clipped.area() <= EPS_GEOM**2:
        raise _invalid(
            _(
                "Diese Trennebene ergibt keine einzelne Hälfte. "
                "Verschieben oder drehen Sie die Trennebene."
            )
        )
    return clipped


def _monotone(section: Any, cancelled: CancelToken | None = None) -> None:
    """Ein seitlicher gerader Montageweg verlangt in Y genau ein Materialintervall."""
    polygon = polygon_of(section)
    points = np.asarray(polygon.exterior.coords)
    xs = np.unique(points[:, 0])
    samples = (xs[:-1] + xs[1:]) / 2.0
    low, high = polygon.bounds[1], polygon.bounds[3]
    for x in samples:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        cut = polygon.intersection(
            LineString(((x, low - BOOLEAN_OVERLAP), (x, high + BOOLEAN_OVERLAP)))
        )
        if cut.geom_type != "LineString":
            raise _invalid(
                _(
                    "Die Kontur hat in Montagerichtung einen Hinterschnitt. "
                    "Drehen Sie die Trennebene oder ändern Sie die Kontur."
                )
            )


def _oriented(section: Any, split_angle: float) -> Any:
    """Im Teilungsrahmen rechnen und das Ergebnis danach zurückdrehen."""
    return section.rotate(-split_angle)


def _features(mesh: MeshData, front: float, back: float) -> dict[str, Feature]:
    """Die versprochenen Stirnflächen am wirklichen Netz benennen.

    Weitere Flächen und Schraubenaufnahmen erkennt die gemeinsame Auswertung.
    Eine Zeichnung kann beliebig viele Seiten besitzen; deren wechselnde
    Erkennungskennungen sind keine dauerhaften Bausteinversprechen.
    """
    found: dict[str, Feature] = {}
    for name, height, sign in (("front", front, -1.0), ("back", back, 1.0)):
        raw = mesh.raw
        indices = np.flatnonzero(
            (np.abs(raw.face_normals[:, 2] - sign) <= EPS_GEOM)
            & (np.abs(raw.triangles_center[:, 2] - height) <= EPS_GEOM)
        )
        if not len(indices):
            raise _invalid(
                _("Eine Anschlussfläche der Hälfte fehlt. Ändern Sie die Klemmtiefe."), "depth"
            )
        area = float(raw.area_faces[indices].sum())
        centre = np.average(raw.triangles_center[indices], axis=0, weights=raw.area_faces[indices])
        occupied = {int(value) for value in indices}
        found[name] = Feature(
            id=name,
            kind="face",
            provenance="generated",
            face_indices=tuple(sorted(occupied)),
            params={
                "centre": tuple(float(v) for v in centre),
                "area": area,
                "normal": (0.0, 0.0, sign),
                "axis": (0.0, 0.0, 1.0),
                "direction": (1.0, 0.0, 0.0),
            },
        )
    return found


@op_params
class ProfileClampShellParams(BaseParams):
    seat_sketch: str = param(
        title=_("Sitzkontur"),
        kind="sketch",
        required=True,
        default=_circle_text(20.25),
        doc=_("Geschlossener Sitz der Einlage einschließlich ihres Einbauspiels."),
    )
    depth: float = param(
        title=_("Klemmtiefe"),
        default=40.0,
        minimum=16.0,
        maximum=80.0,
        unit="mm",
        doc=_("Länge der Schale entlang des Profils."),
    )
    wall: float = param(
        title=_("Schalenwand"),
        default=4.0,
        minimum=2.0,
        maximum=8.0,
        unit="mm",
        doc=_("Normaler Abstand vom Sitz zur Außenkontur."),
    )
    half: str = param(
        title=_("Hälfte"),
        default="lower",
        choices=("lower", "upper"),
        doc=_("Untere Hälfte mit Schraubenkopf oder obere Hälfte mit Mutter."),
    )
    joint_gap: float = param(
        title=_("Teilungsspalt"),
        default=1.0,
        minimum=0.5,
        maximum=2.0,
        unit="mm",
        placement="advanced",
        doc=_("Abstand der beiden Schalen vor dem Anziehen."),
    )
    split_angle: float = param(
        title=_("Winkel der Trennebene"),
        default=0.0,
        unit=DEGREE_UNIT,
        placement="advanced",
        doc=_("Dreht die Teilung innerhalb der Profilkontur."),
    )
    split_offset: float = param(
        title=_("Versatz der Trennebene"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Verschiebt die Teilung senkrecht zu ihrer Linie."),
    )
    screw_size: str = param(
        title=_("Schraubengröße"),
        default="M4",
        choices=("M4",),
        placement="advanced",
        doc=_("Schraube und Mutter aus der Normteiltabelle."),
    )
    play: float = param(
        title=_("Spiel der Schraubenaufnahme"),
        default=0.0,
        minimum=0.0,
        maximum=1.0,
        unit="mm",
        placement="advanced",
        doc=_("Gesamtzugabe an Kopf und Mutter; null verwendet das Materialprofil."),
    )


def _shell_reason(raw: BaseParams) -> TranslatableText | None:
    p = cast(ProfileClampShellParams, raw)
    screw, nut = standards.screw(p.screw_size), standards.nut(p.screw_size)
    envelope = max(screw.head + p.play, (nut.width + p.play) * 2.0 / math.sqrt(3.0))
    if p.depth < envelope + 2.0 * p.wall - EPS_GEOM:
        return _(
            "Die Schraubenaufnahme lässt zu wenig Rand. "
            "Vergrößern Sie die Klemmtiefe oder verringern Sie die Schalenwand."
        )
    return None


@register_part(
    name="profile_clamp_shell",
    title=_("Profilklemmschale"),
    group="mounting",
    params=ProfileClampShellParams,
    standalone=True,
    features=("front", "back"),
    changes=(_ADDED, _SHELL_SEATED),
    feasible=_shell_reason,
    wall=WallRequirement.from_parameter("wall"),
    doc=_(
        "Eine verschraubte Profilklemmenhälfte mit eindeutig gezeichneter Sitzkontur "
        "und Normteilaufnahmen."
    ),
)
def profile_clamp_shell(raw: BaseParams) -> PartResult:
    p = cast(ProfileClampShellParams, raw)
    return build_shell(p, drawn_section(p.seat_sketch))[0]


def build_shell(
    p: ProfileClampShellParams,
    seat: Any,
    *,
    lift: float = 0.0,
    quality: Quality = "fine",
    cancelled: CancelToken | None = None,
) -> tuple[PartResult, SolverInfo]:
    """Eine Schale aus der einmal gemeinsam vorbereiteten ungedrehten Sitzkontur bauen.

    ``lift`` hebt die Schale entlang der Profilachse an. Allein sitzt sie wie
    jeder Baustein bei null auf ihrer Fläche; das Klemmenpaar hebt sie um die
    Bundhöhe der Einlage, damit beide Hälften in einem Rahmen liegen und der
    Bund vor der Stirnfläche anschlägt. Der Freiraum ist Lage, keine Form —
    deshalb ist er kein Maß der Schale.
    """
    reason = _shell_reason(p)
    if reason is not None:
        raise _invalid(reason, "depth")
    seat = _oriented(seat, p.split_angle)
    _monotone(seat, cancelled)
    outer = offset_section(seat, p.wall)
    shell = outer - seat
    screw, nut = standards.screw(p.screw_size), standards.nut(p.screw_size)
    head_diameter = screw.head + p.play
    nut_diameter = (nut.width + p.play) * 2.0 / math.sqrt(3.0)
    ear_width = max(head_diameter, nut_diameter) + 2.0 * p.wall
    ear_height = max(screw.head_height, nut.height) + p.wall + p.joint_gap / 2.0
    left, _low, right, _high = polygon_of(outer).bounds
    centres = (left - ear_width / 2.0 + p.wall, right + ear_width / 2.0 - p.wall)
    for x in centres:
        shell += _rectangle(
            x - ear_width / 2.0,
            x + ear_width / 2.0,
            p.split_offset - ear_height,
            p.split_offset + ear_height,
        )
    solid = _half(shell, p.half, p.joint_gap, p.split_offset).extrude(p.depth)
    body = _mesh(solid.translate((0, 0, lift)))
    tools = []
    for x in centres:
        centre_z = lift + p.depth / 2.0
        through = shapes.cylinder(screw.clearance, 2 * ear_height + 2 * BOOLEAN_OVERLAP)
        through = shapes.moved(
            shapes.turned(through, 90.0, (1.0, 0.0, 0.0)),
            (x, p.split_offset + ear_height + BOOLEAN_OVERLAP, centre_z),
        )
        tools.append(through)
        if p.half == "lower":
            pocket = shapes.cylinder(head_diameter, screw.head_height + BOOLEAN_OVERLAP)
            pocket = shapes.moved(
                shapes.turned(pocket, -90.0, (1.0, 0.0, 0.0)),
                (x, p.split_offset - ear_height - BOOLEAN_OVERLAP, centre_z),
            )
        else:
            pocket = shapes.hexagon(nut.width + p.play, nut.height + BOOLEAN_OVERLAP)
            pocket = shapes.moved(
                shapes.turned(pocket, 90.0, (1.0, 0.0, 0.0)),
                (x, p.split_offset + ear_height + BOOLEAN_OVERLAP, centre_z),
            )
        tools.append(pocket)
    outcome = boolean("difference", [body, *tools], quality=quality, cancelled=cancelled)
    body = shapes.turned(outcome.mesh, p.split_angle)
    return PartResult(
        mesh=body,
        features=_features(body, lift, lift + p.depth),
        findings=outcome.findings,
    ), outcome.solver


def seat_probes(
    p: ProfileClampShellParams, seat: Any, *, strip: float, lift: float = 0.0
) -> tuple[MeshData, MeshData]:
    """Vollständiger Hohlraum und umlaufender Materialstreifen über die ganze Sitztiefe.

    ``lift`` ist derselbe Versatz wie in :func:`build_shell` — die Proben
    liegen dort, wo die geprüfte Schale liegt.
    """
    section = _oriented(seat, p.split_angle)
    band = offset_section(section, strip) - section
    meshes = []
    for shape in (section, band):
        solid = _half(shape, p.half, p.joint_gap, p.split_offset).extrude(p.depth)
        meshes.append(_mesh(solid.translate((0.0, 0.0, lift)).rotate((0, 0, p.split_angle))))
    return meshes[0], meshes[1]


@op_params
class ProfileClampLinerParams(BaseParams):
    counter_sketch: str = param(
        title=_("Gegenkontur"),
        kind="sketch",
        required=True,
        default=_circle_text(16.0),
        doc=_("Gemessener oder ausdrücklich gezeichneter Querschnitt des zu klemmenden Profils."),
    )
    outer_sketch: str = param(
        title=_("Vorhandene Außenkontur"),
        kind="sketch",
        default="",
        placement="advanced",
        doc=_(
            "Beim Ersatz die feste Außenkontur der Einlage; leer erzeugt eine neue Einlage "
            "mit gleichmäßiger Wand."
        ),
    )
    depth: float = param(
        title=_("Klemmtiefe"),
        default=40.0,
        minimum=16.0,
        maximum=80.0,
        unit="mm",
        doc=_("Länge der zugehörigen Klemmschale."),
    )
    liner_thickness: float = param(
        title=_("Einlagenstärke"),
        default=2.0,
        minimum=1.0,
        maximum=5.0,
        unit="mm",
        doc=_("Normale Wandstärke einer neuen Einlage; beim Ersatz die erforderliche Mindestwand."),
    )
    half: str = param(
        title=_("Hälfte"),
        default="lower",
        choices=("lower", "upper"),
        doc=_("Untere oder obere Hälfte des Profilquerschnitts."),
    )
    flange_width: float = param(
        title=_("Bundbreite"),
        default=1.2,
        minimum=0.8,
        maximum=4.0,
        unit="mm",
        placement="advanced",
        doc=_("Wie weit der vordere Anschlag über den Sitz hinausragt."),
    )
    flange_height: float = param(
        title=_("Bundhöhe"),
        default=1.5,
        minimum=1.0,
        maximum=4.0,
        unit="mm",
        placement="advanced",
        doc=_("Axiale Stärke des vorderen Anschlagbundes."),
    )
    rear_relief: float = param(
        title=_("Freiraum hinten"),
        default=2.0,
        minimum=1.0,
        maximum=4.0,
        unit="mm",
        placement="advanced",
        doc=_("Verkürzt den Einlagenkern gegenüber der Schale, damit er hinten nicht ansteht."),
    )
    split_angle: float = param(
        title=_("Winkel der Trennebene"),
        default=0.0,
        unit=DEGREE_UNIT,
        placement="advanced",
        doc=_("Dreht die Teilung innerhalb der Profilkontur."),
    )
    split_offset: float = param(
        title=_("Versatz der Trennebene"),
        default=0.0,
        unit="mm",
        placement="advanced",
        doc=_("Verschiebt die Teilung senkrecht zu ihrer Linie."),
    )
    play: float = param(
        title=_("Teilungsspiel der Einlagen"),
        default=0.0,
        minimum=0.0,
        maximum=1.0,
        unit="mm",
        placement="advanced",
        doc=_("Gesamtspalt zwischen beiden Einlagen; null verwendet das Materialprofil."),
    )
    grip: float = param(
        title=_("Übermaß am Gegenprofil"),
        default=0.0,
        minimum=0.0,
        maximum=0.5,
        unit="mm",
        placement="advanced",
        doc=_(
            "Gesamte Verengung für den beabsichtigten elastischen Eingriff; "
            "null verwendet das Materialprofil."
        ),
    )


def _liner_reason(raw: BaseParams) -> TranslatableText | None:
    p = cast(ProfileClampLinerParams, raw)
    if p.depth <= p.rear_relief + EPS_GEOM:
        return _(
            "Der hintere Freiraum verbraucht die Einlage. "
            "Vergrößern Sie die Klemmtiefe oder verkleinern Sie den Freiraum."
        )
    return None


@register_part(
    name="profile_clamp_liner",
    title=_("Profilklemmen-Einlage"),
    group="mounting",
    params=ProfileClampLinerParams,
    standalone=True,
    features=("front", "back"),
    changes=(_ADDED,),
    feasible=_liner_reason,
    grip_from_profile=True,
    wall=WallRequirement.from_parameter("liner_thickness"),
    doc=_(
        "Eine separat wechselbare Profil-Einlagenhälfte mit vorderem Anschlagbund "
        "und freiem axialem Einschub."
    ),
)
def profile_clamp_liner(raw: BaseParams) -> PartResult:
    p = cast(ProfileClampLinerParams, raw)
    outside = drawn_section(p.outer_sketch) if p.outer_sketch else None
    return build_liner(p, drawn_section(p.counter_sketch), outside=outside)


def build_liner(
    p: ProfileClampLinerParams,
    counter: Any,
    *,
    outside: Any = None,
    cancelled: CancelToken | None = None,
) -> PartResult:
    """Die gemeinsame Gegenkontur, beim Ersatz die belegte feste Außenkontur übernehmen."""
    reason = _liner_reason(p)
    if reason is not None:
        raise _invalid(reason, "depth")
    counter = _oriented(counter, p.split_angle)
    _monotone(counter, cancelled)
    inside = offset_section(counter, -p.grip / 2.0)
    outside = (
        _oriented(outside, p.split_angle)
        if outside is not None
        else offset_section(inside, p.liner_thickness)
    )
    inner_shape, outer_shape = polygon_of(inside), polygon_of(outside)
    if not outer_shape.contains(inner_shape) or (
        inner_shape.boundary.distance(outer_shape.boundary)
        < p.liner_thickness - CONTOUR_SAG - EPS_GEOM
    ):
        raise _invalid(
            _(
                "Die neue Gegenkontur lässt zu wenig Einlagenwand. "
                "Verkleinern Sie die Gegenkontur oder erzeugen Sie eine neue Klemme."
            )
        )
    core = _half(outside - inside, p.half, p.play, p.split_offset).extrude(p.depth - p.rear_relief)
    core = core.translate((0, 0, p.flange_height))
    flange = _half(offset_section(outside, p.flange_width) - inside, p.half, p.play, p.split_offset)
    body = _mesh((core + flange.extrude(p.flange_height)).rotate((0, 0, p.split_angle)))
    return PartResult(
        mesh=body, features=_features(body, 0.0, p.flange_height + p.depth - p.rear_relief)
    )
