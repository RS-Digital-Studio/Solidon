"""Geometry operations (Bauplan §25, category "Transformation").

These are the operations the gizmo produces (§18.11): a drag in the viewport ends
as one of them, with the numbers the drag arrived at. That is what makes a drag
undoable like everything else.
"""

from __future__ import annotations

import dataclasses
from typing import Any, cast

from app.core.errors import Action, AppError
from app.core.geom.align import align_matrix
from app.core.geom.boolean import BooleanKind, boolean
from app.core.geom.mesh import as_mesh_data
from app.core.geom.repair import repair
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
from app.core.types import BaseParams, FeatureRef, OpContext, OpResult, Transform
from app.i18n import _

_AXES = tuple(AXIS_VECTORS)
_ANCHORS = ("centre", "origin", "bed")


def as_transform(matrix: Any) -> Transform:
    """A matrix as plain numbers, so it survives the cache and the file (§21.2)."""
    rows = [tuple(float(value) for value in row) for row in matrix]
    return cast(Transform, tuple(rows))


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
    matrix = translation((params.dx, params.dy, params.dz))
    moved = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=moved)], transform=as_transform(matrix)
    )


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
    matrix = rotation(cast(Axis, params.axis), params.angle, pivot)
    turned = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=turned)], transform=as_transform(matrix)
    )


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
    matrix = scaling(factors, pivot)
    scaled = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=scaled)], transform=as_transform(matrix)
    )


@op_params
class RepairParams(BaseParams):
    fill_holes: bool = param(
        title=_("Offene Stellen schließen"),
        default=True,
        doc=_("Schließt kleine Löcher. Fehlende Wände kann das nicht ersetzen."),
    )
    weld: bool = param(title=_("Punkte verschweißen"), default=True, placement="advanced")
    degenerate: bool = param(
        title=_("Entartete Dreiecke entfernen"), default=True, placement="advanced"
    )
    normals: bool = param(title=_("Normalen vereinheitlichen"), default=True, placement="advanced")
    small_components: bool = param(
        title=_("Kleinstteile löschen"),
        default=False,
        placement="advanced",
        doc=_("Standardmäßig aus: gelöscht wird nur, was ausdrücklich gelöscht werden soll."),
    )
    self_intersections: bool = param(
        title=_("Selbstdurchdringungen auflösen"), default=False, placement="advanced"
    )


@register_op(
    name="repair",
    title=_("Reparieren"),
    category="repair",
    params=RepairParams,
    consumes=1,
    produces=1,
    doc=_("Schließt Löcher, entfernt entartete Dreiecke und richtet die Flächen aus."),
)
def repair_object(ctx: OpContext) -> OpResult:
    params = cast(RepairParams, ctx.params)
    source = ctx.inputs[0]
    result = repair(
        as_mesh_data(source.mesh),
        weld=params.weld,
        degenerate=params.degenerate,
        normals=params.normals,
        holes=params.fill_holes,
        small_components=params.small_components,
        self_intersections=params.self_intersections,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        findings=result.findings,
    )


@op_params
class BooleanParams(BaseParams):
    pass


def _boolean_op(ctx: OpContext, kind: BooleanKind, seed: int | None) -> OpResult:
    """Two bodies in, one out — with the fallback chain behind it (§17.2)."""
    first, second = (as_mesh_data(entry.mesh) for entry in ctx.inputs[:2])
    outcome = boolean(kind, [first, second], quality=ctx.quality, seed=seed)
    return OpResult(
        outputs=[dataclasses.replace(ctx.inputs[0], mesh=outcome.mesh)],
        solver=outcome.solver,
        findings=outcome.findings,
    )


@register_op(
    name="union_objects",
    title=_("Vereinigen"),
    category="boolean",
    params=BooleanParams,
    consumes=2,
    produces=1,
    deterministic=False,
    doc=_("Verschmilzt zwei Objekte zu einem."),
)
def union_objects(ctx: OpContext) -> OpResult:
    return _boolean_op(ctx, "union", ctx.seed)


@register_op(
    name="subtract_objects",
    title=_("Abziehen"),
    category="boolean",
    params=BooleanParams,
    consumes=2,
    produces=1,
    deterministic=False,
    doc=_("Zieht das zweite Objekt vom ersten ab."),
)
def subtract_objects(ctx: OpContext) -> OpResult:
    return _boolean_op(ctx, "difference", ctx.seed)


@register_op(
    name="intersect_objects",
    title=_("Schnittmenge"),
    category="boolean",
    params=BooleanParams,
    consumes=2,
    produces=1,
    deterministic=False,
    doc=_("Behält nur, was beide Objekte gemeinsam haben."),
)
def intersect_objects(ctx: OpContext) -> OpResult:
    return _boolean_op(ctx, "intersection", ctx.seed)


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
    mesh = as_mesh_data(source.mesh)
    matrix = translation((0.0, 0.0, -mesh.bounds.minimum[2]))
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=place_on_bed(mesh))],
        transform=as_transform(matrix),
    )


@op_params
class AlignParams(BaseParams):
    feature: str = param(
        title=_("Merkmal"),
        default="",
        doc=_("Bohrung oder Fläche am bewegten Objekt, zum Beispiel hole_1."),
    )
    target: str = param(
        title=_("Ziel"),
        default="",
        doc=_("Merkmal, auf das ausgerichtet wird, als obj_2:hole_1."),
    )
    flip: bool = param(
        title=_("Umgekehrt herum"),
        default=False,
        placement="advanced",
        doc=_("Dreht das Ergebnis um 180 Grad, wenn die andere Seite gemeint war."),
    )


@register_op(
    name="align_to_feature",
    title=_("An Merkmal ausrichten"),
    category="transform",
    params=AlignParams,
    consumes=1,
    produces=1,
    applies_to=["hole", "face"],
    doc=_("Bringt eine Bohrungsachse oder eine Fläche mit einer zweiten zur Deckung."),
)
def align_to_feature(ctx: OpContext) -> OpResult:
    """Snapping as an operation (§18.11): the file says what was lined up with what."""
    params = cast(AlignParams, ctx.params)
    source = ctx.inputs[0]
    reference = FeatureRef.parse(params.target) if ":" in params.target else None
    if reference is None:
        raise AppError(
            _("Das Ziel muss ein Merkmal eines Objekts benennen."),
            detail=f"malformed target {params.target!r}",
            values={"target": params.target},
            suggestions=(
                Action(id="write_target", label=_("Schreiben Sie das Ziel als obj_2:hole_1.")),
            ),
        )

    moving = source.features.get(params.feature)
    other = ctx.scene.objects.get(reference.object_id)
    wanted = other.features.get(reference.feature_id) if other is not None else None
    if moving is None or wanted is None:
        missing = params.feature if moving is None else params.target
        raise AppError(
            _("Dieses Merkmal gibt es nicht."),
            detail=f"unknown feature {missing!r}",
            values={"feature": missing},
            suggestions=(
                Action(id="pick_feature", label=_("Wählen Sie das Merkmal im Objektbaum aus.")),
            ),
        )

    matrix = align_matrix(moving, wanted, flip=params.flip)
    aligned = apply(as_mesh_data(source.mesh), matrix)
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=aligned)], transform=as_transform(matrix)
    )
