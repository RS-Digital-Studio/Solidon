"""Geprüfte Wannen, Trennwände, Ränder und Steckfüße für Organizer (§24)."""

from __future__ import annotations

import math
from typing import cast

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import ValidationError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.geom.mesh import MeshData
from app.core.knowledge.parts import shapes
from app.core.knowledge.parts.build import face, pin, result, subtract, union
from app.core.knowledge.parts.registry import PartChange, WallRequirement, register_part
from app.core.registry import op_params, param
from app.core.types import BaseParams, PartResult
from app.core.units import EPS_GEOM, MAX_FACET_SAG
from app.i18n import TranslatableText, _

_ADDED = PartChange("1", "2026-09-15", "Parametrische Organizer-Bausteine aus dem Modellkorpus.")


def rounded_prism(width: float, depth: float, height: float, radius: float) -> MeshData:
    """Gerundetes Rechteck in Float64 nativ extrudieren; Außenmaße bleiben exakt."""
    import manifold3d

    if (
        min(width, depth, height) <= EPS_GEOM
        or radius < 0
        or radius * 2 > min(width, depth) + EPS_GEOM
    ):
        raise ValidationError(
            field="radius",
            constraint="organizer_radius",
            detail=_(
                "Der Radius passt nicht in den Körper. Verkleinern Sie ihn "
                "oder vergrößern Sie den Körper."
            ),
        )
    if radius <= EPS_GEOM:
        return shapes.box(width, depth, height)
    step = 2 * math.acos(max(0.0, 1 - MAX_FACET_SAG / radius))
    count = max(4, math.ceil(math.pi / (2 * step)))
    vertices: list[tuple[float, float]] = []
    for quadrant, (cx, cy) in enumerate(
        (
            (width / 2 - radius, depth / 2 - radius),
            (-width / 2 + radius, depth / 2 - radius),
            (-width / 2 + radius, -depth / 2 + radius),
            (width / 2 - radius, -depth / 2 + radius),
        )
    ):
        for angle in np.linspace(quadrant * math.pi / 2, (quadrant + 1) * math.pi / 2, count + 1):
            point = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
            if not vertices or math.dist(point, vertices[-1]) > EPS_GEOM:
                vertices.append(point)
    section = manifold3d.CrossSection([vertices])
    built = section.extrude(height).to_mesh64()
    return MeshData.of(
        trimesh.Trimesh(
            vertices=np.array(built.vert_properties[:, :3], copy=True),
            faces=np.array(built.tri_verts, copy=True),
            process=False,
        )
    )


def _moved(mesh: MeshData, z: float) -> MeshData:
    """Eine neu gebaute Form versetzen, ohne ihr Eingangsnetz zu verändern."""
    raw = mesh.raw.copy()
    raw.apply_translation((0, 0, z))
    return MeshData.of(raw)


def _horizontal_area(mesh: MeshData, z: float, *, up: bool = True) -> float:
    """Die reale ebene Fläche zählen, einschließlich Rundungen und ausgesparter Mitte."""
    normal = np.asarray((0, 0, 1 if up else -1))
    raw = mesh.raw
    mask = (np.linalg.norm(raw.face_normals - normal, axis=1) <= EPS_GEOM) & (
        np.abs(raw.triangles_center[:, 2] - z) <= EPS_GEOM
    )
    return float(raw.area_faces[mask].sum())


