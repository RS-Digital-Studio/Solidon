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
import math
from collections import Counter
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache, partial
from typing import Any, Final, cast

from app.core import expressions
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    CORRECT_INPUT,
    SHOW_DETAILS,
    SHOW_HISTORY,
    SHOW_STEP_VALUES,
    AmbiguityError,
    AppError,
    InternalError,
    NativeReferenceLost,
    OperationCancelled,
    QuestionDeclined,
)
from app.core.geom.mesh import MeshData
from app.core.knowledge.profiles import analysis_limits, for_process
from app.core.log import get_logger
from app.core.perceive.features import (
    DETECTABLE_KINDS,
    carry_detection,
    centre_of,
    detect,
    freeform_dropped,
    known_detection,
    recognised_as_freeform,
    unreadable_void_shells,
)
from app.core.perceive.local import FEATURE_LIMIT_TRIANGLES as FEATURE_LIMIT_TRIANGLES
from app.core.perceive.local import rigid_transform
from app.core.perceive.match_decisions import (
    MAPPING_NO_LONGER_VALID,
    conflict_groups,
    group_fingerprint,
    mapping_with_decisions,
    resolve_group,
)
from app.core.perceive.match_records import (
    GROUP_DOMAIN,
    NATIVE_DOMAIN,
    group_key,
    valid_fingerprint,
)
from app.core.perceive.matching import (
    FeatureTransform,
    MatchResult,
    apply_mapping,
    inherit_originators,
    match,
    moved_features,
    question_for,
    resolve,
    transformed_features,
)
from app.core.perceive.relations import thinnest_sleeve
from app.core.registry import REGISTRY, OperationSpec, Registry, needed_inputs, validate
from app.core.scene.cache import CachedResult, ResultCache
from app.core.scene.cancel import NeverCancelled
from app.core.scene.edge_binding import NO_BINDING, EdgeBinding, EdgeTarget, bind_edges
from app.core.scene.fits import active_fits
from app.core.scene.fits import check as check_fits
from app.core.scene.hashing import FeatureMemo, digest, object_hash, operation_hash
from app.core.scene.orphans import Reference, feature_ref_of_sketch
from app.core.scene.orphans import references as feature_references
from app.core.scene.parameter_usage import ParameterUse, parameter_uses
from app.core.sketch.serialize import sketch_parameter_references
from app.core.types import (
    AskFn,
    BaseParams,
    BoundingBox,
    CancelToken,
    Document,
    Feature,
    FeatureContinuation,
    FeatureId,
    FeatureRef,
    Finding,
    Mesh,
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
from app.core.units import EPS_DISPLAY, EPS_GEOM, MAX_FACET_SAG, is_close
from app.i18n import TranslatableText, _, source_text, tr

_log = get_logger(__name__)

#: Und darüber läuft die **Zuordnung** nicht — dieselbe Bremse, die andere
#: Größe.
#:
#: Die Dreiecksgrenze darüber schützt davor nicht, denn sie zählt Dreiecke und
#: nicht Merkmale, und zwischen beidem liegt kein fester Faktor: Eine
#: ungeschweißte STL mit 3 372 Dreiecken — weit unter der Dreiecksgrenze —
#: brachte 3 372 Merkmale mit, und ``match`` baute daraus eine Kostenmatrix mit
#: 11,4 Millionen Einträgen. Ein Schritt kostete 101 Sekunden.
#:
#: Die ursprüngliche dichte Zuordnung wurde quadratisch gemessen:
#: 250 Merkmale 0,63 s, 500 Merkmale 2,47 s, 1 000 Merkmale 9,94 s, 2 000
#: Merkmale 39,97 s. Der damalige Korpus von zwanzig Netzen enthielt höchstens
#: **16** Merkmale. Das sind historische Messwerte, keine Aussage über die
#: aktuelle Zuordnung oder über größere importierte Lochbleche.
#:
#: Sie liegt deshalb bewusst hoch. Ohne Zuordnung verliert **jedes** Merkmal
#: seinen Bezeichner, und daran hängen Operationen und Passungen (§21.2) — eine
#: enge Grenze schnitte ein Lochblech mit sechshundert Bohrungen ab, das
#: legitim ist. Gefangen werden soll der Ausreißer, nicht der Alltag.
#:
#: **Tausend war der Alltag** (22.09.2026): Roberts Schraubendreherhalter mit
#: Wabenmuster — 7 956 Dreiecke, sauber verschweißt — bringt 1 199 ebene
#: Flächen, sechs Verrundungen, vier Bohrungen mit Senkung mit, und Solidon
#: zeigte davon nichts, mit dem Rat, das Modell zu verschweißen. Die Grenze
#: stammte aus der Zeit der quadratischen Zuordnung; die heutige ordnet
#: gemessen 800 Merkmale in 0,28 s zu, 2 500 in 0,40 s und 4 000 in 0,65 s.
#: Der Halter selbst: Bohrung setzen 0,8 s, Verschieben 1,2 s mit allen 1 213
#: Merkmalen — unter den zwei Sekunden aus §31. Fünftausend fängt weiter den
#: Ausreißer (eine ungeschweißte STL mit einem Merkmal je Dreieck), nicht mehr
#: das Muster.
FEATURE_LIMIT_COUNT = 5_000


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    """Was ein Durchlauf erzeugt hat, und wo er anhielt, falls er es tat."""

    scene: Scene
    completed: tuple[OpId, ...] = ()
    stopped_at: OpId | None = None
    object_hashes: Mapping[ObjectId, str] = field(default_factory=dict)
    object_names: Mapping[ObjectId, str] = field(default_factory=dict)
    """Wie die Körper hießen — **auch die**, die eine spätere Operation
    verbraucht hat.

    ``scene.objects`` hält nur den Endstand. Ein Befund darf aber auf einen
    Körper zeigen, den ein späterer Schritt ersetzt hat: Das Aushöhlen meldet
    etwas über die Dose, danach macht ``create_lid`` aus ihr Deckel und Rumpf,
    und im Prüfbericht stand „obj_1", weil die Auflösung ins Leere griff. Der
    Name, den der Körper trug, ist die Antwort auf „welcher denn" — er ist
    nicht mehr aktuell, aber er war es, als der Befund entstand."""
    solvers: Mapping[OpId, SolverInfo] = field(default_factory=dict)
    """Welche Rückfallstufe welche Operation getragen hat (§17.2). Der
    Aufrufer schreibt sie zurück in den Stapel, damit dieselbe Datei gleich
    nachrechnet."""
    matches: Mapping[OpId, Mapping[str, Any]] = field(default_factory=dict)
    """Antworten auf mehrdeutige Merkmalszuordnungen (§15.7, §21.3).

    **Der Unterschied zu ``solvers`` ist die Richtung**, und er ist derselbe
    wie zwischen ``solvers`` und ``answers``: Eine Rückfallstufe ist ein
    Vermerk, den die Auswertung nie zurückliest. Eine Antwort ist eine
    Anweisung — steht sie nicht im Stapel, stellt die nächste Auswertung
    dieselbe Frage. Gemessen: 99 modale Fenster für 7 Entscheidungen.

    **Und der Unterschied zu ``answers`` ist der Fragesteller.** Was eine
    *Operation* erfragt, passt in ihre Parameter (die Einheitenrückfrage von
    ``load`` ist der Fall). Was die *Zuordnung* entscheidet, passt in keinen
    Parameter — es ist keine Eingabe der Operation, und ``validate`` wiese den
    Schlüssel ab. Es steht deshalb in ``Operation.matches``."""
    answers: Mapping[OpId, Mapping[str, Any]] = field(default_factory=dict)
    """Was eine Operation über eine **Rückfrage** entschieden hat (§15.7).

    Denselben Weg wie ``solvers`` — und doch etwas anderes: Eine Rückfallstufe
    ist ein Vermerk, den die Auswertung nie zurückliest. Eine Antwort ist eine
    **Anweisung**: Steht sie nicht im Stapel, wird dieselbe Frage bei jeder
    Auswertung erneut gestellt, und mit einem Cache, der länger lebt als eine
    Sitzung, irgendwann gar nicht mehr. Der Aufrufer muss sie also schreiben,
    nicht nur können."""
    parameter_usage: Mapping[str, tuple[ParameterUse, ...]] | None = None
    """Verwendungen im aktuellen Stapel; None bedeutet noch nicht zuverlässig erhoben."""
    parameter_usage_error: AppError | None = None
    blocked_references: tuple[FeatureRef, ...] = ()
    """Verweise, die den Halt tragen: alte native Flächenbezüge, die nach dem
    angehaltenen Schritt nicht belegt sind (§21.2).

    Abgeleitet, nie gespeichert. Der Verweisfilter (``orphans.check``) darf
    sie nicht allein wegen eines vorhandenen gleichen Namens für aufgelöst
    halten und sie auch nicht gegen die alte Szene vor dem Halt neu wählen
    lassen — die Fläche, die er dort fände, ist die vor dem Umbau."""

    @property
    def complete(self) -> bool:
        return self.stopped_at is None


type QuestionCandidate = tuple[ObjectId, FeatureId] | EdgeTarget
"""Ein Kandidat einer Rückfrage: ein Merkmal als Paar aus Körper und Kennung —
oder eine Kante als :class:`EdgeTarget` (P1.4c), das statt einer Kennung ein
Antworttoken und seinen Zug trägt."""

type QuestionContext = Callable[[EvaluationResult | None, tuple[QuestionCandidate, ...]], None]
type FeatureQuestionContext = Callable[[SceneObject | None, tuple[FeatureId, ...]], None]


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
    question_context: QuestionContext | None = None,
    detect_features: bool = True,
) -> EvaluationResult:
    """Rechnet die Szene, die das Dokument beschreibt.

    ``detect_features=False`` ist der Weg der Live-Vorschau: Merkmale werden
    dann nur noch dort neu erkannt, wo ein späterer Schritt oder eine Passung
    sie braucht; was der Merker kennt, kommt trotzdem. Die Szene einer solchen
    Auswertung trägt an frisch gerechneten Körpern keine erkannten Merkmale
    und ist damit kein Dokumentstand — sie ist ein Bild.
    """
    result = _evaluate(
        document,
        profile,
        quality=quality,
        progress=progress,
        ask=ask,
        cancelled=cancelled,
        cache=cache,
        registry=registry,
        sources=sources,
        question_context=question_context,
        detect_features=detect_features,
    )
    try:
        usage = parameter_uses(document, registry) if document.parameters else {}
    except AppError as error:
        return dataclasses.replace(result, parameter_usage_error=error.with_traceback(None))
    return dataclasses.replace(result, parameter_usage=usage)


