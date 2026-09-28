"""Stapel, Transaktionen und Undo (Bauplan §12, §15.4, §15.5).

Operationen bilden über ``in``/``out`` einen DAG und bleiben linear
darstellbar: die Reihenfolge der Op-Nummern ist die Reihenfolge des
Verlaufspanels.

Die Einheit des Undo ist die Transaktion, nicht die Operation — ein
Agentenvorschlag ist genau eine Transaktion (AGENTS.md Regel 16), ein Undo
nimmt also in einem Zug zurück, was der Agent vorgeschlagen hat.

Verzweigungen gibt es nicht (§15.4). Wer nach einem Undo etwas anwendet,
verwirft die abgeschnittenen Transaktionen; die Oberfläche fragt vorher, sobald
mehr als eine betroffen ist — dafür gibt es :attr:`History.discardable`.
"""

from __future__ import annotations

import dataclasses
import itertools
import math
import re
import secrets
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Final

from app.core import activation, expressions
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    DECIMATE_AND_RETRY,
    RECOUNT_AND_RETRY,
    REMESH_AND_RETRY,
    REPAIR_AND_RETRY,
    SHOW_STEP_VALUES,
    SPLIT_AND_RETRY,
    AppError,
    InternalError,
    UserError,
    ValidationError,
)
from app.core.log import get_logger
from app.core.perceive.match_records import EDGE_DOMAIN, domain_of, recognition_answer_key
from app.core.registry import REGISTRY, VARIABLE, Registry, needed_inputs
from app.core.registry.params import body_keys
from app.core.scene import bundling
from app.core.types import (
    Document,
    DocumentChange,
    DocumentState,
    FeatureId,
    Fit,
    ObjectId,
    Operation,
    OpId,
    Origin,
    Parameter,
    ParameterName,
    PrintSettings,
    ReferenceExpectation,
    RevisionKind,
    SpoolBinding,
    Suppression,
    Transaction,
    TransactionId,
)
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Wie viele gelöschte Schritte der Titel beim Namen nennt.
#:
#: Drei, und dann eine Zahl: Die Löschung nimmt abhängige Schritte mit, und
#: das können viele sein. Dieselbe Entscheidung wie bei der Sammelzeile des
#: Prüfberichts — jede Einzelzeile stimmt, die Menge begräbt.
_NAMED_IN_TITLE: Final = 3


_OBJECT_PATTERN = re.compile(r"^obj_(\d+)$")

#: Vorgegebene Urheberschaft. Manuelle Operationen sind einzelne Transaktionen
#: des Nutzers (§15.5).
USER_ORIGIN: Final[Origin] = Origin(by="user")


def _living_objects(operations: Sequence[Operation]) -> set[ObjectId]:
    """Die Körper, die nach einer Folge aktiver Schritte noch vorhanden sind.

    Ein ausgeschalteter Schritt zählt nicht (P7.3): Was er frisch anlegen
    würde, gibt es nicht, und was er verbrauchen würde, bleibt stehen —
    dieselbe Rechnung wie in der Auswertung (``evaluate._absent_objects``).
    """
    living: set[ObjectId] = set()
    for entry in operations:
        if entry.suppressed is not None:
            continue
        living.difference_update(set(entry.inputs) - set(entry.outputs))
        living.update(entry.outputs)
    return living


def _structural_objects(operations: Sequence[Operation]) -> set[ObjectId]:
    """Die Körper nach einer Folge **aller** Schritte, ausgeschaltet oder nicht.

    Der Bau eines Verlaufs ist eine Sache der Kennungen: Ein ausgeschalteter
    Schritt, der ``obj_4`` anlegt, bleibt der Schritt, der ``obj_4`` anlegt,
    und ein mitgenommener danach arbeitet weiter an ``obj_4`` — sonst ließe
    sich beim Neuplanen keiner von beiden neu fassen, und beim Einschalten
    stimmte die Kette nicht mehr. Ob gerechnet wird, entscheidet die
    Auswertung; ob die Folge zusammenpasst, diese Rechnung.
    """
    living: set[ObjectId] = set()
    for entry in operations:
        living.difference_update(set(entry.inputs) - set(entry.outputs))
        living.update(entry.outputs)
    return living


def _renumbered_suppression(
    suppression: Suppression | None, renumbered: Mapping[OpId, OpId]
) -> Suppression | None:
    """Dieselbe Unterdrückung, deren Erzeugerkennungen einer Neuplanung folgen.

    Ein ruhender Schritt hält fest, welcher Schritt das Merkmal anlegte, das
    er braucht (``ReferenceExpectation.creator``). Plant ein Umbau diesen
    Erzeuger unter neuer Kennung neu, folgt der Vermerk — sonst prüfte das
    Einschalten gegen einen Schritt, den es nicht mehr gibt.
    """
    if suppression is None or not suppression.expects:
        return suppression
    return dataclasses.replace(
        suppression,
        expects=tuple(
            dataclasses.replace(entry, creator=renumbered.get(entry.creator, entry.creator))
            if entry.creator is not None
            else entry
            for entry in suppression.expects
        ),
    )


def repair_targets(
    document: Document,
    stopped_at: OpId,
    registry: Registry = REGISTRY,
) -> tuple[ObjectId, ...]:
    """Reparierbare Eingänge eines angehaltenen Netzschritts.

    Diese Prüfung ist die gemeinsame Schranke für Verlauf und Oberfläche:
    angeboten wird nur, was :meth:`History.repair_and_retry` anschließend
    wirklich als einen Zug planen kann. Ein Schritt des exakten Kerns bleibt
    ausgeschlossen, weil ``repair`` seine einzeln bearbeitbaren Flächen in
    feste Dreiecke umwandeln würde und der erneute Versuch dann sicher hält.
    """
    operations = tuple(sorted(document.ops, key=lambda entry: entry.id))
    failed_index = next(
        (index for index, entry in enumerate(operations) if entry.id == stopped_at),
        None,
    )
    if failed_index is None:
        return ()
    failed = operations[failed_index]
    if not registry.has(failed.op) or registry.get(failed.op).requires_kind == "brep":
        return ()
    living = _living_objects(operations[:failed_index])
    targets = tuple(dict.fromkeys(failed.inputs))
    if not targets or any(target not in living for target in targets):
        return ()
    return targets


def repair_is_available(
    document: Document | None,
    *,
    stopped_at: OpId | None,
    op_id: OpId | None,
    object_id: ObjectId | None,
    live_objects: Collection[ObjectId] | None = None,
    registry: Registry = REGISTRY,
) -> bool:
    """Ob ein Reparaturvorschlag aus diesem Dokument ausführbar ist.

    Ein Operationsfehler darf seinen Suffix nur am aktuell angehaltenen
    Schritt ersetzen. Ein ausdrücklich genannter, noch vorhandener Körper
    kann dagegen als gewöhnlicher nächster Reparaturschritt behandelt werden.
    Die Bauartprüfung gilt in beiden Fällen.
    """
    if document is None:
        return False
    operation = next((entry for entry in document.ops if entry.id == op_id), None)
    if operation is not None and (
        not registry.has(operation.op) or registry.get(operation.op).requires_kind == "brep"
    ):
        return False
    if op_id is not None and stopped_at == op_id:
        return bool(repair_targets(document, op_id, registry))
    available = (
        live_objects
        if live_objects is not None
        else _living_objects(tuple(sorted(document.ops, key=lambda entry: entry.id)))
    )
    return object_id is not None and object_id in available


def recognition_reopenable(
    document: Document, object_id: ObjectId, *, declined_only: bool = False
) -> bool:
    """Ob am Ladeschritt eines Körpers eine Erkennungswahl steht (§21.1).

    Die eine Auskunft für den Knopf *Alle Merkmale erkennen* und für
    :meth:`History.reopen_recognition`: Zurücknehmen lässt sich nur eine Wahl,
    die dasteht. Ein Körper, der unter der Grenze geladen und erst danach
    größer wurde, hat keine — die Frage gibt es nur am Ladeschritt, und der
    Knopf rechnete dort den Stapel neu, ohne dass eine kam (Review N3,
    25.09.2026). Die Auswertung sagt dasselbe am Befund aus
    ``evaluate._BodyRecognition.answer``. ``declined_only`` fragt nur nach
    einer Absage — nachzuholen gibt es nur, was ausgelassen wurde.
    """
    key = recognition_answer_key(object_id)
    for index in _answering_load_steps(document, {key}):
        record = document.ops[index].matches[key]
        if not declined_only or (isinstance(record, Mapping) and record.get("allowed") is False):
            return True
    return False


def _answering_load_steps(document: Document, keys: Collection[str]) -> list[int]:
    """Die Ladeschritte, die eine dieser Erkennungswahlen tragen, nach Platz im Stapel."""
    return [
        index
        for index, entry in enumerate(document.ops)
        if entry.op == "load" and not set(keys).isdisjoint(entry.matches)
    ]


def _copy_operation_matches(
    entry: Operation,
    *,
    previous_outputs: tuple[ObjectId, ...] | None = None,
    previous_inputs: tuple[ObjectId, ...] | None = None,
) -> Operation:
    """Kopiert Antworten ohne Alias und überträgt keine Gruppe auf einen fremden Körper.

    Gruppen gehören einem Ausgabekörper, Kantenantworten (``edge-answer:``)
    einem Eingangskörper — jede Domäne wird gegen ihre eigene Liste
    gefiltert, wenn sich Aus- beziehungsweise Eingänge ändern. Nichts wird
    auf einen neuen Körper umbenannt.
    """
    if not entry.matches:
        return entry
    matches = dict(entry.matches)
    if previous_outputs is not None and entry.outputs != previous_outputs:
        outputs = set(entry.outputs)
        matches = {
            key: value
            for key, value in matches.items()
            if key == "legacy" or domain_of(key) == EDGE_DOMAIN or value.get("object_id") in outputs
        }
    if previous_inputs is not None and entry.inputs != previous_inputs:
        inputs = set(entry.inputs)
        matches = {
            key: value
            for key, value in matches.items()
            if key == "legacy" or domain_of(key) != EDGE_DOMAIN or value.get("object_id") in inputs
        }
    return dataclasses.replace(entry, matches=deepcopy(matches))


#: Der Namensraum eingesetzter Bausteine im Stapel (``knowledge.parts.ops``).
#: Nur er: Einen Stand zum Wählen haben allein Rezepte, und ein Rezept wird
#: immer eingesetzt — ``create_`` teilt es sich mit den Grundkörpern.
_PART_PREFIX: Final = "insert_"


def _part_state_target(op_name: str, states: Mapping[str, str]) -> str | None:
    """Der Operationsname desselben Schritts mit dem Baustein aus ``states``."""
    if not op_name.startswith(_PART_PREFIX):
        return None
    wanted = states.get(op_name[len(_PART_PREFIX) :])
    return f"{_PART_PREFIX}{wanted}" if wanted else None


def restore(document: Document, state: DocumentState) -> None:
    """Legt eine Seite einer Dokumentänderung ins Dokument zurück (§15.5).

    Eine Funktion für beide Richtungen: ein Undo schreibt ``before``, ein Redo
    ``after``, und das Anwenden ebenfalls ``after``. Zwei getrennte Wege wären
    zwei Stellen, an denen ein Feld vergessen werden kann — und vergessen
    würde hier heißen, dass ein Undo *fast* alles zurücknimmt.

    Ein Feld, das ``None`` ist, war nicht beteiligt und wird nicht angefasst.
    Ein Parameter, der ``None`` ist, gab es zu diesem Zeitpunkt nicht und wird
    entfernt.
    """
    if state.parameters is not None:
        for name, parameter in state.parameters.items():
            if parameter is None:
                document.parameters.pop(name, None)
            else:
                document.parameters[name] = parameter
    if state.fits is not None:
        document.fits[:] = list(state.fits)
    if state.printer is not None:
        document.printer = state.printer
    if state.material is not None:
        document.material = state.material
    if state.spool_bindings is not None:
        document.print_settings = dataclasses.replace(
            document.print_settings or PrintSettings(), spool_bindings=state.spool_bindings
        )
    if state.edited_ops is not None:
        # Eine Fassung ersetzt an Ort und Stelle. ``None`` entfernt; eine
        # Fassung zu einer fehlenden Kennung setzt wieder ein — genau diese
        # beiden Richtungen braucht das rücknehmbare Löschen seit Format v17.
        for op_id, version in state.edited_ops.items():
            if version is None:
                document.ops[:] = [entry for entry in document.ops if entry.id != op_id]
                continue
            for index, entry in enumerate(document.ops):
                if entry.id == op_id:
                    document.ops[index] = _copy_operation_matches(version)
                    break
            else:
                document.ops.append(_copy_operation_matches(version))
        document.ops.sort(key=lambda entry: entry.id)


#: Eine Änderung, die erst feststeht, wenn die Operationen geplant sind.
#:
#: Sie bekommt die geplanten Operationen — mit ihren Ausgabekennungen — und
#: liefert die Dokumentänderung dazu. Siehe :meth:`History.apply`.
ChangeFn = Callable[[Sequence["Operation"]], DocumentChange | None]


def change_for(
    document: Document,
    *,
    parameters: Mapping[ParameterName, Parameter] | None = None,
    fits: Sequence[Fit] | None = None,
    printer: str | None = None,
    material: str | None = None,
    spool_bindings: Sequence[SpoolBinding] | None = None,
) -> DocumentChange:
    """Baut beide Seiten einer Dokumentänderung aus dem heutigen Stand.

    Damit kein Aufrufer die Vorher-Seite selbst zusammensucht: genau das war
    der Fehler, den der Agent hatte — er führte seine eigene Buchhaltung über
    frühere Werte, und die Oberfläche kannte sie nicht. Wer hier ``fits``
    übergibt, meint die vollständige neue Liste, nicht die Ergänzung.

    **Ein Projektmaß trägt endliche Zahlen.** ``float`` liest „inf" und „nan",
    die Projektdatei schreibt beides nicht — ein solcher Parameter machte das
    Projekt unspeicherbar, und die Ablehnung kam erst beim Speichern als
    nackter ValueError (Gesamtreview 05.09.2026, UI-26). Geprüft wird hier,
    wo jede Parameteränderung vorbeikommt: Dialog, Leiste und Agent.
    """
    for parameter in (parameters or {}).values():
        for field_name in ("value", "minimum", "maximum"):
            number = getattr(parameter, field_name)
            if isinstance(number, (int, float)) and not math.isfinite(number):
                raise ValidationError(
                    field=field_name,
                    detail=_(
                        "Ein Projektmaß braucht endliche Zahlen — für den Wert wie für die Grenzen."
                    ),
                    constraint="not_finite",
                    values={"parameter": parameter.name, "field": field_name},
                )
    return DocumentChange(
        before=DocumentState(
            parameters=(
                {name: document.parameters.get(name) for name in parameters}
                if parameters is not None
                else None
            ),
            fits=tuple(document.fits) if fits is not None else None,
            printer=document.printer if printer is not None else None,
            material=document.material if material is not None else None,
            spool_bindings=(
                (document.print_settings.spool_bindings if document.print_settings else ())
                if spool_bindings is not None
                else None
            ),
        ),
        after=DocumentState(
            parameters=dict(parameters) if parameters is not None else None,
            fits=tuple(fits) if fits is not None else None,
            printer=printer,
            material=material,
            spool_bindings=tuple(spool_bindings) if spool_bindings is not None else None,
        ),
    )


@dataclass(frozen=True, slots=True)
class StepNeed:
    """Ein Schritt braucht einen früheren (P7.2, P7.3).

    Zwei Arten, und beide gehören zur Folge, nicht zur Geometrie: ein Körper,
    den erst der frühere anlegt (``feature_id is None``), oder ein Merkmal, das
    in ihm entsteht. Aus der Körperkette folgt die erste Art von selbst; die
    zweite kennt nur eine Auswertung — ``scene.revision.dependencies`` liest
    sie aus den Sichtungen eines Laufs (``Feature.created_by``).
    """

    step: OpId
    on: OpId
    object_id: ObjectId
    feature_id: FeatureId | None = None


