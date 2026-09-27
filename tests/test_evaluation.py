"""Die Auswertung als reine Funktion, und was sie tut, wenn sie nicht
weiterkann (§15).
"""

from __future__ import annotations

import dataclasses
import logging
import math
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.core.errors import GeometryError, OperationCancelled
from app.core.registry import Registry, op_params, param, register_op
from app.core.scene import CancelSignal, History, OperationDraft, ResultCache, evaluate
from app.core.types import (
    BaseParams,
    Document,
    FeatureRef,
    Finding,
    Fit,
    OpContext,
    OpResult,
    Parameter,
    Profile,
    SceneObject,
)
from app.i18n import _
from tests.conftest import FakeMesh

RUNS: dict[str, int] = {}
MESHES = Path(__file__).parent / "data" / "meshes"


def test_secondary_material_profile_recalibrates_a_cached_operation(
    document: Document, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch bei unveränderten Profilkennungen liest der echte Auswertungsweg neue Maße."""
    from app.core.knowledge import profiles

    @op_params
    class MaterialParams(BaseParams):
        liner: str = param(title=_("Material"), kind="material", default="liner")

    registry = Registry()
    secondary = dataclasses.replace(profile.material, id="liner", clearance=0.25)
    original_material = profiles.material
    monkeypatch.setattr(
        profiles, "material", lambda name: secondary if name == "liner" else original_material(name)
    )
    runs = []

    @register_op(
        name="material_probe",
        title=_("Prüfkörper"),
        category="primitive",
        params=MaterialParams,
        consumes=0,
        material_params=("liner",),
        registry=registry,
    )
    def make(ctx: OpContext) -> OpResult:
        runs.append(ctx.params.liner)
        return OpResult(
            outputs=[
                SceneObject(
                    id="",
                    name="Probe",
                    mesh=_mesh(10 + profiles.material(ctx.params.liner).clearance),
                )
            ]
        )

    history = History(document, registry=registry)
    history.apply("Materialprobe", [OperationDraft(op="material_probe")])
    cache = ResultCache()
    first = evaluate(document, profile, registry=registry, cache=cache)
    repeated = evaluate(document, profile, registry=registry, cache=cache)
    assert first.complete and repeated.complete
    assert runs == ["liner"]
    secondary = dataclasses.replace(secondary, clearance=0.4)
    changed = evaluate(document, profile, registry=registry, cache=cache)
    assert changed.complete
    assert runs == ["liner", "liner"]
    assert first.object_hashes != changed.object_hashes
    assert first.scene.objects["obj_1"].mesh.bounds.size[0] == pytest.approx(10.25)
    assert changed.scene.objects["obj_1"].mesh.bounds.size[0] == pytest.approx(10.4)
    history.change_params(document.ops[0].id, {"liner": "missing-material"})
    missing = evaluate(document, profile, registry=registry, cache=cache)
    assert missing.stopped_at == document.ops[0].id
    assert runs == ["liner", "liner"]


def test_failed_result_matching_keeps_every_input(
    document: Document, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine angehaltene Zuordnung veröffentlicht keinen halben Vereinigungsschritt."""
    from importlib import import_module

    from app.core.bootstrap import load_operations
    from app.core.errors import AmbiguityError

    load_operations()
    history = History(document)
    history.apply(
        "Zwei Körper",
        [
            OperationDraft(op="create_box", params={"width": 10.0}),
            OperationDraft(op="create_box", params={"width": 8.0}),
        ],
    )
    before = evaluate(document, profile)
    assert before.complete
    history.apply("Vereinigen", [OperationDraft(op="union_objects", inputs=("obj_1", "obj_2"))])
    module = import_module("app.core.scene.evaluate")
    original = module._with_features

    def fail_at_union(placed, previous, operation, *args, **kwargs):
        if operation.op == "union_objects":
            raise AmbiguityError(question="Erzwungene mehrdeutige Merkmalszuordnung.")
        return original(placed, previous, operation, *args, **kwargs)

    monkeypatch.setattr(module, "_with_features", fail_at_union)
    after = evaluate(document, profile)
    assert after.stopped_at == document.ops[-1].id
    assert set(after.scene.objects) == set(before.scene.objects)
    assert after.object_hashes == before.object_hashes
    assert after.object_names == before.object_names
    for name, source in before.scene.objects.items():
        assert after.scene.objects[name].mesh.volume == pytest.approx(source.mesh.volume)


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
        doc=_("Testversion."),
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
        doc=_("Testversion."),
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
        doc=_("Testversion."),
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
        doc=_("Testversion."),
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
        doc=_("Testversion."),
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
        doc=_("Testversion."),
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
        doc=_("Testversion."),
        registry=own,
    )
    def cancelling(ctx: OpContext) -> OpResult:
        ctx.cancelled.raise_if_cancelled()
        return OpResult(outputs=list(ctx.inputs))

    @register_op(
        name="raising_object",
        title=_("Wirft eine fremde Ausnahme"),
        category="prepare",
        params=EmptyParams,
        consumes=1,
        produces=1,
        doc=_("Testversion."),
        registry=own,
    )
    def raising(ctx: OpContext) -> OpResult:
        import json

        json.loads("kein json")
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
    stand ``malformed target ''``, und bei einem Quelltext-Aufruf eine halbe Seite
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
    assert finding.values["expected"] == 1
    assert finding.values["given"] == 0
    assert "obj_1" in result.scene.objects, "was gerechnet war, bleibt sichtbar"


@pytest.mark.parametrize("count", [0, 1])
def test_a_loaded_variable_operation_stops_before_running_with_too_few_inputs(
    history: History, document: Document, profile: Profile, registry: Registry, count: int
) -> None:
    """Auch ein aus der Datei gelesener Schritt muss die Mindestzahl einhalten."""
    from app.core.registry import VARIABLE

    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Ändern"), [OperationDraft(op="resize_object", inputs=("obj_1",))])
    document.ops[-1] = dataclasses.replace(document.ops[-1], inputs=("obj_1",)[:count])
    spec = registry.get("resize_object")
    registry.remove(spec.name)
    registry.register(dataclasses.replace(spec, consumes=VARIABLE, minimum_inputs=2))

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at == document.ops[-1].id
    finding = next(
        entry for entry in result.scene.report.findings if entry.code == "evaluate.too_few_inputs"
    )
    assert finding.values["expected"] == 2
    assert finding.values["given"] == count
    assert "obj_1" in result.scene.objects


def test_a_loaded_fixed_operation_cannot_silently_consume_an_extra_object(
    history: History,
    document: Document,
    profile: Profile,
    registry: Registry,
) -> None:
    """Ein fehlerhafter Dateischritt darf den zweiten Körper nicht verschwinden lassen.

    Bei fester Stelligkeit über null hält die Kette an, und das bleibt so:
    Welcher der beiden genannten Körper der gemeinte ist, entscheidet der Kern
    nicht (Regel 21). Der Erzeuger daneben ist ein anderer Fall — er hat keine
    Wahl zu treffen, und der Test darunter hält ihn fest.
    """
    history.apply(
        _("Anlegen"), [OperationDraft(op="make_object"), OperationDraft(op="make_object")]
    )
    history.apply(_("Ändern"), [OperationDraft(op="resize_object", inputs=("obj_1",))])
    document.ops[-1] = dataclasses.replace(document.ops[-1], inputs=("obj_1", "obj_2"))

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at == document.ops[-1].id
    assert set(result.scene.objects) == {"obj_1", "obj_2"}
    assert RUNS.get("resize_object", 0) == 0
    assert RUNS["make_object"] == 2
    finding = next(
        entry for entry in result.scene.report.findings if entry.code == "evaluate.too_many_inputs"
    )
    assert finding.values["expected"] == 1
    assert finding.values["given"] == 2
    assert finding.suggestions


