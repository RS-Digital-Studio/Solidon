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
from app.core.log import get_logger
from app.core.registry import REGISTRY, Registry, validate
from app.core.scene import expressions
from app.core.scene.cache import CachedResult, ResultCache
from app.core.scene.cancel import NeverCancelled
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
)
from app.i18n import _

_log = get_logger(__name__)


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
        key = operation_hash(
            operation,
            resolved,
            [hashes[entry] for entry in operation.inputs],
            profile,
            quality,
        )
        cached = cache.get(key) if cache is not None else None

        if cached is not None:
            result = CachedResult(objects=cached.objects, findings=cached.findings)
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
            objects[object_id] = dataclasses.replace(
                produced_object, id=object_id, created_by=operation.id
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
    if stopped_at is not None:
        _log.warning("evaluation stopped at op %s", stopped_at)
    return EvaluationResult(
        scene=scene,
        completed=tuple(completed),
        stopped_at=stopped_at,
        object_hashes=hashes,
        solvers=solvers,
    )


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
