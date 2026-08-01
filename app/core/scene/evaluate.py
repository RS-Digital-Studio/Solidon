"""Die Auswertung als reine Funktion (Bauplan §15.1).

``Stapel + Quellen + Parameter + Profile + Startwerte → Szene``. Kein
versteckter Zustand, keine Nebenwirkungen: zweimal auswerten liefert zweimal
dasselbe — das macht Leitprinzip 4 prüfbar statt bloß gewollt.

Drei Verhaltensweisen sind Absicht:

* **Die Kette hält an, statt zu raten** (§15.2). Liefert eine Operation eine
  andere Objektzahl, als der Stapel deklariert, oder verweist sie auf ein
  Objekt, das es nicht mehr gibt, hält die Auswertung an dieser Operation an
  und sagt es. Nichts rückt von allein nach.
* **Ein abgebrochener Lauf lässt nichts halb angewandt zurück** (§15.6). Der
  Cache wird nach einem vollständigen Durchlauf geschrieben, nicht währenddessen.
* **Der letzte vollständig gerechnete Zustand bleibt gültig** (§15.3). Diese
  Funktion gibt zurück, was sie erreicht hat, plus ``stopped_at``; der Aufrufer
  zeigt weiter die vorige Szene — der Viewport ist nie leer.
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
from app.core.sketch.serialize import sketch_parameter_references
from app.core.types import (
    BaseParams,
    BoundingBox,
    CancelToken,
    Document,
    Feature,
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
from app.core.units import EPS_DISPLAY
from app.i18n import _

_log = get_logger(__name__)

#: Darüber wird die Erkennung übersprungen — und sagt es. §31 setzt das Ziel
#: bei einer Sekunde für 200 000 Dreiecke; sie nach jeder Operation auf einer
#: Million laufen zu lassen, kostete mehr, als es wert ist.
FEATURE_LIMIT_TRIANGLES = 200_000


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Was ein Durchlauf erzeugt hat, und wo er anhielt, falls er es tat."""

    scene: Scene
    completed: tuple[OpId, ...] = ()
    stopped_at: OpId | None = None
    object_hashes: Mapping[ObjectId, str] = field(default_factory=dict)
    solvers: Mapping[OpId, SolverInfo] = field(default_factory=dict)
    """Welche Rückfallstufe welche Operation getragen hat (§17.2). Der
    Aufrufer schreibt sie zurück in den Stapel, damit dieselbe Datei gleich
    nachrechnet."""

    @property
    def complete(self) -> bool:
        return self.stopped_at is None


def _silent_progress(fraction: float, text: str) -> None:
    return None


