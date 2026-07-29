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

import dataclasses
from typing import Any, cast

import trimesh

from app.core.errors import ValidationError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.prepare import BOOLEAN_OVERLAP
from app.core.knowledge.parts.shapes import RIDGE_SHARE, thread_body
from app.core.knowledge.profiles import for_object
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.scene.placement import faces_up
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


def plane_of(source: SceneObject, name: str, stated: float) -> float:
    """The height the opening is at: from the chosen face, or from the number.

    A face wins over the number because it is the more specific of the two — the
    number defaults to the top of the body, which is a guess, while a face is
    what somebody clicked. Both are in the file, so the answer does not depend on
    what happens to be selected when the project is opened again (§11).

    A face that does not look upward is refused rather than read as a height.
    Any face has a centre with a Z in it, and the ceiling of a cavity has one
    that lies inside the part — taken as an opening height it put the lid into
    the middle of the box, at 26,9 of 30 millimetres, and nothing further down
    noticed because a cut below that plane does meet the wall.
    """
    if not name:
        return stated or float(source.mesh.bounds.maximum[2])

    feature = source.features.get(name)
    if feature is None:
        raise ValidationError(
            field="at_feature",
            detail=_("Dieses Merkmal gibt es an diesem Objekt nicht."),
            value=name,
            constraint="unknown_feature",
            values={"known": ", ".join(sorted(source.features))},
        )
    if feature.kind != "face":
        raise ValidationError(
            field="at_feature",
            detail=_("Ein Deckel braucht eine Fläche, kein anderes Merkmal."),
            value=name,
            constraint="not_a_face",
            values={"kind": feature.kind},
        )
    if not faces_up(feature):
        raise ValidationError(
            field="at_feature",
            detail=_("Diese Fläche zeigt nicht nach oben — eine Öffnung für einen Deckel schon."),
            value=name,
            constraint="not_upright",
        )
    centre = feature.params.get("centre") or (0.0, 0.0, 0.0)
    return float(centre[2])


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
    at_feature: str = param(
        title=_("An Fläche"),
        kind="feature",
        default="",
        doc=_(
            "Name einer erkannten Fläche, etwa face_1 — dann liegt die Öffnung in "
            "deren Ebene. Wird beim Anklicken im Fenster eingetragen."
        ),
    )
    z: float = param(
        title=_("Höhe der Öffnung"),
        default=0.0,
        unit="mm",
        doc=_("Null nimmt die Oberkante des Körpers. Eine gewählte Fläche geht vor."),
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

    z = plane_of(source, params.at_feature, params.z)
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


# --- the turning lid ------------------------------------------------------------

#: Pitch of a printed coarse thread. Coarse on purpose: a jar lid is turned by
#: hand and half a turn should close it, while a fine ridge is one the nozzle
#: rounds away until nothing grips.
DEFAULT_PITCH = 3.0

#: How much taller the lid's threaded skirt is than the neck, so the lid comes
#: to rest on the rim and not on the end of the thread.
SKIRT_RELIEF = 0.6

#: Sections around a turned body. Coarser than this and a "round" neck is a
#: polygon the lid catches on.
NECK_SECTIONS = 96


def neck_diameters(outline: Any, cavities: list[Any]) -> tuple[float, float]:
    """Outer and bore diameter of a neck that fits this opening.

    Both come from the narrower side, not from a fitted circle: on a round
    opening that *is* the diameter, and on a rectangular one it is the largest
    round neck the wall can still carry. A circle through the corners of a
    square would stand out over its sides.
    """
    left, bottom, right, top = outline.bounds
    widest = max(cavities, key=lambda ring: ring.area)
    inner_left, inner_bottom, inner_right, inner_top = widest.bounds
    return (
        float(min(right - left, top - bottom)),
        float(min(inner_right - inner_left, inner_top - inner_bottom)),
    )


def _pipe(outer: float, inner: float, height: float, z: float) -> MeshData:
    """A ring of material standing on ``z``, open all the way through."""
    shell = trimesh.creation.cylinder(radius=outer / 2.0, height=height, sections=NECK_SECTIONS)
    shell.apply_translation((0.0, 0.0, z + height / 2.0))
    if inner <= EPS_GEOM:
        return MeshData.of(shell)
    bore = trimesh.creation.cylinder(
        radius=inner / 2.0, height=height + 2.0 * BOOLEAN_OVERLAP, sections=NECK_SECTIONS
    )
    bore.apply_translation((0.0, 0.0, z + height / 2.0))
    return boolean("difference", [MeshData.of(shell), MeshData.of(bore)], quality="fine").mesh


def _lifted(body: MeshData, z: float) -> MeshData:
    raised = body.raw.copy()
    raised.apply_translation((0.0, 0.0, z))
    return body.replacing(raised)


@op_params
class ScrewLidParams(BaseParams):
    height: float = param(
        title=_("Gewindehöhe"),
        default=8.0,
        unit="mm",
        minimum=2.0,
        maximum=100.0,
        doc=_("Wie hoch der Gewindehals wird. Zwei Umdrehungen halten, drei sitzen fest."),
    )
    pitch: float = param(
        title=_("Steigung"),
        default=DEFAULT_PITCH,
        unit="mm",
        minimum=1.0,
        maximum=10.0,
        doc=_("Grob, damit der Drucker sie auflöst und eine halbe Drehung schließt."),
    )
    thickness: float = param(
        title=_("Deckelstärke"), default=2.4, unit="mm", minimum=0.8, maximum=50.0
    )
    wall: float = param(
        title=_("Wandstärke des Deckels"), default=2.4, unit="mm", minimum=0.8, maximum=20.0
    )
    neck: float = param(
        title=_("Halsdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=400.0,
        placement="advanced",
        doc=_("Null nimmt die schmalere Seite der Öffnung."),
    )
    at_feature: str = param(
        title=_("An Fläche"),
        kind="feature",
        default="",
        doc=_(
            "Name einer erkannten Fläche, etwa face_1 — dann liegt die Öffnung in "
            "deren Ebene. Wird beim Anklicken im Fenster eingetragen."
        ),
    )
    z: float = param(
        title=_("Höhe der Öffnung"),
        default=0.0,
        unit="mm",
        doc=_("Null nimmt die Oberkante des Körpers. Eine gewählte Fläche geht vor."),
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


@register_op(
    name="screw_lid",
    title=_("Drehdeckel erzeugen"),
    category="parts",
    params=ScrewLidParams,
    consumes=1,
    produces=2,
    applies_to=["face"],
    doc=_(
        "Setzt einen Gewindehals auf die Öffnung und erzeugt den passenden "
        "Schraubdeckel. Beide Gewinde kommen aus derselben Steigung, das Spiel "
        "aus dem Materialprofil."
    ),
)
def screw_lid(ctx: OpContext) -> OpResult:
    """§25: der Zwilling des eingeschobenen Deckels.

    Two pairs in the model corpus are exactly this and nothing else:
    ``gewuerzbehaelter_body`` beside ``deckel_dreh``, and ``kartuschen_kaefig``
    beside ``kartuschen_deckel``. The part library has a thread, but only in the
    metric screw sizes M2 to M8 — a jar neck of forty millimetres with a coarse
    pitch was out of its reach entirely.

    Both halves come out of one operation because they are one decision. A neck
    cut to one pitch and a lid to another is not two mistakes; it is the one
    mistake that is easiest to make when the halves are made apart.
    """
    params = cast(ScrewLidParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    z = plane_of(source, params.at_feature, params.z)
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

    major, bore = neck_diameters(outline, cavities)
    if params.neck:
        major = params.neck

    ridge = params.pitch * RIDGE_SHARE
    core = major - 2.0 * ridge

    if core - bore <= EPS_GEOM:
        raise ValidationError(
            field="pitch",
            detail=_("Die Wand ist für diese Steigung zu dünn — das Gewinde hätte keinen Kern."),
            constraint="too_coarse",
            values={"neck_mm": round(major, 2), "bore_mm": round(bore, 2)},
        )

    # The core carries the ridge, so it is two ridge depths narrower than the
    # thread is wide: unioned onto a neck of the full diameter the ridge would
    # sit inside the material and change nothing at all.
    neck = _pipe(core, bore, params.height, z)
    turns = _lifted(thread_body(major, params.pitch, params.height), z)
    threaded = boolean("union", [mesh, neck], quality=ctx.quality).mesh
    threaded = boolean("union", [threaded, turns], quality=ctx.quality).mesh

    lid = _screw_cap(major, params, clearance)

    _log.info("screw lid: neck %.2f, pitch %.2f, clearance %.2f", major, params.pitch, clearance)
    return OpResult(
        outputs=[
            dataclasses.replace(source, mesh=threaded, features={}),
            SceneObject(
                id="",
                name=f"{source.name} {_('Drehdeckel').translate()}",
                mesh=lid,
                material=source.material,
            ),
        ],
        findings=[
            Finding(
                code="parts.screw_lid",
                severity="info",
                message=_("Gewindehals und Deckel erzeugt — beide mit derselben Steigung."),
                values={
                    "neck_mm": round(major, 2),
                    "pitch_mm": round(params.pitch, 2),
                    "clearance_mm": round(clearance, 3),
                },
            )
        ],
    )


def _screw_cap(major: float, params: ScrewLidParams, clearance: float) -> MeshData:
    """The lid: a cap whose inside carries the counterpart of the neck thread.

    Cut from the *core* diameter plus the clearance, not from the major one.
    That is the whole difference between a lid and a sleeve: bored to the major
    diameter nothing is left standing for the ridge of the neck to hold, and the
    lid slides straight off. The same rule as the nut of the part library, and
    for the same reason.

    The open end stands on Z = 0, so it prints without a support anywhere.
    """
    skirt = params.height + SKIRT_RELIEF
    inside = major - 2.0 * params.pitch * RIDGE_SHARE + clearance
    outer = major + 2.0 * clearance + 2.0 * params.wall

    body = trimesh.creation.cylinder(
        radius=outer / 2.0, height=skirt + params.thickness, sections=NECK_SECTIONS
    )
    body.apply_translation((0.0, 0.0, (skirt + params.thickness) / 2.0))

    # The two shapes a threaded hole is cut with: the bore at the core, and the
    # groove reaching out of it to the major diameter.
    hollow = trimesh.creation.cylinder(
        radius=inside / 2.0, height=skirt + BOOLEAN_OVERLAP, sections=NECK_SECTIONS
    )
    hollow.apply_translation((0.0, 0.0, (skirt + BOOLEAN_OVERLAP) / 2.0 - BOOLEAN_OVERLAP))
    groove = thread_body(inside, params.pitch, skirt, internal=True)

    cutter = boolean("union", [MeshData.of(hollow), groove], quality="fine").mesh
    return boolean("difference", [MeshData.of(body), cutter], quality="fine").mesh
