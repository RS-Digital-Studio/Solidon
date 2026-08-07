"""Die Auswertung als reine Funktion, und was sie tut, wenn sie nicht
weiterkann (§15).
"""

from __future__ import annotations

import dataclasses

import pytest

from app.core.errors import GeometryError, OperationCancelled
from app.core.registry import Registry, op_params, param, register_op
from app.core.scene import CancelSignal, History, OperationDraft, ResultCache, evaluate
from app.core.types import (
    BaseParams,
    Document,
    Finding,
    OpContext,
    OpResult,
    Parameter,
    Profile,
    SceneObject,
)
from app.i18n import _
from tests.conftest import FakeMesh

RUNS: dict[str, int] = {}


@op_params
class MakeParams(BaseParams):
    name: str = param(title=_("Name"), default="Teil")
    size: float = param(title=_("Kantenlänge"), default=10.0, unit="mm", minimum=0.1)


@op_params
class ResizeParams(BaseParams):
    size: float = param(title=_("Kantenlänge"), default=20.0, unit="mm", minimum=0.1)


@op_params
class EmptyParams(BaseParams):
    pass


def _mesh(size: float) -> FakeMesh:
    return FakeMesh(size=(size, size, size))


@pytest.fixture
def registry() -> Registry:
    RUNS.clear()
    own = Registry()

    @register_op(
        name="make_object",
        title=_("Objekt erzeugen"),
        category="scene",
        params=MakeParams,
        consumes=0,
        produces=1,
        doc=_("Testfassung."),
        registry=own,
    )
    def make(ctx: OpContext) -> OpResult:
        RUNS["make_object"] = RUNS.get("make_object", 0) + 1
        params = ctx.params
        return OpResult(
            outputs=[SceneObject(id="", name=params.name, mesh=_mesh(params.size))],  # type: ignore[attr-defined]
            findings=[Finding(code="test.made", severity="info", message=_("Erzeugt."))],
        )

    @register_op(
        name="resize_object",
        title=_("Objekt skalieren"),
        category="transform",
        params=ResizeParams,
        consumes=1,
        produces=1,
        doc=_("Testfassung."),
        registry=own,
    )
    def resize(ctx: OpContext) -> OpResult:
        RUNS["resize_object"] = RUNS.get("resize_object", 0) + 1
        source = ctx.inputs[0]
        return OpResult(outputs=[dataclasses.replace(source, mesh=_mesh(ctx.params.size))])  # type: ignore[attr-defined]

    @register_op(
        name="split_object",
        title=_("Objekt teilen"),
        category="prepare",
        params=EmptyParams,
        consumes=1,
        produces=2,
        doc=_("Testfassung."),
        registry=own,
    )
    def split(ctx: OpContext) -> OpResult:
        RUNS["split_object"] = RUNS.get("split_object", 0) + 1
        source = ctx.inputs[0]
        return OpResult(
            outputs=[
                dataclasses.replace(source, name=f"{source.name} A"),
                dataclasses.replace(source, name=f"{source.name} B"),
            ]
        )

    @register_op(
        name="unstable_object_count",
        title=_("Wechselnde Objektzahl"),
        category="prepare",
        params=EmptyParams,
        consumes=1,
        produces=1,
        doc=_("Testfassung."),
        registry=own,
    )
    def unstable(ctx: OpContext) -> OpResult:
        source = ctx.inputs[0]
        return OpResult(outputs=[source, dataclasses.replace(source, name="Zusatz")])

    @register_op(
        name="failing_object",
        title=_("Scheitert"),
        category="boolean",
        params=EmptyParams,
        consumes=1,
        produces=1,
        doc=_("Testfassung."),
        registry=own,
    )
    def failing(ctx: OpContext) -> OpResult:
        raise GeometryError()

    @register_op(
        name="detailed_failure",
        title=_("Scheitert mit Grund"),
        category="boolean",
        params=EmptyParams,
        consumes=1,
        produces=1,
        doc=_("Testfassung."),
        registry=own,
    )
    def failing_with_detail(ctx: OpContext) -> OpResult:
        raise GeometryError(
            detail=_("Der Schlitz ist schmaler als die Düse."),
            object_id=ctx.inputs[0].id,
        )

    @register_op(
        name="cancelling_object",
        title=_("Bricht ab"),
        category="prepare",
        params=EmptyParams,
        consumes=1,
        produces=1,
        doc=_("Testfassung."),
        registry=own,
    )
    def cancelling(ctx: OpContext) -> OpResult:
        ctx.cancelled.raise_if_cancelled()
        return OpResult(outputs=list(ctx.inputs))

    return own


@pytest.fixture
def history(document: Document, registry: Registry) -> History:
    return History(document, registry)