def test_a_loaded_creator_drops_its_stray_inputs_instead_of_stopping(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    """Ein Erzeuger mit Eingängen aus einer alten Datei hält die Kette nicht an.

    **Die verschärfte Obergrenze wirkte rückwärts.** ``History.apply`` nahm
    Eingänge an einem Erzeuger bis zum 07.09.2026 an, und die Auswertung
    prüfte den Fall nicht — sie las ``consumes > 0``. Solche Schritte stehen
    also in bestehenden Projektdateien. Seit der Verschärfung hielten sie mit
    ``evaluate.too_many_inputs`` an, ohne Migration und ohne Rückweg: Der
    einzige Vorschlag des Befunds ist *Andere Objekte wählen*, und der landet
    über ``History.change_inputs`` auf derselben Absage.

    Erwartet wird deshalb: Die überzähligen Eingänge fallen weg, der Schritt
    läuft, der genannte Körper bleibt in der Szene — und ein Befund sagt es.
    """
    history.apply(
        _("Anlegen"), [OperationDraft(op="make_object"), OperationDraft(op="make_object")]
    )
    history.apply(_("Noch einer"), [OperationDraft(op="make_object")])
    document.ops[-1] = dataclasses.replace(document.ops[-1], inputs=("obj_1", "obj_2"))

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at is None, "die Kette läuft durch"
    assert set(result.scene.objects) == {"obj_1", "obj_2", "obj_3"}
    assert RUNS["make_object"] == 3, "der Erzeuger läuft, statt übergangen zu werden"
    finding = next(
        entry
        for entry in result.scene.report.findings
        if entry.code == "evaluate.creator_inputs_dropped"
    )
    assert finding.severity == "warning", "die Datei ist schief, die Rechnung nicht"
    assert finding.op_id == document.ops[-1].id
    assert finding.values["given"] == 2
    assert finding.values["ignored"] == "obj_1, obj_2"
    assert not finding.suggestions, "hier gibt es nichts zu wählen"
    assert not [
        entry for entry in result.scene.report.findings if entry.code == "evaluate.too_many_inputs"
    ], "der Erzeuger geht nicht mehr über die Absage"


def test_a_failing_operation_stops_the_chain_with_its_error(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Scheitert"), [OperationDraft(op="failing_object", inputs=("obj_1",))])

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at == 2
    failure = next(
        finding
        for finding in result.scene.report.findings
        if finding.code.startswith("op.failing_object")
    )
    assert {action.id for action in failure.suggestions} == {
        "repair_and_retry",
        "show_locations",
        "cancel",
    }, "der Prüfbericht behält die konkreten Auswege der Ausnahme"


def test_a_foreign_exception_stops_the_chain_instead_of_escaping(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    """Eine fremde Ausnahme aus einer Op-Umsetzung — etwa ein rohes
    ``json.loads`` in einem Sammelparameter-Leser — darf die Auswertung nicht
    verlassen: im echten Betrieb stirbt sonst der Thread, und die Sitzung
    meldet Erfolg mit dem alten Ergebnis."""
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    history.apply(_("Wirft"), [OperationDraft(op="raising_object", inputs=("obj_1",))])

    result = evaluate(document, profile, registry=registry)

    assert result.stopped_at == 2
    failure = next(
        finding
        for finding in result.scene.report.findings
        if finding.code.startswith("op.raising_object")
    )
    assert "JSONDecodeError" in str(failure.message) or "JSONDecodeError" in str(failure.values), (
        "die Ausnahme steht im Befund, nicht im Nirgendwo"
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


def test_an_ambiguous_match_stops_with_a_finding_instead_of_escaping(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Merkmalszuordnung fragt — und wenn niemand da ist, muss sie anhalten
    wie jeder andere Fehler auch.

    Sie stand außerhalb des Fehler-Fangs: die ``AmbiguityError`` flog aus
    ``evaluate`` heraus, statt ein Befund zu werden. Wer keinen Frage-Dialog
    hat — die Kommandozeile, die Fernsteuerung, der Agent —, bekam eine
    Ausnahme und einen leeren Prüfbericht, statt zu erfahren, welche zwei
    Bohrungen gemeint sein könnten.

    **Die Mehrdeutigkeit wird erzwungen und nicht erhofft, und das ist der
    Kern dieses Tests.** Bis zum 23.08.2026 stand hier ein hohler Quader, bei
    dem sie sich von selbst ergab — bis 3d-druck-3a nachmaß, woran das lag:
    Der Körper hat **überhaupt keine Bohrung**. Was die Erkennung als zwei
    meldete, waren seine verrundeten Innenkanten, zwei Flecken mit r = 1,99,
    gleiche Achse, gleicher Durchmesser. Der Test hing damit an zwei
    Fehlbefunden, und jede Verbesserung der Erkennung kippte ihn — zu Recht.

    **Ein besserer Körper wäre die falsche Antwort gewesen.** Er verschiebt
    den Zufall nur: Weder zwei eingelesene Zwillingsbohrungen noch zwei
    gebohrte stellen über den Stapel gemessen eine einzige Frage, und beide
    Male aus demselben Grund — sie stehen von Anfang an beide da, und jede
    findet ihre eigene wieder, egal wie gleich sie aussehen. Mehrdeutigkeit
    entsteht nur, wenn ein *altes* Merkmal auf *zwei neue* gleich gut passt;
    die Merkmalszahl muss sich ändern, nicht die Ähnlichkeit. Das über
    Geometrie herbeizuführen hieße wieder, auf einen Zufall zu bauen.

    Zugesichert ist hier ohnehin etwas anderes: **was ``evaluate`` mit einer
    Mehrdeutigkeit macht**, nicht welcher Körper eine hat. Ersetzt ist deshalb
    nur der Auslöser. Der Weg dahinter läuft echt — der fehlende Frager, die
    ``AmbiguityError``, der Fangbereich, der Befund im Prüfbericht.
    """
    from importlib import import_module

    from app.core.bootstrap import load_operations
    from app.core.perceive.matching import MatchResult
    from app.core.scene.project import ProjectSources, new_project

    def always_ambiguous(
        old: dict[str, object],
        new: dict[str, object],
        centre: object,
        diagonal: float,
        old_centre: object = None,
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> MatchResult:
        """Meldet das erste alte Merkmal als zwischen zweien unentscheidbar."""
        if not old or len(new) < 2:
            return MatchResult()
        return MatchResult(ambiguous={next(iter(old)): tuple(new)[:2]})

    # Die Frage gilt seit dem 25.08.2026 nur verwiesenen Merkmalen — ein
    # unverwiesenes flutete den Nutzer (zwölf Schleifenfragen in Weg 3),
    # ohne dass eine falsche Bindung irgendetwas hätte brechen können. Der
    # Verweis kommt hier als Passung, wie ihn ein echtes Dokument trüge.

    # ``import_module`` mit vollem Pfad und nicht ``from app.core.scene import
    # evaluate``: Das Paket re-exportiert die *Funktion* ``evaluate`` und
    # verdeckt damit sein eigenes gleichnamiges Untermodul. Beide kurzen Formen
    # landen auf der Funktion, und ``monkeypatch`` meldet dann, sie habe kein
    # Attribut ``match``.
    monkeypatch.setattr(import_module("app.core.scene.evaluate"), "match", always_ambiguous)

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Aufbau",
        [
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 30.0}),
            OperationDraft(op="hollow_object", inputs=("obj_1",), params={"wall": 2.0}),
        ],
    )
    first = evaluate(project.document, profile, sources=ProjectSources(project))
    feature_id = next(iter(first.scene.objects["obj_1"].features))
    project.document.fits.append(
        Fit(
            name="probe",
            a=FeatureRef("obj_1", feature_id),
            b=FeatureRef("obj_1", feature_id),
            kind="clearance",
            tolerance="auto:petg",
        )
    )
    History(project.document).apply(
        "Elefantenfuß",
        [OperationDraft(op="compensate_first_layer", inputs=("obj_1",), params={})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert not result.complete, "raten wäre schlimmer, aber die Auswertung gibt es weiter"
    codes = {finding.code for finding in result.scene.report.findings}
    assert any("Ambiguity" in code for code in codes), codes


def test_an_unreferenced_feature_never_becomes_a_question(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Kehrseite des Tests darüber: ohne Verweis keine Frage (§21.3).

    Der Fall, der das erzwungen hat, ist Weg 3: Ein erzeugtes Netz trägt
    zwölf offene Kantenschleifen, jede seit E-15 ein eigenes Merkmal, und
    vor dem zweiten Schritt standen zwölf modale Fragen — dieselbe Gestalt
    wie die 99 Fenster, die §15.7 begraben hat. Eine falsche Bindung eines
    Merkmals, das weder eine Passung noch eine Operation beim Namen nennt,
    könnte nichts brechen; also wird nicht gefragt und nicht geraten,
    sondern die Erkennung behält ihre eigenen Namen.
    """
    from importlib import import_module

    from app.core.bootstrap import load_operations
    from app.core.perceive.matching import MatchResult
    from app.core.scene.project import ProjectSources, new_project

    def always_ambiguous(
        old: dict[str, object],
        new: dict[str, object],
        centre: object,
        diagonal: float,
        old_centre: object = None,
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> MatchResult:
        if not old or len(new) < 2:
            return MatchResult()
        return MatchResult(ambiguous={next(iter(old)): tuple(new)[:2]})

    monkeypatch.setattr(import_module("app.core.scene.evaluate"), "match", always_ambiguous)

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Aufbau",
        [
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 30.0}),
            OperationDraft(op="hollow_object", inputs=("obj_1",), params={"wall": 2.0}),
            OperationDraft(op="compensate_first_layer", inputs=("obj_1",), params={}),
        ],
    )

    def nobody(question: str, choices: list[str]) -> str:
        raise AssertionError(f"ohne Verweis darf keine Frage entstehen: {question}")

    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=nobody)

    assert result.complete, [str(f.message) for f in result.scene.report.findings]


def test_a_finding_learns_which_body_it_belongs_to(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    """Wo die Operation die Kennung nicht kennt, trägt die Auswertung sie nach.

    ``ingest.not_watertight`` ist der Fall, an dem es auffiel: Der Befund
    entsteht im Loader, der auf einem Netz arbeitet, und die Kennungen vergibt
    der Stapel (§11) — selbst die ``load``-Operation sieht sie nicht, ihre
    Ausgaben tragen ``id=""``. Ohne Kennung fiel die Handlung am Befund
    („Reparieren", „Stellen zeigen") über ``_object_of`` auf die *Auswahl*
    zurück, also auf eine Vermutung.

    Hier ist beides bekannt, und ``make_object`` gibt seinen Befund seit je
    ohne Kennung zurück — wie die meisten.
    """
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])
    result = evaluate(document, profile, registry=registry)

    findings = result.scene.report.findings
    assert findings, "ohne Befund prüft das hier nichts"
    for entry in findings:
        assert entry.object_id == "obj_1", entry.code
        assert entry.object_id in result.scene.objects


def test_a_finding_of_two_bodies_stays_silent_about_which(
    history: History, document: Document, profile: Profile
) -> None:
    """Bei mehreren Ausgaben wird nicht geraten (Regel 21).

    Eine Baugruppe kommt als mehrere Körper an, und der Befund gehört dann zu
    einem davon — zu welchem, weiß hier niemand. Eine Kennung einzutragen wäre
    eine Zuordnung, die sich nicht belegen lässt, und die Handlung daran griffe
    den falschen Körper.
    """
    own = Registry()

    @register_op(
        name="two_with_a_finding",
        title=_("Zwei mit Befund"),
        category="scene",
        params=EmptyParams,
        consumes=0,
        produces=2,
        doc=_("Testversion."),
        registry=own,
    )
    def two(ctx: OpContext) -> OpResult:
        body = SceneObject(id="", name="Teil", mesh=_mesh(10.0))
        return OpResult(
            outputs=[body, dataclasses.replace(body, name="Teil B")],
            findings=[Finding(code="test.both", severity="warning", message=_("Zwei."))],
        )

    History(document, own).apply(_("Anlegen"), [OperationDraft(op="two_with_a_finding")])
    result = evaluate(document, profile, registry=own)

    assert len(result.scene.objects) == 2
    entry = next(item for item in result.scene.report.findings if item.code == "test.both")
    assert entry.object_id is None, "zu welchem der beiden? — das weiß hier niemand"
    assert entry.op_id == 1, "die Operation steht trotzdem dabei"


# --- Was ein späterer Schritt behoben hat, warnt nicht mehr (§17.3) -------------


def _finding(code: str, severity: str, op_id: int | None, object_id: str = "obj_1") -> Finding:
    return Finding(code=code, severity=severity, message=code, op_id=op_id, object_id=object_id)


def test_a_warning_that_a_later_step_fixed_is_dropped() -> None:
    """„Weg 3" begrüßte mit drei Warnungen, zwei davon längst erledigt.

    „Das Modell ist nicht geschlossen. „Reparieren" schließt die offenen
    Stellen." stand über „Offene Stellen wurden geschlossen." — für den, der
    die Herkunft nicht Zeile für Zeile mitliest, ein Widerspruch. Gestrichen
    und nicht herabgestuft: Der Satz steht im Präsens und beschreibt einen
    Zustand, den es nicht mehr gibt.
    """
    from app.core.scene.evaluate import _without_settled

    kept = _without_settled(
        [
            _finding("ingest.not_watertight", "warning", 1),
            _finding("repair.holes_filled", "info", 3),
        ]
    )

    assert [entry.code for entry in kept] == ["repair.holes_filled"]


def test_resolved_intersections_settle_the_load_note_that_offered_it() -> None:
    """„… von denen manche ineinanderstecken“ geht, sobald ein späterer Schritt aufgelöst hat.

    Am Bohrmaschinenhalter (69 Teile) blieb die Zeile nach *Überschneidungen
    auflösen* stehen, samt Knopf, über „Überschneidungen wurden aufgelöst.“ —
    der Körper hat danach weiter viele Teile, also griff die Einteiligkeit nicht
    (Durchsicht 0.5.1). Die Fassung ohne Überschneidung sagt etwas anderes und
    bleibt; sie bietet die Auflösung nicht an.
    """
    import dataclasses

    from app.core.errors import RESOLVE_INTERSECTIONS, SPLIT_BODIES
    from app.core.scene.evaluate import _without_settled

    crossing = dataclasses.replace(
        _finding("ingest.multiple_components", "info", 1),
        suggestions=(RESOLVE_INTERSECTIONS, SPLIT_BODIES),
    )
    plain = dataclasses.replace(
        _finding("ingest.multiple_components", "info", 1), suggestions=(SPLIT_BODIES,)
    )
    resolved = _finding("repair.self_intersections", "info", 2)

    assert [e.code for e in _without_settled([crossing, resolved])] == ["repair.self_intersections"]
    assert [e.code for e in _without_settled([plain, resolved])] == [
        "ingest.multiple_components",
        "repair.self_intersections",
    ], "die Fassung ohne Überschneidung bleibt"
    earlier = _finding("repair.self_intersections", "info", 0)
    assert crossing in _without_settled([earlier, crossing]), "nur ein späterer Schritt hebt auf"
    other = dataclasses.replace(resolved, object_id="obj_9")
    assert crossing in _without_settled([crossing, other]), "nur am selben Körper"


def test_a_decimation_that_stays_too_large_does_not_settle_the_warning() -> None:
    """Der Grenzfall des jüngsten Eintrags in ``SETTLED_BY``.

    „Zu fein für die Merkmalserkennung" wird von ``mesh.deviation`` aufgehoben,
    also von einer Dezimierung. Nur: Eine Dezimierung, die *nicht* unter die
    Grenze bringt — von 1,3 Mio. auf 400 000 zum Beispiel —, hebt gar nichts
    auf. Ein Streichen wäre dort ein falsches Versprechen: Der Körper hat immer
    noch keine Merkmale, und der Bericht schwiege darüber.

    Er tut es nicht, und der Grund liegt nicht in ``SETTLED_BY``, sondern in
    der Auswertung: Sie prüft die Größe nach **jeder** Operation, also steht
    nach dem Dezimieren ein *frischer* Befund da — und hinter dem kommt kein
    Heiler mehr. Der alte wird gestrichen, der neue bleibt. An der ganzen Kette
    nachgemessen (1,3 Mio. → 400 000: `perceive.too_large` steht weiter im
    Bericht); hier steht der Mechanismus dahinter.
    """
    from app.core.scene.evaluate import _without_settled

    kept = _without_settled(
        [
            _finding("perceive.too_large", "info", 1),
            _finding("mesh.deviation", "info", 2),
            # Nach dem Dezimieren gemessen und weiter zu fein
            _finding("perceive.too_large", "info", 2),
        ]
    )

    codes = [entry.code for entry in kept]
    assert codes.count("perceive.too_large") == 1, (
        f"der frische Befund muss stehen bleiben, der alte gehen: {codes}"
    )
    assert [entry.op_id for entry in kept if entry.code == "perceive.too_large"] == [2], (
        "gestrichen wurde der falsche von beiden"
    )


def test_a_decimation_below_the_limit_settles_the_warning() -> None:
    """Und der Normalfall: Wer unter die Grenze kommt, hat kein Thema mehr.

    Die Kette des Erzeugers lädt, repariert und dezimiert in einem Zug. Ohne
    diesen Eintrag stand am Ende „zu fein für die Merkmalserkennung" über einem
    Körper, dessen Merkmale gerade erkannt worden waren.
    """
    from app.core.scene.evaluate import _without_settled

    kept = _without_settled(
        [
            _finding("perceive.too_large", "info", 1),
            _finding("mesh.deviation", "info", 3),
        ]
    )

    assert [entry.code for entry in kept] == ["mesh.deviation"]


def test_the_load_advice_goes_once_the_chain_has_decimated() -> None:
    """Der Rat vom Laden verschwindet, wenn dieselbe Kette ihn befolgt hat.

    Nach einem Weg-3-Erzeugungslauf stand ``ingest.very_large`` mit dem Rat
    „‚Dreiecke verringern' hilft" im Bericht — und ``decimate_mesh`` war der
    vierte Schritt desselben Stapels, das Objekt längst bei 150 000 Dreiecken
    (Register, 30.08.2026). Der Kunde las einen Handlungsvorschlag für etwas,
    das die Anwendung im selben Zug getan hatte — muss er raten, ob er noch
    klicken soll, ist es falsch. Dieselbe Entscheidung wie bei
    ``perceive.too_large``: gestrichen, nicht herabgestuft.
    """
    from app.core.scene.evaluate import _without_settled

    kept = _without_settled(
        [
            _finding("ingest.very_large", "warning", 1),
            _finding("mesh.deviation", "info", 4),
        ]
    )

    assert [entry.code for entry in kept] == ["mesh.deviation"]


def test_an_insufficient_decimation_keeps_the_fresh_size_finding() -> None:
    """Und wer über der Erkennungsgrenze bleibt, verliert die Auskunft nicht.

    Eine Dezimierung von 614 000 auf 450 000 streicht den Lade-Rat — der
    beschrieb den Zustand vor ihr —, aber die Auswertung misst nach jeder
    Operation, und der frische ``perceive.too_large`` am Dezimier-Schritt
    trägt die Geschichte weiter: hinter ihm kommt kein Heiler mehr. Die
    Lücke dazwischen (unter der Erkennungs-, über der Kartengrenze) ist
    entschieden: Die Analysekarten melden ihre Ablehnung beim Klick selbst,
    und ein halb erledigter Dauer-Rat kostet mehr Vertrauen, als er nützt.
    """
    from app.core.scene.evaluate import _without_settled

    kept = _without_settled(
        [
            _finding("ingest.very_large", "warning", 1),
            _finding("mesh.deviation", "info", 2),
            _finding("perceive.too_large", "info", 2),
        ]
    )

    codes = [entry.code for entry in kept]
    assert "ingest.very_large" not in codes, "der befolgte Rat gehört gestrichen"
    assert codes.count("perceive.too_large") == 1, "die frische Auskunft bleibt"


@pytest.mark.parametrize("value", [12.0, [1, 2], {"parts": [1, 2]}, _("Teil")])
def test_the_report_of_a_real_run_carries_each_sentence_once(
    document: Document, profile: Profile, value: Any
) -> None:
    """Und die Anwendung tut es auch, nicht nur die Funktion.

    Die drei Tests darunter rufen ``_without_repeats`` direkt auf und bleiben
    grün, wenn niemand sie in die Auswertung einhängt — gemessen: Ich habe die
    Zeile aus ``evaluate`` entfernt, und alle drei liefen weiter durch. Das ist
    die Testart „Anschluss" aus `AGENTS.md`: Was an genau einer Stelle
    eingelöst wird, wird an dieser Stelle geprüft.

    Zwei Operationen melden denselben Befund über denselben Körper, so wie es
    ein Modell über der Erkennungsgrenze bei jedem Schritt tut.
    """
    own = Registry()

    @register_op(
        name="always_complains",
        title=_("Meldet immer"),
        category="scene",
        params=EmptyParams,
        consumes=0,
        produces=1,
        doc=_("Testversion."),
        registry=own,
    )
    def first(ctx: OpContext) -> OpResult:
        return OpResult(
            outputs=[SceneObject(id="", name="Teil", mesh=_mesh(10.0))],
            findings=[
                Finding(
                    code="test.always",
                    severity="info",
                    message=_("Immer."),
                    values={"value": value},
                )
            ],
        )

    @register_op(
        name="complains_again",
        title=_("Meldet nochmal"),
        category="scene",
        params=EmptyParams,
        consumes=1,
        produces=1,
        doc=_("Testversion."),
        registry=own,
    )
    def again(ctx: OpContext) -> OpResult:
        return OpResult(
            outputs=[ctx.inputs[0]],
            findings=[
                Finding(
                    code="test.always",
                    severity="info",
                    message=_("Immer."),
                    object_id=ctx.inputs[0].id,
                    values={"value": value},
                )
            ],
        )

    history = History(document, own)
    history.apply(_("Anlegen"), [OperationDraft(op="always_complains")])
    body = document.ops[0].outputs[0]
    history.apply(_("Nochmal"), [OperationDraft(op="complains_again", inputs=(body,))])
    result = evaluate(document, profile, registry=own)

    same = [entry for entry in result.scene.report.findings if entry.code == "test.always"]
    assert len(same) == 1, (
        f"zweimal derselbe Satz über denselben Körper, einer bleibt: "
        f"{[(e.op_id, e.object_id) for e in same]}"
    )
    assert same[0].op_id == 2, "der letzte beschreibt den heutigen Zustand"


def test_the_same_sentence_about_the_same_body_stands_once() -> None:
    """Dreimal derselbe Satz sind für den Kunden drei Probleme.

    Gemessen am 27.08.2026 an einem erzeugten Modell mit 221 138 Dreiecken:
    Nach dem Einlesen stand „Für die Merkmalserkennung ist dieses Modell zu
    groß." einmal da, nach *Auf Maß bringen* und *Auf das Bett setzen*
    dreimal. Keine der beiden Operationen rührt die Dreieckszahl an — es ist
    dreimal dieselbe Zahl über denselben Körper.

    Behalten wird der **letzte**: Ein Prüfbericht beschreibt den Zustand, in
    dem die Szene jetzt ist, und der steht am Ende der Kette.
    """
    from app.core.scene.evaluate import _without_repeats

    kept = _without_repeats(
        [
            _finding("perceive.too_large", "info", 1),
            _finding("perceive.too_large", "info", 2),
            _finding("perceive.too_large", "info", 3),
        ]
    )

    assert len(kept) == 1, f"drei gleiche Sätze, einer bleibt: {[e.op_id for e in kept]}"
    assert kept[0].op_id == 3, "der letzte beschreibt den heutigen Zustand"


def test_two_bodies_keep_their_own_sentence() -> None:
    """Und zwei Körper mit demselben Problem sind zwei Probleme.

    Die Gegenprobe zum Test darüber: Ohne sie ließe sich das Entdoppeln auch
    dadurch bestehen, dass es je Code nur eine Zeile durchlässt — und dann
    verschwände die Warnung an dem Körper, den niemand angesehen hat.
    """
    from app.core.scene.evaluate import _without_repeats

    kept = _without_repeats(
        [
            _finding("perceive.too_large", "info", 1, object_id="obj_1"),
            _finding("perceive.too_large", "info", 1, object_id="obj_2"),
        ]
    )

    assert {entry.object_id for entry in kept} == {"obj_1", "obj_2"}


def test_a_changed_number_is_a_changed_sentence() -> None:
    """Ändert sich der Wert, sagen die beiden Befunde Verschiedenes.

    Der Fall ist der, in dem eine Dezimierung ihr Ziel nicht erreicht:
    ``SETTLED_BY`` hebt dort bewusst nichts auf, und zwei verschiedene
    Dreieckszahlen sind zwei verschiedene Aussagen. Wer nur nach dem Code
    entdoppelt, verliert die zweite und behauptet einen Zustand von vorhin.
    """
    from app.core.scene.evaluate import _without_repeats

    kept = _without_repeats(
        [
            Finding(
                code="perceive.too_large",
                severity="info",
                message="zu groß",
                op_id=1,
                object_id="obj_1",
                values={"triangles": 900_000},
            ),
            Finding(
                code="perceive.too_large",
                severity="info",
                message="zu groß",
                op_id=2,
                object_id="obj_1",
                values={"triangles": 400_000},
            ),
        ]
    )

    assert [entry.values["triangles"] for entry in kept] == [900_000, 400_000]


def test_an_earlier_repair_does_not_settle_a_later_import() -> None:
    """**Später** ist die ganze Bedingung.

    Ein Reparieren vor dem Einlesen des nächsten Modells hebt dessen Befunde
    nicht auf — sonst verschwände die Warnung an einem Körper, an dem nie
    jemand etwas repariert hat.
    """
    from app.core.scene.evaluate import _without_settled

    kept = _without_settled(
        [
            _finding("repair.holes_filled", "info", 1),
            _finding("ingest.not_watertight", "warning", 3),
        ]
    )

    assert [entry.code for entry in kept] == ["repair.holes_filled", "ingest.not_watertight"]


def test_a_repair_on_another_body_settles_nothing() -> None:
    """Und es muss derselbe Körper sein. Zwei Modelle in einer Szene teilen
    sich den Bericht, nicht ihre Löcher."""
    from app.core.scene.evaluate import _without_settled

    kept = _without_settled(
        [
            _finding("ingest.not_watertight", "warning", 1, "obj_1"),
            _finding("repair.holes_filled", "info", 3, "obj_2"),
        ]
    )

    assert [entry.code for entry in kept] == ["ingest.not_watertight", "repair.holes_filled"]


def test_findings_without_a_settling_partner_stay() -> None:
    """Die Regel greift nur, wo ein Paar dasteht — sonst bleibt alles."""
    from app.core.scene.evaluate import _without_settled

    findings = [
        _finding("ingest.not_watertight", "warning", 1),
        _finding("repair.welded", "info", 3),
    ]

    assert _without_settled(findings) == findings


def test_the_names_of_consumed_bodies_survive_a_cache_hit() -> None:
    """``object_names`` muss auch dann stehen, wenn nichts gerechnet wurde.

    Der zweite Lauf über denselben Stapel kommt aus dem Cache, und das ist der
    **häufige** Fall — jede Parameteränderung wertet neu aus, und alles über der
    geänderten Stelle liegt fertig da. Käme die Zuordnung nur beim echten
    Rechnen zustande, stünde im Prüfbericht wieder „obj_1", und zwar genau dann,
    wenn niemand mehr hinsieht.

    Der Cache-Zweig führt in dieselbe Ausgabeschleife wie das Rechnen; dieser
    Test hält das fest, damit ein Umbau dort nicht die Namen verliert.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge.profiles import make_profile
    from app.core.scene import History, OperationDraft, ResultCache
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    history = History(document)
    history.apply(
        "Dose",
        [
            OperationDraft(
                op="create_box",
                params={"width": 60.0, "depth": 40.0, "height": 30.0, "name": "Dose"},
            )
        ],
    )
    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=(document.ops[-1].outputs[0],),
                params={"wall": 3.0, "open_top": True},
            )
        ],
    )
    # Ein zweiter Körper, den das Abziehen wirklich verbraucht. Der Deckel
    # taugt dafür seit ``keeps_inputs`` nicht mehr: Er setzt die Dose fort und
    # legt den Deckel daneben, verbraucht also nichts — und ein Test über
    # verbrauchte Körper, der keinen verbraucht, prüft nichts.
    history.apply(
        "Werkzeug",
        [OperationDraft(op="create_cylinder", params={"diameter": 10.0, "name": "Werkzeug"})],
    )
    tool = document.ops[-1].outputs[0]
    history.apply(
        "Abziehen",
        [OperationDraft(op="subtract_objects", inputs=("obj_1", tool), params={})],
    )

    profile = make_profile("centauri-carbon-2", "petg")
    cache = ResultCache()
    sources = ProjectSources(project)

    first = evaluate(document, profile, sources=sources, cache=cache)
    second = evaluate(document, profile, sources=sources, cache=cache)

    assert tool not in second.scene.objects, "das Werkzeug ist im Abziehen aufgegangen"
    assert dict(second.object_names) == dict(first.object_names), (
        f"der Cache-Lauf kennt andere Namen: {dict(second.object_names)} "
        f"statt {dict(first.object_names)}"
    )
    assert second.object_names.get(tool) == "Werkzeug", (
        f"der verbrauchte Körper hat seinen Namen verloren: {dict(second.object_names)}"
    )


def test_two_projects_whose_first_source_has_the_same_name_do_not_share_a_result() -> None:
    """Der Schlüssel muss die **Quelle** kennen und nicht ihren Bezeichner.

    Gefunden am 22.08.2026 von solidon-17 beim Anschließen des Plattencaches:
    ``LoadParams.source`` ist eine ID, und **jedes** Projekt nennt seine erste
    Quelle ``src_1``. Der Operations-Hash nimmt die Parameter, also war der
    Schlüssel für zwei völlig verschiedene Dateien derselbe. Gedeckt hat es der
    Speichercache, weil er beim Öffnen geleert wird und eine Sitzung lang lebt —
    eine Ebene, die länger lebt, ist deshalb keine Erweiterung, sondern ein
    Prüfstand für die Schlüssel.
    """
    from pathlib import Path

    from app.core.bootstrap import load_operations
    from app.core.knowledge.profiles import make_profile
    from app.core.scene import History, OperationDraft, ResultCache
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    profile = make_profile("centauri-carbon-2", "petg")
    cache = ResultCache()

    def loaded(filename: str) -> tuple[object, object]:
        project = new_project("centauri-carbon-2", "petg")
        project.document.sources["src_1"] = Source(
            id="src_1", kind="import", path=f"sources/{filename}", sha256=""
        )
        project.sources["src_1"] = (meshes / filename).read_bytes()
        History(project.document).apply(
            "Import", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
        )
        result = evaluate(project.document, profile, sources=ProjectSources(project), cache=cache)
        body = next(iter(result.scene.objects.values()))
        return body.name, body.mesh.triangle_count

    first = loaded("cube_clean.stl")
    second = loaded("plate_holes.stl")

    assert first != second, f"das zweite Projekt bekam das Ergebnis des ersten: {first} == {second}"


def test_a_result_that_came_from_a_question_stays_out_of_the_long_lived_cache() -> None:
    """§15.7, bis sie umgesetzt ist: Der Cache speichert nur, was eine reine
    Funktion des Dokuments ist (§15.1).

    Hat eine Operation unterwegs gefragt, steht die Antwort nirgends im
    Dokument — auf der Platte würde daraus stillschweigend eine Annahme, und ob
    der Nutzer gefragt wird, hinge daran, ob eine Cache-Datei überlebt hat.
    Regel 21 sagt „nie stillschweigend raten"; das wäre manchmal raten und
    manchmal fragen, entschieden vom Dateisystem.

    Geprüft am **Wort**, nicht an einer Platte: Ob das Ergebnis am Ende in einer
    Datei landet, entscheidet die Cache-Ebene; ob die Auswertung es freigibt,
    entscheidet diese Zeile — und nur die ist hier zu Hause.
    """
    from pathlib import Path

    from app.core.bootstrap import load_operations
    from app.core.knowledge.profiles import make_profile
    from app.core.scene import History, OperationDraft
    from app.core.scene.cache import CachedResult
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    class Recorder:
        """Nimmt entgegen und merkt sich, was freigegeben wurde."""

        def __init__(self) -> None:
            self.written: list[bool] = []

        def get(self, key: str) -> CachedResult | None:
            return None

        def put(self, key: str, result: CachedResult, *, to_disk: bool = False) -> None:
            self.written.append(to_disk)

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    profile = make_profile("centauri-carbon-2", "petg")

    def run(filename: str) -> list[bool]:
        project = new_project("centauri-carbon-2", "petg")
        project.document.sources["src_1"] = Source(
            id="src_1", kind="import", path=f"sources/{filename}", sha256=""
        )
        project.sources["src_1"] = (meshes / filename).read_bytes()
        History(project.document).apply(
            "Import", [OperationDraft(op="load", params={"source": "src_1", "unit": "auto"})]
        )
        recorder = Recorder()
        evaluate(
            project.document,
            profile,
            sources=ProjectSources(project),
            cache=recorder,  # type: ignore[arg-type]
            ask=lambda question, choices: choices[0],
        )
        return recorder.written

    # `cube_clean.stl` ist eindeutig Millimeter — keine Rückfrage, also darf es
    # über die Sitzung hinaus. Zwei Einträge, weil ``unit: auto`` beantwortet
    # wird: einer unter dem Schlüssel dieses Laufs, einer unter dem, den die
    # festgehaltene Antwort beim nächsten Lauf erzeugt — beide mit derselben
    # Herkunftsregel.
    assert run("cube_clean.stl") == [True, True]
    # `bracket_inch.stl` ist zwischen Zoll und Zentimeter mehrdeutig und fragt.
    assert run("bracket_inch.stl") == [False, False], (
        "ein Ergebnis, für das gefragt wurde, darf nicht über die Sitzung hinaus"
    )


def _plate_project():
    """Ein Projekt mit der Lochplatte, geladen und ausgewertet — mit Register."""
    from pathlib import Path

    from app.core.bootstrap import load_operations
    from app.core.knowledge.profiles import make_profile
    from app.core.scene import History, OperationDraft, ResultCache
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    profile = make_profile("centauri-carbon-2", "petg")
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (meshes / "plate_holes.stl").read_bytes()
    history = History(project.document)
    history.apply("Import", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    cache = ResultCache()
    sources = ProjectSources(project)
    first = evaluate(project.document, profile, sources=sources, cache=cache)
    return project, history, profile, cache, sources, first


def _detections(monkeypatch) -> list[int]:
    """Zählt, wie oft die Erkennung wirklich rechnet — am Kern der Facettenfrage."""
    from importlib import import_module

    features = import_module("app.core.perceive.features")
    runs: list[int] = []
    original = features._large_facet_faces

    def counted(*args, **kwargs):
        runs.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(features, "_large_facet_faces", counted)
    return runs


def test_a_preview_does_not_detect_features_nobody_reads(monkeypatch) -> None:
    """``detect_features=False``: Der geänderte Körper wird nicht neu erkannt.

    Die Live-Vorschau des Dialogs zeigt Geometrie und Differenz. An 204 000
    Dreiecken kostete die Erkennung je getippter Zahl 1,1 der 2,2 Sekunden
    (gemessen am 22.09.2026) — für Merkmale, die kein Bild zeigt und die
    beim Übernehmen ohnehin neu entstehen.
    """
    from app.core.perceive.features import forget_cache
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate

    project, history, profile, cache, sources, first = _plate_project()
    body = project.document.ops[0].outputs[0]
    assert len(first.scene.objects[body].features) == 10
    history.apply(
        "Bohren", [OperationDraft(op="drill_hole", inputs=(body,), params={"diameter": 6.0})]
    )
    forget_cache()
    runs = _detections(monkeypatch)

    preview = evaluate(
        project.document, profile, sources=sources, cache=cache, detect_features=False
    )

    assert preview.stopped_at is None
    assert runs == [], "die Vorschau rechnet keine Erkennung"
    drilled = preview.scene.objects[project.document.ops[-1].outputs[0]]
    assert all(feature.provenance != "detected" for feature in drilled.features.values()), (
        "ohne Erkennung trägt der gebohrte Körper keine erkannten Merkmale"
    )
    assert not [
        finding for finding in preview.scene.report.findings if finding.code == "perceive.orphaned"
    ], "ohne Zuordnung gibt es keine Waisen"

    # Was der Merker kennt, kommt trotzdem: die genaue Auswertung danach
    # erkennt, und eine zweite Vorschau desselben Netzes trägt ihre Merkmale.
    exact = evaluate(project.document, profile, sources=sources, cache=cache)
    computed = len(runs)
    assert computed >= 1, "die genaue Auswertung erkennt"
    again = evaluate(project.document, profile, sources=sources, cache=cache, detect_features=False)
    assert len(runs) == computed, "der Merker antwortet, nicht die Erkennung"
    assert set(again.scene.objects[project.document.ops[-1].outputs[0]].features) == set(
        exact.scene.objects[project.document.ops[-1].outputs[0]].features
    )


def test_a_preview_still_detects_where_a_later_step_needs_the_feature(monkeypatch) -> None:
    """Braucht ein Folgeschritt ein Merkmal des Körpers, wird trotzdem erkannt."""
    from app.core.perceive.features import forget_cache
    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate

    project, history, profile, cache, sources, _first = _plate_project()
    body = project.document.ops[0].outputs[0]
    history.apply(
        "Bohren", [OperationDraft(op="drill_hole", inputs=(body,), params={"diameter": 6.0})]
    )
    drilled_id = project.document.ops[-1].outputs[0]
    history.apply(
        "Bohrung ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=(drilled_id,),
                params={"at_feature": "hole_1", "diameter": 7.0},
            )
        ],
    )
    forget_cache()
    runs = _detections(monkeypatch)

    preview = evaluate(
        project.document, profile, sources=sources, cache=cache, detect_features=False
    )

    assert preview.stopped_at is None, "der Bezug auf hole_1 ist eingelöst"
    assert len(runs) >= 1, "der gebohrte Körper wurde erkannt, weil hole_1 gebraucht wird"


def test_coarse_steps_before_a_changed_step_rebuild_the_stack_without_gaps(monkeypatch) -> None:
    """Die grobe Vorschaustufe beim Ändern eines Schritts (§15.4, §2.8).

    Die Verkleinerung steht in der Dokumentkopie **vor** dem geänderten
    Schritt; die Schritte danach rücken auf, die Kopie bleibt lückenlos, und
    der geänderte Schritt rechnet auf dem groben Netz. Bis zum 22.09.2026 blieb
    dieser Weg genau: an 204 000 Dreiecken 1,1 s je getippter Zahl, mit der
    Stufe 40 ms ab der zweiten.
    """
    import copy

    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.ui import session as session_module

    project, history, profile, cache, sources, _first = _plate_project()
    body = project.document.ops[0].outputs[0]
    history.apply(
        "Bohren", [OperationDraft(op="drill_hole", inputs=(body,), params={"diameter": 6.0})]
    )
    drill = project.document.ops[-1]
    scene = evaluate(project.document, profile, sources=sources, cache=cache).scene
    original_triangles = scene.objects[body].mesh.triangle_count
    # Die Schwelle am kleinen Korpus erzwingen; das Ziel bleibt über dem
    # Boden, unter dem die Operation nichts anfasst.
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", 1)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", 600)

    working = copy.deepcopy(project.document)
    index = next(number for number, entry in enumerate(working.ops) if entry.id == drill.id)
    inserted = session_module._coarse_steps_before(working, index, scene)

    assert [entry.op for entry in inserted] == ["decimate_mesh"]
    assert inserted[0].inputs == (body,) and inserted[0].outputs == (body,)
    assert inserted[0].params["method"] == "fast", "die grobe Stufe nimmt den Anzeigeweg (RM-208)"
    ids = [int(entry.id) for entry in working.ops]
    assert ids == list(range(ids[0], ids[0] + len(ids))), "keine Lücke, keine Doppelung"
    assert working.ops[index].op == "decimate_mesh"
    assert working.ops[index + 1].op == "drill_hole"
    assert working.ops[index + 1].params == drill.params, "der Schritt selbst bleibt"
    # Das Original ist unberührt.
    assert [entry.op for entry in project.document.ops] == ["load", "drill_hole"]

    result = evaluate(working, profile, sources=sources, cache=cache, detect_features=False)
    assert result.stopped_at is None, "die Kopie rechnet mit dem eingefügten Schritt durch"
    assert set(result.completed) == {entry.id for entry in working.ops}
    assert result.scene.objects[body].mesh.triangle_count <= original_triangles


def test_the_coarse_preview_keeps_the_closed_kernel_body_of_a_figure() -> None:
    """Eine Figur, die der Kern nicht unter 50 000 bringt, bleibt grob geschlossen.

    Der Anzeigeweg nimmt den exakten Kern, solange er das Ziel erreicht, und
    sonst das Raster — und das Raster ist oft offen, eine Bohrung darauf
    scheitert, die Vorschau rechnet dann genau. Am Spiderman lag das Minimum
    der Kernkurve bei 122 952 Dreiecken, am Piratenschiff bei 64 468, am
    Eiffelturm bei 57 680; mit 50 000 als Ziel ging jede Zahl im Bohrdialog
    grob ins Leere und danach genau, 4 bis 54 s (gemessen am 26.09.2026,
    RM-212). Der Körper hier hat dieselbe Kurve: gewellt, 327 680 Dreiecke,
    beim Sehnenfehler rund 145 000, danach um 70 000 und wieder steigend.
    """
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.geom.mesh_ops import decimate_for_display
    from app.ui import session as session_module

    ball = trimesh.creation.icosphere(subdivisions=7, radius=20.0)
    points = np.array(ball.vertices, dtype=float)
    radius = np.linalg.norm(points, axis=1)
    around = np.arctan2(points[:, 1], points[:, 0])
    up = np.arcsin(points[:, 2] / radius)
    points *= ((radius + 0.3 * np.sin(50.0 * around) * np.cos(50.0 * up)) / radius)[:, None]
    figure = MeshData.of(trimesh.Trimesh(points, ball.faces, process=False))
    assert figure.is_watertight
    assert figure.triangle_count > session_module.COARSE_PREVIEW_ABOVE, "sonst keine grobe Stufe"

    before = decimate_for_display(figure, 50_000)
    assert not before.is_watertight, "mit dem alten Ziel ging die Figur ins Raster"

    params = session_module._coarse_params()
    assert params["method"] == "fast"
    coarse = decimate_for_display(figure, params["triangles"])

    assert coarse.is_watertight, "das Kernergebnis, nicht das Raster"
    assert coarse.triangle_count <= session_module.COARSE_PREVIEW_ABOVE
    assert coarse.triangle_count < figure.triangle_count / 2


def test_no_coarse_step_for_a_small_body_or_a_whole_face_texture(monkeypatch) -> None:
    import copy

    from app.core.scene import OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.ui import session as session_module

    project, history, profile, cache, sources, _first = _plate_project()
    body = project.document.ops[0].outputs[0]
    history.apply(
        "Bohren", [OperationDraft(op="drill_hole", inputs=(body,), params={"diameter": 6.0})]
    )
    scene = evaluate(project.document, profile, sources=sources, cache=cache).scene
    working = copy.deepcopy(project.document)
    # Unter der Schwelle: nichts.
    assert session_module._coarse_steps_before(working, 1, scene) == []
    assert [entry.op for entry in working.ops] == ["load", "drill_hole"]
    # Über der Schwelle, aber ein Texturschritt mit Flächenbezug: nichts.
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", 1)
    working.ops[1] = dataclasses.replace(
        working.ops[1], op="apply_texture", params={"coverage": "whole_face"}
    )
    assert session_module._coarse_steps_before(working, 1, scene) == []


def test_the_coarse_reduction_of_the_unchanged_input_outlives_a_superseded_preview(
    monkeypatch,
) -> None:
    """Nur die erste Vorschau trägt die Verkleinerung, auch wenn sie abgelöst wird (RM-208).

    Die Auswertung legt ihre Ergebnisse erst nach einem vollständigen
    Durchlauf in den Cache. Stand die Verkleinerung in der Auswertung der
    Vorschau, ging sie mit jeder abgelösten Anfrage verloren — an der
    Lochplatte mit 815 104 Dreiecken 27 bis 30 s Verkleinerung **je**
    Loslassen des Platzierungsgriffs (Bericht Ansicht, 23.09.2026). Seither
    rechnet sie vorab unter dem Signal der Vorbereitung und wird gemerkt;
    die Vorschau selbst findet sie im Cache.

    Hier wird die erste Vorschau abgelöst, sobald die Verkleinerung steht —
    genau der Augenblick, in dem der Kunde die nächste Zahl tippt.
    """
    from app.core.geom import mesh_ops
    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.ui import session as session_module
    from app.ui.session import Session

    session = Session()
    meshes = Path(__file__).parent / "data" / "meshes"
    assert session.import_model(meshes / "near_sphere_ellipsoid.stl", unit="mm")
    session.evaluate_now()
    body = next(iter(session.last_result.scene.objects))
    # Die Schwelle am kleinen Korpus erzwingen, wie die Nachbartests.
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", DECIMATE_FLOOR)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", DECIMATE_FLOOR)
    superseded = CancelSignal()
    reductions: list[int] = []
    original = mesh_ops.decimate_for_display

    def counted(mesh: Any, target: int, **kwargs: Any) -> Any:
        reductions.append(mesh.triangle_count)
        reduced = original(mesh, target, **kwargs)
        superseded.cancel()
        return reduced

    monkeypatch.setattr(mesh_ops, "decimate_for_display", counted)

    def drill(diameter: float) -> OperationDraft:
        return OperationDraft(
            op="drill_hole",
            params={"diameter": diameter, "x": 0.0, "y": 0.0, "z": 20.0, "depth": 0.0},
            inputs=(body,),
        )

    with pytest.raises(OperationCancelled):
        session._preview_outcome(
            [drill(5.0)], coarsened=[].append, cancelled=superseded, detect_features=False
        )
    assert len(reductions) == 1, "die erste Vorschau trägt die Verkleinerung"

    for diameter in (6.0, 7.0):
        seen: list[int] = []
        _scene, difference, reason = session._preview_outcome(
            [drill(diameter)], coarsened=seen.append, detect_features=False
        )
        assert reason == "" and difference is not None, reason
        assert seen, "grob gerechnet"
        assert difference.removed_volume > 0.0
    assert len(reductions) == 1, "jede weitere Zahl verkleinert nicht noch einmal"


def test_a_coarse_preview_the_kernel_refuses_is_computed_exactly(monkeypatch) -> None:
    """Scheitert der Kern am groben Netz, rechnet die Vorschau genau (RM-208).

    Gemessen am 23.09.2026 an drei von fünf Kundenmodellen (Eiffelturm,
    Voronoi-Spiderman, Piratenschiff): Die grobe Vorschau sagte „Auch die
    letzte Rückfallstufe hat kein brauchbares Ergebnis geliefert", die
    genaue hat ein Ergebnis. Der Halt lag am vorgeschauten Schritt und nicht
    an der Verkleinerung, und der Rückweg auf „genau" fragte nur nach der
    Verkleinerung. Hier weigert sich der Schritt an jedem verkleinerten Netz.
    """
    from app.core.errors import BooleanFailedError
    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.core.registry import REGISTRY
    from app.ui import session as session_module
    from app.ui.session import Session

    session = Session()
    meshes = Path(__file__).parent / "data" / "meshes"
    assert session.import_model(meshes / "near_sphere_ellipsoid.stl", unit="mm")
    result = session.evaluate_now()
    body, entry = next(iter(result.scene.objects.items()))
    full = entry.mesh.triangle_count
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", DECIMATE_FLOOR)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", DECIMATE_FLOOR)
    spec = REGISTRY.get("drill_hole")
    real = spec.fn

    def refuses_the_coarse_body(ctx: OpContext) -> Any:
        if ctx.inputs[0].mesh.triangle_count < full:
            raise BooleanFailedError(attempted=("direct", "welded"))
        return real(ctx)

    draft = OperationDraft(
        op="drill_hole",
        params={"diameter": 5.0, "x": 0.0, "y": 0.0, "z": 20.0, "depth": 0.0},
        inputs=(body,),
    )
    seen: list[int] = []
    object.__setattr__(spec, "fn", refuses_the_coarse_body)
    try:
        _scene, difference, reason = session._preview_outcome(
            [draft], coarsened=seen.append, detect_features=False
        )
    finally:
        object.__setattr__(spec, "fn", real)

    assert reason == "", "keine Absage, die nur am groben Netz gilt"
    assert difference is not None and difference.removed_volume > 0.0
    assert seen == [], 'genau gerechnet — das Band sagt nicht „grob"'


def _ellipsoid_session() -> tuple[Any, str, Any]:
    """Eine Sitzung mit dem Ellipsoid aus dem Korpus: 1 280 Dreiecke, geschlossen."""
    from app.ui.session import Session

    session = Session()
    meshes = Path(__file__).parent / "data" / "meshes"
    assert session.import_model(meshes / "near_sphere_ellipsoid.stl", unit="mm")
    result = session.evaluate_now()
    body, entry = next(iter(result.scene.objects.items()))
    return session, body, entry.mesh


def test_a_refinement_the_original_refuses_is_refused_before_anything_is_reduced(
    monkeypatch,
) -> None:
    """Die grobe Kopie verdeckte die Absage (RESTVERLAUF-04) — jetzt zählt die Vorschau am Original.

    Am Spielbrett aus ``F:\\3D Dateien`` zählte das Original bei 1 mm
    11,97 Mio. Dreiecke (zu fein), die verkleinerte Kopie 7,8 Mio.: Die
    Vorschau rechnete die Kopie, *Übernehmen* hielt danach an. Hier dasselbe
    im Kleinen — eine Decke zwischen der Zählung der Kopie und der des
    Originals. Die Absage kommt mit ihren Werten und Handlungen, bevor
    irgendetwas verkleinert oder gerechnet wird.
    """
    from app.core.errors import ValidationError
    from app.core.geom import mesh_ops
    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.ui import session as session_module

    session, body, mesh = _ellipsoid_session()
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", DECIMATE_FLOOR)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", DECIMATE_FLOOR)
    original = mesh_ops.estimated_triangles(mesh, 0.3, until_short=True)
    coarse = mesh_ops.decimate_for_display(mesh, DECIMATE_FLOOR)
    copied = mesh_ops.estimated_triangles(coarse, 0.3, until_short=True)
    ceiling = (original + copied) // 2
    assert copied < ceiling < original, "sonst prüft der Fall nicht, was die Kopie verdeckte"
    monkeypatch.setattr(mesh_ops, "MAX_REMESH_TRIANGLES", ceiling)

    def not_now(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("die Vorschau rechnet nicht, was schon abgesagt ist")

    monkeypatch.setattr(mesh_ops, "_split_conforming", not_now)
    seen: list[int] = []
    refused: list[object] = []
    draft = OperationDraft(op="remesh_mesh", params={"edge": 0.3}, inputs=(body,))

    _scene, difference, reason = session._preview_outcome(
        [draft], coarsened=seen.append, refused=refused.append, detect_features=False
    )

    assert difference is None
    assert seen == [], "keine grobe Kopie"
    assert len(refused) == 1 and isinstance(refused[0], ValidationError)
    error = refused[0]
    assert error.values["triangles"] == original
    assert error.values["reachable"] > 0.3
    assert "use_reachable" in {action.id for action in error.suggestions}
    assert reason == str(error.detail)


def test_a_refinement_past_the_preview_size_is_counted_and_not_computed(monkeypatch) -> None:
    """Die Vorschau von *Kanten verfeinern* an einem dichten Netz ist die Zahl (RESTVERLAUF-04).

    Am Spielwürfel (250 488 Dreiecke) teilte die grobe Vorschau auf 0,05 mm
    eine Kopie in 16 s auf 4,5 Mio. Dreiecke und stand danach über zehn
    Minuten im Booleschen Vergleich — für ein Bild derselben Form. Jetzt zählt
    sie am Original und rechnet nichts; die Zahl steht im Band.
    """
    from app.core.geom import mesh_ops
    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.ui import session as session_module
    from app.ui.session import TriangleCounts

    session, body, mesh = _ellipsoid_session()
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", DECIMATE_FLOOR)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", DECIMATE_FLOOR)

    def not_now(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("gezählt wird, nicht gerechnet")

    monkeypatch.setattr(mesh_ops, "remesh", not_now)
    seen: list[int] = []
    counts: list[object] = []
    draft = OperationDraft(op="remesh_mesh", params={"edge": 0.5}, inputs=(body,))
    started = time.perf_counter()

    _scene, difference, reason = session._preview_outcome(
        [draft], coarsened=seen.append, counted=counts.append, detect_features=False
    )

    assert time.perf_counter() - started < 5.0
    expected = mesh_ops.estimated_triangles(mesh, 0.5, until_short=True)
    assert counts == [TriangleCounts(mesh.triangle_count, expected, False, True)]
    assert expected > DECIMATE_FLOOR
    assert reason == ""
    assert difference is not None and not difference.entries
    assert seen == []


def test_a_small_refinement_shows_its_new_mesh_without_a_boolean_cut(monkeypatch) -> None:
    """Unter der Vorschaugröße rechnet der Schritt — und die Differenz ist das neue Netz."""
    from app.core.geom import difference as difference_module
    from app.ui.session import TriangleCounts

    session, body, mesh = _ellipsoid_session()

    def no_cut(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("kein Boolescher Vergleich an einer zugesagten Form")

    monkeypatch.setattr(difference_module, "compare", no_cut)
    counts: list[object] = []
    draft = OperationDraft(op="remesh_mesh", params={"edge": 1.0}, inputs=(body,))

    _scene, difference, reason = session._preview_outcome(
        [draft], coarsened=[].append, counted=counts.append, detect_features=False
    )

    assert reason == ""
    assert difference is not None
    after = difference.entries[body].retriangulated
    assert after is not None and after.triangle_count > mesh.triangle_count
    assert counts == [TriangleCounts(mesh.triangle_count, after.triangle_count)]


def test_reducing_a_large_body_is_previewed_on_the_body_itself(monkeypatch) -> None:
    """Keine Verkleinerung vor dem Verkleinern (RESTVERLAUF-04).

    Die grobe Kopie des Spielwürfels hatte 3 858 Dreiecke; *Dreiecke
    verringern* auf 60 000 oder 200 000 sagte an ihr „Die Fläche hat sich
    dabei kaum verschoben.", ohne etwas verringert zu haben — das Original hat
    250 488. Jetzt rechnet die Vorschau am Körper selbst und zeigt das neue
    Netz; der Vergleich zweier fast deckungsgleicher Häute entfällt (genau
    gerechnet 69 s, jetzt 0,8 s).
    """
    from app.core.geom import difference as difference_module
    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.ui import session as session_module

    session, body, mesh = _ellipsoid_session()
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", DECIMATE_FLOOR)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", DECIMATE_FLOOR)

    def no_cut(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("kein Boolescher Vergleich an einer Neuvernetzung")

    monkeypatch.setattr(difference_module, "compare", no_cut)
    seen: list[int] = []
    target = 700
    assert DECIMATE_FLOOR <= target < mesh.triangle_count
    draft = OperationDraft(op="decimate_mesh", params={"triangles": target}, inputs=(body,))

    _scene, difference, _reason = session._preview_outcome(
        [draft], coarsened=seen.append, detect_features=False
    )

    assert seen == [], "am Körper selbst, nicht an einer Kopie"
    assert difference is not None
    after = difference.entries[body].retriangulated
    assert after is not None and after.triangle_count < mesh.triangle_count
    codes = {finding.code for finding in difference.findings}
    assert "mesh.already_below_target" not in codes


def test_changing_a_refinement_counts_at_the_input_of_its_step(monkeypatch) -> None:
    """Beim Ändern eines Schritts ist das Original die Szene **vor** ihm.

    Die angezeigte Szene ist die danach — am schon verfeinerten Netz gezählt,
    hätte die Vorschau eine andere Zahl genannt als der Schritt beim Übernehmen.
    """
    from app.core.errors import ValidationError
    from app.core.geom import mesh_ops

    session, body, mesh = _ellipsoid_session()
    session.history.apply(
        "Kanten verfeinern",
        [OperationDraft(op="remesh_mesh", inputs=(body,), params={"edge": 1.0})],
    )
    session.evaluate_now()
    step = session.project.document.ops[-1].id
    original = mesh_ops.estimated_triangles(mesh, 0.3, until_short=True)
    monkeypatch.setattr(mesh_ops, "MAX_REMESH_TRIANGLES", original - 1)
    refused: list[object] = []

    _scene, difference, _reason = session._preview_outcome(
        [],
        change_op=step,
        change_values={"edge": 0.3},
        coarsened=[].append,
        refused=refused.append,
        detect_features=False,
    )

    assert difference is None
    assert len(refused) == 1 and isinstance(refused[0], ValidationError)
    assert refused[0].values["triangles"] == original, "am Eingang des Schritts gezählt"


def test_a_recorded_answer_does_not_cost_the_import_a_second_time() -> None:
    """§15.7 und §31: Die festgehaltene Antwort ändert den Schlüssel des
    Schritts — und das Ergebnis liegt schon darunter.

    Bis zum 22.09.2026 lief der Import nach ``record_answers`` ein zweites Mal:
    ``unit: auto`` wurde zu ``unit: mm``, der Schlüssel ein anderer, der Cache
    kannte nur den alten. Gemessen an 204 000 Dreiecken kostete der erste
    Folgeschritt 2,7 s Import, die längst gerechnet dastand — und auf der Platte
    lag ein Eintrag, nach dem beim Wiederöffnen nie wieder jemand fragte, weil
    dort die Antwort im Dokument steht und nicht die Frage.
    """
    from pathlib import Path

    from app.core.bootstrap import load_operations
    from app.core.knowledge.profiles import make_profile
    from app.core.scene import History, OperationDraft, ResultCache
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    profile = make_profile("centauri-carbon-2", "petg")
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (meshes / "plate_holes.stl").read_bytes()
    history = History(project.document)
    history.apply("Import", [OperationDraft(op="load", params={"source": "src_1", "unit": "auto"})])
    cache = ResultCache()
    sources = ProjectSources(project)

    first = evaluate(project.document, profile, sources=sources, cache=cache)
    assert first.answers, "ohne festgehaltene Antwort misst der Test nichts"
    assert history.record_answers(first.answers), "die Antwort muss den Schritt ändern"
    assert project.document.ops[0].params["unit"] == "mm"
    assert cache.statistics.misses == 1

    body = project.document.ops[0].outputs[0]
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(body,), params={"dx": 5.0})],
    )
    second = evaluate(project.document, profile, sources=sources, cache=cache)

    assert second.stopped_at is None
    assert cache.statistics.hits == 1, (
        "der Import kommt unter dem beantworteten Schlüssel aus dem Cache"
    )
    assert cache.statistics.misses == 2, "neu gerechnet wird nur das Verschieben"


def test_the_answer_to_a_question_lands_in_the_stack() -> None:
    """§15.7: Die Antwort gehört in die Parameter der fragenden Operation.

    Vorher stand sie nirgends — und weil §15.1 die Auswertung zu einer reinen
    Funktion aus Stack, Quellen, Parametern, Profilen und Startwerten macht,
    hieß das: Dieselbe Frage bei jeder Auswertung. Gemessen kostete eine
    Bauplatte mit 52 Teilen 99 modale Fenster für 7 Entscheidungen.

    Geprüft wird in zwei Schritten, weil die Sache zwei Hälften hat: Die
    Auswertung **meldet** die Antwort, der Verlauf **schreibt** sie. Eine der
    beiden allein wäre die halbe Reparatur, und die sieht aus wie die ganze.
    """
    from pathlib import Path

    from app.core.bootstrap import load_operations
    from app.core.knowledge.profiles import make_profile
    from app.core.scene import History, OperationDraft
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/bracket_inch.stl", sha256=""
    )
    project.sources["src_1"] = (meshes / "bracket_inch.stl").read_bytes()
    history = History(project.document)
    history.apply("Import", [OperationDraft(op="load", params={"source": "src_1", "unit": "auto"})])

    asked: list[str] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append(question)
        return "in"

    first = evaluate(
        project.document,
        make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
        ask=ask,
    )

    assert len(asked) == 1, "the unit of an inch file is ambiguous; it must be asked"
    assert first.answers == {1: {"unit": "in"}}, f"the answer must be reported: {first.answers}"

    assert history.record_answers(first.answers) is True
    assert project.document.ops[0].params["unit"] == "in"

    # Und die Gegenprobe, die den Sinn der Sache ausmacht: kein zweites Fenster.
    second = evaluate(
        project.document,
        make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
        ask=ask,
    )

    assert len(asked) == 1, f"the question came back although the answer is in the stack: {asked}"
    assert not second.answers, "nothing was decided this time, so nothing is reported"


# --- Die Antwort der Zuordnung (§15.7, §21.3) -----------------------------------


def _plate_with_two_close_holes() -> tuple[object, dict[str, object]]:
    """Eine Platte mit zwei Bohrungen, die dicht genug beieinander liegen, um
    eine Zuordnung mehrdeutig zu machen.

    Sechs Millimeter Abstand auf einer Diagonale von rund neunzig: Ein altes
    Merkmal in der Mitte hat zu beiden **dieselben** Kosten, und genau das ist
    der Fall, den §21.3 nicht raten lässt.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect

    plate = trimesh.creation.box(extents=(80.0, 40.0, 8.0))
    for x in (-3.0, 3.0):
        bore = trimesh.creation.cylinder(radius=1.0, height=20.0)
        bore.apply_translation((x, 0.0, 0.0))
        plate = trimesh.boolean.difference([plate, bore])
    mesh = MeshData.of(plate)
    holes = {name: f for name, f in detect(mesh).items() if f.kind == "hole"}
    return mesh, holes


def test_the_fingerprint_survives_a_renumbering() -> None:
    """Der Kern des Entwurfs: gespeichert wird ein Abdruck, kein Bezeichner.

    ``alt → neu`` wäre fragil — die Erkennung nummeriert beim nächsten Lauf
    womöglich anders, und dann zeigte die Antwort auf ein fremdes Merkmal. Aus
    „fragt zu oft" würde „nimmt stillschweigend das falsche", und das ist der
    schlechtere Fehler (Regel 21).
    """
    from app.core.perceive.matching import fingerprint, resolve

    mesh, holes = _plate_with_two_close_holes()
    centre, diagonal = mesh.bounds.centre, mesh.bounds.diagonal
    first, second = sorted(holes)

    saved = fingerprint(holes[first], centre, diagonal)

    # Dieselbe Geometrie, andere Namen — der Abdruck findet sie wieder.
    renamed = {"hole_7": holes[first], "hole_9": holes[second]}
    assert resolve(saved, ("hole_7", "hole_9"), renamed, centre, diagonal) == "hole_7"


def test_two_indistinguishable_candidates_are_asked_again() -> None:
    """Die wichtigere Hälfte von ``resolve``: ``None`` heißt „frag wieder".

    Der Rückfall braucht einen **Abstand**, nicht „am nächsten". Die Kandidaten
    waren mehrdeutig, *weil* sie sich gleichen; wer hier den nächstliegenden
    nimmt, entscheidet über einen Abstand, der kleiner ist als der zwischen
    ihnen — und rät genau dort, wo §21.3 das Fragen verlangt.
    """
    from app.core.perceive.matching import fingerprint, resolve

    mesh, holes = _plate_with_two_close_holes()
    centre, diagonal = mesh.bounds.centre, mesh.bounds.diagonal
    first, _second = sorted(holes)

    saved = fingerprint(holes[first], centre, diagonal)
    # Zweimal dasselbe Merkmal unter verschiedenen Namen: kein Abstand.
    twins = {"a": holes[first], "b": holes[first]}

    assert resolve(saved, ("a", "b"), twins, centre, diagonal) is None


def test_a_saved_answer_is_not_used_for_another_kind() -> None:
    """Eine Fläche ist keine Bohrung, auch wenn sie am selben Ort sitzt."""
    from app.core.perceive.matching import fingerprint, resolve
    from app.core.types import Feature

    mesh, holes = _plate_with_two_close_holes()
    centre, diagonal = mesh.bounds.centre, mesh.bounds.diagonal
    first = min(holes)
    saved = fingerprint(holes[first], centre, diagonal)

    face = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params=dict(holes[first].params),
    )

    assert resolve(saved, ("face_1",), {"face_1": face}, centre, diagonal) is None


