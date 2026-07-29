"""A lid for an opening (Bauplan §25, §14).

The most common second half of a part. Somebody has a box — modelled here,
downloaded, or scanned — and needs something that closes it. Doing that by hand
means measuring the cavity, drawing it again a fraction smaller, and finding out
at the printer by how much the fraction was wrong.

The cavity is not measured, it is taken: a cut through the wall at the height of
the opening gives the outer contour and the hole inside it, and the collar is
that hole shrunk by the clearance from the material profile (§12). The number
that decides whether the lid goes on is therefore the same one the fit check
uses, and calibrating the material (§28.3) reaches a lid that was built before
the calibration.
"""

from __future__ import annotations

from typing import Any, cast

import trimesh

from app.core.errors import ValidationError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.profiles import for_object
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.slice.analysis import cross_section
from app.core.types import BaseParams, Finding, OpContext, OpResult, SceneObject
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: How far below the rim the cut is taken. Exactly at the top edge a cut meets
#: the end of the wall and gives a line instead of a ring; a tenth of a
#: millimetre down it is safely in the material.
BELOW_RIM = 0.1

#: Below this a cavity is a bore, not an opening — 100 mm² is a hole of eleven
#: millimetres, and nobody puts a lid collar into a screw hole. Above it every
#: ring counts, including a small compartment next to a large one: a slot of
#: twelve millimetres square takes a collar perfectly well, and measuring
#: cavities against each other rather than against a size would throw it away.
MIN_CAVITY = 100.0

#: How far the collar is pulled in beyond the clearance, so the lid does not
#: sit on the collar instead of on the rim.
COLLAR_RELIEF = 0.2


def opening(mesh: MeshData, z: float) -> tuple[Any, list[Any]]:
    """The wall ring at this height, as the filled outline and what is open in it.

    The section itself is a ring — wall material with the cavity as its hole.
    The lid is meant to *cover* that hole, so what comes back as the outline is
    the ring filled in; taking the section as it stands would give a lid with
    the opening cut out of it.

    Raises when there is nothing to close: a body that is solid here has no
    opening, and a lid over it would be a plate glued onto a block.
    """
    from shapely.ops import unary_union

    section = cross_section(mesh, z)
    if section is None or section.is_empty:
        raise ValidationError(
            field="z",
            detail=_("Auf dieser Höhe schneidet die Ebene den Körper nicht."),
            value=round(z, 2),
            constraint="no_section",
        )

    parts = list(getattr(section, "geoms", [section]))
    cavities = [ring for part in parts for ring in _holes_of(part) if ring.area >= MIN_CAVITY]
    if not cavities:
        raise ValidationError(
            field="z",
            detail=_("Der Körper ist auf dieser Höhe massiv — es gibt nichts zu verschließen."),
            value=round(z, 2),
            constraint="no_cavity",
        )
    return unary_union([_filled(part) for part in parts]), cavities


def _filled(part: Any) -> Any:
    from shapely.geometry import Polygon as ShapelyPolygon

    return ShapelyPolygon(part.exterior)


def _holes_of(part: Any) -> list[Any]:
    from shapely.geometry import Polygon as ShapelyPolygon

    return [ShapelyPolygon(ring) for ring in getattr(part, "interiors", [])]


def build(
    outline: Any,
    cavities: list[Any],
    *,
    thickness: float,
    collar: float,
    clearance: float,
    z: float,
) -> MeshData:
    """Plate plus collar, standing on the rim of the opening.

    The plate covers the whole outline, so it looks like the box it belongs to.
    The collar reaches down into every cavity — a divided box gets one per
    compartment, because that is what keeps the lid from turning.
    """
    plates = [
        trimesh.creation.extrude_polygon(piece, height=thickness)
        for piece in getattr(outline, "geoms", [outline])
    ]
    for plate in plates:
        plate.apply_translation((0.0, 0.0, z))

    bodies = list(plates)
    for cavity in cavities if collar > EPS_GEOM else []:
        shrunk = cavity.buffer(-(clearance + COLLAR_RELIEF), join_style=2)
        if shrunk.is_empty or shrunk.area <= EPS_GEOM:
            continue
        for piece in getattr(shrunk, "geoms", [shrunk]):
            body = trimesh.creation.extrude_polygon(piece, height=collar)
            body.apply_translation((0.0, 0.0, z - collar))
            bodies.append(body)

    if len(bodies) == 1:
        return MeshData.of(bodies[0])
    joined = MeshData.of(bodies[0])
    for entry in bodies[1:]:
        joined = boolean("union", [joined, MeshData.of(entry)]).mesh
    return joined


@op_params
class LidParams(BaseParams):
    thickness: float = param(
        title=_("Deckelstärke"), default=2.4, unit="mm", minimum=0.4, maximum=50.0
    )
    collar: float = param(
        title=_("Kragentiefe"),
        default=4.0,
        unit="mm",
        minimum=0.0,
        maximum=100.0,
        doc=_("Wie weit der Kragen in die Öffnung reicht. Null heißt: flacher Deckel ohne Kragen."),
    )
    z: float = param(
        title=_("Höhe der Öffnung"),
        default=0.0,
        unit="mm",
        doc=_("Null nimmt die Oberkante des Körpers."),
    )
    clearance: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=2.0,
        placement="advanced",
        doc=_("Null heißt: der Wert aus dem Materialprofil."),
    )
    name: str = param(title=_("Name"), default="", placement="advanced")


@register_op(
    name="create_lid",
    title=_("Deckel erzeugen"),
    category="parts",
    params=LidParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    doc=_(
        "Erzeugt zu einer Öffnung einen passenden Deckel mit Kragen. Der Hohlraum "
        "wird aus dem Körper geschnitten, nicht nachgemessen — das Spiel kommt aus "
        "dem Materialprofil."
    ),
)
def create_lid(ctx: OpContext) -> OpResult:
    """§25: the second half of every box.

    The lid stays where the opening is instead of jumping onto the bed. Whether
    it closes the box is the question somebody has at this moment, and that can
    only be seen in place; arranging for the print is its own operation and
    knows about every other body too.
    """
    params = cast(LidParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    top = float(mesh.bounds.maximum[2])
    z = params.z or top
    outline, cavities = opening(mesh, z - BELOW_RIM)

    clearance = params.clearance
    if not clearance:
        if ctx.profile is None:
            raise ValidationError(
                field="clearance",
                detail=_("Ohne Profil muss das Spiel angegeben werden."),
                constraint="no_profile",
            )
        clearance = for_object(ctx.profile, source).material.clearance

    body = build(
        outline,
        cavities,
        thickness=params.thickness,
        collar=params.collar,
        clearance=clearance,
        z=z,
    )

    _log.info("lid over %d cavities at z=%.2f, clearance %.2f", len(cavities), z, clearance)
    return OpResult(
        outputs=[
            SceneObject(
                id="",
                name=params.name or f"{source.name} {_('Deckel').translate()}",
                mesh=body,
                material=source.material,
            )
        ],
        findings=[
            Finding(
                code="parts.lid",
                severity="info",
                message=_("Deckel erzeugt — das Spiel kommt aus dem Materialprofil."),
                values={
                    "cavities": len(cavities),
                    "clearance_mm": round(clearance, 3),
                    "z_mm": round(z, 2),
                },
            )
        ],
    )
