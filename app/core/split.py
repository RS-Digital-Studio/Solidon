"""Auto Split als Transaktion (Bauplan §25, §14, §22.3).

Die Suche entscheidet, *wo* geschnitten wird; hier entscheidet sich, *was auf
den Stapel kommt*. Eine ``split_pinned``-Operation je Schnitt, in der
Reihenfolge, in der die Suche sie gemacht hat — so bleibt jede Trennebene eine
Zahl, die jemand nachträglich ändern kann, und ein Undo nimmt die ganze
Teilung zurück.

Die Passungspaare entstehen auch hier, und das ist der Grund, warum das nicht
einfach die Operation selbst ist: Passungen leben im Dokument (§14), die
Auswertung ist eine reine Funktion und schreibt nicht hinein (§15.1). Auto
Split ist die Stelle, an der Stift und Bohrung sich treffen, also gehören die
Paare hierher — §14 sagt genau das.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.geom.autosplit import SplitOutcome, split_to_fit
from app.core.geom.mesh import MeshData
from app.core.geom.pins import PIN_COUNT
from app.core.geom.section import SectionPlane
from app.core.log import get_logger
from app.core.scene.history import History, OperationDraft
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


@dataclass(frozen=True, slots=True)
class SplitPlan:
    """Was Auto Split tun würde, bevor irgendetwas angewandt ist."""

    drafts: tuple[OperationDraft, ...]
    outcome: SplitOutcome

    @property
    def cuts(self) -> int:
        return len(self.drafts)


@dataclass(slots=True)
class SplitApplied:
    """Was es getan hat: die Stücke, die Passungspaare, und was zu melden ist."""

    object_ids: list[ObjectId]
    fits: list[Fit] = field(default_factory=list)
    transaction: TransactionId | None = None
    findings: list[Finding] = field(default_factory=list)


def plan_split(
    mesh: MeshData,
    object_id: ObjectId,
    profile: Profile,
    *,
    pins: int = PIN_COUNT,
) -> SplitPlan:
    """Sucht die Schnitte und macht Operationen daraus.

    Die Objekt-IDs, auf die die Schnitte wirken, sind noch nicht bekannt — die
    vergibt der Verlauf. Bekannt ist die *Reihenfolge*, und die genügt: die
    Eingabe des nächsten Schnitts ist eines der zwei Stücke, die der vorige
    gemacht hat.
    """
    outcome = split_to_fit(mesh, profile)
    drafts = [
        OperationDraft(
            op="split_pinned",
            inputs=(object_id,),
            params={"axis": step.plane.axis, "position": step.plane.position, "pins": pins},
        )
        for step in outcome.cuts
    ]
    return SplitPlan(drafts=tuple(drafts), outcome=outcome)


def apply_split(
    document: Document,
    mesh: MeshData,
    object_id: ObjectId,
    profile: Profile,
    *,
    pins: int = PIN_COUNT,
) -> SplitApplied:
    """Schneidet, bis es passt, und hält jede Naht als Passungspaar fest (§14)."""
    plan = plan_split(mesh, object_id, profile, pins=pins)
    return apply_planned(document, plan, object_id, profile, pins=pins)


def apply_planned(
    document: Document,
    plan: SplitPlan,
    object_id: ObjectId,
    profile: Profile,
    *,
    pins: int = PIN_COUNT,
) -> SplitApplied:
    """Wendet einen fertigen Plan an — getrennt vom Suchen.

    Die Suche ist der teure Teil (Schichtanalysen über jede Kandidatenebene)
    und darf abseits des Oberflächen-Threads laufen (§2.8). Das Anwenden
    mutiert das Dokument und gehört in den Thread, dem das Dokument gehört —
    deshalb sind es zwei Funktionen und nicht eine mit einem Schalter.
    """
    if not plan.drafts:
        return SplitApplied(object_ids=[object_id], findings=list(plan.outcome.findings))

    history = History(document)
    pieces: list[ObjectId] = [object_id]
    fits: list[Fit] = []
    transaction = None

    for step, draft in zip(plan.outcome.cuts, plan.drafts, strict=True):
        target = pieces[step.part_index]
        applied = history.apply(
            _("Teilen und verstiften"),
            [OperationDraft(op=draft.op, inputs=(target,), params=dict(draft.params))],
            Origin(by="user"),
        )
        transaction = applied.id
        made = document.ops[-1].outputs
        pieces[step.part_index : step.part_index + 1] = list(made)
        fits.extend(_pairs(made[0], made[1], pins, profile, len(fits)))

    document.fits.extend(fits)
    _log.info("split into %d part(s) with %d fit pair(s)", len(pieces), len(fits))
    return SplitApplied(
        object_ids=pieces,
        fits=fits,
        transaction=transaction,
        findings=list(plan.outcome.findings),
    )


def apply_line_split(
    document: Document,
    object_id: ObjectId,
    plane: SectionPlane,
    profile: Profile,
    *,
    pins: int = PIN_COUNT,
) -> SplitApplied:
    """Ein einzelner Schnitt an einer gezeichneten Linie — mit Passungspaaren.

    Warum das nicht die Operation selbst tut, steht im Modulkopf: Passungen
    leben im Dokument, die Auswertung schreibt nicht hinein. Der Unterschied zu
    Auto Split ist nur die Zahl der Schnitte — einer, den jemand gezeigt hat,
    statt so vieler, wie der Bauraum verlangt.
    """
    history = History(document)
    applied = history.apply(
        _("An gezeichneter Linie trennen"),
        [
            OperationDraft(
                op="split_line",
                inputs=(object_id,),
                params={
                    "normal_x": plane.normal[0],
                    "normal_y": plane.normal[1],
                    "normal_z": plane.normal[2],
                    "position": plane.position,
                    "pins": pins,
                },
            )
        ],
        Origin(by="user"),
    )
    made = document.ops[-1].outputs
    fits = _pairs(made[0], made[1], pins, profile, 0) if pins else []
    document.fits.extend(fits)
    _log.info("split along a drawn line into %d part(s)", len(made))
    return SplitApplied(object_ids=list(made), fits=fits, transaction=applied.id)


def _pairs(
    first: ObjectId, second: ObjectId, pins: int, profile: Profile, made_so_far: int
) -> list[Fit]:
    """Ein Paar je Stift: der Stift auf der einen Hälfte, die Bohrung auf der
    anderen.

    Die Toleranz ist ein Verweis ins Materialprofil, nie die Zahl selbst
    (AGENTS.md Regel 7) — eine Kalibrierung danach muss ein Teil erreichen,
    das vor ihr geteilt wurde.
    """
    return [
        Fit(
            name=f"stift_{made_so_far + index}",
            a=FeatureRef(first, f"pin_{index}"),
            b=FeatureRef(second, f"bore_{index}"),
            kind="clearance",
            tolerance=f"auto:{profile.material.id}",
        )
        for index in range(1, pins + 1)
    ]
