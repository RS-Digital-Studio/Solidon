"""Ganze Zuordnungsentscheidungen geometrisch wiedererkennen und gemeinsam prüfen."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Set
from typing import Any

from app.core.errors import AmbiguityError
from app.core.perceive import matching
from app.core.perceive.match_records import group_key, validate_group
from app.core.types import Feature, FeatureId, ObjectId, Vec3
from app.i18n import _

type Claims = Mapping[FeatureId, tuple[FeatureId, ...]]
type Decisions = Mapping[FeatureId, FeatureId | None]


def _claimants(claims: Claims, check: Callable[[], None] | None) -> dict[FeatureId, set[FeatureId]]:
    """Liest jede Anspruchskante einmal, auch bei dichten Konkurrenzgruppen."""
    owners: dict[str, set[str]] = {}
    for old_id, candidates in claims.items():
        if check is not None:
            check()
        for candidate in candidates:
            owners.setdefault(candidate, set()).add(old_id)
    return owners


def conflict_groups(
    result: matching.MatchResult, *, check_cancelled: Callable[[], None] | None = None
) -> tuple[dict[FeatureId, tuple[FeatureId, ...]], ...]:
    """Gemeinsam beanspruchte Ziele bilden eine Fragegruppe, auch bei nur einem Ziel."""
    if check_cancelled is not None:
        check_cancelled()
    owners = _claimants(result.ambiguous, check_cancelled)
    pending = set(result.ambiguous)
    groups = []
    while pending:
        stack = [min(pending)]
        members: set[str] = set()
        visited_targets: set[str] = set()
        while stack:
            if check_cancelled is not None:
                check_cancelled()
            old_id = stack.pop()
            if old_id in members:
                continue
            members.add(old_id)
            pending.discard(old_id)
            for candidate in result.ambiguous[old_id]:
                if candidate not in visited_targets:
                    visited_targets.add(candidate)
                    stack.extend(owners[candidate])
        groups.append({name: result.ambiguous[name] for name in sorted(members)})
    return tuple(groups)


def mapping_with_decisions(
    result: matching.MatchResult,
    claims: Claims,
    decisions: Decisions,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, FeatureId]:
    """Prüft alle Entscheidungen vor der Übernahme; kein erstes oder letztes Ziel gewinnt."""
    if check_cancelled is not None:
        check_cancelled()
    if set(decisions) != set(claims):
        raise AmbiguityError(
            _("Ordne alle bisherigen Bezüge dieser Gruppe zu oder führe sie nicht weiter.")
        )
    if not any(
        dict(claims) == group for group in conflict_groups(result, check_cancelled=check_cancelled)
    ):
        raise AmbiguityError(
            _("Ordne alle bisherigen Bezüge dieser Gruppe zu oder führe sie nicht weiter.")
        )
    proposed = dict(result.mapping)
    occupied = set(proposed.values())
    if any(target in occupied for candidates in claims.values() for target in candidates):
        raise AmbiguityError(_("Die Zuordnung ist nicht mehr gültig. Wähle die Bezüge erneut aus."))
    for old_id, candidate in decisions.items():
        if check_cancelled is not None:
            check_cancelled()
        if old_id in proposed or (candidate is not None and candidate not in claims[old_id]):
            raise AmbiguityError(
                _("Die Zuordnung ist nicht mehr gültig. Wähle die Bezüge erneut aus.")
            )
        if candidate is not None:
            proposed[old_id] = candidate
    matching.require_injective(proposed)
    if check_cancelled is not None:
        check_cancelled()
    return proposed


def group_fingerprint(
    object_id: ObjectId,
    claims: Claims,
    decisions: Decisions,
    detected: Mapping[FeatureId, Feature],
    centre: Vec3,
    diagonal: float,
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Speichert den ganzen Anspruchsgraphen und die Wahl ohne aktuelle Erkennungsnamen."""
    if check_cancelled is not None:
        check_cancelled()
    mapping_with_decisions(
        matching.MatchResult(ambiguous=dict(claims)),
        claims,
        decisions,
        check_cancelled=check_cancelled,
    )
    owners = _claimants(claims, check_cancelled)
    targets = sorted(owners)
    indices = {name: index for index, name in enumerate(targets)}
    candidates = []
    for target in targets:
        if check_cancelled is not None:
            check_cancelled()
        feature = detected.get(target)
        if feature is None:
            raise AmbiguityError(
                _("Die Zuordnung ist nicht mehr gültig. Wähle die Bezüge erneut aus.")
            )
        candidates.append(
            {
                "fingerprint": matching.fingerprint(feature, centre, diagonal),
                "claims": sorted(owners[target]),
            }
        )
    record = {
        "object_id": object_id,
        "old_ids": sorted(claims),
        "candidates": candidates,
        "decisions": {
            name: {"not_carried": True} if target is None else {"candidate": indices[target]}
            for name, target in sorted(decisions.items())
        },
    }
    try:
        validate_group(
            group_key(object_id, claims), record, (object_id,), check_cancelled=check_cancelled
        )
    except ValueError as error:
        raise AmbiguityError(
            _("Die Zuordnung ist nicht mehr gültig. Wähle die Bezüge erneut aus.")
        ) from error
    if check_cancelled is not None:
        check_cancelled()
    return record


def resolve_group(
    saved: Mapping[str, Any],
    object_id: ObjectId,
    claims: Claims,
    detected: Mapping[FeatureId, Feature],
    centre: Vec3,
    diagonal: float,
    reserved_targets: Set[FeatureId] = frozenset(),
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[FeatureId, FeatureId | None] | None:
    """Eine ganze gespeicherte Wahl gilt gemeinsam oder verlangt eine neue Entscheidung."""
    if check_cancelled is not None:
        check_cancelled()
    try:
        validate_group(
            group_key(object_id, claims), saved, (object_id,), check_cancelled=check_cancelled
        )
    except ValueError:
        return None
    owners = _claimants(claims, check_cancelled)
    targets = tuple(sorted(owners))
    if any(target in reserved_targets for target in targets):
        return None
    records = saved["candidates"]
    if len(records) != len(targets):
        return None
    restored = []
    seen: set[str] = set()
    for record in records:
        if check_cancelled is not None:
            check_cancelled()
        target = matching.resolve(
            record["fingerprint"],
            targets,
            detected,
            centre,
            diagonal,
            check_cancelled=check_cancelled,
        )
        if target is None or target in seen or set(record["claims"]) != owners[target]:
            return None
        seen.add(target)
        restored.append(target)
    decisions = {
        name: None if choice.get("not_carried") is True else restored[choice["candidate"]]
        for name, choice in saved["decisions"].items()
    }
    if any(target in reserved_targets for target in decisions.values() if target is not None):
        return None
    if check_cancelled is not None:
        check_cancelled()
    return decisions
