"""Den Verlauf umbauen, ohne einen Bezug still umzubiegen (RM-188 P7.1 bis P7.3).

Einfügen, Umsortieren, Aus- und Einschalten planen einen neuen Stapel
(:class:`~app.core.scene.history.RevisionPlan`). Bevor er zählt, wird er
**isoliert** ausgewertet, und erst ein gültiges Ergebnis ersetzt die Folge —
ein ungültiger Vorschlag verändert nichts (Konzept vollwertiges CAD §13.9).

**Gültig heißt mehr als „hält nicht an".** Merkmalsnamen hängen an der
Reihenfolge ihrer Erkennung: Ein neues Merkmal bekommt seinen Erkennungsnamen,
wenn er frei ist (``perceive.matching.apply_mapping``). Wer die erste von zwei
Bohrungen ausschaltet, gibt ihren Namen für die zweite frei; wer eine Bohrung
vor eine andere setzt, tauscht ihre Namen. Ein späteres *Bohrung vergrößern*
auf ``hole_1`` hielte danach nicht an — es vergrößerte still die andere. Das
ist genau das „still umbiegen", das §21.3 verbietet.

Deshalb vergleicht dieses Modul je Verweis, was er im Grundstand traf
(``EvaluationResult.sights``) und was er im Vorschlag trifft:

* **gleiche Herkunft** — dasselbe erzeugende Schritt (``Feature.created_by``,
  über die neue Kennung nach dem Neuplanen) — oder, wo keine Herkunft
  bekannt ist, **derselbe geometrische Abdruck** (``matching.resolve``, dieselbe
  Rivalenregel wie bei gespeicherten Antworten, §15.7);
* trägt dasselbe Merkmal nur einen anderen Namen, **folgt der Verweis** — der
  Schritt wird mit dem neuen Namen gefasst, und ein Befund sagt es;
* ist es verloren oder nicht eindeutig, **wird gefragt** (dieselbe Frage wie im
  Verweisfilter, mit den Kandidaten am Vorschlag) — ohne jemanden zum Fragen
  ist der Vorschlag ungültig. Beim Ausschalten ruht ein solcher Schritt
  stattdessen mit: Sein Merkmal entsteht in einem ausgeschalteten Schritt.

Kein Qt, kein Dialog (Regel 1): Die Frage geht über ``ask``, die Kandidaten
über ``announce``, gerechnet wird über den Aufrufer (``evaluate``) — Fenster,
Kommandozeile und Agent benutzen denselben Weg.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Final, Literal

from app.core.errors import CANCEL, SUPPRESS_ALONG, AmbiguityError, UserError
from app.core.log import get_logger
from app.core.perceive.matching import (
    AXIS_TOLERANCE,
    MATCH_THRESHOLD,
    POSITION_TOLERANCE,
    feature_vector,
    fingerprint,
    resolve,
)
from app.core.registry import REGISTRY, Registry
from app.core.registry.params import reads_scene
from app.core.scene.evaluate import EvaluationResult, sight_of
from app.core.scene.fits import active_fits
from app.core.scene.history import (
    Dependencies,
    History,
    OperationDraft,
    RevisionPlan,
    StepNeed,
)
from app.core.scene.orphans import Reference, references, with_reference
from app.core.types import (
    Document,
    Feature,
    FeatureId,
    FeatureRef,
    Finding,
    Fit,
    ObjectId,
    Operation,
    OpId,
    ReferenceExpectation,
    ReferenceSight,
    Transaction,
)
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Wie oft ein Vorschlag nach einem gefolgten Verweis neu gerechnet wird.
#:
#: Jede Runde fasst mindestens einen Verweis neu oder nimmt einen Schritt mit;
#: danach rechnet der Cache alles davor. Mehr Runden als Verweise kann es nicht
#: geben, die Grenze fängt nur einen Programmfehler, der im Kreis liefe.
MAX_ROUNDS: Final = 64


# --- Abhängigkeiten ---------------------------------------------------------------


def expectation_of(sight: ReferenceSight) -> ReferenceExpectation | None:
    """Der Vermerk zu einer Sichtung — was ein ruhender Schritt beim Einschalten treffen muss."""
    if sight.feature is None:
        return None
    return ReferenceExpectation(
        key=sight.key,
        feature=sight.ref.feature_id,
        kind=sight.feature.kind,
        creator=sight.feature.created_by,
        fingerprint=fingerprint(sight.feature, sight.centre, sight.diagonal),
    )


def body_creators(document: Document) -> dict[ObjectId, OpId]:
    """Welcher Schritt welchen Körper frisch anlegt — die Kennung ist nach §15.4 einmalig."""
    creators: dict[ObjectId, OpId] = {}
    for entry in sorted(document.ops, key=lambda operation: operation.id):
        for output in entry.outputs:
            if output not in entry.inputs:
                creators.setdefault(output, entry.id)
    return creators


def dependencies(document: Document, result: EvaluationResult | None) -> Dependencies:
    """Was ein Umbau über die Folge wissen muss, aus einem gerechneten Stand (P7).

    Die Merkmalskante — Schritt X braucht ein Merkmal, das Schritt Y anlegt —
    kennt nur eine Auswertung (``Feature.created_by`` an der Sichtung). Ein
    ausgeschalteter Schritt rechnet nicht; für ihn gilt sein eigener Vermerk
    (``Suppression.expects``). Die Körperkette steht im Stapel und wird beim
    Umbau selbst geprüft; sie steht deshalb nicht hier.
    """
    known = {entry.id for entry in document.ops}
    needs: list[StepNeed] = []
    expectations: dict[OpId, tuple[ReferenceExpectation, ...]] = {}
    for entry in document.ops:
        if entry.suppressed is not None:
            for stored in entry.suppressed.expects:
                if stored.key.startswith("fit:") or stored.creator is None:
                    continue
                if stored.creator in known and stored.creator != entry.id:
                    needs.append(StepNeed(entry.id, stored.creator, "", stored.feature))
            continue
        seen = result.sights.get(entry.id, ()) if result is not None else ()
        noted = tuple(found for sight in seen if (found := expectation_of(sight)) is not None)
        if noted:
            expectations[entry.id] = noted
        for sight in seen:
            creator = sight.feature.created_by if sight.feature is not None else None
            if creator is not None and creator != entry.id and creator in known:
                needs.append(StepNeed(entry.id, creator, sight.ref.object_id, sight.ref.feature_id))
    creators = body_creators(document)
    fit_needs: dict[str, set[OpId]] = {}
    fit_expectations: dict[str, list[ReferenceExpectation]] = {}
    for sight in result.fit_sights if result is not None else ():
        name = sight.key.split(":")[1]
        wanted = fit_needs.setdefault(name, set())
        if sight.ref.object_id in creators:
            wanted.add(creators[sight.ref.object_id])
        maker = sight.feature.created_by if sight.feature is not None else None
        if maker is not None and maker in known:
            wanted.add(maker)
        noted_fit = expectation_of(sight)
        if noted_fit is not None:
            fit_expectations.setdefault(name, []).append(noted_fit)
    return Dependencies(
        needs=tuple(needs),
        expectations=expectations,
        fit_needs={name: frozenset(wanted) for name, wanted in fit_needs.items()},
        fit_expectations={name: tuple(entries) for name, entries in fit_expectations.items()},
    )


def step_needs(document: Document, context: Dependencies) -> tuple[StepNeed, ...]:
    """Alle Kanten der Folge zum Zeigen: Körperkette **und** Merkmale (P7.2).

    „Abhängige Folge kenntlich machen": Der Verlauf nennt je Schritt, was er
    braucht und wer ihn braucht. Die Körperkante zählt nur, wo ein Schritt
    einen Körper nimmt, den ein früherer **frisch** anlegt — wer nur dieselbe
    Kennung fortführt (Bohrung, dann Fase an ``obj_1``), hängt nicht an ihm.
    """
    creators = body_creators(document)
    found: list[StepNeed] = []
    for entry in sorted(document.ops, key=lambda operation: operation.id):
        for name in entry.inputs:
            creator = creators.get(name)
            if creator is not None and creator < entry.id:
                found.append(StepNeed(entry.id, creator, name))
    found.extend(context.needs)
    unique = dict.fromkeys(found)
    return tuple(sorted(unique, key=lambda need: (need.step, need.on)))


# --- Derselbe Bezug? ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Verdict:
    """Was aus einem Verweis im Vorschlag wird."""

    state: Literal["kept", "renamed", "lost"]
    name: FeatureId | None = None
    """Der neue Name desselben Merkmals (``renamed``)."""
    candidates: tuple[FeatureId, ...] = ()
    """Merkmale derselben Art zur Wahl (``lost``)."""


def _same_place(saved: Mapping[str, Any], feature: Feature, centre: Any, diagonal: float) -> bool:
    """Liegt ``feature`` noch dort, wo der Abdruck es sah — Lage und Achse, ohne Maß?

    Der Rückfall, wenn ``resolve`` keinen Kandidaten mit Abstand findet: Eine
    Bohrung, die nur weiter wurde, ist dieselbe Bohrung (``DIAMETER_TOLERANCE``
    ist eng); eine an anderer Stelle ist es nicht. In Python-Zahlen gerechnet,
    ohne BLAS (kern.md, RM-187).
    """
    try:
        vector = [float(value) for value in feature_vector(feature, centre, diagonal)]
        relative = [float(value) for value in saved.get("relative", ())]
        axis = [float(value) for value in saved.get("axis", ())]
    except TypeError, ValueError:
        return False
    if len(relative) != 3 or len(axis) != 3 or not all(map(math.isfinite, vector)):
        return False
    shift = math.sqrt(sum((vector[i] - relative[i]) * (vector[i] - relative[i]) for i in range(3)))
    turn = math.sqrt(sum((vector[3 + i] - axis[i]) * (vector[3 + i] - axis[i]) for i in range(3)))
    if not saved.get("directional", False):
        back = math.sqrt(
            sum((vector[3 + i] + axis[i]) * (vector[3 + i] + axis[i]) for i in range(3))
        )
        turn = min(turn, back)
    return shift / POSITION_TOLERANCE + turn / AXIS_TOLERANCE <= MATCH_THRESHOLD


def verdict(
    expected: ReferenceExpectation,
    found: ReferenceSight | None,
    renumbered: Mapping[OpId, OpId],
) -> Verdict:
    """Trifft der Verweis im Vorschlag **dasselbe** Merkmal wie im Grundstand?

    Zuerst die Herkunft: ein Merkmal derselben Art, das derselbe Schritt
    anlegte (unter seiner neuen Kennung). Wo sie fehlt oder mehrere passen,
    der Abdruck mit Rivalenregel (``matching.resolve``). Findet sich nichts
    mit Abstand, bleibt der alte Name nur, wenn er noch an derselben Stelle
    steht und nicht erkennbar einem anderen Schritt gehört. Alles andere ist
    verloren — geraten wird nicht (Regel 21).
    """
    if found is None or (found.feature is None and not found.candidates):
        return Verdict("lost")
    same_kind = {
        name: feature for name, feature in found.candidates.items() if feature.kind == expected.kind
    }
    creator = renumbered.get(expected.creator, expected.creator) if expected.creator else None
    target: FeatureId | None = None
    if creator is not None:
        by_creator = tuple(
            name for name, feature in same_kind.items() if feature.created_by == creator
        )
        if len(by_creator) == 1:
            target = by_creator[0]
        elif by_creator:
            target = resolve(
                expected.fingerprint, by_creator, same_kind, found.centre, found.diagonal
            ) or (expected.feature if expected.feature in by_creator else None)
    if target is None and expected.fingerprint:
        target = resolve(
            expected.fingerprint, tuple(sorted(same_kind)), same_kind, found.centre, found.diagonal
        )
        if target is not None and creator is not None:
            owner = same_kind[target].created_by
            if owner is not None and owner != creator:
                # Derselbe Ort, ein anderer Erzeuger: ein fremdes Merkmal, das
                # zufällig dort sitzt, wo das gemeinte saß.
                target = None
    # Verglichen wird mit dem Namen, den der Schritt **jetzt** nennt: Nach einem
    # gefolgten Verweis steht dort schon der neue, und dann ist nichts mehr zu tun.
    current = found.ref.feature_id
    if target is None:
        named = same_kind.get(current)
        if (
            named is not None
            and (creator is None or named.created_by in (None, creator))
            and (
                not expected.fingerprint
                or _same_place(expected.fingerprint, named, found.centre, found.diagonal)
            )
        ):
            target = current
    if target is None:
        return Verdict("lost", candidates=tuple(sorted(same_kind)))
    if target == current:
        return Verdict("kept")
    return Verdict("renamed", name=target)


# --- Vergleich Grundstand ↔ Vorschlag ----------------------------------------------


@dataclass(frozen=True, slots=True)
class Drift:
    """Ein Verweis, der im Vorschlag nicht mehr unter seinem Namen dasselbe trifft."""

    key: str
    feature: FeatureId
    object_id: ObjectId
    verdict: Verdict
    step: OpId | None = None
    """Die Kennung des Schritts **im Vorschlag** — ``None`` bei einer Passung."""
    fit: str | None = None
    sight: ReferenceSight | None = None
    """Die Sichtung im Vorschlag, an der das Urteil fiel — für die Antwort des Kunden."""


def _chosen(drift: Drift, name: FeatureId) -> ReferenceExpectation | None:
    """Die Wahl des Kunden als neuer Vermerk: dieses Merkmal ist gemeint, ab jetzt (§21.3)."""
    sight = drift.sight
    if sight is None:
        return None
    feature = sight.candidates.get(name)
    if feature is None:
        return None
    return ReferenceExpectation(
        key=drift.key,
        feature=name,
        kind=feature.kind,
        creator=feature.created_by,
        fingerprint=fingerprint(feature, sight.centre, sight.diagonal),
    )


def _proposal_sights(result: EvaluationResult) -> dict[tuple[OpId | None, str], ReferenceSight]:
    found: dict[tuple[OpId | None, str], ReferenceSight] = {}
    for op_id, seen in result.sights.items():
        for sight in seen:
            found[(op_id, sight.key)] = sight
    for sight in result.fit_sights:
        found[(None, sight.key)] = sight
    return found


def drifts(
    document: Document,
    plan: RevisionPlan,
    baseline: EvaluationResult | None,
    proposal: EvaluationResult,
    chosen: Mapping[tuple[OpId | None, str], ReferenceExpectation] | None = None,
) -> list[Drift]:
    """Jeder Verweis, der im Vorschlag nicht mehr unter seinem Namen dasselbe trifft.

    Verglichen wird, was beide Seiten gerechnet haben: ein Schritt, der im
    Grundstand lief und im Vorschlag läuft, gegen seine Sichtung von vorhin;
    ein Schritt, der wieder angeht, gegen seinen eigenen Vermerk
    (``Suppression.expects``); eine Passung am Endstand genauso. Ein Schritt,
    der nirgends lief, hat keinen Grundstand — ihn prüft die Auswertung wie
    jeden anderen.
    """
    now = _proposal_sights(proposal)
    found: list[Drift] = []
    before = {entry.id: entry for entry in document.ops}

    def check(noted: ReferenceExpectation, step: OpId | None, fit: str | None) -> None:
        sight = now.get((step, noted.key))
        if sight is None:
            return
        # Was der Kunde für diesen Umbau gewählt hat, gilt statt des Grundstands.
        expected = (chosen or {}).get((step, noted.key), noted)
        ruling = verdict(expected, sight, plan.renumbered)
        if ruling.state != "kept":
            found.append(
                Drift(
                    key=expected.key,
                    feature=expected.feature,
                    object_id=sight.ref.object_id,
                    verdict=ruling,
                    step=step,
                    fit=fit,
                    sight=sight,
                )
            )

    for op_id, entry in before.items():
        new_id = plan.new_id(op_id)
        if new_id not in proposal.sights:
            continue
        if entry.suppressed is not None:
            for stored in entry.suppressed.expects:
                if not stored.key.startswith("fit:"):
                    check(stored, new_id, None)
            continue
        for sight in baseline.sights.get(op_id, ()) if baseline is not None else ():
            noted = expectation_of(sight)
            if noted is not None:
                check(noted, new_id, None)
    if proposal.complete:
        seen: set[str] = set()
        for sight in baseline.fit_sights if baseline is not None else ():
            noted = expectation_of(sight)
            if noted is not None:
                seen.add(noted.key)
                check(noted, None, noted.key.split(":")[1])
        for entry in before.values():
            if entry.suppressed is None:
                continue
            for expected in entry.suppressed.expects:
                if expected.key.startswith("fit:") and expected.key not in seen:
                    check(expected, None, expected.key.split(":")[1])
    return found


# --- Der Umbau ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Revision:
    """Ein geprüfter Umbau, bereit zum Übernehmen."""

    plan: RevisionPlan
    result: EvaluationResult
    """Die isolierte Auswertung des Vorschlags — derselbe Stand, den das Übernehmen rechnet."""
    findings: tuple[Finding, ...] = ()
    """Was der Kunde dazu wissen sollte: gefolgte Verweise, mitgenommene Schritte."""


type AnnounceFn = Callable[[EvaluationResult | None, tuple[tuple[ObjectId, FeatureId], ...]], None]


def _followed(drift: Drift) -> Finding:
    """Der Satz zu einem Verweis, der seinem Merkmal unter neuem Namen folgt."""
    return Finding(
        code="history.reference_followed",
        severity="info",
        message=_("Ein Verweis folgt seinem Merkmal, das jetzt anders heißt."),
        object_id=drift.object_id or None,
        op_id=drift.step,
        feature_ids=(drift.verdict.name or drift.feature,),
        values={
            "from": drift.feature,
            "to": drift.verdict.name or "",
            **({"fit": drift.fit} if drift.fit else {}),
        },
    )


def _old_number(plan: RevisionPlan, step: OpId | None) -> OpId | None:
    """Die Kennung, die ein Schritt des Vorschlags **heute** trägt — ``None`` für einen neuen."""
    if step is None:
        return None
    for old, new in plan.renumbered.items():
        if new == step:
            return old
    return None if step in plan.subjects and plan.kind == "insert" else step


def _halted(document: Document, plan: RevisionPlan, result: EvaluationResult) -> UserError:
    """Die Absage, wenn der Vorschlag anhält — mit dem Grund aus dem Halt."""
    halt = next(
        (
            finding
            for finding in result.scene.report.findings
            if finding.severity == "error" and finding.op_id == result.stopped_at
        ),
        None,
    )
    shown = _old_number(plan, result.stopped_at)
    reason: TranslatableText | str = halt.message if halt is not None else ""
    known = {entry.id for entry in document.ops}
    if plan.kind == "suppress" and shown in known and shown not in plan.subjects:
        # Ein späterer Schritt, der ohne den ausgeschalteten nicht rechnet —
        # ein Deckel ohne Hohlraum. Kein stilles Mitnehmen: der Weg ist ein
        # Knopf, der ihn ausdrücklich mit ausschaltet (Regel 17).
        return UserError(
            title=_("Das würde die Kette anhalten — geändert wurde nichts."),
            detail=_(
                "Ohne diesen Schritt hielte Schritt {number} an: {reason}",
                number=shown,
                reason=reason,
            ),
            values={
                **(dict(halt.values) if halt is not None else {}),
                "number": shown,
                "also": shown,
                "steps": ",".join(str(step) for step in plan.subjects),
            },
            op_id=shown,
            suggestions=(SUPPRESS_ALONG, CANCEL),
        )
    return UserError(
        title=_("Das würde die Kette anhalten — geändert wurde nichts."),
        detail=(
            _("Danach hielte Schritt {number} an: {reason}", number=shown, reason=reason)
            if shown is not None
            else _("Danach hielte der neue Schritt an: {reason}", reason=reason)
        ),
        values={
            **(dict(halt.values) if halt is not None else {}),
            **({"number": shown} if shown is not None else {}),
        },
        op_id=shown if shown in known else None,
        suggestions=(CANCEL,),
    )


def _lost(document: Document, drift: Drift, plan: RevisionPlan) -> UserError:
    """Die Absage, wenn ein Verweis sein Merkmal verliert und niemand wählt (Regel 21)."""
    number = _old_number(plan, drift.step)
    known = {entry.id for entry in document.ops}
    return AmbiguityError(
        (
            _("Danach fände Schritt {number} sein Merkmal nicht mehr.", number=number)
            if drift.fit is None and number is not None
            else _("Danach fände eine Passung ihr Merkmal nicht mehr.")
        ),
        candidates=drift.verdict.candidates,
        title=_("Ein Verweis verlöre sein Merkmal — geändert wurde nichts."),
        values={
            "feature": drift.feature,
            "object": drift.object_id,
            **({"fit": drift.fit} if drift.fit else {}),
            **({"step": number} if number is not None else {}),
        },
        op_id=number if number in known else None,
        **({} if drift.verdict.candidates else {"suggestions": (CANCEL,)}),
    )


def _question(drift: Drift) -> tuple[str, list[str]]:
    """Die Frage an den Kunden: welches Merkmal gemeint ist (§21.3)."""
    from app.i18n import tr

    if drift.fit is not None:
        text = tr("Welches Merkmal meint die Passung {name}?").replace("{name}", drift.fit)
    else:
        text = tr("Welches Merkmal meint Schritt {number}?").replace("{number}", str(drift.step))
    return text, list(drift.verdict.candidates)


def _apply_renames(
    history: History,
    plan: RevisionPlan,
    found: Sequence[tuple[Drift, FeatureId]],
    registry: Registry,
) -> RevisionPlan:
    """Die Verweise auf den neuen Namen desselben Merkmals setzen — im Plan, nicht im Dokument."""
    versions: dict[OpId, Operation] = {}
    fits: list[Fit] | None = None
    for drift, name in found:
        if drift.fit is not None:
            if fits is None:
                current = plan.transaction.changes.after.fits if plan.transaction.changes else None
                fits = list(current if current is not None else history.document.fits)
            side = drift.key.rsplit(":", 1)[1]
            fits = [
                (
                    dataclasses.replace(fit, a=FeatureRef(fit.a.object_id, name))
                    if side == "a"
                    else dataclasses.replace(fit, b=FeatureRef(fit.b.object_id, name))
                )
                if fit.name == drift.fit
                else fit
                for fit in fits
            ]
            continue
        assert drift.step is not None
        version = versions.get(drift.step) or plan.version(drift.step)
        if version is None:
            original = history.operation(drift.step)
            changed = with_reference(original, drift.key, name, registry)
            plan = plan.editing(original, changed)
            continue
        versions[drift.step] = with_reference(version, drift.key, name, registry)
    if versions:
        plan = plan.replacing(versions)
    if fits is not None:
        plan = plan.with_fits(history.document.fits, fits)
    return plan


def _expectations_of(
    original: Operation, baseline: EvaluationResult | None
) -> dict[str, ReferenceExpectation]:
    """Was die Verweise eines Schritts treffen sollen — Sichtung von vorhin oder eigener Vermerk."""
    if original.suppressed is not None:
        return {
            expected.key: expected
            for expected in original.suppressed.expects
            if not expected.key.startswith("fit:")
        }
    found: dict[str, ReferenceExpectation] = {}
    for sight in baseline.sights.get(original.id, ()) if baseline is not None else ():
        expected = expectation_of(sight)
        if expected is not None:
            found[expected.key] = expected
    return found


def _fit_expectations(
    document: Document, baseline: EvaluationResult | None
) -> dict[str, ReferenceExpectation]:
    """Was die Passungen am Endstand treffen sollen — aus dem Lauf oder dem Vermerk."""
    found: dict[str, ReferenceExpectation] = {}
    for sight in baseline.fit_sights if baseline is not None else ():
        expected = expectation_of(sight)
        if expected is not None:
            found[expected.key] = expected
    for entry in document.ops:
        if entry.suppressed is None:
            continue
        for expected in entry.suppressed.expects:
            if expected.key.startswith("fit:"):
                found.setdefault(expected.key, expected)
    return found


def _walk(
    history: History,
    plan: RevisionPlan,
    evaluate: Callable[[Document], EvaluationResult],
    baseline: EvaluationResult | None,
    registry: Registry,
    chosen: Mapping[tuple[OpId | None, str], ReferenceExpectation],
) -> tuple[list[Drift], EvaluationResult | None]:
    """Die Verweise Schritt für Schritt gegen den Stand **unmittelbar davor** prüfen.

    Der Weg, wenn der ganze Vorschlag anhält: Ein späterer Verweis unter
    seinem alten Namen verlangt am exakten Körper einen Beleg für ein fremdes
    Merkmal (``NativeReferenceLost`` beim Neubau davor), und die Kette hält,
    bevor der Vergleich den Namen berichtigen kann. Hier rechnet jeweils nur
    der Stapel bis vor den Schritt, ohne Passungen und ohne die Verweise
    danach — der Cache trägt, was schon gerechnet ist. Zurück kommt die erste
    Gruppe verschobener oder verlorener Verweise samt dem Stand, an dem sie
    gefunden wurden, oder der Halt, wenn schon der Stand davor nicht rechnet.
    """
    document = plan.document(history.document)
    ordered = sorted(document.ops, key=lambda operation: operation.id)
    reverse = {new: old for old, new in plan.renumbered.items()}
    originals = {entry.id: entry for entry in history.document.ops}
    grouped: dict[OpId, list[Reference]] = {}
    for reference in references(document, registry):
        if reference.kind != "fit":
            grouped.setdefault(reference.op_id, []).append(reference)
    for index, entry in enumerate(ordered):
        if entry.suppressed is not None or entry.id not in grouped:
            continue
        original = originals.get(reverse.get(entry.id, entry.id))
        if original is None or (plan.kind == "insert" and entry.id in plan.subjects):
            continue
        wanted = _expectations_of(original, baseline)
        if not wanted:
            continue
        state = evaluate(dataclasses.replace(document, ops=ordered[:index], fits=[]))
        if not state.complete:
            return [], state
        found = []
        for reference in grouped[entry.id]:
            expected = chosen.get((entry.id, reference.key), wanted.get(reference.key))
            if expected is None:
                continue
            sight = sight_of(reference, state.scene.objects)
            ruling = verdict(expected, sight, plan.renumbered)
            if ruling.state != "kept":
                found.append(
                    Drift(
                        key=expected.key,
                        feature=expected.feature,
                        object_id=sight.ref.object_id,
                        verdict=ruling,
                        step=entry.id,
                        sight=sight,
                    )
                )
        if found:
            return found, state
    fits = _fit_expectations(history.document, baseline)
    if not fits:
        return [], None
    state = evaluate(dataclasses.replace(document, fits=[]))
    if not state.complete:
        return [], state
    found = []
    for fit in active_fits(document):
        for side, target in (("a", fit.a), ("b", fit.b)):
            key = f"fit:{fit.name}:{side}"
            expected = chosen.get((None, key), fits.get(key))
            if expected is None:
                continue
            sight = sight_of(Reference(key, target), state.scene.objects)
            ruling = verdict(expected, sight, plan.renumbered)
            if ruling.state != "kept":
                found.append(
                    Drift(
                        key=key,
                        feature=expected.feature,
                        object_id=target.object_id,
                        verdict=ruling,
                        fit=fit.name,
                        sight=sight,
                    )
                )
    return found, state


def searched_at_the_end(
    document: Document,
    title: TranslatableText | str,
    drafts: Sequence[OperationDraft],
    *,
    evaluate: Callable[[Document], EvaluationResult],
    registry: Registry | None = None,
) -> list[OperationDraft]:
    """Neue Schritte, die ihre Stelle an der Szene suchen, suchen sie am Endstand (P7.1, §17.1).

    An der Einfügemarke sähe ein weiteres Modell nur die Szene vor der Marke.
    Ein späteres Modell, dessen Stelle schon feststeht, steht dort noch nicht,
    und beide lägen deckungsgleich (Review N4). Gesucht wird deshalb an einer
    Kopie mit den Schritten **am Ende** — dem Stand, den der Kunde vor sich
    hat —, und die Antworten stehen danach im Entwurf (§15.7): Am
    Einfügeort sucht der Schritt nicht mehr. Hält die Kette vorher an, gibt
    es keine Antwort, und der Entwurf bleibt, wie er war.
    """
    source = registry or REGISTRY
    if not any(reads_scene(source.get(draft.op).params, draft.params) for draft in drafts):
        return list(drafts)
    trial = History(deepcopy(document))
    added = trial.apply(title, drafts)
    answers = evaluate(trial.document).answers
    return [
        dataclasses.replace(draft, params={**draft.params, **answers.get(op_id, {})})
        for draft, op_id in zip(drafts, added.ops, strict=True)
    ]


def revise(
    history: History,
    plan: RevisionPlan,
    *,
    evaluate: Callable[[Document], EvaluationResult],
    baseline: EvaluationResult | None,
    context: Dependencies | None = None,
    ask: Callable[[str, list[str]], str] | None = None,
    announce: AnnounceFn | None = None,
    registry: Registry | None = None,
) -> Revision:
    """Einen geplanten Umbau isoliert rechnen und prüfen — oder sagen, warum nicht.

    ``evaluate`` rechnet eine Dokumentkopie, wie der Aufrufer es tut (Cache,
    Profil, Quellen, Abbruch, Fortschritt); das Dokument der ``history`` wird
    nie angefasst. Zurück kommt der Plan, den :meth:`History.commit`
    übernehmen soll — mit gefolgten Verweisen und, beim Ausschalten, mit
    Schritten, die mitruhen müssen. Eine Absage ist ein ``UserError`` mit
    Handlungsvorschlag (Regel 17); geschrieben ist dann nichts.
    """
    source = registry or REGISTRY
    notes: list[Finding] = []
    also: set[OpId] = set()
    paused: dict[OpId, list[str]] = {}
    chosen: dict[tuple[OpId | None, str], ReferenceExpectation] = {}
    for _round in range(MAX_ROUNDS):
        result = evaluate(plan.document(history.document))
        found = drifts(history.document, plan, baseline, result, chosen)
        seen_at = result
        if not found and not result.complete:
            # Hält der Vorschlag an, kann ein späterer Verweis unter altem
            # Namen die Ursache sein: Schritt für Schritt nachsehen.
            walked, state = _walk(history, plan, evaluate, baseline, source, chosen)
            if not walked:
                raise _halted(history.document, plan, state or result)
            found, seen_at = walked, state or result
        if not found:
            return Revision(plan=plan, result=result, findings=tuple(notes))
        renames = [
            (drift, drift.verdict.name) for drift in found if drift.verdict.state == "renamed"
        ]
        lost = [drift for drift in found if drift.verdict.state == "lost"]
        if plan.kind == "suppress" and lost:
            # Beim Ausschalten ist ein verlorenes Merkmal eines, das im
            # ausgeschalteten Schritt entsteht: Sein Nutzer ruht mit.
            for drift in lost:
                if drift.step is not None:
                    also.add(drift.step)
                elif drift.fit is not None:
                    paused.setdefault(plan.subjects[0], []).append(drift.fit)
            plan = history.plan_suppress(
                plan.subjects, context, also=tuple(sorted(also)), paused=paused
            )
            continue
        answered: list[tuple[Drift, FeatureId]] = []
        for drift in lost:
            if ask is None or not drift.verdict.candidates:
                raise _lost(history.document, drift, plan)
            question, choices = _question(drift)
            if announce is not None:
                announce(
                    seen_at, tuple((drift.object_id, name) for name in drift.verdict.candidates)
                )
            try:
                try:
                    answer = ask(question, [*choices, _cancel_choice()])
                except AmbiguityError:
                    raise _lost(history.document, drift, plan) from None
            finally:
                if announce is not None:
                    announce(None, ())
            if answer not in choices:
                raise _lost(history.document, drift, plan)
            answered.append((drift, answer))
            picked = _chosen(drift, answer)
            if picked is not None:
                chosen[(drift.step, drift.key)] = picked
        notes.extend(_followed(drift) for drift, _name in renames)
        plan = _apply_renames(history, plan, [*renames, *answered], source)  # type: ignore[list-item]
    raise UserError(
        title=_("Das würde die Kette anhalten — geändert wurde nichts."),
        detail=_("Die Verweise ließen sich nicht eindeutig zuordnen."),
        suggestions=(CANCEL,),
    )


def _cancel_choice() -> str:
    from app.i18n import tr

    return tr("Abbrechen")


def commit(history: History, revision: Revision) -> Transaction:
    """Übernimmt einen geprüften Umbau und schreibt die Antworten seines Laufs mit.

    Was der Vorschlag beim Rechnen erfragt hat (Einheit, Zuordnung), steht in
    seinem Ergebnis unter den Kennungen, die das Übernehmen vergibt — dieselben
    wie im Plan. Ohne diesen Schritt fragte der nächste Lauf dieselbe Frage
    noch einmal (§15.7). Die Antworten ergänzen die Transaktion und bekommen
    keine eigene.
    """
    transaction = history.commit(revision.plan)
    history.record_answers(revision.result.answers)
    history.record_matches(revision.result.matches)
    history.record_solvers(revision.result.solvers)
    return transaction