def test_the_question_of_the_matcher_is_asked_once_and_then_never_again() -> None:
    """Die Abnahme aus §15.7: 99 Fenster für 7 Entscheidungen werden 7 und dann 0.

    Geprüft wird an der Stelle, an der die Frage entsteht — ``_with_features``
    —, und in beiden Hälften: Es wird **einmal** gefragt, die Antwort wird
    **gemeldet**, und mit ihr im Stapel kommt die Frage nicht wieder.
    """
    from app.core.perceive.match_records import group_key
    from app.core.scene.evaluate import _with_features
    from app.core.types import Feature, Operation, SceneObject

    mesh, _holes = _plate_with_two_close_holes()
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh)
    previous = {
        "pin_1": Feature(
            id="pin_1",
            kind="hole",
            provenance="generated",
            params={"centre": (0.0, 0.0, 4.0), "axis": (0.0, 0.0, 1.0), "diameter": 2.0},
        )
    }

    asked: list[str] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append(question)
        return choices[0]

    operation = Operation(id=1, op="thicken")
    recorded: dict[str, dict[str, object]] = {}
    # ``referenced`` ausdrücklich: Die Frage gilt nur Merkmalen, die das
    # Dokument beim Namen nennt — ``pin_1`` ist hier als verwiesen erklärt,
    # so wie es eine Passung oder ein ``at_feature`` täte.
    _with_features(
        entry, dict(previous), operation, ask, [], recorded=recorded, referenced={"pin_1"}
    )

    assert len(asked) == 1, "two candidates at the same cost must be asked about"
    key = group_key(entry.id, ("pin_1",))
    assert key in recorded, f"the answer must be reported: {recorded}"
    assert recorded[key]["candidates"][0]["fingerprint"]["kind"] == "hole"

    # Und die Gegenprobe, die den Sinn der Sache ausmacht: kein zweites Fenster.
    answered = dataclasses.replace(operation, matches=recorded)
    again: dict[str, dict[str, object]] = {}
    _with_features(entry, dict(previous), answered, ask, [], recorded=again, referenced={"pin_1"})

    assert len(asked) == 1, f"the question came back although the answer is in the stack: {asked}"
    assert not again, "nothing was decided this time, so nothing is reported"