@dataclass(frozen=True, slots=True)
class Dependencies:
    """Was ein Umbau des Verlaufs über die Folge wissen muss — aus einem gerechneten Stand (P7).

    Ohne sie kennt der Verlauf nur die Körperkette. Umsortieren und Ausschalten
    sagen dann nichts über Merkmale, die ein früherer Schritt anlegt; die
    isolierte Auswertung danach fängt es trotzdem, nur später und ohne den
    Grund vorab zu nennen.
    """

    needs: tuple[StepNeed, ...] = ()
    expectations: Mapping[OpId, tuple[ReferenceExpectation, ...]] = field(default_factory=dict)
    """Je Schritt, was seine Verweise zuletzt trafen — für das Ausschalten."""
    fit_needs: Mapping[str, frozenset[OpId]] = field(default_factory=dict)
    """Je Passung die Schritte, deren Merkmal oder Körper sie braucht."""
    fit_expectations: Mapping[str, tuple[ReferenceExpectation, ...]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RevisionPlan:
    """Ein Umbau des Verlaufs, fertig geplant und noch nicht geschrieben (P7).

    **Planen, isoliert rechnen, dann übernehmen.** Der Plan trägt die
    Transaktion, die :meth:`History.commit` anhängt, samt der neu gefassten
    Schritte; :meth:`document` baut daraus die Kopie für die isolierte
    Auswertung. Erst ein gültiges Ergebnis ersetzt die Folge — ein ungültiger
    Vorschlag verändert nichts (Konzept vollwertiges CAD §13.9).
    """

    kind: RevisionKind
    transaction: Transaction
    planned: tuple[Operation, ...] = ()
    """Die neu gefassten Schritte beim Einfügen und Verschieben, in ihrer Folge."""
    renumbered: Mapping[OpId, OpId] = field(default_factory=dict)
    """Alte Kennung → neue Kennung für jeden neu gefassten Schritt."""
    subjects: tuple[OpId, ...] = ()
    """Die gewählten Schritte (beim Einfügen die neuen)."""
    carried: tuple[OpId, ...] = ()
    """Beim Ausschalten die mitgenommenen, beim Einschalten die mitgeholten Schritte."""
    mark: tuple[Any, ...] = ()
    """Der Dokumentstand beim Planen — ein anderer heißt: veraltet."""

    def new_id(self, op_id: OpId) -> OpId:
        """Die Kennung, die ein Schritt nach diesem Umbau trägt."""
        return self.renumbered.get(op_id, op_id)

    def document(self, base: Document) -> Document:
        """Eine Kopie von ``base`` mit diesem Umbau — nur für die isolierte Auswertung."""
        copied = deepcopy(base)
        copied.ops.extend(deepcopy(self.planned))
        copied.transactions.append(self.transaction)
        if self.transaction.changes is not None:
            restore(copied, self.transaction.changes.after)
        return copied

    def version(self, op_id: OpId) -> Operation | None:
        """Die Fassung eines Schritts nach diesem Umbau — neue Kennung gefragt."""
        for entry in self.planned:
            if entry.id == op_id:
                return entry
        changes = self.transaction.changes
        if changes is not None and changes.after.edited_ops is not None:
            return changes.after.edited_ops.get(op_id)
        return None

    def replacing(self, versions: Mapping[OpId, Operation]) -> RevisionPlan:
        """Derselbe Plan mit anderen Fassungen einzelner Schritte — ihr Verweis folgt
        seinem Merkmal unter neuem Namen (``scene.revision``)."""
        planned = tuple(versions.get(entry.id, entry) for entry in self.planned)
        transaction = self.transaction
        changes = transaction.changes
        if changes is not None and changes.after.edited_ops is not None:
            edited = {
                op_id: versions.get(op_id, entry) if entry is not None else None
                for op_id, entry in changes.after.edited_ops.items()
            }
            transaction = dataclasses.replace(
                transaction,
                changes=dataclasses.replace(
                    changes, after=dataclasses.replace(changes.after, edited_ops=edited)
                ),
            )
        return dataclasses.replace(self, planned=planned, transaction=transaction)

    def editing(self, original: Operation, changed: Operation) -> RevisionPlan:
        """Derselbe Plan, der zusätzlich einen unbeteiligten Schritt neu fasst.

        Beim Aus- und Einschalten behält jeder Schritt seine Kennung; verschiebt
        sich dabei nur der Name des Merkmals, das ein anderer Schritt nennt,
        folgt dessen Verweis — und seine alte Fassung reist in derselben
        Transaktion mit, damit ein Strg+Z auch sie zurücklegt.
        """
        changes = self.transaction.changes or DocumentChange()
        before = dict(changes.before.edited_ops or {})
        after = dict(changes.after.edited_ops or {})
        before.setdefault(original.id, _copy_operation_matches(original))
        after[changed.id] = _copy_operation_matches(changed)
        return dataclasses.replace(
            self,
            transaction=dataclasses.replace(
                self.transaction,
                changes=DocumentChange(
                    before=dataclasses.replace(changes.before, edited_ops=before),
                    after=dataclasses.replace(changes.after, edited_ops=after),
                ),
            ),
        )

    def with_fits(self, current: Sequence[Fit], fits: Sequence[Fit]) -> RevisionPlan:
        """Derselbe Plan, dessen Passungen am Ende ``fits`` lauten (vorher: ``current``)."""
        changes = self.transaction.changes or DocumentChange()
        before_fits = changes.before.fits if changes.before.fits is not None else tuple(current)
        return dataclasses.replace(
            self,
            transaction=dataclasses.replace(
                self.transaction,
                changes=DocumentChange(
                    before=dataclasses.replace(changes.before, fits=tuple(before_fits)),
                    after=dataclasses.replace(changes.after, fits=tuple(fits)),
                ),
            ),
        )


@dataclass(frozen=True, slots=True)
class MoveTarget:
    """Eine Stelle, an die sich die gewählten Schritte verschieben ließen (P7.2)."""

    before: OpId | None
    """Vor diesen Schritt, ``None`` ans Ende."""
    problem: AppError | None = None
    """Warum es dort nicht geht — ``None`` heißt: gültig."""


@dataclass(frozen=True, slots=True)
class OperationDraft:
    """Eine Operation kurz vor dem Stapel. Die Nummern vergibt der Verlauf.

    ``outputs`` ist meist abgeleitet: gleiche Anzahl rein wie raus behält die
    IDs, sonst gibt es neue."""

    op: str
    inputs: tuple[ObjectId, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    outputs: tuple[ObjectId, ...] | None = None
    produces: int | None = None
    """Wie viele Objekte eine Operation mit variabler Ausgabe ohne Eingaben
    erzeugen wird.

    Der Fall ist das Laden einer Baugruppe: wie viele Körper herauskommen,
    steht in der Datei, und der Stapel vergibt IDs, bevor die Datei gelesen
    ist (§11). Also sagt es der Aufrufer, der es weiß — für alles andere folgt
    die Anzahl aus der Deklaration, und hier bleibt ``None``."""
    seed: int | None = None


class History:
    """Hält ein Dokument und den Weg hindurch."""

    def __init__(self, document: Document, registry: Registry | None = None) -> None:
        self.document = document
        self._registry = registry or REGISTRY
        self._open_bundle: TransactionId | None = None
        """Die Transaktion, deren Bündel offen ist — nur in sie nimmt ein
        weiterer Zug auf. Ohne Anker beginnt ein Zug einen neuen Schritt,
        auch wenn er gleichartig wäre."""
        self._undone: list[Transaction] = []
        self._undone_ops: dict[OpId, Operation] = {}
        self._undone_anchor: tuple[int, TransactionId | None] | None = None
        """Der Dokumentstand, an dem der Redo-Stapel entstand — siehe
        :meth:`_drop_stale_undone`."""
        self._reseed()

    # --- Lesen -----------------------------------------------------------------

    @property
    def operations(self) -> tuple[Operation, ...]:
        """Der aktive Stapel in Op-Reihenfolge — die lineare Sicht auf den DAG."""
        return tuple(sorted(self.document.ops, key=lambda entry: entry.id))

    @property
    def transactions(self) -> tuple[Transaction, ...]:
        return tuple(self.document.transactions)

    @property
    def can_undo(self) -> bool:
        return bool(self.document.transactions)

    @property
    def can_redo(self) -> bool:
        self._drop_stale_undone()
        return bool(self._undone)

    @property
    def discardable(self) -> int:
        """Transaktionen, die die nächste Änderung wegwerfen würde (§15.4)."""
        self._drop_stale_undone()
        return len(self._undone)

    @property
    def undone(self) -> tuple[Transaction, ...]:
        """Was zurückgenommen wurde, jüngste zuletzt — für den Verlauf.

        Der zeigte nur den aktuellen Stand; ob es noch etwas
        wiederherzustellen gab, verriet allein der Zustand des Menüeintrags.
        """
        self._drop_stale_undone()
        return tuple(self._undone)

    def operation(self, op_id: OpId) -> Operation:
        for entry in self.document.ops:
            if entry.id == op_id:
                return entry
        raise ValidationError(
            field="op",
            detail=_("Diese Operation gibt es im Verlauf nicht."),
            values={"op": op_id},
        )

    def transaction_of(self, op_id: OpId) -> Transaction | None:
        for transaction in self.document.transactions:
            if op_id in transaction.ops:
                return transaction
        return None

    # --- Schreiben -------------------------------------------------------------

    def apply(
        self,
        title: TranslatableText | str,
        drafts: Sequence[OperationDraft] = (),
        origin: Origin = USER_ORIGIN,
        changes: DocumentChange | ChangeFn | None = None,
        bundle: bool = False,
    ) -> Transaction:
        """Fügt Operationen als eine Transaktion an und gibt sie zurück.

        Geprüft wird alles, bevor irgendetwas geschrieben ist — ein
        abgelehnter Aufruf lässt das Dokument exakt, wie es war.

        ``changes`` trägt, was keine Operation ist (§15.5): Parameter,
        Passungen, Drucker, Material. Eine Transaktion darf daraus allein
        bestehen — eine gedrehte Zahl ist eine Änderung am Projekt, auch wenn
        kein Schritt dazukommt, und ohne Transaktion wäre sie nicht
        rücknehmbar.

        **Auch eine Funktion.** Manche Änderung hängt an dem, was die
        Operationen erst hervorbringen: Ein Schnitt legt ein Passungspaar an,
        und das benennt die Körper, die es beim Aufruf noch nicht gibt. Wer
        die Passungen deshalb nach dem Aufruf ins Dokument schreibt, schreibt
        an der Transaktion vorbei — ein Undo nimmt sie dann nicht zurück, ein
        Redo bringt sie nicht wieder. Eine Funktion bekommt die geplanten
        Operationen und liefert die Änderung, und beides bleibt ein Schritt.
        """
        # §2 C: jede Dokumentänderung braucht die Freischaltung — hier, weil
        # keine Dokumentänderung an dieser Funktion vorbeikommt (H3).
        activation.require(activation.CHANGE)

        # **Der Bündelversuch steht vor der Planung**, nicht danach: Gelingt
        # er, entsteht keine neue Operation, und die Kennungen bleiben, wie
        # sie sind. Wer erst plant und dann verwirft, hat die Zähler schon
        # weitergedreht — und ein Verlauf, dessen Kennungen Lücken haben,
        # sieht aus, als sei etwas verloren gegangen.
        if bundle and changes is None:
            merged = self._bundle_into_last(drafts)
            if merged is not None:
                return merged
        if not drafts and changes is None:
            raise ValidationError(
                field="ops",
                detail=_("Eine Transaktion ohne Operationen und ohne Änderungen ändert nichts."),
                constraint="empty",
            )

        # Die Kennungen kommen aus dem Dokument, nicht aus dem Gedächtnis
        # dieses Objekts — die Begründung steht bei :meth:`_reseed`.
        self._reseed()
        known = self._known_objects()
        planned: list[Operation] = []
        for draft in drafts:
            planned.append(self._plan(draft, known))
            known.difference_update(set(planned[-1].inputs) - set(planned[-1].outputs))
            known.update(planned[-1].outputs)

        # Jetzt stehen die Ausgabekennungen fest, und erst jetzt lässt sich
        # eine Änderung bilden, die sie benennt.
        settled = changes(planned) if callable(changes) else changes

        self._forget_undone()
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=title,
            ops=tuple(entry.id for entry in planned),
            origin=origin,
            changes=settled,
        )
        self.document.ops.extend(planned)
        self.document.transactions.append(transaction)
        # Der Anker zeigt auf das Bündel, das gerade offen ist — und nur ein
        # Zug, der eines eröffnet hat, darf später eines fortsetzen.
        self._open_bundle = transaction.id if bundle else None
        if settled is not None:
            self._settle(settled.after)
        else:
            self._record_numbering()
        return transaction

    def repair_and_retry(self, stopped_at: OpId) -> Transaction:
        """Repariert die Eingänge vor einem angehaltenen Schritt und plant neu.

        Ein bloß angehängtes ``repair`` kann nie helfen: Die Auswertung hält
        am fehlerhaften Schritt an und erreicht alles dahinter nicht. Deshalb
        wird der vollständige Suffix ab ``stopped_at`` ersetzt. Vor seine neu
        geplanten Fassungen kommt je lebendem Eingang genau eine Reparatur;
        alte und neue Fassung reisen in **einer** Transaktion, damit ein Undo
        den ganzen Zug und nur ihn zurücknimmt (§15.5, Regel 16).

        Die Ziele stammen ausschließlich aus der Operation. Eine Auswahl aus
        der Oberfläche gehört nicht zum Dokument und wäre nach dem Öffnen oder
        über den Agenten ein anderes Ergebnis (Regel 21).
        """
        activation.require(activation.CHANGE)
        operations = self.operations
        failed = self.operation(stopped_at)
        failed_index = next(
            index for index, entry in enumerate(operations) if entry.id == failed.id
        )
        prefix = operations[:failed_index]
        suffix = operations[failed_index:]

        living = _living_objects(prefix)
        targets = repair_targets(self.document, stopped_at, self._registry)
        # ``has`` zuerst, wie in :func:`repair_targets`: Eine Projektdatei kann
        # eine Operation nennen, die dieses Register nicht hat, und ``get``
        # antwortete darauf mit einem ``InternalError`` samt Fehlerbericht. Ohne
        # Eintrag ist ``targets`` ohnehin leer, und der Satz weiter unten sagt,
        # was hier nicht geht.
        if self._registry.has(failed.op) and self._registry.get(failed.op).requires_kind == "brep":
            raise ValidationError(
                field="in",
                detail=_("Dieses Werkzeug braucht einzeln bearbeitbare Flächen und Kanten."),
                constraint="repair_not_for_exact_body",
                values={"op": stopped_at},
                suggestions=(SHOW_STEP_VALUES, CANCEL),
                op_id=stopped_at,
            )
        declared_targets = tuple(dict.fromkeys(failed.inputs))
        missing = tuple(target for target in declared_targets if target not in living)
        if not targets or missing:
            raise ValidationError(
                field="in",
                detail=_(
                    "Dieser Schritt verwendet kein vorhandenes Modell, das Solidon reparieren kann."
                ),
                constraint="no_repair_target",
                values={"op": stopped_at, "missing": list(missing)},
                suggestions=(SHOW_STEP_VALUES, CANCEL),
                op_id=stopped_at,
            )

        # Erst vollständig planen, dann schreiben. Ein fehlerhafter jüngerer
        # Schritt lässt so weder einen halben Suffix noch eine Reparatur zurück.
        self._reseed()
        planned: list[Operation] = []
        for target in targets:
            repaired = self._plan(OperationDraft(op="repair", inputs=(target,)), living)
            planned.append(repaired)
            living.difference_update(set(repaired.inputs) - set(repaired.outputs))
            living.update(repaired.outputs)
        return self._retried_after(planned, suffix, living, REPAIR_AND_RETRY.label)

    def split_and_retry(self, stopped_at: OpId, target: ObjectId, count: int) -> Transaction:
        """Zerlegt einen Körper vor einem angehaltenen Schritt und plant neu.

        Dasselbe Muster wie :meth:`repair_and_retry`, mit *In Einzelteile
        zerlegen* statt der Reparatur: Der vollständige Suffix ab
        ``stopped_at`` wird ersetzt, davor kommt ``split_bodies`` auf
        ``target`` mit der Stückzahl ``count``, und alte wie neue Fassung
        reisen in **einer** Transaktion (§15.5, Regel 16). Der Anlass ist das
        Ausrichten, das einen Schriftzug als Ganzes auf kein Bett bekommt
        und seine Zerlegung vorschlägt (``prepare_ops._the_way_out_of``).

        **Wo der Körper stand, stehen danach seine Teile** — in jedem Schritt
        des Suffixes, der die ganze Szene nimmt (``takes_whole_scene``): Das
        Ausrichten und das Anordnen meinen das Bett, und das Bett trägt jetzt
        die Teile. Ihre Ausgänge werden dafür neu vergeben, denn bei diesen
        Operationen sind die Ausgänge die Eingänge. Jeder andere Schritt
        behält seine Eingänge: Die erste Kennung der Zerlegung ist die des
        Ausgangskörpers, und sie trägt danach dessen größtes Teil — genau
        wie nach einer von Hand eingefügten Zerlegung.
        """
        activation.require(activation.CHANGE)
        operations = self.operations
        failed = self.operation(stopped_at)
        failed_index = next(
            index for index, entry in enumerate(operations) if entry.id == failed.id
        )
        prefix = operations[:failed_index]
        suffix = operations[failed_index:]

        living = _living_objects(prefix)
        if target not in living:
            raise ValidationError(
                field="in",
                detail=_(
                    "Dieser Schritt verwendet kein vorhandenes Modell, das sich zerlegen ließe."
                ),
                constraint="no_split_target",
                values={"op": stopped_at, "missing": [target]},
                suggestions=(SHOW_STEP_VALUES, CANCEL),
                op_id=stopped_at,
            )

        self._reseed()
        split = self._plan(
            OperationDraft(op="split_bodies", inputs=(target,), params={"count": count}),
            living,
        )
        living.difference_update(set(split.inputs) - set(split.outputs))
        living.update(split.outputs)

        return self._retried_after(
            [split],
            suffix,
            living,
            SPLIT_AND_RETRY.label,
            redraft=lambda entry: self._with_replaced(entry, {target}, split.outputs),
        )

    def recount_and_retry(self, op_id: OpId, count: int) -> Transaction:
        """Setzt die Stückzahl eines Schritts auf die gemessene und plant neu.

        **Der Ausweg, wenn die Stückzahl nicht zu den Teilen passt** — nach
        einem Schriftwechsel, einem anderen Text, einer anderen Datei. §15.2
        verbietet das stille Nachrücken: ``change_params`` weist eine Zahl ab,
        die die Ausgänge ändert, solange ein späterer Schritt sie benutzt, und
        sagt „zurücknehmen und neu anwenden". Hier ist es der Klick auf den
        Vorschlag der Zerlegung selbst (``split_bodies``, Regel 17), und der
        tut genau das in einem Zug: der Schritt mit der neuen Zahl, seine
        Ausgänge erneuert, jeder spätere Schritt neu gefasst — die ganze Szene
        nimmt, was jetzt da ist; alte wie neue Fassung in einer Transaktion.

        **Die vorhandenen Kennungen bleiben.** Wächst die Zahl, kommen
        frische dazu; schrumpft sie, fallen die letzten weg — ein Schritt, der
        genau eine davon braucht, hält den Zug an (``_plan``: „nicht mehr da"),
        und geschrieben ist dann nichts.
        """
        activation.require(activation.CHANGE)
        entry = self.operation(op_id)
        spec = self._spec_of(entry)
        field_name = spec.produces_from
        if not field_name:
            raise InternalError(detail=f"{entry.op} has no piece count to change")
        operations = self.operations
        index = next(position for position, step in enumerate(operations) if step.id == entry.id)
        prefix = operations[:index]
        suffix = operations[index:]
        living = _living_objects(prefix)

        merged = {**entry.params, field_name: count}
        self._check_params(spec.name, spec.params.spec(), merged)
        self._reseed()
        keep = min(count, len(entry.outputs))
        outputs = (
            *entry.outputs[:keep],
            *(f"obj_{next(self._next_object)}" for _ in range(count - keep)),
        )
        gone = set(entry.outputs)

        def redraft(step: Operation) -> OperationDraft | None:
            if step.id == entry.id:
                return OperationDraft(
                    op=step.op, inputs=step.inputs, params=merged, outputs=outputs, seed=step.seed
                )
            return self._with_replaced(step, gone, outputs)

        return self._retried_after([], suffix, living, RECOUNT_AND_RETRY.label, redraft=redraft)

    def decimate_and_retry(
        self, stopped_at: OpId, triangles: int, values: Mapping[str, Any] | None = None
    ) -> Transaction:
        """Verringert die Eingänge vor einem angehaltenen Schritt und plant neu.

        Das vierte Geschwister von :meth:`repair_and_retry`, für ein Netz, das
        zum Teilen schon zu dicht ist (``mesh_ops._too_fine``): Der vollständige
        Suffix ab ``stopped_at`` wird ersetzt, davor kommt je lebendem Eingang
        *Dreiecke verringern* auf ``triangles`` — auf dem schnellen Weg, denn an
        genau dem hat der Kern nachgezählt, dass das Teilen danach geht
        (``mesh_ops._thinning``). Alte und neue Fassung reisen in **einer**
        Transaktion; ein Undo nimmt den ganzen Zug zurück (§15.5, Regel 16).

        Die Zahl stammt aus dem Befund (``values["decimate_to"]``), die Ziele
        aus der Operation — dieselbe Schranke wie bei der Reparatur
        (:func:`repair_targets`): lebende Eingänge, kein Schritt des exakten
        Kerns, dessen einzeln bearbeitbare Flächen das Verringern in Dreiecke
        verwandeln würde.

        ``values`` gibt dem Schritt dabei neue Werte — der Weg aus dem offenen
        Dialog, in dem der Kunde die Zahl gerade geändert hat und die Vorschau
        dieselbe Absage zeigt (RESTVERLAUF-04): Ändern und Verringern sind dort
        eine Handlung und ein Strg+Z.
        """
        activation.require(activation.CHANGE)
        if not repair_targets(self.document, stopped_at, self._registry):
            raise ValidationError(
                field="in",
                detail=_(
                    "Dieser Schritt verwendet kein vorhandenes Modell, dessen Dreiecke "
                    "Solidon verringern kann."
                ),
                constraint="no_decimate_target",
                values={"op": stopped_at},
                suggestions=(SHOW_STEP_VALUES, CANCEL),
                op_id=stopped_at,
            )
        return self._prepared_and_retried(
            stopped_at,
            "decimate_mesh",
            {"triangles": int(triangles), "method": "fast"},
            DECIMATE_AND_RETRY.label,
            values,
        )

    def remesh_and_retry(
        self, stopped_at: OpId, edge: float, values: Mapping[str, Any] | None = None
    ) -> Transaction:
        """Verfeinert die Eingänge vor einem angehaltenen Schritt und plant neu.

        Das Geschwister von :meth:`decimate_and_retry` in der Gegenrichtung, für
        ein Netz, das beim *Glätten* umschlägt, weil seine Dreiecke für die Wand
        zu grob sind: Vor den Suffix ab ``stopped_at`` kommt je lebendem Eingang
        *Kanten verfeinern* auf ``edge`` — die Länge, an der der Kern Verfeinern
        und Glätten durchgespielt hat (``values["remesh_to_mm"]``,
        ``mesh_ops._remeshing_for_smoothing``). Eine Transaktion, dieselbe
        Zielschranke wie die Reparatur.
        """
        activation.require(activation.CHANGE)
        if not repair_targets(self.document, stopped_at, self._registry):
            raise ValidationError(
                field="in",
                detail=_(
                    "Dieser Schritt verwendet kein vorhandenes Modell, dessen Kanten "
                    "Solidon verfeinern kann."
                ),
                constraint="no_remesh_target",
                values={"op": stopped_at},
                suggestions=(SHOW_STEP_VALUES, CANCEL),
                op_id=stopped_at,
            )
        return self._prepared_and_retried(
            stopped_at, "remesh_mesh", {"edge": float(edge)}, REMESH_AND_RETRY.label, values
        )

    def _prepared_and_retried(
        self,
        stopped_at: OpId,
        op: str,
        params: Mapping[str, Any],
        title: TranslatableText | str,
        values: Mapping[str, Any] | None,
    ) -> Transaction:
        """Ein Netzschritt je lebendem Eingang vor den Schritt ``stopped_at``, dann der Suffix neu.

        Der gemeinsame Weg von :meth:`decimate_and_retry` und
        :meth:`remesh_and_retry`; Lizenz und Ziele haben beide vorher geprüft,
        jede mit ihrem eigenen Satz. ``values`` ersetzt Werte des Schritts
        selbst in seiner neuen Fassung; geprüft wird wie beim Ändern
        (``_check_params``), bevor etwas geschrieben ist.
        """
        operations = self.operations
        failed = self.operation(stopped_at)
        failed_index = next(
            index for index, entry in enumerate(operations) if entry.id == failed.id
        )
        prefix = operations[:failed_index]
        suffix = operations[failed_index:]

        living = _living_objects(prefix)
        targets = repair_targets(self.document, stopped_at, self._registry)
        changed: dict[str, Any] | None = None
        if values:
            spec = self._spec_of(failed)
            self._check_params(spec.name, spec.params.spec(), values)
            changed = {**failed.params, **values}

        def redraft(entry: Operation) -> OperationDraft | None:
            """Der Schritt selbst mit den geänderten Werten, jeder andere unverändert."""
            if changed is None or entry.id != failed.id:
                return None
            return OperationDraft(
                op=entry.op,
                inputs=entry.inputs,
                params=changed,
                outputs=entry.outputs,
                seed=entry.seed,
            )

        # Erst vollständig planen, dann schreiben — ein ungültiger Wert hält
        # hier an (``_plan`` prüft die Grenzen der Operation), und geschrieben
        # ist dann nichts.
        self._reseed()
        planned: list[Operation] = []
        for target in targets:
            prepared = self._plan(
                OperationDraft(op=op, inputs=(target,), params=dict(params)),
                living,
            )
            planned.append(prepared)
            living.difference_update(set(prepared.inputs) - set(prepared.outputs))
            living.update(prepared.outputs)
        return self._retried_after(planned, suffix, living, title, redraft)

    def _with_replaced(
        self, step: Operation, gone: set[ObjectId], pieces: tuple[ObjectId, ...]
    ) -> OperationDraft | None:
        """Ein Schritt, der die ganze Szene nimmt, bekommt statt ``gone`` die ``pieces``.

        Nur für ``takes_whole_scene``: Ausrichten und Anordnen meinen das
        Bett, und das Bett trägt jetzt die Teile. Die Ausgänge werden dabei
        neu vergeben (``outputs=None``), denn bei diesen Operationen sind die
        Ausgänge die Eingänge. Jeder andere Schritt behält, was er hat —
        ``None`` heißt: unverändert klonen.
        """
        if not (gone & set(step.inputs)) or not self._registry.has(step.op):
            return None
        if not self._registry.get(step.op).takes_whole_scene:
            return None
        inputs = tuple(
            dict.fromkeys(
                piece for given in step.inputs for piece in (pieces if given in gone else (given,))
            )
        )
        return OperationDraft(
            op=step.op, inputs=inputs, params=step.params, outputs=None, seed=step.seed
        )

    def _retried_after(
        self,
        planned: list[Operation],
        suffix: Sequence[Operation],
        living: set[ObjectId],
        title: TranslatableText | str,
        redraft: Callable[[Operation], OperationDraft | None] = lambda entry: None,
    ) -> Transaction:
        """Den Suffix hinter ``planned`` neu fassen und alles als einen Zug schreiben.

        Der gemeinsame Schluss von :meth:`repair_and_retry`,
        :meth:`split_and_retry`, :meth:`recount_and_retry` und
        :meth:`decimate_and_retry`: Jeder Schritt
        des alten Suffixes bekommt eine neue Fassung mit denselben Werten,
        demselben Startwert und denselben Ein- und Ausgängen — oder die, die
        ``redraft`` für ihn nennt; Passungen, die an einem ersetzten Schritt
        hingen, werden umgebunden, und alte wie neue Fassung stehen in
        **einer** Transaktion.
        """
        replaced_ids: dict[OpId, OpId] = {}
        for entry in suffix:
            cloned = self._clone(entry, living, replaced_ids, redraft(entry))
            planned.append(cloned)
            replaced_ids[entry.id] = cloned.id

        old_versions = {entry.id: _copy_operation_matches(entry) for entry in suffix}
        rebound_fits = tuple(
            dataclasses.replace(
                fit,
                when_positive=(replaced_ids[fit.when_positive[0]], fit.when_positive[1]),
            )
            if fit.when_positive is not None and fit.when_positive[0] in replaced_ids
            else fit
            for fit in self.document.fits
        )
        fits_changed = rebound_fits != tuple(self.document.fits)
        changes = DocumentChange(
            before=DocumentState(
                edited_ops=old_versions,
                fits=tuple(self.document.fits) if fits_changed else None,
            ),
            after=DocumentState(
                edited_ops=dict.fromkeys(old_versions),
                fits=rebound_fits if fits_changed else None,
            ),
        )
        self._forget_undone()
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=title,
            ops=tuple(entry.id for entry in planned),
            changes=changes,
        )
        self.document.ops.extend(planned)
        self.document.transactions.append(transaction)
        self._settle(changes.after)
        return transaction

    def _bundle_into_last(self, drafts: Sequence[OperationDraft]) -> Transaction | None:
        """Die Züge in die vorige Transaktion aufnehmen — oder ``None``.

        **Ein Kunde, der ein Teil an seinen Platz schiebt, zieht selten
        einmal.** Er zieht, sieht nach, zieht nach — und hatte dafür einen
        Eintrag je Zug, für eine einzige Absicht. Ein Strg+Z nahm dann ein
        Drittel zurück (§15.5).

        Gebündelt wird eng: dieselben Operationen in derselben Reihenfolge,
        auf denselben Eingängen, mit demselben Anker, und nur wo eine
        Kumulationsregel steht (:mod:`app.core.scene.bundling`). Alles andere
        gibt ``None`` und wird ein eigener Schritt — ein Bündel zu wenig
        kostet einen Eintrag, ein Bündel zu viel verfälscht Geometrie.

        **Der Anker ist die erste Frage, nicht die Ähnlichkeit.** Aufgenommen
        wird nur in ein Bündel, das dieselbe Sitzung eröffnet hat und das noch
        offen ist (``_open_bundle``). Ohne ihn genügte ein gleichartiger
        letzter Schritt, und der kann von gestern sein: aus der geöffneten
        Datei, aus einem Dialog, oder aus einem Zweig, den ein Undo gerade
        beiseitegelegt hat — dann bliebe der Redo-Zweig stehen, weil gar keine
        neue Transaktion entstand.

        **Das Bündel endet von selbst.** Jede andere Handlung legt eine
        andere Transaktion an, und die passt beim nächsten Zug nicht mehr;
        eine andere Auswahl ändert die Eingänge. Nur der Werkzeugwechsel
        braucht eine Ansage, und die gibt :meth:`end_bundle`.
        """
        if not drafts or not self.document.transactions:
            return None
        last = self.document.transactions[-1]
        if last.id != self._open_bundle:
            return None
        if last.origin != USER_ORIGIN or last.changes is not None:
            return None
        if len(last.ops) != len(drafts):
            return None

        by_id = {entry.id: entry for entry in self.document.ops}
        planned: list[tuple[int, Operation]] = []
        for op_id, draft in zip(last.ops, drafts, strict=True):
            entry = by_id.get(op_id)
            if entry is None or entry.op != draft.op or entry.inputs != tuple(draft.inputs):
                return None
            merged = bundling.merge_params(entry.op, entry.params, draft.params)
            if merged is None:
                return None
            index = next(i for i, one in enumerate(self.document.ops) if one.id == op_id)
            planned.append((index, dataclasses.replace(entry, params=merged)))

        # Erst wenn **jeder** Zug passt, wird geschrieben. Ein halb gebündelter
        # Schritt wäre schlimmer als zwei ganze.
        for index, entry in planned:
            self.document.ops[index] = entry
        return last

    def end_bundle(self) -> None:
        """Das laufende Bündel schließen — der nächste Zug beginnt einen Schritt.

        Nötig, wo eine Handlung keine Transaktion anlegt und trotzdem eine
        ist: ein Werkzeugwechsel, das Schließen der Leiste. Ohne sie hinge ein
        Zug von morgen am Bündel von heute.
        """
        self._open_bundle = None

    def _plan(self, draft: OperationDraft, known: set[ObjectId]) -> Operation:
        spec = self._registry.get(draft.op)
        self._check_params(spec.name, spec.params.spec(), draft.params)

        missing = [entry for entry in draft.inputs if entry not in known]
        if missing:
            # Mit eigenem Titel und eigener Handlung: der Vorgabetitel der
            # ValidationError spricht von einem Wert außerhalb seines
            # Bereichs — hier ist kein Wert schuld, hier fehlt ein Körper,
            # und „Eingabe korrigieren" gäbe es nicht (Regel 17).
            raise ValidationError(
                title=_("Der gewählte Körper ist nicht mehr da."),
                field="in",
                detail=_("Die Operation verweist auf ein Objekt, das es nicht gibt."),
                constraint="unknown_object",
                values={"op": draft.op, "missing": missing},
                # `choose` ist bewusst nicht verdrahtet — der Kern fragt dafür
                # über `ctx.ask`, bevor er wirft. Hier wirft er vorher, also
                # blieb der Vorschlag ein Satz. Die Auswahl ändert man im
                # Objektbaum, und dafür gibt es jetzt einen Knopf.
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        # ``VARIABLE`` heißt: so viele, wie gewählt sind — die Booleschen
        # Operationen nehmen seit dem 06.09.2026 alle Körper auf einmal,
        # statt vier Laschen in vier Schritten anzuschweißen.
        expected = needed_inputs(spec)
        fixed = spec.consumes != VARIABLE and not spec.takes_whole_scene
        if len(draft.inputs) < expected or (fixed and len(draft.inputs) != expected):
            raise ValidationError(
                field="in",
                detail=_("Die Operation erwartet eine andere Anzahl an Objekten."),
                constraint="consumes",
                values={"op": draft.op, "expected": expected, "given": len(draft.inputs)},
                # Ohne eigene Vorschläge erbt die Ausnahme `(CORRECT_INPUT,
                # CANCEL)` — und *Eingabe korrigieren* öffnete einen Dialog auf
                # `field="in"`, also auf eine Zeile, die es nicht gibt.
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        # §11.3: eine randomisierte Prozedur führt einen gespeicherten
        # Startwert. Wo der Aufrufer keinen mitbringt, wird hier einer gezogen —
        # entscheidend ist, dass er aufgehoben wird, nicht, wer ihn sich
        # ausgedacht hat.
        seed = draft.seed
        if seed is None and spec.requires_seed:
            seed = secrets.randbelow(2**31)

        outputs = draft.outputs if draft.outputs is not None else self._outputs_for(spec, draft)
        if draft.outputs is not None:
            # Vorgegebene Kennungen sind gerechnete: Ein Vorschlag bringt die
            # mit, die seine Arbeitskopie vergab. Eine, die hier schon jemand
            # trägt, darf kein zweites Mal ins Dokument — sonst legt die
            # Auswertung das Ergebnis über einen fremden Körper.
            taken = [entry for entry in outputs if entry not in draft.inputs and entry in known]
            if taken:
                raise ValidationError(
                    field="out",
                    detail=_("Die Operation will eine Kennung vergeben, die es schon gibt."),
                    constraint="output_taken",
                    values={"op": draft.op, "taken": taken},
                    suggestions=(CANCEL,),
                )
        return Operation(
            id=next(self._next_op),
            op=draft.op,
            inputs=tuple(draft.inputs),
            outputs=tuple(outputs),
            params=dict(draft.params),
            seed=seed,
        )

    def record_solvers(self, solvers: Mapping[OpId, Any]) -> None:
        """Schreibt die Rückfallstufe, die jede Operation getragen hat, in den
        Stapel (§17.2).

        Die Auswertung ist eine reine Funktion und fasst das Dokument nicht an;
        hier werden ihre Befunde über die Solverstufen aufgehoben.

        Ein Vermerk, keine Anweisung: die Auswertung liest ihn nie zurück. Dass
        eine wieder geöffnete Datei gleich rechnet, liegt daran, dass die Kette
        bei gleichen Eingaben und gespeichertem Startwert deterministisch ist
        (§11.3) — dieser Eintrag lässt den Bericht hinterher sagen, was die
        Zahlen wert sind, und wird überschrieben, sobald ein Lauf eine andere
        Stufe erreicht. Darum braucht ein geänderter Parameter hier auch
        nichts: der nächste Lauf schreibt die Stufe, die seine eigene
        Geometrie erreicht hat.
        """
        if not solvers:
            return
        for index, entry in enumerate(self.document.ops):
            solver = solvers.get(entry.id)
            if solver is not None and entry.solver != solver:
                self.document.ops[index] = dataclasses.replace(entry, solver=solver)

    def record_answers(self, answers: Mapping[OpId, Mapping[str, Any]]) -> bool:
        """Schreibt die Antworten auf Rückfragen in den Stapel (§15.7).

        **Der Unterschied zu** :meth:`record_solvers` **ist die Richtung.** Eine
        Rückfallstufe ist ein Vermerk, den die Auswertung nie zurückliest; eine
        Antwort ist eine Anweisung. Wird sie nicht geschrieben, stellt die
        nächste Auswertung dieselbe Frage — gemessen 99 modale Fenster für 7
        Entscheidungen —, und sobald ein Cache länger lebt als die Sitzung,
        stellt sie sie irgendwann *nicht* mehr und rät stillschweigend
        (Regel 21).

        **Keine eigene Transaktion, und das ist eine Entscheidung.** Eine
        Antwort ist keine neue Handlung, sondern der Abschluss der einen, die
        gefragt hat. Als Transaktion nähme ein Undo sie zurück, die Frage käme
        wieder, und der Verlauf füllte sich mit Einträgen, die keine Handlung
        beschreiben. Das Dokument gilt danach als geändert — es gehört
        gespeichert —, aber es entsteht kein Schritt zum Zurücknehmen.

        Der Rückgabewert sagt, ob sich etwas geändert hat: Danach ist der
        Operations-Hash der fragenden Operation ein anderer, und der Zweig
        darunter rechnet einmal neu. Einmal je Frage, und danach nie wieder.
        """
        if not answers:
            return False
        changed = False
        for index, entry in enumerate(self.document.ops):
            given = answers.get(entry.id)
            if not given:
                continue
            merged = {**entry.params, **given}
            if merged == entry.params:
                continue
            self.document.ops[index] = dataclasses.replace(entry, params=merged)
            changed = True
        return changed

    def record_matches(self, matches: Mapping[OpId, Mapping[str, Any]]) -> bool:
        """Schreibt die Antworten der **Zuordnung** in den Stapel (§15.7, §21.3).

        **Der Unterschied zu** :meth:`record_answers` **ist der Fragesteller,
        nicht die Richtung.** Was eine Operation erfragt, ist eine Eingabe und
        gehört in ihre Parameter — die Einheitenrückfrage von ``load`` ist der
        Fall (§17.1). Was die Zuordnung entscheidet, ist keine Eingabe: Das
        Schema der Operation kennt den Schlüssel nicht, und ``validate`` wiese
        ihn zu Recht ab. Es steht deshalb in einem eigenen Feld neben ``seed``.

        **Kein neuer Hash, und das ist der wichtige Unterschied.** Eine Antwort
        in den Parametern ändert den Operations-Hash, und der Zweig darunter
        rechnet einmal neu — richtig so, denn die Einheit ändert das Ergebnis.
        Eine Zuordnungsantwort ändert es nicht: ``_with_features`` läuft
        *nach* dem Cache, in beiden Zweigen, auch nach einem Treffer. Wer
        ``matches`` „zur Sicherheit" in den Hash einträgt, macht aus jeder
        beantworteten Frage eine vollständige Neuberechnung des Zweigs.

        Wie bei :meth:`record_answers` entsteht **keine Transaktion**: Eine
        Antwort ist keine neue Handlung, sondern der Abschluss der einen, die
        gefragt hat. Das Dokument gilt danach als geändert und gehört
        gespeichert — sonst stünde die Antwort im Stapel, der Titel zeigte kein
        ``*``, und beim Schließen wäre sie weg.

        Ganze Gruppeneinträge werden ersetzt und tief kopiert, keine einzelnen
        Entscheidungen zusammengeführt. Undo und Redo sichern die Antwort
        zusätzlich an der gerade verlassenen Grenze derselben Op-Fassung.
        """
        if not matches:
            return False
        changed = False
        for index, entry in enumerate(self.document.ops):
            given = matches.get(entry.id)
            if not given:
                continue
            merged = {**entry.matches, **given}
            if merged == dict(entry.matches):
                continue
            self.document.ops[index] = dataclasses.replace(entry, matches=deepcopy(merged))
            changed = True
        return changed

    def reopen_recognition(self, object_ids: Collection[ObjectId]) -> bool:
        """Nimmt die gespeicherte Erkennungswahl geladener Körper zurück (§21.1).

        Die Wahl gehört dem Körper und steht an dem Ladeschritt, der ihn
        ausgibt — gefunden wird sie dort, gleich an welchem Schritt der Befund
        stand, der den Knopf trug. Die nächste Auswertung stellt die Frage vor
        der langen Vollerkennung wieder, mit Zeitschätzung und Speicherbedarf;
        was dann gewählt wird, schreibt :meth:`record_matches` fest. Ohne
        diesen Weg war eine Absage eine Sackgasse bis zum Neuladen der Datei.

        **Keine Transaktion und keine Lizenzgrenze**, aus demselben Grund wie
        bei :meth:`record_matches`: Die Wahl ist keine Handlung am Teil,
        sondern die Antwort auf eine Frage der Auswertung, und die Geometrie
        ändert sich nicht. Gibt zurück, ob eine Wahl dastand.
        """
        wanted = {recognition_answer_key(object_id) for object_id in object_ids}
        changed = False
        for index in _answering_load_steps(self.document, wanted):
            entry = self.document.ops[index]
            remaining = {
                name: record for name, record in entry.matches.items() if name not in wanted
            }
            self.document.ops[index] = dataclasses.replace(entry, matches=deepcopy(remaining))
            changed = True
        return changed

    def _spec_of(self, entry: Operation) -> Any:
        """Der Registereintrag eines **bestehenden** Schritts — oder ein Satz.

        **``Registry.get`` wirft ``InternalError``, und für einen Aufruf aus
        dem Code ist das richtig.** Hier kommt der Name aber aus dem geladenen
        Stapel, also aus einer Datei: eine Operation, die es in dieser Fassung
        nicht (mehr) gibt. Das ist ein Zustand, mit dem zu rechnen war, und
        kein Programmfehler.

        Gefunden am 26.08.2026 als Zwilling desselben Fehlers in
        ``scene/evaluate.py`` — und dieser hier ist der schwerere: Der Befund
        von dort schickt den Kunden mit *Verlauf zeigen* genau hierher. Wer
        den Schritt dann anklickt, um seine Werte zu sehen, bekäme einen
        Programmfehler-Dialog. **Ein Handlungsvorschlag, der in einen
        Programmfehler führt, ist schlimmer als gar keiner.**

        Der Vorschlag daneben ist deshalb keine Vertröstung: Die Werte des
        Schritts sind da — bei einer Datei aus 0.1.3 ist das der
        OpenSCAD-Quelltext, den jemand geschrieben hat.
        """
        if not self._registry.has(entry.op):
            raise UserError(
                title=_("Diesen Schritt kann Solidon nicht ändern."),
                detail=_(
                    "Der Schritt ist in dieser Fassung nicht bekannt. Seine Werte "
                    "bleiben erhalten; alles andere im Projekt lässt sich weiter "
                    "ändern."
                ),
                values={"operation": entry.op},
                op_id=entry.id,
                suggestions=(SHOW_STEP_VALUES, CANCEL),
            )
        return self._registry.get(entry.op)

    def change_params(self, op_id: OpId, params: Mapping[str, Any]) -> Operation:
        """Gibt einer Operation des Stapels andere Parameter (§15.4, §11).

        Genau das macht den Stapel zum Stapel statt zu einer Liste von Dingen,
        die passiert sind: eine Bohrung zwei Millimeter weiter links ist
        dieselbe Operation mit einer anderen Zahl, kein Schritt zum
        Zurücknehmen und Neu-Tun. Das Neurechnen folgt aus dem Hash — nur der
        Zweig unter der geänderten Operation wird neu gerechnet, der Rest
        kommt aus dem Cache (§15).

        Zurückgenommene Transaktionen fliegen raus, genau wie beim Anwenden von
        etwas Neuem: Verzweigungen gibt es nicht (§15.4), und ein Redo auf
        einen geänderten Stapel wäre eine Verzweigung unter anderem Namen.

        Abgelehnt wird eine Änderung, die ändert, *wie viele* Objekte die
        Operation erzeugt, solange eine spätere sie noch benutzt. Die IDs der
        neuen Ausgaben sind nicht die alten — die späteren Operationen zeigten
        auf Körper, die es nicht mehr gibt. Und ein Fehler am fernen Ende des
        Stapels, über eine Zahl, die jemand am nahen Ende geändert hat, ist die
        Sorte Fehler, die niemand mit dem verbindet, was er getan hat.
        """
        # Die Lizenzgrenze wie bei ``apply``: Diese Methode schreibt ins
        # Dokument, gehört also zu den Stellen, die selbst holen und selbst
        # werfen (kern.md). Ohne sie blieb nach Ablauf der Demo jeder Schritt
        # umparametrierbar und speicherbar — das Projekt vollständig
        # umkonstruierbar an einer geschlossenen Grenze vorbei.
        activation.require(activation.CHANGE)
        entry = self.operation(op_id)
        spec = self._spec_of(entry)
        self._check_params(spec.name, spec.params.spec(), params)

        # Auch hier werden Kennungen vergeben — eine Operation mit variabler
        # Ausgabe bekommt neue Objekte, sobald die Zahl sich ändert. Also
        # dieselbe Ausrichtung wie vor jeder Transaktion (:meth:`_reseed`).
        self._reseed()
        merged = {**entry.params, **params}
        draft = OperationDraft(op=entry.op, inputs=entry.inputs, params=merged)
        outputs = self._outputs_for(spec, draft) if spec.produces_from else entry.outputs
        # **Dieselbe Zahl heißt nicht dieselben Körper.** Eine Auswahl aus
        # einer Baugruppe (``step_bodies``) kann bei gleicher Zahl andere
        # Körper nennen; die Kennungen blieben dann, und ein späterer Schritt
        # an ``obj_3`` träfe still einen anderen Körper. Ändert sich der Wert,
        # der die Ausgänge nennt, gilt deshalb dieselbe Hürde wie bei einer
        # anderen Zahl.
        members_changed = False
        if spec.produces_from:
            declared = next(
                (item for item in spec.params.spec() if item.name == spec.produces_from), None
            )
            default = declared.default if declared is not None else None
            members_changed = draft.params.get(spec.produces_from, default) != entry.params.get(
                spec.produces_from, default
            )
        if len(outputs) != len(entry.outputs) or members_changed:
            used = self._later_users(op_id, entry.outputs)
            if used and len(outputs) != len(entry.outputs):
                raise ValidationError(
                    field=spec.produces_from or "params",
                    detail=_(
                        "Diese Änderung ändert die Anzahl der Objekte, und spätere "
                        "Operationen arbeiten damit. Dafür die Operation zurücknehmen "
                        "und neu anwenden."
                    ),
                    constraint="count_in_use",
                    values={"op": entry.op, "used_by": sorted(used)},
                )
            if used:
                raise ValidationError(
                    field=spec.produces_from or "params",
                    detail=_(
                        "Diese Änderung tauscht Körper aus, mit denen spätere Operationen "
                        "arbeiten. Dafür die Operation zurücknehmen und neu anwenden."
                    ),
                    constraint="members_in_use",
                    values={"op": entry.op, "used_by": sorted(used)},
                )
        if len(outputs) == len(entry.outputs):
            outputs = entry.outputs

        changed = dataclasses.replace(entry, params=dict(merged), outputs=tuple(outputs))
        _log.info("changed parameters of op %s (%s)", op_id, entry.op)
        return self._swap_operation(spec.title, entry, changed)

    def change_inputs(self, op_id: OpId, inputs: Sequence[ObjectId]) -> Operation:
        """Gibt einem Schritt andere Objekte, auf denen er arbeitet (§15.4).

        **Der zweite Fall von „Eingabe korrigieren", und er ist kein Wert.**
        Eine Operation, deren *Parameter* nicht gehen, öffnet ihren Dialog; eine,
        die auf den falschen oder auf gar keinen Körper zeigt, hat nichts
        aufzuklappen — ``field="in"`` ist keine Zeile im Formular. Was hilft,
        ist eine andere Auswahl, und die trifft man im Objektbaum und nicht in
        einem Dialog.

        Ersetzt wird der Schritt, statt einen zweiten anzulegen: dieselbe
        Zusicherung wie bei :meth:`change_params` und
        :meth:`change_kernel` — jeder Wert bleibt nachträglich änderbar, und der
        Verlauf wächst dabei nicht.

        Geprüft wird beides, was schiefgehen kann: dass die Objekte überhaupt da
        sind, und dass es so viele sind, wie die Operation nimmt. Beide Fälle
        werfen dieselbe Ausnahme wie beim Anlegen, damit die Oberfläche sie
        nicht zweimal verstehen muss.
        """
        activation.require(activation.CHANGE)  # schreibt ins Dokument (kern.md)
        entry = self.operation(op_id)
        spec = self._spec_of(entry)
        # Entscheidend ist der Zustand vor diesem Schritt: Seine bisherigen
        # Eingänge dürfen verbraucht sein, spätere Ausgänge existieren hier nicht.
        known = self._known_objects(before=entry.id)
        missing = [name for name in inputs if name not in known]
        if missing:
            raise ValidationError(
                title=_("Der gewählte Körper ist nicht mehr da."),
                field="in",
                detail=_("Die Operation verweist auf ein Objekt, das es nicht gibt."),
                constraint="unknown_object",
                values={"op": entry.op, "missing": missing},
                suggestions=(CHANGE_SELECTION, CANCEL),
            )
        expected = needed_inputs(spec)
        fixed = spec.consumes != VARIABLE and not spec.takes_whole_scene
        if len(inputs) < expected or (fixed and len(inputs) != expected):
            raise ValidationError(
                field="in",
                detail=_("Die Operation erwartet eine andere Anzahl an Objekten."),
                constraint="consumes",
                values={"op": entry.op, "expected": expected, "given": len(inputs)},
                suggestions=(CHANGE_SELECTION, CANCEL),
            )

        changed = dataclasses.replace(
            entry, inputs=tuple(inputs), outputs=_outputs_following(entry, inputs)
        )
        _log.info("changed inputs of op %s (%s) to %s", op_id, entry.op, list(inputs))
        return self._swap_operation(spec.title, entry, changed)

    def change_kernel(self, op_id: OpId, op_name: str, params: Mapping[str, Any]) -> Operation:
        """Stellt einen Schritt auf seinen Zwilling um — denselben Schritt im
        anderen Rechenkern (§15.4, ``MENU_TWINS``).

        Die Oberfläche behandelt die beiden Kerne seit je als **eine**
        Handlung: ein Menüeintrag, ein Dialog. Bis P2.8 entschied ein Haken
        darin; seither entsteht ein Grundkörper exakt, und dieser Tausch steht
        im Kontextmenü des Verlaufs — für die Quader, die vor P2.8 ohne Haken
        angelegt wurden und sonst endgültig Netze blieben.

        **Nur Zwillinge.** Beliebige Operationen im Verlauf gegeneinander zu
        tauschen wäre kein Bearbeiten mehr, sondern ein Umschreiben der
        Geschichte: Ein Schritt trägt Eingänge und Ausgänge, und was ihn
        ersetzen darf, muss dieselben haben. ``MENU_TWINS`` ist genau die
        Liste der Paare, für die das gilt und die die Oberfläche ohnehin schon
        als eines behandelt.

        Die Parameter kommen gefiltert an — der exakte Quader kennt kein
        ``anchor``. Was danach passiert, entscheidet die Auswertung: Ein
        späterer Schritt, der mit der neuen Art nicht kann, hält die Kette an
        und sagt das. Rücknehmbar ist der Tausch wie jeder andere Schritt.
        """
        from app.core.registry import MENU_TWINS, exact_names

        activation.require(activation.CHANGE)  # schreibt ins Dokument (kern.md)
        entry = self.operation(op_id)
        if op_name != entry.op:
            pairs = {(hidden, shown) for hidden, shown in MENU_TWINS.items()}
            if (op_name, entry.op) not in pairs and (entry.op, op_name) not in pairs:
                raise ValidationError(
                    field="op",
                    detail=_(
                        "Diese beiden Operationen sind kein Paar — ein Schritt im Verlauf "
                        "lässt sich nur auf seinen Zwilling umstellen."
                    ),
                    constraint="not_a_twin",
                    values={"op": entry.op, "wanted": op_name},
                )

        spec = self._registry.get(op_name)
        # **Ins Netz nur, wenn niemand darüber den exakten Körper braucht** (P2.8).
        # Bis dahin sagte das ein Hinweis am Haken; jetzt ist es die Hürde des
        # Kerns, damit Verlauf, Palette und Agent dieselbe Absage bekommen — mit
        # der Zahl der Schritte, die anhalten würden (Regel 17).
        exact = exact_names()
        if entry.op in exact and op_name not in exact:
            # Ein Schritt, den diese Fassung nicht kennt, braucht nichts — er
            # rechnet ohnehin nicht (``evaluate.unknown_operation``). Ihn im
            # Register nachzuschlagen war ein ``InternalError`` statt des
            # Wechsels (Durchsicht 0.5.0).
            later = [
                other
                for other in self.operations
                if other.id > op_id
                and self._registry.has(other.op)
                and self._registry.get(other.op).requires_kind == "brep"
            ]
            if later:
                raise ValidationError(
                    field="op",
                    detail=_(
                        "Schritte darüber brauchen echte Flächen und Kanten. Ändern Sie "
                        "diese zuerst oder lassen Sie den Schritt exakt."
                    ),
                    constraint="needs_exact",
                    values={"op": entry.op, "wanted": op_name, "count": len(later)},
                    suggestions=(CANCEL,),
                )
        self._check_params(spec.name, spec.params.spec(), params)
        # **Nicht** mit den alten verschmelzen, anders als ``change_params``:
        # Die beiden Schemata sind verschieden, und ein ``anchor`` aus dem
        # Netz-Quader wäre am exakten ein unbekannter Parameter.
        changed = dataclasses.replace(entry, op=op_name, params=dict(params))
        _log.info("switched op %s from %s to %s", op_id, entry.op, op_name)
        return self._swap_operation(spec.title, entry, changed)

    def removal_closure(self, op_ids: Sequence[OpId]) -> tuple[OpId, ...]:
        """Die gewählten Schritte samt späteren, die ohne sie unerfüllbar wären.

        Gleiche Kennungen dürfen weiterleben: Wird etwa eine Bohrung aus einer
        Kette genommen, steht ihr Eingangskörper noch unter derselben Kennung
        da, und spätere Verschiebungen bleiben gültig. Erzeugt der gelöschte
        Schritt dagegen einen neuen Körper, müssen dessen spätere Nutzer mit
        hinaus. Unabhängige Zweige bleiben stehen.

        Diese Vorschau ist lesend. Die Oberfläche zeigt damit vor der
        Bestätigung ehrlich, ob außer der Auswahl noch etwas betroffen ist.
        """
        selected = {int(op_id) for op_id in op_ids}
        if not selected:
            return ()
        for op_id in selected:
            self.operation(op_id)

        removed = set(selected)
        living: set[ObjectId] = set()
        for entry in self.operations:
            if entry.id in removed:
                continue
            if any(object_id not in living for object_id in entry.inputs):
                removed.add(entry.id)
                continue
            living.difference_update(set(entry.inputs) - set(entry.outputs))
            living.update(entry.outputs)
        return tuple(sorted(removed))

    def remove_operations(self, op_ids: Sequence[OpId]) -> Transaction:
        """Entfernt Schritte als eine vollständig rücknehmbare Transaktion.

        Die ursprünglichen Transaktionen bleiben als Geschichte erhalten; die
        neue Transaktion trägt auf ihrer Vorher-Seite die vollständigen
        Operationen und auf ihrer Nachher-Seite ``None``. Dadurch überlebt
        nicht nur das Löschen das Speichern, sondern auch sein Undo.

        Wenn spätere Operationen frische Ausgaben der Auswahl brauchen, werden
        sie in derselben Transaktion mitgenommen. Eine halbe Kette mit
        verschwundenen Eingängen ist kein zulässiger Dokumentzustand (§15.2).
        """
        activation.require(activation.CHANGE)
        removed_ids = self.removal_closure(op_ids)
        if not removed_ids:
            raise ValidationError(
                field="ops",
                detail=_("Zum Löschen ist kein Schritt ausgewählt."),
                constraint="empty",
            )

        versions = {op_id: _copy_operation_matches(self.operation(op_id)) for op_id in removed_ids}
        removed_set = set(removed_ids)
        # **Nach Kennungen, nicht nach dem, was gerade rechnet** (P7.3): Eine
        # Passung an einem Körper, den ein ausgeschalteter Schritt anlegt, ruht
        # nur — sie geht erst, wenn dieser Schritt selbst gelöscht wird.
        disappeared = _structural_objects(self.operations) - _structural_objects(
            [entry for entry in self.operations if entry.id not in removed_set]
        )
        remaining_fits = tuple(
            fit
            for fit in self.document.fits
            if fit.a.object_id not in disappeared
            and fit.b.object_id not in disappeared
            and (fit.when_positive is None or fit.when_positive[0] not in removed_set)
        )
        fits_changed = len(remaining_fits) != len(self.document.fits)
        self._reseed()
        self._forget_undone()
        changes = DocumentChange(
            before=DocumentState(
                fits=tuple(self.document.fits) if fits_changed else None,
                edited_ops=versions,
            ),
            after=DocumentState(
                fits=remaining_fits if fits_changed else None,
                edited_ops=dict.fromkeys(removed_ids),
            ),
        )
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=_deletion_title(versions, self._registry),
            ops=(),
            changes=changes,
        )
        self.document.transactions.append(transaction)
        self._settle(changes.after)
        _log.info("removed operation(s) %s", list(removed_ids))
        return transaction

    def _swap_operation(
        self, title: TranslatableText | str, entry: Operation, changed: Operation
    ) -> Operation:
        """Ersetzt einen Schritt als Transaktion mit beiden Fassungen (§15.5).

        Die drei Änderungswege — Parameter, Eingänge, Rechenkern — schrieben
        am Verlauf vorbei ins Dokument: Der alte Stand war unwiederbringlich
        weg, und Strg+Z nahm stattdessen die letzte Transaktion, also einen
        anderen Schritt (Gesamtreview-b, Bericht 01, Szene 5; kern.md: am
        Dokument wird nie vorbei geschrieben). Jetzt trägt eine Transaktion
        ohne eigene Operationen beide Fassungen (``DocumentState.edited_ops``),
        und ``restore`` legt sie in beide Richtungen zurück — dieselbe
        Mechanik wie für Parameter und Passungen, denn es ist dieselbe Zusage.

        Der Verlauf wächst dabei um keinen Schritt (§15.4): Die Operation
        behält Kennung und Platz, nur ihre Fassung wechselt. Was wächst, ist
        die Liste der Transaktionen, und genau die trägt das Undo. Als Titel
        steht der Titel des Schritts — die Transaktion **ist** seine neue
        Fassung, kein eigener Text ohne Katalognachzug.
        """
        _transaction, (swapped,) = self._swap_operations(title, ((entry, changed),))
        return swapped

    def _swap_operations(
        self,
        title: TranslatableText | str,
        pairs: Sequence[tuple[Operation, Operation]],
    ) -> tuple[Transaction, tuple[Operation, ...]]:
        """Wie :meth:`_swap_operation`, für mehrere Schritte in **einer**
        Transaktion — ein Strg+Z legt alle zurück (Regel 16, §15.5)."""
        swapped = tuple(
            _copy_operation_matches(
                changed, previous_outputs=entry.outputs, previous_inputs=entry.inputs
            )
            for entry, changed in pairs
        )
        self._reseed()
        self._forget_undone()
        changes = DocumentChange(
            before=DocumentState(
                edited_ops={entry.id: _copy_operation_matches(entry) for entry, _changed in pairs}
            ),
            after=DocumentState(
                edited_ops={changed.id: _copy_operation_matches(changed) for changed in swapped}
            ),
        )
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=title,
            ops=(),
            changes=changes,
        )
        self.document.transactions.append(transaction)
        self._settle(changes.after)
        return transaction, swapped

    def use_part_states(self, states: Mapping[str, str]) -> Transaction | None:
        """Rechnet benutzte Bausteine mit einem anderen Stand desselben
        Bausteins (§24.4, RM-138).

        ``states`` nennt je Baustein im Stapel den Katalogeintrag, der ab
        jetzt rechnen soll — beim Öffnen der gespeicherte Stand eines eigenen
        Rezepts, den die Projektdatei mitgebracht hat
        (``knowledge.parts.check.saved_states``). Jeder Schritt behält
        Kennung, Platz, Eingänge und Werte; nur der Baustein dahinter wechselt.

        **Eine Transaktion für alle Schritte.** Ein Projekt setzt denselben
        Baustein oft mehrfach ein, und ein halb umgestelltes Projekt rechnete
        mit zwei Ständen nebeneinander. Ein Strg+Z führt vollständig zum
        aktuellen Stand zurück.

        ``None``, wenn kein Schritt einen der genannten Bausteine benutzt.
        """
        activation.require(activation.CHANGE)  # schreibt ins Dokument (kern.md)
        pairs: list[tuple[Operation, Operation]] = []
        for entry in self.operations:
            target = _part_state_target(entry.op, states)
            if target is None:
                continue
            if not self._registry.has(target):
                raise ValidationError(
                    field="op",
                    detail=_("Dieser Stand des Bausteins ist hier nicht verfügbar."),
                    constraint="part_state_missing",
                    values={"op": entry.op, "wanted": target},
                    suggestions=(CANCEL,),
                )
            spec = self._registry.get(target)
            self._check_params(spec.name, spec.params.spec(), entry.params)
            pairs.append((entry, dataclasses.replace(entry, op=target)))
        if not pairs:
            return None
        transaction, _swapped = self._swap_operations(_("Gespeicherten Stand verwenden"), pairs)
        _log.info("switched %d part steps to another state", len(pairs))
        return transaction

    # --- Umbau des Verlaufs (P7) -------------------------------------------------

    def _clone(
        self,
        entry: Operation,
        living: set[ObjectId],
        renumbered: Mapping[OpId, OpId],
        draft: OperationDraft | None = None,
    ) -> Operation:
        """Einen Schritt unter neuer Kennung neu fassen — dieselben Werte, dieselben Körper.

        Der gemeinsame Baustein von :meth:`_retried_after` und dem Umbau des
        Verlaufs. Startwert, Übersetzungsvermerk, Antworten und Unterdrückung
        reisen mit; die Solverauskunft nicht, sie gehört dem nächsten Lauf.
        Ein Schritt, den dieses Register nicht kennt, wird wörtlich übernommen
        — er rechnet ohnehin nicht (``evaluate.unknown_operation``), und ihn im
        Register nachzuschlagen war ein ``InternalError`` statt eines Umbaus.
        """
        suppressed = _renumbered_suppression(entry.suppressed, renumbered)
        if not self._registry.has(entry.op):
            for name in entry.inputs:
                if name not in living:
                    raise ValidationError(
                        title=_("Der gewählte Körper ist nicht mehr da."),
                        field="in",
                        detail=_("Die Operation verweist auf ein Objekt, das es nicht gibt."),
                        constraint="unknown_object",
                        values={"op": entry.op, "missing": [name]},
                        suggestions=(CHANGE_SELECTION, CANCEL),
                    )
            cloned = dataclasses.replace(
                entry, id=next(self._next_op), solver=None, suppressed=suppressed
            )
        else:
            planned = self._plan(
                draft
                or OperationDraft(
                    op=entry.op,
                    inputs=entry.inputs,
                    params=entry.params,
                    outputs=entry.outputs,
                    seed=entry.seed,
                ),
                living,
            )
            cloned = dataclasses.replace(
                planned,
                solver=None,
                translatable=entry.translatable,
                matches=entry.matches,
                suppressed=suppressed,
            )
        cloned = _copy_operation_matches(
            cloned, previous_outputs=entry.outputs, previous_inputs=entry.inputs
        )
        living.difference_update(set(cloned.inputs) - set(cloned.outputs))
        living.update(cloned.outputs)
        return cloned

    def _revision_mark(self) -> tuple[Any, ...]:
        """Woran sich zeigt, dass seit dem Planen etwas geschehen ist.

        Die Transaktionen fangen jede Handlung, die Schrittfassungen auch das,
        was ohne Transaktion geschrieben wird — eine festgehaltene Antwort
        (``record_answers``, ``record_matches``) ändert, was ein neu gefasster
        Schritt mitnehmen müsste. Die Solverauskunft nicht: Sie ist ein
        Vermerk, den der nächste Lauf ohnehin neu schreibt.
        """
        transactions = self.document.transactions
        return (
            len(transactions),
            transactions[-1].id if transactions else None,
            tuple(
                (
                    entry.id,
                    entry.op,
                    entry.inputs,
                    entry.outputs,
                    entry.params,
                    entry.seed,
                    entry.translatable,
                    entry.matches,
                    entry.suppressed,
                )
                for entry in self.operations
            ),
            tuple(self.document.fits),
        )

    def _chosen(self, op_ids: Sequence[OpId]) -> tuple[OpId, ...]:
        """Die gewählten Schritte, aufsteigend, jeder einmal — und jeder vorhanden."""
        chosen = tuple(sorted({int(op_id) for op_id in op_ids}))
        if not chosen:
            raise ValidationError(
                field="ops",
                detail=_("Dafür ist kein Schritt ausgewählt."),
                constraint="empty",
                suggestions=(CANCEL,),
            )
        for op_id in chosen:
            self.operation(op_id)
        return chosen

    def _revision_changes(
        self,
        replaced: Sequence[Operation],
        renumbered: Mapping[OpId, OpId],
        extra: DocumentChange | None,
    ) -> DocumentChange:
        """Beide Seiten eines Neuplanens: alte Fassungen zurück, neue Kennungen gebunden.

        Dieselbe Buchführung wie :meth:`_retried_after` — die alten Fassungen
        stehen vorn, ihre Entfernung hinten, bedingte Passungen folgen ihrem
        Schritt auf die neue Kennung (§14). ``extra`` bringt mit, was der
        eingefügte Schritt selbst ändert (benannte Maße, Passungen); es darf
        keine Schrittfassungen tragen.
        """
        if extra is not None and (
            extra.before.edited_ops is not None or extra.after.edited_ops is not None
        ):
            raise InternalError(detail="an inserted step cannot carry step versions of its own")
        old_versions = {entry.id: _copy_operation_matches(entry) for entry in replaced}
        current = tuple(self.document.fits)
        wanted = (
            tuple(extra.after.fits)
            if extra is not None and extra.after.fits is not None
            else current
        )
        rebound = tuple(
            dataclasses.replace(
                fit, when_positive=(renumbered[fit.when_positive[0]], fit.when_positive[1])
            )
            if fit.when_positive is not None and fit.when_positive[0] in renumbered
            else fit
            for fit in wanted
        )
        fits_changed = rebound != current
        before = extra.before if extra is not None else DocumentState()
        after = extra.after if extra is not None else DocumentState()
        return DocumentChange(
            before=dataclasses.replace(
                before, edited_ops=old_versions, fits=current if fits_changed else None
            ),
            after=dataclasses.replace(
                after,
                edited_ops=dict.fromkeys(old_versions),
                fits=rebound if fits_changed else None,
            ),
        )

    def commit(self, plan: RevisionPlan) -> Transaction:
        """Schreibt einen geplanten Umbau — genau diesen, als **eine** Transaktion.

        Nur, wenn sich das Dokument seit dem Planen nicht bewegt hat: Der Plan
        trägt die alten Fassungen, die ein Undo zurücklegt, und neue
        Kennungen, die über der damaligen Wasserlinie liegen. Ein veralteter
        Plan wird abgewiesen und nichts geschrieben.
        """
        activation.require(activation.CHANGE)
        if plan.mark != self._revision_mark():
            raise UserError(
                title=_("Der Verlauf hat sich inzwischen geändert."),
                detail=_("Die Änderung wurde nicht übernommen. Versuchen Sie es noch einmal."),
                suggestions=(CANCEL,),
            )
        changes = plan.transaction.changes
        if changes is None:
            raise InternalError(detail="a revision plan carries no document change")
        self._forget_undone()
        self._open_bundle = None
        self.document.ops.extend(plan.planned)
        self.document.transactions.append(plan.transaction)
        self._settle(changes.after)
        _log.info("revised the history (%s) with %d step(s)", plan.kind, len(plan.transaction.ops))
        return plan.transaction

    def plan_insert(
        self,
        before: OpId,
        title: TranslatableText | str,
        drafts: Sequence[OperationDraft],
        origin: Origin = USER_ORIGIN,
        changes: DocumentChange | ChangeFn | None = None,
    ) -> RevisionPlan:
        """Neue Schritte **vor** ``before`` einfügen — geplant, nicht geschrieben (P7.1).

        Die Eingaben lösen gegen den Stand unmittelbar vor ``before`` auf:
        Nur was dort lebt, darf ein neuer Schritt nehmen, und ein Körper, den
        erst ein späterer Schritt anlegt, ist hier „nicht mehr da". Danach
        wird die ganze Folge ab ``before`` mit neuen Kennungen neu gefasst —
        dieselben Werte, dieselben Körper, dieselben Startwerte —, denn die
        Reihenfolge des Stapels ist die seiner Kennungen (§15). ``changes``
        reist in derselben Transaktion (benannte Maße, Passungen eines
        Ablaufs): ein Strg+Z nimmt alles zurück und legt die alte Folge mit
        ihren alten Kennungen wieder hin.

        Verbraucht ein neuer Schritt einen Körper, den ein späterer noch
        braucht, gibt es die Stelle nicht — das sagt die Absage, bevor
        irgendetwas gerechnet wird.
        """
        activation.require(activation.CHANGE)
        if not drafts:
            raise ValidationError(
                field="ops",
                detail=_("Zum Einfügen fehlt ein Schritt."),
                constraint="empty",
                suggestions=(CANCEL,),
            )
        mark = self._revision_mark()
        operations = self.operations
        index = self._position_of(before)
        prefix, suffix = operations[:index], operations[index:]
        self._reseed()
        active = _living_objects(prefix)
        structural = _structural_objects(prefix)
        planned: list[Operation] = []
        for draft in drafts:
            entry = self._plan(draft, active)
            planned.append(entry)
            for living in (active, structural):
                living.difference_update(set(entry.inputs) - set(entry.outputs))
                living.update(entry.outputs)
        settled = changes(planned) if callable(changes) else changes
        subjects = tuple(entry.id for entry in planned)
        renumbered: dict[OpId, OpId] = {}
        for entry in suffix:
            try:
                cloned = self._clone(entry, structural, renumbered)
            except ValidationError as problem:
                if problem.constraint != "unknown_object":
                    raise
                raise UserError(
                    title=_("Hier lässt sich der Schritt nicht einfügen."),
                    detail=_(
                        "Er verbraucht einen Körper, den Schritt {number} danach noch braucht.",
                        number=entry.id,
                    ),
                    values={"number": entry.id, "missing": ", ".join(entry.inputs)},
                    op_id=entry.id,
                    suggestions=(CANCEL,),
                ) from problem
            planned.append(cloned)
            renumbered[entry.id] = cloned.id
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=_("Eingefügt: {step}", step=title),
            ops=tuple(entry.id for entry in planned),
            origin=origin,
            changes=self._revision_changes(suffix, renumbered, settled),
            revision="insert",
        )
        return RevisionPlan(
            kind="insert",
            transaction=transaction,
            planned=tuple(planned),
            renumbered=renumbered,
            subjects=subjects,
            mark=mark,
        )

    def _position_of(self, op_id: OpId) -> int:
        """Die Stelle eines Schritts im Stapel — oder der Satz, dass es ihn nicht gibt."""
        found = self.operation(op_id)
        return next(index for index, entry in enumerate(self.operations) if entry.id == found.id)

    def valid_targets(
        self, op_ids: Sequence[OpId], dependencies: Dependencies | None = None
    ) -> tuple[MoveTarget, ...]:
        """Jede Stelle, an die die gewählten Schritte könnten — mit dem Grund, wo nicht (P7.2).

        Für die Oberfläche beim Ziehen und im Kontextmenü: gültige Stellen
        zeigen, ungültige mit ihrem Satz. Stellen, an denen sich nichts
        bewegte, fehlen. Nur lesend und ohne Rechnung — was die Geometrie
        danach sagt, klärt die isolierte Auswertung.
        """
        chosen = self._chosen(op_ids)
        operations = self.operations
        needs = dependencies.needs if dependencies is not None else ()
        targets: list[MoveTarget] = []
        for before in (*(entry.id for entry in operations if entry.id not in chosen), None):
            order = _moved_order(operations, chosen, before)
            if [entry.id for entry in order] == [entry.id for entry in operations]:
                continue
            targets.append(MoveTarget(before, _order_problem(order, needs, self._registry)))
        return tuple(targets)

    def plan_move(
        self,
        op_ids: Sequence[OpId],
        before: OpId | None,
        dependencies: Dependencies | None = None,
    ) -> RevisionPlan:
        """Die gewählten Schritte vor ``before`` setzen (``None``: ans Ende) — geplant (P7.2).

        Mehrere Schritte wandern gemeinsam und in ihrer Folge. Vorher geprüft,
        ohne zu rechnen: Jeder Schritt findet seinen Körper, keiner steht vor
        dem, der ihn anlegt oder verbraucht, und keiner vor dem Schritt, dessen
        Merkmal er braucht (``dependencies``). Ein Vorwärtsbezug wird nicht
        umgebogen, sondern abgesagt, mit beiden Schritten im Satz. Neu gefasst
        wird die Folge ab der ersten Stelle, die sich ändert.
        """
        activation.require(activation.CHANGE)
        chosen = self._chosen(op_ids)
        if before is not None:
            self.operation(before)
        mark = self._revision_mark()
        operations = self.operations
        order = _moved_order(operations, chosen, before)
        first = next(
            (
                index
                for index, (old, new) in enumerate(zip(operations, order, strict=True))
                if old.id != new.id
            ),
            None,
        )
        if first is None:
            raise ValidationError(
                field="before",
                detail=_("An dieser Stelle steht der Schritt schon."),
                constraint="unchanged",
                suggestions=(CANCEL,),
            )
        problem = _order_problem(
            order, dependencies.needs if dependencies is not None else (), self._registry
        )
        if problem is not None:
            raise problem
        self._reseed()
        structural = _structural_objects(operations[:first])
        planned: list[Operation] = []
        renumbered: dict[OpId, OpId] = {}
        for entry in order[first:]:
            cloned = self._clone(entry, structural, renumbered)
            planned.append(cloned)
            renumbered[entry.id] = cloned.id
        versions = {entry.id: entry for entry in operations}
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=_steps_title(
                [versions[op_id] for op_id in chosen],
                self._registry,
                one=lambda step: _("Verschoben: {step}", step=step),
                few=lambda count, steps: _(
                    "{count} Schritte verschoben: {steps}", count=count, steps=steps
                ),
                many=lambda count, steps, rest: _(
                    "{count} Schritte verschoben: {steps} und {rest} weitere",
                    count=count,
                    steps=steps,
                    rest=rest,
                ),
            ),
            ops=tuple(entry.id for entry in planned),
            changes=self._revision_changes(operations[first:], renumbered, None),
            revision="move",
        )
        return RevisionPlan(
            kind="move",
            transaction=transaction,
            planned=tuple(planned),
            renumbered=renumbered,
            subjects=chosen,
            mark=mark,
        )

    def _off_closure(
        self,
        chosen: Collection[OpId],
        dependencies: Dependencies | None,
    ) -> tuple[set[OpId], dict[ObjectId, OpId]]:
        """Welche Schritte ruhen, wenn ``chosen`` aus ist — und welcher Körper wem fehlt.

        Der Reihe nach, denn wer etwas braucht, steht hinter dem, der es
        anlegt: Ein Schritt ruht mit, wenn er einen Körper nimmt, den ein
        ruhender frisch anlegt, oder ein Merkmal braucht, das in einem
        ruhenden entsteht — aus den Sichtungen eines Laufs
        (``Dependencies.needs``) oder, bei einem schon ruhenden, aus seinem
        eigenen Vermerk (``Suppression.expects``). Ein Schritt über die ganze
        Szene (Anordnen, Ausrichten) ruht nie wegen eines Körpers: Er nimmt,
        was auf dem Bett steht (``evaluate._without_absent_inputs``).
        """
        off = set(chosen)
        absent: dict[ObjectId, OpId] = {}
        needs: dict[OpId, set[OpId]] = {}
        for need in dependencies.needs if dependencies is not None else ():
            needs.setdefault(need.step, set()).add(need.on)
        for entry in self.operations:
            if entry.id not in off:
                wanted = set(needs.get(entry.id, ()))
                if entry.suppressed is not None:
                    wanted.update(
                        expected.creator
                        for expected in entry.suppressed.expects
                        if expected.creator is not None
                    )
                gone = [name for name in entry.inputs if name in absent]
                # Ein Schritt über das ganze Bett ruht nie wegen eines Körpers:
                # Er nimmt, was dort steht (``evaluate._without_absent_inputs``).
                whole = (
                    self._registry.has(entry.op)
                    and self._registry.get(entry.op).takes_whole_scene
                    and entry.outputs == entry.inputs
                )
                if (gone and not whole) or wanted & off:
                    off.add(entry.id)
            if entry.id in off:
                for output in entry.outputs:
                    if output not in entry.inputs:
                        absent.setdefault(output, entry.id)
        return off, absent

    def _fit_pauses(
        self,
        off: Collection[OpId],
        absent: Mapping[ObjectId, OpId],
        dependencies: Dependencies | None,
    ) -> dict[OpId, list[str]]:
        """Welche Passung mit welchem ruhenden Schritt ruht (§14, P7.3).

        Eine Passung ruht, wenn einer ihrer Körper nicht entsteht oder ihr
        Merkmal in einem ruhenden Schritt entsteht. Vermerkt wird sie an genau
        diesem Schritt — geht er wieder an, prüft sie wieder.
        """
        pauses: dict[OpId, list[str]] = {}
        fit_needs = dependencies.fit_needs if dependencies is not None else {}
        for fit in self.document.fits:
            holder = next(
                (
                    absent[reference.object_id]
                    for reference in (fit.a, fit.b)
                    if reference.object_id in absent
                ),
                None,
            )
            if holder is None:
                holder = next(
                    (op_id for op_id in sorted(fit_needs.get(fit.name, ())) if op_id in off),
                    None,
                )
            if holder is not None:
                pauses.setdefault(holder, []).append(fit.name)
        return pauses

    def plan_suppress(
        self,
        op_ids: Sequence[OpId],
        dependencies: Dependencies | None = None,
        *,
        also: Collection[OpId] = (),
        paused: Mapping[OpId, Sequence[str]] | None = None,
    ) -> RevisionPlan:
        """Die gewählten Schritte ausschalten — samt dem, was ohne sie nicht rechnen kann (P7.3).

        Nichts wird gelöscht und nichts ersetzt: Die Schritte bleiben mit
        ihren Werten im Verlauf und in der Datei, nur rechnen sie nicht.
        Mitgenommen wird, wer einen Körper braucht, den ein ausgeschalteter
        anlegt, oder ein Merkmal, das in ihm entsteht; beides steht danach
        ausdrücklich im Dokument (``Suppression.chosen=False``). Behält ein
        Schritt die Kennung seines Körpers, rechnen spätere auf dem Zustand
        davor weiter — wie beim Löschen (§15.4). Passungen an einem Körper
        oder Merkmal, das nicht entsteht, ruhen mit. Projektparameter bleiben
        unberührt. Eine Transaktion, rücknehmbar, keine Nachfrage (Regel 19).

        ``also`` und ``paused`` bringt die isolierte Auswertung mit
        (``scene.revision``): Schritte und Passungen, deren Merkmal nach dem
        Ausschalten verloren ist, ohne dass ein Lauf vorher sagen konnte,
        woher es kam.
        """
        activation.require(activation.CHANGE)
        chosen = self._chosen(op_ids)
        mark = self._revision_mark()
        versions = {entry.id: entry for entry in self.operations}
        if all(
            versions[op_id].suppressed is not None and versions[op_id].suppressed.chosen  # type: ignore[union-attr]
            for op_id in chosen
        ):
            raise ValidationError(
                field="ops",
                detail=_("Dieser Schritt ist schon ausgeschaltet."),
                constraint="already_off",
                suggestions=(CANCEL,),
            )
        resting = {op_id for op_id, entry in versions.items() if entry.suppressed is not None}
        off, absent = self._off_closure(resting | set(chosen) | set(also), dependencies)
        pauses = self._fit_pauses(off, absent, dependencies)
        for op_id, names in (paused or {}).items():
            pauses.setdefault(op_id, []).extend(name for name in names if name not in pauses[op_id])
        expectations = dependencies.expectations if dependencies is not None else {}
        fit_expectations = dependencies.fit_expectations if dependencies is not None else {}
        before: dict[OpId, Operation | None] = {}
        after: dict[OpId, Operation | None] = {}
        carried: list[OpId] = []
        for op_id in sorted(off):
            entry = versions[op_id]
            current = entry.suppressed
            fits = tuple(
                dict.fromkeys((*(current.fits if current else ()), *pauses.get(op_id, ())))
            )
            expects = (
                current.expects if current is not None else tuple(expectations.get(op_id, ()))
            ) + tuple(
                expected
                for name in fits
                if current is None or name not in current.fits
                for expected in fit_expectations.get(name, ())
            )
            wanted = Suppression(
                chosen=op_id in chosen or (current is not None and current.chosen),
                expects=expects,
                fits=fits,
            )
            if wanted == current:
                continue
            if current is None and op_id not in chosen:
                carried.append(op_id)
            before[op_id] = _copy_operation_matches(entry)
            after[op_id] = _copy_operation_matches(dataclasses.replace(entry, suppressed=wanted))
        self._reseed()
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=_steps_title(
                [versions[op_id] for op_id in chosen],
                self._registry,
                one=lambda step: _("Ausgeschaltet: {step}", step=step),
                few=lambda count, steps: _(
                    "{count} Schritte ausgeschaltet: {steps}", count=count, steps=steps
                ),
                many=lambda count, steps, rest: _(
                    "{count} Schritte ausgeschaltet: {steps} und {rest} weitere",
                    count=count,
                    steps=steps,
                    rest=rest,
                ),
            ),
            ops=(),
            changes=DocumentChange(
                before=DocumentState(edited_ops=before), after=DocumentState(edited_ops=after)
            ),
            revision="suppress",
        )
        return RevisionPlan(
            kind="suppress",
            transaction=transaction,
            subjects=chosen,
            carried=tuple(carried),
            mark=mark,
        )

    def plan_reactivate(
        self, op_ids: Sequence[OpId], dependencies: Dependencies | None = None
    ) -> RevisionPlan:
        """Ausgeschaltete Schritte wieder einschalten — samt dem, was sie brauchen (P7.3).

        Ein mitgenommener Schritt geht mit dem an, der ihn mitnahm: Wer ihn
        allein wählt, holt dessen Wahl mit zurück, denn ohne sie rechnete er
        nicht. Ein gewählter geht mit allem an, was nur seinetwegen ruhte;
        was aus einem anderen Grund ruht, bleibt aus. Ob die Verweise danach
        dasselbe Merkmal treffen wie vorher, prüft die isolierte Auswertung
        gegen den Vermerk jedes Schritts (``Suppression.expects``).
        """
        activation.require(activation.CHANGE)
        chosen = self._chosen(op_ids)
        mark = self._revision_mark()
        versions = {entry.id: entry for entry in self.operations}
        resting = {op_id: entry for op_id, entry in versions.items() if entry.suppressed}
        targets = [op_id for op_id in chosen if op_id in resting]
        if not targets:
            raise ValidationError(
                field="ops",
                detail=_("Dieser Schritt ist schon eingeschaltet."),
                constraint="already_on",
                suggestions=(CANCEL,),
            )
        roots = {op_id for op_id, entry in resting.items() if entry.suppressed.chosen}  # type: ignore[union-attr]
        freed: set[OpId] = set()
        for op_id in targets:
            if op_id in roots:
                freed.add(op_id)
            else:
                freed |= self._roots_of(op_id, roots, dependencies)
        off, absent = self._off_closure(roots - freed, dependencies)
        pauses = self._fit_pauses(off, absent, dependencies)
        before: dict[OpId, Operation | None] = {}
        after: dict[OpId, Operation | None] = {}
        brought: list[OpId] = []
        for op_id, entry in sorted(resting.items()):
            current = entry.suppressed
            assert current is not None
            if op_id not in off:
                wanted: Suppression | None = None
                if op_id not in chosen:
                    brought.append(op_id)
            else:
                wanted = dataclasses.replace(
                    current,
                    chosen=current.chosen and op_id not in freed,
                    fits=tuple(dict.fromkeys((*current.fits, *pauses.get(op_id, ())))),
                )
            if wanted == current:
                continue
            before[op_id] = _copy_operation_matches(entry)
            after[op_id] = _copy_operation_matches(dataclasses.replace(entry, suppressed=wanted))
        self._reseed()
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=_steps_title(
                [versions[op_id] for op_id in targets],
                self._registry,
                one=lambda step: _("Eingeschaltet: {step}", step=step),
                few=lambda count, steps: _(
                    "{count} Schritte eingeschaltet: {steps}", count=count, steps=steps
                ),
                many=lambda count, steps, rest: _(
                    "{count} Schritte eingeschaltet: {steps} und {rest} weitere",
                    count=count,
                    steps=steps,
                    rest=rest,
                ),
            ),
            ops=(),
            changes=DocumentChange(
                before=DocumentState(edited_ops=before), after=DocumentState(edited_ops=after)
            ),
            revision="reactivate",
        )
        return RevisionPlan(
            kind="reactivate",
            transaction=transaction,
            subjects=tuple(targets),
            carried=tuple(brought),
            mark=mark,
        )

    def _roots_of(
        self, op_id: OpId, roots: Collection[OpId], dependencies: Dependencies | None
    ) -> set[OpId]:
        """Die gewählten ausgeschalteten Schritte, ohne die ``op_id`` nicht rechnen kann.

        Gesucht wird rückwärts über dieselben Kanten wie beim Ausschalten: den
        Körper, den ein früherer frisch anlegt, und das Merkmal, das in ihm
        entsteht (Sichtung oder Vermerk). Was dabei auf einen gewählten
        ausgeschalteten Schritt trifft, muss mit an.
        """
        operations = self.operations
        creators: dict[ObjectId, OpId] = {}
        for entry in operations:
            for output in entry.outputs:
                if output not in entry.inputs:
                    creators.setdefault(output, entry.id)
        needs: dict[OpId, set[OpId]] = {}
        for need in dependencies.needs if dependencies is not None else ():
            needs.setdefault(need.step, set()).add(need.on)
        by_id = {entry.id: entry for entry in operations}
        found: set[OpId] = set()
        pending = [op_id]
        seen: set[OpId] = set()
        while pending:
            current = pending.pop()
            if current in seen or current not in by_id:
                continue
            seen.add(current)
            entry = by_id[current]
            ancestors = {creators[name] for name in entry.inputs if name in creators}
            ancestors |= needs.get(current, set())
            if entry.suppressed is not None:
                ancestors |= {
                    expected.creator
                    for expected in entry.suppressed.expects
                    if expected.creator is not None
                }
            for ancestor in ancestors:
                if ancestor == current or ancestor not in by_id:
                    continue
                if ancestor in roots:
                    found.add(ancestor)
                if by_id[ancestor].suppressed is not None:
                    pending.append(ancestor)
        return found

    def _later_users(self, op_id: OpId, objects: tuple[ObjectId, ...]) -> set[OpId]:
        """Operationen nach dieser, die eine ihrer Ausgaben nehmen."""
        wanted = set(objects)
        return {
            entry.id
            for entry in self.document.ops
            if entry.id > op_id and wanted.intersection(entry.inputs)
        }

    def _outputs_for(self, spec: Any, draft: OperationDraft) -> tuple[ObjectId, ...]:
        """Welche Kennungen ein Schritt zurückgibt — drei Regeln, nicht zwei.

        Gleiche Anzahl rein wie raus heißt: die Objekte bleiben sie selbst.
        Ungleiche Anzahl heißt **nicht** zwangsläufig frische Kennungen: Wo
        eine Operation ``keeps_inputs`` deklariert, behalten ihre ersten
        Ausgänge die Kennung der ersten Eingänge, und nur der Rest ist neu.
        Erst ohne diese Angabe wird alles frisch vergeben.

        Der Satz hat hier bis zum 27.08.2026 gefehlt, und er hat gefehlt, als
        er gebraucht wurde: ``way_four`` in ``make_examples.py`` rechnete
        nach ``blend_union`` (zwei rein, eins raus) mit einer frischen
        Kennung und verwies auf ``obj_3`` — die gab es nie, denn die sechs
        Operationen mit ``keeps_inputs`` heben die Wasserlinie nicht. Der
        Paketbau von 0.2.1 scheiterte daran auf allen vier Plattformen.

        Die Begründung für ``keeps_inputs`` steht unten am Zweig, der sie
        umsetzt; hier steht, **dass** es sie gibt — denn wer diese Frage hat,
        liest zuerst den Docstring.
        """
        if spec.produces == VARIABLE and spec.produces_from:
            # Die Eingänge bleiben sie selbst, neu sind nur die Ausgänge
            # darüber hinaus. Beide Operationen dieser Art — *Objekt
            # duplizieren* und *Kopien in Reihe oder Kreis* — geben an erster
            # Stelle ihr unverändertes Original zurück; wer auch dafür eine
            # frische Kennung vergibt, lässt die Auswertung den Eingang
            # wegräumen, denn der steht dann nicht mehr unter den Ausgaben.
            # Der Nutzer sah daraufhin nicht zwei Körper, sondern einen, und
            # jede weitere Handlung auf seine Auswahl endete in „Der gewählte
            # Körper ist nicht mehr da" — dieselbe Kennung, die er angeklickt
            # hatte, gab es nach dem Duplizieren nicht mehr.
            stated = self._stated(spec, draft, spec.produces_from)
            kept = tuple(draft.inputs)[:stated]
            fresh = (f"obj_{next(self._next_object)}" for _ in range(stated - len(kept)))
            return kept + tuple(fresh)
        if spec.produces == VARIABLE and not draft.inputs:
            if spec.takes_whole_scene:
                # Anordnen und Kollisionsprüfung nehmen die ganze Szene und
                # geben sie zurück. Ohne Eingaben ist das nichts — und ein
                # geplanter Ausgang, den die Operation nicht liefert, hält die
                # **ganze** Auswertung an: alles nach diesem Schritt wird nicht
                # mehr gerechnet. Das Fenster reicht über ``inputs_for`` immer
                # die Szene herein, über Kommandozeile, Agent und MCP ist der
                # Aufruf ohne sie einen Tippfehler entfernt.
                return ()
            # Nimmt nichts und macht eine unbekannte Anzahl: wie viele, kann
            # nur der Aufrufer wissen, und eins ist die ehrliche Vorgabe für
            # eine schlichte Datei.
            return tuple(f"obj_{next(self._next_object)}" for _ in range(draft.produces or 1))
        if spec.produces == VARIABLE or (spec.produces == spec.consumes and draft.inputs):
            return tuple(draft.inputs)
        # Wo eine Operation ihre ersten Ausgänge als **Fortsetzung** ihrer
        # ersten Eingänge deklariert, behalten die ihre Kennung
        # (``keeps_inputs``). Ohne das bekam der Körper, den der Nutzer beim
        # Vereinigen zuerst angeklickt hatte, eine frische — obwohl der
        # Registertext ihm zusagt, er bleibe „mit seinem Namen und Material".
        # Teuer war daran nicht die tote Auswahl, sondern dass die Merkmale
        # des Vorgängers an der alten Kennung hängen: Sie wurden neu vergeben,
        # und ``hole_1`` zeigte danach auf ein anderes Loch (§21.2).
        keep = min(int(getattr(spec, "keeps_inputs", 0)), len(draft.inputs), spec.produces)
        kept = tuple(draft.inputs)[:keep]
        fresh = (f"obj_{next(self._next_object)}" for _ in range(spec.produces - keep))
        return kept + tuple(fresh)

    def _stated(self, spec: Any, draft: OperationDraft, field_name: str) -> int:
        """Die Ausgabezahl, die eine Operation in einen ihrer Parameter
        geschrieben hat.

        Eine nackte Zahl, denn die IDs werden hier vergeben, und ein Ausdruck
        (§13) löst sich erst beim Rechnen der Szene auf. Eine Anzahl, die erst
        berechnet werden müsste, hieße: der Stapel kann nicht sagen, wie viele
        Objekte ein Schritt macht — also wird sie mit genau diesem Satz
        abgelehnt statt geraten.

        Und gegen den deklarierten Bereich geprüft, hier und nicht erst beim
        Rechnen der Szene. Die IDs werden vorher vergeben: eine Stückzahl von
        fünf Millionen war in einer Sekunde fünf Millionen IDs im Dokument,
        und die deklarierte Grenze von hundert kam zu spät, um das zu stoppen.
        """
        declared = next((entry for entry in spec.params.spec() if entry.name == field_name), None)
        value = draft.params.get(field_name, declared.default if declared else 1)
        if declared is not None and declared.kind == "step_bodies":
            # Die Auswahl einer Baugruppe nennt ihre Körper, und ihre Zahl
            # ist die der Ausgänge. Der leere Text ist ein Körper — die
            # ganze Datei, wie vor P7.4 gelesen.
            return len(body_keys(value, field_name)) or 1
        if expressions.is_expression(value):
            raise ValidationError(
                field=field_name,
                detail=_("Eine Stückzahl muss eine Zahl sein, kein Ausdruck."),
                constraint="not_a_number",
                values={"op": spec.name, "value": str(value)},
            )
        try:
            count = int(value)
        except (TypeError, ValueError) as problem:
            raise ValidationError(
                field=field_name,
                detail=_("Eine Stückzahl muss eine Zahl sein, kein Ausdruck."),
                constraint="not_a_number",
                values={"op": spec.name, "value": str(value)},
            ) from problem

        low = int(declared.minimum) if declared and declared.minimum is not None else 1
        high = int(declared.maximum) if declared and declared.maximum is not None else None
        if count < low or (high is not None and count > high):
            raise ValidationError(
                field=field_name,
                detail=_("Diese Stückzahl liegt außerhalb des erlaubten Bereichs."),
                value=count,
                constraint="range",
                values={"op": spec.name, "minimum": low, "maximum": high},
            )
        # Zurück kommt die Zahl, die dasteht. Hier stand ein ``max(count, 1)``,
        # und das war eine zweite, stille Untergrenze neben der deklarierten:
        # Wer eines Tages ``minimum=0`` schreibt, bekäme eine Operation, die
        # eine Ausgabe erzeugt, obwohl ihr Schema keine verlangt. Was zulässig
        # ist, entscheidet das Schema — und die Zeile darüber setzt es durch.
        return count

    def _check_params(self, op_name: str, specs: Iterable[Any], params: Mapping[str, Any]) -> None:
        """Namen und Ausdruckssyntax. Werte werden nach dem Auflösen
        geprüft (§13)."""
        known = {entry.name for entry in specs}
        unknown = sorted(set(params) - known)
        if unknown:
            raise ValidationError(
                field=unknown[0],
                detail=_("Diesen Parameter gibt es bei dieser Operation nicht."),
                constraint="unknown",
                values={"op": op_name, "known": sorted(known)},
            )
        for value in params.values():
            if expressions.is_expression(value):
                expressions.check(value)

    # --- Undo und Redo ---------------------------------------------------------

    def _remember_version_matches(self, transaction: Transaction, *, after: bool) -> Transaction:
        """Sichert Antworten nur an der gerade verlassenen Grenze derselben Op-Fassung.

        Nach einer Auswertung kennt der lebende Stapel neuere Antworten als
        die gespeicherte Änderungsseite. Nur ihre Eingaben binden beide
        Fassungen; eine spätere Solvernotiz und die Antworten selbst nicht.
        """
        changes = transaction.changes
        if changes is None:
            return transaction
        state = changes.after if after else changes.before
        if state.edited_ops is None:
            return transaction
        current = {entry.id: entry for entry in self.document.ops}
        edited = dict(state.edited_ops)
        changed = False
        fields = ("id", "op", "inputs", "outputs", "params", "seed", "translatable", "suppressed")
        for op_id, stored in state.edited_ops.items():
            entry = current.get(op_id)
            if stored is None or entry is None:
                continue
            if any(getattr(stored, name) != getattr(entry, name) for name in fields):
                continue
            if stored.matches != entry.matches:
                edited[op_id] = dataclasses.replace(stored, matches=deepcopy(dict(entry.matches)))
                changed = True
        if not changed:
            return transaction
        remembered = dataclasses.replace(state, edited_ops=edited)
        changes = (
            dataclasses.replace(changes, after=remembered)
            if after
            else dataclasses.replace(changes, before=remembered)
        )
        return dataclasses.replace(transaction, changes=changes)

    def undo(self) -> Transaction | None:
        """Nimmt die letzte Transaktion als Ganzes zurück (§15.5).

        Als Ganzes heißt: mit dem, was keine Operation war. Solange das hier
        nur den Stapel leerte, ließ ein Undo die Parameter und Passungen eines
        Agentenvorschlags stehen — Regel 16 verlangt ihn vollständig zurück.
        """
        if not self.document.transactions:
            return None
        self._drop_stale_undone()
        # Ein Undo schließt jedes offene Bündel: Der nächste Zug ist eine neue
        # Absicht und darf den zurückgenommenen Zweig nicht stehen lassen.
        self._open_bundle = None
        transaction = self._remember_version_matches(self.document.transactions.pop(), after=True)
        remaining: list[Operation] = []
        for entry in self.document.ops:
            if entry.id in transaction.ops:
                self._undone_ops[entry.id] = _copy_operation_matches(entry)
            else:
                remaining.append(entry)
        self.document.ops[:] = remaining
        if transaction.changes is not None:
            restore(self.document, transaction.changes.before)
        self._undone.append(transaction)
        self._undone_anchor = self._document_mark()
        return transaction

    def redo(self) -> Transaction | None:
        self._drop_stale_undone()
        if not self._undone:
            return None
        self._open_bundle = None
        transaction = self._remember_version_matches(self._undone.pop(), after=False)
        for op_id in transaction.ops:
            self.document.ops.append(_copy_operation_matches(self._undone_ops.pop(op_id)))
        self.document.ops.sort(key=lambda entry: entry.id)
        self.document.transactions.append(transaction)
        if transaction.changes is not None:
            restore(self.document, transaction.changes.after)
        self._undone_anchor = self._document_mark()
        return transaction

    def withdraw(self, transaction_id: TransactionId) -> Transaction | None:
        """Nimmt die letzte Transaktion zurück, **ohne** sie für Strg+Y aufzuheben.

        Für eine Rücknahme, die kein Undo des Nutzers ist: Ein Import, dessen
        Datei sich als unlesbar erweist, war nie ein Schritt des Projekts
        (KUNDE-12). Sein Redo brächte einen Ladeschritt zurück, dessen Quelle
        schon wieder ausgetragen ist. Nur genau diese Transaktion, und nur,
        wenn sie noch die letzte ist — sonst ``None`` und nichts geändert.
        """
        transactions = self.document.transactions
        if not transactions or transactions[-1].id != transaction_id:
            return None
        transaction = self.undo()
        self._forget_undone()
        return transaction

    def _document_mark(self) -> tuple[int, TransactionId | None]:
        """Woran sich eine fremde Handlung erkennen lässt: Zahl und Kennung der
        letzten Transaktion im Dokument."""
        transactions = self.document.transactions
        return (len(transactions), transactions[-1].id if transactions else None)

    def _drop_stale_undone(self) -> None:
        """Ein Redo-Stapel gilt nur für den Dokumentstand, an dem er entstand.

        Trennen, Deckeln und Auto Split bauen sich eine **zweite** ``History``
        über demselben Dokument. Eine neue Handlung dort ließ den Redo-Stapel
        der Sitzungs-History stehen, und Strg+Y hängte danach die alte
        Transaktion hinter die neue — ``t1, t3, t2``, obwohl eine neue
        Handlung den zurückgenommenen Zweig verwirft (Gesamtreview
        05.09.2026, CORE-08). Hat sich das Dokument seit dem Undo bewegt, ist
        der Zweig weg — wie bei einer eigenen neuen Handlung auch.
        """
        if self._undone and self._document_mark() != self._undone_anchor:
            self._forget_undone()

    def _forget_undone(self) -> None:
        for transaction in self._undone:
            for op_id in transaction.ops:
                self._undone_ops.pop(op_id, None)
        self._undone.clear()

    # --- Bezeichner ------------------------------------------------------------

    def _known_objects(self, *, before: OpId | None = None) -> set[ObjectId]:
        """Die Objekte am Stapelende oder unmittelbar vor einem Schritt.

        Nicht jede je vergebene Nummer: was eine Vereinigung oder ein
        Entfernen verbraucht und nicht wieder ausgibt, ist weg. Dieselbe
        Rechnung führt die Auswertung, und sie hier zu wiederholen ist der
        Unterschied zwischen einer Operation, die beim Anlegen abgelehnt wird,
        und einem Fehler am fernen Ende der Kette über etwas, das jemand am
        nahen Ende getan hat (§15.2).
        """
        living: set[ObjectId] = set()
        for entry in self.operations:
            if before is not None and entry.id >= before:
                break
            if entry.suppressed is not None:
                # Was ein ausgeschalteter Schritt anlegen würde, gibt es nicht
                # (P7.3) — ein neuer Schritt darauf hielte beim Rechnen an.
                continue
            living.difference_update(set(entry.inputs) - set(entry.outputs))
            living.update(entry.outputs)
        return living

    def _reseed(self) -> None:
        """Die Zähler an dem ausrichten, was im Dokument steht.

        **Vor jeder Vergabe, nicht einmal im Konstruktor.** Ein Zähler, der
        sich beim Anlegen merkt, wo er anfängt, hält nur, solange dieses Objekt
        das einzige ist, das schreibt — und das ist es nicht. Die Sitzung hält
        ihre ``History`` über die ganze Projektlaufzeit; Trennen, Deckeln und
        Auto Split bauen sich eine eigene über demselben Dokument, weil sie
        Passungen nachtragen und die im Dokument leben und nicht im Stapel.

        Was dabei herauskam: Fünf gezeichnete Schnitte vergaben über ihre
        eigene ``History`` die Kennungen 163 bis 167. Die Sitzung stand
        weiterhin auf 163, und die nächste Operation über das Menü bekam 163
        ein zweites Mal. Die Auswertung sortiert nach Kennung (§15) — damit
        rutschte *Auf dem Bett anordnen* zwischen den ersten und den zweiten
        Schnitt, fand die Körper nicht, die es anordnen sollte, und hielt das
        ganze Dokument an. Im Fenster sah es aus, als habe das Anordnen die
        Teilung zerstört.

        Das Dokument ist die Quelle, nicht der Zähler. Neu ausgerichtet wird
        beim Anlegen und zu Beginn jeder Transaktion; innerhalb einer
        Transaktion zählen die Zähler weiter, denn ihre Operationen stehen
        noch nicht im Dokument.

        **Und „was im Dokument steht" ist mehr als sein Stapel**: Was schon
        vergeben, aber gerade zurückgenommen ist, steht in keinem Stapel und
        gehört trotzdem niemand anderem. Dafür führt das Dokument eine
        Wasserlinie mit, die jede Vergabe fortschreibt
        (:meth:`_record_numbering`).
        """
        self._next_op = itertools.count(self._highest_op_id() + 1)
        self._next_object = itertools.count(self._highest_object_index() + 1)
        self._next_transaction = itertools.count(self._highest_transaction_number() + 1)

    def _record_numbering(self) -> None:
        """Schreibt die vergebenen Nummern als Untergrenze ins Dokument (§15.4).

        **Der Bestand allein trägt nicht, und beide Lücken tun weh.**

        *Ein zweites Verlaufsobjekt* sieht den Redo-Stapel des ersten nicht:
        Trennen, Deckeln und Auto Split bauen sich eine eigene ``History``
        über demselben Dokument, und wer vorher Rückgängig gedrückt hat, bekam
        von ihr die zurückgenommene Nummer ein zweites Mal — ein Redo hängte
        danach eine Transaktion ein, deren Op-Kennung inzwischen einer anderen
        gehörte, und ``document.ops`` trug dieselbe Kennung doppelt.

        *Eine geschlossene Datei* hat gar keinen Redo-Stapel mehr. Der
        Chat-Beitrag, der auf die zurückgenommene Transaktion zeigt, steht
        trotzdem darin (``DocumentState`` deckt den Chat nicht) — die nächste
        Handlung bekam seine Kennung, und der Beitrag galt wieder als lebendig.

        Geschrieben wird erst, wenn alles andere geschrieben ist: Ein
        abgelehnter Aufruf lässt das Dokument exakt, wie es war — auch die
        Wasserlinie.
        """
        self.document.highest_transaction = self._highest_transaction_number()
        self.document.highest_op = self._highest_op_id()
        self.document.highest_object = self._highest_object_index()

    def _settle(self, state: DocumentState) -> None:
        """Wasserlinie, Änderungsseite zurücklegen, Wasserlinie — in dieser
        Reihenfolge (§15.4, §15.5).

        **Zweimal, weil beide Seiten Kennungen halten.** Vor dem Zurücklegen
        steht im Dokument die *alte* Fassung eines geänderten Schritts, danach
        die *neue*, und ``_highest_object_index`` liest immer nur, was gerade
        dasteht. Wer nur einmal schreibt, verliert die eine oder die andere
        Hälfte.

        Verloren ging bis zum 02.09.2026 die neue: ``_swap_operation`` schrieb
        die Wasserlinie vor dem ``restore``. Nach *Objekt duplizieren* mit
        Stückzahl 2, umgestellt auf 3, standen ``obj_3`` und ``obj_4`` im
        Stapel und die Wasserlinie weiter auf 2 — ein Rückgängig nahm die neue
        Fassung heraus, ein zweites Verlaufsobjekt über demselben Dokument
        vergab ``obj_3`` erneut, und nach dem Wiederherstellen war ``obj_3``
        die Ausgabe zweier Operationen. Die Auswertung sortiert nach Kennung
        (§15); ab dort rechnet sie auf dem falschen Körper weiter.

        Beides ist gefahrlos, weil die Getter monoton sind: Sie nehmen das
        Maximum aus dem Bestand **und** der bereits eingetragenen Wasserlinie.
        Ein zweiter Aufruf kann sie nur heben, nie senken.
        """
        self._record_numbering()
        restore(self.document, state)
        self._record_numbering()

    def _all_operations(self) -> list[Operation]:
        """Was Kennungen belegt: der Stapel **und** das Zurückgenommene.

        Eine zurückgenommene Operation steht nicht mehr im Dokument und ist
        trotzdem nicht frei — solange ein Redo sie zurückholen kann, gehört
        ihr ihre Nummer. „Numbers are never reused" hält
        ``test_a_change_after_undo_discards_the_cut_off_branch`` fest.

        Was hier fehlt, steht in der Wasserlinie des Dokuments: was ein
        **anderes** Verlaufsobjekt vergeben hat, und was eine frühere Sitzung
        vergeben hatte (:meth:`_record_numbering`).
        """
        return [*self.document.ops, *self._undone_ops.values()]

    def _highest_op_id(self) -> OpId:
        found = max((entry.id for entry in self._all_operations()), default=0)
        return max(found, self.document.highest_op)

    def _highest_transaction_number(self) -> int:
        """Die höchste je vergebene Transaktionsnummer.

        Drei Quellen, und jede fehlt in einer Lage, in der die Nummer zählt:
        der Stapel des Dokuments, das eigene Zurückgenommene — und die
        Wasserlinie des Dokuments, die beides überdauert.

        **Der Chat gehört dazu**, und zwar für die Dateien, die noch keine
        Wasserlinie tragen: Ein Beitrag nennt die Transaktion, die er erzeugt
        hat (§26.3), und ist damit das einzige, was von einer zurückgenommenen
        und dann gespeicherten Transaktion übrig bleibt. Ohne ihn zählte eine
        ältere Datei genau die Nummer neu aus, auf die noch jemand zeigt.
        """
        numbers = [
            *(entry.id for entry in (*self.document.transactions, *self._undone)),
            *(entry.transaction_id for entry in self.document.chat),
        ]
        found = max(
            (int(name[1:]) for name in numbers if name and name[:1] == "t" and name[1:].isdigit()),
            default=0,
        )
        return max(found, self.document.highest_transaction)

    def outputs_still_free(self, drafts: Sequence[OperationDraft]) -> bool:
        """Ob die vorgegebenen Ausgabekennungen der Entwürfe hier noch zu
        vergeben sind.

        Ein Entwurf, der auf einer Kopie dieses Dokuments geplant wurde,
        trägt die Kennungen, die die Kopie vergab — jede lag über der
        damaligen Wasserlinie. Liegt eine heute darunter, hat das Dokument
        seither selbst vergeben, und der Entwurf zeigt auf Fremdes: einen
        Körper, den inzwischen der Nutzer anlegte, oder einen, den er anlegte
        und zurücknahm. Beides ist nicht mehr der Stand, auf dem gerechnet
        wurde (§26.5).

        Kennungen, die ein Entwurf nur fortführt (Ausgang gleich Eingang),
        zählen nicht — sie gehören dem Körper, den er bearbeitet.
        """
        waterline = self._highest_object_index()
        for draft in drafts:
            for object_id in draft.outputs or ():
                if object_id in draft.inputs:
                    continue
                match = _OBJECT_PATTERN.match(object_id)
                if match and int(match.group(1)) <= waterline:
                    return False
        return True

    def _highest_object_index(self) -> int:
        indices = [
            int(match.group(1))
            for entry in self._all_operations()
            for object_id in entry.outputs
            if (match := _OBJECT_PATTERN.match(object_id))
        ]
        return max(max(indices, default=0), self.document.highest_object)


