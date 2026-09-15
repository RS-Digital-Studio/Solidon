"""Registrierter Organizer-Erzeuger mit vollständigem Layoutwert (§10, §25)."""

from __future__ import annotations

from typing import cast

from app.core import expressions
from app.core.organizer.build import build_organizer
from app.core.organizer.layout import resolve_layout
from app.core.organizer.serialize import grid_layout, layout_from_text, layout_to_text
from app.core.registry import NAME_DOC, op_params, param, register_op
from app.core.types import BaseParams, OpContext, OpResult, SceneObject
from app.i18n import _

DEFAULT_LAYOUT = layout_to_text(grid_layout())


@op_params
class OrganizerParams(BaseParams):
    width: float = param(
        title=_("Breite"),
        default=180.0,
        minimum=10.0,
        maximum=2000.0,
        unit="mm",
        doc=_("Außenbreite. Beim Bezug auf Fachmaße wird sie aus der Aufteilung berechnet."),
    )
    depth: float = param(
        title=_("Tiefe"),
        default=148.5,
        minimum=10.0,
        maximum=2000.0,
        unit="mm",
        doc=_("Außentiefe. Beim Bezug auf Fachmaße wird sie aus der Aufteilung berechnet."),
    )
    height: float = param(
        title=_("Höhe"),
        default=120.0,
        minimum=2.0,
        maximum=2000.0,
        unit="mm",
        doc=_("Gesamthöhe einschließlich Boden. Einzelne Trennwände können niedriger sein."),
    )
    layout: str = param(
        title=_("Fachaufteilung"),
        default=DEFAULT_LAYOUT,
        kind="organizer",
        doc=_(
            "Fächer in der Vorschau teilen und Trennwandhöhen ändern. "
            "Maßausdrücke bleiben erhalten."
        ),
    )
    wall: float = param(
        title=_("Außenwand"),
        default=3.0,
        minimum=1.0,
        maximum=100.0,
        unit="mm",
        placement="advanced",
        doc=_("Dicke der Außenwand; die Teilungswände werden in der Aufteilung bemaßt."),
    )
    floor: float = param(
        title=_("Bodenstärke"),
        default=4.0,
        minimum=1.0,
        maximum=100.0,
        unit="mm",
        placement="advanced",
        doc=_("Bodenstärke unabhängig von Fachhöhe und Trennwänden."),
    )
    radius: float = param(
        title=_("Außenradius"),
        default=8.0,
        minimum=0.0,
        maximum=500.0,
        unit="mm",
        placement="advanced",
        doc=_("Radius der senkrechten Außenecken. Die Innenradien stehen an den Fächern."),
    )
    name: str = param(title=_("Name"), default="", placement="advanced", doc=NAME_DOC)


@register_op(
    name="create_organizer",
    title=_("Organizer anlegen"),
    category="primitive",
    params=OrganizerParams,
    consumes=0,
    produces=1,
    doc=_(
        "Erzeugt einen Organizer mit maßlich gekoppelten Fächern und einzeln "
        "veränderbaren Trennwänden."
    ),
)
def create_organizer(ctx: OpContext) -> OpResult:
    params = cast(OrganizerParams, ctx.params)
    values = expressions.resolve(ctx.scene.parameters)
    layout = resolve_layout(
        layout_from_text(params.layout),
        values,
        width=params.width,
        depth=params.depth,
        height=params.height,
        wall=params.wall,
        floor=params.floor,
        radius=params.radius,
    )
    built = build_organizer(
        layout, quality=ctx.quality, cancelled=ctx.cancelled, progress=ctx.progress
    )
    return OpResult(
        outputs=[
            SceneObject(
                id="", name=params.name or _("Organizer"), mesh=built.mesh, features=built.features
            )
        ],
        solver=built.solver,
        findings=list(built.findings),
    )
