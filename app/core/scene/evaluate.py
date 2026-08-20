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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from typing import Any, Final

from app.core.errors import AmbiguityError, AppError, InternalError, OperationCancelled
from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.perceive.features import detect
from app.core.perceive.matching import apply_mapping, match, moved_features, question_for
from app.core.registry import REGISTRY, OperationSpec, Registry, validate
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
from app.i18n import TranslatableText, _

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

        problem = _missing_inputs(operation, objects, spec)
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
            _with_nested_context(spec.params, resolved, values),
            [hashes[entry] for entry in operation.inputs],
            profile,
            quality,
        )
        cached = cache.get(key) if cache is not None else None

        if cached is not None:
            # Unverändert weiterreichen: der Umbau hier warf ohne Not den
            # Solver weg, und nach einem Cache-Treffer fehlte die Stufe in
            # der Solver-Übersicht des Berichts.
            result = cached
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
            except OperationCancelled:
                raise
            except Exception as problem:
                # Eine fremde Ausnahme aus einer Op-Umsetzung ist ein
                # Programmfehler, kein Bedienfehler — aber ohne diesen Fang
                # stirbt der Thread der Auswertung, und die Sitzung meldet
                # Erfolg mit dem alten Ergebnis. Die nächste ungeschützte
                # json.loads in einem Sammelparameter-Leser wäre sonst
                # derselbe Fund noch einmal.
                wrapped = InternalError(
                    detail=f"{type(problem).__name__}: {problem}",
                    values={"operation": str(operation.op)},
                    op_id=operation.id,
                )
                findings.append(_finding_from(wrapped, operation))
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

        # Welcher Art die Eingänge waren, bevor sie verschwinden — gleich
        # darunter wird gefragt, ob aus einem exakten Körper ein Netz wurde.
        art_vorher = {entry: objects[entry].kind for entry in operation.inputs if entry in objects}

        for entry in operation.inputs:
            if entry not in operation.outputs:
                objects.pop(entry, None)

        for index, produced_object in enumerate(result.objects):
            object_id = operation.outputs[index]
            # §30: ob ein Körper Mesh oder B-Rep ist, folgt aus dem Körper,
            # nicht aus dem, was die Operation behauptet hat. Eine Mesh-Op auf
            # einem exakten Teil gibt Dreiecke zurück, und der Objektbaum muss
            # das sagen.
            geworden = kind_of(produced_object.mesh)
            # Der Weg von exakt zu Netz steht jederzeit offen und ist keine
            # Störung — aber er ist eine Einbahnstraße, und bisher ging man
            # sie, ohne es zu merken. „Aushöhlen" auf einem exakten Quader
            # liefert Dreiecke zurück; drei Schritte später lehnt „Tasche
            # schneiden" ab, und der Satz „hier liegt ein Netz" steht dann
            # neben einer Operation, die nichts dafür kann.
            war = art_vorher.get(operation.inputs[index] if index < len(operation.inputs) else "")
            if war is None and operation.inputs:
                war = art_vorher.get(operation.inputs[0])
            if war == "brep" and geworden == "mesh":
                findings.append(
                    Finding(
                        code="evaluate.exact_became_mesh",
                        severity="info",
                        message=_(
                            "Aus einem exakten Körper wurde ein Netz. "
                            "Verrundung, Fase und Skizzen-Operationen stehen darauf nicht mehr "
                            "zur Verfügung."
                        ),
                        values={"op": operation.op, "object": object_id},
                        object_id=object_id,
                        op_id=operation.id,
                        source="internal",
                    )
                )
            placed = dataclasses.replace(
                produced_object,
                id=object_id,
                created_by=operation.id,
                kind=geworden,
            )
            try:
                objects[object_id] = _with_features(
                    placed,
                    previous_features.get(object_id, {}),
                    operation,
                    ask,
                    findings,
                    result.transform,
                    previous_bounds.get(object_id),
                )
            except AppError as error:
                # Die Zuordnung fragt, wenn sie mehrere Kandidaten sieht
                # (§21.2) — und wo niemand antwortet, wirft ``ask``. Das stand
                # außerhalb dieses Fangs: die Ausnahme flog aus ``evaluate``
                # heraus, und wer keinen Frage-Dialog hat (Kommandozeile,
                # Fernsteuerung, Agent) bekam einen leeren Prüfbericht statt
                # der beiden Bohrungen, zwischen denen zu wählen war.
                findings.append(_finding_from(error, operation))
                stopped_at = operation.id
                break
            hashes[object_id] = object_hash(key, index)

        if stopped_at is not None:
            break

        # **Ein Befund gehört zu einem Körper, und er weiß es meist nicht.**
        # ``ingest.not_watertight`` entsteht im Loader, der auf einem Netz
        # arbeitet und keine Kennung kennt — die vergibt der Stapel (§11), und
        # selbst die ``load``-Operation sieht sie nicht: ihre Ausgaben tragen
        # ``id=""``. Ohne Kennung fiel die Handlung am Befund („Reparieren",
        # „Stellen zeigen") über ``_object_of`` auf die *Auswahl* zurück, also
        # auf eine Vermutung — bei einer 3MF-Baugruppe auf die falsche.
        #
        # Hier ist beides bekannt. Eingetragen wird nur bei **genau einer**
        # Ausgabe: Bei mehreren wäre jede Zuordnung geraten, und Raten ist
        # nicht die Aufgabe (Regel 21). Ein Befund, der seine Kennung selbst
        # mitbringt, behält sie.
        lone = operation.outputs[0] if len(operation.outputs) == 1 else None
        findings.extend(
            dataclasses.replace(
                entry,
                op_id=entry.op_id if entry.op_id is not None else operation.id,
                object_id=entry.object_id if entry.object_id is not None else lone,
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
    # Und aus demselben Grund die Lage zum Bauraum: ein Körper, der halb unter
    # der Bauplatte steckt, ist nicht druckbar, und die Schichtanalyse rechnet
    # ihn trotzdem klaglos durch — bis dahin sagte das erst, wer „Kollisionen
    # prüfen" von Hand aufrief.
    if stopped_at is None and objects:
        placement = check_placement(scene)
        if placement:
            findings.extend(placement)
            scene = dataclasses.replace(scene, report=Report(tuple(findings)))
    if stopped_at is not None:
        _log.warning("evaluation stopped at op %s", stopped_at)
    settled = _without_settled(findings)
    if len(settled) != len(findings):
        scene = dataclasses.replace(scene, report=Report(tuple(settled)))
    return EvaluationResult(
        scene=scene,
        completed=tuple(completed),
        stopped_at=stopped_at,
        object_hashes=hashes,
        solvers=solvers,
    )


#: Welcher Befund welchen aufhebt: der Schlüssel wird gestrichen, sobald einer
#: aus seiner Menge an einem **späteren** Schritt steht.
#:
#: Das Beispiel „Weg 3" zeigte, warum das nötig ist. Es begrüßte mit drei
#: Warnungen, und zwei davon waren beim Lesen längst erledigt: „Das Modell ist
#: nicht geschlossen. „Reparieren" schließt die offenen Stellen." stand über
#: „Offene Stellen wurden geschlossen.", und „Es gibt sehr kleine Einzelteile.
#: Gelöscht wurde nichts." über „Kleinstteile wurden gelöscht." — für den, der
#: die Herkunft nicht Zeile für Zeile mitliest, ein Widerspruch.
#:
#: Gestrichen und nicht herabgestuft: Beide Sätze stehen im Präsens und
#: beschreiben einen Zustand, den es nicht mehr gibt. Als Hinweis wären sie
#: nicht milder, sondern falsch. Was übrig bleibt, ist der Satz des Schritts,
#: der es behoben hat — und der erzählt die ganze Geschichte.
SETTLED_BY: Final[dict[str, frozenset[str]]] = {
    "ingest.not_watertight": frozenset({"repair.holes_filled"}),
    "ingest.small_components": frozenset({"repair.components_removed"}),
}


def _without_settled(findings: Sequence[Finding]) -> list[Finding]:
    """Streicht Befunde, die ein späterer Schritt aufgehoben hat (§17.3).

    **Später** ist die ganze Bedingung: Ein Reparieren *vor* dem Einlesen des
    nächsten Modells hebt dessen Befunde nicht auf. Verglichen wird über die
    ``op_id``, und ein Befund ohne sie zählt als am Anfang stehend — die
    Prüfungen am Ende der Auswertung (Passungen, Bauraum) tragen keine.
    """
    if not any(entry.code in SETTLED_BY for entry in findings):
        return list(findings)

    def step(entry: Finding) -> int:
        return entry.op_id if entry.op_id is not None else -1

    kept: list[Finding] = []
    for entry in findings:
        healers = SETTLED_BY.get(entry.code)
        if healers is not None and any(
            other.code in healers
            and step(other) > step(entry)
            and other.object_id == entry.object_id
            for other in findings
        ):
            continue
        kept.append(entry)
    return kept


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
        # Dieselbe Überlegung ein drittes Mal, und diesmal für den Regelfall:
        # ohne einen Verweis darauf ist eine Verwaisung keine Warnung. §21.2
        # führt „kein Partner" als Zuordnungsfall, und §21.3 knüpft das Melden
        # ausdrücklich daran, dass eine spätere Op auf die ID *verweist* —
        # dann hält die Auswertung an und fragt, und dafür gibt es
        # `feature.orphaned` in `orphans.py`. Hier bleibt eine Feststellung:
        # jedes Aushöhlen mit offener Decke verliert die Deckfläche, jede
        # formende Op verliert irgendein erkanntes Merkmal. Als Warnung
        # gezählt, schickt das den Prüfbericht bei gelungener Arbeit nach vorn,
        # bis niemand mehr hinsieht.
        findings.append(
            Finding(
                code="perceive.mended" if defect else "perceive.orphaned",
                severity="info",
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


#: Welcher Sammelparameter seine Ausdrücke in einem eigenen Text versteckt.
#:
#: ``resolve_params`` sieht die **oberste** Ebene eines Parametersatzes. Ein
#: Sammelparameter steht dort als **ein** Wert — ein JSON-Text —, und was
#: darin an Ausdrücken steckt, sieht sie nie. Wer hier fehlt, überlebt die
#: Änderung des Parameters, aus dem er gerechnet wurde: Das Ergebnis bleibt im
#: Cache stehen, während die Zahl daneben schon die neue ist.
#:
#: ``sketch`` stand hier als einziger und **hart verdrahtet**; die Pose kam
#: später dazu und wurde übersehen — obwohl vier Stellen zusagten, dass ein
#: Gelenkwinkel ein Projektparameter sein darf. Eine Zuordnung statt einer
#: Bedingung, damit der nächste Sammelparameter eine Zeile ist und keine
#: Suche.
@cache
def nested_references() -> dict[str, Callable[[str], frozenset[str]]]:
    """Die Zuordnung selbst — **träge**, weil sie sonst einen Import-Kreis schließt.

    ``geom.pose`` braucht den Ausdrucksauswerter und importiert dafür
    ``scene.expressions``; Python lädt dabei das ganze Paket ``scene``, und
    dessen ``__init__`` zieht dieses Modul hier. Stünde
    ``pose_parameter_references`` oben als gewöhnlicher Import, liefe das im
    Kreis, sobald jemand ``app.core.geom.pose`` **als erstes** lädt.

    Die Suite hat das nicht gefangen und konnte es nicht: Sie importiert die
    Kernmodule der Reihe nach in einem Prozess, und da ist ``scene`` längst
    geladen, bevor ``geom.pose`` dran ist. Der Kreis fällt nur auf, wenn ein
    Modul als **erstes** kommt — was ``tests/test_core_isolation.py`` seit
    diesem Fund für jedes einzeln durchspielt.
    """
    from app.core.geom.pose import pose_parameter_references

    return {
        "sketch": sketch_parameter_references,
        "armature": pose_parameter_references,
    }


def _with_nested_context(
    params_class: type[BaseParams],
    resolved: Mapping[str, Any],
    values: Mapping[ParameterName, float],
) -> Mapping[str, Any]:
    """Der Parametersatz für den Cache-Schlüssel, ergänzt um das, was ein
    Sammelparameter von außen liest.

    Maßausdrücke einer gezeichneten Skizze (§30.1) und Gelenkwinkel einer
    Stellung (§13) stehen im JSON-Text der Op und sind für ``resolve_params``
    unsichtbar. Der Schlüssel deckt aber alles, wovon das Ergebnis abhängt
    (§15) — also gehören die Werte der gelesenen Projektparameter hinein,
    sonst überlebt ein Ergebnis die Änderung des Parameters, aus dem es
    gerechnet wurde."""
    context: dict[str, Any] = {}
    for spec in params_class.spec():
        collect = nested_references().get(spec.kind)
        if collect is None:
            continue
        text = resolved.get(spec.name)
        if not isinstance(text, str) or not text:
            continue
        for name in sorted(collect(text)):
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
    operation: Operation, objects: Mapping[ObjectId, SceneObject], spec: OperationSpec
) -> Finding | None:
    """Hat diese Operation, worauf sie arbeiten soll?

    Zwei Arten, das zu verfehlen, und lange sah die Prüfung nur die erste: ein
    Verweis auf ein Objekt, das es nicht mehr gibt. Die zweite ist, gar keinen
    zu tragen — dann greift die Operation selbst nach ``ctx.inputs[0]`` und
    stirbt an einem ``IndexError``, der als Stapelabzug beim Nutzer landet.
    Eine Projektdatei, in der das steht, ließ sich damit überhaupt nicht mehr
    öffnen.
    """
    missing = [entry for entry in operation.inputs if entry not in objects]
    if missing:
        return Finding(
            code="evaluate.missing_input",
            severity="error",
            message=_("Diese Operation verweist auf ein Objekt, das es nicht mehr gibt."),
            op_id=operation.id,
            values={"missing": ", ".join(missing), "op": operation.op},
        )

    # ``VARIABLE`` heißt „so viele wie da sind" und kann auch null sein.
    if spec.consumes > 0 and len(operation.inputs) < spec.consumes:
        return Finding(
            code="evaluate.too_few_inputs",
            severity="error",
            message=_("Dieser Operation fehlt das Objekt, auf dem sie arbeiten soll."),
            op_id=operation.id,
            values={
                "op": operation.op,
                # Englisch, wie jeder Schlüssel — hier standen zwei deutsche.
                "expected": spec.consumes,
                "given": len(operation.inputs),
            },
        )
    return None


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


def check_placement(scene: Scene) -> list[Finding]:
    """Steht jeder Körper im Bauraum — und auf der Platte statt darunter?

    Die Prüfung selbst steht seit je in ``geom.prepare``; sie lief nur, wenn
    jemand „Kollisionen prüfen" aufrief. Ein geladenes Modell sitzt aber
    regelmäßig mittig auf ``z = 0`` und steckt damit zur Hälfte unter der
    Bauplatte: die Schichtanalyse rechnet dann Schichten bei negativer Höhe,
    die Druckvorbereitung meldet „nichts einzuwenden", und niemand sagt es.

    Der Befund trägt den Körper, den er meint. ``check_build_volume`` kennt nur
    die Reihenfolge seiner Liste — hier gibt es die Kennungen, also werden sie
    nachgetragen; ein Bericht, der „ein Objekt" sagt, hilft bei zwanzig nicht.
    """
    from app.core.geom.prepare import check_build_volume, named_for

    profile = scene.profile
    if profile is None or not scene.objects:
        return []
    entries = list(scene.objects.values())
    findings = check_build_volume(
        [entry.mesh for entry in entries], profile, [entry.plate for entry in entries]
    )
    return named_for(findings, entries)


def _finding_from(error: AppError, operation: Operation) -> Finding:
    """Ein Fehler als Zeile im Prüfbericht (§17.3, §33.1).

    Genommen wird der Detailsatz, wo es einen gibt. Bisher stand hier nur der
    Titel — und der ist die Art des Fehlers, nicht sein Grund: „Ein Wert liegt
    außerhalb des zulässigen Bereichs" für einen Körper, dessen Bauart nicht
    passte. Wer danach sucht, sucht bei den Zahlen.

    Der Titel geht dabei nicht verloren: er steht in ``values`` und damit im
    Bericht wie im Fehlercontainer.

    **Nur ein übersetztes Detail** wandert nach vorn, und daran hängt mehr als
    die Sprache: ein ``TranslatableText`` wurde für jemanden geschrieben, eine
    blanke Zeichenkette ist die Notiz daneben. Ohne diese Unterscheidung stand
    im Bericht ``malformed target ''`` statt „Das Ziel muss ein Merkmal eines
    Objekts benennen", und beim OpenSCAD-Aufruf eine halbe Seite roher
    Programmausgabe — während der lesbare Satz beide Male in ``values``
    versteckt lag.
    """
    values = {key: str(value) for key, value in error.values.items()}
    detail = error.detail
    message: TranslatableText | str
    if isinstance(detail, TranslatableText):
        values["kind"] = str(error.title)
        message = detail
    else:
        if detail is not None:
            values["detail"] = str(detail)
        message = error.title if error.title is not None else type(error).__name__
    return Finding(
        code=f"op.{operation.op}.{type(error).__name__}",
        severity="error",
        message=message,
        object_id=error.object_id,
        op_id=operation.id,
        values=values,
    )
