"""Text and logos on a face (Bauplan §25, category "Beschriftung").

A part with its size on it, a lid with what belongs in the box, a bracket with
the date it was printed: the most common reason people leave a modelling
program and open another one. It does not need another one.

The letters come from the font as outlines, not as a picture that gets traced —
so the edges stay clean at any size, and a raised letter has a flat top rather
than a staircase. Everything after that is the same union or difference every
other part uses (§24.1).

The other half is a logo, and that arrives as SVG through the same door: an
outline is an outline, whether a font drew it or Inkscape did.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Literal, cast

import numpy as np
import trimesh

from app.core.errors import ValidationError
from app.core.geom.attributes import with_slot
from app.core.geom.boolean import BooleanKind, boolean
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.transform import apply, rotation, translation
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, MaterialSlot, OpContext, OpResult, SceneObject, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

Placement = Literal["raised", "engraved"]

#: The fonts that are always there. matplotlib ships DejaVu with itself, so a
#: label looks the same on every machine — a system font that exists on one
#: computer and not on the next is a project that opens differently.
FONTS: tuple[str, ...] = ("DejaVu Sans", "DejaVu Serif", "DejaVu Sans Mono")

#: How much a raised label reaches into the body, and an engraved one past its
#: floor. Without this the two faces are coincident and the boolean fails (§39).
OVERLAP = 0.05

#: Below this the letters are thinner than a nozzle and print as a smear.
MIN_SIZE = 3.0

#: How many filaments a slot number may name (§20, same as the colour ops).
MAX_SLOTS = 8


def outlines(text: str, size: float, font: str = FONTS[0]) -> list[Any]:
    """The letters as polygons, in millimetres, sitting on the origin."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.ops import unary_union

    path = TextPath((0.0, 0.0), text, size=size, prop=FontProperties(family=font))
    rings = [np.asarray(entry, dtype=float) for entry in path.to_polygons()]
    rings = [entry for entry in rings if len(entry) >= 4]
    if not rings:
        return []

    # A letter like "o" comes as two rings, and which is the hole follows from
    # containment, not from the order they were drawn in.
    shapes = [ShapelyPolygon(entry).buffer(0) for entry in rings]
    solid = None
    for shape in sorted(shapes, key=lambda entry: -entry.area):
        solid = shape if solid is None else solid.symmetric_difference(shape)
    merged = unary_union([solid]) if solid is not None else None
    if merged is None or merged.is_empty:
        return []
    return [entry for entry in getattr(merged, "geoms", [merged]) if entry.area > EPS_GEOM]


def label_solid(shapes: list[Any], depth: float) -> MeshData | None:
    """One body out of the outlines, standing on Z = 0."""
    parts = [
        trimesh.creation.extrude_polygon(shape, height=depth)
        for shape in shapes
        if shape.area > EPS_GEOM
    ]
    if not parts:
        return None
    return MeshData.of(trimesh.util.concatenate(parts))


def place(body: MeshData, position: Vec3, normal: Vec3, angle: float = 0.0) -> MeshData:
    """Lay a label that stands on +Z onto a face with the given normal."""
    placed = body
    if angle:
        placed = apply(placed, rotation("z", angle))

    direction = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(direction))
    if length > EPS_GEOM:
        matrix = trimesh.geometry.align_vectors([0.0, 0.0, 1.0], direction / length)
        turned = placed.raw.copy()
        turned.apply_transform(matrix)
        placed = placed.replacing(turned)
    return apply(placed, translation(position))


@op_params
class LabelParams(BaseParams):
    text: str = param(
        title=_("Text"),
        default="",
        doc=_("Was daraufstehen soll. Leer heißt: nichts zu tun."),
    )
    size: float = param(
        title=_("Schriftgröße"), default=8.0, unit="mm", minimum=MIN_SIZE, maximum=200.0
    )
    depth: float = param(
        title=_("Tiefe"),
        default=0.6,
        unit="mm",
        minimum=0.1,
        maximum=10.0,
        doc=_("Wie weit erhaben oder wie tief eingelassen."),
    )
    mode: str = param(
        title=_("Art"),
        default="raised",
        choices=("raised", "engraved"),
        doc=_("Erhaben druckt sich besser, vertieft bleibt beim Schleifen erhalten."),
    )
    slot: int = param(
        title=_("Materialslot"),
        default=0,
        minimum=0,
        maximum=MAX_SLOTS - 1,
        doc=_(
            "Legt die Schrift in einen eigenen Slot — der 3MF-Export macht daraus "
            "den Farbwechsel, ohne zweite Datei."
        ),
    )
    font: str = param(title=_("Schrift"), default=FONTS[0], choices=FONTS, placement="advanced")
    x: float = param(title=_("Position X"), default=0.0, unit="mm")
    y: float = param(title=_("Position Y"), default=0.0, unit="mm")
    z: float = param(title=_("Position Z"), default=0.0, unit="mm")
    nx: float = param(title=_("Normale X"), default=0.0, placement="advanced")
    ny: float = param(title=_("Normale Y"), default=0.0, placement="advanced")
    nz: float = param(title=_("Normale Z"), default=1.0, placement="advanced")
    angle: float = param(
        title=_("Drehung"),
        default=0.0,
        unit="grad",
        minimum=-360.0,
        maximum=360.0,
        placement="advanced",
    )


