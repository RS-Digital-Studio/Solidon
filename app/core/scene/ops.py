"""Szenen-Operationen (Bauplan §25, Kategorie „Szene").

Sie fassen keine Geometrie an: sie benennen, kopieren und ordnen, was schon da
ist. Trotzdem laufen sie über Register und Stapel wie jede andere Operation —
„keine Geometrieänderung außerhalb einer Op" (AGENTS.md Regel 2) ist nur
glaubwürdig, wenn auch die billigen Fälle sich daran halten.
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


@register_op(
    name="delete_object",
    title=_("Objekt entfernen"),
    category="scene",
    params=BaseParams,
    consumes=1,
    produces=0,
    shortcut="Del",
    doc=_(
        "Nimmt ein Objekt aus der Szene. Der Schritt steht im Verlauf, ein "
        "Rückgängig holt es also zurück."
    ),
)
def delete_object(ctx: OpContext) -> OpResult:
    """§25: etwas wieder loswerden, ohne den Import zurückzunehmen.

    Eine Operation, die nichts erzeugt — und deshalb keine Ausnahme von
    Regel 3, sondern ihr genauester Fall: sie ändert kein Objekt, sie gibt
    keines zurück. Die Auswertung räumt jeden Eingang weg, der nicht wieder
    herauskommt, also braucht es dafür keinen Sonderweg.

    Was danach noch auf den Körper zeigt, findet ihn nicht mehr: der Stapel
    lehnt eine spätere Operation auf ihm beim Anlegen ab, und eine, die schon
    dasteht, hält die Kette an (§15.2). Beides ist besser als ein Objekt, das
    heimlich weiterlebt, weil ein Schritt darunter es noch braucht.
    """
    return OpResult(outputs=[])


#: Wie viele Exemplare eines Teils in einer Szene stehen dürfen. Eine Platte
#: mit zehn Clips ist ein gewöhnlicher Auftrag; hundert sind schon ein
#: Belastungstest fürs Anordnen, und eine Zahl darüber ist ein Tippfehler,
#: keine Bestellung.
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
    """Namen, die auseinanderbleiben, ohne ein Rätsel zu werden.

    Eine Kopie heißt „Teil (Kopie)", wie eh und je. Mehrere werden nummeriert,
    denn zehn Objekte namens „Teil (Kopie)" sind eine Liste aus einem Ding,
    zehnmal.
    """
    base = chosen or f"{original} ({tr('Kopie')})"
    return base if count <= 2 else f"{base} {index - 1}"