def _evaluate(
    document: Document,
    profile: Profile,
    *,
    quality: Quality,
    progress: ProgressFn,
    ask: Any,
    cancelled: CancelToken | None,
    cache: ResultCache | None,
    registry: Registry | None,
    sources: SourceAccess | None,
    question_context: QuestionContext | None,
    detect_features: bool = True,
) -> EvaluationResult:
    """Geometrie und Befunde auswerten; auch ein Halt erhält anschließend Verwendungsdaten."""
    profile = for_process(profile, document.print_settings)
    source = registry or REGISTRY
    token = cancelled or NeverCancelled()
    operations = sorted(document.ops, key=lambda entry: entry.id)
    total = len(operations) or 1

    try:
        values = expressions.resolve(document.parameters)
    except AppError as error:
        return _unresolved_parameters(document, profile, error, operations)
    parameters = _evaluated_parameters(document.parameters, values)

    objects: dict[ObjectId, SceneObject] = {}
    hashes: dict[ObjectId, str] = {}
    names: dict[ObjectId, str] = {}
    # Teilhashes je Merkmalsobjekt, für diese Auswertung: Ein Merkmal, das
    # unverändert durch den Stapel reist, wird einmal gehasht, nicht je Schritt.
    feature_memo: FeatureMemo = {}
    findings: list[Finding] = []
    # Grenzen gelten auch für Ausdrücke (Gesamtreview B-15): ``max=60`` mit
    # ``=@a*10`` ergab 600, und niemand sagte etwas. Die Eingabe prüft der
    # Dialog; hier landet, was aus Ausdrücken folgt oder aus einer von Hand
    # bearbeiteten Datei kommt. Ein Befund und kein Halt: Die Geometrie
    # rechnet mit dem Wert, und der Bericht sagt, dass er sein Versprechen
    # bricht — anhalten hieße, eine rücknehmbare Lage in eine Sackgasse zu
    # verwandeln (Regel 19).
    for parameter_name, declared in document.parameters.items():
        resolved_value = values.get(parameter_name)
        if resolved_value is None:
            continue
        below = declared.minimum is not None and resolved_value < declared.minimum - EPS_DISPLAY
        above = declared.maximum is not None and resolved_value > declared.maximum + EPS_DISPLAY
        if not below and not above:
            continue
        bounds: dict[str, Any] = {
            "parameter": str(parameter_name),
            "actual": round(resolved_value, 3),
        }
        if declared.minimum is not None:
            bounds["minimum"] = declared.minimum
        if declared.maximum is not None:
            bounds["maximum"] = declared.maximum
        findings.append(
            Finding(
                code="parameter.out_of_range",
                severity="warning",
                message=_(
                    "Ein Parameter liegt außerhalb seiner Grenzen — gerechnet wird "
                    "trotzdem mit ihm. Prüfen Sie den Ausdruck, oder passen Sie "
                    "die Grenzen an."
                ),
                values=bounds,
                source="internal",
            )
        )
    completed: list[OpId] = []
    pending: list[tuple[str, CachedResult, bool]] = []
    solvers: dict[OpId, SolverInfo] = {}
    answers: dict[OpId, Mapping[str, Any]] = {}
    matches: dict[OpId, dict[str, Any]] = {}
    stopped_at: OpId | None = None

    # Welche Merkmale das Dokument beim Namen nennt (Passungen, Operationen
    # mit ``kind="feature"``): Nur für sie lohnt die Zuordnungsfrage aus
    # §21.3 — eine falsche Bindung eines unverwiesenen Merkmals könnte
    # nichts brechen. Einmal erhoben, nicht je Operation: Die Menge hängt am
    # Stapel, und der ändert sich während einer Auswertung nicht.
    referenced_features: dict[ObjectId, set[str]] = {}
    referenced_anywhere: set[str] = set()
    all_references = feature_references(document, source)
    # Für den exakten Körper zählt außerdem, **wann** ein Verweis gebraucht
    # wird: Eine Fläche, die nur ein früherer Schritt benannt hat, sperrt
    # ihren späteren bewussten Umbau nicht (siehe ``_needed_after``).
    positions = {operation.id: index for index, operation in enumerate(operations)}
    active_fit_names = frozenset(fit.name for fit in active_fits(document))
    blocked: list[FeatureRef] = []
    for reference in all_references:
        if reference.ref.object_id == "":
            # Eine Skizzenebene kennt ihren Körper nicht (``frame_for`` sucht
            # über alle) — ihr Merkmal zählt deshalb an jedem Objekt als
            # verwiesen. Genau diese Verweise fehlten hier ganz, und die
            # §21.3-Frage entfiel ausgerechnet bei „Skizze auf Fläche".
            referenced_anywhere.add(reference.ref.feature_id)
            continue
        referenced_features.setdefault(reference.ref.object_id, set()).add(reference.ref.feature_id)

    for position, operation in enumerate(operations):
        token.raise_if_cancelled()
        if not source.has(operation.op):
            # **Ein Name aus einer Datei ist kein Programmfehler.**
            # ``Registry.get`` wirft ``InternalError``, und für einen Aufruf
            # aus dem *Code* ist das richtig — dort ist ein unbekannter Name
            # ein Tippfehler. Hier kommt er aus einem *Dokument*, und dann ist
            # er ein Zustand, mit dem zu rechnen war: eine Operation, die es
            # in dieser Fassung nicht (mehr) gibt.
            #
            # Gemessen am 26.08.2026 an einer Projektdatei aus 0.1.3 mit einem
            # ``create_from_scad``-Schritt: „Im Programm ist ein unerwarteter
            # Fehler aufgetreten", mitsamt dem Knopf für den Fehlerbericht —
            # für eine Datei, die der Kunde selbst angelegt hatte. Ein
            # Programmfehler darf nie wie ein Bedienfehler aussehen, und
            # umgekehrt genauso wenig.
            #
            # Der Fall ist älter als der OpenSCAD-Ausbau und größer: Ein
            # Rezept-Baustein aus einer fremden Bibliothek, den dieser Rechner
            # nicht hat, kommt hier genauso an — nur ist er dann nicht
            # *entfallen*, sondern *nie da gewesen*. Der Satz nennt deshalb
            # keine Ursache, sondern den Zustand.
            #
            # **Und einen Weg — der fehlte bis zum 26.08.2026.** Der Satz sagte
            # „alles andere im Projekt rechnet weiter", während zwei Zeilen
            # tiefer ``break`` steht: Ab hier rechnet gar nichts mehr. Wer das
            # las, suchte den Fehler bei sich und hatte keine Handhabe (Regel
            # 17 verlangt einen Vorschlag, nicht nur einen Befund).
            #
            # Der Weg hinaus **gibt es**, er stand nur nirgends: ``can_undo``
            # liest die Transaktionen aus dem Dokument, und die reisen in der
            # Projektdatei mit — nach dem Öffnen ist Rückgängig also bedienbar.
            # Hinter den Schritt zurückgehen, irgendetwas ändern, und §15.4
            # verwirft ihn samt allem, was hinter ihm lag.
            findings.append(
                Finding(
                    code="evaluate.unknown_operation",
                    severity="error",
                    message=_(
                        "Diesen Schritt kann Solidon nicht rechnen — ab hier bleibt das "
                        "Projekt stehen. Seine Werte gehen nicht verloren: Der Verlauf "
                        "zeigt sie an. Um weiterzuarbeiten, im Verlauf hinter den "
                        "Schritt zurückgehen; die nächste Änderung verwirft ihn."
                    ),
                    op_id=operation.id,
                    values={"operation": operation.op},
                    suggestions=(SHOW_STEP_VALUES, SHOW_HISTORY),
                )
            )
            stopped_at = operation.id
            break
        spec = source.get(operation.op)
        progress(position / total, str(spec.title))

        if operation.op == "paint_slot" and {"radius", "x", "y", "z"} <= operation.params.keys():
            findings.append(
                Finding(
                    code="evaluate.legacy_point_paint",
                    severity="error",
                    message=_(
                        "Dieser ältere Farbschritt färbt um einen Punkt statt eine Fläche. "
                        "Seine Werte bleiben erhalten. Entfernen Sie den Schritt im Verlauf "
                        "und weisen Sie das Filament der gewünschten Fläche erneut zu."
                    ),
                    op_id=operation.id,
                    values={"operation": operation.op},
                    suggestions=(SHOW_STEP_VALUES, SHOW_HISTORY),
                )
            )
            stopped_at = operation.id
            break

        operation, stray = _without_stray_inputs(operation, spec)
        if stray is not None:
            findings.append(stray)

        problem = _missing_inputs(operation, objects, spec)
        if problem is not None:
            findings.append(problem)
            stopped_at = operation.id
            break

        try:
            resolved = expressions.resolve_params(operation.params, values)
            # **Zwei Fassungen derselben Parameter, und der Unterschied ist der
            # ganze Punkt.** ``resolved`` behält die Message-ID als schlichte
            # Zeichenkette und geht so in den Op-Hash (§4.1) — dieselbe Datei
            # hat damit in jeder Sprache dieselbe Prüfsumme, und ein
            # Cache-Schlüssel hängt nie an der Anzeigesprache. ``for_run``
            # trägt den aufgelösten Text und geht in die Operation, damit der
            # Objektname im Baum in der Sprache des Nutzers steht.
            #
            # Aufgelöst wird nur, was ``operation.translatable`` nennt: Bei
            # einem Namen, den der Nutzer selbst getippt hat, steht dort
            # nichts, und er bleibt wörtlich.
            for_run = dict(resolved)
            for key in operation.translatable:
                if for_run.get(key):
                    for_run[key] = TranslatableText(str(for_run[key]))
            params = validate(spec.params, for_run)
        except AppError as error:
            findings.append(_finding_from(error, operation))
            stopped_at = operation.id
            break

        inputs = [objects[entry] for entry in operation.inputs]
        watched = _WatchedAsk(ask)

        def announce_edges(
            targets: tuple[EdgeTarget, ...], *, operation: Operation = operation
        ) -> None:
            """Zeigt die Kanten einer Kollisionsfrage am gültigen Eingangsstand."""
            if question_context is None:
                return
            if not targets:
                question_context(None, ())
                return
            token.raise_if_cancelled()
            question_context(
                EvaluationResult(
                    scene=Scene(
                        objects=dict(objects),
                        parameters=parameters,
                        fits=active_fits(document),
                        profile=profile,
                        report=Report(tuple(findings)),
                    ),
                    completed=tuple(completed),
                    stopped_at=operation.id,
                    object_hashes=dict(hashes),
                    object_names={name: str(body.name) for name, body in objects.items()},
                ),
                targets,
            )

        # Festgehalten, bevor die Operation läuft: die Bezeichner, auf die die
        # neuen Merkmale danach abgebildet werden müssen (§21.2).
        previous_features = {entry.id: dict(entry.features) for entry in inputs}
        inherited_feature_ids = {
            name for entry in inputs for name in (*entry.reserved_feature_ids, *entry.features)
        }
        active_feature_ids = {name for entry in inputs for name in entry.features}
        # Dazu der Hüllquader, in dem sie gemessen wurden — siehe _with_features.
        previous_bounds = {entry.id: entry.mesh.bounds for entry in inputs}
        try:
            # Der Schlüssel liest die Quelle, und eine Quelle, die es nicht
            # gibt, ist ein Bedienfehler und kein Programmfehler: Die Kette
            # hält an und meldet ihn (§15.3), sie fliegt nicht auf. Vor dem
            # 22.08.2026 stand hier kein Fang, weil der Schlüssel nichts
            # nachschlug, was fehlen konnte.
            from app.core.knowledge.profiles import material

            material_profiles = {
                name: dataclasses.replace(profile, material=material(getattr(params, name)))
                if getattr(params, name)
                else profile
                for name in spec.material_params
            }
            # Und das Material jedes Eingangs, wo es nicht das des Projekts
            # ist: Bohren, Deckel, Bausteine und das Lochfeld rechnen Spiel und
            # Lochzugabe mit dem Profil des Körpers (``profiles.for_object``).
            material_profiles.update(_body_profiles(profile, inputs))
            # Ausdrücklich gewählte Kanten werden **vor** dem Cache am
            # aktuellen Eingang gebunden — eine Kollision fragt hier, und die
            # gebundene Auswahl geht in den Schlüssel: Eine andere Antwort ist
            # eine andere Geometrie dieses Schritts (``scene.edge_binding``).
            binding: EdgeBinding = bind_edges(
                spec,
                operation,
                resolved,
                inputs,
                hashes,
                ask=watched,
                announce=announce_edges,
                check_cancelled=token.raise_if_cancelled,
            )
            hashed_params = _with_nested_context(
                spec.params,
                resolved,
                values,
                sources,
                objects,
                hashes,
                reads_other_bodies=spec.reads_other_bodies,
            )
            if binding.context:
                hashed_params = {**hashed_params, **binding.context}
            key = operation_hash(
                operation,
                hashed_params,
                [hashes[entry] for entry in operation.inputs],
                profile,
                quality,
                implementation_version=spec.cache_version,
                material_profiles=material_profiles,
            )
        except AppError as error:
            findings.append(_finding_from(error, operation))
            stopped_at = operation.id
            break
        cached = cache.get(key) if cache is not None else None

        if cached is not None:
            # Unverändert weiterreichen: der Umbau hier warf ohne Not den
            # Solver weg, und nach einem Cache-Treffer fehlte die Stufe in
            # der Solver-Übersicht des Berichts.
            result = cached
        else:
            context = OpContext(
                # Regel 3 hat jetzt einen Boden unter sich: ``scene`` ist eine
                # Lesekopie — Wörterbücher kopiert, jede Objekthülle samt
                # ihres Merkmal-Wörterbuchs ersetzt (``Parameter`` und
                # ``MeshData`` sind eingefroren). Eine Op, die trotzdem
                # schreibt, ändert ihre Kopie und nicht das Ergebnis; vorher
                # erreichte ein geschriebener Parameter die Ergebnisszene
                # (Fund des Gesamtreviews vom 25.08.2026 — die einzige der 22
                # Regeln ohne Schutz und ohne Test).
                scene=Scene(
                    objects={
                        object_id: dataclasses.replace(
                            entry,
                            features=dict(entry.features),
                            # Auch die Slotliste gehört der Kopie — geteilt
                            # erreichte ein append die Ergebnisszene, und der
                            # Boden unter Regel 3 hätte ein Loch.
                            material_slots=list(entry.material_slots),
                        )
                        for object_id, entry in objects.items()
                    },
                    parameters=dict(parameters),
                    # Dieselbe Liste wie in der Ergebnisszene unten: Eine durch
                    # ``when_positive`` abgeschaltete Passung gehört auch hier
                    # nicht hinein, sonst läse eine Operation zwei Wahrheiten.
                    fits=active_fits(document),
                    profile=profile,
                    report=Report(tuple(findings)),
                ),
                inputs=inputs,
                params=params,
                profile=profile,
                quality=quality,
                seed=operation.seed,
                progress=progress,
                ask=watched,
                cancelled=token,
                sources=sources,
                bound_edges=binding.selections,
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
                #
                # **Und der Traceback gehört ins Protokoll.** Der Kundenbericht
                # S-20260906-9ca141 (0.3.4) trug zweimal
                # ``op.load.InternalError`` mit dem Titel und sonst nichts: Die
                # Ausnahmeart lag in ``values`` versteckt, der Traceback stand
                # nirgends, und mit dem Bericht in der Hand war der Fehler nicht
                # zu finden. ``exc_info`` schreibt ihn in die Zeilen, die der
                # Bericht als „protokoll.txt" mitschickt.
                _log.error(
                    "op %s (%s) raised %s: %s",
                    operation.id,
                    operation.op,
                    type(problem).__name__,
                    problem,
                    exc_info=problem,
                )
                wrapped = InternalError(
                    detail=f"{type(problem).__name__}: {problem}",
                    values={"operation": str(operation.op)},
                    op_id=operation.id,
                )
                findings.append(_finding_from(wrapped, operation))
                stopped_at = operation.id
                break
            # §15.7: Die Antwort **hier** abholen und nicht weiter unten. Was
            # die Operation zurückgegeben hat, wird gleich in ein
            # ``CachedResult`` umgewandelt — und das kennt das Feld nicht, weil
            # ein Ergebnis von der Platte niemanden gefragt hat. Wer es unten
            # liest, liest an einem Objekt, das nur so heißt wie das, das er
            # meint.
            answered_key: str | None = None
            if produced.answered:
                answers[operation.id] = dict(produced.answered)
                # **Und das Ergebnis liegt gleich unter dem Schlüssel, den die
                # Antwort beim nächsten Lauf erzeugt.** ``record_answers``
                # schreibt sie in die Parameter des Schritts, und damit ist
                # sein Schlüssel ein anderer: ``unit: auto`` wird ``unit: mm``.
                # Bis zum 22.09.2026 lief der ganze Import deshalb nach dem
                # ersten Folgeschritt ein zweites Mal — 2,7 s an 204 000
                # Dreiecken, an einer 63-MB-Baugruppe die vierzehn Sekunden
                # des Zählens noch einmal —, und auf der Platte lag ein
                # Eintrag, nach dem nie wieder jemand fragte: Beim Wiederöffnen
                # steht die Antwort im Dokument, nicht die Frage (§31, Projekt
                # öffnen aus Plattencache). Der Schlüssel entsteht auf demselben
                # Weg wie beim nächsten Lauf, nicht durch Einsetzen in den
                # gehashten Satz: ``resolve_params`` entscheidet über Typ und
                # Form eines Werts, und ein zweiter Weg dorthin wäre ein
                # zweiter Ort, an dem die Auflösung nachgebaut wäre.
                answered_key = _key_after_answers(
                    operation,
                    spec,
                    produced.answered,
                    values,
                    sources,
                    objects,
                    hashes,
                    binding.context,
                    profile,
                    quality,
                    material_profiles,
                )
                if answered_key == key:
                    answered_key = None
            result = CachedResult(
                objects=tuple(produced.outputs),
                findings=tuple(produced.findings),
                solver=produced.solver,
                transform=produced.transform,
                continuations=tuple(tuple(entries) for entries in produced.feature_continuations),
            )

        if len(result.objects) != len(operation.outputs):
            findings.append(_object_count_finding(operation, len(result.objects)))
            stopped_at = operation.id
            break
        try:
            continuations = _checked_continuations(operation, result, previous_features)
        except AppError as error:
            findings.append(_finding_from(error, operation))
            stopped_at = operation.id
            break

        # Die gesamte Ausgabe wird vorbereitet. Eine noch offene Zuordnung
        # darf weder einen Eingang verbrauchen noch einen Teil der Ergebnisse
        # in den letzten vollständigen Szenenzustand übernehmen (§15.3/15.6).
        prepared_objects: dict[ObjectId, SceneObject] = {}
        prepared_hashes: dict[ObjectId, str] = {}
        prepared_names: dict[ObjectId, str] = {}
        prepared_matches: dict[str, Any] = {}
        output_findings_start = len(findings)

        # Alte Einzelantworten kennen keinen Körper. Ein gleichnamiger Bezug
        # auf mehreren Ausgaben darf deshalb keine davon ungefragt freigeben.
        old_name_counts = Counter(
            name for output in operation.outputs for name in previous_features.get(output, {})
        )
        legacy_eligible = frozenset(name for name, count in old_name_counts.items() if count == 1)

        def announce_candidates(
            current: SceneObject | None,
            candidates: tuple[FeatureId, ...],
            *,
            operation: Operation = operation,
            result: CachedResult = result,
            prepared_objects: dict[ObjectId, SceneObject] = prepared_objects,
        ) -> None:
            """Zeigt echte Ausgabegeometrie ausschließlich als vergänglichen Fragekontext."""
            if question_context is None:
                return
            if current is None:
                question_context(None, ())
                return
            token.raise_if_cancelled()
            preview_objects = {
                name: body for name, body in objects.items() if name not in operation.inputs
            }
            for output, body in zip(operation.outputs, result.objects, strict=True):
                preview_objects[output] = dataclasses.replace(
                    body, id=output, created_by=operation.id, kind=kind_of(body.mesh)
                )
            preview_objects.update(prepared_objects)
            preview_objects[current.id] = current
            question_context(
                EvaluationResult(
                    scene=Scene(
                        objects=preview_objects,
                        parameters=parameters,
                        fits=active_fits(document),
                        profile=profile,
                        report=Report(tuple(findings)),
                    ),
                    completed=tuple(completed),
                    stopped_at=operation.id,
                    # Alte Geometriehashes dürfen keine neue Fragegeometrie
                    # aus dem Viewportcache durch den vorigen Körper ersetzen.
                    object_hashes={
                        name: value
                        for name, value in hashes.items()
                        if name in preview_objects and name not in operation.outputs
                    },
                    object_names={name: str(body.name) for name, body in preview_objects.items()},
                ),
                tuple((current.id, candidate) for candidate in candidates),
            )

        # Welche Kennung zu welchem Namen gehört — für Befunde einer
        # Baugruppe (siehe unten). ``None`` heißt „mehrdeutig": Zwei
        # Körper desselben Namens sind keine Zuordnung, sondern eine Wahl,
        # und die trifft hier niemand.
        produced_by_name: dict[str, ObjectId | None] = {}
        for index, produced_object in enumerate(result.objects):
            object_id = operation.outputs[index]
            # §30: ob ein Körper Mesh oder B-Rep ist, folgt aus dem Körper,
            # nicht aus dem, was die Operation behauptet hat. Eine Mesh-Op auf
            # einem exakten Teil gibt Dreiecke zurück, und der Objektbaum muss
            # das sagen.
            kind_after = kind_of(produced_object.mesh)
            placed = dataclasses.replace(
                produced_object,
                id=object_id,
                created_by=operation.id,
                kind=kind_after,
            )
            produced_name = str(placed.name)
            produced_by_name[produced_name] = (
                object_id if produced_name not in produced_by_name else None
            )
            recorded: dict[str, dict[str, Any]] = {}
            try:
                prepared_objects[object_id] = _with_features(
                    placed,
                    previous_features.get(object_id, {}),
                    operation,
                    # Auch hier der Wächter: Die Zuordnung fragt bei einem
                    # mehrdeutigen Merkmal (§21.3), und diese Antwort steht
                    # genauso wenig im Dokument wie die einer Operation.
                    watched,
                    findings,
                    result.transform,
                    previous_bounds.get(object_id),
                    recorded,
                    referenced_features.get(object_id, set()) | referenced_anywhere,
                    spec.touches_features,
                    token,
                    # Der Bruchteil ist der dieser Operation — die Erkennung
                    # gehört zu ihr, und ein Balken, der dafür zurückspränge,
                    # sagte etwas Falsches. Was sich ändert, ist der Text.
                    partial(progress, position / total),
                    question_context=announce_candidates,
                    legacy_eligible=legacy_eligible,
                    needed=_needed_after(
                        all_references, positions, active_fit_names, position, object_id
                    ),
                    continuations=continuations[index] if continuations else (),
                    # Die Fassung des Erzeugers, für die eine native Neuwahl
                    # gilt: roher Schlüssel plus Ausgabeindex — nicht der
                    # Objekthash danach, der die Wahl selbst enthielte.
                    scope=f"{key}:{index}",
                    # Der Eingang an derselben Stelle, wenn es einen gibt:
                    # Bei einer gemeldeten Bewegung der Beleg, dass die
                    # Ausgabe sein bewegter Zwilling ist. Ob er es ist,
                    # prüft ``carry_detection`` am Netz, nicht am Index.
                    source_mesh=inputs[index].mesh if index < len(inputs) else None,
                    detect_features=detect_features,
                )
            except AppError as error:
                # Die Zuordnung fragt, wenn sie mehrere Kandidaten sieht
                # (§21.2) — und wo niemand antwortet, wirft ``ask``. Das stand
                # außerhalb dieses Fangs: die Ausnahme flog aus ``evaluate``
                # heraus, und wer keinen Frage-Dialog hat (Kommandozeile,
                # Fernsteuerung, Agent) bekam einen leeren Prüfbericht statt
                # der beiden Bohrungen, zwischen denen zu wählen war.
                del findings[output_findings_start:]
                findings.append(_finding_from(error, operation))
                if isinstance(error, NativeReferenceLost):
                    # Strukturiert weiterreichen, nicht nur als Satz: Der
                    # Verweisfilter muss diese Bezüge kennen, damit er sie
                    # nicht an der alten Szene für aufgelöst hält.
                    blocked.extend(error.references)
                stopped_at = operation.id
                break
            except OperationCancelled:
                raise
            except Exception as problem:
                # **Derselbe Fang wie um die Operation darüber** (Durchsicht
                # 0.5.0). Gefangen war hier nur ``AppError``; ein
                # ``MemoryError`` der Erkennung am Puppenhausbett (1,2
                # Millionen Dreiecke aus Weg 3) flog aus ``evaluate`` heraus,
                # und im Fenster blieb ein abgestürzter Arbeiter statt eines
                # Prüfberichts mit dem Schritt, an dem es lag.
                _log.error(
                    "features of op %s (%s) raised %s: %s",
                    operation.id,
                    operation.op,
                    type(problem).__name__,
                    problem,
                    exc_info=problem,
                )
                del findings[output_findings_start:]
                wrapped = InternalError(
                    detail=f"{type(problem).__name__}: {problem}",
                    values={"operation": str(operation.op)},
                    op_id=operation.id,
                )
                findings.append(_finding_from(wrapped, operation))
                stopped_at = operation.id
                break
            else:
                # Eine Operation kann mehrere Objekte ausgeben, und jedes kann
                # eine eigene Frage aufwerfen. Gesammelt wird deshalb über alle
                # Ausgaben derselben Operation hinweg.
                if recorded:
                    prepared_matches.update(recorded)
            prepared_objects[object_id] = _with_feature_reservations(
                prepared_objects[object_id], inherited_feature_ids, active_feature_ids
            )
            if spec.touches_features and index < len(operation.inputs):
                findings.extend(
                    _split_findings(
                        objects.get(operation.inputs[index]), prepared_objects[object_id], operation
                    )
                )
            prepared_hashes[object_id] = object_hash(
                key,
                index,
                prepared_objects[object_id].reserved_feature_ids,
                getattr(prepared_objects[object_id].mesh, "cavity", None),
                features=prepared_objects[object_id].features,
                check_cancelled=token.raise_if_cancelled,
                memo=feature_memo,
            )
            # Wächst nur, wird nie geleert: Genau darin liegt der Wert (siehe
            # ``EvaluationResult.object_names``).
            # Wörtlich festgehalten, nicht als Verweis: Der Name, den ein
            # Körper trug, ist die Antwort auf „welcher denn" — und er soll
            # die Sprache tragen, in der der Befund entstand.
            prepared_names[object_id] = str(prepared_objects[object_id].name)

        if stopped_at is not None:
            break

        token.raise_if_cancelled()
        # Eine Kantenantwort wird erst veröffentlicht, wenn der Schritt ganz
        # gelungen ist — kein halber Antwortsatz an einem Halt; der Aliasfall
        # geht als Parameter denselben Weg wie die Einheitenfrage (§15.7).
        if binding is not NO_BINDING:
            prepared_matches.update(binding.records)
            if binding.answers:
                answers[operation.id] = {**answers.get(operation.id, {}), **binding.answers}
        if prepared_matches:
            matches[operation.id] = prepared_matches

        conversions = _conversion_findings(
            operation, spec.title, inputs, prepared_objects, result.objects
        )
        findings.extend(conversions)
        for entry in operation.inputs:
            if entry not in operation.outputs:
                objects.pop(entry, None)
        objects.update(prepared_objects)
        hashes.update(prepared_hashes)
        names.update(prepared_names)

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
        converted_sources = {entry.values["input_object"] for entry in conversions}
        current_findings = [
            dataclasses.replace(
                entry,
                op_id=entry.op_id if entry.op_id is not None else operation.id,
                object_id=(
                    entry.object_id
                    if entry.object_id is not None
                    else (lone if lone is not None else _by_name(entry, produced_by_name))
                ),
            )
            for entry in result.findings
            # Der direkte Op-Aufruf erhält weiter seinen Befund. Im Stapel
            # ersetzt ihn die vollständige Aussage mit Operation und Herkunft.
            if not (
                entry.code == "brep.converted" and (entry.object_id or lone) in converted_sources
            )
        ]
        findings.extend(current_findings)
        # Sobald die Hälften erfolgreich auf dem Druckbett angeordnet sind,
        # ist der frühere Hinweis aus ``split`` erledigt. Ein stehen gebliebener
        # Arbeitsauftrag würde den Nutzer sonst trotz fertigem Beispiel in den
        # Prüfbericht schicken. Meldet ``arrange_bed`` selbst, dass bereits
        # alles angeordnet war, bleibt der Hinweis dagegen erhalten.
        if operation.op == "arrange_bed" and not any(
            entry.code == "arrange.already_arranged" for entry in current_findings
        ):
            findings[:] = [entry for entry in findings if entry.code != "prepare.halves_in_place"]
        if result.solver is not None:
            solvers[operation.id] = result.solver
        completed.append(operation.id)
        if cached is None:
            # **In den Cache geht die rohe Ausgabe, nicht die vorbereitete.**
            # Ein Treffer läuft danach wie ein frischer Schritt durch
            # `_with_features`; mit schon vorbereiteten Merkmalen war das
            # nicht idempotent (Weg 3, 21.09.2026: zwei Kugeln hießen beim
            # warmen Lauf anders als beim kalten). Was die Operation ihrem
            # Ergebnis an Merkmalen des Eingangs mitgibt — Dreiecksnummern
            # eines anderen Netzes eingeschlossen —, liest der Plattencodec
            # deshalb so zurück, wie es hier steht.
            pending.append((key, result, not watched.used))
            if answered_key is not None:
                # Dieselbe Herkunftsregel für beide Schlüssel: Was ohne Frage
                # entstand, darf auf die Platte; was eine Frage brauchte,
                # bleibt in der Sitzung — auch unter dem beantworteten
                # Schlüssel, denn ob **jede** Frage des Schritts festgehalten
                # wurde, weiß nur die Operation.
                pending.append((answered_key, result, not watched.used))

    token.raise_if_cancelled()
    scene = Scene(
        objects=objects,
        parameters=parameters,
        fits=active_fits(document),
        profile=profile,
        report=Report(tuple(findings)),
    )
    # §14: Passungen werden bei jeder Auswertung geprüft, nie nur auf Nachfrage.
    if stopped_at is None and scene.fits:
        findings.extend(check_fits(scene, profile, document=document, cancelled=token))
        scene = dataclasses.replace(scene, report=Report(tuple(findings)))
        token.raise_if_cancelled()
    # Und aus demselben Grund die Lage zum Bauraum: ein Körper, der halb unter
    # der Bauplatte steckt, ist nicht druckbar, und die Schichtanalyse rechnet
    # ihn trotzdem klaglos durch — bis dahin sagte das erst, wer „Kollisionen
    # prüfen" von Hand aufrief.
    if stopped_at is None and objects:
        placement = check_placement(scene)
        token.raise_if_cancelled()
        if placement:
            findings.extend(placement)
            scene = dataclasses.replace(scene, report=Report(tuple(findings)))
    # Und aus demselben Grund noch eine Zeile weiter: zwei Körper, die genau
    # aufeinander liegen, sind im Bild einer. Hier und nicht in den
    # Operationen, weil erst der Endstand die Frage beantwortet — wer nach dem
    # Duplizieren anordnet, hat sie längst getrennt, und ein Hinweis aus dem
    # Duplizieren stünde dann als überholter Satz da (§17.3).
    if stopped_at is None and len(objects) > 1:
        stacked = check_bodies_in_one_place(scene)
        token.raise_if_cancelled()
        if stacked:
            findings.extend(stacked)
            scene = dataclasses.replace(scene, report=Report(tuple(findings)))
    # Und die dritte Frage, die erst der Endstand beantwortet: Was ist von der
    # Wand übrig? Sie steht in keinem Merkmal, sondern im Verhältnis zweier,
    # und wer die Bohrung aufbohrt und danach außen wächst, hat am Ende eine
    # gute (§17.3, RM-127).
    if stopped_at is None and objects:
        walls = check_thin_walls(scene)
        token.raise_if_cancelled()
        if walls:
            findings.extend(walls)
            scene = dataclasses.replace(scene, report=Report(tuple(findings)))
    # Und die vierte: Liegen belegte Punkte neben der Form, die sie tragen?
    # Bis zum 21.09.2026 stand hier an jedem Körper mit belegten Flächen
    # derselbe Satz — „lässt sich in der Analysekarte prüfen" —, und damit
    # erreichte kein solcher Körper mehr „Keine Befunde. Das Teil ist
    # druckbereit." Ein Befund ist, was zu berichten ist (§18.4: der Klick
    # führt von „es gibt ein Problem" zu „hier ist es"); die Karte selbst
    # steht in der Analyseleiste für jeden.
    if stopped_at is None and objects:
        deviations = check_form_deviation(scene)
        token.raise_if_cancelled()
        if deviations:
            findings.extend(deviations)
        scene = dataclasses.replace(scene, report=Report(tuple(findings)))
    if stopped_at is not None:
        _log.warning(
            "evaluation stopped at op %s: %s", stopped_at, _why_it_stopped(findings, stopped_at)
        )
    # Erst heilen, dann entdoppeln: Was ein späterer Schritt aufgehoben hat,
    # soll gar nicht erst in den Vergleich — sonst überlebte von zwei
    # geheilten Befunden der letzte die Streichung nicht und der erste doch.
    settled = _without_repeats(_without_settled(findings))
    if len(settled) != len(findings):
        scene = dataclasses.replace(scene, report=Report(tuple(settled)))
    token.raise_if_cancelled()
    # Erst nach sämtlichen Abschlussprüfungen ist der Durchlauf vollständig.
    # Abbruch davor veröffentlicht weder einen Teilcache noch eine Fertigmeldung.
    if cache is not None and stopped_at is None:
        for key, result, to_disk in pending:
            cache.put(key, result, to_disk=to_disk)
    progress(1.0, "")
    return EvaluationResult(
        scene=scene,
        completed=tuple(completed),
        stopped_at=stopped_at,
        object_hashes=hashes,
        object_names=names,
        solvers=solvers,
        answers=answers,
        matches=matches,
        blocked_references=tuple(blocked),
    )


#: Die Parameterarten, deren Wert eine Quellenkennung ist — was eine
#: Operation über ``ctx.sources`` liest. Jede davon gehört mit ihrer
#: **Inhaltsprüfsumme** in den Cache-Schlüssel, nicht mit ihrem Namen: Jedes
#: Projekt nennt sein erstes Bild ``src_1``. Bis zum 05.09.2026 stand hier nur
#: ``source``, und ``displace_image`` liest sein Bild als ``image`` — zwei
#: Projekte mit verschiedenen Bildern bekamen aus dem Plattencache dasselbe
#: Relief, mit ``complete=True`` (Gesamtreview, CORE-11).
SOURCE_KINDS: Final = frozenset({"source", "image"})

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
    # „Zu fein für die Merkmalserkennung" beschreibt eine Zahl, und die
    # Dezimierung ändert genau sie. Bei einem erzeugten Körper stehen beide
    # Sätze im selben Bericht — die Kette lädt, repariert und dezimiert in einem
    # Zug (``core/generate.py``) —, und der erste redet vom Zustand vor dem
    # dritten Schritt. Gestrichen und nicht herabgestuft: Es *ist* nicht mehr zu
    # fein, und ein Hinweis darauf wäre nicht milder, sondern falsch.
    #
    # Eine Dezimierung, die **nicht** unter die Grenze bringt, hebt trotzdem
    # nichts auf: Die Auswertung misst nach jeder Operation, also steht danach
    # ein frischer Befund da, und hinter dem kommt kein Heiler
    # (``test_a_decimation_that_stays_too_large_does_not_settle_the_warning``).
    "perceive.too_large": frozenset({"mesh.deviation"}),
    # Der Rat vom Laden — „Dreiecke verringern hilft" — verschwindet, wenn
    # dieselbe Kette ihn befolgt hat: Nach einem Weg-3-Lauf stand er über
    # einem Objekt, das der vierte Schritt desselben Stapels längst auf
    # 150 000 Dreiecke gebracht hatte (Register, 30.08.2026). Anders als
    # ``perceive.too_large`` wird dieser Befund nur beim Laden erhoben; die
    # Sicherung gegen eine unzureichende Dezimierung trägt der frische
    # ``too_large`` am Dezimier-Schritt. Was dabei bewusst entfällt, ist der
    # Dauer-Rat für die Zone zwischen Karten- und Erkennungsgrenze — die
    # Analysekarten melden ihre Ablehnung beim Klick selbst, und ein halb
    # erledigter Rat kostet mehr Vertrauen, als er nützt.
    "ingest.very_large": frozenset({"mesh.deviation"}),
}