def test_a_stack_evaluates_into_a_scene(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object", params={"name": "Halterung"})])
    history.apply(_("Teilen"), [OperationDraft(op="split_object", inputs=("obj_1",))])

    result = evaluate(document, profile, registry=registry)

    assert result.complete
    assert list(result.scene.objects) == ["obj_2", "obj_3"], "the consumed object is gone"
    assert result.scene.objects["obj_2"].name == "Halterung A"
    assert result.scene.objects["obj_2"].created_by == 2
    assert result.completed == (1, 2)


def test_evaluating_twice_gives_the_same_thing_twice(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Teilen"), [OperationDraft(op="split_object", inputs=("obj_1",))])

    first = evaluate(document, profile, registry=registry)
    second = evaluate(document, profile, registry=registry)

    assert first.scene.objects.keys() == second.scene.objects.keys()
    for object_id, entry in first.scene.objects.items():
        other = second.scene.objects[object_id]
        assert entry.name == other.name
        assert entry.mesh == other.mesh
        assert entry.created_by == other.created_by
    assert first.object_hashes == second.object_hashes


def test_findings_carry_the_operation_they_came_from(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    result = evaluate(document, profile, registry=registry)
    assert [finding.op_id for finding in result.scene.report.findings] == [1]


def test_parameters_reach_the_operations_and_the_scene(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    document.parameters["width"] = Parameter(name="width", value=40.0)
    document.parameters["half"] = Parameter(name="half", value=0.0, expression="=@width/2")
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Skalieren"),
        [OperationDraft(op="resize_object", inputs=("obj_1",), params={"size": "=@half"})],
    )

    result = evaluate(document, profile, registry=registry)

    assert result.scene.parameters["half"].value == pytest.approx(20.0)
    assert result.scene.objects["obj_1"].mesh.bounds.size == (20.0, 20.0, 20.0)


def test_a_changed_object_count_stops_the_chain(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Unruhig"), [OperationDraft(op="unstable_object_count", inputs=("obj_1",))])
    history.apply(_("Danach"), [OperationDraft(op="resize_object", inputs=("obj_1",))])

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at == 2, "it stops instead of guessing which object is which"
    assert result.completed == (1,)
    codes = [finding.code for finding in result.scene.report.findings]
    assert "evaluate.object_count" in codes
    assert "obj_1" in result.scene.objects, "what was computed stays visible"


def test_a_missing_input_stops_the_chain(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Teilen"), [OperationDraft(op="split_object", inputs=("obj_1",))])
    # Der Split hat obj_1 verbraucht; eine spätere Operation, die noch darauf
    # zeigt, ist nicht erfüllbar.
    history.apply(
        _("Danach"),
        [OperationDraft(op="resize_object", inputs=("obj_2",), outputs=("obj_2",))],
    )
    document.ops[-1] = dataclasses.replace(document.ops[-1], inputs=("obj_1",))

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at == 3
    assert "evaluate.missing_input" in [f.code for f in result.scene.report.findings]


def test_a_technical_detail_stays_behind_the_readable_sentence(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    """Ein Detail für Menschen darf nach vorn, eine Notiz für Entwickler nicht.

    Der Bericht zeigt das Detail, weil der Titel oft die Art des Fehlers nennt
    statt seines Grundes. Bei einer blanken Zeichenkette schlug das um: dort
    stand ``malformed target ''``, und beim OpenSCAD-Aufruf eine halbe Seite
    roher Programmausgabe — während der lesbare Satz in ``values`` lag.
    """
    from app.core.errors import AppError
    from app.core.scene.evaluate import _finding_from
    from app.core.types import Operation

    operation = Operation(id=1, op="make_object", inputs=(), outputs=("obj_1",), params={})

    technisch = AppError(_("Das Ziel muss ein Merkmal benennen."), detail="malformed target ''")
    zeile = _finding_from(technisch, operation)
    assert "Merkmal" in str(zeile.message), "der lesbare Satz steht vorn"
    assert zeile.values["detail"] == "malformed target ''", "die Notiz bleibt daneben"

    gesprochen = AppError(_("Ein Wert liegt daneben."), detail=_("Die Wand ist zu dünn."))
    zeile = _finding_from(gesprochen, operation)
    assert "Wand" in str(zeile.message), "ein übersetztes Detail sagt mehr als der Titel"
    assert zeile.values["kind"] == "Ein Wert liegt daneben."


def test_an_operation_without_any_input_stops_instead_of_crashing(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    """Kein Verweis ist etwas anderes als ein toter Verweis — und war lange
    schlimmer.

    Die Prüfung sah nur, ob die *genannten* Objekte existieren. Nennt eine
    Operation gar keines, obwohl sie eines verbraucht, griff sie selbst nach
    ``ctx.inputs[0]`` und starb an einem ``IndexError`` — als Stapelabzug beim
    Nutzer, und die Projektdatei ließ sich damit gar nicht mehr öffnen. Genau
    das steht in `tests/data/projects/example_v1.p3d`.
    """
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Ändern"), [OperationDraft(op="resize_object", inputs=("obj_1",), outputs=("obj_1",))]
    )
    document.ops[-1] = dataclasses.replace(document.ops[-1], inputs=())

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at == 2, "sie hält an, statt zu stürzen"
    finding = next(
        entry for entry in result.scene.report.findings if entry.code == "evaluate.too_few_inputs"
    )
    assert finding.severity == "error"
    assert finding.values["erwartet"] == 1
    assert finding.values["vorhanden"] == 0
    assert "obj_1" in result.scene.objects, "was gerechnet war, bleibt sichtbar"


def test_a_failing_operation_stops_the_chain_with_its_error(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Scheitert"), [OperationDraft(op="failing_object", inputs=("obj_1",))])

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at == 2
    assert any(
        finding.code.startswith("op.failing_object") for finding in result.scene.report.findings
    )


def test_the_report_carries_the_reason_not_only_the_kind(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    """§33.1: der Titel nennt die Art des Fehlers, das Detail seinen Grund.

    Der Bericht nahm bisher nur den Titel — und der ist bei einer
    ValidationError „Ein Wert liegt außerhalb des zulässigen Bereichs", auch
    wenn kein Wert schuld war. Der Satz, der die Sache erklärt, stand im Detail
    und kam nie an; die Art des Fehlers steht dafür jetzt in ``values``.
    """
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Scheitert"), [OperationDraft(op="detailed_failure", inputs=("obj_1",))])

    result = evaluate(document, profile, registry=registry)
    failure = next(
        finding
        for finding in result.scene.report.findings
        if finding.code.startswith("op.detailed_failure")
    )

    assert "Der Schlitz ist schmaler als die Düse" in str(failure.message)
    assert "kind" in failure.values, "die Art des Fehlers geht nicht verloren"
    assert failure.object_id == "obj_1", "und der Körper, den er meint, steht dabei"


def test_an_invalid_parameter_stops_before_the_operation_runs(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(
        _("Skalieren"),
        [OperationDraft(op="resize_object", inputs=("obj_1",), params={"size": 5.0})],
    )
    document.ops[-1] = dataclasses.replace(document.ops[-1], params={"size": -5.0})

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at == 2
    assert RUNS.get("resize_object") is None


def test_a_cancelled_run_leaves_nothing_behind(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Abbrechen"), [OperationDraft(op="cancelling_object", inputs=("obj_1",))])
    cache = ResultCache()
    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        evaluate(document, profile, registry=registry, cancelled=signal, cache=cache)

    assert len(cache) == 0, "the cache is written only after a complete pass"


def test_an_incomplete_pass_does_not_fill_the_cache(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Scheitert"), [OperationDraft(op="failing_object", inputs=("obj_1",))])
    cache = ResultCache()

    evaluate(document, profile, registry=registry, cache=cache)

    assert len(cache) == 0


def test_the_second_pass_comes_out_of_the_cache(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Teilen"), [OperationDraft(op="split_object", inputs=("obj_1",))])
    cache = ResultCache()

    evaluate(document, profile, registry=registry, cache=cache)
    evaluate(document, profile, registry=registry, cache=cache)

    assert RUNS["make_object"] == 1
    assert RUNS["split_object"] == 1
    assert cache.statistics.hits == 2


def test_a_parameter_change_only_recomputes_its_branch(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    document.parameters["size"] = Parameter(name="size", value=12.0)
    history.apply(_("Erstes"), [OperationDraft(op="make_object", params={"name": "A"})])
    history.apply(_("Zweites"), [OperationDraft(op="make_object", params={"name": "B"})])
    history.apply(
        _("Skalieren"),
        [OperationDraft(op="resize_object", inputs=("obj_1",), params={"size": "=@size"})],
    )
    cache = ResultCache()

    evaluate(document, profile, registry=registry, cache=cache)
    document.parameters["size"] = Parameter(name="size", value=30.0)
    result = evaluate(document, profile, registry=registry, cache=cache)

    assert RUNS["make_object"] == 2, "the untouched branch came from the cache"
    assert RUNS["resize_object"] == 2, "the affected branch was recomputed"
    assert result.scene.objects["obj_1"].mesh.bounds.size == (30.0, 30.0, 30.0)


def test_a_different_quality_level_is_a_different_result(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    cache = ResultCache()

    evaluate(document, profile, registry=registry, cache=cache, quality="draft")
    evaluate(document, profile, registry=registry, cache=cache, quality="fine")

    assert RUNS["make_object"] == 2


def test_an_empty_document_evaluates_to_an_empty_scene(
    document: Document, profile: Profile, registry: Registry
) -> None:
    result = evaluate(document, profile, registry=registry)
    assert result.complete
    assert result.scene.objects == {}
    assert result.scene.profile is profile
