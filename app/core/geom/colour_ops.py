"""Colour operations (Bauplan §25, category "Farbe").

Two operations, and between them the whole of §20 that a user can reach today:
assign a slot by hand, or let a texture decide. The brush with a radius is a
late phase — but everything below it is here, so the brush will only have to
paint, not invent a data model.
"""

from __future__ import annotations

import dataclasses
import re
from typing import cast

from app.core.errors import ValidationError
from app.core.geom.attributes import counts, with_slot
from app.core.geom.mesh import as_mesh_data
from app.core.geom.texture import to_slots
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, MaterialSlot, OpContext, OpResult
from app.i18n import _

_log = get_logger(__name__)

#: How many filaments the operations allow to be named. More than eight is not
#: a machine anybody owns, and every one of them is a manual change or an AMS
#: slot somebody has to fill.
MAX_SLOTS = 8

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


@op_params
class AssignSlotParams(BaseParams):
    slot: int = param(
        title=_("Slot"),
        default=0,
        minimum=0,
        maximum=MAX_SLOTS - 1,
        doc=_("Der Materialslot, in den das ganze Objekt kommt."),
    )
    name: str = param(
        title=_("Bezeichnung"),
        default="",
        doc=_("Wie das Filament heißt. Leer nimmt „Slot“ und die Nummer."),
    )
    colour: str = param(
        title=_("Farbe"),
        default="",
        doc=_("Anzeigefarbe als #RRGGBB. Nur zur Ansicht — gedruckt wird, was eingelegt ist."),
    )


@register_op(
    name="assign_slot",
    title=_("Slot zuweisen"),
    category="colour",
    params=AssignSlotParams,
    consumes=1,
    produces=1,
    doc=_(
        "Legt das ganze Objekt in einen Materialslot. Mehrfarbig wird ein Teil, "
        "indem verschieden zugewiesene Körper vereinigt werden."
    ),
)
def assign_slot(ctx: OpContext) -> OpResult:
    params = cast(AssignSlotParams, ctx.params)
    source = ctx.inputs[0]
    slot = MaterialSlot(
        index=params.slot,
        name=params.name or f"{_('Slot').translate()} {params.slot}",
        colour=_colour_from(params.colour),
    )
    painted = with_slot(as_mesh_data(source.mesh), params.slot)
    return OpResult(
        outputs=[
            dataclasses.replace(
                source, mesh=painted, material_slots=_merged(source.material_slots, [slot])
            )
        ]
    )


def _colour_from(text: str) -> tuple[float, float, float] | None:
    """``#RRGGBB`` as three numbers, and a clear error for anything else."""
    if not text:
        return None
    match = _HEX.match(text.strip())
    if match is None:
        raise ValidationError(
            field="colour",
            detail=_("Die Farbe wird als #RRGGBB angegeben."),
            value=text,
            constraint="format",
        )
    digits = match.group(1)
    return cast(
        "tuple[float, float, float]",
        tuple(int(digits[start : start + 2], 16) / 255.0 for start in (0, 2, 4)),
    )


@op_params
class SlotsFromTextureParams(BaseParams):
    filaments: int = param(
        title=_("Filamente"),
        default=4,
        minimum=1,
        maximum=MAX_SLOTS,
        doc=_("Auf wie viele Farben umgerechnet wird — so viele, wie eingelegt sind."),
    )


@register_op(
    name="slots_from_texture",
    title=_("Farben in Slots umrechnen"),
    category="colour",
    params=SlotsFromTextureParams,
    consumes=1,
    produces=1,
    deterministic=False,
    doc=_(
        "Rechnet die Textur eines Objekts auf die Anzahl eingelegter Filamente um "
        "und legt das Ergebnis als Materialslots ab (§20)."
    ),
)
def slots_from_texture(ctx: OpContext) -> OpResult:
    """§20, and the sentence that goes with it: never as fine as the render.

    The starting value comes from the operation, not from a parameter of its
    own: §11.3 already keeps one with every randomised step, and that is what
    makes the quantisation repeat itself when the file is opened again.
    """
    params = cast(SlotsFromTextureParams, ctx.params)
    source = ctx.inputs[0]
    seed = ctx.seed or 0

    mesh, slots = to_slots(as_mesh_data(source.mesh), params.filaments, seed)
    if not slots:
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="colour.no_texture",
                    severity="warning",
                    message=_("Dieses Objekt trägt keine Farbinformation."),
                    object_id=source.id,
                )
            ],
        )

    findings = [
        Finding(
            code="colour.quantised",
            severity="info",
            message=_("Die Farben wurden auf die eingelegten Filamente umgerechnet."),
            object_id=source.id,
            values={"slots": len(slots), "wanted": params.filaments, "seed": seed},
        )
    ]
    if len(slots) < params.filaments:
        findings.append(
            Finding(
                code="colour.fewer_than_asked",
                severity="info",
                message=_("Weniger Farben als Filamente — mehr gibt das Modell nicht her."),
                object_id=source.id,
                values={"slots": len(slots), "wanted": params.filaments},
            )
        )
    _log.info("slot shares: %s", counts(mesh))
    return OpResult(
        outputs=[
            dataclasses.replace(
                source, mesh=mesh, material_slots=_merged(source.material_slots, slots)
            )
        ],
        findings=findings,
    )


def _merged(existing: list[MaterialSlot], added: list[MaterialSlot]) -> list[MaterialSlot]:
    """New assignments win; slots the object already knew and still uses stay."""
    known = {entry.index: entry for entry in existing}
    known.update({entry.index: entry for entry in added})
    return [known[index] for index in sorted(known)]
