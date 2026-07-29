"""What a change added and what it removed (Bauplan §18.7).

The difference view is called the most important view in the application (§19.1),
and it earns that by answering one question: what exactly would this proposal do
to my model? Not "something changed" — this much material here is gone, that
much there is new.

Both halves are boolean operations, so both come out of the fallback chain
(§17.2) and both can honestly fail. A difference that could not be computed says
so instead of showing an empty view that looks like "nothing changed".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.errors import PROGRAMMING_ERRORS
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.types import Finding, ObjectId, Quality, Scene, SolverInfo
from app.i18n import _

_log = get_logger(__name__)

#: Volumes below this are meshing noise, not a change (§11.2 in spirit).
NOISE_VOLUME = 1e-3


@dataclass(slots=True)
class Difference:
    """The added and the removed volume of one body."""

    object_id: ObjectId
    added: MeshData | None = None
    removed: MeshData | None = None
    added_volume: float = 0.0
    removed_volume: float = 0.0
    solvers: tuple[SolverInfo, ...] = ()
    findings: list[Finding] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.added_volume > NOISE_VOLUME or self.removed_volume > NOISE_VOLUME


@dataclass(slots=True)
class SceneDifference:
    """The whole scene, body by body, plus what appeared and vanished."""

    entries: dict[ObjectId, Difference] = field(default_factory=dict)
    created: tuple[ObjectId, ...] = ()
    deleted: tuple[ObjectId, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.created or self.deleted) or any(
            entry.changed for entry in self.entries.values()
        )

    @property
    def added_volume(self) -> float:
        return sum(entry.added_volume for entry in self.entries.values())

    @property
    def removed_volume(self) -> float:
        return sum(entry.removed_volume for entry in self.entries.values())


def compare(before: MeshData, after: MeshData, *, quality: Quality = "draft") -> Difference:
    """One body against its successor."""
    entry = Difference(object_id="")
    added = _cut(after, before, quality)
    removed = _cut(before, after, quality)

    if added is not None:
        entry.added, entry.added_volume = added[0], max(added[0].volume, 0.0)
        entry.solvers = (*entry.solvers, added[1])
    if removed is not None:
        entry.removed, entry.removed_volume = removed[0], max(removed[0].volume, 0.0)
        entry.solvers = (*entry.solvers, removed[1])

    if added is None or removed is None:
        entry.findings.append(
            Finding(
                code="difference.incomplete",
                severity="info",
                message=_("Die Differenz ließ sich nicht vollständig berechnen."),
            )
        )
    return entry


def compare_scenes(before: Scene, after: Scene, *, quality: Quality = "draft") -> SceneDifference:
    """The difference of a whole transaction — the unit §18.7 measures in."""
    result = SceneDifference()
    result.created = tuple(name for name in after.objects if name not in before.objects)
    result.deleted = tuple(name for name in before.objects if name not in after.objects)

    for object_id, entry in after.objects.items():
        earlier = before.objects.get(object_id)
        if earlier is None:
            continue
        first, second = earlier.mesh, entry.mesh
        if not isinstance(first, MeshData) or not isinstance(second, MeshData):
            continue
        if abs(first.volume - second.volume) < NOISE_VOLUME and _same_bounds(first, second):
            continue
        difference = compare(first, second, quality=quality)
        difference.object_id = object_id
        result.entries[object_id] = difference
    return result


def _same_bounds(first: MeshData, second: MeshData) -> bool:
    """Cheap pre-check: same volume and same box means nothing moved either."""
    return all(
        abs(a - b) < 1e-6
        for a, b in zip(
            (*first.bounds.minimum, *first.bounds.maximum),
            (*second.bounds.minimum, *second.bounds.maximum),
            strict=True,
        )
    )


def _cut(
    keep: MeshData, subtract: MeshData, quality: Quality
) -> tuple[MeshData, SolverInfo] | None:
    try:
        outcome = boolean("difference", [keep, subtract], quality=quality)
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # kernels fail in kernel-specific ways
        _log.info("difference could not be computed: %s", problem)
        return None
    return outcome.mesh, outcome.solver