def _conversion_findings(
    operation: Operation,
    title: TranslatableText | str,
    inputs: Sequence[SceneObject],
    outputs: Mapping[ObjectId, SceneObject],
    raw_outputs: Sequence[SceneObject],
) -> list[Finding]:
    """Benennt verlorene exakte Eingänge anhand der vollständigen Ergebniszuordnung.

    Die noch nicht umbenannten Ausgaben tragen die Eingangskennung weiter;
    neue Deckel und Dichtungen tragen keine fremde Herkunft. Bei vollständig
    vernetzten Ausgaben gehören auch verbrauchte exakte Werkzeuge zum Befund.
    Eine gemischte Mehrfachausgabe ohne eindeutigen Nachfolger wird keinem
    beliebigen Körper zugeschrieben.
    """
    mesh_outputs = tuple(name for name, entry in outputs.items() if entry.kind == "mesh")
    if not mesh_outputs:
        return []
    findings = []
    for source in inputs:
        if kind_of(source.mesh) != "brep":
            continue
        descendants = tuple(
            name
            for name, entry in zip(operation.outputs, raw_outputs, strict=True)
            if entry.id == source.id
        )
        successor = outputs.get(source.id)
        targets: tuple[ObjectId, ...]
        if descendants:
            targets = tuple(name for name in descendants if name in mesh_outputs)
            if not targets:
                continue
        elif successor is not None:
            if successor.kind != "mesh":
                continue
            targets = (source.id,)
        elif len(mesh_outputs) == len(outputs):
            targets = mesh_outputs
        else:
            continue
        findings.append(conversion_finding(operation, title, source, targets))
    return findings


def conversion_finding(
    operation: Operation,
    title: TranslatableText | str,
    source: SceneObject,
    targets: Sequence[ObjectId],
) -> Finding:
    """Eine belegte Vernetzung, auch beim Vergleich zweier Varianten desselben Schritts."""
    object_id = targets[0]
    return Finding(
        code="evaluate.exact_became_mesh",
        severity="info",
        message=_(
            "„{operation}“ hat „{object}“ in ein Dreiecksmodell umgewandelt. "
            "Flächen und Kanten bleiben bearbeitbar; Rundungen bestehen jetzt "
            "aus geraden Teilstücken. Rückgängig stellt den vorherigen Körper "
            "wieder her.",
            operation=title,
            object=source.name,
        ),
        values={
            "op": operation.op,
            "step": operation.id,
            "object": object_id,
            "outputs": " ".join(targets),
            "input_object": source.id,
            "input_name": str(source.name),
        },
        object_id=object_id,
        op_id=operation.id,
        source="internal",
    )


def _by_name(finding: Finding, produced: Mapping[str, ObjectId | None]) -> ObjectId | None:
    """Die Kennung des Körpers, den ein Befund beim Namen nennt.

    **Der Weg für die Baugruppe, ohne zu raten.** Eine Operation mit mehreren
    Ausgaben bekommt ihre Befunde nicht zugeordnet — bei acht Körpern wäre
    jede Wahl geraten. ``ingest.ops._named`` schreibt aber den Namen des Teils
    in ``values["object"]``, und hier stehen die Namen aller Ausgaben. Trifft
    er genau eine, ist die Zuordnung belegt und nicht vermutet.

    Gemessen am 03.09.2026 an einer 3MF mit acht Körpern: Ohne diesen Weg
    stand ``ingest.very_large`` ohne Kennung da, und damit ohne Handlung —
    *Dreiecke verringern* braucht ein Ziel und landete sonst auf der zufälligen
    Auswahl (3d-druck-7f).
    """
    named = finding.values.get("object")
    if not isinstance(named, str):
        return None
    return produced.get(named)


def _why_it_stopped(findings: Sequence[Finding], stopped_at: int) -> str:
    """Der Grund zum Abbruch, fürs Protokoll — nicht nur die Nummer.

    **Hier stand nur `evaluation stopped at op 10`.** Im Kundenprotokoll vom
    23.08.2026 steht diese Zeile **neunzehnmal** über sieben Minuten, und keine
    davon sagt, was schiefging. Ohne einen Fund an ganz anderer Stelle hätte
    niemand sagen können, woran es lag — auch wir nicht, mit dem Protokoll in
    der Hand.

    **Der Grund war die ganze Zeit da:** Alle sieben Stellen, die `stopped_at`
    setzen, hängen vorher einen Befund an, der ihn trägt. Er landete im
    Prüfbericht und nicht im Protokoll. Dieselbe Sorte Lücke wie ein
    Fehlertext, der nur seinen Titel zeigt: Der Titel ist je Klasse gleich, der
    Grund steht daneben und fehlt in jeder Zeile.

    **Geschrieben wird die Message-ID, nicht die Übersetzung.** Ein Protokoll
    aus Portugal muss der Support lesen können; `str()` gäbe portugiesisch.
    """
    blamed = [f for f in findings if f.op_id == stopped_at]
    if not blamed:
        return "kein Befund zu dieser Operation"
    last = blamed[-1]
    # **Über `source_text`, nicht über `.msgid`.** Die Message-ID von
    # „12 von 400 offenen Kanten geschlossen" lautet `{closed} von {total}
    # offenen Kanten geschlossen` — roh geschrieben stünden im Protokoll die
    # Platzhalter statt der Zahlen, also gerade das, wonach der Support sucht.
    # Dieselbe Funktion löst das für Dateinamen (`Slot number.stl`).
    reason = f"{last.code}: {source_text(last.message)}"
    # **Der Grund eines Programmfehlers steht nicht in der Meldung.** Die ist
    # je Klasse gleich — „Im Programm ist ein unerwarteter Fehler
    # aufgetreten" —, und Ausnahmeart und -text liegen in ``values["detail"]``.
    # Im Kundenprotokoll vom 06.09.2026 (S-20260906-9ca141) hieß die Zeile
    # zweimal dasselbe und sagte beide Male nichts.
    detail = last.values.get("detail")
    return f"{reason} — {detail}" if detail else reason


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


def _without_repeats(findings: Sequence[Finding]) -> list[Finding]:
    """Dieselbe Aussage über denselben Körper steht einmal da, nicht dreimal.

    Die Auswertung misst **nach jeder Operation** — das ist richtig, denn nur
    so steht nach einer Reparatur ein frischer Befund da. Es hat aber eine
    Kehrseite: Was eine Operation nicht ändert, wird nach jeder erneut
    gemeldet. Gemessen am 27.08.2026 an einem erzeugten Modell mit 221 138
    Dreiecken, nach Einlesen, *Auf Maß bringen* und *Auf das Bett setzen*:

        Für die Merkmalserkennung ist dieses Modell zu groß. — eule
        Für die Merkmalserkennung ist dieses Modell zu groß. — eule
        Für die Merkmalserkennung ist dieses Modell zu groß. — eule

    Der Kunde liest drei Probleme und hat eines. Weder *Auf Maß bringen* noch
    *Auf das Bett setzen* rührt die Dreieckszahl an, also ist es dreimal
    dieselbe Zahl über denselben Körper.

    **Verglichen wird alles außer der Schrittnummer** — Code, Körper, Schwere
    und die Werte. Ändert eine Operation die Zahl, sagen die beiden Befunde
    Verschiedenes und bleiben beide stehen; das ist der Fall, in dem eine
    Dezimierung das Ziel nicht erreicht hat und `SETTLED_BY` bewusst nichts
    aufhebt. Behalten wird der **letzte**: Ein Prüfbericht beschreibt den
    Zustand, in dem die Szene jetzt ist, und der steht am Ende der Kette.

    Die Reihenfolge der übrigen Befunde bleibt, wie sie war — der Bericht
    liest sich entlang des Verlaufs, und ein Umsortieren wäre eine zweite
    Änderung in derselben Zeile.
    """
    last: dict[tuple[Any, ...], int] = {}
    for index, entry in enumerate(findings):
        key = (
            entry.code,
            entry.object_id,
            entry.severity,
            tuple(sorted((name, str(value)) for name, value in (entry.values or {}).items())),
        )
        last[key] = index
    keep = set(last.values())
    return [entry for index, entry in enumerate(findings) if index in keep]


def _same_size(first: BoundingBox, second: BoundingBox) -> bool:
    """Gleich groß? Dann hat die Operation den Körper bewegt und nicht umgebaut.

    Die Schwelle ist dieselbe, mit der überall gemessen wird: ein Zehntel
    Millimeter ist unter allem, was ein Drucker auflöst, und über allem, was
    beim Neurechnen an Rundung entsteht.
    """
    return all(is_close(a, b, EPS_DISPLAY) for a, b in zip(first.size, second.size, strict=True))


def _cut_from_a_thread(mesh: MeshData, threads: Sequence[Feature], found: Feature) -> bool:
    """Besteht dieses erkannte Merkmal ganz aus den Dreiecken einer Wendel?

    Gefragt wird über die **Flächen** des Merkmals und nicht über seinen
    eingepassten Mittelpunkt, und das ist der Unterschied zwischen einer
    Abgrenzung und einem Raten: Eine Kugel, die die Einpassung in eine Wendel
    legt, hat einen Mittelpunkt irgendwo — an einem M8-Gewinde einen mit
    Ø 20,99 auf einem 21 mm hohen Teil. Ihre Dreiecke liegen trotzdem alle auf
    dem Gewinde. Der Mittelpunkt sagt, wohin die Rechnung lief; die Dreiecke
    sagen, woraus das Merkmal gemacht ist.

    **Alle Dreiecke, nicht die meisten.** Ein Merkmal, das zur Hälfte auf der
    Wendel und zur Hälfte auf dem Körper daneben liegt, ist kein Artefakt der
    Wendel — es zu verwerfen nähme dem Kunden etwas Echtes. Die Gegenprobe
    dazu steht in ``tests/test_thread_features.py``: eine Bohrung koaxial
    unter dem Bolzen, die bleiben muss.

    Flächen bleiben ausgenommen. Die Oberseite einer Platte hat ihren
    Schwerpunkt dort, wo ein mittig aufgesetzter Bolzen steht, und sie ist
    trotzdem die Platte.
    """
    import numpy as np

    if found.kind == "face" or not found.face_indices:
        return False

    points = np.asarray(mesh.raw.triangles_center, dtype=float)[list(found.face_indices)]
    return any(_within(points, thread) for thread in threads)


