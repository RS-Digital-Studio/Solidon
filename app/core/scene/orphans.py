"""Feature references that lost their feature (Bauplan §21.3).

Identifiers are stable while a session runs (§21.2), but a project file outlives
the session it was made in: the mesh was replaced, the operation before it was
edited, the parts library changed. Then a fit points at ``hole_3`` and there is
no ``hole_3`` any more.

The rule is the same one the whole application follows: **do not guess**. Every
reference in an opened file is checked once, and what cannot be resolved is put
to the user with the candidates in hand. Their answer is written back into the
document, so the question is asked once and not on every evaluation.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.log import get_logger
from app.core.types import Document, Feature, FeatureRef, Finding, Scene
from app.i18n import _, tr

_log = get_logger(__name__)

#: Answer that drops the fit instead of pointing it somewhere else.
REMOVE_CHOICE = "-"


@dataclass(slots=True)
class Reference:
    """One place in the document that names a feature."""

    where: str
    """``fit:stift_1:a`` — enough to write the answer back."""
    ref: FeatureRef

    @property
    def fit_name(self) -> str:
        return self.where.split(":")[1]

    @property
    def side(self) -> str:
        return self.where.split(":")[2]


@dataclass(slots=True)
class CheckResult:
    """What the check found and what it changed."""

    findings: list[Finding] = field(default_factory=list)
    rewritten: int = 0
    removed: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.rewritten or self.removed)


def references(document: Document) -> list[Reference]:
    """Every feature reference the document holds.

    Today that is the fits (§14). Operations carry coordinates, not feature ids;
    when one of them starts to reference a feature it is listed here too, and the
    check works unchanged.
    """
    found: list[Reference] = []
    for fit in document.fits:
        found.append(Reference(f"fit:{fit.name}:a", fit.a))
        found.append(Reference(f"fit:{fit.name}:b", fit.b))
    return found


def check(document: Document, scene: Scene, ask: Any) -> CheckResult:
    """Resolve every reference once, asking where the answer is not obvious (§21.3)."""
    result = CheckResult()
    for reference in references(document):
        if _resolves(scene, reference.ref):
            continue
        candidates = _candidates(scene, reference.ref)
        if not candidates:
            result.findings.append(_lost(reference, None))
            continue

        question, choices = question_for(reference, candidates)
        answer = ask(question, choices)
        if answer in candidates:
            _rewrite(document, reference, answer)
            result.rewritten += 1
            result.findings.append(_rewritten_finding(reference, answer))
        else:
            _remove(document, reference)
            result.removed += 1
            result.findings.append(_lost(reference, reference.fit_name))
    if result.changed:
        _log.info("orphan check rewrote %d and removed %d", result.rewritten, result.removed)
    return result


def _resolves(scene: Scene, reference: FeatureRef) -> bool:
    entry = scene.objects.get(reference.object_id)
    return entry is not None and reference.feature_id in entry.features


def _candidates(scene: Scene, reference: FeatureRef) -> list[str]:
    """Features of the same kind on the same object — the plausible successors."""
    entry = scene.objects.get(reference.object_id)
    if entry is None:
        return []
    wanted = _kind_of(reference.feature_id)
    return sorted(
        feature_id
        for feature_id, feature in entry.features.items()
        if wanted is None or feature.kind == wanted
    )


def _kind_of(feature_id: str) -> str | None:
    """``hole_3`` names a hole. The prefix is the naming rule from §21.1."""
    for kind in ("hole", "face", "edge_loop", "pin", "slot", "thread"):
        if feature_id.startswith(f"{kind}_"):
            return kind
    return None


def question_for(reference: Reference, candidates: Sequence[str]) -> tuple[str, list[str]]:
    """The question and its answers, with dropping the fit as the last resort."""
    question = (
        f"{tr('Dieser Verweis zeigt ins Leere:')} {reference.ref}. "
        f"{tr('Welches Merkmal ist gemeint?')}"
    )
    return question, [*candidates, REMOVE_CHOICE]


def _rewrite(document: Document, reference: Reference, feature_id: str) -> None:
    """Point the fit at the chosen feature — the answer is given once, not daily."""
    for index, fit in enumerate(document.fits):
        if fit.name != reference.fit_name:
            continue
        replacement = FeatureRef(reference.ref.object_id, feature_id)
        document.fits[index] = (
            dataclasses.replace(fit, a=replacement)
            if reference.side == "a"
            else dataclasses.replace(fit, b=replacement)
        )
        return


def _remove(document: Document, reference: Reference) -> None:
    document.fits[:] = [fit for fit in document.fits if fit.name != reference.fit_name]


def _rewritten_finding(reference: Reference, feature_id: str) -> Finding:
    return Finding(
        code="feature.rewritten",
        severity="info",
        message=_("Ein Verweis wurde auf ein anderes Merkmal umgeschrieben."),
        object_id=reference.ref.object_id,
        feature_ids=(feature_id,),
        values={"from": reference.ref.feature_id, "to": feature_id, "fit": reference.fit_name},
    )


def _lost(reference: Reference, removed_fit: str | None) -> Finding:
    return Finding(
        code="feature.orphaned",
        severity="warning" if removed_fit else "error",
        message=_("Ein Verweis zeigt auf ein Merkmal, das es nicht mehr gibt."),
        object_id=reference.ref.object_id,
        feature_ids=(reference.ref.feature_id,),
        values={"reference": str(reference.ref), "fit": reference.fit_name},
    )


def candidates_of(scene: Scene, reference: FeatureRef) -> dict[str, Feature]:
    """The candidate features themselves — the surface highlights them (§21.3)."""
    entry = scene.objects.get(reference.object_id)
    if entry is None:
        return {}
    return {name: entry.features[name] for name in _candidates(scene, reference)}
