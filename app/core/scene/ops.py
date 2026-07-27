"""Scene operations (Bauplan §25, category "Szene").

These touch no geometry: they name, copy and arrange what is already there. They
still go through the registry and the stack like every other operation, because
"no geometry change outside an operation" (AGENTS.md rule 2) is only credible if
the cheap cases follow it too.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, OpContext, OpResult
from app.i18n import _, tr


@op_params
class RenameObjectParams(BaseParams):
    name: str = param(title=_("Name"), doc=_("Neuer Name des Objekts."))


@register_op(
    name="rename_object",
    title=_("Objekt umbenennen"),
    category="scene",
    params=RenameObjectParams,
    consumes=1,
    produces=1,
    shortcut="F2",
    doc=_("Gibt einem Objekt einen anderen Namen. Die Geometrie bleibt unberührt."),
)
def rename_object(ctx: OpContext) -> OpResult:
    params = cast(RenameObjectParams, ctx.params)
    source = ctx.inputs[0]
    return OpResult(outputs=[dataclasses.replace(source, name=params.name)])


@op_params
class DuplicateObjectParams(BaseParams):
    name: str = param(
        title=_("Name der Kopie"),
        default="",
        doc=_("Leer lässt den Namen aus dem Original ableiten."),
    )


@register_op(
    name="duplicate_object",
    title=_("Objekt duplizieren"),
    category="scene",
    params=DuplicateObjectParams,
    consumes=1,
    produces=2,
    shortcut="Ctrl+D",
    doc=_("Legt eine zweite Ausfertigung des Objekts an. Original und Kopie bleiben getrennt."),
)
def duplicate_object(ctx: OpContext) -> OpResult:
    params = cast(DuplicateObjectParams, ctx.params)
    source = ctx.inputs[0]
    name = params.name or f"{source.name} ({tr('Kopie')})"
    copy = dataclasses.replace(
        source,
        name=name,
        features=dict(source.features),
        material_slots=list(source.material_slots),
    )
    return OpResult(outputs=[source, copy])