def test_the_matcher_answer_lands_in_the_stack_beside_seed() -> None:
    """Geschrieben wird in ``matches`` und **nicht** in ``params``.

    Das Schema der Operation kennt den Schlüssel nicht, und ``validate`` wiese
    ihn zu Recht ab — es ist keine Eingabe der Operation, sondern die Antwort
    auf eine Frage, die *bei* ihr entstand. Der Präzedenzfall ist ``seed``.
    """
    from app.core.scene.project import new_project

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 20.0})],
    )

    abdruck = {"kind": "hole", "relative": [0.1, 0.0, 0.0], "axis": [0.0, 0.0, 1.0]}
    assert history.record_matches({1: {"legacy": {"pin_1": abdruck}}}) is True

    entry = project.document.ops[0]
    assert entry.matches["legacy"]["pin_1"] == abdruck
    assert "pin_1" not in entry.params, "an answer of the matcher is not an input"

    # Zweimal dasselbe schreiben ändert nichts — sonst gälte das Dokument nach
    # jeder Auswertung als geändert, ohne dass jemand etwas entschieden hat.
    assert history.record_matches({1: {"legacy": {"pin_1": abdruck}}}) is False


def test_a_recorded_match_survives_saving_and_reopening(tmp_path: Path) -> None:
    """Die Antwort ist erst dann einmal gegeben, wenn sie das Schließen übersteht (RM-024).

    ``Operation.matches`` wird serialisiert, und `record_matches` schreibt
    hinein — beides stand, und dazwischen fehlte der Nachweis. Ohne ihn wäre
    die Zusage aus §15.7 („einmal fragen, nie wieder") an die geöffnete
    Sitzung gebunden: Wer sein Projekt zumacht und morgen weiterarbeitet,
    bekäme dieselben Fenster noch einmal, und genau das waren die 99.

    Geprüft wird die runde Reise durch die Datei und nicht nur das Feld: Ein
    Abdruck ist eine verschachtelte Zuordnung mit Listen darin, und die
    Projektdatei kennt weder Tupel noch Numpy.
    """
    from app.core.scene.project import load, new_project, save

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 20.0})],
    )
    abdruck = {
        "kind": "hole",
        "relative": [0.1, -0.25, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "diameter": 4.2,
    }
    assert history.record_matches({1: {"legacy": {"pin_1": abdruck}}}) is True

    reopened = load(save(project, tmp_path / "zuordnung.p3d"))

    assert reopened.document.ops[0].matches == {"legacy": {"pin_1": abdruck}}, (
        "die Antwort hat die Datei nicht überstanden — die Frage käme wieder"
    )
    assert "pin_1" not in reopened.document.ops[0].params, "eine Antwort ist keine Eingabe"


# --- Übersetzbare Parameter (§4.1, Format 10) -----------------------------------


def test_a_marked_parameter_follows_the_language_and_the_hash_does_not() -> None:
    """Der Kern von ``Operation.translatable``, und beide Hälften in einem Lauf.

    **Die eine Hälfte ist der Gewinn:** Ein Objektname aus einem mitgelieferten
    Beispiel heißt für einen englischen Kunden „Sphere" und nicht „Kugel".

    **Die andere ist die Bedingung, unter der er zu haben ist:** Der Op-Hash
    darf sich dabei nicht ändern. Ein Cache-Schlüssel, der von der
    Anzeigesprache abhängt, wäre derselbe Fehler wie ein Exportdateiname, der
    mit ihr wandert — und genau diese Befürchtung hat den Punkt seit dem
    20.08.2026 aufgehalten. Sie trifft nicht zu, weil in ``resolved`` die
    Message-ID stehen bleibt und nur die Fassung für den Lauf aufgelöst wird.
    """
    import dataclasses

    from app.core.bootstrap import load_operations
    from app.core.knowledge.profiles import make_profile
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language

    load_operations()
    for language in ("en", "es"):
        install_language(language)

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_box",
                params={"width": 20.0, "depth": 20.0, "height": 20.0, "name": "Kugel"},
            )
        ],
    )
    # Der Vermerk: „name" trägt hier eine Message-ID, keinen getippten Text.
    project.document.ops[0] = dataclasses.replace(project.document.ops[0], translatable=("name",))

    before = get_language()
    names: dict[str, str] = {}
    hashes: dict[str, str] = {}
    try:
        for language in ("de", "en", "es"):
            set_language(language)
            result = evaluate(
                project.document,
                make_profile("centauri-carbon-2", "petg"),
                sources=ProjectSources(project),
            )
            entry = next(iter(result.scene.objects.values()))
            names[language] = str(entry.name)
            hashes[language] = next(iter(result.object_hashes.values()))
    finally:
        set_language(before)

    assert names["de"] == "Kugel"
    assert names["en"] == "Sphere", f"der Name folgt der Sprache: {names}"
    assert names["es"] == "Esfera", f"und zwar in jeder: {names}"
    assert len(set(hashes.values())) == 1, f"der Hash folgt ihr nicht: {hashes}"


def test_an_unmarked_parameter_stays_literal() -> None:
    """Ohne Vermerk bleibt ein Name wörtlich — der Normalfall.

    Was ein Nutzer selbst getippt hat, gehört ihm und wird nie übersetzt, auch
    wenn es zufällig wie eine Message-ID aussieht. Dieselbe Regel wie bei einem
    selbst getippten Transaktionstitel (``title_translatable``, §4.1).
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge.profiles import make_profile
    from app.core.scene.evaluate import evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language

    load_operations()
    install_language("en")

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_box",
                params={"width": 20.0, "depth": 20.0, "height": 20.0, "name": "Kugel"},
            )
        ],
    )
    assert project.document.ops[0].translatable == (), "kein Vermerk ist die Vorgabe"

    before = get_language()
    try:
        set_language("en")
        result = evaluate(
            project.document,
            make_profile("centauri-carbon-2", "petg"),
            sources=ProjectSources(project),
        )
    finally:
        set_language(before)

    entry = next(iter(result.scene.objects.values()))
    assert str(entry.name) == "Kugel", "ohne Vermerk wird nichts übersetzt"


def test_a_translatable_text_equals_its_message_id() -> None:
    """Der Docstring von ``TranslatableText`` versprach das, bevor es stimmte.

    Der erzeugte ``__eq__`` eines Dataclass vergleicht nur mit dem eigenen Typ,
    also war ``_("Quader") == "Quader"`` falsch — und der Hash verschieden dazu.
    Aufgefallen ist es, als Objektnamen übersetzbar wurden und ein Test
    ``entry.name == "Quader"`` fragte; im Bestand stehen neunundvierzig solcher
    Vergleiche.

    Verglichen wird die **Message-ID**, nicht die Übersetzung: Die wechselt mit
    der Sprache, und ein Vergleich, der davon abhinge, wäre in jeder zweiten
    Sprache falsch.
    """
    from app.i18n import TranslatableText, get_language, set_language
    from app.i18n.catalog import install_language

    text = TranslatableText("Quader")

    assert text == "Quader", "gleich seiner Message-ID"
    assert hash(text) == hash("Quader"), "und im selben Eimer"
    assert {text: 1}.get("Quader") == 1, "damit ein Nachschlagen mit beidem geht"
    assert text == TranslatableText("Quader")
    assert text != TranslatableText("Quader", "Menü"), "ein Kontext gehört zur Identität"

    # Und die Richtung, auf die es ankommt: Die Übersetzung ändert nichts.
    install_language("en")
    before = get_language()
    try:
        set_language("en")
        assert str(text) == "Box", "angezeigt wird übersetzt"
        assert text == "Quader", "verglichen wird die Message-ID"
        assert text != "Box", "und nicht die Übersetzung"
    finally:
        set_language(before)


def test_a_stopped_evaluation_says_why_in_the_log(caplog: pytest.LogCaptureFixture) -> None:
    """Die Nummer allein hilft niemandem — auch uns nicht.

    Im Kundenprotokoll vom 23.08.2026 steht ``evaluation stopped at op 10``
    **neunzehnmal** über sieben Minuten, und keine der Zeilen sagt, was
    schiefging. Der Grund war die ganze Zeit da: Alle sieben Stellen, die
    ``stopped_at`` setzen, hängen vorher einen Befund an, der ihn trägt — er
    landete nur im Prüfbericht und nicht im Protokoll.

    Geprüft wird über eine Operation, die auf ein Objekt zeigt, das es nicht
    gibt: Die Auswertung hält an (§15.2), und die Protokollzeile muss den Code
    des Befunds nennen.
    """
    from app.core.knowledge.profiles import make_profile
    from app.core.scene.project import new_project
    from app.core.types import Operation

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.ops.append(
        Operation(id=1, op="repair", inputs=("obj_99",), outputs=("obj_1",), params={})
    )

    with caplog.at_level(logging.WARNING, logger="app.core.scene.evaluate"):
        result = evaluate(document, make_profile("centauri-carbon-2", "petg"))

    assert result.stopped_at == 1
    zeilen = [r.getMessage() for r in caplog.records if "evaluation stopped" in r.getMessage()]
    assert zeilen, "keine Abbruchzeile im Protokoll"
    assert zeilen[0] != "evaluation stopped at op 1", "nennt nur die Nummer"
    assert "." in zeilen[0].split("op 1: ")[-1], f"nennt keinen Befundcode: {zeilen[0]}"


def test_an_unexpected_error_leaves_its_traceback_and_cause_in_the_log(
    registry: Registry, caplog: pytest.LogCaptureFixture
) -> None:
    """Ein Programmfehler in einer Operation nennt im Protokoll Ursache und Traceback.

    Der Kundenbericht S-20260906-9ca141 (0.3.4, 06.09.2026) trug zweimal
    ``op.load.InternalError: Im Programm ist ein unerwarteter Fehler
    aufgetreten.`` und sonst nichts — Titel im Protokoll, Titel im Bericht,
    die Ausnahmeart in ``values`` versteckt, der Traceback nirgends. Mit dem
    Bericht in der Hand war der Fehler nicht zu finden.

    Geprüft an einer Operation, die einen ``TypeError`` wirft: Der Befund
    trägt Ausnahmeart und -text, die Abbruchzeile nennt sie, und davor steht
    der Traceback als Fehlerzeile — die drei Dinge, die ein Bericht braucht.
    """
    from app.core.knowledge.profiles import make_profile
    from app.core.scene.project import new_project
    from app.core.types import Operation

    @register_op(
        name="blow_up",
        title=_("Explodieren"),
        category="scene",
        params=EmptyParams,
        consumes=0,
        produces=1,
        doc=_("Testversion."),
        registry=registry,
    )
    def blow_up(ctx: OpContext) -> OpResult:
        raise TypeError("bounds() got an unexpected keyword argument 'tight'")

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.ops.append(Operation(id=1, op="blow_up", inputs=(), outputs=("obj_1",), params={}))

    with caplog.at_level(logging.WARNING, logger="app.core.scene.evaluate"):
        result = evaluate(document, make_profile("centauri-carbon-2", "petg"), registry=registry)

    assert result.stopped_at == 1
    finding = next(
        entry for entry in result.scene.report.findings if entry.code == "op.blow_up.InternalError"
    )
    cause = "TypeError: bounds() got an unexpected keyword argument 'tight'"
    assert finding.values["detail"] == cause

    stopped = [r.getMessage() for r in caplog.records if "evaluation stopped" in r.getMessage()]
    assert stopped and cause in stopped[0], f"die Abbruchzeile nennt den Grund nicht: {stopped}"

    errors = [r for r in caplog.records if r.levelno == logging.ERROR and r.exc_info]
    assert errors, "kein Traceback im Protokoll"
    assert "blow_up" in caplog.text and cause in caplog.text, (
        "der Traceback nennt weder die Operation noch die Ausnahme"
    )


def test_an_unexpected_error_in_the_recognition_stops_at_its_step(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Ein Programmfehler der Merkmalserkennung hält am Schritt an wie einer der Operation.

    Gemessen in der Durchsicht 0.5.0 am Puppenhausbett (1,2 Millionen
    Dreiecke, Weg 3): ``detect`` warf einen ``MemoryError``, und der flog aus
    ``evaluate`` heraus — gefangen war um ``_with_features`` nur ``AppError``.
    Im Fenster endete die Auswertung damit als abgestürzter Arbeiter, ohne
    Prüfbericht und ohne den Schritt, an dem es lag; die Operation selbst hat
    diesen Fang seit dem Gesamtreview.

    **Der Speicherfehler selbst hat am Ladeschritt seit dem 24.09.2026 einen
    eigenen Rückweg** (das Modell lädt ohne Vollerkennung,
    ``test_running_out_of_memory_costs_the_recognition_not_the_import``).
    Geprüft wird hier der allgemeine Fang, also mit einem Fehler, für den es
    keinen Rückweg gibt.
    """
    from importlib import import_module

    from app.core.bootstrap import load_operations
    from app.core.knowledge.profiles import make_profile
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    # Das Modul, nicht die gleichnamige Funktion aus ``app.core.scene``.
    evaluate_module = import_module("app.core.scene.evaluate")

    def exhausted(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("kein Speicher für die Erkennung")

    load_operations()
    monkeypatch.setattr(evaluate_module, "detect", exhausted)
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (
        Path(__file__).parent / "data" / "meshes" / "plate_holes.stl"
    ).read_bytes()
    History(project.document).apply(
        "Import", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )

    with caplog.at_level(logging.WARNING, logger="app.core.scene.evaluate"):
        result = evaluate(
            project.document,
            make_profile("centauri-carbon-2", "petg"),
            sources=ProjectSources(project),
        )

    assert result.stopped_at == 1
    finding = next(
        entry for entry in result.scene.report.findings if entry.code == "op.load.InternalError"
    )
    assert finding.values["detail"] == "RuntimeError: kein Speicher für die Erkennung"
    assert any(r.levelno == logging.ERROR and r.exc_info for r in caplog.records), (
        "kein Traceback im Protokoll"
    )


def test_the_log_reason_carries_the_numbers_not_the_placeholders() -> None:
    """Der Abbruchgrund nennt die Zahlen — sonst hilft er dem Support wieder nicht.

    Der Nachbartest darüber hat die Zeile überhaupt erst sprechend gemacht.
    Nur trägt eine Befundmeldung ihre Werte getrennt von ihrer Vorlage, und
    die Zeile legte allein die Vorlage ab: Aus „12 von 400 offenen Kanten
    geschlossen" wurde ``{closed} von {total} offenen Kanten geschlossen`` —
    also gerade das weg, wonach jemand im Protokoll sucht.

    **Die Message-ID bleibt richtig**, nur eben mit eingesetzten Werten: Ein
    Protokoll aus Portugal muss der Support lesen können, deshalb steht dort
    weiter die Quellsprache und nicht ``str()``. Genau das leistet
    :func:`app.i18n.source_text`, und dieselbe Funktion löst es seit langem
    für Dateinamen (aus ``Slot {number}`` wurde sonst ``Slot number.stl``).
    """
    from app.core.scene.evaluate import _why_it_stopped

    grund = _why_it_stopped(
        [
            Finding(
                code="repair.holes_filled",
                severity="info",
                message=_(
                    "{closed} von {total} offenen Kanten geschlossen.",
                    closed=12,
                    total=400,
                ),
                op_id=3,
            )
        ],
        stopped_at=3,
    )

    assert "{closed}" not in grund and "{total}" not in grund, (
        f"die Protokollzeile zeigt Platzhalter statt Zahlen: {grund!r}"
    )
    assert grund == "repair.holes_filled: 12 von 400 offenen Kanten geschlossen.", grund


def test_an_expression_that_breaks_its_own_bounds_is_reported(
    history: History, document: Document, profile: Profile, registry: Registry
) -> None:
    """Grenzen gelten auch für Ausdrücke (Gesamtreview B-15).

    ``maximum=60`` mit ``=@a*10`` ergab 600, und niemand sagte etwas. Die
    Eingabe lehnt der Dialog ab (§10); was aus Ausdrücken folgt oder aus
    einer von Hand bearbeiteten Datei kommt, sieht erst die Auswertung — und
    die sagt es als Befund, statt anzuhalten: Die Lage ist rücknehmbar und
    korrigierbar, ein Halt machte eine Sackgasse daraus (Regel 19).
    """
    document.parameters["a"] = Parameter(name="a", value=60.0)
    document.parameters["scaled"] = Parameter(
        name="scaled", value=0.0, expression="=@a*10", minimum=10.0, maximum=60.0
    )
    history.apply(_("Anlegen"), [OperationDraft(op="make_object")])

    result = evaluate(document, profile, registry=registry)

    assert result.complete, "der Befund hält nichts an"
    broken = [f for f in result.scene.report.findings if f.code == "parameter.out_of_range"]
    assert len(broken) == 1, "eine Verletzung, ein Befund"
    assert broken[0].values["parameter"] == "scaled"
    assert broken[0].values["actual"] == pytest.approx(600.0)
    assert broken[0].values["maximum"] == pytest.approx(60.0)

    # Und die Untergrenze, die eigene Hälfte der Prüfung: ``minimum`` und
    # ``maximum`` sind in der Auswertung zwei Zweige, und geprüft war bisher
    # nur der obere — der untere hätte wegfallen können, ohne dass ein Lauf
    # rot wird.
    document.parameters["scaled"] = Parameter(
        name="scaled", value=0.0, expression="=@a/60", minimum=10.0, maximum=60.0
    )
    below = evaluate(document, profile, registry=registry)
    zu_klein = [f for f in below.scene.report.findings if f.code == "parameter.out_of_range"]
    assert len(zu_klein) == 1, "auch die Untergrenze ist eine Zusage"
    assert zu_klein[0].values["parameter"] == "scaled"
    assert zu_klein[0].values["actual"] == pytest.approx(1.0)
    assert zu_klein[0].values["minimum"] == pytest.approx(10.0)

    # Und die Gegenrichtung: ein Ausdruck innerhalb seiner Grenzen schweigt.
    document.parameters["scaled"] = Parameter(
        name="scaled", value=0.0, expression="=@a/2", minimum=10.0, maximum=60.0
    )
    quiet = evaluate(document, profile, registry=registry)
    assert not [f for f in quiet.scene.report.findings if f.code == "parameter.out_of_range"]


def test_a_part_gives_its_detected_features_the_step_that_made_them(profile: Profile) -> None:
    """Was ein Baustein an erkennbarer Geometrie mitbringt, kennt seinen Schritt.

    Ein eingesetzter Baustein bringt Verrundungen, Kegel und Flächen mit, die
    ``detect`` findet — sie gelten damit als „erkannt" und trugen bis zum
    25.08.2026 keinen Erzeuger. Von ihnen führte kein Weg zurück: „Diesen
    Schritt ändern" (§21.2) hängt an ``created_by``, und der Kunde sieht sechs
    Verrundungen, von denen keine den Baustein nennt (Befund Robert, am
    Bildschirm gesehen).

    Der Riegel heißt ``touches_features`` — ein Registerfeld, das seit je
    dastand und bis dahin keinen Leser hatte.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Aufbau",
        [
            OperationDraft(op="create_box", params={"width": 120.0, "depth": 40.0, "height": 10.0}),
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    faces = [
        feature_id
        for entry in result.scene.objects.values()
        for feature_id, feature in entry.features.items()
        if feature.kind == "face"
    ]
    assert faces, "ein Quader hat Flächen — sonst prüft der Test nichts"

    History(project.document).apply(
        "Haken",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"system": "skadis", "count": 2, "at_feature": faces[0]},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    step = next(entry.id for entry in project.document.ops if entry.op == "insert_pegboard_hook")
    detected = [
        feature
        for entry in result.scene.objects.values()
        for feature in entry.features.values()
        if feature.provenance != "generated"
    ]
    from_part = [feature for feature in detected if feature.created_by == step]

    assert from_part, "kein erkanntes Merkmal trägt den Baustein-Schritt"
    assert any(feature.kind == "fillet" for feature in from_part), (
        "die verrundeten Zapfen des Einhängers gehören dazu"
    )


def test_loading_a_model_gives_no_detected_feature_an_originator(profile: Profile) -> None:
    """Und der Riegel dagegen: Nach ``load`` ist **jedes** erkannte Merkmal neu.

    Ohne ``touches_features`` trüge jede Bohrung jedes importierten Modells den
    Lade-Schritt, und „Diesen Schritt ändern" öffnete den Lade-Dialog — der
    falsche Dialog, nur tausendfach und im häufigsten Weg (Messung
    3d-druck-61). Dasselbe gälte nach *Dreiecke verringern*, sobald das Netz
    unter die Erkennungsgrenze fällt und der ganze Bestand „neu" auftaucht.
    """
    from pathlib import Path

    from app.core.bootstrap import load_operations
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    meshes = Path(__file__).parent / "data" / "meshes"
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (meshes / "plate_holes.stl").read_bytes()
    History(project.document).apply(
        "Laden",
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    features = [
        (feature_id, feature)
        for entry in result.scene.objects.values()
        for feature_id, feature in entry.features.items()
    ]

    assert features, "die Platte trägt Merkmale — sonst prüft der Test nichts"
    assert all(feature.created_by is None for _name, feature in features), {
        name: feature.created_by for name, feature in features if feature.created_by is not None
    }


def test_an_operation_that_declares_nothing_gives_no_originator(profile: Profile) -> None:
    """Der erste Riegel allein, ohne den zweiten: ``touches_features``.

    Aushöhlen lässt neue Innenflächen entstehen, die ``detect`` findet — und
    trägt das Flag nicht. Ohne diesen Riegel bekämen sie den Aushöhl-Schritt
    eingetragen; die Grenze aus dem Kommentar bei ``declared`` („wer ein
    Merkmal durchreicht, hat es nicht erzeugt") ist bewusst eng gezogen und
    gilt nur für die drei Stellen, die Merkmale wirklich einführen.

    **Dieser Test entstand aus einer Gegenprobe**, die grün blieb: Der
    Lade-Test daneben prüft in Wahrheit den *zweiten* Riegel — nach ``load``
    ist ``previous`` leer, und der erste kommt nie zum Zug.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Aufbau",
        [OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 30.0})],
    )
    evaluate(project.document, profile, sources=ProjectSources(project))

    History(project.document).apply(
        "Aushöhlen",
        [OperationDraft(op="hollow_object", inputs=("obj_1",), params={"wall": 2.0})],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    step = next(entry.id for entry in project.document.ops if entry.op == "hollow_object")
    tagged = [
        (feature_id, feature)
        for entry in result.scene.objects.values()
        for feature_id, feature in entry.features.items()
        if feature.provenance != "generated" and feature.created_by == step
    ]

    assert not tagged, {name: feature.created_by for name, feature in tagged}


def test_a_contested_feature_never_gets_an_originator(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der dritte Riegel: Kandidaten einer Mehrdeutigkeit bleiben frei.

    Unverwiesene mehrdeutige Merkmale binden seit dem Verweisfilter (08246414)
    absichtlich nicht mehr — sie erscheinen der Zuordnung damit in **jedem**
    Lauf als neu und stehen alle in ``matched.fresh``. Bekämen sie pauschal
    den Erzeuger, wäre darunter womöglich genau das alte Merkmal, um dessen
    Zuordnung gerade gestritten wird (Einwand 3d-druck-61).
    """
    from importlib import import_module

    from app.core.bootstrap import load_operations
    from app.core.perceive.matching import MatchResult
    from app.core.scene.project import ProjectSources, new_project

    def all_contested(
        old: dict[str, object],
        new: dict[str, object],
        centre: object,
        diagonal: float,
        old_centre: object = None,
        *,
        check_cancelled: Callable[[], None] | None = None,
    ) -> MatchResult:
        if not old or len(new) < 2:
            return MatchResult(fresh=tuple(new))
        return MatchResult(ambiguous={next(iter(old)): tuple(new)}, fresh=tuple(new))

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Aufbau",
        [OperationDraft(op="create_box", params={"width": 120.0, "depth": 40.0, "height": 10.0})],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    faces = [
        feature_id
        for entry in result.scene.objects.values()
        for feature_id, feature in entry.features.items()
        if feature.kind == "face"
    ]

    monkeypatch.setattr(import_module("app.core.scene.evaluate"), "match", all_contested)
    History(project.document).apply(
        "Haken",
        [
            OperationDraft(
                op="insert_pegboard_hook",
                inputs=("obj_1",),
                params={"system": "skadis", "count": 2, "at_feature": faces[0]},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=lambda *a: "")

    step = next(entry.id for entry in project.document.ops if entry.op == "insert_pegboard_hook")
    tagged = [
        feature
        for entry in result.scene.objects.values()
        for feature in entry.features.values()
        if feature.provenance != "generated" and feature.created_by == step
    ]

    assert not tagged, f"{len(tagged)} umstrittene Merkmale haben einen Erzeuger bekommen"


# --- Die Merkmalsgrenze und das Durchreichen (§2.8, §21.2) -------------------


def _small_body() -> object:
    """Ein echtes ``MeshData`` — ``_with_features`` kehrt bei allem anderen
    sofort um, und ein Test darauf prüfte dann seinen eigenen Aufbau.

    Was darin steht, spielt keine Rolle: Die Erkennung ist in diesen Tests
    ausgetauscht. Gebraucht wird nur ein Körper mit Hüllquader und Diagonale.
    """
    import trimesh

    from app.core.geom.mesh import MeshData

    return MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))


@pytest.mark.parametrize(
    ("triangles", "recognized"),
    [(392_532, True), (885_570, True), (1_500_000, True), (1_500_001, False)],
)
def test_fine_customer_meshes_reach_recognition_with_a_bounded_budget(
    monkeypatch: pytest.MonkeyPatch, triangles: int, recognized: bool
) -> None:
    """Feine Kundennetze erreichen die Erkennung; die obere Schranke bleibt.

    Schlauchhalter und Figur lagen mit 392 532 beziehungsweise 885 570
    Dreiecken bei rund zwölf Sekunden Erkennung, wurden aber vollständig
    übersprungen. Hier wird der Anschluss geprüft, nicht die Geometriezeit:
    Die echte Erkennung misst der Korpus, diese Probe meldet ihren Aufruf.
    """
    from importlib import import_module

    from app.core.geom.mesh import MeshData
    from app.core.types import Operation, SceneObject

    evaluate_module = import_module("app.core.scene.evaluate")
    mesh = _small_body()
    calls: list[object] = []

    def detect(body: object, **kwargs: object) -> dict[str, object]:
        calls.append(body)
        return _many_features(1)

    monkeypatch.setattr(MeshData, "triangle_count", property(lambda _body: triangles))
    monkeypatch.setattr(evaluate_module, "detect", detect)
    monkeypatch.setattr(evaluate_module, "freeform_dropped", lambda _body: 0)
    findings: list[Finding] = []
    result = evaluate_module._with_features(
        SceneObject(id="obj_1", name="Kundenteil", mesh=mesh),
        {},
        Operation(id=1, op="load"),
        lambda _question, choices: choices[0],
        findings,
    )

    assert bool(calls) is recognized
    assert bool(result.features) is recognized
    limited = [finding for finding in findings if finding.code == "perceive.too_large"]
    assert bool(limited) is not recognized
    if limited:
        assert limited[0].values == {"triangles": triangles, "limit": 1_500_000}


def test_a_named_feature_keeps_the_surface_found_in_the_current_mesh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der verständliche Bausteinname darf die sichtbare Fläche nicht kosten.

    Der Baustein kennt Ort und Maß seiner Bohrung, aber keine Dreiecksnummern
    des ausgewerteten Netzes. Die Erkennung liefert genau diese Nummern. Wird
    ihr technischer Name zugunsten des Bausteinnamens entfernt, müssen deshalb
    die aktuellen Dreiecke an den bleibenden Namen übergehen — sonst wählt der
    Baum eine Bohrung, während im Modell nur ihr Beschriftungspunkt erscheint.
    """
    from importlib import import_module

    from app.core.types import Feature, Operation, SceneObject, SurfacePatch

    evaluate_module = import_module("app.core.scene.evaluate")
    params = {
        "centre": (0.0, 0.0, 0.0),
        "axis": (0.0, 0.0, 1.0),
        "diameter": 6.0,
    }
    named = Feature(
        id="mounting_bore",
        kind="hole",
        provenance="generated",
        params=params,
    )
    detected = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params=params,
        face_indices=(2, 3),
        surface_patches=(
            SurfacePatch(
                "cylinder",
                {"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "radius": 3.0},
                (2, 3),
                "fit",
            ),
        ),
    )
    monkeypatch.setattr(evaluate_module, "detect", lambda _mesh, **kwargs: {"hole_1": detected})
    entry = SceneObject(
        id="obj_1",
        name="Halter",
        mesh=_small_body(),
        features={named.id: named},
    )

    result = evaluate_module._with_features(
        entry,
        {},
        Operation(id=1, op="insert_part"),
        lambda _question, choices: choices[0],
        [],
    )

    assert "hole_1" not in result.features, "der technische Doppelname bleibt entfernt"
    assert result.features[named.id].face_indices == (2, 3), (
        "der verständliche Name übernimmt die sichtbare Oberfläche"
    )
    assert result.features[named.id].surface_patches == detected.surface_patches


def _many_features(count: int) -> dict[str, object]:
    """``count`` erkannte Bohrungen, wie ``detect`` sie liefern würde."""
    from app.core.types import Feature

    return {
        f"hole_{index}": Feature(
            id=f"hole_{index}",
            kind="hole",
            provenance="detected",
            params={
                "centre": (float(index), 0.0, 0.0),
                "axis": (0.0, 0.0, 1.0),
                "diameter": 4.0,
            },
        )
        for index in range(count)
    }


def test_a_built_face_measures_what_is_left_of_it_after_a_bore(profile: Profile) -> None:
    """Eine gebaute Fläche nennt nach einer Bohrung ihre heutige Größe (RM-216).

    ``create_box`` benennt seine Deckfläche selbst (``face_top``), und die
    Bohrung danach gibt sie weiter aus. Die Zuordnung gab ihr die Dreiecke
    des erkannten Partners, aber nicht dessen Maße: Steckbrief, Agent und
    Merkmalfenster nannten 2 400 mm² für eine Fläche, der das Loch fehlt —
    die frische Erkennung misst 2 349,878. Was die Erzeugung selbst als
    Messung ausweist (Quelle ``facets``/``fit``), folgt dem Partner; was aus
    einem Parameter kommt, bleibt.
    """
    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect, forget_cache
    from app.core.scene.project import new_project

    forget_cache()
    document = new_project("centauri-carbon-2", "petg").document
    History(document).apply(
        "Schritte",
        [
            OperationDraft(op="create_box", params={"width": 60.0, "depth": 40.0, "height": 10.0}),
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 8.0, "x": -10.0, "y": 5.0, "z": 10.0, "compensate": False},
            ),
        ],
    )
    result = evaluate(document, profile, cache=ResultCache())
    body = result.scene.objects["obj_1"]
    top = body.features["face_top"]
    assert top.provenance == "generated", "der Name der Erzeugung bleibt"
    assert isinstance(body.mesh, MeshData)
    fresh = next(
        feature
        for feature in detect(body.mesh).values()
        if feature.kind == "face" and feature.params["normal"][2] > 0.99
    )
    assert top.params["area"] == pytest.approx(fresh.params["area"], rel=1e-9)
    assert top.params["area"] == pytest.approx(60.0 * 40.0 - math.pi * 4.0 * 4.0, rel=0.01)
    assert top.params["centre"] == pytest.approx(fresh.params["centre"], abs=1e-9)
    assert tuple(top.params["normal"]) == (0.0, 0.0, 1.0), "die Normale kommt aus dem Parameter"
    assert top.measure_sources["area"] == "facets"


