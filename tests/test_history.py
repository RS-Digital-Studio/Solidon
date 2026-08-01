"""Stack, transactions and undo (Bauplan §12, §15.4, §15.5)."""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.registry import Registry, op_params, param, register_op
from app.core.scene import History, OperationDraft
from app.core.types import BaseParams, Document, OpContext, OpResult, Origin
from app.i18n import _


@op_params
class SeedParams(BaseParams):
    count: int = param(title=_("Anzahl"), default=2, minimum=1)


@pytest.fixture
def registry() -> Registry:
    own = Registry()

    @register_op(
        name="rename_object",
        title=_("Objekt umbenennen"),
        category="scene",
        params=SeedParams,
        consumes=1,
        produces=1,
        doc=_("Testfassung."),
        registry=own,
    )
    def rename(ctx: OpContext) -> OpResult:
        return OpResult(outputs=list(ctx.inputs))

    @register_op(
        name="make_object",
        title=_("Objekt erzeugen"),
        category="scene",
        params=SeedParams,
        consumes=0,
        produces=1,
        doc=_("Testfassung."),
        registry=own,
    )
    def make(ctx: OpContext) -> OpResult:
        return OpResult(outputs=[])

    @register_op(
        name="split_object",
        title=_("Objekt teilen"),
        category="prepare",
        params=SeedParams,
        consumes=1,
        produces=2,
        doc=_("Testfassung."),
        registry=own,
    )
    def split(ctx: OpContext) -> OpResult:
        return OpResult(outputs=[])

    @register_op(
        name="scatter",
        title=_("Verteilen"),
        category="prepare",
        params=SeedParams,
        consumes=1,
        produces=1,
        deterministic=False,
        doc=_("Testfassung."),
        registry=own,
    )
    def scatter(ctx: OpContext) -> OpResult:
        _unused = ctx.seed
        return OpResult(outputs=list(ctx.inputs))

    return own


@pytest.fixture
def history(document: Document, registry: Registry) -> History:
    return History(document, registry)


def create(history: History) -> str:
    history.apply(_("Objekt anlegen"), [OperationDraft(op="make_object")])
    return history.operations[-1].outputs[0]


def test_operations_and_objects_are_numbered_in_order(history: History) -> None:
    first = create(history)
    assert first == "obj_1"
    assert history.operations[0].id == 1

    second = create(history)
    assert second == "obj_2"
    assert history.operations[-1].id == 2