def _outputs_following(entry: Operation, inputs: Sequence[ObjectId]) -> tuple[ObjectId, ...]:
    """Die Ausgabekennungen eines Schritts nach einem Eingabewechsel.

    Eine 1:1-Operation gibt ihrem Eingang die Kennung zurück, die er hatte —
    der Verschiebeschritt auf A heißt am Ausgang A. Wer nur die Eingänge
    tauscht, lässt den Schritt B lesen und unter As Kennung ablegen: Die
    Auswertung räumt B als verbrauchten Eingang weg und legt das Ergebnis
    über A — ein Körper verschwand, und der Lauf meldete ``complete=True``
    (Gesamtreview 05.09.2026, CORE-07).

    Die Regeln von :meth:`History._outputs_for` haben eine Form: Was die
    Kennung eines Eingangs fortführt, steht als Präfix in Eingangsreihenfolge;
    was frisch vergeben wurde, folgt danach. Das Präfix folgt dem neuen
    Eingang, das Frische bleibt — eine Vereinigung behält die Kennung ihres
    Ergebnisses, und die Schritte danach finden sie weiter.
    """
    if entry.outputs == entry.inputs:
        # Ganz identisch, in beide Richtungen: auch bei variabler Zahl —
        # Anordnen gibt zurück, was es bekam, und nach dem Wechsel sind das
        # die neuen.
        return tuple(inputs)
    kept = 0
    while (
        kept < min(len(entry.outputs), len(entry.inputs))
        and entry.outputs[kept] == entry.inputs[kept]
    ):
        kept += 1
    return (*tuple(inputs)[:kept], *entry.outputs[kept:])