@register_op(
    name="label_text",
    title=_("Text aufbringen"),
    category="label",
    params=LabelParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    doc=_(
        "Setzt Text erhaben oder vertieft auf eine Fläche. Die Schrift wird als "
        "Umriss verarbeitet, nicht als Bild — die Kanten bleiben in jeder Größe sauber."
    ),
)
def label_text(ctx: OpContext) -> OpResult:
    params = cast(LabelParams, ctx.params)
    source = ctx.inputs[0]
    if not params.text.strip():
        raise ValidationError(
            field="text",
            detail=_("Ohne Text gibt es nichts aufzubringen."),
            constraint="empty",
        )

    shapes = outlines(params.text, params.size, params.font)
    if not shapes:
        raise ValidationError(
            field="text",
            detail=_("Aus diesem Text ließ sich keine Form bilden."),
            value=params.text,
            constraint="no_outline",
        )

    mode = cast(Placement, params.mode)
    depth = params.depth + OVERLAP
    body = label_solid(shapes, depth)
    if body is None:
        raise ValidationError(
            field="text",
            detail=_("Aus diesem Text ließ sich keine Form bilden."),
            constraint="no_outline",
        )

    # Centred on the point that was clicked, not starting there: a label grows
    # around its place, which is what anybody putting one on expects.
    #
    # Which way it reaches depends on the mode. Raised: the depth stands proud
    # of the face and only the overlap reaches in. Engraved: the depth reaches
    # in and only the overlap stands proud — otherwise the cut takes off the
    # overlap and leaves the letters as a scratch.
    middle = body.bounds.centre
    lift = -OVERLAP if mode == "raised" else -params.depth
    body = apply(body, translation((-middle[0], -middle[1], lift)))

    placed = place(
        body, (params.x, params.y, params.z), (params.nx, params.ny, params.nz), params.angle
    )
    body_mesh = as_mesh_data(source.mesh)
    slots = list(source.material_slots)
    if params.slot and mode == "raised":
        # §20: the letters carry a slot of their own into the union, and the
        # attribute transfer of the boolean brings it out the other side. That
        # is what turns a two-colour label into one file instead of two.
        placed = with_slot(placed, params.slot)
        if not body_mesh.slots:
            body_mesh = with_slot(body_mesh, 0)
        slots = _with_slot_named(slots, params.slot)

    kind: BooleanKind = "union" if mode == "raised" else "difference"
    outcome = boolean(kind, [body_mesh, placed], quality=ctx.quality, cut_slot=0)

    _log.info("labelled with %r, %s", params.text, mode)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=outcome.mesh, features={}, material_slots=slots)],
        solver=outcome.solver,
        findings=outcome.findings,
    )


@op_params
class LabelBodyParams(BaseParams):
    text: str = param(title=_("Text"), default="", doc=_("Was der Körper sagen soll."))
    size: float = param(
        title=_("Schriftgröße"), default=8.0, unit="mm", minimum=MIN_SIZE, maximum=200.0
    )
    depth: float = param(title=_("Dicke"), default=0.6, unit="mm", minimum=0.1, maximum=50.0)
    font: str = param(title=_("Schrift"), default=FONTS[0], choices=FONTS, placement="advanced")
    x: float = param(title=_("Position X"), default=0.0, unit="mm")
    y: float = param(title=_("Position Y"), default=0.0, unit="mm")
    z: float = param(title=_("Position Z"), default=0.0, unit="mm")
    name: str = param(title=_("Name"), default="", placement="advanced")


@register_op(
    name="create_label",
    title=_("Schriftzug als Körper"),
    category="label",
    params=LabelBodyParams,
    consumes=0,
    produces=1,
    doc=_(
        "Legt einen Schriftzug als eigenes Objekt an — für den Zweifarbendruck "
        "mit zwei Dateien und für Buchstaben, die aufgeklebt werden."
    ),
)
def create_label(ctx: OpContext) -> OpResult:
    """§25: the same outlines, standing on their own instead of on a part.

    Two colours can be had either way: this one as a second file for a printer
    that changes filament by hand, and ``label_text`` with a slot for a machine
    that reads the groups out of a 3MF (§20). Which is better depends on the
    printer, so both are here.
    """
    params = cast(LabelBodyParams, ctx.params)
    if not params.text.strip():
        raise ValidationError(
            field="text",
            detail=_("Ohne Text gibt es nichts anzulegen."),
            constraint="empty",
        )

    shapes = outlines(params.text, params.size, params.font)
    body = label_solid(shapes, params.depth) if shapes else None
    if body is None:
        raise ValidationError(
            field="text",
            detail=_("Aus diesem Text ließ sich keine Form bilden."),
            value=params.text,
            constraint="no_outline",
        )

    middle = body.bounds.centre
    placed = apply(
        body,
        translation((params.x - middle[0], params.y - middle[1], params.z)),
    )
    return OpResult(
        outputs=[SceneObject(id="", name=params.name or params.text.strip()[:20], mesh=placed)]
    )


def _with_slot_named(slots: list[MaterialSlot], index: int) -> list[MaterialSlot]:
    """Add the slot the lettering goes into, keeping one that is already named."""
    known = {entry.index: entry for entry in slots}
    known.setdefault(0, MaterialSlot(index=0, name=str(_("Körper"))))
    known.setdefault(index, MaterialSlot(index=index, name=str(_("Schrift"))))
    return [known[key] for key in sorted(known)]
