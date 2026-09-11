"""Farb-Operationen (Bauplan §25, Kategorie „Farbe").

Ein Filament zuweisen, sicher abwählen oder eine Textur auf die eingelegten
Filamente vereinfachen. Eine erkannte Fläche färbt die Operation
``paint_slot`` in :mod:`app.core.geom.prepare_ops`; einen punktfesten Pinsel
gibt es seit Formatversion 14 nicht mehr.
"""

from __future__ import annotations

import dataclasses
import re
from typing import cast

from app.core.errors import ValidationError
from app.core.geom.attributes import counts, with_slot
from app.core.geom.mesh import as_mesh_data
from app.core.geom.texture import to_slots
from app.core.knowledge.filaments import profile_name
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import MAX_SLOTS, BaseParams, Finding, MaterialSlot, OpContext, OpResult
from app.i18n import _

_log = get_logger(__name__)

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


@op_params
class AssignSlotParams(BaseParams):
    slot: int = param(
        title=_("Filament"),
        default=0,
        minimum=0,
        maximum=MAX_SLOTS - 1,
        kind="filament",
        doc=_("Das Filament, das dem ganzen Objekt zugewiesen wird."),
    )
    name: str = param(
        title=_("Bezeichnung"),
        default="",
        doc=_("Wie das Filament heißt. Leer nimmt „Filament“ und die Nummer."),
    )
    colour: str = param(
        title=_("Farbe"),
        default="",
        doc=_("Anzeigefarbe als #RRGGBB. Nur zur Ansicht — gedruckt wird, was eingelegt ist."),
    )
    material_type: str = param(
        title=_("Typ"),
        default="",
        placement="advanced",
        doc=_("Materialart des Filaments, etwa PLA oder PETG."),
    )
    slicer_profile: str = param(
        title=_("Slicer-Profil"),
        default="",
        placement="advanced",
        doc=_("Herstellerprofil, aus dem der Slicer die Druckwerte dieser Spule übernimmt."),
    )


@register_op(
    name="assign_slot",
    title=_("Filament zuweisen"),
    category="colour",
    params=AssignSlotParams,
    consumes=1,
    produces=1,
    doc=_(
        "Ordnet dem ganzen Objekt ein Filament zu. Mehrfarbig wird ein Teil, "
        "indem verschieden zugewiesene Körper vereinigt werden."
    ),
)
def assign_slot(ctx: OpContext) -> OpResult:
    params = cast(AssignSlotParams, ctx.params)
    source = ctx.inputs[0]
    slot = MaterialSlot(
        index=params.slot,
        # **Kein ``.translate()``.** Das machte aus dem Wort eine feste
        # Zeichenkette in der Sprache, die beim Rechnen eingestellt war — und
        # der Ergebnis-Cache kennt die Sprache nicht, also blieb sie stehen.
        # Der Text trägt seine Zahl jetzt selbst und wird erst beim Anzeigen
        # aufgelöst.
        name=params.name or _("Slot {number}", number=params.slot),
        colour=colour_from(params.colour),
        material=profile_name(params.slicer_profile) or None,
        material_type=params.material_type or None,
    )
    painted = with_slot(as_mesh_data(source.mesh), params.slot)
    return OpResult(
        outputs=[
            dataclasses.replace(
                source, mesh=painted, material_slots=merged_slots(source.material_slots, [slot])
            )
        ]
    )


@op_params
class ClearFilamentParams(BaseParams):
    at_features: tuple[str, ...] = param(
        title=_("Flächen"),
        default=(),
        kind="features",
        doc=_("Die Flächen, deren Filament entfernt wird. Leer entfernt es am ganzen Körper."),
    )
    at_feature: str = param(
        title=_("Fläche"),
        default="",
        kind="feature",
        doc=_("Die Fläche, deren Filament abgewählt wird. Leer wählt es am ganzen Körper ab."),
    )


