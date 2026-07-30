"""Evaluation as a pure function (Bauplan §15.1).

``stack + sources + parameters + profiles + seeds → scene``. No hidden state, no
side effects: evaluating twice gives the same thing twice, which is what makes
Leitprinzip 4 checkable rather than aspirational.

Three behaviours are deliberate:

* **The chain stops instead of guessing** (§15.2). If an operation returns a
  different number of objects than the stack declares, or refers to an object
  that no longer exists, evaluation halts at that operation and says so. Nothing
  moves up automatically.
* **A cancelled run leaves nothing half applied** (§15.6). The cache is written
  after a complete pass, not during one.
* **The last fully computed state stays valid** (§15.3). This function hands
  back what it reached plus ``stopped_at``; the caller keeps showing the previous
  scene, so the viewport is never empty.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import AmbiguityError, AppError
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.perceive.features import detect
from app.core.perceive.matching import apply_mapping, match, moved_features, question_for
from app.core.registry import REGISTRY, Registry, validate
from app.core.scene import expressions
from app.core.scene.cache import CachedResult, ResultCache
from app.core.scene.cancel import NeverCancelled
from app.core.scene.fits import check as check_fits
from app.core.scene.hashing import object_hash, operation_hash
from app.core.types import (
    CancelToken,
    Document,
    Finding,
    ObjectId,
    OpContext,
    Operation,
    OpId,
    Parameter,
    ParameterName,
    Profile,
    ProgressFn,
    Quality,
    Report,
    Scene,
    SceneObject,
    SolverInfo,
    SourceAccess,
    Transform,
    kind_of,
)
from app.i18n import _

_log = get_logger(__name__)

#: Above this the detection is skipped and says so. §31 puts the target at one
#: second for 200 000 triangles; running it on a million after every operation
#: would cost more than it is worth.
FEATURE_LIMIT_TRIANGLES = 200_000


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """What one pass produced, and where it stopped if it did."""

    scene: Scene
    completed: tuple[OpId, ...] = ()
    stopped_at: OpId | None = None
    object_hashes: Mapping[ObjectId, str] = field(default_factory=dict)
    solvers: Mapping[OpId, SolverInfo] = field(default_factory=dict)
    """Which fallback stage carried which operation (§17.2). The caller writes
    these back into the stack, so the same file recomputes the same way."""

    @property
    def complete(self) -> bool:
        return self.stopped_at is None


def _silent_progress(fraction: float, text: str) -> None:
    return None


def _refuse_to_guess(question: str, choices: list[str]) -> str:
    """Default for ``ask``: without someone to ask, ambiguity is an error, not a guess."""
    raise AmbiguityError(question, candidates=tuple(choices))


def evaluate(
    document: Document,
    profile: Profile,
    *,
    quality: Quality = "fine",
    progress: ProgressFn = _silent_progress,
    ask: Any = _refuse_to_guess,
    cancelled: CancelToken | None = None,
    cache: ResultCache | None = None,
    registry: Registry | None = None,
    sources: SourceAccess | None = None,
) -> EvaluationResult:
    """Compute the scene the document describes."""
    source = registry or REGISTRY
    token = cancelled or NeverCancelled()
    operations = sorted(document.ops, key=lambda entry: entry.id)
    total = len(operations) or 1

    values = expressions.resolve(document.parameters)
    parameters = _evaluated_parameters(document.parameters, values)

    objects: dict[ObjectId, SceneObject] = {}
    hashes: dict[ObjectId, str] = {}
    findings: list[Finding] = []
    completed: list[OpId] = []
    pending: list[tuple[str, CachedResult]] = []
    solvers: dict[OpId, SolverInfo] = {}
    stopped_at: OpId | None = None

    for position, operation in enumerate(operations):
        token.raise_if_cancelled()
        spec = source.get(operation.op)
        progress(position / total, str(spec.title))

        problem = _missing_inputs(operation, objects)
        if problem is not None:
            findings.append(problem)
            stopped_at = operation.id
            break

        try:
            resolved = expressions.resolve_params(operation.params, values)
            params = validate(spec.params, resolved)
        except AppError as error:
            findings.append(_finding_from(error, operation))
            stopped_at = operation.id
            break

        inputs = [objects[entry] for entry in operation.inputs]
        # Kept before the operation runs: the identifiers the new features have
        # to be matched onto afterwards (§21.2).
        previous_features = {entry.id: dict(entry.features) for entry in inputs}
        key = operation_hash(
            operation,
            resolved,
            [hashes[entry] for entry in operation.inputs],
            profile,
            quality,
        )
        cached = cache.get(key) if cache is not None else None

        if cached is not None:
            result = CachedResult(
                objects=cached.objects, findings=cached.findings, transform=cached.transform
            )
        else:
            context = OpContext(
                scene=Scene(
                    objects=dict(objects),
                    parameters=parameters,
                    fits=list(document.fits),
                    profile=profile,
                    report=Report(tuple(findings)),
                ),
                inputs=inputs,
                params=params,
                profile=profile,
                quality=quality,
                seed=operation.seed,
                progress=progress,
                ask=ask,
                cancelled=token,
                sources=sources,
            )
            try:
                produced = spec.fn(context)
            except AppError as error:
                findings.append(_finding_from(error, operation))
                stopped_at = operation.id
                break
            result = CachedResult(
                objects=tuple(produced.outputs),
                findings=tuple(produced.findings),
                solver=produced.solver,
                transform=produced.transform,
            )

        if len(result.objects) != len(operation.outputs):
            findings.append(_object_count_finding(operation, len(result.objects)))
            stopped_at = operation.id
            break

        for entry in operation.inputs:
            if entry not in operation.outputs:
                objects.pop(entry, None)

        for index, produced_object in enumerate(result.objects):
            object_id = operation.outputs[index]
            # §30: whether a body is a mesh or a B-Rep follows from the body,
            # not from what the operation claimed. A mesh operation on an exact
            # part hands back triangles, and the object tree has to say so.
            placed = dataclasses.replace(
                produced_object,
                id=object_id,
                created_by=operation.id,
                kind=kind_of(produced_object.mesh),
            )
            objects[object_id] = _with_features(
                placed,
                previous_features.get(object_id, {}),
                operation,
                ask,
                findings,
                result.transform,
            )
            hashes[object_id] = object_hash(key, index)

        findings.extend(
            dataclasses.replace(
                entry, op_id=entry.op_id if entry.op_id is not None else operation.id
            )
            for entry in result.findings
        )
        if result.solver is not None:
            solvers[operation.id] = result.solver
        completed.append(operation.id)
        if cached is None:
            pending.append((key, result))

    progress(1.0, "")

    # Only a complete pass may write the cache (§15.6).
    if cache is not None and stopped_at is None:
        for key, result in pending:
            cache.put(key, result)

    scene = Scene(
        objects=objects,
        parameters=parameters,
        fits=list(document.fits),
        profile=profile,
        report=Report(tuple(findings)),
    )
    # §14: fits are checked on every evaluation, never only when someone asks.
    if stopped_at is None and scene.fits:
        findings.extend(check_fits(scene, profile))
        scene = dataclasses.replace(scene, report=Report(tuple(findings)))
    if stopped_at is not None:
        _log.warning("evaluation stopped at op %s", stopped_at)
    return EvaluationResult(
        scene=scene,
        completed=tuple(completed),
        stopped_at=stopped_at,
        object_hashes=hashes,
        solvers=solvers,
    )


def _with_features(
    entry: SceneObject,
    previous: dict[str, Any],
    operation: Operation,
    ask: Any,
    findings: list[Finding],
    transform: Transform | None = None,
) -> SceneObject:
    """Detect features again and keep the old identifiers where they still fit.

    §21.2: the detection runs after every operation, otherwise ``hole_3`` in
    step five is a different hole than in step four. Where the match is
    ambiguous the user decides (§21.3) — the one thing that is never done here
    is guessing.
    """
    mesh = entry.mesh
    if not isinstance(mesh, MeshData):
        return entry
    if mesh.triangle_count > FEATURE_LIMIT_TRIANGLES:
        findings.append(
            Finding(
                code="perceive.too_large",
                severity="info",
                message=_("Für die Merkmalserkennung ist dieses Modell zu groß."),
                object_id=entry.id,
                op_id=operation.id,
                values={"triangles": mesh.triangle_count, "limit": FEATURE_LIMIT_TRIANGLES},
            )
        )
        return entry

    # Features a part brought with it are not detected again — they were named
    # when they were built (§24.1), and re-detecting would rename a bore that
    # already has a name. They travel with the body like everything else.
    generated = {
        name: feature
        for name, feature in entry.features.items()
        if feature.provenance == "generated"
    }
    if generated and transform is not None:
        generated = moved_features(generated, transform)

    detected = detect(mesh)
    if not previous:
        return dataclasses.replace(entry, features={**detected, **generated})

    # A turned body looks like a different body to a comparison of positions. The
    # operation knows what it turned, so the old features are carried along
    # first and only then compared (§21.2).
    if transform is not None:
        previous = moved_features(previous, transform)
    previous = {
        name: feature
        for name, feature in previous.items()
        if getattr(feature, "provenance", "detected") != "generated"
    }

    centre = mesh.bounds.centre
    matched = match(previous, detected, centre, mesh.bounds.diagonal)

    for old_id, candidates in matched.ambiguous.items():
        question, choices = question_for(old_id, candidates)
        chosen = ask(question, choices)
        if chosen in candidates:
            matched.mapping[old_id] = chosen
        else:
            findings.append(
                Finding(
                    code="perceive.discarded",
                    severity="info",
                    message=_("Ein Merkmal wurde verworfen, weil es nicht zuzuordnen war."),
                    object_id=entry.id,
                    op_id=operation.id,
                    values={"feature": old_id},
                )
            )

    for old_id in matched.orphaned:
        # Ein verschwundener Defekt ist kein Verlust, sondern das Ziel. Eine
        # offene Kante, die nach dem Reparieren nicht mehr da ist, als Warnung
        # zu melden, sagt dem Nutzer das Gegenteil von dem, was passiert ist —
        # und lässt jeden Weg-3-Bericht wie ein Fehlschlag aussehen.
        defect = getattr(previous.get(old_id), "kind", "") == "edge_loop"
        findings.append(
            Finding(
                code="perceive.mended" if defect else "perceive.orphaned",
                severity="info" if defect else "warning",
                message=(
                    _("Eine offene Stelle ist geschlossen und damit fort.")
                    if defect
                    else _("Ein Merkmal hat keinen Nachfolger mehr.")
                ),
                object_id=entry.id,
                op_id=operation.id,
                values={"feature": old_id},
            )
        )

    return dataclasses.replace(entry, features={**apply_mapping(detected, matched), **generated})


def _evaluated_parameters(
    declared: Mapping[ParameterName, Parameter], values: Mapping[ParameterName, float]
) -> dict[ParameterName, Parameter]:
    """Parameters as the scene sees them: expressions replaced by their result."""
    return {
        name: dataclasses.replace(parameter, value=values[name])
        for name, parameter in declared.items()
    }


def _missing_inputs(
    operation: Operation, objects: Mapping[ObjectId, SceneObject]
) -> Finding | None:
    missing = [entry for entry in operation.inputs if entry not in objects]
    if not missing:
        return None
    return Finding(
        code="evaluate.missing_input",
        severity="error",
        message=_("Diese Operation verweist auf ein Objekt, das es nicht mehr gibt."),
        op_id=operation.id,
        values={"missing": ", ".join(missing), "op": operation.op},
    )


def _object_count_finding(operation: Operation, produced: int) -> Finding:
    """§15.2: a changed object count stops the chain — the user decides, not the code."""
    return Finding(
        code="evaluate.object_count",
        severity="error",
        message=_("Die Operation liefert eine andere Anzahl an Objekten als zuvor."),
        op_id=operation.id,
        values={"expected": len(operation.outputs), "produced": produced, "op": operation.op},
    )


def _finding_from(error: AppError, operation: Operation) -> Finding:
    return Finding(
        code=f"op.{operation.op}.{type(error).__name__}",
        severity="error",
        message=error.title,
        op_id=operation.id,
        values={key: str(value) for key, value in error.values.items()},
    )


def evaluated_object_ids(result: EvaluationResult) -> Sequence[ObjectId]:
    """Objects the scene ended up with, in insertion order."""
    return tuple(result.scene.objects)