def _moved_order(
    operations: Sequence[Operation], chosen: Collection[OpId], before: OpId | None
) -> list[Operation]:
    """Die Folge, wenn ``chosen`` in ihrer Reihenfolge vor ``before`` steht (``None``: ans Ende)."""
    moving = [entry for entry in operations if entry.id in chosen]
    staying = [entry for entry in operations if entry.id not in chosen]
    at = next((index for index, entry in enumerate(staying) if entry.id == before), len(staying))
    return [*staying[:at], *moving, *staying[at:]]


def _order_problem(
    order: Sequence[Operation], needs: Sequence[StepNeed], registry: Registry
) -> UserError | None:
    """Warum diese Folge nicht geht — oder ``None`` (P7.2).

    Drei Fälle, keiner wird umgebogen: ein Schritt vor dem, der seinen Körper
    anlegt; ein Schritt hinter dem, der seinen Körper vorher verbraucht; ein
    Schritt vor dem, dessen Merkmal er braucht. Gerechnet wird nach Kennungen
    über alle Schritte, auch die ausgeschalteten — die Folge muss auch nach
    dem Einschalten stimmen.
    """
    title = _("Dorthin lässt sich der Schritt nicht verschieben.")
    living: set[ObjectId] = set()
    consumers: dict[ObjectId, OpId] = {}
    for entry in order:
        for name in entry.inputs:
            if name in living:
                continue
            if name in consumers:
                return UserError(
                    title=title,
                    detail=_(
                        "Schritt {other} verbraucht vorher den Körper, an dem Schritt "
                        "{step} arbeitet.",
                        step=entry.id,
                        other=consumers[name],
                    ),
                    values={"step": entry.id, "other": consumers[name], "object": name},
                    op_id=entry.id,
                    suggestions=(CANCEL,),
                )
            other = next(
                (later.id for later in order if name in later.outputs and name not in later.inputs),
                None,
            )
            return UserError(
                title=title,
                detail=_(
                    "Schritt {step} arbeitet an einem Körper, den erst Schritt {other} anlegt.",
                    step=entry.id,
                    other=other if other is not None else "?",
                ),
                values={"step": entry.id, "other": other or 0, "object": name},
                op_id=entry.id,
                suggestions=(CANCEL,),
            )
        for name in set(entry.inputs) - set(entry.outputs):
            living.discard(name)
            consumers[name] = entry.id
        living.update(entry.outputs)
    positions = {entry.id: index for index, entry in enumerate(order)}
    for need in needs:
        if need.step not in positions or need.on not in positions:
            continue
        if positions[need.on] > positions[need.step]:
            return UserError(
                title=title,
                detail=_(
                    "Schritt {step} braucht ein Merkmal, das erst Schritt {other} anlegt.",
                    step=need.step,
                    other=need.on,
                )
                if need.feature_id is not None
                else _(
                    "Schritt {step} arbeitet an einem Körper, den erst Schritt {other} anlegt.",
                    step=need.step,
                    other=need.on,
                ),
                values={
                    "step": need.step,
                    "other": need.on,
                    "object": need.object_id,
                    **({"feature": need.feature_id} if need.feature_id is not None else {}),
                },
                op_id=need.step,
                suggestions=(CANCEL,),
            )
    return None


