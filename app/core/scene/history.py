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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from app.core.errors import ValidationError
from app.core.log import get_logger
from app.core.registry import REGISTRY, VARIABLE, Registry
from app.core.scene import expressions
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
)
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

_OBJECT_PATTERN = re.compile(r"^obj_(\d+)$")

#: Vorgegebene Urheberschaft. Manuelle Operationen sind einzelne Transaktionen
#: des Nutzers (§15.5).
USER_ORIGIN: Final[Origin] = Origin(by="user")


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
        self._undone: list[Transaction] = []
        self._undone_ops: dict[OpId, Operation] = {}
        self._next_op = itertools.count(self._highest_op_id() + 1)
        self._next_object = itertools.count(self._highest_object_index() + 1)
        self._next_transaction = itertools.count(len(document.transactions) + 1)

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
        changes: DocumentChange | None = None,
    ) -> Transaction:
        """Fügt Operationen als eine Transaktion an und gibt sie zurück.

        Geprüft wird alles, bevor irgendetwas geschrieben ist — ein
        abgelehnter Aufruf lässt das Dokument exakt, wie es war.

        ``changes`` trägt, was keine Operation ist (§15.5): Parameter,
        Passungen, Drucker, Material. Eine Transaktion darf daraus allein
        bestehen — eine gedrehte Zahl ist eine Änderung am Projekt, auch wenn
        kein Schritt dazukommt, und ohne Transaktion wäre sie nicht
        rücknehmbar.
        """
        if not drafts and changes is None:
            raise ValidationError(
                field="ops",
                detail=_("Eine Transaktion ohne Operationen und ohne Änderungen ändert nichts."),
                constraint="empty",
            )

        known = self._known_objects()
        planned: list[Operation] = []
        for draft in drafts:
            planned.append(self._plan(draft, known))
            known.update(planned[-1].outputs)

        self._forget_undone()
        transaction = Transaction(
            id=f"t{next(self._next_transaction)}",
            title=title,
            ops=tuple(entry.id for entry in planned),
            origin=origin,
            changes=changes,
        )
        self.document.ops.extend(planned)
        self.document.transactions.append(transaction)
        if changes is not None:
            restore(self.document, changes.after)
        return transaction

    def _plan(self, draft: OperationDraft, known: set[ObjectId]) -> Operation:
        spec = self._registry.get(draft.op)
        self._check_params(spec.name, spec.params.spec(), draft.params)

        missing = [entry for entry in draft.inputs if entry not in known]
        if missing:
            raise ValidationError(
                field="in",
                detail=_("Die Operation verweist auf ein Objekt, das es nicht gibt."),
                constraint="unknown_object",
                values={"op": draft.op, "missing": missing},
            )
        if spec.consumes and len(draft.inputs) != spec.consumes:
            raise ValidationError(
                field="in",
                detail=_("Die Operation erwartet eine andere Anzahl an Objekten."),
                constraint="consumes",
                values={"op": draft.op, "expected": spec.consumes, "given": len(draft.inputs)},
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
        entry = self.operation(op_id)
        spec = self._registry.get(entry.op)
        self._check_params(spec.name, spec.params.spec(), params)

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

        self._forget_undone()
        changed = dataclasses.replace(entry, params=dict(merged), outputs=tuple(outputs))
        self.document.ops[self.document.ops.index(entry)] = changed
        _log.info("changed parameters of op %s (%s)", op_id, entry.op)
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
        """Gleiche Anzahl rein wie raus heißt: die Objekte bleiben sie selbst;
        sonst neue IDs."""
        if spec.produces == VARIABLE and spec.produces_from:
            return tuple(
                f"obj_{next(self._next_object)}"
                for _ in range(self._stated(spec, draft, spec.produces_from))
            )
        if spec.produces == VARIABLE and not draft.inputs:
            # Nimmt nichts und macht eine unbekannte Anzahl: wie viele, kann
            # nur der Aufrufer wissen, und eins ist die ehrliche Vorgabe für
            # eine schlichte Datei.
            return tuple(f"obj_{next(self._next_object)}" for _ in range(draft.produces or 1))
        if spec.produces == VARIABLE or (spec.produces == spec.consumes and draft.inputs):
            return tuple(draft.inputs)
        return tuple(f"obj_{next(self._next_object)}" for _ in range(spec.produces))

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

    def _highest_op_id(self) -> OpId:
        return max((entry.id for entry in self.document.ops), default=0)

    def _highest_object_index(self) -> int:
        indices = [
            int(match.group(1))
            for entry in self.document.ops
            for object_id in entry.outputs
            if (match := _OBJECT_PATTERN.match(object_id))
        ]
        return max(indices, default=0)
