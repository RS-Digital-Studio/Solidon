"""Geometry operations (Bauplan §25, category "Transformation").

These are the operations the gizmo produces (§18.11): a drag in the viewport ends
as one of them, with the numbers the drag arrived at. That is what makes a drag
undoable like everything else.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from app.core.geom.mesh import as_mesh_data
from app.core.geom.transform import (
    AXIS_VECTORS,
    Anchor,
    Axis,
    anchor_point,
    apply,
    place_on_bed,
    rotation,
    scaling,
    translation,
)
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, OpContext, OpResult
from app.i18n import _

_AXES = tuple(AXIS_VECTORS)
_ANCHORS = ("centre", "origin", "bed")


@op_params
class TranslateParams(BaseParams):
    dx: float = param(title=_("Verschiebung X"), default=0.0, unit="mm")
    dy: float = param(title=_("Verschiebung Y"), default=0.0, unit="mm")
    dz: float = param(title=_("Verschiebung Z"), default=0.0, unit="mm")


@register_op(
    name="translate_object",
    title=_("Verschieben"),
    category="transform",
    params=TranslateParams,
    consumes=1,
    produces=1,
    shortcut="Ctrl+T",
    doc=_("Verschiebt ein Objekt um die angegebenen Millimeter."),
)
def translate_object(ctx: OpContext) -> OpResult:
    params = cast(TranslateParams, ctx.params)
    source = ctx.inputs[0]
    moved = apply(as_mesh_data(source.mesh), translation((params.dx, params.dy, params.dz)))
    return OpResult(outputs=[dataclasses.replace(source, mesh=moved)])


@op_params
class RotateParams(BaseParams):
    axis: str = param(title=_("Achse"), default="z", choices=_AXES)
    angle: float = param(
        title=_("Winkel"), default=90.0, unit="grad", minimum=-360.0, maximum=360.0
    )
    about: str = param(
        title=_("Drehpunkt"),
        default="centre",
        choices=_ANCHORS,
        placement="advanced",
        doc=_("Schwerpunkt des Objekts, Weltnullpunkt oder Aufstandsfläche."),
    )


@register_op(
    name="rotate_object",
    title=_("Drehen"),
    category="transform",
    params=RotateParams,
    consumes=1,
    produces=1,
    shortcut="Ctrl+R",
    doc=_("Dreht ein Objekt um eine Achse."),
)
def rotate_object(ctx: OpContext) -> OpResult:
    params = cast(RotateParams, ctx.params)
    source = ctx.inputs[0]
    pivot = anchor_point(as_mesh_data(source.mesh), cast(Anchor, params.about))
    turned = apply(
        as_mesh_data(source.mesh), rotation(cast(Axis, params.axis), params.angle, pivot)
    )
    return OpResult(outputs=[dataclasses.replace(source, mesh=turned)])


@op_params
class ScaleParams(BaseParams):
    factor: float = param(
        title=_("Faktor"),
        default=1.0,
        minimum=0.01,
        maximum=100.0,
        doc=_("Gleichmäßige Skalierung. Achsweise Werte stehen hinten."),
    )
    fx: float = param(title=_("Faktor X"), default=0.0, minimum=0.0, placement="advanced")
    fy: float = param(title=_("Faktor Y"), default=0.0, minimum=0.0, placement="advanced")
    fz: float = param(title=_("Faktor Z"), default=0.0, minimum=0.0, placement="advanced")
    about: str = param(
        title=_("Bezugspunkt"), default="centre", choices=_ANCHORS, placement="advanced"
    )


@register_op(
    name="scale_object",
    title=_("Skalieren"),
    category="transform",
    params=ScaleParams,
    consumes=1,
    produces=1,
    doc=_("Skaliert ein Objekt gleichmäßig oder achsweise."),
)
def scale_object(ctx: OpContext) -> OpResult:
    params = cast(ScaleParams, ctx.params)
    source = ctx.inputs[0]
    # A per-axis value of zero means "use the uniform factor for this axis".
    factors = (
        params.fx or params.factor,
        params.fy or params.factor,
        params.fz or params.factor,
    )
    pivot = anchor_point(as_mesh_data(source.mesh), cast(Anchor, params.about))
    scaled = apply(as_mesh_data(source.mesh), scaling(factors, pivot))
    return OpResult(outputs=[dataclasses.replace(source, mesh=scaled)])


@op_params
class PlaceOnBedParams(BaseParams):
    pass


@register_op(
    name="place_on_bed",
    title=_("Auf das Bett setzen"),
    category="transform",
    params=PlaceOnBedParams,
    consumes=1,
    produces=1,
    doc=_("Setzt das Objekt mit seiner Unterseite auf Z = 0."),
)
def place_object_on_bed(ctx: OpContext) -> OpResult:
    source = ctx.inputs[0]
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=place_on_bed(as_mesh_data(source.mesh)))]
    )