def step_name(entry: Operation, registry: Registry = REGISTRY) -> TranslatableText | str:
    """Ein Schritt beim Namen, wie der Verlauf ihn zeigt: Nummer und Titel.

    Die Nummer ist das, wonach der Kunde im Verlauf sucht; ein Schritt, dessen
    Operation das Register nicht kennt, behält sie allein.
    """
    try:
        return _("{number} {title}", number=entry.id, title=registry.get(entry.op).title)
    except AppError:
        return str(entry.id)


def named_steps(
    entries: Sequence[Operation], registry: Registry = REGISTRY
) -> tuple[tuple[TranslatableText | str, ...], int]:
    """Welche Schritte beim Namen genannt werden, und wie viele danach nur als Zahl.

    Für die Nachfrage vor dem Löschen im Verlauf (Regel 19): Sie nennt die
    abhängigen Schritte, die mitgehen — „Bohrung setzen“ statt „spätere
    abhängige Schritte“. **Drei Namen und dann eine Zahl**, wie im Titel der
    Lösch-Transaktion (:func:`_deletion_title`); bleibt nur einer übrig, steht
    auch er da, denn „und 1 weitere“ ist länger als sein Name.
    """
    named = tuple(step_name(entry, registry) for entry in entries)
    if len(named) <= _NAMED_IN_TITLE + 1:
        return named, 0
    return named[:_NAMED_IN_TITLE], len(named) - _NAMED_IN_TITLE


