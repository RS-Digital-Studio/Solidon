"""Scene operations (Bauplan §25, category "Szene").

These touch no geometry: they name, copy and arrange what is already there. They
still go through the registry and the stack like every other operation, because
"no geometry change outside an operation" (AGENTS.md rule 2) is only credible if
the cheap cases follow it too.
"""

from __future__ import annotations

import dataclasses
from typing import cast

from app.core.registry import VARIABLE, op_params, param, register_op
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


#: How many of one part may stand in a scene. A plate of ten clips is an
#: ordinary job; a hundred is already a stress test of the arranging, and a
#: number above it is a typing mistake, not an order.
MAX_COPIES = 100


@op_params
class DuplicateObjectParams(BaseParams):
    count: int = param(
        title=_("Anzahl"),
        default=2,
        minimum=1,
        maximum=MAX_COPIES,
        doc=_(
            "Wie viele Ausfertigungen es danach gibt. Zwei ist eine Kopie — die "
            "Stückzahl steht damit im Stapel und nicht im Dateinamen."
        ),
    )
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
    produces=VARIABLE,
    produces_from="count",
    shortcut="Ctrl+D",
    doc=_(
        "Legt weitere Ausfertigungen des Objekts an. Alle bleiben getrennt, und "
        "die Stückzahl steht als Zahl im Stapel."
    ),
)
def duplicate_object(ctx: OpContext) -> OpResult:
    """§25: „x10" im Dateinamen ist eine Stückzahl, die niemand mehr ändern kann.

    Here it is one step with a number in it, rather than nine duplications
    nobody can read afterwards — and the arranging spreads whatever comes out
    over the plates (§25).
    """
    params = cast(DuplicateObjectParams, ctx.params)
    source = ctx.inputs[0]
    outputs = [source]
    for index in range(2, max(params.count, 1) + 1):
        outputs.append(
            dataclasses.replace(
                source,
                name=_copy_name(source.name, params.name, index, params.count),
                features=dict(source.features),
                material_slots=list(source.material_slots),
            )
        )
    return OpResult(outputs=outputs)


def _copy_name(original: str, chosen: str, index: int, count: int) -> str:
    """Names that stay apart without becoming a riddle.

    One copy is "part (copy)", as it always was. Several are numbered, because
    ten objects called "part (copy)" are a list of one thing ten times over.
    """
    base = chosen or f"{original} ({tr('Kopie')})"
    return base if count <= 2 else f"{base} {index - 1}"