def _within(points: Any, thread: Feature) -> bool:
    """Liegt jeder dieser Punkte in der Hülle des Gewindes?

    Die Hülle ist der Zylinder, über den die Wendel läuft: Achse und Mitte aus
    dem Merkmal, der Nenndurchmesser als Weite, die Gewindelänge als Höhe.

    **Ohne Länge keine Abgrenzung.** Ein Gewindemerkmal ohne ``length`` — aus
    einer Projektdatei, die vor dem Feld entstanden ist — liefert ``False``,
    und die Erkennung behält ihre Funde. Radial allein abzugrenzen wäre der
    teurere Fehler: Eine Bohrung, die koaxial unter dem Bolzen durch die
    Platte geht, fiele mit den Artefakten weg, und eine Passung, die auf sie
    zeigt, verlöre ihr Ziel (§21.3).

    Der Zuschlag ist eine halbe **Steigung** und keine Zahl aus der Luft: Die
    Gangtiefe ist ein Bruchteil der Steigung, und Spiel wie Vernetzung bleiben
    darunter. Ein Innengewinde greift um das halbe Spiel über den
    Nenndurchmesser hinaus — auch das liegt darin.
    """
    import numpy as np

    length = float(thread.params.get("length", 0.0))
    pitch = float(thread.params.get("pitch", 0.0))
    if length <= 0.0 or pitch <= 0.0:
        return False

    axis = np.asarray(thread.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
    norm = float(np.linalg.norm(axis))
    if norm <= EPS_GEOM:
        return False
    axis = axis / norm

    margin = pitch / 2.0
    offset = points - np.asarray(thread.params["centre"], dtype=float)
    along = offset @ axis
    across = np.linalg.norm(offset - np.outer(along, axis), axis=1)

    radius = float(thread.params.get("diameter", 0.0)) / 2.0
    reach = radius + margin
    # **Ein Gewinde ist eine Schale und kein voller Zylinder**, und daran hängt
    # ein Fall, den die Hülle sonst mitnähme: eine Querbohrung durch den
    # Bolzen — ein Splintloch. Sie liegt vollständig in der Hülle, und ohne
    # diese Grenze verlöre sie ihr Merkmal.
    #
    # Der naheliegende Weg über die Achsrichtung ist **gemessen gescheitert**:
    # Ein Phantom-Kegel weicht bis zu 72,8 Grad von der Gewindeachse ab, eine
    # Querbohrung 90 — dazwischen sitzt keine Schwelle, die nicht geraten wäre.
    #
    # Die Schale trägt dagegen, weil sie aus der Bauart folgt und nicht aus
    # einer Messreihe: Der Gewindegrund liegt bei ``radius - pitch *
    # RIDGE_SHARE``, und der Ganganteil ist kleiner als eins — eine Fläche der
    # Wendel liegt deshalb immer über ``radius - pitch``. Nachgemessen über 45
    # Fälle: Der knappste Phantomfund hat 0,158 mm Luft nach unten, die
    # Querbohrung liegt 1,67 mm darunter.
    root = radius - pitch
    return bool(
        np.all(np.abs(along) <= length / 2.0 + margin)
        and np.all(across <= reach)
        and np.all(across >= root)
    )


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


def _shift_between(before: BoundingBox, now: BoundingBox) -> Transform | None:
    """Die reine Verschiebung zwischen zwei Hüllquadern — oder ``None``.

    Eine Operation, die einen Körper nur an einen anderen Platz setzt, meldet
    dafür nicht immer eine Matrix: ``arrange_bed`` setzt jeden Körper einzeln,
    ``orient_for_print`` schweigt bei mehreren. Gleiche Ausdehnung in allen
    drei Achsen bei anderem Mittelpunkt ist eine Verschiebung und sonst nichts
    — erkannt an der Signatur statt am Namen der Operation, damit es auch für
    die nächste gilt, die schiebt, ohne es zu sagen.
    """
    shift = tuple(now.centre[axis] - before.centre[axis] for axis in range(3))
    if not _same_size(before, now) or not any(abs(value) > EPS_DISPLAY for value in shift):
        return None
    return (
        (1.0, 0.0, 0.0, shift[0]),
        (0.0, 1.0, 0.0, shift[1]),
        (0.0, 0.0, 1.0, shift[2]),
        (0.0, 0.0, 0.0, 1.0),
    )


def _inherited_features(
    features: Mapping[FeatureId, Feature], previous: Mapping[FeatureId, Feature]
) -> dict[FeatureId, Feature]:
    """Unveränderte Einträge erkennen, auch mit JSON-Listen aus dem Plattencache."""
    return {
        name: feature
        for name, feature in features.items()
        if (older := previous.get(name)) is not None
        and dataclasses.replace(feature, params=older.params) == older
        and digest(feature.params) == digest(older.params)
    }


def _carried_along(
    entry: SceneObject,
    previous: Mapping[FeatureId, Feature],
    transform: Transform | None,
    previous_bounds: BoundingBox | None,
    *,
    cancelled: CancelToken | None = None,
) -> SceneObject:
    """Nimmt die Merkmale eines exakten Körpers entlang einer starren Bewegung
    mit (§21.2).

    **Für das Netz tut das die Neuerkennung, für den exakten Körper niemand.**
    Die Erkennung darunter misst an Dreiecken; ein ``Solid`` hat keine, seine
    Merkmale liest :func:`app.core.brep.features.features_of` aus der
    Topologie, und zwar in der Operation, die den Körper baut. Wer ihn nur
    bewegt, reicht die alten Merkmale durch — *Drehen* gibt
    ``dataclasses.replace(source, mesh=turned)`` zurück. Danach stand die
    Deckfläche einer um 30 Grad gekippten Platte weiter mit Normale (0, 0, 1)
    bei z = 10 in der Szene, während der Körper längst von z -11,8 bis 21,8
    reichte (gemessen am 17.09.2026).

    Der Kunde merkt es an der Skizze: :mod:`app.core.sketch.planes` baut den
    Skizzenrahmen aus ``normal`` und ``centre`` genau dieser Merkmale, und ein
    Zapfen auf der Deckfläche kam bei z -10 bis 0 heraus — unter dem Bett. Die
    Ebenenwahl beschriftet aus denselben Werten, ``up_to`` und ``height_to``
    rechnen gegen dieselbe Ebene.

    **Neu gerechnet wird nichts.** ``features_of`` kostet einen Durchlauf
    durch die Topologie und vergäbe die Namen neu; eine starre Bewegung ändert
    an einem Merkmal aber nur, wo es sitzt und wohin es zeigt — genau das, was
    :func:`moved_features` mitnimmt. Maße bleiben Maße, und der Name bleibt der
    Name, auf den eine Passung zeigt (§14).

    **Nur, was die Operation unverändert weitergereicht hat.** Hat sie die
    Merkmale selbst gerechnet, hat sie sie am Ausgang gemessen und nicht am
    Eingang; sie ein zweites Mal zu drehen wäre eine Drehung zu viel. Heute
    meldet keine Operation beides, und diese Bedingung sorgt dafür, dass es
    auch dann stimmt, wenn eine es täte.
    """
    matrix = transform
    if matrix is None and previous_bounds is not None:
        matrix = _shift_between(previous_bounds, entry.mesh.bounds)
    if matrix is None or not rigid_transform(matrix):
        return entry
    inherited = _inherited_features(entry.features, previous)
    return dataclasses.replace(
        entry,
        features={
            **entry.features,
            **moved_features(
                inherited,
                matrix,
                check_cancelled=cancelled.raise_if_cancelled if cancelled else None,
            ),
        },
    )


def _needed_after(
    references: Sequence[Reference],
    positions: Mapping[OpId, int],
    active_fits: Collection[str],
    position: int,
    object_id: ObjectId,
) -> dict[FeatureId, tuple[str, ...]]:
    """Welche Merkmale dieses Körpers **nach** diesem Schritt noch jemand
    braucht — und wer.

    Die über das ganze Dokument erhobenen Verweise sagen nur, dass ein Name
    irgendwo benannt ist. Für den Halt an einem umgebauten exakten Körper
    zählt die Lebensdauer: Ein Verweis eines früheren Schritts ist verbraucht,
    einer des Schritts selbst wird an seinem Eingang aufgelöst, und eine
    Passung gilt erst im Endstand — dieselbe zeitliche Grenze wie in
    ``orphans.pending_references``. Ein Körper, dessen Fläche nur ein
    früherer Schritt benannt hat, darf sie in einem späteren Schritt bewusst
    verlieren.

    Gezählt wird am Körper mit **dieser** Kennung, dazu die körperlosen
    Skizzenebenen alter Projekte, die an jedem Körper zu Hause sein dürfen.
    Über eine spätere Teilung hinweg gilt ein gleicher Name nicht als derselbe
    Bezug; dort sucht der Verweisfilter über den Stammbaum, nicht der Halt.
    """
    needed: dict[FeatureId, list[str]] = {}
    for reference in references:
        if reference.kind == "fit":
            if reference.fit_name not in active_fits:
                continue
        elif positions.get(reference.op_id, -1) <= position:
            continue
        if reference.ref.object_id not in ("", object_id):
            continue
        needed.setdefault(reference.ref.feature_id, []).append(reference.title)
    return {name: tuple(who) for name, who in needed.items()}


def _checked_continuations(
    operation: Operation,
    result: CachedResult,
    previous_features: Mapping[ObjectId, Mapping[FeatureId, Feature]],
) -> tuple[tuple[FeatureContinuation, ...], ...]:
    """Die belegten Übergänge einer Operation auf Struktur und Bezug prüfen.

    Die **fachliche** Absicht — ob eine Bohrung wirklich bewusst geändert
    wurde — entsteht allein am Geometrieprüfer der Operation; hier wird nur
    geprüft, dass der Beleg auf etwas zeigt, das es gibt: Die Quelle ist ein
    Eingang dieser Operation und trug das Merkmal, das Ziel steht an der
    zugehörigen Ausgabe, und weder eine Quelle noch ein Ziel kommt zweimal
    vor. Ein Beleg, der das verletzt, ist ein Programmfehler der Operation,
    kein Bedienfehler — und er darf nicht still zu „kein Beleg" werden.
    """
    given = result.continuations
    if not given:
        return ()
    if len(given) != len(result.objects):
        raise InternalError(
            detail="feature continuations do not match the outputs",
            values={"operation": str(operation.op)},
            op_id=operation.id,
        )
    checked: list[tuple[FeatureContinuation, ...]] = []
    for output, entries in zip(result.objects, given, strict=True):
        sources: set[FeatureRef] = set()
        targets: set[FeatureId] = set()
        for entry in entries:
            known = previous_features.get(entry.source.object_id)
            if (
                entry.source.object_id not in operation.inputs
                or known is None
                or entry.source.feature_id not in known
                or entry.target not in output.features
                or entry.source in sources
                or entry.target in targets
            ):
                raise InternalError(
                    detail=f"invalid feature continuation {entry.source} -> {entry.target}",
                    values={"operation": str(operation.op)},
                    op_id=operation.id,
                )
            sources.add(entry.source)
            targets.add(entry.target)
        checked.append(tuple(entries))
    return tuple(checked)


def _selectable(feature: Feature, triangles: int) -> bool:
    """Ob ein aktuelles Merkmal eine gültige Auswahl am aktuellen Körper trägt."""
    return bool(feature.face_indices) and all(
        0 <= index < triangles for index in feature.face_indices
    )


def _native_reselection(
    current: SceneObject,
    previous: Mapping[FeatureId, Feature],
    lost: Mapping[FeatureId, tuple[str, ...]],
    matched: MatchResult,
    operation: Operation,
    ask: Any,
    findings: list[Finding],
    recorded: dict[str, dict[str, Any]] | None,
    watch: CancelToken,
    question_context: FeatureQuestionContext | None,
    scope: str,
) -> tuple[SceneObject, MatchResult]:
    """Lässt am neu gebauten exakten Körper wählen, welche aktuelle Fläche
    einen nicht belegten alten Bezug fortführt — und veröffentlicht die Wahl
    als Alias unter dem alten Namen.

    Kandidaten sind die aktuellen Merkmale derselben Art mit gültiger
    Auswahl, die noch kein belegter alter Name beansprucht — auch ein frisch
    vergebener gleicher Name ist nur ein Kandidat, kein Beleg. Ein alter
    Bezug ohne Kandidaten bleibt verloren; „Nicht weiterführen" ebenfalls —
    beides meldet der Aufrufer als Halt. Die Wahl reist wie eine Netzantwort
    durch ``recorded`` in den Stapel, nur in der nativen Domäne mit Scope.
    """
    # **Wer neu gewählt wird, steht nicht mehr in der Zuordnung.** Ein alter
    # Bezug, den die Geometrie eindeutig einem Merkmal unter anderem Namen
    # zuordnet, ist nicht belegt (``_unproven_native_references``) und wird
    # gefragt — bis zum 23.09.2026 aber mit seiner alten Zuordnung im Gepäck:
    # Sein gefundener Nachfolger galt als besetzt und stand nicht unter den
    # Antworten, und jede Antwort scheiterte an ``mapping_with_decisions``
    # („Die Zuordnung ist nicht mehr gültig"), weil der alte Name schon
    # zugeordnet war. Am exakten Quader genügte dafür, eine Seite zu versetzen,
    # während eine Passung auf Deck- und Bodenfläche lag.
    settled = {old: new for old, new in matched.mapping.items() if old not in lost}
    occupied = set(settled.values())
    triangles = current.mesh.triangle_count
    claims: dict[FeatureId, tuple[FeatureId, ...]] = {}
    for name in sorted(lost):
        watch.raise_if_cancelled()
        kind = previous[name].kind
        options = tuple(
            candidate
            for candidate, feature in sorted(current.features.items())
            if feature.kind == kind
            and candidate not in occupied
            and _selectable(feature, triangles)
        )
        # Der gefundene Nachfolger steht vorn: Er ist, was die Geometrie sagt,
        # und die Zeile, die der Dialog zuerst markiert.
        found = matched.mapping.get(name)
        if found in options:
            options = (found, *(candidate for candidate in options if candidate != found))
        if options:
            claims[name] = options
    if not claims:
        return current, matched
    question = MatchResult(
        mapping=settled,
        orphaned=tuple(name for name in matched.orphaned if name not in claims),
        ambiguous=claims,
        fresh=matched.fresh,
    )
    try:
        _answer_matches(
            current,
            question,
            operation,
            ask,
            findings,
            recorded,
            frozenset(claims),
            watch,
            question_context,
            frozenset(),
            scope=scope,
        )
    except AmbiguityError as refused:
        # Ohne jemanden zum Fragen — Kommandozeile, Agent — bleibt die
        # Frage offen, und die Bezüge bleiben gesperrt: derselbe Halt wie
        # ohne Kandidaten, nur mit den Wahlmöglichkeiten als Vorschläge, damit
        # der Agent antworten kann, und mit den Bezügen für den Verweisfilter.
        raise NativeReferenceLost(
            refused.detail,
            references=tuple(FeatureRef(current.id, name) for name in sorted(claims)),
            suggestions=refused.suggestions,
            values={
                "candidates": refused.values.get("candidates", []),
                "where": "; ".join(sorted({who for name in claims for who in lost[name]})),
                "operation": str(operation.op),
            },
            object_id=current.id,
        ) from refused
    chosen = {old: new for old, new in question.mapping.items() if old in claims}
    if not chosen:
        return current, question
    watch.raise_if_cancelled()
    # Der gewählte Nachfolger lebt unter dem alten Namen weiter — mit seinen
    # aktuellen Maßen, Dreiecken und Teilträgern. Derselbe Aliasweg wie beim
    # gezielten Bohrungswechsel; kein zweiter Eintrag unter dem frischen Namen.
    aliased = apply_mapping(
        dict(current.features),
        MatchResult(mapping=chosen, orphaned=question.orphaned),
        previous=previous,
    )
    return dataclasses.replace(current, features=aliased), question


#: Die Maße, an denen ein Merkmal nach einem Umbau als **unverändert** gilt —
#: Lage und Richtung (``_UNCHANGED_VECTORS``) und Größe (``_UNCHANGED_SIZES``).
_UNCHANGED_VECTORS: Final = ("centre", "normal", "axis", "direction")
_UNCHANGED_SIZES: Final = (
    "area",
    "diameter",
    "radius",
    "depth",
    "length",
    "angle",
    "tube_diameter",
    "pitch",
    "volume",
)


def _unchanged(old: Feature, new: Feature) -> bool:
    """Ob zwei Merkmale bis auf Rechenrauschen dieselbe Geometrie beschreiben.

    Jede Lage und Richtung auf :data:`EPS_GEOM` gleich — eine Achse ohne
    Vorzeichen, wie die Zuordnung sie liest —, jede Größe relativ auf
    :data:`EPS_GEOM`, und was eines trägt, trägt auch das andere. Gemessen an
    ``carpet-corner-clip.step`` und ``build_tray_v3.step`` (23.09.2026): Eine
    Fläche, die *Fläche versetzen* nicht berührt, kommt bitgleich zurück.
    """
    if old.kind != new.kind:
        return False
    for key in _UNCHANGED_VECTORS:
        first, second = old.params.get(key), new.params.get(key)
        if first is None and second is None:
            continue
        if not isinstance(first, tuple | list) or not isinstance(second, tuple | list):
            return False
        if len(first) != 3 or len(second) != 3:
            return False
        try:
            straight = max(abs(float(a) - float(b)) for a, b in zip(first, second, strict=True))
            turned = max(abs(float(a) + float(b)) for a, b in zip(first, second, strict=True))
        except TypeError, ValueError:
            return False
        if straight > EPS_GEOM and (key != "axis" or turned > EPS_GEOM):
            return False
    for key in _UNCHANGED_SIZES:
        first, second = old.params.get(key), new.params.get(key)
        if first is None and second is None:
            continue
        numbers = all(
            isinstance(value, int | float) and not isinstance(value, bool)
            for value in (first, second)
        )
        if not numbers:
            return False
        one, two = float(cast(float, first)), float(cast(float, second))
        if abs(one - two) > EPS_GEOM * max(1.0, abs(one), abs(two)):
            return False
    return True


def _unchanged_continuations(
    current: SceneObject,
    reference: Mapping[FeatureId, Feature],
    unproven: Collection[FeatureId],
    matched: MatchResult,
) -> tuple[SceneObject, MatchResult]:
    """Alte Bezüge, deren eindeutiger Partner unverändert ist, unter ihrem Namen fortführen.

    Beleg nach P1.4c.2 war nur die Zuordnung auf **denselben** Namen. Die native
    Erkennung nummeriert nach jedem Umbau neu, und eine Fläche, die der Schritt
    nicht berührt hat, kam unter anderem Namen zurück: Am Teppichclip fragte
    Solidon bei jedem *Fläche versetzen* nach beiden Flächen einer Passung, die
    niemand angefasst hatte. Ist der eindeutige Partner bis auf Rechenrauschen
    dieselbe Geometrie (:func:`_unchanged`), ist das ein Beleg — strenger als
    die Zuordnung, die §21.2 für „ID bleibt“ genügt. Der Partner wird wie bei
    der Neuwahl unter dem alten Namen veröffentlicht (``apply_mapping``).

    Die Zuordnung danach führt diese Namen auf sich selbst; was auf einen
    umbenannten Partner zeigte, fällt heraus und bleibt damit unbelegt — gefragt
    wird dann wie bisher, nie still angenommen.
    """
    unchanged = {
        name: found
        for name in sorted(unproven)
        if (found := matched.mapping.get(name)) is not None
        and found != name
        and name not in matched.ambiguous
        and name in reference
        and found in current.features
        and _unchanged(reference[name], current.features[found])
    }
    if not unchanged:
        return current, matched
    aliased = apply_mapping(
        dict(current.features),
        MatchResult(
            mapping=unchanged, orphaned=matched.orphaned, ambiguous=dict(matched.ambiguous)
        ),
        previous=reference,
    )
    renamed = set(unchanged.values()) | set(unchanged) | set(matched.orphaned)
    renamed |= set(matched.ambiguous)
    mapping = {
        old: new
        for old, new in matched.mapping.items()
        if old not in unchanged and new not in renamed
    }
    mapping.update({name: name for name in unchanged})
    return dataclasses.replace(current, features=aliased), dataclasses.replace(
        matched, mapping=mapping
    )


def _unproven_native_references(
    wanted: Collection[FeatureId],
    current: SceneObject,
    matched: MatchResult | None,
) -> frozenset[FeatureId]:
    """Welche noch gebrauchten alten Bezüge am neuen exakten Körper nicht
    belegt sind.

    Belegt ist ein Bezug nur durch die eindeutige geometrische Zuordnung auf
    **denselben** logischen Namen mit gültiger aktueller Auswahl. Ein
    verlorener Name, ein umkämpfter, einer, der zu einem anderen aktuellen
    Namen passt, und eine ausgelassene Zuordnung sind alle dasselbe: nicht
    belegt. Ein frisch vergebener gleicher Name beweist die alte Fläche nicht —
    ``features_of`` nummeriert neu, und ``face_1`` kann eine andere sein.
    """
    if not wanted:
        return frozenset()
    if matched is None:
        # Ungeprüft heißt unbekannt, nicht gültig — auch über der
        # Merkmalsgrenze verschwindet die Frage nicht still.
        return frozenset(wanted)
    triangles = current.mesh.triangle_count
    blocked = set()
    for name in wanted:
        feature = current.features.get(name)
        if (
            name in matched.ambiguous
            or matched.mapping.get(name) != name
            or feature is None
            or not _selectable(feature, triangles)
        ):
            blocked.add(name)
    return frozenset(blocked)


def _with_feature_reservations(
    entry: SceneObject, inherited: set[str], active: set[str]
) -> SceneObject:
    """Vergebene Kennungen überleben jede Operation und jeden Cachetreffer.

    Auch eine neue Erkennung darf einen früher gelöschten Namen nicht
    wiederbeleben. Überlebende Merkmale behalten dagegen ihre Zuordnung.
    """
    taken = inherited | set(entry.reserved_feature_ids) | set(entry.features)
    features = {}
    for name, feature in entry.features.items():
        if name in inherited and name not in active:
            stem, separator, tail = name.rpartition("_")
            prefix = stem if separator and tail.isdigit() else name
            highest = max(
                (
                    int(key.rpartition("_")[2])
                    for key in taken
                    if key.rpartition("_")[0] == prefix and key.rpartition("_")[2].isdigit()
                ),
                default=0,
            )
            name = f"{prefix}_{highest + 1}"
            feature = dataclasses.replace(feature, id=name)
            taken.add(name)
        features[name] = feature
    return dataclasses.replace(entry, features=features, reserved_feature_ids=tuple(sorted(taken)))


def _feature_originators(
    features: Mapping[FeatureId, Feature],
    matched: MatchResult,
    operation: Operation,
    touches_features: bool,
    knew_features: bool,
) -> dict[FeatureId, Feature]:
    """Nur wirklich neue Merkmale tragen den aktuellen Schritt als Erzeuger."""
    contested = {name for names in matched.ambiguous.values() for name in names}
    newcomers = set(matched.fresh) - contested if touches_features and knew_features else set()
    result = {}
    for name, feature in features.items():
        if feature.created_by is None and name in newcomers:
            feature = dataclasses.replace(feature, created_by=operation.id)
        result[name] = feature
    return result


def _answer_matches(
    entry: SceneObject,
    result: MatchResult,
    operation: Operation,
    ask: AskFn,
    findings: list[Finding],
    recorded: dict[str, dict[str, Any]] | None,
    referenced: frozenset[str] | set[str],
    watch: CancelToken,
    question_context: FeatureQuestionContext | None,
    legacy_eligible: frozenset[str] | None,
    *,
    scope: str | None = None,
) -> None:
    """Eine konkurrierende Gruppe vollständig wählen, prüfen und erst dann übernehmen.

    Mit ``scope`` ist es die **native Neuwahl** (§21.3, P1.4c): Der exakte
    Körper wurde neu gebaut, und der Kunde wählt, welche aktuelle Fläche
    einen alten Bezug fortführt. Die Antwort liegt in der eigenen Domäne
    ``native-group`` und gilt nur für diese Erzeugerfassung; eine Netzantwort
    unter demselben Namen wird nie dafür genommen, und alte Einzelantworten
    (``legacy``) gelten hier nicht — der Aufrufer übergibt dafür eine leere
    ``legacy_eligible``-Menge.
    """
    matched = dataclasses.replace(result, mapping=dict(result.mapping))
    pending_records: dict[str, dict[str, Any]] = {}
    pending_findings: list[Finding] = []
    centre, diagonal = entry.mesh.bounds.centre, entry.mesh.bounds.diagonal
    legacy = operation.matches.get("legacy", {})
    domain = GROUP_DOMAIN if scope is None else NATIVE_DOMAIN
    grouped_old_ids = {
        name
        for key, record in operation.matches.items()
        if key != "legacy" and record.get("object_id") == entry.id
        for name in record.get("old_ids", ())
    }
    for claims in conflict_groups(matched, check_cancelled=watch.raise_if_cancelled):
        key = group_key(entry.id, claims, domain=domain)
        saved = operation.matches.get(key)
        decisions = (
            resolve_group(
                saved,
                entry.id,
                claims,
                entry.features,
                centre,
                diagonal,
                set(matched.mapping.values()),
                check_cancelled=watch.raise_if_cancelled,
                scope=scope,
            )
            if saved is not None
            else None
        )
        # Historische Einzelantworten belegen keine Konkurrenzgruppe und
        # gelten nur bei einem körperübergreifend eindeutigen alten Namen.
        old_id = next(iter(claims))
        if (
            decisions is None
            and len(claims) == 1
            and old_id not in grouped_old_ids
            and (
                old_id in legacy_eligible
                if legacy_eligible is not None
                else len(operation.outputs) <= 1
            )
        ):
            remembered = legacy.get(old_id)
            if isinstance(remembered, Mapping) and valid_fingerprint(remembered, legacy=True):
                answer = resolve(
                    remembered,
                    claims[old_id],
                    entry.features,
                    centre,
                    diagonal,
                    check_cancelled=watch.raise_if_cancelled,
                )
                if answer is not None and answer not in matched.mapping.values():
                    decisions = {old_id: answer}
        # Bereits bestätigte Identität bleibt auch ohne aktuellen Verbraucher
        # erhalten. Nur eine neue Frage braucht einen tatsächlich verwendeten
        # Bezug; unbenutzte ungeklärte Gruppen behalten ihre frischen Namen.
        if decisions is None and not set(claims) & referenced:
            continue
        newly_chosen = decisions is None
        if newly_chosen:
            decisions = {}
            occupied = set(matched.mapping.values())
            noncontinuation = tr("Nicht weiterführen")
            # **Wer benutzt wird, wählt zuerst.** Die Reihenfolge der Namen
            # stellte die Frage für eine Bohrung, an der eine Passung hing,
            # zuletzt — mit „Nicht weiterführen“ als einziger Antwort, weil zwei
            # unbenutzte die Nachfolger schon genommen hatten (23.09.2026).
            # ``sorted`` ist stabil; unter sich bleibt die Reihenfolge dieselbe.
            for old_id in sorted(claims, key=lambda name: name not in referenced):
                candidates = claims[old_id]
                watch.raise_if_cancelled()
                available = tuple(name for name in candidates if name not in occupied)
                if not available and old_id not in referenced:
                    # Keine Wahl und kein Verbraucher: Ein Dialog mit „Nicht
                    # weiterführen“ als einziger Antwort fragte nichts. Die
                    # Entscheidung wird trotzdem festgehalten wie eine Antwort.
                    decisions[old_id] = None
                    continue
                question, _unused_choices = question_for(old_id, available)
                question = tr("Körper „{object}“: {question}").format(
                    object=str(entry.name), question=question
                )
                if scope is not None:
                    question += "\n\n" + tr(
                        "Dieser Schritt hat den exakten Körper neu gebaut. Wählen Sie die "
                        "aktuelle Fläche, die den bisherigen Bezug fortführt."
                    )
                if len(claims) > 1:
                    question += "\n\n" + tr(
                        "Diese bisherigen Bezüge teilen sich mögliche Nachfolger: {names}. "
                        "Jedes aktuelle Merkmal kann nur einen bisherigen Bezug übernehmen."
                    ).format(names=", ".join(claims))
                # Sie-Form wie jeder Kundentext (``match_decisions``); bis zum
                # 22.09.2026 stand hier „Ordne sie … neu zu".
                question += "\n\n" + tr(
                    "Bei „Nicht weiterführen“ bleiben Verweise auf dieses Merkmal ungeklärt. "
                    "Ordnen Sie sie in den betroffenen Folgeschritten neu zu."
                )
                try:
                    if question_context is not None:
                        question_context(entry, available)
                    chosen = ask(question, [*available, noncontinuation])
                    watch.raise_if_cancelled()
                finally:
                    if question_context is not None:
                        question_context(None, ())
                if chosen == noncontinuation:
                    decisions[old_id] = None
                elif chosen in available:
                    decisions[old_id] = chosen
                    occupied.add(chosen)
                else:
                    raise AmbiguityError(MAPPING_NO_LONGER_VALID)
        assert decisions is not None
        proposed = mapping_with_decisions(
            matched, claims, decisions, check_cancelled=watch.raise_if_cancelled
        )
        new_record = (
            group_fingerprint(
                entry.id,
                claims,
                decisions,
                entry.features,
                centre,
                diagonal,
                check_cancelled=watch.raise_if_cancelled,
                scope=scope,
            )
            if newly_chosen
            else None
        )
        watch.raise_if_cancelled()
        matched.mapping.update(proposed)
        if new_record is not None and recorded is not None:
            pending_records[key] = new_record
        for old_id, candidate in decisions.items():
            if candidate is None:
                pending_findings.append(
                    Finding(
                        code="perceive.discarded",
                        severity="info",
                        message=_("Ein Merkmal wurde verworfen, weil es nicht zuzuordnen war."),
                        object_id=entry.id,
                        op_id=operation.id,
                        values={"feature": old_id},
                    )
                )
    watch.raise_if_cancelled()
    result.mapping = matched.mapping
    findings.extend(pending_findings)
    if recorded is not None:
        recorded.update(pending_records)


def _with_features(
    entry: SceneObject,
    previous: dict[str, Any],
    operation: Operation,
    ask: Any,
    findings: list[Finding],
    transform: Transform | None = None,
    previous_bounds: BoundingBox | None = None,
    recorded: dict[str, dict[str, Any]] | None = None,
    referenced: frozenset[str] | set[str] = frozenset(),
    touches_features: bool = False,
    cancelled: CancelToken | None = None,
    say: Callable[[str], None] | None = None,
    *,
    question_context: FeatureQuestionContext | None = None,
    legacy_eligible: frozenset[str] | None = None,
    needed: Mapping[FeatureId, tuple[str, ...]] | None = None,
    continuations: Sequence[FeatureContinuation] = (),
    scope: str | None = None,
    source_mesh: Mesh | None = None,
    detect_features: bool = True,
) -> SceneObject:
    """Merkmale neu erkennen und die alten Bezeichner behalten, wo sie noch
    passen.

    ``source_mesh`` ist das Netz des Eingangs, aus dem diese Ausgabe entstand —
    bei einer gemeldeten Bewegung der Beleg dafür, dass nicht neu erkannt
    werden muss (:func:`carry_detection`). ``detect_features=False`` lässt
    die Erkennung aus, wo kein späterer Schritt und keine Passung ein Merkmal
    dieses Körpers braucht (siehe :func:`evaluate`).

    ``needed`` nennt die alten Merkmale dieses Körpers, die **nach** dieser
    Operation noch jemand braucht, je mit dem Verbraucher; ohne die Angabe
    gilt ``referenced``. ``continuations`` sind die von der Operation selbst
    belegten Übergänge (``OpResult.feature_continuations``), bereits auf
    Struktur geprüft. ``scope`` benennt die Fassung des Erzeugers — roher
    Operationsschlüssel und Ausgabeindex —, für die eine native Neuwahl gilt;
    ohne ihn wird am exakten Körper nicht gefragt, sondern angehalten. Alles
    drei braucht nur der exakte Körper — am Netz entscheidet die
    Neuerkennung mit der Zuordnungsfrage.

    ``touches_features`` sagt, ob diese Operation Merkmale **einführt** — das
    Flag stand seit je im Register und hatte bis heute keinen Leser. Es
    entscheidet hier, ob ein neu erkanntes Merkmal seinen Erzeuger bekommt;
    ``load`` und ``decimate_mesh`` tragen es nicht, und das ist der Punkt.

    §21.2: die Erkennung läuft nach jeder Operation, sonst ist ``hole_3`` in
    Schritt fünf ein anderes Loch als in Schritt vier. Wo die Zuordnung
    mehrdeutig ist, entscheidet der Nutzer (§21.3) — das eine, was hier nie
    passiert, ist Raten.

    **Und die Antwort wird festgehalten (§15.7).** Vorher galt sie für diesen
    Lauf und war danach vergessen: Gemessen kostete ein Durchgang durch neun
    heruntergeladene Modelle **99 modale Fenster für 7 verschiedene
    Entscheidungen**, weil jede Auswertung dieselben Fragen neu stellte.
    ``operation.matches`` trägt sie jetzt mit; ``recorded`` nimmt neue
    Antworten auf und reicht sie nach oben, wo sie in den Stapel geschrieben
    werden. Ohne dieses Festhalten wäre die Auswertung außerdem nicht die reine
    Funktion, die §15.1 verlangt — eine Antwort, die nur in der Sitzung lebt,
    wäre ein sechster Eingang neben Stack, Quellen, Parametern, Profilen und
    Startwerten.

    **``cancelled`` und ``say`` reichen bis hierher (§2.8).** Beides fehlte,
    und die Folge war messbar: Erkennung und Zuordnung sind der längere Teil
    eines Schritts, sobald ein Netz viele Merkmale mitbringt — 101,6 von 101,8
    Sekunden an einem einzigen ``fit_to_size``. Der Abbrechen-Knopf wirkte in
    dieser ganzen Zeit nicht, denn das Token wurde nur am Kopf der
    Operationsschleife abgefragt, und die Leiste nannte weiter eine Operation,
    die längst fertig war. ``say`` bekommt nur den Text: Welcher Bruchteil des
    Ganzen gerade läuft, weiß der Aufrufer, nicht diese Funktion.
    """
    watch = cancelled or NeverCancelled()
    mesh = entry.mesh
    if not isinstance(mesh, MeshData):
        # Ein exakter Körper hat keine Dreiecke, an denen die Erkennung messen
        # könnte — seine Merkmale kommen aus der Topologie und werden dort
        # gerechnet, wo er entsteht. Bewegt wurde er hier trotzdem
        # (siehe :func:`_carried_along`).
        #
        # **Was die Operation unverändert durchgereicht hat, belegt sich
        # selbst** — gemessen vor der starren Mitnahme, denn danach ist ein
        # bewegtes Merkmal kein gleiches mehr. Alles andere braucht einen
        # Beleg: den der Operation (``continuations``) oder die eindeutige
        # Zuordnung auf denselben Namen.
        passed_through = frozenset(_inherited_features(entry.features, previous))
        exact_entry = _carried_along(entry, previous, transform, previous_bounds, cancelled=watch)
        wanted: Mapping[FeatureId, tuple[str, ...]] = (
            dict.fromkeys(referenced, ()) if needed is None else needed
        )
        wanted = {name: who for name, who in wanted.items() if name in previous}
        continued = frozenset(
            entry_.source.feature_id
            for entry_ in continuations
            if entry_.source.object_id == entry.id
            and entry_.target == entry_.source.feature_id
            and entry_.target in exact_entry.features
        )
        unproven = set(wanted) - passed_through - continued
        matched: MatchResult | None = None
        reference_features: dict[FeatureId, Feature] = previous
        if (
            previous
            and (touches_features or unproven)
            and max(len(previous), len(exact_entry.features)) <= FEATURE_LIMIT_COUNT
        ):
            # Die native Erkennung benennt frisch. Gleiche Namen beweisen
            # deshalb keinen Vorfahren; es gilt dieselbe eindeutige Zuordnung
            # wie am Netz — auch bei Operationen ohne ``touches_features``:
            # *Fläche versetzen* und *Formschräge* bauen den Körper neu und
            # tragen das Flag nicht, denn es beschreibt das Einführen von
            # Merkmalen, nicht das Erhalten von Bezügen. Eine gemeldete
            # Bewegung wird dabei an den alten Maßen nachgeführt, wie am Netz.
            watch.raise_if_cancelled()
            if transform is not None:
                reference_features = transformed_features(
                    previous, transform, check_cancelled=watch.raise_if_cancelled
                ).candidates
            matched = match(
                reference_features,
                exact_entry.features,
                mesh.bounds.centre,
                mesh.bounds.diagonal,
                check_cancelled=watch.raise_if_cancelled,
            )
            watch.raise_if_cancelled()
            if set(matched.ambiguous) & referenced:
                # Ein gleichlautender nativer Topologiename ist kein Beleg
                # für die alte Fläche. Netzantworten benennen keine B-Rep-
                # Träger um; hierfür ist bestätigte native Historie nötig.
                raise AmbiguityError(
                    _(
                        "Die bisherigen Flächenbezüge sind am exakten Körper nicht eindeutig. "
                        "Wählen Sie die betroffenen Flächen im Folgeschritt erneut aus."
                    ),
                    candidates=tuple(sorted(set(matched.ambiguous) & referenced)),
                )
            if touches_features:
                exact_entry = dataclasses.replace(
                    exact_entry,
                    features=_feature_originators(
                        inherit_originators(exact_entry.features, matched, previous),
                        matched,
                        operation,
                        touches_features,
                        True,
                    ),
                )
        if matched is not None and unproven:
            # **Was der Umbau nicht berührt hat, trägt seinen Namen weiter.** Die
            # native Erkennung nummeriert neu, und eine unberührte Fläche kam
            # unter anderem Namen zurück — gefragt wurde nach jeder, auf die eine
            # Passung zeigte. Bitgleich gemessen, ist sie ein Beleg
            # (:func:`_unchanged_continuations`, 23.09.2026).
            exact_entry, matched = _unchanged_continuations(
                exact_entry, reference_features, unproven, matched
            )
        lost = _unproven_native_references(unproven, exact_entry, matched)
        if lost and matched is not None and scope is not None:
            # **Die native Neuwahl** (§21.3): Was die Zuordnung nicht belegt,
            # entscheidet der Kunde am tatsächlich neu gebauten Körper — je
            # alter Bezug die aktuellen Merkmale derselben Art, die noch keinen
            # alten Namen tragen. Dieselbe Gruppen-, Fingerabdruck- und
            # Atomizitätsmechanik wie am Netz, aber in eigener Domäne mit
            # Erzeugerscope: Eine Netzantwort gibt native Konkurrenz nicht
            # frei, und eine andere Erzeugerfassung fragt neu.
            exact_entry, matched = _native_reselection(
                exact_entry,
                previous,
                {name: wanted[name] for name in lost},
                matched,
                operation,
                ask,
                findings,
                recorded,
                watch,
                question_context,
                scope,
            )
            lost = _unproven_native_references(
                set(lost) - set(matched.mapping), exact_entry, matched
            )
        if lost:
            # Atomar an der Erzeugergrenze: keine Ausgabe, keine Antwort, kein
            # Folgecache. Der Befund nennt den späteren Verbraucher, damit der
            # Halt nicht wie ein falscher Wert dieses Schritts aussieht. Wer
            # hier ankommt, hat entweder keine Fassung zum Fragen, keinen
            # Kandidaten derselben Art oder „Nicht weiterführen" gewählt —
            # ein erneutes Wählen derselben alten Kennung heilt nichts.
            raise NativeReferenceLost(
                _(
                    "Dieser Schritt baut den exakten Körper neu, und ein späterer Bezug "
                    "auf eine seiner Flächen ist danach nicht belegt. Wählen Sie die Fläche "
                    "dort neu, oder nehmen Sie den Schritt mit Strg+Z zurück."
                ),
                references=tuple(FeatureRef(entry.id, name) for name in sorted(lost)),
                values={
                    "where": "; ".join(sorted({who for name in lost for who in wanted[name]})),
                    "operation": str(operation.op),
                },
                object_id=entry.id,
            )
        return exact_entry
    local_only = mesh.triangle_count > FEATURE_LIMIT_TRIANGLES
    if local_only:
        from app.core.perceive.local import detect_known

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
        if not previous and not entry.features:
            return entry

    # Merkmale, die ein Baustein mitgebracht hat, werden nicht neu erkannt —
    # sie wurden beim Bauen benannt (§24.1), und eine Neuerkennung benennte
    # eine Bohrung um, die schon einen Namen hat. Sie reisen mit dem Körper
    # wie alles andere.
    # **Wer ein Merkmal durchreicht, hat es nicht erzeugt** — darum nur, wo
    # noch nichts steht. ``entry`` ist das Objekt, das *diese* Operation
    # ausgegeben hat; was darin erzeugt ist und noch keinen Erzeuger trägt, ist
    # hier entstanden. Gibt eine spätere Operation dasselbe Merkmal erneut aus,
    # bleibt die Nummer stehen.
    #
    # Genau daran scheitert ``SceneObject.created_by`` als Antwort auf dieselbe
    # Frage: Es wird weiter oben bei **jeder** Operation gesetzt, die das
    # Objekt ausgibt, und zeigt deshalb auf die zuletzt beteiligte statt auf
    # die erzeugende (§21.2).
    # Ob vor dieser Operation überhaupt schon Merkmale bekannt waren. Ohne das
    # wäre „neu" nach dem Laden die ganze Menge (3d-druck-61) — und nach einem
    # Schritt, bei dem die Erkennung wegen der Dreiecksgrenze übersprungen
    # wurde, hieße „neu" nur „endlich sichtbar".
    knew_features = bool(previous)

    # Ausdrücklich ausgegebene Merkmale stehen bereits im Ergebnisraum.
    # Nur unverändert geerbte Einträge folgen der gemeldeten Bewegung.
    feature_movement = transform
    if feature_movement is None and previous_bounds is not None:
        feature_movement = _shift_between(previous_bounds, mesh.bounds)
    inherited = _inherited_features(entry.features, previous)
    transformed = (
        transformed_features(
            previous,
            feature_movement,
            mesh=mesh if transform is not None else None,
            check_cancelled=cancelled.raise_if_cancelled if cancelled else None,
        )
        if feature_movement is not None
        else FeatureTransform(dict(previous), frozenset(previous))
    )
    output_features = dict(entry.features)
    if feature_movement is not None:
        output_features = {
            name: feature for name, feature in output_features.items() if name not in inherited
        }
        output_features.update(
            (name, transformed.candidates[name]) for name in inherited if name in transformed.exact
        )
    if transform is not None:
        # Eine reine Transformation belegt auch unsichtbare Bausteinmerkmale.
        # Ihre Zuordnung läuft zusammen mit den deklarierten Merkmalen, damit
        # eine nun mögliche Erkennung keinen zweiten Namen daneben erzeugt.
        output_features = {
            **{
                name: feature
                for name, feature in transformed.candidates.items()
                if name in transformed.exact and feature.provenance == "generated"
            },
            **output_features,
        }

    declared = {
        name: (
            feature
            if feature.created_by is not None
            else dataclasses.replace(feature, created_by=operation.id)
        )
        for name, feature in output_features.items()
        if feature.provenance == "generated"
    }
    watch.raise_if_cancelled()
    if say is not None:
        say(str(_("Merkmale erkennen")))
    if local_only:
        detected = detect_known(
            mesh,
            {**transformed.candidates, **output_features},
            check_cancelled=watch.raise_if_cancelled,
        )
    else:
        # **Ein bewegtes Netz wird nicht neu untersucht.** Meldet die
        # Operation eine starre Bewegung und ist die Ausgabe belegbar das
        # bewegte Eingangsnetz — dieselben Dreiecke, jede Ecke dort, wo die
        # Matrix sie hinbewegt —, dann stehen seine Merkmale schon im Merker
        # des Eingangs und werden dorthin übertragen; ``detect`` trifft
        # danach. Die Zuordnung darunter läuft unverändert und findet, was
        # sie bis zum 22.09.2026 nach 1,3 s Neuerkennung auch fand: alles
        # beim Alten. Ohne Beleg — anderes Netz, Skalierung, kein Eintrag im
        # Merker — rechnet die Erkennung wie zuvor.
        if transform is not None and isinstance(source_mesh, MeshData):
            carry_detection(source_mesh, mesh, transform, check_cancelled=watch.raise_if_cancelled)
        if not detect_features and not referenced and not needed:
            # **Die Vorschau rechnet keine Erkennung, die niemand liest.**
            # Der Dialog zeigt Geometrie und Differenz; die Erkennung am
            # geänderten Körper kostete je getippter Zahl an 204 000
            # Dreiecken 1,1 der 2,2 Sekunden (gemessen am 22.09.2026) und
            # war beim Übernehmen ohnehin ein Merker-Treffer für genau ein
            # Netz — das letzte. Was der Merker kennt, kommt trotzdem;
            # sonst bleibt der Körper bei dem, was die Operation ausgab, ohne
            # Zuordnung und ohne Waisenbefund, wie bei ``perceive.too_many``.
            remembered_features = known_detection(mesh)
            if remembered_features is None:
                return (
                    dataclasses.replace(entry, features=output_features)
                    if feature_movement is not None
                    else entry
                )
            detected = remembered_features
        else:
            detected = detect(mesh, check_cancelled=watch.raise_if_cancelled)
    watch.raise_if_cancelled()

    # **Was auf einer Freiform weggelassen wurde, steht hier, nicht nirgends.**
    # ``detect`` nimmt Kugeln, Ringe, Kegel und Verrundungen von einem Modell,
    # das die Erkennung als Freiform einstuft (``features._shapes_on_a_freeform``),
    # denn dort bezeichnen sie nichts — ein Kiefer-Scan brachte 281 davon.
    # Ohne den Satz sähe der Kunde einen Objektbaum, dem etwas fehlt, und
    # fände nirgends den Grund (Regel 17); ein Merkmal, das still verschwindet,
    # ist schlimmer als eines, das dasteht.
    left_out = freeform_dropped(mesh)
    if left_out or recognised_as_freeform(mesh):
        findings.append(
            Finding(
                code="perceive.freeform",
                severity="info",
                # **Der Satz sagt, was gemessen wurde — nicht, woher das Teil
                # kommt** (RM-151). Er hieß „Dieses Modell ist eine Freiform,
                # etwa ein Scan", und das liest ein Kunde als Aussage über sein
                # Teil: Roberts `garden-hose-holder.3mf` ist ein konstruierter
                # Halter, dessen geschwungener Bogen ihn mit 0,701 gegen die
                # Schwelle 0,700 dorthin brachte — ein Tausendstel.
                #
                # **Die Entscheidung darunter ist richtig und bleibt.** Eine
                # gekrümmte Fläche passt örtlich immer auf eine Kugel; die
                # Nachtrennung zerlegt sie in Dutzende Flecken, und jeder
                # fittet. Was fällt, ist die Herkunftsbehauptung daneben.
                #
                # **Und ein zweiter Zustand** — „überwiegend rund" gegen
                # „Freiform" — **kommt nicht.** Er kostete eine zweite Schwelle,
                # und die Lücke zwischen Nozzle-Box (59 Prozent) und Retro-Maus
                # (77 Prozent) ist schmal; zwei Sätze, deren Grenze niemand
                # nachmisst, sind schlechter als einer, der wahr ist.
                # **Und der Satz gilt auch ohne eine einzige weggelassene Form**
                # (RM-193): Die Splitter einer glatten Haut werden gar nicht
                # erst eingepasst, also fand die Erkennung dort nichts, das sie
                # weglassen könnte — und geführt werden Rundformen auf ihr
                # trotzdem nicht.
                message=_(
                    "Die Oberfläche dieses Modells ist überwiegend gekrümmt. Auf einer "
                    "solchen Fläche sind Kugeln, Ringe, Kegel und Verrundungen keine "
                    "Merkmale und werden nicht geführt; Bohrungen, Zapfen und ebene "
                    "Flächen bleiben."
                ),
                object_id=entry.id,
                op_id=operation.id,
                values={"dropped": left_out},
            )
        )

    # **Und ein Einschluss, den die Erkennung nicht lesen konnte, steht ebenso
    # hier.** ``detect`` liest Schalenpaare über die native Differenz; wo die
    # nicht antwortet, fehlt der Lufteinschluss im Baum, und der Kunde
    # druckte das Teil, ohne von der Luft darin zu wissen (Paket C, 21.09.2026).
    unreadable = unreadable_void_shells(mesh)
    if unreadable:
        findings.append(
            Finding(
                code="perceive.voids_unreadable",
                severity="warning",
                message=_(
                    "Dieses Modell besteht aus mehreren Schalen, und ob eine davon ein "
                    "Lufteinschluss ist, ließ sich nicht sicher lesen. Reparieren Sie das "
                    "Netz, oder prüfen Sie es im Slicer auf eingeschlossene Luft."
                ),
                object_id=entry.id,
                op_id=operation.id,
                values={"shells": unreadable},
            )
        )

    # **Und hier hört es auf, wenn es zu viele geworden sind.** Die
    # Dreiecksgrenze oben zählt Dreiecke; diese zählt, was daraus geworden ist,
    # und die zwei hängen nicht aneinander. Ein ungeschweißtes Netz weit
    # unterhalb der Dreiecksgrenze brachte ein Merkmal je Dreieck mit, und die
    # Zuordnung darunter war quadratisch in deren Zahl (siehe
    # ``FEATURE_LIMIT_COUNT`` — die Grenze liegt seit dem Wabenmuster so, dass
    # ein ehrliches Muster darunter bleibt).
    #
    # **Gar keine Zuordnung und nicht eine halbe.** Die erkannten Merkmale
    # trotzdem einzuhängen wäre die verlockende Hälfte — und die falsche: Ihre
    # Namen entstünden dann bei jeder Auswertung neu, und eine Passung, die auf
    # ``hole_3`` zeigt, zeigte danach still auf ein anderes Loch. Das ist genau
    # das Raten, das §21.2 verbietet. Übrig bleibt, was die Operation ausgegeben
    # hat, dazu ein Satz, der sagt warum — dieselbe Bauart wie
    # ``perceive.too_large``.
    if len(detected) > FEATURE_LIMIT_COUNT:
        findings.append(
            Finding(
                code="perceive.too_many",
                severity="info",
                message=_(
                    "Dieses Modell hat mehr einzelne Merkmale, als Solidon über die "
                    "Schritte hinweg zuordnet. Ist es ungeschweißt, verschweißen Sie es "
                    "beim Laden; sonst bleibt es ohne Merkmale bearbeitbar."
                ),
                object_id=entry.id,
                op_id=operation.id,
                values={"features": len(detected), "limit": FEATURE_LIMIT_COUNT},
            )
        )
        return (
            dataclasses.replace(entry, features=output_features)
            if feature_movement is not None
            else entry
        )

    # **Was die Erkennung hier nicht sieht, wird später nicht an ihr gemessen.**
    # Ein Baustein benennt seine Bohrungen beim Bauen; ``detect`` findet sie
    # nicht — an der Dose mit Deckel eine von vier. Ohne diesen Vermerk wanderten
    # die drei anderen beim nächsten Schritt in ``checked`` (weil ``hole`` eine
    # erkennbare Art ist), fanden keinen Partner und verwaisten. Nicht weil sie
    # weg waren, sondern weil sie nie da gewesen waren — gemessen von
    # 3d-druck-3a am 23.08.2026.
    #
    # Gefragt wird über dieselbe Zuordnung, die auch sonst zuordnet: Wer keinen
    # Partner findet, ist ``orphaned``. Mehrdeutig zählt als gefunden — zwei
    # Kandidaten sind ein Kandidat zu viel, nicht keiner.
    if declared:
        watch.raise_if_cancelled()
        if say is not None:
            say(str(_("Merkmale zuordnen")))
        seen = match(
            declared,
            detected,
            mesh.bounds.centre,
            mesh.bounds.diagonal,
            check_cancelled=watch.raise_if_cancelled,
        )
        # **Ein erklärtes Merkmal sucht seinen Partner an seiner Stelle.** Die
        # Zuordnung toleriert 8 % der Diagonale, weil zwischen zwei Schritten
        # ungeklärt gewandert werden darf; was die Operation selbst gesetzt hat,
        # steht aber dort, wo sie es sagt. Am Schraubenhalter nahm eine
        # verschobene Senkung die der Nachbarbohrung 18 mm daneben, und
        # ``cone_2`` war verwaist, ohne dass jemand es angefasst hatte
        # (23.09.2026). Weiter weg als seine eigene Größe ist es nicht es selbst.
        far = {
            name
            for name, found in seen.mapping.items()
            if not _near_its_declaration(declared[name], detected[found])
        }
        if far:
            seen = dataclasses.replace(
                seen,
                mapping={name: found for name, found in seen.mapping.items() if name not in far},
                orphaned=(*seen.orphaned, *sorted(far)),
            )
        blind = set(seen.orphaned)
        # Randöffnungen sind geometrisch erkennbare Langlöcher. Fehlt ihre
        # Wand, darf ein mitgetragener Eintrag nicht zur ungeprüften Zusage
        # eines Bausteins werden. Der Vorgänger läuft unten durch die normale
        # Verlustmeldung und verschwindet aus der Auswahl.
        declared = {
            name: feature
            for name, feature in declared.items()
            if not (
                name in blind
                and (
                    feature.params.get("open")
                    or (
                        feature_movement is not None
                        and name in inherited
                        and name not in transformed.exact
                        and feature.recognised
                    )
                )
            )
        }
        # **Der Name bleibt, die aktuelle Oberfläche geht mit.** Ein Baustein
        # kennt Ort und Maß seiner Bohrung, aber nicht die Dreiecksnummern des
        # Netzes, das erst aus seiner Geometrie entsteht. Die Erkennung kennt
        # genau diese Nummern. Bei einer eindeutigen Zuordnung gehören sie
        # deshalb an das benannte Merkmal, bevor dessen technischer Doppelname
        # unten entfernt wird. Ohne die Übergabe war die Auswahl im Baum
        # richtig, im Viewport erschien aber nur der Beschriftungspunkt.
        visible_faces = {
            old_name: detected[new_name].face_indices
            for old_name, new_name in seen.mapping.items()
            if new_name in detected
        }
        visible_patches = {
            old_name: detected[new_name].surface_patches
            for old_name, new_name in seen.mapping.items()
            if new_name in detected
        }
        visible_scopes = {
            old_name: {"local_search_radius": detected[new_name].params["local_search_radius"]}
            for old_name, new_name in seen.mapping.items()
            if local_only
            and new_name in detected
            and "local_search_radius" in detected[new_name].params
        }
        declared = {
            name: (
                dataclasses.replace(
                    feature,
                    face_indices=visible_faces[name],
                    surface_patches=visible_patches[name],
                    params={**feature.params, **visible_scopes.get(name, {})},
                )
                if name in visible_faces
                else feature
            )
            for name, feature in declared.items()
        }
        declared = {
            name: (
                feature
                if name not in blind
                else dataclasses.replace(feature, recognised=False, surface_patches=())
            )
            for name, feature in declared.items()
        }
        # **Und was einen benannten Partner hat, kommt nicht zusätzlich in die
        # Szene.** Der Kommentar weiter oben sagt es seit je voraus — „eine
        # Neuerkennung benennte eine Bohrung um, die schon einen Namen hat" —,
        # nur wurden beide eingehängt: die benannte Bohrung des Bausteins und
        # dieselbe Bohrung noch einmal als ``hole_1``. Gemessen von 3d-druck-3a
        # trägt in zwei von drei Beispielen jedes zweite bis dritte benannte
        # Merkmal einen solchen Zwilling.
        #
        # Für den Kunden sind das zwei Einträge im Merkmalsbaum für ein Loch,
        # von denen einer die Provenienz und den Namen trägt, auf den eine
        # Passung zeigt (§14), und der andere nichts, was der erste nicht
        # hätte. Beim nächsten Schritt streiten beide um denselben Nachfolger,
        # und das benannte verliert — so verschwand ``heatset_m4_bore_1``.
        #
        # **Nur eindeutige Paare.** ``mapping`` führt, was mit Abstand gewonnen
        # hat; ``ambiguous`` bleibt ausdrücklich draußen. Bei einem Gleichstand
        # weiß niemand, welches erkannte Merkmal das benannte meint, und dann
        # sind zwei Namen besser als ein falsch gelöschter.
        #
        # Wird der Baustein-Schritt später entfernt, gibt es kein benanntes
        # Merkmal mehr; die Erkennung findet die Bohrung dann normal und
        # benennt sie selbst. Die Unterdrückung gilt nur, solange der Name
        # existiert.
        detected = {
            name: feature
            for name, feature in detected.items()
            if name not in set(seen.mapping.values())
        }

    # Ein gedrehter Körper sieht für einen Positionsvergleich aus wie ein
    # anderer Körper. Die Operation weiß, was sie gedreht hat — also werden die
    # alten Merkmale erst mitgenommen und dann verglichen (§21.2).
    previous = {
        **transformed.candidates,
        **{
            name: feature
            for name, feature in output_features.items()
            if feature.provenance == "detected"
        },
    }

    # **Ein erzeugtes Merkmal, das die Operation nicht selbst wieder ausgibt,
    # wird mitgenommen — nicht vergessen.** Hier stand bis zum 22.08.2026, dass
    # die erzeugten Merkmale allein aus der *Ausgabe* kommen. Elf Stellen unter
    # ``app/core/geom/`` geben aber ``features={}`` zurück, ohne damit etwas zu
    # meinen: Sie füllen das Feld nur nicht. Für die erkannten Merkmale ist das
    # folgenlos, die kommen aus ``previous``; die erzeugten fielen dabei
    # lautlos aus der Szene, und mit ihnen die Provenienz-IDs, die §21.2
    # „keine Erkennung, keine Mehrdeutigkeit" nennt. Nachgestellt: ein Körper
    # mit ``op3.pin_1`` und eine Operation, die das Feld leer lässt, kam mit
    # null erzeugten Merkmalen und **null Befunden** heraus.
    carried = {
        name: feature
        for name, feature in previous.items()
        if getattr(feature, "provenance", "detected") == "generated" and name not in declared
    }
    # Mitnehmen heißt nicht glauben. Wo die Erkennung die Art des Merkmals
    # sieht, wird es wie ein erkanntes zugeordnet und fällt heraus, wenn es
    # wirklich weg ist — sonst wäre aus dem lautlosen Verlust ein lautloses
    # Gespenst geworden, und das ist schlimmer: §21.3 hält die Auswertung an,
    # sobald eine späte Op auf eine ID zeigt, die nichts mehr bezeichnet.
    # ``recognised`` und nicht nur die Art: Ein Baustein bringt Bohrungen mit,
    # die ``detect`` an ihrer Stelle nicht findet (§24.1). Sie an der Erkennung
    # zu messen hieße, sie bei jedem Folgeschritt verwaisen zu lassen — und die
    # Unterscheidung „Gewinde reist mit, Bohrung nicht" hinge daran, ob zufällig
    # eine andere Art denselben Namen trägt.
    checked = {
        name: f
        for name, f in carried.items()
        if (f.kind in DETECTABLE_KINDS and f.recognised)
        or (transform is not None and name not in transformed.exact)
    }
    # Und was sie nicht sieht, reist ungeprüft mit. Ein Gewinde ist der Fall:
    # es entsteht in einem Baustein, ``detect`` kennt die Art nicht, und geprüft
    # verlöre es jede Operation.
    unchecked = {name: f for name, f in carried.items() if name not in checked}

    previous = {
        name: feature
        for name, feature in previous.items()
        if getattr(feature, "provenance", "detected") != "generated"
    }
    previous = {**previous, **checked}
    # **Was die Operation unter einem alten Namen neu ausgibt, ist dessen
    # Nachfolger.** *Bohrung ändern* gibt ``hole_1`` mit dem neuen Durchmesser
    # selbst zurück (``_recognised_resized_feature``), weil ein Sprung von
    # 5,19 auf 7,18 mm die Zuordnungstoleranz sprengt und genau hier die
    # ausdrückliche Absicht ist. Die Zuordnung der benannten Merkmale oben hat
    # den erkannten Zwilling dann schon gestrichen — und die alte ``hole_1``
    # fände im Vergleich keinen Partner mehr. Bis zum 02.09.2026 verwaiste sie
    # deshalb: ``perceive.orphaned`` stand unter dem Schritt, der diese
    # Bohrung bewusst geändert hatte, und die Kennung überlebte nur über den
    # neuen Eintrag. Der Vorgänger eines neu ausgegebenen Namens hat hier
    # nichts mehr zu suchen.
    previous = {name: feature for name, feature in previous.items() if name not in declared}

    # **Was aus den Dreiecken einer benannten Wendel besteht, ist die Wendel.**
    # Die Erkennung kennt die Art ``thread`` nicht (§21.1). Sie sieht eine
    # Schraubenlinie und passt darauf ein, was sie kennt — und findet immer
    # etwas: An einem M6-Bolzen zwei Kegel, an M4, M5 und M8 zwei Zapfen, an
    # M3 bei Länge 20 neunzehn Kugeln. Gemessen über die ganze Größentabelle
    # gibt es keinen Fall ohne. Für den Kunden stehen sie neben dem Gewinde im
    # Baum, mit Maßen, die er nirgends eingegeben hat: Ein Kunden-Screenshot
    # vom 04.09.2026 zeigt „Zapfen · Ø 5,79 mm" an einem M6-Bolzen — das ist
    # der verschmolzene Gewindekamm.
    #
    # ``features._without_thread_turns`` fängt sie nicht: Es verlangt drei
    # koaxiale Zylinder, und ``_merged_cylinders`` läuft drei Zeilen davor und
    # verschmilzt die Gänge auf zwei. Kegel und Kugeln filtert es ohnehin
    # nicht. Das ist dort zu reparieren, wo ein Gewinde **ohne** Baustein
    # ankommt — in einer eingelesenen STL. Hier ist der Fall der andere und
    # der sichere: Der Baustein hat das Gewinde benannt, also ist bekannt, wo
    # es steht.
    #
    # **Dieselbe Zusage wie eine Zeile weiter oben**, nur über die Geometrie
    # statt über die Zuordnung: Was einen benannten Partner hat, kommt nicht
    # zusätzlich in die Szene.
    threads = tuple(
        feature
        for feature in (*declared.values(), *unchecked.values(), *checked.values())
        if feature.kind == "thread"
        and (transform is None or feature.id in transformed.exact or feature.id in declared)
    )
    if threads:
        detected = {
            name: feature
            for name, feature in detected.items()
            if not _cut_from_a_thread(mesh, threads, feature)
        }

    if not previous:
        return dataclasses.replace(entry, features={**detected, **unchecked, **declared})

    centre = mesh.bounds.centre
    # Beide Karten stehen jetzt im Ergebnisraum, auch bei Mehrkörper-Ops mit
    # selbst nachgeführten Merkmalen und bei einer aus den Hüllen erkannten
    # Verschiebung. Eine zweite Schwerpunktkorrektur wäre eine zweite Bewegung.
    watch.raise_if_cancelled()
    if say is not None:
        say(str(_("Merkmale zuordnen")))
    matched = match(
        previous,
        detected,
        centre,
        mesh.bounds.diagonal,
        check_cancelled=watch.raise_if_cancelled,
    )

    _answer_matches(
        dataclasses.replace(entry, features=detected),
        matched,
        operation,
        ask,
        findings,
        recorded,
        referenced,
        watch,
        question_context,
        legacy_eligible,
    )

    # Eine bekannte Abbildung kann mehr belegen als die erneute Erkennung.
    # Das gilt nur für weiterhin exakt beschreibbare Merkmale; der Kandidat
    # einer elliptisch verzerrten Bohrung darf hier niemals zur Zusage werden.
    rigid_orphans: dict[str, Feature] = {}
    arranged_rigidly = operation.op == "arrange_bed" and feature_movement is not None
    for old_id in matched.orphaned:
        old_feature = previous.get(old_id)
        if (
            (transform is not None and old_id in transformed.exact) or arranged_rigidly
        ) and old_feature is not None:
            rigid_orphans[old_id] = old_feature
            continue
        # Was außerhalb des neuen Körpers liegt, ist nicht verlorengegangen —
        # es wurde weggeschnitten, und zwar von jemandem, der genau das wollte.
        # Ein Prüfstück schneidet 22 mm aus einem 70er Gehäuse: acht Merkmale
        # bleiben draußen, und acht Warnungen darüber sind acht Warnungen über
        # eine gelungene Operation.
        if _outside(old_feature, mesh.bounds, False):
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
        # Ein **verwendetes erzeugtes** Merkmal ist die Ausnahme von dieser
        # Zurückhaltung, und es bekommt deshalb seinen eigenen Befund. Es trägt
        # einen Namen, den eine Operation vergeben hat, eine Passung kann
        # darauf zeigen (§14), und der Agent verweist darauf statt auf
        # Koordinaten (Leitprinzip 5). Dass es fort ist, ist dann eine Warnung
        # — anders als bei einer unbenutzten Hilfsfläche, die eine formende
        # Operation erwartbar mitnimmt.
        #
        # Zwei Aufrufe statt eines Fragezeichens, und das hat einen Grund:
        # ``tests/test_orphans.py`` liest diesen Quelltext und verlangt, dass
        # ``perceive.orphaned`` wörtlich mit ``info`` gemeldet wird. Ein Ternär
        # an der Stelle sieht kürzer aus und nimmt dem Test seine Aussage.
        #
        # **Und ein verwendetes erkanntes Merkmal ebenso** (RM-189). Zeigt eine
        # Passung oder ein späterer Schritt auf eine Bohrung, die dieser
        # Schritt unkenntlich gemacht hat — *Glätten* am Bohrhalter nahm allen
        # 29 Bohrungen die Zylinderform, starkes *Dreiecke verringern* sieben —,
        # stand im Bericht nur die Passung ohne Merkmal, und welcher Schritt es
        # war, suchte der Kunde selbst. Der Befund steht am Schritt und führt zu
        # ihm (*Eingabe korrigieren*), wie jeder Befund aus einer Operation.
        # Gezählt wird dabei nur, wer **nach** diesem Schritt noch auf das
        # Merkmal zeigt (``needed``, :func:`_needed_after`): *Fläche versetzen*
        # verbraucht seine Fläche selbst, und am Zylinder des Piratenschiffs
        # meldete jeder zweite Versatz einen Verlust, den niemand hatte
        # (23.09.2026).
        generated = getattr(old_feature, "provenance", "detected") == "generated"
        later = needed.get(old_id, ()) if needed is not None else ()
        if (old_id in referenced) if generated or needed is None else (old_id in needed):
            values: dict[str, Any] = {"feature": old_id}
            if later:
                values["where"] = "; ".join(later)
            findings.append(
                Finding(
                    code="perceive.generated_lost" if generated else "perceive.referenced_lost",
                    severity="warning",
                    message=_(
                        "Ein benanntes Merkmal ist nach dieser Operation nicht mehr auffindbar."
                    )
                    if generated
                    else _(
                        "Ein Merkmal, auf das sich eine Passung oder ein späterer Schritt "
                        "bezieht, ist nach diesem Schritt nicht mehr erkennbar."
                    ),
                    object_id=entry.id,
                    op_id=operation.id,
                    values=values,
                    suggestions=(CORRECT_INPUT, SHOW_HISTORY),
                )
            )
            continue

        findings.append(
            Finding(
                code="perceive.mended" if defect else "perceive.orphaned",
                severity="info",
                message=(
                    _("Eine offene Stelle ist geschlossen und damit fort.")
                    if defect
                    else _(
                        "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
                        "wiederzuerkennen."
                    )
                ),
                object_id=entry.id,
                op_id=operation.id,
                values={"feature": old_id},
            )
        )

    # **Wer ein Merkmal einführt, ist sein Erzeuger — unter drei Riegeln.**
    # Ein Baustein bringt Verrundungen und Flächen mit, die ``detect`` findet
    # und die deshalb als „erkannt" gelten. Ohne Erzeuger führt von ihnen kein
    # Weg zurück zu dem Schritt, der sie gemacht hat: „Diesen Schritt ändern"
    # (§21.2) hängt an ``created_by``, und der Kunde sieht sechs Verrundungen,
    # von denen keine den Einhänger nennt (Befund Robert, 25.08.2026).
    #
    # Die Grenze im Kommentar oben — „wer ein Merkmal durchreicht, hat es nicht
    # erzeugt" — bleibt wahr. Sie wird hier nicht verschoben, sondern um einen
    # Fall ergänzt, den drei Riegel eng halten (Entwurf 3d-druck-61):
    #
    # * **Nur Operationen, die Merkmale einführen** (``touches_features``).
    #   Nach ``load`` ist jedes erkannte Merkmal neu; ohne diesen Riegel trüge
    #   jede Bohrung jedes importierten Modells den Lade-Schritt, und dasselbe
    #   nach *Dreiecke verringern*, sobald das Netz unter die Erkennungsgrenze
    #   fällt.
    # * **Nur, wenn vorher schon erkannt war** (``knew_features``). Sonst heißt
    #   „neu" nicht „entstanden", sondern „zum ersten Mal angesehen".
    # * **Nie ein Kandidat einer Mehrdeutigkeit.** Unverwiesene mehrdeutige
    #   Merkmale binden seit dem Verweisfilter (08246414) absichtlich nicht und
    #   erscheinen der Zuordnung in jedem Lauf als neu — ein Kandidat kann das
    #   alte Merkmal selbst sein.
    #
    # Was neu ist, sagt ``matched.fresh`` — auch dieses Feld hatte bis heute
    # keinen Leser, und es nachzubauen hieße, dieselbe Frage ein zweites Mal
    # zu beantworten. Die Kandidaten müssen trotzdem eigens heraus: Bei einer
    # Mehrdeutigkeit bindet die Zuordnung keinen von ihnen, und damit stehen
    # sie alle in ``fresh``.
    detected = _feature_originators(detected, matched, operation, touches_features, knew_features)

    mapped = apply_mapping(detected, matched, previous=previous)
    # Ein Bezeichner, der von einem erzeugten Merkmal kommt, bleibt erzeugt.
    # ``apply_mapping`` trägt den *Namen* weiter, die Provenienz steckt aber im
    # Merkmal, das gerade erkannt wurde — und das ist per Definition
    # „detected". Ohne diese Zeile wäre ``op3.pin_1`` nach der ersten
    # Operation ein erkannter Stift mit einem erzeugten Namen, und die nächste
    # Erkennung dürfte ihn umbenennen.
    for name in checked:
        found = mapped.get(name)
        if found is not None and found.provenance != "generated":
            mapped[name] = dataclasses.replace(found, provenance="generated")
    return dataclasses.replace(
        entry,
        features={**mapped, **rigid_orphans, **unchecked, **declared},
    )


def _near_its_declaration(declared: Feature, found: Feature) -> bool:
    """Ob ein erkanntes Merkmal dort liegt, wo die Operation ihr erklärtes gesetzt hat.

    Quer zur Achse darf der Mittelpunkt höchstens um die Breite des erklärten
    Merkmals abweichen — Durchmesser, bei einem Langloch seine Länge —, entlang
    der Achse höchstens um seine Tiefe, wo eine erklärt ist: Wo auf der Achse
    eine Mitte liegt, ist eine Frage der Messung (Mündung oder Mitte, je nach
    Erzeuger), wie weit daneben eine Bohrung liegt, nicht. Ohne Achse gilt die
    Breite als Abstand. Ein erklärtes Merkmal ohne Größe oder ohne Ort wird
    nicht beschränkt; dort entscheidet die Zuordnung allein.
    """

    def number(key: str) -> float:
        value = declared.params.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return abs(float(value))
        return 0.0

    width = max(number("diameter"), number("length"))
    where = declared.params.get("centre")
    there = found.params.get("centre")
    if not isinstance(where, tuple | list) or not isinstance(there, tuple | list):
        return True
    if width <= EPS_GEOM:
        return True
    try:
        offset = [float(b) - float(a) for a, b in zip(where, there, strict=True)]
        axis = declared.params.get("axis")
        direction = [float(value) for value in axis] if isinstance(axis, tuple | list) else []
    except TypeError, ValueError:
        return True
    length = math.hypot(*direction) if len(direction) == 3 else 0.0
    if length <= EPS_GEOM:
        return math.hypot(*offset) <= width
    unit = [value / length for value in direction]
    along = sum(a * b for a, b in zip(offset, unit, strict=True))
    across = math.hypot(*(value - along * part for value, part in zip(offset, unit, strict=True)))
    depth = number("depth")
    return across <= width and (depth <= EPS_GEOM or abs(along) <= depth)


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
def nested_references(*, strict: bool = False) -> dict[str, Callable[[str], frozenset[str]]]:
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

    Die Verwendungsabfrage fordert ``strict`` an: Ein beschädigter Sammelwert
    bedeutet dort unbekannte Verwendung und darf nicht leer zurückkommen.
    """
    from app.core.geom.pose import pose_parameter_references
    from app.core.organizer.serialize import layout_references

    return {
        "sketch": partial(sketch_parameter_references, strict=strict),
        "armature": partial(pose_parameter_references, strict=strict),
        "organizer": partial(layout_references, strict=strict),
    }


class _WatchedAsk:
    """Reicht eine Rückfrage weiter und merkt sich, dass es eine gab.

    **Wozu:** Der Cache speichert nur, was eine reine Funktion des Dokuments
    ist (§15.1). Hat eine Operation unterwegs gefragt, ist ihr Ergebnis keine —
    die Antwort steht nirgends im Dokument, solange §15.7 nicht umgesetzt ist.
    Auf der Platte würde daraus stillschweigend eine Annahme: Der Nutzer bekommt
    beim zweiten Öffnen kein Fenster mehr, und ob er eines bekommt, hängt daran,
    ob eine Cache-Datei überlebt hat. Regel 21 sagt „nie stillschweigend raten";
    hier rät die Anwendung manchmal und fragt manchmal, und der Unterschied liegt
    im Dateisystem.

    Im Speicher bleibt alles wie vorher — dort lebt das Ergebnis eine Sitzung,
    und innerhalb einer Sitzung wird nicht zweimal gefragt.

    **Diese Klasse verschwindet nicht, wenn §15.7 steht.** Dann hält jede
    fragende Operation ihre Antwort im Stapel fest, ``used`` bleibt überall
    falsch, und der Wächter tut nichts mehr — außer für die nächste Operation,
    die zu fragen anfängt, ohne es aufzuschreiben.
    """

    __slots__ = ("_ask", "used")

    def __init__(self, ask: AskFn) -> None:
        self._ask = ask
        self.used = False

    def __call__(self, question: str, choices: list[str]) -> str:
        self.used = True
        try:
            return self._ask(question, choices)
        except QuestionDeclined:
            # **Ohne Wahl geschlossen heißt: dieser Schritt wartet** — nicht
            # „die Rechnung ist abgebrochen". Jede Frage eines Schritts geht
            # hier durch (Kantenbindung, Operation, Merkmalszuordnung); aus der
            # Absage wird ein Befund am Schritt mit dem Weg zurück, und der
            # Stand davor bleibt zu sehen (RM-024, 23.09.2026).
            raise AmbiguityError(
                QUESTION_LEFT_OPEN, suggestions=(CORRECT_INPUT, SHOW_HISTORY)
            ) from None


#: Der Befund, wenn eine Frage eines Schritts ohne Wahl geschlossen wurde
#: (``QuestionDeclined``). *Eingabe korrigieren* öffnet den Schritt; beim
#: Übernehmen rechnet die Auswertung ihn neu und fragt wieder.
QUESTION_LEFT_OPEN: Final = _(
    "Die Frage wurde ohne Wahl geschlossen. Öffnen Sie den Schritt erneut, dann kommt sie "
    "wieder, oder nehmen Sie ihn mit Strg+Z zurück."
)


def _body_profiles(profile: Profile, inputs: Sequence[SceneObject]) -> dict[str, Profile]:
    """Das Druckprofil jedes Eingangs, der nicht im Projektmaterial gedruckt wird.

    **Für den Schlüssel, weil die Operationen es lesen.** Ein Körper trägt sein
    eigenes Material (*Material wählen*, oder die Spule seines Slots), und wer
    daran eine Länge aus dem Material rechnet — die Lochzugabe beim Bohren, das
    Spiel eines Deckels, die Bohrung eines Bausteins, das Lochfeld —, fragt
    ``profiles.for_object`` statt das Projektprofil. Der Schlüssel kannte davon
    nur die Materialkennung, die im Parameter des früheren Schritts steht,
    nicht die Werte dahinter: Nach dem Kalibrieren des Körpermaterials kam die
    Bohrung mit der alten Zugabe aus dem Cache — gemessen Ø 5,2 statt 5,6 an
    PETG in einem PLA-Projekt, über das Schließen hinaus (Durchsicht 0.5.0,
    22.09.2026).

    Aufgenommen wird je Eingang an seiner Stelle, nicht an seiner Kennung:
    Derselbe Schritt an einem anderen Körper desselben Materials ist derselbe
    Schlüssel. Ein Material, das dieser Rechner nicht kennt, bleibt draußen —
    liest die Operation es, hält sie selbst mit dem Satz dazu an, und liest sie
    es nicht, darf ihr Ergebnis nicht daran scheitern.
    """
    from app.core.knowledge.profiles import for_object

    found: dict[str, Profile] = {}
    for index, entry in enumerate(inputs):
        try:
            own = for_object(profile, entry)
        except AppError:
            continue
        if own is not profile:
            found[f"#input{index}"] = own
    return found


def _key_after_answers(
    operation: Operation,
    spec: Any,
    answered: Mapping[str, Any],
    values: Mapping[ParameterName, float],
    sources: SourceAccess | None,
    objects: Mapping[ObjectId, SceneObject],
    hashes: Mapping[ObjectId, str],
    binding_context: Mapping[str, Any],
    profile: Profile,
    quality: Quality,
    material_profiles: Mapping[str, Profile],
) -> str | None:
    """Der Schlüssel, den dieser Schritt trägt, sobald seine Antworten in den
    Parametern stehen (§15.7) — oder ``None``, wenn er sich nicht bilden lässt.

    Gebaut wie der Schlüssel des nächsten Laufs: aus den zusammengeführten
    Parametern über ``resolve_params``, den Kontext und ``operation_hash``.
    Scheitert die Auflösung — eine Antwort, die kein gültiger Parameterwert
    ist —, gibt es keinen zweiten Schlüssel; der nächste Lauf meldet den
    Fehler dann selbst, und hier rät niemand.
    """
    try:
        resolved = expressions.resolve_params({**operation.params, **answered}, values)
    except AppError:
        return None
    hashed = _with_nested_context(
        spec.params,
        resolved,
        values,
        sources,
        objects,
        hashes,
        reads_other_bodies=spec.reads_other_bodies,
    )
    if binding_context:
        hashed = {**hashed, **binding_context}
    return operation_hash(
        operation,
        hashed,
        [hashes[entry] for entry in operation.inputs],
        profile,
        quality,
        implementation_version=spec.cache_version,
        material_profiles=material_profiles,
    )


def _with_nested_context(
    params_class: type[BaseParams],
    resolved: Mapping[str, Any],
    values: Mapping[ParameterName, float],
    sources: SourceAccess | None = None,
    objects: Mapping[ObjectId, SceneObject] | None = None,
    hashes: Mapping[ObjectId, str] | None = None,
    reads_other_bodies: bool = False,
) -> Mapping[str, Any]:
    """Der Parametersatz für den Cache-Schlüssel, ergänzt um das, was ein
    Parameter von außen liest.

    Maßausdrücke einer gezeichneten Skizze (§30.1) und Gelenkwinkel einer
    Stellung (§13) stehen im JSON-Text der Op und sind für ``resolve_params``
    unsichtbar. Der Schlüssel deckt aber alles, wovon das Ergebnis abhängt
    (§15) — also gehören die Werte der gelesenen Projektparameter hinein,
    sonst überlebt ein Ergebnis die Änderung des Parameters, aus dem es
    gerechnet wurde.

    **Dasselbe gilt für die Quelle, und dort war der Schlüssel blind.** Ein
    Quellparameter trägt einen Bezeichner — ``src_1`` —, und jedes Projekt nennt
    seine erste Quelle so. Zwei völlig verschiedene Dateien hatten damit
    denselben Schlüssel. Gedeckt hat es der Speichercache, der beim Öffnen
    geleert wird und eine Sitzung lang lebt; sichtbar wurde es, als eine Ebene
    dazukam, die länger lebt, und ein Projekt die Geometrie eines anderen
    bekam. Also steht hier die Inhaltsprüfsumme, nicht der Name (§15,
    Leitprinzip 4).

    **Und für jeden benannten Träger.** Drei Lesarten greifen an fremden
    Körpern vorbei an den eigenen Eingängen in die Szene: das Ziel von
    ``align_to_feature`` (``kind="feature"``), die Zielfläche von ``up_to``
    und die ``feature:<id>``-Ebene einer Skizze. Keiner ihrer Hashes stand im
    Schlüssel — Platte um 40 mm verschoben, der ausgerichtete Körper blieb
    mit Cache an der alten Lage; Quader von 10 auf 30 mm, die Extrusion bis
    ``face_top`` blieb bei z = 10. Und der Plattencache lebt länger als die
    Sitzung, der falsche Eintrag überlebte das Schließen. Aufgenommen werden
    die Hashes **aller** Träger des Merkmals: Zwei Körper können denselben
    Merkmalsnamen tragen, und der Schlüssel muss jede Lesart decken.

    **Die vierte Lesart hängt an keinem Parameter.** ``orient_for_print``
    liest die *übrigen* Körper der Szene, um den gedrehten nicht in einen
    nicht gewählten zu legen — es gibt keinen Parameter, der sie benennt, also
    auch keinen Zweig oben, der sie fände. Sie ist am Register deklariert
    (``reads_other_bodies``), und der Schlüssel bekommt die Hashes **aller**
    Objekte: Die Eingänge stehen ohnehin darin, doppelt schadet nicht, und
    „alle außer den Eingängen" wüsste hier niemand — die Eingangsliste steht
    an der Operation, nicht am Parametersatz."""
    context: dict[str, Any] = {}
    if reads_other_bodies and hashes is not None:
        # Sortiert, weil ein Schlüssel aus einer Wörterbuchreihenfolge kein
        # Schlüssel ist: Zwei gleiche Szenen müssen denselben ergeben.
        context["#scene"] = tuple(sorted(hashes.items()))
    for spec in params_class.spec():
        if spec.kind in SOURCE_KINDS and sources is not None:
            source_id = resolved.get(spec.name)
            if isinstance(source_id, str) and source_id:
                context[f"#{spec.name}"] = sources.identity(source_id)
            continue
        if spec.kind == "features":
            named_features = resolved.get(spec.name)
            if (
                isinstance(named_features, list | tuple)
                and objects is not None
                and hashes is not None
            ):
                for named_feature in named_features:
                    if isinstance(named_feature, str) and named_feature:
                        carriers = _carrier_hashes(named_feature, objects, hashes)
                        if carriers:
                            context[f"#{spec.name}:{named_feature}"] = carriers
            continue
        if spec.kind == "feature" or spec.targets_feature:
            named = resolved.get(spec.name)
            if isinstance(named, str) and named and objects is not None and hashes is not None:
                # Ein Ziel darf qualifiziert sein — ``obj_2:hole_1`` bei
                # ``align_to_feature``. Dann zählt genau dieser Träger; ein
                # nackter Merkmalsname deckt weiter jeden, der ihn trägt.
                carrier_id: ObjectId | None = None
                feature_id = named
                if ":" in named:
                    try:
                        reference = FeatureRef.parse(named)
                    except ValueError:
                        reference = None
                    if reference is not None:
                        carrier_id, feature_id = reference.object_id, reference.feature_id
                carriers = _carrier_hashes(feature_id, objects, hashes, object_id=carrier_id)
                if carriers:
                    context[f"#{spec.name}"] = carriers
            continue
        if spec.kind == "sketch" and objects is not None and hashes is not None:
            drawn = resolved.get(spec.name)
            if isinstance(drawn, str) and drawn:
                plane_reference = feature_ref_of_sketch(drawn)
                if plane_reference is not None:
                    carriers = _carrier_hashes(
                        plane_reference.feature_id,
                        objects,
                        hashes,
                        object_id=plane_reference.object_id or None,
                    )
                    if carriers:
                        context[f"#{spec.name}.plane"] = carriers
            # Kein ``continue``: Der Skizzentext trägt daneben @-Parameter,
            # und die sammelt der Zweig darunter wie bisher.
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


def _carrier_hashes(
    feature_id: str,
    objects: Mapping[ObjectId, SceneObject],
    hashes: Mapping[ObjectId, str],
    *,
    object_id: ObjectId | None = None,
) -> tuple[str, ...]:
    """Die Hashes aller Körper, die dieses Merkmal tragen — sortiert nach
    Objektkennung, damit der Schlüssel stabil bleibt. Leer, wenn keiner es
    trägt: Dann hält die Operation selbst an, und ein leerer Eintrag würde
    nur jeden bestehenden Schlüssel kippen. Bei einer eindeutigen
    Skizzenebene zählt ausschließlich der ausdrücklich benannte Körper."""
    return tuple(
        hashes[carrier_id]
        for carrier_id in sorted(objects)
        if carrier_id in hashes
        and feature_id in objects[carrier_id].features
        and (carrier_id == object_id if object_id is not None else True)
    )


def _unresolved_parameters(
    document: Document,
    profile: Profile,
    error: AppError,
    operations: Sequence[Operation],
) -> EvaluationResult:
    """Die Auswertung, die gar nicht anfangen konnte (§15.3).

    ``expressions.resolve`` stand als einzige Zeile von :func:`evaluate`
    außerhalb jedes ``try``. Eine Division durch null, ein Kreis oder ein
    Verweis auf einen Parameter, den es nicht gibt, kam damit als **Ausnahme**
    aus der Auswertung heraus — während jeder andere Fehler eine Zeile im
    Prüfbericht ist. Der Kunde verlor dabei mehr als die Meldung: §15.3 sagt
    zu, dass der letzte vollständig gerechnete Zustand stehen bleibt, und ein
    Aufrufer, der eine Ausnahme fängt, hat kein Ergebnis, aus dem er ihn nimmt.

    Angehalten wird am **ersten** Schritt: Ohne aufgelöste Parameter ist keiner
    von ihnen zu rechnen, und ``stopped_at`` ist die Zahl, an der die
    Oberfläche den Verlauf markiert. Ein Dokument ohne Stapel hat keinen —
    dort steht der Befund allein, denn die Parameterleiste zeigt den Zustand
    an, und ein leerer Bericht hieße „alles in Ordnung".
    """
    stopped_at = operations[0].id if operations else None
    detail = error.detail if error.detail is not None else error.title
    finding = Finding(
        code="parameter.unresolvable",
        severity="error",
        message=_(
            "Ein Parameterausdruck lässt sich nicht auflösen — bis er stimmt, "
            "rechnet Solidon die Szene nicht."
        ),
        op_id=stopped_at,
        values={
            **{key: str(value) for key, value in error.values.items()},
            "reason": str(detail),
        },
        suggestions=tuple(error.suggestions),
    )
    _log.warning("evaluation could not resolve the parameters: %s", detail)
    return EvaluationResult(
        scene=Scene(
            parameters=dict(document.parameters),
            fits=list(document.fits),
            profile=profile,
            report=Report((finding,)),
        ),
        stopped_at=stopped_at,
    )


def _evaluated_parameters(
    declared: Mapping[ParameterName, Parameter], values: Mapping[ParameterName, float]
) -> dict[ParameterName, Parameter]:
    """Parameter, wie die Szene sie sieht: Ausdrücke ersetzt durch ihr Ergebnis."""
    return {
        name: dataclasses.replace(parameter, value=values[name])
        for name, parameter in declared.items()
    }


def _without_stray_inputs(
    operation: Operation, spec: OperationSpec
) -> tuple[Operation, Finding | None]:
    """Ein Erzeuger mit Eingängen verliert sie, statt die Kette anzuhalten.

    **Der Fall ist eine Datei und keine Geste.** ``inputs_for`` gibt einem
    Erzeuger nie ein Objekt, und ``History.apply`` weist es seit dem
    07.09.2026 ab. Bestehende Projektdateien tragen es trotzdem: Vorher nahm
    ``apply`` es an, und die Auswertung prüfte den Fall gar nicht — sie las
    ``consumes > 0`` und ging an einem Erzeuger vorbei. Gerechnet wurde
    weiter, und das genannte Objekt verschwand dabei stillschweigend aus der
    Szene: Jeder Eingang, der nicht auch Ausgang ist, gilt als verbraucht.

    Beides war falsch, und die Verschärfung hat nur die Richtung getauscht:
    Seitdem hält so eine Datei mit ``evaluate.too_many_inputs`` an, und ihr
    einziger Vorschlag — *Andere Objekte wählen* — führt über
    ``History.change_inputs`` auf dieselbe Absage zurück. Eine Sackgasse ohne
    Migration.

    **Verworfen und nicht geraten** (Regel 21): Bei einem Erzeuger ist die
    erwartete Zahl null, es gibt also keine Wahl zwischen mehreren Eingängen,
    sondern nur eine Menge, die keine Bedeutung hat. Bei fester Stelligkeit
    über null bleibt es beim Anhalten — dort wäre „welcher darf bleiben" eine
    Entscheidung, die der Kern nicht trifft.

    Gemeldet wird es trotzdem: Der Schritt in der Datei bleibt, wie er ist,
    und beim nächsten Öffnen steht der Befund wieder da. Wer ihn loswerden
    will, leert die Eingänge des Schritts — das nimmt ``change_inputs`` an.

    **Derselbe Satz wie beim Anhalten, ein anderer Rang.** Es ist dieselbe
    Aussage über dieselbe Datei; verschieden ist nur, ob der Kern daraus eine
    Entscheidung ableiten muss. Der Rang trägt den Unterschied — ``warning``
    statt ``error`` —, und ``values`` nennt die übergangenen Kennungen.
    ``suggestions`` bleibt leer: *Andere Objekte wählen* ist hier genau die
    Sackgasse, aus der dieser Befund herausführt, und ein Erzeuger hat für den
    Nutzer nichts zu wählen.
    """
    if spec.consumes != 0 or spec.takes_whole_scene or not operation.inputs:
        return operation, None
    return dataclasses.replace(operation, inputs=()), Finding(
        code="evaluate.creator_inputs_dropped",
        severity="warning",
        # **Ein eigener Satz und nicht der geliehene von ``too_many_inputs``.**
        # „Die Operation erwartet eine andere Anzahl an Objekten" beschreibt
        # eine Absage; hier ist nichts abgesagt, sondern etwas übergangen und
        # die Kette läuft weiter. Ein Befund, der das Falsche sagt, ist
        # schlechter als einer mit dürftigem Satz.
        message=_(
            "Diese Operation erzeugt und nimmt keine Objekte. "
            "Die eingetragenen wurden übergangen; sie bleiben erhalten."
        ),
        op_id=operation.id,
        values={
            "op": operation.op,
            "expected": 0,
            "given": len(operation.inputs),
            "ignored": ", ".join(operation.inputs),
        },
    )


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

    # Variable Eingänge behalten die im Register festgelegte Untergrenze.
    expected = needed_inputs(spec)
    if spec.consumes >= 0 and not spec.takes_whole_scene and len(operation.inputs) > expected:
        return Finding(
            code="evaluate.too_many_inputs",
            severity="error",
            message=_("Die Operation erwartet eine andere Anzahl an Objekten."),
            op_id=operation.id,
            values={"op": operation.op, "expected": expected, "given": len(operation.inputs)},
            suggestions=(CHANGE_SELECTION, CANCEL),
        )
    if len(operation.inputs) < expected:
        return Finding(
            code="evaluate.too_few_inputs",
            severity="error",
            message=_("Dieser Operation fehlt das Objekt, auf dem sie arbeiten soll."),
            op_id=operation.id,
            values={
                "op": operation.op,
                # Englisch, wie jeder Schlüssel — hier standen zwei deutsche.
                "expected": expected,
                "given": len(operation.inputs),
            },
        )
    return None


MESSAGE_BODY_SPLIT: Final = _(
    "Der Körper zerfällt nach diesem Schritt in lose Teile. Strg+Z nimmt ihn zurück."
)


def _split_findings(
    before: SceneObject | None, after: SceneObject, operation: Operation
) -> list[Finding]:
    """Ein Körper, der nach einer Merkmalsänderung in Teile zerfällt, sagt es.

    **Gemessen an 34 Modellen aus dem Netz (15.09.2026):** *Merkmal entfernen*
    an einem Zapfen Ø 11,3 — dem ganzen unteren Teil eines Uhrenrads — ließ
    50 Komponenten zurück, *Merkmal versetzen* an einer Bohrung nahe der Wand
    zwei, und beide Läufe endeten „vollständig", mit dichtem Netz und ohne
    einen Satz im Prüfbericht. Ein Körper, der auseinanderfällt, ist kein
    Fehler der Operation, aber selten das, was jemand wollte: Beim Drucken
    liegen die Teile lose auf dem Bett. Deshalb steht es als Warnung dort, wo
    der Kunde hinsieht — und der Weg zurück gleich dabei.

    Gezählt werden die zusammenhängenden Teile vor und nach dem Schritt; ein
    Körper, der schon vorher aus mehreren bestand, meldet erst, wenn es mehr
    werden. Die exakten Körper kennen die Zahl nicht — dort bleibt es still.
    """
    if before is None:
        return []
    were = getattr(before.mesh, "component_count", None)
    are = getattr(after.mesh, "component_count", None)
    if not isinstance(were, int) or not isinstance(are, int) or are <= were:
        return []
    return [
        Finding(
            code="feature.body_split",
            severity="warning",
            message=MESSAGE_BODY_SPLIT,
            object_id=after.id,
            op_id=operation.id,
            values={"before": were, "after": are, "op": operation.op},
            source="internal",
        )
    ]


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
    die Reihenfolge seiner Liste — hier gibt es die Kennungen, also gehen sie
    mit; ein Bericht, der „ein Objekt" sagt, hilft bei zwanzig nicht.
    """
    from app.core.geom.prepare import check_build_volume

    profile = scene.profile
    if profile is None or not scene.objects:
        return []
    entries = list(scene.objects.values())
    # Die Kennungen direkt statt ``named_for`` hinterher: So trägt der Befund
    # dieselbe Gestalt wie der der Exportprüfung — gleiche Werte, gleiche
    # Kennung —, und der Bericht erkennt beide als denselben Sachverhalt,
    # statt ihn zweimal zu zeigen (Roberts Foto, 30.08.2026).
    return check_build_volume(
        [entry.mesh for entry in entries],
        profile,
        [entry.plate for entry in entries],
        [entry.id for entry in entries],
    )


def check_bodies_in_one_place(scene: Scene) -> list[Finding]:
    """Liegen Körper genau übereinander, so dass man sie für einen hält?

    **Der Fall, der es aufgedeckt hat, ist der häufigste überhaupt:** Wer
    zweimal *Quader anlegen* wählt, bekommt zwei Quader an derselben Stelle
    und sieht einen. Dasselbe beim Duplizieren — die Stückzahl gehört in den
    Stapel, das Verteilen ans Anordnen (§25), und dazwischen liegt ein
    Zustand, in dem das Bild weniger zeigt, als die Szene enthält. Gemeldet
    wurde es als „das Objekt ist nicht zweimal da".

    **Gefragt wird über Hüllquader und Volumen, nicht über den Objekt-Hash** —
    und der erste Anlauf nahm den Hash, weil eine Messung ihn zu empfehlen
    schien: Zwei angelegte Quader trugen denselben. Sie trugen ihn aber, weil
    sie aus derselben Operation mit denselben Werten stammen; der Hash
    beschreibt die **Herkunft** und nicht die Gestalt. Original und Kopie
    haben deshalb verschiedene Hashes, obwohl sie Punkt auf Punkt liegen — und
    genau der Fall, um den es geht, wäre durchgerutscht. Die Gegenprobe hatte
    denselben Fehler: Ein verschobener Körper bekam einen anderen Hash, weil
    eine Operation dazukam, nicht weil er woanders lag.

    Der Hüllquader allein wäre zu grob (eine Kugel und ein Würfel derselben
    Größe teilen sich einen), das Volumen allein auch (zwei gleich große
    Körper an verschiedenen Orten). Zusammen sind sie scharf genug für einen
    Hinweis und kosten nichts: Beide Zahlen liegen an jedem Körper bereit,
    gleich ob Netz oder exakter Kern.

    **Die Platte gehört in den Schlüssel**, sonst schlägt die Prüfung
    ausgerechnet nach dem Anordnen an: Jede Druckplatte hat ihren eigenen
    Nullpunkt, und ``arrange_bed`` setzt Platte 2 bewusst an dieselbe Stelle
    wie Platte 1, weil beide einzeln gedruckt werden. Zwei Kopien auf zwei
    Platten liegen im Modell aufeinander und sind trotzdem richtig verteilt.
    """
    if len(scene.objects) < 2:
        return []
    groups: dict[tuple[Any, ...], list[ObjectId]] = {}
    for object_id, entry in scene.objects.items():
        mesh = entry.mesh
        bounds = getattr(mesh, "bounds", None)
        volume = getattr(mesh, "volume", None)
        if bounds is None or volume is None:
            # Ein Körper, der seine Maße nicht nennt, wird nicht geraten.
            continue
        # Gerundet statt verglichen: Fließkomma nie mit ``==`` (Regel 6). Ein
        # Tausendstel Millimeter ist feiner als jede Düse und gröber als das
        # Rauschen einer Transformation.
        groups.setdefault(
            (
                entry.plate,
                tuple(round(float(value), 3) for value in bounds.minimum),
                tuple(round(float(value), 3) for value in bounds.maximum),
                round(float(volume), 3),
            ),
            [],
        ).append(object_id)
    findings: list[Finding] = []
    for key, members in groups.items():
        plate = int(key[0])
        if len(members) < 2:
            continue
        names = [str(scene.objects[entry].name) for entry in members]
        findings.append(
            Finding(
                code="arrange.bodies_in_one_place",
                severity="info",
                message=_("Mehrere Körper liegen genau übereinander."),
                object_id=members[0],
                values={
                    "count": len(members),
                    "objects": ", ".join(names),
                    "plate": plate + 1,
                },
            )
        )
    return findings


def check_form_deviation(scene: Scene) -> list[Finding]:
    """Je Körper das Merkmal, dessen belegte Punkte am weitesten neben der Form liegen.

    ``fit_error`` ist der größte geometrische Abstand der Stützpunkte, die
    eine Rundform tragen, in Millimetern — kein Facettenband, denn die Ecken
    eines sauber facettierten Zylinders liegen **auf** dem Zylinder. Wo er
    über der Sehnengrenze der Tessellierung (:data:`units.MAX_FACET_SAG`) liegt,
    ist die Haut verformt oder verrauscht: ein gescannter Zapfen, ein
    gedruckter und wieder eingelesener Sitz. Der Befund nennt Merkmal und
    Maß; der Klick darauf schaltet die Karte „Formabweichung" ein, die zeigt,
    wo (§18.4). Ein Körper ohne solchen Punkt bekommt keinen Satz — auch
    keinen, der nur sagt, dass es die Karte gibt.
    """
    findings: list[Finding] = []
    for object_id, entry in scene.objects.items():
        worst: tuple[float, FeatureId] | None = None
        for feature_id, feature in entry.features.items():
            error = feature.params.get("fit_error")
            if not feature.surface_patches or isinstance(error, bool):
                continue
            if not isinstance(error, int | float) or not math.isfinite(error):
                continue
            if worst is None or float(error) > worst[0]:
                worst = (float(error), feature_id)
        if worst is None or worst[0] <= MAX_FACET_SAG:
            continue
        findings.append(
            Finding(
                code="perceive.deviation",
                severity="info",
                message=_(
                    "Belegte Punkte liegen neben der eingepassten Form. "
                    "Prüfen Sie die Abweichung in der Analysekarte."
                ),
                object_id=object_id,
                feature_ids=(worst[1],),
                values={"deviation_mm": round(worst[0], 2)},
            )
        )
    return findings


def check_thin_walls(scene: Scene) -> list[Finding]:
    """Wände, die der Drucker nicht mehr legen kann — am **Endzustand** (RM-127).

    **Die Wand steht in keinem Merkmal**, sie entsteht aus dem Verhältnis
    zweier: Eine Bohrung nennt ihren Durchmesser, der Mantel den seinen, und
    was dazwischen bleibt, rechnet `relations.sleeve_at`. Und sie entsteht aus
    dem **letzten** Verhältnis: Wer die Bohrung aufbohrt und danach das
    Außenmaß vergrößert, hat am Ende eine gute Wand — eine Warnung aus dem
    ersten Schritt stünde dort als überholter Satz, und beide Reihenfolgen
    derselben zwei Änderungen müssten denselben Bericht ergeben.

    Deshalb hier und nicht in den Operationen, dieselbe Bauart und derselbe
    Grund wie bei :func:`check_placement` und
    :func:`check_bodies_in_one_place`: Erst der Endstand beantwortet die Frage.
    Die Warnungen *in* den Operationen bleiben, wo sie stehen — `hollow`
    spricht über den Wert, den jemand eingetragen hat, und der bleibt wahr,
    gleich was danach kommt.

    **Die Grenze gilt den verwendeten Materialien** (Regel 7):
    `analysis_limits` berücksichtigt Körpermaterial und benutzte Spulen samt
    ihrer Kalibrierung. Eine unbekannte Materialart übernimmt keine fremde
    Messung. Ohne Profil gibt es keine Aussage — ein Aufrufer, der keinen
    Drucker kennt, soll keinen erfinden.

    **Gemeldet wird je Körper einmal**, und zwar die dünnste Stelle. Ein Rohr
    in einem Rohr hat mehrere Wände; drei Zeilen über dasselbe Teil sind zwei
    zu viel, und die innerste ist ohnehin die, die als Erste reißt.
    """
    profile = scene.profile
    if profile is None:
        return []
    findings: list[Finding] = []
    for object_id, entry in scene.objects.items():
        thinnest = thinnest_sleeve(entry.features)
        if thinnest is None:
            continue
        least, _overhang = analysis_limits(profile, entry)
        if thinnest.thickness >= least - EPS_GEOM:
            continue
        bore = entry.features.get(thinnest.bore)
        centre = centre_of(bore) if bore is not None else None
        findings.append(
            Finding(
                code="perceive.thin_wall",
                severity="warning",
                message=_(
                    "Zwischen einer Bohrung und dem Material um sie herum bleibt weniger "
                    "Wand stehen, als der Drucker legen kann. Vergrößern Sie das Außenmaß "
                    "oder verkleinern Sie die Bohrung."
                ),
                object_id=object_id,
                feature_ids=(thinnest.bore, thinnest.wall),
                values={"wall_mm": round(thinnest.thickness, 2), "least_mm": round(least, 2)},
                suggestions=(SHOW_HISTORY, SHOW_DETAILS),
                location=None
                if centre is None
                else (float(centre[0]), float(centre[1]), float(centre[2])),
            )
        )
    return findings


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
    Objekts benennen", und beim Aufruf eines fremden Programms eine halbe
    Seite roher Ausgabe — während der lesbare Satz beide Male in ``values``
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
        suggestions=tuple(error.suggestions),
    )