def test_a_face_that_a_bore_divides_is_not_reported_lost(profile: Profile) -> None:
    """Eine Bohrung über die Kante teilt die Seite, die sie anschneidet — ein Verlust ist das nicht.

    Quader 20 × 20 × 10, Bohrung Ø 6 genau auf der rechten Kante: Die rechte
    Seite steht danach als zwei Flächen in derselben Ebene da. Der Bericht
    sagte dazu „Ein Formdetail ist nach diesem Schritt nicht mehr automatisch
    wiederzuerkennen“ (`perceive.orphaned` für `face_6`, Befund texte der
    Durchsicht 0.5.1, RM-217) — über einem Schritt, der genau das tun sollte.
    """
    from app.core.perceive.features import forget_cache
    from app.core.scene.project import new_project

    forget_cache()
    document = new_project("centauri-carbon-2", "petg").document
    History(document).apply(
        "Schritte",
        [
            OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 10.0}),
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 6.0, "axis": "z", "x": 10.0, "y": 0.0, "z": 10.0},
            ),
        ],
    )
    result = evaluate(document, profile, cache=ResultCache())

    assert result.complete
    step = document.ops[-1].id
    codes = [finding.code for finding in result.scene.report.findings if finding.op_id == step]
    assert "perceive.orphaned" not in codes, codes
    right = [
        feature
        for feature in result.scene.objects["obj_1"].features.values()
        if feature.kind == "face" and feature.params["normal"][0] > 0.99
    ]
    assert len(right) == 2, "die rechte Seite steht in zwei Stücken da"


def test_a_face_that_a_split_divides_is_not_reported_lost_in_either_half(
    profile: Profile,
) -> None:
    """*Teilen* schneidet jede Fläche, durch die die Ebene geht — auch für die zweite Hälfte.

    Eine Fläche, die die Ebene quert, reist mit der Hälfte, auf der ihre Mitte
    liegt (``prepare_ops._features_after_split``). Ob sie dort nur geteilt
    ist, misst die Auswertung an ihren Dreiecken im Eingangsnetz — und das
    bekam nur die **erste** Ausgabe: Die zweite hatte keinen Eingang „an
    derselben Stelle“, und Deck-, Boden- und Seitenflächen standen dort als
    „Ein Formdetail ist nach diesem Schritt nicht mehr automatisch
    wiederzuerkennen“ (RM-217, zweiter Punkt; am Besenhalter drei Flächen,
    Durchsicht 0.5.1, Sonde p64).
    """
    from app.core.perceive.features import forget_cache
    from app.core.scene.project import new_project

    forget_cache()
    document = new_project("centauri-carbon-2", "petg").document
    History(document).apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 10.0})],
    )
    box = evaluate(document, profile, cache=ResultCache()).scene.objects["obj_1"]
    # Die Ebene drei Millimeter vor der Mitte: Jede querende Fläche reist mit
    # der zweiten Hälfte.
    position = float(box.mesh.bounds.centre[0]) - 3.0
    History(document).apply(
        "Teilen",
        [
            OperationDraft(
                op="split_pinned",
                inputs=("obj_1",),
                params={"axis": "x", "position": position, "pins": 0},
            )
        ],
    )
    result = evaluate(document, profile, cache=ResultCache())

    assert result.complete
    step = document.ops[-1].id
    lost = [
        finding.values.get("feature")
        for finding in result.scene.report.findings
        if finding.op_id == step and finding.code == "perceive.orphaned"
    ]
    assert not lost, lost
    halves = [result.scene.objects[name] for name in document.ops[-1].outputs]
    # Jede Hälfte ist ein Quader mit sechs Flächen, jede erkannt und mit
    # Dreiecken. Die Deckfläche trägt in beiden Hälften den Namen, den der
    # Quader ihr gab — die Stücke einer geteilten Fläche behalten ihn seit R4
    # (``evaluate._divided_partners``), statt neben einem unerkannten Eintrag
    # frisch benannt zu werden.
    faces = [
        sorted(
            name
            for name, feature in half.features.items()
            if feature.kind == "face" and feature.recognised and feature.face_indices
        )
        for half in halves
    ]
    assert all(len(names) == 6 for names in faces), faces
    assert all("face_top" in names for names in faces), faces


@pytest.mark.parametrize("cut", ["split", "below", "above"])
@pytest.mark.parametrize("box", ["create_box", "create_brep_box"])
def test_a_cut_face_keeps_its_name_on_its_piece(profile: Profile, box: str, cut: str) -> None:
    """*Teilen* und *Abschneiden*: Eine Fläche, die die Ebene quert, heißt am Stück weiter (R4).

    Quader 20 x 20 x 10, Ebene 3 mm neben der Mitte, eine bündige Passung an
    der Deckfläche. Vorher reiste die Deckfläche mit der Hälfte ihrer Mitte,
    fand dort kein gleich großes Stück und stand als unerkannter Eintrag mit
    400 mm² da, ohne Dreiecke; das Stück daneben hieß neu. Schob man die Ebene
    über die Mitte, meldete *Teilen* „nicht mehr erkennbar“ und die Passung
    „Merkmal fehlt“. *Abschneiden* reichte die Flächen ohne Dreiecke weiter:
    Die Seiten standen als verloren im Bericht, und nach dem Verschieben zeigte
    die Passung auf die Schnittfläche oder den Boden — „10 mm statt 0 mm“ an
    einer Deckfläche, die stimmte (Durchsicht 0.5.1). Beide Kerne gleich: Der
    exakte Quader wird an seiner Tessellierung geschnitten.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.features import forget_cache
    from app.core.scene.project import new_project

    load_operations()
    forget_cache()
    document = new_project("centauri-carbon-2", "petg").document
    history = History(document)
    size = {"width": 20.0, "depth": 20.0, "height": 10.0}
    history.apply("Quader", [OperationDraft(op=box, params=dict(size))])
    history.apply("Nachbar", [OperationDraft(op=box, params={**size, "y": 40.0})])
    scene = evaluate(document, profile, cache=ResultCache()).scene

    def top_of(features: dict[str, Any]) -> str:
        return next(
            name
            for name, feature in sorted(features.items())
            if feature.kind == "face" and feature.params["normal"][2] > 0.99
        )

    top = top_of(dict(scene.objects["obj_1"].features))
    middle = float(scene.objects["obj_1"].mesh.bounds.centre[0])
    params: dict[str, Any] = {"axis": "x", "position": middle - 3.0}
    params.update({"pins": 0} if cut == "split" else {"keep": cut})
    history.apply(
        "Schnitt",
        [
            OperationDraft(
                op="split_pinned" if cut == "split" else "cut_away",
                inputs=("obj_1",),
                params=params,
            )
        ],
    )
    outputs = tuple(document.ops[-1].outputs)
    partner = (
        FeatureRef(outputs[1], top)
        if cut == "split"
        else FeatureRef("obj_2", top_of(dict(scene.objects["obj_2"].features)))
    )
    document.fits.append(
        Fit(
            name="deckel",
            a=FeatureRef(outputs[0], top),
            b=partner,
            kind="flush",
            tolerance="auto:petg",
        )
    )

    for position in (middle - 3.0, middle + 3.0):
        step = document.ops[-1]
        if step.params["position"] != position:
            history.change_params(step.id, {**step.params, "position": position})
        result = evaluate(document, profile, cache=ResultCache())

        assert result.complete
        codes = {finding.code for finding in result.scene.report.findings}
        lost = {
            "perceive.orphaned",
            "perceive.referenced_lost",
            "perceive.generated_lost",
            "fit.missing_feature",
            "fit.not_measurable",
            "fit.violated",
        }
        assert not codes & lost, (position, sorted(codes))
        for name in outputs:
            body = result.scene.objects[name]
            faces = {n: f for n, f in body.features.items() if f.kind == "face"}
            assert all(f.recognised and f.face_indices for f in faces.values()), faces
            face = faces[top]
            width = float(body.mesh.bounds.maximum[0] - body.mesh.bounds.minimum[0])
            assert face.params["normal"][2] > 0.99
            assert face.params["centre"][2] == pytest.approx(10.0, abs=1e-6)
            assert face.params["area"] == pytest.approx(width * 20.0, rel=1e-6)


def _box_top(indices: str) -> tuple[Any, Any]:
    """Ein Quader 20 x 20 x 10 als Netz und seine alte Deckfläche.

    ``indices``: ``"top"`` gibt ihr die Dreiecke der Deckfläche, ``"bottom"``
    die des Bodens — Nummern, die nicht diese Fläche sind.
    """
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import Feature

    body = trimesh.creation.box(extents=(20.0, 20.0, 10.0))
    body.apply_translation((0.0, 0.0, 5.0))
    wanted = 1.0 if indices == "top" else -1.0
    faces = tuple(
        int(index) for index in np.flatnonzero(np.isclose(body.face_normals[:, 2], wanted))
    )
    old = Feature(
        id="face_top",
        kind="face",
        provenance="generated",
        params={"normal": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 10.0), "area": 400.0},
        face_indices=faces,
    )
    return MeshData.of(body), old


def _piece(name: str, x: float, area: float) -> Any:
    """Ein erkanntes Stück der Deckfläche bei ``x``."""
    from app.core.types import Feature

    return Feature(
        id=name,
        kind="face",
        provenance="detected",
        params={"normal": (0.0, 0.0, 1.0), "centre": (x, 0.0, 10.0), "area": area},
    )


def test_two_equal_pieces_of_a_divided_face_are_a_question() -> None:
    """Zwei gleich große Stücke: Die Lage entscheidet nicht, die Zuordnung fragt (R4, Regel 21).

    Das größte Stück trägt den Namen einer geteilten Fläche. Sind die größten
    gleich groß, wäre jede Wahl geraten; das Paar geht als offene Frage an die
    Zuordnung, die fragt, sobald ein Verweis daran hängt.
    """
    from app.core.perceive.matching import MatchResult
    from app.core.scene.evaluate import _divided_partners

    source, old = _box_top("top")
    seen = MatchResult(orphaned=("face_top",), fresh=("face_1", "face_2"))

    equal = {"face_1": _piece("face_1", -5.0, 200.0), "face_2": _piece("face_2", 5.0, 200.0)}
    result, missing = _divided_partners({"face_top": old}, equal, seen, source, {})
    assert result.ambiguous == {"face_top": ("face_1", "face_2")}
    assert not result.mapping and not result.orphaned and not missing

    larger = {"face_1": _piece("face_1", -6.5, 140.0), "face_2": _piece("face_2", 3.5, 260.0)}
    result, missing = _divided_partners({"face_top": old}, larger, seen, source, {})
    assert result.mapping == {"face_top": "face_2"}
    assert result.fresh == ("face_1",) and not result.ambiguous and not missing


def test_old_triangles_that_are_another_face_find_no_piece() -> None:
    """Dreiecksnummern, die nicht die alte Fläche bezeichnen, geben keinem Stück ihren Namen (R4).

    So sehen Nummern aus, die eine Operation an ihrem eigenen Ergebnis vergab:
    Am Eingang zeigen sie auf fremde Dreiecke. Hier der Boden unter dem Namen
    der Deckfläche — der Name bleibt ohne Stück, statt aus dem Hüllquader des
    Bodens eines zu wählen. Reicht die Operation die Fläche ohne Dreiecke
    weiter, gelten die des Eingangs.
    """
    import dataclasses

    from app.core.perceive.matching import MatchResult
    from app.core.scene.evaluate import _divided_partners

    source, wrong = _box_top("bottom")
    seen = MatchResult(orphaned=("face_top",), fresh=("face_1",))
    pieces = {"face_1": _piece("face_1", 3.5, 260.0)}

    result, missing = _divided_partners({"face_top": wrong}, pieces, seen, source, {})
    assert missing == ("face_top",) and not result.mapping

    _source, right = _box_top("top")
    passed_on = dataclasses.replace(right, face_indices=())
    result, missing = _divided_partners(
        {"face_top": passed_on}, pieces, seen, source, {"face_top": right}
    )
    assert result.mapping == {"face_top": "face_1"} and not missing


@pytest.mark.parametrize(
    ("answer", "gone"),
    [
        ("Nur das gewählte Merkmal", {"cone_1"}),
        ("Den ganzen Hohlraum entfernen", {"cone_1", "hole_1"}),
    ],
)
def test_a_removed_feature_is_told_once(profile: Profile, answer: str, gone: set[str]) -> None:
    """*Merkmal entfernen* sagt einmal, dass das Merkmal fort ist (RM-217).

    Die Operation meldet ``remove_feature.gone`` — „Das Merkmal ist
    entfernt" — und die Zuordnung danach noch einmal ``perceive.orphaned``:
    „Ein Formdetail ist nach diesem Schritt nicht mehr automatisch
    wiederzuerkennen". Zwei Sätze über dasselbe, und der zweite klingt, als sei
    etwas schiefgegangen, wo der Kunde genau das wollte.
    """
    from app.core.perceive.features import forget_cache
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    meshes = Path(__file__).parent / "data" / "meshes"
    forget_cache()
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = (meshes / "plate_countersunk.stl").read_bytes()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_countersunk.stl", sha256=""
    )
    history = History(project.document)
    history.apply("Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    history.apply(
        "Entfernen",
        [OperationDraft(op="remove_feature", inputs=("obj_1",), params={"at_feature": "cone_1"})],
    )
    result = evaluate(
        project.document,
        profile,
        sources=ProjectSources(project),
        cache=ResultCache(),
        ask=lambda question, choices: answer if answer in choices else choices[0],
    )

    assert result.complete
    step = project.document.ops[-1].id
    removed = [
        finding
        for finding in result.scene.report.findings
        if finding.op_id == step and finding.code == "remove_feature.gone"
    ]
    assert removed and set(removed[0].feature_ids) == gone
    lost = {
        name.strip()
        for finding in result.scene.report.findings
        if finding.op_id == step and finding.code == "perceive.orphaned"
        for name in str(finding.values.get("feature", "")).split(",")
    }
    assert not lost & gone, "das entfernte Merkmal steht zweimal im Bericht"


def test_too_many_features_keep_the_largest_and_say_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Über der Grenze bleiben die größten Merkmale, zugeordnet wie sonst (RM-235).

    Die Grenze fängt ab, was die Zuordnung und der Objektbaum nicht mehr
    tragen — und bis zum 25.09.2026 fiel dahinter **alles** weg: Die
    Kumiko-Schale (7 295 Flächen) stand ohne ihre vier großen Deckflächen da.
    Jetzt bleiben ``FEATURE_LIMIT_COUNT`` Merkmale, die mit der größten
    Oberfläche, und benannt und zugeordnet wird genau diese; der Befund sagt,
    dass es mehr waren (Regel 17).
    """
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    from app.core.types import Feature, Operation, SceneObject

    body = _small_body()
    monkeypatch.setattr(evaluate_module, "FEATURE_LIMIT_COUNT", 3)
    areas = [float(area) for area in body.raw.area_faces]
    # Vier Flächen aus verschieden vielen Dreiecken des Quaders: 4, 1, 2, 3.
    faces = {
        f"face_{number}": Feature(
            id=f"face_{number}",
            kind="face",
            provenance="detected",
            params={
                "centre": (float(number), 0.0, 0.0),
                "normal": (0.0, 0.0, 1.0),
                "area": sum(areas[index] for index in triangles),
            },
            face_indices=triangles,
        )
        for number, triangles in enumerate([(0, 1, 2, 3), (4,), (5, 6), (7, 8, 9)], start=1)
    }
    monkeypatch.setattr(evaluate_module, "detect", lambda mesh, **kwargs: dict(faces))
    findings: list[Finding] = []
    result = evaluate_module._with_features(
        SceneObject(id="obj_1", name="Teil", mesh=body),
        {},
        Operation(id=1, op="load", outputs=("obj_1",)),
        lambda q, c: c[0],
        findings,
    )

    codes = [item.code for item in findings]
    assert "perceive.too_many" in codes, codes
    values = next(item for item in findings if item.code == "perceive.too_many").values
    assert values == {"features": 4, "limit": 3}
    kept = sorted(len(feature.face_indices) for feature in result.features.values())
    assert kept == [2, 3, 4], "die kleinste Fläche fällt, die drei größten bleiben"


