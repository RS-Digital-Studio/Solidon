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
import re
import secrets
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from app.core import activation, expressions
from app.core.errors import (
    CANCEL,
    CHANGE_SELECTION,
    REPAIR_AND_RETRY,
    SHOW_STEP_VALUES,
    UserError,
    ValidationError,
)
from app.core.log import get_logger
from app.core.registry import REGISTRY, VARIABLE, Registry
from app.core.scene import bundling
from app.core.types import (
    Document,
    DocumentChange,
    DocumentState,
    Fit,
    ObjectId,
    Operation,
    OpId,
    Origin,
    Parameter,
    ParameterName,
    Transaction,
    TransactionId,
)
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

_OBJECT_PATTERN = re.compile(r"^obj_(\d+)$")

#: Vorgegebene Urheberschaft. Manuelle Operationen sind einzelne Transaktionen
#: des Nutzers (§15.5).
USER_ORIGIN: Final[Origin] = Origin(by="user")


def _living_objects(operations: Sequence[Operation]) -> set[ObjectId]:
    """Die Körper, die nach einer Folge aktiver Schritte noch vorhanden sind."""
    living: set[ObjectId] = set()
    for entry in operations:
        living.difference_update(set(entry.inputs) - set(entry.outputs))
        living.update(entry.outputs)
    return living


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
                    document.ops[index] = version
                    break
            else:
                document.ops.append(version)
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
) -> DocumentChange:
    """Baut beide Seiten einer Dokumentänderung aus dem heutigen Stand.

    Damit kein Aufrufer die Vorher-Seite selbst zusammensucht: genau das war
    der Fehler, den der Agent hatte — er führte seine eigene Buchhaltung über
    frühere Werte, und die Oberfläche kannte sie nicht. Wer hier ``fits``
    übergibt, meint die vollständige neue Liste, nicht die Ergänzung.
    """
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
        ),
        after=DocumentState(
            parameters=dict(parameters) if parameters is not None else None,
            fits=tuple(fits) if fits is not None else None,
            printer=printer,
            material=material,
        ),
    )


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
        return bool(self._undone)

    @property
    def discardable(self) -> int:
        """Transaktionen, die die nächste Änderung wegwerfen würde (§15.4)."""
        return len(self._undone)

    @property
    def undone(self) -> tuple[Transaction, ...]:
        """Was zurückgenommen wurde, jüngste zuletzt — für den Verlauf.

        Der zeigte nur den aktuellen Stand; ob es noch etwas
        wiederherzustellen gab, verriet allein der Zustand des Menüeintrags.
        """
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
        self._record_numbering()
        if settled is not None:
            restore(self.document, settled.after)
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

        for entry in suffix:
            cloned = self._plan(
                OperationDraft(
                    op=entry.op,
                    inputs=entry.inputs,
                    params=entry.params,
                    outputs=entry.outputs,
                    seed=entry.seed,
                ),
                living,
            )
            cloned = dataclasses.replace(
                cloned,
                solver=None,
                translatable=entry.translatable,
                matches=entry.matches,
            )
            planned.append(cloned)
            living.difference_update(set(cloned.inputs) - set(cloned.outputs))
            living.update(cloned.outputs)

        old_versions = {entry.id: entry for entry in suffix}
        changes = DocumentChange(
            before=DocumentState(edited_ops=old_versions),
            after=DocumentState(edited_ops=dict.fromkeys(old_versions)),
        )
        self._forget_undone()
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=REPAIR_AND_RETRY.label,
            ops=tuple(entry.id for entry in planned),
            changes=changes,
        )
        self.document.ops.extend(planned)
        self.document.transactions.append(transaction)
        restore(self.document, changes.after)
        self._record_numbering()
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
        if spec.consumes and len(draft.inputs) != spec.consumes:
            raise ValidationError(
                field="in",
                detail=_("Die Operation erwartet eine andere Anzahl an Objekten."),
                constraint="consumes",
                values={"op": draft.op, "expected": spec.consumes, "given": len(draft.inputs)},
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
            self.document.ops[index] = dataclasses.replace(entry, matches=merged)
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
        if len(outputs) != len(entry.outputs):
            used = self._later_users(op_id, entry.outputs)
            if used:
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
        else:
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
        # Die Objekte am Ende des Stapels: genau das, was der Nutzer im
        # Objektbaum vor sich hat, wenn er die Auswahl ändert.
        known = self._known_objects()
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
        if spec.consumes and len(inputs) != spec.consumes:
            raise ValidationError(
                field="in",
                detail=_("Die Operation erwartet eine andere Anzahl an Objekten."),
                constraint="consumes",
                values={"op": entry.op, "expected": spec.consumes, "given": len(inputs)},
                suggestions=(CHANGE_SELECTION, CANCEL),
            )

        changed = dataclasses.replace(entry, inputs=tuple(inputs))
        _log.info("changed inputs of op %s (%s) to %s", op_id, entry.op, list(inputs))
        return self._swap_operation(spec.title, entry, changed)

    def change_kernel(self, op_id: OpId, op_name: str, params: Mapping[str, Any]) -> Operation:
        """Stellt einen Schritt auf seinen Zwilling um — denselben Schritt im
        anderen Rechenkern (§15.4, ``MENU_TWINS``).

        Die Oberfläche behandelt die beiden Kerne seit je als **eine**
        Handlung: ein Menüeintrag, ein Dialog, und ein Haken darin entscheidet.
        Beim Nachbearbeiten fehlte genau das. Wer den Quader ohne den Haken
        angelegt hatte, fand später sieben Werkzeuge grau — Fase, Verrundung,
        Formschräge, Fläche versetzen, exaktes Aushöhlen, Tasche schneiden,
        Umwandeln — und der einzige Weg dorthin war, den Schritt zu löschen
        und alles darüber neu zu bauen.

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
        from app.core.registry import MENU_TWINS

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

        versions = {op_id: self.operation(op_id) for op_id in removed_ids}
        objects_before = self._known_objects()
        objects_after: set[ObjectId] = set()
        removed_set = set(removed_ids)
        for entry in self.operations:
            if entry.id in removed_set:
                continue
            objects_after.difference_update(set(entry.inputs) - set(entry.outputs))
            objects_after.update(entry.outputs)
        disappeared = objects_before - objects_after
        remaining_fits = tuple(
            fit
            for fit in self.document.fits
            if fit.a.object_id not in disappeared and fit.b.object_id not in disappeared
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
            title=_("Schritt löschen"),
            ops=(),
            changes=changes,
        )
        self.document.transactions.append(transaction)
        self._record_numbering()
        restore(self.document, changes.after)
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
        self._reseed()
        self._forget_undone()
        changes = DocumentChange(
            before=DocumentState(edited_ops={entry.id: entry}),
            after=DocumentState(edited_ops={entry.id: changed}),
        )
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=title,
            ops=(),
            changes=changes,
        )
        self.document.transactions.append(transaction)
        self._record_numbering()
        restore(self.document, changes.after)
        return changed

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
        return max(count, 1)

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

    def undo(self) -> Transaction | None:
        """Nimmt die letzte Transaktion als Ganzes zurück (§15.5).

        Als Ganzes heißt: mit dem, was keine Operation war. Solange das hier
        nur den Stapel leerte, ließ ein Undo die Parameter und Passungen eines
        Agentenvorschlags stehen — Regel 16 verlangt ihn vollständig zurück.
        """
        if not self.document.transactions:
            return None
        # Ein Undo schließt jedes offene Bündel: Der nächste Zug ist eine neue
        # Absicht und darf den zurückgenommenen Zweig nicht stehen lassen.
        self._open_bundle = None
        transaction = self.document.transactions.pop()
        remaining: list[Operation] = []
        for entry in self.document.ops:
            if entry.id in transaction.ops:
                self._undone_ops[entry.id] = entry
            else:
                remaining.append(entry)
        self.document.ops[:] = remaining
        if transaction.changes is not None:
            restore(self.document, transaction.changes.before)
        self._undone.append(transaction)
        return transaction

    def redo(self) -> Transaction | None:
        if not self._undone:
            return None
        self._open_bundle = None
        transaction = self._undone.pop()
        for op_id in transaction.ops:
            self.document.ops.append(self._undone_ops.pop(op_id))
        self.document.ops.sort(key=lambda entry: entry.id)
        self.document.transactions.append(transaction)
        if transaction.changes is not None:
            restore(self.document, transaction.changes.after)
        return transaction

    def _forget_undone(self) -> None:
        for transaction in self._undone:
            for op_id in transaction.ops:
                self._undone_ops.pop(op_id, None)
        self._undone.clear()

    # --- Bezeichner ------------------------------------------------------------

    def _known_objects(self) -> set[ObjectId]:
        """Die Objekte, die am Ende des Stapels noch leben.

        Nicht jede je vergebene Nummer: was eine Vereinigung oder ein
        Entfernen verbraucht und nicht wieder ausgibt, ist weg. Dieselbe
        Rechnung führt die Auswertung, und sie hier zu wiederholen ist der
        Unterschied zwischen einer Operation, die beim Anlegen abgelehnt wird,
        und einem Fehler am fernen Ende der Kette über etwas, das jemand am
        nahen Ende getan hat (§15.2).
        """
        living: set[ObjectId] = set()
        for entry in self.operations:
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

    def _highest_object_index(self) -> int:
        indices = [
            int(match.group(1))
            for entry in self._all_operations()
            for object_id in entry.outputs
            if (match := _OBJECT_PATTERN.match(object_id))
        ]
        return max(max(indices, default=0), self.document.highest_object)
