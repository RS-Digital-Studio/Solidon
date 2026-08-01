"""Was eine Änderung hinzugefügt und was sie entfernt hat (Bauplan §18.7).

Die Differenzansicht heißt die wichtigste Ansicht der Anwendung (§19.1), und
sie verdient das, indem sie eine Frage beantwortet: was genau täte dieser
Vorschlag mit meinem Modell? Nicht „etwas hat sich geändert" — so viel Material
hier ist fort, so viel dort ist neu.

Beide Hälften sind Boolesche Operationen, kommen also beide aus der
Rückfallkette (§17.2) und können beide ehrlich scheitern. Eine Differenz, die
sich nicht rechnen ließ, sagt das, statt eine leere Ansicht zu zeigen, die wie
„nichts hat sich geändert" aussieht.
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

#: Volumen darunter sind Vernetzungsrauschen, keine Änderung (§11.2 dem
#: Sinne nach).
NOISE_VOLUME = 1e-3


@dataclass(slots=True)
class Difference:
    """Das hinzugekommene und das entfernte Volumen eines Körpers."""

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
    """Die ganze Szene, Körper für Körper, plus was erschien und verschwand."""

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
    """Ein Körper gegen seinen Nachfolger."""
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
    """Die Differenz einer ganzen Transaktion — die Einheit, in der §18.7
    misst."""
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
    """Billige Vorprüfung: gleiches Volumen und gleicher Quader heißt, dass
    sich auch nichts bewegt hat."""
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