def _refuse_to_guess(question: str, choices: list[str]) -> str:
    """Vorgabe für ``ask``: ohne jemanden zum Fragen ist Mehrdeutigkeit ein
    Fehler, kein Ratespiel."""
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
    """Rechnet die Szene, die das Dokument beschreibt."""
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
        # Festgehalten, bevor die Operation läuft: die Bezeichner, auf die die
        # neuen Merkmale danach abgebildet werden müssen (§21.2).
        previous_features = {entry.id: dict(entry.features) for entry in inputs}
        # Dazu der Hüllquader, in dem sie gemessen wurden — siehe _with_features.
        previous_bounds = {entry.id: entry.mesh.bounds for entry in inputs}
        key = operation_hash(
            operation,
            _with_sketch_context(spec.params, resolved, values),
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
            # §30: ob ein Körper Mesh oder B-Rep ist, folgt aus dem Körper,
            # nicht aus dem, was die Operation behauptet hat. Eine Mesh-Op auf
            # einem exakten Teil gibt Dreiecke zurück, und der Objektbaum muss
            # das sagen.
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
                previous_bounds.get(object_id),
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

    # Nur ein vollständiger Durchlauf darf den Cache schreiben (§15.6).
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
    # §14: Passungen werden bei jeder Auswertung geprüft, nie nur auf Nachfrage.
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


def _same_size(first: BoundingBox, second: BoundingBox) -> bool:
    """Gleich groß? Dann hat die Operation den Körper bewegt und nicht umgebaut.

    Die Schwelle ist dieselbe, mit der überall gemessen wird: ein Zehntel
    Millimeter ist unter allem, was ein Drucker auflöst, und über allem, was
    beim Neurechnen an Rundung entsteht.
    """
    return all(abs(a - b) <= EPS_DISPLAY for a, b in zip(first.size, second.size, strict=True))


def _outside(feature: Feature | None, bounds: BoundingBox, moved: bool) -> bool:
    """Lag dieses Merkmal außerhalb dessen, was übrig geblieben ist?

    Nur zu fragen, wenn der Körper nicht bewegt wurde — sonst wären nach einer
    Verschiebung alle Merkmale „draußen". Die Toleranz ist eine Anzeigestelle:
    ein Merkmal genau auf der Schnittkante zählt noch als drinnen.
    """
    if feature is None or moved:
        return False
    position = feature.params.get("centre")
    if not isinstance(position, tuple | list) or len(position) != 3:
        return False
    return any(
        value < low - EPS_DISPLAY or value > high + EPS_DISPLAY
        for value, low, high in zip(position, bounds.minimum, bounds.maximum, strict=True)
    )


def _with_features(
    entry: SceneObject,
    previous: dict[str, Any],
    operation: Operation,
    ask: Any,
    findings: list[Finding],
    transform: Transform | None = None,
    previous_bounds: BoundingBox | None = None,
) -> SceneObject:
    """Merkmale neu erkennen und die alten Bezeichner behalten, wo sie noch
    passen.

    §21.2: die Erkennung läuft nach jeder Operation, sonst ist ``hole_3`` in
    Schritt fünf ein anderes Loch als in Schritt vier. Wo die Zuordnung
    mehrdeutig ist, entscheidet der Nutzer (§21.3) — das eine, was hier nie
    passiert, ist Raten.
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

    # Merkmale, die ein Baustein mitgebracht hat, werden nicht neu erkannt —
    # sie wurden beim Bauen benannt (§24.1), und eine Neuerkennung benennte
    # eine Bohrung um, die schon einen Namen hat. Sie reisen mit dem Körper
    # wie alles andere.
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

    # Ein gedrehter Körper sieht für einen Positionsvergleich aus wie ein
    # anderer Körper. Die Operation weiß, was sie gedreht hat — also werden die
    # alten Merkmale erst mitgenommen und dann verglichen (§21.2).
    if transform is not None:
        previous = moved_features(previous, transform)
    previous = {
        name: feature
        for name, feature in previous.items()
        if getattr(feature, "provenance", "detected") != "generated"
    }

    centre = mesh.bounds.centre
    # In welchem Bezugspunkt die alten Merkmale gelesen werden, hängt daran, was
    # die Operation getan hat — und es gibt genau zwei Fälle.
    #
    # **Verschoben.** Der Hüllquader ist gleich groß und liegt woanders. Dann
    # ist jedes Merkmal mitgewandert, und beide Seiten werden in ihrem eigenen
    # Bezugspunkt gelesen. *Auf dem Bett anordnen* ist das: es schiebt jedes
    # Objekt einzeln und kann darum keine gemeinsame Transformation nachreichen.
    #
    # **Umgebaut.** Der Körper hat eine andere Ausdehnung, weil etwas dazukam
    # oder wegging. Dann steht er im Raum, wo er stand, und beide Seiten werden
    # in *demselben* Bezugspunkt gelesen. Der eigene wäre hier falsch: ein
    # aufgesetzter Baustein hebt den Schwerpunkt, und die Grundfläche, die sich
    # nie bewegt hat, läge auf einmal sieben Millimeter tiefer als vorher.
    moved = (
        transform is None
        and previous_bounds is not None
        and _same_size(previous_bounds, mesh.bounds)
    )
    old_centre = previous_bounds.centre if moved and previous_bounds is not None else centre
    matched = match(previous, detected, centre, mesh.bounds.diagonal, old_centre=old_centre)

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
        old_feature = previous.get(old_id)
        # Was außerhalb des neuen Körpers liegt, ist nicht verlorengegangen —
        # es wurde weggeschnitten, und zwar von jemandem, der genau das wollte.
        # Ein Prüfstück schneidet 22 mm aus einem 70er Gehäuse: acht Merkmale
        # bleiben draußen, und acht Warnungen darüber sind acht Warnungen über
        # eine gelungene Operation.
        if _outside(old_feature, mesh.bounds, moved):
            continue

        # Ein verschwundener Defekt ist kein Verlust, sondern das Ziel. Eine
        # offene Kante, die nach dem Reparieren nicht mehr da ist, als Warnung
        # zu melden, sagt dem Nutzer das Gegenteil von dem, was passiert ist —
        # und lässt jeden Weg-3-Bericht wie ein Fehlschlag aussehen.
        defect = getattr(old_feature, "kind", "") == "edge_loop"
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


def _with_sketch_context(
    params_class: type[BaseParams],
    resolved: Mapping[str, Any],
    values: Mapping[ParameterName, float],
) -> Mapping[str, Any]:
    """Der Parametersatz für den Cache-Schlüssel, ergänzt um das, was ein
    Skizzentext von außen liest.

    Maßausdrücke einer gezeichneten Skizze (§30.1) stehen im JSON-Text der Op
    und sind für ``resolve_params`` unsichtbar. Der Schlüssel deckt aber alles,
    wovon das Ergebnis abhängt (§15) — also gehören die Werte der gelesenen
    Projektparameter hinein, sonst überlebt ein Ergebnis die Änderung des
    Parameters, aus dem es gerechnet wurde."""
    context: dict[str, Any] = {}
    for spec in params_class.spec():
        if spec.kind != "sketch":
            continue
        text = resolved.get(spec.name)
        if not isinstance(text, str) or not text:
            continue
        for name in sorted(sketch_parameter_references(text)):
            if name in values:
                context[f"@{name}"] = values[name]
    return {**resolved, **context} if context else resolved


def _evaluated_parameters(
    declared: Mapping[ParameterName, Parameter], values: Mapping[ParameterName, float]
) -> dict[ParameterName, Parameter]:
    """Parameter, wie die Szene sie sieht: Ausdrücke ersetzt durch ihr Ergebnis."""
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
    """§15.2: eine geänderte Objektzahl hält die Kette an — es entscheidet der
    Nutzer, nicht der Code."""
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
    """Die Objekte, bei denen die Szene gelandet ist, in Einfügereihenfolge."""
    return tuple(result.scene.objects)