def test_same_count_in_and_out_keeps_the_object(history: History) -> None:
    object_id = create(history)
    history.apply(_("Umbenennen"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    assert history.operations[-1].outputs == (object_id,)


def test_a_different_count_produces_new_objects(history: History) -> None:
    object_id = create(history)
    history.apply(_("Teilen"), [OperationDraft(op="split_object", inputs=(object_id,))])
    assert history.operations[-1].outputs == ("obj_2", "obj_3")


def test_a_transaction_groups_its_operations(history: History) -> None:
    object_id = create(history)
    transaction = history.apply(
        _("Zwei Schritte"),
        [
            OperationDraft(op="rename_object", inputs=(object_id,)),
            OperationDraft(op="split_object", inputs=(object_id,)),
        ],
        origin=Origin(by="agent", model="test", rules_version="1"),
    )
    assert len(transaction.ops) == 2
    assert transaction.origin.by == "agent"
    assert history.transaction_of(transaction.ops[0]) is transaction


def test_undo_takes_the_whole_transaction(history: History) -> None:
    object_id = create(history)
    history.apply(
        _("Zwei Schritte"),
        [
            OperationDraft(op="rename_object", inputs=(object_id,)),
            OperationDraft(op="rename_object", inputs=(object_id,)),
        ],
    )
    assert len(history.operations) == 3

    history.undo()
    assert len(history.operations) == 1
    assert len(history.transactions) == 1

    history.redo()
    assert len(history.operations) == 3
    assert [entry.id for entry in history.operations] == [1, 2, 3]


def test_undo_and_redo_survive_ten_transactions(history: History) -> None:
    object_id = create(history)
    for _index in range(10):
        history.apply(_("Umbenennen"), [OperationDraft(op="rename_object", inputs=(object_id,))])

    for _index in range(10):
        assert history.undo() is not None
    assert len(history.transactions) == 1
    assert history.undo() is not None
    assert history.undo() is None
    assert not history.can_undo

    for _index in range(11):
        assert history.redo() is not None
    assert history.redo() is None
    assert len(history.operations) == 11


def test_a_change_after_undo_discards_the_cut_off_branch(history: History) -> None:
    object_id = create(history)
    history.apply(_("Eins"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    history.apply(_("Zwei"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    history.undo()
    history.undo()
    assert history.discardable == 2, "the surface asks before more than one is thrown away"

    history.apply(_("Drei"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    assert history.discardable == 0
    assert not history.can_redo
    assert [entry.id for entry in history.operations] == [1, 4], "numbers are never reused"


def test_an_unknown_input_object_is_rejected(history: History) -> None:
    with pytest.raises(ValidationError) as caught:
        history.apply(_("Falsch"), [OperationDraft(op="rename_object", inputs=("obj_9",))])
    assert caught.value.constraint == "unknown_object"


def test_the_declared_object_count_is_enforced(history: History) -> None:
    create(history)
    with pytest.raises(ValidationError) as caught:
        history.apply(_("Falsch"), [OperationDraft(op="rename_object")])
    assert caught.value.constraint == "consumes"


def test_a_random_operation_always_ends_up_with_a_stored_seed(history: History) -> None:
    """§11.3: entscheidend ist, dass der Startwert aufgehoben wird, nicht wer
    ihn sich ausgedacht hat.
    """
    object_id = create(history)
    history.apply(_("Verteilen"), [OperationDraft(op="scatter", inputs=(object_id,))])
    drawn = history.operations[-1].seed
    assert drawn is not None, "a randomised operation never runs without a stored seed"

    history.apply(
        _("Verteilen"), [OperationDraft(op="scatter", inputs=(object_id,), seed=20260727)]
    )
    assert history.operations[-1].seed == 20260727, "a given seed is kept as it is"


def test_a_deterministic_operation_gets_no_seed(history: History) -> None:
    object_id = create(history)
    history.apply(_("Umbenennen"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    assert history.operations[-1].seed is None


def test_unknown_parameters_and_broken_expressions_are_caught_early(history: History) -> None:
    object_id = create(history)
    with pytest.raises(ValidationError):
        history.apply(
            _("Falsch"),
            [OperationDraft(op="rename_object", inputs=(object_id,), params={"nope": 1})],
        )
    with pytest.raises(ValidationError):
        history.apply(
            _("Falsch"),
            [OperationDraft(op="rename_object", inputs=(object_id,), params={"count": "=@a ** 2"})],
        )


def test_a_rejected_call_leaves_the_document_untouched(history: History) -> None:
    object_id = create(history)
    before = len(history.operations)
    with pytest.raises(ValidationError):
        history.apply(
            _("Halb falsch"),
            [
                OperationDraft(op="rename_object", inputs=(object_id,)),
                OperationDraft(op="rename_object", inputs=("obj_99",)),
            ],
        )
    assert len(history.operations) == before
    assert len(history.transactions) == 1


def test_an_empty_transaction_is_refused(history: History) -> None:
    with pytest.raises(ValidationError):
        history.apply(_("Nichts"), [])


def test_a_reopened_document_continues_the_numbering(registry: Registry) -> None:
    document = Document(format_version=1, app_version="0.0.1")
    first = History(document, registry)
    create(first)
    create(first)

    reopened = History(document, registry)
    create(reopened)
    assert reopened.operations[-1].id == 3
    assert reopened.operations[-1].outputs == ("obj_3",)