def test_the_largest_features_are_kept_the_same_way_every_time() -> None:
    """Bei gleicher Größe entscheiden Art und Dreiecke, nie die Reihenfolge."""
    from importlib import import_module

    from app.core.types import Feature

    evaluate_module = import_module("app.core.scene.evaluate")
    body = _small_body()
    features = {
        name: Feature(id=name, kind="face", provenance="detected", params={}, face_indices=faces)
        for name, faces in (("a", (0,)), ("b", (1,)), ("c", (2,)), ("d", (3,)))
    }
    forward = evaluate_module._heaviest(features, body, 2)
    backward = evaluate_module._heaviest(dict(reversed(list(features.items()))), body, 2)
    assert set(forward) == set(backward)


def test_over_the_limit_a_stretched_body_keeps_its_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """Was vorher behalten war, bleibt es nach dem Strecken (RM-235).

    Ungleichmäßiges Skalieren sortiert die Flächen nach Inhalt um: Am in x
    gestreckten Würfel wachsen die vier Seiten längs der Streckung, die beiden
    Stirnseiten nicht. Nach der Größe allein fiele eine behaltene Stirnseite
    heraus und reiste als starr mitbewegte weiter, und eine Seite käme unter
    neuem Namen dazu — an der Kumiko-Schale wechselten so 1 814 Namen, und aus
    5 000 Merkmalen wurden 5 898.
    """
    from importlib import import_module

    import numpy as np

    from app.core.geom.ops import as_transform
    from app.core.geom.transform import apply, scaling
    from app.core.types import Feature, Operation, SceneObject

    evaluate_module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(evaluate_module, "FEATURE_LIMIT_COUNT", 3)

    def sides(mesh: Any, **kwargs: Any) -> dict[str, Feature]:
        raw = mesh.raw
        found: dict[str, Feature] = {}
        for axis, letter in enumerate("xyz"):
            for sign, mark in ((-1.0, "n"), (1.0, "p")):
                rows = np.flatnonzero(raw.face_normals[:, axis] * sign > 0.5)
                name = f"face_{letter}{mark}"
                found[name] = Feature(
                    id=name,
                    kind="face",
                    provenance="detected",
                    params={
                        "centre": tuple(float(v) for v in raw.triangles_center[rows].mean(axis=0)),
                        "normal": tuple(sign if index == axis else 0.0 for index in range(3)),
                        "area": float(raw.area_faces[rows].sum()),
                    },
                    face_indices=tuple(int(row) for row in rows),
                )
        return found

    monkeypatch.setattr(evaluate_module, "detect", sides)
    body = _small_body()
    loaded = evaluate_module._with_features(
        SceneObject(id="obj_1", name="Teil", mesh=body),
        {},
        Operation(id=1, op="load", outputs=("obj_1",)),
        lambda q, c: c[0],
        [],
    )
    assert len(loaded.features) == 3
    matrix = scaling((3.0, 1.0, 1.0))
    findings: list[Finding] = []
    stretched = evaluate_module._with_features(
        SceneObject(id="obj_1", name="Teil", mesh=apply(body, matrix)),
        dict(loaded.features),
        Operation(id=2, op="scale_object", inputs=("obj_1",), outputs=("obj_1",)),
        lambda q, c: c[0],
        findings,
        as_transform(matrix),
    )
    assert set(stretched.features) == set(loaded.features)
    assert "perceive.orphaned" not in [item.code for item in findings]


def test_a_model_below_the_feature_limit_is_matched_as_before(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gegenrichtung, ohne die die Grenze alles abschneiden könnte.

    Ein Verbotstest über eine leere Menge ist immer grün; dieser hier stellt
    sicher, dass die Grenze im Normalfall **nicht** greift.
    """
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    from app.core.types import Operation, SceneObject

    crowd = _many_features(evaluate_module.FEATURE_LIMIT_COUNT)
    monkeypatch.setattr(evaluate_module, "detect", lambda mesh, **kwargs: dict(crowd))

    entry = SceneObject(id="obj_1", name="Teil", mesh=_small_body())
    findings: list[Finding] = []
    evaluate_module._with_features(
        entry, dict(_many_features(3)), Operation(id=1, op="thicken"), lambda q, c: c[0], findings
    )

    assert [item.code for item in findings if item.code == "perceive.too_many"] == [], (
        "genau auf der Grenze wird noch zugeordnet"
    )


def test_a_plate_with_a_pocket_pattern_keeps_its_holes() -> None:
    """Ein Muster aus tausend ebenen Flächen ist Alltag, kein Ausreißer.

    Roberts Schraubendreherhalter mit Wabenmuster (22.09.2026): 7 956 Dreiecke,
    verschweißt, 1 199 ebene Flächen, sechs Verrundungen, vier Bohrungen mit
    Senkung — und die Auswertung hängte **nichts** ein, mit dem Rat, das Modell
    zu verschweißen. Die Grenze von tausend stammte aus der Zeit der
    quadratischen Zuordnung. Hier dieselbe Gestalt im Kleinen: 220 Taschen und
    zwei Bohrungen, über tausend Merkmale — und die Bohrungen bleiben.

    Die Taschen sind jede anders tief, in gewürfelter Folge: Gleich tiefe
    Taschen im Raster wären seit RM-207 **ein** Muster mit sieben Merkmalen
    daneben, und der Test prüfte nichts mehr über tausend.
    """
    import random
    from importlib import import_module

    import trimesh

    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import MeshData
    from app.core.types import Operation, SceneObject

    evaluate_module = import_module("app.core.scene.evaluate")
    plate = trimesh.creation.box(extents=(100.0, 60.0, 8.0))
    plate.apply_translation((0.0, 0.0, 4.0))
    tools = []
    depths = [1.0 + 0.1 * (index % 20) for index in range(220)]
    random.Random(7).shuffle(depths)
    for column in range(22):
        for row in range(10):
            depth = depths[column * 10 + row]
            pocket = trimesh.creation.box(extents=(2.4, 2.4, depth))
            pocket.apply_translation((-47.0 + column * 4.4, -25.0 + row * 5.0, 8.0))
            tools.append(pocket)
    for x in (-40.0, 40.0):
        bore = trimesh.creation.cylinder(radius=3.0, height=20.0, sections=48)
        bore.apply_translation((x, 25.0, 4.0))
        tools.append(bore)
    cut = boolean("difference", [MeshData.of(plate), MeshData.of(trimesh.util.concatenate(tools))])
    entry = SceneObject(id="obj_1", name="Halter", mesh=cut.mesh)

    findings: list[Finding] = []
    result = evaluate_module._with_features(
        entry, {}, Operation(id=1, op="load"), lambda q, c: c[0], findings
    )

    assert [item.code for item in findings if item.code == "perceive.too_many"] == []
    kinds = [feature.kind for feature in result.features.values()]
    assert kinds.count("hole") == 2, "die zwei Bohrungen neben dem Muster"
    assert kinds.count("face") > evaluate_module.FEATURE_LIMIT_COUNT // 5, (
        "ohne das Muster prüft der Test nur eine Platte mit zwei Löchern"
    )
    assert len(kinds) > 1_000, "die alte Grenze — darunter wäre der Fall nie aufgefallen"


def test_the_recognition_can_be_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    """§2.8: Was rechnet, ist abbrechbar — auch die Erkennung.

    Sie stand außerhalb: ``raise_if_cancelled`` wurde nur am Kopf der
    Operationsschleife abgefragt, und Erkennung samt Zuordnung liefen danach
    ohne jede Rückfrage. Gemessen waren das an einem einzigen Schritt 101,6 von
    101,8 Sekunden, in denen der Abbrechen-Knopf nichts tat.
    """
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    from app.core.types import Operation, SceneObject

    signal = CancelSignal()
    signal.cancel()
    entry = SceneObject(id="obj_1", name="Teil", mesh=_small_body())

    def must_not_run(mesh: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("nach dem Abbrechen darf nicht mehr erkannt werden")

    monkeypatch.setattr(evaluate_module, "detect", must_not_run)

    with pytest.raises(OperationCancelled):
        evaluate_module._with_features(
            entry, {}, Operation(id=1, op="thicken"), lambda q, c: c[0], [], cancelled=signal
        )


def test_cancellation_during_first_recognition_does_not_publish_a_result(
    monkeypatch: pytest.MonkeyPatch,
    history: History,
    document: Document,
    profile: Profile,
    registry: Registry,
) -> None:
    """Ein Abbruch während der ersten Erkennung darf weder Szene noch Cache liefern."""
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    signal = CancelSignal()
    cache = ResultCache()

    @register_op(
        name="load_test_mesh",
        title=_("Testnetz laden"),
        category="import",
        params=EmptyParams,
        consumes=0,
        produces=1,
        doc=_("Testversion."),
        registry=registry,
    )
    def load_test_mesh(ctx: OpContext) -> OpResult:
        return OpResult(outputs=[SceneObject(id="", name="Teil", mesh=_small_body())])

    def cancelled_detection(mesh: object, **kwargs: object) -> dict[str, object]:
        check_cancelled = kwargs["check_cancelled"]
        assert callable(check_cancelled)
        check_cancelled()
        signal.cancel()
        with pytest.raises(OperationCancelled):
            check_cancelled()
        return _many_features(1)

    monkeypatch.setattr(evaluate_module, "detect", cancelled_detection)
    history.apply(_("Einfügen"), [OperationDraft(op="load_test_mesh")])

    with pytest.raises(OperationCancelled):
        evaluate(document, profile, registry=registry, cancelled=signal, cache=cache)

    assert len(cache) == 0, "ein abgebrochener Erstimport darf keinen fertigen Stand ablegen"


def test_the_recognition_reports_what_it_is_doing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Und dieselbe Strecke meldet, woran sie ist.

    Ohne das nannte die Leiste weiter die Operation, die längst fertig war —
    hundert Sekunden lang derselbe Satz. Der Bruchteil bleibt der des Schritts;
    was sich ändert, ist der Text.
    """
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    from app.core.types import Operation, SceneObject

    monkeypatch.setattr(evaluate_module, "detect", lambda mesh, **kwargs: dict(_many_features(2)))
    said: list[str] = []
    entry = SceneObject(id="obj_1", name="Teil", mesh=_small_body())

    evaluate_module._with_features(
        entry,
        dict(_many_features(2)),
        Operation(id=1, op="thicken"),
        lambda q, c: c[0],
        [],
        say=said.append,
    )

    assert said, "die Erkennung meldet sich nicht"
    assert any("zuordnen" in text.lower() for text in said), said


def test_what_the_recognition_left_out_on_a_freeform_is_said(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Merkmal, das still verschwindet, ist schlimmer als eines, das dasteht.

    ``detect`` nimmt Kugeln, Ringe, Kegel und Verrundungen von einer Freiform
    — ein Kiefer-Scan brachte 281 davon. Der Kunde sieht dann einen
    Objektbaum, dem etwas fehlt, und der Befund sagt ihm, warum (Regel 17).
    """
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    from app.core.types import Operation, SceneObject

    monkeypatch.setattr(evaluate_module, "detect", lambda mesh, **kwargs: dict(_many_features(3)))
    monkeypatch.setattr(evaluate_module, "freeform_dropped", lambda mesh: 281)

    entry = SceneObject(id="obj_1", name="Kiefer", mesh=_small_body())
    findings: list[Finding] = []
    evaluate_module._with_features(
        entry, {}, Operation(id=1, op="thicken"), lambda q, c: c[0], findings
    )

    freeform = [item for item in findings if item.code == "perceive.freeform"]
    assert len(freeform) == 1, [item.code for item in findings]
    assert freeform[0].severity == "info"
    assert freeform[0].values["dropped"] == 281
    assert freeform[0].object_id == "obj_1" and freeform[0].op_id == 1
    # **Und er sagt, was gemessen wurde, nicht woher das Teil kommt** (RM-151).
    # „Dieses Modell ist eine Freiform, etwa ein Scan" stand über einer Zählung
    # und las sich als Aussage über das Bauteil: Roberts konstruierter Halter
    # kam mit 0,701 gegen die Schwelle 0,700 dorthin, also um ein Tausendstel.
    gesagt = str(freeform[0].message)
    assert "Scan" not in gesagt, f"der Satz schreibt dem Modell eine Herkunft zu: {gesagt}"
    assert "gekrümmt" in gesagt, f"und er nennt nicht, was gemessen wurde: {gesagt}"


def test_a_skin_without_dropped_shapes_still_gets_the_freeform_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RM-193: Die Splitter einer Haut werden nicht eingepasst, also lässt die
    Erkennung dort nichts weg — der Kunde sieht trotzdem keine Rundformen
    auf seiner Figur und soll lesen, warum (Regel 17)."""
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    from app.core.types import Operation, SceneObject

    monkeypatch.setattr(evaluate_module, "detect", lambda mesh, **kwargs: dict(_many_features(3)))
    monkeypatch.setattr(evaluate_module, "freeform_dropped", lambda mesh: 0)
    monkeypatch.setattr(evaluate_module, "recognised_as_freeform", lambda mesh: True)

    entry = SceneObject(id="obj_1", name="Drache", mesh=_small_body())
    findings: list[Finding] = []
    evaluate_module._with_features(
        entry, {}, Operation(id=1, op="thicken"), lambda q, c: c[0], findings
    )

    freeform = [item for item in findings if item.code == "perceive.freeform"]
    assert len(freeform) == 1, [item.code for item in findings]
    assert freeform[0].values["dropped"] == 0
    gesagt = str(freeform[0].message)
    assert "weggelassen" not in gesagt and "fand" not in gesagt, (
        f"der Satz behauptet eine Suche, die nicht stattfand: {gesagt}"
    )


def test_a_model_that_is_no_freeform_gets_no_such_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gegenrichtung: null weggelassen heißt kein Satz darüber."""
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    from app.core.types import Operation, SceneObject

    monkeypatch.setattr(evaluate_module, "detect", lambda mesh, **kwargs: dict(_many_features(3)))
    monkeypatch.setattr(evaluate_module, "freeform_dropped", lambda mesh: 0)
    monkeypatch.setattr(evaluate_module, "recognised_as_freeform", lambda mesh: False)

    entry = SceneObject(id="obj_1", name="Teil", mesh=_small_body())
    findings: list[Finding] = []
    evaluate_module._with_features(
        entry, {}, Operation(id=1, op="thicken"), lambda q, c: c[0], findings
    )

    assert [item.code for item in findings if item.code == "perceive.freeform"] == []


def test_shells_the_recognition_could_not_read_become_a_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Einschluss, der fehlt, weil sein Schalenpaar nicht lesbar war, fehlt nicht still.

    ``detect`` liest Schalenpaare über die native Differenz; wo die nicht
    antwortet, gab es bis zum 21.09.2026 leere Gruppen und keinen Satz — der
    Kunde druckte das Teil, ohne von der Luft darin zu wissen (Regel 17).
    """
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    from app.core.types import Operation, SceneObject

    monkeypatch.setattr(evaluate_module, "detect", lambda mesh, **kwargs: dict(_many_features(3)))
    monkeypatch.setattr(evaluate_module, "freeform_dropped", lambda mesh: 0)
    monkeypatch.setattr(evaluate_module, "unreadable_void_shells", lambda mesh: 2)

    entry = SceneObject(id="obj_1", name="Gehäuse", mesh=_small_body())
    findings: list[Finding] = []
    evaluate_module._with_features(
        entry, {}, Operation(id=1, op="thicken"), lambda q, c: c[0], findings
    )

    unreadable = [item for item in findings if item.code == "perceive.voids_unreadable"]
    assert len(unreadable) == 1, [item.code for item in findings]
    assert unreadable[0].severity == "warning"
    assert unreadable[0].values["shells"] == 2
    assert unreadable[0].object_id == "obj_1" and unreadable[0].op_id == 1
    gesagt = str(unreadable[0].message)
    assert "Lufteinschlüsse" in gesagt, gesagt
    # Der Rat steckt im Knopf (Bedienweg A6): Wer einen Weg nennt, bietet ihn an.
    assert "Slicer" not in gesagt and "Reparieren" not in gesagt, gesagt
    assert [action.id for action in unreadable[0].suggestions] == [
        "show_layers",
        "show_locations",
    ]


def test_readable_shells_get_no_such_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Gegenrichtung: Wo jedes Schalenpaar gelesen wurde, steht kein Satz."""
    from importlib import import_module

    evaluate_module = import_module("app.core.scene.evaluate")
    from app.core.types import Operation, SceneObject

    monkeypatch.setattr(evaluate_module, "detect", lambda mesh, **kwargs: dict(_many_features(3)))
    monkeypatch.setattr(evaluate_module, "freeform_dropped", lambda mesh: 0)
    monkeypatch.setattr(evaluate_module, "unreadable_void_shells", lambda mesh: 0)

    entry = SceneObject(id="obj_1", name="Teil", mesh=_small_body())
    findings: list[Finding] = []
    evaluate_module._with_features(
        entry, {}, Operation(id=1, op="thicken"), lambda q, c: c[0], findings
    )

    assert [item.code for item in findings if item.code == "perceive.voids_unreadable"] == []


@pytest.mark.parametrize("triangles", [1_500_001, 2_330_374, 5_000_000])
@pytest.mark.parametrize("choice", [0, 1, "closed", "cancel"])
def test_large_import_asks_before_recognition_and_keeps_original(monkeypatch, triangles, choice):
    """Die Warnung eröffnet den großen Pfad; Absage lädt, echter Abbruch beendet ihn."""
    from importlib import import_module

    from app.core.errors import QuestionDeclined
    from app.core.geom.mesh import MeshData
    from app.core.types import Operation

    module = import_module("app.core.scene.evaluate")
    mesh = _small_body()
    monkeypatch.setattr(MeshData, "triangle_count", property(lambda _body: triangles))
    calls, asked, progress, recorded, findings = [], [], [], {}, []
    monkeypatch.setattr(module, "detect", lambda body, **_: calls.append(body) or _many_features(1))
    monkeypatch.setattr(module, "freeform_dropped", lambda _: 0)
    body = SceneObject("obj_1", "Großes Teil", mesh)

    from app.core.perceive.local import recognition_gigabytes, recognition_minutes

    minimum, maximum = recognition_minutes(triangles)
    millions = f"{triangles / 1_000_000:.1f}".replace(".", ",")

    def ask(question, choices):
        assert progress[-1] == "Merkmale erkennen" and not calls
        assert f"{millions} Millionen Dreiecke" in question
        assert f"geschätzt {minimum} bis {maximum} Minuten" in question
        assert f"etwa {recognition_gigabytes(triangles)} GB Arbeitsspeicher" in question
        # Die Spanne gilt diesem Rechner (``recognition_time``); ein Zusatz über
        # „langsame Rechner" ließ raten, ob sie das tut (erkennung-01).
        assert "auf diesem Rechner geschätzt" in question
        assert "langsamen Rechnern" not in question
        assert choices[0] == "Sofort laden", "die sichere Wahl steht vorn"
        asked.append(question)
        if choice == "closed":
            raise QuestionDeclined()
        if choice == "cancel":
            raise OperationCancelled()
        return choices[choice]

    def run():
        return module._with_features(
            body,
            {},
            Operation(1, "load", outputs=("obj_1",)),
            module._WatchedAsk(ask),
            findings,
            recorded=recorded,
            say=progress.append,
        )

    if choice == "cancel":
        with pytest.raises(OperationCancelled):
            run()
        assert not calls and not recorded
        return
    result = run()
    assert len(asked) == 1
    assert result.mesh is mesh
    assert bool(result.features) is (choice == 1)
    assert bool(calls) is (choice == 1)
    assert next(iter(recorded.values()))["allowed"] is (choice == 1)
    assert any(f.code == "perceive.too_large" for f in findings) is (choice != 1)
    # Während der langen Erkennung sagt die Zeile, was läuft; die Dauer rechnet
    # die Statuszeile aus dem wachsenden Anteil hoch (KUNDE-14) — eine feste
    # Spanne daneben wäre eine zweite Auskunft über dieselbe Zeit.
    assert progress[-1] == "Merkmale erkennen"
    assert not [text for text in progress if "geschätzt" in text]


@pytest.mark.parametrize(
    ("operation", "triangles", "detect_features"),
    [("load", 5_000_001, True), ("repair", 2_330_374, True), ("load", 2_330_374, False)],
)
def test_large_recognition_never_asks_above_cap_after_import_or_for_preview(
    monkeypatch, operation, triangles, detect_features
):
    """Die Bestätigung gilt nur dem Laden innerhalb der Obergrenze, nie der Vorschau."""
    from importlib import import_module

    from app.core.geom.mesh import MeshData
    from app.core.types import Operation

    module = import_module("app.core.scene.evaluate")
    mesh = _small_body()
    monkeypatch.setattr(MeshData, "triangle_count", property(lambda _: triangles))
    monkeypatch.setattr(module, "detect", lambda *_a, **_k: pytest.fail("unexpected full scan"))
    records = {}
    result = module._with_features(
        SceneObject("obj_1", "Teil", mesh),
        {},
        Operation(1, operation, outputs=("obj_1",)),
        lambda *_: pytest.fail("unexpected question"),
        [],
        recorded=records,
        detect_features=detect_features,
    )
    assert result.mesh is mesh and not result.features and not records


def _loaded_plate(name: str = "plate_holes.stl") -> Any:
    """Ein Projekt mit einem Ladeschritt, wie das Fenster es anlegt."""
    from app.core.scene.project import new_project
    from app.core.types import Source

    meshes = Path(__file__).parent / "data" / "meshes"
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = (meshes / name).read_bytes()
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    return project


def test_first_the_model_then_its_features_in_a_second_run(profile: Profile) -> None:
    """Erst das Modell, dann die Merkmale — zwei Läufe mit einem Cache (KUNDE-14).

    Das Piratenschiff erschien nach 57 statt 12 Sekunden, weil es seit 0.5.1
    unter der Grenze der Vollerkennung liegt und vor dem ersten Bild erkannt
    wurde; 48 Sekunden davon stand der Balken auf „Merkmale erkennen · 0 %“.
    Der erste Lauf ohne Erkennung zeigt Geometrie und Bericht und nennt, was er
    ausließ. Der zweite trifft den Ladeschritt im Cache, erkennt, und sein
    Anteil wandert dabei über den Bereich des Schritts bis eins. Danach kennt
    der Merker alles, und ein Lauf ohne Erkennung lässt nichts mehr aus.
    """
    from itertools import pairwise

    from app.core.perceive.features import forget_cache
    from app.core.scene.project import ProjectSources

    forget_cache()
    project = _loaded_plate()
    sources = ProjectSources(project)
    cache = ResultCache()
    body_id = project.document.ops[-1].outputs[0]

    first = evaluate(project.document, profile, sources=sources, cache=cache, detect_features=False)
    assert first.complete
    assert first.recognition_left_out == {body_id}
    assert not first.scene.objects[body_id].features

    told: list[tuple[float, str]] = []
    second = evaluate(
        project.document,
        profile,
        sources=sources,
        cache=cache,
        progress=lambda fraction, text: told.append((fraction, text)),
    )
    assert second.complete
    assert cache.statistics.hits >= 1, "der Ladeschritt kommt aus dem Cache"
    assert second.recognition_left_out == frozenset()
    kinds = sorted(feature.kind for feature in second.scene.objects[body_id].features.values())
    assert kinds.count("hole") == 4
    during = [fraction for fraction, text in told if text == "Merkmale erkennen"]
    assert during[0] == 0.0 and during[-1] == 1.0, during
    assert all(later > earlier for earlier, later in pairwise(during[1:])), during
    assert len(during) > 5, "der Balken wandert während der Erkennung"

    third = evaluate(project.document, profile, sources=sources, cache=cache, detect_features=False)
    assert third.recognition_left_out == frozenset(), "der Merker kennt die Merkmale jetzt"
    assert third.scene.objects[body_id].features == second.scene.objects[body_id].features


@pytest.mark.parametrize("detect_features", [False, True])
def test_a_large_import_without_recognition_is_not_declined(
    monkeypatch: pytest.MonkeyPatch, profile: Profile, detect_features: bool
) -> None:
    """Der Lauf ohne Erkennung fragt nicht vor der Vollerkennung — und sagt nicht ab (KUNDE-14).

    Über der automatischen Grenze stellt erst der Lauf mit Erkennung die Frage.
    Der erste Lauf des Wegs „erst das Modell“ darf deshalb weder fragen noch
    „ausgelassen“ in den Bericht schreiben: Nichts ist entschieden, und der
    Satz stünde über einer Frage, die gleich kommt. Er nennt den Körper als
    ausgelassen; der zweite Lauf fragt und schreibt die Absage wie bisher.
    """
    from importlib import import_module

    from app.core.perceive.features import forget_cache
    from app.core.scene.project import ProjectSources

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    forget_cache()
    project = _loaded_plate()
    body_id = project.document.ops[-1].outputs[0]
    asked: list[str] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append(question)
        return choices[0]

    result = evaluate(
        project.document,
        profile,
        sources=ProjectSources(project),
        ask=ask,
        detect_features=detect_features,
    )
    codes = [finding.code for finding in result.scene.report.findings]
    assert bool(asked) is detect_features
    assert ("perceive.too_large" in codes) is detect_features
    assert result.recognition_left_out == (frozenset() if detect_features else {body_id})


@pytest.mark.parametrize("allowed", [False, True])
def test_large_recognition_answer_survives_save_cache_undo_and_changed_source(
    monkeypatch, tmp_path, profile, allowed
):
    """Echter Import mit kleinem Testbudget: Cache ist kein Ersatz für die gespeicherte Wahl."""
    from importlib import import_module

    from app.core.geom.mesh import MeshCodec
    from app.core.perceive.features import forget_cache
    from app.core.scene.cache import DiskCache
    from app.core.scene.project import ProjectSources, checksum, load, new_project, save
    from app.core.types import Source

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source("src_1", "import", "sources/box.stl", "")
    project.sources["src_1"] = _small_body().raw.export(file_type="stl")
    history = History(project.document)
    history.apply("Laden", [OperationDraft("load", params={"source": "src_1", "unit": "mm"})])
    cache_path = tmp_path / "cache"
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=cache_path))
    asked = []

    def answer(question, choices):
        asked.append(question)
        return choices[int(allowed)]

    def run(project, cache, ask):
        return evaluate(
            project.document, profile, sources=ProjectSources(project), cache=cache, ask=ask
        )

    first = run(project, cache, answer)
    assert first.complete and len(asked) == 1
    assert bool(first.scene.objects["obj_1"].features) is allowed
    assert history.record_matches(first.matches)
    recorded = dict(project.document.ops[0].matches)

    def refuse(*_):
        pytest.fail("an unchanged saved choice must not ask again")

    second = run(project, cache, refuse)
    assert second.complete and not second.matches
    assert second.scene.objects["obj_1"].features == first.scene.objects["obj_1"].features
    history.undo()
    history.redo()
    assert project.document.ops[0].matches == recorded
    assert run(project, cache, refuse).complete
    reopened = load(save(project, tmp_path / "large.p3d"))
    forget_cache()
    cold = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=cache_path))
    again = run(reopened, cold, refuse)
    assert again.complete and not again.matches
    assert bool(again.scene.objects["obj_1"].features) is allowed

    if allowed:
        from app.core.registry import REGISTRY

        registry = Registry()
        registry.register(REGISTRY.get("load"))

        @op_params
        class InspectParams(BaseParams):
            at: str = param(title=_("Merkmal"), kind="feature")

        @register_op(
            name="inspect_large_face",
            title=_("Merkmal prüfen"),
            category="scene",
            params=InspectParams,
            registry=registry,
        )
        def inspect(ctx):
            assert ctx.params.at in ctx.inputs[0].features
            return OpResult(outputs=list(ctx.inputs))

        face = next(iter(again.scene.objects["obj_1"].features))
        preview_history = History(reopened.document, registry=registry)
        preview_history.apply(
            "Merkmal prüfen",
            [OperationDraft("inspect_large_face", inputs=("obj_1",), params={"at": face})],
        )
        for clear_features in (False, True):
            if clear_features:
                forget_cache()
            preview = evaluate(
                reopened.document,
                profile,
                sources=ProjectSources(reopened),
                registry=registry,
                cache=cold,
                ask=refuse,
                detect_features=False,
            )
            assert preview.complete
            assert face in preview.scene.objects["obj_1"].features
        preview_history.undo()

    # Gleiche Dreieckszahl und Kennung, andere Koordinaten: erneut entscheiden.
    different = _small_body().raw.copy()
    different.apply_scale((1.2, 1, 1))
    reopened.sources["src_1"] = different.export(file_type="stl")
    reopened.document.sources["src_1"] = dataclasses.replace(
        reopened.document.sources["src_1"], sha256=checksum(reopened.sources["src_1"])
    )
    changed = run(reopened, cold, answer)
    assert changed.complete and len(asked) == 2
    assert changed.matches
    assert (
        next(iter(changed.matches[1].values()))["scope"] != next(iter(recorded.values()))["scope"]
    )


def test_declined_recognition_does_not_poison_a_later_acceptance(monkeypatch, profile):
    """Die gleiche Geometrie kann nach einer Absage in einem zweiten Import erkannt werden."""
    from importlib import import_module

    from app.core.types import Operation

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    mesh = _small_body()
    declined = module._with_features(
        SceneObject("obj_1", "Teil", mesh),
        {},
        Operation(1, "load", outputs=("obj_1",)),
        lambda _, choices: choices[0],
        [],
        recorded={},
    )
    accepted = module._with_features(
        SceneObject("obj_2", "Teil", mesh),
        {},
        Operation(2, "load", outputs=("obj_2",)),
        lambda _, choices: choices[1],
        [],
        recorded={},
    )
    assert not declined.features and accepted.features
    assert declined.mesh is accepted.mesh is mesh


def test_recognition_estimate_contains_the_reference_and_preserves_generation_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Warnung behauptet keine Sekundenpräzision und erhöht nicht das KI-Ausgabebudget."""
    from app.core.generate import GENERATED_TRIANGLE_LIMIT, GENERATED_TRIANGLE_TARGET
    from app.core.perceive import recognition_time
    from app.core.perceive.local import (
        CONFIRMED_FEATURE_LIMIT_TRIANGLES,
        FEATURE_LIMIT_TRIANGLES,
        recognition_minutes,
    )
    from app.core.perceive.recognition_time import (
        RECOGNITION_REFERENCE_SECONDS,
        RECOGNITION_REFERENCE_TRIANGLES,
    )

    assert FEATURE_LIMIT_TRIANGLES == 1_500_000
    assert CONFIRMED_FEATURE_LIMIT_TRIANGLES == 5_000_000
    assert (GENERATED_TRIANGLE_LIMIT, GENERATED_TRIANGLE_TARGET) == (1_000_000, 750_000)
    assert GENERATED_TRIANGLE_LIMIT <= FEATURE_LIMIT_TRIANGLES, (
        "ein erzeugtes Netz über der Erkennungsgrenze verlöre seine Merkmale"
    )
    # Auf dem Referenzrechner; ein anderer Rechner verschiebt die Spanne mit
    # seiner Rechenprobe (``test_recognition_time.py``).
    monkeypatch.setattr(
        recognition_time, "_probe_seconds", recognition_time.PROBE_REFERENCE_SECONDS
    )
    lower, upper = recognition_minutes(RECOGNITION_REFERENCE_TRIANGLES)
    # Minuten sind die Einheit der Frage: Unter einer Minute steht „1“.
    assert lower * 60 <= max(60, RECOGNITION_REFERENCE_SECONDS) <= upper * 60
    assert 1 <= lower < upper


def test_recognition_memory_estimate_covers_the_measured_imports():
    """Die Speicherangabe der Frage liegt über jedem gemessenen Spitzenbedarf.

    Gemessen am 24.09.2026 je Import in einem eigenen Prozess, Einlesen
    eingeschlossen: Gartenschlauchhalter 392 532 Dreiecke 601 MiB, Piratenschiff
    1 223 836 Dreiecke 2 163 MiB (RM-042), Drache 2 330 374 Dreiecke 3 859 MiB.
    """
    from app.core.perceive.local import recognition_gigabytes

    for triangles, mebibytes in ((392_532, 601), (1_223_836, 2_163), (2_330_374, 3_859)):
        assert recognition_gigabytes(triangles) * 1_000_000_000 >= mebibytes * 2**20
    assert recognition_gigabytes(1) == 1, "nie null Gigabyte"


@pytest.mark.parametrize("nobody", ["refuse", "end_of_input"])
def test_a_large_import_without_anyone_to_ask_loads_like_a_declined_one(monkeypatch, nobody):
    """Kommandozeile ohne Eingabe und Aufrufer ohne Dialog laden weiter — ohne festzuhalten.

    Vor der Anhebung der Grenze lud ein Modell mit zwei Millionen Dreiecken
    dort mit begrenzter Erkennung. Die neue Frage darf daraus keinen Halt
    machen, und eine Absage, die niemand gegeben hat, gehört nicht in den
    Stapel: Das nächste Fenster fragt.
    """
    from importlib import import_module

    from app.core.errors import UserError
    from app.core.geom.mesh import MeshData
    from app.core.types import Operation

    module = import_module("app.core.scene.evaluate")
    mesh = _small_body()
    monkeypatch.setattr(MeshData, "triangle_count", property(lambda _: 2_330_374))
    monkeypatch.setattr(module, "detect", lambda *_a, **_k: pytest.fail("unexpected full scan"))

    def end_of_input(question, choices):
        # Wie ``cli.main.terminal_ask`` bei EOF.
        raise UserError(title=_("Diese Frage braucht eine Antwort, und hier ist niemand."))

    ask = module._refuse_to_guess if nobody == "refuse" else end_of_input
    recorded, findings = {}, []
    result = module._with_features(
        SceneObject("obj_1", "Teil", mesh),
        {},
        Operation(1, "load", outputs=("obj_1",)),
        module._WatchedAsk(ask),
        findings,
        recorded=recorded,
    )
    assert result.mesh is mesh and not result.features
    assert not recorded
    assert [finding.code for finding in findings] == ["perceive.too_large"]


def test_a_large_import_through_the_default_question_completes(monkeypatch, profile):
    """Ende zu Ende: ``evaluate`` ohne ``ask`` rechnet den Import durch."""
    from importlib import import_module

    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source("src_1", "import", "sources/box.stl", "")
    project.sources["src_1"] = _small_body().raw.export(file_type="stl")
    History(project.document).apply(
        "Laden", [OperationDraft("load", params={"source": "src_1", "unit": "mm"})]
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    assert not result.matches
    assert "perceive.too_large" in {finding.code for finding in result.scene.report.findings}


def test_a_confirmed_large_import_reaches_the_disk_cache(monkeypatch, tmp_path, profile):
    """Die Erkennungsfrage macht den rohen Import nicht zu einem Ergebnis nur der Sitzung.

    Gefragt wird nach der Operation, und ihre Ausgabe hängt nicht an der
    Antwort. Als Frage des Schritts gezählt, ging der Import eines großen
    Modells nie auf die Platte — und jedes Öffnen las die Datei neu.
    """
    from importlib import import_module

    from app.core.geom.mesh import MeshCodec
    from app.core.ingest import ops as ingest_ops
    from app.core.perceive.features import forget_cache
    from app.core.scene.cache import DiskCache
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source("src_1", "import", "sources/box.stl", "")
    project.sources["src_1"] = _small_body().raw.export(file_type="stl")
    history = History(project.document)
    history.apply("Laden", [OperationDraft("load", params={"source": "src_1", "unit": "mm"})])
    reads = []
    normalise = ingest_ops.normalise

    def counted(*args, **kwargs):
        reads.append(1)
        return normalise(*args, **kwargs)

    monkeypatch.setattr(ingest_ops, "normalise", counted)
    directory = tmp_path / "cache"

    first = evaluate(
        project.document,
        profile,
        sources=ProjectSources(project),
        cache=ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory)),
        ask=lambda _question, choices: choices[1],
    )
    assert first.complete and first.scene.objects["obj_1"].features
    assert history.record_matches(first.matches)
    assert reads == [1]

    forget_cache()
    reopened = evaluate(
        project.document,
        profile,
        sources=ProjectSources(project),
        cache=ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory)),
        ask=lambda *_: pytest.fail("the saved choice must not ask again"),
    )
    assert reopened.complete and reopened.scene.objects["obj_1"].features
    assert reads == [1], "der Import kam von der Platte und wurde nicht neu gelesen"


