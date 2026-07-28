"""Keeping feature identifiers stable across operations (Bauplan §21.2, §21.3).

After every operation the detection runs again, and the new features have to be
matched to the old ones — otherwise ``hole_3`` in step five is a different hole
than ``hole_3`` in step four, and every reference in the stack quietly rots.

Matching happens over a feature vector (kind, diameter, axis, position **in the
object's own frame**, neighbourhood) with the Hungarian method over the cost
matrix. Position is taken relative to the body, so moving the whole object does
not orphan every feature it has.

Three outcomes, and only one of them is quiet:

* one clear partner below the threshold — the identifier stays;
* no partner — orphaned;
* several equally good candidates — **ambiguous**, and that stops the chain and
  asks (§21.3). Guessing here would be worse than asking.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.core.log import get_logger
from app.core.types import Feature, FeatureId, Transform, Vec3
from app.core.units import EPS_GEOM

_log = get_logger(__name__)

#: How close the second best candidate may be before the match counts as
#: ambiguous, relative to the best cost.
AMBIGUITY_MARGIN = 0.25

#: Tolerances, one per part of the feature vector. Each part is divided by its
#: own tolerance, so a cost of 1.0 means "as far off as we still accept" no
#: matter which part it came from.
POSITION_TOLERANCE = 0.08
"""Share of the model diagonal a feature may have travelled."""
DIAMETER_TOLERANCE = 0.15
"""Relative change in diameter — a bore can be widened and stay itself."""
AXIS_TOLERANCE = 0.3
"""Length of the difference between the unit axes, roughly 17 degrees."""

#: Everything below this counts as the same feature.
MATCH_THRESHOLD = 1.0

#: What a mismatch in kind costs: more than anything else can add up to.
KIND_PENALTY = 1e6


@dataclass(slots=True)
class MatchResult:
    """Who became whom, and what could not be decided."""

    mapping: dict[FeatureId, FeatureId] = field(default_factory=dict)
    """Old identifier to new identifier."""
    orphaned: tuple[FeatureId, ...] = ()
    """Old features with no partner (§21.2)."""
    ambiguous: dict[FeatureId, tuple[FeatureId, ...]] = field(default_factory=dict)
    """Old features with several equally good candidates — these get asked about."""
    fresh: tuple[FeatureId, ...] = ()
    """New features nobody was expecting."""

    @property
    def settled(self) -> bool:
        """True when nothing needs a decision from the user."""
        return not self.ambiguous and not self.orphaned


def feature_vector(feature: Feature, centre: Vec3, diagonal: float) -> np.ndarray:
    """Position relative to the body, plus what the feature is."""
    params = feature.params
    position = np.asarray(params.get("centre", (0.0, 0.0, 0.0)), dtype=float)
    relative = (position - np.asarray(centre, dtype=float)) / max(diagonal, EPS_GEOM)
    axis = np.asarray(params.get("axis", params.get("normal", (0.0, 0.0, 0.0))), dtype=float)
    diameter = float(params.get("diameter", params.get("area", 0.0)))
    return np.concatenate([relative, axis, [diameter]])


def cost(
    first: Feature,
    second: Feature,
    first_centre: Vec3,
    second_centre: Vec3,
    diagonal: float,
) -> float:
    """What it would cost to call these two the same feature.

    Each body is measured in its own frame, so moving the whole object leaves
    every cost untouched — otherwise a translation would orphan everything.
    """
    if first.kind != second.kind:
        return KIND_PENALTY

    one = feature_vector(first, first_centre, diagonal)
    two = feature_vector(second, second_centre, diagonal)

    position = float(np.linalg.norm(one[:3] - two[:3])) / POSITION_TOLERANCE
    axis = float(np.linalg.norm(one[3:6] - two[3:6])) / AXIS_TOLERANCE
    scale = max(abs(float(one[6])), abs(float(two[6])), EPS_GEOM)
    diameter = abs(float(one[6]) - float(two[6])) / scale / DIAMETER_TOLERANCE
    return float(position + axis + diameter)


def match(
    old: dict[FeatureId, Feature],
    new: dict[FeatureId, Feature],
    centre: Vec3,
    diagonal: float,
    old_centre: Vec3 | None = None,
) -> MatchResult:
    """Assign new features to old identifiers, and say what stayed open.

    ``centre`` is the new body's frame; ``old_centre`` the one the old features
    were measured in, defaulting to the same.
    """
    if not old:
        return MatchResult(fresh=tuple(new))
    if not new:
        return MatchResult(orphaned=tuple(old))

    before = old_centre if old_centre is not None else centre
    old_ids = list(old)
    new_ids = list(new)
    matrix = np.array(
        [[cost(old[a], new[b], before, centre, diagonal) for b in new_ids] for a in old_ids],
        dtype=float,
    )
    threshold = MATCH_THRESHOLD

    rows, columns = linear_sum_assignment(matrix)
    result = MatchResult()
    taken: set[str] = set()

    for row, column in zip(rows, columns, strict=True):
        old_id = old_ids[row]
        best = float(matrix[row, column])
        if best > threshold:
            result.orphaned = (*result.orphaned, old_id)
            continue

        rivals = [
            new_ids[other]
            for other in range(len(new_ids))
            if other != column
            and float(matrix[row, other]) <= max(best * (1 + AMBIGUITY_MARGIN), threshold)
        ]
        if rivals:
            # §21.3: several dense candidates — stop and ask instead of guessing.
            result.ambiguous[old_id] = (new_ids[column], *rivals)
            continue

        result.mapping[old_id] = new_ids[column]
        taken.add(new_ids[column])

    unmatched = [identifier for identifier in old_ids if identifier not in result.mapping]
    result.orphaned = tuple(
        identifier
        for identifier in unmatched
        if identifier not in result.ambiguous and identifier not in result.orphaned
    ) + tuple(entry for entry in result.orphaned)
    result.fresh = tuple(identifier for identifier in new_ids if identifier not in taken)

    if result.ambiguous:
        _log.info("feature matching left %d ambiguous", len(result.ambiguous))
    return result


def apply_mapping(new: dict[FeatureId, Feature], result: MatchResult) -> dict[FeatureId, Feature]:
    """Rename the new features onto the old identifiers that survived."""
    renamed: dict[FeatureId, Feature] = {}
    reverse = {value: key for key, value in result.mapping.items()}
    for identifier, feature in new.items():
        target = reverse.get(identifier, identifier)
        renamed[target] = Feature(
            id=target,
            kind=feature.kind,
            provenance=feature.provenance,
            params=feature.params,
            face_indices=feature.face_indices,
        )
    return renamed


def question_for(old_id: FeatureId, candidates: tuple[FeatureId, ...]) -> tuple[str, list[str]]:
    """The question the core asks when a feature cannot be told apart (§21.3)."""
    from app.i18n import tr

    return (
        tr("Welches Merkmal entspricht {name}?").replace("{name}", old_id),
        [*candidates, tr("Verwerfen")],
    )


def moved_features(
    features: dict[FeatureId, Feature], transform: Transform
) -> dict[FeatureId, Feature]:
    """Carry features along a rigid motion the operation reported (§21.2).

    Only the parts that live in space are touched: the point a feature sits at
    and the direction it points in. A diameter does not move, and an area is not
    a place. Without this a rotation would orphan every feature on the body —
    not because it disappeared, but because it is somewhere else now.
    """
    matrix = np.asarray(transform, dtype=float)
    turn = matrix[:3, :3]
    moved: dict[FeatureId, Feature] = {}
    for identifier, feature in features.items():
        params = dict(feature.params)
        for key in ("centre", "position"):
            if key in params:
                point = np.asarray(params[key], dtype=float)
                carried = matrix @ np.array([*point, 1.0])
                params[key] = (float(carried[0]), float(carried[1]), float(carried[2]))
        for key in ("axis", "normal"):
            if key in params:
                direction = turn @ np.asarray(params[key], dtype=float)
                length = float(np.linalg.norm(direction))
                if length > EPS_GEOM:
                    direction = direction / length
                params[key] = (float(direction[0]), float(direction[1]), float(direction[2]))
        moved[identifier] = Feature(
            id=feature.id,
            kind=feature.kind,
            provenance=feature.provenance,
            params=params,
            face_indices=feature.face_indices,
        )
    return moved
