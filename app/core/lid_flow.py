"""Deckel erzeugen als Ablauf, nicht als einzelne Operation (Bauplan §14, §25).

Die Operation baut den Körper. Was ihr fehlte, ist das Paar: ein Deckel und
die Schachtel, in die er gehört, sind eine **Passung** — und die lebt im
Dokument, nicht in der Geometrie (§14). Ohne sie greifen die drei Regeln aus
``slice/advise.py`` nie, die genau für Passungen da sind: genaue Außenwand,
gebremste Beschleunigung, Bügeln. Ausgerechnet am Deckel, wo das Zusammenspiel
der Zweck ist, druckte Solidon also wie an jeder beliebigen Wand.

**Warum ein Ablauf und nicht die Operation selbst.** Eine Op bekommt ihre
Szene nur lesend (Regel 3), und die Auswertung ist eine reine Funktion
(§15.1): sie darf keine Passung ins Dokument schreiben, sonst käme bei jedem
Neurechnen eine dazu. Der Ablauf steht deshalb daneben, wie
``split.apply_split`` beim Verstiften — er wendet die Operation an und trägt
die Passung in derselben Transaktion ein, die auch die Geometrie gebracht hat.
Ein Undo nimmt beides zusammen zurück.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field

from app.core.geom.lid import CAVITY_FEATURE, COLLAR_FEATURE
from app.core.log import get_logger
from app.core.scene.history import History, OperationDraft, change_for
from app.core.types import (
    Document,
    FeatureRef,
    Finding,
    Fit,
    ObjectId,
    Origin,
    Profile,
    TransactionId,
)
from app.i18n import _

_log = get_logger(__name__)

#: Wie die Passung heißt, wenn sie die erste ihres Namens ist.
FIT_NAME = "deckel"


@dataclass(slots=True)
class LidApplied:
    """Was der Ablauf hinterlassen hat."""

    object_ids: list[ObjectId] = field(default_factory=list)
    fit: Fit | None = None
    transaction: TransactionId | None = None
    findings: list[Finding] = field(default_factory=list)


def unique_name(document: Document, wanted: str = FIT_NAME) -> str:
    """Ein Name, den es im Dokument noch nicht gibt.

    Eine Schachtel mit zwei Fächern bekommt zwei Deckel, und zwei Passungen
    desselben Namens wären eine, die die andere verdeckt.
    """
    taken = {fit.name for fit in document.fits}
    if wanted not in taken:
        return wanted
    number = 2
    while f"{wanted}_{number}" in taken:
        number += 1
    return f"{wanted}_{number}"


def apply_lid(
    document: Document,
    object_id: ObjectId,
    params: dict[str, object],
    profile: Profile,
    *,
    op: str = "create_lid",
    origin: Origin | None = None,
) -> LidApplied:
    """Erzeugt den Deckel und hält ihn als Passung fest (§14).

    Die Toleranz ist ein Verweis ins Materialprofil und nie die Zahl selbst
    (Regel 7) — dieselbe Entscheidung wie beim Verstiften, und aus demselben
    Grund: eine Kalibrierung nach §28.3 muss einen Deckel erreichen, der vor
    ihr entstanden ist.
    """
    history = History(document)
    applied = history.apply(
        _("Deckel erzeugen"),
        [OperationDraft(op=op, inputs=(object_id,), params=dict(params))],
        origin or Origin(by="user"),
    )

    made = document.ops[-1].outputs
    if len(made) < 2:
        # Die Operation hat keinen zweiten Körper geliefert — dann gibt es
        # nichts zu paaren, und ein Fit ins Leere wäre schlimmer als keiner.
        _log.info("lid flow: the operation produced %d output(s), no fit", len(made))
        return LidApplied(object_ids=list(made), transaction=applied.id)

    box_id, lid_id = made[0], made[1]
    fit = Fit(
        name=unique_name(document),
        a=FeatureRef(box_id, CAVITY_FEATURE),
        b=FeatureRef(lid_id, COLLAR_FEATURE),
        kind="clearance",
        tolerance=f"auto:{profile.material.id}",
    )
    # Die Passung gehört in dieselbe Transaktion wie die Geometrie: sie ist
    # keine Operation, also reist sie als DocumentChange mit (§15.5). Ohne das
    # ließe ein Undo den Deckel verschwinden und die Passung stehen — sie
    # zeigte dann auf ein Objekt, das es nicht mehr gibt.
    #
    # Nachgetragen und nicht mitgegeben, weil erst der Verlauf die Objekt-IDs
    # vergibt: vor ``apply`` gibt es nichts, worauf ein ``FeatureRef`` zeigen
    # könnte.
    changes = change_for(document, fits=[*document.fits, fit])
    document.fits.append(fit)
    document.transactions[-1] = dataclasses.replace(applied, changes=changes)

    _log.info("lid flow: %s ↔ %s as fit %s", box_id, lid_id, fit.name)
    return LidApplied(
        object_ids=list(made),
        fit=fit,
        transaction=applied.id,
        findings=[
            Finding(
                code="parts.lid_fit",
                severity="info",
                message=_(
                    "Deckel und Schachtel sind als Passung eingetragen — "
                    "der Slicer bekommt dafür die genauere Außenwand."
                ),
                values={"fit": fit.name, "tolerance": str(fit.tolerance)},
            )
        ],
    )


def features_of_lid() -> tuple[str, str]:
    """Die zwei Merkmalsnamen, auf die die Passung zeigt — für Tests und
    Oberfläche."""
    return CAVITY_FEATURE, COLLAR_FEATURE


__all__ = ["FIT_NAME", "LidApplied", "apply_lid", "features_of_lid", "unique_name"]