@pytest.mark.parametrize("triangles", [None, 2_330_374])
def test_running_out_of_memory_costs_the_recognition_not_the_import(monkeypatch, triangles):
    """Ein Speicherfehler der Erkennung lässt das Modell stehen und wiederholt sich nicht.

    ``None`` ist ein Import unter der automatischen Grenze, die Zahl einer
    darüber mit Zustimmung (RM-235: ``MemoryError`` in ``features._fitted``
    schon bei 1,2 Millionen Dreiecken). Vorher hielt der Ladeschritt an, und
    nach dem Warten stand kein Modell da.
    """
    from importlib import import_module

    from app.core.geom.mesh import MeshData
    from app.core.types import Operation

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(import_module("app.core.perceive.local"), "_OUT_OF_MEMORY", set())
    mesh = _small_body()
    if triangles is not None:
        monkeypatch.setattr(MeshData, "triangle_count", property(lambda _: triangles))

    def out_of_memory(*_args, **_kwargs):
        raise MemoryError

    monkeypatch.setattr(module, "detect", out_of_memory)
    recorded, findings = {}, []
    operation = Operation(1, "load", outputs=("obj_1",))
    body = SceneObject("obj_1", "Teil", mesh)
    result = module._with_features(
        body, {}, operation, lambda _question, choices: choices[1], findings, recorded=recorded
    )
    assert result.mesh is mesh and not result.features
    assert [(finding.code, finding.severity) for finding in findings] == [
        ("perceive.too_large", "warning")
    ]
    assert "Arbeitsspeicher" in str(findings[0].message)
    assert "Alle Merkmale erkennen" in str(findings[0].message), "die Absage steht am Schritt"
    assert [(record["allowed"], record.get("out_of_memory")) for record in recorded.values()] == [
        (False, True)
    ]

    # Der nächste Lauf liest die Absage und versucht es nicht noch einmal —
    # und sagt weiter, warum (Review B11): eine Warnung über den Speicher,
    # nicht der Hinweis auf eine ausgelassene Erkennung.
    monkeypatch.setattr(module, "detect", lambda *_a, **_k: pytest.fail("the run repeated"))
    later: list = []
    again = module._with_features(
        body,
        {},
        dataclasses.replace(operation, matches=dict(recorded)),
        lambda *_: pytest.fail("unexpected question"),
        later,
        recorded={},
    )
    assert again.mesh is mesh and not again.features
    assert [(finding.code, finding.severity) for finding in later] == [
        ("perceive.too_large", "warning")
    ]
    assert str(later[0].message) == str(findings[0].message)
    assert later[0].values["memory"] >= 1


def test_a_memory_error_outside_the_import_still_stops_the_step(monkeypatch):
    """Nur die Erkennung eines geladenen Körpers hat einen Rückweg ohne sie."""
    from importlib import import_module

    from app.core.types import Operation

    module = import_module("app.core.scene.evaluate")

    def out_of_memory(*_args, **_kwargs):
        raise MemoryError

    monkeypatch.setattr(module, "detect", out_of_memory)
    with pytest.raises(MemoryError):
        module._with_features(
            SceneObject("obj_1", "Teil", _small_body()),
            {},
            Operation(2, "repair", inputs=("obj_1",), outputs=("obj_1",)),
            lambda *_: pytest.fail("unexpected question"),
            [],
            recorded={},
        )


def test_a_declined_recognition_can_be_asked_again(monkeypatch, profile):
    """Eine Absage beim Laden ist keine Sackgasse bis zum Neuladen der Datei.

    ``History.reopen_recognition`` nimmt die gespeicherte Wahl zurück, und die
    nächste Auswertung stellt dieselbe Frage mit Zeitschätzung wieder; die
    neue Antwort gilt, und der Befund mit dem Rückweg verschwindet.
    """
    from importlib import import_module

    from app.core.perceive.match_records import recognition_answer_key
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source("src_1", "import", "sources/box.stl", "")
    project.sources["src_1"] = _small_body().raw.export(file_type="stl")
    history = History(project.document)
    history.apply("Laden", [OperationDraft("load", params={"source": "src_1", "unit": "mm"})])
    asked = []

    def answer(allowed):
        def ask(question, choices):
            asked.append(question)
            return choices[int(allowed)]

        return ask

    def run(ask):
        return evaluate(project.document, profile, sources=ProjectSources(project), ask=ask)

    declined = run(answer(False))
    assert history.record_matches(declined.matches)
    assert not declined.scene.objects["obj_1"].features
    assert "„Alle Merkmale erkennen“" in next(
        str(finding.message)
        for finding in declined.scene.report.findings
        if finding.code == "perceive.too_large"
    )

    assert history.reopen_recognition(("obj_1",))
    assert recognition_answer_key("obj_1") not in project.document.ops[0].matches
    assert not history.reopen_recognition(("obj_1",)), "nichts mehr zurückzunehmen"

    accepted = run(answer(True))
    assert len(asked) == 2, "die Frage kam wieder"
    assert accepted.scene.objects["obj_1"].features
    assert "perceive.too_large" not in {f.code for f in accepted.scene.report.findings}
    assert history.record_matches(accepted.matches)
    assert run(lambda *_: pytest.fail("the new answer holds")).scene.objects["obj_1"].features


def _confirmed_large_box(monkeypatch, profile, second):
    """Ein Quader, der als großes Netz gilt, geladen und von ``second`` weiterbearbeitet."""
    from importlib import import_module

    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source("src_1", "import", "sources/box.stl", "")
    project.sources["src_1"] = _small_body().raw.export(file_type="stl")
    history = History(project.document)
    history.apply("Laden", [OperationDraft("load", params={"source": "src_1", "unit": "mm"})])
    history.apply("Weiter", [second])

    def run(allowed):
        return evaluate(
            project.document,
            profile,
            sources=ProjectSources(project),
            ask=lambda _question, choices: choices[int(allowed)],
        )

    return run


@pytest.mark.parametrize(
    "second",
    [
        OperationDraft("scale_object", inputs=("obj_1",), params={"factor": 1.5}),
        OperationDraft("translate_object", inputs=("obj_1",), params={"dx": 5.0}),
    ],
    ids=["scale", "translate"],
)
def test_a_confirmed_recognition_holds_for_the_later_steps_of_the_body(
    monkeypatch, profile, second
):
    """Die Zustimmung beim Laden gilt dem Körper, nicht dem einen Netz (RM-235, B10).

    Vorher fiel der erste Folgeschritt auf die örtliche Nachmessung aller
    bekannten Merkmale zurück, und die hielt an jedem großen an — nach einem
    Verschieben um 5 mm stand „zu viele Dreiecke für die lokale Suche“ im
    Bericht. Jetzt erkennt der Folgeschritt vollständig nach; die örtliche
    Nachmessung wird gar nicht erst gefragt.
    """
    from app.core.perceive import local

    monkeypatch.setattr(
        local, "detect_known", lambda *_a, **_k: pytest.fail("the step fell back to local")
    )
    result = _confirmed_large_box(monkeypatch, profile, second)(True)
    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    assert result.scene.objects["obj_1"].features
    assert "perceive.too_large" not in {f.code for f in result.scene.report.findings}


def test_a_declined_recognition_keeps_the_later_steps_local(monkeypatch, profile):
    """Wer abgelehnt hat, bekommt auch im Folgeschritt keine lange Vollerkennung."""
    from importlib import import_module

    monkeypatch.setattr(
        import_module("app.core.scene.evaluate"),
        "detect",
        lambda *_a, **_k: pytest.fail("the full recognition ran"),
    )
    second = OperationDraft("scale_object", inputs=("obj_1",), params={"factor": 1.5})
    result = _confirmed_large_box(monkeypatch, profile, second)(False)
    assert result.complete
    assert not result.scene.objects["obj_1"].features
    assert "perceive.too_large" in {f.code for f in result.scene.report.findings}


def test_the_way_back_to_the_full_recognition_survives_a_follow_up_step(monkeypatch, profile):
    """Nach einem Verschieben trägt der Befund weiter „Alle Merkmale erkennen“ (Review B1).

    Die Wahl gehört dem Körper; vorher verlor der Befund des Folgeschritts den
    Satz mit dem Rückweg, und im Bericht blieb nur „Dreiecke verringern“.
    """
    second = OperationDraft("translate_object", inputs=("obj_1",), params={"dx": 5.0})
    result = _confirmed_large_box(monkeypatch, profile, second)(False)
    messages = [
        str(finding.message)
        for finding in result.scene.report.findings
        if finding.code == "perceive.too_large"
    ]
    assert messages
    assert all("„Alle Merkmale erkennen“" in message for message in messages)


def _loaded_box_with(second):
    """Ein kleiner Quader, geladen und von ``second`` weiterbearbeitet."""
    from app.core.scene.project import new_project
    from app.core.types import Source

    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source("src_1", "import", "sources/box.stl", "")
    project.sources["src_1"] = _small_body().raw.export(file_type="stl")
    history = History(project.document)
    history.apply("Laden", [OperationDraft("load", params={"source": "src_1", "unit": "mm"})])
    history.apply("Weiter", [second])
    return project, history


def test_a_memory_error_below_the_limit_keeps_the_later_steps_standing(monkeypatch, profile):
    """Speicherfehler beim Laden unter der automatischen Grenze, danach Skalieren (Review B2).

    Vorher lief der Folgeschritt wieder in die volle Erkennung, derselbe Fehler
    kam als Programmfehler am Schritt, und das Modell ließ sich nicht einmal
    verschieben — bei jeder Auswertung.
    """
    from importlib import import_module

    from app.core.scene.project import ProjectSources

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(import_module("app.core.perceive.local"), "_OUT_OF_MEMORY", set())
    tried = []

    def out_of_memory(mesh, **_kwargs):
        tried.append(mesh.triangle_count)
        raise MemoryError

    monkeypatch.setattr(module, "detect", out_of_memory)
    project, history = _loaded_box_with(
        OperationDraft("scale_object", inputs=("obj_1",), params={"factor": 1.5})
    )
    for _run in range(2):
        result = evaluate(
            project.document,
            profile,
            sources=ProjectSources(project),
            ask=lambda *_: pytest.fail("below the limit nobody is asked"),
        )
        assert result.complete, [str(finding.message) for finding in result.scene.report.findings]
        history.record_matches(result.matches)
    assert len(tried) == 1, "nur der Ladeschritt versuchte es, und nur beim ersten Lauf"


def test_a_memory_error_after_a_confirmation_is_not_repeated(monkeypatch, profile):
    """Ein bestätigter Folgeschritt, der am Speicher scheitert, versucht es nicht bei jeder
    Auswertung neu (Review B3) — am echten Netz kostete jeder Versuch Minuten."""
    from importlib import import_module

    import numpy as np

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(import_module("app.core.perceive.local"), "_OUT_OF_MEMORY", set())
    original = module.detect
    failed = []

    def scaled_fails(mesh, **kwargs):
        if float(np.ptp(np.asarray(mesh.raw.vertices)[:, 0])) > 25.0:
            failed.append(1)
            raise MemoryError
        return original(mesh, **kwargs)

    monkeypatch.setattr(module, "detect", scaled_fails)
    second = OperationDraft("scale_object", inputs=("obj_1",), params={"factor": 1.5})
    run = _confirmed_large_box(monkeypatch, profile, second)
    first, again = run(True), run(True)
    assert first.complete and again.complete
    assert len(failed) == 1
    assert any(
        finding.code == "perceive.too_large" and finding.severity == "warning"
        for finding in again.scene.report.findings
    )


def test_a_feature_that_cannot_be_remeasured_speaks_the_language_of_the_step(monkeypatch):
    """Hält die örtliche Nachmessung an einem gewöhnlichen Schritt an, nennt der Satz,
    was dort hilft — nicht den Suchradius, den der Schritt nicht hat (Review B20)."""
    from importlib import import_module

    from app.core.errors import DECIMATE_MESH, UserError
    from app.core.perceive import local

    module = import_module("app.core.scene.evaluate")

    def budget(*_args, **_kwargs):
        raise local.local_error("budget")

    monkeypatch.setattr(local, "detect_known", budget)
    with pytest.raises(UserError) as caught:
        module._remeasured(
            SceneObject("obj_1", "Teil", _small_body()), {}, {"hole_1"}, module.NeverCancelled()
        )
    assert DECIMATE_MESH in caught.value.suggestions
    assert "Suchradius" not in str(caught.value.title)
    assert caught.value.object_id == "obj_1"


