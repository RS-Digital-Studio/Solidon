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

    @register_op(
        name="raising_object",
        title=_("Wirft eine fremde Ausnahme"),
        category="prepare",
        params=EmptyParams,
        consumes=1,
        produces=1,
        doc=_("Testfassung."),
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
    profile: Profile,
) -> None:
    """Die Merkmalszuordnung fragt — und wenn niemand da ist, muss sie anhalten
    wie jeder andere Fehler auch.

    Sie stand außerhalb des Fehler-Fangs: die ``AmbiguityError`` flog aus
    ``evaluate`` heraus, statt ein Befund zu werden. Wer keinen Frage-Dialog
    hat — die Kommandozeile, die Fernsteuerung, der Agent —, bekam eine
    Ausnahme und einen leeren Prüfbericht, statt zu erfahren, welche zwei
    Bohrungen gemeint sein könnten.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Aufbau",
        [
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 30.0}),
            OperationDraft(op="hollow_object", inputs=("obj_1",), params={"wall": 2.0}),
        ],
    )
    History(project.document).apply(
        "Elefantenfuß",
        [OperationDraft(op="compensate_first_layer", inputs=("obj_1",), params={})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert not result.complete, "raten wäre schlimmer, aber die Auswertung gibt es weiter"
    codes = {finding.code for finding in result.scene.report.findings}
    assert any("Ambiguity" in code for code in codes), codes


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
        doc=_("Testfassung."),
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