@op_params
class TrayParams(BaseParams):
    width: float = param(
        title=_("Breite"),
        default=120.0,
        minimum=20.0,
        maximum=300.0,
        unit="mm",
        doc=_("Außenbreite der Wanne."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=80.0,
        minimum=20.0,
        maximum=300.0,
        unit="mm",
        doc=_("Außentiefe der Wanne."),
    )
    height: float = param(
        title=_("Höhe"),
        default=40.0,
        minimum=6.0,
        maximum=200.0,
        unit="mm",
        doc=_("Gesamthöhe ab der Unterseite."),
    )
    wall: float = param(
        title=_("Wandstärke"),
        default=3.0,
        minimum=1.0,
        maximum=12.0,
        unit="mm",
        placement="advanced",
        doc=_("Dicke der umlaufenden Außenwand."),
    )
    floor: float = param(
        title=_("Bodenstärke"),
        default=3.0,
        minimum=1.0,
        maximum=10.0,
        unit="mm",
        placement="advanced",
        doc=_("Dicke des geschlossenen Bodens."),
    )
    radius: float = param(
        title=_("Außenradius"),
        default=8.0,
        minimum=0.0,
        maximum=25.0,
        unit="mm",
        placement="advanced",
        doc=_("Rundet die senkrechten Außenecken. Der Innenradius erhält die Wandstärke."),
    )


def _tray_reason(raw: BaseParams) -> TranslatableText | None:
    params = cast(TrayParams, raw)
    if min(params.width, params.depth) <= 2 * params.wall + EPS_GEOM:
        return _(
            "Die Wandstärke lässt keinen Innenraum. Vergrößern Sie die Wanne "
            "oder verringern Sie die Wandstärke."
        )
    if params.floor >= params.height - EPS_GEOM:
        return _("Die Bodenstärke erreicht die Gesamthöhe. Verringern Sie die Bodenstärke.")
    if 2 * params.radius > min(params.width, params.depth) + EPS_GEOM:
        return _("Der Außenradius ist zu groß. Verkleinern Sie den Radius.")
    return None


def _require(reason: TranslatableText | None) -> None:
    if reason is not None:
        raise ValidationError(field="dimensions", constraint="organizer_part", detail=reason)


@register_part(
    name="organizer_tray",
    title=_("Organizer-Wanne"),
    group="structure",
    params=TrayParams,
    standalone=True,
    features=("base", "floor", "rim"),
    changes=[_ADDED],
    feasible=_tray_reason,
    doc=_("Offene Wanne mit unabhängigem Boden, gleichmäßiger Außenwand und gerundeten Ecken."),
)
def organizer_tray(raw: BaseParams) -> PartResult:
    params = cast(TrayParams, raw)
    _require(_tray_reason(params))
    base = rounded_prism(params.width, params.depth, params.height, params.radius)
    cavity = rounded_prism(
        params.width - 2 * params.wall,
        params.depth - 2 * params.wall,
        params.height - params.floor + BOOLEAN_OVERLAP,
        max(0, params.radius - params.wall),
    )
    body = subtract(base, _moved(cavity, params.floor))
    area = _horizontal_area(body, params.floor)
    return result(
        body,
        face("base", _horizontal_area(body, 0, up=False), (0, 0, 0), (0, 0, -1)),
        face("floor", area, (0, 0, params.floor)),
        face(
            "rim",
            _horizontal_area(body, params.height),
            (0, (params.depth - params.wall) / 2, params.height),
        ),
    )


@op_params
class DividerParams(BaseParams):
    length: float = param(
        title=_("Länge"),
        default=80.0,
        minimum=5.0,
        maximum=300.0,
        unit="mm",
        doc=_("Länge der geraden Trennwand."),
    )
    height: float = param(
        title=_("Höhe"),
        default=30.0,
        minimum=1.0,
        maximum=200.0,
        unit="mm",
        doc=_("Höhe der Trennwand über ihrer Auflage."),
    )
    thickness: float = param(
        title=_("Dicke"),
        default=3.0,
        minimum=1.0,
        maximum=12.0,
        unit="mm",
        doc=_("Dicke zwischen den beiden Wandseiten."),
    )


@register_part(
    name="organizer_divider",
    title=_("Organizer-Trennwand"),
    group="structure",
    params=DividerParams,
    standalone=True,
    features=("base", "top", "front", "back"),
    changes=[_ADDED],
    wall=WallRequirement.from_parameter("thickness"),
    doc=_("Gerade Trennwand mit benannten Seiten und eigener Höhe; an den Boden anfügen."),
)
def organizer_divider(raw: BaseParams) -> PartResult:
    p = cast(DividerParams, raw)
    return result(
        shapes.box(p.length, p.thickness, p.height),
        face("base", p.length * p.thickness, (0, 0, 0), (0, 0, -1)),
        face("top", p.length * p.thickness, (0, 0, p.height)),
        face("front", p.length * p.height, (0, -p.thickness / 2, p.height / 2), (0, -1, 0)),
        face("back", p.length * p.height, (0, p.thickness / 2, p.height / 2), (0, 1, 0)),
    )


@op_params
class RimParams(BaseParams):
    width: float = param(
        title=_("Breite"),
        default=120.0,
        minimum=20.0,
        maximum=300.0,
        unit="mm",
        doc=_("Außenbreite des umlaufenden Randes."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=80.0,
        minimum=20.0,
        maximum=300.0,
        unit="mm",
        doc=_("Außentiefe des umlaufenden Randes."),
    )
    height: float = param(
        title=_("Höhe"),
        default=3.0,
        minimum=1.0,
        maximum=20.0,
        unit="mm",
        doc=_("Höhe des zusätzlichen Randes."),
    )
    thickness: float = param(
        title=_("Randbreite"),
        default=3.0,
        minimum=1.0,
        maximum=12.0,
        unit="mm",
        placement="advanced",
        doc=_("Breite des Randes von außen nach innen."),
    )
    radius: float = param(
        title=_("Außenradius"),
        default=8.0,
        minimum=0.0,
        maximum=25.0,
        unit="mm",
        placement="advanced",
        doc=_("Radius der äußeren senkrechten Ecken."),
    )


def _rim_reason(raw: BaseParams) -> TranslatableText | None:
    p = cast(RimParams, raw)
    if min(p.width, p.depth) <= 2 * p.thickness + EPS_GEOM:
        return _(
            "Die Randbreite schließt die Öffnung. Verringern Sie sie oder vergrößern Sie den Rand."
        )
    if 2 * p.radius > min(p.width, p.depth) + EPS_GEOM:
        return _("Der Außenradius ist zu groß. Verkleinern Sie den Radius.")
    return None


@register_part(
    name="organizer_rim",
    title=_("Organizer-Rand"),
    group="structure",
    params=RimParams,
    standalone=True,
    features=("rim",),
    changes=[_ADDED],
    feasible=_rim_reason,
    wall=WallRequirement.from_parameter("thickness"),
    doc=_("Umlaufender offener Rand; an die Oberkante einer Wanne anfügen."),
)
def organizer_rim(raw: BaseParams) -> PartResult:
    p = cast(RimParams, raw)
    _require(_rim_reason(p))
    base = rounded_prism(p.width, p.depth, p.height, p.radius)
    cut = rounded_prism(
        p.width - 2 * p.thickness,
        p.depth - 2 * p.thickness,
        p.height + 2 * BOOLEAN_OVERLAP,
        max(0, p.radius - p.thickness),
    )
    mesh = subtract(base, _moved(cut, -BOOLEAN_OVERLAP))
    # Der Montageursprung liegt auf Material. In der Mitte der Öffnung
    # bliebe ein an eine kleine Fläche gesetzter Rand ein schwebender Körper.
    anchored = mesh.raw.copy()
    anchored.apply_translation((0, -(p.depth - p.thickness) / 2, 0))
    mesh = MeshData.of(anchored)
    return result(
        mesh,
        face(
            "rim",
            _horizontal_area(mesh, p.height),
            (0, 0, p.height),
        ),
    )


@op_params
class FootParams(BaseParams):
    diameter: float = param(
        title=_("Flanschdurchmesser"),
        default=18.0,
        minimum=6.0,
        maximum=40.0,
        unit="mm",
        doc=_("Außendurchmesser der Standfläche; größer als der Zapfen."),
    )
    height: float = param(
        title=_("Fußhöhe"),
        default=11.0,
        minimum=1.0,
        maximum=30.0,
        unit="mm",
        doc=_("Abstand zwischen Standfläche und Anschlag des Zapfens."),
    )
    pin_diameter: float = param(
        title=_("Zapfendurchmesser"),
        default=13.0,
        minimum=2.0,
        maximum=30.0,
        unit="mm",
        doc=_("Nennmaß des Steckzapfens. Das Spiel gehört in die zugehörige Aufnahme."),
    )
    pin_length: float = param(
        title=_("Zapfenlänge"),
        default=8.0,
        minimum=1.0,
        maximum=20.0,
        unit="mm",
        doc=_("Länge des Zapfens oberhalb des Anschlags."),
    )


def _foot_reason(raw: BaseParams) -> TranslatableText | None:
    p = cast(FootParams, raw)
    if p.pin_diameter >= p.diameter - EPS_GEOM:
        return _(
            "Der Flansch muss breiter als der Zapfen sein. Vergrößern Sie "
            "den Flansch oder verkleinern Sie den Zapfen."
        )
    return None


@register_part(
    name="organizer_foot",
    title=_("Organizer-Steckfuß"),
    group="structure",
    params=FootParams,
    standalone=True,
    at_face=False,
    features=("base", "seat", "pin"),
    changes=[_ADDED],
    feasible=_foot_reason,
    doc=_(
        "Separater Steckfuß mit Flansch, Anschlag und benanntem Zapfen. Die "
        "Aufnahme erhält das Materialspiel."
    ),
)
def organizer_foot(raw: BaseParams) -> PartResult:
    p = cast(FootParams, raw)
    _require(_foot_reason(p))
    # Der vorhandene Standfuß fasst bei Fase=0 automatisch. Der Steckfuß
    # verspricht dagegen einen zylindrischen Flansch wie die Vorlagen.
    base = shapes.cylinder(p.diameter, p.height)
    peg = _moved(shapes.cylinder(p.pin_diameter, p.pin_length), p.height)
    mesh = union(base, peg)
    return result(
        mesh,
        face("base", _horizontal_area(mesh, 0, up=False), (0, 0, 0), (0, 0, -1)),
        face(
            "seat",
            _horizontal_area(mesh, p.height),
            ((p.diameter + p.pin_diameter) / 4, 0, p.height),
        ),
        pin("pin", p.pin_diameter, (0, 0, p.height + p.pin_length / 2), length=p.pin_length),
    )
