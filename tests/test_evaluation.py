"""Die Auswertung als reine Funktion, und was sie tut, wenn sie nicht
weiterkann (§15).
"""

from __future__ import annotations

import dataclasses
import logging

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
    assert finding.values["expected"] == 1
    assert finding.values["given"] == 0
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
    history.apply(
        "Deckel",
        [OperationDraft(op="create_lid", inputs=(document.ops[-1].outputs[0],), params={})],
    )

    profile = make_profile("centauri-carbon-2", "petg")
    cache = ResultCache()
    sources = ProjectSources(project)

    first = evaluate(document, profile, sources=sources, cache=cache)
    second = evaluate(document, profile, sources=sources, cache=cache)

    assert "obj_1" not in second.scene.objects, "der Deckel hat obj_1 nicht ersetzt"
    assert dict(second.object_names) == dict(first.object_names), (
        f"der Cache-Lauf kennt andere Namen: {dict(second.object_names)} "
        f"statt {dict(first.object_names)}"
    )
    assert second.object_names.get("obj_1") == "Dose", (
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
    # über die Sitzung hinaus.
    assert run("cube_clean.stl") == [True]
    # `bracket_inch.stl` ist zwischen Zoll und Zentimeter mehrdeutig und fragt.
    assert run("bracket_inch.stl") == [False], (
        "ein Ergebnis, für das gefragt wurde, darf nicht über die Sitzung hinaus"
    )


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
    assert "pin_1" in recorded, f"the answer must be reported: {recorded}"
    assert recorded["pin_1"]["kind"] == "hole"

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
    assert history.record_matches({1: {"pin_1": abdruck}}) is True

    entry = project.document.ops[0]
    assert entry.matches["pin_1"] == abdruck
    assert "pin_1" not in entry.params, "an answer of the matcher is not an input"

    # Zweimal dasselbe schreiben ändert nichts — sonst gälte das Dokument nach
    # jeder Auswertung als geändert, ohne dass jemand etwas entschieden hat.
    assert history.record_matches({1: {"pin_1": abdruck}}) is False


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