@register_op(
    name="clear_filament",
    title=_("Filament entfernen"),
    category="colour",
    params=ClearFilamentParams,
    consumes=1,
    produces=1,
    applies_to=["face", "curved_face"],
    doc=_(
        "Entfernt die Filamentzuweisung am Körper oder an einer Fläche. "
        "Die übrigen Flächen behalten ihr Filament; die Geometrie bleibt unverändert."
    ),
)
def clear_filament(ctx: OpContext) -> OpResult:
    """Slot null wird neutral, ohne seine weiter benutzte Definition zu verlieren."""
    from app.core.export.threemf import slots_for_object
    from app.core.geom.paint import fill_feature
    from app.core.perceive.actions import reason_against

    params = cast(ClearFilamentParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)
    feature_ids = tuple(
        dict.fromkeys((*params.at_features, *((params.at_feature,) if params.at_feature else ())))
    )
    if not feature_ids:
        return OpResult(
            outputs=[
                dataclasses.replace(
                    source,
                    mesh=dataclasses.replace(mesh, slots=()),
                    material_slots=[],
                    material=None,
                )
            ]
        )
    field_name = "at_features" if params.at_features else "at_feature"
    selected: set[int] = set()
    for feature_id in feature_ids:
        feature = source.features.get(feature_id)
        if feature is None:
            raise ValidationError(
                title=_("Dieses Merkmal gibt es am Körper nicht."),
                field=field_name,
                constraint="unknown_feature",
                detail=_(
                    "Wählen Sie eine vorhandene Fläche oder wählen Sie das Filament "
                    "am ganzen Körper ab."
                ),
            )
        reason = reason_against("clear_filament", feature.kind)
        if reason is not None:
            raise ValidationError(field=field_name, constraint="feature_kind", detail=reason)
        indices = {index for index in feature.face_indices if 0 <= index < mesh.triangle_count}
        if not indices:
            raise ValidationError(
                field=field_name,
                constraint="empty_feature",
                detail=_(
                    "Wählen Sie eine vorhandene Fläche oder wählen Sie das Filament "
                    "am ganzen Körper ab."
                ),
            )
        selected.update(indices)
    stroke = fill_feature(mesh, tuple(sorted(selected)), 0)
    before = mesh.slots or (0,) * mesh.triangle_count
    outside = {slot for index, slot in enumerate(before) if index not in selected}
    definitions = {slot.index: slot for slot in slots_for_object(source)}
    after = list(stroke.mesh.slots)
    zero = definitions.pop(0, None)
    if zero is not None and 0 in outside:
        # Eine bereits benutzte identische Definition braucht keinen weiteren
        # Platz. Sonst zählen nur nach der Abwahl noch belegte Dreiecke.
        replacement = next(
            (
                slot.index
                for slot in definitions.values()
                if slot.index in outside and dataclasses.replace(zero, index=slot.index) == slot
            ),
            None,
        )
        if replacement is None:
            replacement = next(
                (index for index in range(1, MAX_SLOTS) if index not in outside), None
            )
        if replacement is None:
            raise ValidationError(
                field=field_name,
                constraint="slots_full",
                detail=_(
                    "Alle acht Filamentplätze bleiben belegt. Wählen Sie sämtliche Flächen eines "
                    "Filaments oder den ganzen Körper ab, damit die übrigen Flächen "
                    "ihr Filament behalten."
                ),
            )
        definitions[replacement] = dataclasses.replace(zero, index=replacement)
        for index, slot in enumerate(before):
            if slot == 0 and index not in selected:
                after[index] = replacement
    used = set(after)
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=dataclasses.replace(mesh, slots=tuple(after)),
                material=None,
                material_slots=[
                    definitions[index] for index in sorted(definitions) if index in used
                ],
            )
        ]
    )


def colour_from(text: str) -> tuple[float, float, float] | None:
    """``#RRGGBB`` als drei Zahlen, und ein klarer Fehler für alles andere.

    Öffentlich, seit die Füllung (``paint_slot``) dieselbe Farbe annimmt:
    Zwei Umrechnungen für ein Format wären zwei Gelegenheiten,
    auseinanderzulaufen — und die Fehlermeldung soll in beiden Fällen
    derselbe Satz sein.
    """
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
    title=_("Textur in Filamente umrechnen"),
    category="colour",
    params=SlotsFromTextureParams,
    consumes=1,
    produces=1,
    deterministic=False,
    doc=_(
        "Rechnet die Textur eines Objekts auf die Anzahl eingelegter Filamente um "
        "und speichert das Ergebnis als Filamentzuweisung."
    ),
)
def slots_from_texture(ctx: OpContext) -> OpResult:
    """§20, und der Satz, der dazugehört: nie so fein wie die Darstellung.

    Der Startwert kommt aus der Operation, nicht aus einem eigenen Parameter:
    §11.3 führt ohnehin bei jedem randomisierten Schritt einen mit, und genau
    das lässt die Quantisierung sich wiederholen, wenn die Datei erneut
    geöffnet wird.
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
                source, mesh=mesh, material_slots=merged_slots(source.material_slots, slots)
            )
        ],
        findings=findings,
    )


def merged_slots(existing: list[MaterialSlot], added: list[MaterialSlot]) -> list[MaterialSlot]:
    """Neue Zuweisungen gewinnen; Slots, die das Objekt schon kannte und
    weiter benutzt, bleiben.
    """
    known = {entry.index: entry for entry in existing}
    known.update({entry.index: entry for entry in added})
    return [known[index] for index in sorted(known)]
