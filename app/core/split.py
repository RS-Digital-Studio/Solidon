"""Auto split as a transaction (Bauplan §25, §14, §22.3).

The search decides *where* to cut; this decides *what goes on the stack*. One
``split_pinned`` operation per cut, in the order the search made them — so
every parting plane stays a number somebody can change afterwards, and one undo
takes the whole split back.

The fit pairs are made here too, and that is the reason this is not simply the
operation itself: fits live in the document (§14), evaluation is a pure
function and does not write to it (§15.1). Auto split is where pin and bore
meet, so it is where the pairs belong — §14 says as much.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.geom.autosplit import SplitOutcome, split_to_fit
from app.core.geom.mesh import MeshData
from app.core.geom.pins import PIN_COUNT
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
from app.i18n import tr

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SplitPlan:
    """What auto split would do, before anything is applied."""

    drafts: tuple[OperationDraft, ...]
    outcome: SplitOutcome

    @property
    def cuts(self) -> int:
        return len(self.drafts)


@dataclass(slots=True)
class SplitApplied:
    """What it did: the pieces, the fit pairs, and what is worth reporting."""

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
    """Search for the cuts and turn them into operations.

    The object ids the cuts apply to are not known yet — the history hands
    those out. What is known is the *order*, and that is enough: the input of
    the next cut is one of the two pieces the previous one made.
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
    """Cut until it fits, and record every seam as a fit pair (§14)."""
    plan = plan_split(mesh, object_id, profile, pins=pins)
    if not plan.drafts:
        return SplitApplied(object_ids=[object_id], findings=list(plan.outcome.findings))

    history = History(document)
    pieces: list[ObjectId] = [object_id]
    fits: list[Fit] = []
    transaction = None

    for step, draft in zip(plan.outcome.cuts, plan.drafts, strict=True):
        target = pieces[step.part_index]
        applied = history.apply(
            tr("Teilen und verstiften"),
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


def _pairs(
    first: ObjectId, second: ObjectId, pins: int, profile: Profile, made_so_far: int
) -> list[Fit]:
    """One pair per pin: the pin on one half, the bore on the other.

    The tolerance is a reference into the material profile, never the number
    itself (AGENTS.md rule 7) — a calibration afterwards has to reach a part
    that was split before it.
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
