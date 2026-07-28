"""Operations for print preparation (Bauplan §25).

Drilling, splitting, arranging and the collision check. The last one changes no
geometry at all — it only reports, which is a perfectly good thing for an
operation to do when the alternative is a surprise at the printer.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from app.core.errors import ValidationError
from app.core.geom.autosplit import Candidate
from app.core.geom.mesh import as_mesh_data
from app.core.geom.orient import orient_for_print
from app.core.geom.pins import PIN_COUNT, PIN_MAX, PinnedPair, add_pins, plan_pins
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
from app.core.slice.orientation import DEFAULT_CANDIDATES, search
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
class SplitPinnedParams(BaseParams):
    axis: str = param(title=_("Achse"), default="z", choices=_AXES)
    position: float = param(title=_("Position"), default=0.0, unit="mm")
    pins: int = param(
        title=_("Passstifte"),
        default=PIN_COUNT,
        minimum=0,
        maximum=6,
        doc=_("Null heißt: nur schneiden. Zwei halten die Hälften gegen Verdrehen."),
    )
    diameter: float = param(
        title=_("Stiftdurchmesser"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=PIN_MAX,
        placement="advanced",
        doc=_("Null heißt: aus der Schnittfläche ableiten."),
    )
    play: float = param(
        title=_("Spiel"),
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=1.0,
        placement="advanced",
        doc=_("Null heißt: Wert aus dem kalibrierten Materialprofil."),
    )


@register_op(
    name="split_pinned",
    title=_("Teilen und verstiften"),
    category="prepare",
    params=SplitPinnedParams,
    consumes=1,
    produces=2,
    doc=_(
        "Teilt ein Objekt an einer Ebene und setzt Passstifte in die Schnittfläche. "
        "Das Spiel kommt aus dem Materialprofil."
    ),
)
def split_pinned(ctx: OpContext) -> OpResult:
    """§25: the cut and the pins in one step, because they belong together.

    A seam without pins is a seam somebody has to align by hand while the glue
    grabs; a pin without a seam is nothing. Both in one operation also means one
    undo takes the whole thing back.
    """
    params = cast(SplitPinnedParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)
    candidate = Candidate(
        axis=cast(Axis, params.axis),
        position=params.position,
        area=0.0,
        contours=1,
        score=0.0,
    )

    first, second, findings = split_at_plane(mesh, candidate.plane)
    if not (first.triangle_count and second.triangle_count):
        raise ValidationError(
            field="position",
            detail=_("Diese Ebene teilt das Objekt nicht."),
            value=params.position,
            constraint="no_split",
        )

    plan = plan_pins(mesh, candidate, count=params.pins) if params.pins else None
    if plan is not None and params.diameter:
        plan = dataclasses.replace(plan, diameter=params.diameter)

    pair = (
        add_pins(first, second, plan, ctx.profile, play=params.play or None)
        if plan is not None and ctx.profile is not None
        else PinnedPair(first=first, second=second)
    )

    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=pair.first,
                name=f"{source.name} A",
                features={**source.features, **pair.pin_features},
            ),
            dataclasses.replace(
                source,
                mesh=pair.second,
                name=f"{source.name} B",
                features=dict(pair.bore_features),
            ),
        ],
        findings=[*findings, *pair.findings],
    )


@op_params
class OrientParams(BaseParams):
    thorough: bool = param(
        title=_("Gründlich suchen"),
        default=True,
        doc=_(
            "Rechnet hunderte Lagen mit der Schichtanalyse durch. "
            "Aus heißt: schnelle Heuristik über die Flächen."
        ),
    )
    candidates: int = param(
        title=_("Kandidaten"),
        default=DEFAULT_CANDIDATES,
        minimum=8,
        maximum=2000,
        placement="advanced",
    )


@register_op(
    name="orient_for_print",
    title=_("Druckoptimal ausrichten"),
    category="transform",
    params=OrientParams,
    consumes=1,
    produces=1,
    deterministic=False,
    doc=_("Sucht die Lage mit dem geringsten Stützbedarf."),
)
def orient_for_print_op(ctx: OpContext) -> OpResult:
    """Thorough means the layer analysis judges; otherwise the P2 heuristic does."""
    params = cast(OrientParams, ctx.params)
    mesh = as_mesh_data(ctx.inputs[0].mesh)

    if params.thorough:
        found = search(
            mesh,
            count=params.candidates,
            seed=ctx.seed,
            progress=ctx.progress,
            cancelled=ctx.cancelled,
        )
        return OpResult(
            outputs=[dataclasses.replace(ctx.inputs[0], mesh=found.mesh)],
            findings=found.findings,
        )

    result = orient_for_print(mesh)
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
