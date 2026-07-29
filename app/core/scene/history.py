"""Stack, transactions and undo (Bauplan §12, §15.4, §15.5).

Operations form a DAG through ``in``/``out`` and stay linearly presentable: the
order of the operation numbers is the order of the history panel.

The unit of undo is the transaction, not the operation — an agent proposal is
exactly one transaction (AGENTS.md rule 16), so one undo takes back what the
agent suggested in one go.

There are no branches (§15.4). Applying something after an undo discards the cut
off transactions; the surface asks first as soon as more than one is affected,
which is what :attr:`History.discardable` is for.
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
from app.core.registry import REGISTRY, VARIABLE, Registry
from app.core.scene import expressions
from app.core.types import Document, ObjectId, Operation, OpId, Origin, Transaction
from app.i18n import TranslatableText, _

_OBJECT_PATTERN = re.compile(r"^obj_(\d+)$")

#: Default authorship. Manual operations are single transactions by the user (§15.5).
USER_ORIGIN: Final[Origin] = Origin(by="user")


@dataclass(frozen=True, slots=True)
class OperationDraft:
    """An operation about to enter the stack. Numbers are handed out by the history."""

    op: str
    inputs: tuple[ObjectId, ...] = ()
    params: Mapping[str, Any] = field(default_factory=dict)
    outputs: tuple[ObjectId, ...] | None = None
    """Usually derived: same count in and out keeps the ids, otherwise new ones."""
    produces: int | None = None
    """How many objects a variable-output operation that takes none will make.

    Loading an assembly is the case: how many bodies come out is written in the
    file, and the stack hands out ids before the file is read (§11). So the
    caller who knows says so — for everything else the count follows from the
    declaration and this stays ``None``."""
    seed: int | None = None


class History:
    """Holds a document and the way through it."""

    def __init__(self, document: Document, registry: Registry | None = None) -> None:
        self.document = document
        self._registry = registry or REGISTRY
        self._undone: list[Transaction] = []
        self._undone_ops: dict[OpId, Operation] = {}
        self._next_op = itertools.count(self._highest_op_id() + 1)
        self._next_object = itertools.count(self._highest_object_index() + 1)
        self._next_transaction = itertools.count(len(document.transactions) + 1)

    # --- reading ---------------------------------------------------------------

    @property
    def operations(self) -> tuple[Operation, ...]:
        """The active stack in operation order — the linear view of the DAG."""
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
        """Transactions the next change would throw away (§15.4)."""
        return len(self._undone)

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

    # --- writing ---------------------------------------------------------------

    def apply(
        self,
        title: TranslatableText | str,
        drafts: Sequence[OperationDraft],
        origin: Origin = USER_ORIGIN,
    ) -> Transaction:
        """Add operations as one transaction and return it.

        Everything is checked before anything is written, so a rejected call
        leaves the document exactly as it was.
        """
        if not drafts:
            raise ValidationError(
                field="ops",
                detail=_("Eine Transaktion ohne Operationen ergibt keinen Sinn."),
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
        )
        self.document.ops.extend(planned)
        self.document.transactions.append(transaction)
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
        # §11.3: a randomised procedure carries a stored seed. Where the caller
        # did not bring one, one is drawn here — what matters is that it is kept,
        # not who thought of it.
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
        """Write the fallback stage that carried each operation into the stack (§17.2).

        Evaluation is a pure function and does not touch the document; this is
        where its findings about solver stages are kept, so reopening the file
        recomputes the same way.
        """
        if not solvers:
            return
        for index, entry in enumerate(self.document.ops):
            solver = solvers.get(entry.id)
            if solver is not None and entry.solver != solver:
                self.document.ops[index] = dataclasses.replace(entry, solver=solver)

    def _outputs_for(self, spec: Any, draft: OperationDraft) -> tuple[ObjectId, ...]:
        """Same count in and out means the objects stay themselves; otherwise new ids."""
        if spec.produces == VARIABLE and spec.produces_from:
            return tuple(
                f"obj_{next(self._next_object)}"
                for _ in range(self._stated(spec, draft, spec.produces_from))
            )
        if spec.produces == VARIABLE and not draft.inputs:
            # Takes nothing and makes an unknown number: only the caller can
            # know how many, and one is the honest default for a plain file.
            return tuple(f"obj_{next(self._next_object)}" for _ in range(draft.produces or 1))
        if spec.produces == VARIABLE or (spec.produces == spec.consumes and draft.inputs):
            return tuple(draft.inputs)
        return tuple(f"obj_{next(self._next_object)}" for _ in range(spec.produces))

    def _stated(self, spec: Any, draft: OperationDraft, field_name: str) -> int:
        """The output count an operation wrote into one of its parameters.

        A plain number, because the ids are handed out here and an expression
        (§13) is only resolved when the scene is computed. A count that first
        has to be calculated would mean the stack could not say how many
        objects a step makes — so it is refused with that sentence rather than
        guessed at.
        """
        value = draft.params.get(
            field_name,
            next((entry.default for entry in spec.params.spec() if entry.name == field_name), 1),
        )
        if expressions.is_expression(value):
            raise ValidationError(
                field=field_name,
                detail=_("Eine Stückzahl muss eine Zahl sein, kein Ausdruck."),
                constraint="not_a_number",
                values={"op": spec.name, "value": str(value)},
            )
        try:
            return max(int(value), 1)
        except (TypeError, ValueError) as problem:
            raise ValidationError(
                field=field_name,
                detail=_("Eine Stückzahl muss eine Zahl sein, kein Ausdruck."),
                constraint="not_a_number",
                values={"op": spec.name, "value": str(value)},
            ) from problem

    def _check_params(self, op_name: str, specs: Iterable[Any], params: Mapping[str, Any]) -> None:
        """Names and expression syntax. Values are checked once resolved (§13)."""
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

    # --- undo and redo ---------------------------------------------------------

    def undo(self) -> Transaction | None:
        """Take back the last transaction as a whole (§15.5)."""
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
        return transaction

    def _forget_undone(self) -> None:
        for transaction in self._undone:
            for op_id in transaction.ops:
                self._undone_ops.pop(op_id, None)
        self._undone.clear()

    # --- identifiers -----------------------------------------------------------

    def _known_objects(self) -> set[ObjectId]:
        known: set[ObjectId] = set()
        for entry in self.document.ops:
            known.update(entry.outputs)
        return known

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