def test_several_large_bodies_of_one_import_share_one_question(monkeypatch):
    """Mehrere große Körper eines Imports: eine Frage mit der Summe (Review B14).

    Vorher kam je Körper eine Frage mit der Schätzung nur dieses einen; die
    Summe erfuhr niemand.
    """
    from importlib import import_module

    from app.core.types import Operation

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    operation = Operation(1, "load", outputs=("obj_1", "obj_2"))
    produced = [
        SceneObject("a", "Teil A", _small_body()),
        SceneObject("b", "Teil B", _small_body()),
    ]
    asked, recorded, told = [], {}, []

    def ask(question, choices):
        asked.append(question)
        return choices[1]

    decided = module._ask_once_for_large_bodies(
        operation,
        produced,
        ask,
        recorded,
        module.NeverCancelled(),
        lambda op_id, key, record: told.append((op_id, key, record["allowed"])),
    )

    assert decided == {"obj_1": True, "obj_2": True}
    assert len(asked) == 1 and "2 Modelle" in asked[0]
    # Die Frage sagt, wo sich eine Absage zurücknehmen lässt (Review B14).
    assert "„Alle Merkmale erkennen“ im Prüfbericht" in asked[0]
    assert sorted(record["object_id"] for record in recorded.values()) == ["obj_1", "obj_2"]
    assert [allowed for _op, _key, allowed in told] == [True, True]
    single = module._ask_once_for_large_bodies(
        Operation(1, "load", outputs=("obj_1",)),
        produced[:1],
        lambda *_: pytest.fail("one body is asked on its own"),
        {},
        module.NeverCancelled(),
        None,
    )
    assert single == {}


def _import_of_two_large_bodies(document, monkeypatch) -> Registry:
    """Ein Ladeschritt mit zwei Körpern über der (auf 1 gesenkten) Erkennungsgrenze."""
    from importlib import import_module

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    monkeypatch.setattr(module, "detect", lambda *_a, **_k: pytest.fail("no full recognition"))
    own = Registry()

    @register_op(
        name="load",
        title=_("Modell einfügen"),
        category="import",
        params=EmptyParams,
        consumes=0,
        produces=2,
        doc=_("Testversion."),
        registry=own,
    )
    def two_bodies(ctx: OpContext) -> OpResult:
        return OpResult(
            outputs=[
                SceneObject(id="", name="Teil A", mesh=_small_body()),
                SceneObject(id="", name="Teil B", mesh=_small_body()),
            ]
        )

    History(document, own).apply(_("Laden"), [OperationDraft(op="load")])
    return own


def test_an_answer_outside_the_shared_recognition_question_stops_at_the_import(
    document: Document, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die gemeinsame Frage eines Imports hält am Ladeschritt an, statt aus ``evaluate`` zu fliegen.

    Die Frage für **einen** Körper steht im Fang um die Merkmalsbindung: Eine
    Antwort, die keine der angebotenen ist, wird dort ein Befund am Schritt mit
    den Antworten als Handlungen. Die gemeinsame Frage für mehrere große Körper
    stand davor, ohne Fang — dieselbe Antwort flog als ``AmbiguityError`` aus
    der Auswertung, und statt des Prüfberichts kam ein Absturz des Arbeiters.
    """
    registry = _import_of_two_large_bodies(document, monkeypatch)
    asked: list[str] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append(question)
        return "Vielleicht"

    result = evaluate(document, profile, registry=registry, ask=ask)

    assert len(asked) == 1 and "2 Modelle" in asked[0]
    assert result.stopped_at == document.ops[0].id
    (stop,) = [entry for entry in result.scene.report.findings if entry.severity == "error"]
    assert stop.op_id == document.ops[0].id
    assert "choose:Sofort laden" in {action.id for action in stop.suggestions}
    assert not result.matches


def test_nobody_to_ask_about_the_shared_recognition_asks_no_body_again(
    document: Document, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne jemanden zum Fragen kommt die gemeinsame Frage einmal, nicht einmal mehr je Körper.

    ``_ask_once_for_large_bodies`` verspricht dann: Jeder Körper lädt wie nach
    einer Absage, **ohne Frage**, und nichts wird festgehalten. Tatsächlich
    fragte danach jeder Körper noch einmal einzeln — die Kommandozeile ohne
    Eingabe druckte so zu einer Baugruppe mit zwei großen Körpern drei Fragen,
    von denen keine eine Antwort bekommen konnte.
    """
    from app.core.errors import UserError

    registry = _import_of_two_large_bodies(document, monkeypatch)
    asked: list[str] = []

    def end_of_input(question: str, choices: list[str]) -> str:
        # Wie ``cli.main.terminal_ask`` bei EOF.
        asked.append(question)
        raise UserError(title=_("Diese Frage braucht eine Antwort, und hier ist niemand."))

    result = evaluate(document, profile, registry=registry, ask=end_of_input)

    assert result.complete
    assert len(asked) == 1 and "2 Modelle" in asked[0]
    assert not result.matches, "eine Absage, die niemand gegeben hat, gehört nicht in den Stapel"
    skipped = [
        entry for entry in result.scene.report.findings if entry.code == "perceive.too_large"
    ]
    assert sorted(entry.object_id for entry in skipped) == ["obj_1", "obj_2"]


def test_the_answer_to_the_recognition_question_is_told_at_once(monkeypatch, profile):
    """Die Antwort kommt sofort beim Aufrufer an, nicht erst mit dem Ergebnis (Review B18)."""
    from importlib import import_module

    from app.core.scene.project import ProjectSources

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    project, _history = _loaded_box_with(
        OperationDraft("translate_object", inputs=("obj_1",), params={"dx": 5.0})
    )
    told = []
    result = evaluate(
        project.document,
        profile,
        sources=ProjectSources(project),
        ask=lambda _question, choices: choices[1],
        on_recognition_answer=lambda op_id, key, record: told.append((op_id, dict(record))),
    )
    assert result.complete
    # Genau einmal: Der Folgeschritt bewegt nur, der Merker trägt die
    # Erkennung, und eine lange Erkennung startet dort nicht (Review R5).
    assert told == [(1, {"object_id": "obj_1", "scope": told[0][1]["scope"], "allowed": True})]


def _detect_failing_once(module, monkeypatch):
    """Der erste Aufruf von ``detect`` läuft in den Speicher, jeder weitere rechnet."""
    real = module.detect
    calls: list[int] = []

    def detect(mesh, **kwargs):
        calls.append(mesh.triangle_count)
        if len(calls) == 1:
            raise MemoryError
        return real(mesh, **kwargs)

    monkeypatch.setattr(module, "detect", detect)
    return calls


@pytest.mark.parametrize("limit", [None, 1])
def test_a_new_decision_after_running_out_of_memory_tries_again(monkeypatch, profile, limit):
    """Nach dem Speicherfehler entscheidet „Alle Merkmale erkennen“ neu (Review N2).

    ``None`` lädt unter der automatischen Grenze, ``1`` darüber mit Zustimmung.
    Vorher meldete der Prozessmerker nach der neuen Entscheidung sofort
    denselben Speicherfehler, ohne dass ``detect`` einmal lief — der Kunde,
    der Programme geschlossen hatte, kam nur über einen Neustart weiter.
    """
    from importlib import import_module

    from app.core.perceive import local
    from app.core.scene.project import ProjectSources

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(local, "_OUT_OF_MEMORY", set())
    if limit is not None:
        monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", limit)
    project, history = _loaded_box_with(
        OperationDraft("translate_object", inputs=("obj_1",), params={"dx": 5.0})
    )
    calls = _detect_failing_once(module, monkeypatch)

    def run():
        result = evaluate(
            project.document,
            profile,
            sources=ProjectSources(project),
            ask=lambda _question, choices: choices[1],
        )
        history.record_matches(result.matches)
        return result

    failed = run()
    assert failed.complete and not failed.scene.objects["obj_1"].features
    assert len(calls) == 1

    # Über der Grenze ist die Antwort auf die neue Frage die neue
    # Entscheidung; unter ihr gibt es keine Frage, und den Merker leert,
    # wer neu entscheiden lässt — Fenster und Kommandozeile (Review R3).
    assert history.reopen_recognition(("obj_1",))
    if limit is None:
        local.forget_out_of_memory()
    retried = run()
    assert len(calls) >= 2, "die neue Entscheidung hat einen Versuch bekommen"
    assert retried.scene.objects["obj_1"].features
    assert not any(
        finding.code == "perceive.too_large" for finding in retried.scene.report.findings
    )


def test_the_same_mesh_in_another_project_is_a_new_decision(monkeypatch, profile):
    """Derselbe Import in einem neuen Projekt fragt den Speichermerker nicht (Review N2)."""
    from importlib import import_module

    from app.core.perceive import local
    from app.core.scene.project import ProjectSources

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(local, "_OUT_OF_MEMORY", set())
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    first, _history = _loaded_box_with(
        OperationDraft("translate_object", inputs=("obj_1",), params={"dx": 5.0})
    )
    calls = _detect_failing_once(module, monkeypatch)
    evaluate(
        first.document,
        profile,
        sources=ProjectSources(first),
        ask=lambda _question, choices: choices[1],
    )
    assert calls == [calls[0]]
    other, _other_history = _loaded_box_with(
        OperationDraft("translate_object", inputs=("obj_1",), params={"dx": 5.0})
    )
    fresh = evaluate(
        other.document,
        profile,
        sources=ProjectSources(other),
        ask=lambda _question, choices: choices[1],
    )
    assert len(calls) >= 2
    assert fresh.scene.objects["obj_1"].features


def test_a_body_that_grows_past_the_limit_offers_no_way_back(monkeypatch, profile):
    """Unter der Grenze geladen, danach gewachsen: kein Rückweg im Satz (Review N3).

    Die Frage gibt es nur am Ladeschritt, und der hatte nichts zu fragen. Der
    Befund versprach „Alle Merkmale erkennen“, und der Klick rechnete neu,
    ohne dass eine Frage kam.
    """
    from importlib import import_module

    from app.core.scene.history import recognition_reopenable
    from app.core.scene.project import ProjectSources

    module = import_module("app.core.scene.evaluate")
    project, history = _loaded_box_with(
        OperationDraft("subdivide_surface", inputs=("obj_1",), params={"edge": 4.0})
    )
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", _small_body().triangle_count)
    result = evaluate(
        project.document,
        profile,
        sources=ProjectSources(project),
        ask=lambda *_: pytest.fail("nothing to ask: the load step is below the limit"),
    )
    history.record_matches(result.matches)
    (finding,) = [f for f in result.scene.report.findings if f.code == "perceive.too_large"]
    assert finding.op_id == 2
    assert result.scene.objects["obj_1"].mesh.triangle_count > _small_body().triangle_count
    assert "Alle Merkmale erkennen" not in str(finding.message)
    assert "Dreiecke verringern" in str(finding.message)
    assert not recognition_reopenable(project.document, "obj_1")
    assert not history.reopen_recognition(("obj_1",))


def test_a_saved_confirmation_is_told_when_the_long_recognition_starts(monkeypatch, profile):
    """Auch ein „Ja“ aus der Datei kommt beim Aufrufer an (Review B18).

    Ohne das bot ein Abbruch beim Wiederöffnen keinen Weg zum Modell: Die
    Sitzung kannte nur Antworten, die in diesem Lauf gegeben wurden.
    """
    from importlib import import_module

    from app.core.scene.project import ProjectSources

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(module, "FEATURE_LIMIT_TRIANGLES", 1)
    project, history = _loaded_box_with(
        OperationDraft("translate_object", inputs=("obj_1",), params={"dx": 5.0})
    )
    first = evaluate(
        project.document,
        profile,
        sources=ProjectSources(project),
        ask=lambda _question, choices: choices[1],
    )
    history.record_matches(first.matches)

    def reopen() -> list:
        told: list = []
        evaluate(
            project.document,
            profile,
            sources=ProjectSources(project),
            ask=lambda *_: pytest.fail("the saved choice must not ask again"),
            on_recognition_answer=lambda op_id, key, record: told.append((op_id, dict(record))),
        )
        return told

    # Der Merker kennt das Netz: Es startet keine lange Erkennung, und
    # gemeldet wird nichts — sonst böte ein Abbruch irgendeiner Rechnung an,
    # eine längst fertige Erkennung zurückzunehmen (Review R5).
    assert reopen() == []

    # Kennt er es nicht, startet sie, und die gespeicherte Zustimmung kommt an.
    monkeypatch.setattr(module, "known_detection", lambda _mesh: None)
    told = reopen()
    assert told and {(op_id, record["allowed"]) for op_id, record in told} == {(1, True)}
    assert told[0][1]["object_id"] == "obj_1"


def test_an_unrecorded_memory_decline_does_not_repeat_the_long_run(monkeypatch, profile):
    """Kommt die Absage nach dem Speicherfehler nicht am Ladeschritt an, läuft
    derselbe Minutenlauf nicht noch einmal (Review R3).

    Ein Lauf, den der Kunde abbricht oder eine Änderung überholt, hält sein
    Ergebnis nie fest; ``evaluate_now`` tut es nie. Vorher galt der nächste
    Lauf dann als neue Entscheidung und übersprang den Merker. Die Absage geht
    deshalb sofort an den Aufrufer, wie eine Antwort.
    """
    from importlib import import_module

    from app.core.perceive import local
    from app.core.scene.project import ProjectSources

    module = import_module("app.core.scene.evaluate")
    monkeypatch.setattr(local, "_OUT_OF_MEMORY", set())
    project, _history = _loaded_box_with(
        OperationDraft("translate_object", inputs=("obj_1",), params={"dx": 5.0})
    )
    calls: list[int] = []

    def out_of_memory(mesh, **_kwargs):
        calls.append(mesh.triangle_count)
        raise MemoryError

    monkeypatch.setattr(module, "detect", out_of_memory)
    told: list = []
    for _run in range(2):
        result = evaluate(
            project.document,
            profile,
            sources=ProjectSources(project),
            ask=lambda *_: pytest.fail("below the limit nobody is asked"),
            on_recognition_answer=lambda op_id, key, record: told.append((op_id, dict(record))),
        )
        assert result.complete and not result.scene.objects["obj_1"].features
    assert len(calls) == 1, "der zweite Lauf hat den Speicherfehler nicht wiederholt"
    assert told[0][0] == 1
    assert (told[0][1]["allowed"], told[0][1]["out_of_memory"]) == (False, True)


def _session_with_unshown_import(path: Path) -> Any:
    """Eine Sitzung mit einem Ladeschritt, dessen Körper noch nie im Bild stand."""
    from app.ui.session import Session

    session = Session()
    assert session.import_model(path, unit="mm")
    # Der Arbeiter, den das Einfügen anstößt, meldet ohne Ereignisschleife
    # nichts zurück; angehalten und abgewartet, rechnet hier nur der Test.
    running = session._worker
    session.cancel_evaluation()
    if running is not None:
        assert running.wait(60_000)
    session.cancel_signal.reset()
    return session


def test_a_large_import_is_shown_before_its_recognition(monkeypatch) -> None:
    """Das Modell steht im Bild, bevor seine Merkmale erkannt sind (KUNDE-14).

    Das Piratenschiff (1,2 Mio. Dreiecke) erschien in 0.5.1 erst nach 60 s:
    8 s Einlesen, dann 51 s Erkennung unter dem Ladeschleier. Der Ladeweg
    rechnet jetzt erst das Bild ohne Erkennung, dann denselben Lauf mit ihr —
    und der liest die Geometrie aus dem Cache, statt noch einmal einzulesen.
    """
    from app.core.registry import REGISTRY
    from app.ui import session as session_module
    from app.ui.session import _EvaluationWorker

    monkeypatch.setattr(session_module, "PICTURE_FIRST_TRIANGLES", 1)
    session = _session_with_unshown_import(MESHES / "plate_holes.stl")
    assert session.picture_first(), "ein Ladeschritt ohne Bild zeigt erst das Modell"

    spec = REGISTRY.get("load")
    real = spec.fn
    loads: list[int] = []

    def counted(ctx: OpContext) -> Any:
        loads.append(1)
        return real(ctx)

    worker = _EvaluationWorker(session, picture_first=True)
    pictures: list[Any] = []
    worker.pictureWith.connect(pictures.append)
    object.__setattr__(spec, "fn", counted)
    try:
        result = worker._evaluate(session)
    finally:
        object.__setattr__(spec, "fn", real)

    assert len(pictures) == 1, "genau ein Bild vor der Erkennung"
    picture = pictures[0]
    body = next(iter(picture.scene.objects.values()))
    assert not body.features, "das Bild trägt noch keine Merkmale"
    codes = [entry.code for entry in picture.scene.report.findings]
    assert "perceive.pending" in codes and "perceive.too_large" not in codes
    assert any(entry.features for entry in result.scene.objects.values()), "danach erkannt"
    assert "perceive.pending" not in {entry.code for entry in result.scene.report.findings}
    assert len(loads) == 1, "der zweite Lauf nimmt die Geometrie aus dem Cache"

    session._on_picture(picture)
    assert session.last_result is picture and session.picture is picture
    assert not session.result_current, "ein Bild ist kein fertiges Ergebnis"
    assert session.picture_first(), "solange ein Bild steht, zeigt auch der nächste Lauf eins"
    session._on_finished(result)
    assert session.picture is None and session.last_result is result
    assert not session.picture_first(), "danach rechnet eine Änderung wie bisher"


def test_a_small_import_is_not_shown_twice(monkeypatch) -> None:
    """Unter der Schwelle kommt kein Bild: Die Erkennung ist schneller als ein
    zweiter Aufbau von Baum, Bericht und Ansicht (KUNDE-14)."""
    from app.ui.session import PICTURE_FIRST_TRIANGLES, _EvaluationWorker

    session = _session_with_unshown_import(MESHES / "plate_holes.stl")
    worker = _EvaluationWorker(session, picture_first=True)
    pictures: list[Any] = []
    worker.pictureWith.connect(pictures.append)
    result = worker._evaluate(session)
    body = next(iter(result.scene.objects.values()))
    assert body.mesh.triangle_count < PICTURE_FIRST_TRIANGLES
    assert not pictures


def test_the_run_after_the_picture_does_not_ask_again(monkeypatch) -> None:
    """Was das Bild schon gefragt hat, beantwortet der Lauf danach selbst (KUNDE-14).

    Beide Läufe rechnen denselben Stand; eine zweite, gleiche Frage am
    Bildschirm wäre ein Fenster für nichts.
    """
    from app.core.errors import QuestionDeclined
    from app.ui.session import Session

    session = Session()
    asked: list[Any] = []
    session.askRequested.connect(asked.append)
    session._pending.replay = {
        ("Welche Einheit?", ("mm", "Zoll")): "Zoll",
        ("Welche Seite?", ("oben", "unten")): None,
    }
    try:
        assert session.ask_from_worker("Welche Einheit?", ["mm", "Zoll"]) == "Zoll"
        with pytest.raises(QuestionDeclined):
            session.ask_from_worker("Welche Seite?", ["oben", "unten"])
    finally:
        session._pending.replay = None
    assert not asked, "keine Frage am Bildschirm"


def test_a_halted_load_is_not_computed_twice(tmp_path: Path) -> None:
    """Hält schon der Ladeschritt an, gibt es nichts zu zeigen und nichts zu
    erkennen — der Lauf endet mit dem ersten Durchgang, und der nächste Lauf
    rechnet ihn nicht zweimal (KUNDE-12, KUNDE-14)."""
    from app.core.registry import REGISTRY
    from app.ui.session import _EvaluationWorker

    broken = tmp_path / "kaputt.stl"
    # Wie ein abgebrochener Download: Facetten angekündigt, keine gültige Ecke.
    broken.write_bytes(b"solid x\n facet normal 0 0 1\n  outer loop\n   vertex 0 0 nope\n" * 3)
    session = _session_with_unshown_import(broken)
    spec = REGISTRY.get("load")
    real = spec.fn
    loads: list[int] = []

    def counted(ctx: OpContext) -> Any:
        loads.append(1)
        return real(ctx)

    worker = _EvaluationWorker(session, picture_first=True)
    object.__setattr__(spec, "fn", counted)
    try:
        result = worker._evaluate(session)
    finally:
        object.__setattr__(spec, "fn", real)
    assert result.stopped_at is not None and not result.scene.objects
    assert len(loads) == 1, "ein Durchgang"
    session._on_finished(result)
    assert not session.picture_first(), "der angehaltene Ladeschritt rechnet nicht doppelt"


def _broken_stl(folder: Path) -> Path:
    """Wie ein abgebrochener Download: Facetten angekündigt, keine gültige Ecke."""
    broken = folder / "kaputt.stl"
    broken.write_bytes(b"solid x\n facet normal 0 0 1\n  outer loop\n   vertex 0 0 nope\n" * 3)
    return broken


def _settled(session: Any) -> None:
    """Den Lauf, den eine Rücknahme anstößt, anhalten und abwarten."""
    running = session._worker
    session.cancel_evaluation()
    if running is not None:
        assert running.wait(60_000)
    session.cancel_signal.reset()


def test_a_file_without_a_model_does_not_become_a_step(tmp_path: Path) -> None:
    """Eine Datei, die erst am Ladeschritt scheitert, wird zurückgenommen (KUNDE-12).

    Bis zur Durchsicht 0.5.1 blieb sie als Schritt 1 stehen: leerer
    Arbeitsbereich, jede weitere abgelegte Datei mit „Die Kette hält an“
    abgewiesen. Jetzt geht sie den Weg jedes Lesefehlers — ohne Redo, ohne
    Quelle, und ein neues Projekt gilt danach nicht als geändert.
    """
    from app.core.errors import CHOOSE_ANOTHER_FILE

    session = _session_with_unshown_import(_broken_stl(tmp_path))
    assert session.import_unconfirmed
    rejected: list[Any] = []
    confirmed: list[bool] = []
    session.importRejected.connect(rejected.append)
    session.importConfirmed.connect(lambda: confirmed.append(True))
    result = session.run_evaluation()
    assert result.stopped_at is not None

    session._on_finished(result)
    _settled(session)

    assert len(rejected) == 1 and not confirmed
    error = rejected[0]
    assert str(error.title) == str(_("Diese Datei ließ sich nicht lesen."))
    assert CHOOSE_ANOTHER_FILE in error.suggestions
    assert error.values == {"path": "kaputt.stl"}, "nur der Name, keine Art und keine Nummer"
    assert not session.project.document.ops, "kein Schritt bleibt stehen"
    assert not session.project.document.sources and not session.project.sources
    assert not session.history.can_redo, "Strg+Y bringt die Datei nicht zurück"
    assert not session.modified, "ein neues Projekt, in dem nie etwas ankam"
    assert not session.import_unconfirmed


def test_a_file_with_a_model_is_confirmed(tmp_path: Path) -> None:
    """Das Gegenstück: Ein Modell, das steht, bleibt und wird bestätigt (KUNDE-12)."""
    session = _session_with_unshown_import(MESHES / "cube_clean.stl")
    rejected: list[Any] = []
    confirmed: list[bool] = []
    session.importRejected.connect(rejected.append)
    session.importConfirmed.connect(lambda: confirmed.append(True))
    session._on_finished(session.run_evaluation())
    assert confirmed == [True] and not rejected
    assert len(session.project.document.ops) == 1
    assert not session.import_unconfirmed


def test_a_broken_file_after_other_work_is_not_withdrawn_blindly(tmp_path: Path) -> None:
    """Zurückgenommen wird nur die letzte Transaktion und nur der Import selbst (KUNDE-12)."""
    session = _session_with_unshown_import(_broken_stl(tmp_path))
    result = session.run_evaluation()
    # Danach kam noch etwas — der Import ist nicht mehr die letzte Transaktion.
    session.history.apply(
        _("Quader"),
        [OperationDraft(op="create_box", params={})],
    )
    rejected: list[Any] = []
    session.importRejected.connect(rejected.append)
    session._on_finished(result)
    _settled(session)
    assert not rejected
    assert len(session.project.document.ops) == 2


def test_the_halt_refusal_does_not_repeat_its_sentence(tmp_path: Path) -> None:
    """Die Absage hinter einem Halt nennt nicht noch einmal Art und Nummer (KUNDE-12).

    Unter „Angehalten ist Schritt 1 (Modell einfügen): …“ standen „Art: Die
    Eingabe war so nicht verwendbar.“ und „Operation: 1“ — der Titel des
    Fehlers und die Nummer, die der Satz schon sagt. Die Handler lesen
    ``op_id``.
    """
    session = _session_with_unshown_import(_broken_stl(tmp_path))
    session.last_result = session.run_evaluation()
    refusal = session.halt_in_the_way()
    assert refusal is not None and refusal.op_id == 1
    assert "kind" not in refusal.values and "op" not in refusal.values, refusal.values
