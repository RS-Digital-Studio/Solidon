"""Stapel, Transaktionen und Undo (Bauplan §12, §15.4, §15.5)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.registry import VARIABLE, Registry, op_params, param, register_op
from app.core.scene import History, OperationDraft
from app.core.scene.history import change_for
from app.core.scene.project import Project, load, save
from app.core.scene.serialise import document_from_data, document_to_data
from app.core.types import (
    BaseParams,
    ChatEntry,
    Document,
    FeatureRef,
    Fit,
    OpContext,
    OpResult,
    Origin,
    Parameter,
    SolverInfo,
)
from app.i18n import _


def _parameter(name: str, value: float) -> Parameter:
    """Ein Parameter, wie ihn die Leiste anlegt — kurz gehalten, oft gebraucht."""
    return Parameter(name=name, value=value, unit="mm")


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
        doc=_("Testversion."),
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
        doc=_("Testversion."),
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
        doc=_("Testversion."),
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
        doc=_("Testversion."),
        registry=own,
    )
    def scatter(ctx: OpContext) -> OpResult:
        _unused = ctx.seed
        return OpResult(outputs=list(ctx.inputs))

    @register_op(
        name="repair",
        title=_("Reparieren"),
        category="prepare",
        params=SeedParams,
        consumes=1,
        produces=1,
        doc=_("Testversion."),
        registry=own,
    )
    def repair(ctx: OpContext) -> OpResult:
        return OpResult(outputs=list(ctx.inputs))

    @register_op(
        name="combine_objects",
        title=_("Körper verbinden"),
        category="prepare",
        params=SeedParams,
        consumes=2,
        produces=1,
        doc=_("Testversion."),
        registry=own,
    )
    def combine(ctx: OpContext) -> OpResult:
        return OpResult(outputs=[])

    @register_op(
        name="copy_object",
        title=_("Objekt duplizieren"),
        category="scene",
        params=SeedParams,
        consumes=1,
        produces=VARIABLE,
        produces_from="count",
        doc=_("Testversion — die Stückzahl steht im Parameter."),
        registry=own,
    )
    def copy_object(ctx: OpContext) -> OpResult:
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


def test_a_second_history_over_the_same_document_keeps_numbering(
    document: Document, registry: Registry
) -> None:
    """Zwei Stapel über einem Dokument vergeben keine Kennung zweimal.

    Kein erfundener Fall: Die Sitzung hält ihre ``History`` über die ganze
    Projektlaufzeit, und Trennen, Deckeln und Auto Split bauen sich eine
    eigene über demselben Dokument — sie tragen Passungen nach, und die leben
    im Dokument. Nach fünf gezeichneten Schnitten vergab die Sitzung eine
    Kennung, die es schon gab.

    Und das bleibt nicht folgenlos: Die Auswertung sortiert nach Kennung
    (§15). Eine doppelte reiht die Operation an der falschen Stelle ein, wo
    ihre Eingänge noch nicht existieren — im Fenster sah es aus, als habe das
    Anordnen die Teilung zerstört.
    """
    first = History(document, registry)
    second = History(document, registry)

    first.apply(_("Über den einen"), [OperationDraft(op="make_object")])
    second.apply(_("Über den anderen"), [OperationDraft(op="make_object")])
    first.apply(_("Wieder über den einen"), [OperationDraft(op="make_object")])

    ids = [entry.id for entry in document.ops]
    assert ids == sorted(ids), "die Reihenfolge im Dokument ist die der Kennungen"
    assert len(set(ids)) == len(ids), f"doppelte Op-Kennung: {ids}"

    objects = [name for entry in document.ops for name in entry.outputs]
    assert len(set(objects)) == len(objects), f"doppelte Objektkennung: {objects}"

    names = [entry.id for entry in document.transactions]
    assert len(set(names)) == len(names), f"doppelte Transaktionskennung: {names}"


def test_repair_and_retry_replaces_the_complete_suffix_as_one_transaction(
    history: History,
) -> None:
    """Der Reparaturknopf darf nie hinter dem gescheiterten Schritt landen.

    Der bisherige Weg hängte ``repair`` ans Ende. Die Auswertung hielt aber
    vorher am fehlerhaften Schritt an und erreichte die Reparatur nie. Der
    neue Zug ersetzt deshalb den ganzen Suffix: Reparatur zuerst, danach neue
    Fassungen des gescheiterten und aller jüngeren Schritte — auch eines
    unabhängigen. Ein Undo stellt den alten Suffix vollständig wieder her.
    """
    object_id = create(history)
    history.apply(
        _("Gescheiterter Schritt"),
        [OperationDraft(op="rename_object", inputs=(object_id,), params={"count": 4})],
    )
    failed_id = history.operations[-1].id
    marked = dataclasses.replace(
        history.operations[-1],
        solver=SolverInfo(strategy="direct"),
        seed=91,
        translatable=("name",),
        matches={"face": {"kind": "face", "centre": [1.0, 2.0, 3.0]}},
    )
    history.document.ops[-1] = marked
    history.apply(
        _("Abhängiger Schritt"),
        [OperationDraft(op="rename_object", inputs=(object_id,), params={"count": 5})],
    )
    create(history)

    prefix = tuple(entry for entry in history.operations if entry.id < failed_id)
    old_suffix = tuple(entry for entry in history.operations if entry.id >= failed_id)
    old_transaction_count = len(history.transactions)

    transaction = history.repair_and_retry(failed_id)

    assert len(history.transactions) == old_transaction_count + 1
    assert history.transactions[-1] is transaction
    assert transaction.changes is not None
    assert transaction.changes.before.edited_ops == {entry.id: entry for entry in old_suffix}
    assert transaction.changes.after.edited_ops == dict.fromkeys(entry.id for entry in old_suffix)

    new_ops = tuple(entry for entry in history.operations if entry.id in transaction.ops)
    assert [entry.op for entry in new_ops] == [
        "repair",
        "rename_object",
        "rename_object",
        "make_object",
    ]
    assert new_ops[0].inputs == (object_id,)
    retried = new_ops[1]
    assert retried.params == marked.params
    assert retried.inputs == marked.inputs
    assert retried.outputs == marked.outputs
    assert retried.seed == marked.seed
    assert retried.translatable == marked.translatable
    assert retried.matches == marked.matches
    assert retried.solver is None, "die neue Auswertung bestimmt die Rückfallstufe neu"
    assert set(transaction.ops).isdisjoint({entry.id for entry in old_suffix})
    assert tuple(entry for entry in history.operations if entry.id not in transaction.ops) == prefix

    history.undo()
    assert history.operations == prefix + old_suffix

    history.redo()
    assert tuple(entry for entry in history.operations if entry.id in transaction.ops) == new_ops
    assert not {entry.id for entry in old_suffix}.intersection(
        entry.id for entry in history.operations
    )


def test_repair_and_retry_repairs_each_live_input_once(history: History) -> None:
    """Eine Operation mit zwei Eingängen bekommt zwei Reparaturen, nicht eine Wahl."""
    first = create(history)
    second = create(history)
    history.apply(
        _("Gescheiterte Verbindung"),
        [OperationDraft(op="combine_objects", inputs=(first, second))],
    )
    failed_id = history.operations[-1].id
    old_output = history.operations[-1].outputs

    transaction = history.repair_and_retry(failed_id)

    new_ops = tuple(entry for entry in history.operations if entry.id in transaction.ops)
    assert [entry.op for entry in new_ops] == ["repair", "repair", "combine_objects"]
    assert [entry.inputs for entry in new_ops[:2]] == [(first,), (second,)]
    assert new_ops[-1].inputs == (first, second)
    assert new_ops[-1].outputs == old_output


def test_repair_and_retry_survives_saving_with_undo_and_redo(
    history: History, registry: Registry, tmp_path: Path
) -> None:
    object_id = create(history)
    history.apply(_("Gescheitert"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    failed_id = history.operations[-1].id
    original = history.operations
    transaction = history.repair_and_retry(failed_id)
    repaired = history.operations

    target = save(Project(document=history.document), tmp_path / "reparatur.p3d")
    reopened = History(load(target).document, registry)

    assert reopened.operations == repaired
    assert reopened.transactions[-1].id == transaction.id
    reopened.undo()
    assert reopened.operations == original
    reopened.redo()
    assert reopened.operations == repaired


def test_repair_and_retry_never_guesses_a_target(history: History) -> None:
    """Ein Schritt ohne Eingang ist kein Anlass, die aktuelle Auswahl zu nehmen."""
    create(history)
    failed_id = history.operations[-1].id
    before = document_to_data(history.document)

    with pytest.raises(ValidationError) as caught:
        history.repair_and_retry(failed_id)

    assert caught.value.constraint == "no_repair_target"
    assert document_to_data(history.document) == before


def test_repair_and_retry_rejects_an_input_that_is_no_longer_alive(history: History) -> None:
    """Auch eine gespeicherte, aber ungültige Eingangs-ID wird nicht ersetzt."""
    object_id = create(history)
    history.apply(_("Gescheitert"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    failed_id = history.operations[-1].id
    history.document.ops[-1] = dataclasses.replace(
        history.operations[-1], inputs=("obj_404",), outputs=("obj_404",)
    )
    before = document_to_data(history.document)

    with pytest.raises(ValidationError) as caught:
        history.repair_and_retry(failed_id)

    assert caught.value.constraint == "no_repair_target"
    assert caught.value.values["missing"] == ["obj_404"]
    assert document_to_data(history.document) == before


def test_repair_and_retry_says_no_to_an_operation_it_does_not_know(history: History) -> None:
    """Ein Schritt aus einer fremden Fassung ist kein Programmfehler.

    Eine Projektdatei kann eine Operation nennen, die dieses Register nicht
    hat — eine neuere Fassung, ein ausgebautes Werkzeug. ``repair_targets``
    fragt deshalb zuerst ``has``; ``repair_and_retry`` tat es nicht und griff
    unmittelbar ``get``, also bekam der Kunde einen ``InternalError`` mit
    Fehlerbericht statt des Satzes, der sagt, was hier nicht geht.
    """
    object_id = create(history)
    history.apply(_("Gescheitert"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    failed_id = history.operations[-1].id
    history.document.ops[-1] = dataclasses.replace(history.operations[-1], op="aus_der_zukunft")
    before = document_to_data(history.document)

    with pytest.raises(ValidationError) as caught:
        history.repair_and_retry(failed_id)

    assert caught.value.constraint == "no_repair_target"
    assert caught.value.suggestions
    assert document_to_data(history.document) == before


def test_repair_and_retry_never_turns_an_exact_shell_into_triangles() -> None:
    """Aushöhlen braucht seinen exakten Körper auch beim erneuten Versuch.

    Eine vorgeschaltete Netzreparatur würde die einzeln bearbeitbaren Flächen
    in Dreiecke umwandeln. ``shell_exact`` könnte danach nur noch mit
    ``NeedsSolidError`` halten; deshalb bleibt der Verlauf unverändert.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene.project import new_project

    load_operations()
    project = new_project()
    exact_history = History(project.document)
    exact_history.apply(
        _("Exakter Quader"),
        [OperationDraft(op="create_brep_box", params={"width": 40.0, "depth": 30.0})],
    )
    object_id = exact_history.operations[-1].outputs[0]
    exact_history.apply(
        _("Aushöhlen"),
        [OperationDraft(op="shell_exact", inputs=(object_id,), params={"wall": 2.0})],
    )
    stopped_at = exact_history.operations[-1].id
    before = document_to_data(project.document)

    with pytest.raises(ValidationError) as caught:
        exact_history.repair_and_retry(stopped_at)

    assert caught.value.constraint == "repair_not_for_exact_body"
    assert document_to_data(project.document) == before


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


