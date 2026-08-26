"""Flächen in ein Filament färben (Bauplan §20, Konzept Filamente).

Bis zum 26.08.2026 stand hier ein Pinsel: ein Radius um einen Klickpunkt, mit
Kantenerkennung als Grenze. Robert hat ihn ersetzt — eine Anwendung, die ihre
Flächen beim Namen kennt, malt nicht um Punkte: Ein Klick auf „Oberseite"
färbt die Oberseite, und die Grenze der Fläche hat die Erkennung schon
gezogen (``Feature.face_indices``). Die Füllung ist damit merkmalsstabil:
Ändert ein früherer Schritt die Maße, wandert sie mit — ein gespeicherter
Punkt läge daneben (§21). Alte Punkt-Schritte bleiben in ihren Dateien stehen
und halten beim Auswerten ehrlich an (Migration 13 → 14).

Die andere Hälfte von §20 — Textur zu Slots — steht in
:mod:`app.core.geom.texture`. Das ganze Teil färbt ``assign_slot``
(:mod:`app.core.geom.colour_ops`).
"""

from __future__ import annotations

import dataclasses
from typing import cast

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.log import get_logger
from app.core.registry import op_params, param, register_op
from app.core.types import BaseParams, Finding, MaterialSlot, OpContext, OpResult
from app.i18n import _

_log = get_logger(__name__)

#: Wie viele Filamente eine Slotnummer benennen darf (§20, wie bei den
#: Farb-Operationen).
MAX_SLOTS = 8


@dataclasses.dataclass(frozen=True, slots=True)
class BrushResult:
    """Der gefärbte Körper und wie viele Dreiecke der Strich wirklich traf.

    Getrennt, weil die zweite Zahl nirgends sonst herkommt: Wie viele Dreiecke
    am Ende in einem Slot sitzen, sagt :func:`app.core.geom.attributes.counts`
    — aber das ist der **Bestand** und nicht der Strich. Bei Slot 0 sind die
    beiden Zahlen so weit auseinander, wie sie nur sein können: Ein Netz ohne
    Slots gilt ganz als Slot 0, also meldete eine leere Füllung sonst die
    volle Dreieckszahl als Erfolg.
    """

    mesh: MeshData
    painted: int


def fill_feature(mesh: MeshData, indices: tuple[int, ...], slot: int) -> BrushResult:
    """Färbt genau die Dreiecke eines Merkmals — die Füllung des
    Filament-Konzepts (26.08.2026).

    Kein Lauf über Nachbarn, kein Radius, kein Kantenwinkel: Die Erkennung hat
    die Grenze der Fläche schon gezogen (``Feature.face_indices``), und sie
    noch einmal zu suchen hieße, eine zweite Antwort auf eine beantwortete
    Frage zu riskieren. Indizes außerhalb des Netzes werden übergangen statt
    zu werfen — ein Merkmal einer früheren Auswertung kann mehr Dreiecke
    kennen, als das Netz nach einer Änderung noch hat, und der Rest der
    Fläche ist dann immer noch gemeint.
    """
    body = mesh.raw
    faces = len(body.faces)
    reached = [int(index) for index in indices if 0 <= int(index) < faces]
    if not reached:
        return BrushResult(mesh=mesh, painted=0)
    slots = list(mesh.slots) if mesh.slots else [0] * faces
    for index in reached:
        slots[index] = int(slot)
    _log.info("filled %d of %d faces into slot %d", len(reached), faces, slot)
    return BrushResult(mesh=MeshData(raw=body, slots=tuple(slots)), painted=len(reached))


@op_params
class PaintParams(BaseParams):
    slot: int = param(
        title=_("Slot"),
        default=1,
        minimum=0,
        maximum=MAX_SLOTS - 1,
        doc=_("In welchen Materialslot der Pinsel malt."),
    )
    at_feature: str = param(
        title=_("Fläche"),
        default="",
        # Die Art, nicht nur der Name: ``kind="feature"`` ist die eine Frage,
        # nach der Dialog-Combo, Klick-Vorbelegung (``values_for``, §21.3)
        # und der Cache-Schlüssel der Auswertung dieses Feld erkennen — und
        # ``test_a_feature_parameter_is_declared_as_one`` hält sie fest.
        kind="feature",
        doc=_(
            "Die erkannte Fläche, die vollständig gefärbt wird — gesetzt vom Klick auf das Merkmal."
        ),
    )
    name: str = param(
        title=_("Bezeichnung"),
        default="",
        placement="advanced",
        doc=_("Name des Slots, etwa das Filament. Erscheint im 3MF beim Farbwechsel."),
    )


@register_op(
    name="paint_slot",
    title=_("Bemalen"),
    category="colour",
    params=PaintParams,
    consumes=1,
    produces=1,
    applies_to=["face"],
    doc=_(
        "Färbt eine erkannte Fläche vollständig in ein Filament. Die Grenze "
        "der Fläche kommt aus der Erkennung — kein Pinsel, kein Radius."
    ),
)
def paint_slot(ctx: OpContext) -> OpResult:
    params = cast(PaintParams, ctx.params)
    source = ctx.inputs[0]
    mesh = as_mesh_data(source.mesh)

    # **Nur noch die Füllung** (Konzept Filamente, 26.08.2026): Ein Klick auf
    # „Oberseite" färbt die Oberseite — die Dreiecke kommen aus dem Merkmal.
    # Damit wandert die Färbung mit, wenn ein früherer Schritt die Maße
    # ändert; der Punkt-Radius-Pinsel, der hier bis v13 stand, konnte das
    # nicht und ist mit dem Format 14 entfallen.
    if not params.at_feature:
        raise ValidationError(
            title=_("Zum Färben gehört eine Fläche."),
            field="at_feature",
            detail=_(
                "Klicken Sie das Merkmal an, das gefärbt werden soll — oder "
                "färben Sie über das Kontextmenü das ganze Teil."
            ),
            value=params.at_feature,
            constraint="empty",
        )
    feature = source.features.get(params.at_feature)
    if feature is None:
        raise ValidationError(
            title=_("Dieses Merkmal gibt es am Körper nicht."),
            field="at_feature",
            detail=_(
                "Die Fläche wurde nicht gefunden — vielleicht hat ein "
                "früherer Schritt sie verändert. Wählen Sie sie neu, oder "
                "färben Sie das ganze Teil."
            ),
            value=params.at_feature,
            constraint="unknown_feature",
            values={"feature": params.at_feature},
        )
    stroke = fill_feature(mesh, feature.face_indices, params.slot)
    covered = stroke.painted
    if not covered:
        return OpResult(
            outputs=[source],
            findings=[
                Finding(
                    code="colour.nothing_painted",
                    severity="warning",
                    message=_("Dieses Merkmal hat keine eigene Fläche zu färben."),
                    object_id=source.id,
                    values={"feature": params.at_feature},
                )
            ],
        )

    known = {entry.index: entry for entry in source.material_slots}
    known.setdefault(
        params.slot,
        MaterialSlot(
            index=params.slot, name=params.name or f"{_('Slot').translate()} {params.slot}"
        ),
    )
    return OpResult(
        outputs=[
            dataclasses.replace(
                source,
                mesh=stroke.mesh,
                material_slots=[known[index] for index in sorted(known)],
            )
        ],
        findings=[
            Finding(
                code="colour.painted",
                severity="info",
                message=_("Die Fläche wurde bemalt."),
                object_id=source.id,
                values={"faces": covered, "slot": params.slot},
            )
        ],
    )