def _steps_title(
    entries: Sequence[Operation],
    registry: Registry,
    *,
    one: Callable[[TranslatableText | str], TranslatableText],
    few: Callable[[int, TranslatableText | str], TranslatableText],
    many: Callable[[int, TranslatableText | str, int], TranslatableText],
) -> TranslatableText:
    """Welche Schritte eine Handlung am Verlauf betrifft, im Titel — drei Namen, dann eine Zahl.

    Dieselbe Form wie beim Löschen (:func:`_deletion_title`): Nummer und Titel
    je Schritt in der Folge des Stapels, damit der Kunde im Verlauf findet,
    was gemeint ist.
    """
    named = [step_name(entry, registry) for entry in entries]
    if len(named) == 1:
        return one(named[0])
    steps = named[0] if named else ""
    for title in named[1:_NAMED_IN_TITLE]:
        steps = _("{head}, {tail}", head=steps, tail=title)
    if len(named) <= _NAMED_IN_TITLE:
        return few(len(named), steps)
    return many(len(named), steps, len(named) - _NAMED_IN_TITLE)


def _deletion_title(
    versions: Mapping[OpId, Operation], registry: Registry = REGISTRY
) -> TranslatableText:
    """Was gelöscht wurde, steht im Titel — nicht nur, dass gelöscht wurde.

    **Der Fall.** Im Verlauf eines Kunden standen zwei Einträge untereinander,
    beide „Schritt löschen", beide ohne Nummer und ohne Namen (Alexanders
    Bildschirmfoto, gemessen von 3d-druck-4d am 04.09.2026). Er konnte nicht
    sehen, welchen der beiden Strg+Z zurückholt — und die Nummer fehlt hier
    zwangsläufig, weil eine Lösch-Transaktion keine eigene Operation vertritt
    (``ops=()``) und der Verlauf seine Zahl von dort nimmt.

    Die Transaktion **weiß** es: ``versions`` trägt die vollständigen
    Operationen, die verschwinden. Ihre Nummern und Titel gehören damit in den
    Satz, und zwar in der Reihenfolge des Stapels — wer im Verlauf nach oben
    sieht, sucht sie dort.

    **Drei Namen und dann eine Zahl.** Die Löschung nimmt abhängige Schritte
    mit (``removal_closure``), und das können viele sein; eine Zeile mit
    vierzehn Titeln liest niemand. Die drei ersten stehen da, der Rest als
    Zahl — dieselbe Entscheidung wie bei der Sammelzeile des Prüfberichts.

    Ein Schritt, dessen Operation das Register nicht kennt, behält seine
    Nummer: Sie ist das, wonach der Kunde im Verlauf sucht, und sie stimmt
    auch dann.
    """
    named: list[TranslatableText | str] = []
    for op_id, entry in versions.items():
        try:
            named.append(_("{number} {title}", number=op_id, title=registry.get(entry.op).title))
        except AppError:
            named.append(str(op_id))

    if len(named) == 1:
        return _("Schritt löschen: {step}", step=named[0])
    # Die Liste bewahrt jeden Namen als übersetzbaren Wert, auch nach dem Speichern.
    steps = named[0] if named else ""
    for title in named[1:_NAMED_IN_TITLE]:
        steps = _("{head}, {tail}", head=steps, tail=title)
    if len(named) <= _NAMED_IN_TITLE:
        return _(
            "{count} Schritte löschen: {steps}",
            count=len(named),
            steps=steps,
        )
    return _(
        "{count} Schritte löschen: {steps} und {rest} weitere",
        count=len(named),
        steps=steps,
        rest=len(named) - _NAMED_IN_TITLE,
    )