def test_a_middle_step_can_be_removed_and_restored(history: History) -> None:
    """Ein falscher Schritt im Verlauf ist kein Grund, alles danach zu verlieren.

    Eine Operation mit gleicher Ein- und Ausgabe lässt sich aus der Kette
    herausnehmen: Der Körper davor bleibt unter derselben Kennung da, und der
    spätere Schritt arbeitet auf ihm weiter. Das Löschen selbst ist eine
    Transaktion, damit Strg+Z genau diesen Handgriff zurücknimmt.
    """
    object_id = create(history)
    history.apply(_("Erster Name"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    removed_id = history.operations[-1].id
    history.apply(_("Zweiter Name"), [OperationDraft(op="rename_object", inputs=(object_id,))])
    later_id = history.operations[-1].id

    assert history.removal_closure((removed_id,)) == (removed_id,)

    transaction = history.remove_operations((removed_id,))

    assert transaction.ops == (), "das Löschen fügt keine Operation hinzu"
    assert [entry.id for entry in history.operations] == [1, later_id]

    history.undo()
    assert [entry.id for entry in history.operations] == [1, removed_id, later_id]

    history.redo()
    assert [entry.id for entry in history.operations] == [1, later_id]


def test_removing_a_producer_also_removes_only_its_dependants(history: History) -> None:
    """Kein späterer Schritt bleibt mit einer verschwundenen Eingabe zurück.

    Ein unabhängig erzeugter Körper bleibt dagegen stehen. Das ist die Grenze
    zwischen einer Abhängigkeitskette und dem bloß späteren Platz im Verlauf.
    """
    first = create(history)
    producer_id = history.operations[-1].id
    history.apply(_("Abhängig"), [OperationDraft(op="rename_object", inputs=(first,))])
    dependant_id = history.operations[-1].id
    create(history)
    independent_id = history.operations[-1].id

    assert history.removal_closure((producer_id,)) == (producer_id, dependant_id)

    history.remove_operations((producer_id,))

    assert [entry.id for entry in history.operations] == [independent_id]
    history.undo()
    assert [entry.id for entry in history.operations] == [
        producer_id,
        dependant_id,
        independent_id,
    ]


def test_removing_an_object_removes_and_restores_its_fits(
    history: History, registry: Registry
) -> None:
    """Passungen verschwinden und kehren mit derselben Löschtransaktion zurück."""
    first = create(history)
    first_op = history.operations[-1].id
    second = create(history)
    fit = Fit(
        name="Steckung",
        a=FeatureRef(first, "pin"),
        b=FeatureRef(second, "hole"),
    )
    history.document.fits.append(fit)

    history.remove_operations((first_op,))

    assert history.document.fits == [], "die Passung zeigte auf einen gelöschten Körper"
    history.undo()
    assert history.document.fits == [fit], "Undo stellte die Passung nicht wieder her"
    history.redo()
    assert history.document.fits == [], "Redo ließ die Passung erneut stehen"

    reopened = History(document_from_data(document_to_data(history.document)), registry)
    reopened.undo()
    assert reopened.document.fits == [fit], "die Passung ging beim Speichern des Undo verloren"


def test_a_removed_step_and_its_undo_survive_serialisation(
    history: History, registry: Registry
) -> None:
    """Beide Seiten der Löschung reisen mit der Projektdatei.

    Sonst wäre das Löschen bis zum Speichern rücknehmbar und danach endgültig
    — genau der Fehler, den die Änderungs-Transaktionen in Format v12 behoben.
    """
    create(history)
    removed_id = history.operations[-1].id
    history.remove_operations((removed_id,))

    reopened = History(document_from_data(document_to_data(history.document)), registry)

    assert reopened.operations == ()
    reopened.undo()
    assert [entry.id for entry in reopened.operations] == [removed_id]
    reopened.redo()
    assert reopened.operations == ()


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


# --- Was keine Operation ist (§15.5) -------------------------------------------


def test_a_transaction_may_consist_of_changes_alone(history: History) -> None:
    """Eine gedrehte Zahl ist eine Änderung am Projekt, auch ohne Schritt."""
    document = history.document
    transaction = history.apply(
        _("Parameter width"),
        changes=change_for(document, parameters={"width": _parameter("width", 84.0)}),
    )

    assert transaction.ops == ()
    assert document.parameters["width"].value == 84.0
    assert history.can_undo


def test_changing_params_is_a_transaction_and_undo_restores_them(history: History) -> None:
    """Strg+Z traf einen anderen Schritt (Gesamtreview-b, Bericht 01, Szene 5).

    ``change_params`` schrieb an jeder Transaktion vorbei ins Dokument: Der
    alte Wert war unwiederbringlich weg, und ein Undo entfernte stattdessen
    die letzte Transaktion — gemessen: die ganze Bohrung verschwand, der
    geänderte Durchmesser blieb. Jetzt ist die Änderung selbst eine
    Transaktion mit beiden Fassungen (kern.md: am Dokument wird nie vorbei
    geschrieben), und der Verlauf wächst dabei um keinen Schritt (§15.4).
    """
    create(history)
    op_id = history.operations[-1].id
    before = len(history.document.transactions)

    history.change_params(op_id, {"count": 7})

    assert history.operations[-1].params["count"] == 7
    assert len(history.document.transactions) == before + 1, "die Änderung ist eine Transaktion"
    assert len(history.operations) == 1, "und der Verlauf wächst um keinen Schritt"

    history.undo()
    assert [entry.op for entry in history.operations] == ["make_object"], "der Schritt bleibt"
    # Die Ur-Fassung trug keinen Wert — die Vorgabe lebt im Schema. Genau so
    # muss sie zurückkommen: ein materialisiertes ``count`` wäre eine zweite,
    # stillere Änderung.
    assert "count" not in history.operations[-1].params, "das Undo stellt die Ur-Fassung her"

    history.redo()
    assert history.operations[-1].params["count"] == 7, "und das Redo die Änderung"


def test_changed_inputs_and_their_undo_survive_saving(history: History, registry: Registry) -> None:
    """Beide Fassungen reisen in der Datei mit (Format v12).

    Der gemessene Kern des Fundes: Nach Ändern, Speichern und Öffnen war der
    alte Stand nirgends mehr — kein Undo der Welt konnte ihn holen. Die
    Transaktion trägt Vorher- und Nachher-Fassung des Schritts, also kann
    eine frische ``History`` über der wiedergeöffneten Datei zurücknehmen.
    """
    first = create(history)
    second = create(history)
    history.apply(_("Umbenennen"), [OperationDraft(op="rename_object", inputs=(first,))])
    op_id = history.operations[-1].id

    history.change_inputs(op_id, [second])
    assert history.operations[-1].inputs == (second,)

    reloaded = document_from_data(document_to_data(history.document))
    again = History(reloaded, registry)
    again.undo()
    assert again.operations[-1].inputs == (first,), "die Vorher-Fassung überlebt das Speichern"


def test_undo_puts_a_changed_parameter_back(history: History) -> None:
    document = history.document
    document.parameters["width"] = _parameter("width", 84.0)

    history.apply(
        _("Parameter width"),
        changes=change_for(document, parameters={"width": _parameter("width", 120.0)}),
    )
    assert document.parameters["width"].value == 120.0

    history.undo()
    assert document.parameters["width"].value == 84.0, "§15.5: das Undo nimmt sie mit"

    history.redo()
    assert document.parameters["width"].value == 120.0


def test_undo_removes_a_parameter_that_did_not_exist_before(history: History) -> None:
    """Der Unterschied zwischen „war 0" und „gab es nicht" — sonst legt ein
    Undo eine Null an, wo vorher nichts war.
    """
    document = history.document
    history.apply(
        _("Parameter depth"),
        changes=change_for(document, parameters={"depth": _parameter("depth", 30.0)}),
    )

    history.undo()
    assert "depth" not in document.parameters

    history.redo()
    assert document.parameters["depth"].value == 30.0


def test_undo_puts_fits_printer_and_material_back(history: History) -> None:
    document = history.document
    document.printer = "centauri-carbon-2"
    document.material = "petg"
    fit = Fit(
        name="stift_1",
        a=FeatureRef.parse("obj_1:op1.pin_1"),
        b=FeatureRef.parse("obj_2:op1.hole_1"),
    )

    history.apply(
        _("Anderes Material"),
        changes=change_for(document, fits=[fit], printer="prusa-mk4", material="tpu-95a"),
    )
    assert (document.printer, document.material) == ("prusa-mk4", "tpu-95a")
    assert [entry.name for entry in document.fits] == ["stift_1"]

    history.undo()
    assert (document.printer, document.material) == ("centauri-carbon-2", "petg")
    assert document.fits == []


def test_operations_and_changes_travel_in_one_transaction(history: History) -> None:
    """Regel 16: ein Agentenvorschlag ist eine Transaktion, und ein Undo nimmt
    ihn ganz zurück — Operationen wie Parameter.
    """
    document = history.document
    create(history)
    before = len(history.operations)

    history.apply(
        _("Vorschlag"),
        [OperationDraft(op="make_object")],
        changes=change_for(document, parameters={"width": _parameter("width", 84.0)}),
    )
    assert len(history.operations) == before + 1

    history.undo()
    assert len(history.operations) == before
    assert "width" not in document.parameters, "beide Hälften oder keine"


def test_a_transaction_without_operations_and_without_changes_is_refused(
    history: History,
) -> None:
    with pytest.raises(ValidationError):
        history.apply(_("Nichts"))


# --- Denselben Schritt im anderen Rechenkern (§15.4, MENU_TWINS) -----------------


def test_a_step_can_be_switched_to_its_exact_twin() -> None:
    """Ein Netz-Quader ließ sich nachträglich nicht exakt machen.

    Die Oberfläche behandelt die beiden Rechenkerne seit je als **eine**
    Handlung: ein Menüeintrag, ein Dialog, ein Haken darin. Beim Nachbearbeiten
    fehlte genau das — wer den Quader ohne den Haken angelegt hatte, fand
    später sieben Werkzeuge grau, und der einzige Weg dorthin war, den Schritt
    zu löschen und alles darüber neu zu bauen.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene.project import new_project

    load_operations()
    project = new_project()
    history = History(project.document)
    history.apply(
        "Quader", [OperationDraft(op="create_box", params={"width": 30.0, "anchor": "centre"})]
    )
    op_id = project.document.ops[0].id

    changed = history.change_kernel(op_id, "create_brep_box", {"width": 30.0})

    assert changed.op == "create_brep_box"
    assert [entry.op for entry in project.document.ops] == ["create_brep_box"]
    # Das Schema des exakten Kerns kennt kein ``anchor`` — verschmolzen würde
    # es hier stehen und die Operation beim Rechnen ablehnen.
    assert "anchor" not in changed.params


def test_a_step_switches_back_as_well() -> None:
    """Beide Richtungen: der Haken lässt sich auch wieder abwählen."""
    from app.core.bootstrap import load_operations
    from app.core.scene.project import new_project

    load_operations()
    project = new_project()
    history = History(project.document)
    history.apply("Quader", [OperationDraft(op="create_brep_box", params={"width": 30.0})])
    op_id = project.document.ops[0].id

    history.change_kernel(op_id, "create_box", {"width": 30.0, "anchor": "centre"})

    assert project.document.ops[0].op == "create_box"


def test_only_twins_may_be_switched() -> None:
    """Beliebige Operationen zu tauschen wäre kein Bearbeiten, sondern ein
    Umschreiben der Geschichte.

    Ein Schritt trägt Eingänge und Ausgänge; was ihn ersetzen darf, muss
    dieselben haben. ``MENU_TWINS`` ist genau die Liste der Paare, für die das
    gilt — und die die Oberfläche ohnehin schon als eine Handlung zeigt.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene.project import new_project

    load_operations()
    project = new_project()
    history = History(project.document)
    history.apply("Quader", [OperationDraft(op="create_box", params={"width": 30.0})])
    op_id = project.document.ops[0].id

    with pytest.raises(ValidationError) as raised:
        history.change_kernel(op_id, "create_sphere", {"diameter": 20.0})

    assert "Zwilling" in str(raised.value)
    assert project.document.ops[0].op == "create_box", "abgelehnt heißt unverändert"


def test_a_transaction_number_is_never_reused_after_undo(history: History) -> None:
    """Vergeben ist vergeben — wie bei den Op-Kennungen.

    ``len(transactions) + 1`` vergab „t2" nach dem Zurücknehmen von t2
    erneut: Ein Chat-Beitrag zeigte danach auf eine wildfremde Transaktion
    und galt als lebendig (Fund des Gesamtreviews vom 25.08.2026).
    """
    object_id = create(history)
    second = history.apply(
        _("Umbenennen"), [OperationDraft(op="rename_object", inputs=(object_id,))]
    )
    history.undo()
    third = history.apply(
        _("Noch einmal"), [OperationDraft(op="rename_object", inputs=(object_id,))]
    )
    assert third.id != second.id, "eine zurückgenommene Kennung darf nie neu vergeben werden"


# --- Vergeben ist vergeben, auch über Sitzungen und Verlaufsobjekte hinweg -------


def _round_trip(document: Document, *, drop_numbering: bool = False) -> Document:
    """Speichern und wieder öffnen — durch das Dateiformat, nicht daran vorbei.

    ``drop_numbering`` streicht die Wasserlinie aus den Daten und macht damit
    aus der Datei eine, wie sie vor diesem Feld entstanden ist: Dann muss der
    Verlauf allein aus dem Bestand zählen.
    """
    data = json.loads(json.dumps(document_to_data(document)))
    if drop_numbering:
        data.pop("numbering", None)
    return document_from_data(data)


def test_a_number_survives_undo_saving_and_reopening(
    document: Document, registry: Registry
) -> None:
    """Szenario A: zurückgenommen, gespeichert, geschlossen — und t2 lebt weiter.

    Ein Agentenvorschlag legt t2 an, der Chatbeitrag trägt die Kennung. Der
    Nutzer nimmt zurück und speichert: ``document.transactions`` endet bei t1,
    und der Redo-Stapel steht in keiner Datei. Der Beitrag mit „t2" steht
    trotzdem darin, denn ``DocumentState`` deckt den Chat nicht.

    Wer beim Öffnen nur die Transaktionen zählt, gibt die nächste Handlung als
    t2 aus. Danach hält ``agent/context.is_discarded`` den alten Beitrag für
    lebendig, und eine gezielte Rücknahme („nimm t2 zurück") trifft eine
    wildfremde Transaktion.

    Beide Fassungen der Datei werden geprüft: die neue mit der Wasserlinie und
    die alte ohne sie, die dieselbe Antwort aus dem Chat gewinnen muss.
    """
    history = History(document, registry)
    object_id = create(history)
    proposal = history.apply(
        _("Vorschlag"),
        [OperationDraft(op="rename_object", inputs=(object_id,))],
        origin=Origin(by="agent", model="test", rules_version="1"),
    )
    document.chat.append(
        ChatEntry(id="c1", role="agent", text="Erledigt.", transaction_id=proposal.id)
    )
    history.undo()

    for old_file in (False, True):
        reopened = _round_trip(document, drop_numbering=old_file)
        assert [entry.id for entry in reopened.transactions] == ["t1"]
        assert reopened.chat[0].transaction_id == proposal.id

        after = History(reopened, registry).apply(
            _("Danach"), [OperationDraft(op="rename_object", inputs=(object_id,))]
        )
        assert after.id != proposal.id, f"Kennung zweimal vergeben (alte Datei: {old_file})"
        live = {entry.id for entry in reopened.transactions}
        assert reopened.chat[0].transaction_id not in live, (
            "der zurückgenommene Beitrag bleibt verworfen"
        )


def test_a_second_history_does_not_reuse_an_undone_number(
    document: Document, registry: Registry
) -> None:
    """Szenario B: Undo, dann *Automatisch teilen* — und die Nummer kommt wieder.

    Trennen, Deckeln und Auto Split bauen sich eine **zweite** ``History`` über
    demselben Dokument (``core/split.py``, ``core/lid_flow.py``); die Sitzung
    ruft sie direkt, und ihr eigener Redo-Stapel bleibt dabei stehen. Die
    zweite sieht ihn nicht — sie zählt, was im Dokument steht, und vergibt die
    zurückgenommene Kennung ein zweites Mal.

    Folgenreich wird das beim Redo: Es hängt die alte Transaktion wieder ein,
    und dann trägt ``document.ops`` dieselbe Op-Kennung doppelt. Die Auswertung
    sortiert danach (§15).
    """
    session = History(document, registry)
    create(session)
    undone = session.apply(_("Vorschlag"), [OperationDraft(op="make_object")])
    session.undo()

    other = History(document, registry)
    made = other.apply(_("Deckel erzeugen"), [OperationDraft(op="make_object")])
    assert made.id != undone.id, "die zweite History kennt den fremden Redo-Stapel nicht"

    session.redo()

    op_ids = [entry.id for entry in document.ops]
    assert len(set(op_ids)) == len(op_ids), f"doppelte Op-Kennung: {op_ids}"
    names = [entry.id for entry in document.transactions]
    assert len(set(names)) == len(names), f"doppelte Transaktionskennung: {names}"
    objects = [name for entry in document.ops for name in entry.outputs]
    assert len(set(objects)) == len(objects), f"doppelte Objektkennung: {objects}"


def test_a_changed_count_raises_the_watermark(document: Document, registry: Registry) -> None:
    """Szenario C: eine geänderte Stückzahl vergibt Kennungen — und sie zählen.

    ``change_params`` legt für eine Operation mit variabler Ausgabe frische
    Objektkennungen an. Die Wasserlinie wurde bis zum 02.09.2026 **vor** dem
    Zurücklegen der neuen Fassung geschrieben, las also noch die alte: Nach
    Stückzahl 2 → 3 standen ``obj_3`` und ``obj_4`` im Stapel und die
    Wasserlinie weiter auf 2.

    Folgenreich wird das nach einem Rückgängig, genau wie in Szenario B: Die
    neue Fassung ist dann aus ``document.ops`` heraus, ein zweites
    Verlaufsobjekt zählt nur den Bestand und vergibt ``obj_3`` erneut — und
    das Wiederherstellen macht daraus die Ausgabe zweier Operationen.
    """
    session = History(document, registry)
    create(session)
    session.apply(_("Duplizieren"), [OperationDraft(op="copy_object", inputs=("obj_1",))])
    copied = session.operations[-1]

    session.change_params(copied.id, {"count": 3})

    assert session.operations[-1].outputs == ("obj_1", "obj_3", "obj_4")
    assert document.highest_object == 4, "die frisch vergebenen Kennungen stehen darin"

    session.undo()
    other = History(document, registry)
    other.apply(_("Über den anderen"), [OperationDraft(op="make_object")])
    session.redo()

    # Nur die **frisch** vergebenen zählen: Eine Kennung, die ein Schritt als
    # Eingang bekommt und unverändert zurückgibt, steht zu Recht zweimal da.
    fresh = [name for entry in document.ops for name in entry.outputs if name not in entry.inputs]
    assert len(set(fresh)) == len(fresh), f"doppelt vergebene Objektkennung: {fresh}"


def test_removing_a_step_keeps_its_numbers_reserved(registry: Registry) -> None:
    """Die Gegenrichtung derselben Wasserlinie: Was hinausgeht, bleibt vergeben.

    ``remove_operations`` nimmt den Schritt aus ``document.ops`` heraus — ein
    Rückgängig holt ihn zurück, also gehört seine Kennung weiter ihm. Eine
    Datei ohne Wasserlinie (vor Format v14) hat dafür nur den Bestand, und der
    ist nach dem Löschen um genau diesen Schritt kürzer. Deshalb wird die
    Wasserlinie **vor** dem Zurücklegen geschrieben und danach noch einmal.
    """
    from app.core.types import Operation, Transaction

    document = Document(format_version=1, app_version="0.0.1")
    document.ops.append(Operation(id=1, op="make_object", outputs=("obj_1",)))
    document.ops.append(Operation(id=2, op="make_object", outputs=("obj_2",)))
    document.transactions.append(Transaction(id="t1", title=_("Angelegt"), ops=(1, 2)))
    session = History(document, registry)

    session.remove_operations([2])

    assert document.highest_op == 2, "die Kennung des gelöschten Schritts bleibt vergeben"
    assert document.highest_object == 2, "und die seines Körpers ebenso"

    session.apply(_("Danach"), [OperationDraft(op="make_object")])

    assert document.ops[-1].id == 3
    assert document.ops[-1].outputs == ("obj_3",)


def test_an_old_file_counts_from_its_stock(registry: Registry) -> None:
    """Eine eingecheckte Datei kennt die Wasserlinie nicht und zählt trotzdem
    richtig (§16.2).

    ``example_v11.p3d`` trägt eine Transaktion, zwei Operationen und drei
    Objekte. Ohne das Feld ist der Bestand die Quelle — und er muss es bleiben,
    solange Dateien aus der Zeit davor geöffnet werden.
    """
    from app.core.scene.project import load

    document = load(Path(__file__).parent / "data" / "projects" / "example_v11.p3d").document
    assert document.highest_transaction == 0, "die eingecheckte Datei kennt das Feld nicht"
    assert [entry.id for entry in document.transactions] == ["t1"]
    assert [entry.id for entry in document.ops] == [1, 2]

    added = History(document, registry).apply(_("Danach"), [OperationDraft(op="make_object")])

    assert added.id == "t2"
    assert document.ops[-1].id == 3
    assert document.ops[-1].outputs == ("obj_4",), "obj_1 bis obj_3 sind vergeben"


def test_a_step_this_version_cannot_run_is_not_a_program_error() -> None:
    """§16.2, und der Zwilling zu ``evaluate.unknown_operation``.

    **Der schwerere von beiden.** Der Befund aus der Auswertung schickt den
    Kunden mit *Verlauf zeigen* genau hierher; wer den Schritt dann anklickt,
    um seine Werte zu sehen, bekam ``InternalError`` — „Im Programm ist ein
    unerwarteter Fehler aufgetreten", samt Knopf für den Fehlerbericht, für
    eine Datei, die er selbst angelegt hat. Ein Handlungsvorschlag, der in
    einen Programmfehler führt, ist schlimmer als gar keiner.

    Geprüft an beiden Änderungswegen, denn beide holten den Registereintrag
    ungeprüft: ``change_params`` und ``change_inputs``.
    """
    from app.core.errors import InternalError, UserError
    from app.core.types import Document, Operation

    document = Document(format_version=13, app_version="0.0.1")
    document.ops.append(Operation(id=1, op="create_from_scad", params={"source": "cube(10);"}))
    history = History(document)

    for name, call in (
        ("change_params", lambda: history.change_params(1, {"source": "cube(20);"})),
        ("change_inputs", lambda: history.change_inputs(1, ())),
    ):
        try:
            call()
        except UserError as fehler:
            assert fehler.suggestions, f"{name}: Regel 17 — ohne Vorschlag endet es im Nichts"
            assert "show_step_values" in {a.id for a in fehler.suggestions}, (
                f"{name}: die Werte des Schritts sind das Einzige, was noch zu holen ist"
            )
            assert fehler.values.get("operation") == "create_from_scad"
            assert fehler.op_id == 1, f"{name}: der Vorschlag braucht die Schrittkennung"
        except InternalError:  # pragma: no cover - genau das darf nicht mehr sein
            raise AssertionError(
                f"{name}: eine Operation aus einer Datei ist kein Programmfehler"
            ) from None
        else:  # pragma: no cover
            raise AssertionError(f"{name}: der Schritt ist unbekannt, das gehört gesagt")
