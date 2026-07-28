"""Operations for print preparation (Bauplan §25).

Drilling, splitting, arranging and the collision check. The last one changes no
geometry at all — it only reports, which is a perfectly good thing for an
operation to do when the alternative is a surprise at the printer.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from app.core.geom.mesh import as_mesh_data
from app.core.geom.orient import orient_for_print
from app.core.geom.prepare import (
    arrange_on_bed,
    check_build_volume,
    check_collisions,
    drill,
    split_at_plane,
)
from app.core.geom.section import AXIS_NORMALS, SectionPlane
from app.core.geom.transform import Axis
from app.core.registry import VARIABLE, op_params, param, register_op
from app.core.types import BaseParams, OpContext, OpResult
from app.i18n import _

_AXES = tuple(AXIS_NORMALS)


@op_params
class DrillParams(BaseParams):
    diameter: float = param(
        title=_("Durchmesser"), default=5.0, unit="mm", minimum=0.2, maximum=200.0
    )
    x: float = param(title=_("Position X"), default=0.0, unit="mm")
    y: float = param(title=_("Position Y"), default=0.0, unit="mm")
    z: float = param(title=_("Position Z"), default=0.0, unit="mm")
    axis: str = param(title=_("Achse"), default="z", choices=_AXES)
    depth: float = param(
        title=_("Tiefe"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        placement="advanced",
        doc=_("Null bohrt durch das ganze Teil."),
    )
    compensate: bool = param(
        title=_("Materialtoleranz berücksichtigen"),
        default=True,
        placement="advanced",
        doc=_("Vergrößert die Bohrung um den Wert aus dem Materialprofil."),
    )


@register_op(
    name="drill_hole",
    title=_("Bohrung setzen"),
    category="holes",
    params=DrillParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    touches_features=True,
    deterministic=False,
    shortcut="Ctrl+B",
    doc=_("Bohrt ein rundes Loch — auf Wunsch um die Materialtoleranz vergrößert."),
)
def drill_hole(ctx: OpContext) -> OpResult:
    params = cast(DrillParams, ctx.params)
    source = ctx.inputs[0]
    result = drill(
        as_mesh_data(source.mesh),
        position=(params.x, params.y, params.z),
        axis=cast(Axis, params.axis),
        diameter=params.diameter,
        depth=params.depth,
        profile=ctx.profile,
        compensate=params.compensate,
        quality=ctx.quality,
        seed=ctx.seed,
    )
    return OpResult(
        outputs=[dataclasses.replace(source, mesh=result.mesh)],
        solver=result.solver,
        findings=result.findings,
    )


@op_params
class SplitPlaneParams(BaseParams):
    axis: str = param(title=_("Achse"), default="z", choices=_AXES)
    position: float = param(title=_("Position"), default=0.0, unit="mm")


@register_op(
    name="split_plane",
    title=_("An Ebene teilen"),
    category="prepare",
    params=SplitPlaneParams,
    consumes=1,
    produces=2,
    doc=_("Teilt ein Objekt an einer Ebene in zwei Hälften mit geschlossenen Schnittflächen."),
)
def split_plane(ctx: OpContext) -> OpResult:
    params = cast(SplitPlaneParams, ctx.params)
    source = ctx.inputs[0]
    plane = SectionPlane(normal=AXIS_NORMALS[cast(Axis, params.axis)], position=params.position)
    first, second, findings = split_at_plane(as_mesh_data(source.mesh), plane)
    return OpResult(
        outputs=[
            dataclasses.replace(source, mesh=first, name=f"{source.name} A"),
            dataclasses.replace(source, mesh=second, name=f"{source.name} B", features={}),
        ],
        findings=findings,
    )


@op_params
class OrientParams(BaseParams):
    pass


@register_op(
    name="orient_for_print",
    title=_("Druckoptimal ausrichten"),
    category="transform",
    params=OrientParams,
    consumes=1,
    produces=1,
    doc=_("Dreht das Objekt auf eine flache Auflage — vorerst über eine Heuristik."),
)
def orient_for_print_op(ctx: OpContext) -> OpResult:
    result = orient_for_print(as_mesh_data(ctx.inputs[0].mesh))
    return OpResult(
        outputs=[dataclasses.replace(ctx.inputs[0], mesh=result.mesh)],
        findings=result.findings,
    )


@op_params
class ArrangeParams(BaseParams):
    spacing: float = param(title=_("Abstand"), default=5.0, unit="mm", minimum=0.0, maximum=100.0)


@register_op(
    name="arrange_bed",
    title=_("Auf dem Bett anordnen"),
    category="scene",
    params=ArrangeParams,
    consumes=0,
    produces=VARIABLE,
    doc=_("Legt alle Objekte nebeneinander auf das Druckbett."),
)
def arrange_bed(ctx: OpContext) -> OpResult:
    params = cast(ArrangeParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    arranged, findings = arrange_on_bed(meshes, ctx.profile, params.spacing)
    findings.extend(check_collisions(arranged))
    return OpResult(
        outputs=[
            dataclasses.replace(entry, mesh=mesh)
            for entry, mesh in zip(ctx.inputs, arranged, strict=True)
        ],
        findings=findings,
    )


@op_params
class CollisionParams(BaseParams):
    clearance: float = param(
        title=_("Mindestabstand"), default=0.0, unit="mm", minimum=0.0, maximum=50.0
    )


@register_op(
    name="check_collisions",
    title=_("Kollisionen prüfen"),
    category="scene",
    params=CollisionParams,
    consumes=0,
    produces=VARIABLE,
    doc=_("Meldet Überschneidungen und was über den Bauraum hinaussteht."),
)
def check_collisions_op(ctx: OpContext) -> OpResult:
    params = cast(CollisionParams, ctx.params)
    meshes = [as_mesh_data(entry.mesh) for entry in ctx.inputs]
    findings = check_collisions(meshes, params.clearance)
    findings.extend(check_build_volume(meshes, ctx.profile))
    # Changes nothing: the objects pass through untouched, the findings are the result.
    return OpResult(outputs=list(ctx.inputs), findings=findings)
